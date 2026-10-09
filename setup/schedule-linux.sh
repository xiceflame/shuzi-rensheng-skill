#!/bin/bash
# Linux：按任务名写 crontab（与 schedule-macos.sh 同一任务目录）
# 用法：bash setup/schedule-linux.sh [推荐集] | <任务名>... | all
set -u
ENGINE="${SHUZI_ENGINE:-$HOME/shuzi-rensheng-skill/engine}"
X="${SHUZI_X:-$HOME/.wxexport}"
RECOMMENDED="chat-ingest finance-ingest rebuild transcribe lint idea-review rollup qkb-follow"

line() { # line <任务名> → cron 行
  case "$1" in
    chat-ingest)       echo "7 8,21 * * *   bash $ENGINE/run.sh chat-ingest" ;;
    finance-ingest)    echo "40 */4 * * *   bash $ENGINE/run.sh finance-ingest" ;;
    rebuild)           echo "10 */4 * * *   bash $ENGINE/scripts-extra.sh rebuild" ;;
    transcribe)        echo "20 */4 * * *   bash $ENGINE/scripts-extra.sh transcribe" ;;
    lint)              echo "7 21 * * 0    bash $ENGINE/run.sh lint" ;;
    idea-review)       echo "7 10 * * 1    bash $ENGINE/run.sh idea-review" ;;
    rollup)            echo "7 9 1 * *     bash $ENGINE/run.sh rollup" ;;
    qkb-follow)        echo "*/5 * * * *   python3 \$HOME/.config/qkb/qkb-follow.py --once" ;;
    collector-refresh) echo "0 */4 * * *   bash $X/refresh.sh" ;;
    *) echo "# 未知任务: $1（目录见 bash setup/schedule.sh）" ;;
  esac
}

TASKS_IN="${*:-}"
[ -z "$TASKS_IN" ] && TASKS_IN="$RECOMMENDED"
[ "$TASKS_IN" = "all" ] && TASKS_IN="$RECOMMENDED collector-refresh"

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v 'shuzi-rensheng\|qkb-follow\|run\.sh\|scripts-extra\|wxexport' > "$TMP" || true
{
  echo "# ── 数字人生 ──"
  for t in $TASKS_IN; do line "$t"; done
} >> "$TMP"
crontab "$TMP" && rm -f "$TMP" && echo "  ✓ crontab 已写入（crontab -l 查看）"
