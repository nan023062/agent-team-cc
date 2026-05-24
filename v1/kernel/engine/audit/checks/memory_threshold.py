"""checks/memory_threshold.py — memory store volume / staleness drift.

Thin metrics consumer over kernel/memory's `stats()` interface. Does not
read raw memory files; does not judge promotion-worthiness. Three findings:
  MEMORY_SHORT_OVERFLOW  info/warn/error  short tier entry count band
  MEMORY_STALE           warn             oldest short entry over age cutoff
  MEMORY_VOLUME          warn             short tier total bytes over cutoff
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from memory import stats as memory_stats

from ..config import resolve_bands
from ..result import AuditFinding

_DAY_SECONDS = 86400


def _parse_iso(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    cfg = config.get("memory", {})
    short_max = cfg.get("short_max_entries", 80)
    short_age = cfg.get("short_max_age_days", 7)
    short_kb = cfg.get("short_max_total_kb", 512)

    s = memory_stats(
        filter={"tier": "short"},
        store_dir=project_root / ".cbim" / "memory",
    )

    short_count = s["counts_by_tier"]["short"]
    sev = resolve_bands(short_count, short_max)
    if sev:
        findings.append(AuditFinding(
            check="memory_threshold",
            severity=sev,
            target="short",
            message=(
                f"short tier has {short_count} entries "
                f"(threshold {short_max})"
            ),
            suggestion="Distill via `cbim skill show memory_distill`.",
            code="MEMORY_SHORT_OVERFLOW",
            metadata={"count": short_count, "threshold": short_max},
        ))

    oldest_ts = _parse_iso(s.get("oldest_entry_at"))
    if oldest_ts is not None:
        age_days = (time.time() - oldest_ts) / _DAY_SECONDS
        if age_days > short_age:
            findings.append(AuditFinding(
                check="memory_threshold",
                severity="warn",
                target="short",
                message=(
                    f"oldest short entry is {age_days:.1f} days old "
                    f"(max {short_age})"
                ),
                suggestion=f"Run `cbim memory cleanup --keep-days {short_age}`.",
                code="MEMORY_STALE",
                metadata={
                    "oldest_age_days": round(age_days, 1),
                    "threshold_days": short_age,
                },
            ))

    short_bytes = s["disk_bytes"].get("short", 0)
    total_kb = short_bytes / 1024
    if total_kb >= short_kb:
        findings.append(AuditFinding(
            check="memory_threshold",
            severity="warn",
            target="short",
            message=(
                f"short tier total size {total_kb:.1f} KB "
                f"exceeds threshold {short_kb} KB"
            ),
            suggestion="Distill or `cbim memory cleanup` to reduce volume.",
            code="MEMORY_VOLUME",
            metadata={"size_kb": round(total_kb, 1), "threshold_kb": short_kb},
        ))

    return findings
