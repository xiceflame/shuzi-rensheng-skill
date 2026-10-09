#!/bin/bash
# 企业微信群机器人
[ -n "${WECOM_WEBHOOK:-}" ] || { echo "[skip] 未设 WECOM_WEBHOOK"; exit 0; }
curl -s -X POST "$WECOM_WEBHOOK" -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json,os;print(json.dumps({'msgtype':'text','text':{'content':os.environ['SHUZI_NOTIFY_MSG']}}))")" >/dev/null
echo "[wecom] 已发送"
