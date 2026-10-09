"""Decrypt the databases we hold keys for into a plaintext tree."""
import json
import os
import sqlite3

from . import detect
from .crypto import decrypt_db, PAGE


def run(data_dir, keys_path, out_dir):
    keys = json.load(open(keys_path))
    dbmap = {rel: path for rel, path in detect.iter_encrypted_dbs(data_dir)}
    ok, fail = 0, 0
    for rel, info in keys.items():
        path = dbmap.get(rel)
        if not path:
            continue
        key = bytes.fromhex(info["enc_key"])
        reserve = info.get("reserve", 80)
        outp = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        try:
            data = open(path, "rb").read()
            plain = decrypt_db(data, key, reserve)
            with open(outp, "wb") as fh:
                fh.write(plain)
            # sanity check
            con = sqlite3.connect(outp)
            con.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            con.close()
            ok += 1
        except Exception as e:
            print("  FAIL %s: %s" % (rel, e))
            fail += 1
    return ok, fail
