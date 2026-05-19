"""
engine/snapshot.py — Project knowledge snapshot for session context.

Generates a concise markdown summary of:
  - Module tree (business layer, from .dna/)
  - Agent roster (capability layer, from .claude/agents/)

Usage:
  python cbim/knowledge/engine/snapshot.py --root <project-root>
  from knowledge.engine.snapshot import build_snapshot
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from knowledge.engine.modules import list_modules
from knowledge.engine.agents import list_agents


def build_snapshot(root: Path) -> str:
    agents_dir = root / ".claude" / "agents"
    agents = list_agents(agents_dir)
    modules = list_modules(root)

    lines: list[str] = ["## 项目知识快照\n"]

    lines.append("### 模块树（业务层）\n")
    if modules:
        for m in modules:
            path = m["path"]
            name = m["name"]
            desc = m["description"]
            owner = m["owner"]
            suffix = f" — {desc}" if desc else ""
            owner_tag = f" (owner: {owner})" if owner else ""
            lines.append(f"- `{path}` **{name}**{suffix}{owner_tag}")
    else:
        lines.append("- （暂无模块）")

    lines.append("")
    lines.append("### Agent 列表（能力层）\n")
    if agents:
        for a in agents:
            aid = a["id"]
            name = a["name"]
            desc = a["description"]
            suffix = f" — {desc}" if desc else ""
            lines.append(f"- **{name}** (`{aid}`){suffix}")
    else:
        lines.append("- （暂无 work agent）")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate project knowledge snapshot")
    parser.add_argument("--root", default=".", help="Project root directory")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    print(build_snapshot(root))


if __name__ == "__main__":
    main()
