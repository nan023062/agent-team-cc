"""
services/_fm.py — frontmatter helpers shared across service modules.

Intentionally minimal: a permissive scalar/list YAML-frontmatter parser
that matches what preview/server.py used to do inline. No PyYAML dep.
"""

from __future__ import annotations


def parse_frontmatter(text: str) -> dict:
    """Parse a leading `---\\n...\\n---` block. Returns {} when absent."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta: dict = {}
    current_key = ""
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            val = line.strip().lstrip("- ").strip()
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(val)
            continue
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if not v:
                meta[k] = []
            elif v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                meta[k] = [
                    item.strip().strip("'\"")
                    for item in inner.split(",")
                ] if inner else []
            else:
                meta[k] = v.strip("'\"")
    return meta


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def find_project_root(cwd) -> "object":
    """Walk up from cwd looking for .cbim/. Returns Path or cwd."""
    from pathlib import Path
    p = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    cur = p
    for _ in range(6):
        if (cur / ".cbim").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return p
