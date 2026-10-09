#!/usr/bin/env python3
"""WX plaintext snapshot -> legacy-compatible monthly Markdown + normalized JSONL.

Explicit --policy selects conversation IDs, time range and types. Without it,
focus.txt retains its existing name-based behavior. This is an export selector,
NOT a query ACL: existing files/index entries are not deleted on scope changes.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import uuid

NS = uuid.uuid5(uuid.NAMESPACE_URL, "shuzi-rensheng/wechat-evidence/v1")
MSG_TYPES = {1: "文本", 3: "图片", 34: "语音", 43: "视频", 47: "表情", 48: "位置", 49: "链接/文件", 50: "通话", 10000: "系统"}


def safe(value):
    return re.sub(r'[/\\:*?"<>|\s]', "_", value or "")[:50].strip(" .") or "unknown"


def atomic(path, data):
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


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def page_id(account, conversation, month, existing=None):
    if existing and existing.exists():
        header = existing.read_text(encoding="utf-8").split("\n---", 1)[0]
        for field, expected in (("account_id", account), ("conversation_id", conversation)):
            metadata = re.search(r"^" + field + r":\s*(.+)$", header, re.M)
            if metadata:
                value = metadata.group(1).strip()
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value.strip("\"'")
                if value != expected:
                    raise ValueError("EXISTING_PAGE_IDENTITY_MISMATCH")
        found = re.search(r"^id:\s*(\S+)", header, re.M)
        if found:
            return str(uuid.UUID(found.group(1).strip('"\'')))
    return str(uuid.uuid5(NS, json.dumps([account, conversation, month], ensure_ascii=False)))


def message_id(account, conversation, database, table, local_id, server_id=None):
    parts = [account, conversation, "server", str(server_id)] if server_id not in (None, 0, "0", "") else [account, conversation, "local", database, table, str(local_id)]
    return str(uuid.uuid5(NS, json.dumps(parts, ensure_ascii=False)))


def decode_content(value):
    if value is None:
        return "", "missing"
    data = value.encode() if isinstance(value, str) else bytes(value)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("CONTENT_TOO_LARGE")
    if data.startswith(b"\x28\xb5\x2f\xfd"):
        import zstandard
        data = zstandard.ZstdDecompressor().decompress(data, max_output_size=8 * 1024 * 1024)
    return data.decode("utf-8"), "available"


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Policy dates must specify timezone")
    return int(result.timestamp())


def export(work, targets, account, start, end, types=None, routes=None):
    out, source = work / "searchable", work / "decrypted"
    buckets, events, errors = defaultdict(list), {}, []
    names = json.loads((work / "namemap.json").read_text(encoding="utf-8"))["names"]
    routes = routes or {}
    # Keep legacy paths, but never silently merge two same-name conversations.
    filenames = [safe(name) for name in targets.values()]
    if len(filenames) != len(set(filenames)):
        raise ValueError("CONVERSATION_NAME_COLLISION: assign distinct export names in policy")
    by_md5 = {hashlib.md5(uid.encode()).hexdigest(): uid for uid in targets}
    recovery_file = source / "recovery-manifest.json"
    verified = None
    if recovery_file.exists():
        recovery = json.loads(recovery_file.read_text())
        if recovery.get("status") != "READY":
            raise ValueError("Recovery is incomplete; consult recovery-manifest.json")
        verified = {row["path"]: row for row in recovery["databases"] if row["status"] == "READY"}
    databases = sorted(source.glob("message/message_[0-9]*.db"))
    actual = {path.relative_to(source).as_posix() for path in databases}
    if verified is not None:
        for rel in set(verified) - actual:
            if re.fullmatch(r"message/message_[0-9]+\.db", rel):
                errors.append({"database": rel, "error": "MISSING_VERIFIED_SHARD"})
    if not databases:
        errors.append({"error": "NO_MESSAGE_DATABASES"})
    seen = set()
    for database in databases:
        rel = database.relative_to(source).as_posix()
        con = None
        try:
            if database.is_symlink() or source.resolve() not in database.resolve().parents:
                raise ValueError("UNSAFE_SOURCE")
            wal = Path(str(database) + "-wal")
            if wal.exists() and wal.stat().st_size:
                raise ValueError("WAL_PRESENT")
            fingerprint = hash_bytes(database.read_bytes())
            if verified is not None and (rel not in verified or verified[rel]["plaintext_sha256"] != fingerprint):
                raise ValueError("RECOVERY_HASH_MISMATCH")
            con = sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
            con.execute("PRAGMA trusted_schema=OFF")
            if con.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("SQLITE_INTEGRITY_FAILED")
            senders = dict(con.execute("SELECT rowid,user_name FROM Name2Id"))
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
            for table in tables:
                uid = by_md5.get(table[4:])
                if uid is None:
                    continue
                seen.add(uid)
                if not re.fullmatch(r"Msg_[0-9a-fA-F]{32}", table):
                    raise ValueError("UNSUPPORTED_TABLE")
                columns = {r[1] for r in con.execute('PRAGMA table_info("' + table + '")')}
                if not {"create_time", "real_sender_id", "local_type", "message_content"} <= columns:
                    errors.append({"database": rel, "table": table, "error": "SCHEMA_UNSUPPORTED"}); continue
                local_col = '"local_id"' if "local_id" in columns else "rowid"
                server_col = '"server_id"' if "server_id" in columns else "NULL"
                sql = 'SELECT create_time,real_sender_id,local_type,message_content,' + local_col + ',' + server_col + ' FROM "' + table + '" WHERE create_time>=? AND create_time<? ORDER BY create_time,' + local_col
                for ct, sender_no, local_type, content, local, server in con.execute(sql, (start, end)):
                    try:
                        typ = int(local_type or 0) & 0xFFFFFFFF
                        if types is not None and typ not in types:
                            continue
                        text, content_state = decode_content(content)
                        sender = senders.get(sender_no)
                        if typ == 1:
                            prefix = re.match(r"^([0-9A-Za-z_\-@.]+):\n", text)
                            if prefix:
                                sender = sender or prefix.group(1)
                                text = text[prefix.end():]
                        mid = message_id(account, uid, rel, table, local, server)
                        revision = hash_bytes(json.dumps([int(ct), sender, typ, text], ensure_ascii=False).encode())
                        event = {"schema_version": 1, "account_id": account, "conversation_id": uid, "message_id": mid,
                                 "timestamp": int(ct), "event_time": datetime.fromtimestamp(int(ct), timezone.utc).isoformat(),
                                 "sender_id": sender, "message_type": typ, "content": text,
                                 "content_state": content_state, "content_revision": revision,
                                 "id_scope": "server" if server not in (None, 0, "0", "") else "shard-local" if "local_id" in columns else "snapshot-rowid",
                                 "epistemic_status": "source_evidence", "media_state": "not_applicable" if typ == 1 else "pending_derivative",
                                 "source": {"database": rel, "table": table, "local_id": str(local), "server_id": server},
                                 "category": routes.get(uid, {}).get("category", "待分类"), "project": routes.get(uid, {}).get("project", "")}
                        if mid in events:
                            if events[mid]["content_revision"] != revision:
                                raise ValueError("DUPLICATE_ID_CONFLICT")
                            events[mid].setdefault("additional_sources", []).append(event["source"])
                            continue
                        events[mid] = event
                        who = names.get(sender, sender) if sender else "（发送者未标注）"
                        body = text if typ == 1 else "[" + MSG_TYPES.get(typ, "类型%d" % typ) + "；待派生处理]"
                        month = datetime.fromtimestamp(int(ct)).strftime("%Y-%m")
                        buckets[uid, month].append((int(ct), who, body, mid))
                    except Exception as error:
                        errors.append({"database": rel, "table": table, "local_id": str(local),
                                       "error": str(error) if isinstance(error, ValueError) and str(error) in ("DUPLICATE_ID_CONFLICT", "CONTENT_TOO_LARGE") else type(error).__name__})
            if hash_bytes(database.read_bytes()) != fingerprint:
                raise ValueError("SNAPSHOT_CHANGED")
        except Exception as error:
            errors.append({"database": rel, "error": str(error) if isinstance(error, ValueError) else type(error).__name__})
        finally:
            if con is not None:
                con.close()
    for uid in sorted(set(targets) - seen):
        errors.append({"conversation_id": uid, "error": "CONVERSATION_NOT_FOUND"})
    report = {"schema_version": 1, "status": "PARTIAL" if errors else "EXPORTED", "messages": len(events),
              "recovery_verified": verified is not None, "errors": errors, "pages": [], "unlinked_asr": 0,
              "scope": {"account_id": account, "conversations": sorted(targets), "start_inclusive": start, "end_exclusive": end}}
    if errors:
        atomic(out / "_export-report.json", json.dumps(report, ensure_ascii=False, indent=2).encode())
        return report
    # Preserve legacy transcripts, but keep their unverified association explicit.
    name_to_id = {name: uid for uid, name in targets.items()}
    for vf in sorted((work / "focus-voice-text").glob("*.txt")):
        uid = name_to_id.get(vf.stem)
        if uid is None or (types is not None and 34 not in types):
            continue
        for lineno, line in enumerate(vf.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*([^:]*):\s*(.*)", line)
            if not match:
                continue
            ts = int(datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").timestamp())
            if not start <= ts < end:
                continue
            aid = str(uuid.uuid5(NS, json.dumps([account, uid, "unlinked-asr", vf.name, lineno, line], ensure_ascii=False)))
            buckets[uid, match.group(1)[:7]].append((ts, match.group(2).strip() or "（发送者未标注）", "[语音转写·未按消息ID关联] " + match.group(3), aid))
            report["unlinked_asr"] += 1
    rendered = []
    registry_path = out / "_page-map.json"
    page_map = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    for (uid, month), items in sorted(buckets.items()):
        stable_key = str(uuid.uuid5(NS, json.dumps([account, uid, month], ensure_ascii=False)))
        relative = page_map.get(stable_key, safe(targets[uid]) + "/" + month + ".md")
        rel_path = Path(relative)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError("INVALID_PAGE_REGISTRY_PATH")
        path = out / rel_path
        if out.resolve() not in path.resolve().parents:
            raise ValueError("INVALID_PAGE_REGISTRY_PATH")
        page_map[stable_key] = rel_path.as_posix()
        for _, _, _, mid in items:
            if mid in events:
                events[mid]["evidence_ref"] = "raw/chatlogs/" + rel_path.as_posix() + "#^m-" + mid
        props = {"id": page_id(account, uid, month, path), "context": targets[uid], "created": month + "-01",
                 "tags": ["聊天记录"], "source_schema": "wx-evidence-v1", "account_id": account, "conversation_id": uid,
                 "category": routes.get(uid, {}).get("category", "待分类"), "project": routes.get(uid, {}).get("project", "")}
        lines = ["---", *[k + ": " + json.dumps(v, ensure_ascii=False) for k, v in props.items()], "---", "",
                 "# " + targets[uid].replace("\n", " ") + " · " + month, ""]
        for ts, who, body, mid in sorted(items, key=lambda item: (item[0], item[3])):
            lines.extend(["[%s] %s: %s" % (datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), who, body), "^m-" + mid, ""])
        data = "\n".join(lines).encode()
        rendered.append((path, data))
        report["pages"].append({"path": path.relative_to(out).as_posix(), "id": props["id"], "sha256": hash_bytes(data)})
    payload = b"".join(json.dumps(e, ensure_ascii=False, sort_keys=True).encode() + b"\n" for e in sorted(events.values(), key=lambda e: (e["timestamp"], e["message_id"])))
    report["events_sha256"] = hash_bytes(payload)
    for path, data in rendered:
        if not path.exists() or path.read_bytes() != data:
            atomic(path, data)
    atomic(out / "_events.jsonl", payload)
    atomic(registry_path, json.dumps(page_map, ensure_ascii=False, sort_keys=True, indent=2).encode())
    atomic(out / "_export-report.json", json.dumps(report, ensure_ascii=False, indent=2).encode())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="?", type=int, default=3)
    parser.add_argument("--work", type=Path, default=Path(os.environ.get("WX_EXPORT_WORK", "~/wx-export")).expanduser())
    parser.add_argument("--policy", type=Path, default=os.environ.get("WX_EXPORT_POLICY"))
    parser.add_argument("--account-id", default=os.environ.get("WX_ACCOUNT_ID"))
    args = parser.parse_args(argv)
    if args.years < 1:
        parser.error("years must be positive")
    work = args.work.expanduser()
    nm = json.loads((work / "namemap.json").read_text(encoding="utf-8"))
    if args.policy:
        policy = json.loads(args.policy.expanduser().read_text(encoding="utf-8"))
        if policy.get("schema_version") != 1 or not isinstance(policy.get("conversations"), dict) or not policy["conversations"]:
            parser.error("Policy requires schema_version=1 and exact conversation-ID rules")
        account = args.account_id or policy.get("account_id")
        if not isinstance(account, str) or not account:
            parser.error("A stable account_id is required for controlled exports")
        start, end = timestamp(policy["date_from"]), timestamp(policy["date_to"])
        if start >= end:
            parser.error("date_from must precede date_to")
        routes = policy["conversations"]
        targets = {uid: rule.get("name", nm["names"].get(uid, uid)) for uid, rule in routes.items()}
        types = policy.get("message_types")
        if types is not None and (not isinstance(types, list) or any(type(t) is not int for t in types)):
            parser.error("message_types must be an integer list")
    else:
        from focus_match import matcher
        focus = matcher()
        targets = {uid: nm["names"].get(uid, uid) for uid in set(nm["md5map"].values()) if uid and focus(nm["names"].get(uid, uid))}
        account = args.account_id or "legacy-" + hash_bytes(str(work.resolve()).encode())[:16]
        start = int((datetime.now() - timedelta(days=365 * args.years)).timestamp())
        end, types, routes = int(datetime.now().timestamp()) + 1, None, {}
    report = export(work, targets, account, start, end, types, routes)
    print(json.dumps({"status": report["status"], "messages": report["messages"], "unlinked_asr": report["unlinked_asr"], "errors": report["errors"]}, ensure_ascii=False))
    return 0 if report["status"] == "EXPORTED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
