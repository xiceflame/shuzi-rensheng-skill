"""Offline follower, runner, retrieval and scheduling regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import unittest
from unittest.mock import patch
from test_boundaries import Isolated, PAGE, ROOT, follow, runtime, schedule, sentinel, vaultq


class ConflictTests(Isolated):
    def sources(self):
        return [self.page(), self.page("wiki/projects/example.sync-conflict-20261009-120000-DEVICE.md", PAGE + "other")]

    def test_default_is_report_only(self):
        paths = self.sources()
        result = self.run_cli("assets/scripts/conflict-sentinel.py")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(all(p.exists() for p in paths))
        self.assertIn("CONFLICT_NEEDS_REVIEW", result.stdout)

    def test_failed_archive_keeps_sources(self):
        paths = self.sources()
        with patch.object(sentinel, "copy_verified", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                sentinel.archive_group(paths, self.vault, self.home / "archive")
        self.assertEqual([p.read_text() for p in paths], [PAGE, PAGE + "other"])

    def test_verified_archive_keeps_sources(self):
        paths = self.sources()
        directory = sentinel.archive_group(paths, self.vault, self.home / "archive")
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual(manifest["state"], "ARCHIVED_UNRESOLVED")
        self.assertEqual(len(manifest["files"]), 2)
        self.assertTrue(all(p.exists() for p in paths))

    def test_archive_must_be_outside_vault(self):
        with self.assertRaises(ValueError):
            sentinel.archive_group(self.sources(), self.vault, self.vault / "archive")


class FollowerTests(Isolated):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.page()

    def run_fake(self, args, **kwargs):
        self.calls.append(args)
        return subprocess.CompletedProcess(args, 0, "chunks (0 pending)", "")

    def test_no_repeated_ingest(self):
        self.assertEqual(follow.follow_once(self.run_fake), "INDEXED")
        self.calls.clear()
        self.assertEqual(follow.follow_once(self.run_fake), "NO_CHANGE")
        self.assertFalse(any("ingest" in a for a in self.calls))

    def test_same_mtime_changed_content(self):
        follow.follow_once(self.run_fake)
        path = self.vault / "wiki/projects/example.md"
        info = path.stat()
        path.write_text(PAGE + "new")
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertEqual(follow.follow_once(self.run_fake), "INDEXED")

    def test_failure_no_checkpoint_and_retry(self):
        def fail(args, **kwargs):
            raise subprocess.CalledProcessError(37, args)
        with self.assertRaises(subprocess.CalledProcessError):
            follow.follow_once(fail)
        self.assertFalse((runtime.qkb_dir() / "follow-state-v2.json").exists())
        self.assertEqual(follow.follow_once(self.run_fake), "INDEXED")

    def test_midrun_changes_are_not_lost(self):
        def change(args, **kwargs):
            if "ingest" in args:
                self.page(content=PAGE + "arrived during ingest")
            return self.run_fake(args, **kwargs)
        follow.follow_once(change)
        self.assertEqual(follow.follow_once(self.run_fake), "INDEXED")

    def test_pending_after_embed_fails(self):
        def pending(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "chunks (3 pending)", "")
        with self.assertRaises(RuntimeError):
            follow.follow_once(pending)
        self.assertFalse((runtime.qkb_dir() / "follow-state-v2.json").exists())

    def test_unknown_status_is_not_zero(self):
        def unknown(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "unknown status format", "")
        with self.assertRaises(ValueError):
            follow.follow_once(unknown)

    def test_deleted_file_changes_snapshot(self):
        path = self.page()
        follow.follow_once(self.run_fake)
        path.unlink()
        self.assertEqual(follow.follow_once(self.run_fake), "INDEXED")


class RetrievalTests(Isolated):
    def test_filter_before_rerank(self):
        self.page()
        self.page("wiki/private/personal.md")
        candidates = [{"file_path": "wiki/projects/example.md", "matched_text": "public"},
                      {"file_path": "wiki/private/personal.md", "matched_text": "private-fixture"}]
        def rerank(query, docs, config):
            self.assertEqual(len(docs), 1)
            self.assertNotIn("private-fixture", json.dumps(docs))
            return [(1.0, docs[0])]
        with patch.object(vaultq, "qkb_search", return_value=candidates), patch.object(vaultq, "rerank", side_effect=rerank):
            ranked, status = vaultq.search("question")
        self.assertEqual(status, "RERANKED")
        self.assertEqual(len(ranked), 1)
        self.assertFalse((runtime.qkb_dir() / "usage.log").exists())

    def test_outside_symlink_stale_filtered(self):
        path = self.page()
        (self.vault / "wiki/alias.md").symlink_to(path)
        for value in ("../outside.md", str(self.home / "outside.md"), "wiki/alias.md", "wiki/missing.md", "wiki/private/no.md"):
            with self.subTest(value=value):
                self.assertFalse(vaultq.authorized_path(value, self.vault))

    def test_all_private_no_remote(self):
        self.page("wiki/private/personal.md")
        with patch.object(vaultq, "qkb_search", return_value=[{"file_path": "wiki/private/personal.md"}]), patch.object(vaultq, "rerank") as remote:
            self.assertEqual(vaultq.search("q")[1], "NO_AUTHORIZED_MATCH")
            remote.assert_not_called()

    def test_rerank_fallback(self):
        self.page()
        with patch.object(vaultq, "qkb_search", return_value=[{"file_path": "wiki/projects/example.md", "score": 2}]), patch.object(vaultq, "rerank", side_effect=TimeoutError), contextlib.redirect_stderr(io.StringIO()):
            ranked, status = vaultq.search("q")
        self.assertEqual((ranked[0][0], status), (2, "QKB_FALLBACK"))


class RunnerTests(Isolated):
    def test_nested_api_lookup(self):
        self.assertIs(runtime.get({"api": {"llm": {"enabled": True}}}, "llm.enabled"), True)

    def test_invalid_config_not_silently_defaulted(self):
        self.config.write_text("invalid-json")
        with self.assertRaises(ValueError):
            runtime.load_config()

    def test_configured_vault(self):
        with patch.dict(os.environ):
            del os.environ["SHUZI_VAULT"]
            self.assertEqual(runtime.vault_path(), self.vault)

    def test_dryrun_no_state(self):
        result = self.run_cli("engine/run.py", "lint", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.vault), result.stdout)
        self.assertFalse((self.home / "state").exists())

    def test_failed_backend_propagates(self):
        directory = self.home / "bin"
        directory.mkdir()
        stub = directory / "claude"
        stub.write_text("#!/bin/sh\necho simulated-error >&2\nexit 37\n")
        stub.chmod(0o700)
        with patch.dict(os.environ, PATH=str(directory) + os.pathsep + os.environ["PATH"]):
            result = self.run_cli("engine/run.py", "lint", "--engine", "claude")
        self.assertEqual(result.returncode, 37, result.stderr)
        receipt = json.loads(next((self.home / "state/runs").glob("*.json")).read_text())
        self.assertEqual((receipt["status"], receipt["exit_code"]), ("FAILED", 37))
        self.assertIn("simulated-error", Path(receipt["log"]).read_text())

    def test_manual_needs_action(self):
        result = self.run_cli("engine/run.py", "lint", "--engine", "manual")
        self.assertEqual(result.returncode, 3)
        self.assertIn("NEEDS_USER_ACTION", result.stdout)

    def test_ollama_unsupported(self):
        result = self.run_cli("engine/run.py", "lint", "--engine", "ollama")
        self.assertEqual(result.returncode, 4)
        self.assertIn("UNSUPPORTED_CAPABILITY", result.stdout)

    def test_engine_path_traversal(self):
        self.assertEqual(self.run_cli("engine/run.py", "lint", "--engine", "../../bad").returncode, 2)


class ScheduleTests(Isolated):
    def test_disabled_no_install(self):
        self.assertEqual(self.run_cli("setup/schedule.py", "lint").returncode, 2)
        self.assertFalse((self.home / "state").exists())

    def test_no_implicit_tasks(self):
        self.assertEqual(self.run_cli("setup/schedule.py").returncode, 2)

    def test_preview_no_mutation(self):
        result = self.run_cli("setup/schedule.py", "lint", "--dry-run", "--platform", "macos")
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = json.loads(result.stdout)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["environment"]["SHUZI_VAULT"], str(self.vault))
        self.assertFalse((self.home / "Library/LaunchAgents").exists())
        self.assertFalse((self.home / "state").exists())

    def test_custom_times_xml_roundtrip(self):
        jobs = schedule.plan(["lint"], {"schedule": {"lint": "12 16 * * 2"}}, "macos")
        plist = plistlib.loads(plistlib.dumps(jobs[0]["plist"]))
        self.assertEqual(plist["StartCalendarInterval"], [{"Minute": 12, "Hour": 16, "Weekday": 2}])
        self.assertEqual(plist["WorkingDirectory"], str(self.vault))

    def test_crontab_preserves_unrelated_idempotent(self):
        unrelated = "# user job\n0 1 * * * /somewhere/run.sh\n0 2 * * * /other/qkb-follow-custom\n"
        jobs = schedule.plan(["lint"], {}, "linux")
        once = schedule.merge_crontab(unrelated, jobs)
        self.assertEqual(once, schedule.merge_crontab(once, jobs))
        self.assertIn(unrelated, once)

    def test_crontab_preserves_unselected_job(self):
        first = schedule.merge_crontab("", schedule.plan(["lint"], {}, "linux"))
        second = schedule.merge_crontab(first, schedule.plan(["rollup"], {}, "linux"))
        self.assertIn("# BEGIN SHUZI lint", second)
        self.assertIn("# BEGIN SHUZI rollup", second)

    def test_invalid_cron(self):
        for value in ("61 0 * * *", "*/0 * * * *", "0 0 1 * 2", "nonsense"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                schedule.calendar(value)

    def test_disabled_runtime_no_dispatch(self):
        result = self.run_cli("setup/scheduled-task.py", "chat-ingest")
        self.assertEqual(result.returncode, 0)
        self.assertIn("DISABLED", result.stdout)
        self.assertFalse((self.home / "state").exists())


if __name__ == "__main__":
    unittest.main()
