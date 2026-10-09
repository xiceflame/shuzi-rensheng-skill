#!/usr/bin/env python3
"""Check the live scheduling consent switch before dispatching a registered job."""
import os
from pathlib import Path
import subprocess
import sys

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "assets" / "scripts"))
from shuzi_runtime import get, load_config, vault_path


def main():
    if len(sys.argv) != 2:
        return 2
    config = load_config()
    if get(config, "schedule.enabled") is not True:
        print("DISABLED: schedule.enabled is not true")
        return 0
    task = sys.argv[1]
    env = dict(os.environ, SHUZI_VAULT=str(vault_path(config)), SHUZI_PYTHON=sys.executable)
    if task in ("chat-ingest", "finance-ingest", "lint", "idea-review", "rollup"):
        # Pin the backend; do not choose a newly installed tool or vendor silently.
        engine = get(config, "schedule.engine", "api")
        if engine in ("auto", "manual", "ollama"):
            raise ValueError("Unattended jobs require an explicitly supported engine, not auto/manual/ollama")
        args = [sys.executable, str(PKG / "engine/run.py"), task, "--engine", engine]
    elif task == "qkb-follow":
        args = [sys.executable, str(PKG / "assets/scripts/qkb-follow.py"), "--once"]
    elif task in ("rebuild", "transcribe"):
        args = ["/bin/bash", str(PKG / "engine/scripts-extra.sh"), task]
    elif task == "collector-refresh" and sys.platform == "darwin":
        relay = Path.home() / ".wxexport/relay.command"
        if not relay.is_file():
            raise FileNotFoundError("Configure the collector relay explicitly before scheduling")
        args = ["/usr/bin/open", str(relay)]
    else:
        raise ValueError("Unknown or unsupported scheduled task: " + task)
    rc = subprocess.call(args, env=env, cwd=vault_path(config))
    return rc if rc >= 0 else 128 - rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + str(error), file=sys.stderr)
        raise SystemExit(1)
