#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 searchable（MacBook 导出的近三年聊天）写入 **raw/chatlogs**（证据区）。

⚠️ 遵守 CLAUDE.md §9.4：
  - **绝不 rmtree**（vault 由 Syncthing 准实时同步，删目录+重建会触发竞态丢文件）
  - 只覆盖 / 只新增；保留原 frontmatter id（避免 qkb 全量重嵌入）
  - 失效文件**逐个 os.remove**

结构：raw/chatlogs/<会话>/<YYYY-MM>.md
"""
import glob
import os
import re
import shutil
import uuid
from collections import defaultdict

W = os.path.expanduser("~/wechat-export")
SRC = os.path.join(W, "searchable")
VT = os.path.join(W, "focus-voice-text")
DST = os.path.expanduser("~/数字人生/raw/chatlogs")

os.makedirs(DST, exist_ok=True)

# 1) 记录现有文件的 id（按 <会话>/<月> 定位）
old_ids = {}
for root, _d, fs in os.walk(DST):
    for fn in fs:
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        p = os.path.join(root, fn)
        try:
            head = open(p, encoding="utf-8", errors="replace").read(500)
        except OSError:
            continue
        m = re.search(r"^id:\s*(\S+)", head, re.M)
        if m:
            old_ids[os.path.relpath(p, DST)] = m.group(1)
print("复用旧 id: %d" % len(old_ids))

# 2) 文字：searchable/<会话>/<YYYY-MM>.md -> raw/chatlogs/<会话>/<YYYY-MM>.md
n_txt = 0
want = set()
for root, _d, files in os.walk(SRC):
    for fn in files:
        if not fn.endswith(".md"):
            continue
        sp = os.path.join(root, fn)
        rel = os.path.relpath(sp, SRC)          # 会话/YYYY-MM.md
        want.add(rel)
        dp = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        body = open(sp, encoding="utf-8", errors="replace").read()
        # 去掉源 frontmatter
        if body.startswith("---\n"):
            j = body.find("\n---\n", 4)
            body = body[j + 5:] if j > 0 else body
        conv = os.path.basename(os.path.dirname(rel)) or os.path.basename(root)
        ym = fn[:-3]
        rid = old_ids.get(rel) or str(uuid.uuid4())
        with open(dp, "w", encoding="utf-8") as f:
            f.write("---\nid: %s\ncontext: %s\ncreated: %s-01\ntags: [聊天记录, %s]\n---\n\n"
                    % (rid, conv, ym, conv))
            f.write(body)
        n_txt += 1
print("写入文字文件: %d" % n_txt)

# 3) 语音转写：并入对应 <会话>/<YYYY-MM>.md（重写该文件，正文=文字+语音）
voice = defaultdict(list)
for vf in glob.glob(os.path.join(VT, "*.txt")):
    cname = os.path.basename(vf)[:-4]
    for line in open(vf, encoding="utf-8", errors="replace"):
        m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*([^:]*):\s*(.*)", line.strip())
        if m:
            voice[(cname, m.group(1)[:7])].append(
                (m.group(1), m.group(2).strip() or "?", m.group(3)))

n_v = 0
for (conv, ym), items in voice.items():
    rel = os.path.join(conv, "%s.md" % ym)
    want.add(rel)
    dp = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(dp), exist_ok=True)
    rid = old_ids.get(rel) or str(uuid.uuid4())
    # 保留已有正文（去掉旧 frontmatter 与旧语音段），再追加最新语音
    body = ""
    if os.path.exists(dp):
        s = open(dp, encoding="utf-8", errors="replace").read()
        if s.startswith("---\n"):
            j = s.find("\n---\n", 4)
            s = s[j + 5:] if j > 0 else s
        body = s.split("\n## 语音转写")[0].rstrip() + "\n"
    with open(dp, "w", encoding="utf-8") as f:
        f.write("---\nid: %s\ncontext: %s\ncreated: %s-01\ntags: [聊天记录, %s]\n---\n\n"
                % (rid, conv, ym, conv))
        f.write(body)
        f.write("\n## 语音转写\n\n")
        for ts, who, txt in sorted(items):
            f.write("[%s] %s: %s\n" % (ts, who, txt))
    n_v += 1
print("并入语音: %d 个 (会话,月)" % n_v)

# 4) 失效文件：**逐个 os.remove**（绝不 rmtree）
removed = 0
for root, _d, fs in os.walk(DST):
    for fn in fs:
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, DST)
        if rel not in want:
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
print("删除失效文件: %d" % removed)

tot = sum(len(fs) for _r, _d, fs in os.walk(DST))
print("raw/chatlogs 现有 %d 个文件" % tot)
