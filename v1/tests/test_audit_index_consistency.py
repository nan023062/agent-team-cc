"""Unit tests for engine.audit.checks.index_consistency."""
from __future__ import annotations

from pathlib import Path

from engine.audit.checks.index_consistency import check


def _seed(root: Path) -> None:
    (root / ".cbim").mkdir(parents=True)


def _make_module(root: Path, rel: str) -> None:
    mod = root / rel
    (mod / ".dna").mkdir(parents=True)
    (mod / ".dna" / "module.md").write_text(
        "---\nname: m\nowner: x\ndescription: m\n---\n\nbody\n",
        encoding="utf-8",
    )


def _write_index(root: Path, entries: list[str]) -> None:
    lines = ["# Module Index", ""]
    for e in entries:
        lines.append(f"- {e}")
    (root / ".cbim" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_missing_root_is_error(tmp_path):
    _seed(tmp_path)
    findings = check(tmp_path, {})
    assert any(f.code == "INDEX_MISSING_ROOT" for f in findings)
    assert findings[0].severity == "error"


def test_empty_index_no_modules_clean(tmp_path):
    _seed(tmp_path)
    _write_index(tmp_path, [])
    findings = check(tmp_path, {})
    assert findings == []


def test_missing_entry_warn(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha")
    _write_index(tmp_path, [])
    findings = check(tmp_path, {})
    codes = {f.code for f in findings}
    assert "INDEX_MISSING_ENTRY" in codes
    missing = next(f for f in findings if f.code == "INDEX_MISSING_ENTRY")
    assert missing.severity == "warn"
    assert missing.target == "alpha"


def test_stale_entry_warn(tmp_path):
    _seed(tmp_path)
    _write_index(tmp_path, ["ghost"])
    findings = check(tmp_path, {})
    codes = {f.code for f in findings}
    assert "INDEX_STALE_ENTRY" in codes


def test_unnormalised_and_duplicate_path(tmp_path):
    _seed(tmp_path)
    _make_module(tmp_path, "alpha")
    _write_index(tmp_path, ["alpha/", "alpha"])
    findings = check(tmp_path, {})
    codes = {f.code for f in findings}
    assert "INDEX_PATH_FORMAT" in codes
    assert "INDEX_DUPLICATE" in codes
