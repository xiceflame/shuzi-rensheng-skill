import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DiagnosticsTests(unittest.TestCase):
    def run_script(self, script, *args, env=None):
        merged = os.environ.copy()
        merged.update(env or {})
        return subprocess.run([sys.executable, str(ROOT / script), *args], text=True, capture_output=True, env=merged)

    def test_identity_persists_and_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "instance.json"
            env = {"SHUZI_INSTANCE_FILE": str(path)}
            first = json.loads(self.run_script("setup/instance.py", "--json", env=env).stdout)
            second = json.loads(self.run_script("setup/instance.py", "--json", env=env).stdout)
            rotated = json.loads(self.run_script("setup/instance.py", "--json", "--reset", env=env).stdout)
            self.assertEqual(first["instance_id"], second["instance_id"])
            self.assertNotEqual(first["instance_id"], rotated["instance_id"])

    def test_report_schema_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            result = self.run_script("engine/diagnostics.py", "--export", str(report),
                                     env={"SHUZI_INSTANCE_FILE": str(Path(tmp) / "instance.json")})
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(report.read_text())
            self.assertTrue(data["report_id"].startswith("rpt_"))
            self.assertTrue(data["instance_id"].startswith("sr_"))
            self.assertNotIn("OPENAI_API_KEY", json.dumps(data))
            self.assertEqual(data["privacy"]["upload"], "disabled_by_default")

    def test_missing_dependencies_still_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            result = self.run_script("engine/diagnostics.py", "--export", str(report),
                                     env={"HOME": tmp, "PATH": "/usr/bin"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreaterEqual(len(json.loads(report.read_text())["checks"]), 5)

if __name__ == "__main__":
    unittest.main()
