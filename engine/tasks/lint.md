执行知识库工作流 lint（体检维护）。规范见 {{VAULT}}/CLAUDE.md（§四、§九）。
检查项：
1. 断链：[[xxx]] 指向不存在的页；chatlog 引用必须是路径式 [[raw/chatlogs/<会话>/<YYYY-MM>|YYYY-MM]] 且目标存在
2. 孤立页：没有任何页链接到它
3. 已退役路径：wiki/ 内不得再出现 chatlogs/ 目录或 [[chatlogs/...]] 链接（原始记录只在 raw/chatlogs）
4. 索引一致性：index.md / 人物索引 / monthly / quarterly 与实际页面对得上（缺登记 / 多登记）
5. frontmatter 合规：wiki 页都有 id + context + created（缺了 qkb 不索引）
6. raw/ 边界（§9.3）：raw/ 只读——允许 ingest 覆盖「展示层」（媒体内联）；禁止删除 raw/ 文件或手改正文，发现即报告
7. 「意义」标注（§9.2）：journal/people 每条应为 事实 / 计划（未落实）/ 意义（解读，措辞保守）/ 待确认 之一；
   把解读写成事实的标为违规
8. journal 唯一性：wiki/journal/ 下 YYYY-MM-DD.md 一天一页，无重复日期
9. 超 30 天未更新的 seed 想法
能自动修的自动修；不能的列成清单。最后更新 index.md 与 log.md，跑 qkb ingest && qkb embed。
回复正文就是体检报告（会由 notify.sh 按用户配置的渠道推送）
