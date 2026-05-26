"""
services/memory_service.py — memory store read + transactional write facade.

Read side (`list_entries`) is unchanged from the historical service shape.

Write side (`reindex`, `cleanup`) is the single implementation shared by:
  - engine/cli.py `cmd_reindex` / `cmd_cleanup` (CLI surface)
  - mcp_server/tools/memory.py (MCP surface)

Phase 1 design note: previously this layer was read-only. The "No service
writes" rule was reversed so we don't duplicate the MemoryEngine wiring on
every surface. Entry creation / deletion still flow through
`cbi.resources.Memory` directly (those are single-step and already shared
between CLI and MCP).
"""

from __future__ import annotations

import re
from pathlib import Path

from ._fm import find_project_root, parse_frontmatter, strip_frontmatter

# v2: short tier removed. Only medium remains as a file tier.
TIERS = ("medium",)


def list_entries(tier: str | None = None, cwd=None) -> list[dict]:
    """Return all memory entries, newest first.

    Args:
        tier:  Optional filter — must be "medium" or None in v2. (The legacy
               "short" value raises ValueError; short tier was removed.)
        cwd:   Project search base (defaults to current working dir). The
               function walks up to find `.cbim/` and reads
               `.cbim/memory/medium/*.md` underneath it.

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
    store_dir = Path(root) / ".cbim" / "memory"

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


# ---------------------------------------------------------------------------
# Write facade — shared by engine/cli.py and mcp_server/tools/memory.py
# ---------------------------------------------------------------------------

def _build_backend(cwd: str = ""):
    """Construct the default FileBackend for `<project>/.cbim/memory/`.

    Returns (backend, store_dir). Both `compaction.rebuild` and
    `compaction.sweep_expired` need the store dir as a separate arg.
    """
    from memory.crud.backend import MemoryBackend  # noqa: F401  (typing)
    from memory.crud.file_backend import FileBackend

    root = Path(find_project_root(cwd or None))
    store_dir = root / ".cbim" / "memory"
    store_dir.mkdir(parents=True, exist_ok=True)
    return FileBackend(store_dir), store_dir


def reindex(tier: str = "", cwd: str = "") -> str:
    """Rescan the memory store and rebuild backend + retrieval indices.

    v2: only "" (default = medium) or "medium" is accepted. "short" raises
    ValueError. Output now includes drift counts from the engine.retrieval
    verify pass that runs alongside the local rebuild.
    """
    if tier not in ("", "medium"):
        raise ValueError(
            f"tier must be 'medium' or '' (default), got: {tier!r}; "
            f"short tier was removed in v2"
        )
    from memory.compaction.rebuilder import rebuild_and_verify
    backend, store_dir = _build_backend(cwd)
    report = rebuild_and_verify(store_dir, backend)
    return (
        f"reindexed {report.indexed_count} entries; "
        f"drift checked={report.drift_checked} "
        f"drifted={report.drift_drifted} "
        f"repaired={report.drift_repaired} "
        f"failed={report.drift_failed}"
    )


def get_entry(entry_id: str, cwd: str = "") -> dict | None:
    from memory._facade import get as _facade_get
    root = Path(find_project_root(cwd or None))
    store_dir = root / ".cbim" / "memory"
    return _facade_get(entry_id, store_dir=store_dir)


def cleanup(keep_days: int, cwd: str = "") -> str:
    """Sweep stale candidate stubs older than `keep_days`.

    v2: the v1 target (distilled + aged short entries) is gone with the
    short tier. The signature is preserved so MCP and CLI callers keep
    working; semantics now point at the candidates work area.
    """
    if keep_days < 0:
        raise ValueError(f"keep_days must be >= 0, got: {keep_days!r}")
    from memory.compaction import sweep_expired
    backend, store_dir = _build_backend(cwd)
    count = sweep_expired(store_dir, backend, keep_days=keep_days)
    return f"swept {count} stale candidates older than {keep_days} days"
