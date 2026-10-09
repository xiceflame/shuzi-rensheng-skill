#!/bin/bash
# 适配器：OpenClaw。用 --agent 指定分工；单 agent 时用 $SHUZI_AGENT 或默认 main。
OC="${OPENCLAW_BIN:-/opt/homebrew/bin/openclaw}"
AGENT="${SHUZI_AGENT:-main}"
"$OC" agent --agent "$AGENT" --session-key "agent:$AGENT:$SHUZI_TASK" \
  --timeout 2400 -m "$SHUZI_PROMPT"
