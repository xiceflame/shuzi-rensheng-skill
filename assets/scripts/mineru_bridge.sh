#!/bin/bash
# MinerU 桥接：选「高价值件」→ scp 到 4090 → 批量 MinerU → 结果拉回
set -u
HOME_W="$HOME/wechat-export"
IN="$HOME_W/mineru/in"; OUT="$HOME_W/media-text-mineru"
DONE="$HOME_W/mineru/.done.tsv"
PY="$HOME/.wxexport/.venv-media/bin/python"
mkdir -p "$IN" "$OUT"; touch "$DONE"

# GPU 主机：环境变量 GPU_SSH_HOST > config.json network.gpu.host
GPU_HOST="${GPU_SSH_HOST:-$(/usr/bin/python3 -c '
import json,os,sys
try: c=json.load(open(os.path.expanduser("~/.shuzi-rensheng/config.json")))
except Exception: sys.exit(0)
for k in "network.gpu.host".split("."):
    if not isinstance(c,dict) or k not in c: sys.exit(0)
    c=c[k]
print(c if isinstance(c,str) else "")' 2>/dev/null)}"
if [ -z "$GPU_HOST" ]; then
  echo "[ERR] 未配置 GPU 主机：config.json network.gpu.host（或环境变量 GPU_SSH_HOST）。组网见 references/network-setup.md" >&2
  exit 1
fi
GPU_DIR="${GPU_SSH_DIR:-E:/AI/mineru}"
# 1) 选件：去重代表 + 高价值类型（合同/报价/方案/发票/协议/明细/预算/PPT/Excel）
"$PY" - "$IN" "$DONE" <<'PY'
import sys,os,re,glob,hashlib,shutil,collections
in_dir,done_f=sys.argv[1],sys.argv[2]
done=set(l.strip() for l in open(done_f) if l.strip()) if os.path.exists(done_f) else set()
KEY=('合同','报价','协议','方案','发票','明细','预算','结算','标书','计划','报告')
EXT=('.pdf','.docx','.pptx','.xlsx','.doc','.xls','.ppt')
seen=collections.defaultdict(list)
for f in glob.glob(os.path.expanduser('~/wechat-export/focus-media/*/*')):
    if os.path.splitext(f)[1].lower() in EXT:
        h=hashlib.sha256(open(f,'rb').read()).hexdigest()
        seen[h].append(f)
n=0
for h,files in seen.items():
    rep=files[0]
    if h in done: continue
    base=os.path.basename(rep)
    if not any(k in base for k in KEY): continue
    # 消毒：替换 Windows 非法字符 + 限长
    safe=re.sub(r'[<>:"/\\|?*]', '_', base)[:80]
    if not safe.lower().endswith(os.path.splitext(base)[1].lower()):
        safe = os.path.splitext(safe)[0] + os.path.splitext(base)[1]
    dst=os.path.join(in_dir, safe)
    if not os.path.exists(dst):
        try: shutil.copy2(rep,dst)
        except OSError as e:
            print("跳过(不可读) %s: %s"%(base,e), file=sys.stderr); continue
    with open(os.path.join(in_dir,'_map.tsv'),'a',encoding='utf-8') as m:
        m.write("%s\t%s\n"%(safe,rep))
    print(h)
    n+=1
print("选定 %d 个高价值件"%n, file=sys.stderr)
PY
# 2) 推、跑、拉
scp -q "$IN"/* "$GPU_HOST":"$GPU_DIR"/in/ 2>/dev/null && echo "→ 已推送 $(ls "$IN" | wc -l | tr -d ' ') 个"
ssh -o BatchMode=yes "$GPU_HOST" "cmd /c ${GPU_DIR//\//\\}\\run_all.cmd" >/dev/null 2>&1
scp -qr "$GPU_HOST":"$GPU_DIR"/out/* "$OUT/" 2>/dev/null && echo "→ 已拉回结果到 $OUT"
