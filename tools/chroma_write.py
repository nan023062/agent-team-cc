"""
chroma_write.py — 将 agent session entry 写入 ChromaDB

用法：
    python3 tools/chroma_write.py \
        --agent programmer \
        --slug fix-auth-token \
        --content "JWT token 过期时间单位错误（秒 vs 毫秒），已修复。" \
        --modules auth \
        --tags incident decision

环境变量（可选）：
    CHROMA_HOST   ChromaDB 服务器地址（不设则用本地 ./chroma_db）
    CHROMA_PORT   ChromaDB 服务器端口（默认 8000）
"""

import argparse
import os
import sys
from datetime import date


def get_client():
    host = os.environ.get("CHROMA_HOST")
    if host:
        import chromadb
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    import chromadb
    return chromadb.PersistentClient(path="./chroma_db")


def main():
    parser = argparse.ArgumentParser(description="写入 agent session 到 ChromaDB")
    parser.add_argument("--agent",   required=True, help="agent id，如 programmer")
    parser.add_argument("--slug",    required=True, help="简短描述，如 fix-pathfinding")
    parser.add_argument("--content", required=True, help="session 内容（正文）")
    parser.add_argument("--modules", nargs="*", default=[], help="涉及的模块名，如 combat")
    parser.add_argument("--tags",    nargs="*", default=[], help="额外 tag，如 decision incident")
    args = parser.parse_args()

    today = date.today().strftime("%Y-%m-%d")
    entry_id = f"{today}-{args.agent}-{args.slug}"

    try:
        client = get_client()
        col = client.get_or_create_collection("memories")
        col.upsert(
            ids=[entry_id],
            documents=[args.content],
            metadatas=[{
                "agent":   args.agent,
                "slug":    args.slug,
                "date":    today,
                "modules": ",".join(args.modules),
                "tags":    ",".join(args.tags),
            }],
        )
        mode = "server" if os.environ.get("CHROMA_HOST") else "local"
        print(f"[chroma/{mode}] 已写入 id={entry_id}")
    except Exception as e:
        print(f"[chroma] 写入失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
