#!/bin/bash
# 适配器：Hermes Agent（常驻自治 agent，截至撰写时无「claude -p 式」无头一次性 CLI）。
#
# 正确用法（二选一）：
#   ① 日常任务：由 Hermes 自己执行——它读技能文档（SKILL.md 即其原生格式）直接跑，
#      或用 Hermes 内置 cron 定时（自然语言添加）
#   ② 系统定时（launchd/cron）：engine/run.sh <task> --engine manual 或 api
# 本适配器仅在显式 --engine hermes 时触发：给出指引并打印拼好的 prompt（可手动贴给 Hermes）。
echo "[hermes 适配器] Hermes 没有无头一次性执行 CLI，不直接代跑。" >&2
echo "  · 日常任务：直接让 Hermes 执行（它按 SKILL.md/技能文档自己跑）" >&2
echo "  · 定时：Hermes 内置 cron，或系统定时 + --engine manual/api" >&2
echo "  · 下面是拼好的任务 prompt，可手动贴给 Hermes：" >&2
echo "────────────────────────"
echo "$SHUZI_PROMPT"
echo "────────────────────────"
exit 2
