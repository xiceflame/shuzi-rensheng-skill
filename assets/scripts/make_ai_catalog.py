#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 AI 会话存档索引页（只记位置/规模/查法，不含正文）。"""
import glob
import os
import uuid
from datetime import datetime

VAULT = os.environ.get("SHUZI_VAULT", os.path.expanduser("~/数字人生"))
OUT = os.path.join(VAULT, "raw", "chat", "AI会话存档索引.md")


def fm(context, tags):
    return "---\nid: %s\ncontext: %s\ncreated: %s\ntags: [%s]\n---\n\n" % (
        str(uuid.uuid4()), context, "2026-09-12", ", ".join(tags))


def stat(pattern, label, grep_dir):
    files = sorted(glob.glob(os.path.expanduser(pattern)))
    if not files:
        return []
    total = 0
    oldest = newest = None
    for f in files:
        total += os.path.getsize(f)
        mt = datetime.fromtimestamp(os.path.getmtime(f))
        oldest = mt if oldest is None or mt < oldest else oldest
        newest = mt if newest is None or mt > newest else newest
    return [
        "## " + label,
        "",
        "- 位置：`" + pattern.replace(os.path.expanduser("~"), "~") + "`",
        "- 文件数 %d ｜ 共 %.0f MB ｜ 跨度 %s ~ %s" % (
            len(files), total / 1048576.0,
            oldest.strftime("%Y-%m"), newest.strftime("%Y-%m")),
        "- 查法：`grep -l \"关键词\" " + grep_dir + "`",
        "",
    ]


def main():
    lines = [
        fm("AI会话存档索引", ["AI对话", "存档索引"]),
        "# AI 会话存档索引",
        "",
        "> ⚠️ 策略：AI 开发会话**全文不入 vault**——会话是过程，产物才是资产。",
        "> 本页只记「有什么、在哪、怎么查」。要找内容时直接 grep 原始 jsonl。",
        "> 开发产物的索引走 `files_index.py` 只挑 docs/README/进展记录（--ext .md）。",
        "",
    ]
    lines += stat("~/.claude/projects/*/*.jsonl", "Claude Code 会话",
                  os.path.expanduser("~/.claude/projects"))
    lines += stat("~/.codex/sessions/*/*/*/rollout-*.jsonl", "Codex 会话",
                  os.path.expanduser("~/.codex/sessions"))
    lines += [
        "- 需要全文时：`assets/scripts/ai_chat_export.py` 随时可导出（按项目/月度 md）",
    ]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("已生成:", OUT)


if __name__ == "__main__":
    main()
