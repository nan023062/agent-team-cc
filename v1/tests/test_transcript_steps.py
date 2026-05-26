"""Unit tests for the v2 transcript-driven dream-loop leaves.

Covers TranscriptScan / DistillGate / TranscriptDelete in isolation
(no Runner, no MCP, no real ~/.claude/projects/).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from engine.core.node import Status
from engine.dream.actions import transcript_steps as ts_mod
from engine.dream.actions.transcript_steps import (
    DistillGate,
    TranscriptDelete,
    TranscriptScan,
)
from memory._lib.paths import cc_project_slug as _project_slug
from engine.dream.core.blackboard import DreamBlackboard


# ---------------------------------------------------------------------------
# slug helper
# ---------------------------------------------------------------------------

def test_project_slug_drive_letter_and_backslashes():
    assert _project_slug(Path("D:\\GitRepository\\cbim-kernel")) == \
        "D--GitRepository-cbim-kernel"


def test_project_slug_posix_path():
    assert _project_slug(Path("/home/linan/proj")) == "-home-linan-proj"


# ---------------------------------------------------------------------------
# TranscriptScan
# ---------------------------------------------------------------------------

@pytest.fixture
def bb() -> DreamBlackboard:
    b = DreamBlackboard()
    b.run_id = "test-run"
    return b


def _aged_file(parent: Path, name: str, age_seconds: float) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    p = parent / name
    p.write_text('{"role": "user"}\n', encoding="utf-8")
    past = time.time() - age_seconds
    os.utime(p, (past, past))
    return p


def test_scan_empty_dir_returns_empty(bb, tmp_path):
    node = TranscriptScan(transcripts_dir=tmp_path / "nonexistent")
    assert node.tick(bb) is Status.SUCCESS
    assert bb.transcript_paths == []


def test_scan_skips_young_files(bb, tmp_path):
    scan_dir = tmp_path / "transcripts"
    _aged_file(scan_dir, "young.jsonl", age_seconds=60)
    node = TranscriptScan(transcripts_dir=scan_dir)
    assert node.tick(bb) is Status.SUCCESS
    assert bb.transcript_paths == []


def test_scan_picks_mature_files_sorted_by_mtime(bb, tmp_path):
    scan_dir = tmp_path / "transcripts"
    older = _aged_file(scan_dir, "a.jsonl", age_seconds=3 * 86400)
    newer_but_still_mature = _aged_file(
        scan_dir, "b.jsonl", age_seconds=2 * 86400,
    )
    # Young file should be skipped.
    _aged_file(scan_dir, "c.jsonl", age_seconds=60)
    node = TranscriptScan(transcripts_dir=scan_dir)
    assert node.tick(bb) is Status.SUCCESS
    assert bb.transcript_paths == [str(older), str(newer_but_still_mature)]


def test_scan_ignores_non_jsonl(bb, tmp_path):
    scan_dir = tmp_path / "transcripts"
    _aged_file(scan_dir, "ignored.txt", age_seconds=3 * 86400)
    _aged_file(scan_dir, "kept.jsonl", age_seconds=3 * 86400)
    node = TranscriptScan(transcripts_dir=scan_dir)
    assert node.tick(bb) is Status.SUCCESS
    assert len(bb.transcript_paths) == 1
    assert bb.transcript_paths[0].endswith("kept.jsonl")


# ---------------------------------------------------------------------------
# DistillGate
# ---------------------------------------------------------------------------

def test_gate_skips_when_no_transcripts(bb):
    bb.transcript_paths = []
    node = DistillGate()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mem_distill_dispatched is False
    assert bb.mem_distill_result == {
        "skipped": True,
        "reason": "no_mature_transcripts",
    }


def test_gate_dispatches_when_transcripts_present(bb):
    bb.transcript_paths = ["/tmp/x.jsonl"]
    node = DistillGate()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mem_distill_dispatched is True
    # Result must NOT be pre-filled — Collect owns this slot.
    assert bb.mem_distill_result is None


# ---------------------------------------------------------------------------
# TranscriptDelete
# ---------------------------------------------------------------------------

def test_delete_skips_when_dispatch_was_skipped(bb, tmp_path, monkeypatch):
    bb.mem_distill_dispatched = False
    bb.mem_distill_result = {"skipped": True, "reason": "no_mature_transcripts"}
    calls = []
    monkeypatch.setattr(ts_mod, "Path", Path)  # sanity

    def _fake_index_delete(source, doc_id):
        calls.append((source, doc_id))

    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "index_delete", _fake_index_delete)

    node = TranscriptDelete()
    assert node.tick(bb) is Status.SUCCESS
    assert calls == []
    assert bb.transcript_delete_errors == []


def test_delete_unlinks_distilled_paths_and_calls_retrieval(
    bb, tmp_path, monkeypatch,
):
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    p1.write_text("{}\n", encoding="utf-8")
    p2.write_text("{}\n", encoding="utf-8")

    bb.mem_distill_dispatched = True
    bb.mem_distill_result = {
        "skipped": False,
        "distilled_paths": [str(p1), str(p2)],
        "medium_entries_written": [],
        "skipped_paths": [],
        "errors": [],
    }

    calls = []

    def _fake_index_delete(source, doc_id):
        calls.append((source, doc_id))

    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "index_delete", _fake_index_delete)

    node = TranscriptDelete()
    assert node.tick(bb) is Status.SUCCESS
    assert not p1.exists()
    assert not p2.exists()
    assert calls == [
        ("transcript", str(p1)),
        ("transcript", str(p2)),
    ]
    assert bb.transcript_delete_errors == []


def test_delete_missing_file_is_idempotent(bb, tmp_path, monkeypatch):
    """Re-running a tick that previously deleted the file must not blow up."""
    p1 = tmp_path / "gone.jsonl"
    # File never created.

    bb.mem_distill_dispatched = True
    bb.mem_distill_result = {
        "skipped": False,
        "distilled_paths": [str(p1)],
        "medium_entries_written": [],
        "skipped_paths": [],
        "errors": [],
    }

    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "index_delete",
                        lambda source, doc_id: None)

    node = TranscriptDelete()
    assert node.tick(bb) is Status.SUCCESS
    assert bb.transcript_delete_errors == []


def test_delete_records_retrieval_failure_but_still_unlinks(
    bb, tmp_path, monkeypatch,
):
    p1 = tmp_path / "x.jsonl"
    p1.write_text("{}\n", encoding="utf-8")

    bb.mem_distill_dispatched = True
    bb.mem_distill_result = {
        "skipped": False,
        "distilled_paths": [str(p1)],
        "medium_entries_written": [],
        "skipped_paths": [],
        "errors": [],
    }

    def _boom(source, doc_id):
        raise RuntimeError("retrieval down")

    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "index_delete", _boom)

    node = TranscriptDelete()
    assert node.tick(bb) is Status.SUCCESS
    assert not p1.exists(), "unlink must proceed even if retrieval fails"
    assert len(bb.transcript_delete_errors) == 1
    err = bb.transcript_delete_errors[0]
    assert err["stage"] == "index_delete"
    assert "retrieval down" in err["error"]


def test_delete_with_error_report_and_no_paths_is_noop(bb, tmp_path, monkeypatch):
    bb.mem_distill_dispatched = True
    bb.mem_distill_result = {"error": "report_not_a_dict", "skipped": False}

    calls = []

    def _fake_index_delete(source, doc_id):
        calls.append((source, doc_id))

    import engine.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "index_delete", _fake_index_delete)

    node = TranscriptDelete()
    assert node.tick(bb) is Status.SUCCESS
    assert calls == []
