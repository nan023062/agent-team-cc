"""actions/mode_classify.py — classify user_request → bb.mode.

Five-mode policy (v3.5 — extends the v3 two-mode):
  1. Rule path — keyword/pattern tables. Deterministic; no LLM call.
     - design / blueprint / module-shape requests → bb.mode = "architect"
     - agent recruitment / training / assessment   → bb.mode = "hr"
     - independent review / audit                  → bb.mode = "audit"
     - questions / lookups / greetings             → bb.mode = "conversation"
     - everything else (execution verbs, default)  → bb.mode = "execution"
  2. LLM path — only on rule MISS where the LLM is wired. NullLLM returns
     "execution" as a safe default; never raises.

Empty / whitespace-only request → "conversation" so DirectReply ships a
friendly "please describe what you want" message instead of blowing up
the execution pipeline.

Precedence on rule conflict: architect > hr > audit > execution-verb >
conversation. The three core-agent signals win over generic execution
verbs because "design a new module" and "implement a new module" both
contain execution verbs but only the former should reach Architect
directly.

NEVER fails (returns SUCCESS always). The mode is a routing decision, not
an error condition.
"""

from __future__ import annotations

import re
from typing import Any

from engine.core.node import Node, Status
from .llm_hook import NullLLM


# The 5 mode strings returned by classify_mode (and written to bb.mode).
MODES: tuple[str, ...] = ("conversation", "architect", "hr", "audit", "execution")
DEFAULT_MODE = "execution"


_ARCHITECT_PATTERNS = [
    # English design / blueprint phrasing
    re.compile(
        r"\b(design|blueprint|architect|architecture|module\s+shape|"
        r"redesign|re-?architect|propose\s+a\s+design|sketch\s+a\s+design|"
        r"knowledge\s+pack|context\s*pack|\.dna|module\.md|contract\.md)\b",
        re.IGNORECASE,
    ),
    # Chinese design / blueprint phrasing
    re.compile(
        r"(设计|架构|蓝图|知识包|画一下|出一份设计|拆分模块|"
        r"模块边界|模块化|重构架构|定义契约|契约设计)"
    ),
]

_HR_PATTERNS = [
    # English recruitment / training / assessment phrasing
    re.compile(
        r"\b(recruit|hire|onboard|train|coach|mentor|assess|evaluate|fire|"
        r"retire|promote|agent\s+(recruit|hire|onboard|train|gap)|"
        r"work\s*agent|workforce)\b",
        re.IGNORECASE,
    ),
    # Chinese recruitment / training / assessment phrasing
    re.compile(
        r"(招募|招聘|入职|培训|带教|考核|评估|裁撤|晋升|"
        r"工作\s*agent|人员管理|能力管理|岗位|招一个|招个)"
    ),
]

_AUDIT_PATTERNS = [
    # English audit / independent review phrasing
    re.compile(
        r"\b(audit|independent\s+review|critique|second\s+opinion|"
        r"sanity\s+check|code\s+review|design\s+review|gov(ernance)?\s+check)\b",
        re.IGNORECASE,
    ),
    # Chinese audit / independent review phrasing
    re.compile(
        r"(审计|独立审查|独立审核|独立复核|独立评审|"
        r"复盘|挑刺|找问题|质疑|提出反对意见|做\s*code\s*review)"
    ),
]

_CONVERSATION_PATTERNS = [
    # English question / lookup / greeting phrasing
    re.compile(r"^\s*(what|who|when|where|why|how|which|is|are|do|does|can|could|should|would)\b",
               re.IGNORECASE),
    re.compile(r"\b(explain|describe|tell me|show me|status|recall|history|hi|hello|hey|thanks)\b",
               re.IGNORECASE),
    # Chinese question / lookup / greeting phrasing
    re.compile(r"(什么|为什么|怎么|如何|哪|是不是|有没有|可不可以|能不能|是否|多少|多久)"),
    re.compile(r"(查询|查一下|查看|看一下|介绍一下|说明|解释|状态|你好|您好|谢谢)"),
]

_EXECUTION_PATTERNS = [
    # Strong action verbs — short-circuit to execution even if a
    # conversation pattern incidentally matches. (Architect / HR / Audit
    # patterns are tested BEFORE these and win when matched.)
    re.compile(r"\b(implement|add|fix|refactor|build|wire|create|split|merge|deprecate|"
               r"update|delete|remove)\b",
               re.IGNORECASE),
    re.compile(r"(实现|新增|修复|重构|加(一?个|入)|创建|拆分|合并|废弃|更新|删除|改写|重写)"),
]


class ModeClassify(Node):
    def __init__(self, *, llm: Any = None, name: str = "ModeClassify") -> None:
        self.name = name
        self._llm = llm or NullLLM()

    def tick(self, bb) -> Status:
        text = (bb.user_request or "").strip()
        if not text:
            bb.mode = "conversation"
            return Status.SUCCESS

        # Precedence: architect > hr > audit > execution-verb > conversation.
        # The three core-agent signals must beat the generic execution
        # verbs ("design" / "recruit" / "audit" all contain or imply
        # action verbs, but each routes to its own dedicated agent).
        for pat in _ARCHITECT_PATTERNS:
            if pat.search(text):
                bb.mode = "architect"
                return Status.SUCCESS
        for pat in _HR_PATTERNS:
            if pat.search(text):
                bb.mode = "hr"
                return Status.SUCCESS
        for pat in _AUDIT_PATTERNS:
            if pat.search(text):
                bb.mode = "audit"
                return Status.SUCCESS

        # Generic execution verbs.
        for pat in _EXECUTION_PATTERNS:
            if pat.search(text):
                bb.mode = "execution"
                return Status.SUCCESS

        # Conversation-shaped phrasing.
        for pat in _CONVERSATION_PATTERNS:
            if pat.search(text):
                bb.mode = "conversation"
                return Status.SUCCESS

        # Rule miss — defer to LLM (NullLLM returns DEFAULT_MODE).
        try:
            verdict = self._llm.classify_mode(text)
        except Exception:
            verdict = DEFAULT_MODE
        if verdict not in MODES:
            verdict = DEFAULT_MODE
        bb.mode = verdict
        return Status.SUCCESS
