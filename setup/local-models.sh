#!/bin/bash
# 本机模型一键安装：让「语音转写 / 文档抽取 / OCR」在自己的电脑上跑（零 GPU 服务器、零 API）
# 用法：
#   bash setup/local-models.sh             # 基础集（转写 + 抽取 + OCR）
#   bash setup/local-models.sh --dry-run   # 只看会装什么，不动手
#   bash setup/local-models.sh --ollama    # 追加：本地嵌入模型（qwen3-embedding:4b，需已装 Ollama）
#   bash setup/local-models.sh --mineru    # 追加：MinerU 本机跑 PDF（CPU 可跑但慢，有 GPU 更佳）
set -u
DRY=0; WANT_OLLAMA=0; WANT_MINERU=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --ollama)  WANT_OLLAMA=1 ;;
    --mineru)  WANT_MINERU=1 ;;
    *) echo "未知参数: $a"; exit 1 ;;
  esac
done
PY="${SHUZI_PY:-python3}"
OS="linux"; case "$(uname -s)" in Darwin) OS="macos" ;; MINGW*|MSYS*|CYGWIN*) OS="windows" ;; esac
GPU="none"; command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1 && GPU="nvidia"
[ "$OS" = "macos" ] && GPU="apple"

run() { echo "  + $*"; [ "$DRY" -eq 0 ] && "$@"; }
pip() { run "$PY" -m pip install --user --quiet "$@"; }

echo "── 本机模型安装（os=$OS gpu=$GPU dry=${DRY}）──"

echo "① 文档抽取（PDF/docx/pptx/xlsx → 文本，免费保结构）"
pip pypdf python-docx python-pptx openpyxl xlrd

echo "② 语音转写（whisper 系，全离线）"
if [ "$OS" = "macos" ]; then
  echo "   Apple Silicon：mlx-whisper（原生加速，M 系首选）+ faster-whisper 兜底"
  pip mlx-whisper faster-whisper
else
  echo "   faster-whisper（CPU 也快 4–8×；有 N 卡自动用 CUDA）"
  pip faster-whisper
fi
echo "   说明：长音频批量建议再配 silero-VAD 过滤静音/音乐（见 references/speech-to-text.md §三）"

echo "③ OCR（扫描件/图片）"
if [ "$OS" = "macos" ]; then
  echo "   macOS：系统 Vision OCR 零安装；只补 PyMuPDF（扫描 PDF 渲染成图）"
  pip pymupdf
else
  echo "   RapidOCR（ONNX CPU）+ PyMuPDF（扫描 PDF 渲染）"
  pip rapidocr-onnxruntime pymupdf
fi

if [ "$WANT_OLLAMA" = "1" ]; then
  echo "④ 本地嵌入（向量检索本地化：qwen3-embedding:4b，2560 维）"
  if command -v ollama >/dev/null 2>&1; then
    run ollama pull qwen3-embedding:4b
    echo "   → config.json local.embedding_model 已默认指向它；qkb 的 ollama_host 保持 127.0.0.1:11434"
  else
    echo "   [跳过] 未装 Ollama —— 先 https://ollama.com 安装，再重跑本项"
  fi
fi

if [ "$WANT_MINERU" = "1" ]; then
  echo "⑤ MinerU（高价值 PDF → Markdown 保表格版面）"
  if [ "$GPU" = "nvidia" ]; then
    pip "mineru[core]"
    echo "   → 检测到 N 卡：本机直跑即可"
  else
    echo "   ⚠️ 无 N 卡：CPU 可跑但慢（大批量建议走 API 或 GPU 机桥接 mineru_bridge.sh）"
    pip "mineru[core]"
  fi
fi

echo "── 完成 ──"
echo "  转写模型选型/参数见 references/speech-to-text.md；OCR 分层见 references/attachments-ocr.md"
echo "  config.json 的 local 段（transcribe_backend=local）无需改动即为全本地方案"
