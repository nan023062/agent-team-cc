"""Unit tests for engine.audit.checks.memory_threshold."""
from __future__ import annotations

import os
import time
from pathlib import Path

from engine.audit.checks.memory_threshold import check


def _seed_mem(root: Path) -> tuple[Path, Path]:
    short = root / ".cbim" / "memory" / "short"
    medium = root / ".cbim" / "memory" / "medium"
    short.mkdir(parents=True)
    medium.mkdir(parents=True)
    return short, medium


def _write_entry(d: Path, name: str, body: str = "x") -> Path:
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_empty_store_no_findings(tmp_path):
    _seed_mem(tmp_path)
    assert check(tmp_path, {"memory": {
        "short_max_entries": 80, "short_max_age_days": 7,
        "short_max_total_kb": 512, "medium_max_entries": 40,
    }}) == []


def test_short_overflow_warn(tmp_path):
    short, _ = _seed_mem(tmp_path)
    for i in range(11):
        _write_entry(short, f"2026-05-22-e{i}.md")
    findings = check(tmp_path, {"memory": {
        "short_max_entries": 10, "short_max_age_days": 7,
        "short_max_total_kb": 9999, "medium_max_entries": 40,
    }})
    overflow = [f for f in findings if f.code == "MEMORY_SHORT_OVERFLOW"]
    assert len(overflow) == 1
    assert overflow[0].severity == "warn"


def test_short_overflow_error_band(tmp_path):
    short, _ = _seed_mem(tmp_path)
    for i in range(16):
        _write_entry(short, f"2026-05-22-e{i}.md")
    findings = check(tmp_path, {"memory": {
        "short_max_entries": 10, "short_max_age_days": 7,
        "short_max_total_kb": 9999, "medium_max_entries": 40,
    }})
    overflow = next(f for f in findings if f.code == "MEMORY_SHORT_OVERFLOW")
    assert overflow.severity == "error"


def test_short_info_band(tmp_path):
    short, _ = _seed_mem(tmp_path)
    for i in range(8):
        _write_entry(short, f"2026-05-22-e{i}.md")
    findings = check(tmp_path, {"memory": {
        "short_max_entries": 10, "short_max_age_days": 30,
        "short_max_total_kb": 9999, "medium_max_entries": 40,
    }})
    overflow = next(f for f in findings if f.code == "MEMORY_SHORT_OVERFLOW")
    assert overflow.severity == "info"


def test_stale_entry_emits_warn(tmp_path):
    short, _ = _seed_mem(tmp_path)
    old = _write_entry(short, "2026-05-01-old.md")
    past = time.time() - 30 * 86400
    os.utime(old, (past, past))
    findings = check(tmp_path, {"memory": {
        "short_max_entries": 80, "short_max_age_days": 7,
        "short_max_total_kb": 9999, "medium_max_entries": 40,
    }})
    stale = [f for f in findings if f.code == "MEMORY_STALE"]
    assert len(stale) == 1
    assert stale[0].severity == "warn"
    assert stale[0].target == "short"
    assert "oldest_age_days" in stale[0].metadata


def test_promotion_findings_removed(tmp_path):
    """Phase 4B: promotion findings are no longer emitted (architecture rule)."""
    _, medium = _seed_mem(tmp_path)
    for i in range(50):
        _write_entry(medium, f"2026-05-22-m{i}.md")
    findings = check(tmp_path, {"memory": {
        "short_max_entries": 80, "short_max_age_days": 7,
        "short_max_total_kb": 9999, "medium_max_entries": 10,
    }})
    codes = {f.code for f in findings}
    assert "MEMORY_PROMOTE_TO_AGENT_SKILL" not in codes
    assert "MEMORY_PROMOTE_TO_DNA_KNOWLEDGE" not in codes


def test_audit_does_not_read_memory_files_directly():
    """Phase 4B: source-level grep — audit must reach memory only via stats()."""
    src = (
        Path(__file__).resolve().parents[1]
        / "kernel/engine/audit/checks/memory_threshold.py"
    )
    text = src.read_text(encoding="utf-8")
    forbidden = [
        ".cbim/memory",
        "memory/short",
        "memory/medium",
        "memory/candidates",
        "glob(",
        "rglob(",
        "iterdir(",
    ]
    hits = [tok for tok in forbidden if tok in text]
    assert not hits, f"forbidden raw-memory access tokens: {hits}"
