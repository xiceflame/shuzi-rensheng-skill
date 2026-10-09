# 适配：OpenClaw

> 你跑在 OpenClaw 上，**功能最全**——但也别把系统绑死在它身上（其他人可能没有）。

## 你的能力
- **多 agent**：每个 agent 有独立 workspace / IDENTITY.md / skills/
- **cron**：`openclaw cron add ...`（gateway 托管，进程不随 ssh 断）
- **channels**：Discord / 飞书 / 企业微信 / 微信连接器等
- **远程节点**：`exec(host="node", node="<名称>")` 可直接操作另一台机器
- **MCP**：`openclaw mcp add ...`

## 跑任务
```bash
# 方式 A（推荐，通用）：走 engine
bash engine/run.sh chat-ingest --engine openclaw
# 方式 B：直接用你的 agent
openclaw agent --agent <id> -m "$(cat engine/tasks/chat-ingest.md)"
```

## 定时
**优先用系统原生**（launchd/cron）—— 跨框架可移植。OpenClaw cron 只在「你确定用户就你一个 agent 框架」时用。

## 通知
普通用户建议 `feishu` / `wecom` / `desktop`；你自己有 channles 能力，但**别假设用户也用 Discord**。

## 装技能
```bash
bash install.sh                     # 装到所有 agent workspace
```

## 注意
- **多 agent 是可选优化**：写入边界那套只在你真的分了多个 agent 时才需要；
  单 agent 用目录约定（`projects/工作/` 等）即可，见 `references/single-agent.md`
- 你擅长「一轮里并行调多个 agent」——**setup 阶段别这么干**，一步步来
