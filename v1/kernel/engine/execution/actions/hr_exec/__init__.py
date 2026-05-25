"""hr_exec — HR-execution sub-loop, expressed as a Python BT subtree.

Topology (matches design/WORKFLOW-HR.zh-CN.md §1 执行模式):

    Sequence([
        Scan,                                     # deterministic: read .claude/agents/
        ForEach(arch_plan → hr_current_task,
            Sequence([
                Match,                            # LLM: grade inventory vs task
                SwitchBranch(by hr_current_match.kind, {
                    "fit":  AppendAssignment,     # deterministic append
                    "weak": AppendWeak,           # deterministic append + train-hint
                    "miss": Sequence([
                        CoreAgentSelector,        # deterministic core-agent table
                        AppendResult,             # appends assignment or gap
                    ]),
                }),
            ]),
        ),
        Build,                                    # deterministic: draft → agent_assignments
    ])

Construction is parametric on `llm_client` so tests can inject stubs.
Only Match consumes the LLM; everything else is deterministic.
"""

from __future__ import annotations

from typing import Any

from engine.core.composite import ForEach, Sequence, SwitchBranch
from engine.core.node import Node, Status

from . import assemble, decide, match, scan


def _append_draft(bb, record: dict) -> None:
    """Append `record` to bb.hr_assignments_draft, creating the list on
    first write. Tolerates blackboards that pin a __slots__ schema and
    refuse new attributes — in that case the draft path is the parent
    loop's problem to wire up.
    """
    draft = getattr(bb, "hr_assignments_draft", None)
    if not isinstance(draft, list):
        draft = []
    bb.hr_assignments_draft = draft + [record]


def _build_assignment_record(bb, *, weak: bool) -> dict:
    task = getattr(bb, "hr_current_task", None) or {}
    m = getattr(bb, "hr_current_match", None) or {}
    rec = {
        "task_id": task.get("id"),
        "agent_file": m.get("agent_file"),
        "capability": task.get("required_capability"),
        "match_kind": m.get("kind"),
        "note": m.get("note", ""),
    }
    if weak:
        rec["training_suggested"] = True
    return rec


def _build_gap_record(bb) -> dict:
    task = getattr(bb, "hr_current_task", None) or {}
    m = getattr(bb, "hr_current_match", None) or {}
    return {
        "task_id": task.get("id"),
        "agent_file": None,
        "capability": task.get("required_capability"),
        "match_kind": "miss",
        "agent_gap": task.get("required_capability") or "unknown",
        "note": m.get("note", ""),
    }


class _AppendAssignment(Node):
    """fit branch — append a clean assignment record."""

    def __init__(self, *, name: str = "AppendAssignment") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        _append_draft(bb, _build_assignment_record(bb, weak=False))
        return Status.SUCCESS


class _AppendWeak(Node):
    """weak branch — append assignment record with training suggestion."""

    def __init__(self, *, name: str = "AppendWeak") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        _append_draft(bb, _build_assignment_record(bb, weak=True))
        return Status.SUCCESS


class _AppendResult(Node):
    """post-CoreAgentSelector — either a fit (table-upgraded) or a gap."""

    def __init__(self, *, name: str = "AppendResult") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        m = getattr(bb, "hr_current_match", None) or {}
        if m.get("kind") == "fit":
            _append_draft(bb, _build_assignment_record(bb, weak=False))
        else:
            _append_draft(bb, _build_gap_record(bb))
        return Status.SUCCESS


def build_hr_execution_subtree(llm_client: Any) -> Node:
    """Build the HR-execution subtree rooted at a Sequence.

    The returned Node is stateless across ticks (per BT iron rule); the
    same instance can be reused across ticks/runs as long as the bb is
    swapped per run.
    """
    scan_node = scan.build()
    match_node = match.build(llm_client)
    core_select_node = decide.build()
    build_node = assemble.build()

    per_task_switch = SwitchBranch(
        name="MatchKindSwitch",
        key_fn=lambda bb: (getattr(bb, "hr_current_match", None) or {}).get("kind", "miss"),
        cases={
            "fit":  _AppendAssignment(),
            "weak": _AppendWeak(),
            "miss": Sequence([core_select_node, _AppendResult()], name="MissBranch"),
        },
    )

    per_task_body = Sequence([match_node, per_task_switch], name="PerTaskBody")

    per_task_loop = ForEach(
        name="PerTaskLoop",
        items_field="arch_plan",
        item_var="hr_current_task",
        child=per_task_body,
    )

    return Sequence(
        [scan_node, per_task_loop, build_node],
        name="HrExecution",
    )


__all__ = ["build_hr_execution_subtree"]
