#!/bin/bash
# 适配器：裸 API（读集中配置 ~/.shuzi-rensheng/config.json 的 api.llm）
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../lib/config.sh"

if ! cfg_on llm; then
  echo "[ERR] config.json 里 api.llm.enabled 不是 true。"
  echo "      要么启用它，要么用别的引擎：--engine claude / openclaw / manual"
  exit 1
fi
BASE="$(cfg_get llm.base_url)"; KEY="$(cfg_key llm)"
MODEL="$(cfg_get llm.model)"; MAX="$(cfg_get llm.max_tokens)"
[ -z "$BASE" ] && { echo "[ERR] 缺 api.llm.base_url"; exit 1; }
[ -z "$KEY" ]  && { echo "[ERR] 环境变量 $(cfg_get llm.api_key_env) 为空"; exit 1; }

python3 "$HERE/../api-agent.py" \
  --base "$BASE" --key "$KEY" --model "${MODEL:-gpt-4o-mini}" \
  --max-tokens "${MAX:-4096}" --prompt "$SHUZI_PROMPT"
