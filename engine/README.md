# engine —— 任务运行器（引擎无关）

**目的**：让这套系统**不再绑死 OpenClaw**。普通人只有 Claude Code / 只有一个 API key，
甚至什么都没有，也能跑。

```
engine/
├── run.sh              ← 统一入口：bash run.sh <任务名>
├── engines/            ← 执行引擎适配器（自动选，可 --engine 指定）
│   ├── openclaw.sh     OpenClaw（多 agent，你当前方案）
│   ├── claude.sh       Claude Code 无头模式（普通人最可能有）
│   ├── codex.sh        OpenAI Codex CLI
│   ├── api.sh          裸 API（只填个 key 就行）
│   ├── ollama.sh       本地模型（零成本）
│   └── manual.sh       ★ 兜底：打印 prompt，人工贴给网页版 AI
├── tasks/              ← 任务定义（**纯 prompt，与引擎无关**）
│   ├── chat-ingest.md     写「我的每一天」+ 人物时间线 + 项目页
│   ├── finance-ingest.md  财务增量（官方账单→beancount 账本；聊天转账=注释层）
│   ├── rollup.md          月/季汇总
│   ├── lint.md            知识库体检
│   └── idea-review.md     想法复盘
└── schedule/           ← 系统原生定时模板（不依赖 OpenClaw cron）
```

> ⚠️ **维护者注意**：公开版 `tasks/` 只有以上 **5 个通用任务**。
> 曾存在的 `*-weekly.md`（business/coding/engineer/hr 周汇总）是**原作者私有 7-agent
> 拓扑的任务定义**（内含私人项目名与合作方信息），**有意从公开包中移除**，
> 不是误删——请勿"恢复"。多 agent 用户请参照 `references/agent-topology.md`
> 自行编写自己领域的周汇总任务。

## 用法

```bash
bash engine/run.sh chat-ingest                    # 自动选引擎
bash engine/run.sh chat-ingest --engine claude     # 指定用 Claude Code
bash engine/run.sh chat-ingest --engine manual     # 没有 agent → 打印 prompt
bash engine/run.sh --list                          # 看有哪些任务
bash engine/run.sh lint --dry-run                  # 只看 prompt，不执行
```

## 两类任务

| 类型 | 例子 | 需要 LLM 吗 |
|---|---|---|
| **脚本任务** | 解密导出、语音转写、重建索引 | ❌ 纯脚本，系统自带定时就能跑 |
| **整理任务** | chat-ingest / rollup / lint / finance | ✅ 需要，但**走上面的适配器** |

> **大部分计算是脚本任务**（解密/转码/嵌向量），不烧 token；只有「把原始信息提炼成 wiki 页」
> 才需要 LLM，且**每天只需跑 1–2 次**。
