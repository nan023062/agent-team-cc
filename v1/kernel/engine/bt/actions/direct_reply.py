"""actions/direct_reply.py — conversation-mode fast path.

Writes a coordinator-level reply directly into bb.final_response without
yielding to any agent. Used when ModeClassify routes bb.mode="conversation".

LLM hook: optional. NullLLM returns a passthrough placeholder; a real LLM
generates a coherent reply. Never yields, never fails.
"""

from __future__ import annotations

from typing import Any

from ..core.node import Node, Status
from .llm_hook import NullLLM


class DirectReply(Node):
    def __init__(self, *, llm: Any = None, name: str = "DirectReply") -> None:
        self.name = name
        self._llm = llm or NullLLM()

    def tick(self, bb) -> Status:
        text = (bb.user_request or "").strip()
        if not text:
            bb.final_response = "请描述你的需求。"
            return Status.SUCCESS
        try:
            reply = self._llm.reply_conversation(text)
        except Exception:
            reply = f"（对话模式）{text}"
        if not isinstance(reply, str) or not reply:
            reply = f"（对话模式）{text}"
        bb.final_response = reply
        return Status.SUCCESS
