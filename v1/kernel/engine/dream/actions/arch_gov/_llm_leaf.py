"""arch_gov/_llm_leaf.py — Subclassable LLM leaf base for governance scans.

Different interface from engine.core.llm_leaf.LlmActionLeaf (which uses
injected callables). These governance scan leaves use subclass overrides.
"""
from __future__ import annotations

from engine.core.node import Node, Status


class LlmActionLeaf(Node):
    """Base for scan leaves that override build_prompt / parse_reply / apply_result.

    Constructor: LlmActionLeaf(*, llm, name)
      llm : any object with .run(prompt: str) -> str
    """

    def __init__(self, *, llm, name: str = "LlmActionLeaf") -> None:
        self.name = name
        self._llm = llm

    def build_prompt(self, bb, state: dict) -> str:
        return ""

    def parse_reply(self, reply: str):
        return reply

    def apply_result(self, bb, state: dict, parsed) -> None:
        return None

    def tick(self, bb) -> Status:
        state = getattr(self, "_state", {})
        try:
            prompt = self.build_prompt(bb, state)
            reply = self._llm.run(prompt)
            parsed = self.parse_reply(reply)
            self.apply_result(bb, state, parsed)
        except Exception:
            return Status.FAILURE
        return Status.SUCCESS


__all__ = ["LlmActionLeaf"]
