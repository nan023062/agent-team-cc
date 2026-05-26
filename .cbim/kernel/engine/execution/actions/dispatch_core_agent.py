"""actions/dispatch_core_agent.py — single-yield leaf for core-agent dispatch.

Used by the three core-agent branches of the execution root
(architect / hr / audit modes). Each branch instantiates one
``DispatchCoreAgent(agent_type=...)`` and gets:

  - first tick → fills ``bb.pending_dispatch`` with a DispatchRequest whose
    ``agent_type`` and ``agent_file`` come from ``CORE_AGENT_FILES``, then
    returns RUNNING (Runner yields to main agent's Task tool).
  - resume → stores the dispatch payload under ``bb.work_results[<key>]``
    using a stable key derived from ``agent_type`` so on a re-tick the
    presence of the result short-circuits to SUCCESS.

State rule (iron): no field on ``self`` survives across ticks; the leaf
derives everything from ``bb`` each tick. The reference pattern is
``WorkAgentLeaf`` (actions/dispatch_work.py).

Result-key scheme: ``core:<agent_type>`` — namespaced so a Work Agent
result with the same string would never collide.

bb schema: reuses the existing ``work_results`` dict; no new bb field.
"""

from __future__ import annotations

from engine.core.node import Node, Status

from .core_agents import CORE_AGENT_FILES
from ..api.result import DispatchRequest


def _result_key(agent_type: str) -> str:
    return f"core:{agent_type}"


class DispatchCoreAgent(Node):
    """Yield once to dispatch a core agent (architect / hr / auditor).

    Parameters
    ----------
    agent_type :
        One of the keys in ``CORE_AGENT_FILES`` (``"architect"``,
        ``"hr"``, ``"auditor"``). Drives both the DispatchRequest field
        and the result-key under ``bb.work_results``.
    agent_file :
        Optional override. Defaults to ``CORE_AGENT_FILES[agent_type]``.
    name :
        Node name (used by Runner trace + resume path). Defaults to
        ``f"DispatchCoreAgent#{agent_type}"`` so each branch produces a
        distinct path segment.
    """

    def __init__(
        self,
        *,
        agent_type: str,
        agent_file: str | None = None,
        name: str | None = None,
    ) -> None:
        if agent_type not in CORE_AGENT_FILES:
            raise ValueError(
                f"DispatchCoreAgent: unknown agent_type {agent_type!r}; "
                f"expected one of {sorted(CORE_AGENT_FILES)}"
            )
        self.agent_type = agent_type
        self.agent_file = agent_file or CORE_AGENT_FILES[agent_type]
        self.name = name or f"DispatchCoreAgent#{agent_type}"

    def tick(self, bb) -> Status:
        key = _result_key(self.agent_type)
        result = (bb.work_results or {}).get(key)
        if result is not None:
            status = result.get("status") if isinstance(result, dict) else None
            if status == "ok":
                return Status.SUCCESS
            return Status.FAILURE

        bb.pending_dispatch = DispatchRequest(
            agent_type=self.agent_type,
            agent_file=self.agent_file,
            prompt=self._compose_prompt(bb),
            subtask_id=key,
            timeout_hint_s=None,
        )
        return Status.RUNNING

    def on_resume(self, bb, payload) -> None:
        text = payload if isinstance(payload, str) else (
            payload.get("output", "") if isinstance(payload, dict) else str(payload)
        )
        key = _result_key(self.agent_type)
        new_results = dict(bb.work_results or {})
        new_results[key] = {
            "status": "ok",
            "output": text,
            "raw": payload if not isinstance(payload, str) else None,
        }
        bb.work_results = new_results
        bb.pending_dispatch = None

    def _compose_prompt(self, bb) -> str:
        # Core-agent prompt is just the user's original request — these
        # agents read the workspace and decide their own next steps.
        # ModeClassify already routed mode=<agent_type>, so the receiving
        # agent knows why it was called from its system prompt.
        return (bb.user_request or "").strip()
