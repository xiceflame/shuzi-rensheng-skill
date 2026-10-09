# 适配：Codex CLI

> 你跑在 OpenAI Codex CLI 上。

## 跑任务
```bash
codex exec --full-auto "$(cat engine/tasks/chat-ingest.md)"
# 或
bash engine/run.sh chat-ingest --engine codex
```

## 定时 / 通知 / 注意
与 Claude Code 同：**定时走系统原生**，通知走 `engine/notify.sh`。
无头模式适合放进 launchd/cron。
