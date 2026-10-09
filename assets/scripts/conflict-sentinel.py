#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冲突哨兵：扫描 vault 里的 *.sync-conflict-* 冲突副本，
按「修改时间最新者为正本」自动收口；旧版归档到 vault 之外（不参与同步）。

- 正本 = 冲突文件与正本文件中 mtime 最新者
- 其余版本复制到 ARCHIVE（vault 外，避免再次同步），再删除冲突副本
- 无冲突时不输出（automation 空输出不推送）
"""
import os
import re
import shutil
import time

VAULT = os.path.expanduser("~/数字人生")
ARCHIVE = os.path.expanduser("~/.wxexport/_conflict-archive")
PAT = re.compile(r"^(?P<base>.+?)\.sync-conflict-\d{8}-\d{6}-[A-Z0-9]+(?P<ext>\.[^.]+)?$")

def main():
    resolved = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in (".stversions", ".git")]
        for fn in files:
            if ".sync-conflict-" not in fn:
                continue
            m = PAT.match(fn)
            if not m:
                continue
            conflict = os.path.join(root, fn)
            canonical = os.path.join(root, m.group("base") + (m.group("ext") or ""))
            cands = [p for p in (canonical, conflict) if os.path.exists(p)]
            if not cands:
                continue
            newest = max(cands, key=lambda p: os.path.getmtime(p))
            stamp = time.strftime("%Y%m%d-%H%M%S")
            os.makedirs(ARCHIVE, exist_ok=True)
            for p in cands:
                if p == newest:
                    continue
                rel = os.path.relpath(p, VAULT).replace(os.sep, "__")
                try:
                    shutil.copy2(p, os.path.join(ARCHIVE, "%s__%s" % (stamp, rel)))
                except OSError:
                    pass
                try:
                    os.remove(p)
                except OSError:
                    pass
            # 若最新者是冲突副本 → 覆盖回正本
            if newest != canonical:
                shutil.copy2(newest, canonical)
                try:
                    os.remove(newest)
                except OSError:
                    pass
            resolved.append((os.path.relpath(canonical, VAULT), newest == conflict))
    if resolved:
        print("🛡️ 冲突哨兵：自动解决 %d 处（按修改时间最新）" % len(resolved))
        for rel, took_conflict in resolved:
            print(" - %s%s" % (rel, "（采信后续版本）" if took_conflict else "（保留正本）"))
        print("旧版已归档：%s" % ARCHIVE)

if __name__ == "__main__":
    main()
