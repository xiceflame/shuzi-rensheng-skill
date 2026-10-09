#!/bin/bash
# 纯脚本任务统一入口（**零 token**，不需要任何 LLM）
#
# 用法: bash scripts-extra.sh <任务名>
# 这些是本系统里「不需要 AI 介入」的环节——占全部工作量的大头。
set -uo pipefail
E="${SHUZI_ENGINE:-$HOME/shuzi-rensheng-skill/engine}"
W="${SHUZI_WORK:-$HOME/wechat-export}"
X="${SHUZI_X:-$HOME/.wxexport}"
V="${SHUZI_VAULT:-$HOME/数字人生}"

case "${1:-}" in
  # ── 采集端 ──
  collector-refresh)  bash "$X/refresh.sh" ;;                    # 解密+导出全部数据
  collector-full)     bash "$X/full_refresh.sh" ;;               # 每周全量历史

  # ── 大脑侧 ──
  transcribe)         bash "$W/run_transcribe.sh" ;;             # 语音转写（本地/API）
  rebuild)            bash "$W/rebuild_index.sh" ;;              # 重建证据层 + 向量索引
  media-extract)      python3 "$X/media_extract.py" "$W/focus-media" "$V/raw/docs" ;;
                                                                 # 附件 → 纯文本（省钱关键）
  media-dedupe)       python3 "$X/media_dedupe.py" ;;            # 附件去重（省钱关键）
  ai-export)          /usr/bin/python3 "$E/../assets/scripts/ai_chat_export.py" ;;
                           # Claude Code / Codex 会话 → raw/chat/
  files-index)        shift; /usr/bin/python3 "$E/../assets/scripts/files_index.py" "$@" ;;
                           # 任意文件夹 → 可检索 md
  conflict-sentinel)  python3 "$X/conflict-sentinel.py" ;;       # 收口同步冲突副本
  qkb-follow)         python3 "$HOME/.config/qkb/qkb-follow.py" ;;      # 索引跟随（常驻更佳）
  qkb-prune)          node "$HOME/.config/qkb/prune-stale.mjs" ;;       # 清理陈旧索引条目

  *) echo "用法: $0 <任务名>"
     echo "可用: collector-refresh collector-full transcribe rebuild media-extract"
     echo "      media-dedupe conflict-sentinel qkb-follow qkb-prune"
     exit 1 ;;
esac
