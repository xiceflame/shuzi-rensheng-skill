#!/bin/bash
# 数字人生 · 环境探测（给 agent 用，输出 JSON）
# 用法: bash setup/detect.sh
set -uo pipefail
have() { command -v "$1" >/dev/null 2>&1 && echo true || echo false; }
j() { printf '"%s": %s' "$1" "$2"; }

OS="unknown"
case "$(uname -s)" in
  Darwin) OS="macos" ;;
  Linux)  OS="linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
esac
[ -n "${OS:-}" ] || OS="unknown"

# ── GPU 探测（型号 + 显存 + 能力判定）──────────────────────
GPU="none"; GPU_NAME=""; GPU_VRAM_MB=0; GPU_TIER="none"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  GPU="nvidia"
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs)
  GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | xargs)
  [ -z "$GPU_VRAM_MB" ] && GPU_VRAM_MB=0
elif [ "$OS" = "macos" ]; then
  GPU="apple"
  GPU_NAME=$(sysctl -n machdep.cpu.brand_string 2>/dev/null | xargs)
  # Apple 统一内存：取物理内存的 ~75% 作为可用显存估算
  MEM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
  GPU_VRAM_MB=$(( MEM_BYTES / 1048576 * 3 / 4 ))
fi

# 能力分级（决定「本地能跑什么」）
if [ "$GPU" = "none" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then GPU_TIER="cpu-mac"; else GPU_TIER="cpu"; fi
elif [ "${GPU_VRAM_MB:-0}" -ge 20000 ]; then GPU_TIER="xl"    # ≥20GB：可跑 7B 量化 + 重排
elif [ "${GPU_VRAM_MB:-0}" -ge 12000 ]; then GPU_TIER="lg"    # ≥12GB：可跑嵌入 + 重排 + 语音
elif [ "${GPU_VRAM_MB:-0}" -ge 8000 ];  then GPU_TIER="md"    # ≥8GB：嵌入 + 语音，重排勉强
elif [ "${GPU_VRAM_MB:-0}" -ge 4000 ];  then GPU_TIER="sm"    # ≥4GB：只够嵌入
else GPU_TIER="xs"; fi

# 微信容器
WX="false"
for p in "$HOME/Library/Containers/com.tencent.xinWeChat" \
         "$HOME/Documents/xwechat_files" \
         "${USERPROFILE:-}/Documents/xwechat_files"; do
  [ -n "$p" ] && [ -d "$p" ] && WX=true
done

# Obsidian
OBS="false"
[ -d "$HOME/Applications/Obsidian.app" ] || [ -d "/Applications/Obsidian.app" ] || \
  [ -d "$HOME/AppData/Local/Obsidian" ] && OBS=true

# 组网（多机部署需要：Tailscale，见 references/network-setup.md）
TS="false"; TS_UP="false"; TS_PEERS=0
command -v tailscale >/dev/null 2>&1 && TS=true
if [ "$TS" = "true" ] && tailscale status >/dev/null 2>&1; then
  TS_UP=true
  TS_PEERS=$(tailscale status 2>/dev/null | grep -vc '^#' || true)
fi
NET_TOPO="$(/usr/bin/python3 -c '
import json,os,sys
try: c=json.load(open(os.path.expanduser("~/.shuzi-rensheng/config.json")))
except Exception: sys.exit(0)
for k in "network.topology".split("."):
    if not isinstance(c,dict) or k not in c: sys.exit(0)
    c=c[k]
print(c if isinstance(c,str) else "")' 2>/dev/null)"

# agent 框架
AGENTS="[]"
A=""
command -v openclaw >/dev/null 2>&1 && A="$A\"openclaw\","
command -v claude   >/dev/null 2>&1 && A="$A\"claude\","
command -v codex    >/dev/null 2>&1 && A="$A\"codex\","
[ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ] && A="$A\"api-key\","
AGENTS="[${A%,}]"

# 已有配置 / 进度
CFG=false; [ -f "$HOME/.shuzi-rensheng/config.json" ] && CFG=true
STATE=false; [ -f "$HOME/.shuzi-rensheng/state.json" ] && STATE=true

# 已有 vault
VAULT=""
for v in "$HOME/数字人生" "$HOME/Documents/数字人生"; do
  [ -d "$v" ] && [ -f "$v/CLAUDE.md" ] && { VAULT="$v"; break; }
done

cat <<EOF
{
  $(j os "\"$OS\""),
  $(j gpu "\"$GPU\""),
  $(j gpu_name "\"$GPU_NAME\""),
  $(j gpu_vram_mb "$GPU_VRAM_MB"),
  $(j gpu_tier "\"$GPU_TIER\""),
  $(j has_python3 "$(have python3)"),
  $(j has_node "$(have node)"),
  $(j has_ollama "$(have ollama)"),
  $(j has_qkb "$(have qkb)"),
  $(j has_syncthing "$(have syncthing)"),
  $(j has_tailscale "$TS"),
  $(j tailscale_up "$TS_UP"),
  $(j tailscale_peers "$TS_PEERS"),
  $(j network_topology "\"$NET_TOPO\""),
  $(j has_wechat_container "$WX"),
  $(j has_obsidian "$OBS"),
  $(j agent_frameworks "$AGENTS"),
  $(j config_exists "$CFG"),
  $(j state_exists "$STATE"),
  $(j existing_vault "\"$VAULT\""),
  $(j home "\"$HOME\"")
}
EOF

# 给 agent 的建议（stderr，纯提示）
{
  echo "── 建议 ──"
  [ "$OS" = "windows" ] && echo "· 采集走 windows-collector.md（免权限）"
  [ "$OS" = "macos" ] && [ "$WX" = "true" ] && echo "· 采集走 wechat-pipeline.md（需 FDA+中继）"
  [ "$(have ollama)" = "false" ] && [ "$GPU" = "none" ] && echo "· 无 Ollama 无 GPU → 嵌入建议走 API"
  case "$GPU_TIER" in
    xl|lg) echo "· GPU 显存 ${GPU_VRAM_MB}MB ≥ 8GB → 可本地跑：嵌入 + 重排 + 语音（大 LLM 仍走 API）" ;;
    md)    echo "· GPU 显存 ${GPU_VRAM_MB}MB ≥ 8GB → 可本地跑：嵌入 + 重排 + 语音" ;;
    sm)    echo "· GPU 显存 ${GPU_VRAM_MB}MB < 8GB 门槛 → 【一律走 API】，本地只跑纯脚本" ;;
    *)     echo "· 无独显（< 8GB 门槛）→ 【一律走 API】，本机只跑纯脚本" ;;
  esac
  echo "· ⚠️ 首次大批量处理必须用 API 或高性能 GPU，别用弱机器硬扛（见 references/performance-tiering.md）"
  [ "$(have qkb)" = "false" ] && echo "· 未装 qkb → npm i -g @miguelarios/qkb"
  [ "$NET_TOPO" = "multi" ] && [ "$TS_UP" != "true" ] && echo "· 多机模式但 Tailscale 未就绪 → 先组网（references/network-setup.md）"
  [ "$NET_TOPO" = "multi" ] && echo "· 多机模式：确认 config.json network.brain.host 已填且 ssh 可达（验证见 network-setup.md §6）"
  [ -n "$VAULT" ] && echo "· 已存在知识库：${VAULT}（走「继续」而非「新建」）"
} >&2
