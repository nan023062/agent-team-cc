"""memory v2 crud primitives — retrieval sync side-effects + tier guards.

Verifies the v2 contract (memory/crud/.dna/module.md, status=spec):
- write / update / delete reject tier='short' with ValueError.
- write performs a synchronous engine.retrieval.index_upsert with
  source='memory_medium' and a source_path metadata field.
- delete performs a synchronous engine.retrieval.index_delete.
- A retrieval-side failure propagates out of the primitive.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import engine.retrieval as retrieval
import engine.retrieval.facade as retrieval_facade
from memory.crud.file_backend import FileBackend
from memory.crud.primitives import (
    MEDIUM,
    RETRIEVAL_SOURCE,
    delete,
    update,
    write,
)


@pytest.fixture
def short_tmp_path():
    """Bypass pytest's deeply-nested tmp_path on Windows.

    The retrieval store percent-encodes doc_ids (which include the full
    medium-file path) into filenames; combined with pytest's default
    ``...pytest-of-<user>/pytest-NNN/<test_name_truncated_to_30>/...``
    layout we routinely blow past Windows' 260-char MAX_PATH. The fix
    is to root the test workspace at a short prefix instead.
    """
    import os
    import shutil
    import tempfile

    short = Path(tempfile.mkdtemp(prefix="mv2_", dir=os.environ.get("TEMP") or None))
    try:
        yield short
    finally:
        shutil.rmtree(short, ignore_errors=True)


@pytest.fixture
def isolated_retrieval(short_tmp_path, monkeypatch):
    """Point engine.retrieval at a tmp index_root and reset the singleton.

    Yields the live RetrievalFacade so assertions can call search/stats/
    verify_consistency against the same instance crud touches.
    """
    index_root = short_tmp_path / "i"
    fac = retrieval_facade.RetrievalFacade(index_root)
    monkeypatch.setattr(retrieval_facade, "_default_facade", fac)
    yield fac
    retrieval_facade.reset_default_facade()


def _make_medium_file(store: Path, name: str, body: str,
                      frontmatter: dict | None = None) -> Path:
    medium_dir = store / "medium"
    medium_dir.mkdir(parents=True, exist_ok=True)
    p = medium_dir / name
    fm = ""
    if frontmatter:
        lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
        fm = f"---\n{lines}\n---\n\n"
    p.write_text(fm + body + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tier guards
# ---------------------------------------------------------------------------

def test_write_rejects_short_tier(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-a.md", "body")
    backend = FileBackend(store)
    with pytest.raises(ValueError, match="short"):
        write(p, "short", backend)


def test_update_rejects_short_tier(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-a.md", "body")
    backend = FileBackend(store)
    with pytest.raises(ValueError, match="short"):
        update(p, "short", backend)


# ---------------------------------------------------------------------------
# Retrieval sync — write
# ---------------------------------------------------------------------------

def test_write_upserts_into_retrieval_memory_medium(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(
        store, "2026-05-22-a.md", "alpha distinctive body",
        frontmatter={"tier": "medium", "tags": "alpha"},
    )
    backend = FileBackend(store)
    write(p, MEDIUM, backend)

    hits = isolated_retrieval.search(RETRIEVAL_SOURCE, "alpha distinctive", top_k=5)
    doc_ids = [h.doc_id for h in hits]
    assert str(p) in doc_ids


def test_write_passes_source_path_into_retrieval(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-b.md", "needle body")
    backend = FileBackend(store)
    write(p, MEDIUM, backend)

    # Look the doc up via the facade's internal state to confirm source_path
    # was promoted to a first-class DocRecord field.
    state = isolated_retrieval._get(RETRIEVAL_SOURCE)
    rec = state.records[str(p)]
    assert rec.source_path == str(p)


def test_update_re_upserts(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-c.md", "v1 body content")
    backend = FileBackend(store)
    write(p, MEDIUM, backend)

    # Rewrite with new content; update() should refresh the retrieval index.
    p.write_text("v2 body content with rewritten phrase\n", encoding="utf-8")
    update(p, MEDIUM, backend)

    hits = isolated_retrieval.search(RETRIEVAL_SOURCE, "rewritten phrase", top_k=5)
    assert any(h.doc_id == str(p) for h in hits)


# ---------------------------------------------------------------------------
# Retrieval sync — delete
# ---------------------------------------------------------------------------

def test_delete_removes_from_retrieval(short_tmp_path, isolated_retrieval):
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-d.md", "doomed body")
    backend = FileBackend(store)
    write(p, MEDIUM, backend)

    # Sanity: present.
    assert any(
        h.doc_id == str(p)
        for h in isolated_retrieval.search(RETRIEVAL_SOURCE, "doomed", top_k=5)
    )

    delete(p, backend)
    assert not any(
        h.doc_id == str(p)
        for h in isolated_retrieval.search(RETRIEVAL_SOURCE, "doomed", top_k=5)
    )


# ---------------------------------------------------------------------------
# Retrieval failure propagation
# ---------------------------------------------------------------------------

def test_write_propagates_retrieval_error(short_tmp_path, monkeypatch):
    """If retrieval.index_upsert raises, write() must surface the error
    (no swallow-and-success). Caller decides whether to roll back."""
    store = short_tmp_path / "m"
    p = _make_medium_file(store, "2026-05-22-e.md", "body")
    backend = FileBackend(store)

    def _boom(**kwargs):
        raise retrieval.RetrievalError("simulated persist failure")

    monkeypatch.setattr("engine.retrieval.index_upsert", _boom)

    with pytest.raises(retrieval.RetrievalError, match="simulated"):
        write(p, MEDIUM, backend)
