#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件夹索引器：把任意文件夹的内容变成可检索的 Markdown（供 qkb 向量索引）。

对每个文件生成一个带 frontmatter 的 .md：
  文本类文件 → 直接收正文
  PDF/Office → 尝试本地抽文本（装了对应库才生效）
  其他/过大   → 只登记路径（占位条目，图谱可见、正文待补）

落点：<vault>/raw/docs-indexed/<相对路径>.md
增量：源文件 mtime+size 记录在 ~/wechat-export/.files-index-manifest.tsv

用法:
  python3 files_index.py <源目录> [--out 子目录名] [--ext .md,.py,.pdf,...]
"""
import argparse
import hashlib
import os
import sys
import uuid

VAULT = os.environ.get("SHUZI_VAULT", os.path.expanduser("~/数字人生"))
WORK = os.environ.get("SHUZI_WORK", os.path.expanduser("~/wechat-export"))
MANIFEST = os.path.join(WORK, ".files-index-manifest.tsv")

TEXT_EXTS = {".md", ".markdown", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml",
             ".py", ".js", ".ts", ".sh", ".go", ".rs", ".c", ".cpp", ".h", ".java",
             ".tex", ".bib", ".html", ".css", ".sql", ".toml", ".ini", ".cfg", ".log"}
PDF_OFFICE = {".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".obsidian", ".venv", "venv",
             ".trash", "Library", ".sync"}
MAX_BYTES = 400_000        # 单文件正文上限
PLACEHOLDER_MAX = 50_000_000  # 超过 50MB 只登记不读


def fm(context, created, tags):
    return "---\nid: %s\ncontext: %s\ncreated: %s\ntags: [%s]\n---\n\n" % (
        str(uuid.uuid4()), context, created, ", ".join(tags))


def load_manifest():
    done = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2:
                    done[parts[0]] = parts[1]
    return done


def save_manifest(done):
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        for k in sorted(done):
            f.write("%s\t%s\n" % (k, done[k]))


def file_sig(path):
    st = os.stat(path)
    return "%d-%d" % (int(st.st_mtime), st.st_size)


def extract_text(path, ext):
    """返回 (文本, 完整度)。完整度: full / partial / path-only"""
    try:
        if ext in TEXT_EXTS:
            with open(path, encoding="utf-8", errors="replace") as f:
                data = f.read(MAX_BYTES)
            full = os.path.getsize(path) <= MAX_BYTES
            return data, ("full" if full else "partial")
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                text = "\n".join((pg.extract_text() or "") for pg in reader.pages[:50])
                return text[:MAX_BYTES], ("full" if text.strip() else "path-only")
            except ImportError:
                return "", "path-only"
        if ext in (".docx",):
            try:
                import docx
                d = docx.Document(path)
                text = "\n".join(p.text for p in d.paragraphs)
                return text[:MAX_BYTES], ("full" if text.strip() else "path-only")
            except ImportError:
                return "", "path-only"
        if ext in (".pptx", ".xlsx"):
            return "", "path-only"          # 交给 media_extract.py 处理后补
    except Exception as e:
        sys.stderr.write("[files-index] %s: %s\n" % (path, e))
    return "", "path-only"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="要索引的源目录")
    ap.add_argument("--out", default=None, help="输出子目录名（默认取源目录名）")
    ap.add_argument("--ext", default=None, help="逗号分隔的扩展名过滤，如 .md,.py")
    args = ap.parse_args()

    src = os.path.abspath(os.path.expanduser(args.source))
    if not os.path.isdir(src):
        print("[files-index] 源目录不存在: %s" % src)
        return 1
    out_name = args.out or os.path.basename(src.rstrip("/")) or "indexed"
    dst_root = os.path.join(VAULT, "raw", "docs-indexed", out_name)
    exts = set(x.strip().lower() for x in args.ext.split(",")) if args.ext else None

    done = load_manifest()
    n_new = n_upd = n_skip = n_placeholder = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                continue
            path = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            if exts and ext not in exts:
                continue
            rel = os.path.relpath(path, src)
            key = "%s|%s" % (src, rel)
            sig = file_sig(path)
            if done.get(key) == sig:
                n_skip += 1
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > PLACEHOLDER_MAX:
                text, grade = "", "path-only"
            else:
                text, grade = extract_text(path, ext)
            if grade == "path-only":
                n_placeholder += 1

            dst = os.path.join(dst_root, rel + ".md")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            from datetime import date
            created = date.today().isoformat()
            mtime = date.fromtimestamp(os.path.getmtime(path)).isoformat()
            with open(dst, "w", encoding="utf-8") as f:
                f.write(fm(rel, created, ["文件索引", out_name, grade]))
                f.write("# %s\n\n" % rel)
                f.write("> 源文件: `%s` ｜ 修改: %s ｜ 完整度: %s\n\n" % (path, mtime, grade))
                if text.strip():
                    f.write("---\n\n%s\n" % text)
                else:
                    f.write("（正文未抽取——交给 media_extract / OCR 后补）\n")
            done[key] = sig
            if key in done and n_new >= 0:
                pass
            n_new += 1

    save_manifest(done)
    print("[files-index] 新/更新 %d（其中仅登记路径 %d），跳过未变 %d" % (n_new, n_placeholder, n_skip))
    print("[files-index] 输出: %s" % dst_root)
    print("[files-index] 下一步: qkb ingest && qkb embed 建索引")
    return 0


if __name__ == "__main__":
    sys.exit(main())
