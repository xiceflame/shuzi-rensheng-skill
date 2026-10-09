#!/bin/bash
# Discord（可选，非默认）
AGENT="${SHUZI_AGENT:-main}"; OC="${OPENCLAW_BIN:-openclaw}"
if command -v "$OC" >/dev/null 2>&1 && [ -n "${DISCORD_CHANNEL:-}" ]; then
  "$OC" message send --channel discord --target "channel:$DISCORD_CHANNEL" --message "$SHUZI_NOTIFY_MSG" >/dev/null && echo "[discord] 已发送"
else
  echo "[skip] 未配置 Discord"
fi
