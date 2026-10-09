#!/bin/bash
# 附件流水线：抽文本 → 去重/建队列 → 本机 Vision OCR（扫描件/图片）
# 由 automation `media-extract` 定时调用。
set -u
W=$HOME/wechat-export
PY=$HOME/.wxexport/.venv-media/bin/python
LOG=$W/media-pipeline.log
{
  echo "--- $(date '+%F %T') 附件流水线开始 ---"
  "$PY" $HOME/.wxexport/media_extract.py "$W/focus-media" "$HOME/数字人生/raw/docs" 2>&1 | tail -2
  "$PY" $HOME/.wxexport/media_dedupe.py 2>&1 | tail -3
  "$PY" $HOME/.wxexport/ocr_vision.py --queue 2>&1 | tail -1
  echo "--- $(date '+%F %T') 结束 ---"
} >> "$LOG" 2>&1
tail -5 "$LOG"
