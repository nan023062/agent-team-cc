"""
services/knowledge_service.py — read-only .dna module service.

Thin wrapper over cbi.engine.modules.list_modules that also pulls the
collateral docs (contract.md, workflows/*/workflow.md) into a single
record shape suitable for the dashboard UI and MCP tooling.
"""

from __future__ import annotations

from pathlib import Path

from ._fm import find_project_root, parse_frontmatter, strip_frontmatter


def list_modules(cwd=None) -> list[dict]:
    """Return all registered .dna modules.

    Args:
        cwd: Project search base; walks up to find `.cbim/`.

    Returns:
        List of dicts shaped like::

            {
              "id":           <project-relative path>,
              "path":         <project-relative path>,
              "name":         <frontmatter name>,
              "owner":        <frontmatter owner>,
              "description":  <frontmatter description>,
              "keywords":     [str, ...],
              "dependencies": [str, ...],
              "architecture": <module.md body, frontmatter stripped>,
              "contract":     <contract.md content or "">,
              "workflows":    [ {"id": <slug>, "name": <fm name>, "body": <md>}, ... ],
            }
    """
    root = Path(find_project_root(cwd))

    # Re-use the canonical loader — it understands the registry, legacy
    # module.json fallback, and skip-dir rules.
    import sys as _sys
    cbim_dir = root / ".cbim"
    cbim_str = str(cbim_dir)
    if cbim_str not in _sys.path:
        _sys.path.insert(0, cbim_str)

    from cbi.engine.modules import list_modules as _list_modules

    modules = _list_modules(root)
    # The engine loader returns workflows as a list of slugs; the dashboard
    # UI expects full {id, name, body} records. Inflate here.
    inflated = []
    for m in modules:
        mod_dir = root if m["path"] in (".", "") else (root / m["path"])
        m = dict(m)  # don't mutate the engine's dict
        m["workflows"] = _collect_workflows(mod_dir / ".dna" / "workflows")
        kw = m.get("keywords", [])
        if isinstance(kw, str):
            kw = [k.strip() for k in kw.split(",") if k.strip()] if kw else []
        m["keywords"] = kw if isinstance(kw, list) else []
        deps = m.get("dependencies", [])
        if isinstance(deps, str):
            deps = [d.strip() for d in deps.split(",") if d.strip()] if deps else []
        m["dependencies"] = deps if isinstance(deps, list) else []
        inflated.append(m)
    return inflated


def _collect_workflows(workflows_dir: Path) -> list[dict]:
    if not workflows_dir.exists():
        return []
    out = []
    for wf_dir in sorted(workflows_dir.iterdir()):
        if not wf_dir.is_dir():
            continue
        wf_file = wf_dir / "workflow.md"
        if not wf_file.exists():
            continue
        try:
            raw = wf_file.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            raw = ""
        meta = parse_frontmatter(raw)
        out.append({
            "id": wf_dir.name,
            "name": meta.get("name", wf_dir.name),
            "body": strip_frontmatter(raw),
        })
    return out
