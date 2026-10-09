#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
focus-media 里的**独立音频**批量转写（与 focus-voice 的微信语音不同）。

- 扫 ~/wechat-export/focus-media/**/*.{m4a,mp3,wav,aac,amr}
- whisper 批处理（模型只加载一次）
- 结果写 ~/wechat-export/media-text/<相对路径>.txt（与抽取/OCR 同目录，agent 统一读）
- 已处理清单：~/wechat-export/media-text/.transcribed.tsv

用法: whisper-venv/bin/python media_transcribe.py [模型=base] [上限=0]
"""
import os
import sys
import glob
import time
import datetime

HOME = os.path.expanduser("~")
MEDIA = os.path.join(HOME, "wechat-export/focus-media")
TXT = os.path.join(HOME, "wechat-export/media-text")
DONE = os.path.join(TXT, ".transcribed.tsv")
EXTS = (".m4a", ".mp3", ".wav", ".aac", ".amr", ".mp4")


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "base"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    import whisper
    os.makedirs(TXT, exist_ok=True)

    done = set()
    if os.path.exists(DONE):
        done = {l.strip() for l in open(DONE, encoding="utf-8") if l.strip()}

    files = sorted(f for f in glob.glob(os.path.join(MEDIA, "*", "*"))
                   if os.path.splitext(f)[1].lower() in EXTS)
    todo = [f for f in files if f not in done]
    if limit:
        todo = todo[:limit]
    print("[stt] 待转写 %d / 共 %d（模型 %s）" % (len(todo), len(files), model_name), flush=True)
    if not todo:
        return

    t0 = time.time()
    model = whisper.load_model(model_name)
    print("[stt] 模型加载 %.1fs" % (time.time() - t0), flush=True)

    ok = 0
    secs = 0.0
    for f in todo:
        try:
            r = model.transcribe(f, language="zh", fp16=False)
            text = (r.get("text") or "").strip()
            segs = r.get("segments") or []
            if segs:
                secs += float(segs[-1].get("end", 0) or 0)
        except Exception as e:
            print("[stt] 失败 %s: %s" % (os.path.basename(f), e), flush=True)
            continue
        rel = os.path.relpath(f, HOME)
        dst = os.path.join(TXT, rel + ".txt")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write("# 源：%s\n# 转写：whisper %s (%s)\n\n%s\n"
                     % (rel, model_name, datetime.datetime.now().isoformat(timespec="seconds"), text))
        with open(DONE, "a", encoding="utf-8") as fh:
            fh.write(f + "\n")
        ok += 1
        if ok % 10 == 0:
            el = time.time() - t0
            print("[stt] %d/%d 条，音频 %.0f 分钟，用时 %.0f 秒（%.1f×）"
                  % (ok, len(todo), secs / 60, el, secs / el if el else 0), flush=True)
    el = time.time() - t0
    print("[stt] 完成 %d 条，音频 %.0f 分钟，用时 %.0f 秒（%.1f×）"
          % (ok, secs / 60, el, secs / el if el else 0), flush=True)


if __name__ == "__main__":
    main()
