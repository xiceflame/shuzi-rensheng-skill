#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ChatGPT 网页聊天导入器：官方导出的 conversations.json → 可检索月度 md。

获取数据（人工，一次性）：ChatGPT 网页 → 设置 → 数据控制 → 导出数据
  → 邮箱收 zip → 解压 → 把 conversations.json 放到 ~/wechat-export/chatgpt-import/
落点：<vault>/raw/chat/chatgpt/<YYYY-MM>.md（frontmatter 可索引）
增量：按 conversation id 记录于 manifest，已处理的跳过。

用法: python3 chatgpt_export.py [conversations.json 路径]
"""
import glob
import json
import os
import re
import sys
import uuid
from datetime import datetime

VAULT = os.environ.get("SHUZI_VAULT", os.path.expanduser("~/数字人生"))
WORK = os.environ.get("SHUZI_WORK", os.path.expanduser("~/wechat-export"))
INBOX = os.path.join(WORK, "chatgpt-import")
MANIFEST = os.path.join(WORK, ".chatgpt-manifest.tsv")
MSG_CAP = 10_000


def fm(context, created, tags):
    return "---\nid: %s\ncontext: %s\ncreated: %s\ntags: [%s]\n---\n\n" % (
        str(uuid.uuid4()), context, created, ", ".join(tags))


def load_manifest():
    done = set()
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            done = set(x.strip() for x in f)
    return done


def parse_convs(path):
    with open(path, encoding="utf-8") as f:
        convs = json.load(f)
    done = load_manifest()
    n_conv = n_msg = 0
    by_month = {}
    for conv in convs:
        cid = conv.get("conversation_id") or conv.get("id") or ""
        if cid and cid in done:
            continue
        title = conv.get("title") or "未命名"
        ct = conv.get("create_time")
        messages = []
        mapping = conv.get("mapping") or {}
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            author = (msg.get("author") or {}).get("role")
            if author not in ("user", "assistant"):
                continue
            content = msg.get("content") or {}
            if content.get("content_type") not in ("text", "multimodal_text"):
                continue
            parts = content.get("parts") or []
            texts = [p for p in parts if isinstance(p, str) and p.strip()]
            if not texts:
                continue
            t = msg.get("create_time")
            try:
                dt = datetime.fromtimestamp(t) if t else None
            except Exception:
                dt = None
            for tx in texts:
                messages.append((dt, "用户" if author == "user" else "ChatGPT", tx.strip()))
        if not messages:
            continue
        messages.sort(key=lambda x: (x[0] is None, x[0]))
        anchor = next((dt for dt, _w, _t in messages if dt), None)
        month_key = (anchor or datetime.now()).strftime("%Y-%m")
        by_month.setdefault(month_key, []).append((title, messages))
        if cid:
            done.add(cid)
        n_conv += 1
        n_msg += len(messages)

    for month in sorted(by_month):
        target = os.path.join(VAULT, "raw", "chat", "chatgpt")
        os.makedirs(target, exist_ok=True)
        path = os.path.join(target, "%s.md" % month)
        is_new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if is_new:
                f.write(fm("ChatGPT 聊天", "%s-01" % month, ["AI对话", "ChatGPT", "日常"]))
                f.write("# ChatGPT 日常聊天 · %s\n\n" % month)
            for title, messages in by_month[month]:
                f.write("## %s\n\n" % title)
                for dt, who, text in messages:
                    t = dt.strftime("%m-%d %H:%M") if dt else "--"
                    f.write("**%s**（%s）：\n\n%s\n\n---\n\n" % (who, t, text[:MSG_CAP]))
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(done)) + "\n")
    print("[chatgpt] 新增 %d 段对话 / %d 条消息 → %s" % (
        n_conv, n_msg, os.path.join(VAULT, "raw", "chat", "chatgpt")))
    print("[chatgpt] 下一步: qkb ingest && qkb embed")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(INBOX, "conversations.json")
    if not os.path.exists(src):
        found = glob.glob(os.path.join(INBOX, "**", "conversations.json"), recursive=True)
        if found:
            src = found[0]
        else:
            print("[chatgpt] 未找到 conversations.json —— 请先从 ChatGPT 网页导出数据")
            print("         （设置 → 数据控制 → 导出数据），解压后放入 %s/" % INBOX)
            sys.exit(1)
    parse_convs(src)
