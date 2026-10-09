#!/usr/bin/env python3
"""
macOS 版 Config.Cipher 只读扫描 —— 不用断点/hook/重启，不会让微信崩溃。

原理（源自 sunhanaix/pc_wechat_exp 的 config_cipher_extract.py，Windows 版）：
  WeChat 4.1+ 内存里不再有明文 `x'<64hex key><32hex salt>'`，但 WCDB 保留一个
  `com.Tencent.WCDB.Config.Cipher` 对象，其配置 blob 被【固定 32 字节掩码】XOR
  混淆，解混淆后即得到每个库的 x'<hex>' 字面量。

Windows 版是「定位对象 → 按固定偏移取 blob」；macOS 布局不同，这里改用更稳的
做法：对每个掩码相位，直接在内存里搜「XOR 后的 x' 两字节模式」，命中处就地解
混淆、先用 10 个 hex 字符快速过滤，再走 HMAC 验真。

只做 ReadMemory（停止态），不设任何断点。
"""
import hashlib
import hmac
import lldb
import os
import struct
import time

PAGE = 4096
MASK = bytes.fromhex(
    "d2c7442458020000004889442450488b"
    "450048844c2448488944254048584c24"
)
assert len(MASK) == 32
NAME_ANCHOR = b"com.Tencent.WCDB.Config.Cipher"

_pages = {}      # basename -> page1
_found = {}
_out = None
_t0 = 0
_stats = {"bytes": 0, "regions": 0, "hits": 0, "anchors": 0}


def _is_hex(c):
    return (48 <= c <= 57) or (97 <= c <= 102) or (65 <= c <= 70)


def _mac_ok(key, page1):
    salt = page1[:16]
    mk = hashlib.pbkdf2_hmac("sha512", key, bytes(b ^ 0x3A for b in salt), 2, 32)
    h = hmac.new(mk, page1[16:PAGE - 80 + 16], hashlib.sha512)
    h.update(struct.pack("<I", 1))
    return h.digest() == page1[PAGE - 64:]


def _test_hex(hx, phase):
    if len(hx) < 64 or len(hx) % 2:
        return
    try:
        key = bytes.fromhex(hx[:64])
    except ValueError:
        return
    _stats["hits"] += 1
    for name, page1 in _pages.items():
        if name in _found:
            continue
        try:
            if _mac_ok(key, page1):
                _found[name] = key.hex()
                with open(_out, "a") as f:
                    f.write(key.hex() + "\n")
                print("KEY!! %s = %s  (phase=%d)" % (name, key.hex(), phase), flush=True)
        except Exception:
            pass


def _scan(buf, phase):
    """搜相位 phase 下被掩码混淆的 `x'`，命中再解混淆取 hex。"""
    m = [MASK[(phase + i) % 32] for i in range(208)]
    pat = bytes([0x78 ^ m[0], 0x27 ^ m[1]])
    n = len(buf)
    s = 0
    while True:
        i = buf.find(pat, s)
        if i < 0:
            return
        s = i + 2
        if i + 12 > n:
            return
        # 快速筛：紧跟 10 个 hex 字符
        ok = True
        for k in range(2, 12):
            if not _is_hex(buf[i + k] ^ m[k]):
                ok = False
                break
        if not ok:
            continue
        # 完整解混淆直到收尾单引号
        out = bytearray()
        for k in range(2, 200):
            if i + k >= n:
                break
            c = buf[i + k] ^ m[k]
            if c == 0x27:
                break
            out.append(c)
        if len(out) < 64:
            continue
        try:
            hx = out.decode("ascii")
        except UnicodeDecodeError:
            continue
        _test_hex(hx, phase)


def wxcc(debugger, command, result, internal_dict):
    global _out, _t0
    args = command.split()
    if len(args) < 3:
        print("usage: wxcc <pid> <out> <db_path> ...")
        return
    pid = int(args[0])
    _out = os.path.abspath(os.path.expanduser(args[1]))
    for p in args[2:]:
        p = os.path.abspath(os.path.expanduser(p))
        try:
            with open(p, "rb") as f:
                page1 = f.read(PAGE)
        except OSError:
            continue
        if len(page1) >= PAGE:
            _pages[os.path.basename(p)] = page1
    print("targets=%d: %s" % (len(_pages), ",".join(sorted(_pages))), flush=True)

    debugger.SetAsync(True)
    target = debugger.CreateTarget("")
    err = lldb.SBError()
    process = target.Attach(lldb.SBAttachInfo(pid), err)
    if not err.Success() or not process or not process.IsValid():
        print("ATTACH_FAIL %s" % err.GetCString())
        return
    print("ATTACHED pid=%d" % pid, flush=True)

    regions = process.GetMemoryRegions()
    n = regions.GetSize()
    blocks = []
    for idx in range(n):
        info = lldb.SBMemoryRegionInfo()
        if not regions.GetMemoryRegionAtIndex(idx, info) or not info.IsReadable():
            continue
        base = info.GetRegionBase()
        size = info.GetRegionEnd() - base
        if size > 0 and base != 0 and not info.IsExecutable():
            blocks.append((base, size))
    print("readable regions=%d" % len(blocks), flush=True)

    _t0 = time.time()
    CHUNK = 1 << 21
    for bi, (base, size) in enumerate(blocks):
        off = 0
        while off < size:
            cs = min(CHUNK, size - off)
            e = lldb.SBError()
            data = process.ReadMemory(base + off, cs, e)
            if e.Success() and data:
                _stats["bytes"] += len(data)
                if NAME_ANCHOR in data:
                    _stats["anchors"] += 1
                for ph in range(32):
                    _scan(data, ph)
            off += cs
        if bi % 150 == 0:
            print("  ..%d/%d %.0fMB anchors=%d hits=%d %.0fs" % (
                bi, len(blocks), _stats["bytes"] / 1048576.0,
                _stats["anchors"], _stats["hits"], time.time() - _t0), flush=True)

    process.Detach()
    print("DONE found=%d/%d scanned=%.0fMB anchors=%d hits=%d %.0fs" % (
        len(_found), len(_pages), _stats["bytes"] / 1048576.0,
        _stats["anchors"], _stats["hits"], time.time() - _t0), flush=True)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f scan_cc.wxcc wxcc")
