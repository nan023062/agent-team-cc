"""arch_exec — architect-execution sub-loop, expressed as a Python BT subtree.

Topology (matches design/WORKFLOW-ARCHITECT.zh-CN.md §2):

    Sequence([
        Scan,
        StateCheck,
        SwitchBranch(by bb.arch_state, {
            "missing":         Sequence([Worth, SwitchBranch(create-or-skip)]),
            "in_sync":         Extract,
            "code_ahead":      Diff,
            "knowledge_ahead": Validate,
        }, default=AlwaysSuccess),
        Map,
        Assemble,
    ])

Construction is parametric on `llm_client` so tests can inject stubs.
"""

from __future__ import annotations

from typing import Any

from engine.core.composite import AlwaysSuccess, Sequence, SwitchBranch
from engine.core.node import Node

from . import assemble, create, diff, extract, map_tasks, scan, state_check, validate, worth


def build_architect_execution_subtree(llm_client: Any) -> Node:
    """Build the architect-execution subtree rooted at a Sequence.

    The returned Node is stateless across ticks (per BT iron rule); the
    same instance can be reused across ticks/runs as long as the bb is
    swapped per run.
    """
    scan_node = scan.build(llm_client)
    state_check_node = state_check.build(llm_client)
    worth_node = worth.build(llm_client)
    create_node = create.build(llm_client)
    extract_node = extract.build(llm_client)
    diff_node = diff.build(llm_client)
    validate_node = validate.build(llm_client)
    map_node = map_tasks.build(llm_client)
    assemble_node = assemble.build(llm_client)

    create_or_skip = SwitchBranch(
        name="WorthSwitch",
        key_fn=lambda bb: "create" if getattr(bb, "arch_worth", False) else "skip",
        cases={
            "create": create_node,
            "skip": AlwaysSuccess(name="SkipCreate"),
        },
    )

    missing_branch = Sequence([worth_node, create_or_skip], name="MissingBranch")

    state_switch = SwitchBranch(
        name="StateSwitch",
        key_fn=lambda bb: getattr(bb, "arch_state", "missing"),
        cases={
            "missing": missing_branch,
            "in_sync": extract_node,
            "code_ahead": diff_node,
            "knowledge_ahead": validate_node,
        },
        default=AlwaysSuccess(name="StateDefault"),
    )

    return Sequence(
        [scan_node, state_check_node, state_switch, map_node, assemble_node],
        name="ArchitectExecution",
    )


__all__ = ["build_architect_execution_subtree"]
