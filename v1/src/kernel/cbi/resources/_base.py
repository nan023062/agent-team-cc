"""
_base.py — Resource protocol.

A Resource is a single addressable, persistent markdown-with-frontmatter
artifact on disk (or a small directory of related markdown files). The
protocol gives every concrete resource the same lifecycle surface:

    load / create / exists  — classmethods that build the in-memory object
    save / delete / archive — instance methods that mutate the filesystem
    id / path / dirty       — properties

Subclasses must implement load/create/exists/save; delete/archive have
sane defaults that subclasses may override.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Resource:
    """Abstract base for all kernel resource objects.

    Lifecycle invariant: an instance returned by load() / create() reflects
    on-disk state at construction time; in-memory edits flip `.dirty` to True
    and only land on disk when `.save()` is called.
    """

    # Subclasses set their on-disk path here (absolute).
    _path: Path
    _id: str
    _dirty: bool

    # ------------------------------------------------------------------
    # Classmethods — subclasses MUST implement
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, identifier: Any, *, root: Path | None = None) -> "Resource":
        raise NotImplementedError

    @classmethod
    def create(cls, identifier: Any, **kwargs: Any) -> "Resource":
        raise NotImplementedError

    @classmethod
    def exists(cls, identifier: Any, *, root: Path | None = None) -> bool:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Instance methods — save MUST be implemented; others have defaults
    # ------------------------------------------------------------------

    def save(self) -> None:
        raise NotImplementedError

    def delete(self, *, force: bool = False) -> None:
        """Remove the resource from disk. Subclasses override when the
        resource owns more than a single file (e.g. agent dir, .dna dir)."""
        if self._path.is_file():
            self._path.unlink()
        elif self._path.is_dir():
            import shutil
            if not force:
                raise RuntimeError(
                    f"delete on directory requires force=True: {self._path}"
                )
            shutil.rmtree(self._path)

    def archive(self) -> Path:
        """Default archive: rename file to <name>.archived. Subclasses with
        richer archival semantics (e.g. Agent renames to .md.archived) override."""
        if not self._path.exists():
            raise FileNotFoundError(f"not found: {self._path}")
        archived = self._path.with_suffix(self._path.suffix + ".archived")
        self._path.rename(archived)
        return archived

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def path(self) -> Path:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    # ------------------------------------------------------------------
    # Internal helpers for subclasses
    # ------------------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _mark_clean(self) -> None:
        self._dirty = False
