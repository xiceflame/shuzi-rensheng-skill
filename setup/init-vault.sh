#!/bin/bash
# 数字人生 · 建知识库骨架（幂等：已存在则只补缺，不覆盖已有内容）
# 用法: bash setup/init-vault.sh [vault路径] [--lines 工作,家庭,个人]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(cd "$HERE/.." && pwd)"

VAULT="${1:-$HOME/数字人生}"
LINES=""
[ "${2:-}" = "--lines" ] && LINES="${3:-}"

echo "═══ 初始化知识库：$VAULT ═══"
for d in raw/chatlogs raw/media raw/docs raw/voice raw/screenshots raw/clips raw/misc \
         raw/chat/wechat raw/chat/claude raw/chat/chatgpt \
         wiki/projects wiki/people wiki/journal wiki/monthly wiki/quarterly wiki/tasks \
         wiki/concepts wiki/finance wiki/ideas wiki/sources wiki/entities wiki/outputs wiki/private \
         templates .obsidian; do
  mkdir -p "$VAULT/$d"
done
echo "  ✓ 目录"

# 根文件（不覆盖已存在的）
cp -n "$PKG/assets/CLAUDE.md.template" "$VAULT/CLAUDE.md" 2>/dev/null
cp -n "$PKG/assets/README.md.template" "$VAULT/README.md" 2>/dev/null
cp -n "$PKG/assets/qkb.config.toml.template" "$VAULT/qkb.config.toml" 2>/dev/null
echo "  ✓ CLAUDE.md / README.md / qkb 配置模板"

# 模板
for t in "$PKG/assets/templates/tpl-"*.md; do
  [ -f "$t" ] && cp -n "$t" "$VAULT/templates/" 2>/dev/null
done
echo "  ✓ 页模板"

# Obsidian 忽略 raw/（图谱不被原始素材淹没）
for f in app.json graph.json; do
  if [ -f "$PKG/assets/obsidian/$f" ]; then
    cp -n "$PKG/assets/obsidian/$f" "$VAULT/.obsidian/$f" 2>/dev/null && echo "  ✓ Obsidian $f"
  fi
done

# 索引页（不覆盖）
[ -f "$VAULT/wiki/index.md" ] || cat > "$VAULT/wiki/index.md" <<'EOF'
---
id: 00000000-0000-4000-8000-000000000001
context: 索引
created: 1970-01-01
tags: [索引]
---

# 项目索引

> **本文件是全库唯一的索引。** 每次操作先读它；新增/改动后回来登记。

## 分类

（按你的实际线索分。setup 时会问你主要管哪几条线。）
EOF
[ -f "$VAULT/wiki/log.md" ] || cat > "$VAULT/wiki/log.md" <<'EOF'
---
id: 00000000-0000-4000-8000-000000000002
context: 日志
created: 1970-01-01
tags: []
---

# 操作日志

> 每次改动记一行：`- YYYY-MM-DD HH:MM 动作 目标`（最新在上）
EOF
echo "  ✓ 索引页"

# 按用户说的「线」建分类目录
if [ -n "$LINES" ]; then
  IFS=',' read -ra arr <<< "$LINES"
  for l in "${arr[@]}"; do
    l="$(echo "$l" | xargs)"
    [ -n "$l" ] && mkdir -p "$VAULT/wiki/projects/$l" && echo "  ✓ 分类目录: projects/$l"
  done
fi

# 写 state
mkdir -p "$HOME/.shuzi-rensheng"
python3 - "$HOME/.shuzi-rensheng/state.json" "$VAULT" <<'PYEOF' 2>/dev/null || true
import json, os, sys
p, vault = sys.argv[1], sys.argv[2]
st = {}
if os.path.exists(p):
    try: st = json.load(open(p))
    except Exception: st = {}
st.setdefault("step1", {})
st["step1"].update({"done": True, "vault": vault})
json.dump(st, open(p, "w"), ensure_ascii=False, indent=2)
print("  ✓ state.json 已更新")
PYEOF

echo
echo "完成。结构："
find "$VAULT" -maxdepth 2 -type d -not -path '*/.obsidian*' | sed "s|$VAULT|.|" | sort | head -25
echo
echo "下一步：把 <vault>/qkb.config.toml 复制到 ~/.config/qkb/config.toml 并按需改，"
echo "        然后 bash engine/run.sh lint --dry-run 验证引擎可用。"
