# 适配：Hermes Agent（Nous Research）

> 你跑在 Hermes 上——常驻自治 agent，技能用 agentskills.io 开放标准（SKILL.md），
> 和本包的格式**天然同源**：技能即文档，装进去就能读。

## 你的能力
- **技能**：`~/.hermes/skills/`，SKILL.md 开放标准（本包无需转换）
- **shell 执行**：本地终端 / SSH 远程 / Docker 隔离
- **内置 cron**：自然语言添加定时任务（日报/备份/审计）
- **gateway 渠道**：Telegram / Discord / Slack / WhatsApp / Signal / Email
- **自进化技能**：解决难题后会自动写成可复用技能文档
- ⚠️ **没有无头一次性 CLI**（无 `claude -p` 等价物）→ 无人值守执行见下

## 跑任务
**日常任务由你直接执行**：读 `SKILL.md` 与任务定义（`engine/tasks/*.md`），自己跑脚本
（采集/解密/建索引都是纯脚本，LLM 只做「提炼成笔记」）。

无人值守（定时）两条路：
```text
① Hermes 内置 cron（推荐）：自然语言添加，如
   「每天 21:07 跑数字人生的 chat-ingest 任务（engine/run.sh chat-ingest --engine manual
    的 prompt 你自己按 engine/tasks/chat-ingest.md 执行）」
② 系统定时兜底：launchd/cron 调 engine/run.sh <task> --engine manual（打印 prompt 交给你）
   ——与框架解耦，见 setup/schedule-{macos,linux,windows}
```

## 定时
内置 cron 或系统原生均可；**系统原生更可移植**（换框架不重配）。

## 通知
你有 gateway 渠道可用；但**别假设用户配了 Telegram/Discord**——
通用路径是 `engine/notify.sh`（feishu/wecom/desktop，配 `~/.shuzi-rensheng/config.json` 的 notify 段）。

## 装技能
```bash
bash install.sh        # 检测 ~/.hermes → 装到 ~/.hermes/skills/shuzi-rensheng/
```

## 注意
- **你是常驻 agent**：状态可以放内存，但 setup 进度仍写 `~/.shuzi-rensheng/state.json`
  （跨框架、跨重启）
- **自进化技能别和本包重复**：数字人生的运维经验请写进本包的 `references/`
  或 vault 的 log，不要另建一个「数字人生 2」技能
- 多机模式：你能 SSH → 可以当大脑侧调度采集机；组网见 `references/network-setup.md`
