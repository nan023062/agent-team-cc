"""
memory/_facade.py — 4 read-only interfaces: query / scan / get / stats.

Phase 4A: This is the **only** outward-facing contract layer. Zero business
logic lives here — every method is forwarding. All writes go through the
3 dedicated entry points (Hook / memory_write MCP / CLI) into crud/; this
facade refuses to expose anything that mutates state.

See .dna/contract.md for the public API definition and stability rules.
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

# Backend selection
# ------------------------------------------------------------------
# The facade builds a default backend lazily, anchored at <project>/.cbim/memory.
# Caller may pass an explicit backend or store_dir for tests; in normal
# operation this delegates to the same default wiring the legacy engine used.

_BACKEND_NAME = "file"  # 4A: only FileBackend wired. ChromaBackend opt-in via env in 4B.


def _resolve_store_dir(store_dir: Path | None = None) -> Path:
    if store_dir is not None:
        return Path(store_dir)
    try:
        # `context.cbim_dir()` walks up to the project root (.cbim/).
        from context import cbim_dir
        return cbim_dir() / "memory"
    except Exception:
        # Last-ditch fallback for unit tests that don't set up a project.
        return Path.cwd() / ".cbim" / "memory"


def _build_backend(store_dir: Path) -> MemoryBackend:
    # 4A: hard-wired to FileBackend; 4B introduces backend pick via config.
    return FileBackend(store_dir)


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
        return True  # invalid since — don't filter out
    return ts >= cutoff


def _list_tier_files(store_dir: Path, tier: str) -> list[Path]:
    d = store_dir / tier
    if not d.exists():
        return []
    return [p for p in d.glob("*.md") if p.is_file()]


def _list_candidates(store_dir: Path) -> list[Path]:
    # candidates/ uses CandidatesArea; we don't import CandidatesArea here
    # to keep the facade decoupled from compaction internals — just stat
    # the directory like every other tier.
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
    """Apply scan/stats filter: tier → tag/path_prefix/since (in that order).

    The facade contract requires the filter order be tier first, then
    tag / path_prefix / since. Returning True means "keep".
    """
    if not filt:
        return True
    if "tier" in filt and entry.get("tier") != filt["tier"]:
        return False
    if "tag" in filt:
        meta = entry.get("metadata", {}) or {}
        # Tag may live under 'tag' or 'tags' (string or comma list)
        tags_raw = meta.get("tag") or meta.get("tags") or ""
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
        if filt["tag"] not in tags:
            return False
    if "path_prefix" in filt:
        if not str(entry.get("path", "")).startswith(filt["path_prefix"]):
            return False
    if "since" in filt:
        # entry.mtime is ISO; parse back to compare
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

    The 4A FileBackend returns by mtime (text ignored); ChromaBackend (4B)
    will honour `text` for true vector search. Callers MUST treat ordering
    as backend-defined.
    """
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

    Supported filter keys (per ContextPack §4):
        tier            : "short" | "medium" | "candidates"
        tag             : exact tag match
        path_prefix     : str prefix
        since           : ISO-8601 cutoff (entry.mtime >= since)
        promote_candidate : truthy → only promote candidates

    Returns a list copy (immutable snapshot for the caller); empty list
    if nothing matches.
    """
    store_dir = _resolve_store_dir(store_dir)
    filt = dict(filter or {})

    # Decide which tier dirs to walk based on the filter
    if filt.get("tier") == "candidates" or "promote_candidate" in filt:
        tiers_to_walk = ["candidates"]
    elif filt.get("tier"):
        tiers_to_walk = [filt["tier"]]
    else:
        tiers_to_walk = ["short", "medium"]

    entries: list[dict] = []
    for t in tiers_to_walk:
        if t == "candidates":
            for p in _list_candidates(store_dir):
                # Candidates are JSON; load minimally so filter sees real metadata.
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
    # Sort by mtime DESC; None mtimes go last.
    out.sort(key=lambda e: e.get("mtime") or "", reverse=True)
    return list(out)  # explicit copy (snapshot)


# ------------------------------------------------------------------
# 3. get — pinpoint fetch
# ------------------------------------------------------------------

def get(entry_id: str | Path,
        *,
        store_dir: Path | None = None) -> dict | None:
    """Return full entry by id or absolute path. None if missing.

    `entry_id` may be:
      - a full path (str or Path)
      - a basename (resolved against short/, medium/, candidates/)
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

    # Treat as basename; search standard tiers.
    name = str(entry_id)
    for t in ("short", "medium"):
        cand = store_dir / t / name
        if cand.is_file():
            try:
                content = cand.read_text(encoding="utf-8")
            except OSError:
                content = ""
            entry = _entry_dict(cand, t)
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
    """Memory observation snapshot. See ContextPack §3 for field schema.

    Filter order (per contract): tier → tag → path_prefix → since.
    Never raises — per-field failures fall back to 0/None.
    """
    store_dir = _resolve_store_dir(store_dir)
    filt = dict(filter or {})

    counts_by_tier = {"short": 0, "medium": 0, "candidates": 0}
    counts_by_status = {
        "distilled": 0,
        "undistilled": 0,
        "promote_candidate": 0,
    }
    disk_bytes = {"short": 0, "medium": 0, "candidates": 0, "index": 0}
    oldest_ts: float | None = None
    newest_ts: float | None = None
    last_distill_at: str | None = None

    # Walk regular tiers
    for t in ("short", "medium"):
        # Tier filter (if specified) narrows scope.
        if filt.get("tier") and filt["tier"] != t:
            continue
        for p in _list_tier_files(store_dir, t):
            entry = _entry_dict(p, t)
            if not _matches_filter(entry, filt):
                continue
            counts_by_tier[t] += 1
            # Disk bytes (subject to filter).
            try:
                disk_bytes[t] += p.stat().st_size
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if oldest_ts is None or mtime < oldest_ts:
                oldest_ts = mtime
            if newest_ts is None or mtime > newest_ts:
                newest_ts = mtime
            # Distilled marker — read body for "distilled: YYYY-MM-DD"
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

    # Disk bytes for index. Per ContextPack §8 #1: branch by backend.
    # FileBackend → .cbim/memory/.index/ ; ChromaBackend → .cbim/memory/.chroma/
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
