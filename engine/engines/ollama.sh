#!/bin/bash
# 适配器：本地 Ollama（质量有限，适合「不心疼 token」的日常整理）
MODEL="${SHUZI_OLLAMA_MODEL:-qwen2.5:14b}"
exec curl -s http://127.0.0.1:11434/api/generate -d "$(python3 -c "
import json,os
print(json.dumps({'model':'$MODEL','prompt':os.environ['SHUZI_PROMPT'],'stream':False}))
")" | python3 -c "import json,sys; print(json.load(sys.stdin).get('response',''))"
