"""关注名单匹配（精确优先）。

focus.txt 规则：
  - 不以 # 开头的行是名单项
  - **行尾带 `*` = 包含匹配**（大小写不敏感）
  - 其它 = **精确匹配会话名**（推荐，避免「李明」误带「李明浩」）

用法：
    from focus_match import matcher
    hit = matcher()
    if hit("李明"): ...
"""
import os

FOCUS_FILE = os.path.expanduser("~/.wxexport/focus.txt")


def load():
    exact, partial = set(), []
    if not os.path.exists(FOCUS_FILE):
        return exact, partial
    with open(FOCUS_FILE, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.endswith("*"):
                partial.append(s[:-1].strip().lower())
            else:
                exact.add(s)
    return exact, partial


def matcher():
    exact, partial = load()

    def m(name):
        if not name:
            return False
        if name in exact:
            return True
        ln = name.lower()
        return any(k in ln for k in partial)

    return m
