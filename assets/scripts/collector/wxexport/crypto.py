"""SQLCipher 4 / WCDB page crypto used by WeChat 4.x on macOS.

Parameters (confirmed against WeChat 4.1.11):
    cipher      AES-256-CBC
    KDF         raw key (the 32 bytes are used directly, no PBKDF2 on the main key)
    HMAC        HMAC-SHA512, mac key = PBKDF2-HMAC-SHA512(key, salt ^ 0x3a, 2)
    page size   4096
    reserve     80  (IV 16 + HMAC 64), salt = first 16 bytes of the file
"""
import hashlib
import hmac
import struct
from Crypto.Cipher import AES

PAGE = 4096
SQLITE_HDR = b"SQLite format 3\x00"
DEFAULT_RESERVE = 80
RESERVE_CANDIDATES = (80, 48, 16, 64, 32)


def mac_key(key, salt):
    return hashlib.pbkdf2_hmac("sha512", key, bytes(b ^ 0x3a for b in salt), 2, dklen=32)


def verify_key(key, page1, reserve):
    """Return True if *key* decrypts page 1 under *reserve* (HMAC check)."""
    if len(page1) < PAGE:
        return False
    salt = page1[:16]
    mk = mac_key(key, salt)
    hdata = page1[16:PAGE - reserve + 16]
    want = hmac.new(mk, hdata + struct.pack("<I", 1), hashlib.sha512).digest()
    return want == page1[PAGE - reserve + 16:PAGE - reserve + 16 + 64]


def find_reserve(key, page1):
    """Return the reserve size for which *key* validates page 1, or None."""
    for r in RESERVE_CANDIDATES:
        if verify_key(key, page1, r):
            return r
    return None


def decrypt_db(data, key, reserve=DEFAULT_RESERVE):
    """Decrypt a whole SQLCipher database blob to a plaintext SQLite blob."""
    if len(key) != 32 or reserve != DEFAULT_RESERVE:
        raise ValueError("UNSUPPORTED_CIPHER_PROFILE: expected WCDB4 raw-key/4096/80")
    if not data or len(data) % PAGE:
        raise ValueError("TRUNCATED_DATABASE: incomplete cipher page")
    n = len(data) // PAGE
    mk = mac_key(key, data[:16])
    out = bytearray()
    for i in range(n):
        page = data[i * PAGE:(i + 1) * PAGE]
        start = 16 if i == 0 else 0
        authenticated = page[start:PAGE - reserve + 16] + struct.pack("<I", i + 1)
        expected = hmac.new(mk, authenticated, hashlib.sha512).digest()
        if not hmac.compare_digest(expected, page[PAGE - reserve + 16:]):
            raise ValueError("PAGE_AUTH_FAILED: page %d" % (i + 1))
        iv = page[PAGE - reserve:PAGE - reserve + 16]
        if i == 0:
            body = AES.new(key, AES.MODE_CBC, iv).decrypt(page[16:PAGE - reserve])
            out += SQLITE_HDR + body + b"\x00" * reserve
        else:
            body = AES.new(key, AES.MODE_CBC, iv).decrypt(page[:PAGE - reserve])
            out += body + b"\x00" * reserve
    return bytes(out)
