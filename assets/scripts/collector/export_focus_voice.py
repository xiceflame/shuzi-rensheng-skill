#!/usr/bin/env python3
"""
导出关注会话的语音（默认最近 365 天）→ 解码为 mp3 + 清单。

微信 4.x 语音存于 media_N.db 的 VoiceInfo 表（voice_data = 明文 SILK v3）。
链路：VoiceInfo.voice_data → 去掉微信多出的 \\x02 前缀 → pilk 解 SILK 为 PCM
      → 写 WAV → ffmpeg 转 mp3(单声道 16kHz 32kbps)

归属：VoiceInfo.chat_name_id 是该库 Name2Id 的 rowid（= 会话），
      local_id 与消息表的 local_id 对应。

用法: python3 export_focus_voice.py [天数=365] [上限=0=不限]
输出: ~/wx-export/focus-voice/*.mp3  +  _manifest.tsv
"""
import glob
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from focus_match import matcher  # noqa: E402

import pilk  # noqa: E402

WORK = os.path.expanduser("~/wx-export")
DEC = os.path.join(WORK, "decrypted")
NAMEMAP = os.path.join(WORK, "namemap.json")
OUT = os.path.join(WORK, "focus-voice")
FFMPEG = "/opt/homebrew/bin/ffmpeg"
VOICE_TYPE = 34
RATE = 24000


def _name2id(con):
    """rowid -> username"""
    m = {}
    try:
        con.text_factory = bytes
        for rid, uname in con.execute("SELECT rowid, user_name FROM Name2Id"):
            m[rid] = uname.decode("utf-8", "replace") if isinstance(uname, bytes) else uname
    except Exception:
        pass
    return m


def collect_targets(focus):
    """返回 {username: display} （关注会话）。"""
    nm = json.load(open(NAMEMAP, encoding="utf-8"))
    NAMES, MD5MAP = nm["names"], nm["md5map"]
    out = {}
    for _md5, user in MD5MAP.items():
        n = NAMES.get(user, user)
        if user and focus(n):
            out[user] = n
    return out


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    focus = matcher()
    os.makedirs(OUT, exist_ok=True)
    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())

    targets = collect_targets(focus)
    print("[voice] 关注会话 %d 个（近 %d 天）" % (len(targets), days))

    # 2) 从 media 库取 voice_data 并解码
    manifest = []
    done = 0
    for db in sorted(glob.glob(os.path.join(DEC, "message", "media_[0-9]*.db"))):
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        id2user = _name2id(con)
        # chat_name_id -> username；只看关注会话
        cid2user = {rid: u for rid, u in id2user.items() if u in targets}
        if not cid2user:
            con.close()
            continue
        q = ("SELECT chat_name_id, local_id, create_time, voice_data, data_index "
             "FROM VoiceInfo WHERE chat_name_id IN (%s)" % ",".join(str(i) for i in cid2user))
        try:
            rows = con.execute(q).fetchall()
        except Exception as e:
            print("[voice] %s 查询失败: %s" % (os.path.basename(db), e))
            con.close()
            continue
        for cid, lid, ct, vd, di in rows:
            if limit and done >= limit:
                break
            if ct is not None and ct < cutoff:
                continue
            if di not in (None, "0", 0, b"0"):
                continue
            user = cid2user.get(cid)
            name = targets.get(user)
            if not name or not vd:
                continue
            raw = bytes(vd)
            if raw[:1] == b"\x02" and raw[1:10] == b"#!SILK_V3":
                raw = raw[1:]
            if raw[:9] != b"#!SILK_V3":
                continue
            tmpd = tempfile.mkdtemp()
            sp = os.path.join(tmpd, "a.silk")
            pp = os.path.join(tmpd, "a.pcm")
            with open(sp, "wb") as f:
                f.write(raw)
            try:
                pilk.decode(sp, pp, RATE)
            except Exception:
                continue
            # PCM -> WAV
            wp = os.path.join(tmpd, "a.wav")
            pcm = open(pp, "rb").read()
            with wave.open(wp, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm)
            stamp = datetime.fromtimestamp(ct or 0).strftime("%Y-%m-%d_%H%M%S")
            safe = re.sub(r'[/\\:*?"<>|\s]', "_", name)[:40]
            mp3 = os.path.join(OUT, "%s_%s_%s.mp3" % (stamp, safe, lid))
            if os.path.exists(mp3) and os.path.getsize(mp3) > 0:
                continue  # 增量：已导出过就跳过
            r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", wp,
                                "-ac", "1", "-ar", "16000", "-b:a", "32k", mp3],
                               capture_output=True)
            for f in (sp, pp, wp):
                try:
                    os.unlink(f)
                except OSError:
                    pass
            try:
                os.rmdir(tmpd)
            except OSError:
                pass
            if r.returncode == 0:
                done += 1
                manifest.append((stamp, name, lid, len(raw), os.path.basename(mp3)))
            if done % 200 == 0 and done:
                print("[voice] 已解码 %d 条..." % done)
        con.close()
        if limit and done >= limit:
            break

    with open(os.path.join(OUT, "_manifest.tsv"), "w", encoding="utf-8") as f:
        f.write("时间\t会话\tlocal_id\tsilk字节\t文件\n")
        for row in sorted(manifest):
            f.write("\t".join(str(x) for x in row) + "\n")
    print("[voice] 解码完成 %d 条 -> %s" % (done, OUT))


if __name__ == "__main__":
    main()
