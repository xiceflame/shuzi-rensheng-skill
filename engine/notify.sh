#!/bin/bash
# 数字人生 · 提醒分发（渠道由集中配置决定）
# 用法：bash notify.sh "消息正文" [--to <渠道>]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/config.sh" 2>/dev/null || true

MSG=""; TO=""
while [ $# -gt 0 ]; do case "$1" in --to) TO="$2"; shift 2;; *) [ -z "$MSG" ] && MSG="$1"; shift;; esac; done
[ -z "$MSG" ] && { echo "用法: bash notify.sh \"消息\""; exit 1; }

# 优先级：--to > 环境变量 SHUZI_NOTIFY > config.json 的 notify.channel > 自动挑
pick() {
  [ -n "$TO" ] && { echo "$TO"; return; }
  [ -n "${SHUZI_NOTIFY:-}" ] && { echo "$SHUZI_NOTIFY"; return; }
  local c; c="$(cfg_get notify.channel 2>/dev/null)"
  [ -n "$c" ] && [ -f "$HERE/notify/$c.sh" ] && { echo "$c"; return; }
  for x in feishu wecom wechat-connector desktop log; do
    [ -f "$HERE/notify/$x.sh" ] && { echo "$x"; return; }
  done
  echo log
}
C="$(pick)"
A="$HERE/notify/$C.sh"
[ -f "$A" ] || { echo "[ERR] 渠道不存在: $C"; exit 1; }
SHUZI_NOTIFY_MSG="$MSG" bash "$A"
