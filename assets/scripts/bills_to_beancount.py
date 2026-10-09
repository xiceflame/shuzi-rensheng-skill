#!/usr/bin/env python3
"""
bills_to_beancount.py — 微信支付/支付宝官方账单 CSV → beancount 分录

方案 A 的转换器(见 references/finance-integration.md):
  raw/bills/<source>/<YYYY-MM>/xxx.csv  →  ledger/<source>/<YYYY-MM>.beancount

设计要点
- **交易单号是唯一主键**:对照 ledger/seen.json 与已有 .beancount 文件里的
  wx_txid/alipay_txid 元数据去重,重复行直接跳过(官方账单重导也不会重复记账);
- **规则优先,LLM 兜底**:rules.json 命中 → 直接归类;未命中 → Expenses:FIXME
  + #FIXME 标签,留给人工/agent 确认后固化进 rules.json;
- 输出即落盘前先语法自检(装了 beancount 包则调用 bean-check 逻辑校验文件);
- 容忍 utf-8 / utf-8-sig / gbk / utf-16 编码与账单头部元信息行。

用法
  python3 bills_to_beancount.py <账单.csv> --source wechat  --ledger <vault>/ledger
  python3 bills_to_beancount.py <账单.csv> --source alipay --ledger <vault>/ledger --dry-run

外部依赖(可选):pip install beancount   # 无则跳过最终校验,仅告警
"""
import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import datetime

DEFAULT_RULES = {
    "rules": [
        # {"match": "关键词(在 交易对方/商品说明 里找)", "account": "Expenses:Food"}
    ],
    "default_expense": "Expenses:FIXME",
    "default_income": "Income:Misc",
    "default_neutral_other": "Equity:Uncategorized",
    "asset_map": {
        "零钱通": "Assets:WeChat:Fund",
        "零钱": "Assets:WeChat:Balance",
        "余额宝": "Assets:Alipay:Fund",
        "余额": "Assets:Alipay:Balance",
    },
    "asset_default": {"wechat": "Assets:WeChat:Balance", "alipay": "Assets:Alipay:Balance"},
    "bank_fallback": "Assets:Bank:Default",
}

# 每个数据源的列映射:以"表头行第一个字段"识别
SOURCES = {
    "wechat": {
        "header_start": "交易时间",
        "columns": ["交易时间", "交易类型", "交易对方", "商品", "收/支", "金额(元)",
                    "支付方式", "当前状态", "交易单号", "商户单号", "备注"],
        "txid": "交易单号", "meta_key": "wx_txid",
    },
    "alipay": {
        "header_start": "交易时间",
        "columns": ["交易时间", "交易分类", "交易对方", "对方账号", "商品说明", "收/支",
                    "金额", "收/付款方式", "交易状态", "交易订单号", "商家订单号", "备注"],
        "txid": "交易订单号", "meta_key": "alipay_txid",
    },
}


def read_csv_rows(path):
    """容错解码 + 定位表头行,返回 (rows, colmap)。"""
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if text is None:
        sys.exit(f"[ERR] 无法解码 {path}(尝试过 utf-8/gbk/utf-16)")
    # 去掉 BOM 期零宽字符;按行找表头(交易时间,...)
    lines = text.splitlines()
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("交易时间") and "," in ln:
            header_idx = i
            break
    if header_idx is None:
        sys.exit("[ERR] 未找到表头行(应以「交易时间」开头)——确认这是官方账单明细 CSV")
    header = next(csv.reader([lines[header_idx]]))
    header = [h.strip().lstrip("'").strip() for h in header]
    rows = []
    for ln in lines[header_idx + 1:]:
        if not ln.strip() or set(ln.strip()) <= {"-", " "} or "总" in ln[:4]:
            continue
        vals = next(csv.reader([ln]))
        if len(vals) < len(header):
            continue
        rows.append(dict(zip(header, [v.strip() for v in vals])))
    return rows, set(header)


def detect_source(header_cols):
    if "商户单号" in header_cols or "支付方式" in header_cols:
        return "wechat"
    if "商家订单号" in header_cols or "收/付款方式" in header_cols:
        return "alipay"
    return None


def norm_amount(s):
    s = re.sub(r"[¥￥,，\s]", "", s or "")
    return float(s) if s else None


def pick(row, *names):
    for n in names:
        if n in row and row[n] not in ("", "/"):
            return row[n]
    return ""


def asset_account(row, source, rules):
    method = pick(row, "支付方式", "收/付款方式")
    for key in sorted(rules["asset_map"], key=len, reverse=True):  # 长词优先(零钱通>零钱)
        if key in method:
            return rules["asset_map"][key], method
    if "银行" in method or "卡" in method:
        return rules["bank_fallback"], method
    return rules["asset_default"].get(source, "Assets:Cash"), method or "默认"


def rule_account(counterparty, product, rules):
    hay = f"{counterparty} {product}"
    for r in rules.get("rules", []):
        if r.get("match") and r["match"] in hay:
            return r["account"], False
    return None, True


def existing_txids(ledger_dir):
    """扫描已有分录文件里的 txid 元数据(双保险,seen.json 之外)。"""
    ids, includes = set(), set()
    for root, _, files in os.walk(ledger_dir):
        for f in files:
            if not f.endswith(".beancount"):
                continue
            p = os.path.join(root, f)
            includes.add(os.path.relpath(p, ledger_dir))
            for m in re.finditer(r'(?:wx_txid|alipay_txid):\s*"?([\w\-]+)"?', open(p, encoding="utf-8").read()):
                ids.add(m.group(1))
    return ids, includes


def fmt_entry(d, payee, narr, txid_key, txid, status, method, postings, fixme):
    tag = " #FIXME" if fixme else ""
    meta = [f'  {txid_key}: "{txid}"']
    if status:
        meta.append(f'  status: "{status}"')
    if method:
        meta.append(f'  pay_method: "{method}"')
    lines = [f'{d} * "{payee}" "{narr}"{tag}'] + meta
    lines += [f"  {acct}  {amt:+.2f} CNY" for acct, amt in postings]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("--source", choices=["wechat", "alipay"], default=None)
    ap.add_argument("--ledger", default=os.path.expanduser("~/数字人生/ledger"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows, cols = read_csv_rows(args.csv_file)
    source = args.source or detect_source(cols)
    if not source:
        sys.exit("[ERR] 识别不出账单类型,请用 --source wechat|alipay 指定")
    spec = SOURCES[source]

    os.makedirs(args.ledger, exist_ok=True)
    rules_path = os.path.join(args.ledger, "rules.json")
    rules = DEFAULT_RULES if not os.path.exists(rules_path) else \
        {**DEFAULT_RULES, **json.load(open(rules_path, encoding="utf-8"))}
    seen_path = os.path.join(args.ledger, "seen.json")
    seen = set(json.load(open(seen_path, encoding="utf-8"))) if os.path.exists(seen_path) else set()
    disk_ids, _ = existing_txids(args.ledger)

    out = {}       # month -> [entries]
    n_new = n_dup = n_skip = n_fixme = 0
    for row in rows:
        txid = row.get(spec["txid"], "")
        amt = norm_amount(pick(row, "金额(元)", "金额"))
        if not txid or amt is None:
            n_skip += 1
            continue
        if txid in seen or txid in disk_ids:
            n_dup += 1
            continue
        d = (row.get("交易时间") or "")[:10].replace("/", "-")
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            n_skip += 1
            continue
        direction = pick(row, "收/支")  # 收入 / 支出 / 不计收支 或 /
        if "不计" in direction or direction in ("/", ""):
            dir_kind = "neutral"      # 「不计收支」同时含"收""支"二字,必须先判
        elif "收" in direction:
            dir_kind = "income"
        elif "支" in direction:
            dir_kind = "expense"
        else:
            dir_kind = "neutral"
        cp = pick(row, "交易对方", "对方")
        prod = pick(row, "商品", "商品说明")
        status = pick(row, "当前状态", "交易状态")
        asset, method = asset_account(row, source, rules)
        acct, fixme = rule_account(cp, prod, rules)
        if dir_kind == "income":
            inc = acct or rules["default_income"]
            postings = [(asset, amt), (inc, -amt)]
        elif dir_kind == "expense":
            exp = acct or rules["default_expense"]
            fixme = fixme or exp.endswith("FIXME")
            postings = [(exp, amt), (asset, -amt)]
        else:  # 不计收支:零钱↔银行卡/理财等中性流水
            postings = [(asset, -amt), (rules["default_neutral_other"], amt)]
            fixme = True
        n_fixme += 1 if fixme else 0
        out.setdefault(d[:7], []).append(
            fmt_entry(d, cp[:40] or "(对方未知)", (prod or row.get("交易类型", ""))[:60],
                      spec["meta_key"], txid, status, method, postings, fixme))
        seen.add(txid)
        n_new += 1

    print(f"[{source}] 新增 {n_new} 笔(其中待分类 FIXME {n_fixme}) | 重复跳过 {n_dup} | 无效跳过 {n_skip}")
    if args.dry_run:
        for m, es in sorted(out.items()):
            print(f"--- {m} ({len(es)} 笔) ---")
            print("".join(es)[:800] + ("..." if sum(map(len, es)) > 800 else ""))
        return

    main_file = os.path.join(args.ledger, "main.beancount")
    for m, es in sorted(out.items()):
        rel = f"{source}/{m}.beancount"
        path = os.path.join(args.ledger, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            if os.path.getsize(path) if os.path.exists(path) else 0:
                f.write("\n")
            f.write(f";; +{len(es)} 笔,导入于 {datetime.now():%F %T}\n")
            f.write("".join(es))
        # main.beancount 自动补 include(只增不改)
        if os.path.exists(main_file):
            cur = open(main_file, encoding="utf-8").read()
            if f'"{rel}"' not in cur:
                with open(main_file, "a", encoding="utf-8") as f:
                    f.write(f'include "{rel}"\n')
    json.dump(sorted(seen), open(seen_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"已写入 {args.ledger}/{source}/ 共 {len(out)} 个月份文件;seen.json 更新({len(seen)} 单号)")

    # 语法校验(装了 beancount 才做;失败不回滚,提示人工处理)
    try:
        from beancount import loader
        _, errors, _ = loader.load_file(main_file if os.path.exists(main_file) else args.ledger)
        if errors:
            print(f"[WARN] bean-check 报 {len(errors)} 个错误,请检查:")
            for e in errors[:5]:
                print("   ", e)
        else:
            print("bean-check 通过 ✓")
    except ImportError:
        print("[提示] 未安装 beancount 包,跳过最终校验(pip install beancount 后可启用)")


if __name__ == "__main__":
    main()
