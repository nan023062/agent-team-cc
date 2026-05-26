"""actions/direct_reply.py — conversation-mode fast path.

Writes a coordinator-level reply directly into bb.final_response without
yielding to any agent. Used when ModeClassify routes bb.mode="conversation".

PR-D: the deterministic passthrough is the full implementation. In the
Claude Code edition the coordinator (main agent) is itself the
conversational voice — when the user asks a question, the user is
already talking to a model. Routing conversation through a second LLM
inside the kernel would be pure ceremony.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class DirectReply(Node):
    def __init__(self, *, name: str = "DirectReply") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        text = (bb.user_request or "").strip()
        if not text:
            bb.final_response = "请描述你的需求。"
            return Status.SUCCESS
        bb.final_response = f"（对话模式）{text}"
        return Status.SUCCESS
