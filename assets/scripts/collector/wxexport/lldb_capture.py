"""lldb-loaded module that captures WeChat's SQLCipher keys from live memory.

WeChat 4.1.x on macOS hands the raw 32-byte per-database AES key to Apple's
CommonCrypto ``CCCryptorCreate`` every time it decrypts database pages. We set a
breakpoint there, read the key argument (arm64: x3 = key pointer, x4 = key length),
and record every distinct 32-byte key we see. No fixed offsets, no version-specific
struct layouts — it rides on the stable CommonCrypto ABI.

Why this and not a raw memory scan: on 4.1.x the key is not stored as the old
``x'<hex>'`` pragma text, and the region holding it is unreadable through the
mach_vm API that older tools use. lldb's debugserver can read it, and the
breakpoint sidesteps the search entirely.

Usage (WeChat must be ad-hoc re-signed and SIP disabled — see scripts/):
    sudo lldb --batch \
        -o "command script import wxexport/lldb_capture.py" \
        -o "wxcapture <pid> <seconds> <out_file>" \
        -o "quit"
"""
import lldb
import os
import time

_seen = set()
_out_path = None


def _grab(frame):
    """On a CCCryptorCreate hit, dump 32-byte keys to the output file."""
    try:
        klen = frame.FindRegister("x4").GetValueAsUnsigned()
        if klen != 32:
            return
        kptr = frame.FindRegister("x3").GetValueAsUnsigned()
        if not kptr:
            return
        err = lldb.SBError()
        data = frame.GetThread().GetProcess().ReadMemory(kptr, 32, err)
        if err.Success() and data and len(data) == 32:
            h = data.hex()
            if h not in _seen:
                _seen.add(h)
                with open(_out_path, "a") as f:
                    f.write(h + "\n")
    except Exception:
        pass


def _cb(frame, bp_loc, internal_dict):
    _grab(frame)
    return False  # never stop; auto-continue


def wxcapture(debugger, command, result, internal_dict):
    global _out_path
    args = command.split()
    if len(args) < 3:
        print("usage: wxcapture <pid> <seconds> <out_file>")
        return
    pid = int(args[0])
    dur = int(args[1])
    _out_path = os.path.abspath(os.path.expanduser(args[2]))

    debugger.SetAsync(True)
    target = debugger.CreateTarget("")
    err = lldb.SBError()
    process = target.Attach(lldb.SBAttachInfo(pid), err)
    if not err.Success() or not process or not process.IsValid():
        print("ATTACH_FAIL %s" % err.GetCString())
        return
    print("ATTACHED pid=%d" % process.GetProcessID())

    bp = target.BreakpointCreateByName("CCCryptorCreate")
    bp.SetScriptCallbackFunction("lldb_capture._cb")
    print("BP CCCryptorCreate locations=%d" % bp.GetNumLocations())

    listener = debugger.GetListener()
    process.Continue()
    deadline = time.time() + dur
    last = 0
    while time.time() < deadline:
        ev = lldb.SBEvent()
        if listener.WaitForEvent(1, ev) and lldb.SBProcess.EventIsProcessEvent(ev):
            st = lldb.SBProcess.GetStateFromEvent(ev)
            if st == lldb.eStateExited:
                print("PROC_EXITED")
                return
            if st == lldb.eStateStopped:
                process.Continue()
        if len(_seen) != last:
            print("KEYS %d" % len(_seen))
            last = len(_seen)
    # graceful detach — never leave WeChat killed
    process.Stop()
    time.sleep(0.3)
    process.Detach()
    print("DETACHED keys=%d" % len(_seen))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f lldb_capture.wxcapture wxcapture")
