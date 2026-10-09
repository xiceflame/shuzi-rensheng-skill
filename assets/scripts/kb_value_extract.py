#!/usr/bin/env python3
"""知识增值提取（每周）——从已入库数据里反向提炼「该沉淀却没沉淀」的东西。

产出两份清单（写进 wiki/outputs/增值提取-<今天>.md，由 daily agent 消费）：
  ① 高提及无页人名 —— 在 raw/chatlogs 里发言很多、却没有 wiki/people/<名>.md 的人
     （2026-09-12 的「杨斌」就是这么漏的：673 条消息、66 处提及、无页）
  ② 未闭环计划 —— journal 里标了「**计划**」、但已超 7 天的行
     （CLAUDE.md 规则 11：计划要回看——落成改「事实」，未落实改「未落实」）

纯脚本、无 LLM；建页/回看的判断由 automation（daily）完成。
"""
import os
import re
import glob
import shutil
import time
import uuid
from collections import Counter

VAULT = os.path.expanduser("~/数字人生")
PEOPLE = os.path.join(VAULT, "wiki", "people")
CHATLOGS = os.path.join(VAULT, "raw", "chatlogs")
JOURNAL = os.path.join(VAULT, "wiki", "journal")
OUTDIR = os.path.join(VAULT, "wiki", "outputs")
PLAN_AFTER_DAYS = 7
TOP_N = 15

NON_PERSON = {"我", "系统", "unknown", "Unknown", "对方", "[图片]", "[链接]", "[语音]"}
WORKER_ROOTS = [os.path.expanduser(p) for p in os.environ.get(
    "SHUZI_WORKER_ROOTS", "~/.openclaw/workspaces ~/clawd").split()]
SWEEP_OUT = os.path.join(VAULT, "raw", "media", "worker-deliverables")
FM_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "shuzi-rensheng.worker-deliverables")


def _norm(s):
    s = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u20E3️]", "", s)
    return re.sub(r"[\s_\-～~]", "", s)


def people_names():
    names = {}
    for f in glob.glob(os.path.join(PEOPLE, "*.md")):
        base = os.path.basename(f)[:-3]
        names[base] = True
        try:
            head = open(f, encoding="utf-8").read(1500)
        except Exception:
            continue
        m = re.search(r"^alias:\s*(.+)$", head, re.M)
        if m:
            for a in re.split(r"[/·、,，]", m.group(1)):
                a = a.strip().strip("（）()「」")
                if a:
                    names[a] = True
        m = re.search(r"^name:\s*(.+)$", head, re.M)
        if m:
            names[m.group(1).strip()] = True
    # 归一化变体（去 emoji/空格/符号），用于包含式匹配
    names["_norm"] = {_norm(k) for k in list(names) if _norm(k)}
    return names


def is_known(name, known):
    n = _norm(name)
    if not n:
        return True
    if n in known["_norm"]:
        return True
    for k in known["_norm"]:
        if len(k) >= 3 and (k in n or n in k):
            return True
    return False


def speakers():
    """发言者 → (条数, 最早, 最晚, 出现过的会话)"""
    cnt = Counter()
    first, last, conv = {}, {}, Counter()
    pat = re.compile(r"^\[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*([^:：]{1,40}):")
    for f in glob.glob(os.path.join(CHATLOGS, "*", "*.md")):
        conv_name = os.path.basename(os.path.dirname(f))
        try:
            for line in open(f, encoding="utf-8", errors="ignore"):
                m = pat.match(line)
                if not m:
                    continue
                d, who = m.group(1), m.group(2).strip()
                if who in NON_PERSON or len(who) < 2:
                    continue
                cnt[who] += 1
                conv[who] += 1
                first.setdefault(who, d)
                if d >= last.get(who, ""):
                    last[who] = d
        except Exception:
            continue
    return cnt, first, last, conv


def unclosed_plans():
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - PLAN_AFTER_DAYS * 86400))
    out, old_cnt = [], 0
    recent_cut = time.strftime("%Y-%m-%d", time.localtime(time.time() - 60 * 86400))
    for f in sorted(glob.glob(os.path.join(JOURNAL, "20*.md"))):
        d = os.path.basename(f)[:10]
        if d > cutoff:
            continue
        try:
            for line in open(f, encoding="utf-8", errors="ignore"):
                if "计划" in line and "｜" in line and "事实 + 计划" not in line:
                    if d >= recent_cut:
                        out.append((d, line.strip()[:220]))
                    else:
                        old_cnt += 1
        except Exception:
            continue
    return out, old_cnt



def sweep_deliverables():
    """⓪ 扫各 worker 的 deliverables/，未镜像的整包归档进 vault
    （规则 15 兜底：worker「可交付」≠「已沉淀」；.md 包上 frontmatter 使其可检索）"""
    added = []
    for root in WORKER_ROOTS:
        for d in sorted(glob.glob(os.path.join(root, "*", "deliverables", "*"))):
            if not os.path.isdir(d):
                continue
            agent = os.path.basename(os.path.dirname(os.path.dirname(d)))
            name = os.path.basename(d)
            dst = os.path.join(SWEEP_OUT, agent, name)
            if os.path.isdir(dst):
                continue  # 已镜像（幂等）
            os.makedirs(dst, exist_ok=True)
            for src_root, _, files in os.walk(d):
                rel = os.path.relpath(src_root, d)
                outdir = dst if rel == "." else os.path.join(dst, rel)
                os.makedirs(outdir, exist_ok=True)
                for fn in files:
                    src_file = os.path.join(src_root, fn)
                    dst_file = os.path.join(outdir, fn)
                    if fn.endswith(".md"):
                        try:
                            body = open(src_file, encoding="utf-8", errors="ignore").read()
                        except Exception:
                            continue
                        fm = (f"---\nid: {uuid.uuid5(FM_NS, os.path.relpath(dst_file, VAULT))}\n"
                              "context: 交付归档\n"
                              f"created: {time.strftime('%Y-%m-%d')}\n"
                              f"tags: [交付归档, {agent}]\n"
                              f"source_worker: {agent}\n"
                              f"source: \"{src_file}\"\n---\n\n")
                        open(dst_file, "w", encoding="utf-8").write(fm + body)
                    else:
                        shutil.copy2(src_file, dst_file)
            added.append(f"{agent}/{name}")
    return added


def main():
    mirrored = sweep_deliverables()
    known = people_names()
    cnt, first, last, conv = speakers()
    cands = [(n, c, first.get(n, "?"), last.get(n, "?")) for n, c in cnt.most_common()
             if not is_known(n, known) and c >= 20]
    os.makedirs(OUTDIR, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    dst = os.path.join(OUTDIR, f"增值提取-{today}.md")

    lines = [
        "---",
        f"id: {uuid.uuid5(uuid.NAMESPACE_DNS, 'value-extract-' + today)}",
        "context: 输出",
        f"created: {today}",
        "tags: [增值提取, 巡检]",
        "---", "",
        f"# 知识增值提取 · {today}", "",
        "> 由 `~/.wxexport/kb_value_extract.py` 生成（每周 automation `vault-value-extract`）。",
        "> ① 高提及无页人名 → daily 判断后建/补 `wiki/people/<名>.md`；",
        "> ② 未闭环计划 → 逐条回看：落成改「事实」、未落实改「未落实」、不确定列给主人。", "",
        f"## ① 高提及无页人名（{len(cands)} 个，按消息数排序，取前 {TOP_N}）", "",
        "| 人名 | 消息数 | 最早 | 最晚 | 建议 |",
        "|---|---|---|---|---|",
    ]
    for n, c, f1, l1 in cands[:TOP_N]:
        lines.append(f"| {n} | {c} | {f1} | {l1} | 待判断（注意与已建档人物别名区分） |")
    if not cands:
        lines.append("|（无）| | | | |")

    plans, old_cnt = unclosed_plans()
    lines += ["", f"## ② 未闭环计划（近 60 天 {len(plans)} 条；更早历史存量 {old_cnt} 条不逐条列出）", "",
              f"> 回看口径：落成→改「事实」；未落实→改「未落实」；历史存量不必逐条翻旧账。", ""]
    for d, l in plans[:60]:
        lines.append(f"- **{d}** {l}")
    if not plans:
        lines.append("-（无）")

    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if mirrored:
        print("新镜像交付物:", " | ".join(mirrored))
    print(f"报告: {dst}")
    print(f"① 无页人名 {len(cands)} 个（top: {', '.join(n for n,_,_,_ in cands[:5]) or '无'}）")
    print(f"② 未闭环计划 {len(plans)} 条")
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
