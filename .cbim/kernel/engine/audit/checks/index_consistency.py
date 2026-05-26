"""checks/index_consistency.py — compare .cbim/index.md against filesystem scan.

Findings:
  INDEX_MISSING_ROOT  error  registry file does not exist at all
  INDEX_MISSING_ENTRY warn   on-disk module not listed in registry
  INDEX_STALE_ENTRY   warn   registry path no longer has .dna/module.md on disk
  INDEX_PATH_FORMAT   warn   entry not normalised (trailing slash, leading ./, etc.)
  INDEX_DUPLICATE     warn   same path listed twice
"""

from __future__ import annotations

from pathlib import Path

from cbi._primitives.modules import index_path, list_modules, read_index

from ..result import AuditFinding

_SUGGEST_REINDEX = "Run `cbim dna reindex` to rebuild the registry from disk."


def _normalise(p: str) -> str:
    s = p.strip()
    if s.startswith("./"):
        s = s[2:]
    if s != "." and s.endswith("/"):
        s = s.rstrip("/")
    return s


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    reg_file = index_path(project_root)
    if not reg_file.exists():
        findings.append(AuditFinding(
            check="index_consistency",
            severity="error",
            target=str(reg_file.relative_to(project_root)),
            message=".cbim/index.md is missing; module registry not initialised",
            suggestion=_SUGGEST_REINDEX,
            code="INDEX_MISSING_ROOT",
        ))
        return findings

    raw_entries = read_index(project_root)
    seen: dict[str, int] = {}
    normalised: list[str] = []
    for raw in raw_entries:
        norm = _normalise(raw)
        if norm != raw:
            findings.append(AuditFinding(
                check="index_consistency",
                severity="warn",
                target=raw,
                message=f"registry entry {raw!r} is not normalised; expected {norm!r}",
                suggestion=_SUGGEST_REINDEX,
                code="INDEX_PATH_FORMAT",
                metadata={"normalised": norm},
            ))
        seen[norm] = seen.get(norm, 0) + 1
        normalised.append(norm)
    for path, count in seen.items():
        if count > 1:
            findings.append(AuditFinding(
                check="index_consistency",
                severity="warn",
                target=path,
                message=f"registry contains duplicate entry {path!r} ({count} times)",
                suggestion=_SUGGEST_REINDEX,
                code="INDEX_DUPLICATE",
                metadata={"count": count},
            ))

    on_disk = {m["path"] for m in list_modules(project_root, use_registry=False)}
    registered = set(normalised)

    for missing in sorted(on_disk - registered):
        findings.append(AuditFinding(
            check="index_consistency",
            severity="warn",
            target=missing,
            message=f"module {missing!r} exists on disk but is not in the registry",
            suggestion=_SUGGEST_REINDEX,
            code="INDEX_MISSING_ENTRY",
        ))
    for stale in sorted(registered - on_disk):
        findings.append(AuditFinding(
            check="index_consistency",
            severity="warn",
            target=stale,
            message=f"registry path {stale!r} has no .dna/module.md on disk",
            suggestion=_SUGGEST_REINDEX,
            code="INDEX_STALE_ENTRY",
        ))

    return findings
