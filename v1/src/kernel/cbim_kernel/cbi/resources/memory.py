"""
memory.py — Memory resource.

Thin object facade over memory/engine/engine.py:MemoryEngine. A Memory
instance is one markdown entry file under .cbim/memory/<tier>/. The
class-level helpers (create, query, list_all, cleanup) wrap the engine's
write / search / maintenance APIs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ._base import Resource
from ._body import Body
from ._frontmatter import Frontmatter
from ._io import atomic_write_text
from cbim_kernel.services._fm import parse_frontmatter, strip_frontmatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_store(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root) / ".cbim" / "memory"
    from cbim_kernel.context import cbim_dir
    return cbim_dir() / "memory"


def _build_engine(store_dir: Path):
    """Construct a MemoryEngine with the default FileBackend.

    Mirrors memory/engine/cli.py:_build_engine so behaviour stays in lockstep.
    """
    from cbim_kernel.memory.engine.engine import MemoryEngine
    from cbim_kernel.memory.engine.file_backend import FileBackend
    return MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)


# ---------------------------------------------------------------------------
# Memory resource
# ---------------------------------------------------------------------------

class Memory(Resource):

    def __init__(self, path: Path, *, frontmatter: Frontmatter, body: Body,
                 store_dir: Path | None = None):
        self._path = path.resolve()
        self._id = path.stem
        self._dirty = False
        self._store_dir = (store_dir or path.parent.parent).resolve()
        self.frontmatter = frontmatter
        self.body = body
        frontmatter._on_change = self._mark_dirty
        body._on_change = self._mark_dirty

    # ------------------------------------------------------------------
    # Classmethods
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str, **_kw) -> "Memory":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"memory entry not found: {p}")
        raw = p.read_text(encoding="utf-8")
        return cls(
            p,
            frontmatter=Frontmatter(parse_frontmatter(raw)),
            body=Body(strip_frontmatter(raw)),
        )

    @classmethod
    def create(
        cls,
        *,
        slug: str,
        content: str,
        tier: str = "short",
        kind: str = "manual",
        root: Path | None = None,
    ) -> "Memory":
        """Write a new memory entry file and register it with the engine."""
        store = _default_store(root)
        slug_clean = slug.strip().replace(" ", "-")
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filename = f"{ts}-{kind}-{slug_clean}.md"
        path = store / tier / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        engine = _build_engine(store)
        engine.add(path, tier)
        return cls.load(path)

    @classmethod
    def exists(cls, path: Path | str, **_kw) -> bool:
        return Path(path).is_file()

    @classmethod
    def query(
        cls,
        text: str,
        *,
        tier: str | None = None,
        top_k: int = 5,
        verbose: bool = False,
        root: Path | None = None,
    ) -> list[dict]:
        """Return query_verbose result dicts (doc_id, score, metadata).

        The `verbose` flag is accepted for interface symmetry; callers can
        inspect each dict regardless.
        """
        store = _default_store(root)
        engine = _build_engine(store)
        return engine.query_verbose(text, tier=tier, top_k=top_k)

    @classmethod
    def list_all(
        cls,
        *,
        tier: str | None = None,
        root: Path | None = None,
    ) -> list["Memory"]:
        store = _default_store(root)
        tiers = [tier] if tier else ["short", "medium"]
        out: list[Memory] = []
        for t in tiers:
            tier_dir = store / t
            if not tier_dir.is_dir():
                continue
            for md in sorted(tier_dir.glob("*.md")):
                try:
                    out.append(cls.load(md))
                except FileNotFoundError:
                    continue
        return out

    @classmethod
    def cleanup(
        cls,
        *,
        keep_days: int = 3,
        root: Path | None = None,
    ) -> int:
        store = _default_store(root)
        engine = _build_engine(store)
        return engine.cleanup_short(keep_days=keep_days)

    # ------------------------------------------------------------------
    # Save / Promote
    # ------------------------------------------------------------------

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
        # Re-index so the engine picks up the new content.
        tier = self.frontmatter.get("tier") or self._path.parent.name
        engine = _build_engine(self._store_dir)
        engine.add(self._path, tier)
        self._mark_clean()

    def delete(self, *, force: bool = False) -> None:
        """Remove this entry from the engine index and unlink the file.

        Overrides the base default (which only unlinks) so the backend index
        stays consistent — leaving a stale doc_id behind would surface as a
        phantom hit in `Memory.query`.
        """
        engine = _build_engine(self._store_dir)
        engine.delete(self._path)
        if self._path.is_file():
            self._path.unlink()

    def promote(self, to_tier: str) -> None:
        """Move this entry from its current tier directory to <to_tier>/.

        Updates the engine index (delete old doc_id, re-add at new path) and
        rewrites the in-memory `tier` field in frontmatter.
        """
        if to_tier not in ("short", "medium"):
            raise ValueError(f"tier must be 'short' or 'medium', got {to_tier!r}")
        new_path = self._store_dir / to_tier / self._path.name
        new_path.parent.mkdir(parents=True, exist_ok=True)

        engine = _build_engine(self._store_dir)
        engine.delete(self._path)
        self._path.rename(new_path)
        self._path = new_path
        self.frontmatter.set("tier", to_tier)
        # Persist the tier update + re-index.
        self.save()
