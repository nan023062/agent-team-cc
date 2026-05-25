"""L5 — real-LLM integration tests (v3).

Gated on ANTHROPIC_API_KEY: skipped cleanly when the env var is unset, run
against the real Anthropic API when it is set. The `requires_api_key`
marker is informational; the hard skip lives in the module-level fixture
so the tests are safe to collect anywhere.

v3 note: the only v3 action that calls into an LLM is ModeClassify (on rule
miss) and DirectReply (always). DispatchArchitect/HR/Work don't call an LLM
themselves — they yield to peer agents whose own implementation may or may
not use LLMs internally. This file covers the two engine-internal LLM paths.
"""
from __future__ import annotations

import os

import pytest

from engine.execution.actions.direct_reply import DirectReply
from engine.execution.actions.mode_classify import ModeClassify
from engine.execution.core.blackboard import Blackboard
from engine.execution.core.node import Status


pytestmark = [
    pytest.mark.requires_api_key,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


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


def test_mode_classify_with_real_llm_on_rule_miss():
    # A free-form sentence the rule table doesn't recognize — LLM must
    # produce one of the two valid mode labels.
    bb = _bb(user_request="please reorganize the data pipeline so it can "
                          "absorb spikes without dropping events.")
    node = ModeClassify(llm=_llm())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.mode in ("conversation", "execution")


def test_direct_reply_with_real_llm_generates_response():
    bb = _bb(user_request="What is CBIM in one sentence?")
    node = DirectReply(llm=_llm())
    assert node.tick(bb) is Status.SUCCESS
    assert bb.final_response
    assert len(bb.final_response) > 0
