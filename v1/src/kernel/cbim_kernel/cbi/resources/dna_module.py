"""
dna_module.py — DNAModule resource.

A module lives at <module>/.dna/ with:
    module.md            — frontmatter + body (positioning / decisions / etc.)
    contract.md          — optional public contract
    workflows/<name>/workflow.md — optional workflow specs

DNAModule is the in-memory mirror, built on top of the cbi/_primitives/modules.py
primitives (load_module, init_module, list_modules, update_index, _build_module_md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator

from ._base import Resource
from ._body import Body
from ._frontmatter import Frontmatter
from ._io import atomic_write_text
from .workflow import Workflow
from cbim_kernel.cbi._primitives import modules as _mod_eng
from cbim_kernel.services._fm import parse_frontmatter, strip_frontmatter


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

class ModuleFrontmatter(Frontmatter):
    _SCHEMA = (
        "name", "owner", "description",
        "keywords", "dependencies", "includeDirs",
    )


# ---------------------------------------------------------------------------
# Contract sub-object
# ---------------------------------------------------------------------------

class Contract:
    """The optional <module>/.dna/contract.md file."""

    def __init__(self, path: Path, body: Body, *, parent: "DNAModule"):
        self._path = path
        self.body = body
        self._parent = parent
        self._dirty = False
        body._on_change = self._mark_dirty

    def exists(self) -> bool:
        return self._path.is_file()

    def ensure(self, *, name: str | None = None) -> "Contract":
        """Create contract.md with a default skeleton if absent."""
        if not self._path.is_file():
            display = name or self._parent.frontmatter.get("name", self._parent.id)
            text = f"# {display} — Contract\n\n## Interfaces\n\n## Events\n"
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self._path, text)
            self.body.write(text)
            self._dirty = False
        return self

    def delete(self) -> None:
        if self._path.is_file():
            self._path.unlink()
            self.body.write("")
            self._dirty = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _mark_dirty(self) -> None:
        self._dirty = True
        # Propagate to parent so DNAModule.dirty reflects contract edits too.
        self._parent._mark_dirty()


# ---------------------------------------------------------------------------
# Workflow collection
# ---------------------------------------------------------------------------

class WorkflowCollection:
    """View over <module>/.dna/workflows/*/workflow.md."""

    def __init__(self, workflows_dir: Path):
        self._dir = workflows_dir

    def list(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(w.parent.name for w in self._dir.glob("*/workflow.md"))

    def get(self, name: str) -> Workflow:
        return Workflow.load(self._dir / name / "workflow.md")

    def add(self, name: str, content: str = "") -> Workflow:
        target = self._dir / name / "workflow.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        return Workflow.create(target, content=content)

    def remove(self, name: str) -> None:
        target = self._dir / name / "workflow.md"
        if target.is_file():
            target.unlink()

    def __contains__(self, name: str) -> bool:
        return (self._dir / name / "workflow.md").is_file()


# ---------------------------------------------------------------------------
# DNAModule
# ---------------------------------------------------------------------------

class DNAModule(Resource):

    def __init__(
        self,
        mod_dir: Path,
        root: Path,
        *,
        frontmatter: ModuleFrontmatter,
        body: Body,
        legacy: bool = False,
    ):
        self._mod_dir = mod_dir.resolve()
        self._root = root.resolve()
        self._aimod = self._mod_dir / ".dna"
        self._path = (self._aimod / "module.md").resolve()
        try:
            rel = self._mod_dir.relative_to(self._root).as_posix()
        except ValueError:
            rel = self._mod_dir.as_posix()
        self._id = rel or "."
        self._dirty = False
        self._legacy = legacy
        self.frontmatter = frontmatter
        self.body = body
        self.workflows = WorkflowCollection(self._aimod / "workflows")
        # Lazy contract sub-object: read existing body or empty.
        contract_path = self._aimod / "contract.md"
        contract_body = (
            contract_path.read_text(encoding="utf-8")
            if contract_path.is_file() else ""
        )
        self.contract = Contract(contract_path, Body(contract_body), parent=self)
        frontmatter._on_change = self._mark_dirty
        body._on_change = self._mark_dirty

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_root(root: Path | None) -> Path:
        if root is not None:
            return Path(root).resolve()
        from cbim_kernel.context import project_root
        return project_root().resolve()

    # ------------------------------------------------------------------
    # Classmethods
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        mod_dir: Path | str,
        *,
        root: Path | None = None,
    ) -> "DNAModule":
        mod_path = Path(mod_dir)
        actual_root = cls._resolve_root(root)
        aimod = mod_path / ".dna"
        module_md = aimod / "module.md"
        legacy_json = aimod / "module.json"

        if module_md.is_file():
            raw = module_md.read_text(encoding="utf-8")
            fm = ModuleFrontmatter(parse_frontmatter(raw))
            body = Body(strip_frontmatter(raw))
            return cls(mod_path, actual_root, frontmatter=fm, body=body)

        if legacy_json.is_file():
            # Legacy format: synthesize a frontmatter dict from JSON and load
            # architecture.md as the body. Saving will convert to new format.
            print(
                f"[DEPRECATED] {mod_path}: using legacy module.json + architecture.md; "
                f"migrate to module.md",
                file=sys.stderr,
            )
            data = json.loads(legacy_json.read_text(encoding="utf-8"))
            fm = ModuleFrontmatter({
                "name": data.get("name", ""),
                "owner": data.get("owner", ""),
                "description": data.get("description", ""),
                "keywords": data.get("keywords", []),
                "dependencies": data.get("dependencies", []),
            })
            arch_path = aimod / "architecture.md"
            body_text = (
                arch_path.read_text(encoding="utf-8")
                if arch_path.is_file() else ""
            )
            return cls(
                mod_path, actual_root,
                frontmatter=fm,
                body=Body(body_text),
                legacy=True,
            )

        raise FileNotFoundError(
            f"no .dna/ module found at: {mod_path} (missing {module_md})"
        )

    @classmethod
    def create(
        cls,
        mod_dir: Path | str,
        *,
        name: str,
        owner: str,
        description: str = "",
        type: str = "leaf",
        with_contract: bool = False,
        root: Path | None = None,
    ) -> "DNAModule":
        mod_path = Path(mod_dir)
        actual_root = cls._resolve_root(root)
        _mod_eng.init_module(
            mod_path,
            name=name,
            owner=owner,
            description=description,
            with_contract=with_contract,
            type_=type,
            project_root=actual_root,
        )
        return cls.load(mod_path, root=actual_root)

    @classmethod
    def exists(
        cls,
        mod_dir: Path | str,
        *,
        root: Path | None = None,
    ) -> bool:
        p = Path(mod_dir)
        return (p / ".dna" / "module.md").is_file() or (p / ".dna" / "module.json").is_file()

    @classmethod
    def list_all(
        cls,
        *,
        root: Path | None = None,
        use_registry: bool = True,
    ) -> list["DNAModule"]:
        actual_root = cls._resolve_root(root)
        out: list[DNAModule] = []
        # Walk the registry (or scan) and load each one through the resource
        # constructor so callers get rich objects, not dicts.
        if use_registry:
            registered = _mod_eng.read_index(actual_root)
            if registered:
                for rel in registered:
                    mod_dir = actual_root if rel == "." else (actual_root / rel)
                    try:
                        out.append(cls.load(mod_dir, root=actual_root))
                    except FileNotFoundError:
                        continue
                return out
        # Fallback: full scan via the engine helper.
        for raw in _mod_eng._scan_modules(actual_root):
            rel = raw["path"]
            mod_dir = actual_root if rel == "." else (actual_root / rel)
            try:
                out.append(cls.load(mod_dir, root=actual_root))
            except FileNotFoundError:
                continue
        return out

    @classmethod
    def reindex(cls, *, root: Path | None = None) -> None:
        actual_root = cls._resolve_root(root)
        _mod_eng.update_index(actual_root)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _render(self) -> str:
        """Return the in-memory module.md text (frontmatter + body) that save()
        would write. No filesystem touch — used by dry-run paths."""
        meta = self.frontmatter.to_dict()
        body_text = self.body.read()
        return _mod_eng._build_module_md(meta, body_text)

    def save(self) -> None:
        """Atomically write module.md (and contract.md if dirty)."""
        # If we loaded from legacy format, on save we write the new module.md
        # alongside; we do NOT delete legacy files automatically — migration is
        # an explicit action.
        rendered = self._render()
        atomic_write_text(self._path, rendered)

        if self.contract.dirty and self.contract.body.read():
            atomic_write_text(self.contract.path, self.contract.body.read())
            self.contract._dirty = False

        self._mark_clean()

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[Workflow]:
        for name in self.workflows.list():
            yield self.workflows.get(name)
