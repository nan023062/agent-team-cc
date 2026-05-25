"""hr_exec/scan.py — Scan deterministic leaf.

Reads `.claude/agents/` and writes `bb.hr_agent_inventory` (list[dict]).
No LLM call. Every entry has the shape:

    {
        "agent_id":     str,           # frontmatter `name` or filename stem
        "agent_file":   str,           # project-root-relative posix path
        "description":  str,           # frontmatter `description` (may be "")
        "capabilities": list[str],     # frontmatter `capabilities` split on commas
    }

Missing/unreadable agents directory → empty list (SUCCESS — downstream
ForEach + CoreAgentSelector still handle dispatch fallback).
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
    """Minimal `---`-delimited frontmatter parser (kept identical to
    hr_gov/load.py for cross-loop consistency).
    """
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


def _split_capabilities(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


class Scan(Node):
    """Deterministic inventory of `.claude/agents/`."""

    def __init__(self, *, name: str = "Scan") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        root = _project_root()
        agents_dir = root / ".claude" / "agents"
        inventory: list[dict[str, Any]] = []

        if agents_dir.is_dir():
            for md in sorted(agents_dir.rglob("*.md")):
                rel = str(md.relative_to(root)).replace("\\", "/")
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                fm = _read_frontmatter(text)
                inventory.append({
                    "agent_id": fm.get("name") or md.stem,
                    "agent_file": rel,
                    "description": fm.get("description", ""),
                    "capabilities": _split_capabilities(fm.get("capabilities", "")),
                })

        bb.hr_agent_inventory = inventory
        return Status.SUCCESS


def build() -> Scan:
    return Scan()
