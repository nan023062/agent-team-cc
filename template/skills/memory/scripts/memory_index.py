"""
memory_index.py — 从 memory/entries/*.md 构建向量索引

用法：
    .venv/bin/python memory/memory_index.py [--entries-dir memory/entries]

markdown 文件是唯一数据源，可提交 git。
ChromaDB (memory/chroma_db/) 仅作为向量索引，不提交 git。
"""

import argparse
import os
import re
import sys
from pathlib import Path


def get_client():
    import chromadb
    host = os.environ.get("CHROMA_HOST")
    if host:
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    return chromadb.PersistentClient(path="./memory/chroma_db")


def parse_filename(stem):
    """从 YYYY-MM-DD-<agent>-<slug> 提取 date 和 agent。"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})-([^-]+)-.+", stem)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def parse_frontmatter(text):
    """解析可选 YAML frontmatter，返回 (meta_dict, body)。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def main():
    parser = argparse.ArgumentParser(description="构建/更新 memory entries 向量索引")
    parser.add_argument("--entries-dir", default="memory/entries", help="entries 目录路径")
    args = parser.parse_args()

    entries_dir = Path(args.entries_dir)
    if not entries_dir.exists():
        print(f"[index] 目录不存在: {entries_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = {p.stem: p for p in sorted(entries_dir.glob("*.md"))}

    client = get_client()
    col = client.get_or_create_collection("memory_entries")

    # 获取已索引条目，用于增量更新和过期清理
    existing = col.get(include=["metadatas"])
    existing_mtime = {
        eid: (meta or {}).get("mtime", "")
        for eid, meta in zip(existing["ids"], existing["metadatas"])
    }

    ids, docs, metas = [], [], []
    for stem, path in md_files.items():
        mtime = str(path.stat().st_mtime)
        if existing_mtime.get(stem) == mtime:
            continue  # 内容未变，跳过
        content = path.read_text(encoding="utf-8")
        date, agent = parse_filename(stem)
        fm, _ = parse_frontmatter(content)
        date = date or fm.get("date", "")
        agent = agent or fm.get("agent", "")
        # 规范化（去掉 YAML list 括号等）
        modules = fm.get("modules", "").strip("[]").replace('"', "").replace("'", "")
        tags = fm.get("tags", "").strip("[]").replace('"', "").replace("'", "")

        ids.append(stem)
        docs.append(content)
        metas.append({
            "path": str(path),
            "filename": path.name,
            "date": date,
            "agent": agent,
            "modules": modules,
            "tags": tags,
            "mtime": mtime,
        })

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)

    # 清理已不存在文件的索引条目
    stale = set(existing["ids"]) - set(md_files.keys())
    if stale:
        col.delete(ids=list(stale))

    mode = "server" if os.environ.get("CHROMA_HOST") else "local"
    print(
        f"[index/{mode}] 共 {len(md_files)} 个文件，"
        f"更新 {len(ids)} 个，清理 {len(stale)} 个"
    )


if __name__ == "__main__":
    main()
