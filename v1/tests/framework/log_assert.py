"""Assertion DSL over CBIM session logs.

Session log line format (from engine.logger.append):

    [YYYY-MM-DD HH:MM:SS] [TAG] [agent:<name>] <message>

Tags observed:
    USER, CALL, CBIM:<dom>, CBIM:skill, CBIM:agent, RET, RET:<dom>, ASSIST, MCP

The `[agent:<name>]` segment is present only when the line originated from a
subagent transcript.

Verdict carries sub-check counts and a `top_failure` so the reporter can show
a per-case summary without re-running the assertions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_LINE_RE = re.compile(
    r"^\[(?P<ts>[0-9\- :]+)\]\s+\[(?P<tag>[^\]]+)\]\s*(?:\[agent:(?P<agent>[^\]]+)\]\s*)?(?P<msg>.*)$"
)


@dataclass
class LogEvent:
    ts: str
    tag: str
    agent: str
    message: str
    raw: str


@dataclass
class Verdict:
    passed: bool
    diagnostics: list[str] = field(default_factory=list)
    sub_checks_passed: int = 0
    sub_checks_total: int = 0
    top_failure: str | None = None

    def __bool__(self) -> bool:
        return self.passed


# ---------------------------------------------------------------------------
# Internal: scoped check helper
# ---------------------------------------------------------------------------


class _Checks:
    """Tiny check accumulator used by the assert_*_loop builders.

    Each `check(cond, fail_msg)` increments total; on pass increments passed;
    on fail records fail_msg as a diagnostic and (if first) as top_failure.
    """

    def __init__(self) -> None:
        self.passed = 0
        self.total = 0
        self.diagnostics: list[str] = []
        self.top_failure: str | None = None
        self.ok = True

    def check(self, cond: bool, fail_msg: str) -> bool:
        self.total += 1
        if cond:
            self.passed += 1
            return True
        self.ok = False
        self.diagnostics.append(fail_msg)
        if self.top_failure is None:
            self.top_failure = fail_msg
        return False

    def note(self, msg: str) -> None:
        self.diagnostics.append(msg)

    def verdict(self) -> Verdict:
        return Verdict(
            passed=self.ok,
            diagnostics=self.diagnostics,
            sub_checks_passed=self.passed,
            sub_checks_total=self.total,
            top_failure=self.top_failure,
        )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_log(log_text: str) -> list[LogEvent]:
    events: list[LogEvent] = []
    for raw in log_text.splitlines():
        line = raw.rstrip("\n")
        m = _LINE_RE.match(line)
        if not m:
            continue
        events.append(
            LogEvent(
                ts=m.group("ts").strip(),
                tag=m.group("tag").strip(),
                agent=(m.group("agent") or "").strip(),
                message=m.group("msg").strip(),
                raw=line,
            )
        )
    return events


# ---------------------------------------------------------------------------
# Query primitives
# ---------------------------------------------------------------------------

def has_dispatch(events: list[LogEvent], agent_name: str) -> bool:
    needle = f"subagent={agent_name}"
    return any(e.tag == "CBIM:agent" and needle in e.message for e in events)


def dispatch_order(events: list[LogEvent], *agents: str) -> bool:
    remaining = list(agents)
    for e in events:
        if not remaining:
            break
        if e.tag != "CBIM:agent":
            continue
        if f"subagent={remaining[0]}" in e.message:
            remaining.pop(0)
    return not remaining


def has_mcp_call(events: list[LogEvent], tool_name: str) -> bool:
    for e in events:
        if e.tag == "MCP" and tool_name in e.message:
            return True
        if e.tag == "CALL" and tool_name in e.message:
            return True
    return False


def has_audit_call(events: list[LogEvent], *, check: str | None = None) -> bool:
    """Whether `mcp__cbim__audit_run` was invoked.

    When `check` is given, also require that the check name appears in the
    same event's message (the MCP/CALL tag prints the full args payload).
    """
    for e in events:
        if e.tag not in ("MCP", "CALL"):
            continue
        if "audit_run" not in e.message:
            continue
        if check is None or check in e.message:
            return True
    return False


def has_cbim_call(events: list[LogEvent], domain: str, verb: str | None = None) -> bool:
    tag = f"CBIM:{domain}"
    for e in events:
        if e.tag != tag:
            continue
        if verb is None or f" {verb}" in f" {e.message} ":
            return True
    return False


def agents_seen(events: list[LogEvent]) -> set[str]:
    return {e.agent for e in events if e.agent}


def memory_written_files(project_root: Path) -> list[Path]:
    short = project_root / ".cbim" / "memory" / "short"
    if not short.is_dir():
        return []
    return sorted(p for p in short.rglob("*") if p.is_file())


def has_user_event(events: list[LogEvent]) -> bool:
    return any(e.tag == "USER" for e in events)


def has_assist_event(events: list[LogEvent]) -> bool:
    return any(e.tag == "ASSIST" for e in events)


# ---------------------------------------------------------------------------
# Loop-level aggregate assertions
# ---------------------------------------------------------------------------

def _diag_summary(events: list[LogEvent], project_root: Path) -> str:
    tag_counts: dict[str, int] = {}
    for e in events:
        tag_counts[e.tag] = tag_counts.get(e.tag, 0) + 1
    short_files = memory_written_files(project_root)
    return (
        f"events={len(events)} tags={tag_counts} "
        f"short_memory_files={[p.name for p in short_files]}"
    )


def assert_execution_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    c = _Checks()
    c.note(_diag_summary(events, project_root))
    c.check(has_user_event(events), "missing [USER] event — UserPromptSubmit hook did not fire")

    if positive:
        arch_dispatched = has_dispatch(events, "architect")
        worker_dispatched = (
            has_dispatch(events, "programmer")
            or any(
                e.tag == "CBIM:agent"
                and "subagent=" in e.message
                and "architect" not in e.message
                and "auditor" not in e.message
                and "hr" not in e.message
                for e in events
            )
        )
        c.check(arch_dispatched, "expected architect dispatch (knowledge-gate) — none seen")
        c.check(worker_dispatched, "expected a work-agent dispatch (e.g. programmer) — none seen")
        if arch_dispatched and worker_dispatched and has_dispatch(events, "programmer"):
            c.check(
                dispatch_order(events, "architect", "programmer"),
                "dispatch order wrong: programmer ran before architect",
            )
    else:
        c.check(
            not has_dispatch(events, "programmer"),
            "unexpected programmer dispatch on a pure-query prompt",
        )

    return c.verdict()


def assert_architect_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    c = _Checks()
    c.note(_diag_summary(events, project_root))
    c.check(has_user_event(events), "missing [USER] event")

    if positive:
        c.check(has_dispatch(events, "architect"), "expected architect dispatch — none seen")
        c.check(
            has_cbim_call(events, "dna", "init") or has_mcp_call(events, "dna_init"),
            "expected `cbim dna init` or `mcp__cbim__dna_init` — none seen",
        )
    else:
        forbidden = ("init", "edit", "update", "split", "merge", "archive")
        offenders = [
            e.raw for e in events
            if e.tag == "CBIM:dna" and any(f" {v}" in f" {e.message} " for v in forbidden)
        ]
        c.check(not offenders, f"unexpected DNA write verbs on read-only prompt: {offenders[:3]}")

    return c.verdict()


def assert_hr_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    c = _Checks()
    c.note(_diag_summary(events, project_root))
    c.check(has_user_event(events), "missing [USER] event")

    if positive:
        c.check(has_dispatch(events, "hr"), "expected hr dispatch — none seen")
        c.check(
            has_cbim_call(events, "agent", "scaffold") or has_mcp_call(events, "agent_scaffold"),
            "expected `cbim agent scaffold` — none seen",
        )
    else:
        forbidden = ("scaffold", "update", "archive", "edit")
        offenders = [
            e.raw for e in events
            if e.tag == "CBIM:agent" and any(f" {v}" in f" {e.message} " for v in forbidden)
        ]
        c.check(not offenders, f"unexpected agent write verbs on read-only prompt: {offenders[:3]}")

    return c.verdict()


def assert_audit_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    check_name: str,
    expected_agent: str,
) -> Verdict:
    """Verdict for an audit-loop case.

    Sub-checks:
      1. [USER] event present
      2. coordinator dispatched `expected_agent`
      3. that agent (or auditor) invoked `mcp__cbim__audit_run`
      4. the invocation referenced `check_name` (best-effort; only required
         when the helper can prove either a check arg or an empty-args
         all-checks call — empty-args is accepted as a superset)
    """
    c = _Checks()
    c.note(_diag_summary(events, project_root))
    c.check(has_user_event(events), "missing [USER] event")
    c.check(
        has_dispatch(events, expected_agent),
        f"expected {expected_agent!r} dispatch — none seen",
    )
    c.check(
        has_audit_call(events),
        "expected `mcp__cbim__audit_run` call — none seen",
    )
    # The model may call audit_run with no `checks` arg (= run all) which is a
    # valid superset; only fail if it called audit_run with a *different*
    # explicit check and never included `check_name`.
    audit_msgs = [
        e.message for e in events
        if e.tag in ("MCP", "CALL") and "audit_run" in e.message
    ]
    if audit_msgs:
        any_with_check = any(check_name in m for m in audit_msgs)
        any_all_checks = any(
            "checks" not in m or "checks=None" in m or "checks=[]" in m
            for m in audit_msgs
        )
        c.check(
            any_with_check or any_all_checks,
            f"audit_run never targeted {check_name!r} and never ran the full set; calls={audit_msgs[:3]}",
        )
    return c.verdict()


def assert_memory_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    c = _Checks()
    c.note(_diag_summary(events, project_root))
    c.check(has_user_event(events), "missing [USER] event")

    if positive:
        wrote = has_cbim_call(events, "memory", "write") or has_mcp_call(events, "memory_write")
        files = memory_written_files(project_root)
        c.check(wrote, "expected `cbim memory write` (LLM-driven) — none seen")
        c.check(bool(files), "expected new file under .cbim/memory/short/ — none present")
    else:
        wrote = has_cbim_call(events, "memory", "write") or has_mcp_call(events, "memory_write")
        c.check(not wrote, "unexpected LLM-driven `cbim memory write` on a greeting prompt")

    return c.verdict()
