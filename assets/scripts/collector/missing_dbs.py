#!/usr/bin/env python3
"""
列出【当前没有密钥】的加密库的绝对路径（每行一个）。

流程：读 rawkeys.txt 的全部候选密钥，对每个 .db 用 page-1 HMAC 验真，
都不匹配就说明缺密钥 —— 输出其绝对路径，供 Config.Cipher 只读扫描补齐。
"""
import glob
import hashlib
import hmac
import os
import struct

PAGE = 4096
WORK = os.path.expanduser("~/wx-export")
ACC = os.environ.get("WX_ACCOUNT_DIR") or (
    glob.glob(os.path.expanduser(
        "~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/*")) or [""])[0]
SNAP = os.path.join(WORK, "xwechat_files", os.path.basename(ACC), "db_storage")
RAW = os.path.join(WORK, "rawkeys.txt")


def mac_ok(key, page1):
    salt = page1[:16]
    mk = hashlib.pbkdf2_hmac("sha512", key, bytes(b ^ 0x3A for b in salt), 2, 32)
    h = hmac.new(mk, page1[16:PAGE - 80 + 16], hashlib.sha512)
    h.update(struct.pack("<I", 1))
    return h.digest() == page1[PAGE - 64:]


keys = []
if os.path.exists(RAW):
    seen = set()
    for line in open(RAW):
        h = line.strip()
        if len(h) == 64 and h not in seen:
            seen.add(h)
            try:
                keys.append(bytes.fromhex(h))
            except ValueError:
                pass

# 只关心「大库」：小的辅助库（chatbot / general / solitaire / third_app_icon /
# weclaw 等）微信基本不打开，拿不到密钥也无所谓，避免每次刷新都白跑一次扫描。
MIN_BYTES = int(os.environ.get("WX_MISSING_MIN_MB", "8")) * 1024 * 1024

for p in sorted(glob.glob(os.path.join(SNAP, "**", "*.db"), recursive=True)):
    try:
        if os.path.getsize(p) < max(PAGE, MIN_BYTES):
            continue
        with open(p, "rb") as f:
            page1 = f.read(PAGE)
    except OSError:
        continue
    if page1[:15] == b"SQLite format 3":
        continue
    for k in keys:
        try:
            if mac_ok(k, page1):
                break
        except Exception:
            pass
    else:
        print(p)
