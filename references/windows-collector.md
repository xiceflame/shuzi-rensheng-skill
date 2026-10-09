# Windows 采集端（推荐给普通用户）

> **重要**：微信采集**不是 macOS 专属**。Windows 反而更省事——
> 没有 SIP / `task_for_pid` / TCC 这些限制，**不需要 FDA、不需要 Terminal 中继、不需要重签微信**。

## 一、为什么 Windows 更简单

| 难点 | macOS | **Windows** |
|---|---|---|
| 密钥获取 | SIP 阻止 `task_for_pid` → 需重签微信 | ✅ **标准开源工具内存扫描即可** |
| 容器权限 | TCC/FDA（按进程授，sshd≠Terminal） | ✅ 直接读用户目录 |
| 定时任务 | LaunchAgent 会弹「访问其他 App 数据」→ 需 Terminal 中继 | ✅ 计划任务（Task Scheduler）直接跑 |
| 其他 | bash 副本被 `Killed: 9` | ✅ 无障碍 |

## ⚠️ 先说清楚：脚本的边界

**本包的采集脚本（`assets/scripts/collector/`）是 macOS 专用**（依赖容器路径 / Terminal 中继）。
**Windows 用户**：用 §三 的现成开源工具（PyWxDump / chatlog）完成解密导出，
**把产物按 `wechat-export/` 的目录结构放好**（focus/ · focus-voice/ · focus-media/ …）——
**大脑侧的整理/检索/索引脚本全部照常工作**（它们只认目录结构，不认平台）。

## 二、数据在哪

```
%USERPROFILE%\Documents\xwechat_files\<wxid>\db_storage\
├── message\message_0..N.db      ← 聊天（按年分片）
├── message\media_0..N.db        ← 语音（VoiceInfo 表）
├── contact\contact.db
└── ...
```

> 若装在非默认盘：微信 → 设置 → 文件管理 里能看到实际路径。

## 三、密钥获取（用标准开源工具）

Windows 版微信 4.x 的密钥**在内存中**（不是磁盘明文），
获取思路与 macOS 相同：**读自己进程的内存 → 定位候选密钥 → 用数据库头 HMAC 验真**。

> 💡 **自研路线见下节「三-b」**（本包 macOS 脚本的技术源头就是 Windows 项目）。
> 微信升级导致失效时，去哪找新方案：**附录 `sources.md`**。
> 不想接触解密：走「四-b 手工导入」（完全合规）。

典型流程：
```powershell
pip install pywxdump
python -m pywxdump bias          # 查微信进程
python -m pywxdump decrypt -o D:\wx-export   # 解密导出
```

> ⚠️ **macOS 的 scan_cc.py 不能直接在 Windows 上跑**（lldb、容器路径都是 macOS 专属），
> 但**原理可移植**——见下节「自研路径」。

## 三-b、自研路径：把 Config.Cipher 原理移植到 Windows

> **好消息**：这套技巧**本来就源自 Windows** —— scan_cc.py 的出处就是
> Windows 项目 `pc_wechat_exp` 的 `config_cipher_extract.py`（定位 Config.Cipher 对象 →
> 按固定偏移取被 XOR 混淆的 blob）。macOS 版只是换了搜索策略的移植版。
> 所以「反向移植回 Windows」在原理上是通的。

**两条技术路线**（按看雪 4.0 逆向分析 + pc_wechat_exp 原理）：

| 路线 | 做法 | 适用 |
|---|---|---|
| **A. 定位对象法**（原 Windows 版） | 在微信进程内存里定位 WCDB 的 Config.Cipher 对象 → 按固定偏移读取被 32 字节掩码 XOR 混淆的配置 blob → 解混淆得密钥 | 微信 4.0.x；对象偏移随版本微调 |
| **B. 模式搜索法**（macOS 版同款） | 对 32 个掩码相位，在内存中搜索「XOR 后的 `x'` 两字节模式」→ 命中处解混淆 → HMAC 验真 | 更不挑版本偏移，macOS 版即此法 |

**Windows 实现要点**（对应改写 scan_cc.py）：
1. **内存读取**：`ReadProcessMemory`（WinAPI）读 WeChat 进程内存段（等价于 macOS 的 lldb 只读）
2. **进程定位**：`CreateToolhelp32Snapshot` 找 WeChat.exe + 对应账号的进程
3. **验证逻辑不变**：命中候选 → 用库文件**第一页 HMAC 验真**（这段代码直接复用）
4. **依赖**：Python + `ctypes`/`psutil`（Windows 免费自带能力，无需驱动/管理员常驻）
5. **估计工作量**：对有逆向经验者 1-2 天；验证逻辑（HMAC/解密参数）可直接复用本包代码

**前置条件（与 macOS 相同的原则）**：
- 微信正在运行且已登录（密钥只在内存里有）
- 只读、不断点、不写进程 —— 不会让微信崩溃（与 macOS 版同一安全性质）

## 四、语音 / 图片（与平台无关）

- **语音**：`media_N.db` 的 `VoiceInfo.voice_data` 是**明文 SILK v3**；
  去掉 `\x02` 前缀 → `pilk` 解码 → WAV（详见 `wechat-pipeline.md` §4）
- **图片**：`.dat` 是 V2 封装；密钥同样可从**磁盘约定**派生
  （`xor_key = uin & 0xFF`、`aes_key = MD5(str(uin)+wxid)[:16]`）

## 四-b、无工具路径（完全合规）：手工导入

若不愿承担解密工具的合规风险，**系统不接微信也能完整运转**：
1. 手机微信 → 聊天记录迁移到 PC（官方功能）
2. 重要会话**手动导出**（复制文本 / 截图 / 官方备份文件）
3. 放进 `<vault>/raw/`（`raw/docs/` 或 `raw/misc/`）
4. 整理 / 检索 / 图谱 **全部照常工作**

> 对「只想管理笔记与文档」的客户，这就是完整产品。

## 五、定时（Windows 计划任务）

```powershell
schtasks /create /tn "数字人生-采集" /tr "python D:\tools\refresh.py" /sc hourly /mo 4
schtasks /create /tn "数字人生-整理" /tr "bash D:\engine\run.sh chat-ingest" /sc daily /st 08:07
```

## 六、能省掉什么

- ✅ 不需要 Syncthing（agent 和 vault 都在这台 Windows 上）
- ✅ 不需要 Terminal 中继 / FDA / 重签
- ✅ 不需要 OpenClaw（`engine/run.sh` 会用本机有的任何 agent）
