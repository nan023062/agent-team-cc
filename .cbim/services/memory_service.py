"""
services/memory_service.py — read-only memory store service.

Exposes pure functions returning structured dicts. The preview HTTP
adapter and the MCP `memory_*` tools both depend on these.

Why a service layer:
  - preview/server.py used to glob the store and parse frontmatter inline,
    duplicating logic that the engine/MCP layer also needs.
  - Centralising the loader here means a single canonical shape for an
    "entry" record — schema changes happen in one place.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._fm import find_project_root, parse_frontmatter, strip_frontmatter

TIERS = ("short", "medium")


def list_entries(tier: str | None = None, cwd=None) -> list[dict]:
    """Return all memory entries, newest first.

    Args:
        tier:  Optional filter — "short" or "medium". None = both tiers.
        cwd:   Project search base (defaults to current working dir). The
               function walks up to find `.cbim/` and reads
               `.cbim/memory/store/{tier}/*.md` underneath it.

    Returns:
        List of dicts shaped like::

            {
              "id":       <filename>,         # e.g. "2026-05-21-manual-foo.md"
              "tier":     "short" | "medium",
              "date":     "YYYY-MM-DD" | "",
              "keyword":  <frontmatter or "">,
              "type":     <frontmatter or "">,
              "modules":  <frontmatter or "">,
              "sources":  <frontmatter or "">,
              "title":    <first non-frontmatter heading/line, truncated>,
              "body":     <markdown body, frontmatter stripped>,
            }

        Sort: tier order short→medium, within each tier filename DESC
        (newest first by date-prefixed name).
    """
    root = find_project_root(cwd)
    store_dir = Path(root) / ".cbim" / "memory" / "store"

    if tier is not None and tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS} or None, got {tier!r}")

    tiers = [tier] if tier else list(TIERS)
    entries: list[dict] = []
    for t in tiers:
        tier_dir = store_dir / t
        if not tier_dir.exists():
            continue
        for md_file in sorted(tier_dir.glob("*.md"), reverse=True):
            entries.append(_parse_entry(md_file, t))
    return entries


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _parse_entry(path: Path, tier: str) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        raw = ""
    meta = parse_frontmatter(raw)
    body = strip_frontmatter(raw)
    return {
        "id": path.name,
        "tier": tier,
        "date": meta.get("date") or _date_from_name(path.name),
        "keyword": meta.get("keyword", ""),
        "type": meta.get("type", ""),
        "modules": meta.get("modules", ""),
        "sources": meta.get("sources", ""),
        "title": _extract_title(body, path.name),
        "body": body,
    }


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("## "):
            return line[3:].strip()
        if line and not line.startswith("#"):
            return line[:80]
    return fallback


def _date_from_name(name: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""
