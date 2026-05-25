"""tests/stub_llm.py — in-process LLM stubs used by L3 / L4 tests.

Post-t6 the architect / HR execution sub-loops are real BT subtrees that
call ``llm.run(prompt)`` at every stage. Tests that want to drive a full
execution tick to the DispatchWork yield need a stub that recognizes each
stage from prompt text and returns a structurally valid reply.
"""
from __future__ import annotations

import json


class StubArchHrLLM:
    """Returns scripted JSON for every arch_exec / hr_exec leaf.

    Hard-codes ``task_id="a1"`` (configurable) in the produced arch_plan so
    DispatchWork yields one work-agent dispatch per tick.
    """

    def __init__(self, *, task_id: str = "a1") -> None:
        self._task_id = task_id

    # v3 protocol methods (used by ModeClassify / DirectReply).
    def classify_mode(self, user_request: str) -> str:
        return "execution"

    def reply_conversation(self, user_request: str) -> str:
        return f"(conversation) {user_request}"

    def run(self, prompt: str) -> str:
        tid = self._task_id
        # arch_exec stages
        if "Architect 执行子循环 · Scan" in prompt:
            return json.dumps({
                "intent": "stub intent",
                "modules": ["src/stub"],
                "notes": "",
            })
        if "Architect 执行子循环 · StateCheck" in prompt:
            return json.dumps({"state": "in_sync", "reason": "stub"})
        if "Architect 执行子循环 · Extract" in prompt:
            return json.dumps({
                "modules": [{"path": "src/stub", "constraints": []}],
            })
        if "Architect 执行子循环 · Map" in prompt:
            return json.dumps({
                "plan_draft": [{
                    "id": tid,
                    "description": "stub task",
                    "required_capability": "programmer",
                    "params": {},
                    "arch_context": "stub-ctx",
                }],
            })
        if "Architect 执行子循环 · Assemble" in prompt:
            return json.dumps({
                "arch_plan": [{
                    "id": tid,
                    "description": "stub task",
                    "required_capability": "programmer",
                    "params": {},
                    "arch_context": "stub-ctx",
                }],
            })
        # hr_exec stages
        if "HR 执行子循环 · Match" in prompt:
            return json.dumps({
                "kind": "fit",
                "agent_file": ".claude/agents/programmer/programmer.md",
                "note": "stub fit",
            })
        # Benign fallback so unforeseen prompts never parse-fail into FAILURE.
        return json.dumps({"result": None})
