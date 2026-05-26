"""ContextRetrieval node unit tests.

Covers:
  - Empty user_request → empty buckets, SUCCESS.
  - Normal path: 4 sources called, results bucketed into three slots,
    recent_memory merged + sorted by score desc.
  - Per-source failure isolation: one source raises → other three still
    populate; node still SUCCESS.
  - Failure path: importing engine.retrieval blowing up is absorbed
    inside _safe_search (the @Catch outer wrapper in the tree is a
    belt-and-suspenders extra; we don't depend on it here).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.core.node import Status
from engine.execution.actions import context_retrieval as cr_mod
from engine.execution.actions.context_retrieval import ContextRetrieval


class _FakeHit:
    """Minimal stub of engine.retrieval.Hit with to_dict()."""

    def __init__(self, doc_id, source, score, content="", metadata=None):
        self.doc_id = doc_id
        self.source = source
        self.score = score
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "score": self.score,
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@pytest.fixture
def bb():
    return SimpleNamespace(user_request="", retrieved_context=None)


def test_empty_request_writes_empty_buckets(bb, monkeypatch):
    bb.user_request = "   "
    calls = []

    def _stub(src, query, top_k):
        calls.append((src, query, top_k))
        return []

    monkeypatch.setattr(cr_mod, "_safe_search", _stub)
    node = ContextRetrieval()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.retrieved_context == {
        "recent_memory": [],
        "agents": [],
        "module_knowledge": [],
    }
    # No search calls for an empty request.
    assert calls == []


def test_full_pull_buckets_and_orders(bb, monkeypatch):
    bb.user_request = "implement login"

    def _stub(src, query, top_k):
        assert query == "implement login"
        if src == "transcript":
            return [_FakeHit("t1", src, 0.3).to_dict()]
        if src == "memory_medium":
            return [_FakeHit("m1", src, 0.9).to_dict(),
                    _FakeHit("m2", src, 0.5).to_dict()]
        if src == "agents":
            return [_FakeHit("a1", src, 0.7).to_dict()]
        if src == "dna":
            return [_FakeHit("d1", src, 0.4).to_dict()]
        raise AssertionError(f"unexpected source {src!r}")

    monkeypatch.setattr(cr_mod, "_safe_search", _stub)
    node = ContextRetrieval()
    assert node.tick(bb) is Status.SUCCESS

    ctx = bb.retrieved_context
    # recent_memory = transcript + memory_medium, sorted by score desc.
    recent_scores = [h["score"] for h in ctx["recent_memory"]]
    assert recent_scores == sorted(recent_scores, reverse=True)
    recent_ids = [h["doc_id"] for h in ctx["recent_memory"]]
    assert recent_ids == ["m1", "a1" if False else "m2", "t1"][:0] + ["m1", "m2", "t1"]
    # Skip the typo trick — real assertion:
    assert recent_ids == ["m1", "m2", "t1"]

    assert [h["doc_id"] for h in ctx["agents"]] == ["a1"]
    assert [h["doc_id"] for h in ctx["module_knowledge"]] == ["d1"]


def test_per_source_failure_does_not_kill_others(bb, monkeypatch):
    bb.user_request = "x"

    def _stub_search(src, query, top_k=10, filters=None):
        if src == "transcript":
            raise RuntimeError("transcript index missing")
        return [_FakeHit(f"{src}-1", src, 1.0)]

    # Patch the actual import target inside _safe_search.
    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "search", _stub_search)

    node = ContextRetrieval()
    assert node.tick(bb) is Status.SUCCESS
    ctx = bb.retrieved_context
    assert ctx["recent_memory"] == [
        # transcript bombed → only memory_medium contributes.
        {"doc_id": "memory_medium-1", "source": "memory_medium",
         "score": 1.0, "content": "", "metadata": {}}
    ]
    assert [h["doc_id"] for h in ctx["agents"]] == ["agents-1"]
    assert [h["doc_id"] for h in ctx["module_knowledge"]] == ["dna-1"]


def test_import_failure_yields_empty(bb, monkeypatch):
    """If engine.retrieval can't be imported at all (e.g. broken module
    state), every _safe_search returns []. Node still SUCCESS with empty
    buckets."""
    bb.user_request = "y"

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __import__

    def _bad_import(name, *a, **kw):
        if name == "engine.retrieval":
            raise ImportError("simulated")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", _bad_import)
    node = ContextRetrieval()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.retrieved_context == {
        "recent_memory": [],
        "agents": [],
        "module_knowledge": [],
    }
