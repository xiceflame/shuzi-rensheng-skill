---
name: shuzi-rensheng
description: 「数字人生」个人知识库（Obsidian vault）的通用维护规范与从零部署方案：把微信/语音/图片/文件自动整理成人和 AI 都能检索的长期记忆库。含目录结构、双视图（我的每一天 + 人物时间线）、9 个工作流、分层治理、**安全护栏（禁止改坏文件）**、多 agent 分工与写入边界、以及完整的数据采集→整理→检索流水线。当需要读写用户的长期知识库、整理资料、记录想法/日记、查询历史信息、部署或维护这样一套系统时使用。
---

# 数字人生 · 通用规范

> **本技能是「说明书」；运行时以**知识库根目录的 `CLAUDE.md`（"宪法"）与 `README.md`（工程总览）为准。
> 冲突时以 `CLAUDE.md` 为准。首次部署见 `setup/SETUP.md`。


---

## 🚀 首次使用：先走 Setup（**不要跳过**）

> **给 agent**：用户第一次用本技能（说「开始」、发第一条消息、或意图不明）时，
> **先完成初始化**，再谈整理内容。

**流程**：
0. **先搞清楚「我在哪、我是谁」**（最关键的一步）：
   - `bash setup/detect.sh` —— 机器环境（OS / Ollama / 微信 / vault）
   - `bash setup/detect-agent.sh` —— **★ Agent 自我识别**（我是哪个框架？能力边界？）
   - **读 `setup/frameworks/<你的框架>.md`** —— 你的工具名/定时/通知适配说明
   > ⚠️ 不同框架工具名、定时、通知全不同；识别错了后面每步都会用错工具。
1. 读 `~/.shuzi-rensheng/state.json` 看做到哪一步
2. 按 `setup/SETUP.md` **一步一步**引导用户（共 8 步：第 0 步自动探测；
   第 1 步建骨架、第 6 步验收**必需**，其余各步**都可跳过**）
3. 每完成一步更新 `state.json`

**要点**：
- 一次只推进一件事，**先解释「这步在干嘛」再问输入**，别一口气问一堆
- **只做第 1 + 6 步也能用**（得到一个空知识库，手工投喂即可）
- API **全部走 OpenAI 兼容协议**（不用 Anthropic 格式），三类集中配：
  **LLM / Embedding / VLM**，都写在 `~/.shuzi-rensheng/config.json` 一个文件里
- API key **不写进 JSON**，只存环境变量名
- 用户可以随时说「跳过」

**完整指南**：`setup/SETUP.md` · **配置模板**：`assets/config.json`

## 一、这是什么

把**聊天（微信等）、语音、图片、文件**自动变成一座**人和 AI 都能检索**的个人知识库：

```
①采集  每 4h：解密/导出 聊天·语音·图片·文件·视频·财务
          │  rsync / 同步
          ▼
②同步  Syncthing 准实时（两台机器 ⇄；不是 git）
          │
          ▼
③整理  OpenClaw agents 自动：提炼进 wiki 页 → 更新索引 → 向量化
          ▼
④消费  Obsidian 浏览 · qkb/vaultq 语义检索 · 摘要推送（notify 渠道）
```

三层角色：**采集端**（导出机器）· **大脑**（vault 所在机器，agent 整理）· **眼睛**（Obsidian 浏览）。

## 二、⚠️ 安全护栏（最重要 — 不许改坏文件）

> 这套系统**由多个 agent 并发维护**，且 vault 通过 **Syncthing 准实时同步**。以下为**硬性禁止项**，违反会导致丢文件：

1. **`raw/` 只读** —— 原始素材区**只由管线写入**，agent **不改正文**；`raw/media/` 只**新增复制**。**绝不删除** `raw/` 文件。
2. **禁止 `rmtree` / 删目录后重建** —— vault 内大批量重组会触发同步竞态丢文件。**只覆盖、只新增**；要删就**逐个 `os.remove`**；重组前先**暂停同步**。
3. **frontmatter 三件套** —— 每页必须含 `id` + `context` + `created`，否则检索不索引（新建页务必带上，`id` 用 uuid，**不要复制导致重复 id**）。
4. **写入边界** —— `wiki/journal/` 与 `wiki/people/` **由 owner agent 独占写**；其他 agent **只写自己领域的页**；跨领域信息标「待 owner 汇总」。
5. **写操作串行** —— 检索库（qkb）的 `ingest/embed` **必须经锁包装器**（`qkb-lock.py`）调用，否则并发抢插报 UNIQUE 错。
6. **不删除，只归档** —— 过期内容移到 `archive/`，不删。
7. **`wiki/private/`** —— 仅在明确查询时提及，**不主动引用**。
8. **唯一索引** —— 只有 `wiki/index.md` 一份索引；不要再建「项目索引」类文件。
9. **★ 索引范围完整性（最容易漏的一条）** —— 检索库**只索引 vault 内、且带 frontmatter 的页**。
   任何产在 **vault 之外**的中间产物（附件抽文本、OCR、ASR 转写、聊天证据…）**默认是检索不到的**——
   这正是关键信息被遗漏的头号原因。**必须**把这类产物**镜像成带 frontmatter 的 vault 页**
   （`media_text_to_vault.py`，稳定 id 防重嵌），并由常驻守护做**增量索引**（数据一更新就跑，
   不许攒批）。**新增任何一种产物类型时，必须同时接上「镜像 + 增量索引」两步，否则等于没做。**

10. **★ 新连接 / 新进展必沉淀（最容易只留在会话里的一条）** —— 每轮**搜集 / 整理 / 调研**发现的**新连接、新进展**，必须连同相关**资产与记录**整理进库：**① 发现的内容**、**② 用户给出的指令**、**③ 用户提示的关系**；**均保留出处**（发言人 / 日期 / 会话）。**不得只停留在会话里**。

细节与理由见 `references/safety.md`。

## ⭐ 执行清单（任何整理/导入任务，动手前先通读——一次想全，别做一步看一步）

**动手前**
- [ ] 先读 vault 的 `CLAUDE.md` + `wiki/index.md`：这类内容**归谁、放哪、有没有先例**
- [ ] 是**新产物类型**吗？→ 必须同时设计「**镜像进 vault** + **增量索引**」两步（护栏 9）
- [ ] 数据在**库外**吗？→ 默认检索不到，先接镜像
- [ ] 量级判断：**日常增量（本机轻量）**还是**批量回填（服务器/API）**？（分层见 attachments-ocr / speech-to-text）
- [ ] 有没有**同步目录**？大重组先暂停同步

**执行中**
- [ ] **先去重**再处理（内容 hash）
- [ ] **按格式分流**（.doc/.xls→textutil/xlrd；扫描件→OCR；别喂错引擎）
- [ ] 每个文件**超时保护**，失败/超时移 `failed/`，**别让一个坏文件卡死整批**
- [ ] 映射/清单文件（_map.tsv 等）**绝不混进待处理队列**
- [ ] **不删只归档**、增量不 rmtree、写操作经锁
- [ ] 写内容守**四类**（事实/计划/意义解读/待确认）+ **写入边界**（journal/people 归 owner）

**收尾（缺一步就是没做完）**
- [ ] 产物**镜像进检索范围**（库外→vault）
- [ ] `qkb-lock.py ingest` + `embed`（大活走 4090）
- [ ] **双维护**：`index.md` + `log.md`
- [ ] 本轮**新连接 / 新进展**（含**用户指令**、**用户提示的关系**）已连同**出处**入库，未只留在会话里（护栏 10）
- [ ] **验证**：`vaultq`/`qkb search` 用**产物里的原文**实测能搜到；点回原话/原件有效；无断链
- [ ] 批跑结束清点：in/out/failed 三个数对得上，failed 逐个归因

> 这份清单来自真实踩坑。**每一条后面都有一个曾经发生的事故。**

## 三、目录骨架

```
数字人生/
├── README.md      ← 工程总览（先读这个）
├── CLAUDE.md      ← "宪法"：工作流 + 约束 + 业务规则（agent 操作手册）
├── raw/           ← 原始素材（只读 · 不进图谱/检索）
│   ├── chatlogs/  ← 历史聊天证据（`<会话>/<YYYY-MM>.md`，整理页可点回原话）
│   ├── media/     ← 项目素材（合同/方案/发票）
│   └── docs/ voice/ screenshots/ clips/ misc/
├── wiki/          ← 整理层（agent 维护）
│   ├── index.md · log.md
│   ├── journal/   ← 「我的每一天」（时间轴）· people/ 人物（人物轴）
│   ├── monthly/ quarterly/  ← 月/季汇总（检索先命中汇总，再下钻）
│   └── projects/ tasks/ concepts/ finance/ ideas/ sources/ entities/ outputs/ private/
└── templates/     ← 模板（journal/person/task/project/idea/chatlog）
```

## 四、双视图（核心设计）

- **时间主轴 =「我的每一天」** `wiki/journal/YYYY-MM-DD.md`：当天各会话事件，按 **人/项目** 分组；每条＝
  `人（别名）：事件 → [[链接]]｜意义｜事实/计划`；语音摘录、图片内嵌。
- **人物轴 = 个人文档** `wiki/people/<姓名>.md`：`## 时间线（事件+意义）` 每行链 `[[日记日期]]`+`[[项目]]`；
  另含 `## 关系统览`、`## 记录目录`（链 `raw/chatlogs` 月，**可点回原话**）。
- 二者**互链**：同一事件 `[[YYYY-MM-DD]]` ↔ `[[姓名]]`。

## 五、9 个工作流（速查）

| 工作流 | 触发 | 关键动作 |
|---|---|---|
| **chat-ingest** | 定时 / 同步完成 | ①chatlog 就地内联媒体 → ②写「我的每一天」→ ③**事件三层路由**（项目 / 个人·商业待收纳 / `tasks/`）→ ④更新人物时间线 → ⑤素材归 `raw/media/<项目>` → ⑥index+log |
| **ai-chat-ingest** | 放入 `raw/chat/claude|chatgpt` | 识别主题 → 写 `wiki/sources/<日期>-<主题>.md` → 提炼可复用 prompt/方法进 concepts |
| **attachment-ingest** | 定时（每 4h）/ 用户要求 | **真读附件内容**（分层，见 `references/attachments-ocr.md`）：①去重 → ②本地抽文本（电子文档，免费且保结构）→ ③本地 OCR（扫描件/图片）→ ④复杂/批量/高价值→服务器或 API；再 LLM 提炼决定/数据/结论 → 归到 项目/人物/journal；原件复制进 `raw/media/<项目>/` |
| **owner-at-sync** | 主人在任意笔记写自定标记（如 `@owner`；每 10 分钟自动扫） | **主人的手写＝最高优先级**：读意图（增/改/删）→ 落实到结构层 → 处理完**删掉 @ 标记**（主人靠搜 @ 定位新增）→ 双维护。建页必做双维护 |
| **idea-capture** | 「记个想法」 | 建 `ideas/<slug>.md`，状态 `seed`（seed 不进全局索引） |
| **idea-review** | 每周（定时） | 审 seed/growing，建议合并/升级/归档；超 30 天未更新的单列 |
| **journal-ingest** | chat-ingest / 「记日记」 | 写 `journal/<当天>.md`；**允许 AI 汇总**（按人/项目分组、写清意义） |
| **query** | 提问 | 先查 index → `vaultq`/`qkb query` → 重要答案存 `outputs/` |
| **people-update** | 发现人物信息 | 建/更新 `people/<姓名>.md`（时间线+关系统览+记录目录） |
| **lint** | 每周（定时） | 查孤立页·断链·陈旧 seed·索引一致性·raw 只读·frontmatter 合规 |

## 六、分层治理（四条口径）

1. **检索分层**：journal（天）→ monthly（月）→ quarterly（季）；「某段时间发生了什么」先查汇总再下钻。
2. **四类区分**：**事实** / **计划（未落实）** / **意义（解读）**（措辞保守，不得写成事实）/ **待确认**。
3. **raw/ 边界**：正文只由管线写；展示层媒体内联可由 ingest 覆盖；**绝不删 raw/**。
4. **批量操作必须增量**：禁止 rmtree；只覆盖/只新增；保留原 id。
5. **信息时效**：近 3 个月聊天/语音 > 群里的 PDF/PPT/图片 > 更早聊天 > 老库迁入（仅作历史）。超 3 个月无更新不得当「当前状态」。
6. **人名带别名 + 跨会话推断**：写 `[[正名]]（别名）`；简称要推断是否同一人。**发言人未标注不臆测**。

## 七、谁在维护（多 agent）

每个 agent 负责一个**方向**，只写自己范围内的页；`journal/`+`people/` 由 owner 独占写。分工与写入边界见
`references/agent-topology.md`。

## 八、先读哪些文件

| 想了解 | 看哪 |
|---|---|
| 系统是什么样 | 根目录 `README.md` |
| agent 怎么整理（规范/约束/业务规则） | 根目录 `CLAUDE.md` |
| 首次部署（从 0） | `setup/SETUP.md`（8 步引导） |
| 安全护栏（不许改坏文件） | `references/safety.md` |
| 多 agent 分工 | `references/agent-topology.md` |
| **微信升级应对 / 合规边界** | `references/wechat-tools-landscape.md` |
| **★ 参考来源附录（出问题去哪找）** | `references/sources.md` |
| 微信采集链路 | `references/wechat-pipeline.md` |
| **★ 财务集成（官方账单→beancount 账本；聊天转账=注释层）** | `references/finance-integration.md` |


> 🧾 **任何 agent 收到用户的财务/账单文件时（微信/支付宝账单 zip·csv、银行对账单）**，按 `references/finance-integration.md` §三路由：
> ①归位到 `<vault>/raw/bills/<source>/<YYYY-MM>/`（wechat/alipay/bank；**原件只增不删**；zip 请用户解压或要密码，转换器只吃 CSV）
> ②立即处理：`python3 <skill>/assets/scripts/bills_to_beancount.py <csv> --source wechat|alipay --ledger <vault>/ledger`（或交给财务方向 agent / 等 4h 的 finance-ingest 周期）
> ③**不要自己读账单数字写进 wiki/finance/**——分类与汇总一律走账本管线（bean-check 把关）。
| **附件处理与 OCR（分层：本地轻量 ↔ 服务器/API）** | `references/attachments-ocr.md` |
| **性能分级 / 增量与批量分离** | `references/performance-tiering.md` |
| **★ 首次初始化（回灌数据+建图谱）** | `references/bootstrap.md` |
| **向量检索（两阶段：召回+重排）** | `references/vector-search.md` |
| **常驻服务清单** | `references/services.md` |
| **Obsidian 接入（数据/节点/图谱配色）** | `references/obsidian.md` |
| **成本参考（怎么算、怎么省）** | `references/cost.md` |
| **格式与分类规范（产出标准）** | `references/format-spec.md` |
| **范例（好的产出长什么样）** | `examples/` |
| **向量嵌入部署（检索质量关键）** | `references/embedding-setup.md` |
| Windows 采集端 | `references/windows-collector.md` |
| 本地模型换 API | `references/models-as-api.md` |
| 现在有什么 / 改过什么 | `wiki/index.md` · `wiki/log.md` |

> 📐 **写页面前先看** `references/format-spec.md`（格式与分类标准） 与 `examples/`（范例）。
> 常见错误：把 AI 的【解读】写成【事实】、把 3 个月前的事当【当前进展】、按时间流水抄聊天记录。

## 九、检索

> 🎯 **用户问「人/事/钱/时间」类问题时，挂子技能 `skills/shuzi-query`（信息检索/知识提取）**——
> 那里有完整的「怎么查、怎么答」手册（触发词 · 三层查法 · 出处硬规则）；本节只列命令。

```bash
vaultq "<问题>"          # ★ 两阶段：召回 + reranker（关系/概念题首选）
qkb query "<问题>"       # 单阶段混合（BM25 + 向量 + RRF）
qkb status               # 索引状态 / 待嵌入
python3 ~/.config/qkb/qkb-lock.py ingest   # 改完 wiki 后重建（顺序不可颠倒）
python3 ~/.config/qkb/qkb-lock.py embed
node ~/.config/qkb/prune-stale.mjs         # 清理已删页面的陈旧索引条目
```

**⭐ 索引是"近实时"的（关键，务必部署）**：qkb 是批处理——**没跑过 ingest+embed 的内容搜不到**。
所以库上要挂一个**常驻守护**（`assets/scripts/qkb-follow.py`），**每 5 分钟**自动
`qkb ingest`（增量，秒级）+ 有 pending 就 `qkb embed`：

- **写完页不必手动重建**：新日志/页约 **5 分钟内**即可被检索（否则要等 4h 的批量任务）。
- macOS 装 `engine/schedule/launchd/ai.shuzi.qkb-follow.plist`（**KeepAlive 常驻**）：
  `bash setup/schedule-macos.sh qkb-follow`（自动替换 `__HOME__`/`__LOGDIR__` 并加载）；
  Linux 用 `*/5 * * * * python3 ~/.config/qkb/qkb-follow.py --once`。
  ⚠️ **别用 `StartInterval`**（实测 macOS 对"跑完即退"的 job 不按时触发）。
- 只有**全量重建 / 换模型**才手动：`qkb-bigjob embed --full`。详见 `references/embedding-setup.md` §六。

## 十、脚本资产在哪（本包 `assets/`）

| 目录 | 内容 |
|---|---|
| `assets/scripts/collector/` | **采集端**脚本（部署到采集机器 `~/.wxexport/` + `~/wechat-export-macos/`）：<br>`refresh.sh`（主刷新，9 步）· `scan_cc.py`（★只读密钥扫描）· `missing_dbs.py`（缺密钥检测）· `export_focus.py` · `export_focus_voice.py` · `decode_focus_images.py` · `extract_money.py` · `export_searchable.py` · `focus_match.py` · `relay.command`（Terminal 中继）· `full_refresh.sh`（每周全量） |
| `assets/scripts/` | **大脑侧**脚本：`rebuild_index.sh` · `rebuild_chatlogs.py` · `run_transcribe.sh` · `transcribe_voice.py` · `finance_ingest.sh`（run.sh 包装器） · `bills_to_beancount.py`（官方账单 CSV→beancount 分录，交易单号去重） · `dev_feed.py`（git 提交活动→dev-feed 数据源，`SHUZI_REPOS` 配置仓库）· `run_rollup.sh`（run.sh 包装器）· `rollup.msg` · `sync_watch.py` · `conflict-sentinel.py`（同步冲突收口）· `qkb-lock.py` · `qkb-follow.py` · `qkb-bigjob` · `prune-stale.mjs` · `vaultq.py` · `vault-search-mcp.mjs` · `embed-proxy.py` · `compute-health.py` |
| `assets/scripts/`（**附件**） | `media_pipeline.sh`（抽文本→去重→本地OCR）· `media_extract.py`（PDF/Office→文本）· `media_dedupe.py`（内容 hash 去重）· `ocr_vision.py`（macOS Vision OCR，扫描件/图片）· `media_transcribe.py` / `media_transcribe_mlx.py`（音频→whisper 转写）· `media_flag_nonspeech.py`（静音段标记）· `media_text_to_vault.py`（产物镜像进 vault）· `mineru_bridge.sh`（复杂 PDF 解析桥） |
| `assets/templates/` | LaunchAgent 模板（`ai.wxexport.refresh.plist` / `.full` / `ai.syncthing.watch.plist`）+ `focus.txt.template` + 6 个页模板 |
| `assets/*.template` | 知识库根目录的 `CLAUDE.md` / `README.md` / `qkb.config.toml` / `.obsidian/app.json` |

> 采集端脚本与大脑侧脚本**不要混放**：前者部署到「有微信的那台机器」，后者部署到「vault 所在的机器」。

## 十一、微信链路的完整细节

**踩过的坑、具体数值、排障速查** 全部在 `references/wechat-pipeline.md`（14KB runbook）——
包括 `Config.Cipher` 的**固定掩码常量**、SILK 的 `\x02` 前缀、`.dat` 图片密钥的磁盘派生公式、
FDA/中继/PATH 三大权限坑、分片年表等。**移植到新系统前务必通读。**

## 十二、引擎无关（★ 普通用户看这里）

**这套系统不绑死 OpenClaw。** 任务定义（prompt）与执行引擎是分开的：

```
engine/run.sh <任务名>              # 自动挑可用引擎
engine/engines/  openclaw | claude | codex | api | ollama | manual
engine/tasks/    chat-ingest · finance-ingest · rollup · lint · idea-review
engine/schedule/ launchd / cron 模板（系统原生，不依赖 OpenClaw cron）
```

**六个引擎适配器**，按你的情况自动选：

| 你有什么 | 用的引擎 |
|---|---|
| OpenClaw（多 agent） | `openclaw` |
| Claude Code | `claude` |
| OpenAI Codex CLI | `codex` |
| 只有一个 API key | `api` |
| 想零成本（本地模型） | `ollama` |
| **什么都没有** | **`manual` ← 打印 prompt，人工贴给网页版 AI** |

**关键事实：大部分工作不烧 token。**

| 环节 | 烧 token？ |
|---|---|
| 解密数据库 / 语音转写 / 图片解码 / 向量嵌入 / 重建索引 | ❌ 全是本地纯计算 |
| **只有「把原始信息提炼成 wiki 页」** | ✅ 需要 LLM，且**每天 1–2 次** |

### 单 agent 就够（普通人）

7 个 agent 的价值只是**写入边界**（谁写哪块）。单 agent 时用**目录约定**替代即可：
`projects/工作/` · `projects/家庭/` · `projects/其他/`。
详见 `references/single-agent.md`。

> 定时也不用 OpenClaw：`engine/schedule/` 里有 **launchd / cron 原生模板**，
> 照抄改路径就能跑。

## 十三、平台与算力可选（★ 别被 macOS 经验带偏）

### 13.1 微信采集**不是 macOS 专属**

Windows 反而更省事：**没有 SIP / TCC / task_for_pid 限制** →
**不需要 FDA、不需要 Terminal 中继、不需要重签微信**，用标准开源工具（PyWxDump / chatlog）
内存扫描即可。详见 `references/windows-collector.md`。

| 你用什么 | 采集怎么做 |
|---|---|
| **Windows**（推荐给普通用户） | 现成开源工具，零权限门槛 |
| macOS | 见 `references/wechat-pipeline.md`（有 FDA/中继/重签的完整解法） |
| 不接微信 | 把任何数据丢进 `raw/` 即可，系统照跑 |

### 13.2 本地模型**全部可换成 API**

| 环节 | 本地依赖（重） | 可换成 |
|---|---|---|
| 语音转写 | whisper（GB 级） | ✅ 任何 OpenAI 兼容 ASR 端点 |
| 向量嵌入 | qwen3-embedding:4b（~2.5GB）—— 小模型如 embeddinggemma-300M 中文效果差，不推荐 | ✅ qkb 原生支持 `provider="openai"` 兼容端点 |
| 整理 | agent | ✅ 已是可插拔（`engine/`） |

换成 API 后，采集端**只剩 Python + 几个小库**，不再需要任何大模型文件。
详见 `references/models-as-api.md`（含配置示例与成本量级）。

> **硬盘不是瓶颈，模型才是**——所以优先把「要下大模型」的环节搬到 API。

### 13.3 提醒**不绑 Discord** —— 由 agent 触发，渠道可插拔

```
engine/notify.sh "消息"               # 自动挑可用渠道
engine/notify.sh "消息" --to feishu    # 或显式指定
```

内置渠道：`feishu`（飞书）· `wecom`（企业微信）· `wechat-connector`（微信连接器/由 agent 发）·
`desktop`（系统通知）· `discord`（可选）· `log`（兜底，永不失败）。

配置：`export SHUZI_NOTIFY=feishu` + 对应 webhook 环境变量。
**普通用户用飞书/企业微信/系统通知即可，不假设 Discord。**
