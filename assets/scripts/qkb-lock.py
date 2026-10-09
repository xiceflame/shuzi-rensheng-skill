#!/usr/bin/env python3
"""串行化 qkb 的写操作 —— 防止并发抢插导致的 UNIQUE 报错。

背景（2026-09-11 实测）：
    qkb 自身没有加锁。若 `rebuild-index` 自动化里的 `qkb embed`
    与另一次 `qkb embed` 同时运行，两者会各自算出同一批 pending chunks
    （pendingChunks() = chunks 里没有向量的），然后抢插同一批 chunk_id，
    后到的那个报：
        Error: UNIQUE constraint failed on chunks_vec primary key

本包装器用 fcntl 排他锁把 qkb 的调用串行化：
    - 锁随进程退出自动释放 → 不会留下残留锁文件
    - 后到的进程会**阻塞等待**，而不是报错退出
    - 读操作（query/search/status）走这里也无害

用法：
    python3 ~/.config/qkb/qkb-lock.py ingest
    python3 ~/.config/qkb/qkb-lock.py embed
    python3 ~/.config/qkb/qkb-lock.py query "问题"

（等价于直接跑 `qkb <args>`，只是加了串行化。）
"""
import fcntl
import os
import subprocess
import sys

QKB = "/opt/homebrew/bin/qkb"
LOCK = os.path.expanduser("~/.config/qkb/.qkb-write.lock")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: qkb-lock.py <qkb-args...>", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)  # 阻塞直到拿到锁；退出即释放
        return subprocess.call([QKB, *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
