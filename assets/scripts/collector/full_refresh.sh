#!/bin/bash
# 全量历史导出（每周一次）：把全部会话、全部历史渲染成文本/HTML 并推送大脑（多机；单机跳过）。
# 说明：不做容器拷贝（不需要 FDA），直接用 refresh.sh 维护的 db_storage 快照。
set -uo pipefail
PY=/usr/bin/python3
WORK="$HOME/wx-export"
TOOL="$HOME/wechat-export-macos/rmqg-export"
LOG="$WORK/full_refresh.log"

# ── 跨机推送目标：环境变量 > ~/.shuzi-rensheng/config.json 的 network 段 ──
cfgget() {  # cfgget <a.b.c>：读 config.json 字符串值，缺失输出空
  "$PY" -c '
import json,os,sys
try: c=json.load(open(os.path.expanduser("~/.shuzi-rensheng/config.json")))
except Exception: sys.exit(0)
for k in sys.argv[1].split("."):
    if not isinstance(c,dict) or k not in c: sys.exit(0)
    c=c[k]
print(c if isinstance(c,str) else "")' "$1" 2>/dev/null
}
TOPOLOGY="${WX_TOPOLOGY:-$(cfgget network.topology)}"
REMOTE="${WX_REMOTE:-$(cfgget network.brain.host)}"
REMOTE_DIR="${WX_REMOTE_DIR:-$(cfgget network.brain.dir)}"
REMOTE_DIR="${REMOTE_DIR:-wechat-export}"

{
  echo "=== $(date '+%F %T') 全量导出开始 ==="
  cd "$TOOL" || { echo "[ERR] 工具目录不存在"; exit 1; }
  "$PY" -m wxexport build 2>&1 | grep -E '^matched|^decrypted|^exported' || true
  if [ -z "$REMOTE" ] && [ "$TOPOLOGY" != "multi" ]; then
    echo "单机模式：跳过推送（产物保留在 $WORK/export）"
  elif [ -z "$REMOTE" ]; then
    echo "[ERR] 多机模式但未配置大脑主机：config.json network.brain.host 或环境变量 WX_REMOTE（组网见 references/network-setup.md）"
  else
    /usr/bin/rsync -az --delete -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
      "$WORK/export/" "$REMOTE:$REMOTE_DIR/" && echo "已推送全量导出"
  fi
  echo "=== $(date '+%F %T') 全量导出结束 ==="
} >> "$LOG" 2>&1
