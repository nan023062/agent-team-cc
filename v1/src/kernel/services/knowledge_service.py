"""
services/knowledge_service.py — .dna module read + transactional write facade.

Read side (`list_modules`) inflates module dicts with workflow records and
normalises list-typed frontmatter fields.

Write side (`init_module`, `edit_module`, `split_module`, `write_doc`,
`write_section`) is the single implementation shared by:
  - engine/cli.py `_handle_dna_*` (CLI surface)
  - mcp_server/tools/dna.py (MCP surface)

Phase 1 design note: previously this layer was read-only. The "No service
writes" rule was reversed so we don't duplicate the multi-file orchestration
(`.dna/module.md` + `.dna/contract.md` + registry update) on every surface.
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

    from cbi._primitives.modules import list_modules as _list_modules

    modules = _list_modules(root)
    inflated = []
    for m in modules:
        mod_dir = root if m["path"] in (".", "") else (root / m["path"])
        m = dict(m)
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


# ---------------------------------------------------------------------------
# Write facade — shared by engine/cli.py and mcp_server/tools/dna.py
# ---------------------------------------------------------------------------

def _resolve_root(cwd: str = "") -> Path:
    return Path(find_project_root(cwd or None))


def init_module(
    dir: str | Path,
    kind: str,
    name: str,
    owner: str,
    description: str = "",
    with_contract: bool = False,
    status: str | None = None,
    cwd: str = "",
) -> str:
    """Create a new `.dna/` module at `dir` and register it.

    Args:
        dir:           Directory that will own the new `.dna/` subdir.
        kind:          "root" | "parent" | "leaf".
        name:          Module name (frontmatter).
        owner:         Owning role (frontmatter).
        description:   Optional description (frontmatter).
        with_contract: Also create `.dna/contract.md`.
        status:        "spec" | "planned" | "implemented" — default decided
                       by `init_module` primitive (spec for parent/leaf,
                       implemented for root).
        cwd:           Project search base.

    Returns the absolute path to the created `.dna/` directory as a string.
    Raises `FileExistsError` when `.dna/` already exists, `ValueError` for
    invalid kind / status, `FileNotFoundError` when the registry is missing.
    """
    from cbi.resources import DNAModule
    root = _resolve_root(cwd)
    m = DNAModule.create(
        Path(dir),
        name=name,
        owner=owner,
        description=description,
        with_contract=with_contract,
        type=kind,
        status=status,
        root=root,
    )
    return str(m.path.parent.resolve())


def edit_module(
    module_path: str | Path,
    target: str,
    payload: dict,
    mode: str = "replace",
    cwd: str = "",
) -> str:
    """Edit module.md / contract.md / workflow under `<module_path>/.dna/`.

    Args:
        module_path: Path to the module directory (the one containing `.dna/`).
        target:      "frontmatter" | "body" | "section" | "contract" |
                     "contract-section" | "workflow".
        payload:     Per-target dict; shape mirrors `agent_service.update_agent`.
                     workflow -> {"name": str, "content": str}
                     contract / contract-section -> like body / section but on
                     contract.md (auto-creates contract.md if missing).
        mode:        Default section mode when payload omits its own "mode".
        cwd:         Project search base.

    Returns the absolute path to the saved file as a string.
    """
    from cbi.resources import DNAModule
    from cbi._primitives.modules import (
        _MODULE_FM_LIST_FIELDS,
        _MODULE_FM_STATUS_VALUES,
    )

    root = _resolve_root(cwd)
    m = DNAModule.load(Path(module_path), root=root)

    if target == "frontmatter":
        field = payload.get("field")
        if field is None:
            raise ValueError("payload.field is required for target=frontmatter")
        has_scalar = "value" in payload and payload["value"] is not None
        has_list = "value_list" in payload and payload["value_list"] is not None
        if has_scalar and has_list:
            raise ValueError("payload.value and payload.value_list are mutually exclusive")
        if not has_scalar and not has_list:
            raise ValueError("one of payload.value or payload.value_list is required")
        if field in _MODULE_FM_LIST_FIELDS and has_scalar:
            raise ValueError(
                f"field {field!r} is a list-typed field; use payload.value_list"
            )
        new_value = payload["value_list"] if has_list else payload["value"]
        if has_list and new_value == [] and field not in _MODULE_FM_LIST_FIELDS:
            raise ValueError(
                f"field {field!r} is not list-typed; cannot clear "
                f"(allowed list-typed fields: {sorted(_MODULE_FM_LIST_FIELDS)})"
            )
        if field == "status":
            if has_list:
                raise ValueError("field 'status' is a scalar enum; use payload.value")
            if new_value not in _MODULE_FM_STATUS_VALUES:
                raise ValueError(
                    f"status must be one of {_MODULE_FM_STATUS_VALUES}, "
                    f"got: {new_value!r}"
                )
        m.frontmatter.set(field, new_value)
        m.save()
        return str(m.path.resolve())

    if target == "body":
        content = payload.get("content")
        if content is None:
            raise ValueError("payload.content is required for target=body")
        m.body.write(content)
        m.save()
        return str(m.path.resolve())

    if target == "section":
        heading = payload.get("heading")
        if heading is None:
            raise ValueError("payload.heading is required for target=section")
        sec_mode = payload.get("mode") or mode or "replace"
        needs_content = sec_mode != "delete"
        content = payload.get("content")
        if needs_content and content is None:
            raise ValueError("payload.content is required unless mode=delete")
        if not needs_content and content is not None:
            raise ValueError("payload.content forbidden with mode=delete")
        insert_after = payload.get("insert_after")
        insert_at_top = bool(payload.get("insert_at_top", False))
        if insert_after is not None and insert_at_top:
            raise ValueError(
                "payload.insert_after and payload.insert_at_top are mutually exclusive"
            )
        m.body.write_section(
            heading,
            content,
            level=int(payload.get("level", 2)),
            mode=sec_mode,
            create_if_missing=bool(payload.get("create_if_missing", False)),
            insert_after=insert_after,
            insert_at_top=insert_at_top,
        )
        m.save()
        return str(m.path.resolve())

    if target == "contract":
        content = payload.get("content")
        if content is None:
            raise ValueError("payload.content is required for target=contract")
        m.contract.ensure()
        m.contract.body.write(content)
        m.save()
        return str(m.contract.path.resolve())

    if target == "contract-section":
        heading = payload.get("heading")
        if heading is None:
            raise ValueError("payload.heading is required for target=contract-section")
        sec_mode = payload.get("mode") or mode or "replace"
        needs_content = sec_mode != "delete"
        content = payload.get("content")
        if needs_content and content is None:
            raise ValueError("payload.content is required unless mode=delete")
        if not needs_content and content is not None:
            raise ValueError("payload.content forbidden with mode=delete")
        insert_after = payload.get("insert_after")
        insert_at_top = bool(payload.get("insert_at_top", False))
        if insert_after is not None and insert_at_top:
            raise ValueError(
                "payload.insert_after and payload.insert_at_top are mutually exclusive"
            )
        m.contract.ensure()
        m.contract.body.write_section(
            heading,
            content,
            level=int(payload.get("level", 2)),
            mode=sec_mode,
            create_if_missing=bool(payload.get("create_if_missing", False)),
            insert_after=insert_after,
            insert_at_top=insert_at_top,
        )
        m.save()
        return str(m.contract.path.resolve())

    if target == "workflow":
        wf_name = payload.get("name")
        if not wf_name:
            raise ValueError("payload.name is required for target=workflow")
        content = payload.get("content")
        if content is None:
            raise ValueError("payload.content is required for target=workflow")
        m.workflows.add(wf_name, content)
        return str((m.path.parent / "workflows" / wf_name / "workflow.md").resolve())

    raise ValueError(f"unknown target: {target!r}")


def split_module(
    source_module_path: str | Path,
    splits: list[dict],
    strategy: str = "comment",
    cwd: str = "",
) -> dict:
    """Atomically split one source module into one source + N new modules.

    Args:
        source_module_path: Path to the source module directory.
        splits:             List of split specs, each like
                            {"path": str, "name": str, "headings": [str, ...],
                             "owner"?: str}.
        strategy:           "comment" (default) — leave a `<!-- split: -->`
                            marker in the source; "move" — strip the section
                            from source entirely.
        cwd:                Project search base.

    Returns a dict describing the result::

        {
          "created":          [<abs path of each new module.md>, ...],
          "dependency_refs":  [{"module": ..., "action_required": ...}, ...],
        }
    """
    from cbi.resources import DNAModule

    if strategy not in ("comment", "move"):
        raise ValueError(f"strategy must be 'comment' or 'move', got: {strategy!r}")

    root = _resolve_root(cwd)
    result = DNAModule.split(
        Path(source_module_path),
        splits,
        root=root,
        dry_run=False,
        keep_source=(strategy == "comment"),
    )
    return {
        "created": [str(m.path.resolve()) for m in result.created_modules],
        "dependency_refs": list(result.dependency_refs_report or []),
    }


def write_doc(
    module_path: str | Path,
    file: str,
    body: str,
    cwd: str = "",
) -> str:
    """[deprecated] Whole-file body write of `.dna/<file>`, preserving frontmatter.

    Prefer `edit_module(target="body")` or `edit_module(target="contract")`.
    """
    from cbi._primitives.modules import write_module_doc
    if file not in ("module.md", "contract.md"):
        raise ValueError(f"file must be 'module.md' or 'contract.md', got: {file!r}")
    # cwd resolution is a no-op for write_module_doc — it works on absolute or
    # cwd-relative module_path directly; the cwd kwarg is kept for API symmetry.
    _ = _resolve_root(cwd)
    written = write_module_doc(Path(module_path), file, body)
    return str(written.resolve())


def write_section(
    module_path: str | Path,
    file: str,
    heading: str,
    content: str | None,
    mode: str,
    cwd: str = "",
    *,
    level: int = 2,
    create_if_missing: bool = False,
) -> str:
    """[deprecated] Section-level edit of `.dna/<file>`.

    Prefer `edit_module(target="section")` or `edit_module(target="contract-section")`.
    """
    from cbi._primitives.modules import write_module_section
    if file not in ("module.md", "contract.md"):
        raise ValueError(f"file must be 'module.md' or 'contract.md', got: {file!r}")
    _ = _resolve_root(cwd)
    result = write_module_section(
        Path(module_path),
        file,
        heading,
        level,
        mode,
        content,
        create_if_missing=create_if_missing,
        dry_run=False,
    )
    return str(Path(result).resolve())
