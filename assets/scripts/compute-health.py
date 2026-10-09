#!/usr/bin/env python3
"""计算节点健康巡检：4090 嵌入 / 重排 + 本地回落 + qkb 待嵌入数。

只在**状态发生变化**时推 Discord（避免刷屏）：
  - 4090 嵌入服务 掉线/恢复（掉线时 qkb 已自动回落本机，注明即可）
  - 4090 重排服务 掉线/恢复（掉线时 vaultq 已自动回退 qkb 排序）
  - 出现新的待嵌入积压（pening 由 0 变 >0）——可能是算力不可用

用法：`python3 ~/.config/qkb/compute-health.py [--notify-test]`
默认由 launchd（ai.shuzi.qkb-compute-health，每 10 分钟）拉起。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

OPENCLAW = "/opt/homebrew/bin/openclaw"
QKB = "/opt/homebrew/bin/qkb"
DISCORD_CHANNEL = os.environ.get("DISCORD_CHANNEL", "")
EMBED_URL = os.environ.get("EMBED_URL", "")   # 例: http://<GPU机>:11434；留空=跳过嵌入探测
RERANK_URL = os.environ.get("RERANK_URL", "")   # 例: http://<GPU机>:8081/health；留空=跳过重排探测
STATE = os.path.expanduser("~/.config/qkb/compute-health.state")
LOG = os.path.expanduser("~/.config/qkb/compute-health.log")


def probe(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def pending() -> int | None:
    try:
        p = subprocess.run([QKB, "status"], capture_output=True, text=True, timeout=90)
        m = re.search(r"\((\d+) pending\)", p.stdout)
        if m:
            return int(m.group(1))
        return 0 if "pending" not in p.stdout else None
    except Exception:
        return None


def notify(msg: str):
    try:
        subprocess.run([OPENCLAW, "message", "send", "--channel", "discord",
                        "--target", "channel:%s" % DISCORD_CHANNEL,
                        "--message", msg], capture_output=True, timeout=60)
    except Exception as e:
        log(f"notify failed: {e}")


def log(s: str):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + s
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main() -> int:
    embed_up = probe(EMBED_URL)
    rerank_up = probe(RERANK_URL)
    pend = pending()
    cur = {"embed_up": embed_up, "rerank_up": rerank_up, "pending": pend, "ts": time.time()}

    if "--notify-test" in sys.argv:
        notify("✅ 计算节点健康巡检已上线：4090 嵌入 %s / 重排 %s；qkb 待嵌入 %s。"
               % ("在线" if embed_up else "离线", "在线" if rerank_up else "离线", pend))
        return 0

    prev = {}
    try:
        prev = json.load(open(STATE))
    except Exception:
        pass

    msgs = []
    if prev.get("embed_up") is not None and prev["embed_up"] != embed_up:
        msgs.append("4090 **算力** %s（日常增量走本机、不受影响；全量/大批量才需 4090）" % (
            "恢复 ✅" if embed_up else "离线 ⚠️"))
    if prev.get("rerank_up") is not None and prev["rerank_up"] != rerank_up:
        msgs.append("4090 **重排**服务 %s" % (
            "恢复 ✅" if rerank_up else "掉线 ⚠️（vaultq 自动回退纯 qkb 排序）"))
    if (isinstance(pend, int) and isinstance(prev.get("pending"), int)
            and prev["pending"] == 0 and pend > 0):
        msgs.append("⚠️ 出现 **%d** 个待嵌入 chunk（算力可能不可用）" % pend)

    if msgs:
        notify("🖥 数字人生·计算节点巡检\n" + "\n".join("- " + m for m in msgs))
        log("notified: " + " | ".join(msgs))

    log("embed_up=%s rerank_up=%s pending=%s%s" % (
        embed_up, rerank_up, pend, "  [changed]" if msgs else ""))
    try:
        json.dump(cur, open(STATE, "w"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    # `--loop`：常驻守护（由 launchd KeepAlive 拉起）——因为 macOS 的
    # StartInterval 对"跑完即退"的 Agent 常不按时触发（实测 runs=1 后不再跑）。
    if "--loop" in sys.argv:
        while True:
            try:
                main()
            except Exception as e:  # noqa: BLE001
                log(f"loop error: {e}")
            time.sleep(600)
    sys.exit(main())
