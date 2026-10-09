# 运维手册（Operations）

> 日常检查、常见故障、恢复、迁移 —— 集中在这一篇。
> 配套：`services.md`（常驻服务）· `safety.md`（安全护栏）· `bootstrap.md`（首次初始化）

---

## 一、日常健康检查（每周看一眼）

```bash
# 1) 数据还在更新吗（最近一次采集）
tail -5 ~/wechat-export/refresh.log        # 应有今天的「刷新结束」

# 2) 索引跟得上吗
qkb status                                  # pending 应为 0

# 3) 同步正常吗（多机时）
tail -3 ~/wechat-export/sync-watch.log      # 无连续报错

# 4) 定时任务最近跑成功了吗
# OpenClaw: openclaw cron list 看 last/状态
# 系统 cron: grep -i error ~/.shuzi-rensheng/logs/*.log
```

**发现异常的处理路径**：本手册 §三 逐条对号入座。

---

## 二、档案会一直涨：增长治理

| 数据 | 增速（参考） | 治理 |
|---|---|---|
| `raw/chatlogs/` | ~1 MB/月 | 纯文本，无需治理（10 年 < 200MB） |
| `wiki/journal/` | ~30 页/月 | 靠 **monthly/quarterly 汇总**（检索不受影响） |
| **qkb 向量库** | 随消息线性涨 | 见下 |
| Syncthing 版本文件 | 取决于配置 | 给 `file-versioning` 设保留天数（建议 30 天） |

**qkb 索引重建会随数据变慢**：
- 每 4h 的 `rebuild-index` 目前全量重写（<1 分钟 / 337MB 库）
- **若超过 10 分钟**：改用增量策略 —— 只重写「近 2 个月」的文件，
  更早的月份内容不变（聊天历史不变，天然适合增量）
- 向量嵌入只处理 pending，天然增量 ✅

---

## 三、故障与恢复（症状 → 处置）

### 3.1 采集层
| 症状 | 原因 | 处置 |
|---|---|---|
| 刷新日志停在「密钥 0 个」 | 微信没开/没登录/未重签 | 开微信登录；macOS 重签（见 wechat-pipeline §5.3） |
| 某段时间整段没消息 | 该分片缺密钥 | 按分片年表补扫（wechat-pipeline §2.4） |
| 定时任务突然全停 | Terminal 中继失效 | 重跑一次 relay.command；检查 LaunchAgent |

### 3.2 整理层（LLM API）
| 症状 | 原因 | 处置 |
|---|---|---|
| **agent 任务全失败** | **API 欠费 / 配额超限 / key 失效** | 充值/换 key → 手动跑一次 `run.sh chat-ingest` 补上；期间数据不丢（focus/ 里的原始数据还在，之后会补整理） |
| 单任务超时 | 输入过大 | 缩小范围（按周/按会话分片）；或临时调低输入量 |
| 产出的日记质量变差 | 模型/提示词变化 | 看 `log.md` 最近条目定位是哪次改动；回滚 prompt |

> ⭐ **核心安心点**：`raw/` 是**源头数据**。整理任务失败**不丢数据**——
> 原始聊天/语音/附件都在，任何时候可以重跑整理。

### 3.3 检索层
| 症状 | 原因 | 处置 |
|---|---|---|
| 搜不到新内容 | qkb-follow 停了 | `launchctl kickstart -k gui/$(id -u)/ai.shuzi.qkb-follow`（名字按实际） |
| 结果变差/报 UNIQUE | 并发写索引 | 必须 `qkb-lock.py`（见 vector-search §七） |
| **索引损坏** | 磁盘/进程被杀 | **删掉索引库重建**：`qkb embed --full`（vault 是真数据，索引随时可重建） |
| 搜到已删页面 | 陈旧条目 | `prune-stale.mjs` |

> ⭐ **第二安心点**：**vault 才是真数据，索引只是派生物**。
> 索引坏了随时全量重建（几百 MB 库约几分钟~几十分钟）。

### 3.4 同步层
| 症状 | 原因 | 处置 |
|---|---|---|
| 文件莫名消失 | 同步目录 rmtree 竞态 | 见 safety §9.4；从另一端找回 + 归档恢复 |
| `.sync-conflict-*` 文件堆积 | 双端同时改 | conflict-sentinel 自动收口（services §一） |
| 两端版本不一致 | 一端离线太久 | 回到网络后自动追平；确认 completion=100 |

---

## 四、机器迁移（换电脑 / 重装系统）

**原则：vault 是真数据，其他都可以重建。**

| 项 | 怎么搬 | 能否自动 |
|---|---|---|
| **vault（真数据）** | Syncthing 已同步到对端 → 直接用；或整目录拷贝 | ✅ |
| `~/.shuzi-rensheng/config.json` | 拷贝（含 API/通知/路径配置） | ✅ 手动拷 |
| `~/.wxexport/focus.txt` | 拷贝（关注名单） | ✅ |
| **qkb 索引（240MB）** | **不用搬** —— 新机 `qkb embed --full` 重建 | ✅ 自动 |
| LaunchAgents / cron | 按新机平台重装（`setup/schedule-*.sh`） | ✅ |
| 采集端脚本 | 新机重装（Windows 见 windows-collector） | ⚠️ 人工 |
| **微信解密** | 新机**必须重新拿密钥**（微信在新机登录后） | ⚠️ 人工 |

**迁移步骤**（新机上）：
```bash
# 1) 装包
git clone <本包> && cd shuzi-rensheng-skill && bash install.sh
# 2) 恢复配置
mkdir -p ~/.shuzi-rensheng && cp <旧机配置> ~/.shuzi-rensheng/config.json
cp <旧机 focus.txt> ~/.wxexport/focus.txt
# 3) vault 到位后重建索引
qkb embed --full        # 或 bash assets/scripts/qkb-bigjob embed --full（有大 GPU 时）
```

---

## 五、新增关注人（focus.txt 改动后）

**问题**：focus.txt 加了新人，**只有从现在起的数据**——他的历史消息不在库里。

**想要历史的完整流程**：
```
1. 改 focus.txt（加名字）
2. 触发一次「全量导出」（不是 4h 增量）：
   bash ~/.wxexport/full_refresh.sh          # macOS 采集端
3. 对新会话跑一次「迷你回填」：
   - 该会话的可检索导出（export_searchable）
   - 该会话的语音转写（如需要）
   - LLM 提炼该会话的历史 → 人物页/项目页
4. qkb ingest && embed
```
> 成本很小（单会话），但**必须做第 2 步**，否则新人只有「认识你之后」的数据。

---

## 六、微信版本升级检查清单（macOS）

微信升级会**覆盖重签**。升级后跑一遍：

- [ ] 微信能正常启动登录
- [ ] `codesign --force --deep --sign - /Applications/WeChat.app`（重签）
- [ ] 手动跑一次采集：`bash ~/.wxexport/refresh.sh`
- [ ] 检查 `refresh.log`：密钥数 > 0、26 库全解密
- [ ] 确认 `focus/` 有当天新消息

（Windows 无此问题。）

---

## 七、备份策略（简单但够用）

| 数据 | 方式 |
|---|---|
| **vault** | Syncthing 两机互为备份 + `file-versioning` 30 天；**足够** |
| 配置（config.json / focus.txt） | 并入 vault 或手动备份一份 |
| **qkb 索引** | **不备份**（可重建） |
| raw/ 原始数据 | 跟随采集端机器；重要原始件建议再放一份到 vault/raw（Syncthing 覆盖） |

> 大库（几百 MB 纯文本）用 git 备份**不划算**（历史版本爆炸）——
> Syncthing 版本控制已经是更好的方案。
