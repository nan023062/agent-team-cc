"""Unit tests for engine.audit.checks.memory_threshold (memory v2).

Two breach codes mirror memory.compaction.health.HealthReport:
    MEMORY_VOLUME              medium_bytes/1024 >= medium_max_total_kb
    MEMORY_CANDIDATE_BACKLOG   candidate_count >= candidate_max

Severity bands:
    ratio < 2.0 -> warn
    ratio >= 2.0 -> error

These tests exercise the audit wrapper end-to-end against a real
HealthChecker; they do not stub it. Thresholds are pushed down through
the memory `_config.load_config` patch so the check still respects the
"audit doesn't own thresholds" architectural rule.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.audit.checks.memory_threshold import check


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _seed_store(root: Path) -> tuple[Path, Path]:
    medium = root / ".cbim" / "memory" / "medium"
    medium.mkdir(parents=True)
    cand = root / ".cbim" / "memory" / "candidates"
    cand.mkdir(parents=True)
    return medium, cand


def _write_medium(medium: Path, name: str, size_bytes: int) -> Path:
    p = medium / name
    p.write_text("x" * size_bytes, encoding="utf-8")
    return p


def _write_candidate(cand: Path, name: str) -> Path:
    p = cand / f"{name}.candidate.json"
    p.write_text(json.dumps({"metadata": {"kind": "test"}}), encoding="utf-8")
    return p


@pytest.fixture()
def patch_thresholds(monkeypatch):
    """Override compaction._load_thresholds so tests don't need the
    project's `memory_config.json`. We monkey-patch the lookup function
    directly inside the health module — that's where the check pulls
    them from."""

    def _apply(*, medium_max_total_kb: int = 16384, candidate_max: int = 200) -> None:
        from memory.compaction import health as _h

        def _fake_load():
            return {
                "candidate_max": candidate_max,
                "medium_max_total_kb": medium_max_total_kb,
                "index_drift_seconds": None,
            }

        monkeypatch.setattr(_h, "_load_thresholds", _fake_load)

    return _apply


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_store_no_findings(tmp_path, patch_thresholds):
    _seed_store(tmp_path)
    patch_thresholds()
    assert check(tmp_path, {}) == []


def test_no_memory_dir_returns_empty(tmp_path):
    """Project without .cbim/memory/ shouldn't blow up — just no findings."""
    assert check(tmp_path, {}) == []


def test_medium_volume_warn_band(tmp_path, patch_thresholds):
    medium, _ = _seed_store(tmp_path)
    # Threshold 4 KiB; write 5 KiB -> ratio 1.25 -> warn
    patch_thresholds(medium_max_total_kb=4)
    _write_medium(medium, "big.md", 5 * 1024)

    findings = check(tmp_path, {})
    volume = [f for f in findings if f.code == "MEMORY_VOLUME"]
    assert len(volume) == 1
    assert volume[0].severity == "warn"
    assert volume[0].target == "medium"
    assert "medium_bytes" in volume[0].metadata


def test_medium_volume_error_band(tmp_path, patch_thresholds):
    medium, _ = _seed_store(tmp_path)
    # Threshold 4 KiB; write 12 KiB -> ratio 3.0 -> error
    patch_thresholds(medium_max_total_kb=4)
    _write_medium(medium, "big.md", 12 * 1024)

    findings = check(tmp_path, {})
    volume = next(f for f in findings if f.code == "MEMORY_VOLUME")
    assert volume.severity == "error"
    assert volume.metadata["ratio"] >= 2.0


def test_candidate_backlog_warn(tmp_path, patch_thresholds):
    _, cand = _seed_store(tmp_path)
    patch_thresholds(candidate_max=10)
    for i in range(11):
        _write_candidate(cand, f"c{i}")

    findings = check(tmp_path, {})
    bl = [f for f in findings if f.code == "MEMORY_CANDIDATE_BACKLOG"]
    assert len(bl) == 1
    assert bl[0].severity == "warn"
    assert bl[0].target == "candidates"
    assert bl[0].metadata["candidate_count"] == 11


def test_candidate_backlog_error_band(tmp_path, patch_thresholds):
    _, cand = _seed_store(tmp_path)
    patch_thresholds(candidate_max=5)
    for i in range(15):
        _write_candidate(cand, f"c{i}")

    findings = check(tmp_path, {})
    bl = next(f for f in findings if f.code == "MEMORY_CANDIDATE_BACKLOG")
    assert bl.severity == "error"


def test_both_breaches_surface_independently(tmp_path, patch_thresholds):
    medium, cand = _seed_store(tmp_path)
    patch_thresholds(medium_max_total_kb=2, candidate_max=3)
    _write_medium(medium, "big.md", 4 * 1024)
    for i in range(5):
        _write_candidate(cand, f"c{i}")

    findings = check(tmp_path, {})
    codes = {f.code for f in findings}
    assert "MEMORY_VOLUME" in codes
    assert "MEMORY_CANDIDATE_BACKLOG" in codes


def test_no_short_tier_codes_emitted(tmp_path, patch_thresholds):
    """v1 codes (MEMORY_SHORT_OVERFLOW / MEMORY_STALE) must never appear."""
    medium, cand = _seed_store(tmp_path)
    patch_thresholds(medium_max_total_kb=1, candidate_max=1)
    _write_medium(medium, "big.md", 8 * 1024)
    _write_candidate(cand, "c0")
    _write_candidate(cand, "c1")

    findings = check(tmp_path, {})
    codes = {f.code for f in findings}
    assert "MEMORY_SHORT_OVERFLOW" not in codes
    assert "MEMORY_STALE" not in codes
    assert "MEMORY_PROMOTE_TO_AGENT_SKILL" not in codes


def test_audit_does_not_read_memory_files_directly():
    """Architectural rule: audit must reach memory only via the
    HealthChecker interface, never by globbing memory files itself."""
    src = (
        Path(__file__).resolve().parents[1]
        / "kernel/engine/audit/checks/memory_threshold.py"
    )
    text = src.read_text(encoding="utf-8")
    forbidden = [
        ".cbim/memory/short",
        ".cbim/memory/medium",
        "memory/short",
        "memory/medium",
        "memory/candidates",
        "glob(",
        "rglob(",
        "iterdir(",
    ]
    hits = [tok for tok in forbidden if tok in text]
    assert not hits, f"forbidden raw-memory access tokens: {hits}"
