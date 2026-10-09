# 回填执行手册（已验证的提示词与命令）

> 本手册里的提示词是 **2026-09 实跑验证过** 的版本（15 个月、438 页日记由此生成）。
> 用「一个子代理 = 一个月」并行派批。执行引擎无关（OpenClaw/Claude Code/API 均可）。

## §0 摸底

```bash
cd ~/数字人生/raw/chatlogs
for m in 2025-03 2025-04 2025-05; do
  echo -n "$m: $(ls */$m.md 2>/dev/null | wc -l) 会话, \
活跃 $(grep -rhoE "^\[$m-[0-9]{2}" */$m.md 2>/dev/null | sort -u | wc -l) 天"
  echo
done
```

## §1 journal 子代理提示词（逐日日记页）

```text
为 Obsidian 知识库「数字人生」写「我的每一天」日记页（以主人「我」为主线）。
**只新建 wiki/journal/YYYY-MM-DD.md，不改动任何其它文件。**

## 任务
为 <YYYY-MM-01> ~ <YYYY-MM-末> 每天各写一个 wiki/journal/YYYY-MM-DD.md
（无实质内容的当天可跳过并说明）。

## 数据来源（只读）
raw/chatlogs/<会话>/<YYYY-MM>.md。消息行 [YYYY-MM-DD HH:MM:SS] 发言人: 内容；
底部可能有 ## 语音转写 段。逐日提取：
for f in */YYYY-MM.md; do c=$(dirname "$f"); L=$(grep "^\[YYYY-MM-DD" "$f");
  [ -n "$L" ] && { echo "### $c"; echo "$L"; sed -n '/## 语音转写/,$p' "$f" | grep "^\[YYYY-MM-DD"; }; done

## 页面格式（严格）
---
id: <uuidgen 小写>
context: 日记
created: YYYY-MM-DD
tags: [我的每一天]
---
# YYYY-MM-DD（周几）｜今日主线：<一句话>
## 今日事件与意义
### 🎾 网球 / 🎻 乐团 / 🏢 项目 / 🏠 个人
- **[[人名]]（别名）**：事件 → [[链接]]｜意义：…｜**事实/计划**
## 今日待办 / 碎片

## 硬规则
1. 四类区分：事实 / 计划（未落实）/ 意义（解读，保守措辞）/ 待确认
2. 人名带别名 + 跨会话推断（按库内别名表）
3. 同类活动分「实际打球」与「复盘/督练」等（按领域惯例）
4. 过滤噪音；不臆测发言人（? 写「（发言人未标注）」）
5. [[人名]]/[[项目]] 必须已存在；无页用纯文本，勿造断链
6. chatlog 引用用路径式 [[raw/chatlogs/<会话>/YYYY-MM|YYYY-MM]]
7. 简洁但覆盖当天所有重要会话
```

## §2 人物时间线子代理提示词

```text
更新 <N 个> 人物页的「时间线（事件+意义）」，补 <日期范围>。只改这些文件。
1. 读 wiki/journal/<范围>/*.md，按人名+别名 grep 事件
2. 按日期**增量插入**到时间线（已有内容不删不改）
3. 每条 = - YYYY-MM-DD 事件 → [[日记日期]] · [[项目]]（意义：…）；只收有长期意义的事
4. 拿不准标「待确认」；不臆测
5. ⚠️ 建页后**必做双维护**：人物索引登记（删「暂未建档」表述）+ log.md 一行；漏了下游会重复建档
```

## §3 月/季汇总子代理提示词

```text
生成 wiki/monthly/YYYY-MM.md（每月一个）与 wiki/quarterly/YYYY-QN.md。
参考既有汇总风格。内容：本月主线（1–3 条）/ 关键决定（金额·日期）/ 未结事项 /
人物动向 / 项目进展；每行带下钻链接。三类区分（事实/计划/意义解读）。
frontmatter 含 id（uuid）+ context + created。只新建指定文件。
```

## §4 收尾

```bash
# 附件镜像（如有新产物）
python3 ~/.wxexport/media_text_to_vault.py
# 索引：先 ingest，大批量嵌入走 4090（确认 MinerU 批没在抢 GPU）
/usr/bin/python3 ~/.config/qkb/qkb-lock.py ingest
/usr/bin/python3 ~/.config/qkb/qkb-bigjob embed        # 大批量
# 验收
python3 - <<'PY'
# id 唯一 + 断链扫描（见 shuzi-rensheng §六验收）
PY
```

## §5 实测数据（2026-09-11/12，本机 M4 + 4090）

| 批 | 页数 | 子代理 | 耗时 |
|---|---|---|---|
| 2026-03~05 | 92 | 3 | ~35 分钟 |
| 2025-09~2026-02 | 181 | 6 | ~35 分钟 |
| 2025-07/08 | 62 | 2（后台） | ~7 分钟 |

- 期刊产出后**抽查 2–3 天**给主人看，确认再继续
- 嵌入：35.8k chunks 走 4090 ≈ 45–60 分钟（**别用本机**，4s/chunk 要 40 小时）
