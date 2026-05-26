"""Phase 4 — smoke wiring tests for the two memory hooks.

These confirm `cbim_stop` and `cbim_session_start` successfully resolve
the v2 `engine.retrieval` import layout and run without raising. We
import the hook modules directly and call the private helpers — no
subprocess, no event protocol — so a regression in import wiring shows
up as an ImportError at collection time, not a silent hook-log failure.

v2 behavioural assertions:

  - cbim_stop._index_transcript replaces the old _distill: it pushes
    the raw JSONL into engine.retrieval source="transcript" instead of
    materialising a short-tier memory file.

  - cbim_session_start._build_context still runs the dream banner / log
    start / snapshot pipeline. The previous "load recent memory into
    additionalContext" job has moved into the execution behaviour tree
    (ContextRetrieval node), so the function no longer queries memory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_HOOKS_SRC = Path(__file__).resolve().parent.parent / "kernel" / "project" / "hooks_src"


@pytest.fixture(autouse=True)
def _hooks_on_path():
    s = str(_HOOKS_SRC)
    added = s not in sys.path
    if added:
        sys.path.insert(0, s)
    try:
        yield
    finally:
        if added:
            try:
                sys.path.remove(s)
            except ValueError:
                pass


def _make_min_transcript(tmp_path: Path, body: str = '{"role":"user","content":"hi"}\n') -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(body, encoding="utf-8")
    return transcript


def _isolate_index_root(monkeypatch, tmp_path: Path) -> Path:
    """Steer engine.retrieval's default facade at a per-test index root
    so the test doesn't bleed into (or read from) the real .cbim/index/."""
    from engine.retrieval import facade as _facade_mod

    index_root = tmp_path / ".cbim" / "index"
    monkeypatch.setattr(_facade_mod, "_resolve_index_root", lambda: index_root)
    _facade_mod.reset_default_facade()
    return index_root


def test_cbim_stop_index_transcript_wiring(monkeypatch, tmp_path):
    """cbim_stop._index_transcript reads the JSONL and routes it through
    engine.retrieval.index_upsert("transcript", ...). After the call,
    the transcript source should report total_docs >= 1."""
    import cbim_stop

    _isolate_index_root(monkeypatch, tmp_path)
    transcript = _make_min_transcript(tmp_path)

    cbim_stop._index_transcript(tmp_path, transcript)

    from engine.retrieval import stats
    s = stats("transcript")
    assert s.total_docs >= 1


def test_cbim_stop_index_transcript_swallows_unreadable(monkeypatch, tmp_path):
    """Missing file path must not raise — the hook MUST NOT block CC."""
    import cbim_stop

    _isolate_index_root(monkeypatch, tmp_path)
    cbim_stop._index_transcript(tmp_path, tmp_path / "missing.jsonl")


def test_cbim_stop_resolve_transcript_prefers_event_path(tmp_path):
    """When event supplies an existing transcript_path, that wins."""
    import cbim_stop

    transcript = _make_min_transcript(tmp_path)
    out = cbim_stop._resolve_transcript(tmp_path, str(transcript), session_id="abc")
    assert out == transcript


def test_cbim_stop_resolve_transcript_returns_none_when_missing(tmp_path):
    """Bad event path and no session_id => None, no raise."""
    import cbim_stop

    out = cbim_stop._resolve_transcript(tmp_path, "", session_id="")
    assert out is None


def test_cbim_session_start_wiring_resolves(monkeypatch, tmp_path):
    """cbim_session_start._build_context still composes and returns a
    str (possibly empty). It MUST NOT raise even when nothing exists on
    disk; the index sync paths are wrapped in safe_run."""
    import cbim_session_start

    _isolate_index_root(monkeypatch, tmp_path)
    (tmp_path / ".cbim" / "memory" / "medium").mkdir(parents=True)

    result = cbim_session_start._build_context(tmp_path, session_id="test-session")
    assert isinstance(result, str)


def test_cbim_session_start_refresh_indexes_handles_empty(monkeypatch, tmp_path):
    """_refresh_indexes runs three index passes; an empty project still
    completes cleanly."""
    import cbim_session_start

    _isolate_index_root(monkeypatch, tmp_path)
    cbim_session_start._refresh_indexes(tmp_path)
