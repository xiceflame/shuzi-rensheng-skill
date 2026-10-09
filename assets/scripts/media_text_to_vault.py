#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 media-text（附件抽文本 / OCR / ASR 产物）镜像成 **可检索的 vault 页**。

- 源：~/wechat-export/media-text/**/*.txt
- 目标：<vault>/raw/attachments/<相对路径>.md   （qkb 只索引 vault 内 + 要求 frontmatter 三件套）
- frontmatter：id 用 uuid5(源相对路径) **稳定生成**（重跑不复嵌）；context=附件；created 取文件日期
- 幂等：目标已存在且内容一致 → 跳过；源变了 → 覆盖；源没了 → 逐个删
- 之后由常驻守护 qkb-follow（每 5 分钟）自动 ingest+embed → **增量近实时**

用法: python3 media_text_to_vault.py          # 全量同步一次
"""
import os
import sys
import glob
import uuid
import hashlib
import shutil

HOME = os.path.expanduser("~")
SRC = os.path.join(HOME, "wechat-export/media-text")
VAULT = os.path.join(HOME, "数字人生")
DST = os.path.join(VAULT, "raw/attachments")
NS = uuid.UUID("6f1e0c2e-77d9-5b7a-9a4f-2c1d3e5f7a09")  # 本流程固定命名空间


def stable_id(rel):
    return str(uuid.uuid5(NS, rel))


def main():
    if not os.path.isdir(SRC):
        print("源目录不存在:", SRC)
        sys.exit(1)
    os.makedirs(DST, exist_ok=True)

    made = updated = removed = 0
    want = set()
    for f in glob.glob(os.path.join(SRC, "**", "*.txt"), recursive=True):
        base = os.path.basename(f)
        if base.startswith("_") or base.startswith("."):
            continue
        rel = os.path.relpath(f, SRC)                      # 如 focus-media/2026-08/xx.pdf.txt
        stem = rel[:-4] if rel.endswith(".txt") else rel   # 去掉 .txt
        # 日期：优先从路径里的 YYYY-MM
        import re
        m = re.search(r"(20\d{2})-(\d{2})", stem)
        created = f"{m.group(1)}-{m.group(2)}-01" if m else datetime_date(stem, f)
        dst = os.path.join(DST, stem + ".md")
        want.add(os.path.relpath(dst, DST))

        body = open(f, encoding="utf-8", errors="replace").read()
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        rid = stable_id(stem)

        head = ("---\nid: %s\ncontext: 附件\ncreated: %s\nsource: %s\n"
                "content_hash: %s\ntags: [附件]\n---\n\n"
                % (rid, created, os.path.join("wechat-export/media-text", stem + ".txt"), content_hash))
        new = head + body + ("\n" if not body.endswith("\n") else "")

        if os.path.exists(dst):
            old = open(dst, encoding="utf-8", errors="replace").read()
            if old == new:
                continue
            # 内容变了但 frontmatter id 不变 → 只覆盖（不会触发重嵌入全量）
            open(dst, "w", encoding="utf-8").write(new)
            updated += 1
        else:
            d = os.path.dirname(dst)
            os.makedirs(d, exist_ok=True)
            tmp = dst + ".tmp"
            open(tmp, "w", encoding="utf-8").write(new)
            os.replace(tmp, dst)
            made += 1

    # 源没了的 → 逐个删（绝不 rmtree）
    for dp, _dn, fns in os.walk(DST):
        for fn in fns:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, DST)
            if rel not in want:
                os.remove(p)
                removed += 1

    print("镜像附件文本 → vault：新建 %d，更新 %d，删除失效 %d（目录 %s）" % (made, updated, removed, DST))


def datetime_date(stem, f):
    import datetime
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
    except Exception:
        return "1970-01-01"


if __name__ == "__main__":
    main()
