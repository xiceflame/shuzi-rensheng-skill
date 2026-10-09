#!/bin/bash
# 定时任务 · 选装入口（SETUP 第 5 步；把「装哪些自动化」变成安装时可选项）
# 用法：
#   bash setup/schedule.sh              # 交互选择（推荐集/逐项/全部）
#   bash setup/schedule.sh <任务名>...  # 非交互：直接装指定项
#   bash setup/schedule.sh all          # 全部（含采集机项）
set -u
PKG="$(cd "$(dirname "$0")/.." && pwd)"
RECOMMENDED="chat-ingest finance-ingest rebuild transcribe lint idea-review rollup qkb-follow"
ALL_TASKS="$RECOMMENDED collector-refresh"

case "$(uname -s)" in
  Darwin)        PLAT="$PKG/setup/schedule-macos.sh" ;;
  Linux)         PLAT="$PKG/setup/schedule-linux.sh" ;;
  MINGW*|MSYS*)  PLAT="$PKG/setup/schedule-windows.ps1" ;;
  *) echo "未知系统，请手动运行 setup/schedule-{macos,linux,windows}"; exit 1 ;;
esac

catalog() {
  cat <<'EOF'
┌─ 数字人生 · 定时任务目录（安装后可随时增删，重跑本脚本即可）─────────────
│ [1] chat-ingest       整理「我的每一天」/人物时间线    08:07 / 21:07   ★推荐
│ [2] finance-ingest    财务增量整理                    每 4 小时       ★推荐
│ [3] rebuild           重建证据层 + 向量检索索引        每 4 小时       ★推荐
│ [4] transcribe        语音转写（本地 whisper）         每 4 小时       ★推荐
│ [5] lint              知识库体检（断链/孤岛/索引）     每周日 21:07    ★推荐
│ [6] idea-review       想法复盘                        每周一 10:07    ★推荐
│ [7] rollup            月汇总                          每月 1 日 09:07 ★推荐
│ [8] qkb-follow        检索索引跟随（5 分钟级）         常驻/每 5 分钟  ★推荐
│ [9] collector-refresh 微信采集刷新                    每 4 小时       ⚠仅采集机（macOS 需 Terminal 中继，见 wechat-pipeline.md §5.2）
└──────────────────────────────────────────────────────────────────────
说明：[1][2] 需要 LLM API；[3][4][8] 纯本地；[9] 只装在登录微信的那台机器上。
EOF
}

if [ "$#" -gt 0 ]; then
  exec bash "$PLAT" "$@"
fi
if [ ! -t 0 ]; then
  catalog
  echo "（非交互环境：自动安装推荐集 [1-8]）"
  exec bash "$PLAT" $RECOMMENDED
fi

catalog
printf "选择要安装的项（如 1 3 5 ｜ all=全部9项 ｜ 回车=推荐集[1-8]）: "
read -r ans
[ -z "$ans" ] && ans="1 2 3 4 5 6 7 8"
[ "$ans" = "all" ] && exec bash "$PLAT" $ALL_TASKS
PICKED=""
for n in $ans; do
  case "$n" in
    1) PICKED="$PICKED chat-ingest" ;;
    2) PICKED="$PICKED finance-ingest" ;;
    3) PICKED="$PICKED rebuild" ;;
    4) PICKED="$PICKED transcribe" ;;
    5) PICKED="$PICKED lint" ;;
    6) PICKED="$PICKED idea-review" ;;
    7) PICKED="$PICKED rollup" ;;
    8) PICKED="$PICKED qkb-follow" ;;
    9) PICKED="$PICKED collector-refresh" ;;
    *) echo "忽略无效输入: $n" ;;
  esac
done
[ -z "${PICKED// /}" ] && { echo "未选择任何任务，退出"; exit 0; }
exec bash "$PLAT" $PICKED
