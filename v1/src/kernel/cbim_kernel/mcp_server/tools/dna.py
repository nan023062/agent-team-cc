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
        from cbim_kernel.cbi.resources import DNAModule
        root = _project_root(cwd)
        mod_dir = (root / module_path).resolve()
        try:
            m = DNAModule.load(mod_dir, root=root)
        except FileNotFoundError:
            return f"ERROR: no .dna/ found in {mod_dir}"
        fm = m.frontmatter
        lines = [
            f"Name        : {fm.get('name', m.id)}",
            f"Owner       : {fm.get('owner', '')}",
            f"Description : {fm.get('description', '')}",
        ]
        keywords = fm.get("keywords") or []
        if keywords:
            lines.append(f"Keywords    : {', '.join(keywords)}")
        dependencies = fm.get("dependencies") or []
        if dependencies:
            lines.append(f"Dependencies: {', '.join(dependencies)}")
        workflows = m.workflows.list()
        if workflows:
            lines.append(f"Workflows   : {', '.join(workflows)}")
        body_text = m.body.read()
        if body_text:
            lines.append("\n--- module.md (body) ---\n" + body_text)
        contract_text = m.contract.body.read() if m.contract.exists() else ""
        if contract_text:
            lines.append("\n--- contract.md ---\n" + contract_text)
        return "\n".join(lines)

    @mcp.tool()
    def dna_reindex(cwd: str = "") -> str:
        """Rescan the filesystem and rebuild `.cbim/index.md` registry.

        Args:
            cwd: Project directory (default: current working dir).
        """
        from cbim_kernel.cbi.resources import DNAModule
        root = _project_root(cwd)
        DNAModule.reindex(root=root)
        count = len(DNAModule.list_all(root=root))
        return f"Rebuilt registry  ({count} modules)"
