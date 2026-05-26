"""memory v2 parent facade (memory.query / scan / get / stats) tests.

Covers the v2 contract:
- tier ∈ {medium, candidates} only; "short" raises ValueError
- stats() schema v2 (no short bucket; schema_version field present)
- get / scan walk medium/ + candidates/, never short/
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from memory import get, query, scan, stats
from memory._facade import STATS_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_entry(p: Path, body: str = "body", frontmatter: dict | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = ""
    if frontmatter:
        lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
        fm = f"---\n{lines}\n---\n\n"
    p.write_text(fm + body + "\n", encoding="utf-8")
    return p


def _write_candidate(store: Path, name: str, metadata: dict) -> Path:
    cand_dir = store / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    p = cand_dir / f"{name}.candidate.json"
    p.write_text(
        json.dumps({"id": name, "path": str(p), "metadata": metadata}),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def store(tmp_path) -> Path:
    """Populated v2 memory store: 2 medium entries, 1 candidate. No short/."""
    s = tmp_path / "memory_store"
    _write_entry(
        s / "medium" / "2026-05-20-a.md",
        body="alpha body",
        frontmatter={"tier": "medium", "tags": "alpha,test"},
    )
    _write_entry(
        s / "medium" / "2026-05-22-b.md",
        body="beta body distilled",
        frontmatter={"tier": "medium", "distilled": "2026-05-24", "tags": "beta"},
    )
    _write_candidate(s, "promo1", {"promote_candidate": "true", "tier": "medium"})
    return s


# ---------------------------------------------------------------------------
# v2 hard rule: short tier rejected
# ---------------------------------------------------------------------------

def test_query_rejects_tier_short(store):
    with pytest.raises(ValueError, match="short"):
        query("x", tier="short", store_dir=store)


def test_scan_rejects_tier_short(store):
    with pytest.raises(ValueError, match="short"):
        scan({"tier": "short"}, store_dir=store)


def test_stats_rejects_tier_short(store):
    with pytest.raises(ValueError, match="short"):
        stats({"tier": "short"}, store_dir=store)


# ---------------------------------------------------------------------------
# 1. query
# ---------------------------------------------------------------------------

def test_query_returns_only_medium_entries(store):
    res = query("anything", limit=10, store_dir=store)
    assert isinstance(res, list)
    # 2 medium entries; candidates aren't returned by query.
    assert len(res) == 2
    assert all(r["metadata"]["tier"] == "medium" for r in res)


def test_query_with_tier_medium(store):
    res = query("anything", tier="medium", limit=10, store_dir=store)
    assert len(res) == 2


# ---------------------------------------------------------------------------
# 2. scan
# ---------------------------------------------------------------------------

def test_scan_no_filter_returns_medium_only(store):
    res = scan(store_dir=store)
    tiers = {e["tier"] for e in res}
    assert tiers == {"medium"}
    assert len(res) == 2


def test_scan_by_tier_medium(store):
    res = scan({"tier": "medium"}, store_dir=store)
    assert len(res) == 2
    assert all(e["tier"] == "medium" for e in res)


def test_scan_by_tier_candidates(store):
    res = scan({"tier": "candidates"}, store_dir=store)
    assert len(res) == 1
    assert res[0]["tier"] == "candidates"


def test_scan_sorted_desc_by_mtime(store):
    res = scan({"tier": "medium"}, store_dir=store)
    mtimes = [e["mtime"] for e in res]
    assert mtimes == sorted(mtimes, reverse=True)


def test_scan_by_tag(store):
    res = scan({"tag": "alpha"}, store_dir=store)
    assert len(res) == 1
    assert res[0]["id"] == "2026-05-20-a.md"


def test_scan_promote_candidate(store):
    res = scan({"promote_candidate": True}, store_dir=store)
    assert len(res) == 1
    assert res[0]["tier"] == "candidates"


def test_scan_returns_snapshot_copy(store):
    res1 = scan({"tier": "medium"}, store_dir=store)
    res2 = scan({"tier": "medium"}, store_dir=store)
    assert res1 is not res2


def test_scan_empty_returns_empty_list(store):
    res = scan({"tag": "nonexistent"}, store_dir=store)
    assert res == []


# ---------------------------------------------------------------------------
# 3. get
# ---------------------------------------------------------------------------

def test_get_by_basename(store):
    e = get("2026-05-20-a.md", store_dir=store)
    assert e is not None
    assert "alpha body" in e["content"]
    assert e["tier"] == "medium"


def test_get_by_path(store):
    full = store / "medium" / "2026-05-22-b.md"
    e = get(full, store_dir=store)
    assert e is not None
    assert e["tier"] == "medium"


def test_get_missing_returns_none(store):
    assert get("nope.md", store_dir=store) is None


# ---------------------------------------------------------------------------
# 4. stats — v2 schema
# ---------------------------------------------------------------------------

def test_stats_schema_version_present(store):
    s = stats(store_dir=store)
    assert s["schema_version"] == STATS_SCHEMA_VERSION
    assert s["schema_version"] == 2


def test_stats_required_fields_present(store):
    s = stats(store_dir=store)
    for required in (
        "schema_version",
        "counts_by_tier",
        "counts_by_status",
        "last_distill_at",
        "candidate_count",
        "index_age_seconds",
        "disk_bytes",
    ):
        assert required in s, f"missing required field: {required}"


def test_stats_counts_by_tier_has_no_short(store):
    s = stats(store_dir=store)
    assert s["counts_by_tier"] == {"medium": 2, "candidates": 1}
    assert "short" not in s["counts_by_tier"]


def test_stats_disk_bytes_has_no_short(store):
    s = stats(store_dir=store)
    db = s["disk_bytes"]
    for k in ("medium", "candidates", "index"):
        assert k in db
        assert isinstance(db[k], int)
    assert "short" not in db
    assert db["medium"] > 0
    assert db["candidates"] > 0


def test_stats_counts_by_status(store):
    s = stats(store_dir=store)
    cs = s["counts_by_status"]
    assert cs["distilled"] == 1
    assert cs["undistilled"] == 1
    assert cs["promote_candidate"] == 1


def test_stats_candidate_count(store):
    s = stats(store_dir=store)
    assert s["candidate_count"] == 1


def test_stats_last_distill_at(store):
    s = stats(store_dir=store)
    assert s["last_distill_at"] == "2026-05-24"


def test_stats_oldest_and_newest_iso(store):
    s = stats(store_dir=store)
    assert s["oldest_entry_at"] is not None
    assert s["newest_entry_at"] is not None
    datetime.fromisoformat(s["oldest_entry_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(s["newest_entry_at"].replace("Z", "+00:00"))


def test_stats_backend_label(store):
    s = stats(store_dir=store)
    assert s["backend"] == "file"


def test_stats_empty_store_does_not_raise(tmp_path):
    empty = tmp_path / "empty_memory"
    s = stats(store_dir=empty)
    assert s["counts_by_tier"] == {"medium": 0, "candidates": 0}
    assert s["candidate_count"] == 0
    assert s["last_distill_at"] is None
    assert s["index_age_seconds"] is None
    assert s["schema_version"] == 2


def test_stats_with_tier_filter_medium(store):
    s = stats({"tier": "medium"}, store_dir=store)
    assert s["counts_by_tier"]["medium"] == 2
    assert s["counts_by_tier"]["candidates"] == 0


def test_stats_index_age_when_index_dir_exists(tmp_path):
    """When .index/ exists, index_age_seconds should be a non-negative int."""
    store = tmp_path / "mem"
    (store / ".index").mkdir(parents=True)
    (store / ".index" / "sentinel").write_text("x", encoding="utf-8")
    s = stats(store_dir=store)
    assert s["index_age_seconds"] is not None
    assert s["index_age_seconds"] >= 0
    assert s["disk_bytes"]["index"] > 0
