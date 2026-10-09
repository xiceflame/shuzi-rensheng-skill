#!/usr/bin/env python3
"""Report sync conflicts; optionally archive verified snapshots. NEVER delete or elect a winner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from shuzi_runtime import atomic_json, state_dir, vault_path

PAT = re.compile(r"^(?P<base>.+?)\.sync-conflict-\d{8}-\d{6}-[A-Za-z0-9]+(?P<ext>\.[^.]+)?$")


def conflicts(vault):
    for root, dirs, files in os.walk(vault, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in (".stversions", ".git") and not (Path(root) / d).is_symlink())
        for name in sorted(files):
            match = PAT.match(name)
            if not match:
                continue
            conflict = Path(root) / name
            canonical = Path(root) / (match.group("base") + (match.group("ext") or ""))
            if conflict.is_symlink() or canonical.is_symlink():
                continue
            yield [p for p in (canonical, conflict) if p.is_file()]


def copy_verified(source, target):
    data = source.read_bytes()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    digest = hashlib.sha256(data).hexdigest()
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise OSError("Archive verification failed")
    return digest


def archive_group(paths, vault, archive):
    archive = archive.resolve()
    if archive == vault or vault in archive.parents:
        raise ValueError("Archive must be outside the vault")
    destination = archive / uuid.uuid4().hex
    destination.mkdir(parents=True, mode=0o700)
    records = []
    for number, source in enumerate(paths):
        target = destination / (str(number) + ".snapshot")
        sha = copy_verified(source, target)
        records.append({"source": str(source.relative_to(vault)), "snapshot": target.name, "sha256": sha})
    atomic_json(destination / "manifest.json", {"state": "ARCHIVED_UNRESOLVED", "files": records})
    # Even after successful verification, originals are deliberately untouched.
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="store_true", help="Copy verified snapshots; keep all source versions")
    parser.add_argument("--archive-dir", type=Path)
    args = parser.parse_args()
    vault = vault_path()
    if not vault.is_dir():
        raise FileNotFoundError("Vault does not exist")
    groups = list(conflicts(vault))
    failures = 0
    for paths in groups:
        print(json.dumps({"state": "CONFLICT_NEEDS_REVIEW", "files": [str(p.relative_to(vault)) for p in paths]}, ensure_ascii=False))
        if args.archive:
            try:
                archive_group(paths, vault, args.archive_dir or state_dir() / "conflict-archive")
            except Exception as error:
                failures += 1
                print("[ERR] Archive failed; all source versions retained: " + str(error), file=sys.stderr)
    return 1 if failures else (2 if groups else 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + str(error), file=sys.stderr)
        raise SystemExit(1)
