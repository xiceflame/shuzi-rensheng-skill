#!/usr/bin/env python3
"""Content-hash index follower. Checkpoint only after successful ingest/embed/status.

Uses the same code path for --once and the daemon. A snapshot taken BEFORE the
run is committed, so content arriving during indexing is picked up next time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from shuzi_runtime import atomic_json, checked_run, command, file_lock, qkb_dir, vault_path


def snapshot(vault):
    if not vault.is_dir():
        raise FileNotFoundError("Vault does not exist")
    result = {}
    for subtree in ("wiki", "raw/chat-full", "raw/attachments", "raw/chatlogs", "raw/docs-indexed"):
        base = vault / subtree
        if not base.exists():
            continue
        if base.is_symlink():
            raise ValueError("Watched roots must not be symlinks")
        for root, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (Path(root) / d).is_symlink())
            for name in sorted(files):
                path = Path(root) / name
                if not name.endswith(".md") or ".sync-conflict-" in name or path.is_symlink():
                    continue
                result[str(path.relative_to(vault))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def pending(qkb, run=checked_run):
    output = run([qkb, "status"], timeout=300).stdout
    match = re.search(r"\((\d+) pending\)", output)
    if not match:
        raise ValueError("Unrecognized qkb status; refusing to mark indexing complete")
    return int(match.group(1))


def follow_once(run=checked_run):
    vault = vault_path()
    directory = qkb_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    qkb = command("qkb", "QKB_BIN")
    state = directory / "follow-state-v2.json"
    identity = {"vault": str(vault), "qkb": qkb}
    # Include the index configuration so changing the model/vault forces ingest.
    config = directory / "config.toml"
    identity["config_sha256"] = hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else ""
    with file_lock(directory / ".follow.lock", blocking=False):
        start = snapshot(vault)
        previous = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
        if previous.get("identity") == identity and previous.get("files") == start:
            # Pending chunks may also be created by other authorized producers.
            if pending(qkb, run) == 0:
                return "NO_CHANGE"
        lock = Path(__file__).with_name("qkb-lock.py")
        run([sys.executable, str(lock), "ingest"], timeout=3600)
        count = pending(qkb, run)
        if count:
            run([sys.executable, str(lock), "embed"], timeout=14400)
        if pending(qkb, run) != 0:
            raise RuntimeError("Embedding still pending; checkpoint not advanced")
        atomic_json(state, {"version": 2, "identity": identity, "files": start, "completed_at": time.time()})
        return "INDEXED"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    interval = int(os.environ.get("FOLLOW_INTERVAL", "300"))
    if interval < 1:
        parser.error("FOLLOW_INTERVAL must be positive")
    while True:
        try:
            status = follow_once()
            if status != "NO_CHANGE":
                print(status, flush=True)
        except BlockingIOError:
            if args.once:
                return 75
        except Exception as error:
            print("[ERR] " + str(error), file=sys.stderr, flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
