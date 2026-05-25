"""api/result.py — public dataclasses for the dream loop.

Stability surface per .dna/contract.md:
  - 4 kind strings on DreamResult: "done" / "yield" / "error" / "skipped"
  - DreamRunSummary.status restricted to
    {"running", "done", "failed", "abandoned"}
  - Skipped.reason restricted to
    {"within_window", "another_run_in_progress", "recent_failure_cooldown"}
  - DispatchRequest.agent_type restricted to {"architect", "hr"} per
    governance contract (the dream loop never dispatches work / auditor)

The governance loop yields for the Architect / HR governance sub-loops
via the dispatch leaves under ``engine.dream.actions.dispatch_*``. The
Runner uses ``DREAM_AGENT_TYPE_TO_LEAF`` to resolve the on_resume target
leaf name from ``pending_dispatch.agent_type``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Maps ``pending_dispatch.agent_type`` to the leaf-node name the Runner's
# resume path should land on. Names must match the ``name`` attribute set
# in the dispatch leaves' constructors (see ``DispatchArchGovern`` /
# ``DispatchHRGovern``). The Runner finds the path-by-name and then
# delivers ``dispatch_result`` via ``on_resume`` on the matching node;
# but the on_resume implementation lives on the **paired Collect** sibling
# inside the same Sequence — see ``collect_arch_advice`` /
# ``collect_hr_advice``. We register the Collect leaf names here so the
# resume target lands on the node that knows how to parse the payload.
DREAM_AGENT_TYPE_TO_LEAF: dict[str, str] = {
    "architect": "CollectArchAdvice",
    "hr":        "CollectHRAdvice",
}


# ---------------------------------------------------------------------------
# DispatchRequest
# ---------------------------------------------------------------------------

@dataclass
class DispatchRequest:
    """Returned inside DreamResult.Yield to describe a Task-tool dispatch.

    Governance-context value constraints (per .dna/contract.md):
      - ``agent_type`` ∈ {"architect", "hr"} (no work / no auditor)
      - ``subtask_id`` ∈ {"governance_knowledge", "governance_capability"}
      - ``prompt`` must start with ``## 治理模式`` (or equivalent governance
        marker) so the receiving agent enters governance mode rather than
        executing a user task.
    """

    agent_type: str
    agent_file: str | None
    prompt: str
    subtask_id: str | None = None
    timeout_hint_s: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "DispatchRequest | None":
        if d is None:
            return None
        return cls(
            agent_type=d.get("agent_type", "architect"),
            agent_file=d.get("agent_file"),
            prompt=d.get("prompt", ""),
            subtask_id=d.get("subtask_id"),
            timeout_hint_s=d.get("timeout_hint_s"),
        )


# ---------------------------------------------------------------------------
# DreamResult — four-state union
# ---------------------------------------------------------------------------

@dataclass
class DreamResult:
    """Public four-state union returned by dream_tick / dream_tick_resume.

    kind ∈ {"done", "yield", "error", "skipped"}.
    """

    kind: str

    # kind == "done"
    summary: str | None = None
    report_path: str | None = None

    # kind == "yield"
    run_id: str | None = None
    dispatch_request: DispatchRequest | None = None

    # kind == "error"
    error_code: str | None = None
    error_message: str | None = None

    # kind == "skipped"
    reason: str | None = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"kind": self.kind}
        if self.kind == "done":
            out["summary"] = self.summary or ""
            out["report_path"] = self.report_path
        elif self.kind == "yield":
            out["run_id"] = self.run_id
            out["dispatch_request"] = (
                self.dispatch_request.to_dict() if self.dispatch_request else None
            )
        elif self.kind == "error":
            out["error_code"] = self.error_code or "engine_internal"
            out["error_message"] = self.error_message or ""
            if self.report_path:
                out["report_path"] = self.report_path
        elif self.kind == "skipped":
            out["reason"] = self.reason or ""
        return out


# ---------------------------------------------------------------------------
# DreamRunSummary (dream_list_runs)
# ---------------------------------------------------------------------------

@dataclass
class DreamRunSummary:
    run_id: str
    trigger_reason: str
    status: str  # running | done | failed | abandoned
    started_at: str
    finished_at: str | None
    step_results: dict = field(default_factory=dict)
    report_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# AbortResult (dream_abort)
# ---------------------------------------------------------------------------

@dataclass
class AbortResult:
    aborted: bool
    run_id: str
    reason: str
    abandoned_at: str

    def to_dict(self) -> dict:
        return asdict(self)
