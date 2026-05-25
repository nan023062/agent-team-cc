"""Tests for compaction.identifier — deterministic candidate staging.

Covers the contract:
  - identify() never calls LLM, never mutates store, only stages candidates
  - delete_short staged for distilled shorts that have a referencing medium
  - merge_short_into_medium staged for same-tag groups crossing threshold
  - candidates carry the exact shape compactor expects (kind +
    target_medium_path + target_medium_text + source_short_paths)
  - re-running identify is idempotent (deterministic candidate filenames)
  - compact() consumes them and produces medium/, deletes shorts
"""

from __future__ import annotations

from pathlib import Path

import pytest

from memory.compaction import compact
from memory.compaction.candidates import CandidatesArea
from memory.compaction.identifier import identify
from memory.crud.file_backend import FileBackend
from memory.crud.primitives import SHORT, write as crud_write


def _make_short(store: Path, name: str, body: str, tags: str = "session",
                distilled: str | None = None) -> Path:
    short_dir = store / "short"
    short_dir.mkdir(parents=True, exist_ok=True)
    p = short_dir / name
    fm_lines = ["tier: short", f"tags: {tags}"]
    if distilled:
        fm_lines.append(f"distilled: {distilled}")
    fm = "---\n" + "\n".join(fm_lines) + "\n---\n\n"
    p.write_text(fm + body + "\n", encoding="utf-8")
    return p


def _make_medium(store: Path, name: str, body: str, tags: str = "session") -> Path:
    medium_dir = store / "medium"
    medium_dir.mkdir(parents=True, exist_ok=True)
    p = medium_dir / name
    fm = f"---\ntier: medium\ntags: {tags}\n---\n\n"
    p.write_text(fm + body + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------

def test_identify_noop_on_medium_tier(tmp_path):
    store = tmp_path / "mem"
    p = _make_medium(store, "2026-05-20-x.md", "x")
    identify({"path": str(p), "tier": "medium", "metadata": {}})
    area = CandidatesArea(store)
    assert area.pull_pending() == []


def test_identify_noop_on_missing_path(tmp_path):
    store = tmp_path / "mem"
    (store / "short").mkdir(parents=True)
    identify({"path": str(store / "short" / "nope.md"), "tier": "short",
              "metadata": {}})
    assert CandidatesArea(store).pull_pending() == []


def test_identify_noop_on_generic_tag_only(tmp_path):
    store = tmp_path / "mem"
    # 3 shorts but ONLY 'session' — generic, no merge group.
    for i in range(3):
        _make_short(store, f"2026-05-2{i}-a.md", f"body{i}", tags="session")
    p = _make_short(store, "2026-05-24-a.md", "body4", tags="session")
    identify({"path": str(p), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    assert cands == []


# ---------------------------------------------------------------------------
# delete_short rule
# ---------------------------------------------------------------------------

def test_delete_short_when_distilled_and_medium_references_it(tmp_path):
    store = tmp_path / "mem"
    short = _make_short(store, "2026-05-20-x.md", "alpha",
                        tags="alpha", distilled="2026-05-22")
    # Medium body mentions the short's basename → counts as referencing.
    _make_medium(store, "2026-05-22-merged.md",
                 f"merged from 2026-05-20-x.md and friends", tags="alpha")

    identify({"path": str(short), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    delete_cands = [c for c in cands if c.get("kind") == "delete_short"]
    assert len(delete_cands) == 1
    assert str(short) in delete_cands[0]["source_short_paths"]


def test_no_delete_when_distilled_but_no_medium_reference(tmp_path):
    store = tmp_path / "mem"
    short = _make_short(store, "2026-05-20-x.md", "alpha",
                        tags="alpha", distilled="2026-05-22")
    # Medium exists but doesn't mention the short's basename.
    _make_medium(store, "2026-05-22-other.md", "unrelated body", tags="other")

    identify({"path": str(short), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    assert not any(c.get("kind") == "delete_short" for c in cands)


def test_no_delete_when_not_distilled(tmp_path):
    store = tmp_path / "mem"
    short = _make_short(store, "2026-05-20-x.md", "alpha", tags="alpha")
    _make_medium(store, "2026-05-22-merged.md", "2026-05-20-x.md", tags="alpha")
    identify({"path": str(short), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    assert not any(c.get("kind") == "delete_short" for c in cands)


# ---------------------------------------------------------------------------
# merge_short_into_medium rule
# ---------------------------------------------------------------------------

def test_merge_staged_when_three_shorts_share_tag(tmp_path):
    store = tmp_path / "mem"
    p1 = _make_short(store, "2026-05-20-a.md", "alpha body 1", tags="alpha")
    p2 = _make_short(store, "2026-05-21-b.md", "alpha body 2", tags="alpha")
    p3 = _make_short(store, "2026-05-22-c.md", "alpha body 3", tags="alpha")

    identify({"path": str(p3), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    merge_cands = [c for c in cands if c.get("kind") == "merge_short_into_medium"]
    assert len(merge_cands) == 1
    cand = merge_cands[0]
    assert set(cand["source_short_paths"]) == {str(p1), str(p2), str(p3)}
    assert cand["target_medium_path"].endswith(".md")
    assert "medium" in cand["target_medium_path"].replace("\\", "/")
    # Body must concatenate verbatim — no rewrites.
    assert "alpha body 1" in cand["target_medium_text"]
    assert "alpha body 2" in cand["target_medium_text"]
    assert "alpha body 3" in cand["target_medium_text"]


def test_no_merge_below_threshold(tmp_path):
    store = tmp_path / "mem"
    _make_short(store, "2026-05-20-a.md", "a1", tags="alpha")
    p2 = _make_short(store, "2026-05-21-b.md", "a2", tags="alpha")
    identify({"path": str(p2), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    assert not any(c.get("kind") == "merge_short_into_medium" for c in cands)


def test_no_merge_when_outside_date_window(tmp_path):
    store = tmp_path / "mem"
    _make_short(store, "2026-01-01-a.md", "a1", tags="alpha")
    _make_short(store, "2026-03-01-b.md", "a2", tags="alpha")
    p3 = _make_short(store, "2026-05-01-c.md", "a3", tags="alpha")
    identify({"path": str(p3), "tier": "short", "metadata": {}})
    cands = CandidatesArea(store).pull_pending()
    assert not any(c.get("kind") == "merge_short_into_medium" for c in cands)


def test_merge_idempotent_on_repeat(tmp_path):
    store = tmp_path / "mem"
    p1 = _make_short(store, "2026-05-20-a.md", "a1", tags="alpha")
    p2 = _make_short(store, "2026-05-21-b.md", "a2", tags="alpha")
    p3 = _make_short(store, "2026-05-22-c.md", "a3", tags="alpha")

    for _ in range(3):
        identify({"path": str(p3), "tier": "short", "metadata": {}})

    cands = [c for c in CandidatesArea(store).pull_pending()
             if c.get("kind") == "merge_short_into_medium"]
    assert len(cands) == 1


def test_merge_group_grows_overwrites_prior_candidate(tmp_path):
    store = tmp_path / "mem"
    p1 = _make_short(store, "2026-05-20-a.md", "a1", tags="alpha")
    p2 = _make_short(store, "2026-05-21-b.md", "a2", tags="alpha")
    p3 = _make_short(store, "2026-05-22-c.md", "a3", tags="alpha")
    identify({"path": str(p3), "tier": "short", "metadata": {}})

    p4 = _make_short(store, "2026-05-23-d.md", "a4", tags="alpha")
    identify({"path": str(p4), "tier": "short", "metadata": {}})

    cands = [c for c in CandidatesArea(store).pull_pending()
             if c.get("kind") == "merge_short_into_medium"]
    assert len(cands) == 1
    assert str(p4) in cands[0]["source_short_paths"]


# ---------------------------------------------------------------------------
# End-to-end: identify → compact actually mutates the store
# ---------------------------------------------------------------------------

def test_identify_then_compact_writes_medium_and_deletes_shorts(tmp_path):
    store = tmp_path / "mem"
    p1 = _make_short(store, "2026-05-20-a.md", "alpha body 1", tags="alpha")
    p2 = _make_short(store, "2026-05-21-b.md", "alpha body 2", tags="alpha")
    p3 = _make_short(store, "2026-05-22-c.md", "alpha body 3", tags="alpha")

    identify({"path": str(p3), "tier": "short", "metadata": {}})

    backend = FileBackend(store)
    report = compact(store, backend=backend)
    assert report.medium_entries_written == 1
    assert report.short_entries_deleted == 3
    assert report.errors == []

    # Source shorts gone, medium present with all bodies.
    assert not p1.exists()
    assert not p2.exists()
    assert not p3.exists()
    mediums = list((store / "medium").glob("*.md"))
    assert len(mediums) == 1
    txt = mediums[0].read_text(encoding="utf-8")
    assert "alpha body 1" in txt
    assert "alpha body 2" in txt
    assert "alpha body 3" in txt


def test_identify_via_crud_write_path(tmp_path):
    """crud.primitives.write triggers identify as step 2 — verify the
    wiring still works after the identifier got real logic.
    """
    store = tmp_path / "mem"
    backend = FileBackend(store)
    # Three writes sharing tag → third should stage a merge candidate.
    for i, name in enumerate(["2026-05-20-a.md", "2026-05-21-b.md",
                              "2026-05-22-c.md"]):
        p = _make_short(store, name, f"alpha body {i}", tags="alpha")
        crud_write(p, SHORT, backend)

    cands = [c for c in CandidatesArea(store).pull_pending()
             if c.get("kind") == "merge_short_into_medium"]
    assert len(cands) == 1
    assert len(cands[0]["source_short_paths"]) == 3
