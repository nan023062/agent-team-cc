"""arch_gov/load_all.py — LoadAll deterministic leaf.

Reads the .dna/ module index from disk and stashes the inventory in the
subtree's shared state dict. No LLM, no MCP — pure filesystem.

The inventory shape is intentionally minimal so the eight scan leaves can
filter / cross-reference without re-walking the tree:

    state["inventory"] = {
        "modules": [
            {"path": str, "dna_present": bool, "dir_present": bool,
             "frontmatter": dict, "deps": list[str]},
            ...
        ],
        "index_md_modules": [str, ...],   # paths declared by .dna/index.md
        "errors": [str, ...],             # non-fatal read errors
    }

The kernel may not yet expose a stable "list all DNA modules" helper, so we
walk the workspace defensively. SUCCESS even when nothing is found
(empty inventory is a legitimate signal for downstream scans).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.core.node import Node, Status


def _project_root() -> Path:
    """Best-effort project root discovery.

    Walks upward from this file looking for a `.cbim` sibling — that's the
    CBIM project root by convention (see CLAUDE.md "Project Root").
    Falls back to cwd if nothing found.
    """
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".cbim").is_dir():
            return parent
    return Path.cwd()


def _read_frontmatter(text: str) -> dict[str, Any]:
    """Parse leading `---\\n...\\n---\\n` YAML-ish frontmatter, key: value only.

    Deliberately minimal — we don't want a YAML dependency here, and the
    governance scan only needs presence/absence of a handful of keys.
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


class LoadAll(Node):
    """Walk .dna/ tree → state["inventory"]; always SUCCESS."""

    def __init__(self, *, state: dict, name: str = "LoadAll") -> None:
        self.name = name
        self._state = state

    def tick(self, bb) -> Status:
        root = _project_root()
        modules: list[dict[str, Any]] = []
        errors: list[str] = []
        index_md_modules: list[str] = []

        # Every `.dna/module.md` under the workspace.
        for module_md in root.rglob(".dna/module.md"):
            module_dir = module_md.parent.parent  # strip .dna/module.md
            rel_path = str(module_dir.relative_to(root)).replace("\\", "/")
            try:
                text = module_md.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                errors.append(f"{rel_path}: read failed: {e}")
                continue
            fm = _read_frontmatter(text)
            deps_raw = fm.get("dependencies", "") or fm.get("deps", "")
            deps = [d.strip() for d in deps_raw.split(",") if d.strip()] if deps_raw else []
            modules.append({
                "path": rel_path,
                "dna_present": True,
                "dir_present": module_dir.is_dir(),
                "frontmatter": fm,
                "deps": deps,
            })

        # Top-level .dna/index.md (if present) — listed paths drive the
        # "orphan" / "stale" cross-check.
        index_md = root / ".dna" / "index.md"
        if index_md.exists():
            try:
                for line in index_md.read_text(encoding="utf-8", errors="replace").splitlines():
                    # Very loose: any markdown link target that looks like a module path.
                    line = line.strip()
                    if line.startswith("- ") and "(" in line and ")" in line:
                        target = line.split("(", 1)[1].split(")", 1)[0]
                        index_md_modules.append(target.strip())
            except Exception as e:
                errors.append(f".dna/index.md: read failed: {e}")

        self._state["inventory"] = {
            "modules": modules,
            "index_md_modules": index_md_modules,
            "errors": errors,
        }
        return Status.SUCCESS
