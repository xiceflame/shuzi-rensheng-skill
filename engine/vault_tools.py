"""Restricted POSIX file tools for the bundled API agent (not a host sandbox).

No arbitrary shell, no writes outside wiki, no symlink traversal. Existing
files require compare-and-swap hashes and a verified backup before replacement.
Other agent frameworks must configure their own sandbox and tool permissions.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets" / "scripts"))
from shuzi_runtime import atomic_json, file_lock, state_dir

WRITE_ROOTS = {
    "owner": ("wiki",),
    "finance": ("wiki/finance",),
    "engineer": ("wiki/projects", "wiki/concepts"),
    "business": ("wiki/projects",),
    "query": (),
}
READ_ROOTS = {"raw", "wiki", "templates", "ledger"}
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".tsv", ".json", ".beancount"}
MAX_BYTES = 2 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VaultTools:
    def __init__(self, root: Path, role: str = "owner"):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("Restricted API writer requires macOS/Linux; native Windows is not supported")
        if role not in WRITE_ROOTS:
            raise ValueError("Unknown writer role")
        self.root = root.resolve(strict=True)
        self.role = role
        self.identity = digest(str(self.root).encode())[:24]
        self.failed_calls = 0
        self.writes = []

    def parts(self, value: str, write: bool = False) -> tuple:
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("Invalid path")
        path = Path(value).expanduser()
        if ".." in path.parts:
            raise PermissionError("Parent traversal denied")
        if path.is_absolute():
            try:
                path = path.relative_to(self.root)
            except ValueError:
                raise PermissionError("Path outside vault") from None
        parts = path.parts
        if any(p.startswith(".") or p.casefold() == "private" or ".sync-conflict-" in p for p in parts):
            raise PermissionError("Private, hidden and conflict paths are not available to the agent")
        if parts and parts[0] not in READ_ROOTS and parts not in (("CLAUDE.md",), ("README.md",)):
            raise PermissionError("Path is not in the read allowlist")
        if write:
            relative = path.as_posix()
            if not any(relative.startswith(prefix + "/") for prefix in WRITE_ROOTS[self.role]):
                raise PermissionError("Writer role cannot modify this path")
            if path.suffix != ".md":
                raise PermissionError("Only wiki Markdown writes are allowed")
        return parts

    @contextlib.contextmanager
    def directory(self, parts, create=False):
        # dir_fd + O_NOFOLLOW prevents both ordinary and raced symlink traversal.
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def read_at(fd, name):
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(handle, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionError("Only regular, non-hardlinked files are readable")
            data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("File exceeds 2 MiB tool limit")
            return data

    def read_file(self, path):
        parts = self.parts(path)
        if not parts or Path(parts[-1]).suffix not in TEXT_SUFFIXES:
            raise PermissionError("Only supported text files are readable")
        with self.directory(parts[:-1]) as fd:
            data = self.read_at(fd, parts[-1])
        return {"content": data.decode("utf-8"), "sha256": digest(data)}

    def list_dir(self, path):
        parts = self.parts(path)
        with self.directory(parts) as fd:
            names = []
            for name in sorted(os.listdir(fd)):
                try:
                    self.parts(str(Path(*parts) / name))
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        continue
                    names.append(name)
                except (PermissionError, OSError):
                    continue
            return names[:500]

    @staticmethod
    def validate_markdown(content: str, old: bytes | None):
        if not content.startswith("---\n") or "\n---" not in content[4:]:
            raise ValueError("Wiki page requires YAML frontmatter")
        header = content.split("\n---", 1)[0]
        for key in ("id", "context", "created"):
            if not re.search(r"^" + key + r":\s*\S+", header, re.M):
                raise ValueError("Missing frontmatter field: " + key)
        new_id = re.search(r"^id:\s*(.+)$", header, re.M).group(1).strip()
        uuid.UUID(new_id.strip("\"'"))
        if old:
            match = re.search(r"^id:\s*(.+)$", old.decode("utf-8").split("\n---", 1)[0], re.M)
            if match and match.group(1).strip() != new_id:
                raise ValueError("Existing page id must remain unchanged")

    def backup(self, relative, data):
        directory = state_dir() / "backups" / self.identity
        if directory.resolve() == self.root or self.root in directory.resolve().parents:
            raise PermissionError("Backup directory must be outside the vault")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / (uuid.uuid4().hex + ".md")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if target.read_bytes() != data:
            raise OSError("Backup verification failed")
        atomic_json(target.with_suffix(".json"), {"vault": str(self.root), "source": relative,
                                                  "sha256": digest(data), "snapshot": target.name})
        return str(target)

    def write_file(self, path, content, expected_sha256=None):
        parts = self.parts(path, write=True)
        if not isinstance(content, str):
            raise ValueError("content must be text")
        data = content.encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ValueError("Content exceeds 2 MiB tool limit")
        backup = None
        with file_lock(state_dir() / ("writer-" + self.identity + ".lock")):
            with self.directory(parts[:-1], create=True) as fd:
                try:
                    old = self.read_at(fd, parts[-1])
                except FileNotFoundError:
                    old = None
                if old is not None and expected_sha256 != digest(old):
                    raise ValueError("Stale or missing expected_sha256; read the file before writing")
                if old is None and expected_sha256 is not None:
                    raise ValueError("Expected file no longer exists")
                self.validate_markdown(content, old)
                if old is not None:
                    backup = self.backup(str(Path(*parts)), old)
                temp = ".shuzi-write-" + uuid.uuid4().hex
                handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    with os.fdopen(handle, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if old is None:
                        # Atomic create without clobbering a concurrently created page.
                        os.link(temp, parts[-1], src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                    else:
                        if self.read_at(fd, parts[-1]) != old:
                            raise ValueError("File changed while preparing replacement")
                        os.replace(temp, parts[-1], src_dir_fd=fd, dst_dir_fd=fd)
                    os.fsync(fd)
                finally:
                    try:
                        os.unlink(temp, dir_fd=fd)
                    except FileNotFoundError:
                        pass
        receipt = {"path": str(Path(*parts)), "sha256": digest(data), "backup": backup}
        self.writes.append(receipt)
        return receipt

    def dispatch(self, name, args):
        try:
            handlers = {"read_file": self.read_file, "write_file": self.write_file, "list_dir": self.list_dir}
            if name not in handlers:
                raise PermissionError("Unknown or prohibited tool; shell execution is disabled")
            return {"ok": True, "result": handlers[name](**args)}
        except Exception as error:
            self.failed_calls += 1
            return {"ok": False, "error": type(error).__name__, "message": str(error)}
