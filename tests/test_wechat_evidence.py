"""Synthetic local fixtures only; never attach to a real client or read user data."""
import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "assets/scripts/collector"
sys.path.insert(0, str(COLLECTOR))
from wxexport import crypto, decrypt
from wxexport import __main__ as cli
import export_searchable as exporter
from Crypto.Cipher import AES


class CryptoTests(unittest.TestCase):
    def cipher(self):
        key, salt, iv = bytes(range(32)), bytes(range(16)), bytes(range(16, 32))
        mk = crypto.mac_key(key, salt)
        chunks = []
        for number in (1, 2):
            plain = b"a" * (4000 if number == 1 else 4016)
            ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(plain)
            tag = hmac.new(mk, ciphertext + iv + struct.pack("<I", number), hashlib.sha512).digest()
            chunks.append((salt if number == 1 else b"") + ciphertext + iv + tag)
        return key, b"".join(chunks)

    def test_authenticated_pages(self):
        key, data = self.cipher()
        plain = crypto.decrypt_db(data, key)
        self.assertEqual(len(plain), 8192)
        self.assertEqual(plain[:16], b"SQLite format 3\x00")
        self.assertEqual(plain[16:4016], b"a" * 4000)

    def test_wrong_key(self):
        key, data = self.cipher()
        with self.assertRaisesRegex(ValueError, "PAGE_AUTH_FAILED"):
            crypto.decrypt_db(data, bytes(reversed(key)))

    def test_later_page_tamper(self):
        key, data = self.cipher()
        damaged = bytearray(data); damaged[5000] ^= 1
        with self.assertRaisesRegex(ValueError, "page 2"):
            crypto.decrypt_db(bytes(damaged), key)

    def test_partial_page_rejected(self):
        key, data = self.cipher()
        with self.assertRaisesRegex(ValueError, "TRUNCATED_DATABASE"):
            crypto.decrypt_db(data[:-1], key)

    def test_unsupported_profile(self):
        key, data = self.cipher()
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_CIPHER_PROFILE"):
            crypto.decrypt_db(data, key, 48)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="wx-fixture-")
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.source = self.home / "snapshot"
        self.dbdir = self.source / "account-fixture/db_storage/message"
        self.dbdir.mkdir(parents=True)
        self.output = self.home / "decrypted"
        self.keys = self.home / "synthetic-keys.json"
        self.keys.write_text("{}")

    def run_recovery(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = decrypt.run(str(self.source), str(self.keys), str(self.output))
        manifest = json.loads((self.output / "recovery-manifest.json").read_text())
        return result, manifest

    def plaintext(self):
        path = self.dbdir / "message_0.db"
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE example(value TEXT)")
        con.execute("INSERT INTO example VALUES ('fixture')")
        con.commit(); con.close()
        return path

    def test_plaintext_snapshot_validated(self):
        path = self.plaintext()
        result, manifest = self.run_recovery()
        self.assertEqual(result, (1, 0))
        self.assertEqual(manifest["status"], "READY")
        self.assertEqual((self.output / "message/message_0.db").read_bytes(), path.read_bytes())

    def test_missing_key_is_counted(self):
        (self.dbdir / "message_0.db").write_bytes(b"x" * 4096)
        result, manifest = self.run_recovery()
        self.assertEqual(result, (0, 1))
        self.assertEqual(manifest["databases"][0]["status"], "KEY_MISSING")

    def test_partial_coverage(self):
        self.plaintext()
        (self.dbdir / "message_1.db").write_bytes(b"x" * 4096)
        result, manifest = self.run_recovery()
        self.assertEqual(result, (1, 1))
        self.assertEqual(manifest["status"], "PARTIAL")

    def test_truncated_file_not_ignored(self):
        (self.dbdir / "message_0.db").write_bytes(b"x")
        result, manifest = self.run_recovery()
        self.assertEqual(result, (0, 1))
        self.assertEqual(manifest["databases"][0]["status"], "TRUNCATED_DATABASE")

    def test_wal_not_silently_dropped(self):
        path = self.plaintext()
        Path(str(path) + "-wal").write_bytes(b"unhandled fixture WAL")
        result, manifest = self.run_recovery()
        self.assertEqual(manifest["databases"][0]["status"], "WAL_PRESENT")
        self.assertEqual(result, (0, 1))

    def test_failure_preserves_previous_plaintext(self):
        path = self.plaintext()
        self.run_recovery()
        previous = (self.output / "message/message_0.db").read_bytes()
        path.write_bytes(b"damaged")
        self.run_recovery()
        self.assertEqual((self.output / "message/message_0.db").read_bytes(), previous)

    def test_multiple_accounts_rejected(self):
        (self.source / "another/db_storage").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "SELECT_ONE_ACCOUNT"):
            self.run_recovery()

    def test_no_databases_not_ready(self):
        result, manifest = self.run_recovery()
        self.assertEqual(result, (0, 1))
        self.assertEqual(manifest["status"], "FAILED")

    def test_invalid_keys_invalidate_previous_ready(self):
        self.plaintext(); self.run_recovery()
        self.keys.write_text("broken")
        with self.assertRaises(ValueError):
            self.run_recovery()
        self.assertNotEqual(json.loads((self.output / "recovery-manifest.json").read_text())["status"], "READY")

    def test_cli_failure_propagates(self):
        args = type("Args", (), {"work": str(self.home), "data_dir": str(self.source)})()
        with patch.object(cli.decrypt, "run", return_value=(1, 1)), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                cli.cmd_decrypt(args)
        self.assertEqual(error.exception.code, 1)


class ExportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="wx-export-fixture-")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.cid = "wxid_project_fixture"
        self.table = "Msg_" + hashlib.md5(self.cid.encode()).hexdigest()
        self.db = self.work / "decrypted/message/message_0.db"
        self.db.parent.mkdir(parents=True)
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE Name2Id(user_name TEXT)")
        con.execute("INSERT INTO Name2Id VALUES ('wxid_sender_fixture')")
        con.execute('CREATE TABLE "' + self.table + '"(local_id INTEGER,server_id INTEGER,create_time INTEGER,real_sender_id INTEGER,local_type INTEGER,message_content BLOB)')
        con.executemany('INSERT INTO "' + self.table + '" VALUES (?,?,?,?,?,?)', [
            (1,101,1700000000,1,1,"first quotation"),
            (2,102,1700000000,99,1,"second quotation"),
            (3,103,1700000010,1,34,"voice payload")])
        con.commit(); con.close()
        (self.work / "namemap.json").write_text(json.dumps({"names": {self.cid: "项目群", "wxid_sender_fixture": "成员甲"}, "md5map": {self.table[4:]: self.cid}}))
        self.targets = {self.cid: "项目群"}

    def export(self, **overrides):
        params = dict(work=self.work, targets=self.targets, account="account-a", start=1699999990, end=1700000020)
        params.update(overrides)
        return exporter.export(**params)

    def events(self):
        return [json.loads(line) for line in (self.work / "searchable/_events.jsonl").read_text().splitlines()]

    def test_stable_ids_and_bytes_on_repeat(self):
        first = self.export()
        original = (self.work / "searchable/_events.jsonl").read_bytes()
        second = self.export()
        self.assertEqual(first, second)
        self.assertEqual((self.work / "searchable/_events.jsonl").read_bytes(), original)

    def test_same_second_distinct_messages(self):
        self.export(); events = self.events()
        self.assertNotEqual(events[0]["message_id"], events[1]["message_id"])
        self.assertEqual(len(events), 3)

    def test_unknown_sender_not_guessed(self):
        self.export()
        event = next(e for e in self.events() if e["content"] == "second quotation")
        self.assertIsNone(event["sender_id"])

    def test_time_half_open_and_type_filters(self):
        self.export(start=1700000000, end=1700000010, types=[1])
        self.assertEqual(len(self.events()), 2)

    def test_name_change_keeps_message_identity(self):
        first = self.export()
        mids = [e["message_id"] for e in self.events()]
        refs = [e["evidence_ref"] for e in self.events()]
        second = self.export(targets={self.cid: "新名字"})
        self.assertEqual(mids, [e["message_id"] for e in self.events()])
        self.assertEqual(refs, [e["evidence_ref"] for e in self.events()])
        self.assertEqual(first["pages"][0]["path"], second["pages"][0]["path"])
        self.assertEqual(len(list((self.work / "searchable").glob("**/*.md"))), 1)

    def test_account_identity_separated(self):
        self.assertNotEqual(exporter.message_id("a", self.cid, "db", "table", 1, 100), exporter.message_id("b", self.cid, "db", "table", 1, 100))

    def test_metadata_routes(self):
        self.export(routes={self.cid: {"category": "work", "project": "project-a"}})
        self.assertEqual(self.events()[0]["project"], "project-a")
        self.assertEqual(self.events()[0]["epistemic_status"], "source_evidence")

    def test_decode_failure_does_not_replace_previous(self):
        self.export(); old = (self.work / "searchable/_events.jsonl").read_bytes()
        con = sqlite3.connect(self.db)
        con.execute('UPDATE "' + self.table + '" SET message_content=? WHERE local_id=1', (b"\xff",))
        con.commit(); con.close()
        self.assertEqual(self.export()["status"], "PARTIAL")
        self.assertEqual((self.work / "searchable/_events.jsonl").read_bytes(), old)

    def test_schema_mismatch_visible(self):
        con = sqlite3.connect(self.db)
        con.execute('ALTER TABLE "' + self.table + '" RENAME COLUMN message_content TO unsupported_payload')
        con.commit(); con.close()
        report = self.export()
        self.assertEqual(report["errors"][0]["error"], "SCHEMA_UNSUPPORTED")

    def test_name_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "NAME_COLLISION"):
            self.export(targets={self.cid: "same", "other": "same"})

    def test_legacy_id_preserved(self):
        report = self.export()
        path = self.work / "searchable" / report["pages"][0]["path"]
        self.assertEqual(exporter.page_id("account-a", self.cid, "month", path), report["pages"][0]["id"])

    def test_no_content_does_not_invent_text(self):
        self.assertEqual(exporter.decode_content(None), ("", "missing"))

    def test_media_not_treated_as_transcribed(self):
        self.export()
        voice = next(e for e in self.events() if e["message_type"] == 34)
        self.assertEqual(voice["media_state"], "pending_derivative")

    def test_unsafe_directory_name_sanitized(self):
        self.assertEqual(exporter.safe(".."), "unknown")
        self.assertNotIn("/", exporter.safe("a/b"))

    def test_policy_timezone_required(self):
        with self.assertRaises(ValueError):
            exporter.timestamp("2026-10-09T08:00:00")

    def test_bad_recovery_state_blocks_export(self):
        (self.work / "decrypted/recovery-manifest.json").write_text('{"status":"PARTIAL"}')
        with self.assertRaises(ValueError):
            self.export()

    def test_no_databases_reported(self):
        self.db.unlink()
        report = self.export()
        self.assertEqual(report["status"], "PARTIAL")
        self.assertIn({"error": "NO_MESSAGE_DATABASES"}, report["errors"])

    def test_policy_cli(self):
        policy = self.work / "policy.json"
        policy.write_text(json.dumps({"schema_version": 1, "account_id": "account-a",
            "date_from": "2023-11-14T22:13:10+00:00", "date_to": "2023-11-14T22:13:40+00:00",
            "message_types": [1], "conversations": {self.cid: {"name": "项目群", "project": "fixture-project"}}}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(exporter.main(["--work", str(self.work), "--policy", str(policy)]), 0)
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(self.events()[0]["project"], "fixture-project")

    def test_existing_page_account_mismatch(self):
        report = self.export()
        path = self.work / "searchable" / report["pages"][0]["path"]
        with self.assertRaisesRegex(ValueError, "IDENTITY_MISMATCH"):
            exporter.page_id("another-account", self.cid, "month", path)


class ObsidianTemplateTests(unittest.TestCase):
    def test_native_base_yaml(self):
        import yaml
        value = yaml.safe_load((ROOT / "assets/obsidian/memory-management.base").read_text())
        self.assertEqual(len(value["views"]), 3)
        self.assertTrue(all(view["type"] == "table" for view in value["views"]))
        self.assertIn('file.inFolder("wiki/memory-controls")', value["filters"]["and"])

    def test_control_template_not_claiming_active_acl(self):
        import yaml
        text = (ROOT / "assets/templates/tpl-memory-control.md").read_text()
        props = yaml.safe_load(text[4:].split("\n---", 1)[0])
        self.assertEqual(props["agent_use"], "excluded")
        self.assertIn("后台属性回读尚未接入", text)


if __name__ == "__main__":
    unittest.main()
