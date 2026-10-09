"""Command-line interface.

Typical flow (see README for the prerequisites: SIP off + WeChat re-signed):

    # 1. copy the live data out (fast APFS clone), then capture keys while WeChat runs
    python -m wxexport copy
    ./scripts/capture-keys.sh 180
    # 2. turn the captured keys into a keyed manifest, decrypt, and export
    python -m wxexport build
"""
import argparse
import os
import subprocess
import sys

from . import detect, match, decrypt, nameindex, export

DEFAULT_WORK = os.path.expanduser("~/wx-export")


def _paths(args):
    work = os.path.abspath(os.path.expanduser(args.work))
    return {
        "work": work,
        "data": args.data_dir or os.path.join(work, "xwechat_files"),
        "raw": os.path.join(work, "rawkeys.txt"),
        "keys": os.path.join(work, "keys.json"),
        "decrypted": os.path.join(work, "decrypted"),
        "namemap": os.path.join(work, "namemap.json"),
        "export": os.path.join(work, "export"),
    }


def cmd_copy(args):
    p = _paths(args)
    src = detect.find_data_dir()
    os.makedirs(p["work"], exist_ok=True)
    dst = os.path.join(p["work"], "xwechat_files")
    print("cloning %s -> %s (APFS clone, near-instant)" % (src, dst))
    # -c uses clonefile(2) on APFS: copy-on-write, no extra disk used
    subprocess.check_call(["cp", "-Rc", src, p["work"]])
    print("done. quit WeChat before this step for a consistent copy.")


def cmd_match(args):
    p = _paths(args)
    res, missing = match.match(p["data"], p["raw"], p["keys"])
    print("matched %d databases -> %s" % (len(res), p["keys"]))
    if missing:
        print("no key yet for: %s" % ", ".join(missing))


def cmd_decrypt(args):
    p = _paths(args)
    ok, fail = decrypt.run(p["data"], p["keys"], p["decrypted"])
    print("decrypted %d databases (%d failed) -> %s" % (ok, fail, p["decrypted"]))
    if fail or not ok:
        raise SystemExit(1)  # Do not export stale/partial plaintext as a complete run.


def cmd_export(args):
    p = _paths(args)
    me = detect.find_account_wxid(p["data"])
    nameindex.build(p["decrypted"], p["namemap"])
    n, total = export.run(p["decrypted"], p["namemap"], me, p["export"])
    print("exported %d conversations, %d messages -> %s" % (n, total, p["export"]))


def cmd_build(args):
    cmd_match(args)
    cmd_decrypt(args)
    cmd_export(args)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wxexport",
                                 description="Decrypt and export WeChat 4.x chat history on macOS.")
    ap.add_argument("--work", default=DEFAULT_WORK, help="working directory (default: ~/wx-export)")
    ap.add_argument("--data-dir", default=None,
                    help="path to an xwechat_files copy (default: <work>/xwechat_files)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (
        ("copy", cmd_copy, "clone the live WeChat data dir into the working dir"),
        ("match", cmd_match, "attribute captured raw keys to databases -> keys.json"),
        ("decrypt", cmd_decrypt, "decrypt databases we hold keys for"),
        ("export", cmd_export, "render decrypted messages to text/html/csv"),
        ("build", cmd_build, "match + decrypt + export"),
    ):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(func=fn)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
