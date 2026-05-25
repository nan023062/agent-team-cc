"""actions/collect_advice.py — post-yield collectors for Architect / HR reports.

Two thin nodes that own on_resume() for their respective DispatchXxx peer.
The Runner's resume path lands here (per dream/api/result.DREAM_AGENT_TYPE_TO_LEAF
mapping); we parse the payload into a structured advice dict and store it on
the right bb field.

Tick semantics: on the FIRST tick of a step before any dispatch, the report
field is None — return SUCCESS no-op (the dispatch sibling is what RUNs).
After resume the report is set, again SUCCESS.

FAILURE only when the dispatch flag was set (we ARE post-yield) but the
report is malformed beyond recognition.
"""

from __future__ import annotations

from typing import Any

from engine.core.node import Node, Status


class CollectArchAdvice(Node):
    def __init__(self, *, name: str = "CollectArchAdvice") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        # The dispatch sibling sets arch_governance_dispatched=True and yields;
        # on resume we run again — if the report exists we're done.
        if bb.arch_governance_report is not None:
            return Status.SUCCESS
        # If we never dispatched, nothing to collect — SUCCESS no-op.
        if not bb.arch_governance_dispatched:
            return Status.SUCCESS
        # Dispatched but no report on bb yet — means on_resume wasn't called
        # (engine-internal failure). Surface as FAILURE.
        bb.arch_governance_report = {
            "error": "no_payload_received",
            "safe_actions_applied": [],
            "advice_pending": [],
        }
        return Status.FAILURE

    def on_resume(self, bb, payload: Any) -> None:
        bb.arch_governance_report = _parse_advice_report(payload)
        bb.pending_dispatch = None


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
        bb.hr_governance_report = _parse_advice_report(payload)
        bb.pending_dispatch = None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_advice_report(payload: Any) -> dict:
    """Convert a Task-tool return into {safe_actions_applied, advice_pending}.

    Accepts:
      - dict with the expected keys (passed through after coercion)
      - str containing the YAML-ish block shown in the dispatch prompt
      - anything else → wrap as a single advice_pending line
    """
    if isinstance(payload, dict):
        return {
            "safe_actions_applied": _as_str_list(payload.get("safe_actions_applied")),
            "advice_pending": _as_str_list(payload.get("advice_pending")),
            "raw": payload.get("raw"),
        }
    text = payload if isinstance(payload, str) else str(payload)
    safe: list[str] = []
    pending: list[str] = []
    current: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("safe_actions_applied"):
            current = safe
            continue
        if stripped.startswith("advice_pending"):
            current = pending
            continue
        if not stripped:
            continue
        if stripped.startswith("- ") and current is not None:
            current.append(stripped[2:].strip())
    return {
        "safe_actions_applied": safe,
        "advice_pending": pending,
        "raw": text[:4000],
    }


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]
