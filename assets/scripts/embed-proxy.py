#!/usr/bin/env python3
"""qkb 嵌入的高可用代理：优先 4090，不可用时自动回落本机 Ollama。

背景：嵌入算力在 4090 主机（远程算力主机，默认本机）。若它关机/断连，
vault 的 `qkb embed` 会失败、新内容无法语义检索。本代理让调用方只连
127.0.0.1:11430，由它决定发往 4090 还是本机（本机也装了同一个
qwen3-embedding:4b → 向量空间一致，回落后向量仍兼容）。

策略：
  - 每 REFRESH 秒探测一次 4090 /api/version（2s 超时，带缓存）；
    探测失败 → 该窗口内走本机；探测成功 → 走 4090（长超时，容忍冷加载）。
  - 只代理 Ollama 的 /api/* 请求（非流式 JSON）。
  - 当前目标写入状态文件，供健康巡检读取。
"""
import http.server
import json
import os
import socketserver
import time
import urllib.error
import urllib.request

PRIMARY = os.environ.get("EMBED_PRIMARY", "http://127.0.0.1:11434")
LOCAL = os.environ.get("EMBED_LOCAL", "http://127.0.0.1:11434")
PORT = int(os.environ.get("EMBED_PROXY_PORT", "11430"))
REFRESH = 15          # 探测结果缓存秒数
PROBE_TIMEOUT = 2     # 探测超时
BIG_TIMEOUT = 600     # 真实请求超时（容忍 4090 冷加载）

STATE = os.path.expanduser("~/.config/qkb/embed-proxy.state")
_cache = {"target": None, "at": 0.0, "primary_up": None}


def _probe(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=PROBE_TIMEOUT) as r:
            return r.status == 200
    except Exception:
        return False


def choose() -> str:
    now = time.time()
    if _cache["target"] and now - _cache["at"] < REFRESH:
        return _cache["target"]
    up = _probe(PRIMARY)
    target = PRIMARY if up else LOCAL
    changed = up != _cache["primary_up"]
    _cache.update(target=target, at=now, primary_up=up)
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump({"target": target, "primary_up": up, "ts": now}, f)
    except Exception:
        pass
    if changed:
        print(f"[embed-proxy] primary_up={up} -> {target}", flush=True)
    return target


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method: str):
        base = choose()
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
        req = urllib.request.Request(base + self.path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=BIG_TIMEOUT) as r:
                data = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            data, status = e.read(), e.code
        except Exception as e:  # 目标半途挂掉 → 再试另一个
            alt = LOCAL if base == PRIMARY else PRIMARY
            try:
                req = urllib.request.Request(alt + self.path, data=body, method=method,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=BIG_TIMEOUT) as r:
                    data, status = r.read(), r.status
            except Exception as e2:
                data, status = (f'{{"error":"{e2}"}}').encode(), 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(data)

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")

    def do_HEAD(self):
        self._proxy("HEAD")

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as srv:
        print(f"[embed-proxy] listening 127.0.0.1:{PORT} primary={PRIMARY} local={LOCAL}", flush=True)
        srv.serve_forever()
