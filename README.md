# 数字人生（shuzi-rensheng）· 你的私人记忆库

> **业务主线与本次改进**：[微信获取 → 条件记忆 → Obsidian 管理](references/wechat-memory-obsidian.md)。保留现有授权采集与解密路线，新增可核验的恢复报告、稳定消息事件和导出筛选。Obsidian 管理视图为样板，完整 Agent 条件查询与用户属性回读仍是待实施项目，不把展示字段当成已经生效的权限控制。

[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/xiceflame/shuzi-rensheng-skill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/core-macOS%20%7C%20Linux-lightgrey.svg)](#上手需要什么)
[![Privacy](https://img.shields.io/badge/隐私-local--first%20本地优先-brightgreen.svg)](#费用与隐私)
[![AI Engines](https://img.shields.io/badge/AI%20引擎-OpenClaw%20%7C%20Hermes%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20API-orange.svg)](#一键部署到你的-ai-助手)

> WX 里聊过的事、发过的语音、收到的文件——过了半年还想找回来吗？
> 这个工具把它们**整理成一座属于你自己的、可搜索的知识库**。
> 知识库文件保存在你指定的电脑上；使用外部模型、嵌入或重排服务时，相关内容会发送到你配置的服务。数据外发与服务费用需分别确认。

> **安全修复版：升级前先读 [兼容性与迁移说明](references/review-fixes.md)。** 本版限制内置 API 的文件操作、保留冲突来源、传播失败回执，并将查询与安装分流。定时任务需明确选装；旧 Ollama 整理适配器暂不支持；原生 Windows 全链路未验收。已有部署副本不会随 git 更新自动覆盖。

---

## 它能帮你做什么

- **用一句话检索历史资料**：问「上次跟张三聊报价是什么时候？」——在已导入、已索引且允许访问的范围内查找，并要求关键结论**点回原始聊天记录**核对。速度与准确性取决于数据和服务状态。
- **整理每日记录**：配置并验收任务后，AI 可将授权资料整理成「我的每一天」：事件、人物、待办，事实与解读分别标注。
- **按人物建立档案**：用人物页记录有出处的时间线、重要约定和关系信息；不能仅靠简称猜测合并人物。提醒需另外配置渠道和任务。
- **按项目归档附件**：对授权的 PDF、Office、图片与扫描件抽取内容，按项目和人物分类。不同格式、平台与下游脚本需分别验收。
- **用 Obsidian 浏览**：直接打开 Markdown 知识库；手机访问需另行配置你认可的同步方式。

**管线（30 秒版）**：

```text
WX / 手工资料 / 其他授权导出
      ↓
raw/ 证据层（对整理 Agent 只读，可回溯）
      ↓
AI 提炼 → wiki/ 整理层（journal 时间轴 × people 人物轴 × projects 项目轴）
      ↓
qkb 混合召回 → 路径过滤 → 可选重排 → 带出处的回答
```

摘要是阅读入口，不是事实裁决依据；出现矛盾时需核对原始证据和业务权威记录。

## 一键部署到你的 AI 助手

安装器提供统一入口，但**技能复制、模型配置、系统权限和链路验收是不同步骤**：

```bash
bash install.sh
```

| AI 助手 | 当前安装器的行为 |
|---|---|
| [OpenClaw](https://github.com/openclaw/openclaw) | 检测到 CLI 和 `~/.openclaw/` 后，为已有 `workspaces/*/` 复制技能及子技能；不等于 gateway、定时和通知已配置完成 |
| Claude Code | 没有进入 OpenClaw 分支且存在 `~/.claude/` 时，复制到用户级技能目录 |
| [Hermes](https://github.com/NousResearch/hermes-agent) | 没有进入前两种分支且存在 `~/.hermes/` 时，复制到其技能目录 |
| Cursor / Codex 等 | 按 `setup/frameworks/` 的说明接入；当前安装器不自动创建这些框架的技能目录 |
| 没有 Agent 框架 | 保留包内技能，通过配置内置 API 文件工具或 manual 人工兜底使用 |

任务定义与执行引擎解耦，但不同后端的工具和权限并不等价。`auto` 仅使用已配置且启用的内置 API，否则进入 manual；外部框架需明确选择并单独设置沙箱。打印提示词不表示任务已执行。

## 上手需要什么

| 需要 | 说明 |
|---|---|
| 一台电脑 | 本版受限执行器与调度以 macOS / Linux、Python 3.9+ 为目标；原生 Windows 全链路未验收 |
| **可选**：LLM API key | 使用支持工具调用的兼容 API，费用按实际数据量和服务价格计算；没有时可采用人工兜底 |
| **可选**：WX | 不接 WX 也能用，可先手工导入少量已授权资料 |
| **可选**：QKB 与嵌入模型 | 用于语义检索，需独立配置与验收；未安装时可直接浏览 Markdown |

## 出错时如何定位安装实例

本版本加入了本地诊断与脱敏报告：

- `python3 setup/instance.py --json` 查看实例 ID
- `python3 engine/diagnostics.py --export ./report.json` 生成脱敏报告
- 提交问题时只提供 report_id、instance_id、版本和错误码，不要上传聊天正文、原始数据库、Obsidian 正文或凭据

自动上传默认关闭，离线导出优先。完整字段和隐私边界见 `references/diagnostics.md`。

## 快速开始（3 步）

```bash
# ① 拿到本包
 git clone https://github.com/xiceflame/shuzi-rensheng-skill.git
 cd shuzi-rensheng-skill

# ② 安装（会探测环境并复制技能、初始化所选目录）
 bash install.sh

# ③ 对你的 AI 说「请继续配置数字人生知识库」
```

第②步可预览定时任务；实际注册需要明确指定任务并启用 `schedule.enabled`，不会默认安装一整套。第③步按 `setup/SETUP.md` 确认数据源、API 和提醒渠道；普通查询、审阅或第一条消息不会触发安装。

## 装好之后，每天会发生什么

完成各链路验收后，系统可按你明确选装并启用的任务运行。以下是目标工作流，不表示仅安装后就全部接通：

| 它做的事 | 默认计划 | 验收依据 |
|---|---|---|
| 采集 WX 新消息 | 每 4 小时 | 导出清单和原始记录，而非中继启动成功 |
| 语音转文字、文件抽内容 | 按任务配置 | 成功、失败和待处理清单 |
| 整理「我的每一天」与人物档案 | 08:07 / 21:07 | 有出处的页面与索引回执 |
| 知识库体检 | 每周日 | 格式、断链等检查结果 |
| 月度汇总 | 每月 1 日 | 可下钻核对的汇总页面 |

调整时先预览指定任务：

```bash
bash setup/schedule.sh qkb-follow lint --dry-run
```

启用配置并确认后，去掉 `--dry-run` 注册。修改时间后重新生成相关任务；旧调度的停用与迁移见升级说明。时间采用机器本地时区。`EXECUTED_UNVERIFIED` 只表示引擎退出正常，不等于笔记、索引或业务任务已验收。

## 三种部署形态

| 形态 | 适合 | 要点 |
|---|---|---|
| **单机 + API** | 接受将授权内容发送到指定服务的用户 | 本地做采集与文件处理，AI 提炼调用所配置的 API |
| **本地处理 + 人工兜底** | 不想用云服务 | 可按环境配置本地转写/OCR/嵌入，整理采用人工兜底；旧 Ollama 适配器尚无可靠文件工具循环，本版明确返回不支持 |
| **多机**（采集机 + 大脑 + 可选算力机） | 愿意维护网络与同步的进阶用户 | 用自己的 [Tailscale](https://tailscale.com) 组网，分别配置数据与服务权限，见 `references/network-setup.md` |

## 费用与隐私

**本地处理**：配置为本地执行的导出、转写、文档抽取和索引无需模型 API 费用，但仍消耗本机资源。

**外部服务费用**：整理、嵌入、重排或其他处理选用外部 API 时，按实际调用收费。先用小样本估算，不承诺固定月费。

**隐私**：磁盘文件保存在指定位置，但 API 会收到相应输入。普通检索在重排和输出前过滤 private 等路径；这不是 QKB 内部权限隔离，已有私密索引、直接 QKB 调用和云端嵌入需另外处理。多机同步、备份与服务访问也需独立配置。

## 常见问题

**Q：需要显卡吗？**
取决于模型、数据量与可接受速度。先评估本地资源；不能因为性能不足就把资料发送给未授权 API，也不能将不同后端视为能力完全相同。

**Q：WX 怎么接入？有风险吗？**
采集是独立选项，需核对数据授权、应用版本和系统权限。macOS 与 Windows 的历史参考分别见 `references/wechat-pipeline.md`、`references/windows-collector.md`；这些文档不代表所有版本兼容或 Windows 全链路已验收。也可先手工导入少量授权文件。

**Q：AI 会不会编造记忆？**
仍可能误解资料或总结错误，因此要求结论带出处、事实与计划/解读分开，不确定内容标为待确认。原文核对和业务权威记录不能由 AI 的自我确认替代。

**Q：我是小白，装得动吗？**
明确告诉 AI「请帮我配置数字人生」，从最小功能开始。升级前先备份，不要为重装而删除知识库。只做手工笔记也可使用，不必启用自动采集和定时任务。

**Q：支持其他 IM（钉钉/飞书/WhatsApp…）吗？**
可将合法授权的导出文件接入同一证据与整理流程，但需验证格式、去重、来源映射和索引，不能仅复制文件就认定自动接入完成。

---

## 进阶指南

<details>
<summary><b>依赖清单与组件</b></summary>

| 组件 | 本包自带？ | 说明 |
|---|---|---|
| 采集/整理脚本、任务模板、文档 | ✅ | `assets/` `engine/` `setup/`；下游脚本需分别验收 |
| 检索侧脚本（vaultq / qkb-follow…） | ✅ | `install.sh` 部署到 `~/.config/qkb/`，不自动覆盖已有副本 |
| [qkb](https://www.npmjs.com/package/@miguelarios/qkb) 主程序 | ❌ `npm i -g @miguelarios/qkb` | 需核对安装版本、配置和输出格式 |
| 本机模型（whisper/OCR/嵌入） | ❌ `bash setup/local-models.sh` | 安装前审阅依赖及模型下载；按环境选择 |
| [Obsidian](https://obsidian.md) | ❌ | Markdown 浏览界面 |
| Python 3.9+ / Node | ❌ | 核心脚本与可选 MCP 运行时 |
| [beancount](https://github.com/beancount/beancount)（可选记账） | ❌ `pip install beancount` | 确定性账本转换与校验，API 文件工具不能代替执行 |
| Tailscale（可选，多机） | ❌ | 见 `references/network-setup.md` |

</details>

<details>
<summary><b>完整文档地图</b></summary>

| 想了解 | 看哪 |
|---|---|
| 引导式安装全流程（8 步） | `setup/SETUP.md` |
| WX 采集（macOS runbook / Windows） | `references/wechat-pipeline.md` / `references/windows-collector.md` |
| 语音转写分层 | `references/speech-to-text.md` |
| 附件/PDF/OCR 分层 | `references/attachments-ocr.md` |
| 语义检索与重排 | `references/vector-search.md` · `references/embedding-setup.md` |
| 显卡要求 / 性能分级 | `references/gpu-requirements.md` · `references/performance-tiering.md` |
| 历史回填与人物深挖（DeepFill） | `skills/shuzi-deepfill/` |
| 财务集成 | `references/finance-integration.md` |
| 多机组网（Tailscale） | `references/network-setup.md` |
| 定时任务选装 | `setup/schedule.sh` |
| 多 agent 分工 / 单 agent | `references/agent-topology.md` · `references/single-agent.md` |
| AI 助手适配 | `setup/frameworks/` |
| 安全护栏 | `references/safety.md` |
| 安全修复、迁移与未覆盖范围 | `references/review-fixes.md` |
| Obsidian 接入/多端同步 | `references/obsidian.md` |
| 成本参考 | `references/cost.md`，按实际服务重新估算 |

</details>

<details>
<summary><b>设计原则</b></summary>

1. **证据层/整理层分离**：`raw/` 原始证据对整理 Agent 只读；`wiki/` 是有出处的整理结果。
2. **双轴视图**：日记（时间）× 人物（关系），与项目页互相链接。
3. **增量与批量分开**：日常处理增量，首次回填单独评估数据、资源和费用。
4. **引擎解耦但不假定等价**：不同后端的工具、权限与验收能力分别说明。
5. **安全与可恢复**：冲突保留全部来源；文件覆盖先校验旧版本与备份；失败如实返回。
6. **按授权使用模型**：确定性程序负责能校验的处理，AI 辅助语义整理；外发前确认范围。

</details>

## 测试

```bash
python3 -m unittest discover -s tests -v
node --check assets/scripts/vault-search-mcp.mjs
```

离线回归使用临时目录与合成资料，不访问真实 WX、不调用付费模型、不注册系统服务。模拟测试不等于 QKB、外部 Agent 或完整生产链路验收。

## 许可

MIT（见 [LICENSE](LICENSE)），使用和分发需保留相应版权与许可声明。
