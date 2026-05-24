"""actions/intent_analyze.py — classify user_request → bb.intent.

Two-path policy:
  1. Rule path — IntentRules (keyword table extracted from cbi/skills/dispatch
     classification table) matches first. Deterministic; no LLM call.
  2. LLM path — only on rule miss. If no LLM is wired (NullLLM), set
     interrupt_reason and FAILURE; the parent Retry will catch and the
     coordinator will see an error result.

IntentRules.from_dispatch_skill() reads the static `SKILL` string and
parses the Classification Examples table; rule changes therefore live in
the skill file (single source of truth).
"""

from __future__ import annotations

import re
from typing import Any

from ..core.node import Node, Status


INTENT_KINDS = ("business_crud", "capability_crud", "execution", "review",
                "pure_query", "non_requirement", "ambiguous")


# ---------------------------------------------------------------------------
# LLM hooks
# ---------------------------------------------------------------------------

class NullLLM:
    """Default LLM hook for 4A+4B — every call raises NotImplementedError.

    Tests that want a stub pass StubLLM to the action constructor.
    """

    def classify(self, user_request: str, schema: dict) -> dict:
        raise NotImplementedError("LLM not wired in 4A/4B; rule path required")

    def decompose(self, user_request: str, intent: dict, prior_results: dict) -> list[dict]:
        raise NotImplementedError("LLM not wired in 4A/4B; rule path required")

    def judge_converge(self, bb_summary: dict) -> dict:
        raise NotImplementedError("LLM not wired in 4A/4B; rule path required")


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------

class _RuleHit:
    __slots__ = ("kind", "target_agent", "clarification_needed", "clarifying_question")

    def __init__(self, *, kind: str, target_agent: str | None = None,
                 clarification_needed: bool = False,
                 clarifying_question: str = "") -> None:
        self.kind = kind
        self.target_agent = target_agent
        self.clarification_needed = clarification_needed
        self.clarifying_question = clarifying_question

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target_agent": self.target_agent,
            "clarification_needed": self.clarification_needed,
            "clarifying_question": self.clarifying_question,
        }


class IntentRules:
    """Keyword-based intent classifier.

    Each rule is a (regex, kind, target_agent) triple. The first matching
    regex wins. Patterns are case-insensitive and matched on the full
    user_request (re.search, not match).
    """

    def __init__(self, rules: list[tuple[str, str, str | None]]) -> None:
        self._rules = [(re.compile(p, re.IGNORECASE), k, t) for p, k, t in rules]

    def match(self, user_request: str) -> _RuleHit | None:
        if not user_request or not user_request.strip():
            return _RuleHit(
                kind="ambiguous",
                clarification_needed=True,
                clarifying_question="Empty request — please describe what you want.",
            )
        for pat, kind, target in self._rules:
            if pat.search(user_request):
                return _RuleHit(kind=kind, target_agent=target)
        return None

    @classmethod
    def default(cls) -> "IntentRules":
        # Derived from cbi/skills/dispatch Classification Examples + Table.
        # Order matters: more specific first.
        rules: list[tuple[str, str, str | None]] = [
            # Review (auditor)
            (r"\breview\b|\baudit\b|审[查核]|复核|评审", "review", "auditor"),
            # Capability layer (HR)
            (r"\b(recruit|hire|train|onboard|fire|assess)\s+.*\b(agent|engineer)\b",
             "capability_crud", "hr"),
            (r"招募|培训|考核.*(agent|工程师|代理)", "capability_crud", "hr"),
            # Pure query / look-up
            (r"^\s*(look\s*up|查询|查一下|查看|recall|history)\b", "pure_query", "architect"),
            (r"decision\s+history|历史决策", "pure_query", "architect"),
            # Execution (code)
            (r"\b(implement|add|fix|refactor|build|wire)\b.+\b(api|module|feature|bug|crash|handler|test|hook)\b",
             "execution", "programmer"),
            (r"实现|新增|修复|重构|加(一?个|入)", "execution", "programmer"),
            # Business layer (architect)
            (r"\b(create|design|split|merge|deprecate)\s+.*\bmodule\b",
             "business_crud", "architect"),
            (r"(创建|设计|拆分|合并|废弃).*(模块|module)", "business_crud", "architect"),
            (r"\b\.dna/|knowledge\s+blueprint", "business_crud", "architect"),
        ]
        return cls(rules)

    @classmethod
    def from_dispatch_skill(cls) -> "IntentRules":
        # 4B: skill file is the source of truth, but parsing the markdown
        # table at every tick is wasteful and brittle. Default() embeds
        # the same examples — keep them in sync via the skill's NOTE
        # section and the L2 test_root_structure_matches_design.
        return cls.default()


# ---------------------------------------------------------------------------
# IntentAnalyze Action
# ---------------------------------------------------------------------------

INTENT_SCHEMA = {
    "kind": "one of " + " | ".join(INTENT_KINDS),
    "target_agent": "string | null",
    "clarification_needed": "bool",
    "clarifying_question": "string (only when clarification_needed)",
}


class IntentAnalyze(Node):
    def __init__(self, *, rules: IntentRules | None = None,
                 llm: Any = None, name: str = "IntentAnalyze") -> None:
        self.name = name
        self._rules = rules or IntentRules.default()
        self._llm = llm or NullLLM()

    def tick(self, bb) -> Status:
        user_request = bb.user_request or ""
        rule_hit = self._rules.match(user_request)
        if rule_hit is not None:
            bb.intent = rule_hit.to_dict()
            return Status.SUCCESS
        try:
            payload = self._llm.classify(user_request, schema=INTENT_SCHEMA)
        except NotImplementedError:
            bb.interrupt_reason = "llm_fallback_required_but_unavailable"
            return Status.FAILURE
        # Normalize LLM payload to the canonical dict shape.
        bb.intent = {
            "kind": payload.get("kind", "ambiguous"),
            "target_agent": payload.get("target_agent"),
            "clarification_needed": bool(payload.get("clarification_needed")),
            "clarifying_question": payload.get("clarifying_question", ""),
        }
        return Status.SUCCESS
