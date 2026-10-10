#!/usr/bin/env python3
"""Stable, privacy-preserving installation identity for shuzi-rensheng."""
from __future__ import annotations
import argparse, json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_PATH = Path.home() / ".config" / "shuzi-rensheng" / "instance.json"

def instance_path() -> Path:
    return Path(os.environ.get("SHUZI_INSTANCE_FILE", str(DEFAULT_PATH))).expanduser()

def load_or_create(reset: bool = False) -> dict[str, Any]:
    path = instance_path()
    if not reset and path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("instance_id"), str):
                return value
        except (OSError, ValueError):
            pass
    value = {"schema_version": SCHEMA_VERSION, "instance_id": "sr_" + uuid.uuid4().hex,
             "created_at": datetime.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try: path.chmod(0o600)
    except OSError: pass
    return value

def main() -> int:
    parser = argparse.ArgumentParser(description="Show or reset the local shuzi-rensheng installation identity.")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    value = load_or_create(args.reset)
    print(json.dumps(value, ensure_ascii=False) if args.json else value["instance_id"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
