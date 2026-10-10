# 诊断与错误报告

数字人生默认采用本地优先、隐私保护的诊断方式。

## 命令

- python3 setup/instance.py --json：显示当前安装实例 ID。
- python3 setup/instance.py --reset：主动轮换实例 ID。
- python3 engine/diagnostics.py：生成本地脱敏报告。
- python3 engine/diagnostics.py --export ./report.json：导出报告，便于手动上传或发给维护者。

## 可识别范围

报告包含 instance_id、report_id、版本/平台、依赖可见性、配置是否可读、Tailscale/qkb/Agent 能力探测结果和稳定错误码。它不把设备序列号、MAC 地址、微信账号当作身份。

## 隐私边界

默认不读取或上传微信聊天正文、原始数据库、Obsidian 笔记正文、API key、Cookie、密码、原始媒体或绝对路径中的用户名。自动上传没有在本版本开启；后续若增加上传，必须采用明确 opt-in、一次性 upload token 和可撤销的实例关联。

## Issue 报告

提交问题时优先提供 report_id、instance_id、版本、错误码和复现步骤。不要粘贴聊天内容、数据库、凭据或完整知识库目录。
