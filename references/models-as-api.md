# 把本地模型换成外部 API

> **动机**：本地模型（whisper / embedding）对普通用户是**最重的依赖**——
> 要下几个 GB、要 Apple Silicon、要装 Python 环境。
> 这些**全部可以换成 API**，省掉硬盘与算力门槛。

## 一、语音转写：本地 whisper → ASR API

**现状**：`run_transcribe.sh` 调本地 `openai-whisper`（brew 装的那份）。

**换法**：改用任何 ASR API，把 `transcribe_voice.py` 里的转写函数替换即可。

| 服务 | 端点 | 备注 |
|---|---|---|
| OpenAI Whisper API | `POST /v1/audio/transcriptions` | `model=whisper-1`，兼容端点通用 |
| 智谱 / 通义 / 讯飞 | 各自 OpenAI 兼容端点 | 国内直连、便宜 |
| 本地 vLLM / LM Studio | OpenAI 兼容 | 想自建也行 |

**通用写法**（任何 OpenAI 兼容端点）：
```python
import requests, os
def transcribe(mp3_path):
    with open(mp3_path, "rb") as f:
        r = requests.post(
            os.environ["ASR_BASE_URL"] + "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer " + os.environ["ASR_API_KEY"]},
            files={"file": f},
            data={"model": os.environ.get("ASR_MODEL", "whisper-1"), "language": "zh"},
            timeout=120)
    return r.json().get("text", "").strip()
```

**取舍**：本地 whisper 免费但要装环境；API 便宜（音频按分钟计费）但需要 key。
**普通用户建议用 API**（省掉整个本地环境）。

## 二、向量嵌入：本地 llama → embedding API

**qkb 原生支持 4 种 provider**（`~/.config/qkb/config.toml` 的 `[embedding]`）：

| provider | 说明 |
|---|---|
| `llama`（默认） | 本地 GGUF，要下 ~318MB 模型 |
| `ollama` | 本地/共享 Ollama |
| **`openai`** | **任何 OpenAI 兼容 `/v1/embeddings` 端点** ← 换 API 走这里 |
| `fake` | 测试用 |

**换成 API**：
```toml
[embedding]
provider  = "openai"
model     = "embedding-3"                 # 按你的服务商填
dimension = 2048                          # ★ 必须与服务商实际维度一致
base_url  = "https://open.bigmodel.cn/api/paas/v4"   # 例：智谱
api_key_env = "ZHIPU_API_KEY"
```

常用服务商与维度：
| 服务商 | model | 维度 |
|---|---|---|
| 智谱 | `embedding-3` | 2048（可选 1024/512） |
| 通义 | `text-embedding-v3` | 1024 |
| OpenAI | `text-embedding-3-small` | 1536 |

> ⚠️ **换 provider 或 model 会改变向量**，必须 `qkb embed --full` 全量重嵌。
> ⚠️ `dimension` 必须与服务商**实际返回维度**一致，否则检索会出错。

## 三、还有哪些本地依赖可以搬走

| 环节 | 本地依赖 | 可换成 |
|---|---|---|
| 语音转写 | whisper（GB 级） | ✅ ASR API |
| 向量嵌入 | qwen3-embedding:4b（~2.5GB）—— 小模型如 embeddinggemma-300M 中文效果差，不推荐 | ✅ embedding API |
| 图片解码 | `pilk`（小） | ⭕ 无必要，很小 |
| 解密 | `pycryptodome`（小） | ⭕ 无必要 |
| 整理（提炼 wiki） | agent | ✅ 已经是可插拔（`engine/`） |

**结论**：把**语音转写**与**向量嵌入**换成 API 后，
采集端只剩「Python + 几个小库」，**不再需要任何大模型文件**。

## 四、成本量级（参考）

- 向量嵌入：1 万条消息 ≈ 几十万 token ≈ **几毛到几块钱**（一次全量）
- 语音转写：1 小时音频 ≈ **几毛到几块钱**
- 整理（LLM）：每天 1–2 次，每次几万 token

> 相比「本地跑」的隐性成本（硬盘 + 装环境 + 算力要求），**API 对普通用户更划算**。
