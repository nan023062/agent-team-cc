"""
mcp_server/tools/dna.py — MCP tools for the CBIM module knowledge system (.dna/).

Exposes:
  dna_list(root)                 — all registered modules
  dna_show(module_path)          — full module.md + contract.md content
  dna_reindex(root)              — rescan filesystem, rebuild registry
"""

from __future__ import annotations

from pathlib import Path

from cbim_kernel.context import project_root


def _project_root(cwd: str) -> Path:
    """Locate the project root. Honour explicit cwd if provided, else
    use the kernel context."""
    if cwd:
        p = Path(cwd).resolve()
        for _ in range(6):
            if (p / ".cbim").is_dir():
                return p
            if p.parent == p:
                break
            p = p.parent
        return Path(cwd).resolve()
    return project_root()


def register(mcp) -> None:
    @mcp.tool()
    def dna_list(cwd: str = "") -> str:
        """List all registered .dna/ modules.

        Args:
            cwd: Project directory (default: current working dir of the MCP server).

        Returns:
            One module per line as `<path> [<owner>] <description>`.
        """
        # Route through the shared service layer so dashboard and MCP read
        # an identical module list (and an identical inflated workflow
        # structure, even though dna_list only surfaces a one-liner).
        from cbim_kernel.services import list_modules as _list_modules
        modules = _list_modules(cwd=cwd or None)
        if not modules:
            return "(no .dna modules found)"
        return "\n".join(
            f"{m['path']:32s}  [{m['owner']:12s}]  {m['description'][:40]}"
            for m in modules
        )

    @mcp.tool()
    def dna_show(module_path: str, cwd: str = "") -> str:
        """Show metadata + architecture body for the .dna/ module at `module_path`.

        Args:
            module_path: Path to the module directory (containing .dna/), e.g. 'src/combat'.
            cwd: Project directory (default: current working dir).
        """
        from cbim_kernel.cbi.engine.modules import load_module
        root = _project_root(cwd)
        mod_dir = (root / module_path).resolve()
        m = load_module(mod_dir, root)
        if not m:
            return f"ERROR: no .dna/ found in {mod_dir}"
        lines = [
            f"Name        : {m['name']}",
            f"Owner       : {m['owner']}",
            f"Description : {m['description']}",
        ]
        if m.get("keywords"):
            lines.append(f"Keywords    : {', '.join(m['keywords'])}")
        if m.get("dependencies"):
            lines.append(f"Dependencies: {', '.join(m['dependencies'])}")
        if m.get("workflows"):
            lines.append(f"Workflows   : {', '.join(m['workflows'])}")
        if m.get("architecture"):
            lines.append("\n--- module.md (body) ---\n" + m["architecture"])
        if m.get("contract"):
            lines.append("\n--- contract.md ---\n" + m["contract"])
        return "\n".join(lines)

    @mcp.tool()
    def dna_reindex(cwd: str = "") -> str:
        """Rescan the filesystem and rebuild `.cbim/.dna/index.md` registry.

        Args:
            cwd: Project directory (default: current working dir).
        """
        from cbim_kernel.cbi.engine.modules import update_index, list_modules
        root = _project_root(cwd)
        update_index(root)
        return f"Rebuilt registry  ({len(list_modules(root))} modules)"
