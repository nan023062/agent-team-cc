"""
compaction/health.py — HealthChecker.

The contract (compaction/.dna/module.md Key Decision #3):
- Compaction owns health thresholds; audit must NOT re-implement them.
- audit reaches indicators via the parent facade's stats() and decides
  whether to surface a finding.
- HealthChecker.check() returns a HealthReport — does NOT emit, log, or
  notify.

v2 surfaces: medium tier + candidates. No more SHORT_* indicators or
breaches (short tier removed).

Thresholds (in priority order):
  1. memory config `compaction` section (`_config.load_config()`).
  2. Hard-coded defaults below.

Indicators surfaced:
  medium_count, medium_bytes, candidate_count, oldest_medium_age_days,
  index_drift (bool — reserved for backend-flagged drift).

Breaches (string codes — stable for callers that branch on them):
  CANDIDATES_BACKLOG  candidate_count >= candidate_max
  MEDIUM_VOLUME       medium_bytes / 1024 >= medium_max_total_kb
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

_DAY_SECONDS = 86400

# Defaults — keep audit/checks/memory_threshold.py in step with these.
_DEFAULT_THRESHOLDS = {
    "candidate_max": 200,
    "medium_max_total_kb": 16384,  # 16 MiB — medium is long-lived so allow plenty
    # Reserved seam for backends that flag drift directly.
    "index_drift_seconds": None,
}


@dataclass
class HealthReport:
    indicators: dict = field(default_factory=dict)
    breaches: list[str] = field(default_factory=list)
    # Mirror at top-level so MemRebuildIndex can read without poking
    # indicators. False on FileBackend (files are the index).
    index_drift: bool = False


def _load_thresholds() -> dict:
    out = dict(_DEFAULT_THRESHOLDS)
    try:
        from memory._config import load_config
        cfg = load_config().get("compaction", {})
        if isinstance(cfg, dict):
            for k in out:
                if k in cfg and cfg[k] is not None:
                    out[k] = cfg[k]
    except Exception:
        pass
    return out


class HealthChecker:

    def __init__(self, store_dir: Path) -> None:
        self._store = Path(store_dir)

    def check(self) -> HealthReport:
        thresholds = _load_thresholds()
        indicators = self._collect_indicators()
        breaches: list[str] = []

        if indicators["candidate_count"] >= thresholds["candidate_max"]:
            breaches.append("CANDIDATES_BACKLOG")
        if (indicators["medium_bytes"] / 1024.0) >= thresholds["medium_max_total_kb"]:
            breaches.append("MEDIUM_VOLUME")

        indicators["thresholds"] = thresholds

        return HealthReport(
            indicators=indicators,
            breaches=breaches,
            index_drift=False,
        )

    def _collect_indicators(self) -> dict:
        medium_dir = self._store / "medium"
        medium_count, medium_bytes, oldest_mtime = self._scan_tier(medium_dir)
        candidate_count = self._count_candidates()

        oldest_age_days: float | None = None
        if oldest_mtime is not None:
            oldest_age_days = round((time.time() - oldest_mtime) / _DAY_SECONDS, 2)

        return {
            "medium_count": medium_count,
            "medium_bytes": medium_bytes,
            "candidate_count": candidate_count,
            "oldest_medium_age_days": oldest_age_days,
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
