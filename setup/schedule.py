#!/usr/bin/env python3
"""Explicit, previewable macOS/Linux schedules generated from shared configuration."""
from __future__ import annotations

import argparse
from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import subprocess
import sys
import tempfile

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "assets" / "scripts"))
from shuzi_runtime import config_path, get, load_config, state_dir, vault_path

DEFAULTS = {
    "chat-ingest": "7 8,21 * * *", "finance-ingest": "40 */4 * * *",
    "rebuild": "10 */4 * * *", "transcribe": "20 */4 * * *",
    "lint": "7 21 * * 0", "idea-review": "7 10 * * 1",
    "rollup": "7 9 1 * *", "qkb-follow": "*/5 * * * *",
    "collector-refresh": "0 */4 * * *",
}


def cron_values(field, lower, upper):
    values = set()
    for part in field.split(","):
        base, separator, step = part.partition("/")
        stride = int(step) if separator else 1
        if stride < 1:
            raise ValueError("Cron step must be positive")
        if base == "*":
            start, end = lower, upper
        elif "-" in base:
            start, end = map(int, base.split("-"))
        else:
            start = end = int(base)
        if not lower <= start <= end <= upper:
            raise ValueError("Cron value out of range")
        values.update(range(start, end + 1, stride))
    return sorted(values)


def calendar(expression):
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Expected five cron fields")
    if fields[2] != "*" and fields[4] != "*":
        raise ValueError("Combined day-of-month/day-of-week rules are not portable; split into separate jobs")
    choices = []
    for field, key, limits in zip(fields, ("Minute", "Hour", "Day", "Month", "Weekday"), ((0,59),(0,23),(1,31),(1,12),(0,6))):
        # Validate even wildcard fields. Omitted calendar keys mean any value.
        values = cron_values(field, *limits)
        choices.append([(key, value) for value in values] if field != "*" else [(None, None)])
    combinations = 1
    for values in choices:
        combinations *= len(values)
    if combinations > 2000:
        raise ValueError("Schedule expands to more than 2000 calendar entries")
    return [{key: value for key, value in values if key} for values in itertools.product(*choices)]


def environment(config):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "SHUZI_CONFIG": str(config_path()),
            "SHUZI_VAULT": str(vault_path(config)), "SHUZI_PYTHON": sys.executable}


def job_command(name, config):
    # The wrapper rechecks schedule.enabled on EVERY invocation.
    return [sys.executable, str(PKG / "setup" / "scheduled-task.py"), name]


def plan(names, config, platform):
    env = environment(config)
    jobs = []
    for name in names:
        if name not in DEFAULTS:
            raise ValueError("Unknown task: " + name)
        expression = get(config, "schedule." + name.replace("-", "_"), DEFAULTS[name])
        cal = calendar(expression)
        args = job_command(name, config)
        job = {"name": name, "cron": expression, "command": args, "environment": env}
        if platform == "macos":
            job["plist"] = {"Label": "ai.shuzi." + name, "ProgramArguments": args,
                            "StartCalendarInterval": cal, "EnvironmentVariables": env,
                            "WorkingDirectory": str(vault_path(config)), "ProcessType": "Background"}
        jobs.append(job)
    return jobs


def merge_crontab(existing, jobs):
    text = existing
    for job in jobs:
        name = job["name"]
        begin, end = "# BEGIN SHUZI " + name, "# END SHUZI " + name
        if text.count(begin) != text.count(end) or text.count(begin) > 1:
            raise ValueError("Malformed managed cron block; refusing to modify crontab")
        text = re.sub(r"(?m)^" + re.escape(begin) + r"\n.*?^" + re.escape(end) + r"(?:\n|$)", "", text, flags=re.S)
        env_args = [key + "=" + value for key, value in job["environment"].items()]
        command = shlex.join(["/usr/bin/env", *env_args, *job["command"]]).replace("%", r"\%")
        text = text.rstrip("\n") + "\n" + begin + "\n" + job["cron"] + " " + command + "\n" + end + "\n"
    return text.lstrip("\n")


def install(jobs, platform):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backups = state_dir() / "schedule-backups" / stamp
    backups.mkdir(parents=True, mode=0o700)
    if platform == "linux":
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        if current.returncode and not (current.returncode == 1 and "no crontab for" in current.stderr.lower()):
            raise RuntimeError("Cannot read existing crontab; refusing to replace it")
        previous = current.stdout if current.returncode == 0 else ""
        (backups / "crontab.txt").write_text(previous, encoding="utf-8")
        new = merge_crontab(previous, jobs)
        subprocess.run(["crontab", "-"], input=new, text=True, check=True, timeout=10)
    else:
        directory = Path.home() / "Library" / "LaunchAgents"
        directory.mkdir(parents=True, exist_ok=True)
        for job in jobs:
            target = directory / (job["plist"]["Label"] + ".plist")
            if target.exists():
                (backups / target.name).write_bytes(target.read_bytes())
            data = plistlib.dumps(job["plist"])
            fd, temporary = tempfile.mkstemp(dir=directory, prefix=".shuzi-")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{job['plist']['Label']}"], capture_output=True, timeout=10)
            subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=True, timeout=10)
    print("已注册指定任务；旧配置备份：" + str(backups))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--platform", choices=("macos", "linux"))
    args = parser.parse_args()
    if not args.tasks:
        parser.error("Explicit task names required; available: " + ", ".join(DEFAULTS))
    native = "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else None
    platform = args.platform or native
    if not platform or (not args.dry_run and platform != native):
        parser.error("Native Windows is not validated; use macOS/Linux. Cross-platform output is preview-only")
    names = list(DEFAULTS) if args.tasks == ["all"] else list(dict.fromkeys(args.tasks))
    config = load_config()
    jobs = plan(names, config, platform)
    if args.dry_run:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
        return 0
    if get(config, "schedule.enabled") is not True:
        parser.error("Set schedule.enabled=true explicitly before registering tasks; --dry-run is always available")
    if not vault_path(config).is_dir():
        parser.error("Configured vault does not exist")
    install(jobs, platform)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] " + str(error), file=sys.stderr)
        raise SystemExit(1)
