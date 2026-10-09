#!/bin/bash
# iCloud ↔ 数字人生 双向桥（每 30 分钟；建议 launchd→ssh localhost 上下文跑，见 references/obsidian.md §双单向桥）
# 模式：主库是本地真实目录（agent 永不直接写 iCloud）；桥只做两件单向事：
#   ① 收件箱回流（手机随手写 → 主库，处理后转存已入库）
#   ② 主库 → iCloud 镜像（手机全量可读）
set -uo pipefail
VAULT="${SHUZI_VAULT:-$HOME/数字人生}"
ICLOUD="${ICLOUD_VAULT:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/数字人生云}"
LOG="${ICLOUD_BRIDGE_LOG:-$HOME/.shuzi-rensheng/icloud-bridge.log}"
INBOX="收件箱"; DONE="已入库"
mkdir -p "$(dirname "$LOG")"
echo "== $(date '+%F %T') bridge 开始 ==" >> "$LOG"

# 0) fileprovider 健康：读不到直接退出（不硬扛）
ls "$ICLOUD" >/dev/null 2>&1 || { echo "[$(date '+%T')] iCloud 不可读，跳过本轮" >> "$LOG"; exit 0; }

# 1) 让云端把新文件拉下来（异步，不阻塞）
command -v brctl >/dev/null 2>&1 && brctl download "$ICLOUD" >/dev/null 2>&1

# 2) 收件箱回流（手机 → 主库），处理后转存已入库
if [ -d "$ICLOUD/$INBOX" ] && [ -n "$(ls -A "$ICLOUD/$INBOX" 2>/dev/null)" ]; then
  mkdir -p "$VAULT/$INBOX"
  rsync -a "$ICLOUD/$INBOX/" "$VAULT/$INBOX/" \
    && { mkdir -p "$ICLOUD/$DONE/$(date +%F)"; \
         rsync -a "$ICLOUD/$INBOX/" "$ICLOUD/$DONE/$(date +%F)/" && rm -f "$ICLOUD/$INBOX"/*; }
  echo "[$(date '+%T')] 收件箱已回流 $(find "$VAULT/$INBOX" -name '*.md' | wc -l | tr -d ' ') 个文件" >> "$LOG"
fi

# 3) 导出镜像（主库 → iCloud，收件箱/已入库除外）
rsync -a --delete --exclude "$INBOX" --exclude "$DONE" "$VAULT/" "$ICLOUD/" 2>&1 | tail -1 >> "$LOG"
echo "== $(date '+%F %T') bridge 完成 ==" >> "$LOG"
