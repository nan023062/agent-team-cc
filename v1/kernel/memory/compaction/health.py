"""
compaction/health.py — HealthChecker.

The contract (compaction/.dna/module.md Key Decision #3):
- Compaction owns health thresholds; audit must NOT re-implement them.
- audit reaches indicators via the parent facade's stats() and decides
  whether to surface a finding.
- HealthChecker.check() returns a HealthReport — does NOT emit, log, or
  notify.

Threshold sources (in priority order):
  1. memory config `compaction` section (`_config.load_config()`) — caller
     can pin tighter / looser values per deployment.
  2. Hard-coded defaults below — same numbers the audit `memory_threshold`
     check uses, so a "you need to compact" signal from this checker and a
     "memory threshold breached" audit finding will fire in lockstep.

Indicators surfaced:
  short_count, short_bytes, medium_count, candidate_count, oldest_age_days,
  index_drift (bool — used by MemRebuildIndex).

Breaches surfaced (string codes — stable for callers that branch on them):
  SHORT_OVERFLOW   short_count >= short_max_entries
  SHORT_VOLUME     short_bytes / 1024 >= short_max_total_kb
  SHORT_STALE      oldest short entry age (days) >= short_max_age_days
  CANDIDATES_BACKLOG  candidate_count >= candidate_max
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_DAY_SECONDS = 86400

# Defaults aligned with engine/audit/checks/memory_threshold.py so the two
# layers agree out of the box. Override via memory config `compaction`.
_DEFAULT_THRESHOLDS = {
    "short_max_entries": 80,
    "short_max_total_kb": 512,
    "short_max_age_days": 7,
    "candidate_max": 200,
    # Index drift: backend index newer-than-source check is backend specific;
    # FileBackend treats files as the index so drift is always False unless
    # a future backend flags it. Kept as a knob so we don't lose the seam.
    "index_drift_seconds": None,
}


@dataclass
class HealthReport:
    indicators: dict = field(default_factory=dict)
    breaches: list[str] = field(default_factory=list)
    # Mirror the rebuild flag at top-level so MemRebuildIndex can read it
    # without poking into indicators. False by default — never spurious-true.
    index_drift: bool = False


def _load_thresholds() -> dict:
    """Pull thresholds from memory config, falling back to defaults."""
    out = dict(_DEFAULT_THRESHOLDS)
    try:
        from memory._config import load_config
        cfg = load_config().get("compaction", {})
        if isinstance(cfg, dict):
            for k in out:
                if k in cfg and cfg[k] is not None:
                    out[k] = cfg[k]
    except Exception:
        # Config layer is best-effort; defaults are always safe.
        pass
    return out


class HealthChecker:

    def __init__(self, store_dir: Path) -> None:
        self._store = Path(store_dir)

    def check(self) -> HealthReport:
        thresholds = _load_thresholds()
        indicators = self._collect_indicators()
        breaches: list[str] = []

        if indicators["short_count"] >= thresholds["short_max_entries"]:
            breaches.append("SHORT_OVERFLOW")
        if (indicators["short_bytes"] / 1024.0) >= thresholds["short_max_total_kb"]:
            breaches.append("SHORT_VOLUME")
        oldest_days = indicators.get("oldest_age_days")
        if oldest_days is not None and oldest_days >= thresholds["short_max_age_days"]:
            breaches.append("SHORT_STALE")
        if indicators["candidate_count"] >= thresholds["candidate_max"]:
            breaches.append("CANDIDATES_BACKLOG")

        indicators["thresholds"] = thresholds

        return HealthReport(
            indicators=indicators,
            breaches=breaches,
            index_drift=False,  # FileBackend = files-are-index; reserved seam.
        )

    # ------------------------------------------------------------------
    # Indicator collection — file-system only, no backend dependency.
    # ------------------------------------------------------------------

    def _collect_indicators(self) -> dict:
        short_dir = self._store / "short"
        medium_dir = self._store / "medium"

        short_count, short_bytes, oldest_mtime = self._scan_tier(short_dir)
        medium_count, _medium_bytes, _ = self._scan_tier(medium_dir)
        candidate_count = self._count_candidates()

        oldest_age_days: float | None = None
        if oldest_mtime is not None:
            oldest_age_days = round((time.time() - oldest_mtime) / _DAY_SECONDS, 2)

        return {
            "short_count": short_count,
            "short_bytes": short_bytes,
            "medium_count": medium_count,
            "candidate_count": candidate_count,
            "oldest_age_days": oldest_age_days,
        }

    @staticmethod
    def _scan_tier(tier_dir: Path) -> tuple[int, int, float | None]:
        if not tier_dir.exists():
            return 0, 0, None
        count = 0
        total_bytes = 0
        oldest: float | None = None
        for p in tier_dir.glob("*.md"):
            if not p.is_file():
                continue
            count += 1
            try:
                st = p.stat()
            except OSError:
                continue
            total_bytes += st.st_size
            if oldest is None or st.st_mtime < oldest:
                oldest = st.st_mtime
        return count, total_bytes, oldest

    def _count_candidates(self) -> int:
        from .candidates import CANDIDATES_SUBDIR
        d = self._store / CANDIDATES_SUBDIR
        if not d.exists():
            return 0
        return sum(1 for _ in d.glob("*.candidate.json"))
