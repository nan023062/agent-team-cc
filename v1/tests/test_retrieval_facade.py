"""RetrievalFacade end-to-end (BM25 fallback path).

These tests construct RetrievalFacade directly with a tmp_path index_root
so they don't depend on .cbim/ being a real project directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.retrieval.config import RetrievalConfig
from engine.retrieval.facade import (
    Hit,
    IndexStats,
    RetrievalError,
    RetrievalFacade,
)


def _new_facade(tmp_path: Path) -> RetrievalFacade:
    return RetrievalFacade(tmp_path / "index", RetrievalConfig())  # provider=null


def test_unknown_source_rejected(tmp_path):
    f = _new_facade(tmp_path)
    with pytest.raises(RetrievalError):
        f.index_upsert("bogus", "d1", "x")
    with pytest.raises(RetrievalError):
        f.search("bogus", "q")
    with pytest.raises(RetrievalError):
        f.index_delete("bogus", "d1")


def test_invalid_args_rejected(tmp_path):
    f = _new_facade(tmp_path)
    with pytest.raises(RetrievalError):
        f.index_upsert("dna", "", "content")
    with pytest.raises(RetrievalError):
        f.index_upsert("dna", "d1", None)  # type: ignore[arg-type]
    with pytest.raises(RetrievalError):
        f.search("dna", "q", top_k=0)


def test_upsert_then_search_bm25(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "mod_a", "The quick brown fox", {"owner": "alice"})
    f.index_upsert("dna", "mod_b", "Lazy dogs sleep", {"owner": "bob"})
    hits = f.search("dna", "fox")
    assert len(hits) == 1
    assert hits[0].doc_id == "mod_a"
    assert hits[0].source == "dna"
    assert hits[0].metadata == {"owner": "alice"}
    assert hits[0].content == "The quick brown fox"
    assert hits[0].score > 0


def test_search_returns_empty_when_no_docs(tmp_path):
    f = _new_facade(tmp_path)
    assert f.search("dna", "anything") == []


def test_upsert_is_idempotent_update(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "mod_a", "alpha beta")
    f.index_upsert("dna", "mod_a", "gamma delta")
    assert f.search("dna", "alpha") == []
    hits = f.search("dna", "gamma")
    assert len(hits) == 1 and hits[0].doc_id == "mod_a"


def test_delete_removes(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "mod_a", "hello world")
    f.index_delete("dna", "mod_a")
    assert f.search("dna", "hello") == []


def test_delete_unknown_doc_is_noop(tmp_path):
    f = _new_facade(tmp_path)
    # No error.
    f.index_delete("dna", "does_not_exist")


def test_filters_apply_to_search(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("memory_medium", "m1", "decision X", {"type": "decision"})
    f.index_upsert("memory_medium", "m2", "decision Y", {"type": "fact"})
    hits = f.search("memory_medium", "decision", filters={"type": "decision"})
    assert [h.doc_id for h in hits] == ["m1"]


def test_persistence_across_facade_instances(tmp_path):
    f1 = _new_facade(tmp_path)
    f1.index_upsert("agents", "a1", "scout description")
    f1.index_upsert("agents", "a2", "coder description")

    f2 = RetrievalFacade(tmp_path / "index", RetrievalConfig())
    hits = f2.search("agents", "coder")
    assert len(hits) == 1 and hits[0].doc_id == "a2"


def test_stats_basic(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "mod_a", "hello")
    st = f.stats("dna")
    assert isinstance(st, IndexStats)
    assert st.source == "dna"
    assert st.total_docs == 1
    assert st.embedding_provider == "null"
    assert st.fallback_active is True
    assert st.index_size_bytes > 0
    assert st.last_upsert_at
    assert st.vector_dim is None


def test_stats_all_sources_when_none(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "mod_a", "x")
    res = f.stats()
    assert isinstance(res, list)
    sources = {s.source for s in res}
    assert sources == {"transcript", "memory_medium", "dna", "agents"}


def test_hit_to_dict_shape(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("dna", "m", "hello world", {"k": "v"})
    h = f.search("dna", "hello")[0]
    d = h.to_dict()
    assert set(d.keys()) == {"doc_id", "source", "score", "content", "metadata"}


def test_chinese_search(tmp_path):
    f = _new_facade(tmp_path)
    f.index_upsert("memory_medium", "m1", "向量检索系统设计")
    f.index_upsert("memory_medium", "m2", "图像识别管线")
    hits = f.search("memory_medium", "检索")
    assert [h.doc_id for h in hits] == ["m1"]


# --------------------------------------------------------------------------
# Regression: embedding provider that is "available" but degenerate.
#
# Symptom we are guarding against: provider.embed() returns a constant or
# near-zero vector for every input. VectorIndex.search() then produces tied
# cosine scores, and Python's stable sort hands back VectorBlob.doc_ids in
# insertion order (≈ indexed_at). The facade used to ship that "ranking"
# straight to the caller, masking the embedder failure as a working
# vector search. Fix: detect the tie and fall back to BM25.
# --------------------------------------------------------------------------


from engine.retrieval.embedding.base import EmbeddingProvider


class _ConstantEmbeddingProvider(EmbeddingProvider):
    """Stub that claims availability but returns a fixed vector every time.

    Models a real provider stuck on a cached / default / quantized-to-zero
    response. is_available() is True so the facade exercises the vector path.
    """

    name = "constant_stub"

    def __init__(self, dim: int = 4, fill: float = 0.0) -> None:
        self._dim = dim
        self._fill = fill

    def is_available(self) -> bool:
        return True

    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str):
        return [self._fill] * self._dim


def _facade_with_provider(tmp_path: Path, provider: EmbeddingProvider) -> RetrievalFacade:
    f = RetrievalFacade(tmp_path / "index", RetrievalConfig())
    f.provider = provider  # override the null provider for this test
    return f


@pytest.mark.parametrize("fill", [0.0, 1.0])
def test_facade_constant_embedding_does_not_collapse_to_insertion_order(tmp_path, fill):
    """A broken embedder must not produce indexed_at-ordered results.

    Acceptable behaviors per contract.md:
      * transparent fallback to BM25 (preferred — keeps callers working), OR
      * raise an error (acceptable — surfaces the failure loudly).

    Forbidden behavior:
      * silently return docs in indexed_at order while pretending to be a
        semantic ranking. This is what the bug looked like in the wild.
    """
    import time

    provider = _ConstantEmbeddingProvider(dim=4, fill=fill)
    f = _facade_with_provider(tmp_path, provider)

    # Five topically-distinct docs. Sleep between upserts so indexed_at
    # actually differs (second-resolution timestamps in store.now_iso).
    docs = [
        ("d_fox",     "the quick brown fox jumps over"),
        ("d_db",      "postgres index btree query planner"),
        ("d_cook",    "garlic butter shrimp recipe weeknight"),
        ("d_astro",   "supernova remnant pulsar magnetar"),
        ("d_legal",   "contract clause arbitration jurisdiction"),
    ]
    for doc_id, content in docs:
        f.index_upsert("dna", doc_id, content)
        time.sleep(1.05)  # cross a whole-second boundary for indexed_at

    insertion_order = [doc_id for doc_id, _ in docs]

    def _run(query: str, expected_top: str):
        try:
            hits = f.search("dna", query, top_k=5)
        except Exception:
            # "Loud failure" is an acceptable contract — the test passes.
            return
        # Otherwise we expect BM25 fallback to have done real work.
        got_order = [h.doc_id for h in hits]
        # Forbidden: returning the full corpus in indexed_at (insertion) order.
        assert got_order != insertion_order, (
            f"facade collapsed to insertion order for query={query!r}; "
            f"constant-embedding fallback to BM25 did not engage"
        )
        # And BM25 should put the lexically matching doc on top.
        assert hits and hits[0].doc_id == expected_top, (
            f"expected BM25 to rank {expected_top!r} first for {query!r}, "
            f"got {got_order}"
        )
        # All hits must still have a real float score (contract: Hit.score is float).
        for h in hits:
            assert isinstance(h.score, float)

    # Two unrelated queries — each should pick a different winner if BM25
    # is in charge; both would tie to insertion order under the bug.
    _run("fox", expected_top="d_fox")
    _run("pulsar", expected_top="d_astro")
