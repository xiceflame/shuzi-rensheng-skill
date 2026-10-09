#!/usr/bin/env python3
"""
把 focus-voice 里的语音批量转写成文字（大脑侧，whisper）。

- 读取 ~/wechat-export/focus-voice/_manifest.tsv（含 时间/会话/发言人/文件）
- 对尚未转写的 mp3 逐个跑 whisper（模型只加载一次，批处理才快）
- 结果按会话写入 ~/wechat-export/focus-voice-text/<会话名>.txt
  行格式：[YYYY-MM-DD HH:MM:SS] 发言人: 文本
- 已处理清单：~/wechat-export/focus-voice/.transcribed.tsv

用法: python3 transcribe_voice.py [模型=base] [上限=0]
"""
import os
import sys
import time

WORK = os.path.expanduser("~/wechat-export")
VOICE = os.path.join(WORK, "focus-voice")
TEXT = os.path.join(WORK, "focus-voice-text")
TSV = os.path.join(VOICE, "_manifest.tsv")
DONE = os.path.join(VOICE, ".transcribed.tsv")


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "base"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    import whisper
    os.makedirs(TEXT, exist_ok=True)

    done = set()
    if os.path.exists(DONE):
        with open(DONE, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    done.add(s)

    rows = []
    if os.path.exists(TSV):
        with open(TSV, encoding="utf-8") as f:
            hdr = f.readline().rstrip("\n").split("\t")
            # 兼容两种格式：
            #   5 列: 时间 会话 local_id silk字节 文件
            #   6 列: 时间 会话 发言人 local_id silk字节 文件
            i_who = hdr.index("发言人") if "发言人" in hdr else -1
            i_file = len(hdr) - 1
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) != len(hdr):
                    continue
                stamp = p[0]
                cname = p[1]
                who = p[i_who] if i_who >= 0 else ""
                fn = p[i_file]
                rows.append([stamp, cname, who, "", "", fn])

    todo = [r for r in rows if r[5] not in done]
    todo.sort()
    if limit:
        todo = todo[:limit]
    print("[stt] 待转写 %d 条（共 %d）" % (len(todo), len(rows)))
    if not todo:
        return

    t0 = time.time()
    model = whisper.load_model(model_name)
    print("[stt] 模型 %s 加载完成 %.1fs" % (model_name, time.time() - t0))

    handles = {}
    ok = 0
    secs = 0.0
    for stamp, cname, who, lid, _sz, fn in todo:
        path = os.path.join(VOICE, fn)
        if not os.path.exists(path):
            continue
        try:
            r = model.transcribe(path, language="zh", fp16=False)
            text = (r.get("text") or "").strip()
            segs = r.get("segments") or []
            if segs:
                secs += float(segs[-1].get("end", 0) or 0)
        except Exception as e:
            print("[stt] 失败 %s: %s" % (fn, e))
            continue
        if text:
            # stamp 形如 "2026-06-09_172244"
            try:
                ts = "%s-%s-%s %s:%s:%s" % (
                    stamp[0:4], stamp[5:7], stamp[8:10],
                    stamp[11:13], stamp[13:15], stamp[15:17])
            except Exception:
                ts = stamp
            h = handles.get(cname)
            if h is None:
                h = open(os.path.join(TEXT, "%s.txt" % cname), "a", encoding="utf-8")
                handles[cname] = h
            h.write("[%s] %s: %s\n" % (ts, who or "?", text))
            h.flush()
        with open(DONE, "a", encoding="utf-8") as f:
            f.write(fn + "\n")
        ok += 1
        if ok % 100 == 0:
            el = time.time() - t0
            print("[stt] 已转写 %d 条，音频 %.0f 分钟，用时 %.0f 秒（%.1f 倍速）" % (
                ok, secs / 60.0, el, secs / el if el else 0))

    for h in handles.values():
        h.close()
    el = time.time() - t0
    print("[stt] 完成 %d 条，音频 %.0f 分钟，用时 %.0f 秒（%.1f 倍速）" % (
        ok, secs / 60.0, el, secs / el if el else 0))


if __name__ == "__main__":
    main()
