#!/bin/bash
# 适配器：Claude Code 无头模式。普通用户最可能有的。
# 需要：已安装 claude CLI 且已登录（或设了 ANTHROPIC_API_KEY）
exec claude -p "$SHUZI_PROMPT" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit,Bash,Glob,Grep" \
  --output-format text
