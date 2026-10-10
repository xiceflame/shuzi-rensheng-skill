#!/usr/bin/env python3
"""Local-first diagnostic report generator with conservative redaction."""
from __future__ import annotations
import argparse, datetime as dt, importlib.util, json, os, platform, re, shutil, uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("shuzi_instance", ROOT / "setup" / "instance.py")
_instance = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_instance)

SECRET_KEY = re.compile(r"(key|token|secret|password|cookie|credential)", re.I)

def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SECRET_KEY.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(Path.home()), "~")
        value = re.sub(r"/Users/[^/]+", "/Users/<user>", value)
        value = re.sub(r"/home/[^/]+", "/home/<user>", value)
        return value
    return value

def check(code: str, level: str, message: str, suggestion: str = "") -> dict[str, str]:
    return {"code": code, "level": level, "message": message, "suggestion": suggestion}

def command_check(command: str, code: str, label: str) -> dict[str, str]:
    path = shutil.which(command)
    return check(code, "PASS" if path else "INFO", f"{label}: {'available' if path else 'not found'}",
                 "" if path else f"Install or configure {label} only if needed.")

def build_report(config_path: Path | None = None) -> dict[str, Any]:
    identity = _instance.load_or_create()
    checks = [
        check("RUNTIME_PYTHON", "PASS", f"Python {platform.python_version()}"),
        check("PLATFORM", "PASS", f"{platform.system()} {platform.machine()}"),
        command_check("qkb", "QKB_NOT_FOUND", "qkb"),
        command_check("openclaw", "OPENCLAW_NOT_FOUND", "OpenClaw"),
        command_check("claude", "CLAUDE_NOT_FOUND", "Claude Code"),
        command_check("hermes", "HERMES_NOT_FOUND", "Hermes"),
        command_check("tailscale", "TAILSCALE_NOT_FOUND", "Tailscale"),
    ]
    cfg = config_path or Path(os.environ.get("SHUZI_CONFIG", str(Path.home() / ".shuzi-rensheng" / "config.json"))).expanduser()
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            checks.append(check("CONFIG_VALID", "PASS", "Configuration JSON is valid"))
            network = data.get("network", {}) if isinstance(data, dict) else {}
            for name in ("brain", "gpu"):
                host = (network.get(name) or {}).get("host") if isinstance(network, dict) else None
                if host:
                    checks.append(check(f"NETWORK_{name.upper()}_CONFIGURED", "INFO", f"{name} host is configured"))
        except (OSError, ValueError):
            checks.append(check("CONFIG_INVALID", "ERROR", "Configuration JSON cannot be parsed",
                                "Repair the configuration before running tasks."))
    else:
        checks.append(check("CONFIG_MISSING", "INFO", "Configuration file is not present",
                            "Run install.sh or create ~/.shuzi-rensheng/config.json."))
    return redact({
        "schema_version": 1, "report_id": "rpt_" + uuid.uuid4().hex,
        "instance_id": identity["instance_id"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "privacy": {"chat_content": "excluded", "raw_databases": "excluded",
                    "secrets": "redacted", "upload": "disabled_by_default"},
        "checks": checks,
    })

def write_report(report: dict[str, Any], target: Path | None = None) -> Path:
    out = target or (Path.home() / ".config" / "shuzi-rensheng" / "reports" / f"{report['report_id']}.json")
    out = out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    return out

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local, redacted shuzi-rensheng diagnostic report.")
    parser.add_argument("--export", metavar="PATH")
    parser.add_argument("--config", metavar="PATH")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(Path(args.config).expanduser() if args.config else None)
    path = write_report(report, Path(args.export) if args.export else None)
    print(json.dumps(report, ensure_ascii=False) if args.json else f"{report['report_id']}\t{path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
