"""
mcp_server/tools/memory.py — MCP tools for the CBIM memory engine.

Exposes:
  memory_query(text, tier, top_k)       — semantic search across the store
  memory_create(slug, content, tier)    — create a new memory entry
  memory_list(tier)                     — list all entry IDs
  memory_get(entry_id)                  — fetch a single entry by id or path
  memory_delete(path)                   — delete a memory entry
"""

from __future__ import annotations

import json
from pathlib import Path


def _project_root(cwd: Path) -> Path:
    """Walk up from cwd to find the directory containing .cbim/."""
    p = cwd.resolve()
    for _ in range(6):
        if (p / ".cbim").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise RuntimeError(
        f"No .cbim/ directory found walking up from {cwd}; cannot locate memory store."
    )


def _store_dir(cwd: str) -> Path:
    """Resolve <project>/.cbim/memory/ for the given cwd (creating if absent)."""
    root = _project_root(Path(cwd) if cwd else Path.cwd())
    store = root / ".cbim" / "memory"
    store.mkdir(parents=True, exist_ok=True)
    return store


def register(mcp) -> None:
    @mcp.tool()
    def memory_query(text: str, tier: str = "", top_k: int = 5, cwd: str = "") -> str:
        """Search CBIM memory store for entries matching `text`.

        Args:
            text: Query string (free-form natural language).
            tier: Optional "medium" to filter by tier; empty = all v2 tiers.
                  v2 removed the short tier — passing tier="short" is rejected
                  with an ERROR string (the memory facade would also raise
                  ValueError; this MCP wrapper surfaces it as a readable
                  message rather than a stack trace).
            top_k: Max number of matches to return (default 5).
            cwd: Project directory (default: current working dir of the MCP server).

        Returns:
            Newline-separated list of matching entry IDs (paths relative to the store).
        """
        from cbi.resources import Memory
        if tier == "short":
            return (
                "ERROR: tier='short' was removed in memory v2; use "
                "tier='medium' or omit the argument"
            )
        if tier and tier != "medium":
            return f"ERROR: tier must be 'medium' or empty, got {tier!r}"
        root = _project_root(Path(cwd) if cwd else Path.cwd())
        tier_arg = "medium" if tier == "medium" else None
        results = Memory.query(text, tier=tier_arg, top_k=top_k, root=root)
        if not results:
            return "(no matches)"
        return "\n".join(r["doc_id"] for r in results)

    @mcp.tool()
    def memory_list(tier: str = "", cwd: str = "") -> str:
        """List all memory entry IDs.

        Args:
            tier: Optional "short" or "medium"; empty = both.
            cwd: Project directory (default: current working dir).
        """
        # Read via the shared service layer (single source of truth that
        # dashboard also uses). The historical wire format here is the
        # backend's doc_id — i.e. the store-relative path string — so
        # rebuild that from the service's structured records.
        from services import list_entries
        if tier == "short":
            return (
                "ERROR: tier='short' was removed in memory v2; use "
                "tier='medium' or omit the argument"
            )
        if tier and tier not in ("medium", "candidates"):
            return f"ERROR: tier must be 'medium' / 'candidates' or empty, got {tier!r}"
        tier_arg = tier if tier in ("medium", "candidates") else None
        entries = list_entries(tier=tier_arg, cwd=cwd or None)
        if not entries:
            return "(empty)"
        store_dir = _store_dir(cwd)
        return "\n".join(
            str(store_dir / e["tier"] / e["id"]) for e in entries
        )

    @mcp.tool()
    def memory_create(
        slug: str,
        content: str,
        tier: str = "medium",
        cwd: str = "",
    ) -> str:
        """Create a new memory entry under the given tier.

        Args:
            slug: Short kebab-case identifier (becomes filename suffix).
            content: Markdown body of the memory entry.
            tier: "medium" — the only writable tier in memory v2 (the
                  short tier was removed; transcripts are indexed and
                  distilled to medium by the dream loop instead). Default
                  "medium". Any other value is rejected.
            cwd: Project directory (default: current working dir).

        Returns:
            Path of the created entry relative to the store.
        """
        from cbi.resources import Memory

        if tier == "short":
            return (
                "ERROR: tier='short' was removed in memory v2; use "
                "tier='medium' (the default)"
            )
        if tier != "medium":
            return f"ERROR: tier must be 'medium', got {tier!r}"

        root = _project_root(Path(cwd) if cwd else Path.cwd())
        store = root / ".cbim" / "memory"
        store.mkdir(parents=True, exist_ok=True)
        entry = Memory.create(
            slug=slug, content=content, tier=tier, kind="manual", root=root,
        )
        return str(entry.path.relative_to(store))

    @mcp.tool()
    def memory_reindex(tier: str = "", cwd: str = "") -> str:
        """Rescan the memory store and rebuild backend indices.

        Args:
            tier: "short" | "medium" | "" (both, default).
            cwd:  Project directory (default: current working dir).
        """
        from services import memory_reindex as _reindex
        try:
            return _reindex(tier=tier, cwd=cwd)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def memory_cleanup(keep_days: int, cwd: str = "") -> str:
        """Delete short-term memory entries older than `keep_days` days.

        Args:
            keep_days: Retention window in days (must be >= 0).
            cwd:       Project directory (default: current working dir).
        """
        from services import memory_cleanup as _cleanup
        try:
            return _cleanup(keep_days=keep_days, cwd=cwd)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def memory_get(entry_id: str, cwd: str = "") -> str:
        """Fetch a single memory entry by id or absolute path.

        Args:
            entry_id: Absolute path, or bare basename resolved against
                      short/, medium/, candidates/ in that order.
            cwd: Project directory (default: current working dir).

        Returns:
            JSON-encoded entry dict ({id, path, tier, mtime, metadata,
            content}) on hit, or the literal string "null" when no such
            entry exists.
        """
        from services import get_entry as _get_entry
        try:
            entry = _get_entry(entry_id, cwd=cwd)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            return json.dumps({"error": str(e)})
        if entry is None:
            return "null"
        return json.dumps(entry, ensure_ascii=False)

    @mcp.tool()
    def memory_delete(path: str, cwd: str = "") -> str:
        """Delete a memory entry by relative path (e.g. 'short/2026-05-21-manual-foo.md').

        Args:
            path: Path relative to the memory store directory.
            cwd: Project directory (default: current working dir).
        """
        from cbi.resources import Memory

        store = _store_dir(cwd)
        target = (store / path).resolve()
        try:
            target.relative_to(store.resolve())
        except ValueError:
            return f"ERROR: path {path!r} escapes the memory store"
        if not target.exists():
            return f"ERROR: not found: {path}"
        Memory.load(target).delete()
        return f"deleted {path}"
