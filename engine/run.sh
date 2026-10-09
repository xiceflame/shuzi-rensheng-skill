#!/bin/bash
# 数字人生 · 任务运行器（引擎无关）
#
# 用法：
#   bash run.sh <任务名> [--engine auto|openclaw|claude|codex|api|ollama|manual] [--dry-run]
#   bash run.sh --list              # 列出所有任务
#
# 设计：**任务定义（tasks/*.md 里的 prompt）与执行引擎解耦**。
# 同一段 prompt，可以用 OpenClaw / Claude Code / Codex / 裸 API / 本地模型 / 人工 执行。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TASKS="$HERE/tasks"
ENGINES="$HERE/engines"
VAULT="${SHUZI_VAULT:-$HOME/数字人生}"
LOG="${SHUZI_LOG:-$HOME/.shuzi-rensheng/run.log}"
mkdir -p "$(dirname "$LOG")"

TASK=""; ENGINE="auto"; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --list) ls "$TASKS" 2>/dev/null | sed 's/\.md$//'; exit 0 ;;
    --engine) ENGINE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) TASK="$1"; shift ;;
  esac
done

[ -z "$TASK" ] && { echo "用法: bash run.sh <任务名> [--engine ...] [--dry-run]"; echo "任务列表:"; ls "$TASKS" 2>/dev/null | sed 's/\.md$//' | sed 's/^/  /'; exit 1; }

TASKFILE="$TASKS/$TASK.md"
[ -f "$TASKFILE" ] || { echo "[ERR] 任务不存在: $TASK"; exit 1; }

# 组装 prompt：任务定义 + 运行时变量
PROMPT="$(sed "s|{{VAULT}}|$VAULT|g; s|{{HOME}}|$HOME|g; s|{{DATE}}|$(date +%F)|g" "$TASKFILE")"

# 自动选引擎：优先用户指定的，否则按可用性 fallback
pick_engine() {
  [ "$ENGINE" != "auto" ] && { echo "$ENGINE"; return; }
  if [ -x "$(command -v openclaw 2>/dev/null)" ] && [ -f "$HOME/.openclaw/openclaw.json" ]; then echo openclaw; return; fi
  if [ -x "$(command -v claude 2>/dev/null)" ]; then echo claude; return; fi
  if [ -x "$(command -v codex 2>/dev/null)" ]; then echo codex; return; fi
  if [ -n "${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}" ]; then echo api; return; fi
  if [ -x "$(command -v ollama 2>/dev/null)" ]; then echo ollama; return; fi
  echo manual
}
E="$(pick_engine)"
ADAPTER="$ENGINES/$E.sh"
[ -f "$ADAPTER" ] || { echo "[ERR] 引擎适配器不存在: $E"; exit 1; }

echo "═══ 任务: $TASK ｜ 引擎: $E ｜ vault: $VAULT ═══"
if [ "$DRY" = "1" ]; then
  echo "--- prompt（dry-run）---"
  echo "$PROMPT"
  exit 0
fi

{
  echo "=== $(date '+%F %T') task=$TASK engine=$E start ==="
  SHUZI_PROMPT="$PROMPT" SHUZI_TASK="$TASK" bash "$ADAPTER"
  rc=$?
  echo "=== $(date '+%F %T') task=$TASK engine=$E end rc=$rc ==="
} >> "$LOG" 2>&1
echo "完成（日志：${LOG}）"
