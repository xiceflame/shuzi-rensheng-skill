#!/bin/bash
# 微信连接器（如 OpenClaw 的 weixin channel / 第三方 iLink 桥接）
# 把消息交给 agent 由其所在渠道发出——即「由 Agent 触发提醒」的通用形态。
AGENT="${SHUZI_AGENT:-main}"
OC="${OPENCLAW_BIN:-openclaw}"
if command -v "$OC" >/dev/null 2>&1; then
  "$OC" agent --agent "$AGENT" --session-key "agent:$AGENT:notify" -m "$SHUZI_NOTIFY_MSG"
else
  echo "[skip] 无可用微信连接器"
fi
