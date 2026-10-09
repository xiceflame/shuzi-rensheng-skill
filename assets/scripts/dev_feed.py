#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发动态生成器：把每天的代码仓活动变成 chat-ingest 可读的数据源。

扫描配置的仓库（git log 当天提交 + 分支 + 变更统计），
写 ~/wechat-export/dev-feed/YYYY-MM-DD.md —— 与 focus/ 同级，
digest（chat-ingest）把它并入「我的每一天」的开发小节。

用法: python3 dev_feed.py [日期，默认今天]
仓库列表: 环境变量 SHUZI_REPOS（冒号分隔），默认 ~/projects
"""
import os
import subprocess
import sys
from datetime import date, datetime

WORK = os.environ.get("SHUZI_WORK", os.path.expanduser("~/wechat-export"))
REPOS = os.environ.get("SHUZI_REPOS", os.path.expanduser("~/projects")).split(":")  # 配置:export SHUZI_REPOS="仓库A:仓库B"


def git(repo, args):
    try:
        r = subprocess.run(["git", "-C", repo] + args,
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def all_commit_days(repo):
    out = git(repo, ["log", "--pretty=format:%ad", "--date=short"])
    days = sorted(set(l.strip() for l in out.splitlines() if l.strip()), reverse=True)
    return days


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        n = 0
        for repo in [os.path.expanduser(r.strip()) for r in REPOS]:
            if not os.path.isdir(repo):
                continue
            for day in all_commit_days(repo):
                out = os.path.join(WORK, "dev-feed", "%s.md" % day)
                if not os.path.exists(out):
                    render_day(repo, day, out)
                    n += 1
        print("[dev-feed] 回填完成：新增 %d 天 → %s" % (n, os.path.join(WORK, "dev-feed")))
        return
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    out = os.path.join(WORK, "dev-feed", "%s.md" % day)
    render_day(None, day, out, all_repos=True)
    print("[dev-feed] %s → %s" % (day, out))


def render_day(repo, day, out, all_repos=False):
    lines = ["---",
             "id: dev-feed-%s" % day,
             "context: 开发动态",
             "created: %s" % day,
             "tags: [开发动态, 开发]",
             "---", "",
             "# 开发动态 · %s" % day, ""]
    total = 0
    repos = REPOS if all_repos else [repo]
    for repo in repos:
        repo = os.path.expanduser(repo.strip())
        if not os.path.isdir(repo):
            continue
        name = os.path.basename(repo.rstrip("/"))
        branch = git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
        log = git(repo, ["log", "--since=%s 00:00" % day, "--until=%s 23:59" % day,
                         "--pretty=format:%h|%s|%an"] )
        lines.append("## %s（%s）" % (name, branch or "?"))
        lines.append("")
        commits = [l for l in log.splitlines() if l.strip()]
        if commits:
            lines.append("**提交 %d 个：**" % len(commits))
            for c in commits:
                parts = c.split("|", 2)
                if len(parts) == 3:
                    lines.append("- `%s` %s（%s）" % (parts[0], parts[1], parts[2]))
        else:
            lines.append("（当天无提交）")
        lines.append("")
        total += len(commits)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return total


if __name__ == "__main__":
    main()
