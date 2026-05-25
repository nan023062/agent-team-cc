"""hr_gov/load.py — Load deterministic leaf.

Reads `.claude/agents/` and stashes the agent inventory in
state["inventory"]. No LLM, no MCP — pure filesystem.

Inventory shape:
    state["inventory"] = {
        "agents": [
            {"name": str, "path": str, "frontmatter": dict, "body_len": int},
            ...
        ],
        "errors": [str, ...],
    }
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.core.node import Node, Status


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".cbim").is_dir():
            return parent
    return Path.cwd()


def _read_frontmatter(text: str) -> dict[str, Any]:
    """Minimal `---`-delimited frontmatter parser; see arch_gov/load_all.py."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    body = text[4:end]
    out: dict[str, Any] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Load(Node):
    def __init__(self, *, state: dict, name: str = "Load") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        root = _project_root()
        agents_dir = root / ".claude" / "agents"
        agents: list[dict[str, Any]] = []
        errors: list[str] = []

        if not agents_dir.is_dir():
            self._state["inventory"] = {"agents": [], "errors": ["agents dir missing"]}
            return Status.SUCCESS

        for md in agents_dir.rglob("*.md"):
            rel = str(md.relative_to(root)).replace("\\", "/")
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                errors.append(f"{rel}: read failed: {e}")
                continue
            fm = _read_frontmatter(text)
            agents.append({
                "name": fm.get("name") or md.stem,
                "path": rel,
                "frontmatter": fm,
                "body_len": len(text),
            })

        self._state["inventory"] = {"agents": agents, "errors": errors}
        return Status.SUCCESS
