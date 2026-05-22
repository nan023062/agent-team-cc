"""
mcp_server/tools/memory.py — MCP tools for the CBIM memory engine.

Exposes:
  memory_query(text, tier, top_k)       — semantic search across the store
  memory_create(slug, content, tier)    — create a new memory entry
  memory_list(tier)                     — list all entry IDs
  memory_delete(path)                   — delete a memory entry
"""

from __future__ import annotations

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
            tier: Optional "short" or "medium" to filter by tier; empty = both.
            top_k: Max number of matches to return (default 5).
            cwd: Project directory (default: current working dir of the MCP server).

        Returns:
            Newline-separated list of matching entry IDs (paths relative to the store).
        """
        from cbim_kernel.cbi.resources import Memory
        root = _project_root(Path(cwd) if cwd else Path.cwd())
        tier_arg = tier if tier in ("short", "medium") else None
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
        from cbim_kernel.services import list_entries
        tier_arg = tier if tier in ("short", "medium") else None
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
        tier: str = "short",
        cwd: str = "",
    ) -> str:
        """Create a new memory entry under the given tier.

        Args:
            slug: Short kebab-case identifier (becomes filename suffix).
            content: Markdown body of the memory entry.
            tier: "short" (raw) or "medium" (distilled pattern). Default "short".
            cwd: Project directory (default: current working dir).

        Returns:
            Path of the created entry relative to the store.
        """
        from cbim_kernel.cbi.resources import Memory

        if tier not in ("short", "medium"):
            return f"ERROR: tier must be 'short' or 'medium', got {tier!r}"

        root = _project_root(Path(cwd) if cwd else Path.cwd())
        store = root / ".cbim" / "memory"
        store.mkdir(parents=True, exist_ok=True)
        entry = Memory.create(
            slug=slug, content=content, tier=tier, kind="manual", root=root,
        )
        return str(entry.path.relative_to(store))

    @mcp.tool()
    def memory_delete(path: str, cwd: str = "") -> str:
        """Delete a memory entry by relative path (e.g. 'short/2026-05-21-manual-foo.md').

        Args:
            path: Path relative to the memory store directory.
            cwd: Project directory (default: current working dir).
        """
        from cbim_kernel.cbi.resources import Memory

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
