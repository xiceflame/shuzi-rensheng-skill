"""Offline regression tests: only synthetic data in temporary directories."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "assets/scripts"), str(ROOT / "engine")]
import shuzi_runtime as runtime
from vault_tools import VaultTools
import vaultq


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


follow = load("follow", "assets/scripts/qkb-follow.py")
sentinel = load("sentinel", "assets/scripts/conflict-sentinel.py")
api = load("api_agent", "engine/api-agent.py")
schedule = load("schedule", "setup/schedule.py")
PAGE = "---\nid: 00000000-0000-4000-8000-000000000003\ncontext: test\ncreated: 2026-10-09\n---\nOriginal evidence\n"


class Isolated(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="shuzi-test-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.vault = self.home / "vault with spaces & 中文"
        self.vault.mkdir()
        for directory in ("wiki/projects", "wiki/private", "wiki/finance", "raw"):
            (self.vault / directory).mkdir(parents=True, exist_ok=True)
        self.config = self.home / "config.json"
        self.config.write_text(json.dumps({"vault": str(self.vault), "schedule": {"enabled": False}}))
        env = {"HOME": str(self.home), "SHUZI_CONFIG": str(self.config), "SHUZI_VAULT": str(self.vault),
               "SHUZI_STATE_DIR": str(self.home / "state"), "SHUZI_QKB_DIR": str(self.home / "qkb"),
               "SHUZI_PYTHON": sys.executable, "QKB_BIN": sys.executable}
        self.environ = patch.dict(os.environ, env)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.tools = VaultTools(self.vault)

    def page(self, name="wiki/projects/example.md", content=PAGE):
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, relative, *args):
        return subprocess.run([sys.executable, str(ROOT / relative), *args], capture_output=True, text=True, timeout=15)


class FileBoundaryTests(Isolated):
    def test_creation(self):
        result = self.tools.write_file("wiki/projects/new.md", PAGE)
        self.assertEqual((self.vault / result["path"]).read_text(), PAGE)

    def test_outside_path_denied(self):
        with self.assertRaises(PermissionError):
            self.tools.write_file(str(self.home / "outside.md"), PAGE)
        self.assertFalse((self.home / "outside.md").exists())

    def test_parent_traversal_denied(self):
        with self.assertRaises(PermissionError):
            self.tools.write_file("wiki/../raw/test.md", PAGE)

    def test_raw_immutable(self):
        path = self.page("raw/source.md")
        with self.assertRaises(PermissionError):
            self.tools.write_file(str(path), PAGE + "changed")
        self.assertEqual(path.read_text(), PAGE)

    def test_private_read_and_listing_denied(self):
        self.page("wiki/private/personal.md")
        with self.assertRaises(PermissionError):
            self.tools.read_file("wiki/private/personal.md")
        self.assertNotIn("private", self.tools.list_dir("wiki"))

    def test_directory_symlink_denied(self):
        (self.vault / "wiki/linked").symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(OSError):
            self.tools.write_file("wiki/linked/outside.md", PAGE)
        self.assertFalse((self.home / "outside.md").exists())

    def test_file_symlink_denied(self):
        target = self.home / "target.md"
        target.write_text(PAGE)
        (self.vault / "wiki/link.md").symlink_to(target)
        with self.assertRaises(OSError):
            self.tools.read_file("wiki/link.md")

    def test_hardlink_denied(self):
        target = self.page()
        os.link(target, self.vault / "wiki/hardlink.md")
        with self.assertRaises(PermissionError):
            self.tools.read_file("wiki/hardlink.md")

    def test_role_boundary(self):
        tools = VaultTools(self.vault, "finance")
        with self.assertRaises(PermissionError):
            tools.write_file("wiki/projects/no.md", PAGE)
        tools.write_file("wiki/finance/allowed.md", PAGE)

    def test_query_role_cannot_write(self):
        with self.assertRaises(PermissionError):
            VaultTools(self.vault, "query").write_file("wiki/projects/no.md", PAGE)

    def test_configuration_not_writable(self):
        with self.assertRaises(PermissionError):
            self.tools.write_file("CLAUDE.md", PAGE)

    def test_markdown_schema(self):
        with self.assertRaises(ValueError):
            self.tools.write_file("wiki/no-header.md", "hello")

    def test_compare_and_swap_required(self):
        path = self.page()
        with self.assertRaises(ValueError):
            self.tools.write_file(str(path), PAGE + "new")
        self.assertEqual(path.read_text(), PAGE)

    def test_backup_and_successful_update(self):
        path = self.page()
        sha = self.tools.read_file(str(path))["sha256"]
        receipt = self.tools.write_file(str(path), PAGE + "new", sha)
        self.assertEqual(Path(receipt["backup"]).read_text(), PAGE)
        self.assertEqual(path.read_text(), PAGE + "new")

    def test_backup_failure_retains_original(self):
        path = self.page()
        sha = self.tools.read_file(str(path))["sha256"]
        with patch.object(self.tools, "backup", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.tools.write_file(str(path), PAGE + "new", sha)
        self.assertEqual(path.read_text(), PAGE)

    def test_stable_id(self):
        path = self.page()
        sha = self.tools.read_file(str(path))["sha256"]
        with self.assertRaises(ValueError):
            self.tools.write_file(str(path), PAGE.replace("000000000003", "000000000004"), sha)

    def test_shell_tool_removed(self):
        self.assertNotIn("run_shell", [tool["function"]["name"] for tool in api.TOOLS])
        self.assertFalse(self.tools.dispatch("run_shell", {})["ok"])

    def test_no_success_after_tool_failure(self):
        self.tools.dispatch("run_shell", {})
        def reply(*args):
            return {"choices": [{"message": {"role": "assistant", "content": "done"}}]}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.run("task", "", "", "", 10, 1, self.tools, caller=reply), 1)


if __name__ == "__main__":
    unittest.main()
