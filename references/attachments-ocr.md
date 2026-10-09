# 附件处理与 OCR（分层策略）

> 附件（PDF / Office / 表格 / 图片 / 扫描件）**不能只当文件名**，要让 LLM 真读内容。
> 但「怎么读」要**分层**：本地能做的别上服务器，简单的别用贵的模型。

## 〇、四层（按成本从低到高）

```
①去重（本地·0成本）
   └─ 内容 sha256：同一文件被反复转发 → 只留一份
②本地轻量抽文本（本地·0成本·保结构）
   └─ 电子文档：PDF/docx/doc/pptx/xls/xlsx/csv/txt → 纯文本
③本地 OCR（本地·0成本·离线）
   └─ 扫描件/图片：系统自带 OCR（macOS Vision 等）
④规模化 / 高价值（服务器 或 线上 API · 有成本）
   └─ 批量回填、复杂版面、公司重要件 → 高性能服务器（MinerU/PaddleOCR-VL）或线上 OCR/VLM API
```

**决策**：先 ①②③，**只有 ③ 仍不行的**（复杂版面、手写、公式、多栏、表格、高价值件）才上 ④。

> 本机一键安装（②抽取 + ③OCR 全套）：`bash setup/local-models.sh`
> （macOS = Vision OCR + PyMuPDF；Linux/Windows = RapidOCR；MinerU 想本机跑加 `--mineru`，无 GPU 会提示权衡）。

---

## 一、① 去重（先做，省 17% 起步）

同一份文件常被多次转发（`方案(4).pdf` / `方案(15).pdf` / `方案(16).pdf` …）。
按**内容 sha256** 去重，只留一份代表。脚本：`assets/scripts/media_dedupe.py`
产出 `_dedupe.tsv`（每组重复）与 `_ocr_queue.tsv`（需 OCR 的）。

## 二、② 本地抽文本（电子文档首选 —— 免费且**保结构**）

| 格式 | 抽法 |
|---|---|
| PDF | `pypdf`（文本层） |
| docx | `python-docx` |
| doc | macOS `textutil`（跨平台可用 `antiword`/`libreoffice`） |
| pptx | `python-pptx` |
| xlsx / xls | `openpyxl` / `xlrd` |
| csv/txt/md/json… | 直读 |

脚本：`assets/scripts/media_extract.py`。产出 `media-text/<相对路径>.txt` + `_manifest.tsv`。

> **为什么不直接 OCR？** 电子文档有**文本层**，抽取**又准又免费又保结构**（标题/表格/段落顺序都在）；
> OCR 反而会引入错字、丢版面。**只有「抽出来是空的」（扫描件）才需要 OCR。**

## 三、③ 本地 OCR（扫描件 / 图片 —— 增量主力）

**目标**：零/小模型、离线、快，处理「抽不出文本」的。

| 系统 | 方案 | 说明 |
|---|---|---|
| **macOS** | **系统 Vision OCR**（`ocr_vision.py`） | 零模型、离线、中文强；扫描 PDF 先用 PyMuPDF 渲染成图再 OCR |
| Linux / Windows | **RapidOCR** / **Tesseract** / PaddleOCR(CPU) | 轻量本地方案 |
| 任意 | 小 VLM（如 3B 级视觉模型，经 Ollama/llama.cpp） | 需要一点版面/语义理解时 |

**何时用**：日常增量、零散扫描件、图片截图（结合聊天上下文更准）。

## 四、④ 服务器 / 线上 API（规模化 + 高价值）

**触发条件**（任一）：
- **批量回填**（成百上千份，本地太慢）；
- **复杂版面**：多栏、表格、公式、手写、票证；
- **高价值**：合同、报价、方案、发票、公司 PDF/PPT/Excel。

### 选型（2026 年 SOTA）

### ⚠️ 按格式分流（别把老格式喂给 MinerU）

| 格式 | 正确工具 | 说明 |
|---|---|---|
| `.pdf`（电子）/`.docx`/`.pptx`/`.xlsx` | ② 本地抽文本 即可 | MinerU 只在**扫描/复杂版面**时才需要 |
| **`.doc` / `.xls`（97-2003 老格式）** | **`textutil`(macOS) / `xlrd`** —— ② 层就解决了 | ❌ **MinerU 不吃老格式**，实测秒退（本批 13 份 .doc/.xls 全因此失败，而 ② 层早已覆盖） |
| `.caj` / `.ofd` / `.et` / `.pages` | 专用工具或转 PDF | 知网/公文/WPS 格式 |
| 图片 / 扫描件 | ③ 本地 OCR → ④ MinerU/PaddleOCR-VL | |

> **排队批跑的坑**：① 别把映射表/清单文件混进待处理队列（实测 `_map.tsv` 混入导致 MinerU 挂死）；
> ② **必须给每个文件加超时**（10 分钟），超时/失败移入 `failed/`，防止整批卡死。

| 方案 | 特点 | 适合 |
|---|---|---|
| **MinerU 2.5** | 62.7k stars；原生吃 PDF/DOCX/PPTX/XLSX；表格/公式/多栏最强 | **公司高价值件**、结构化文档 |
| **PaddleOCR-VL 1.5/1.6** | 精度最高（OmniDocBench 94.5+）、中文最好 | 扫描件大批量、中文票据 |
| **DeepSeek-OCR(.rs)** | 双端原生（Mac Metal + CUDA）、7GB 显存、部署最轻 | 想要一套双端通用 |
| **线上 API**（各家 OCR/VLM） | 零运维、按量计费 | 峰值批量、不自建 |

**部署形态**：自建 GPU 服务器（如 24G 显存单卡）跑 MinerU/PaddleOCR-VL 的推理服务，
客户端（本机）经内网/Tailscale 调用 → **算力集中、本机轻量**。

## 五、分流决策表

| 情况 | 用哪层 |
|---|---|
| 电子文档（有文本层） | ② 本地抽文本 |
| 零散扫描件 / 图片（增量） | ③ 本地 Vision OCR |
| 复杂版面 / 表格 / 公式 | ④ 服务器（MinerU / PaddleOCR-VL） |
| 公司合同/报价/方案/发票 | ④ 服务器 + **VLM 深读**（出要点、金额、承诺） |
| 批量历史回填 | ④ 服务器（一次跑完） |
| 纯音频（语音） | —— 不是 OCR，走**语音转写**（ASR）：`assets/scripts/media_transcribe.py`（whisper 批处理，产物同 `media-text/`） |
| 纯音频（音乐/演出） | 转写意义不大（会出乱码）→ 只记「这是哪场/哪次」的元信息，不做文字提炼 |

### ASR 引擎选择（大范围 vs 增量）

| 场景 | 推荐 | 说明 |
|---|---|---|
| **增量、微信语音（短片 ≤60s）** | whisper `base`（现状） | 海量短片 + 每批只处理新增 → 够快；**批处理（模型只加载一次）是关键** |
| **长音频 / 批量** | **mlx-whisper（Apple）** 或 **faster-whisper（CUDA）** | 比 openai-whisper **快 4–8×（CPU）/ 几十倍（GPU）**；4070/4090 上 large-v3 可 **20–40× 实时** |
| **国内下载模型** | 设 `HF_ENDPOINT=https://hf-mirror.com` | HF 直连很慢，镜像快 10× 以上 |

⚠️ **VAD 的局限**：`webrtcvad` 只能分「语音 vs 静音」，**分不出音乐**（实测纯音乐文件也被判 0.9 人声）。
要跳音乐得用专门的音乐/语音分类器，或转完后按「重复/乱码」启发式标记。故 VAD 只用于**跳过静音**。
| 压缩包 | 先解开，里面的文件再按上面分流 |

## 六、流水线与产物

```bash
# 本地流水线：抽文本 → 去重 → 本地 OCR
bash assets/scripts/media_pipeline.sh
# 产出（都在 vault 外，供 agent 读取）：
#   ~/wechat-export/media-text/<相对路径>.txt   ← 可检索的文本
#   ~/wechat-export/media-text/_manifest.tsv     ← 每份的 pages/字数/状态
#   ~/wechat-export/media-text/_dedupe.tsv       ← 重复组
#   ~/wechat-export/media-text/_ocr_queue.tsv    ← 待 OCR（④ 的输入）
```

### ★ 最后一层（必做）：镜像进检索范围

> ⚠️ **media-text 在 vault 之外 → 检索库默认扫不到 → 这些内容等于「白处理了」**。
> 这是关键信息被遗漏的头号原因。

```bash
python3 assets/scripts/media_text_to_vault.py   # 产物镜像成带 frontmatter 的 vault 页
```

- 目标：`<vault>/raw/attachments/<相对路径>.md`（`id` 用 uuid5(源路径) **稳定生成**，重跑不重嵌）
- 镜像后由**常驻守护**（每 5 分钟 ingest+embed）自动增量入库——**数据一更新就跑，不许攒批**
- **规则**：今后**新增任何一种产物类型**（新的抽取器/转写器/OCR…），必须同时接上
  「**镜像进 vault + 增量索引**」两步，否则等于没做。

**交给 LLM**：agent 读 `media-text/*.txt`（②③④的产物）→ 提炼决定/数据/结论 → 归到 项目/人物/journal；
原件复制进 `raw/media/<项目>/`。

## 七、成本直觉

- **①②③ 全是本地** → **0 token**（只是电费/时间）。
- **LLM 读**才是主要成本：只读**去重后**、**有价值**的；批量回填按「月」分批。
- **④ 服务器**是一次性投入 + 电费；单次批量可能几秒到几分钟。
- 经验值（2026）：去重省 ~17%；真需 OCR 的往往只是**少数扫描件**（本项目 1071 份里仅 **55 份**）。


### ④ 服务器批量：MinerU 桥接（已实测）

```bash
bash assets/scripts/mineru_bridge.sh     # 选高价值件 → scp 到 GPU 机 → MinerU → 拉回 Markdown
```

- **选件**：去重代表 + 关键词（合同/报价/方案/发票/明细/预算/结算/报告…）
- **文件名消毒**：Windows 不收 `< > : " / \ | ? *` → 桥接自动改名（并留 `_map.tsv` 映射）
- **产物**：`media-text-mineru/<名>.md`（表格保留为 `<table>`，`layout.pdf` 可视化版面）
- **实测**：`报价单.pdf` 2 页 → Markdown 表格完整（本地 pypdf 则被压平）
- ⚠️ Windows OpenSSH **无 rsync** → 用 `scp -r`；大批量按批推拉

### ASR 幻觉处理

whisper 在**音乐/噪音**上会吐重复幻觉（如「优优独播剧场」循环），且常接在真实对话之后。
`assets/scripts/media_flag_nonspeech.py`：**n-gram 频次法截断幻觉尾巴** + 剩余过短/多样性过低 → 标「疑似非语音 → 跳过提炼」。
> 提醒：被当文件发来的音频**大量是音乐/演出**，转写价值低——优先只处理「对话里被点名要听」的那些。
