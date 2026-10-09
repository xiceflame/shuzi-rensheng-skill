#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频转写「幻觉尾巴」清理 + 非语音标记。

whisper 在音乐/噪音上会吐**重复幻觉**（如「优优独播剧场」循环），且常**接在真实对话之后**。
所以策略是：
  1) 找到「短片段连续重复 ≥N 次」的幻觉段 → **从该段开始截断**（保留前面真实内容）
  2) 截断后若剩余正文 ≥ 50 字 → 视为「有效（已截断幻觉尾巴）」
  3) 剩余过短/字符多样性过低 → 标「疑似非语音（音乐/噪音）→ 跳过提炼」

用法: python3 media_flag_nonspeech.py
"""
import os
import re
import glob

TXT = os.path.expanduser("~/wechat-export/media-text")
MARK = "# 判定：疑似非语音（音乐/噪音）→ 跳过提炼"
NOTE_TRIM = "# 注：已截断末尾重复幻觉段"


def find_hallucination(text):
    """n-gram 频次法：若某个 20-gram 反复出现（≥4 次）且占比 ≥30%，
    取它**首次连续重复**的位置作为幻觉起点（在去空白文本上的下标）。-1 表示无。"""
    from collections import Counter
    t = re.sub(r"\s+", "", text)
    n = len(t)
    if n < 120:
        return -1
    W = 20
    grams = [t[i:i + W] for i in range(0, max(1, n - W), 5)]
    if not grams:
        return -1
    gram, c = Counter(grams).most_common(1)[0]
    if c < 4 or (c * W) / n < 0.30:
        return -1
    # 找它第一次出现且后面紧跟重复的地方
    first = t.find(gram)
    if first < 0 or first < n * 0.20:
        first = t.find(gram, int(n * 0.20))
    return first if first > 0 else -1


def clean(body):
    i = find_hallucination(body)          # 该下标是在「去空白」后的文本上的
    if i <= 0:
        return body, False
    # 映射回去空白文本的计数 → 原串位置
    cnt = 0
    pos = len(body)
    for k, ch in enumerate(body):
        if not ch.isspace():
            cnt += 1
            if cnt > i:
                pos = k
                break
    return body[:pos].rstrip(), True


def judge(body):
    t = re.sub(r"\s+", "", body)
    if len(t) < 50:
        return True, "too-short(%d)" % len(t)
    uniq = len(set(t)) / len(t)
    if uniq < 0.18:
        return True, "low-unique(%.2f)" % uniq
    punct = sum(t.count(c) for c in "，。！？、；：,.!?;:")
    if punct / len(t) < 0.004:
        return True, "no-punct"
    return False, ""


def main():
    n = trimmed = flagged = 0
    for f in glob.glob(os.path.join(TXT, "**", "*.txt"), recursive=True):
        try:
            s = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "# 转写：" not in s:
            continue
        n += 1
        head, _, body = s.partition("\n\n")
        # 清掉上一次的标记，重判
        head_lines = [l for l in head.split("\n")
                      if not l.startswith("# 判定") and not l.startswith(NOTE_TRIM)]
        head = "\n".join(head_lines)
        body, did = clean(body)
        bad, why = judge(body)
        notes = []
        if did:
            notes.append(NOTE_TRIM)
            trimmed += 1
        if bad:
            notes.append("%s（原因：%s）" % (MARK, why))
            flagged += 1
        out = head + ("\n" + "\n".join(notes) if notes else "") + "\n\n" + body + "\n"
        open(f, "w", encoding="utf-8").write(out)
    print("ASR 文本 %d：截断幻觉 %d，标非语音 %d" % (n, trimmed, flagged))


if __name__ == "__main__":
    main()
