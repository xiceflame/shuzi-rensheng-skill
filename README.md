# 数字人生（shuzi-rensheng）· 你的私人记忆库

<<<<<<< HEAD
[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/xiceflame/shuzi-rensheng-skill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](#)
[![Privacy](https://img.shields.io/badge/隐私-local--first%20本地优先-brightgreen.svg)](#费用与隐私)
[![AI Engines](https://img.shields.io/badge/AI%20引擎-OpenClaw%20%7C%20Hermes%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20API-orange.svg)](#一键部署到你的-ai-助手)

> WX 里聊过的事、发过的语音、收到的文件——过了半年还想找回来吗？
> 这个工具把它们**自动整理成一座属于你自己的、可搜索的知识库**。
> 数据全部留在你自己的磁盘上，不上传、不订阅。
=======
> **安全修复版：升级前先读 [兼容性与迁移说明](references/review-fixes.md)。** 本版收紧内置 API 的文件权限、保留冲突来源、传播失败回执，并将查询与安装分流。定时任务需明确选装；旧 Ollama 整理适配器暂不支持；原生 Windows 全链路未验收。已有部署副本不会随 git 更新自动覆盖。

> 微信里聊过的事、发过的语音、收到的文件——过了半年还想找回来吗？
> 这个工具把它们**整理成一座属于你自己的、可以搜索的知识库**。
> 知识库文件保存在你指定的电脑上；使用外部模型、嵌入或重排服务时，相关内容会发送到你配置的服务。是否外发与服务费用需分别确认。
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

---

## 它能帮你做什么

<<<<<<< HEAD
- **一句话找回任何记忆**：问「上次跟张三聊报价是什么时候？」——两阶段检索（混合召回 + 重排）秒级命中，**每条结论可点回原始聊天记录**，杜绝 AI 幻觉。
- **每天自动写日记**：早 8 点 / 晚 9 点，LLM 自动把当天的会话整理成「我的每一天」：事件、人物、待办、意义分层标注。
- **人物自动建档**：每个常联系人一个页面——时间线、别名推断、约定追踪、生日/纪念日，以及「超过 90 天未联系」的关系维护提醒。
- **附件不再石沉大海**：WX 里的 PDF / Office / 图片 / 扫描件，分层抽取内容（文本层直抽 → Vision/RapidOCR → MinerU），按项目与人物归档。
- **手机上随时翻**：[Obsidian](https://obsidian.md)（免费）打开，双链图谱 + 全文检索。

**管线（30 秒版）**：

```
WX 本地解密导出（密钥不出本机，纯脚本零成本）
      ↓
raw/ 证据层（只读、可回溯）
      ↓
LLM 提炼 → wiki/ 整理层（journal 时间轴 × people 人物轴，互链）
      ↓
检索：qkb 混合召回（BM25+向量+RRF）→ bge-reranker 重排 → vaultq 秒回
```

## 一键部署到你的 AI 助手

装好 [OpenClaw](https://github.com/openclaw/openclaw) 或 [Hermes](https://github.com/NousResearch/hermes-agent)？**一条命令接入**：

```bash
bash install.sh
```

| AI 助手 | install.sh 自动做的事 |
|---|---|
| 🦞 [**OpenClaw**](https://github.com/openclaw/openclaw) | 发现 `~/.openclaw/` 下**所有 agent workspace**，逐个装好技能（含子技能）；gateway cron / channels 直接可用 |
| 🤖 [**Hermes**](https://github.com/NousResearch/hermes-agent) | 装到 `~/.hermes/skills/`——本技能就是 [agentskills.io](https://agentskills.io) 开放标准的 SKILL.md，**原生格式零转换**；内置 cron / gateway 渠道直接接管定时与通知 |
| Claude Code / Cursor / Codex | 装到对应技能目录（`~/.claude/skills/` 等） |
| 都没有 | 纯 API 模式，或「打印 prompt 人工贴」兜底——照样完整可用 |

> 引擎无关是设计原则：任务定义与执行引擎解耦（`engine/run.sh` 6 个适配器），换助手不换数据。
=======
- **用一句话检索历史资料**：问「上次跟张三聊报价是什么时候？」——在已导入、已索引且允许访问的范围内查找，并要求关键结论**点回原始聊天记录**核对。速度和准确性取决于数据与服务状态。
- **整理每日记录**：配置并验收对应任务后，AI 可将授权资料整理成「我的每一天」：见了谁、聊了什么、有什么待办。
- **按人物建立档案**：用人物页记录有出处的时间线、重要约定与关系信息。提醒需要另外配置渠道和任务，不能仅因存在人物页就视为已接通。
- **按项目归档文件**：对已授权的 PDF、表格、图片抽取内容，按项目和人物分类；格式与平台兼容性需逐项验证。
- **用 Obsidian 浏览**：直接打开 Markdown 知识库；手机访问需另行配置你认可的同步方式。

**它是怎么工作的**（30 秒版）：经授权的采集脚本在本地导出资料 → AI 在受控范围内把原始记录提炼成笔记 → 你用 Obsidian 浏览，或通过检索入口提问。使用 API 会向所配置的模型服务发送必要内容；纯手工笔记模式无需模型服务。
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

## 上手需要什么

| 需要 | 说明 |
|---|---|
<<<<<<< HEAD
| 一台电脑 | macOS / Windows / Linux |
| **可选**：LLM API key | [DeepSeek](https://platform.deepseek.com) 等 OpenAI 兼容端点，每月几元级；不用也行（Ollama 全本地 / 人工兜底） |
| **可选**：WX | 不接 WX 也能用——任何文件丢进 `raw/` 即进同一套流水线 |
=======
| 一台电脑 | 本版受限执行器和调度以 macOS / Linux、Python 3.9+ 为目标；原生 Windows 全链路未验收 |
| **可选**：一个 AI 的 API key | 使用支持工具调用的兼容 API，费用按实际数据量和服务价格计算；没有时可采用人工兜底 |
| **可选**：微信 | 不接微信也能用，可先手工导入少量已授权资料 |
| **可选**：QKB 与嵌入模型 | 用于语义检索，需独立配置和验收；未安装时可直接浏览 Markdown |
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

## 快速开始（3 步）

```bash
# ① 拿到本包
git clone https://github.com/xiceflame/shuzi-rensheng-skill.git
cd shuzi-rensheng-skill

<<<<<<< HEAD
# ② 一键安装（自动探测环境 + AI 助手）
=======
# ② 安装（会探测你的环境）
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)
bash install.sh

# ③ 对你的 AI 说「请继续配置数字人生知识库」
```

<<<<<<< HEAD
- 第②步会问你要不要**顺手选装定时任务**（自动整理 / 语音转写 / 体检 / 月汇总……9 项目录按需勾选）
- 第③步之后，AI 像朋友帮你装机一样**一步一步引导**：接不接 WX、配不配 API、提醒发到哪——每步可跳过、随时可重来

## 装好之后，每天会发生什么

你什么都不用做，选装的定时任务自动运行：

| 它做的事 | 频率 | 技术形态 |
|---|---|---|
| 采集 WX 新消息 | 每 4h | 本地解密 + 增量导出（macOS 走 Terminal 中继/ssh 回环，Windows 免权限） |
| 语音转文字 | 每 4h | whisper 系本机模型（Apple Silicon 自动用 mlx-whisper） |
| 整理「我的每一天」+ 人物档案 | 08:07 / 21:07 | LLM 提炼，写入带 frontmatter 的 Markdown，自动登记索引 |
| 附件抽取 / OCR | 跟随采集 | 分层：文本层直抽 → Vision OCR → MinerU（高价值件） |
| 知识库体检 | 每周日 | 断链 / 孤岛 / 索引一致性 lint |
| 月度汇总 | 每月 1 日 | 汇总层生成，检索先命中汇总再下钻 |

调整像点菜：重跑 `bash setup/schedule.sh`。
=======
- 第②步安装时可预览定时任务；实际注册需要明确指定任务并启用 `schedule.enabled`，不会默认装上一整套。
- 第③步明确授权配置后，AI 按 `setup/SETUP.md` 引导你确认数据源、API 和提醒渠道。普通查询、审阅或第一条消息不会触发安装。

> 没有装 AI 助手（Claude Code / OpenClaw / Hermes 等）？可使用受限 API 模式，或用 manual 打印任务交给人工处理。外部 Agent 框架需要独立设置沙箱；“打印了任务”不代表任务已执行。

## 装好之后，每天会发生什么

完成各链路验收后，系统可按你明确选装并启用的定时任务运行。以下是目标工作流，不代表仅安装后就已全部接通：

| 它做的事 | 默认计划 | 验收依据 |
|---|---|---|
| 采集微信新消息 | 每 4 小时 | 导出清单与原始记录，而非中继启动成功 |
| 语音转文字、文件抽内容 | 按任务配置 | 成功、失败和待处理清单 |
| 整理「我的每一天」+ 更新人物档案 | 08:07 / 21:07 | 有出处的页面与索引回执 |
| 知识库体检 | 每周日 | 格式、断链等检查结果 |
| 月度汇总 | 每月 1 日 | 可下钻核对的汇总页面 |

调整时先预览指定任务，例如：

```bash
bash setup/schedule.sh qkb-follow lint --dry-run
```

启用配置并确认后，去掉 `--dry-run` 注册。修改时间后重新生成相关任务；旧调度的停用与迁移见升级说明。时间采用机器本地时区。`EXECUTED_UNVERIFIED` 只表示引擎退出正常，不等于笔记、索引或业务任务已验收。
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

## 三种部署形态

| 形态 | 适合 | 要点 |
|---|---|---|
<<<<<<< HEAD
| **单机 + API**（推荐） | 大多数人 | 脏活本地跑，LLM 提炼走便宜 API；无需 GPU |
| **单机全本地** | 数据不出门党 | `bash setup/local-models.sh` 一键装 whisper/OCR/嵌入；LLM 用 [Ollama](https://ollama.com) |
| **多机**（采集机 + 大脑 + GPU 机） | 进阶 | 用你自己的 [Tailscale](https://tailscale.com) 组私有内网（零公网暴露），见 `references/network-setup.md` |

## 费用与隐私

- **免费（占大头）**：WX 解密、语音转写、PDF/OCR 抽取、索引构建——全部本地脚本，零 API 调用
- **花钱（可选）**：LLM 提炼笔记——DeepSeek 实测每月几元；或 Ollama 免费；或人工
- **隐私**：原始数据、密钥、知识库**只在你的磁盘**。多机版走你自己的 tailnet，不暴露公网。本包不含任何回传通道。

## 常见问题

**Q：需要显卡吗？**
不需要。8GB+ 显存可加速转写/嵌入（可选项）；没有则自动走 API 或纯本地慢一点，功能一致。

**Q：WX 怎么接入？有风险吗？**
macOS 走本包自研管线（本地密钥扫描 + 解密，需授权几步，见 `references/wechat-pipeline.md`）；Windows 免权限（`references/windows-collector.md`）。不想折腾就不接——文件投喂模式零配置。

**Q：AI 会不会编造记忆？**
多层防幻觉：结论必须带出处链接（可点回原始聊天）；四类标注（事实/计划/意义/待确认）；低置信度不入库、转「待确认」问人。

**Q：我是小白，装得动吗？**
对 AI 说「开始」即可——8 步引导，每步可跳过。极端情况有零配置的手工投喂模式。

**Q：支持其他 IM（钉钉/飞书/WhatsApp…）吗？**
能导出成文件的都能进 `raw/` 走同一管线；WX 是打磨最深的数据源。
=======
| **单机 + API** | 接受将授权内容发送到指定服务的用户 | 本地做采集与文件处理，AI 提炼调用所配置的 API |
| **单机本地处理 + 人工兜底** | 不想用云服务 | 可按环境配置本地转写/OCR/嵌入，整理采用人工兜底；旧 Ollama 适配器尚无可靠文件工具循环，本版明确返回不支持 |
| **多机**（采集机 + 大脑 + 可选算力机） | 愿意维护网络和同步的进阶用户 | 用你自己的 Tailscale 组网，分别配置数据与服务权限，见 `references/network-setup.md` |

## 费用与隐私

- **本地处理**：配置为本地执行的导出、转写、文档抽取与索引无需模型 API 费用，但仍消耗本机资源。
- **外部服务费用（可选）**：整理、嵌入、重排或其他处理选用外部 API 时，按实际调用收费；先小样本估算，不承诺固定月费。
- **隐私**：磁盘文件保存在你指定的位置，但 API 会收到相应输入。普通检索会在重排与输出前过滤 private 等路径；这不是 QKB 内部权限隔离，已有私密索引及直接 QKB 访问要另外处理。多机同步、备份与服务访问也需独立配置。

## 常见问题

**Q：需要好的显卡吗？**
取决于使用的模型、数据量和可接受速度。先用小样本评估本地资源；不会因为本机性能不足就自动把资料发给未授权 API，也不能将不同执行后端视为能力完全相同。

**Q：微信怎么接入？会不会有风险？**
采集是独立选项，需要逐项核对数据授权、应用版本和系统权限。macOS 与 Windows 的历史参考分别见 `references/wechat-pipeline.md`、`references/windows-collector.md`；这些文档不代表所有版本兼容或原生 Windows 全链路已验收。也可先手工导入少量已授权文件，不接微信。

**Q：AI 会不会编造我的记忆？**
仍可能误解资料或总结错误，因此要求关键结论带出处、事实与计划/解读分开，不确定内容标为待确认。原文核对与业务权威记录不能由 AI 的自我确认替代。

**Q：我是小白，装得动吗？**
明确告诉 AI「请帮我配置数字人生」，从已有资料和最小功能开始。升级前先备份，不要为了重新安装而删除知识库。只做手工笔记也可使用，不必启用自动采集和定时任务。

**Q：支持其他聊天工具吗（钉钉/飞书/WhatsApp…）？**
可将合法授权的导出文件接入同一套证据与整理流程，但需验证格式、去重、来源映射和索引，不能仅复制文件后就认定自动接入完成。
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

---

## 进阶指南

<details>
<summary><b>依赖清单与组件</b></summary>

| 组件 | 本包自带？ | 说明 |
|---|---|---|
<<<<<<< HEAD
| 采集/整理脚本、任务模板、文档 | ✅ | `assets/` `engine/` `setup/` |
| 检索侧脚本（vaultq / qkb-follow / embed-proxy…） | ✅ | `install.sh` 部署到 `~/.config/qkb/` |
| [qkb](https://www.npmjs.com/package/@miguelarios/qkb) 语义检索主程序 | ❌ `npm i -g` | 未装时 Obsidian 搜索兜底 |
| 本机模型（whisper / OCR / 嵌入） | ❌ `bash setup/local-models.sh` | 一键装齐，全离线 |
| [Obsidian](https://obsidian.md) | ❌ 免费 | 浏览界面 |
| [beancount](https://github.com/beancount/beancount)（可选记账） | ❌ `pip install` | 财务方案 A：官方账单 → 复式记账 |
=======
| 采集/整理脚本、任务模板、文档 | ✅ | `assets/` `engine/` `setup/`；不同下游脚本需分别验收 |
| 检索侧脚本（vaultq / qkb-follow…） | ✅ | `install.sh` 部署到 `~/.config/qkb/`，不自动覆盖已有副本 |
| `qkb` 主程序（语义检索） | ❌ `npm i -g @miguelarios/qkb` | 需核对安装版本、配置和输出格式 |
| 本机模型（whisper/OCR/嵌入） | ❌ `bash setup/local-models.sh` | 安装前审阅所需依赖和模型下载；按环境选择 |
| Obsidian | ❌ | Markdown 浏览界面 |
| Python 3.9+ / Node | ❌ | 核心脚本与可选 MCP 运行时 |
| beancount（可选，记账） | ❌ `pip install beancount` | 确定性账本转换与校验，API 文件工具不能代替执行 |
| Tailscale（可选，多机） | ❌ | 见 `references/network-setup.md` |
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

</details>

<details>
<summary><b>完整文档地图</b></summary>

| 想了解 | 看哪 |
|---|---|
| 引导式安装全流程（8 步） | `setup/SETUP.md` |
<<<<<<< HEAD
| WX 采集（macOS runbook / Windows） | `references/wechat-pipeline.md` / `windows-collector.md` |
| 语音转写分层（短片 vs 长音频） | `references/speech-to-text.md` |
| 附件/PDF/OCR 分层 | `references/attachments-ocr.md` |
| 语义检索与重排 | `references/vector-search.md` · `embedding-setup.md` |
| 显卡要求 / 性能分级 | `references/gpu-requirements.md` · `performance-tiering.md` |
| 历史回填与人物深挖（DeepFill） | `skills/shuzi-deepfill/` |
| 财务集成 | `references/finance-integration.md` |
| 多机组网（Tailscale） | `references/network-setup.md` |
| 定时任务选装 | `setup/schedule.sh` |
| 多 agent 分工 / 单 agent | `references/agent-topology.md` · `single-agent.md` |
| AI 助手适配 | `setup/frameworks/`（OpenClaw / Hermes / Claude Code / Cursor / Codex / API-only） |
| 安全护栏 | `references/safety.md` |
=======
| 微信采集（macOS runbook / Windows） | `references/wechat-pipeline.md` / `references/windows-collector.md` |
| 语音转写分层（短片 vs 长音频） | `references/speech-to-text.md` |
| 附件/PDF/OCR 分层 | `references/attachments-ocr.md` |
| 语义检索与重排 | `references/vector-search.md` · `references/embedding-setup.md` |
| 显卡要求 / 性能分级 | `references/gpu-requirements.md` · `references/performance-tiering.md` |
| 首次历史数据回填（DeepFill） | `skills/shuzi-deepfill/` |
| 财务记账（官方账单→beancount） | `references/finance-integration.md` |
| 多机组网（Tailscale） | `references/network-setup.md` |
| 定时任务选装 | `setup/schedule.sh` |
| 多 agent 分工 / 单 agent 模式 | `references/agent-topology.md` · `references/single-agent.md` |
| 接入哪些 AI 助手 | `setup/frameworks/`（OpenClaw / Claude Code / Cursor / Codex / Hermes / API-only） |
| 安全护栏（不许改坏文件） | `references/safety.md` |
| 安全修复、迁移与未覆盖范围 | `references/review-fixes.md` |
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)
| Obsidian 接入/多端同步 | `references/obsidian.md` |
| 成本参考 | `references/cost.md`，按实际服务重新估算 |

</details>

<details>
<summary><b>设计原则</b></summary>

<<<<<<< HEAD
1. **证据层/整理层分离**：`raw/`（只读原始）≠ `wiki/`（AI 提炼），任何结论可回溯到原话
2. **双轴视图**：journal（时间）× people（关系），双向链接成图谱
3. **增量与批量分离**：日常本地细水长流，首次回填才上算力
4. **引擎无关**：prompt 与执行解耦，6 个适配器 + manual 兜底
5. **安全护栏**：不删 raw/、写入边界、并发锁、断点续跑
6. **贵模型只花在刀刃上**：免费本地优先，API/GPU 只用于提炼与批量
=======
1. **证据层/整理层分离**：`raw/` 原始证据对整理 Agent 只读；`wiki/` 是有出处的整理结果。
2. **双视图**：日记（时间轴）+ 人物（关系轴），与项目页互相链接。
3. **增量与批量分开**：日常处理增量，首次回填单独评估数据、资源和费用。
4. **引擎解耦但不假定等价**：不同后端的工具、权限与验收能力分别说明。
5. **安全与可恢复**：冲突保留所有来源；文件覆盖先校验旧版本和备份；失败如实返回。
6. **按授权使用模型**：确定性程序负责能校验的处理，AI 辅助语义整理；外发前确认范围。
>>>>>>> 17a3822 (fix: harden skill execution, indexing and scheduling)

</details>

## 测试

```bash
python3 -m unittest discover -s tests -v
node --check assets/scripts/vault-search-mcp.mjs
```

离线回归使用临时目录与合成资料，不访问真实微信、不调用付费模型、不注册系统服务。模拟测试不等于 QKB、外部 Agent 或完整生产链路验收。

## 许可

MIT（见 [LICENSE](LICENSE)），使用和分发需保留相应版权与许可声明。
