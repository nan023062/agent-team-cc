"""actions/collect_arch_advice.py — post-yield collector for Architect report.

Owns ``on_resume`` for the architect-governance dispatch path. The
Runner's resume path lands here (per dream/api/result.DREAM_AGENT_TYPE_TO_LEAF
mapping). On resume we parse the architect's payload through
``loops.architect_governance.parse_response`` and store the structured
advice on ``bb.arch_governance_report``.

Tick semantics:
  - Report already present (i.e. resume completed) → SUCCESS.
  - Dispatch flag never set (DispatchArchGovern's tick never ran or short-
    circuited) → SUCCESS no-op; nothing to collect.
  - Dispatch flag set but no report on bb → engine-internal failure
    (on_resume was not called for some reason). Write a placeholder error
    report and return FAILURE.

Pairs with ``actions/dispatch_arch.DispatchArchGovern`` inside
``ArchitectGovernanceStep`` sequence.
"""

from __future__ import annotations

from typing import Any

from engine.core.node import Node, Status


def _loop():
    # Lazy import to break the import cycle.
    import engine.dream.loops.architect_governance as m
    return m


class CollectArchAdvice(Node):
    def __init__(self, *, name: str = "CollectArchAdvice") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.arch_governance_report is not None:
            return Status.SUCCESS
        if not bb.arch_governance_dispatched:
            # Dispatch sibling decided not to dispatch (already done in a
            # prior tick or pre-seeded). Nothing to collect.
            return Status.SUCCESS
        # Dispatched but on_resume never delivered a payload — surface as
        # FAILURE with a placeholder report so EmitReport still has shape.
        bb.arch_governance_report = {
            "error": "no_payload_received",
            "safe_actions_applied": [],
            "advice_pending": [],
        }
        return Status.FAILURE

    def on_resume(self, bb, payload: Any) -> None:
        parsed = _loop().parse_response(_extract_text(payload))
        # parse_response returns {"arch_governance_report": {...}, ...}
        report = parsed.get("arch_governance_report")
        if report is None and parsed.get("error"):
            report = {
                "error": parsed["error"],
                "safe_actions_applied": [],
                "advice_pending": [],
            }
        bb.arch_governance_report = report or {
            "safe_actions_applied": [],
            "advice_pending": [],
        }
        bb.pending_dispatch = None


def _extract_text(payload: Any) -> Any:
    """Unwrap Task-tool dict shape ({status, output, raw, ...}) into the
    architect's raw output string, leaving dicts/lists untouched so
    parse_response can json-decode them if needed."""
    if isinstance(payload, dict) and "output" in payload:
        return payload.get("output") or ""
    return payload
