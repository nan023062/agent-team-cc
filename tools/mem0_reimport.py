"""
mem0_reimport.py — 从本地 memory/entries/ 重建 mem0 Cloud 数据

用法：
    python3 tools/mem0_reimport.py              # 导入全部
    python3 tools/mem0_reimport.py --agent programmer   # 只导入某 agent
    python3 tools/mem0_reimport.py --dry-run    # 预览，不实际写入

环境变量：
    MEM0_API_KEY  mem0 Cloud API key（必填）
"""

import argparse
import os
import re
import sys
import time


def get_client():
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("[mem0] 缺少 MEM0_API_KEY", file=sys.stderr)
        sys.exit(1)
    from mem0 import MemoryClient
    return MemoryClient(api_key=api_key)


def parse_entry(filepath):
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not m:
        return None

    fm_raw, body = m.group(1), m.group(2).strip()

    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            key, val = k.strip(), v.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
            fm[key] = val

    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    modules = [t[len("module-"):] for t in tags if t.startswith("module-")]
    content_tags = [t for t in tags if not t.startswith("module-")]

    return {
        "agent":   fm.get("agent", "unknown"),
        "date":    fm.get("date", ""),
        "tags":    content_tags,
        "modules": modules,
        "content": body,
    }


def main():
    parser = argparse.ArgumentParser(description="从本地 entries 重建 mem0 Cloud")
    parser.add_argument("--agent",   default=None, help="只导入指定 agent 的 entries")
    parser.add_argument("--dry-run", action="store_true", help="预览，不实际写入")
    args = parser.parse_args()

    entries_dir = "memory/entries"
    if not os.path.isdir(entries_dir):
        print(f"目录不存在: {entries_dir}")
        sys.exit(1)

    files = sorted(f for f in os.listdir(entries_dir) if f.endswith(".md"))
    if not files:
        print("memory/entries/ 下没有 entry 文件")
        return

    # 解析所有 entry
    entries = []
    for fname in files:
        fpath = os.path.join(entries_dir, fname)
        parsed = parse_entry(fpath)
        if not parsed:
            print(f"  [skip] {fname}（无法解析 frontmatter）")
            continue
        if args.agent and parsed["agent"] != args.agent:
            continue
        entries.append((fname, parsed))

    print(f"共找到 {len(entries)} 条 entry（过滤条件：agent={args.agent or '全部'}）\n")

    if args.dry_run:
        for fname, e in entries:
            print(f"  {fname}")
            print(f"    agent={e['agent']}  modules={e['modules']}  tags={e['tags']}")
            print(f"    content 前 80 字：{e['content'][:80]}...")
            print()
        print("[dry-run] 未写入 mem0 Cloud")
        return

    client = get_client()
    ok, failed = 0, []

    for fname, e in entries:
        user_id = f"agent-{e['agent']}"
        metadata = {
            "modules": e["modules"],
            "tags":    e["tags"],
            "slug":    fname.removesuffix(".md"),
        }
        try:
            client.add(e["content"], user_id=user_id, metadata=metadata)
            print(f"  [ok] {fname}")
            ok += 1
            time.sleep(0.3)  # 避免触发 Cloud 限速
        except Exception as ex:
            print(f"  [fail] {fname}: {ex}")
            failed.append(fname)

    print(f"\n完成：{ok} 条成功，{len(failed)} 条失败")
    if failed:
        print("失败列表：")
        for f in failed:
            print(f"  {f}")


if __name__ == "__main__":
    main()
