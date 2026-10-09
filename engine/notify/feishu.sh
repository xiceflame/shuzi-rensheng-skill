#!/bin/bash
# 飞书自定义机器人（国内常用）
# 配置：export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
[ -n "${FEISHU_WEBHOOK:-}" ] || { echo "[skip] 未设 FEISHU_WEBHOOK"; exit 0; }
curl -s -X POST "$FEISHU_WEBHOOK" -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json,os;print(json.dumps({'msg_type':'text','content':{'text':os.environ['SHUZI_NOTIFY_MSG']}}))")" >/dev/null
echo "[feishu] 已发送"
