"""
mcp_server/tools/dna.py — MCP tools for the CBIM module knowledge system (.dna/).

Read tools:
  dna_list(cwd)                  — all registered modules
  dna_show(module_path, cwd)     — full module.md + contract.md content
  dna_reindex(cwd)               — rescan filesystem, rebuild registry

Write tools (route through services.knowledge_service):
  dna_init(dir, kind, name, owner, description, with_contract, status, cwd)
  dna_edit(module_path, target, payload, mode, cwd)
  dna_split(source_module_path, splits, strategy, cwd)
  dna_write_doc(module_path, file, body, cwd)            [deprecated]
  dna_write_section(module_path, file, heading, content, mode, cwd) [deprecated]
"""

from __future__ import annotations

from pathlib import Path

from context import project_root


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
        from services import list_modules as _list_modules
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
        from cbi.resources import DNAModule
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
        from cbi.resources import DNAModule
        root = _project_root(cwd)
        DNAModule.reindex(root=root)
        count = len(DNAModule.list_all(root=root))
        return f"Rebuilt registry  ({count} modules)"

    @mcp.tool()
    def dna_init(
        dir: str,
        kind: str,
        name: str,
        owner: str,
        description: str = "",
        with_contract: bool = False,
        status: str = "",
        cwd: str = "",
    ) -> str:
        """Create a new `.dna/` module at `dir` and register it.

        Args:
            dir:           Directory that will own the new `.dna/` subdir
                           (relative to the project root or absolute).
            kind:          "root" | "parent" | "leaf".
            name:          Module name (frontmatter).
            owner:         Owning role (frontmatter).
            description:   Optional description.
            with_contract: Also create `.dna/contract.md`.
            status:        "spec" | "planned" | "implemented" or "" for default.
            cwd:           Project directory (default: current working dir).

        Returns:
            Path of the created `.dna/` directory, or `ERROR: ...` on failure.
        """
        from services import init_module
        try:
            return init_module(
                dir,
                kind=kind,
                name=name,
                owner=owner,
                description=description,
                with_contract=with_contract,
                status=status or None,
                cwd=cwd,
            )
        except FileExistsError as e:
            return f"ERROR: {e}"
        except (ValueError, FileNotFoundError) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def dna_edit(
        module_path: str,
        target: str,
        payload: dict,
        mode: str = "replace",
        cwd: str = "",
    ) -> str:
        """Edit `module.md` / `contract.md` / a workflow under `<module_path>/.dna/`.

        Args:
            module_path: Path to the module directory (the one containing `.dna/`).
            target:      "frontmatter" | "body" | "section" | "contract" |
                         "contract-section" | "workflow".
            payload:     Per-target dict; see services.knowledge_service.edit_module.
            mode:        Default section mode when payload omits its own "mode".
            cwd:         Project directory (default: current working dir).

        Returns:
            Path of the saved file, or `ERROR: ...` on failure.
        """
        from services import edit_module
        try:
            return edit_module(module_path, target, payload, mode=mode, cwd=cwd)
        except FileNotFoundError as e:
            return f"ERROR: {e}"
        except (ValueError, LookupError, RuntimeError) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def dna_split(
        source_module_path: str,
        splits: list,
        strategy: str = "comment",
        cwd: str = "",
    ) -> dict:
        """Atomically split one source module into one source + N new modules.

        Args:
            source_module_path: Path to the source module directory.
            splits:             List of split specs, each like
                                {"path": str, "name": str, "headings": [str, ...],
                                 "owner"?: str}.
            strategy:           "comment" (default — leave `<!-- split -->` marker)
                                or "move" (strip the section entirely).
            cwd:                Project directory (default: current working dir).

        Returns:
            {"created": [paths], "dependency_refs": [refs]} on success, or
            {"error": str} on failure.
        """
        from services import split_module
        try:
            return split_module(
                source_module_path,
                splits,
                strategy=strategy,
                cwd=cwd,
            )
        except (ValueError, LookupError, FileNotFoundError, FileExistsError, RuntimeError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def dna_write_doc(
        module_path: str,
        file: str,
        body: str,
        cwd: str = "",
    ) -> str:
        """[deprecated] Whole-file body write of `.dna/<file>`, preserving frontmatter.

        Prefer `dna_edit(target="body")` or `dna_edit(target="contract")`.

        Args:
            module_path: Path to the module directory.
            file:        "module.md" or "contract.md".
            body:        Body markdown (frontmatter is preserved separately).
            cwd:         Project directory (default: current working dir).
        """
        from services import write_doc
        try:
            return write_doc(module_path, file, body, cwd=cwd)
        except (ValueError, FileNotFoundError) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def dna_write_section(
        module_path: str,
        file: str,
        heading: str,
        content: str,
        mode: str,
        cwd: str = "",
    ) -> str:
        """[deprecated] Section-level edit of `.dna/<file>`.

        Prefer `dna_edit(target="section")` or `dna_edit(target="contract-section")`.

        Args:
            module_path: Path to the module directory.
            file:        "module.md" or "contract.md".
            heading:     Exact heading text (no leading '#').
            content:     Markdown body for the section (ignored when mode='delete').
            mode:        "replace" | "append" | "insert-after" | "delete".
            cwd:         Project directory (default: current working dir).
        """
        from services import write_section
        try:
            return write_section(
                module_path, file, heading,
                None if mode == "delete" else content,
                mode,
                cwd=cwd,
            )
        except (ValueError, FileNotFoundError, LookupError, RuntimeError) as e:
            return f"ERROR: {e}"
