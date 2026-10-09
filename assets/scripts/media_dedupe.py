#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
附件去重 + OCR 队列：
1) 按内容 sha256 去重（同一文件被多次转发 → 只留一份代表）
2) 标记「需要 OCR」的：抽文本为空/过短的电子文档 + 图片类型
输出：~/wechat-export/media-text/_dedupe.tsv、_ocr_queue.tsv
"""
import os
import sys
import glob
import hashlib
import collections

SRC = os.path.expanduser("~/wechat-export/focus-media")
TXT = os.path.expanduser("~/wechat-export/media-text")
IMG = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".hevc", ".bmp", ".tif", ".tiff"}


def sha(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    by_hash = collections.defaultdict(list)
    for p in glob.glob(os.path.join(SRC, "*", "*")):
        if os.path.isfile(p) and not os.path.basename(p).startswith("."):
            by_hash[sha(p)].append(p)
    dup_groups = {h: v for h, v in by_hash.items() if len(v) > 1}
    total = sum(len(v) for v in by_hash.values())
    uniq = len(by_hash)
    saved = total - uniq

    # OCR 队列：抽文本为空/极短者 + 图片
    ocr = []
    for h, files in by_hash.items():
        rep = files[0]
        ext = os.path.splitext(rep)[1].lower()
        rel = os.path.relpath(rep, os.path.expanduser("~"))
        tpath = os.path.join(TXT, rel + ".txt")
        need = False
        why = ""
        if ext in IMG:
            need, why = True, "image"
        else:
            if os.path.exists(tpath):
                body = open(tpath, encoding="utf-8", errors="replace").read()
                if len(body.strip()) < 120:
                    need, why = True, "text-too-short(scanned?)"
            else:
                need, why = True, "no-text-yet"
        if need:
            ocr.append((rel, ext, why))

    with open(os.path.join(TXT, "_dedupe.tsv"), "w", encoding="utf-8") as f:
        f.write("sha256\tcount\trepresentative\tall\n")
        for h, v in sorted(by_hash.items(), key=lambda x: -len(x[1])):
            f.write("%s\t%d\t%s\t%s\n" % (h, len(v), os.path.relpath(v[0], os.path.expanduser("~")),
                                          " ; ".join(os.path.relpath(x, os.path.expanduser("~")) for x in v)))
    with open(os.path.join(TXT, "_ocr_queue.tsv"), "w", encoding="utf-8") as f:
        f.write("file\text\treason\n")
        for r in ocr:
            f.write("\t".join(r) + "\n")

    print("附件总数 %d → 去重后 %d（重复 %d，省 %.0f%%）" % (total, uniq, saved, 100.0 * saved / max(total, 1)))
    print("需 OCR（去重后）: %d 个" % len(ocr))
    n_img = sum(1 for r in ocr if r[1] in IMG)
    print("  其中图片 %d / 扫描件或抽不出文本的电子文档 %d" % (n_img, len(ocr) - n_img))
    print("清单：%s/_dedupe.tsv · _ocr_queue.tsv" % TXT)


if __name__ == "__main__":
    main()
