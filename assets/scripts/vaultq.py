#!/usr/bin/env python3
"""vaultq — qkb 召回 + 本地 reranker 重排（bge-reranker-v2-m3，跑在 4090 上）。

用两阶段检索修「答案散落、Top5 不准」的问题：
  1) qkb query 取 N 个候选（BM25+向量+RRF）
  2) 候选片段送 reranker（cross-encoder）重排，返回最相关的 K 个

依赖：
  - qkb CLI
  - rerank 服务：GPU 机上 llama-server --reranking（组网见 references/network-setup.md）；
    远端地址用 config.json network.gpu.rerank_url 或环境变量 RERANK_URL_REMOTE 配置
（服务不可用时会自动回退为 qkb 原始排序，不报错中断。）
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

QKB = os.environ.get("QKB_BIN", "/opt/homebrew/bin/qkb")
# rerank 链：本机（launchd com.<user>.rerank-local，0.7s/30条）→ 远端 GPU（可选）→ 放弃（回退 qkb 排序）
def _cfg(path):
    try:
        c = json.load(open(os.path.expanduser("~/.shuzi-rensheng/config.json")))
        for k in path.split("."):
            c = c[k]
        return c if isinstance(c, str) else ""
    except Exception:
        return ""

RERANK_URLS = [os.environ.get("RERANK_URL", "http://127.0.0.1:8082/rerank")]
_REMOTE_RERANK = os.environ.get("RERANK_URL_REMOTE") or _cfg("network.gpu.rerank_url")
if _REMOTE_RERANK:
    RERANK_URLS.append(_REMOTE_RERANK)


def qkb_search(query: str, n: int) -> list:
    p = subprocess.run([QKB, "query", query, "--limit", str(n), "--json"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write((p.stderr or p.stdout)[-500:] + "\n")
        sys.exit(1)
    out = p.stdout
    i = out.find("[")
    return json.loads(out[i:]) if i >= 0 else []


def rerank(query: str, docs: list) -> list:
    body = json.dumps({"query": query, "documents": docs}).encode()
    last = None
    for url in RERANK_URLS:
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["results"]
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last else RuntimeError("no rerank url")


def main() -> int:
    ap = argparse.ArgumentParser(description="qkb + reranker 两阶段检索")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5, help="最终返回条数")
    ap.add_argument("-n", type=int, default=30, help="qkb 候选条数")
    ap.add_argument("--files", action="store_true", help="只输出文件路径")
    ap.add_argument("--no-rerank", action="store_true", help="只用 qkb 排序")
    a = ap.parse_args()

    cands = qkb_search(a.query, a.n)
    if not cands:
        print("(无结果)")
        return 0

    fallback = False
    if a.no_rerank:
        fallback = True
    else:
        try:
            docs = [(c.get("matched_text") or c.get("title") or "") for c in cands]
            rs = rerank(a.query, docs)
            order = sorted(rs, key=lambda x: x["relevance_score"], reverse=True)
            ranked = [(r["relevance_score"], cands[r["index"]]) for r in order]
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"⚠ reranker 不可用（{e}）→ 回退 qkb 排序\n")
            fallback = True
    if fallback:
        ranked = [(c.get("score", 0.0), c) for c in cands]

    for i, (s, c) in enumerate(ranked[:a.k], 1):
        fp = c.get("file_path", "")
        if a.files:
            print(f"{i}\t{s:.4f}\t{fp}")
        else:
            print(f"{i}. [{s:+.3f}] {c.get('title','')} — {fp}")

    # ★ 整理页保底：全量聊天入库后，原文证据常在重排中胜出（合理），
    #   但 wiki 整理页（口径/结论）不能被挤出视野 —— top-k 里没有就补一条。
    def is_curated(c):
        fp = c.get("file_path", "")
        return fp.startswith("wiki/") and "/journal/" not in fp and "/monthly/" not in fp
    if not a.files and ranked:
        top = ranked[:a.k]
        if not any(is_curated(c) for _, c in top):
            cur = next(((s, c) for s, c in ranked if is_curated(c)), None)
            if cur:
                s, c = cur
                print(f"   📌 整理页 [{s:+.3f}] {c.get('title','')} — {c.get('file_path','')}")

    # 里程表：真实调用量化（谁在用、查什么、命中什么）
    try:
        top1 = ranked[0][1].get("file_path", "") if ranked else ""
        with open(os.path.expanduser("~/.config/qkb/usage.log"), "a", encoding="utf-8") as uf:
            uf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{a.query}\trr={0 if fallback else 1}\ttop1={top1}\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
