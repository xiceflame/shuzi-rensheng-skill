#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
focus-media 长音频批量转写：**mlx-whisper（Apple Silicon 原生，快）+ webrtcvad 预筛**。

- 每个文件先 ffmpeg 转 16k 单声道 wav → webrtcvad 算「人声占比」
- 人声占比 < 阈值（默认 0.10）→ 判为音乐/静音，**跳过转写**（只写元信息）
- 否则 mlx-whisper 转写（默认 large-v3-turbo）
- 产物：~/wechat-export/media-text/<相对路径>.txt（与抽取/OCR 同目录）

用法: .venv-media/bin/python media_transcribe_mlx.py [模型] [人声阈值]
     模型默认 mlx-community/whisper-large-v3-turbo
"""
import os
import sys
import glob
import wave
import struct
import subprocess
import tempfile
import time
import datetime

HOME = os.path.expanduser("~")
MEDIA = os.path.join(HOME, "wechat-export/focus-media")
TXT = os.path.join(HOME, "wechat-export/media-text")
DONE = os.path.join(TXT, ".transcribed-mlx.tsv")
EXTS = (".m4a", ".mp3", ".wav", ".aac", ".amr", ".mp4")
MODEL = "mlx-community/whisper-large-v3-turbo"


def to_wav16k(src, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-f", "wav", dst],
                   check=True, timeout=600, capture_output=True)


def speech_ratio(wav_path, aggressiveness=2):
    import webrtcvad
    vad = webrtcvad.Vad(aggressiveness)
    wf = wave.open(wav_path, "rb")
    rate = wf.getframerate()
    frame_ms = 30
    n = int(rate * frame_ms / 1000)
    voiced = total = 0
    while True:
        data = wf.readframes(n)
        if len(data) < n * 2:
            break
        total += 1
        try:
            if vad.is_speech(data, rate):
                voiced += 1
        except Exception:
            pass
    wf.close()
    return (voiced / total) if total else 0.0


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else MODEL
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.10

    import mlx_whisper
    os.makedirs(TXT, exist_ok=True)
    done = set()
    if os.path.exists(DONE):
        done = {l.strip() for l in open(DONE, encoding="utf-8") if l.strip()}

    files = sorted(f for f in glob.glob(os.path.join(MEDIA, "*", "*"))
                   if os.path.splitext(f)[1].lower() in EXTS)
    todo = [f for f in files if f not in done]
    print("[stt] 待转写 %d / 共 %d（模型 %s，VAD 阈值 %.2f）" % (len(todo), len(files), model, thr), flush=True)

    t0 = time.time()
    ok = skipped = 0
    for f in todo:
        rel = os.path.relpath(f, HOME)
        dst = os.path.join(TXT, rel + ".txt")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav = tf.name
        try:
            to_wav16k(f, wav)
            r = speech_ratio(wav)
            if r < thr:
                with open(dst, "w", encoding="utf-8") as fh:
                    fh.write("# 源：%s\n# 判定：非语音（人声占比 %.2f）→ 音乐/静音，跳过转写\n"
                             % (rel, r))
                skipped += 1
                status = "skip(%.2f)" % r
            else:
                out = mlx_whisper.transcribe(wav, path_or_hf_repo=model, language="zh",
                                             verbose=False)
                text = (out.get("text") or "").strip()
                with open(dst, "w", encoding="utf-8") as fh:
                    fh.write("# 源：%s\n# 转写：mlx-whisper %s（人声占比 %.2f）\n\n%s\n"
                             % (rel, model.split("/")[-1], r, text))
                ok += 1
                status = "ok"
        except Exception as e:
            status = "err:%s" % str(e)[:60]
            print("[stt] 失败 %s: %s" % (os.path.basename(f), e), flush=True)
        finally:
            if os.path.exists(wav):
                os.remove(wav)
        with open(DONE, "a", encoding="utf-8") as fh:
            fh.write(f + "\n")
        if (ok + skipped) % 10 == 0:
            el = time.time() - t0
            print("[stt] 已处理 %d/%d（转写 %d / 跳过 %d），用时 %.0f 秒"
                  % (ok + skipped, len(todo), ok, skipped, el), flush=True)

    el = time.time() - t0
    print("[stt] 完成：转写 %d，跳过(非语音) %d，用时 %.0f 秒" % (ok, skipped, el), flush=True)


if __name__ == "__main__":
    main()
