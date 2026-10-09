# 适配：Claude Code

> 你跑在 Claude Code 上（终端 / 桌面 / IDE 插件 / claude.ai/code）。

## 你的能力
- **工具名**：`Read` `Write` `Edit` `Bash` `Glob` `Grep`（**注意**：不是 OpenClaw 的 `exec`）
- **无内置 cron** → 用系统 `launchd` / `cron` / `schtasks`
- **无内置 channels** → 通知走 `engine/notify.sh`（feishu/wecom/desktop…）
- **skills**：`~/.claude/skills/<name>/SKILL.md` 或项目 `.claude/skills/`
- **hooks / settings**：`.claude/settings.json`（可用 `update-config` skill 配置）

## 跑任务
```bash
# 无头模式（定时任务里用这个）
claude -p "$(cat engine/tasks/chat-ingest.md)" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit,Bash,Glob,Grep"
```
`engine/run.sh chat-ingest --engine claude` 已封装好。

## 定时
用系统原生：
```bash
bash setup/schedule-macos.sh    # macOS → launchd
bash setup/schedule-linux.sh    # Linux → crontab
```

## 通知
`engine/notify.sh "消息"`（配 `~/.shuzi-rensheng/config.json` 的 `notify` 段）。
也可以配 **settings hooks**（如 Stop hook）做「每次干完提醒我」。

## 装技能
```bash
mkdir -p ~/.claude/skills/shuzi-rensheng
cp SKILL.md references/ -r ~/.claude/skills/shuzi-rensheng/
```

## 注意
- 你**没有常驻进程** → **别把关键定时放在你这儿**，一定落到系统定时
- 每次调用是独立会话 → 依赖 `~/.shuzi-rensheng/state.json` 记住 setup 进度
