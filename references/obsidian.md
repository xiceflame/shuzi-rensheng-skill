# Obsidian 接入（数据 · 节点 · 图谱配色）

> 本系统**用 Obsidian 做「眼睛」**（浏览），但**不依赖它运行** —— 数据是纯 Markdown 文件夹，
> 没有 Obsidian 也能被 agent 读写、被检索库索引。
> 本文讲三件事：**数据怎么存**、**节点怎么建**、**图谱颜色怎么设计**。

---

## 一、数据保存方式

### 1.1 一切皆纯文本
- 每个「页面」= 一个 `.md` 文件；**没有数据库、没有专有格式**
- 所以：可用任意编辑器打开、可 git 版本化、可被任何工具读写
- **Obsidian 只是叠加的一层视图**，删了 Obsidian 数据照样在

### 1.2 目录 = 分类
```
<vault>/
├── CLAUDE.md          ← 规范（agent 的"宪法"）
├── README.md          ← 工程总览
├── raw/               ← 原始素材（只读 · 不进图谱）
│   ├── chatlogs/      ← 历史聊天证据
│   ├── media/         ← 项目素材（合同/发票/关键截图）
│   └── docs/ voice/ screenshots/ clips/ misc/
├── wiki/              ← 整理层（agent 维护）
│   ├── index.md · log.md
│   ├── journal/       ← 时间轴（我的每一天）
│   ├── people/        ← 人物轴
│   ├── projects/      ← 项目
│   ├── monthly/ quarterly/  ← 汇总层
│   └── tasks/ concepts/ finance/ ideas/ sources/ entities/ outputs/ private/
└── templates/         ← 模板
```

### 1.3 关键：`raw/` 要从图谱里排除
`.obsidian/app.json`：
```json
{ "userIgnoreFilters": ["raw/"] }
```
**为什么**：`raw/chatlogs/` 可能有几百个月度文件；不排除的话，图谱会被原始素材**淹没**，
看不到整理层的结构。但它们**仍会被检索库索引**（可点回原话）—— 两全其美。

### 1.4 多端互联（电脑 ⇄ 手机）

vault 就是一个文件夹 → 用任何同步方案都行。但**跨网络时会有坑**：

| 方案 | 适用 | 优点 | 代价 |
|---|---|---|---|
| **Obsidian Sync**（官方） | 想省事 | 开箱即用、自带冲突处理 | **付费**（按月） |
| **Syncthing** | 免费、可控 | 免费、点对点、快 | 需配；**跨网要隧道** |
| **iCloud / 坚果云** | 苹果生态 / 国内 | 简单 | 大库慢、冲突处理弱 |
| **git** | 极客 | 有版本历史 | 不适合二进制附件 |

#### ⚠️ 跨网络的关键：需要一条隧道

多端互联的**真正门槛不是同步软件，是网络可达**：
- **同一局域网** → Syncthing 直接发现，无需额外配置
- **不同网络**（手机 4G / 公司网 / 家里）→ **两端互不可见** → Syncthing 连不上

**解决：先组网，再同步。**

| 组网方式 | 说明 |
|---|---|
| **Tailscale**（推荐） | 免费、零配置、NAT 穿透好；装完两端互相可见，Syncthing 立刻能连 |
| ZeroTier / WireGuard | 同类，配置略多 |
| 公网 IP + 端口转发 | 可行性看运营商，且有安全风险 |

> 🔧 **这一步必须人工**：在**每台设备**上装 Tailscale 客户端并登录**同一账号**。
> 自动化流程替代不了（涉及图形界面登录/授权）。
> **在给用户列步骤时，把它明确标成「需人工」。**

#### ★ 双单向桥（agent 场景的定案模式）
**agent 永不直接写 iCloud**——主库是本地真实目录；桥每 30 分钟：
①主库 → iCloud 镜像（手机全量可读）②iCloud/收件箱 → 主库（手机随手写回流，处理后转已入库）。
脚本：`assets/scripts/icloud-bridge.sh`（fileprovider 探活 + brctl download + 双向 rsync）。

#### 本方案的实际做法（参考）
```
MacBook（采集端） ⇄ macmini（大脑）  → 已在同一 Tailscale 网络
手机端 Obsidian   → 装 Tailscale + Obsidian，vault 用 Obsidian Sync 或 Syncthing 拉
```

### 1.5 多端同时编辑：冲突怎么处理

**两端都在编辑同一个 vault** 时，同步软件会产生**冲突副本**
（Syncthing 会生成 `xxx.sync-conflict-YYYYMMDD-HHMMSS.md`）。

**处理规则**：
1. **以修改时间最新的为准**，旧版**归档**（不删）
2. 用 `conflict-sentinel` 脚本**每 10 分钟自动收口**（见 `services.md`）
3. ⚠️ **不要让两端同时改同一页** —— 尤其别让 agent 在 A 端写的同时人在 B 端改

> ⚠️ **别在同步目录里做「删目录+重建」**（会触发同步竞态丢文件），见 `safety.md`。

---

## 二、节点与边的创建

### 2.1 节点 = 文件，边 = `[[链接]]`
| Obsidian 概念 | 本系统的做法 |
|---|---|
| **节点** | 一个 `.md` 页面 |
| **边** | 页面里的 `[[另一页]]` |
| **孤岛** | 没有任何页面链接到它 —— **要尽量避免** |
| **未解析节点**（虚线） | `[[xxx]]` 指向的页面不存在 |

> **图谱好不好看，取决于有没有认真写链接。** 内容写得再好，不链接就是一堆孤岛。

### 2.2 建页面的三条硬规则

**① frontmatter 三件套**（缺了检索库不索引）
```yaml
---
id: <uuid>
context: <上下文名>
created: YYYY-MM-DD
---
```

**② 每个页面都要「链出去」**
- 项目页 → 链**参与人** `[[人]]`、**相关项目** `[[项目]]`、**相关会话** `[[raw/chatlogs/...]]`
- 人物页 → 链**所属项目**、**时间线里的当天** `[[YYYY-MM-DD]]`
- 日记页 → 链**当天涉及的人与项目**
- 汇总页 → 链**下钻目标**

**③ 引用证据用「路径式」内链**
```markdown
[[raw/chatlogs/<会话名>/YYYY-MM|YYYY-MM]]
```
好处：显示简洁（`2026-09`），点击能跳到**原话**。

### 2.3 让节点名字可读
- 人名带别名：`[[<教练A>]]（帅哥/张<教练A>）`
- 用显示文本别名：`[[长文件名|简称]]`
- ⚠️ **文件名要唯一** —— 不同目录下的同名文件（如多个 `2024-06.md`）会让 Obsidian 无法消歧义，
  **必须用能区分的命名**（如 `<会话>/<YYYY-MM>.md` 或扁平 `<会话>_<YYYY-MM>.md`）

### 2.4 检查图谱健康
```bash
# 找孤岛：没有任何页面链接到它
grep -rL "\[\[" <vault>/wiki/*.md

# 找断链：[[xxx]] 指向不存在的页面（Obsidian 里显示为虚线节点）
#  → Obsidian 的「未解析链接」面板，或 lint 工作流
```
> 本方案的 `lint` 工作流每周自动做这件事。

---

## 三、图谱配色（★ 设计逻辑）

配置文件：`.obsidian/graph.json` 的 `colorGroups`。
**按查询（query）分组着色** —— query 支持 `tag:` `path:` `file:` 三种。

### 3.1 配色设计原则

| 原则 | 说明 |
|---|---|
| **色系 = 维度** | 一条线一个色系（业务橙 / 时间蓝 / 人物青 / 主业紫 / 爱好绿…） |
| **同色系深浅 = 层级** | 深色=具体（日记、具体项目），浅色=汇总/主体（月汇总、公司主体） |
| **红 = 需行动** | 只给 `tasks/`（要去做的事） |
| **灰 = 弱化** | 给 `index`/`log` 等元页面（不需要关注） |
| **一眼看出归属** | 看颜色就知道这个节点属于哪条线 |

### 3.2 参考方案（15 组）

| 查询 | 颜色 | 设计意图 |
|---|---|---|
| `tag:#<业务线A>` | `#F97316` 橙 | 业务能力分类（深） |
| `tag:#<业务线B>` | `#EA580C` 深橙 | 同上 |
| `tag:#<业务线C>` | `#F59E0B` 琥珀 | 同上 |
| `file:<公司主体> OR …` | `#FDBA74` **浅橙** | **同色系浅** = 支撑层 |
| `file:<主业页> OR …` | `#8B5CF6` 紫 | 主业 |
| `file:<爱好页>` | `#22C55E` 绿 | 爱好 |
| `file:<个人页>` | `#EC4899` 粉 | 个人 |
| `path:wiki/people` | `#06B6D4` 青 | **人物轴** |
| `path:wiki/journal` | `#3B82F6` **深蓝** | **时间轴** |
| `path:wiki/monthly OR path:wiki/quarterly` | `#93C5FD` **浅蓝** | 汇总层 —— **与 journal 同色系** |
| `path:wiki/finance` | `#EAB308` 黄 | 财务 |
| `path:wiki/tasks` | `#EF4444` **红** | **需行动** |
| `path:wiki/concepts OR entities OR sources OR ideas OR outputs` | `#14B8A6` 蓝绿 | 辅助类 |
| `path:wiki/index.md OR path:wiki/log.md` | `#94A3B8` **灰** | **元页面，弱化** |

> **最妙的一处**：`journal`（深蓝）与 `monthly/quarterly`（浅蓝）**同色系** ——
> 一眼就看出「天 → 月 → 季」是同一维度下的层级关系。

### 3.3 怎么改（改成你自己的线）
1. 用 Obsidian 打开 vault → **图谱视图** → ⚙️ **Groups** → 添加颜色组
2. 或直接改 `.obsidian/graph.json`（本包 `assets/obsidian/graph.json` 是模板）
3. **query 语法**：
   - `path:wiki/people` —— 按路径
   - `tag:#工作` —— 按标签
   - `file:某页面` —— 按文件名
   - 组合：`path:wiki/projects OR tag:#工作`

### 3.4 建议的图谱设置
```json
{
  "showTags": false,          // 标签节点会喧宾夺主
  "showAttachments": false,   // 图片/PDF 不在图谱里显示
  "showOrphans": true,        // ★ 显示孤岛 —— 方便发现「没链接的页」
  "hideUnresolved": false     // ★ 显示断链（虚线）—— 方便发现「指向不存在的页」
}
```
> `showOrphans` 和 `hideUnresolved` **故意开着** —— 让问题**显形**，配合 `lint` 工作流修复。

---

## 四、Obsidian 不是必需的

| 不装 Obsidian 也行 | 替代 |
|---|---|
| 浏览 | 任意 Markdown 编辑器（Typora / VS Code / 甚至文件管理器） |
| 图谱 | `lint` 工作流的文本报告 |
| 搜索 | 检索库 CLI（`qkb query` / `vaultq`） |
| 双链跳转 | 编辑器自带的「转到定义」 |

> **本系统真正依赖的是「纯文本 + `[[链接]]` + frontmatter」这套约定**，
> Obsidian 只是把这些约定**可视化**得最好的工具。
