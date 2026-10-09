#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把「关注会话」近 N 年（默认 3 年）的聊天记录导出成**可向量化的 Markdown**。

为什么：微信原始数据不在 vault 里、没有 frontmatter，qkb 索引不到。
这个脚本把它切成「每个会话 × 每个月」一个 .md，带规范 frontmatter，
放进 wiki/chatlogs/，让 qkb 能建索引做语义检索。

并把语音转写（focus-voice-text/）按时间合并进对应月份。

用法: python3 export_searchable.py [年数=3]
输出: ~/数字人生/wiki/chatlogs/<会话名>/<YYYY-MM>.md
"""
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from focus_match import matcher  # noqa: E402

WORK = os.path.expanduser("~/wx-export")
DEC = os.path.join(WORK, "decrypted")
NAMEMAP = os.path.join(WORK, "namemap.json")
VOICE = os.path.join(WORK, "focus-voice-text")
OUT = os.path.join(WORK, "searchable")   # 先落到 wx-export，再传到 vault

MSG_TYPES = {1: "文本", 3: "图片", 34: "语音", 43: "视频", 47: "表情",
             48: "位置", 49: "链接/文件", 50: "通话", 10000: "系统"}
TAG = re.compile(r"<[^>]+>")


def safe(s):
    return re.sub(r'[/\\:*?"<>|\s]', "_", s or "")[:50] or "unknown"


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    cutoff = int((datetime.now() - timedelta(days=365 * years)).timestamp())
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
    print("[export] 关注会话 %d 个，范围：近 %d 年" % (len(targets), years))

    # 收集：(会话名, 月份) -> [(时间戳, 发言人, 类型, 文本)]
    buckets = defaultdict(list)
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
                    'SELECT create_time, real_sender_id, local_type, message_content, '
                    'WCDB_CT_message_content FROM "%s" WHERE create_time >= ?' % t, (cutoff,))
                while True:
                    r = cur.fetchone()
                    if r is None:
                        break
                    ct, sid, lt, mc, ctf = r
                    if mc is None:
                        continue
                    raw = bytes(mc) if isinstance(mc, (bytes, bytearray)) else str(mc).encode()
                    if raw[:4] == b"\x28\xb5\x2f\xfd":
                        try:
                            import zstandard as zstd
                            raw = zstd.ZstdDecompressor().decompress(raw)
                        except Exception:
                            continue
                    txt = raw.decode("utf-8", "replace")
                    base = (lt or 0) & 0xFFFFFFFF
                    if base == 1:
                        # 群聊前缀 "wxid_xxx:\n"
                        m = re.match(r"^([0-9A-Za-z_\-@.]+):\n", txt)
                        if m:
                            txt = txt[m.end():]
                        body = txt.strip()
                    elif base == 34:
                        body = "[语音]"
                    elif base in MSG_TYPES:
                        body = "[%s]" % MSG_TYPES[base]
                    else:
                        body = "[类型%d]" % base
                    if not body:
                        continue
                    who = disp(id2user.get(sid, "")) or "对方"
                    ym = datetime.fromtimestamp(ct or 0).strftime("%Y-%m")
                    buckets[(cname, ym)].append((int(ct or 0), who, base, body))
            except Exception:
                continue
        con.close()
        print("  扫描 %s" % os.path.basename(db))

    # 合并语音转写
    vcount = 0
    for vf in glob.glob(os.path.join(VOICE, "*.txt")):
        cname = os.path.basename(vf)[:-4]
        if cname not in targets.values():
            continue
        for line in open(vf, encoding="utf-8", errors="replace"):
            m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*([^:]*):\s*(.*)", line.strip())
            if not m:
                continue
            try:
                ts = int(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                continue
            buckets[(cname, m.group(1)[:7])].append(
                (ts, m.group(2).strip() or "?", 1, "[语音] " + m.group(3).strip()))
            vcount += 1
    print("[export] 合并语音转写 %d 条" % vcount)

    # 写文件
    n_files = 0
    n_msgs = 0
    for (cname, ym), items in buckets.items():
        items.sort(key=lambda x: x[0])
        d = os.path.join(OUT, safe(cname))
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "%s.md" % ym)
        with open(p, "w", encoding="utf-8") as f:
            f.write("---\nid: %s\ncontext: %s\ncreated: %s-01\ntags: [聊天记录, %s]\n---\n\n"
                    % (uuid.uuid4(), cname, ym, safe(cname)))
            f.write("# %s · %s（%d 条）\n\n" % (cname, ym, len(items)))
            for ts, who, _b, body in items:
                f.write("[%s] %s: %s\n" % (
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), who, body))
        n_files += 1
        n_msgs += len(items)

    print("[export] 写出 %d 个文件，共 %d 条消息 -> %s" % (n_files, n_msgs, OUT))


if __name__ == "__main__":
    main()
