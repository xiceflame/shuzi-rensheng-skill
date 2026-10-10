---
context: 资料管理
category: 待分类
project: ""
review_status: pending
agent_use: excluded
privacy: local
source_page: ""
source_message_ids: []
reviewed_source_revision: ""
---

# 资料管理卡

> 本批为界面与数据字段样板，后台属性回读尚未接入。修改 agent_use/privacy 不会自动限制既有 QKB 或其他 Agent 的读取。不要把此模板当作已生效的权限控制。

## 来源与用途

填写 source_page 的 Obsidian 内部链接，记录资料来源、时间范围和用途。原文是证据；AI 总结和人的判断应分别标注。

## 我的分类与更正

这里是用户正文。后续自动整理不应覆盖这些内容。

## 待确认的解释或关联

把缺少证据的姓名合并、关系推断、金额解释和完成状态放在这里，不自动升级为事实。

## 使用意图

- context：希望允许作为带出处的上下文。
- excluded：希望排除 Agent 使用。
- archived：可在 review_status 中标记归档。

以上是待实现的使用意图字段；应由受控检索入口读取并执行，并且不能扩大受信配置授予的权限。
