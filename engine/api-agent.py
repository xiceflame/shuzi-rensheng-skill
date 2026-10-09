#!/usr/bin/env python3
"""最小 Agent 循环：只给 LLM 三个工具（读文件/写文件/列目录），跑整理任务。

这是「没有 agent 框架、只有 API key」时的执行器。
"""
import argparse, json, os, subprocess, sys

TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "读文件",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "写文件（覆盖）",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "列目录",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_shell", "description": "跑一条 shell 命令（谨慎）",
     "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
]


def call(base, key, model, msgs, max_tokens):
    import urllib.request
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "messages": msgs, "tools": TOOLS,
                         "tool_choice": "auto", "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def do(name, args):
    try:
        if name == "read_file":
            return open(os.path.expanduser(args["path"]), encoding="utf-8", errors="replace").read()[:200000]
        if name == "write_file":
            p = os.path.expanduser(args["path"]); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(args["content"]); return "ok: " + p
        if name == "list_dir":
            return "\n".join(os.listdir(os.path.expanduser(args["path"]))[:500])
        if name == "run_shell":
            return subprocess.run(args["cmd"], shell=True, capture_output=True, text=True, timeout=300).stdout[:20000]
    except Exception as e:
        return "ERR: %s" % e
    return "unknown tool"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--key", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--prompt", required=True); ap.add_argument("--max-turns", type=int, default=40)
    a = ap.parse_args()
    msgs = [{"role": "user", "content": a.prompt}]
    for _ in range(a.max_turns):
        r = call(a.base, a.key, a.model, msgs, a.max_tokens)
        m = r["choices"][0]["message"]; msgs.append(m)
        tcs = m.get("tool_calls") or []
        if not tcs:
            print(m.get("content", "")); return 0
        for tc in tcs:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            out = do(tc["function"]["name"], args)
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": str(out)})
    print("[warn] 达到最大轮数", file=sys.stderr); return 1


if __name__ == "__main__":
    sys.exit(main())
