"""
memory_query.py — 向量检索 memory entries，返回文件路径

用法：
    .venv/bin/python memory/memory_query.py "查询意图" [选项]

输出：匹配的文件路径（每行一个）。调用方读取文件获取内容。

每次查询自动增量同步索引，无需手动运行 memory_index.py。
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
    m = re.match(r"(\d{4}-\d{2}-\d{2})-([^-]+)-.+", stem)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def parse_frontmatter(text):
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


def do_reindex(entries_dir, col):
    """增量更新索引：只处理新增/修改文件，清理已删除文件。"""
    entries_dir = Path(entries_dir)
    if not entries_dir.exists():
        return

    md_files = {p.stem: p for p in sorted(entries_dir.glob("*.md"))}
    existing = col.get(include=["metadatas"])
    existing_mtime = {
        eid: (meta or {}).get("mtime", "")
        for eid, meta in zip(existing["ids"], existing["metadatas"])
    }

    ids, docs, metas = [], [], []
    for stem, path in md_files.items():
        mtime = str(path.stat().st_mtime)
        if existing_mtime.get(stem) == mtime:
            continue
        content = path.read_text(encoding="utf-8")
        date, agent = parse_filename(stem)
        fm, _ = parse_frontmatter(content)
        date = date or fm.get("date", "")
        agent = agent or fm.get("agent", "")
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

    stale = set(existing["ids"]) - set(md_files.keys())
    if stale:
        col.delete(ids=list(stale))


def main():
    parser = argparse.ArgumentParser(
        description="向量检索 memory entries，输出匹配的文件路径"
    )
    parser.add_argument("query", help="查询语句")
    parser.add_argument("--top-k", type=int, default=5, help="返回条数（默认 5）")
    parser.add_argument("--agent", default=None, help="过滤 agent id，如 programmer")
    parser.add_argument("--module", default=None, help="过滤模块名，如 combat")
    parser.add_argument(
        "--entries-dir", default="memory/entries", help="entries 目录路径"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="输出路径时附带 agent、日期、相似度分数"
    )
    args = parser.parse_args()

    try:
        client = get_client()
        col = client.get_or_create_collection("memory_entries")
    except Exception as e:
        print(f"[query] 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 每次查询前自动增量更新索引：按 mtime 跳过未变文件，开销可忽略
    do_reindex(args.entries_dir, col)

    total = col.count()
    if total == 0:
        print("[query] memory/entries/ 为空，尚无可查询的记录", file=sys.stderr)
        sys.exit(1)

    where = {"agent": args.agent} if args.agent else None
    n = min(args.top_k, total)

    try:
        kwargs = {
            "query_texts": [args.query],
            "n_results": n,
            "include": ["metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
    except Exception as e:
        print(f"[query] 检索失败: {e}", file=sys.stderr)
        sys.exit(1)

    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    hits = []
    for i, doc_id in enumerate(ids):
        meta = metadatas[i] or {}
        path = meta.get("path", f"{args.entries_dir}/{doc_id}.md")
        modules_str = meta.get("modules", "")
        if args.module and args.module not in modules_str:
            continue
        hits.append({
            "path": path,
            "agent": meta.get("agent", ""),
            "date": meta.get("date", ""),
            "score": round(1 - distances[i], 4),
        })

    if not hits:
        print("[query] 无匹配结果", file=sys.stderr)
        sys.exit(0)

    for h in hits:
        if args.verbose:
            print(f"{h['path']}  # agent={h['agent']} date={h['date']} score={h['score']}")
        else:
            print(h["path"])


if __name__ == "__main__":
    main()
