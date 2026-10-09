# 安全与可靠性修复 · 升级说明

初始审阅基线为 `82fd8cba38824b5346794c7e45715e56b7311cf3`；PR 基于重新发布的 `v0.1.0` 主线 `349ca90c20c060cc543c7c99a090486ed3098003`，保留新版 README 结构并纠正与实现不符的说明。本批修复内置执行器、冲突处理、索引跟随、检索输出边界与定时注册。**这是可审阅的工程修复，不是整套系统的生产安全认证。**

## 已实现的变化

| 范围 | 本版本行为 |
|---|---|
| API 文件工具 | 取消任意 shell；只读允许的文本范围；按角色限制 wiki 写入；拒绝越界路径、符号链接、硬链接与 private；覆盖需要旧版本 SHA-256、校验过的备份和原子替换 |
| 冲突哨兵 | 默认只报告；`--archive` 复制并校验所有版本，保留全部来源；不再按 mtime 删除旧版 |
| 任务运行器 | 传播失败退出码，记录独立 JSON 回执与日志；同一任务防重入；超时停止进程组；引擎退出与业务验收明确分开 |
| 索引跟随 | 按内容哈希而非错误的 mtime 标记检测变化；保存运行前快照；只有 ingest/embed/status 都成功才提交检查点；失败可重试，处理中到达的内容留给下一轮 |
| 检索与 MCP | 共用 vaultq，私密、越界、失效与符号链接路径在重排和输出前过滤；不再记录查询原文与命中路径；错误与无匹配分开 |
| 配置 | API 的 `llm.*` 调用映射到真实 `api.llm.*`；不再 eval 环境变量名或通过 argv 传密钥；核心运行链读取配置中的 vault，QKB 可通过 PATH 或 QKB_BIN 定位 |
| 定时任务 | 必须明确列出任务；支持无副作用预览；读取 schedule 时间；启用开关在注册和实际运行时都检查；Linux 只更新本包自己的具名 cron 区块，保留其他任务 |
| 技能指令 | 查询、维护、安装分流；资料与 @owner 标记不能提升权限；检索未找到不等于资料不存在；摘要不能压过原始权威证据 |

## 兼容性变化：升级前必读

**运行环境。** 核心受限写入与锁使用 POSIX 接口，需要 macOS/Linux 和 Python 3.9+。原生 Windows 未完成这一套安全实现与端到端验收；不要绕过统一入口去使用旧 PowerShell 安装器。Windows 采集文档不等于 Windows 全链路已受支持。

**引擎。** `auto` 只选显式配置且启用的 API；否则返回 manual，不再自动选择机器上碰巧存在的外部 CLI。外部框架仍可用 `--engine claude|codex|openclaw|hermes` 明确选择，但必须单独设置其沙箱和工具权限。Ollama 旧适配器只有文本生成，没有完整文件工具循环，本版本返回 `UNSUPPORTED_CAPABILITY`，不再假装已经完成整理。API 工具没有 shell、通知、QKB、账本转换能力；这些步骤必须由受控的确定性管线执行，不能让模型声称代办成功。

**角色。** 在启动 API 执行器时用 `SHUZI_ROLE` 明确设置 `owner`、`finance`、`engineer`、`business` 或 `query`。默认 owner 仅供可信单用户维护。角色不能由读到的文件或模型自行调整。该机制是目录写入约束，不是多租户身份认证。

**退出码与回执。** 普通失败非零；manual 为 3；Ollama 不支持为 4；忙碌为 75；超时为 124。冲突哨兵：无冲突为 0、有待审冲突为 2、归档或扫描错误为 1。`EXECUTED_UNVERIFIED` 表示引擎退出 0，回执的 `semantic_verified` 仍为 false；不要据此标记业务 PASS。

## 路径与配置

`SHUZI_CONFIG` 指定配置文件，默认 `~/.shuzi-rensheng/config.json`。`SHUZI_VAULT` 优先于其中的 `vault`；vault 必须使用绝对路径或 `~/...`。`SHUZI_STATE_DIR` 控制回执、备份与锁目录。`SHUZI_PYTHON` 可指定统一 Python。QKB 从 PATH 查找或用 `QKB_BIN` 指定。

`SHUZI_QKB_DIR` 控制本包 QKB 锁与跟随状态目录，默认 `~/.config/qkb`；**它不是已验证的 QKB 原生配置选项**。QKB 自身的 `config.toml` 仍需独立配置，确保其 vault 与本包一致。更换嵌入模型后仍需按 QKB 能力全量重建，不能把本包检测到配置变化理解为已经重算旧向量。

备份位于 `<state>/backups/<vault标识>/`，每份 Markdown 配有 JSON 清单，包含原路径与哈希。任务回执位于 `<state>/runs/`。备份不在同步 vault 内；其权限与留存应由用户管理，不能把它公开同步。

## 已有安装如何升级

本 PR 不自动修改正在运行的用户机器。`install.sh` 对 `~/.config/qkb/` 中已有脚本仍采取“不覆盖”策略，**仅 git pull 并不代表所有已部署副本已更新**。

升级应先暂停本包的旧任务及相关写入者，备份现有配置、定时条目、技能目录和知识库。随后审阅并统一更新下面这一组文件，不能只换单个脚本：

- 本包 `engine/`、`setup/`、`SKILL.md`、子技能及相关 references；从新的固定包路径运行。
- 检索目录中的 `shuzi_runtime.py`、`qkb-lock.py`、`qkb-follow.py`、`vaultq.py`、`vault-search-mcp.mjs`，从本包 `assets/scripts/` 复制。不要覆盖用户修改前不做差异检查。
- 若曾将冲突哨兵另放在 `~/.wxexport/`，更新时同时复制其依赖 `shuzi_runtime.py`；或直接把入口改为本包 `assets/scripts/conflict-sentinel.py`。

旧 `.follow-last-run` 不再使用，首次跟随会建立 `follow-state-v2.json`，不需删除知识库或现有索引。新的查询日志不再追加原文，旧 `usage.log` 不自动删除，应按用户授权处理存量隐私。

### 定时任务先预览，再注册

```bash
bash setup/schedule.sh qkb-follow lint --dry-run
```

检查路径、时区（采用机器本地时区）和执行模型。只有明确启用 `schedule.enabled=true` 后，再运行不带 `--dry-run` 的相同命令。修改具体 cron 表达式后重新生成相关任务；修改 vault 路径或 Python 环境也需重新生成。

`schedule.engine` 应明确配置受支持的后端，默认 api；不允许 auto、manual、ollama 用于无人值守任务。API 环境变量必须实际配置在服务的运行环境中，**交互式 shell 中 export 不保证 launchd/cron 可见**；调度器不会把密钥复制进 plist 或 cron。

新 Linux 安装器不删除历史无标记条目，以免误删其他任务。旧任务要先人工确认并停用，避免与新具名区块重复运行。macOS 旧 `ai.wxexport.refresh` 与新的 `ai.shuzi.collector-refresh` 名称不同，也需确认不存在双重调度。

`schedule.enabled=false` 只阻止使用新包装器的后续执行，不会中断已经启动的任务，也不能停掉旧的独立 launchd/cron 条目。

## 测试与未覆盖范围

回归测试全部使用临时目录、合成文件与模拟的 QKB/模型响应；不会访问真实微信、调用付费模型、改动真实索引、注册服务或发送通知。

```bash
python3 -m unittest discover -s tests -v
node --check assets/scripts/vault-search-mcp.mjs
```

覆盖路径越界、软/硬链接、角色权限、原始资料只读、备份失败、冲突来源保留、失败退出与回执、处理中新增内容、重复索引、重排前私密过滤、cron 保留及预览等场景。

**剩余限制不能被解释为已修复：**

1. `vaultq` 是检索后、重排前的输出过滤，不是 QKB 内部 ACL。已进入 QKB 的 private 数据不会由本 PR 自动移除；直接 QKB 工具、云端嵌入及其他调用者也不受这个过滤保护。敏感资料应拆分物理库/索引并限制服务权限；本包不能作为多租户隔离层。
2. 内置 API 只提供文件级备份与提交，尚无完整“变更集审批→跨文件事务→业务验收”的闭环。非合作的外部写入者和跨机器同步仍需单写者策略、快照及恢复演练。
3. QKB 真实安装版本、JSON 字段、status 输出、原生 vault 配置，MCP SDK 依赖布局和外部 Agent CLI 均需部署环境验证；回归模拟不等于这些集成通过。
4. 微信采集刷新、附件/语音的旧脚本、`scripts-extra.sh` 等尚有环境路径及失败传播问题，本批未完整重构。不要把新调度入口等同于这些下游任务都已通过验收；collector 的 GUI 中继启动也不等于采集成功。
5. 外部框架的宿主权限、自动日志留存/脱敏、全局 UUID 唯一性、来源可信度与业务内容正确性仍需独立控制和验收。

先用少量已授权的非敏感资料验证“原文→笔记→索引→带出处回答”，再考虑扩大无人值守范围。
