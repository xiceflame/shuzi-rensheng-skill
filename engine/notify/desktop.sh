#!/bin/bash
# 系统桌面通知（macOS / Linux；Windows 见注释）
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$SHUZI_NOTIFY_MSG\" with title \"数字人生\"" && echo "[desktop] 已通知"
elif command -v notify-send >/dev/null 2>&1; then
  notify-send "数字人生" "$SHUZI_NOTIFY_MSG" && echo "[desktop] 已通知"
else
  echo "[skip] 无桌面通知工具（Windows 可用 powershell -c \"[void][Windows.UI.Notifications.ToastNotificationManager,...]\")"
fi
