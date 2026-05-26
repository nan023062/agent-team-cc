"""
memory/_facade.py — 4 read-only interfaces: query / scan / get / stats.

This is the **only** outward-facing contract layer. Zero business logic
lives here — every method is forwarding. All writes go through the two
dedicated entry points (memory_write MCP / CLI) into crud/; this facade
refuses to expose anything that mutates state.

v2 contract changes (see .dna/contract.md):
- `tier` parameter value set narrowed to {medium, candidates}. Passing
  "short" raises ValueError (it was a valid value in v1).
- `stats()` schema bumped to v2 — no `short` bucket, `schema_version` field
  added.
- `scan` / `get` no longer walk a short/ directory.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend
from memory.crud.primitives import _read_frontmatter

# Schema version for stats() output. Bumped from 1 (implicit) to 2 when
# the short bucket was removed.
STATS_SCHEMA_VERSION = 2

# Allowed tier values across the read interfaces. "short" is intentionally
# absent in v2.
_ALLOWED_TIERS = ("medium", "candidates")

_BACKEND_NAME = "file"


def _resolve_store_dir(store_dir: Path | None = None) -> Path:
    if store_dir is not None:
        return Path(store_dir)
    try:
        from context import cbim_dir
        return cbim_dir() / "memory"
    except Exception:
        return Path.cwd() / ".cbim" / "memory"


def _build_backend(store_dir: Path) -> MemoryBackend:
    return FileBackend(store_dir)


def _validate_tier(tier: str | None) -> None:
    """Raise ValueError for any tier the v2 contract doesn't permit."""
    if tier is None:
        return
    if tier not in _ALLOWED_TIERS:
        raise ValueError(
            f"tier must be one of {_ALLOWED_TIERS} or None, got {tier!r}; "
            f"short tier was removed in v2"
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _within_since(ts: float, since_iso: str | None) -> bool:
    if not since_iso:
        return True
    try:
        cutoff = datetime.fromisoformat(since_iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return True
    return ts >= cutoff


def _list_tier_files(store_dir: Path, tier: str) -> list[Path]:
    d = store_dir / tier
    if not d.exists():
        return []
    return [p for p in d.glob("*.md") if p.is_file()]


def _list_candidates(store_dir: Path) -> list[Path]:
    from memory.compaction.candidates import CANDIDATES_SUBDIR
    d = store_dir / CANDIDATES_SUBDIR
    if not d.exists():
        return []
    return [p for p in d.glob("*.candidate.json") if p.is_file()]


def _file_meta(path: Path, tier: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    fm = _read_frontmatter(text)
    fm.setdefault("tier", tier)
    fm.setdefault("filename", path.name)
    return fm


def _entry_dict(path: Path, tier: str) -> dict:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return {
        "id": path.name,
        "path": str(path),
        "tier": tier,
        "mtime": _iso(mtime),
        "metadata": _file_meta(path, tier),
    }


def _matches_filter(entry: dict, filt: dict) -> bool:
    if not filt:
        return True
    if "tier" in filt and entry.get("tier") != filt["tier"]:
        return False
    if "tag" in filt:
        meta = entry.get("metadata", {}) or {}
        tags_raw = meta.get("tag") or meta.get("tags") or ""
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
        if filt["tag"] not in tags:
            return False
    if "path_prefix" in filt:
        if not str(entry.get("path", "")).startswith(filt["path_prefix"]):
            return False
    if "since" in filt:
        try:
            ts = datetime.fromisoformat(
                (entry.get("mtime") or "").replace("Z", "+00:00")
            ).timestamp()
        except (ValueError, TypeError):
            ts = 0.0
        if not _within_since(ts, filt["since"]):
            return False
    if "promote_candidate" in filt:
        meta = entry.get("metadata", {}) or {}
        flag = meta.get("promote_candidate") or meta.get("status")
        if str(flag).lower() not in ("true", "1", "yes", "promote_candidate"):
            return False
    return True


# ------------------------------------------------------------------
# 1. query — semantic / keyword retrieval
# ------------------------------------------------------------------

def query(text: str,
          *,
          tier: str | None = None,
          limit: int = 5,
          store_dir: Path | None = None,
          backend: MemoryBackend | None = None,
          **_extra_filter) -> list[dict]:
    """Semantic/keyword retrieval. Returns ranked entries (most relevant first).

    Defers to the backend (default FileBackend = recency order). Pass
    `tier="medium"` to restrict scope; `tier="short"` raises ValueError.
    """
    _validate_tier(tier)
    store_dir = _resolve_store_dir(store_dir)
    backend = backend or _build_backend(store_dir)
    where = {"tier": tier} if tier else None
    return backend.query(text, n_results=limit, where=where)


# ------------------------------------------------------------------
# 2. scan — structured enumeration
# ------------------------------------------------------------------

def scan(filter: dict | None = None,
         *,
         store_dir: Path | None = None) -> list[dict]:
    """Enumerate entries matching `filter`. Sorted by mtime DESC.

    Supported filter keys:
        tier            : "medium" | "candidates" (short removed in v2)
        tag             : exact tag match
        path_prefix     : str prefix
        since           : ISO-8601 cutoff (entry.mtime >= since)
        promote_candidate : truthy → only promote candidates

    Returns a list copy (immutable snapshot); empty list if nothing matches.
    """
    store_dir = _resolve_store_dir(store_dir)
    filt = dict(filter or {})
    _validate_tier(filt.get("tier"))

    # Decide which tier dirs to walk based on the filter.
    if filt.get("tier") == "candidates" or "promote_candidate" in filt:
        tiers_to_walk = ["candidates"]
    elif filt.get("tier"):
        tiers_to_walk = [filt["tier"]]
    else:
        tiers_to_walk = ["medium"]

    entries: list[dict] = []
    for t in tiers_to_walk:
        if t == "candidates":
            for p in _list_candidates(store_dir):
                try:
                    import json as _json
                    raw = _json.loads(p.read_text(encoding="utf-8"))
                    meta = raw.get("metadata", {}) or {}
                    try:
                        mtime = p.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    entries.append({
                        "id": p.stem,
                        "path": str(p),
                        "tier": "candidates",
                        "mtime": _iso(mtime),
                        "metadata": meta,
                    })
                except (OSError, ValueError):
                    continue
        else:
            for p in _list_tier_files(store_dir, t):
                entries.append(_entry_dict(p, t))

    out = [e for e in entries if _matches_filter(e, filt)]
    out.sort(key=lambda e: e.get("mtime") or "", reverse=True)
    return list(out)


# ------------------------------------------------------------------
# 3. get — pinpoint fetch
# ------------------------------------------------------------------

def get(entry_id: str | Path,
        *,
        store_dir: Path | None = None) -> dict | None:
    """Return full entry by id or absolute path. None if missing.

    `entry_id` may be:
      - a full path (str or Path)
      - a basename (resolved against medium/, then candidates/)
    """
    store_dir = _resolve_store_dir(store_dir)
    p = Path(entry_id)
    if p.is_file():
        tier = p.parent.name
        content = ""
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            pass
        entry = _entry_dict(p, tier)
        entry["content"] = content
        return entry

    # Treat as basename; search the v2 tier set.
    name = str(entry_id)
    cand = store_dir / "medium" / name
    if cand.is_file():
        try:
            content = cand.read_text(encoding="utf-8")
        except OSError:
            content = ""
        entry = _entry_dict(cand, "medium")
        entry["content"] = content
        return entry

    # candidates dir uses *.candidate.json — try both bare name and suffixed.
    from memory.compaction.candidates import CANDIDATES_SUBDIR
    cand_dir = store_dir / CANDIDATES_SUBDIR
    for fname in (name, f"{name}.candidate.json"):
        cand = cand_dir / fname
        if cand.is_file():
            try:
                content = cand.read_text(encoding="utf-8")
            except OSError:
                content = ""
            try:
                mtime = cand.stat().st_mtime
            except OSError:
                mtime = 0.0
            return {
                "id": cand.stem,
                "path": str(cand),
                "tier": "candidates",
                "mtime": _iso(mtime),
                "metadata": {},
                "content": content,
            }

    return None


# ------------------------------------------------------------------
# 4. stats — observation / health / capacity
# ------------------------------------------------------------------

def stats(filter: dict | None = None,
          *,
          store_dir: Path | None = None) -> dict:
    """Memory observation snapshot.

    v2 schema (schema_version=2):
      - counts_by_tier  : {medium, candidates}  (no short bucket)
      - counts_by_status: {distilled, undistilled, promote_candidate}
      - disk_bytes      : {medium, candidates, index}
      - last_distill_at, candidate_count, index_age_seconds,
        oldest_entry_at, newest_entry_at, backend

    Filter order: tier → tag → path_prefix → since. Never raises on
    per-field failures (falls back to 0/None).
    """
    store_dir = _resolve_store_dir(store_dir)
    filt = dict(filter or {})
    _validate_tier(filt.get("tier"))

    counts_by_tier = {"medium": 0, "candidates": 0}
    counts_by_status = {
        "distilled": 0,
        "undistilled": 0,
        "promote_candidate": 0,
    }
    disk_bytes = {"medium": 0, "candidates": 0, "index": 0}
    oldest_ts: float | None = None
    newest_ts: float | None = None
    last_distill_at: str | None = None

    # Walk medium tier (the only file tier left in v2).
    if not filt.get("tier") or filt["tier"] == "medium":
        for p in _list_tier_files(store_dir, "medium"):
            entry = _entry_dict(p, "medium")
            if not _matches_filter(entry, filt):
                continue
            counts_by_tier["medium"] += 1
            try:
                disk_bytes["medium"] += p.stat().st_size
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if oldest_ts is None or mtime < oldest_ts:
                oldest_ts = mtime
            if newest_ts is None or mtime > newest_ts:
                newest_ts = mtime
            try:
                raw = p.read_text(encoding="utf-8")
            except OSError:
                raw = ""
            distilled_match = re.search(r"^distilled:\s*(\S+)", raw, re.MULTILINE)
            if distilled_match:
                counts_by_status["distilled"] += 1
                dval = distilled_match.group(1)
                if last_distill_at is None or dval > last_distill_at:
                    last_distill_at = dval
            else:
                counts_by_status["undistilled"] += 1

    # Walk candidates
    if not filt.get("tier") or filt["tier"] == "candidates":
        for p in _list_candidates(store_dir):
            counts_by_tier["candidates"] += 1
            try:
                disk_bytes["candidates"] += p.stat().st_size
                mtime = p.stat().st_mtime
            except OSError:
                continue
            counts_by_status["promote_candidate"] += 1
            if oldest_ts is None or mtime < oldest_ts:
                oldest_ts = mtime
            if newest_ts is None or mtime > newest_ts:
                newest_ts = mtime

    # Disk bytes for the local backend index (FileBackend → .index/,
    # ChromaBackend → .chroma/). The external retrieval index lives under
    # .cbim/index/ — not the memory store — and is observed via
    # engine.retrieval.stats(), not here.
    for sub in (".index", ".chroma"):
        d = store_dir / sub
        if d.exists():
            try:
                for f in d.rglob("*"):
                    if f.is_file():
                        try:
                            disk_bytes["index"] += f.stat().st_size
                        except OSError:
                            continue
            except OSError:
                continue

    # Index age — newest mtime under .index/ or .chroma/
    index_newest: float | None = None
    for sub in (".index", ".chroma"):
        d = store_dir / sub
        if d.exists():
            try:
                for f in d.rglob("*"):
                    if f.is_file():
                        try:
                            m = f.stat().st_mtime
                        except OSError:
                            continue
                        if index_newest is None or m > index_newest:
                            index_newest = m
            except OSError:
                continue
    index_age_seconds: int | None
    if index_newest is None:
        index_age_seconds = None
    else:
        index_age_seconds = max(0, int(time.time() - index_newest))

    return {
        "schema_version": STATS_SCHEMA_VERSION,
        "counts_by_tier": counts_by_tier,
        "counts_by_status": counts_by_status,
        "last_distill_at": last_distill_at,
        "candidate_count": counts_by_tier["candidates"],
        "index_age_seconds": index_age_seconds,
        "disk_bytes": disk_bytes,
        "oldest_entry_at": _iso(oldest_ts),
        "newest_entry_at": _iso(newest_ts),
        "backend": _BACKEND_NAME,
    }
