"""audit/cli.py — `cbim audit ...` subparser + dispatch.

Subcommands:
  run [--severity {info,warn,error}] [--check NAME ...] [--json]
  index | memory | agents | dna | tree         (single-check aliases)
  list-checks

Exit codes (based on the post-filter findings):
  0   no findings, or highest severity = info
  1   highest severity = warn
  2   highest severity = error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services._fm import find_project_root

from . import list_checks, run_audit
from .registry import CHECKS
from .report import to_json, to_stdout

_SEVERITY_EXIT = {None: 0, "info": 0, "warn": 1, "error": 2}
_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}

_SINGLE_CHECK_ALIAS = {
    "index": "index_consistency",
    "memory": "memory_threshold",
    "agents": "agent_fission",
    "dna": "dna_fission",
    "tree": "dna_tree",
}


def register_audit_subparser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="audit_command")

    run_p = sub.add_parser("run", help="Run governance drift checks")
    run_p.add_argument(
        "--severity",
        choices=["info", "warn", "error"],
        default=None,
        help="Only display findings at or above this severity (also affects exit code).",
    )
    run_p.add_argument(
        "--check",
        action="append",
        default=None,
        choices=sorted(CHECKS.keys()),
        help="Run only the named check (repeatable). Default: all checks.",
    )
    run_p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")

    for alias in _SINGLE_CHECK_ALIAS:
        ap = sub.add_parser(alias, help=f"Alias for `run --check {_SINGLE_CHECK_ALIAS[alias]}`")
        ap.add_argument("--severity", choices=["info", "warn", "error"], default=None)
        ap.add_argument("--json", action="store_true")

    sub.add_parser("list-checks", help="Print available check names.")


def dispatch(args) -> int:
    cmd = getattr(args, "audit_command", None)
    if cmd is None:
        print("usage: cbim audit {run,index,memory,agents,dna,tree,list-checks}", file=sys.stderr)
        return 1

    if cmd == "list-checks":
        for name in list_checks():
            print(name)
        return 0

    if cmd in _SINGLE_CHECK_ALIAS:
        return _run(
            checks=[_SINGLE_CHECK_ALIAS[cmd]],
            severity=getattr(args, "severity", None),
            as_json=getattr(args, "json", False),
        )

    if cmd == "run":
        return _run(
            checks=getattr(args, "check", None),
            severity=getattr(args, "severity", None),
            as_json=getattr(args, "json", False),
        )

    print(f"audit: unknown subcommand {cmd!r}", file=sys.stderr)
    return 1


def _run(*, checks: list[str] | None, severity: str | None, as_json: bool) -> int:
    root = Path(find_project_root(None))
    result = run_audit(root, checks=checks)

    if severity is not None:
        min_rank = _SEVERITY_RANK[severity]
        result.findings = [f for f in result.findings if _SEVERITY_RANK[f.severity] >= min_rank]
        result.summary["total"] = len(result.findings)
        for s in ("error", "warn", "info"):
            result.summary[s] = sum(1 for f in result.findings if f.severity == s)

    if as_json:
        sys.stdout.write(to_json(result) + "\n")
    else:
        sys.stdout.write(to_stdout(result))

    return _SEVERITY_EXIT[result.max_severity()]
