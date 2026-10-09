#!/usr/bin/env python3
"""
只导出「关注列表」里的会话，且只取最近 N 天的消息。

为什么这样省：
  - 解密省不了（微信按时间切分片，每个分片混着所有会话）
  - 但渲染省得很多：226 万条 → 只渲染十几个会话的最近 N 天，通常几千条

关注列表：~/.wxexport/focus.txt（每行一个名称/关键词，支持部分匹配）
输出：~/wx-export/focus/<会话名>.txt + _summary.txt

用法: python3 export_focus.py [天数，默认 7]
"""
import glob
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wxexport import export as E          # noqa: E402
from wxexport import nameindex, detect    # noqa: E402

WORK = os.path.expanduser("~/wx-export")
DEC = os.path.join(WORK, "decrypted")
NAMEMAP = os.path.join(WORK, "namemap.json")
DATA = os.path.join(WORK, "xwechat_files")
OUT = os.path.join(WORK, "focus")
FOCUS_FILE = os.path.expanduser("~/.wxexport/focus.txt")

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from focus_match import matcher as _mk_matcher
except ImportError:
    _mk_matcher = None


def load_focus():
    """返回匹配函数；无名单返回 None。"""
    if _mk_matcher is None:
        return None
    if not os.path.exists(FOCUS_FILE):
        return None
    return _mk_matcher()


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    focus = load_focus()
    if focus is None:
        print("[focus] 未配置 %s，退出" % FOCUS_FILE)
        return

    me = detect.find_account_wxid(DATA)
    nameindex.build(DEC, NAMEMAP)
    nm = json.load(open(NAMEMAP))
    NAMES, MD5MAP = nm["names"], nm["md5map"]

    def disp(u):
        return NAMES.get(u, u) if u else ""

    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
    os.makedirs(OUT, exist_ok=True)

    # 收集所有 Msg_ 表（跨分片）
    convs = {}
    for f in sorted(glob.glob(os.path.join(DEC, "message", "message_[0-9]*.db"))):
        con = sqlite3.connect(f)
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"):
            convs.setdefault(t[4:], []).append((f, t))
        con.close()

    summary = []
    for md5, parts in convs.items():
        user = MD5MAP.get(md5, "")
        name = disp(user) or ""
        if not name:
            continue
        if not focus(name):
            continue
        is_group = user.endswith("@chatroom")
        msgs = []
        for f, t in parts:
            con = sqlite3.connect(f)
            con.text_factory = bytes
            id2user = {}
            try:
                for rid, uname in con.execute("SELECT rowid, user_name FROM Name2Id"):
                    id2user[rid] = E._bdecode(uname)
            except Exception:
                pass
            try:
                cur = con.execute(
                    'SELECT local_type, real_sender_id, create_time, message_content FROM "%s"' % t)
                while True:
                    r = cur.fetchone()
                    if r is None:
                        break
                    lt, sid, ct, mc = r
                    ct = ct or 0
                    if ct < cutoff:
                        continue
                    base = (lt or 0) & 0xFFFFFFFF
                    su = id2user.get(sid, "")
                    content = E._bdecode(mc)
                    if su == me:
                        who = "我"
                    elif su:
                        who = disp(su)
                    else:
                        m = re.match(r"^([0-9A-Za-z_\-@.]+):\n", content)
                        who = disp(m.group(1)) if m else "对方"
                    msgs.append((ct, who, E._render(base, content)))
            except Exception:
                pass
            con.close()
        if not msgs:
            continue
        msgs.sort(key=lambda x: x[0])
        fn = "%s__%s.txt" % (E._safe(name), md5[:8])
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as fh:
            fh.write("# %s  (%s)  最近%d天 %d 条\n" % (
                name, "群聊" if is_group else "对话", days, len(msgs)))
            fh.write("# %s ~ %s\n\n" % (E._fmt(msgs[0][0]), E._fmt(msgs[-1][0])))
            for ct, who, text in msgs:
                fh.write("[%s] %s: %s\n" % (E._fmt(ct), who, text))
        summary.append((name, len(msgs), E._fmt(msgs[0][0]), E._fmt(msgs[-1][0]), fn))

    summary.sort(key=lambda x: -x[1])
    with open(os.path.join(OUT, "_summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("关注会话（最近 %d 天）\n\n" % days)
        for name, n, a, b, fn in summary:
            fh.write("- %s: %d 条 (%s ~ %s) -> %s\n" % (name, n, a, b, fn))
    print("[focus] 导出 %d 个关注会话，共 %d 条消息 -> %s" % (
        len(summary), sum(s[1] for s in summary), OUT))


if __name__ == "__main__":
    main()
