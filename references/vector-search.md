# 向量检索（完整链路）

> **一句话**：检索是**两阶段**的 —— 先用 `qkb` 粗召回，再用 **reranker** 精排。
> 两个模型、两个服务、一条高可用链。只看 `embedding-setup.md` 会漏掉一半。

---

## 一、全景图

```
                        查询 "上个月跟谁聊过什么"
                                │
                    ┌───────────▼───────────┐
                    │  ① 召回 qkb            │   BM25(关键词) + 向量(语义) + RRF 融合
                    │  取 N 个候选（默认 20） │   索引：~/.local/share/qkb/qkb.db
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  ② 精排 reranker       │   cross-encoder 逐条打分
                    │  返回 Top-K（默认 5）  │   bge-reranker-v2-m3 @ 4090
                    └───────────┬───────────┘
                                │
                            最终结果
```

**为什么两阶段**：单靠向量召回，Top5 常不准（答案散落、语义近但答案不对）。
cross-encoder 能**同时看查询和文档**，把真正相关的顶上来。

---

## 二、两个模型

| 角色 | 模型 | 维度/大小 | 跑在哪 | 换掉的代价 |
|---|---|---|---|---|
| **嵌入 Embedding** | `qwen3-embedding:4b` | 2560 维 / ~2.5GB | Ollama（GPU 优先，本机回落） | ⚠️ 换后必须 `qkb embed --full` |
| **重排 Reranker** | `bge-reranker-v2-m3` | ~2.3GB | `llama-server --reranking` | ⭕ 换后无需重建索引（不参与索引） |

> 💡 **关键区别**：嵌入模型决定**索引本身**（换了要全量重嵌）；
> reranker 只在**查询时**用（换了即时生效，不动索引）。
> 所以 **reranker 更容易升级**——想提质量可以先换它。

---

## 三、六个组件

| 组件 | 作用 | 缺了会怎样 |
|---|---|---|
| **`qkb`** | 索引 + 粗召回（CLI + `qkb mcp`） | ❌ 没有检索 |
| **`embed-proxy.py`** | 嵌入高可用代理（GPU 在线走 GPU，离线回落本机） | ⭕ 直连也行，但 GPU 一关机就卡 |
| **`compute-health.py`** | 算力健康检查（定期探活） | ⭕ 探活失效，问题靠人工发现 |
| **`vaultq.py`** | CLI **两阶段**入口（召回 + 重排） | ⭕ 退回单阶段（`qkb query`） |
| **`vault-search-mcp.mjs`** | MCP 版两阶段（agent 可调） | ⭕ agent 只能用 CLI |
| **`qkb-follow.py`** | 索引跟随（内容变了自动重建） | ⚠️ 新内容搜不到，要手动 `qkb ingest` |
| **`qkb-lock.py`** | 并发锁（防多 agent 同时写索引） | ⚠️ 报 `UNIQUE constraint failed` |
| **`prune-stale.mjs`** | 清理已删页面的陈旧索引条目 | ⚠️ 搜到不存在的页 |

### 3.1 组件从哪来

- **`qkb` 主程序是外部依赖，本包不带** —— 安装：`npm i -g @miguelarios/qkb`。
  **没装 qkb 系统照样能用**：vault 就是纯 Markdown，Obsidian 自带全文搜索兜底；
  只是没有语义检索（`vaultq` / `qkb query`）与自动索引，后补即可。
- 其余脚本（`vaultq.py`、`qkb-lock.py`、`qkb-follow.py`、`prune-stale.mjs`、
  `vault-search-mcp.mjs`、`embed-proxy.py`、`compute-health.py`、`qkb-bigjob`）
  **随本包附带**，位于 `assets/scripts/`；
  `bash install.sh` 会把它们复制到 `~/.config/qkb/`（不覆盖已有文件）。
- 配置模板：`assets/qkb.config.toml.template` → 复制为 `~/.config/qkb/config.toml` 后填嵌入服务与库路径。

---

## 四、常用命令

```bash
# ── 检索 ──
vaultq "<问题>"                  # ★ 两阶段（召回 + 重排），关系/概念题首选
vaultq "<问题>" -k 5             # 只要 Top5
qkb query "<问题>"               # 单阶段（BM25+向量+RRF），快
qkb search "<关键词>"            # 纯关键词

# ── 索引维护（改完 wiki 后）──
python3 ~/.config/qkb/qkb-lock.py ingest    # ★ 必须经锁包装器
python3 ~/.config/qkb/qkb-lock.py embed
python3 ~/.config/qkb/qkb-lock.py embed --full   # 换嵌入模型后必做
node ~/.config/qkb/prune-stale.mjs          # 清理陈旧条目

# ── 状态 ──
qkb status                       # 看 provider/model/dim/pending
```

---

## 五、部署这套（含 GPU 高可用）

### 5.1 嵌入端
见 `embedding-setup.md`（Qwen3-Embedding-4B + embed-proxy + 本机回落）。

### 5.2 Reranker 端

在 GPU 机器上（本方案是 **4090 Windows 主机**，经 Tailscale）：
```bash
# 用 llama.cpp 的 server，开启 reranking
llama-server -m bge-reranker-v2-m3.gguf --reranking --host 0.0.0.0 --port 8081
```
> 该主机还需**只放行 Tailscale 网段**（`100.64.0.0/10`），**不要暴露公网**。

在大脑侧指向它：
```bash
export RERANK_URL="http://<GPU主机Tailscale IP>:8081/rerank"
```
> GPU 主机加入你的 Tailscale、连通验证见 `references/network-setup.md` §7；
> 该地址写入 `config.json` 的 `network.gpu.rerank_url`（或环境变量 `RERANK_URL_REMOTE`）。

### 5.3 没有 GPU 怎么办
| 方案 | 做法 |
|---|---|
| **只用单阶段** | 不部署 reranker —— `qkb query` 本身就可用，只是 Top5 稍差 |
| **本机 CPU 跑 reranker** | 慢（每次查询几百 ms~几秒），小库可接受 |
| **用 Rerank API** | 任何提供 `/rerank` 的服务（Jina / Cohere / 智谱 等） |

> ⚠️ **`vaultq.py` 在 reranker 不可用时会自动回退为 qkb 原始排序**（不报错中断）——
> 所以**可以先只部署 qkb，之后再补 reranker**，系统不会挂。

---

## 六、MCP（可选，不强制）

本方案注册了两个 MCP（OpenClaw / Claude Code 都能用）：

| MCP 名 | 提供 |
|---|---|
| `vault-search` | 纯 qkb 检索 |
| **`vault-search-rerank`** | 两阶段（含重排），**agent 首选** |

```bash
# OpenClaw
openclaw mcp add vault-search-rerank --command "node /path/vault-search-mcp.mjs"

# Claude Code
claude mcp add vault-search-rerank -- node /path/vault-search-mcp.mjs
```

**不用 MCP 也行**——`vaultq` / `qkb query` 是 CLI，任何 agent 都能通过跑命令使用。

---

## 七、排障

| 症状 | 先查 |
|---|---|
| 搜不到新内容 | `qkb-follow` 是否在跑？或手动 `qkb-lock.py ingest` |
| 结果明显变差 | 换过嵌入模型但没 `--full`？或 reranker 挂了（回退到单阶段） |
| `UNIQUE constraint failed` | 是否绕过 `qkb-lock.py` 直接 `qkb ingest`（多 agent 并发） |
| 搜到已删除的页 | 跑 `prune-stale.mjs` |
| 查询很慢 | GPU 主机离线 → 嵌入/重排都回落本机 CPU |
| `pending` 长期不为 0 | 嵌入服务不可达 → `curl <ollama_host>/api/tags` |
| 两机向量不一致 | 两端嵌入模型 **tag 必须相同** |
