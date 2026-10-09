# 适配：Cursor

> 你跑在 Cursor 里，**以编辑器为中心**。

## 你的能力
- 编辑器内读写文件、跑终端命令
- **无内置 cron / channel**
- 规则文件：`.cursorrules` / `.cursor/rules/`

## 跑任务
在 Cursor 里打开本包目录，直接让我读 `engine/tasks/<任务>.md` 并执行。
**长任务建议交给系统定时**（`claude -p` 或 `codex exec` 无头跑），不要依赖编辑器常开。

## 定时
同上——系统原生（`setup/schedule-*`）。

## 通知
`engine/notify.sh`。

## 注意
- 用户**关掉 Cursor 你就停了** → 定时任务必须落在系统层
- 建议把本包路径写进项目规则，方便下次直接调用
