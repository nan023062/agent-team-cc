"""L5 — real-LLM integration tests (v3.5).

Two test groups in this module:

  1. Real-LLM integration tests — gated on ANTHROPIC_API_KEY via the
     ``_requires_api_key`` marker chain. Skipped when the env var is
     unset, run against the live Anthropic API when it is set.
  2. Prompt-shape / verdict-validation tests — pure introspection over
     the AnthropicLLM system prompt and its verdict-coercion logic.
     These do NOT make a network call and run unconditionally; they
     guard the 5-mode enumeration in the classify_mode prompt against
     silent drift.

Note: the only execution-root actions that call an LLM directly are
ModeClassify (on rule miss) and DirectReply (always). DispatchWork yields
to a Work Agent — the agent itself may or may not use an LLM internally,
but that is outside this engine's surface. The Architect execution
sub-loop runs as an in-process Python BT subtree; its LLM use is covered
elsewhere. (v3.6 removed the HR execution sub-loop entirely — the
capability→agent_file lookup now happens in the main agent via MCP.)
This file covers the two engine-internal LLM paths.
"""
from __future__ import annotations

import os

import pytest

from engine.execution.actions.direct_reply import DirectReply
from engine.execution.actions.mode_classify import ModeClassify
from engine.core.blackboard import Blackboard
from engine.core.node import Status


_requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY", "").strip(),
    reason="ANTHROPIC_API_KEY not set",
)


def _bb(**overrides) -> Blackboard:
    bb = Blackboard()
    bb.tick_id = "test"
    bb.user_request = overrides.get("user_request", "")
    for k, v in overrides.items():
        setattr(bb, k, v)
    return bb


def _llm():
    # Imported lazily so collection works even without the SDK installed.
    from engine.execution.actions.llm_client import AnthropicLLM
    return AnthropicLLM()


@_requires_api_key
@pytest.mark.requires_api_key
def test_mode_classify_with_real_llm_on_rule_miss():
    # A free-form sentence the rule table doesn't recognize — LLM must
    # produce one of the five valid mode labels.
    bb = _bb(user_request="please reorganize the data pipeline so it can "
                          "absorb spikes without dropping events.")
    node = ModeClassify(llm=_llm())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mode in ("conversation", "architect", "hr", "audit", "execution")


@_requires_api_key
@pytest.mark.requires_api_key
def test_direct_reply_with_real_llm_generates_response():
    bb = _bb(user_request="What is CBIM in one sentence?")
    node = DirectReply(llm=_llm())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.final_response
    assert len(bb.final_response) > 0


# ---------------------------------------------------------------------------
# classify_mode prompt enumerates all 5 modes
#
# These checks are SDK-free — they inspect the system prompt the
# AnthropicLLM would send, not the network round-trip — so they run even
# without ANTHROPIC_API_KEY. They are placed in this file to keep the
# real-LLM surface checks colocated; the module-level pytestmark skips
# only the tests that call the network.
# ---------------------------------------------------------------------------

class _PromptCaptureLLM:
    """Stand-in for the real Anthropic client; records the system prompt
    and returns a fixed reply so we can introspect what classify_mode
    actually asks the model."""

    def __init__(self, reply: str = "execution") -> None:
        self.last_system: str | None = None
        self.last_user: str | None = None
        self.last_kwargs: dict | None = None
        self._reply = reply

    class _Block:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Resp:
        def __init__(self, text: str) -> None:
            self.content = [_PromptCaptureLLM._Block(text)]

    class _Messages:
        def __init__(self, outer: "_PromptCaptureLLM") -> None:
            self._outer = outer

        def create(self, **kwargs):
            self._outer.last_kwargs = kwargs
            self._outer.last_system = kwargs.get("system")
            msgs = kwargs.get("messages") or []
            self._outer.last_user = msgs[0]["content"] if msgs else None
            return _PromptCaptureLLM._Resp(self._outer._reply)

    @property
    def messages(self):
        return _PromptCaptureLLM._Messages(self)


def _build_anthropic_with_stub_client(reply: str = "execution"):
    """Construct an AnthropicLLM without going through __init__ (which
    requires the SDK + an API key) and inject the prompt-capturing
    fake client directly."""
    from engine.execution.actions.llm_client import AnthropicLLM, DEFAULT_MODEL

    llm = AnthropicLLM.__new__(AnthropicLLM)
    fake = _PromptCaptureLLM(reply=reply)
    object.__setattr__(llm, "_client", fake)
    object.__setattr__(llm, "_model", DEFAULT_MODEL)
    object.__setattr__(llm, "_max_tokens", 1024)
    return llm, fake


def test_classify_mode_prompt_enumerates_five_modes():
    """The AnthropicLLM classify_mode system prompt must enumerate
    exactly the 5 mode labels and instruct the model to reply with one
    of them. This guards against silently dropping a mode from the
    prompt after the topology grew from 2 to 5 modes."""
    llm, fake = _build_anthropic_with_stub_client(reply="conversation")
    verdict = llm.classify_mode("hello")
    assert verdict == "conversation"

    system = fake.last_system or ""
    # Every mode label must appear, quoted, in the enumeration.
    for mode in ("conversation", "architect", "hr", "audit", "execution"):
        assert f"'{mode}'" in system, \
            f"classify_mode system prompt missing mode {mode!r}; got:\n{system}"

    # The reply instruction must list all 5 modes, not just two.
    assert "five" in system.lower() or "5" in system, \
        f"classify_mode prompt does not call out 5 modes explicitly:\n{system}"


def test_classify_mode_rejects_unknown_verdict_and_defaults_to_execution():
    """Any reply outside the 5-mode set must be coerced to 'execution'."""
    llm, _fake = _build_anthropic_with_stub_client(reply="nonsense_mode")
    assert llm.classify_mode("anything") == "execution"


def test_classify_mode_accepts_each_of_the_five_modes():
    """Each of the 5 labels must round-trip through classify_mode."""
    for mode in ("conversation", "architect", "hr", "audit", "execution"):
        llm, _fake = _build_anthropic_with_stub_client(reply=mode)
        assert llm.classify_mode("anything") == mode
