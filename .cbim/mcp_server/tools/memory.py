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


def _engine_for_project(cwd: Path):
    """Build a MemoryEngine pointed at <project>/.cbim/memory/store/."""
    from memory.engine.engine import MemoryEngine
    from memory.engine.file_backend import FileBackend

    # Find the .cbim/ directory by walking up from cwd
    p = cwd.resolve()
    for _ in range(6):
        if (p / ".cbim").is_dir():
            store_dir = p / ".cbim" / "memory" / "store"
            store_dir.mkdir(parents=True, exist_ok=True)
            return MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)
        if p.parent == p:
            break
        p = p.parent
    raise RuntimeError(
        f"No .cbim/ directory found walking up from {cwd}; cannot locate memory store."
    )


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
        engine = _engine_for_project(Path(cwd) if cwd else Path.cwd())
        tier_arg = tier if tier in ("short", "medium") else None
        results = engine.query(text, tier=tier_arg, top_k=top_k)
        if not results:
            return "(no matches)"
        return "\n".join(results)

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
        tier_arg = tier if tier in ("short", "medium") else None
        entries = list_entries(tier=tier_arg, cwd=cwd or None)
        if not entries:
            return "(empty)"
        engine = _engine_for_project(Path(cwd) if cwd else Path.cwd())
        store_dir = engine.store_dir
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
        from datetime import date

        if tier not in ("short", "medium"):
            return f"ERROR: tier must be 'short' or 'medium', got {tier!r}"

        engine = _engine_for_project(Path(cwd) if cwd else Path.cwd())
        store = engine.store_dir / tier
        store.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        path = store / f"{today}-manual-{slug}.md"
        if path.exists():
            return f"ERROR: {path.name} already exists"
        path.write_text(content, encoding="utf-8")
        engine.add(path, tier)
        return str(path.relative_to(engine.store_dir))

    @mcp.tool()
    def memory_delete(path: str, cwd: str = "") -> str:
        """Delete a memory entry by relative path (e.g. 'short/2026-05-21-manual-foo.md').

        Args:
            path: Path relative to the memory store directory.
            cwd: Project directory (default: current working dir).
        """
        engine = _engine_for_project(Path(cwd) if cwd else Path.cwd())
        target = (engine.store_dir / path).resolve()
        try:
            target.relative_to(engine.store_dir.resolve())
        except ValueError:
            return f"ERROR: path {path!r} escapes the memory store"
        if not target.exists():
            return f"ERROR: not found: {path}"
        engine.delete(target)
        target.unlink()
        return f"deleted {path}"
