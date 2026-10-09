# 微信采集链路 · 完整 Runbook（含全部踩坑记录）

> 目标：在**采集端**（如 MacBook）把微信 4.x 数据解密导出，同步到**大脑**，供 agent 整理。
> 本文件是**可复现手册**——照做能在另一台机器上跑通。踩坑细节都写了，别跳。
>
> 适用范围：微信 macOS 4.1.x（实测 4.1.13）。Windows 思路类似但路径/工具不同。

---

> 💡 本文件的自研方案（Config.Cipher 只读扫描）与版本升级应对见
> `wechat-tools-landscape.md`；所有原理出处与「出问题去哪找」见附录 `sources.md`。

## 〇、先看这张「坑位总表」（省时间）

| 坑 | 症状 | 正解 |
|---|---|---|
| 用 lldb 断点抓密钥 | **一加断点微信就崩**；断点条件还让 lldb 自身崩（JIT 内存分配失败） | ❌ 废弃。用**只读内存扫描**（§2.1） |
| 内存找「盐附近的密钥」 | 扫 7.9GB 零命中 | ❌ 微信 4.x 不把盐与密钥放一起 |
| 磁盘找密钥 | 扫 7292 文件零命中 | ❌ 密钥只在进程内存 |
| `VoiceInfo.voice_data` 直接喂 ffmpeg | `Invalid data found` | SILK 头有 **`\x02` 前缀**，去掉；且 **ffmpeg 不支持 SILK**，用 `pilk` |
| 语音清单列数变化 | 转写静默「待转写 0 条」 | 解析要**按表头定位列**，别写死列数（§4.2） |
| ssh 读不了微信容器 | `Operation not permitted` | **sshd 的 FDA 与 Terminal 是分开的两套**（§5.1） |
| LaunchAgent 直接跑脚本 | 每次弹「访问其他 App 数据」；或 `Killed: 9` | 走 **Terminal 中继**；bash 副本必须重签名（§5.2） |
| Terminal 中继里依赖缺失 | `No module named 'zstandard'` | PATH 让 homebrew python3 抢先了 → **显式 `/usr/bin/python3`** |
| 在同步目录里 `rmtree` 重建 | **文件同步丢**（两机竞态） | 只覆盖/只新增；要删逐个删（§6.3） |
| 并发写检索库 | `UNIQUE constraint failed` | ingest/embed 必须**经锁包装器**串行 |

---

## 一、总体流程

```
采集端（每 4h）                                   大脑
─────────────────────────────────────────────────────────────
① 克隆 db_storage ──┐
② 密钥匹配/补齐     │  解密
③ 解密 26 个库      │
④ 关注会话文字      ├→ ~/wx-export/{focus,focus-voice,focus-images,
⑤ 语音 → mp3        │                    focus-media,focus-video,
⑥ 图片 → png/jpg    │                    focus-money,searchable}/
⑦ 转账/红包提取     │
⑧ 文件/视频收集     │
⑨ 近三年 → 月度 md ─┘
                                    ──rsync──▶  ~/wechat-export/
                                                    │
                                              整理管线（§7）
```

---

## 二、密钥：**整个链路最关键的一步**

### 2.1 正解 —— 只读 Config.Cipher 扫描

微信 4.1+ 内存里**没有明文密钥**，但 WCDB 保留一个
`com.Tencent.WCDB.Config.Cipher` 对象，其配置块被**固定 32 字节掩码 XOR 混淆**，
解混淆后就是 `x'<64hex key><32hex salt>'`。

**固定掩码**（版本稳定，直接抄）：

```
d2c7442458020000004889442450488b450048844c2448488944254048584c24
```

**做法**：
1. lldb attach 微信（**只读内存，不设任何断点**）
2. 遍历可读内存区域，对 **32 个掩码相位**，搜索「被掩码混淆后的 `x'`」两字节模式
3. 命中处就地解混淆、取 hex、用 **page-1 HMAC** 验真
4. 写入 `rawkeys.txt`，再用 `match.py` 归属到各库

**实测**：扫 3.7GB / 133 秒 / 一次拿到 5 个缺失密钥 / **微信零崩溃**。

现成脚本：本包 `assets/scripts/` 里对应采集端的 `scan_cc.py`（或参考
`sunhanaix/pc_wechat_exp` 的 `config_cipher_extract.py`，Windows 版逻辑同源）。

### 2.2 为什么不能用其它办法（都试过）

| 方法 | 结果 |
|---|---|
| lldb 断点 `CCCryptorCreate` | ❌ 命中频繁 → 微信卡死；加条件过滤 → **lldb 自身崩溃**（`Couldn't malloc: address space is full`） |
| lldb 断点 `sqlite3_key` | ❌ 符号存在但**从不触发**（WCDB 不走它） |
| 内存搜「盐 ±8KB 内的 32 字节」 | ❌ 扫 7.9GB 零命中 |
| 在容器/配置里找落盘密钥 | ❌ 扫 7292 文件零命中 |

### 2.3 解密参数（SQLCipher 4，实测 4.1.x）

| 参数 | 值 |
|---|---|
| 算法 | AES-256-CBC |
| 主密钥 | **原始 32 字节直接用**（主密钥不做 PBKDF2） |
| HMAC | HMAC-SHA512；`mac_key = PBKDF2-HMAC-SHA512(key, salt ^ 0x3a, 2)` |
| 页大小 | 4096 |
| reserve | 80（IV 16 + HMAC 64） |
| salt | 文件头前 16 字节 |

### 2.4 分片是「按年」切的（排障关键）

| 分片 | 覆盖 |
|---|---|
| `message_8` | 2018-09 ~ 2019-06 |
| `message_7` | 2019-06 ~ 2020-06 |
| `message_6` | 2020-06 ~ 2021-06 |
| `message_5` | 2021-06 ~ 2022-06 |
| `message_4` | 2022-06 ~ 2023-06 |
| `message_2` | 2023-06 ~ 2024-06 |
| `message_1` | 2024-06 ~ 2025-06 |
| `message_0` | 2025-06 ~ 2026-06 |
| `message_3` | 2026-06 ~ 现在 |

> 若「某段时间整段没消息」→ **多半是那片密钥缺失**，不是真没聊。
> 缺密钥时用 §2.1 的只读扫描补齐（脚本 `missing_dbs.py` 只挑 >8MB 的大库，避免空跑）。

---

## 三、数据在哪（微信 4.x macOS 目录）

```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/<账号>/
├── db_storage/                    ← 加密数据库（26 个）
│   ├── message/message_0..8.db    ← 聊天（按年分片）
│   ├── message/media_0..1.db      ← ★ 语音在这里（VoiceInfo 表）
│   ├── contact/contact.db         ← 联系人
│   ├── session/session.db         ← 会话列表
│   └── ...
├── msg/
│   ├── file/<YYYY-MM>/            ← 群里发的 PDF/Office
│   ├── video/<YYYY-MM>/           ← 视频
│   └── attach/<hash>/<YYYY-MM>/
│       └── Img/<md5>[_t|_h].dat   ← ★ 聊天图片（加密 .dat）
└── app_data/net/kvcomm/key_<uin>_*.statistic   ← uin（图片密钥要用）
```

---

## 四、语音（最容易踩坑的一环）

### 4.1 语音是**明文 SILK v3**，不必解密

- 位置：`db_storage/message/media_N.db` 的 **`VoiceInfo`** 表，字段 **`voice_data`**（BLOB）
- 字段：`chat_name_id`（= 该库 Name2Id 的 rowid，即会话）、`local_id`（对应消息表）、`create_time`、`data_index`
- ⚠️ **`voice_data` 是明文**，不是加密的

**解码链**：
```
voice_data
  ↓ 去掉微信多出的 \x02 前缀（标准 SILK 头是 "#!SILK_V3"，微信是 "\x02#!SILK_V3"）
  ↓ pilk.decode(silk, pcm, 24000)          ← pip install pilk
PCM (s16le 24kHz mono)
  ↓ 自己写 WAV 头（比调 ffmpeg 快，避免每文件一个子进程）
WAV
```

> ⚠️ **ffmpeg 不支持 SILK 解码**（`ffmpeg -codecs | grep silk` 为空），别浪费时间。
> 解出来的 `.hevc` 是动态照片，忽略。

### 4.2 语音清单的列数坑（实测踩过）

清单 `_manifest.tsv` 的列会变（5 列 / 6 列都出现过，取决于是否回填了「发言人」）。
**转写脚本必须按表头定位列，不能写死 `len(p) >= 6`** —— 否则静默变成「待转写 0 条」。

### 4.3 转写（whisper）

```bash
# macOS 上 whisper 常由 brew 装在独立 venv，用它的 python 而不是系统 python3
/opt/homebrew/Cellar/openai-whisper/*/libexec/bin/python3 transcribe_voice.py base
```

- **批处理**（模型只加载一次）是快的根本：M4 上 `tiny` **≈21× 实时**、`base` ≈4–8×
- 增量：已处理的文件名记进 `.transcribed.tsv`，重跑跳过
- 关键金额请以对账单为准（`base` 偶有错字）；**发言人未标注就写「（发言人未标注）」，不臆测**

---

## 五、macOS 权限（第二大坑区）

### 5.1 FDA 是「按进程」授的，sshd 和 Terminal 两码事

**症状**：给 Terminal 授了「完全磁盘访问」，但 ssh 进来读微信容器仍 `Operation not permitted`。

**原因**：TCC 按**进程**授权；ssh 会话的命令由 **sshd** 启动，不继承 Terminal 的授权。

**处置（二选一）**：
- 给 `/usr/sbin/sshd` 与 `/usr/libexec/sshd-session` **各授一次** FDA；或
- **走 Terminal 中继**（下节），复用 Terminal 已有的 FDA（更省事，且不用给 sshd 开权限）

### 5.2-bis ★★ ssh 本机回环（LaunchAgent 无人值守的最优姿势，2026-09-14 实测）

比 Terminal 中继更好：**零 GUI、零弹窗、无需给 Terminal 授 FDA**。

```bash
# 一次性准备：本机自登录（钥匙 + authorized_keys）
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/id_ed25519
grep -q "$(cut -d' ' -f2 ~/.ssh/id_ed25519.pub)" ~/.ssh/authorized_keys 2>/dev/null || cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys

# LaunchAgent 直接跑：launchd → ssh localhost → 脚本（借 sshd 的 TCC 上下文）
# ProgramArguments: /usr/bin/ssh -o BatchMode=yes localhost bash ~/.wxexport/refresh-studio.sh
```

**两个前提**（缺一就退回 Terminal 中继）：
① 微信重签时带 `get-task-allow` → attach 不再挑调用方/不再要交互授权
② sshd 能读微信容器（宿主已授 FDA 类权限；无则 ssh 下 `Operation not permitted`）

**两种无人值守模式怎么选**（2026-09-14 双机实测定案）：
| | ssh 本机回环 | Terminal 中继 |
|---|---|---|
| 前提 | 上述①②都要 | Terminal 授「开发者工具」+FDA（GUI 点两次） |
| 弹窗 | 零 | 首次配置时两次，之后零 |
| 适用 | **新机部署首选**（前提齐时最干净） | 前提凑不齐/嵌套签名失败时的成熟兜底 |
| 已知坑 | — | 每 4h 闪一次 Terminal 窗口 |
⚠️ 个别机器 `codesign --deep` 会因嵌套 App（如 WeChatAppEx.app）失败、微信保持原厂
hardened-runtime 签名——此时走 TCC「开发者工具」授权 Terminal 的中继路（MacBook 生产模式）。

## 5.2 Terminal 中继（LaunchAgent 的正确姿势）

LaunchAgent 直接跑脚本会**每次弹**「…想要访问其他 App 的数据」；`/bin/bash` 的副本还会被
**`Killed: 9`**。正解：

1. 复制 bash 并**重签名**（`cp /bin/bash ~/.wxexport/wxbash && codesign --force --sign - ~/.wxexport/wxbash`）
2. LaunchAgent 改为 `open -g -a Terminal ~/.wxexport/relay.command`
3. `relay.command` 里跑真正的刷新脚本，**跑完关掉自己那个终端窗口**（Terminal 控制自身窗口不需要额外授权）：
   ```bash
   osascript -e "tell application \"Terminal\" to close (every window whose tty is \"$(tty)\")"
   ```

**⚠️ 中继里的 PATH 坑**：若 PATH 让 `/opt/homebrew/bin` 排在 `/usr/bin` 前面，
`python3` 会解析到 homebrew 版 → **缺 `zstandard`/`pycryptodome`**。
→ **刷新脚本里显式写 `/usr/bin/python3`**。

### 5.3 微信重签

```bash
sudo codesign --force --deep --sign - /Applications/WeChat.app
```
- 目的：去掉 hardened runtime，让调试/内存读取可行
- **不必关闭 SIP**
- ⚠️ **微信每次升级会覆盖重签** → 需重做（**这步必须人工**）

### 5.4 图片密钥可从磁盘约定派生（不需要读内存）

`.dat` 图片是 V2 格式（头 `07 08 56 32`）＝ `AES-128-ECB + XOR` 三段式，密钥可**离线推导**：

```
xor_key = uin & 0xFF
aes_key = MD5(str(uin) + wxid).hexdigest()[:16]     # 取前 16 位 hex 当 ASCII 字符串
```

- `uin` 来源①：`app_data/net/kvcomm/key_<uin>_*.statistic` 的文件名
- `uin` 来源②：**wxid 目录名后 4 位 hex == `md5(str(uin))[:4]`**（可反推）
- 现成工具：`Bryan-Cyf/WeChatDaily` 的 `find_image_key_macos.py`（派生）+ `decode_image.py`（解码）
- 实测值示例：`uin=211854695, xor_key=0x67, aes_key=450e4c771a594ffb`
- ⚠️ `decode_image.py` 的 CLI **不传密钥**，要直接调 `v2_decrypt_file(path, out, aes_key=…, xor_key=…)`

---

## 六、同步到大脑

### 6.1 机制
Syncthing **准实时**：`fsWatcherEnabled=true` + `fsWatcherDelayS=10`（变化后 10 秒）+ 每小时兜底重扫。

### 6.2 同步完成的「可靠」判定
⚠️ Syncthing 的**事件流不可靠**（缓冲会过期，`/rest/events` 常返回空）。
→ 改用**轮询对端完成度**：

```
GET /rest/db/completion?folder=<id>&device=<对端deviceID>
    completion == 100  → 同步完成
```

（本包 `assets/scripts/sync_watch.py` 即此实现：轮询 8 秒，完成时写事件队列 + 发通知 + 触发下游整理。）

### 6.3 ⚠️ 绝不在同步目录里 `rmtree`
在 Syncthing 同步的目录里「删目录 + 重建」会触发**删除/新增竞态**，把文件在两机间**同步丢失**（实测发生过）。
**只覆盖、只新增；要删逐个 `os.remove`；大规模重组先暂停同步。**

---

## 七、大脑侧：整理管线

采集端 rsync 到的 `~/wechat-export/`，由大脑的 automation 消费：

| 时刻 | 任务 | 作用 |
|---|---|---|
| `:23 */4` | voice-transcribe | 增量转写语音 → `focus-voice-text/` |
| `:40 */4` | finance-ingest | 财务增量 → `wiki/finance/` |
| `:55 */4` | rebuild-index | 拉最新 `searchable/` → 写 **`raw/chatlogs/`**（证据区）→ 重建向量索引 |
| `0 8` / `0 21` | wechat-digest | 读文字/语音/图片/PDF → 写「我的每一天」+ 人物时间线 + 项目页 → 推 Discord |
| 每月 1 日 | vault-rollup | 生成月/季汇总（检索第一层） |
| 周一 / 周日 | idea-review / lint | 想法复盘 / 体检 |

> ⚠️ **chatlog 写在 `raw/chatlogs/`（证据区，不进图谱）**，不是 `wiki/`。
> 整理页用路径式内链 `[[raw/chatlogs/<会话>/<YYYY-MM>|YYYY-MM]]` 可点回原话。

### 检索
```bash
qkb query "<问题>"                      # BM25 + 向量混合
python3 ~/.config/qkb/qkb-lock.py ingest   # ★ 必须经锁包装器，否则并发报 UNIQUE
python3 ~/.config/qkb/qkb-lock.py embed
node ~/.config/qkb/prune-stale.mjs         # 清理已删页面的陈旧条目
```

---

## 八、移植到新系统的清单

> **Mac → Mac**：本清单照做即可（scan_cc.py 直接可用）。
> **Mac → Windows**：scan_cc.py 不能直接跑；按 `windows-collector.md` §三-b「自研路径」移植
> （原理同源——这套技巧本就源自 Windows 项目 pc_wechat_exp，验证逻辑可复用）。

- [ ] 微信 4.x macOS，**已 ad-hoc 重签**（§5.3）
- [ ] 装依赖：`pycryptodome`、`zstandard`、`pilk`（**装到 `/usr/bin/python3` 的 user site**）
- [ ] whisper（brew 版）+ ffmpeg
- [ ] 授予 FDA：Terminal（或 sshd+sshd-session）
- [ ] 准备 `~/.wxexport/`：`refresh.sh`、`focus.txt`、`scan_cc.py`、`missing_dbs.py`、
      `export_focus*.py`、`decode_focus_images.py`、`extract_money.py`、`export_searchable.py`
- [ ] LaunchAgent：`ai.wxexport.refresh`（每 4h，**经 Terminal 中继**）+ 可选 `ai.wxexport.full`（每周全量）
- [ ] 改 `focus.txt` 为**你自己的关注名单**（精确匹配）
- [ ] 首次全跑一次 `refresh.sh`，确认 9 步都出产物
- [ ] 配 Syncthing 同步到大脑；装 `sync_watch.py` 监听
- [ ] 大脑侧建 4 个 automation（§7 表）
- [ ] 首次解密后**立刻验证**：`qkb query` 能搜到内容

---

## 九、排障速查（症状 → 处置）

| 症状 | 先查 |
|---|---|
| 密钥 0 个 | 微信是否在运行且已登录？是否已重签？`Config.Cipher` 掩码是否抄对？ |
| 某段时间整段没消息 | 对照 §2.4 分片表 → 该片密钥是否缺失 → 跑只读扫描 |
| 语音解不出 | 是否去了 `\x02` 前缀？用的 `pilk` 而非 ffmpeg？ |
| 转写「待转写 0 条」 | 清单列数是否变化（§4.2） |
| 读不了微信目录 | FDA 是否授给了**当前进程**（sshd ≠ Terminal，§5.1） |
| 定时任务没产出 | 是否走了 Terminal 中继？bash 副本是否重签？PATH 是否让 homebrew python3 抢先（§5.2） |
| 同步后文件消失 | 是否在同步目录里 `rmtree`（§6.3） |
| `UNIQUE constraint failed` | 是否绕过了 `qkb-lock.py` |

---

## 十、已知限制

1. 语音转写 `base` 模型偶有错字 —— **关键金额以对账单为准**
2. 小辅助库（chatbot / general / solitaire / third_app_icon / weclaw）微信不打开 → 拿不到密钥，**不影响主流程**
3. 视频只做收集与归类，**不解析内容**
4. 微信大版本升级可能改变密钥/图片封装格式 → 需重新验证 §2.1 与 §5.4

## 5.5 ★ macOS 新机 attach 排障（2026-09-14 Studio 实测定案）

**症状**：`Not allowed to attach to process`，连自己的进程都拒。

**根因是两层的，都要修**：
| 层 | 问题 | 修复 |
|---|---|---|
| ① binary | CLT 26.4 的 debugserver 本身坏（裸跑即静默退出码1） | 升级 CLT：`softwareupdate -i "Command Line Tools for Xcode 26.5-26.5"`（label 必须带 `-26.5` 后缀） |
| ② 策略 | 目标进程无可调试标记，TCC 拒 task_for_pid | **重签微信时保留原 entitlements + 追加 `get-task-allow`**（见 §5.3 与 wechat-crack.sh ③） |

**get-task-allow 重签法**（免 sudo，App 属用户所有时）：
```bash
codesign -d --entitlements :- /Applications/WeChat.app 2>/dev/null > /tmp/wx-ent.xml
# 在 </dict> 前插入 <key>com.apple.security.get-task-allow</key><true/>
codesign --force --deep --sign - --entitlements /tmp/wx-ent.plist /Applications/WeChat.app
killall WeChat; sleep 3; open -ga WeChat   # quit 无效；重签后必须重启微信并验证 PID 已变
```

**已证伪的弯路**（别再走）：DevToolsSecurity/开发者模式、`_developer` 组、TCC 开发者工具与完全磁盘访问（授权 cmux）、brew lldb 签 cs.debugger、SIP/boot-args、MDM、launchd/sshd 宿主差异、CLT-vs-Xcode（MacBook 也只有 CLT 却全通——差异在系统小版本 26.5.1 vs 26.6.2 的策略宽严）。

**登录墙检测**：killall 重启后若 `db_storage` 零写入 = 停在登录墙（密钥在登录后才进内存）。
布哨兵：轮询 `session.db` mtime，一变即自动扫密钥（参考 /tmp/wx-autokey.sh 模式）。

**skill 标准入口**：`bash setup/wechat-crack.sh`（prepare→scan→decrypt→verify，含上述全部自检）。

## 十一、多账号采集（一机一号，命名空间隔离）

- 每个微信账号一台采集机（或同机多账号靠「最新 db_storage」探测区分——不推荐同机双活）。
- **推送目录按账号命名空间隔离**：个人号 → `~/wechat-export/`；商业号 → `~/wechat-export-biz/`。
  ⚠️ 同一联系人（如同事）可能在两个账号都有对话——**绝不合并目录**，整理时分别记录并标注账号来源。
- 商业账号数据量通常小 → `focus.txt` 用单独一行 `*` 全量关注即可。
- 大脑侧：digest/chat-ingest 提示词列出全部数据源及各自路由（见 engine/tasks/chat-ingest.md 尾部）。
