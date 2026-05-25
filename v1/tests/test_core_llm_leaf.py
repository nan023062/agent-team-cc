"""Unit tests for engine.core.llm_leaf.LlmActionLeaf.

Covers the five contract points called out in the t2 brief:
  1. Happy path → SUCCESS + bb.<output_field> written.
  2. Parse failure → FAILURE + bb.<output_field> untouched.
  3. skip_if=True → SUCCESS + zero LLM calls.
  4. Self-tracing → start/end/parse_ok events appended.
  5. No cross-tick state on self.
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.core import LlmActionLeaf
from engine.core.node import Status
from engine.execution.actions.llm_hook import NullLLM


class _RecordingLLM:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls: list[str] = []

    def run(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._reply


def _bb(**fields):
    bb = SimpleNamespace(trace=[])
    for k, v in fields.items():
        setattr(bb, k, v)
    return bb


def test_happy_path_writes_output_and_returns_success():
    llm = _RecordingLLM("hello")
    leaf = LlmActionLeaf(
        name="LeafA",
        llm_client=llm,
        prompt_builder=lambda bb: f"prompt:{bb.user_request}",
        response_parser=lambda s: s.upper(),
        output_field="answer",
    )
    bb = _bb(user_request="ping")

    status = leaf.tick(bb)

    assert status is Status.SUCCESS
    assert llm.calls == ["prompt:ping"]
    assert bb.answer == "HELLO"


def test_parse_failure_returns_failure_and_does_not_write_field():
    llm = _RecordingLLM("garbage")
    leaf = LlmActionLeaf(
        name="LeafB",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: None,
        output_field="answer",
    )
    bb = _bb()

    status = leaf.tick(bb)

    assert status is Status.FAILURE
    assert llm.calls == ["p"]  # call still happened, parse just failed
    assert not hasattr(bb, "answer")


def test_skip_if_true_skips_llm_call():
    llm = _RecordingLLM("hello")
    leaf = LlmActionLeaf(
        name="LeafC",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: s,
        output_field="answer",
        skip_if=lambda bb: True,
    )
    bb = _bb()

    status = leaf.tick(bb)

    assert status is Status.SUCCESS
    assert llm.calls == []
    assert not hasattr(bb, "answer")
    # No trace events for a skipped tick.
    assert bb.trace == []


def test_self_traces_start_end_and_parse_ok():
    llm = _RecordingLLM("payload")
    leaf = LlmActionLeaf(
        name="LeafD",
        llm_client=llm,
        prompt_builder=lambda bb: "prompt",
        response_parser=lambda s: {"v": s},
        output_field="parsed",
    )
    bb = _bb()

    leaf.tick(bb)

    events = [e["event"] for e in bb.trace]
    assert events == ["llm_call_start", "llm_call_end", "parse_ok"]

    start, end, ok = bb.trace
    assert start["node"] == "LeafD"
    assert "prompt_hash" in start and len(start["prompt_hash"]) == 12
    assert "duration_ms" in end and end["output_chars"] == len("payload")
    assert ok["output_field"] == "parsed"


def test_parse_fail_event_emitted_on_failure():
    leaf = LlmActionLeaf(
        name="LeafE",
        llm_client=_RecordingLLM("x"),
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: None,
        output_field="answer",
    )
    bb = _bb()
    leaf.tick(bb)
    events = [e["event"] for e in bb.trace]
    assert events == ["llm_call_start", "llm_call_end", "parse_fail"]


def test_no_cross_tick_state_leak_on_same_instance():
    llm = _RecordingLLM("ok")
    leaf = LlmActionLeaf(
        name="LeafF",
        llm_client=llm,
        prompt_builder=lambda bb: f"p:{bb.user_request}",
        response_parser=lambda s: s,
        output_field="answer",
    )

    bb1 = _bb(user_request="r1")
    leaf.tick(bb1)

    # Second tick on a fresh bb: its trace must NOT contain bb1's events.
    bb2 = _bb(user_request="r2")
    leaf.tick(bb2)

    assert [e["event"] for e in bb2.trace] == [
        "llm_call_start", "llm_call_end", "parse_ok",
    ]
    # And the prompt_hash for bb2's start event differs from bb1's (different prompt).
    h1 = bb1.trace[0]["prompt_hash"]
    h2 = bb2.trace[0]["prompt_hash"]
    assert h1 != h2

    # Self should hold no per-tick attributes beyond the constructor-set ones.
    public_attrs = {
        k for k in vars(leaf).keys()
        if not k.startswith("_") and k != "name"
    }
    assert public_attrs == set()


def test_works_with_nullllm_default_stub():
    """Smoke test: NullLLM.run returns valid JSON that a json.loads parser handles."""
    import json

    leaf = LlmActionLeaf(
        name="LeafG",
        llm_client=NullLLM(),
        prompt_builder=lambda bb: "anything",
        response_parser=lambda s: json.loads(s),
        output_field="payload",
    )
    bb = _bb()
    status = leaf.tick(bb)
    assert status is Status.SUCCESS
    assert bb.payload == {"result": None}
