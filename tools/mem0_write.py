"""
mem0_write.py — 将 agent session entry 写入 mem0 Cloud + 本地文件

用法：
    python3 tools/mem0_write.py \
        --agent programmer \
        --slug fix-combat-pathfinding \
        --content "完成了战斗模块寻路重构，决策：改用 A*..." \
        --modules combat pathfinding \
        --tags decision refactor

环境变量：
    MEM0_API_KEY      mem0 Cloud API key（必填，在 app.mem0.ai 注册获取）

同时将 entry 写入 memory/entries/<date>-<agent>-<slug>.md 作为 git 审计记录。
"""

import argparse
import os
import sys
from datetime import date


def get_client():
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("[mem0] 缺少 MEM0_API_KEY，请在 app.mem0.ai 注册后设置环境变量", file=sys.stderr)
        sys.exit(1)
    from mem0 import MemoryClient
    return MemoryClient(api_key=api_key)


def write_entry_file(agent: str, slug: str, content: str,
                     modules: list, tags: list) -> str:
    today = date.today().strftime("%Y-%m-%d")
    entries_dir = os.path.join("memory", "entries")
    os.makedirs(entries_dir, exist_ok=True)

    filename = f"{today}-{agent}-{slug}.md"
    filepath = os.path.join(entries_dir, filename)

    module_tags = [f"module-{m}" for m in modules]
    all_tags = module_tags + tags

    frontmatter = f"""---
date: {today}
agent: {agent}
tags: [{', '.join(all_tags)}]
---

{content}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter)

    return filepath


def main():
    parser = argparse.ArgumentParser(description="写入 agent session 到 mem0 Cloud + 本地文件")
    parser.add_argument("--agent",   required=True, help="agent id，如 programmer")
    parser.add_argument("--slug",    required=True, help="简短描述，如 fix-pathfinding")
    parser.add_argument("--content", required=True, help="session 内容（正文）")
    parser.add_argument("--modules", nargs="*", default=[], help="涉及的模块名，如 combat")
    parser.add_argument("--tags",    nargs="*", default=[], help="额外 tag，如 decision incident")
    args = parser.parse_args()

    # 1. 写本地 entry 文件
    filepath = write_entry_file(
        args.agent, args.slug, args.content, args.modules, args.tags
    )
    print(f"[entry] 已写入 {filepath}")

    # 2. 写入 mem0 Cloud
    # agent-id 映射到 user_id（绕过 mem0 v2 agent_id 过滤 bug）
    try:
        client = get_client()
        user_id = f"agent-{args.agent}"
        metadata = {
            "modules": args.modules,
            "tags":    args.tags,
            "slug":    args.slug,
        }
        client.add(args.content, user_id=user_id, metadata=metadata)
        print(f"[mem0/cloud] 已写入 user_id={user_id}, modules={args.modules}")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[mem0] 写入失败（本地文件已保存）: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
