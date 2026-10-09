#!/usr/bin/env python3
"""近实时跟进：vault 有新增/改动 → 增量 ingest + embed。

背景：qkb 的索引原本靠「每 4h 的 rebuild-index + 每日两次摘要」批量更新，
新写的日志/日记最长要等 ~4 小时才可语义检索。本守护兜底：

  1) 门闸：wiki / raw/chat-full / raw/attachments 下有比上次运行更新的 .md 才继续
     （否则 qkb ingest 要全量扫描 5.5k+ 文件、耗时 10 分钟以上，空转不划算）
  2) `qkb ingest`（增量）
  3) 若有 pending → `qkb embed`（默认本机；积压 >BIG 自动切 4090）
  4) 若「大作业」(qkb-bigjob) 正在跑 → 本轮跳过（避免抢锁/误清 prefer-4090 标记）

全部经 `qkb-lock.py` 串行化。由 launchd `com.<user>.qkb-follow`（KeepAlive）常驻。
"""
import os
import re
import subprocess
import sys
import time

QKB = "/opt/homebrew/bin/qkb"
LOCK = os.path.expanduser("~/.config/qkb/qkb-lock.py")
MARK = os.path.expanduser("~/.config/qkb/prefer-4090")
LAST = os.path.expanduser("~/.config/qkb/.follow-last-run")
VAULT = os.path.expanduser("~/数字人生")
WATCH = [os.path.join(VAULT, "wiki"),
         os.path.join(VAULT, "raw", "chat-full"),
         os.path.join(VAULT, "raw", "attachments")]
INTERVAL = int(os.environ.get("FOLLOW_INTERVAL", "300"))
BIG = int(os.environ.get("FOLLOW_BIG", "200"))


def log(s: str):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + s, flush=True)


def bigjob_running() -> bool:
    r = subprocess.run(["pgrep", "-f", "qkb-bigjob"], capture_output=True)
    return r.returncode == 0


def something_new() -> bool:
    """自上次成功运行后，被索引目录里有没有更新的 .md？"""
    if not os.path.exists(LAST):
        return True
    cmd = ["find", *WATCH, "-name", "*.md", "-newer", LAST, "-print", "-quit"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return bool(r.stdout.strip())


def touch_last():
    try:
        open(LAST, "a").close()
    except Exception:
        pass


def proceed() -> list:
    did = []
    subprocess.run(["/usr/bin/python3", LOCK, "ingest"],
                   capture_output=True, text=True, timeout=3600)
    p = subprocess.run([QKB, "status"], capture_output=True, text=True, timeout=300)
    m = re.search(r"\((\d+) pending\)", p.stdout)
    n = int(m.group(1)) if m else 0
    if n:
        created = n >= BIG
        created_by_us = False
        if created and not os.path.exists(MARK):
            open(MARK, "w").close()
            created_by_us = True
        try:
            subprocess.run(["/usr/bin/python3", LOCK, "embed"],
                           capture_output=True, text=True, timeout=14400)
            did.append(f"嵌入 {n} chunk(s){' @4090' if created else ' @本机'}")
        finally:
            if created_by_us and os.path.exists(MARK):
                os.remove(MARK)
    return did


def main() -> int:
    if "--once" in sys.argv:
        did = proceed()
        log("跟进：" + (" | ".join(did) if did else "无变化"))
        return 0
    log(f"follow daemon start (interval={INTERVAL}s, big={BIG})")
    while True:
        try:
            if bigjob_running():
                log("大作业进行中，本轮跳过")
            elif not something_new():
                pass  # 无变化，静默
            else:
                did = proceed()
                touch_last()
                if did:
                    log("跟进：" + " | ".join(did))
        except Exception as e:  # noqa: BLE001
            log(f"error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
