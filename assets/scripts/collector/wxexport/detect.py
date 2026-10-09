"""Locate the WeChat 4.x data directory, the logged-in account, and its databases.

Everything downstream is derived from a single ``xwechat_files`` directory — either
the live container or a copy of it. Nothing here is account-specific at the code
level; the account wxid is discovered from the directory layout.
"""
import os
import glob

# Default location of the live container on macOS (WeChat 4.x).
LIVE_CONTAINER = os.path.expanduser(
    "~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
)


def find_data_dir(explicit=None):
    """Return the xwechat_files directory to work from."""
    if explicit:
        d = os.path.abspath(os.path.expanduser(explicit))
        if os.path.isdir(d):
            return d
        raise FileNotFoundError("xwechat_files not found at %s" % d)
    if os.path.isdir(LIVE_CONTAINER):
        return LIVE_CONTAINER
    raise FileNotFoundError(
        "Could not find xwechat_files. Pass --data-dir pointing at a copy of\n"
        "  ~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
    )


def find_account_wxid(data_dir):
    """Discover the logged-in account's wxid from the directory layout.

    WeChat stores it two ways; we try both:
      xwechat_files/all_users/login/<wxid>/
      xwechat_files/<wxid>_<hash>/db_storage/
    """
    login = glob.glob(os.path.join(data_dir, "all_users", "login", "*"))
    for p in login:
        name = os.path.basename(p)
        if name.startswith("wxid_") or name:
            return name
    for p in glob.glob(os.path.join(data_dir, "*", "db_storage")):
        acct = os.path.basename(os.path.dirname(p))
        # strip the trailing _<hash> that WeChat appends to the account folder
        return acct.rsplit("_", 1)[0] if "_" in acct else acct
    return ""


def find_account_dir(data_dir):
    """Return the per-account folder that contains db_storage/."""
    hits = glob.glob(os.path.join(data_dir, "*", "db_storage"))
    if not hits:
        raise FileNotFoundError("No db_storage/ under %s" % data_dir)
    return os.path.dirname(hits[0])


def iter_encrypted_dbs(data_dir):
    """Yield (relpath_under_db_storage, absolute_path) for every encrypted .db."""
    for f in sorted(glob.glob(os.path.join(data_dir, "*", "db_storage", "**", "*.db"),
                              recursive=True)):
        try:
            with open(f, "rb") as fh:
                hdr = fh.read(16)
        except OSError:
            continue
        if len(hdr) < 16 or hdr[:15] == b"SQLite format 3":
            continue  # unencrypted or too small
        rel = f.split("db_storage" + os.sep, 1)[1]
        yield rel.replace(os.sep, "/"), f
