#!/bin/bash
# macOS：按任务名生成并加载 launchd 定时任务（数字人生定时任务安装器）
# 用法：
#   bash setup/schedule-macos.sh                # 推荐集（8 项，见 setup/schedule.sh 目录）
#   bash setup/schedule-macos.sh <任务名>...    # 只装指定项（如 qkb-follow / rebuild transcribe）
#   bash setup/schedule-macos.sh all            # 全部（推荐集 + 采集机项 collector-refresh）
set -u
ENGINE="${SHUZI_ENGINE:-$HOME/shuzi-rensheng-skill/engine}"
PKG="$(cd "$(dirname "$0")/.." && pwd)"
LOGD="$HOME/.shuzi-rensheng/logs"; mkdir -p "$LOGD"
mkdir -p "$HOME/Library/LaunchAgents"
UID_="$(id -u)"
RECOMMENDED="chat-ingest finance-ingest rebuild transcribe lint idea-review rollup qkb-follow"

# cal_xml <hours-csv> <minute> [weekly:W(0=日,1=一…6=六) | monthly:D]
cal_xml() {
  local hs="$1" m="$2" extra="${3:-}" out="" hh
  if [ -n "$extra" ]; then
    local k="${extra%%:*}" v="${extra##*:}"
    if [ "$k" = "weekly" ]; then
      out="<dict><key>Weekday</key><integer>$v</integer><key>Hour</key><integer>${hs%%,*}</integer><key>Minute</key><integer>$m</integer></dict>"
    else
      out="<dict><key>Day</key><integer>$v</integer><key>Hour</key><integer>${hs%%,*}</integer><key>Minute</key><integer>$m</integer></dict>"
    fi
  else
    for hh in ${hs//,/ }; do
      out="$out<dict><key>Hour</key><integer>$hh</integer><key>Minute</key><integer>$m</integer></dict>"
    done
  fi
  echo "$out"
}

# write_plist <name> <StartCalendarInterval-xml> <cmd...>
write_plist() {
  local name="$1" cal="$2"; shift 2
  local p="$HOME/Library/LaunchAgents/ai.shuzi.$name.plist" arg args=""
  for arg in "$@"; do args="$args
    <string>$arg</string>"; done
  cat > "$p" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ai.shuzi.$name</string>
  <key>ProgramArguments</key><array>$args
  </array>
  <key>StartCalendarInterval</key><array>
    $cal
  </array>
  <key>StandardOutPath</key><string>$LOGD/$name.log</string>
  <key>StandardErrorPath</key><string>$LOGD/$name.err.log</string>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
PLIST
  launchctl bootout "gui/$UID_/ai.shuzi.$name" 2>/dev/null
  launchctl bootstrap "gui/$UID_" "$p" 2>/dev/null && echo "  ✓ ai.shuzi.$name"
}

# 常驻：qkb-follow（KeepAlive；模板 __HOME__/__LOGDIR__ 自动替换）
install_qkb_follow() {
  local src="$PKG/engine/schedule/launchd/ai.shuzi.qkb-follow.plist"
  local dst="$HOME/Library/LaunchAgents/ai.shuzi.qkb-follow.plist"
  [ -f "$HOME/.config/qkb/qkb-follow.py" ] || { echo "  [跳过] ~/.config/qkb/qkb-follow.py 不存在（先跑 install.sh）"; return; }
  [ -f "$src" ] || { echo "  [跳过] 模板不存在: $src"; return; }
  sed -e "s|__HOME__|$HOME|g" -e "s|__LOGDIR__|$LOGD|g" "$src" > "$dst"
  launchctl bootout "gui/$UID_/ai.shuzi.qkb-follow" 2>/dev/null
  launchctl bootstrap "gui/$UID_" "$dst" 2>/dev/null && echo "  ✓ ai.shuzi.qkb-follow（KeepAlive 常驻）"
}

# 采集机：微信刷新（Terminal 中继；需先按 wechat-pipeline.md §5.2 配好 ~/.wxexport/relay.command）
install_collector_refresh() {
  local src="$PKG/assets/templates/ai.wxexport.refresh.plist"
  local dst="$HOME/Library/LaunchAgents/ai.wxexport.refresh.plist"
  [ -f "$src" ] || { echo "  [跳过] 模板不存在: $src"; return; }
  [ -f "$HOME/.wxexport/relay.command" ] || echo "  ⚠️ ~/.wxexport/relay.command 不存在 —— 首次会弹授权，建议先配 Terminal 中继（wechat-pipeline.md §5.2）"
  sed "s|__HOME__|$HOME|g" "$src" > "$dst"
  launchctl bootout "gui/$UID_/ai.wxexport.refresh" 2>/dev/null
  launchctl bootstrap "gui/$UID_" "$dst" 2>/dev/null && echo "  ✓ ai.wxexport.refresh（每 4h，经 Terminal 中继）"
}

install_one() {
  case "$1" in
    chat-ingest)    write_plist chat-ingest    "$(cal_xml 8,21 7)"             /bin/bash "$ENGINE/run.sh" chat-ingest ;;
    finance-ingest) write_plist finance-ingest "$(cal_xml 0,4,8,12,16,20 40)"  /bin/bash "$ENGINE/run.sh" finance-ingest ;;
    rebuild)        write_plist rebuild        "$(cal_xml 0,4,8,12,16,20 10)"  /bin/bash "$ENGINE/scripts-extra.sh" rebuild ;;
    transcribe)     write_plist transcribe     "$(cal_xml 0,4,8,12,16,20 20)"  /bin/bash "$ENGINE/scripts-extra.sh" transcribe ;;
    lint)           write_plist lint           "$(cal_xml 21 7 weekly:0)"       /bin/bash "$ENGINE/run.sh" lint ;;
    idea-review)    write_plist idea-review    "$(cal_xml 10 7 weekly:1)"       /bin/bash "$ENGINE/run.sh" idea-review ;;
    rollup)         write_plist rollup         "$(cal_xml 9 7 monthly:1)"       /bin/bash "$ENGINE/run.sh" rollup ;;
    qkb-follow)     install_qkb_follow ;;
    collector-refresh) install_collector_refresh ;;
    *) echo "  [跳过] 未知任务: $1（目录见 bash setup/schedule.sh）" ;;
  esac
}

TASKS_IN="${*:-}"
[ -z "$TASKS_IN" ] && TASKS_IN="$RECOMMENDED"
[ "$TASKS_IN" = "all" ] && TASKS_IN="$RECOMMENDED collector-refresh"
for t in $TASKS_IN; do install_one "$t"; done
