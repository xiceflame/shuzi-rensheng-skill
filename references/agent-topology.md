# 多 agent 分工与写入边界

> 原则：**每个 agent 负责一个「方向」，只写自己范围内的页**；`journal/` 与 `people/` 由 **owner agent 独占写**。
> 这样多个 agent 并发也不会抢写同一页（避免同步冲突与内容互相覆盖）。

## 典型分工（可按需增删）

| Agent | 方向 | 读写范围 |
|---|---|---|
| **daily-owner**（owner） | 日常 / 时间线 | `wiki/journal/`（**独占**）· `wiki/people/`（**独占**）· `wiki/tasks/` · `wiki/monthly/` · `wiki/quarterly/` |
| **finance-agent** | 财务 | `wiki/finance/` |
| **business-agent** | 商务 / 客户 / 合作 | `wiki/projects/` 的商务类页 |
| **coding-agent** | 软件 / AI 项目 | `wiki/projects/` 的软件类页 |
| **engineer-agent** | 工程 / 硬件 / 装置 | `wiki/projects/` 的工程类页 |
| **hr-agent** | 人事 / 团队 | 公司页的「团队」小节（`people/` 只读） |
| **review-agent** | 总览 / 汇总 | **只读**全库 + 复核月/季汇总 |
| **main / 采集 agent** | 采集 / 管道 | `raw/`（不入 `wiki/`） |

> 方向 ≠ 固定：按你的领域划分。关键是**每块内容有唯一负责人**。

## 三条规则

1. **检索统一走 MCP / CLI**：`vault_search`（召回 + 重排）或 `vaultq "<问题>" -k 5`；动手前先读 `wiki/index.md`。
2. **写入边界**：只写自己范围内的页；**跨领域信息** → 写进自己领域页并标「**待 <owner> 汇总**」。
   例：hr-agent 发现<同事A>薪酬 → 写进公司页团队小节 + 标「待 daily-owner 汇总」。
3. **触发**：owner 有 chat 摘要 / rollup / lint；各方向有**每周汇总**（读本周 journal → 增量写进自己领域页）。

## 怎么落地（新 agent 接入三步）

1. **装技能**：`bash install.sh`（检测到 OpenClaw 时自动把 SKILL.md + references 复制到每个 workspace 的 `skills/shuzi-rensheng/`）。
2. **写职责**：在其 `AGENTS.md` 追加一节：
   ```markdown
   ## 数字人生（知识库）职责
   - 我的方向：<方向>
   - 读写范围（只写这些）：<页/目录>
   - 写入边界：journal/ 与 people/ 由 owner 独占写；跨领域信息标「待 owner 汇总」
   - 检索：MCP `vault_search` / `vaultq`
   - 规范：~/<vault>/CLAUDE.md 与本技能
   ```
3. **验证**：`openclaw skills check --agent <id>` 显示 `shuzi-rensheng` Ready；
   `openclaw automations list` 能看到其周汇总（若配了）。

## 写入顺序与并发

- 多个 agent 同时写**不同页**：安全。
- 同时写**同一页**：会产 `*.sync-conflict-*` → 由**冲突哨兵**收口。
- 大改（移动/重命名大量页）：**先暂停同步**，改完恢复。

## 数据层的 agent 路由（engineer / business 双向消费）

 导入的仓库关键文件（docs/README/进展记录）是**跨方向资产**：

| 方向 | 怎么用 |
|---|---|
| **engineer** | 读实现细节与技术状态；更新项目页「当前进展」的技术面 |
| **business** | 读项目最新进展与**闭环完成情况**（交付/合同/收款节点），支撑运营管理（如某项目的首单闭环、客户跟进） |

规则：项目页的「开发进展数据源」小节列出已索引的仓库位置；
business 周汇总（business-weekly）核对闭环时**先查数据源再查聊天**，
聊天里的说法与仓库进展不一致时以仓库为准并标注差异。
