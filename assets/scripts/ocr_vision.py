#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本机 macOS Vision OCR：图片 / 扫描件 PDF → 文本（零模型、离线、中文强）。
用于「抽不出文本的附件」的增量 OCR；结果并入 media-text/<rel>.txt。

用法：
    .venv-media/bin/python ocr_vision.py <文件或目录> [...]       # 只处理 OCR 队列里的
    .venv-media/bin/python ocr_vision.py --queue                 # 读 _ocr_queue.tsv 批量跑
"""
import os
import sys
import glob
import tempfile
import datetime

import Vision
from Foundation import NSURL
import pymupdf  # PDF 渲染

HOME = os.path.expanduser("~")
TXT = os.path.join(HOME, "wechat-export/media-text")
IMG = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".tif", ".tiff"}
OCR_LANGS = ["zh-Hans", "en-US"]


def _req():
    r = Vision.VNRecognizeTextRequest.alloc().init()
    r.setRecognitionLanguages_(OCR_LANGS)
    r.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    r.setUsesLanguageCorrection_(True)
    return r


def ocr_file_image(path):
    url = NSURL.fileURLWithPath_(path)
    req = _req()
    ok, err = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {}).performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(str(err))
    return "\n".join(o.topCandidates_(1)[0].string() for o in (req.results() or []))


def ocr_pdf(path, dpi=200):
    doc = pymupdf.open(path)
    parts = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            pix.save(tf.name)
            tmp = tf.name
        try:
            t = ocr_file_image(tmp)
        finally:
            os.remove(tmp)
        parts.append("--- p%d ---\n%s" % (i + 1, t))
    doc.close()
    return "\n".join(parts)


def out_path(src):
    rel = os.path.relpath(os.path.abspath(src), HOME)
    return os.path.join(TXT, rel + ".txt")


def _has_real_text(dst):
    """抽取器可能已写过「空/极短」的 txt —— 那种要重做 OCR。"""
    if not os.path.exists(dst):
        return False
    body = open(dst, encoding="utf-8", errors="replace").read()
    body = body.split("\n\n", 1)[-1] if body.startswith("#") else body
    return len(body.strip()) >= 120


def process(src):
    ext = os.path.splitext(src)[1].lower()
    dst = out_path(src)
    if _has_real_text(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return "skip"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        if ext == ".pdf":
            txt = ocr_pdf(src)
        elif ext in IMG:
            txt = ocr_file_image(src)
        else:
            return "skip-type"
        with open(dst, "w", encoding="utf-8") as f:
            f.write("# 源：%s\n# OCR：macOS Vision (%s)\n\n%s\n"
                    % (os.path.relpath(src, HOME), datetime.datetime.now().isoformat(timespec="seconds"), txt))
        return "ok(%d字)" % len(txt.strip())
    except Exception as e:
        return "error: %s" % str(e)[:80]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    files = []
    if args == ["--queue"]:
        q = os.path.join(TXT, "_ocr_queue.tsv")
        for line in open(q, encoding="utf-8").read().splitlines()[1:]:
            rel, ext, why = line.split("\t")
            if ext.lower() in IMG or ext.lower() == ".pdf":
                files.append(os.path.join(HOME, rel))
    else:
        for a in args:
            a = os.path.abspath(os.path.expanduser(a))
            if os.path.isfile(a):
                files.append(a)
            else:
                for dp, _dn, fns in os.walk(a):
                    files += [os.path.join(dp, fn) for fn in fns if not fn.startswith(".")]
    ok = sum(1 for f in files if process(f).startswith("ok"))
    print("OCR %d 个（成功 %d）→ %s" % (len(files), ok, TXT))


if __name__ == "__main__":
    main()
