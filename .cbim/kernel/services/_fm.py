"""
services/_fm.py — frontmatter helpers shared across service modules.

Intentionally minimal: a permissive scalar/list YAML-frontmatter parser
that matches what dashboard/server.py used to do inline. No PyYAML dep.
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


def render_frontmatter(meta: dict, schema: tuple[str, ...] = ()) -> str:
    """Render `meta` as a `---\\n...\\n---\\n` YAML frontmatter block.

    Fields listed in `schema` are emitted first, in the given order, only if
    present in `meta`. Remaining keys follow in insertion order. Lists render
    block-style when populated (``key:`` then ``  - item`` lines) and ``[]``
    when empty. All other values are rendered as ``key: value``.
    """
    lines: list[str] = ["---"]
    emitted: set[str] = set()
    for key in schema:
        if key in meta:
            lines.extend(_render_field(key, meta[key]))
            emitted.add(key)
    for key, val in meta.items():
        if key in emitted:
            continue
        lines.extend(_render_field(key, val))
    lines.append("---")
    return "\n".join(lines) + "\n"


def _render_field(key: str, val) -> list[str]:
    if isinstance(val, list):
        if val:
            out = [f"{key}:"]
            for item in val:
                out.append(f"  - {item}")
            return out
        return [f"{key}: []"]
    return [f"{key}: {val}"]


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
