"""Phase 4C — smoke wiring tests for the two memory hooks.

These confirm `cbim_stop._distill` and `cbim_session_start._build_context`
successfully resolve the new `memory.*` import layout (no more
`memory.engine.*` aliases) and run without raising.

We import the hook modules directly and call the private helpers — no
subprocess, no event protocol — so a regression in import wiring shows up
as an ImportError at collection time, not a silent hook-log failure.
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


def _make_min_transcript(tmp_path: Path) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("", encoding="utf-8")
    return transcript


def test_cbim_stop_wiring_resolves(tmp_path):
    """cbim_stop._distill builds backend + calls write_session via new
    import paths (memory._config / memory.crud.file_backend /
    memory.crud.session_writer) without raising."""
    import cbim_stop

    (tmp_path / ".cbim" / "memory" / "short").mkdir(parents=True)
    transcript = _make_min_transcript(tmp_path)

    cbim_stop._distill(tmp_path, str(transcript))


def test_cbim_session_start_wiring_resolves(tmp_path):
    """cbim_session_start._build_context builds backend + calls
    load_context via new import paths (memory._config /
    memory.crud.file_backend / memory.session_loader) without raising;
    returns a str (may be empty)."""
    import cbim_session_start

    (tmp_path / ".cbim" / "memory" / "short").mkdir(parents=True)

    result = cbim_session_start._build_context(tmp_path, session_id="test-session")
    assert isinstance(result, str)
