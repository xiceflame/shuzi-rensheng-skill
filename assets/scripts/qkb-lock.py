#!/usr/bin/env python3
"""Serialize QKB writes with a shared lock; command location is configurable."""
import subprocess
import sys
from shuzi_runtime import command, file_lock, qkb_dir


def main():
    if len(sys.argv) < 2:
        print("usage: qkb-lock.py <qkb-args...>", file=sys.stderr)
        return 2
    qkb = command("qkb", "QKB_BIN")
    with file_lock(qkb_dir() / ".qkb-write.lock"):
        rc = subprocess.call([qkb, *sys.argv[1:]])
        return rc if rc >= 0 else 128 - rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + str(error), file=sys.stderr)
        raise SystemExit(1)
