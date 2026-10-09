#!/usr/bin/env python3
"""QKB recall + reranking, with path filtering BEFORE remote reranking/output.

This is a single-vault output boundary, NOT a tenant-aware QKB authorization
system. Do not share the underlying QKB index with untrusted clients.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.request

from shuzi_runtime import checked_run, command, get, load_config, vault_path


def authorized_path(value, vault):
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    path = Path(value).expanduser()
    if ".." in path.parts:
        return False
    try:
        relative = path.relative_to(vault) if path.is_absolute() else path
        if not relative.parts or relative.parts[0] not in ("wiki", "raw"):
            return False
        current = vault
        for part in relative.parts:
            if part.startswith(".") or part.casefold() == "private" or ".sync-conflict-" in part:
                return False
            current = current / part
            if current.is_symlink():
                return False
        return current.is_file() and current.suffix == ".md" and current.stat().st_nlink == 1
    except (ValueError, OSError):
        return False


def filter_candidates(candidates, vault):
    return [c for c in candidates if isinstance(c, dict) and authorized_path(c.get("file_path"), vault)]


def qkb_search(query, count):
    result = checked_run([command("qkb", "QKB_BIN"), "query", query, "--limit", str(count), "--json"], timeout=60)
    start = result.stdout.find("[")
    if start < 0:
        raise ValueError("QKB returned no JSON result array")
    data = json.loads(result.stdout[start:])
    if not isinstance(data, list):
        raise ValueError("QKB results must be an array")
    return data


def rerank(query, candidates, config):
    urls = [os.environ.get("RERANK_URL", "http://127.0.0.1:8082/rerank")]
    remote = os.environ.get("RERANK_URL_REMOTE") or get(config, "network.gpu.rerank_url", "")
    if remote:
        urls.append(remote)
    body = json.dumps({"query": query, "documents": [c.get("matched_text") or c.get("title") or "" for c in candidates]}).encode()
    timeout = float(get(config, "retrieval.rerank_timeout_seconds", 3))
    if not 0 < timeout <= 30:
        raise ValueError("rerank timeout must be between 0 and 30 seconds")
    for url in urls:
        try:
            request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                results = json.load(response)["results"]
            indices = [r["index"] for r in results]
            if any(type(i) is not int for i in indices) or sorted(indices) != list(range(len(candidates))):
                raise ValueError("Invalid or incomplete reranker indices")
            if any(not math.isfinite(float(r["relevance_score"])) for r in results):
                raise ValueError("Non-finite reranker score")
            return [(float(r["relevance_score"]), candidates[r["index"]]) for r in sorted(results, key=lambda r: float(r["relevance_score"]), reverse=True)]
        except Exception:
            # Avoid logging queries, document text or endpoint credentials on failure.
            continue
    raise RuntimeError("All configured rerankers unavailable or returned invalid results")


def search(query, count=30, no_rerank=False):
    config = load_config()
    candidates = filter_candidates(qkb_search(query, count), vault_path(config))
    if not candidates:
        return [], "NO_AUTHORIZED_MATCH"
    if not no_rerank:
        try:
            return rerank(query, candidates, config), "RERANKED"
        except Exception:
            print("[WARN] Reranking unavailable; using QKB order", file=sys.stderr)
    return [(float(c.get("score", 0)), c) for c in candidates], "QKB_FALLBACK"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("-n", type=int, default=30)
    parser.add_argument("--files", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()
    if not args.query.strip() or len(args.query) > 8000 or not 1 <= args.k <= args.n <= 200:
        parser.error("Nonempty query (<=8000 chars) and 1 <= k <= n <= 200 required")
    ranked, status = search(args.query, args.n, args.no_rerank)
    if not ranked:
        print("本次检索未找到授权范围内的匹配；不代表资料不存在。")
        return 0
    top = ranked[:args.k]
    if not args.files:
        curated = lambda c: str(c.get("file_path", "")).startswith("wiki/") and "/journal/" not in c["file_path"]
        if not any(curated(c) for _, c in top):
            extra = next(((score, c) for score, c in ranked[args.k:] if curated(c)), None)
            if extra:
                top.append(extra)
    for number, (score, candidate) in enumerate(top, 1):
        path = candidate["file_path"].replace("\n", " ").replace("\r", " ")
        title = str(candidate.get("title", "")).replace("\n", " ").replace("\r", " ")
        print(f"{number}\t{score:.4f}\t{path}" if args.files else f"{number}. [{score:+.3f}] {title} — {path}")
    # Deliberately no usage.log containing queries or hit paths.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("[ERR] Retrieval failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
