"""Resolve Msg_<md5> table names back to human-readable contacts / groups.

Message tables are named ``Msg_<md5(username)>``. We build a username -> display
name map from contact.db / session.db, then md5 every known username so the tables
can be labelled.
"""
import hashlib
import json
import os
import sqlite3


def _q(db, sql):
    try:
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        rows = c.execute(sql).fetchall()
        c.close()
        return rows
    except Exception:
        return []


def build(decrypted_dir, out_path):
    cdb = os.path.join(decrypted_dir, "contact", "contact.db")
    sdb = os.path.join(decrypted_dir, "session", "session.db")

    names = {}

    def add(u, n):
        if not u or not n:
            return
        if u not in names or (names[u].startswith("wxid_") and not n.startswith("wxid_")):
            names[u] = n

    for tbl in ("contact", "stranger"):
        for r in _q(cdb, "SELECT username, remark, nick_name, alias FROM %s" % tbl):
            disp = ((r["remark"] or "").strip() or (r["nick_name"] or "").strip()
                    or (r["alias"] or "").strip() or r["username"])
            add(r["username"], disp)

    sessions = {}
    for r in _q(sdb, "SELECT username, summary, last_timestamp, sort_timestamp FROM SessionTable"):
        sessions[r["username"]] = {"summary": r["summary"],
                                   "ts": r["sort_timestamp"] or r["last_timestamp"]}
    for r in _q(sdb, "SELECT username, session_title FROM SessionNoContactInfoTable"):
        add(r["username"], r["session_title"])

    allusers = set(names) | set(sessions)
    for r in _q(cdb, "SELECT username FROM chat_room"):
        allusers.add(r["username"])
    md5map = {hashlib.md5(u.encode()).hexdigest(): u for u in allusers}

    json.dump({"names": names, "md5map": md5map, "sessions": {}}, open(out_path, "w"))
    return names, md5map
