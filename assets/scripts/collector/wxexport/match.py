"""Attribute captured raw keys to individual databases and write keys.json.

Each WeChat 4.x database has its own key and its own salt (first 16 bytes of the
file). We try every captured key against every database's page 1; the one whose
HMAC verifies is that database's key.
"""
import json
import os

from . import detect
from .crypto import find_reserve, PAGE


def load_raw_keys(path):
    keys = []
    seen = set()
    with open(path) as fh:
        for line in fh:
            h = line.strip()
            if len(h) == 64 and h not in seen:
                seen.add(h)
                keys.append(bytes.fromhex(h))
    return keys


def match(data_dir, raw_keys_path, out_path):
    raw = load_raw_keys(raw_keys_path)
    result = {}
    dbs = list(detect.iter_encrypted_dbs(data_dir))
    for rel, path in dbs:
        with open(path, "rb") as fh:
            page1 = fh.read(PAGE)
        for key in raw:
            reserve = find_reserve(key, page1)
            if reserve is not None:
                result[rel] = {"enc_key": key.hex(), "reserve": reserve}
                break
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    missing = [rel for rel, _ in dbs if rel not in result]
    return result, missing
