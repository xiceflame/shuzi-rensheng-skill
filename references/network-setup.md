# 多机组网 —— 用你自己的 Tailscale 打通「采集机 ⇄ 大脑 ⇄ GPU」

> 本系统的跨机流水线（refresh.sh 推送 / rebuild_index.sh 拉取 / rerank / MinerU 桥）
> 都只走 **SSH + rsync**，所以唯一的前置条件是：**几台机器能互相 ssh 通**。
> Tailscale 是让这件事「在任何网络环境下都成立」的推荐方式——公司的网、家里的网、4G 热点，都一样。
>
> **单机部署（大多数用户）不需要本页**：`config.json` 的 `network.topology` 保持 `single`，
> 所有跨机推送自动跳过。

---

## 一、什么时候需要这页

| 形态 | 表现 | 要做什么 |
|---|---|---|
| **单机** | 采集 + 大脑同一台（README 形态①②） | **跳过本页**，`topology: single` |
| **采集机 + 大脑** | 如 MacBook 采集微信、台式机/服务器跑 agent 整理 | 本页 §2–§6 |
| **另有 GPU 机** | 嵌入/重排/OCR 放独立 GPU 机（README 形态③） | 本页 §2–§6 + §7 |

角色定义（后文沿用）：
- **采集机**：登录微信、跑解密导出的机器（macOS 需 FDA，见 `wechat-pipeline.md`）
- **大脑**：vault（知识库）所在、agent 整理与检索发生的机器
- **GPU 机**（可选）：跑嵌入/重排/MinerU 的算力机（常为 Windows + NVIDIA）

## 二、原理（30 秒）

Tailscale = **用你的账号把多台设备组成一个私有内网**：
- 每台设备拿到一个固定内网 IP（`100.x.y.z`，公网不可路由）＋ 可选的 MagicDNS 名字
- 通信走 WireGuard 加密，NAT 穿透自动协商（打洞失败时经中继，慢但仍通）
- **没有任何端口暴露公网**；对两端所在的网络（公司/家庭/4G）零要求
- 免费档：100 设备 / 3 用户，个人用绰绰有余

> 同类替代：ZeroTier、自建 WireGuard、Tailscale 自托管 headscale——思路相同，本页以 Tailscale 为准。

## 三、组网四步

### ① 每台机器装客户端

| 系统 | 安装 |
|---|---|
| macOS | App Store 搜 Tailscale（推荐，图形界面）；或 `brew install --cask tailscale` |
| Windows | 官网下载安装包 |
| Linux | `curl -fsSL https://tailscale.com/install.sh | sh` |

### ② 登录**同一个账号**【🔧 必须人工】

> 🔧 这一步无法自动化（涉及浏览器图形界面登录/授权），每台机器一次。
> **在给用户列步骤时，把它明确标成「需人工」。**

在每台机器上登录**同一个** Tailscale 账号（Google/GitHub/邮箱注册均可）。
⚠️ 最常见错误：两台机器登了不同账号 → 永远互不可见。

### ③ 确认互见

```bash
tailscale status        # 应列出所有已登录设备及其 100.x IP
```

### ④ 起稳定的名字（推荐 MagicDNS）

- 登录 Tailscale 管理台（https://login.tailscale.com）→ Machines → 给每台机器改名（如 `brain`、`collector`、`gpu`）
- 开启 MagicDNS 后可直接用短名（`ssh brain`）；也可用完整名 `brain.tailxxxx.ts.net`
- 不开 MagicDNS 就用 `100.x.y.z` IP，效果一样

## 四、SSH 免密（采集机 → 大脑，一次配置）

流水线全部走 `ssh -o BatchMode=yes`（无人值守），必须免密：

```bash
# 在采集机上：
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/id_ed25519
ssh-copy-id <user>@<大脑名或IP>        # 输一次大脑密码，之后永久免密
ssh -o BatchMode=yes <user>@<大脑名或IP> echo ok   # 必须输出 ok 且不问密码
```

> Windows 大脑：设置 → 可选功能 → 装 OpenSSH 服务器；
> ⚠️ Windows OpenSSH **没有 rsync**，推送脚本会自动退化为 scp/roboclay（见 `attachments-ocr.md`）。
> macOS 大脑若要被无人值守 ssh 读微信容器，sshd 需单独授 FDA（见 `wechat-pipeline.md` §5.1——仅采集机本机回环场景需要，跨机推送不涉及）。

## 五、写入 config.json（大脑侧与采集机各一份）

`~/.shuzi-rensheng/config.json`：

```jsonc
"network": {
  "topology": "multi",
  "brain": { "host": "user@brain.tailxxxx.ts.net",   // 采集机上填；user@ 可省略若本机用户名相同
             "dir": "wechat-export" },                 // 大脑侧接收目录（相对其 HOME）
  "gpu":   { "host": "user@gpu",                      // 用到 GPU 机才填（§7）
             "rerank_url": "" }                       // http://<GPU机>:8081/rerank
}
```

> 环境变量优先级更高（`WX_TOPOLOGY` / `WX_REMOTE` / `WX_REMOTE_DIR` / `GPU_SSH_HOST` / `RERANK_URL_REMOTE`），
> 适合「一份脚本多机复用」的场景。多账号采集（个人号/商业号）用 `WX_REMOTE_DIR` 区分（如 `wechat-export-biz`）。

大脑侧准备接收目录：`mkdir -p ~/wechat-export`（与 `dir` 一致即可）。

## 六、验证清单（全过才算组网完成）

```bash
tailscale status | grep -c .          # ≥ 机器数
ssh -o BatchMode=yes <brain> echo ok  # 输出 ok（采集机上跑）
# 采集机试推一个小目录：
rsync -az -e "ssh -o BatchMode=yes" ~/.wxexport/focus/ <brain>:wechat-export/focus/ && echo 推送OK
bash setup/detect.sh                  # has_tailscale=true, tailscale_up=true, network_topology=multi
bash ~/.wxexport/refresh.sh           # 末尾应出现「已推送 focus …」而非报错
```

- [ ] `tailscale status` 两端互见
- [ ] 采集机 → 大脑 ssh 免密（BatchMode 不问密码）
- [ ] 试推一个目录成功
- [ ] `refresh.sh` 跑完日志里有「已推送」或「单机模式：跳过推送」（二者必居其一，报错即未配好）

## 七、GPU 机接入（可选，嵌入/重排/OCR 加速）

前提：GPU 机也登进**同一个** Tailscale 账号（§三）。

1. **服务暴露**：GPU 机上相应服务绑 `0.0.0.0`（ollama / llama-server rerank 等），
   防火墙**只放行 Tailscale 网段 `100.64.0.0/10`，绝不暴露公网**（详见 `embedding-setup.md`、`vector-search.md` §5.2）
2. **重排**：大脑侧 `config.json` → `network.gpu.rerank_url = "http://<GPU机>:8081/rerank"`
   （服务不可用时 vaultq 自动回退本地/原始排序，不中断）
3. **MinerU OCR 桥**：`network.gpu.host`（或环境变量 `GPU_SSH_HOST`）+ 可选 `GPU_SSH_DIR`（默认 `E:/AI/mineru`，Windows 约定）
4. ssh 免密同 §四（大脑 → GPU 机）

## 八、常见坑

| 症状 | 原因 | 处理 |
|---|---|---|
| 两台机器 `tailscale status` 互相看不到 | 登了**不同账号**（最常见） | 退出后用同一账号重登 |
| 能 ping 通但 rsync/ssh 超时 | 对端没装/没开 ssh 服务 | macOS：打开「远程登录」；Windows：装 OpenSSH Server；Linux：`apt install openssh-server` |
| 速度奇慢 | NAT 打洞失败，走中继（DERP） | 一般可用不管；追求带宽看 Tailscale 自定义 DERP / 直连出口 |
| 好好的突然全断（数月后） | Tailscale 密钥默认约 180 天过期 | `tailscale up` 重新授权，或在管理台关掉密钥过期（个人设备建议关） |
| `Permission denied (publickey)` | 免密没配成 | 重跑 §四 `ssh-copy-id`；确认 `ssh -o BatchMode=yes` 不弹密码 |
| Windows 大脑 scp 正常 rsync 报错 | Windows OpenSSH 无 rsync | 正常现象，脚本自动退化（`attachments-ocr.md`） |
| 换了台机器 IP 变了 | 删旧设备重加会换 100.x IP | **用 MagicDNS 名字别用 IP**；或管理台固定 IP |

## 九、单机模式的行为（对照）

`topology: single`（或未配置 brain.host）时：
- `refresh.sh` / `full_refresh.sh`：解密导出照常，**跳过推送**（产物留在本机 `~/wx-export`，大脑侧直接读）
- `vaultq.py`：只用本机 rerank，无远端一跳
- `mineru_bridge.sh`：未配 `gpu.host` 直接报「未配置 GPU 主机」退出（不误跑本地慢路径）

> 结论：**先单机跑通，再升级多机**——组网是增量步骤，不是前置门槛。
