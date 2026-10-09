# 适配：只有 API key（没有任何 agent 框架）

> 你是一个直接调 API 的脚本。**你没有工具**——所以需要一个「最小代理层」替你操作文件。

## 用现成的最小 Agent
```bash
# 需要在 ~/.shuzi-rensheng/config.json 里启用 api.llm
bash engine/run.sh chat-ingest --engine api
```
它跑的是 `engine/api-agent.py`：给模型 **4 个工具**（读文件 / 写文件 / 列目录 / 跑命令），
让它在 vault 里完成整理任务。这是「只有 key 也能自动化」的路径。

## 注意事项
- **能力边界**：模型只能通过那 4 个工具操作，**不能像 Claude Code 那样灵活**
- **长任务容易跑偏** → 建议把任务拆小（一次一个会话/一天）
- **务必设 `max_turns`**（默认 40），防止死循环烧钱
- 如果连 API 都不想配 → 用 `--engine manual`（打印 prompt，人工贴给网页版 AI）

## 定时 / 通知
同其它框架：系统原生定时 + `engine/notify.sh`。
