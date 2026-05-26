"""mcp_server/tools/audit.py — MCP tools for CBIM governance drift audit (read-only).

Read tools:
  audit_run(checks, min_severity, cwd)  — execute the audit and return JSON dict
  audit_list_checks(cwd)                — list all registered audit check names
"""

from __future__ import annotations

from pathlib import Path

from engine.audit import list_checks, run_audit

_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}


def register(mcp) -> None:
    @mcp.tool()
    def audit_run(
        checks: list[str] | None = None,
        min_severity: str | None = None,
        cwd: str = "",
    ) -> dict:
        """Run CBIM governance drift checks across .dna / .claude/agents / .cbim/memory.

        Read-only — never mutates project state.

        Args:
            checks:       Optional subset of check names (e.g. ["index_consistency",
                          "memory_threshold"]). If None, runs all registered checks.
            min_severity: Optional 'info' | 'warn' | 'error' filter applied to
                          findings. Summary counts are refreshed to stay
                          consistent with the filtered findings list.
            cwd:          Project directory (default: current working dir).

        Returns:
            AuditResult.to_dict() — keys: findings, summary, ran_at,
            project_root, config_snapshot. On unknown check names returns
            {"error": "..."}.
        """
        project_root = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        try:
            result = run_audit(project_root, checks=checks)
        except ValueError as e:
            return {"error": str(e)}

        out = result.to_dict()

        if min_severity:
            if min_severity not in _SEVERITY_RANK:
                return {
                    "error": (
                        f"unknown min_severity: {min_severity!r}; "
                        f"expected one of {sorted(_SEVERITY_RANK)}"
                    )
                }
            threshold = _SEVERITY_RANK[min_severity]
            kept = [
                f for f in out["findings"]
                if _SEVERITY_RANK[f["severity"]] >= threshold
            ]
            out["findings"] = kept
            checks_ran = out["summary"].get("checks_ran", [])
            out["summary"] = {
                "total": len(kept),
                "error": sum(1 for f in kept if f["severity"] == "error"),
                "warn": sum(1 for f in kept if f["severity"] == "warn"),
                "info": sum(1 for f in kept if f["severity"] == "info"),
                "checks_ran": checks_ran,
                "by_check": {
                    n: sum(1 for f in kept if f["check"] == n)
                    for n in checks_ran
                },
            }

        return out

    @mcp.tool()
    def audit_list_checks(cwd: str = "") -> list[str]:
        """List all registered audit check names.

        Args:
            cwd: Project directory (unused; kept for tool-signature consistency).
        """
        return list_checks()
