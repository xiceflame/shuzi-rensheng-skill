# 数字人生（shuzi-rensheng）· 你的私人记忆库

[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/xiceflame/shuzi-rensheng-skill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](#)
[![Privacy](https://img.shields.io/badge/隐私-local--first%20本地优先-brightgreen.svg)](#费用与隐私)
[![AI Engines](https://img.shields.io/badge/AI%20引擎-OpenClaw%20%7C%20Hermes%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20API-orange.svg)](#一键部署到你的-ai-助手)

> WX 里聊过的事、发过的语音、收到的文件——过了半年还想找回来吗？
> 这个工具把它们**自动整理成一座属于你自己的、可搜索的知识库**。
> 数据全部留在你自己的磁盘上，不上传、不订阅。

---

## 它能帮你做什么

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

## 上手需要什么

| 需要 | 说明 |
|---|---|
| 一台电脑 | macOS / Windows / Linux |
| **可选**：LLM API key | [DeepSeek](https://platform.deepseek.com) 等 OpenAI 兼容端点，每月几元级；不用也行（Ollama 全本地 / 人工兜底） |
| **可选**：WX | 不接 WX 也能用——任何文件丢进 `raw/` 即进同一套流水线 |

## 快速开始（3 步）

```bash
# ① 拿到本包
git clone https://github.com/xiceflame/shuzi-rensheng-skill.git
cd shuzi-rensheng-skill

# ② 一键安装（自动探测环境 + AI 助手）
bash install.sh

# ③ 对你的 AI 说「开始」
```

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

## 三种部署形态

| 形态 | 适合 | 要点 |
|---|---|---|
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

---

## 进阶指南

<details>
<summary><b>依赖清单与组件</b></summary>

| 组件 | 本包自带？ | 说明 |
|---|---|---|
| 采集/整理脚本、任务模板、文档 | ✅ | `assets/` `engine/` `setup/` |
| 检索侧脚本（vaultq / qkb-follow / embed-proxy…） | ✅ | `install.sh` 部署到 `~/.config/qkb/` |
| [qkb](https://www.npmjs.com/package/@miguelarios/qkb) 语义检索主程序 | ❌ `npm i -g` | 未装时 Obsidian 搜索兜底 |
| 本机模型（whisper / OCR / 嵌入） | ❌ `bash setup/local-models.sh` | 一键装齐，全离线 |
| [Obsidian](https://obsidian.md) | ❌ 免费 | 浏览界面 |
| [beancount](https://github.com/beancount/beancount)（可选记账） | ❌ `pip install` | 财务方案 A：官方账单 → 复式记账 |

</details>

<details>
<summary><b>完整文档地图</b></summary>

| 想了解 | 看哪 |
|---|---|
| 引导式安装全流程（8 步） | `setup/SETUP.md` |
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
| Obsidian 接入/多端同步 | `references/obsidian.md` |
| 成本参考 | `references/cost.md` |

</details>

<details>
<summary><b>设计原则</b></summary>

1. **证据层/整理层分离**：`raw/`（只读原始）≠ `wiki/`（AI 提炼），任何结论可回溯到原话
2. **双轴视图**：journal（时间）× people（关系），双向链接成图谱
3. **增量与批量分离**：日常本地细水长流，首次回填才上算力
4. **引擎无关**：prompt 与执行解耦，6 个适配器 + manual 兜底
5. **安全护栏**：不删 raw/、写入边界、并发锁、断点续跑
6. **贵模型只花在刀刃上**：免费本地优先，API/GPU 只用于提炼与批量

</details>

## 许可

MIT（见 [LICENSE](LICENSE)）——个人使用、修改、分发均自由。
