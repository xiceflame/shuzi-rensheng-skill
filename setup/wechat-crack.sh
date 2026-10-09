#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 数字人生 · macOS 微信采集 一键安装+破解（标准路径）
#
# 适用：macOS 26 / Apple Silicon，**不要求装 Xcode**（CLT 的 lldb 不能用，
#       本脚本自动改用 brew llvm 并签上调试器 entitlement —— 标准路径）。
#
# 用法：
#   bash wechat-crack.sh            # 全流程：准备→扫描→解密→验证
#   bash wechat-crack.sh prepare    # 只装环境
#   bash wechat-crack.sh scan       # 只扫密钥
#   bash wechat-crack.sh decrypt    # 只解密
#   bash wechat-crack.sh verify     # 只验证
# ═══════════════════════════════════════════════════════════
set -uo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
COL="$PKG/assets/scripts/collector"
W="$HOME/wx-export"
LOG="$W/crack.log"; mkdir -p "$W"
STAGE="${1:-all}"
say() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── 微信账号目录自动探测（只认含 db_storage 的、按修改时间最新的）──
detect_account() {
  local base="$HOME/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
  ls -dt "$base"/*/db_storage 2>/dev/null | head -1 | xargs dirname 2>/dev/null
}

# ── lldb 解析：brew llvm 优先（CLT 的不可用）──
lldb_bin() {
  local b
  for b in "$(brew --prefix 2>/dev/null)/opt/lldb/bin/lldb" /usr/bin/lldb; do
    [ -x "$b" ] && { echo "$b"; return; }
  done
  echo lldb
}

stage_prepare() {
  say "① 依赖：brew llvm（CLT 的 lldb 缺调试器 entitlement，标准路径用 brew llvm）"
  if [ ! -x "$(brew --prefix 2>/dev/null)/opt/llvm/bin/lldb" ]; then
    brew install llvm 2>&1 | tail -2
  fi
  local L; L="$(brew --prefix)/opt/llvm/bin/lldb"
  [ -x "$L" ] || { say "  ✗ brew llvm 的 lldb 不存在（brew reinstall llvm）"; exit 1; }
  cat > /tmp/dbg.ent.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.cs.debugger</key><true/></dict></plist>
EOF
  codesign -s - --force --entitlements /tmp/dbg.ent.plist "$L" && say "  ✓ lldb 已签调试器 entitlement"
  # 判定性自检：attach 自己的进程
  sleep 120 & local spid=$!
  if "$L" -b -o "process attach --pid $spid" -o detach -o quit 2>&1 | grep -q "Not allowed"; then
    say "  ✗ 自检仍被拒——attach 通路异常，停止（把本输出发给排查）"; kill $spid 2>/dev/null; exit 1
  fi
  kill $spid 2>/dev/null; say "  ✓ 自检通过：attach 通路正常"

  say "② python 依赖"
  /usr/bin/python3 -m pip install --user --quiet zstandard pycryptodome pypdf 2>/dev/null
  /usr/bin/python3 -c "import zstandard, Crypto" 2>/dev/null && say "  ✓ 依赖OK"

  say "③ 微信重签（★ 保留原 entitlements + 追加 get-task-allow —— 2026-09-14 实测定案）"
  # 只重签一次：已带 get-task-allow 且无 Runtime 就跳过（反复重签会打断登录态）
  if codesign -d --entitlements :- /Applications/WeChat.app 2>/dev/null | grep -q get-task-allow \
     && ! codesign -dv /Applications/WeChat.app 2>&1 | grep -q "Runtime"; then
    say "  ✓ 已是正确签名（get-task-allow 在，Runtime 无）"
  elif [ -O /Applications/WeChat.app ]; then
    codesign -d --entitlements :- /Applications/WeChat.app 2>/dev/null \
      | /usr/bin/python3 -c "import sys; x=sys.stdin.read(); open('/tmp/wx-ent.plist','w').write(x.replace('</dict>','<key>com.apple.security.get-task-allow</key><true/></dict>'))"
    codesign --force --deep --sign - --entitlements /tmp/wx-ent.plist /Applications/WeChat.app \
      && say "  ✓ 已重签（原 entitlements + get-task-allow；免 sudo）"
  else
    say "  ⚠️ App 属 root：需人工 sudo 重签（同样带 --entitlements /tmp/wx-ent.plist）"; exit 1
  fi

  say "④ 重启微信（killall，quit 无效；并验证 PID 已变）"
  local old new; old=$(pgrep -x WeChat | head -1)
  killall WeChat 2>/dev/null; sleep 3; open -ga WeChat; sleep 10
  new=$(pgrep -x WeChat | head -1)
  [ -n "$new" ] && [ "$new" != "$old" ] && say "  ✓ 微信已重启 [$old -> $new]" \
    || { say "  ⚠️ PID 未变或未运行（old=$old new=${new}）——若在登录墙请手机确认登录后重跑"; }

  say "⑤ 账号目录"
  ACCT="$(detect_account)"
  [ -n "$ACCT" ] && say "  ✓ $(basename "$ACCT")" || { say "  ✗ 未找到账号（有无 db_storage 的目录）"; exit 1; }
  say "⑥ 克隆数据库快照"
  local snap="$W/xwechat_files/$(basename "$ACCT")"
  mkdir -p "$(dirname "$snap")"; rm -rf "$snap"
  ditto "$ACCT/db_storage" "$snap/db_storage" && say "  ✓ 快照 $(du -sh "$snap" | cut -f1)"  # cp -Rc 在容器路径会静默失败，用 ditto
}

stage_scan() {
  local ACCT L WPID DBS
  ACCT="$(detect_account)"; L="$(lldb_bin)"; WPID=$(pgrep -x WeChat | head -1)
  DBS=$(find "$ACCT/db_storage" -name "*.db" | tr '\n' ' ')
  say "⑦ 扫描密钥（${L}，PID=${WPID}）"
  "$L" -b -o "command script import $COL/scan_cc.py" \
       -o "wxcc $WPID $W/rawkeys.txt $DBS" -o quit 2>&1 \
    | grep -E "ATTACH_FAIL" && { say "  ✗ attach 被拒"; exit 1; }
  local n; n=$(wc -l < "$W/rawkeys.txt" 2>/dev/null | tr -d ' ')
  [ "${n:-0}" -gt 0 ] && say "  ✓ 密钥 $n 条 → $W/rawkeys.txt" \
    || { say "  ✗ 0 条密钥——微信是否在登录墙？（近1小时无库写入=登录墙）"; exit 1; }
}

stage_decrypt() {
  say "⑧ 匹配 + 解密"
  ( cd "$COL" && /usr/bin/python3 -m wxexport match 2>&1 | grep -E "matched" ) \
    || { say "  ✗ match 失败"; exit 1; }
  ( cd "$COL" && /usr/bin/python3 -m wxexport decrypt 2>&1 | grep -E "decrypted" ) \
    || { say "  ✗ decrypt 失败"; exit 1; }
}

stage_verify() {
  say "⑨ 验证解密产物"
  /usr/bin/python3 - "$W" <<'PYEOF'
import glob, os, sqlite3, sys
w = sys.argv[1]
dbs = glob.glob(os.path.join(w, "decrypted", "message", "message_[0-9]*.db"))
ok = 0
for db in sorted(dbs):
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' LIMIT 3")]
        n = 0
        for t in tables:
            try:
                n = con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
                break
            except Exception:
                continue
        con.close()
        print("  ✓ %s：表 %s，样本行数 %d" % (os.path.basename(db), tables[:1], n))
        ok += 1
    except Exception as e:
        print("  ✗ %s：%s" % (os.path.basename(db), e))
print("  可读库：%d / %d" % (ok, len(dbs)))
PYEOF
}

case "$STAGE" in
  prepare) stage_prepare ;;
  scan)    stage_scan ;;
  decrypt) stage_decrypt ;;
  verify)  stage_verify ;;
  all)     stage_prepare; stage_scan; stage_decrypt; stage_verify;
           say "═══ 全流程完成 ═══" ;;
  *) echo "用法: $0 [prepare|scan|decrypt|verify|all]"; exit 1 ;;
esac
