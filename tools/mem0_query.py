"""
mem0_query.py — 从 mem0 Cloud 查询相关记忆

用法：
    # 查询某 agent 的相关记忆（HR 压缩用）
    python3 tools/mem0_query.py --agent programmer --query "寻路相关决策"

    # 查询某模块的相关记忆（架构师压缩用）
    python3 tools/mem0_query.py --module combat --query "战斗模块架构决策"

    # 通用查询
    python3 tools/mem0_query.py --query "A* 算法" --top-k 10

环境变量：
    MEM0_API_KEY      mem0 Cloud API key（必填，在 app.mem0.ai 注册获取）
"""

import argparse
import json
import os
import sys


def get_client():
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("[mem0] 缺少 MEM0_API_KEY，请在 app.mem0.ai 注册后设置环境变量", file=sys.stderr)
        sys.exit(1)
    from mem0 import MemoryClient
    return MemoryClient(api_key=api_key)


def main():
    parser = argparse.ArgumentParser(description="从 mem0 Cloud 查询相关记忆")
    parser.add_argument("--query",  required=True, help="查询语句")
    parser.add_argument("--agent",  default=None,  help="过滤 agent id，如 programmer")
    parser.add_argument("--module", default=None,  help="过滤模块名，如 combat")
    parser.add_argument("--top-k",  type=int, default=5, help="返回条数（默认 5）")
    parser.add_argument("--json",   action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    try:
        client = get_client()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[mem0] 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # agent-id 映射到 user_id（绕过 mem0 v2 agent_id 过滤 bug）
    filters = {}
    if args.agent:
        filters["user_id"] = f"agent-{args.agent}"

    try:
        search_kwargs = {"query": args.query, "top_k": args.top_k}
        if filters:
            search_kwargs["filters"] = filters
        results = client.search(**search_kwargs)
    except Exception as e:
        print(f"[mem0] 查询失败: {e}", file=sys.stderr)
        sys.exit(1)

    memories = results.get("results", results) if isinstance(results, dict) else results

    # 模块过滤（client-side，metadata server filter 不稳定）
    if args.module:
        memories = [
            m for m in memories
            if args.module in (m.get("metadata") or {}).get("modules", [])
        ]

    if args.json:
        print(json.dumps(memories, ensure_ascii=False, indent=2))
        return

    print(f"[mem0/cloud] 查询：{args.query!r}，命中 {len(memories)} 条\n")
    for i, m in enumerate(memories, 1):
        meta = m.get("metadata") or {}
        modules = meta.get("modules", [])
        tags    = meta.get("tags", [])
        score   = m.get("score", "—")
        memory  = m.get("memory", m.get("text", ""))

        print(f"── [{i}] score={score}")
        if modules:
            print(f"   modules: {', '.join(modules)}")
        if tags:
            print(f"   tags:    {', '.join(tags)}")
        print(f"   {memory[:300]}{'...' if len(memory) > 300 else ''}")
        print()


if __name__ == "__main__":
    main()
