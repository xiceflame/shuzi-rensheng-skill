#!/usr/bin/env python3
"""
Syncthing 同步状态监听器（大脑侧）—— 轮询版，稳定可靠。

- 每 15 秒查一次「数字人生」文件夹状态
- 状态从「同步中」变为「完成（idle 且 needBytes==0）」时：
    · 写一条事件到队列 ~/wechat-export/sync-events.jsonl（供 agent 读取）
    · 发一条 Discord 通知（5 分钟防抖）
- 同时捕捉「有文件正在同步」的开始，也记一条

用法: python3 sync_watch.py [--once]
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

API = "KLqZNYa3bvbinFidXjciFkemTyxLmnEF"
BASE = "http://127.0.0.1:8384"
FOLDER_ID = "vault"
FOLDER_LABEL = "数字人生"
QUEUE = os.path.expanduser("~/wechat-export/sync-events.jsonl")
OPENCLAW = "/opt/homebrew/bin/openclaw"
DISCORD_CHANNEL = os.environ.get("DISCORD_CHANNEL", "")   # 留空=只写事件队列，不发 Discord
DIGEST_CRON = "094f54c4-7b6b-425a-a422-41b63dde02c9"   # 摘要任务（早间）
TRIGGER_DIGEST = True        # 同步完成后自动跑一次摘要
TRIGGER_DEBOUNCE_S = 1800    # 触发防抖：30 分钟最多一次
POLL_S = 8
PEER = "6ZWYU7E-22BBUOI-DQCO34S-O3FQIBW-6TI74MI-GKNU367-HGNVUQE-XDO4EQ2"  # MacBook
DEBOUNCE_S = 300


def status():
    req = urllib.request.Request(
        "%s/rest/db/status?folder=%s" % (BASE, FOLDER_ID),
        headers={"X-API-Key": API})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def completion():
    """对端（MacBook）对该文件夹的完成度 0..100。"""
    req = urllib.request.Request(
        "%s/rest/db/completion?folder=%s&device=%s" % (BASE, FOLDER_ID, PEER),
        headers={"X-API-Key": API})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def log_event(kind, data):
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "event": kind, **data}
    try:
        os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
        with open(QUEUE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    print(rec, flush=True)


def run_digest():
    """同步完成后触发一次摘要（即闭环）。"""
    try:
        subprocess.run([OPENCLAW, "cron", "run", DIGEST_CRON],
                       capture_output=True, timeout=120)
        print("已触发摘要任务", flush=True)
    except Exception as e:
        print("触发摘要失败:", e, flush=True)


def notify(msg):
    try:
        subprocess.run([OPENCLAW, "message", "send", "--channel", "discord",
                        "--target", "channel:%s" % DISCORD_CHANNEL,
                        "--message", msg], capture_output=True, timeout=60)
        print("已通知:", msg, flush=True)
    except Exception as e:
        print("通知失败:", e, flush=True)


def main():
    once = "--once" in sys.argv
    prev = None
    last_notify = 0.0
    print("开始监听「%s」同步状态（每 %ds 轮询）" % (FOLDER_LABEL, POLL_S), flush=True)

    while True:
        try:
            st = status()
        except Exception as e:
            print("查询失败:", e, flush=True)
            time.sleep(POLL_S)
            if once:
                return
            continue

        n = st.get("localFiles", 0)
        try:
            pct = completion().get("completion", 0)
        except Exception:
            pct = None
        full = (pct is not None and pct >= 100.0)

        if prev is not None and full != prev:
            if not full:
                log_event("sync_start", {"folder": FOLDER_LABEL, "peer_completion": pct})
            else:
                log_event("sync_done", {"folder": FOLDER_LABEL, "files": n,
                                        "peer_completion": pct})
                t = time.time()
                if (t - last_notify) > DEBOUNCE_S:
                    last_notify = t
                    notify("✅「%s」已同步到 MacBook（%d 个文件），正在触发摘要…"
                           % (FOLDER_LABEL, n))
                    if TRIGGER_DIGEST and (t - (globals().get("_last_trigger") or 0)) > TRIGGER_DEBOUNCE_S:
                        globals()["_last_trigger"] = t
                        run_digest()
        prev = full

        if once:
            print("当前: state=%s files=%s peer_completion=%s" % (st.get("state"), n, pct))
            return
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
