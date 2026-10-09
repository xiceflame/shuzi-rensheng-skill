# 数字人生 · 可分发安装包

> 一套「**采集 → AI agent 自动整理 → 语义检索 → Obsidian 浏览**」的个人知识库系统。
> **不绑任何 agent 框架**：有 OpenClaw 用 OpenClaw，有 Claude Code 用 Claude Code，
> 有 Hermes 用 Hermes（SKILL.md 开放标准，同源格式），只有 API key 也行，
> 什么都没有也能用（manual 兜底）。

---

## 它解决什么问题

把散落在**微信聊天、语音、图片、文件、其他工作端**里的信息，
自动变成一座**可检索、有图谱、可长期维护**的个人知识库：

```
微信 / Work Buddy / 手工资料
        │  采集脚本（解密·转码·抽取，本地免费）
        ▼
raw/ 原始证据层
        │  agent 整理（提炼成笔记，走 LLM API）
        ▼
wiki/ 整理层（journal 我的每一天 · people 人物 · projects 项目 · monthly 汇总）
        │  qkb 两阶段检索（召回 + 重排）
        ▼
vaultq "上周跟谁聊过什么" → 秒回
```

## 依赖清单（哪些自带、哪些自备）

| 依赖 | 本包含？ | 说明 |
|---|---|---|
| 采集/整理脚本、任务模板、文档 | ✅ 自带 | `assets/` · `engine/` · `setup/` |
| 检索侧脚本（qkb-lock / vaultq / qkb-follow…） | ✅ 自带 | `install.sh` 部署到 `~/.config/qkb/` |
| **`qkb` 主程序**（索引+召回） | ❌ **自备** | 见 `references/vector-search.md` §3.1；没装也能用（Obsidian 搜索兜底） |
| Obsidian | ❌ 自备 | 免费安装，纯原生零插件即可 |
| Python 3 | ❌ 自备 | 采集/转码脚本 |
| LLM / Embedding API key（可选） | ❌ 自备 | OpenAI 兼容协议即可；全本地也有适配器 |
| Syncthing（可选） | ❌ 自备 | 仅双机部署需要 |
| Tailscale（可选，多机） | ❌ 自备 | 采集机⇄大脑⇄GPU 跨网组网，免费档够用；单机不需要（见 `references/network-setup.md`） |
| beancount / Fava（可选，财务方案 A） | ❌ 自备 | `pip install beancount fava`；账单转换脚本本包自带 |
| whisper / OCR 模型（可选，全本地） | ❌ 自备 | `bash setup/local-models.sh` 一键装（转写+抽取+OCR，零 API 零 GPU 服务器） |

## 快速开始（两条路）

### 路线 A：让 AI 带你装（推荐）

```bash
git clone <本包> && cd shuzi-rensheng-skill
bash install.sh           # 探测环境 → 装技能 → 建骨架 → 生成配置
```
然后对 AI 说「**开始**」—— 它会按 `setup/SETUP.md` 的 8 步引导你完成其余配置。

### 路线 B：手动 5 分钟版

```bash
bash setup/detect.sh            # ① 看环境（OS / GPU / 有没有微信）
bash setup/detect-agent.sh      # ② 看你自己跑在什么框架上
bash setup/init-vault.sh        # ③ 建知识库骨架
cp assets/config.json ~/.shuzi-rensheng/config.json   # ④ 集中配置
                                # ⑤ 对 AI 说「开始」→ 按 SETUP.md 继续
```

## 文档地图

| 想了解 | 看哪 |
|---|---|
| **技能（大技能 + 子技能）** | `SKILL.md`（shuzi-rensheng 维护规范）· **`skills/shuzi-query/`（信息检索/知识提取，worker 答问用）** |
| **完整引导流程（8 步）** | `setup/SETUP.md` |
| 环境探测 / Agent 自我识别 | `setup/detect.sh` · `setup/detect-agent.sh` |
| 任务运行器（引擎无关） | `engine/run.sh`（6 个引擎适配器） |
| **财务集成（官方账单→beancount；调研+方案 A）** | `references/finance-integration.md` |
| 提醒渠道（飞书/企微/系统通知） | `engine/notify.sh` |
| 首次初始化（灌数据+建图谱） | `references/bootstrap.md` |
| 时长/成本估算 | `setup/estimate.sh` |
| **定时任务选装（安装时推荐项）** | `setup/schedule.sh`（交互目录；三平台同名任务） |
| **本机模型一键安装（whisper/OCR/嵌入）** | `setup/local-models.sh` |
| **安全护栏（不许改坏文件）** | `references/safety.md` |
| 格式与分类规范 | `references/format-spec.md` + `examples/` |
| 微信采集（macOS runbook） | `references/wechat-pipeline.md` |
| 微信采集（Windows） | `references/windows-collector.md` |
| 向量检索（两阶段） | `references/vector-search.md` |
| 向量嵌入部署 | `references/embedding-setup.md` |
| 显卡要求 | `references/gpu-requirements.md` |
| 性能分级 / 增量与批量分离 | `references/performance-tiering.md` |
| 语音转写分层 | `references/speech-to-text.md` |
| 附件 OCR 分层 | `references/attachments-ocr.md` |
| 常驻服务 | `references/services.md` |
| 多 agent 分工 | `references/agent-topology.md` |
| 单 agent 模式 | `references/single-agent.md` |
| 成本参考 | `references/cost.md` |
| Obsidian 接入/多端/配色 | `references/obsidian.md` |
| **多机组网（Tailscale）** | `references/network-setup.md` |
| 模板 | `assets/templates/` · `examples/` |

## 三种典型部署形态

| 形态 | 适合 | 要点 |
|---|---|---|
| **单机全走 API** | 大多数人 | Windows/macOS 均可；本地只跑纯脚本，AI 全走 API；无需 GPU |
| **单机 + GPU 本地推理** | 有 4080+/M 系列高配 | 嵌入/重排/语音本地（**≥8GB 显存门槛**）；大 LLM 仍走 API |
| **多机**（采集机 + 大脑 + GPU 机） | 进阶 | 先按 `references/network-setup.md` 用你自己的 Tailscale 组网，再把主机填进 `config.json` 的 `network` 段；Syncthing 同步；GPU 机跑重活 |

## 关键设计原则

1. **证据层/整理层分离**：`raw/`（原始，只读）≠ `wiki/`（agent 提炼）
2. **双视图**：`journal/`（时间轴）+ `people/`（人物轴），互链
3. **分层治理**：天→月→季汇总，检索先命中汇总
   四类标注：事实 / 计划 / 意义（解读）/ 待确认
4. **增量与批量分开**：日常本地细水长流；首次回填用 API/GPU
   **8GB 显存硬门槛**：低于就走 API
5. **引擎无关**：任务 prompt 与执行引擎解耦（6 个适配器 + manual 兜底）
6. **渠道无关**：提醒发飞书/企微/系统通知，不假设 Discord
7. **安全护栏**：不 rmtree 同步目录、不删 raw/、写入边界、并发锁

## 许可与用途

个人知识库方案（MIT，见 LICENSE）。**本包不含任何私有端点**：跨机目标（大脑/GPU 主机、
rerank 地址）全部走 `~/.shuzi-rensheng/config.json` 的 `network` 段或环境变量，
未配置时自动进入单机模式；多机组网指引见 `references/network-setup.md`。
