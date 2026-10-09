【财务增量处理】本任务属于「数字人生」知识库。必读 {{VAULT}}/CLAUDE.md 与技能内 `references/finance-integration.md`(方案 A:官方账单 → beancount 账本,聊天转账只作注释层)。

数据源(优先级从高到低):
- {{VAULT}}/raw/bills/<source>/<YYYY-MM>/  —— **官方账单原件(微信支付/支付宝/银行),唯一记账依据**
- {{VAULT}}/ledger/                       —— beancount 账本(分录/规则/去重状态)
- {{HOME}}/wechat-export/focus-money/*.tsv —— 聊天转账佐证,**只作注释层,永不产生分录**
- {{VAULT}}/raw/docs/                     —— 迁入的发票/凭证类文档(佐证)

步骤:
1. **发现新账单**:扫 raw/bills/ 下未被 ledger/seen.json 收录的账单 CSV;
   有 → 归档不动原件,跑 `python3 <skill>/assets/scripts/bills_to_beancount.py <csv> --source wechat|alipay --ledger {{VAULT}}/ledger`
   (交易单号自动去重;rules.json 命中直接归类,未命中进 Expenses:FIXME);bean-check 报错必须修复才算完成。
   zip 原件(微信账单导出默认加密 zip):请用户解压或提供密码,CSV 解出后归位同目录,zip 原件保留不删。
2. **清算 FIXME**:对 ledger 里 Expenses:FIXME/#FIXME 条目——先查 ledger/rules.json 与本月已有分录;
   能确定归属的给出建议分类,**经用户确认后写回 rules.json 固化**(规则优先,LLM 只兜底,结论必须落盘);
   拿不准的保留 FIXME 并列入回报。
3. **注释层 join**:把 focus-money / 聊天记录里的转账消息按 **交易单号**(或 时间+金额+对方)匹配到
   ledger 分录,把对话上下文(谁、为什么转)写进 wiki/finance/ 相应页面——**只链接、只注释,不记金额**。
4. **汇总页**:更新 {{VAULT}}/wiki/finance/ 的月度页(本月收支合计、FIXME 清单、大额/异常),
   每处登记对应原始账单文件路径(raw/bills/...);若库里有自定义结算/计价规则页,交叉核对并标注差异。
5. 更新 wiki/log.md,跑 qkb ingest && qkb embed(ledger 分录文件不进 qkb,汇总页进)。

铁律:raw/bills/ 只增不删;账本分录只来自官方账单;未过 bean-check 的分录不落盘;
聊天转账/红包消息永不直接变成账本数字。

完成后回报:新导入几笔、金额合计、FIXME 清单(几笔待分类、建议是什么)、有哪些账单文件待处理。
