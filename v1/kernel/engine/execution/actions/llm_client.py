"""actions/llm_client.py — Real LLM client for the BT engine (v3).

Implements the two-method LLM protocol used by v3 ModeClassify and
DirectReply:

    classify_mode(user_request)     -> 'conversation' | 'execution'
    reply_conversation(user_request) -> str

Constructor injection only — never instantiated at module import time. The
`anthropic` SDK import is deferred so `import engine.execution` works on machines
without the SDK installed; missing SDK or missing API key surfaces only when
a method is actually called.

API key source: os.environ["ANTHROPIC_API_KEY"].
Default model: claude-haiku-4-5-20251001 (fast, cheap, good for routing /
short replies).
"""

from __future__ import annotations

import os

try:  # Deferred import — module import must not fail without the SDK.
    import anthropic  # type: ignore
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore


DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicLLM:
    """Anthropic-backed implementation of the v3 two-method LLM protocol."""

    def __init__(self, *, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 max_tokens: int = 1024, timeout: float = 30.0) -> None:
        if anthropic is None:
            raise RuntimeError(
                "anthropic SDK not installed; pip install anthropic"
            )
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # v3 Protocol methods
    # ------------------------------------------------------------------

    def classify_mode(self, user_request: str) -> str:
        system = (
            "You classify a user request into exactly one of two CBIM modes:\n"
            "  - 'conversation': a question, lookup, explanation, status check,\n"
            "    greeting, or anything that the coordinator can answer directly\n"
            "    without dispatching to a subagent.\n"
            "  - 'execution': a request to do something — implement, fix, design,\n"
            "    audit, recruit, train, refactor, etc. — anything requiring\n"
            "    Architect / HR / Work Agent involvement.\n\n"
            "Reply with ONLY the single word 'conversation' or 'execution'. "
            "No prose, no punctuation, no quotes."
        )
        reply = self._call(system, user_request, temperature=0,
                           max_tokens=8)
        verdict = (reply or "").strip().lower()
        if verdict not in ("conversation", "execution"):
            return "execution"
        return verdict

    def reply_conversation(self, user_request: str) -> str:
        system = (
            "You are the CBIM coordinator's conversational voice. The user "
            "asked something that does not need any subagent dispatch. Give "
            "a concise, helpful reply in the user's language. No filler, no "
            "self-introductions."
        )
        reply = self._call(system, user_request, temperature=0.3)
        return (reply or "").strip()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call(self, system: str, user: str, *, temperature: float = 0,
              max_tokens: int | None = None) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # `resp.content` is a list of content blocks; concatenate text blocks.
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)
