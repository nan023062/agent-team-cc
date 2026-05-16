"""
chroma_query.py — 从 ChromaDB 语义检索记忆

用法：
    # 按 agent 查（HR 用）
    python3 tools/chroma_query.py --agent programmer --query "踩坑 问题"

    # 按模块查（架构师用）
    python3 tools/chroma_query.py --module combat --query "架构决策"

    # 输出 JSON
    python3 tools/chroma_query.py --agent programmer --query "缓存策略" --json

环境变量（可选）：
    CHROMA_HOST   ChromaDB 服务器地址（不设则用本地 ./chroma_db）
    CHROMA_PORT   ChromaDB 服务器端口（默认 8000）
"""

import argparse
import json
import os
import sys


def get_client():
    host = os.environ.get("CHROMA_HOST")
    if host:
        import chromadb
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    import chromadb
    return chromadb.PersistentClient(path="./chroma_db")


def main():
    parser = argparse.ArgumentParser(description="从 ChromaDB 语义检索记忆")
    parser.add_argument("--query",  required=True, help="查询语句")
    parser.add_argument("--agent",  default=None, help="过滤 agent id，如 programmer")
    parser.add_argument("--module", default=None, help="过滤模块名，如 combat")
    parser.add_argument("--top-k",  type=int, default=5, help="返回条数（默认 5）")
    parser.add_argument("--json",   action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    try:
        client = get_client()
        col = client.get_or_create_collection("memories")
    except Exception as e:
        print(f"[chroma] 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # agent 过滤用 ChromaDB where 子句，module 在客户端二次过滤
    where = {"agent": args.agent} if args.agent else None

    try:
        kwargs = {"query_texts": [args.query], "n_results": args.top_k}
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
    except Exception as e:
        print(f"[chroma] 查询失败: {e}", file=sys.stderr)
        sys.exit(1)

    ids       = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # 拼装结果
    hits = []
    for i, entry_id in enumerate(ids):
        meta = metadatas[i]
        hits.append({
            "id":       entry_id,
            "score":    round(1 - distances[i], 4),   # 距离转相似度
            "agent":    meta.get("agent", ""),
            "date":     meta.get("date", ""),
            "modules":  [m for m in meta.get("modules", "").split(",") if m],
            "tags":     [t for t in meta.get("tags", "").split(",") if t],
            "content":  documents[i],
        })

    # 模块过滤（客户端）
    if args.module:
        hits = [h for h in hits if args.module in h["modules"]]

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return

    mode = "server" if os.environ.get("CHROMA_HOST") else "local"
    print(f"[chroma/{mode}] 查询：{args.query!r}，命中 {len(hits)} 条\n")
    for i, h in enumerate(hits, 1):
        print(f"── [{i}] id={h['id']}  score={h['score']}")
        if h["modules"]:
            print(f"   modules: {', '.join(h['modules'])}")
        if h["tags"]:
            print(f"   tags:    {', '.join(h['tags'])}")
        print(f"   {h['content'][:300]}{'...' if len(h['content']) > 300 else ''}")
        print()


if __name__ == "__main__":
    main()
