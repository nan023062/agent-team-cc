"""Assertion DSL over CBIM session logs.

Session log line format (from engine.logger.append):

    [YYYY-MM-DD HH:MM:SS] [TAG] [agent:<name>] <message>

Tags observed:
    USER           — user prompt (UserPromptSubmit hook)
    CALL           — generic tool invocation (Read/Write/Edit/Bash/Glob/Grep/...)
    CBIM:<dom>     — cbim CLI bash call; dom in {dna, agent, skill, memory, snapshot, log, ...}
    CBIM:skill     — Skill tool invocation
    CBIM:agent     — Agent tool dispatch (subagent_type=<name>)
    RET            — tool result preview
    RET:<dom>      — cbim CLI tool result
    ASSIST         — final assistant text (Stop hook)
    MCP            — MCP tool call

The `[agent:<name>]` segment is present only when the line originated from a
subagent transcript.
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
    tag: str           # e.g. "USER", "CALL", "CBIM:dna", "CBIM:agent", "RET", "ASSIST"
    agent: str         # "" for main session, otherwise the subagent type
    message: str
    raw: str


@dataclass
class Verdict:
    passed: bool
    diagnostics: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


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
    """True iff a `[CBIM:agent]` line dispatched the given subagent_type."""
    needle = f"subagent={agent_name}"
    return any(e.tag == "CBIM:agent" and needle in e.message for e in events)


def dispatch_order(events: list[LogEvent], *agents: str) -> bool:
    """True iff the given agents appear as dispatches in this order (subsequence)."""
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
    """True iff an MCP tool with the given name was invoked.

    MCP tools surface either as a [MCP] line or as a [CALL] line whose
    message starts with `mcp__cbim__<name>`. We accept both shapes.
    """
    for e in events:
        if e.tag == "MCP" and tool_name in e.message:
            return True
        if e.tag == "CALL" and tool_name in e.message:
            return True
    return False


def has_cbim_call(events: list[LogEvent], domain: str, verb: str | None = None) -> bool:
    """True iff a `cbim <domain> [verb] ...` CLI call was logged.

    domain example: "dna" matches tag "CBIM:dna". When verb is given, the
    message must also contain it (matches `cbim dna init ...`).
    """
    tag = f"CBIM:{domain}"
    for e in events:
        if e.tag != tag:
            continue
        if verb is None or f" {verb}" in f" {e.message} ":
            return True
    return False


def agents_seen(events: list[LogEvent]) -> set[str]:
    """Subagent names that produced at least one logged event."""
    return {e.agent for e in events if e.agent}


def memory_written_files(project_root: Path) -> list[Path]:
    """All files currently under `.cbim/memory/short/`."""
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
    """EXECUTION loop assertions.

    Positive case: a coding task — coordinator must dispatch architect (the
    必经门) before the work agent, then the work agent (programmer or similar)
    must run.

    Negative case: a pure-query — coordinator must NOT dispatch a work agent;
    no programmer/work agent invocation should be visible. Architect may or
    may not be touched (per spec it can be skipped for pure queries).
    """
    diags: list[str] = [_diag_summary(events, project_root)]
    ok = has_user_event(events)
    if not ok:
        diags.append("missing [USER] event — UserPromptSubmit hook did not fire")

    if positive:
        arch_dispatched = has_dispatch(events, "architect")
        worker_dispatched = (
            has_dispatch(events, "programmer")
            or any(
                e.tag == "CBIM:agent" and "subagent=" in e.message and "architect" not in e.message and "auditor" not in e.message and "hr" not in e.message
                for e in events
            )
        )
        if not arch_dispatched:
            ok = False
            diags.append("expected architect dispatch (knowledge-gate) — none seen")
        if not worker_dispatched:
            ok = False
            diags.append("expected a work-agent dispatch (e.g. programmer) — none seen")
        if arch_dispatched and worker_dispatched and not dispatch_order(events, "architect", "programmer"):
            # Order check only if both were dispatched and the worker is programmer.
            if has_dispatch(events, "programmer"):
                ok = False
                diags.append("dispatch order wrong: programmer ran before architect")
    else:
        # Negative: pure query — should not dispatch a work agent at all.
        if has_dispatch(events, "programmer"):
            ok = False
            diags.append("unexpected programmer dispatch on a pure-query prompt")

    return Verdict(passed=ok, diagnostics=diags)


def assert_architect_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    """ARCHITECT loop assertions.

    Positive case: a DNA-write request — architect must be dispatched AND a
    `cbim dna init` (or equivalent write verb) must surface in the log.

    Negative case: a read-only "list modules" request — `cbim dna` traffic
    should be read-only (`list`/`show`/`scan`), no `init`/`edit`/`update`.
    """
    diags: list[str] = [_diag_summary(events, project_root)]
    ok = has_user_event(events)
    if not ok:
        diags.append("missing [USER] event")

    if positive:
        if not has_dispatch(events, "architect"):
            ok = False
            diags.append("expected architect dispatch — none seen")
        if not (
            has_cbim_call(events, "dna", "init")
            or has_mcp_call(events, "dna_init")
        ):
            ok = False
            diags.append("expected `cbim dna init` or `mcp__cbim__dna_init` — none seen")
    else:
        forbidden = ("init", "edit", "update", "split", "merge", "archive")
        offenders = [
            e.raw for e in events
            if e.tag == "CBIM:dna" and any(f" {v}" in f" {e.message} " for v in forbidden)
        ]
        if offenders:
            ok = False
            diags.append(f"unexpected DNA write verbs on read-only prompt: {offenders[:3]}")

    return Verdict(passed=ok, diagnostics=diags)


def assert_hr_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    """HR loop assertions.

    Positive case: a recruit-an-agent request — HR must be dispatched AND a
    `cbim agent scaffold` (or equivalent) must surface.

    Negative case: a list-agents request — `cbim agent` traffic should be
    read-only (`list`/`show`), no `scaffold`/`update`/`archive`.
    """
    diags: list[str] = [_diag_summary(events, project_root)]
    ok = has_user_event(events)
    if not ok:
        diags.append("missing [USER] event")

    if positive:
        if not has_dispatch(events, "hr"):
            ok = False
            diags.append("expected hr dispatch — none seen")
        if not (
            has_cbim_call(events, "agent", "scaffold")
            or has_mcp_call(events, "agent_scaffold")
        ):
            ok = False
            diags.append("expected `cbim agent scaffold` — none seen")
    else:
        forbidden = ("scaffold", "update", "archive", "edit")
        offenders = [
            e.raw for e in events
            if e.tag == "CBIM:agent" and any(f" {v}" in f" {e.message} " for v in forbidden)
        ]
        if offenders:
            ok = False
            diags.append(f"unexpected agent write verbs on read-only prompt: {offenders[:3]}")

    return Verdict(passed=ok, diagnostics=diags)


def assert_memory_loop(
    events: list[LogEvent],
    project_root: Path,
    *,
    positive: bool,
) -> Verdict:
    """MEMORY loop assertions.

    Positive case: explicit "remember this" request — at least one new file
    must exist under `.cbim/memory/short/` after the run, AND we expect a
    `cbim memory write` (or `mcp__cbim__memory_write`) call.

    Negative case: pure social pleasantries — coordinator-driven
    `cbim memory write` should NOT fire (hooks may still touch short/, but the
    LLM should not have explicitly written). We tolerate Stop-hook writes by
    not asserting on file count for the negative; we assert only that no
    explicit `cbim memory write` verb is seen.
    """
    diags: list[str] = [_diag_summary(events, project_root)]
    ok = has_user_event(events)
    if not ok:
        diags.append("missing [USER] event")

    if positive:
        wrote = (
            has_cbim_call(events, "memory", "write")
            or has_mcp_call(events, "memory_write")
        )
        files = memory_written_files(project_root)
        if not wrote:
            ok = False
            diags.append("expected `cbim memory write` (LLM-driven) — none seen")
        if not files:
            ok = False
            diags.append("expected new file under .cbim/memory/short/ — none present")
    else:
        wrote = (
            has_cbim_call(events, "memory", "write")
            or has_mcp_call(events, "memory_write")
        )
        if wrote:
            ok = False
            diags.append("unexpected LLM-driven `cbim memory write` on a greeting prompt")

    return Verdict(passed=ok, diagnostics=diags)
