汇总微信关注会话（数据在 ~/wechat-export/：focus 文字、focus-voice-text 语音转写、focus-images 图片、focus-media 文件、focus-video 视频、focus-money 财务佐证）。
步骤：
①归档到 {{VAULT}}/wiki/outputs/微信摘要/{{DATE}}-早.md（晚上用 -晚.md）
②覆盖更新 {{VAULT}}/wiki/outputs/微信摘要/最新日程.md，只留未过期条目
③增量更新知识库 {{VAULT}}/（先读它的 CLAUDE.md 与 §九；索引 wiki/index.md 唯一，改完登记 index.md 与 log.md）：
   a) 写「我的每一天」 wiki/journal/{{DATE}}.md —— 当天各会话事件，按 人/项目 分组；
      每条＝「- **[[人名]]（别名）**：事件 → [[链接]]｜意义：…｜**事实/计划**」
   b) 更新相关人物页的「时间线（事件 + 意义）」（每人一行，链到 [[当天]] 与 [[项目]]）
   c) 项目页 / 财务页照旧增量
④事件三层路由：能归项目→项目页；无对应项目→ [[个人]]/[[商业]] 的「待收纳碎片」；已识为一件事但搁置→ wiki/tasks/<slug>.md
⑤chatlog 已退役，别再往 wiki/chatlogs 写：原始记录由 rebuild-index 管线写入 raw/chatlogs/；
   整理页引用用路径式 [[raw/chatlogs/<会话>/<YYYY-MM>|YYYY-MM]]（可点回原话）
⑥财务线索不记金额：聊天里的转账/红包只作注释层（金额一律以 raw/bills/ 官方账单→ledger/ 为准，见 finance-integration.md）；发现财务相关对话时在 wiki/finance/ 记一条线索待 finance-ingest 处理
⑦跑 qkb ingest && qkb embed
口径：区分 事实 / 计划（未落实）/ 意义（解读，措辞保守）/ 待确认 四类；
人名带别名并跨会话推断——同一人在不同会话可能用不同称呼（昵称/全名/简称），推断要给依据，拿不准标「疑似同一人」；
语音发言人未标注不臆测（写「（发言人未标注）」）。月/季汇总由 rollup 任务负责，本任务不生成。
你的回复正文就是摘要本身（会由 notify.sh 按用户配置的渠道推送：飞书/企业微信/系统通知等）。只提取时间/地点/相关人和待办；不确定的标「待确认」；没有新增就写「本时段无新增安排」，绝不编造。

【第二数据源 · 商业账号】~/wechat-export-biz/（微信小店运营号，全量关注）。journal 条目标注「商业账号」；路由：小店运营/客服(openim)→商业往来，团队协作→公司/团队项目页，版权/合同/发票→财务待处理。同一人在两账号的对话分别记录，不合并语境。
