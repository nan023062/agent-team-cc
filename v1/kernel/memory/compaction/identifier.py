"""
compaction/identifier.py — `identify(entry)` — sync side-effect of crud.write.

The contract (crud/.dna/module.md Key Decision #1):
- `identify` is called by crud.primitives.write step 2 (after persist+index).
- It must NOT notify any external caller, emit events, or call back into crud.
- Its sole side-effect is staging matching entries into the candidates/ work area.

Iron rule (dream/.dna/module.md): identify is deterministic Python — NO LLM
call. Grouping is structural (tags / dates / explicit frontmatter markers),
not semantic. Semantic short→medium merging is the `memory_distill` skill's
job, which runs separately and is LLM-driven.

What this module produces:
- `delete_short`: a short entry already distilled into a medium entry that
  still exists on disk — safe to drop the short copy.
- `merge_short_into_medium`: a group of short entries sharing a non-generic
  tag, with the merged body pre-composed verbatim (no rewriting / summarising).

Idempotency: the candidate path is deterministic per group key, so re-running
identify after another entry joins the group overwrites the prior candidate
rather than piling new ones up.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from .candidates import CandidatesArea

# Tags that on their own don't carry topical signal — every session-written
# short entry has `tags: session`, so grouping on it would lump the whole
# tier together. Excluded from merge key selection.
_GENERIC_TAGS = {"session", "manual", ""}

# A merge candidate is staged only when at least this many short entries share
# the grouping key. Below the threshold the group stays as separate shorts.
_MERGE_MIN_GROUP = 3

# Only group entries whose filename-encoded dates fall within this many days
# of each other. Stops a single tag from accumulating shorts across months.
_MERGE_WINDOW_DAYS = 14

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_DISTILLED_RE = re.compile(r"^distilled:\s*(\S+)", re.MULTILINE)


def identify(entry: dict) -> None:
    """Sync side-effect of crud.primitives.write.

    `entry` shape (built by crud.primitives.write):
        {"path": <str>, "tier": "short"|"medium", "metadata": {...}}

    Only short-tier writes drive identification; medium writes don't
    re-trigger the scan (compactor's own update of medium would otherwise
    cause a recursion loop).
    """
    if not isinstance(entry, dict):
        return
    if entry.get("tier") != "short":
        return

    path_str = entry.get("path")
    if not path_str:
        return
    entry_path = Path(path_str)
    if not entry_path.exists():
        return

    store_dir = _resolve_store_dir(entry_path)
    if store_dir is None:
        return

    area = CandidatesArea(store_dir)

    # Rule 1 — delete_short: this entry is already distilled and the
    # corresponding medium entry still exists on disk.
    if _is_distilled(entry_path) and _has_referencing_medium(store_dir, entry_path):
        _stage_delete_short(area, entry_path)

    # Rule 2 — merge_short_into_medium: scan short/ for a same-tag group
    # this entry belongs to. If the group hits the threshold, stage a
    # deterministic merge candidate (overwrites any prior candidate for
    # the same group).
    for tag in _topical_tags(entry_path):
        group = _collect_group(store_dir, tag)
        if len(group) < _MERGE_MIN_GROUP:
            continue
        if not _within_window(group, _MERGE_WINDOW_DAYS):
            continue
        _stage_merge(area, store_dir, tag, group)


# ---------------------------------------------------------------------------
# Helpers — filesystem & frontmatter
# ---------------------------------------------------------------------------

def _resolve_store_dir(entry_path: Path) -> Path | None:
    """The store root is the parent of the entry's tier directory.

    Returns None when the file isn't under a recognised `<store>/short/`
    layout — keeps identify a no-op for anything weird.
    """
    parent = entry_path.parent
    if parent.name != "short":
        return None
    return parent.parent


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _read_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _body_after_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text.strip()
    end = text.find("\n---", 3)
    if end == -1:
        return text.strip()
    return text[end + 4:].strip()


def _is_distilled(path: Path) -> bool:
    text = _read_text(path)
    if not text:
        return False
    # `distilled:` may sit in the frontmatter or in a body field — both
    # count. session_writer leaves it absent until a distill skill stamps it.
    if _DISTILLED_RE.search(text):
        return True
    fm = _read_frontmatter(text)
    return bool(fm.get("distilled"))


def _has_referencing_medium(store_dir: Path, short_path: Path) -> bool:
    """True iff some medium/*.md mentions this short entry's basename.

    We don't parse medium content — a plain substring is enough because the
    distill skill writes the source filename into the merged medium body
    (see compactor._apply_merge's text composition contract).
    """
    medium_dir = store_dir / "medium"
    if not medium_dir.exists():
        return False
    needle = short_path.name
    for m in medium_dir.glob("*.md"):
        if needle in _read_text(m):
            return True
    return False


def _topical_tags(path: Path) -> list[str]:
    """Frontmatter tags minus generic ones, in declaration order.

    Returns [] when the entry only carries generic tags — those don't form
    merge groups.
    """
    fm = _read_frontmatter(_read_text(path))
    raw = fm.get("tags") or fm.get("tag") or ""
    tags = [t.strip() for t in str(raw).split(",") if t.strip()]
    return [t for t in tags if t.lower() not in _GENERIC_TAGS]


def _entry_date(path: Path) -> str | None:
    m = _DATE_RE.match(path.name)
    return m.group(1) if m else None


def _collect_group(store_dir: Path, tag: str) -> list[Path]:
    """All short/*.md files that carry `tag` (case-insensitive)."""
    short_dir = store_dir / "short"
    if not short_dir.exists():
        return []
    needle = tag.lower()
    hits: list[Path] = []
    for p in sorted(short_dir.glob("*.md")):
        if not p.is_file():
            continue
        if needle in [t.lower() for t in _topical_tags(p)]:
            hits.append(p)
    return hits


def _within_window(paths: list[Path], window_days: int) -> bool:
    dates = [d for d in (_entry_date(p) for p in paths) if d]
    if len(dates) < 2:
        # Single date (or no parseable date) — trivially "in window".
        return True
    try:
        ds = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
    except ValueError:
        return True
    return (max(ds) - min(ds)).days <= window_days


# ---------------------------------------------------------------------------
# Helpers — candidate composition
# ---------------------------------------------------------------------------

def _slug(value: str) -> str:
    """Conservative slug for filenames: keep word chars, collapse the rest."""
    s = re.sub(r"[^\w-]+", "-", value, flags=re.UNICODE).strip("-").lower()
    return s or "untagged"


def _candidate_path(store_dir: Path, kind: str, key: str) -> str:
    """Stable in-area filename per (kind, key). Overwrite-friendly.

    We feed this through CandidatesArea.stage() as `path`; CandidatesArea
    then slugs separators away, so we pass an already-sanitised string.
    """
    return f"identifier__{kind}__{_slug(key)}"


def _compose_merged_text(tag: str, sources: list[Path]) -> str:
    """Concatenate source bodies verbatim under per-source headers.

    Identifier does NOT summarise or rewrite — that crosses into LLM
    territory. The compactor writes this string to medium/ as-is.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    parts = [
        "---",
        "tier: medium",
        f"tags: {tag}",
        f"merged_from: {', '.join(p.name for p in sources)}",
        f"merged_at: {today}",
        "---",
        "",
        f"# 合并条目 — tag: {tag}",
        "",
        "本条目由 identifier 按相同 tag 合并 short 条目机械生成（无语义改写）。",
        "源条目原文按时间顺序逐条收录：",
        "",
    ]
    for src in sorted(sources, key=lambda p: p.name):
        body = _body_after_frontmatter(_read_text(src))
        parts.append(f"## {src.name}")
        parts.append("")
        parts.append(body if body else "（空）")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _target_medium_path(store_dir: Path, tag: str, sources: list[Path]) -> Path:
    """Stable medium filename per (tag, source-set).

    Hash the sorted source basenames so two different groupings of the same
    tag don't trample each other. compact() then enforces the medium/
    boundary on this path.
    """
    digest = hashlib.sha1(
        "|".join(sorted(p.name for p in sources)).encode("utf-8")
    ).hexdigest()[:8]
    today = datetime.now().strftime("%Y-%m-%d")
    fname = f"{today}-merged-{_slug(tag)}-{digest}.md"
    return store_dir / "medium" / fname


# ---------------------------------------------------------------------------
# Helpers — staging
# ---------------------------------------------------------------------------

def _stage_delete_short(area: CandidatesArea, short_path: Path) -> None:
    candidate = {
        "kind": "delete_short",
        "path": _candidate_path(short_path.parent.parent, "delete", short_path.name),
        "source_short_paths": [str(short_path)],
        "reason": "distilled + referencing medium exists",
    }
    area.stage(candidate)


def _stage_merge(area: CandidatesArea, store_dir: Path,
                 tag: str, group: list[Path]) -> None:
    target = _target_medium_path(store_dir, tag, group)
    text = _compose_merged_text(tag, group)
    candidate = {
        "kind": "merge_short_into_medium",
        # Stable per-tag candidate name → re-staging overwrites in place
        # (idempotent when the group grows).
        "path": _candidate_path(store_dir, "merge", tag),
        "target_medium_path": str(target),
        "target_medium_text": text,
        "source_short_paths": [str(p) for p in group],
        "tag": tag,
    }
    area.stage(candidate)
