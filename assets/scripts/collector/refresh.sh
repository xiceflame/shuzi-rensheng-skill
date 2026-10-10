#!/bin/bash
# 微信关注会话定时刷新（每 4 小时）
#   ① 数据库快照 + 密钥匹配（缺密钥自动只读扫描补齐）+ 解密
#   ② 关注会话文字（30 天）
#   ③ 关注会话语音 → 解码 mp3（增量）
#   ④ 关注会话图片 → 解码 png/jpg
#   ⑤ 关注会话文件媒体（PDF/Office，45 天）
#   ⑥ 关注会话视频（收集文件，供 agent 归类）
#   ⑦ 全部推送大脑（多机组网后；单机自动跳过）
# 由 LaunchAgent 经 Terminal 中继调用（复用 Terminal 的容器访问权限，避免反复弹授权框）
set -uo pipefail

# 固定用系统 python3（zstandard / pycryptodome / pilk 装在它的 user site-packages 下）
PY=/usr/bin/python3

WX_ACCOUNT_DIR="${WX_ACCOUNT_DIR:-$(ls -d "$HOME/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"/*/db_storage 2>/dev/null | head -1 | xargs dirname)}"
SRC="${WX_ACCOUNT_DIR%/}"
WORK="$HOME/wx-export"
SNAP="$WORK/xwechat_files/$(basename "$SRC")"
# 工具目录：默认用包内自带 collector（含 wxexport 模块与全部导出脚本）；WX_TOOL 可指回外部工具
TOOL="${WX_TOOL:-$(cd "$(dirname "$0")" && pwd)}"
LOG="$WORK/refresh.log"
DAYS="${WX_FOCUS_DAYS:-30}"
MEDIA_DAYS="${WX_MEDIA_DAYS:-45}"
MAX_MB="${WX_MEDIA_MAX_MB:-25}"
VID_DAYS="${WX_VIDEO_DAYS:-365}"
VID_MAX_MB="${WX_VIDEO_MAX_MB:-80}"

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
REMOTE_DIR="${REMOTE_DIR:-wechat-export}"  # 多账号：商业号设 WX_REMOTE_DIR=wechat-export-biz

mkdir -p "$WORK"
{
  echo "=== $(date '+%F %T') 刷新开始 (py=$PY) ==="

  # ① 数据库快照
  mkdir -p "$SNAP"
  rm -rf "$SNAP/db_storage"
  if ! /bin/cp -Rc "$SRC/db_storage" "$SNAP/db_storage" 2>/dev/null; then
    /bin/cp -R "$SRC/db_storage" "$SNAP/db_storage"
  fi

  # ⑤ 文件类媒体（群里的日程 PDF 在 msg/file 下）
  MEDIA="$WORK/focus-media"
  rm -rf "$MEDIA"; mkdir -p "$MEDIA"
  if [ -d "$SRC/msg/file" ]; then
    N=0
    while IFS= read -r -d '' f; do
      rel="${f#$SRC/msg/file/}"
      sz=$(/usr/bin/stat -f%z "$f" 2>/dev/null || echo 0)
      [ "$sz" -gt $((MAX_MB * 1024 * 1024)) ] && continue
      mkdir -p "$MEDIA/$(dirname "$rel")"
      /bin/cp -c "$f" "$MEDIA/$rel" 2>/dev/null || /bin/cp "$f" "$MEDIA/$rel" 2>/dev/null || continue
      N=$((N + 1))
    done < <(/usr/bin/find "$SRC/msg/file" -type f -newermt "-${MEDIA_DAYS} days" -print0 2>/dev/null)
    echo "文件媒体: $N 个（最近 ${MEDIA_DAYS} 天，≤${MAX_MB}MB）"
  fi

  # ⑥ 视频（只收集文件，不做深度处理；供 agent 结合上下文归类）
  VID="$WORK/focus-video"
  mkdir -p "$VID"
  VN=0
  for d in "$SRC/msg/video" "$SRC/msg/attach"; do
    [ -d "$d" ] || continue
    while IFS= read -r -d '' f; do
      base=$(basename "$f")
      case "$base" in *_thumb*|*_t.*) continue;; esac
      sz=$(/usr/bin/stat -f%z "$f" 2>/dev/null || echo 0)
      [ "$sz" -gt $((VID_MAX_MB * 1024 * 1024)) ] && continue
      [ "$sz" -lt 20000 ] && continue
      rel="${f#$d/}"; rel="${rel//\//_}"
      [ -e "$VID/$rel" ] && continue
      /bin/cp -c "$f" "$VID/$rel" 2>/dev/null || /bin/cp "$f" "$VID/$rel" 2>/dev/null || continue
      VN=$((VN + 1))
      [ "$VN" -ge 300 ] && break
    done < <(/usr/bin/find "$d" -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.m4v' \) -newermt "-${VID_DAYS} days" -print0 2>/dev/null)
    [ "$VN" -ge 300 ] && break
  done
  echo "视频: $VN 个（最近 ${VID_DAYS} 天，≤${VID_MAX_MB}MB）"

  cd "$TOOL" || { echo "[ERR] 工具目录不存在"; exit 1; }

  # ① 续 匹配密钥 + 解密
  "$PY" -m wxexport match 2>&1 | grep -E '^matched' || true
  MISSING="$("$PY" "$HOME/.wxexport/missing_dbs.py" 2>/dev/null | tr '\n' ' ')"
  if [ -n "${MISSING// /}" ]; then
    WPID="$(pgrep -x WeChat | head -1 || true)"
    if [ -n "$WPID" ]; then
      echo "缺密钥的库，启动只读扫描补齐"
      lldb -b \
        -o "command script import $HOME/wechat-export-macos/scan_cc.py" \
        -o "wxcc $WPID $WORK/rawkeys.txt $MISSING" \
        -o "quit" 2>&1 | grep -E 'KEY!!|DONE' || true
      "$PY" -m wxexport match 2>&1 | grep -E '^matched' || true
    else
      echo "微信未运行，跳过密钥补齐"
    fi
  fi
  if ! "$PY" -m wxexport decrypt; then
    echo "[ERR] 恢复不完整；保留上次导出，停止本轮处理与推送（见 recovery-manifest.json）"
    exit 1
  fi

  # ② 关注会话文字
  "$PY" export_focus.py "$DAYS" 2>&1 | tail -2

  # ③ 关注会话语音（增量解码为 mp3）
  "$PY" export_focus_voice.py 365 2>&1 | tail -2

  # ④ 关注会话图片
  rm -rf "$WORK/focus-images"; mkdir -p "$WORK/focus-images"
  "$PY" decode_focus_images.py "$DAYS" 400 2>&1 | tail -2

  # ④c 可检索聊天记录（近三年，切成带 frontmatter 的月度 md）
  if ! "$PY" export_searchable.py 3; then
    echo "[ERR] 聊天标准化不完整；停止本轮推送（见 searchable/_export-report.json）"
    exit 1
  fi

  # ④b 财务：转账/红包/收款结构化提取
  "$PY" extract_money.py 2>&1 | tail -2

  # ⑦ 推送（仅多机；单机模式跳过——大脑侧直接读本地 ~/wx-export 产物）
  if [ -z "$REMOTE" ] && [ "$TOPOLOGY" != "multi" ]; then
    echo "单机模式：跳过推送（产物保留在 ${WORK}）"
  elif [ -z "$REMOTE" ]; then
    echo "[ERR] 多机模式但未配置大脑主机：config.json network.brain.host 或环境变量 WX_REMOTE（组网见 references/network-setup.md）"
  else
    for pair in "focus:focus" "focus-media:focus-media" "focus-images:focus-images" \
                "focus-voice:focus-voice" "focus-video:focus-video" \
                "focus-money:focus-money" \
                "searchable:searchable"; do
      sub="${pair%%:*}"; dst="${pair##*:}"
      [ -d "$WORK/$sub" ] || { echo "跳过 ${sub}（不存在）"; continue; }
      /usr/bin/rsync -az --delete -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
        "$WORK/$sub/" "$REMOTE:$REMOTE_DIR/$sub/" && echo "已推送 $sub"
    done
  fi

  echo "=== $(date '+%F %T') 刷新结束 ==="
} >> "$LOG" 2>&1
