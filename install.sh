#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 数字人生 · 统一安装器
#
# 「数字人生」= 采集 → agent 自动整理 → 语义检索 → Obsidian 浏览
#
# 用法：
#   bash install.sh                    # 交互式（推荐）：跟着提示走
#   bash install.sh --skills-only     # 只装技能文档（Claude Code / OpenClaw）
#   bash install.sh --help
#
# 完整引导流程见 setup/SETUP.md（8 步）。本脚本是它的快捷方式。
# ═══════════════════════════════════════════════════════════
set -uo pipefail
PKG="$(cd "$(dirname "$0")" && pwd)"
MODE="interactive"

case "${1:-}" in
  --skills-only) MODE="skills" ;;
  -h|--help)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
esac

echo "════════════════════════════════════════════"
echo " 数字人生 · 安装器"
echo "════════════════════════════════════════════"
echo
echo " ① 安装实例身份"
"${SHUZI_PYTHON:-python3}" "$PKG/setup/instance.py" --json
echo " ② 环境探测"
bash "$PKG/setup/detect.sh" 2>&1 | tail -8
echo
bash "$PKG/setup/detect-agent.sh" 2>/dev/null | head -6 || true
echo

# ── A. 技能文档（所有框架通用）──────────────────────────
# 大技能 shuzi-rensheng（维护规范）+ skills/ 下全部子技能（如 shuzi-query 信息检索）
install_skills_to() {
  local dest="$1"          # 技能根目录，如 <workspace>/skills/shuzi-rensheng
  mkdir -p "$dest"
  cp -R "$PKG/SKILL.md" "$PKG/references" "$PKG/examples" "$PKG/engine" "$PKG/setup" "$dest/" 2>/dev/null
  cp -R "$PKG/assets" "$dest/" 2>/dev/null
  # 子技能：skills/<name>/ → <dest 的父目录>/<name>/
  local parent="$(dirname "$dest")"
  for sk in "$PKG"/skills/*/; do
    [ -d "$sk" ] || continue
    local name="$(basename "$sk")"
    mkdir -p "$parent/$name"
    cp -R "$sk." "$parent/$name/" 2>/dev/null
  done
  echo "    ✓ 技能已装到 ${dest}（含子技能）"
}

echo " ② 安装技能文档"
if command -v openclaw >/dev/null 2>&1 && [ -d "$HOME/.openclaw" ]; then
  echo "    检测到 OpenClaw：装到各 agent workspace"
  for ws in "$HOME"/.openclaw/workspaces/*/; do
    [ -d "$ws" ] && install_skills_to "$ws/skills/shuzi-rensheng"
  done
elif [ -d "$HOME/.claude" ]; then
  echo "    检测到 Claude Code：装到用户级技能目录"
  install_skills_to "$HOME/.claude/skills/shuzi-rensheng"
elif [ -d "$HOME/.hermes" ]; then
  echo "    检测到 Hermes：装到 ~/.hermes/skills/（SKILL.md 开放标准）"
  install_skills_to "$HOME/.hermes/skills/shuzi-rensheng"
else
  echo "    未检测到 agent 框架 —— 技能留在包内即可（agent 会从包路径读取）"
fi
[ "${1:-}" = "--skills-only" ] && { echo; echo "完成（--skills-only）"; exit 0; }

echo
echo " ③ 知识库骨架"
VAULT="$("${SHUZI_PYTHON:-python3}" "$PKG/assets/scripts/shuzi_runtime.py" vault)" || exit 1
if [ -f "$VAULT/CLAUDE.md" ]; then
  echo "    已存在：${VAULT}（跳过）"
else
  read -r -p "    知识库路径 [默认 $VAULT]: " v
  VAULT="${v:-$VAULT}"
  bash "$PKG/setup/init-vault.sh" "$VAULT"
fi

echo
echo " ④ 集中配置"
CFG="${SHUZI_CONFIG:-$HOME/.shuzi-rensheng/config.json}"
mkdir -p "$(dirname "$CFG")"
if [ -f "$CFG" ]; then
  echo "    已存在：${CFG}（跳过）"
else
  "${SHUZI_PYTHON:-python3}" - "$PKG/assets/config.json" "$CFG" "$VAULT" <<'PY' || exit 1
import json, os, sys
from pathlib import Path
source, target, vault = sys.argv[1:]
config = json.loads(Path(source).read_text(encoding="utf-8"))
config["vault"] = str(Path(vault).expanduser().resolve())
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    json.dump(config, stream, ensure_ascii=False, indent=2)
PY
  echo "    ✓ 已生成 ${CFG}（vault 与安装选择一致）"
fi

echo
echo " ⑤ 部署检索侧脚本到 ~/.config/qkb/"
QKB_DIR="$HOME/.config/qkb"
mkdir -p "$QKB_DIR"
for f in shuzi_runtime.py qkb-lock.py qkb-follow.py vaultq.py prune-stale.mjs \
         vault-search-mcp.mjs embed-proxy.py compute-health.py qkb-bigjob; do
  [ -f "$PKG/assets/scripts/$f" ] || continue
  if [ -f "$QKB_DIR/$f" ]; then
    echo "    已存在：~/.config/qkb/${f}（不覆盖）"
  else
    cp "$PKG/assets/scripts/$f" "$QKB_DIR/" && echo "    ✓ ~/.config/qkb/$f"
  fi
done
echo "    （qkb 主程序本身需另行安装，见 references/vector-search.md §安装）"

echo
echo " ⑥ 定时任务（可选——让系统自动跑）"
if [ -t 0 ]; then
  read -r -p "    现在选装定时任务吗？（整理/转写/体检/月汇总等，可多选）[y/N]: " yn
  case "$yn" in
    [yY]*) bash "$PKG/setup/schedule.sh" qkb-follow lint --dry-run
           echo "    仅预览；启用 schedule.enabled 后，明确指定任务名注册。" ;;
    *)     echo "    跳过（以后随时：bash setup/schedule.sh）" ;;
  esac
else
  echo "    非交互环境跳过（以后随时：bash setup/schedule.sh 交互选装）"
fi

echo
echo " ⑦ 后续步骤"
echo "    请让 AI agent 按 setup/SETUP.md 继续："
echo "    · 第 2 步 定性能架构 + 配 API"
echo "    · 第 3 步 配采集端（微信等）"
echo "    · 第 4~6 步 提醒 / 定时 / 验收"
echo "    · 第 7 步 启动首次初始化（先跑 setup/estimate.sh 估时长与成本）"
echo
echo "════════════════════════════════════════════"
echo " 完成。说「开始」即可让 agent 接管剩余步骤。"
echo "══════════════════════ --skills-only 可跳过 ③④⑤"
