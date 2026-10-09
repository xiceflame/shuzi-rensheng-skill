#!/bin/bash
# 兜底：只写日志（永远不会失败）
mkdir -p "$HOME/.shuzi-rensheng"
echo "[$(date '+%F %T')] $SHUZI_NOTIFY_MSG" >> "$HOME/.shuzi-rensheng/notify.log"
echo "[log] 已记录"
