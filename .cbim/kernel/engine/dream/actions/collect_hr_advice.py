"""actions/collect_hr_advice.py — post-yield collector for HR report.

Mirror of ``collect_arch_advice.CollectArchAdvice``. Owns ``on_resume``
for the HR-governance dispatch path, parses the HR payload through
``loops.hr_governance.parse_response`` and stores the report on
``bb.hr_governance_report``.

Pairs with ``actions/dispatch_hr.DispatchHRGovern`` inside
``HRGovernanceStep`` sequence.
"""

from __future__ import annotations

from typing import Any

from engine.core.node import Node, Status


def _loop():
    import engine.dream.loops.hr_governance as m
    return m


class CollectHRAdvice(Node):
    def __init__(self, *, name: str = "CollectHRAdvice") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        if bb.hr_governance_report is not None:
            return Status.SUCCESS
        if not bb.hr_governance_dispatched:
            return Status.SUCCESS
        bb.hr_governance_report = {
            "error": "no_payload_received",
            "safe_actions_applied": [],
            "advice_pending": [],
        }
        return Status.FAILURE

    def on_resume(self, bb, payload: Any) -> None:
        parsed = _loop().parse_response(_extract_text(payload))
        report = parsed.get("hr_governance_report")
        if report is None and parsed.get("error"):
            report = {
                "error": parsed["error"],
                "safe_actions_applied": [],
                "advice_pending": [],
            }
        bb.hr_governance_report = report or {
            "safe_actions_applied": [],
            "advice_pending": [],
        }
        bb.pending_dispatch = None


def _extract_text(payload: Any) -> Any:
    if isinstance(payload, dict) and "output" in payload:
        return payload.get("output") or ""
    return payload
