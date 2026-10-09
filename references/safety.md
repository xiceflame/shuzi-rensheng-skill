# 安全护栏（不许改坏文件）

> 本版本实现与升级要求见 `review-fixes.md`。API 文件工具已增加目录及角色限制、旧版本校验与备份，但外部 Agent 框架仍需独立配置系统权限。查询不授权安装或写入；资料及笔记标记不授权执行。以下规则不能被用于扩大用户授权。

> 这套库由**多个 agent 并发维护**，且通过 **Syncthing 准实时双向同步**到多台机器。
> 「一个 agent 随手改坏」→ 会经由同步扩散，且难回滚。所以下列项是**硬性禁止**，不是建议。

## 1. `raw/` 是只读证据区

- 正文**只由管线写入**（采集/重建脚本）；agent **不手改** `raw/` 里的正文。
- `raw/media/` 允许**新增复制**（把有价值的素材复制进来），**不删原件**。
- **绝不 `rm`/删除 `raw/` 下任何文件**。

理由：`raw/` 是「事后可追溯」的唯一来源；整理页里的每条都靠它点回原话。

## 2. 禁止 `rmtree` / 删目录后重建

**反例（曾导致丢文件）**：脚本先 `shutil.rmtree(vault_dir)` 再重建 → 期间 Syncthing 判定「大量文件被删」并向另一台机器同步删除，网络抖动/竞态下会造成**双向丢失**。

**正确做法**：
- 只**覆盖**（逐文件写）、只**新增**；
- 要移除失效文件：**逐个 `os.remove`**；
- **保留原 `id`**（避免检索库全量重嵌）；
- 大规模重组前：**先暂停同步**（Syncthing 里 pause 该 folder），完成后再恢复。

## 3. frontmatter 三件套

每个 wiki 页**必须**有：

```yaml
---
id: <uuid>          # 唯一；不要复制别页的 id（重复 id → 检索冲突）
context: <分类>      # 如 人物 / 项目 / 日记
created: YYYY-MM-DD
---
```

缺了 → 检索（qkb）**不索引**该页。

## 4. 写入边界（防多 agent 抢写）

- **`wiki/journal/` 与 `wiki/people/` 由 owner agent 独占写**。
- 其他 agent **只写自己领域的页**（见 `agent-topology.md`）；发现跨领域信息 → 写进自己领域页并标
  「**待 <owner> 汇总**」，**不要直接改 journal/people**。
- 同一页避免两端同时编辑（配合同步会产 `*.sync-conflict-*`）。

## 5. 写操作串行（检索库）

`qkb ingest / embed` **必须**经锁包装器调用：

```bash
python3 ~/.config/qkb/qkb-lock.py ingest
python3 ~/.config/qkb/qkb-lock.py embed
```

并发直调会抢插同一批 chunk → `UNIQUE constraint failed`。

## 6. 不删除，只归档

过期内容移到 `archive/`（或页面内「历史」小节），**不删**。

## 7. 隐私与索引唯一

- `wiki/private/` 不通过普通 API 整理工具、vaultq 或 MCP 提供；显式提问不自动提升权限。此约束是重排前的输出过滤，不是 QKB 内部 ACL；已有索引与直接 QKB 调用需另行隔离，详见 `review-fixes.md`。
- **只有一份索引** `wiki/index.md`；不要再造「项目索引」类文件。

## 8. 冲突副本（同步产物）

同步产生的 `*.sync-conflict-*` 表示**两端同时改了同一文件**。处理：
- 「**冲突哨兵**」（`assets/scripts/conflict-sentinel.py`）默认只报告并保留所有版本，不按修改时间自动选择正本。
- 显式使用 `--archive` 时，复制并校验各版本到 vault 之外的目录；归档成功或失败都不删除任何来源。
- 返回 2 表示仍需审阅冲突，返回 1 表示出错。多机合并要比较内容并保留备份，不能据此宣称冲突已经解决。

## 9. 每次改动都要可追溯

改完更新 `wiki/index.md`（登记）+ `wiki/log.md`（一行），并（按需）重建检索索引。

---

## 附：写这些脚本时的 shell 坑（本项目实测踩过）

### ⚠️ 中文标点紧跟 `$VAR` 会吞掉变量名（**本项目已踩 4 次**）

> 这是本仓库**最高频的 bug**，写脚本时**必须**注意。已有自动修复脚本：
> `~/.wxexport/fix_cjk_vars.py`（扫描全库 .sh 并自动加花括号）。
```bash
echo "跑在：$FRAMEWORK（置信度 $CONFIDENCE）"   # ✗ bash 把「FRAMEWORK（」当变量名 → unbound variable
echo "跑在：${FRAMEWORK} [置信度 ${CONFIDENCE}]" # ✓ 加花括号 + 用 ASCII 标点
```
**根因**：`（`、`，`、`。` 是多字节，bash 解析变量名时会把它们的字节并入。
**规则**：变量后面**不要直接跟中文标点**；要么加 `${}`，要么换 ASCII 标点。

### `$(case ... esac)` 嵌在 heredoc 里会炸
heredoc 里写 `"key": "$(case $X in a) echo A ;; esac)"` → 语法错。
**正解**：先在 heredoc 外把值算进变量，再 `"$A_VAR"`。

### heredoc 里的多行列表不会自动按行切
`while read d; do mkdir "$V/$d"; done <<< "$LIST"` 若处理不当会建出带换行的怪目录。
**正解**：直接用 `for d in a b c; do ...; done`（空格分隔），最省心。

### brace expansion 跨行会失效
`mkdir -p "$V"/{a,b,\n c,d}` → 建出带换行的目录名。
**正解**：拆成显式列表循环。
