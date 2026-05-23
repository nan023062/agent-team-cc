"""
workflow.py — Workflow resource.

A workflow lives at <module>/.dna/workflows/<name>/workflow.md and describes
a repeatable process. Same shape as Skill: single markdown file with optional
frontmatter.
"""

from __future__ import annotations

from pathlib import Path

from ._base import Resource
from ._body import Body
from ._frontmatter import Frontmatter
from ._io import atomic_write_text
from services._fm import strip_frontmatter


class Workflow(Resource):

    def __init__(self, path: Path, *, frontmatter: Frontmatter, body: Body):
        self._path = path.resolve()
        # id is the workflow folder name (parent dir of workflow.md)
        self._id = path.parent.name if path.name == "workflow.md" else path.stem
        self._dirty = False
        self.frontmatter = frontmatter
        self.body = body
        frontmatter._on_change = self._mark_dirty
        body._on_change = self._mark_dirty

    @classmethod
    def load(cls, path: Path | str, *, root: Path | None = None) -> "Workflow":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"workflow not found: {p}")
        raw = p.read_text(encoding="utf-8")
        return cls(
            p,
            frontmatter=Frontmatter.parse(raw),
            body=Body(strip_frontmatter(raw)),
        )

    @classmethod
    def create(cls, path: Path | str, *, content: str = "", **kwargs) -> "Workflow":
        p = Path(path)
        if p.exists():
            raise FileExistsError(f"workflow already exists: {p}")
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(p, content)
        return cls.load(p)

    @classmethod
    def exists(cls, path: Path | str, *, root: Path | None = None) -> bool:
        return Path(path).is_file()

    def save(self) -> None:
        fm = self.frontmatter.render() if self.frontmatter.to_dict() else ""
        body = self.body.read()
        if fm:
            text = fm + "\n" + body if not body.startswith("\n") else fm + body
        else:
            text = body
        if not text.endswith("\n"):
            text += "\n"
        atomic_write_text(self._path, text)
        self._mark_clean()
