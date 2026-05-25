"""actions/mode_classify.py — classify user_request → bb.mode.

Five-mode policy (v3.7 — tighten core-agent patterns, prioritize execution verbs):
  1. Rule path — keyword/pattern tables. Deterministic; no LLM call.
     - architect-preempt (split/merge/deprecate a module, update .dna) → architect
     - execution verbs (implement/add/fix/refactor/build/…)            → execution
     - explicit architect request (design a module / ask architect …) → architect
     - explicit hr request (recruit X agent / ask HR …)                → hr
     - explicit auditor request (audit X / ask auditor / code review)  → audit
     - questions / lookups / greetings                                 → conversation
     - everything else (default)                                       → execution
  2. LLM path — only on rule MISS where the LLM is wired. NullLLM returns
     "execution" as a safe default; never raises.

Empty / whitespace-only request → "conversation" so DirectReply ships a
friendly "please describe what you want" message instead of blowing up
the execution pipeline.

Precedence on rule conflict (v3.7):
  architect-preempt > execution-verb > architect-request > hr-request >
  audit-request > conversation > LLM fallback.

The v3.5/v3.6 ordering (`architect > hr > audit > execution-verb`) used
bare topic keywords ("architecture" / "audit" / "module.md" / "recruit")
that hijacked execution requests like "implement audit logging" or
"refactor the architecture module". v3.7 flips precedence so the
execution verb wins by default, and restricts the three core-agent
tables to explicit dispatch phrasing — either naming the role
(ask/let/dispatch/找/让 + architect/HR/auditor) or pairing a meta-task
verb with that role's exclusive deliverable (design a module, draw the
architecture, recruit an agent, audit X, do a code review …).

The single exception is the architect-preempt layer, which fires
BEFORE execution verbs for "split/merge/deprecate a module" and
"update .dna" — these have no execution landing (their real output is
.dna edits, not source-code edits) and are unambiguously architect work.

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


# ---------------------------------------------------------------------------
# Pre-emption layer — architect-only actions that semantically cannot be
# "code execution". Runs BEFORE the execution-verb table.
# ---------------------------------------------------------------------------

_ARCHITECT_PREEMPT_PATTERNS = [
    # Chinese: 拆分 / 合并 / 废弃 / 下架 模块
    re.compile(r"(拆分|拆|合并|废弃|下架)\s*[一个]?\s*\S*\s*模块"),
    # Chinese: 更新 / 修订 / 重写 / 调整 .dna
    re.compile(r"(更新|修订|重写|调整)\s*\.?dna"),
    re.compile(r"更新\s*(module|contract)\.md", re.IGNORECASE),
    # English: split/merge/deprecate (a) module
    re.compile(
        r"\b(split|merge|deprecate|retire|archive)\s+(an?\s+|the\s+)?\w*\s*module\b",
        re.IGNORECASE,
    ),
    # English: update/edit/touch .dna (and friends)
    re.compile(
        r"\b(update|edit|modify|touch|fix|amend|rewrite)\s+(the\s+)?"
        r"(\.dna|module\.md|contract\.md|dna\s+(doc|entry|record|module))\b",
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Execution verbs — broad action verbs that signal "code is going to move".
# ---------------------------------------------------------------------------

_EXECUTION_PATTERNS = [
    re.compile(
        r"\b(implement|add|fix|refactor|build|wire|create|split|merge|deprecate|"
        r"update|delete|remove)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(实现|新增|修复|重构|加(一?个|入)|创建|拆分|合并|废弃|更新|删除|改写|重写)"
    ),
]


# ---------------------------------------------------------------------------
# Architect request — explicit dispatch to the architect role. Requires
# either naming the architect + a dispatch verb, OR pairing an architect-
# specific meta-task verb with an architect-exclusive deliverable. Bare
# topic words (architecture / module.md / contract.md) DO NOT trigger.
# ---------------------------------------------------------------------------

_ARCHITECT_PATTERNS = [
    # (a1) English: dispatch verb + architect
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?architect\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让 / 请 / 找 / 问 / 叫 / 派给 / 交给 架构师
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*架构师"),
    # (b1) English: design + architect-exclusive deliverable
    # Allows up to 4 modifier words between "design [a/the/new]" and the
    # deliverable noun, so "design a new login module" still matches.
    re.compile(
        r"\bdesign\s+(an?\s+|the\s+)?(new\s+)?(\w+\s+){0,4}"
        r"(module|sub-?module|system|component|service|API|architecture|"
        r"blueprint|contract|interface|boundary|layer)\b",
        re.IGNORECASE,
    ),
    # (b2) English: draw / sketch / propose / outline / re-architect + architecture-like noun
    re.compile(
        r"\b(draw|sketch|propose|outline|re-?architect|redesign)\s+"
        r"(an?\s+|the\s+)?(architecture|blueprint|design|module\s+shape|"
        r"module\s+boundary|component\s+diagram)\b",
        re.IGNORECASE,
    ),
    # (b3) English: define a contract / module boundary
    re.compile(
        r"\bdefine\s+(an?\s+|the\s+)?(contract|interface|module\s+boundary|"
        r"sub-?module\s+boundaries)\b",
        re.IGNORECASE,
    ),
    # (b4) English: produce / write / prepare / build / generate a knowledge pack / context pack
    re.compile(
        r"\b(produce|write|prepare|build|generate)\s+(an?\s+|the\s+)?"
        r"(knowledge\s+pack|context\s*pack)\b",
        re.IGNORECASE,
    ),
    # (b5) Chinese: architect meta-task verbs + deliverable nouns
    re.compile(
        r"(画|出|做|提供|写|准备|生成)\s*(一?份|一?张|一?套)?\s*"
        r"(设计|蓝图|架构|知识包|context\s*pack|模块划分|模块边界|契约设计)"
    ),
    # (b6) Chinese: 模块化 / 重构架构 / 拆分模块 / 合并模块 / 定义契约 / 架构设计
    re.compile(r"(模块化|重构架构|拆分模块|合并模块|定义契约|架构设计)"),
]


# ---------------------------------------------------------------------------
# HR request — explicit dispatch to HR. Either naming HR + a dispatch verb,
# OR pairing a lifecycle verb (recruit / hire / onboard / train / …) with
# an explicit "agent" object.
# ---------------------------------------------------------------------------

_HR_PATTERNS = [
    # (a1) English: dispatch verb + HR
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?hr\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让 / 请 / 找 / 问 / 叫 / 派给 / 交给 HR
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*HR", re.IGNORECASE),
    # (b1) English: recruit / hire / onboard / … + agent
    # Allows up to 4 modifier words between the verb and "agent" so
    # "recruit a python backend engineer agent" still matches.
    re.compile(
        r"\b(recruit|hire|onboard|train|coach|mentor|assess|evaluate|fire|"
        r"retire|promote)\s+(an?\s+|the\s+)?(\w+\s+){0,4}(work\s+)?agent\b",
        re.IGNORECASE,
    ),
    # (b2) Chinese: 招 / 聘 / 上岗 / 培训 / 带教 / 考核 / 裁撤 / 晋升 + agent
    # Allows up to 20 chars of any modifier text (incl. embedded Latin
    # words like "Rust") between the verb and "agent" so phrases like
    # "招一个会写 Rust 的工作 agent" still match. Non-greedy keeps the
    # window tight to the nearest "agent".
    re.compile(
        r"(招募|招聘|招(一?个)?|聘请|入职|上岗|培训|带教|考核|评估|"
        r"裁撤|晋升|下岗).{0,20}?(work\s*)?agent",
        re.IGNORECASE,
    ),
    # (b3) Chinese: 能力管理 / 人员管理 / 岗位调整 / 招聘 agent / 入职 agent
    re.compile(r"(能力管理|人员管理|岗位调整|招聘\s*agent|入职\s*agent)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Audit request — explicit dispatch to the auditor. Either naming the
# auditor + a dispatch verb, OR a verb-form audit/review request (audit
# X, do a code review, run a design review). Bare topic noun "audit" no
# longer triggers — "implement audit logging" must NOT route to audit.
# ---------------------------------------------------------------------------

_AUDIT_PATTERNS = [
    # (a1) English: dispatch verb + auditor
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?auditor\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让 / 请 / 找 / 问 / 叫 / 派给 / 交给 审计员
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*审计员"),
    # (b1) English: independent review / second opinion / sanity / governance check
    re.compile(
        r"\b(independent\s+(review|audit|critique)|second\s+opinion|"
        r"sanity\s+check|governance\s+check|gov\s+check)\b",
        re.IGNORECASE,
    ),
    # (b2) English: audit as verb — line-initial or after a polite/request lead-in
    re.compile(
        r"(^|\b(please|kindly|could you|can you|let'?s|let us)\s+)"
        r"audit\s+(the\s+|this\s+|our\s+|my\s+)?\w+",
        re.IGNORECASE,
    ),
    # (b3) English: do / run / perform / conduct / kick off a code/design/architecture review or audit
    re.compile(
        r"\b(do|run|perform|conduct|kick\s*off)\s+(an?\s+|the\s+)?"
        r"(code\s*review|design\s*review|architecture\s*review|audit)\b",
        re.IGNORECASE,
    ),
    # (b4) Chinese: 独立审查 / 复盘 / 挑刺 / 质疑 / code review
    re.compile(
        r"(审计|独立审查|独立审核|独立复核|独立评审|"
        r"复盘|挑刺|找问题|质疑|提出反对意见|做\s*code\s*review)"
    ),
]


# ---------------------------------------------------------------------------
# Conversation — questions / lookups / greetings (unchanged from v3.5).
# ---------------------------------------------------------------------------

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


class ModeClassify(Node):
    def __init__(self, *, llm: Any = None, name: str = "ModeClassify") -> None:
        self.name = name
        self._llm = llm or NullLLM()

    def tick(self, bb) -> Status:
        text = (bb.user_request or "").strip()
        if not text:
            bb.mode = "conversation"
            return Status.SUCCESS

        # v3.7 precedence:
        #   architect-preempt > execution-verb > architect-request >
        #   hr-request > audit-request > conversation > LLM fallback.

        # 1. Architect preempt — split/merge/deprecate a module, update .dna.
        for pat in _ARCHITECT_PREEMPT_PATTERNS:
            if pat.search(text):
                bb.mode = "architect"
                return Status.SUCCESS

        # 2. Execution verbs — the broad default for "code is going to move".
        for pat in _EXECUTION_PATTERNS:
            if pat.search(text):
                bb.mode = "execution"
                return Status.SUCCESS

        # 3. Explicit architect request.
        for pat in _ARCHITECT_PATTERNS:
            if pat.search(text):
                bb.mode = "architect"
                return Status.SUCCESS

        # 4. Explicit HR request.
        for pat in _HR_PATTERNS:
            if pat.search(text):
                bb.mode = "hr"
                return Status.SUCCESS

        # 5. Explicit auditor request.
        for pat in _AUDIT_PATTERNS:
            if pat.search(text):
                bb.mode = "audit"
                return Status.SUCCESS

        # 6. Conversation-shaped phrasing.
        for pat in _CONVERSATION_PATTERNS:
            if pat.search(text):
                bb.mode = "conversation"
                return Status.SUCCESS

        # 7. Rule miss — defer to LLM (NullLLM returns DEFAULT_MODE).
        try:
            verdict = self._llm.classify_mode(text)
        except Exception:
            verdict = DEFAULT_MODE
        if verdict not in MODES:
            verdict = DEFAULT_MODE
        bb.mode = verdict
        return Status.SUCCESS
