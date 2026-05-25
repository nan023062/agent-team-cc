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


class _ScriptedLLM:
    """LLM stub that returns a different reply per call so we can drive
    the retry path."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, int | None]] = []

    def run(self, prompt: str, *, max_tokens: int | None = None) -> str:
        idx = len(self.calls)
        self.calls.append((prompt, max_tokens))
        if idx < len(self._replies):
            return self._replies[idx]
        return self._replies[-1]


class _PositionalOnlyLLM:
    """Old-shape stub whose `run` doesn't accept the max_tokens kwarg.

    Mirrors stubs that predate the per-leaf max_tokens parameter.
    """

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls: list[str] = []

    def run(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._reply


def test_retries_succeed_on_second_attempt_when_first_parse_fails():
    """Truncation-style failure on attempt 1, clean reply on attempt 2 →
    SUCCESS, exactly two LLM calls, parse_retry event between them."""
    llm = _ScriptedLLM(replies=["garbage", '{"v": "ok"}'])

    import json as _json
    leaf = LlmActionLeaf(
        name="RetryLeaf",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: _json.loads(s) if s.startswith("{") else None,
        output_field="answer",
        retries=2,
    )
    bb = _bb()

    status = leaf.tick(bb)

    assert status is Status.SUCCESS
    assert len(llm.calls) == 2
    assert bb.answer == {"v": "ok"}
    events = [e["event"] for e in bb.trace]
    # start → end(1) → retry → end(2) → ok
    assert events == [
        "llm_call_start", "llm_call_end", "parse_retry",
        "llm_call_end", "parse_ok",
    ]


def test_retries_exhausted_returns_failure_with_attempts_count():
    """Every attempt returns garbage → FAILURE, parse_fail event records
    the attempts count, bb.<output_field> stays unwritten."""
    llm = _ScriptedLLM(replies=["g1", "g2", "g3"])

    leaf = LlmActionLeaf(
        name="ExhaustLeaf",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: None,
        output_field="answer",
        retries=3,
    )
    bb = _bb()

    status = leaf.tick(bb)

    assert status is Status.FAILURE
    assert len(llm.calls) == 3
    assert not hasattr(bb, "answer")
    fail_event = bb.trace[-1]
    assert fail_event["event"] == "parse_fail"
    assert fail_event["attempts"] == 3


def test_max_tokens_passed_to_llm_run_when_set():
    """When max_tokens is set, every LLM call receives it as a kwarg."""
    llm = _ScriptedLLM(replies=['{"ok": true}'])

    import json as _json
    leaf = LlmActionLeaf(
        name="CapLeaf",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: _json.loads(s),
        output_field="answer",
        max_tokens=4096,
    )
    bb = _bb()
    leaf.tick(bb)

    assert llm.calls == [("p", 4096)]


def test_max_tokens_omitted_when_not_set():
    """When max_tokens is None, the kwarg is not forwarded (preserves the
    pre-feature default-cap behavior)."""
    llm = _ScriptedLLM(replies=['{"ok": true}'])

    import json as _json
    leaf = LlmActionLeaf(
        name="NoCapLeaf",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: _json.loads(s),
        output_field="answer",
    )
    bb = _bb()
    leaf.tick(bb)

    assert llm.calls == [("p", None)]


def test_max_tokens_tolerates_clients_without_kwarg():
    """Stub clients whose run() doesn't accept max_tokens still work —
    the kwarg is silently dropped via TypeError fallback."""
    llm = _PositionalOnlyLLM(reply='{"ok": true}')

    import json as _json
    leaf = LlmActionLeaf(
        name="LegacyLeaf",
        llm_client=llm,
        prompt_builder=lambda bb: "p",
        response_parser=lambda s: _json.loads(s),
        output_field="answer",
        max_tokens=2048,
    )
    bb = _bb()
    status = leaf.tick(bb)

    assert status is Status.SUCCESS
    assert llm.calls == ["p"]
    assert bb.answer == {"ok": True}


def test_retries_zero_rejected_at_construction():
    """retries < 1 is a misuse — fail loudly at construction time."""
    import pytest as _pytest
    with _pytest.raises(ValueError):
        LlmActionLeaf(
            name="X",
            llm_client=_RecordingLLM("x"),
            prompt_builder=lambda bb: "p",
            response_parser=lambda s: s,
            output_field="answer",
            retries=0,
        )


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
