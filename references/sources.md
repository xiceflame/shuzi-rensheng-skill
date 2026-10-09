# 附录：参考仓库与解决方案来源

> **用途**：微信版本升级导致采集失效、图片/语音解不出、路径变化时，**按这里去找解决方案**。
> 本包自研脚本（scan_cc.py 等）的原理与出处也在其中——改脚本前先对照原始实现。

---

## 一、密钥提取（原理与逆向分析）

| 来源 | 说了什么 | 我们怎么用的 |
|---|---|---|
| **[sunhanaix/pc_wechat_exp](https://github.com/sunhanaix/pc_wechat_exp)**（Windows） | **Config.Cipher 技巧的源头**：WCDB 在内存保留 `com.Tencent.WCDB.Config.Cipher` 对象，配置 blob 被固定 32 字节掩码 XOR 混淆；`config_cipher_extract.py` 用「定位对象 → 固定偏移取 blob」 | ★ `scan_cc.py` 的直接出处。macOS 版改为「按 32 相位搜索 XOR 后的 `x'` 模式」，更不挑版本偏移 |
| **[看雪论坛：微信 4.0 聊天记录数据库解密分析](https://bbs.kanxue.com/thread-284417.htm)** | Windows 4.0.0.26 逆向全过程：多分片加密结构、密钥定位、数据目录变化 | 理解 4.0 存储结构的主参考；**新版本失效时先来这里搜最新帖** |
| **[CTF 导航：解开 Windows 微信 4.0 主数据库](https://www.ctfiot.com/307364.html)** | 密钥提取思路 + **聊天图片 DAT 文件解密** | Windows 密钥路线 + 图片解密的交叉验证 |
| **[ycccccccy/wx_key](https://github.com/ycccccccy/wx_key)** | 微信 4.0+ 密钥的**暴力搜索**思路（不依赖版本偏移） | ⚠️ 原 repo 已被 DMCA 下架——找 **GitHub fork 网络**或 web.archive.org 的历史快照；**思路本身**（内存搜索 + 逐候选 HMAC 验真）仍是 Windows 自研的首选路线 |
| **chatlog**（sjzar，已删库） | FAQ #197 记录了关键版本行为：**Windows 4.0.3.36+ / macOS 4.0.3.80+ 密钥在内存中的存放方式变化**；4.1.x 可「外部取密钥 → 手动输入」解密 | 版本行为对照表的价值最大；原 repo 已删，从 **fork / [Wayback Machine](https://web.archive.org)** 找 README 与 issues |

> **已下架仓库的找法**：GitHub 仓库页 → Forks 标签（别人的 fork 常在）；
> 或 `web.archive.org/web/<URL>` 找历史快照；或在 GitHub 搜同名关键词找复刻。

---

## 二、图片密钥与解码

| 来源 | 说了什么 | 我们怎么用的 |
|---|---|---|
| **[Bryan-Cyf/WeChatDaily](https://github.com/Bryan-Cyf/WeChatDaily)**（macOS） | `find_image_key_macos.py`：图片密钥**离线派生**（`xor_key = uin & 0xFF`；`aes_key = MD5(str(uin)+wxid)[:16]`）；`decode_image.py`：V2 格式（`07 08 56 32` 魔数）= AES-128-ECB + XOR 三段式 | ★ 图片解码直接采用；`uin` 从 `key_<uin>_*.statistic` 文件名或 wxid 目录名反推 |

---

## 三、语音

| 来源 | 用途 |
|---|---|
| **[pilk](https://pypi.org/project/pilk/)**（PyPI） | SILK v3 解码（微信 `voice_data` 去掉 `\x02` 前缀后喂给它） |
| **openai-whisper / faster-whisper / mlx-whisper** | 转写引擎选型见 `speech-to-text.md`（增量 base / 批量 GPU） |

---

## 四、版本与路径变化

| 来源 | 说了什么 |
|---|---|
| **[知乎：微信 4.1 版本变化及文件存储路径](https://zhuanlan.zhihu.com/p/1940701662940477422)** | 4.1 首次升级会**新建 `xwechat_files`** 并迁移旧记录（我们的账号目录自动探测即据此设计） |
| **[CSDN 问答：3.9 升 4.0 聊天记录问题](https://ask.csdn.net/questions/9592989)** | 4.0 把单库 SQLite 改为**多分片加密**——分片年表（`wechat-pipeline.md` §2.4）的背景 |

---

## 五、知识库侧组件（活跃维护中）

| 组件 | 位置 |
|---|---|
| qkb（检索：BM25+向量+RRF） | `npm i -g @miguelarios/qkb` |
| Ollama / Qwen3-Embedding / bge-reranker-v2-m3 | ollama.com / HuggingFace（国内走 hf-mirror.com） |
| Syncthing | syncthing.net |

---

## 六、出了问题去哪找（速查路由）

```
微信升级后「密钥 0 个」
   → 看雪论坛搜「微信 <版本号> 数据库 密钥」（第一站，逆向分析最快出现的地方）
   → 对照 pc_wechat_exp / wx_key 的思路是否仍适用
   → 我们要改的通常只是「内存搜索特征/对象偏移」，HMAC 验真与解密参数不动

图片解不出
   → Bryan-Cyf/WeChatDaily 的 DAT 格式与密钥派生公式
   → CTF 导航那篇的图片解密章节

语音解不出
   → 先确认去了 \x02 前缀、用 pilk 而非 ffmpeg（speech-to-text.md §排障）

数据路径找不到（如 4.1 的 xwechat_files）
   → 知乎 4.1 路径帖；我们的脚本已做自动探测

GitHub 仓库 404（被下架）
   → Forks 标签 / web.archive.org / GitHub 搜索同名复刻
```
