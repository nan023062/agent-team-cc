"""actions/mode_classify.py — classify user_request → bb.mode ∈ {conversation, execution}.

Two-mode policy (v3, replaces v2's 7-class IntentAnalyze):
  1. Rule path — keyword/pattern table. Deterministic; no LLM call.
     Hit "conversation"-shaped requests (questions, look-ups, greetings) →
     bb.mode = "conversation"; everything else defaults to "execution".
  2. LLM path — only on rule MISS where the LLM is wired. NullLLM returns
     "execution" as a safe default; never raises.

Empty / whitespace-only request → "conversation" so DirectReply can ship
a friendly "please describe what you want" message instead of blowing up
the execution pipeline.

NEVER fails (returns SUCCESS always). The mode is a routing decision, not
an error condition.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.node import Node, Status
from .llm_hook import NullLLM


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
    # conversation pattern incidentally matches.
    re.compile(r"\b(implement|add|fix|refactor|build|wire|create|design|split|merge|deprecate|"
               r"recruit|hire|train|onboard|fire|assess|review|audit|update|delete|remove)\b",
               re.IGNORECASE),
    re.compile(r"(实现|新增|修复|重构|加(一?个|入)|创建|设计|拆分|合并|废弃|招募|培训|考核|审查|审核|复核|评审|更新|删除|改写|重写)"),
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

        # Strong execution verbs win unconditionally.
        for pat in _EXECUTION_PATTERNS:
            if pat.search(text):
                bb.mode = "execution"
                return Status.SUCCESS

        # Conversation-shaped phrasing.
        for pat in _CONVERSATION_PATTERNS:
            if pat.search(text):
                bb.mode = "conversation"
                return Status.SUCCESS

        # Rule miss — defer to LLM (NullLLM returns "execution").
        try:
            verdict = self._llm.classify_mode(text)
        except Exception:
            verdict = "execution"
        if verdict not in ("conversation", "execution"):
            verdict = "execution"
        bb.mode = verdict
        return Status.SUCCESS
