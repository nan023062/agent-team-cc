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
            "You classify a user request into exactly one of five CBIM modes:\n"
            "  - 'conversation': a question, lookup, explanation, status check,\n"
            "    greeting, or anything the coordinator can answer directly\n"
            "    without dispatching to a subagent.\n"
            "  - 'architect': design, blueprint, module shape, knowledge-pack,\n"
            "    or .dna / module.md / contract.md authoring requests.\n"
            "  - 'hr': agent recruitment, training, assessment, gap filling,\n"
            "    workforce / capability management requests.\n"
            "  - 'audit': independent review, critique, second opinion, code or\n"
            "    design review requests.\n"
            "  - 'execution': any request to do work (implement / fix / refactor /\n"
            "    build / wire / create / etc.) that needs the full Architect →\n"
            "    HR → Work Agent pipeline; this is the default when in doubt.\n\n"
            "Reply with ONLY one of the five single words 'conversation', "
            "'architect', 'hr', 'audit', or 'execution'. No prose, no "
            "punctuation, no quotes."
        )
        reply = self._call(system, user_request, temperature=0,
                           max_tokens=8)
        verdict = (reply or "").strip().lower()
        if verdict not in ("conversation", "architect", "hr", "audit", "execution"):
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

    def run(self, prompt: str, *, max_tokens: int | None = None) -> str:
        """Generic single-prompt entry used by LlmActionLeaf.

        The prompt is the whole user message; no separate system block is
        injected here so the caller stays in full control of the framing
        (each scan leaf already builds its own contract-bearing prompt).

        ``max_tokens`` overrides the client-default cap for this single
        call. Leaves that emit JSON arrays (Scan / Map / Assemble) must
        pass a higher value to avoid truncation-induced parse failures.
        When unset, falls back to ``self._max_tokens`` (constructor default).
        """
        reply = self._call(system="", user=prompt, temperature=0,
                           max_tokens=max_tokens)
        return reply or ""

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call(self, system: str, user: str, *, temperature: float = 0,
              max_tokens: int | None = None) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        # `resp.content` is a list of content blocks; concatenate text blocks.
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)
