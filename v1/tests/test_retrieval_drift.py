"""Drift / verify_consistency tests."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from engine.retrieval.config import RetrievalConfig
from engine.retrieval.facade import RetrievalError, RetrievalFacade


def _facade(tmp_path: Path) -> RetrievalFacade:
    return RetrievalFacade(tmp_path / "index", RetrievalConfig())


def test_verify_invalid_mode_rejected(tmp_path):
    f = _facade(tmp_path)
    with pytest.raises(RetrievalError):
        f.verify_consistency("dna", "weird")


def test_fast_check_no_drift_when_clean(tmp_path):
    f = _facade(tmp_path)
    src = tmp_path / "src.md"
    src.write_text("hello world", encoding="utf-8")
    f.index_upsert("dna", "d1", src.read_text(encoding="utf-8"), {"source_path": str(src)})
    report = f.verify_consistency("dna", "fast")
    assert report.source == "dna"
    assert report.mode == "fast"
    assert report.checked == 1
    assert report.drifted == []
    assert report.repaired == []
    assert report.failed == []


def test_fast_check_detects_mtime_change_and_repairs(tmp_path):
    f = _facade(tmp_path)
    src = tmp_path / "src.md"
    src.write_text("hello world", encoding="utf-8")
    f.index_upsert("dna", "d1", src.read_text(encoding="utf-8"), {"source_path": str(src)})

    # Modify source file (changes mtime + size).
    time.sleep(0.01)
    src.write_text("hello brand new world", encoding="utf-8")

    report = f.verify_consistency("dna", "fast")
    assert report.drifted == ["d1"]
    assert report.repaired == ["d1"]
    # Re-search should now find the new content.
    hits = f.search("dna", "brand")
    assert len(hits) == 1 and hits[0].doc_id == "d1"


def test_fast_check_deletes_when_source_gone(tmp_path):
    f = _facade(tmp_path)
    src = tmp_path / "src.md"
    src.write_text("hello", encoding="utf-8")
    f.index_upsert("dna", "d1", "hello", {"source_path": str(src)})
    src.unlink()
    report = f.verify_consistency("dna", "fast")
    assert "d1" in report.drifted
    assert "d1" in report.repaired
    # Doc should no longer be searchable.
    assert f.search("dna", "hello") == []


def test_full_check_catches_hash_drift_when_mtime_replayed(tmp_path):
    """Same mtime + same size, different content — fast misses, full catches."""
    f = _facade(tmp_path)
    src = tmp_path / "src.md"
    src.write_text("alpha", encoding="utf-8")  # 5 bytes
    f.index_upsert("dna", "d1", "alpha", {"source_path": str(src)})

    # Overwrite with same length but rewind mtime to the recorded value.
    rec = f._sources["dna"].records["d1"]
    src.write_text("BRAVO", encoding="utf-8")  # also 5 bytes
    import os
    os.utime(src, (rec.mtime, rec.mtime))

    fast = f.verify_consistency("dna", "fast")
    assert fast.drifted == []  # fast can't see it

    full = f.verify_consistency("dna", "full")
    assert "d1" in full.drifted
    assert "d1" in full.repaired
    # Searchable under new content.
    hits = f.search("dna", "BRAVO")
    assert len(hits) == 1 and hits[0].doc_id == "d1"


def test_full_check_no_source_path_snapshot_hash(tmp_path):
    """When no source_path was recorded, full-check validates the doc
    snapshot against its recorded hash."""
    f = _facade(tmp_path)
    f.index_upsert("memory_medium", "m1", "content here")
    # All clean: snapshot hash matches recorded hash.
    report = f.verify_consistency("memory_medium", "full")
    assert report.failed == []
    assert report.drifted == []


def test_report_duration_set(tmp_path):
    f = _facade(tmp_path)
    f.index_upsert("dna", "d1", "x", {"source_path": str(tmp_path / "missing.md")})
    # source_path doesn't exist — counts as drift, repaired-via-delete.
    report = f.verify_consistency("dna", "fast")
    assert report.duration_ms >= 0.0
