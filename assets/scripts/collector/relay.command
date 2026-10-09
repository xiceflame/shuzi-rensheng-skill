#!/bin/bash
# 由 LaunchAgent 用 `open -g -a Terminal` 拉起：
# 在 Terminal 里执行刷新（复用 Terminal 已获得的容器访问权限，不会再弹授权框），
# 跑完后关闭自己这个终端窗口（Terminal 控制自身窗口不需要额外授权）。
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
bash "$HOME/.wxexport/refresh.sh"
# 关掉本窗口
osascript -e "tell application \"Terminal\" to close (every window whose tty is \"$(tty)\")" >/dev/null 2>&1
