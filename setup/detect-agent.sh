#!/bin/bash
# 数字人生 · **Agent 自我识别**（第 0b 步）
#
# 目的：让当前运行的 AI 先搞清楚「我是谁、我能干什么」，
#       再据此调整 setup 的后续步骤（工具名/定时/通知/工作区约定都不同）。
#
# 用法: bash setup/detect-agent.sh
# 输出: JSON（framework + capabilities + 适配建议）
set -uo pipefail
have() { command -v "$1" >/dev/null 2>&1 && echo true || echo false; }
any_env() { for v in "$@"; do [ -n "${!v:-}" ] && { echo true; return; }; done; echo false; }

FRAMEWORK="generic"
CONFIDENCE="low"
NOTES=""

# ── 1) 框架判定 ──────────────────────────────────────────────
if [ -d "$HOME/.openclaw" ] && command -v openclaw >/dev/null 2>&1; then
  FRAMEWORK="openclaw"; CONFIDENCE="high"
  NOTES="多 agent（workspaces/skills）、gateway cron、channels 通知、exec(host=node) 可操作远程节点"
elif [ -n "${CLAUDECODE:-}${CLAUDE_CODE_ENTRYPOINT:-}" ] || [ -d "$HOME/.claude" ]; then
  FRAMEWORK="claude-code"; CONFIDENCE="high"
  NOTES="工具名 Read/Write/Edit/Bash/Glob/Grep；无内置 cron，用系统 launchd/cron；通知走 webhook 或 settings hooks"
elif [ -n "${CURSOR_TRACE_ID:-}${CURSOR:-}" ] || [ -d "$HOME/.cursor" ]; then
  FRAMEWORK="cursor"; CONFIDENCE="medium"
  NOTES="以编辑器为中心；长任务建议交系统定时，不依赖编辑器常开"
elif [ -d "$HOME/.codex" ] || command -v codex >/dev/null 2>&1; then
  FRAMEWORK="codex"; CONFIDENCE="medium"
  NOTES="codex exec 无头执行；工具集与 Claude Code 类似"
elif [ -d "$HOME/.hermes" ] && command -v hermes >/dev/null 2>&1; then
  FRAMEWORK="hermes"; CONFIDENCE="high"
  NOTES="常驻自治 agent；agentskills.io 开放标准技能（SKILL.md）；shell 本地/SSH 执行；内置 cron；gateway 多渠道（Telegram/Discord/…）；无无头一次性 CLI"
elif [ -n "${OPENAI_API_KEY:-}${ANTHROPIC_API_KEY:-}" ] || [ -n "${DASHSCOPE_API_KEY:-}${ZHIPU_API_KEY:-}" ]; then
  FRAMEWORK="api-only"; CONFIDENCE="medium"
  NOTES="只有 API key、没有 agent 框架 → 用 engine/api-agent.py（最小文件读写循环）或 engine/run.sh --engine manual"
fi

# ── 2) 能力探测 ──────────────────────────────────────────────
can_shell=$(have bash)
can_python=$(have python3)
can_node=$(have node)
can_cron=false
case "$(uname -s)" in
  Darwin) [ "$(have launchctl)" = "true" ] && can_cron=true ;;
  Linux)  command -v crontab >/dev/null 2>&1 && can_cron=true ;;
  *)      command -v schtasks >/dev/null 2>&1 && can_cron=true ;;
esac

# 是否能操作「另一台机器」（多机模式的关键）
can_remote=false
if [ "$FRAMEWORK" = "openclaw" ]; then
  openclaw nodes status 2>/dev/null | grep -q "connected" && can_remote=true
elif command -v ssh >/dev/null 2>&1; then
  can_remote="ssh"
fi

# ── 3) 先算适配建议（避免 case 嵌在 heredoc 里）──
case "$FRAMEWORK" in
  openclaw)    A_RUN='engine/run.sh --engine openclaw（用你的 agent 跑）' ;;
  claude-code) A_RUN='engine/run.sh --engine claude（claude -p 无头）' ;;
  cursor)      A_RUN='engine/run.sh --engine claude；或在编辑器里手工触发' ;;
  codex)       A_RUN='engine/run.sh --engine codex' ;;
  hermes)      A_RUN='任务由 Hermes 直接执行（它读 SKILL.md 自己跑）；无人值守走 Hermes 内置 cron，或系统定时 + --engine manual/api' ;;
  api-only)    A_RUN='engine/run.sh --engine api（需在 config.json 配 llm）' ;;
  *)           A_RUN='engine/run.sh --engine manual（打印 prompt 人工贴）' ;;
esac
case "$FRAMEWORK" in
  openclaw) A_SCHED='可用 OpenClaw cron；也可用系统 launchd/cron（推荐后者，更通用）' ;;
  hermes)   A_SCHED='可用 Hermes 内置 cron（自然语言添加）；也可用系统 launchd/cron（推荐后者，更通用）' ;;
  *)        A_SCHED='用系统原生定时（setup/schedule-{macos,linux,windows}）' ;;
esac
case "$FRAMEWORK" in
  openclaw) A_NOTIFY='可用 OpenClaw channels；普通用户建议 feishu/wecom/desktop' ;;
  hermes)   A_NOTIFY='可用 Hermes gateway 渠道（Telegram/Discord/Slack/…）；普通用户建议 feishu/wecom/desktop' ;;
  *)        A_NOTIFY='走 engine/notify.sh（feishu/wecom/wechat-connector/desktop/log）' ;;
esac
case "$FRAMEWORK" in
  openclaw)    A_SKILL='各 agent 的 workspace/skills/ 下放一份（install.sh 支持）' ;;
  claude-code) A_SKILL='放 ~/.claude/skills/shuzi-rensheng/（或项目 .claude/skills/）' ;;
  hermes)      A_SKILL='放 ~/.hermes/skills/shuzi-rensheng/（install.sh 支持；SKILL.md 即其原生技能格式）' ;;
  *)           A_SKILL='把本包放在固定路径并在系统提示里引用即可（无强制约定）' ;;
esac

cat <<EOF
{
  "framework": "$FRAMEWORK",
  "confidence": "$CONFIDENCE",
  "notes": "$NOTES",
  "capabilities": {
    "shell": $can_shell,
    "python3": $can_python,
    "node": $can_node,
    "native_schedule": $can_cron,
    "remote_exec": "$can_remote"
  },
  "adaptation": {
    "run_task": "$A_RUN",
    "schedule": "$A_SCHED",
    "notify": "$A_NOTIFY",
    "skill_install": "$A_SKILL"
  }
}
EOF

# ── 4) 给它看的说明（stderr）──
{
  echo "== 你(AI)现在跑在: $FRAMEWORK  [置信度 $CONFIDENCE] =="
  echo "   $NOTES"
  echo
  echo "== 据此调整 setup =="
  echo "   . 第 2 步配 API: 若你已有内置模型，可跳过（用 --engine 指定自己）"
  echo "   . 第 5 步配定时: 用系统原生定时，别绑框架（跨框架可移植）"
  echo
  echo "== 先读你自己的适配说明 =="
  echo "   setup/frameworks/$FRAMEWORK.md"
} >&2
