# 单 agent 模式（给普通人）

> 本系统**不要求**装 OpenClaw，也不要求 7 个 agent。
> 多 agent 只是「一个人管多条线时更清晰」的**可选优化**，不是架构必需。

## 一、最少需要什么

| 角色 | 能不能省 | 说明 |
|---|---|---|
| 采集脚本 | ❌ 必需 | 解密/导出/转码，**纯 Python，不烧 token** |
| 同步 | ⭕ 单机可省 | 只有一台机器就不需要 Syncthing |
| 检索索引（qkb） | ⭕ 可省 | 只用 Obsidian 搜索也能用；qkb 只是更好搜 |
| **整理用的 LLM** | ❌ 必需 | 但**任何**能读写文件的 AI 都行（见 `engine/`） |
| Obsidian | ⭕ 可换 | 任何 Markdown 编辑器；甚至直接用文件管理器 |
| 定时 | ⭕ 可换 | 系统自带 launchd / cron 就够 |

## 二、单 agent 怎么做「多线区分」

7 个 agent 的价值是**写入边界**（谁写哪块）。单 agent 时用**目录约定**替代：

```
wiki/
├── journal/      我的每一天（时间轴，自动生成）
├── people/       人物（人物轴）
├── projects/
│   ├── 工作/     ← 主工作线
│   ├── 家庭/     ← 家庭线
│   └── 其他/     ← 杂项
└── ...
```

单 agent 的任务 prompt 里加一句即可：
> 「按目录归类：工作相关进 `projects/工作/`，家人相关进 `projects/家庭/`，其余进 `projects/其他/`。」

**不需要** `agent-topology.md` 里那套写入边界——那是多 agent 才需要的。

## 三、token 成本真相

**大部分工作不烧 token：**

| 环节 | 烧 token？ |
|---|---|
| 解密数据库 | ❌ 纯计算 |
| 语音转写（whisper） | ❌ 本地模型 |
| 图片解码 | ❌ 纯计算 |
| 向量嵌入（qkb） | ❌ 本地模型 |
| 重建索引 | ❌ 纯脚本 |
| **只有「把原始信息提炼成 wiki 页」** | ✅ 需要 LLM |

而且整理**每天跑 1–2 次就够**（早上/晚上），不是持续跑。

## 四、按你的情况选引擎

```bash
bash engine/run.sh chat-ingest                 # 自动挑（有谁用谁）
bash engine/run.sh chat-ingest --engine claude  # 有 Claude Code
bash engine/run.sh chat-ingest --engine api     # 只有 API key
bash engine/run.sh chat-ingest --engine ollama  # 想零成本（本地模型）
bash engine/run.sh chat-ingest --engine manual  # 什么都没有 → 打印 prompt，人工贴给网页版
```

> **`manual` 是重要的兜底**：没有 agent 也能用这套系统——脚本自动采集+解密+转写+建索引，
> 只有「整理」这步让人工拿着现成 prompt 去问 AI，再把结果贴回 vault。
