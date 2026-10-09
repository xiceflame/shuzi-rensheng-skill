#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 对话导出器：Claude Code / Codex 本地会话 → 可检索月度 Markdown。

落点：<vault>/raw/chat/{claude,codex}/<项目>/<YYYY-MM>.md（带 frontmatter，qkb 可索引）
增量：manifest 记录每个会话文件的 mtime，没变就跳过。

用法:
  python3 ai_chat_export.py                  # 全部
  python3 ai_chat_export.py --claude-only
  python3 ai_chat_export.py --codex-only
"""
import argparse
import glob
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime

VAULT = os.environ.get("SHUZI_VAULT", os.path.expanduser("~/数字人生"))
WORK = os.environ.get("SHUZI_WORK", os.path.expanduser("~/wechat-export"))
MANIFEST = os.path.join(WORK, ".ai-chat-manifest.tsv")
MSG_CAP = 20_000         # 单条正文截断（字符）——检索够用，防止单条撑爆
MONTH_CAP = 1_000_000    # 单月文件上限，超出开 -partN

TAGS = {"claude": ["AI对话", "ClaudeCode"], "codex": ["AI对话", "Codex"]}


# ---------- 基础工具 ----------

def fm(context, created, tags):
    return "---\nid: %s\ncontext: %s\ncreated: %s\ntags: [%s]\n---\n\n" % (
        str(uuid.uuid4()), context, created, ", ".join(tags))


def safe(s, n=40):
    s = re.sub(r'[/\\:*?"<>|\s]+', "_", s or "")
    return s[:n] or "misc"


def parse_time(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts).astimezone()
        except Exception:
            return None
    s = str(ts)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).astimezone()
        except Exception:
            continue
    return None


def load_manifest():
    done = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2:
                    try:
                        done[parts[0]] = int(parts[1])
                    except ValueError:
                        pass
    return done


def save_manifest(done):
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        for k in sorted(done):
            f.write("%s\t%d\n" % (k, done[k]))


# ---------- 解析：Claude Code ----------

def parse_claude(path):
    """返回 [(dt, who, text)]。"""
    items = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("isSidechain"):
                continue
            if obj.get("type") not in ("user", "assistant"):
                continue
            msg = obj.get("message") or {}
            content = msg.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        parts.append(b.get("text", ""))
                text = "\n".join(p for p in parts if p)
            text = (text or "").strip()
            if not text or text.startswith("<"):
                continue
            ts = parse_time(obj.get("timestamp"))
            who = "用户" if obj["type"] == "user" else "Claude"
            items.append((ts, who, text))
    return items


def claude_project(path):
    """目录名形如 -Users-<用户名>-xxx → 还原成项目名。"""
    d = os.path.basename(os.path.dirname(path))
    if d == "subagents":
        d = os.path.basename(os.path.dirname(os.path.dirname(path)))
    d = d.lstrip("-")
    user = os.environ.get("USER") or os.path.basename(os.path.expanduser("~"))
    prefix = "Users-{}-".format(user)
    if d.startswith(prefix):
        d = d[len(prefix):]
    d = d.replace("-", " ").strip()
    return d or "misc"


# ---------- 解析：Codex ----------

def parse_codex(path):
    """返回 ([(dt, who, text)], project)。"""
    items = []
    project = "misc"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("type")
            ts = parse_time(obj.get("timestamp"))
            payload = obj.get("payload") or {}
            if t == "session_meta":
                cwd = (payload.get("cwd") or "").rstrip("/")
                if cwd:
                    project = os.path.basename(cwd) or "misc"
            elif t == "response_item" and payload.get("type") == "message":
                role = payload.get("role", "assistant")
                parts = []
                for b in payload.get("content") or []:
                    if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text"):
                        parts.append(b.get("text", ""))
                text = "\n".join(x for x in parts if x).strip()
                if text:
                    items.append((ts, "用户" if role == "user" else "Codex", text))
            elif t == "event_msg" and payload.get("type") == "user_message":
                text = (payload.get("message") or "").strip()
                if text and not text.startswith("<"):
                    items.append((ts, "用户", text))
    # 去重：event_msg 与 response_item 常双记同一条用户输入
    seen = set()
    uniq = []
    for dt, who, text in items:
        k = (who, text[:500])
        if k in seen:
            continue
        seen.add(k)
        uniq.append((dt, who, text))
    return uniq, project


# ---------- 写入 ----------

def write_items(source, project, items):
    """按月聚合追加写入。返回写入条数。"""
    if not items:
        return 0
    items.sort(key=lambda x: (x[0] is None, x[0]))
    by_month = defaultdict(list)
    for dt, who, text in items:
        key = dt.strftime("%Y-%m") if dt else "unknown"
        by_month[key].append((dt, who, text))

    target = os.path.join(VAULT, "raw", "chat", source, project)
    os.makedirs(target, exist_ok=True)
    n = 0
    for month in sorted(by_month):
        rows = by_month[month]
        base = os.path.join(target, "%s.md" % month)
        # 分片：超过上限就开 -part2/-part3…
        part = 1
        while os.path.exists(base) and os.path.getsize(base) > MONTH_CAP:
            part += 1
            base = os.path.join(target, "%s-part%d.md" % (month, part))
        is_new = not os.path.exists(base) or os.path.getsize(base) == 0
        with open(base, "a", encoding="utf-8") as f:
            if is_new:
                f.write(fm("%s %s" % (source, project), "%s-01" % month, TAGS[source] + [project]))
                f.write("# %s · %s\n\n" % (project, month))
            for dt, who, text in rows:
                t = dt.strftime("%m-%d %H:%M") if dt else "--"
                f.write("## %s ｜ %s\n\n%s\n\n" % (t, who, text[:MSG_CAP]))
                n += 1
    return n


# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude-only", action="store_true")
    ap.add_argument("--codex-only", action="store_true")
    args = ap.parse_args()

    done = load_manifest()
    stat_files = stat_msgs = 0

    if not args.codex_only:
        for path in sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))):
            key = path
            mtime = int(os.path.getmtime(path))
            if done.get(key) == mtime:
                continue
            items = parse_claude(path)
            if items:
                proj = claude_project(path)
                stat_msgs += write_items("claude", proj, items)
                stat_files += 1
            done[key] = mtime
        print("[ai-export] Claude Code 处理 %d 个会话" % stat_files)

    if not args.claude_only:
        n_files = 0
        for path in sorted(glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/rollout-*.jsonl"))):
            key = path
            mtime = int(os.path.getmtime(path))
            if done.get(key) == mtime:
                continue
            items, proj = parse_codex(path)
            if items:
                stat_msgs += write_items("codex", safe(proj), items)
                n_files += 1
            done[key] = mtime
        print("[ai-export] Codex 处理 %d 个会话" % n_files)

    save_manifest(done)
    print("[ai-export] 共写入 %d 条消息 → %s" % (stat_msgs, os.path.join(VAULT, "raw", "chat")))
    print("[ai-export] 提示: 之后跑 qkb ingest && qkb embed 建索引；"
          "LLM 提炼（concepts/sources）按需挑选重要会话，不必全量")


if __name__ == "__main__":
    main()
