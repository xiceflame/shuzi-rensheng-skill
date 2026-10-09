#!/bin/bash
# 数字人生 · 首次初始化的「时长 + 成本」估算
#
# 用法:
#   bash setup/estimate.sh                          # 按实际数据量估（全量）
#   bash setup/estimate.sh --convs 8 --months 12    # 按用户阐述的范围估
#   bash setup/estimate.sh --convs 8 --months 12 --parallel 4   # 含并发
#
# 设计意图：
#   1) 启动大批量处理前，必须先让用户知道「要花多久、多少钱」
#   2) 用户可以用自然语言阐述关注范围（哪些会话/方向/截止到何时），
#      据此**缩小范围**，估算随之下降 —— 不要机械按全量算
set -uo pipefail
# ── 参数解析：第一个非 -- 开头的才当作数据目录 ──
W="$HOME/wechat-export"
CONVS=""; MONTHS=""; PARALLEL=1
while [ $# -gt 0 ]; do
  case "$1" in
    --convs) CONVS="$2"; shift 2 ;;
    --months) MONTHS="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    --*) shift ;;
    *) W="$1"; shift ;;
  esac
done

python3 - "$W" "$CONVS" "$MONTHS" "$PARALLEL" <<'PYEOF'
import os, sys

W = sys.argv[1]
CONVS = int(sys.argv[2]) if sys.argv[2] else None      # 用户阐述的关注会话数
MONTHS = int(sys.argv[3]) if sys.argv[3] else None     # 用户阐述的截止范围（近 N 个月）
PAR = max(1, int(sys.argv[4]))                          # 并发度

def count(d, pat=None):
    p = os.path.join(W, d)
    if not os.path.isdir(p):
        return 0
    n = 0
    for root, _ds, fs in os.walk(p):
        n += len([f for f in fs if not f.startswith(".") and (pat is None or f.endswith(pat))])
    return n

def lines(d, ext=".md"):
    p, n = os.path.join(W, d), 0
    if not os.path.isdir(p):
        return 0
    for root, _ds, fs in os.walk(p):
        for f in fs:
            if f.endswith(ext):
                try:
                    with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                        n += sum(1 for _ in fh)
                except OSError:
                    pass
    return n

# ── 实际数据量 ──
n_text   = count("text")
n_focus  = count("focus")
n_voice  = count("focus-voice", ".mp3")
n_media  = count("focus-media")
n_img    = count("focus-images")
msg_all  = lines("searchable")
voice_h  = n_voice * 10 / 3600.0

# ── 按用户阐述缩小范围 ──
scope_note = []
if CONVS:
    ratio_c = min(1.0, CONVS / max(1, n_focus))
    scope_note.append("关注会话 %d/%d（%.0f%%）" % (CONVS, n_focus, ratio_c * 100))
else:
    ratio_c = 1.0
if MONTHS:
    ratio_m = min(1.0, MONTHS / 36.0)      # 近 3 年是默认全量口径
    scope_note.append("近 %d 个月（约 %.0f%%）" % (MONTHS, ratio_m * 100))
else:
    ratio_m = 1.0

ratio = ratio_c * ratio_m
msg    = max(1, int(msg_all * ratio))
voice  = voice_h * ratio
media  = max(1, int(n_media * ratio))

# ── 速率（实测校准）──
R_VOICE_LOCAL = 4.5        # ×实时（M4 whisper base）
R_VOICE_GPU   = 60.0       # ×实时（faster-whisper + CUDA）
R_EXTRACT     = 120.0      # 份/分钟
R_EMB_LOCAL   = 36000.0    # chunks/小时（M4 实测 ~10/s）
R_EMB_API     = 360000.0   # chunks/小时（并发后）
R_LLM         = 100000.0   # 条消息/小时（单线程 API）

chunks = max(1, msg // 6)

t_extract = media / R_EXTRACT / 60
t_voice_l = voice / R_VOICE_LOCAL
t_voice_g = voice / R_VOICE_GPU
# ★ 并发：API 调用可异步并发，按并发度折算
t_emb_l = chunks / R_EMB_LOCAL
t_emb_a = chunks / R_EMB_API / PAR
t_llm   = msg / R_LLM / PAR

t_slow = t_voice_l + t_extract + t_emb_l + t_llm
t_fast = t_voice_g + t_extract + t_emb_a + t_llm

def hm(h):
    if h < 1: return "%.0f 分钟" % (h * 60)
    if h < 24: return "%.1f 小时" % h
    return "%.1f 天" % (h / 24)

# ── 成本 ──
tok_hit  = msg * 3.0 * 0.8
tok_miss = msg * 3.0 * 0.2
tok_out  = msg * 0.5
cost_idle = (tok_hit/1e6)*0.02 + (tok_miss/1e6)*1.0 + (tok_out/1e6)*4.0

print("════ 本次范围 ════")
if scope_note:
    print("  " + " ｜ ".join(scope_note))
    print("  （按用户阐述的**关注点**缩小，不是全量）")
else:
    print("  全量（未限定范围）")
print()
print("  会话 %d ｜ 消息 ~%d 条 ｜ 语音 ~%.1f 小时 ｜ 附件 ~%d 份" % (n_focus, msg, voice, media))
print()
print("════ 时长估算（并发度 %d）════" % PAR)
print("  ①附件抽文本（本地·免费）      %s" % hm(t_extract))
print("  ②语音转写   本地 %s ｜ GPU %s" % (hm(t_voice_l), hm(t_voice_g)))
print("  ③向量嵌入   本地 %s ｜ API %s" % (hm(t_emb_l), hm(t_emb_a)))
print("  ④LLM 提炼   必须 API           %s" % hm(t_llm))
print("  ────────────────────────────────")
print("  慢路线（全本地）%s   ｜   快路线（GPU+API+并发）%s" % (hm(t_slow), hm(t_fast)))
print()
print("════ 成本估算（一次性）════")
print("  LLM 提炼（主要开销）    空闲 ≈ ¥%.0f ｜ 高峰 ≈ ¥%.0f" % (cost_idle, cost_idle*2))
print("  语音转写（若走 ASR）    ≈ ¥%.0f" % (voice * 1.0))
print("  向量嵌入（若走 API）    ≈ ¥%.1f" % (chunks/1e6*0.7))
print()
print("  ⚠️ 量级估算，用于心里有数；实际以账单为准。空闲时段省一半（见 cost.md）")
print()
print("════ 建议 ════")
if t_fast > 2:
    print("  ⏱ 预计 %s（快路线）—— 启动后**可以去干别的**。" % hm(t_fast))
else:
    print("  ⏱ 数据量不大，%s 内可完成。" % hm(t_fast))
print("  💡 先说清关注点可大幅缩小范围与花费；阶段①（免费的）应先做完。")
PYEOF
