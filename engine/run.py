#!/usr/bin/env python3
"""Task runner with explicit failure propagation and non-semantic execution receipts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "assets" / "scripts"))
from shuzi_runtime import api_key, atomic_json, config_path, file_lock, get, load_config, state_dir, vault_path

ENGINES = ("auto", "openclaw", "claude", "codex", "hermes", "api", "ollama", "manual")


def pick_engine(config):
    # Auto mode never grants an installed framework its broader host toolset.
    # External frameworks must be selected explicitly and sandboxed separately.
    if get(config, "llm.enabled") is True and api_key("llm", config):
        return "api"
    return "manual"


def execute(task, engine, prompt, vault, timeout):
    directory = state_dir() / "runs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_id = uuid.uuid4().hex
    receipt_path = directory / (run_id + ".json")
    log_path = directory / (run_id + ".log")
    receipt = {"run_id": run_id, "task": task, "engine": engine, "vault": str(vault),
               "started_at": datetime.now(timezone.utc).isoformat(), "status": "RUNNING",
               "semantic_verified": False, "log": str(log_path)}
    atomic_json(receipt_path, receipt)
    env = dict(os.environ, SHUZI_PROMPT=prompt, SHUZI_TASK=task,
               SHUZI_VAULT=str(vault), SHUZI_CONFIG=str(config_path()))
    rc = 1
    try:
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as log:
            with subprocess.Popen(["/bin/bash", str(HERE / "engines" / (engine + ".sh"))],
                                  cwd=vault, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  start_new_session=True) as process:
                try:
                    rc = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    rc = 124
                except BaseException:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    rc = 130
        rc = rc if rc >= 0 else 128 - rc
        receipt["status"] = ("NEEDS_USER_ACTION" if engine == "manual" and rc == 3 else
                             "UNSUPPORTED_CAPABILITY" if engine == "ollama" and rc == 4 else
                             "EXECUTED_UNVERIFIED" if rc == 0 else "FAILED")
    except Exception as error:
        receipt.update(status="FAILED", error=type(error).__name__ + ": " + str(error))
        rc = 1
    finally:
        receipt.update(exit_code=rc, ended_at=datetime.now(timezone.utc).isoformat())
        atomic_json(receipt_path, receipt)
    print(f"{receipt['status']} rc={rc} receipt={receipt_path}")
    if rc == 0:
        print("引擎已退出；产物、索引和业务完成状态仍需独立验收。")
    return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--engine", choices=ENGINES, default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=2400)
    args = parser.parse_args()
    if args.list:
        print("\n".join(sorted(p.stem for p in (HERE / "tasks").glob("*.md"))))
        return 0
    if not args.task or not re.fullmatch(r"[a-z][a-z0-9-]*", args.task):
        parser.error("A valid task name is required")
    task = HERE / "tasks" / (args.task + ".md")
    if not task.is_file():
        parser.error("Unknown task: " + args.task)
    if not 1 <= args.timeout <= 14400:
        parser.error("timeout must be between 1 and 14400 seconds")
    config = load_config()
    vault = vault_path(config)
    prompt = task.read_text(encoding="utf-8")
    for token, value in (("{{VAULT}}", str(vault)), ("{{HOME}}", str(Path.home())), ("{{DATE}}", datetime.now().date().isoformat())):
        prompt = prompt.replace(token, value)
    if args.dry_run:
        print(prompt)
        return 0
    if not vault.is_dir():
        parser.error("Vault does not exist; setup must be requested explicitly")
    engine = pick_engine(config) if args.engine == "auto" else args.engine
    identity = hashlib.sha256((str(vault) + ":" + args.task).encode()).hexdigest()[:24]
    try:
        with file_lock(state_dir() / ("task-" + identity + ".lock"), blocking=False):
            return execute(args.task, engine, prompt, vault, args.timeout)
    except BlockingIOError:
        print("BUSY: this task is already running", file=sys.stderr)
        return 75


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + str(error), file=sys.stderr)
        raise SystemExit(1)
