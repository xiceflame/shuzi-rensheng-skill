执行知识库工作流 **idea-review**（想法复盘）。规范见 {{VAULT}}/CLAUDE.md 第二节。

步骤：
1. 读 {{VAULT}}/wiki/index.md 与 {{VAULT}}/wiki/ideas/想法索引.md
2. 遍历 {{VAULT}}/wiki/ideas/ 下所有状态为 seed / growing 的想法页
3. 对每条给出建议：合并 / 升级为 growing / 归档；**超 30 天未更新的 seed 单独列出**
4. 更新想法页状态与 想法索引.md
5. 更新 index.md 与 log.md
6. 跑 qkb ingest && qkb embed
7. 回复正文就是复盘摘要（会由 notify.sh 按用户配置的渠道推送：飞书/企业微信/系统通知等）
