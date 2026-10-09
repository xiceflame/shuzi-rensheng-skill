#!/bin/bash
# 重建「可检索聊天记录」+ 向量索引（每 4 小时，跟在同步之后）
{
  echo "=== $(date '+%F %T') 索引重建开始 ==="
  # 1) 从 MacBook 拉最新的 searchable（文字）
  # 单机部署时跳过（多机时设 DATA_SOURCE_HOST 即可）
  if [ -n "${DATA_SOURCE_HOST:-}" ]; then
    rsync -az --delete -e "ssh -o BatchMode=yes" \
      "${DATA_SOURCE_HOST}:wx-export/searchable/" "$HOME/wechat-export/searchable/" 2>&1 | tail -1
  else
    echo "（单机模式：跳过 rsync，直接用本地 searchable/）"
  fi
  # 2) 重建 chatlogs（文字 + 最新语音转写，含归属链接与时间轴）
  /usr/bin/python3 $HOME/.wxexport/rebuild_chatlogs.py 2>&1 | tail -4
  # 3) 重建向量索引（经 qkb-lock 串行化，避免与其他 qkb 写操作并发抢插）
  #    并发 embed 会撞 "UNIQUE constraint failed on chunks_vec primary key"
  /usr/bin/python3 $HOME/.config/qkb/qkb-lock.py ingest 2>&1 | tail -1
  /usr/bin/python3 $HOME/.config/qkb/qkb-lock.py embed 2>&1 | tail -1
  echo "=== $(date '+%F %T') 索引重建结束 ==="
} >> $HOME/wechat-export/rebuild-index.log 2>&1
