# 财务集成 · 调研结论与方案 A(官方账单 → beancount → vault)

> 本文是 2026-09 对开源个人知识库/第二大脑、数字孪生(lifelogging)、开源记账三大赛道
> 40+ 项目的调研沉淀。结论:**财务环节不自研提取,数据源用官方账单,账本用 beancount
> 纯文本进 vault,聊天转账降级为注释层。**

---

## 一、调研结论(三句话)

1. **PKM/第二大脑工具普遍不做财务**。Logseq/SiYuan/Trilium/AFFiNE/Memos/Khoj/Reor 均无
   交易/账本概念。唯一例外是 Obsidian 生态(30+ 财务插件),但模式统一:
   **"PKM 存账(beancount/hledger 纯文本),专门工具算账(Fava/CLI)"**——见
   [plaintextaccounting.org](https://plaintextaccounting.org/)。
2. **数字孪生工具主动回避财务**。[screenpipe](https://github.com/mediar-ai/screenpipe)(21.5k★)
   默认把卡号/银行账号当 PII **擦除**而非提取,官方 pipe store 无任何财务 pipe。
   原因:金额抽取错了很难发现、银行数据合规灰区、存在更干净的数据源。
3. **成熟路线惊人一致:官方账单导出 → 规则转换 → 复式记账纯文本**。
   中文圈事实标准是
   [double-entry-generator](https://github.com/deb-sig/double-entry-generator)
   (原生支持微信/支付宝/六大行/美团/京东账单 → beancount);
   [ezbookkeeping](https://github.com/mayswind/ezbookkeeping)(5.6k★,原生微信/支付宝导入
   + HTTP API + 官方 MCP)是服务化备选;[Beancount-Trans](https://github.com/dhr2333/Beancount-Trans)
   用本地 BERT 做分类。
   社区共识(beancount.io 官方 LLM 文档 + HN 高分帖):
   **确定性规则优先,LLM 只兜底长尾,LLM 结论必须落盘成规则或人工复核后进账本。**

## 二、为什么放弃"聊天记录提取交易"作为账本来源

| 维度 | 官方账单(微信支付/支付宝 App 导出) | 聊天记录提取(focus-money) |
|---|---|---|
| 覆盖面 | 全渠道:扫码、App 内支付、自动扣费、零钱通、还款 | 仅社交转账/红包切片 |
| 退款/退回 | 状态字段,单号不重复 | 独立消息,与原交易难区分 |
| 去重主键 | 交易单号天然唯一 | 需"同会话+同金额+48h"启发式猜 |
| 字段质量 | 对方全称/商品/支付方式/秒级时间 | 金额常缺失(红包),对方是昵称 |
| 解析维护 | 格式是事实标准,生态解析器有人维护 | 只有自己维护 |

聊天记录的**不可替代价值**是语境:"这笔转账对应哪段对话"——官方账单给不了。
所以它不废弃,**降级为注释层**(见 §四.3)。

## 三、方案 A 架构

```
微信/支付宝 App 申请账单(邮件收加密 zip;按月/季)
        │  手动下载 / 收单脚本丢进
        ▼
<vault>/raw/bills/<source>/<YYYY-MM>/     ← 原始账单文件(只增不删,权威依据层)
        │  bills_to_beancount.py(本包自带;或 double-entry-generator)
        │  · 交易单号去重 · 规则映射 · 未匹配 → Expenses:FIXME
        ▼
<vault>/ledger/                            ← beancount 纯文本账本(git 可审计,LLM 可直读)
        │  bean-check 校验 / Fava 报表 / bean-query 查询
        ▼
wiki/finance/ 汇总页(月度收支、待确认清单)→ qkb 索引,进入语义检索
```

### 目录约定(vault 内,全部只增)

```
raw/bills/wechat/YYYY-MM/     微信支付账单 zip/csv 原件
raw/bills/alipay/YYYY-MM/     支付宝账单原件
raw/bills/bank/YYYY-MM/       银行对账单
ledger/main.beancount         include 总入口 + 账户开立
ledger/<source>/YYYY-MM.beancount   按源按月的分录(生成物,可再生)
ledger/rules.json             对方/商品 → 账户映射规则(人审后固化)
ledger/seen.json              已导入交易单号(去重状态)
```

## 四、组件与职责

### 4.1 转换器(本包 `assets/scripts/bills_to_beancount.py`)

- 解析微信支付/支付宝账单 CSV(容忍 utf-8/gbk 编码与前置元信息行);
- **交易单号去重**(对照 `seen.json` 与已有分录),重复跳过;
- `rules.json` 命中 → 直接归类;未命中 → `Expenses:FIXME`/`Income:FIXME` + 原始字段进 metadata;
- 输出分录,`bean-check` 通过才落盘。

更重的需求可用 [double-entry-generator](https://github.com/deb-sig/double-entry-generator)
(YAML 规则,支持的账单源更多),本脚本输出与其兼容(都是标准 beancount)。

### 4.2 校验与报表(外部依赖,自备)

```bash
pip install beancount fava        # bean-check 校验;fava 本地报表
bean-check <vault>/ledger/main.beancount
fava <vault>/ledger/main.beancount   # 浏览器报表/过滤/账户树
```

### 4.3 LLM/agent 的新职责(代替"从聊天找金额")

1. **FIXME 清算**:处理 `Expenses:FIXME` 条目——先查 rules.json,命中不了的建议分类,
   **经用户确认后写回 rules.json 固化**(规则优先,LLM 只兜底,结论落盘);
2. **注释层 join**:把 `focus-money`/聊天里的转账消息按 **交易单号** 或
   "时间+金额+对方"匹配到账本条目,把对话上下文写进 wiki 财务页
   (只链接、只注释,**不记金额**);
3. **汇总页**:从 ledger 生成 `wiki/finance/` 月度页(收支、待确认清单),
   登记对应原始账单文件路径(`raw/bills/...`),跑 qkb ingest。

### 4.4 铁律(更新版,写进 vault CLAUDE.md)

- **账本唯一权威 = raw/bills/ 的官方账单 → ledger/ 分录**;
- 聊天转账/红包消息 = **注释层**,永不产生账本分录;
- `raw/bills/` 只增不删;`ledger/<source>/` 是再生品但**保留历史不重写**;
- 未经 bean-check 通过的分录不落盘。

## 五、迁移步骤(从聊天提取路线)

1. 建 §三 目录骨架,`ledger/main.beancount` 开立账户(CNY);
2. 微信支付 App:我 → 服务 → 钱包 → 账单 → 常见问题 → 导出账单记录
   (邮件收 zip,解压得 CSV;支付宝同理);
3. 逐月把 CSV 丢进 `raw/bills/<source>/<YYYY-MM>/`,跑
   `python3 bills_to_beancount.py <csv> --source wechat --ledger <vault>/ledger`;
4. `bean-check` 通过 → 用 Fava 核对首月 → 修 rules.json 直到 FIXME 收敛;
5. 旧 focus-money 数据停止进账本,只留作注释层匹配源。

## 六、备选:方案 B(服务化)

不想维护 beancount 文件时,用 [ezbookkeeping](https://github.com/mayswind/ezbookkeeping):
原生微信/支付宝导入、Web 报表、**官方 MCP server**(agent 可直连问答)。
代价:多一个常驻服务,账本数据在它的库里而非 vault 文件(脱离 git/全文检索体系)。

## 参考项目

- [double-entry-generator](https://github.com/deb-sig/double-entry-generator) · 账单→beancount(微信/支付宝/银行,中文事实标准)
- [ezbookkeeping](https://github.com/mayswind/ezbookkeeping) · 自托管记账 + MCP
- [Beancount-Trans](https://github.com/dhr2333/Beancount-Trans) · 账单转换 + 本地 BERT 分类
- [beancount-import](https://github.com/jbms/beancount-import) · 决策树学习式分类(美式来源)
- [my-beancount-scripts](https://github.com/zsxsoft/my-beancount-scripts) · 个人微信/支付宝导入脚本集
- [Bills-save](https://github.com/edge-sky/Bills-save) · 邮箱自动收账单→入库(自动化收单参考)
- [Fava](https://github.com/beancount/fava) · beancount Web 报表
- [screenpipe](https://github.com/mediar-ai/screenpipe) · 数字孪生标杆(财务=PII 擦除的对照证据)
- [Firefly III](https://github.com/firefly-iii/firefly-iii) · 规则引擎最强的全功能记账(无中文账单原生支持)
- [plaintextaccounting.org](https://plaintextaccounting.org/) · 纯文本记账社区
