"""Recover an explicitly selected local account snapshot using its existing keys.

Capture/key acquisition remains in the existing collector. This stage authenticates
cipher pages, checks SQLite integrity and publishes a key-free coverage manifest.
It is not a WAL decryptor and never operates on the original database in-place.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from . import detect
from .crypto import decrypt_db


def _signature(path):
    stat = path.stat()
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".wx-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(data_dir, keys_path, out_dir):
    root, output = Path(data_dir).resolve(), Path(out_dir).resolve()
    if output == root or root in output.parents or output in root.parents:
        raise ValueError("SNAPSHOT_AND_OUTPUT_MUST_BE_SEPARATE")
    # Invalidate an earlier READY report before doing work, even if validation
    # later aborts. Never let a failed new attempt masquerade as fresh recovery.
    _atomic(output / "recovery-manifest.json", b'{"schema_version":1,"status":"RUNNING"}\n')
    with open(keys_path, encoding="utf-8") as stream:
        keys = json.load(stream)
    if not isinstance(keys, dict):
        raise ValueError("INVALID_KEY_MANIFEST")
    # Relpaths alone cannot distinguish two logged-in accounts. Fail instead of
    # overwriting one account's message_0 with another account's message_0.
    accounts = list(root.glob("*/db_storage"))
    if len(accounts) != 1:
        raise ValueError("SELECT_ONE_ACCOUNT_SNAPSHOT: expected one */db_storage")
    records = []
    for source in sorted(accounts[0].rglob("*.db")):
        rel = source.relative_to(accounts[0]).as_posix()
        record = {"path": rel, "status": "PENDING"}
        temporary = None
        try:
            if source.is_symlink() or root not in source.resolve().parents:
                raise ValueError("UNSAFE_SOURCE_PATH")
            wal = Path(str(source) + "-wal")
            if wal.exists() and wal.stat().st_size:
                raise ValueError("WAL_PRESENT: require a coherent checkpointed snapshot; WAL recovery is not implemented")
            before = _signature(source)
            data = source.read_bytes()
            if before != _signature(source):
                raise ValueError("SNAPSHOT_CHANGED_DURING_READ")
            if len(data) < 16:
                raise ValueError("TRUNCATED_DATABASE")
            if data.startswith(b"SQLite format 3\x00"):
                plain = data
                record["input_kind"] = "plaintext"
            else:
                if rel not in keys:
                    raise ValueError("KEY_MISSING")
                info = keys[rel]
                key = bytes.fromhex(info["enc_key"])
                plain = decrypt_db(data, key, info.get("reserve", 80))
                record["input_kind"] = "encrypted"
            target = output / rel
            if output not in target.resolve().parents:
                raise ValueError("UNSAFE_OUTPUT_PATH")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temporary = tempfile.mkstemp(prefix=".wx-validate-", dir=target.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(plain)
                stream.flush()
                os.fsync(stream.fileno())
            con = sqlite3.connect(Path(temporary).as_uri() + "?mode=ro&immutable=1", uri=True)
            try:
                con.execute("PRAGMA trusted_schema=OFF")
                if con.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("SQLITE_INTEGRITY_FAILED")
                tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            finally:
                con.close()
            os.replace(temporary, target)
            temporary = None
            record.update(status="READY", cipher_sha256=hashlib.sha256(data).hexdigest(),
                          plaintext_sha256=hashlib.sha256(plain).hexdigest(),
                          bytes=len(plain), table_count=len(tables))
        except Exception as error:
            # Never log key material, content, or provider exception strings.
            code = str(error).split(":", 1)[0] if isinstance(error, ValueError) else type(error).__name__
            allowed = {"WAL_PRESENT", "KEY_MISSING", "SNAPSHOT_CHANGED_DURING_READ", "UNSAFE_SOURCE_PATH",
                       "UNSAFE_OUTPUT_PATH", "SQLITE_INTEGRITY_FAILED", "PAGE_AUTH_FAILED",
                       "TRUNCATED_DATABASE", "UNSUPPORTED_CIPHER_PROFILE"}
            record.update(status=code if code in allowed else "RECOVERY_FAILED")
            print("  FAIL %s: %s" % (rel, record["status"]))
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        records.append(record)
    ok = sum(row["status"] == "READY" for row in records)
    fail = len(records) - ok
    if not records:
        fail = 1
    manifest = {"schema_version": 1, "cipher_profile": "wcdb4-rawkey-4096-80",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "READY" if ok and not fail else "PARTIAL" if ok else "FAILED",
                "discovered": len(records), "ready": ok, "failed": fail, "databases": records}
    _atomic(output / "recovery-manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    return ok, fail
