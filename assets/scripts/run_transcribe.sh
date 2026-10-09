#!/bin/bash
# 增量转写 focus-voice 里新到的语音（由 cron 调用）
HOME=$HOME
WHISPER_PY=/opt/homebrew/Cellar/openai-whisper/20250625_3/libexec/bin/python3
LOG="$HOME/wechat-export/stt.log"
mkdir -p "$HOME/wechat-export"
{
  echo "--- $(date '+%F %T') 转写开始 ---"
  "$WHISPER_PY" "$HOME/.wxexport/transcribe_voice.py" base 2>&1 | grep -E '^\[stt\]'
  echo "--- $(date '+%F %T') 转写结束 ---"
} >> "$LOG" 2>&1
