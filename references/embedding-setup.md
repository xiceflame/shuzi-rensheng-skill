# 向量嵌入部署（★ 检索质量的决定因素）

> **一句话**：嵌入模型是整套系统**检索质量的最大变量**。
> ⚠️ **本文只讲「嵌入」一半**。检索是**两阶段**（召回 + 重排）——完整链路见 `vector-search.md`。
> 小模型（如 embeddinggemma-300M）在中文长文本、专有名词、关系题上**明显不够用** ——
> **本方案默认用 `Qwen3-Embedding-4B`（2560 维）**，实测在中文语料上质量显著更好。

---

## 一、为什么是 Qwen3-Embedding-4B

| 模型 | 体积 | 中文效果 | 结论 |
|---|---|---|---|
| embeddinggemma-300M | 318MB | 一般，专名/关系题易错 | ❌ **太小，不推荐** |
| bge-m3 | 2.2GB | 好 | ⭕ 可用备选 |
| **Qwen3-Embedding-4B** | **~2.5GB (Q4_K_M)** | **好（中文尤其强）** | ✅ **本方案默认** |
| Qwen3-Embedding-8B | ~5GB | 更好 | ⭕ 算力够可上 |

**换模型会改变整个向量空间** → 必须 `qkb embed --full` 全量重嵌（见 §五）。

---

## 二、推荐架构：远程 GPU + 本机回落（高可用）

```
┌─────────────────────┐        Tailscale / 局域网        ┌──────────────────┐
│  大脑（vault 所在）  │ ───────────────────────────────▶ │  算力主机（GPU）  │
│  qkb                │      ollama :11434               │  Ollama          │
│   └ embed-proxy ────┤                                  │  qwen3-embedding │
│      127.0.0.1:11430│ ──(GPU 离线/超时)──────────────▶ │  :4b (2560 维)   │
│                     │      本机 Ollama :11434           └──────────────────┘
│                     │      同 tag 同模型 → 向量空间一致
└─────────────────────┘
```

**为什么要这一层**：向量嵌入是**持续调用的**（每次 `qkb embed` 都要跑成百上千次）。
有 GPU 的机器跑得快得多；但**GPU 机器可能关机** → 代理自动回落到本机。

### 配置要点
1. **GPU 主机**：`ollama pull qwen3-embedding:4b`；服务绑 `0.0.0.0`；
   防火墙**只放行 Tailscale 网段**（`100.64.0.0/10`）——**不要暴露公网**。
2. **本机**：也 `ollama pull qwen3-embedding:4b`（**同 tag 同模型**，保证向量空间一致）。
3. **代理**：`embed-proxy.py`（见 `assets/scripts/`）监听 `127.0.0.1:11430`，
   健康探测 GPU 主机 → 不可达则转发本机 `:11434`。
4. **qkb 配置**：`ollama_host = "http://127.0.0.1:11430"`（**只指向代理**，
   不要直连 GPU 主机 —— 那样就没回落了）。

> GPU 主机加入你的 Tailscale、命名与连通验证见 `references/network-setup.md`（§7 GPU 机接入）。

```toml
# ~/.config/qkb/config.toml
[embedding]
provider    = "ollama"
model       = "qwen3-embedding:4b"
dimension   = 2560                      # ★ 与模型一致
ollama_host = "http://127.0.0.1:11430"  # 指向代理，不是 GPU 主机
```

---

## 三、没有 GPU 怎么办

| 方案 | 做法 | 取舍 |
|---|---|---|
| **本机 CPU 跑** | 本机 Ollama + `qwen3-embedding:4b`（Q4_K_M ~2.5GB） | 慢（一次全量可能几十分钟），但**免费且质量一样** |
| **embedding API** | `provider = "openai"` + 兼容端点 | 快、无需算力；按量计费 |
| **借一台 GPU 机器** | 上节的远程架构 | 最优（本方案默认） |

### 用 API 替代（无 GPU 且不想等）
```toml
[embedding]
provider  = "openai"
model     = "text-embedding-v3"        # 按服务商填
dimension = 1024                       # ★ 必须与服务商实际维度一致
base_url  = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key_env = "DASHSCOPE_API_KEY"
```

---

## 四、质量调优（做完这些，检索才真的好）

1. **维度用满**：Qwen3-Embedding-4B 原生 2560 维。若硬盘/速度吃紧可降到 1024/512
   （它支持 MRL 截断），但**质量会降** —— 优先用满。
2. **chunk 大小**：qkb 默认按结构切。日记/人物页这类**语义完整的短页**效果最好；
   长聊天记录（月度）会被切成多块，**属正常**（正好适合「先召回后精读」）。
3. **加 reranker**（若你的检索工具支持）：Qwen3-Reranker 系列能把**关系题/概念题**
   的准确率再提一档。
4. **分层检索**（本系统已内置）：先命中 `monthly/quarterly` 汇总，再下钻 ——
   比「直接在几百页日记里捞」准得多。见 `CLAUDE.md` §9.1。
5. **换模型后必须全量重嵌**（下一步）。

---

## 五、切换/升级模型的正确步骤

```bash
# 0) 确认新旧模型都在（或先 pull 新的）
ollama list | grep qwen3-embedding

# 1) 改配置（provider / model / dimension）
vim ~/.config/qkb/config.toml

# 2) ★ 全量重嵌（换模型/换维必做；qkb 会按新维重建 chunks_vec）
python3 ~/.config/qkb/qkb-lock.py embed --full

# 3) 校验
qkb status          # 看 "Built with:" 是否为新模型、pending 是否为 0
qkb query "测试问题" # 实测召回质量
```

⚠️ **别忘 `--full`**：只跑 `embed` 只会补缺失块，**旧向量仍是旧模型产的**，
新旧混用会导致检索结果错乱。

---

## 六、索引时效：近实时跟进（★ 必做，否则"刚写的搜不到"）

**问题**：qkb 是**批处理**——只有跑过 `ingest` + `embed` 的内容才可检索。
若只靠"每 4 小时重建一次"，**新写的日记/日志最长要等 4 小时**才搜得到（实测积压可达数百 chunk）。

**做法**：让一个**常驻守护每 5 分钟**兜一次增量（`assets/scripts/qkb-follow.py`）：

```bash
# 跑一轮就退出（cron 用）
python3 "$HOME/.config/qkb/qkb-follow.py" --once
```

- **macOS**：`bash setup/schedule-macos.sh qkb-follow`（**KeepAlive 常驻**，脚本内部每 5 分钟一轮；自动替换模板路径并加载）。
  ⚠️ **别用 `StartInterval`**——实测 macOS 对"跑完即退"的 job **不按时触发**（只跑 1 次就停），务必用 KeepAlive 循环。
- **Linux / 其他**：`crontab` 加一行 —— `*/5 * * * * python3 $HOME/.config/qkb/qkb-follow.py --once`
- **成本极低**：无变化时只做一次 `qkb ingest`（按内容哈希，秒级）；**有变化才** `embed`（几十条 ≈ 本机 2 分钟）。
- 积压 >200 条自动切 GPU 主机（脚本读 `embed-proxy` 的 `prefer-4090` 标记）。
- 手工重建（全量/换模型）见下一节；**日常写完页不必手动重建**。

---

## 七、排障

| 症状 | 原因 | 处置 |
|---|---|---|
| `qkb embed` 卡住/极慢 | 走的是本机 CPU（GPU 主机离线） | 查 `embed-proxy` 日志、GPU 主机是否开机 |
| `dimension mismatch` | 配置维度与模型实际维度不一致 | 改 `dimension` 后 `embed --full` |
| 检索结果明显变差 | 换过模型但没 `--full` | 跑 `embed --full` |
| `pending` 长期不为 0 | 嵌入服务不可达 | `curl <ollama_host>/api/tags` 验证 |
| 两台机器向量不一致 | 两端模型 tag 不同 | **统一 tag**（本方案两端都是 `qwen3-embedding:4b`） |
