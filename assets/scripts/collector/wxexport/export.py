"""Render decrypted message databases into readable per-conversation text.

Content model (WeChat 4.x):
  * each chat is a table Msg_<md5(username)>, sharded across message_0..N.db
  * message_content is "sender_wxid:\n<payload>"; sender also resolvable via Name2Id
  * payload is plain text for type 1, XML for media/app messages
  * rows flagged by WCDB_CT_* are zstd-compressed BLOBs (magic 28 b5 2f fd)
"""
import csv
import datetime
import glob
import html
import json
import os
import re
import sqlite3

import zstandard

ZMAGIC = b"\x28\xb5\x2f\xfd"
_DCTX = zstandard.ZstdDecompressor()

TYPE_LABEL = {3: "[图片]", 34: "[语音]", 43: "[视频]", 47: "[动画表情]", 48: "[位置]",
              42: "[名片]", 50: "[音视频通话]", 51: "[视频号]", 63: "[视频]", 66: "[分享]"}


def _bdecode(raw):
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    b = bytes(raw)
    if b[:4] == ZMAGIC:
        try:
            b = _DCTX.decompress(b)
        except Exception:
            try:
                b = _DCTX.decompressobj().decompress(b)
            except Exception:
                pass
    return b.decode("utf-8", "replace")


def _safe(s, n=60):
    s = re.sub(r'[/\\:\*\?"<>\|\n\r\t]', "_", s or "")
    return (s[:n] or "unknown").strip()


def _fmt(ts):
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _strip_prefix(s):
    return re.sub(r"^[0-9A-Za-z_\-@.]+:\n", "", s, count=1)


def _tag(s, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), s, re.S)
    return m.group(1).strip() if m else ""


def _render(base_type, content):
    c = _strip_prefix(content or "")
    if base_type == 1:
        return c
    if base_type == 10000:
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
        return "[系统] " + t[:200]
    if base_type == 49:
        typ = _tag(c, "type")
        label = {"6": "[文件]", "5": "[链接]", "57": "[引用]", "53": "[引用]",
                 "2000": "[转账]", "51": "[视频号]"}.get(typ, "[链接/文件]")
        extra = " ".join(x for x in (_tag(c, "title"), _tag(c, "des")) if x)
        return (label + " " + extra).strip()
    if base_type == 3:
        return "[图片]"
    if base_type == 47:
        return "[动画表情]"
    return TYPE_LABEL.get(base_type, "[类型%d]" % base_type)


def run(decrypted_dir, namemap_path, me_wxid, out_dir):
    nm = json.load(open(namemap_path))
    NAMES, MD5MAP = nm["names"], nm["md5map"]

    def disp(u):
        return NAMES.get(u, u) if u else ""

    txt_dir = os.path.join(out_dir, "text")
    os.makedirs(txt_dir, exist_ok=True)

    # gather Msg_ tables across all message shards
    convs = {}
    for f in sorted(glob.glob(os.path.join(decrypted_dir, "message", "message_[0-9]*.db"))):
        con = sqlite3.connect(f)
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"):
            convs.setdefault(t[4:], []).append((f, t))
        con.close()

    index = []
    for md5, parts in convs.items():
        user = MD5MAP.get(md5, "")
        name = disp(user) or ("(unknown_%s)" % md5[:10])
        is_group = user.endswith("@chatroom")
        msgs = []
        for f, t in parts:
            con = sqlite3.connect(f)
            con.text_factory = bytes
            id2user = {}
            try:
                for rid, uname in con.execute("SELECT rowid, user_name FROM Name2Id"):
                    id2user[rid] = _bdecode(uname)
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
                    base = (lt or 0) & 0xFFFFFFFF
                    su = id2user.get(sid, "")
                    content = _bdecode(mc)
                    if su == me_wxid:
                        who = "我"
                    elif su:
                        who = disp(su)
                    else:
                        m = re.match(r"^([0-9A-Za-z_\-@.]+):\n", content)
                        who = disp(m.group(1)) if m else "对方"
                    msgs.append((ct or 0, who, _render(base, content)))
            except Exception:
                pass
            con.close()
        if not msgs:
            continue
        msgs.sort(key=lambda x: x[0])
        fn = "%s__%s.txt" % (_safe(name), md5[:8])
        with open(os.path.join(txt_dir, fn), "w") as fh:
            fh.write("# %s  (%s)  %d 条消息\n" % (name, "群聊" if is_group else "对话", len(msgs)))
            fh.write("# %s ~ %s\n\n" % (_fmt(msgs[0][0]), _fmt(msgs[-1][0])))
            for ct, who, text in msgs:
                fh.write("[%s] %s: %s\n" % (_fmt(ct), who, text))
        index.append({"name": name, "type": "群聊" if is_group else "对话",
                      "count": len(msgs), "first": _fmt(msgs[0][0]),
                      "last": _fmt(msgs[-1][0]), "file": "text/" + fn})

    index.sort(key=lambda r: r["count"], reverse=True)
    with open(os.path.join(out_dir, "index.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "type", "count", "first", "last", "file"])
        w.writeheader()
        for r in index:
            w.writerow(r)
    _write_html(index, os.path.join(out_dir, "index.html"))
    total = sum(r["count"] for r in index)
    return len(index), total


def _write_html(index, path):
    with open(path, "w") as fh:
        fh.write("<!doctype html><meta charset=utf-8><title>WeChat export</title>")
        fh.write("<style>body{font-family:-apple-system,sans-serif;max-width:900px;"
                 "margin:2em auto;padding:0 1em}table{border-collapse:collapse;width:100%}"
                 "td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}"
                 "th{position:sticky;top:0;background:#fff}a{color:#0a7;text-decoration:none}"
                 "tr:hover{background:#f6f6f6}</style>")
        fh.write("<h1>WeChat export</h1><p>%d conversations · %d messages</p>" %
                 (len(index), sum(r["count"] for r in index)))
        fh.write("<table><tr><th>Conversation</th><th>Type</th><th>Messages</th><th>Range</th></tr>")
        for r in index:
            fh.write("<tr><td><a href='%s'>%s</a></td><td>%s</td><td>%d</td><td>%s ~ %s</td></tr>" %
                     (html.escape(r["file"]), html.escape(r["name"]), r["type"], r["count"],
                      r["first"][:10], r["last"][:10]))
        fh.write("</table>")
