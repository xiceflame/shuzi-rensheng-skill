"""Shared configuration and process helpers. No installation or service startup on import."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile


def config_path() -> Path:
    return Path(os.environ.get("SHUZI_CONFIG", "~/.shuzi-rensheng/config.json")).expanduser().absolute()


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("config.json must contain an object")
    return config


def get(config: dict, key: str, default=None):
    # Preserve older API adapter calls while reading the actual api.* schema.
    if key.split(".")[0] in ("llm", "embedding", "vlm"):
        key = "api." + key
    value = config
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def vault_path(config=None) -> Path:
    if config is None:
        config = load_config()
    path = Path(os.environ.get("SHUZI_VAULT") or get(config, "vault", "~/数字人生")).expanduser()
    if not path.is_absolute():
        raise ValueError("vault must be an absolute path (or ~/...) independent of working directory")
    return path.resolve()


def state_dir() -> Path:
    path = Path(os.environ.get("SHUZI_STATE_DIR", "~/.shuzi-rensheng")).expanduser().absolute()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def qkb_dir() -> Path:
    return Path(os.environ.get("SHUZI_QKB_DIR", "~/.config/qkb")).expanduser().absolute()


def command(name: str, env_name: str) -> str:
    value = os.environ.get(env_name, name)
    result = shutil.which(os.path.expanduser(value))
    if not result:
        raise FileNotFoundError("Required executable not found: " + name + " (set " + env_name + ")")
    return result


def api_key(kind: str, config=None) -> str:
    config = load_config() if config is None else config
    name = get(config, kind + ".api_key_env", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid api_key_env name")
    return os.environ.get(name, "")


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".shuzi-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextlib.contextmanager
def file_lock(path: Path, blocking: bool = True):
    # Native Windows is intentionally rejected rather than silently running unlocked.
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def checked_run(args, timeout: int = 300, **kwargs):
    """Kill the whole POSIX process group on timeout, including wrapper children."""
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=True, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        result.check_returncode()
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("get", "key", "vault"))
    parser.add_argument("path", nargs="?", default="")
    args = parser.parse_args()
    config = load_config()
    value = vault_path(config) if args.action == "vault" else (
        api_key(args.path, config) if args.action == "key" else get(config, args.path, ""))
    print(json.dumps(value, ensure_ascii=False) if isinstance(value, (bool, dict, list)) else value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
