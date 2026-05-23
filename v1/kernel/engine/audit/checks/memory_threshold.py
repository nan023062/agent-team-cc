"""checks/memory_threshold.py — memory store volume / staleness / promotion.

Short tier:
  MEMORY_SHORT_OVERFLOW   info/warn/error  short tier entry count exceeds threshold
  MEMORY_STALE            warn             individual short entry older than max age
  MEMORY_VOLUME           warn             short tier total size exceeds threshold

Medium tier (promotion signals — two complementary findings per overflow):
  MEMORY_PROMOTE_TO_AGENT_SKILL   warn/error  HR should distill to agent skills
  MEMORY_PROMOTE_TO_DNA_KNOWLEDGE warn/error  architect should distill to .dna
"""

from __future__ import annotations

import time
from pathlib import Path

from ..config import resolve_bands
from ..result import AuditFinding

_DAY_SECONDS = 86400
_ERROR_MULTIPLIER = 1.5


def _list_files(tier_dir: Path) -> list[Path]:
    if not tier_dir.exists():
        return []
    return sorted(p for p in tier_dir.glob("*.md") if p.is_file())


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    cfg = config.get("memory", {})
    short_max = cfg.get("short_max_entries", 80)
    short_age = cfg.get("short_max_age_days", 7)
    short_kb = cfg.get("short_max_total_kb", 512)
    medium_max = cfg.get("medium_max_entries", 40)

    mem_root = project_root / ".cbim" / "memory"
    short_dir = mem_root / "short"
    medium_dir = mem_root / "medium"

    short_files = _list_files(short_dir)
    medium_files = _list_files(medium_dir)

    short_count = len(short_files)
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

    now = time.time()
    age_cutoff = short_age * _DAY_SECONDS
    for f in short_files:
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        age_days = (now - mtime) / _DAY_SECONDS
        if (now - mtime) > age_cutoff:
            findings.append(AuditFinding(
                check="memory_threshold",
                severity="warn",
                target=f"short/{f.name}",
                message=(
                    f"short entry {f.name!r} is {age_days:.1f} days old "
                    f"(max {short_age})"
                ),
                suggestion=f"Run `cbim memory cleanup --keep-days {short_age}`.",
                code="MEMORY_STALE",
                metadata={"age_days": round(age_days, 1), "threshold_days": short_age},
            ))

    total_bytes = 0
    for f in short_files:
        try:
            total_bytes += f.stat().st_size
        except OSError:
            continue
    total_kb = total_bytes / 1024
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

    medium_count = len(medium_files)
    if medium_count >= medium_max:
        sev = "error" if medium_count >= medium_max * _ERROR_MULTIPLIER else "warn"
        findings.append(AuditFinding(
            check="memory_threshold",
            severity=sev,
            target=None,
            message=(
                f"medium tier has {medium_count} entries with recurring "
                "agent-capability patterns; HR should distill to agent skills"
            ),
            suggestion=(
                "Dispatch HR: review medium-tier patterns and propose new "
                "`agent_*.skills.*` entries via `cbim agent update --target body`."
            ),
            code="MEMORY_PROMOTE_TO_AGENT_SKILL",
            metadata={"count": medium_count, "threshold": medium_max},
        ))
        findings.append(AuditFinding(
            check="memory_threshold",
            severity=sev,
            target=None,
            message=(
                f"medium tier has {medium_count} entries with recurring "
                "module-knowledge patterns; architect should distill to .dna"
            ),
            suggestion=(
                "Dispatch architect: review medium-tier patterns and promote to "
                "`.dna/module.md` via `cbim dna edit`."
            ),
            code="MEMORY_PROMOTE_TO_DNA_KNOWLEDGE",
            metadata={"count": medium_count, "threshold": medium_max},
        ))

    return findings
