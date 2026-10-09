#!/bin/bash
# 读取集中配置 ~/.shuzi-rensheng/config.json
# 用法: source engine/lib/config.sh
#       cfg_get llm.base_url        # 取一个值
#       cfg_env llm.api_key_env     # 取环境变量名
CFG_FILE="${SHUZI_CONFIG:-$HOME/.shuzi-rensheng/config.json}"

cfg_get() {
  python3 - "$CFG_FILE" "$1" <<'PY' 2>/dev/null
import json, os, sys
f, path = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(f))
except Exception:
    sys.exit(0)
cur = d
for k in path.split("."):
    if isinstance(cur, dict) and k in cur:
        cur = cur[k]
    else:
        sys.exit(0)
print("" if cur is None else (cur if isinstance(cur, (str, int, float)) else json.dumps(cur, ensure_ascii=False)))
PY
}

# 取 API key：从 api_key_env 指的环境变量里读（key 不落 JSON）
cfg_key() {
  local envname; envname="$(cfg_get "$1.api_key_env")"
  [ -n "$envname" ] && eval "echo \"\${$envname:-}\""
}

# 启用判定
cfg_on() { [ "$(cfg_get "$1.enabled")" = "True" ] || [ "$(cfg_get "$1.enabled")" = "true" ]; }
