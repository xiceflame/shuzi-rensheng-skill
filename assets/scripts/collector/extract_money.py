#!/usr/bin/env python3
"""
结构化提取关注会话里的「钱」相关消息：转账、红包、收款、支付。

⚠️ **本数据只是佐证材料，不是账目依据。**
微信转账消息存在以下歧义，**单看消息无法分辨**：
  1. 同一笔转账在双方视角各生成一条消息（金额相同）
  2. 「转账后又被退回」也会产生一条同金额消息
  3. 到期未领取的**自动退款**同样如此
**权威依据是「微信支付对账单」**（微信 → 我 → 服务 → 钱包 → 账单 → 下载账单）。
本文件用于**交叉印证**，差额与结论必须以对账单为准。

这些内容在 message_content 的 XML 里（local_type=49 的 appmsg 子类型，
或 2000=转账、2001=红包 等）。提取成表格，供财务对账参考(**注释层**)。

定位(2026-09 起,见 references/finance-integration.md):本脚本的产物
**只作为注释/佐证层**,用于把转账消息 join 回官方账单生成的 ledger 分录;
**不再作为账本数据源**——账本数字一律来自 raw/bills/ 官方账单。

输出：
  ~/wechat-export/focus-money/YYYY-MM.tsv   （时间/会话/发言人/类型/金额/备注/原文摘要）
  以及汇总 ~/wechat-export/focus-money/_summary.txt
"""
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from focus_match import matcher  # noqa: E402

WORK = os.path.expanduser("~/wx-export")
DEC = os.path.join(WORK, "decrypted")
NAMEMAP = os.path.join(WORK, "namemap.json")
OUT = os.path.join(WORK, "focus-money")

MONEY_HINTS = ("<wcpayinfo>", "转账", "红包", "收款", "已收钱", "微信支付",
               "transfer", "paymsg", "<type>2000</type>", "<type>2001</type>")


def _tag(s, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), s, re.S)
    return m.group(1).strip() if m else ""


def classify(x):
    if "<type>2000</type>" in x or "转账" in x:
        return "转账"
    if "<type>2001</type>" in x or "红包" in x:
        return "红包"
    if "收款" in x or "已收钱" in x:
        return "收款"
    if "微信支付" in x or "wcpayinfo" in x:
        return "支付"
    return "其他"


def amount_of(x):
    """精确取金额。
    优先 <totalfee>（分）；其次 <feedesc> 的 CDATA（如 ￥72.00）；
    再次 des 里的「收到转账72.00元」。红包金额本就保密 —— 返回 None。
    """
    m = re.search(r"<totalfee>(\d+)</totalfee>", x)
    if m:
        try:
            return int(m.group(1)) / 100.0
        except ValueError:
            pass
    m = re.search(r"<feedesc><!\[CDATA\[([^\]]*)\]\]></feedesc>", x)
    if not m:
        m = re.search(r"<feedesc>([^<]{0,40})</feedesc>", x)
    if m and m.group(1).strip():
        m2 = re.search(r"([\d]+(?:\.\d+)?)", m.group(1))
        if m2:
            return float(m2.group(1))
    m = re.search(r"收到转账([\d.]+)元", x)
    if m:
        return float(m.group(1))
    m = re.search(r"<title><!\[CDATA\[([^\]]{0,30})\]\]></title>", x)
    return None


def main():
    focus = matcher()
    nm = json.load(open(NAMEMAP, encoding="utf-8"))
    NAMES, MD5MAP = nm["names"], nm["md5map"]

    def disp(u):
        return NAMES.get(u, u) if u else ""

    targets = {}
    for _md5, u in MD5MAP.items():
        n = disp(u)
        if u and focus(n):
            targets[u] = n
    by_md5 = {hashlib.md5(u.encode()).hexdigest(): u for u in targets}

    os.makedirs(OUT, exist_ok=True)
    rows = []
    for db in sorted(glob.glob(os.path.join(DEC, "message", "message_[0-9]*.db"))):
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        con.text_factory = bytes
        id2user = {}
        try:
            for rid, uname in con.execute("SELECT rowid, user_name FROM Name2Id"):
                id2user[rid] = uname.decode("utf-8", "replace")
        except Exception:
            pass
        tables = [(r[0].decode() if isinstance(r[0], bytes) else r[0])
                  for r in con.execute(
                      "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
        for t in tables:
            user = by_md5.get(t[4:])
            if not user:
                continue
            cname = targets[user]
            try:
                cur = con.execute(
                    'SELECT create_time, real_sender_id, message_content, '
                    'WCDB_CT_message_content FROM "%s" WHERE message_content IS NOT NULL' % t)
                while True:
                    r = cur.fetchone()
                    if r is None:
                        break
                    ct, sid, mc, ctf = r
                    if mc is None:
                        continue
                    raw = bytes(mc) if isinstance(mc, (bytes, bytearray)) else str(mc).encode()
                    if raw[:4] == b"\x28\xb5\x2f\xfd":
                        try:
                            import zstandard as zstd
                            raw = zstd.ZstdDecompressor().decompress(raw)
                        except Exception:
                            continue
                    x = raw.decode("utf-8", "replace")
                    if not any(h in x for h in MONEY_HINTS):
                        continue
                    who = disp(id2user.get(sid, "")) or "?"
                    amt = amount_of(x)
                    rows.append((int(ct or 0), cname, who, classify(x),
                                 ("%.2f" % amt) if amt is not None else ("(红包金额未知)" if classify(x) == "红包" else ""),
                                 _tag(x, "title") or _tag(x, "des") or "",
                                 re.sub(r"<[^>]+>", " ", x)[:120].strip()))
            except Exception:
                continue
        con.close()

    # 标记「可能配对」：同会话 + 同金额 + 48 小时内出现多次
    from collections import defaultdict as _dd
    import datetime as _dt
    buckets = _dd(list)
    for i, r in enumerate(rows):
        if r[4] and r[4][0].isdigit():
            buckets[(r[1], r[4])].append(i)
    pair_flag = {}
    for _k, idxs in buckets.items():
        if len(idxs) < 2:
            continue
        ts = sorted(rows[i][0] for i in idxs)
        for a, b in zip(ts, ts[1:]):
            if b - a <= 48 * 3600:
                for i in idxs:
                    pair_flag[id(rows[i])] = "⚠️可能配对(转账/收款确认/退回)"
                break

    bymonth = defaultdict(list)
    for r in rows:
        ym = __import__("datetime").datetime.fromtimestamp(r[0]).strftime("%Y-%m")
        bymonth[ym].append(r)

    total = 0.0
    for ym, rs in sorted(bymonth.items()):
        rs.sort()
        with open(os.path.join(OUT, "%s.tsv" % ym), "w", encoding="utf-8") as f:
            f.write("时间\t会话\t发言人\t类型\t金额\t标题\t备注\t摘要\n")
            for r in rs:
                note = pair_flag.get(id(r), "")
                f.write("\t".join(
                    __import__("datetime").datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S")
                    if i == 0 else str(v) for i, v in enumerate(r)) + "\t" + note + "\n")
                try:
                    total += float(r[4])
                except (ValueError, TypeError):
                    pass  # 红包金额未知等
    with open(os.path.join(OUT, "_summary.txt"), "w", encoding="utf-8") as f:
        f.write("关注会话「钱」相关消息汇总\n")
        f.write("=" * 46 + "\n")
        f.write("⚠️ 佐证材料，不是账目依据。权威来源：微信支付对账单。\n")
        f.write("   同金额重复可能是「收款确认」或「退回/自动退款」，单看消息无法区分。\n")
        f.write("=" * 46 + "\n\n")
        f.write("总计 %d 条；有金额的合计 %.2f 元\n\n" % (len(rows), total))
        for ym, rs in sorted(bymonth.items(), reverse=True):
            f.write("- %s: %d 条\n" % (ym, len(rs)))
    print("[money] 提取 %d 条（含金额合计 %.2f）-> %s" % (len(rows), total, OUT))


if __name__ == "__main__":
    main()
