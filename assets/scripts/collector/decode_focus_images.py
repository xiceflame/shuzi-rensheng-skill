#!/usr/bin/env python3
"""
解码关注会话最近 N 天的聊天图片（微信 4.x V2 .dat）→ focus-images/

为什么需要：群里的日程/排班表常以图片形式发，只有把图片解出来，
整理 agent 才能读到「谁被打勾」。

依赖：~/wechat-export-macos/WCD/tools/wechat-decrypt（Bryan-Cyf/WeChatDaily）
必须在有 FDA 的进程里跑（要读微信容器里的 .dat 与 message_resource 的原始库）。

用法: python3 decode_focus_images.py [天数=7] [上限=400]
输出: ~/wx-export/focus-images/<YYYY-MM-DD_HHMM>_<会话名>_<md5前8>.<ext>
"""
import glob
import json
import glob
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

TOOL = os.path.expanduser("~/wechat-export-macos/WCD/tools/wechat-decrypt")
sys.path.insert(0, TOOL)
from decode_image import ImageResolver  # noqa: E402

WORK = os.path.expanduser("~/wx-export")
DEC = os.path.join(WORK, "decrypted")
DBS = os.path.join(WORK, "xwechat_files")
NAMEMAP = os.path.join(WORK, "namemap.json")
OUT = os.path.join(WORK, "focus-images")
FOCUS_FILE = os.path.expanduser("~/.wxexport/focus.txt")
TOOL_CFG = os.path.join(TOOL, "config.json")

BASE_DIR = os.path.join(
    os.path.expanduser("~"),
    os.environ.get("WX_ACCOUNT_DIR") or _detect_account(),
)

IMG_TYPE = 3


class DecryptedCache:
    """给 ImageResolver 用的最小 shim：把相对路径映射到已解密的明文库。"""

    def get(self, rel):
        p = os.path.join(DEC, rel)
        return p if os.path.exists(p) else None


def load_focus():
    """返回匹配函数（精确优先，行尾 * 为包含匹配）。"""
    try:
        from focus_match import matcher as _mk
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from focus_match import matcher as _mk
    return _mk()


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 400

    focus = load_focus()

    cfg = json.load(open(TOOL_CFG, encoding="utf-8"))
    aes_key = cfg.get("image_aes_key")
    xor_key = cfg.get("image_xor_key", 0x88)
    if not aes_key:
        print("[img] config.json 缺少 image_aes_key，跳过")
        return

    os.makedirs(OUT, exist_ok=True)
    nm = json.load(open(NAMEMAP, encoding="utf-8"))
    NAMES, MD5MAP = nm["names"], nm["md5map"]

    resolver = ImageResolver(BASE_DIR, OUT, DecryptedCache(), aes_key=aes_key, xor_key=xor_key)

    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
    dbs = sorted(glob.glob(os.path.join(DEC, "message", "message_[0-9]*.db")))

    done = 0
    ok = 0
    for db in dbs:
        if ok >= limit:
            break
        con = sqlite3.connect(db)
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
        con.close()
        for t in tables:
            if ok >= limit:
                break
            md5 = t[4:]
            user = MD5MAP.get(md5, "")
            if not user:
                continue
            name = NAMES.get(user, user)
            if not focus(name):
                continue
            con = sqlite3.connect(db)
            try:
                rows = con.execute(
                    'SELECT local_id, create_time FROM "%s" '
                    'WHERE (local_type %% 4294967296) = ? AND create_time >= ? '
                    'ORDER BY create_time DESC' % t, (IMG_TYPE, cutoff)).fetchall()
            except Exception:
                rows = []
            con.close()
            for local_id, ct in rows:
                if ok >= limit:
                    break
                done += 1
                r = resolver.decode_image(user, local_id)
                if r.get("success"):
                    ext = r.get("format", "jpg")
                    stamp = datetime.fromtimestamp(ct).strftime("%Y-%m-%d_%H%M")
                    safe = re.sub(r'[/\\:*?"<>|\s]', "_", name)[:40]
                    new = os.path.join(
                        OUT, "%s_%s_%s.%s" % (stamp, safe, (r.get("md5") or "x")[:8], ext))
                    try:
                        os.rename(r["path"], new)
                    except OSError:
                        pass
                    ok += 1
    print("[img] 尝试 %d 张，成功解出 %d 张 -> %s" % (done, ok, OUT))


if __name__ == "__main__":
    main()
