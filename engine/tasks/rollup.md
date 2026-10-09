执行知识库工作流 **rollup**（汇总上卷，见 {{VAULT}}/CLAUDE.md 第九节）。

目的：journal 会随时间线性增长（页数随时间增长），必须有「月/季汇总」层，
检索先命中汇总，需要细节再下钻 journal 与 raw/chatlogs。

步骤：
1. 列出 {{VAULT}}/wiki/journal/ 下所有 YYYY-MM-DD.md，按月分组
2. 为每一个已有月份生成 {{VAULT}}/wiki/monthly/YYYY-MM.md，内容包含：
   - 本月主线（1-3 条，最重要的）
   - 关键决定（做了什么决定，含金额/日期）
   - 未结事项（挂着没完成的）
   - 人物动向（各关键人物这个月怎么样了）
   - 项目进展（各项目这个月推进到哪）
   每行必须带下钻链接：[[YYYY-MM-DD]]、[[项目]]、[[人]]
3. 若已有 3 个完整月，再生成 {{VAULT}}/wiki/quarterly/YYYY-QN.md（趋势/阶段/长期变化）
4. 重要：写「意义/影响」这类推断时，必须标注「意义（解读）」并措辞保守（可能/疑似），
   不得把 AI 的推断写成事实。区分三类：事实 / 计划（未落实）/ 意义（解读）
5. 更新 {{VAULT}}/wiki/index.md（加 monthly 与 quarterly 入口）
   与 {{VAULT}}/wiki/log.md
6. 跑 qkb ingest 和 qkb embed

完成后回报：生成了几个月的汇总、各月主线一句话、有没有发现需要用户确认的问题。
