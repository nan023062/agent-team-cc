"""Unit tests for engine.execution.actions.receipt.parse_trailer.

Covers PR-A spec §8.2 cases 1-9.
"""
from __future__ import annotations

import textwrap

from engine.execution.actions.receipt import ReceiptTrailer, parse_trailer


def _trailer(body_lines: list[str], prose: str = "deliverable here") -> str:
    body = "\n".join(body_lines)
    return f"{prose}\n\n<!-- BEGIN CBIM-RECEIPT v1\n{body}\nEND CBIM-RECEIPT -->\n"


# ---------------------------------------------------------------------------
# Case 1 — the four §2.4 samples each parse cleanly
# ---------------------------------------------------------------------------

def test_sample_ok_parses_cleanly():
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: Stop hook flushes pending dream_tick; tests pass.",
        "artifacts: .claude/hooks/cbim_stop.py, tests/hooks/test_cbim_stop.py",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert t.task_id == "t1"
    assert t.agent == "programmer"
    assert t.summary.startswith("Stop hook")
    assert t.artifacts == (
        ".claude/hooks/cbim_stop.py",
        "tests/hooks/test_cbim_stop.py",
    )
    assert t.extras == {}


def test_sample_needs_arch_decision_parses_cleanly():
    text = _trailer([
        "status: needs_arch_decision",
        "task_id: t1",
        "agent: programmer",
        "summary: Missing receipt schema.",
        "question: What are the required fields for status=failed?",
        "blocking_module: v1/kernel/engine/execution",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "needs_arch_decision"
    assert t.question.startswith("What are the required fields")
    assert t.blocking_module == "v1/kernel/engine/execution"
    assert t.extras == {}


def test_sample_needs_user_input_parses_cleanly():
    text = _trailer([
        "status: needs_user_input",
        "task_id: t1",
        "agent: programmer",
        'summary: "tidy up memory" is ambiguous.',
        "question: Do you want (a) distill short, or (b) archive old entries?",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "needs_user_input"
    assert "ambiguous" in t.summary
    assert t.question.startswith("Do you want")
    assert t.failure_kind is None


def test_sample_failed_parses_cleanly():
    text = _trailer([
        "status: failed",
        "task_id: t1",
        "agent: programmer",
        "summary: pytest segfaults on macOS in CI; runs fine locally.",
        "failure_kind: test_failed",
        "artifacts: tests/engine/conftest.py",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "test_failed"
    assert t.artifacts == ("tests/engine/conftest.py",)


# ---------------------------------------------------------------------------
# Case 2 — legacy reply (no trailer)
# ---------------------------------------------------------------------------

def test_legacy_reply_falls_back_to_ok_with_legacy_flag():
    text = "Here's the patch. Done."
    t = parse_trailer(text, dispatch_task_id="t-legacy")
    assert t.status == "ok"
    assert t.task_id == "t-legacy"
    assert t.agent == "unknown"
    assert t.extras["_legacy"] == "no_trailer"


# ---------------------------------------------------------------------------
# Case 3 — unknown status enum
# ---------------------------------------------------------------------------

def test_unknown_status_collapses_to_failed_with_parse_error():
    text = _trailer([
        "status: maybe",
        "task_id: t1",
        "agent: programmer",
        "summary: tried.",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "other"
    assert "parse error" in t.summary
    assert "_raw" in t.extras


# ---------------------------------------------------------------------------
# Case 4 — missing required field for declared status
# ---------------------------------------------------------------------------

def test_needs_arch_decision_without_question_collapses_to_failed():
    text = _trailer([
        "status: needs_arch_decision",
        "task_id: t1",
        "agent: programmer",
        "summary: blocked.",
        # no question
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "other"
    assert "question" in t.summary


def test_failed_without_failure_kind_collapses_to_failed_parse_error():
    text = _trailer([
        "status: failed",
        "task_id: t1",
        "agent: programmer",
        "summary: something blew up.",
        # no failure_kind
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "other"
    assert "failure_kind" in t.summary


# ---------------------------------------------------------------------------
# Case 5 — two trailer blocks back-to-back; last wins, first shadowed
# ---------------------------------------------------------------------------

def test_two_trailers_last_wins_first_shadowed():
    text = (
        "first prose\n\n"
        "<!-- BEGIN CBIM-RECEIPT v1\n"
        "status: failed\n"
        "task_id: t1\n"
        "agent: programmer\n"
        "summary: first reply.\n"
        "failure_kind: other\n"
        "END CBIM-RECEIPT -->\n\n"
        "second prose\n\n"
        "<!-- BEGIN CBIM-RECEIPT v1\n"
        "status: ok\n"
        "task_id: t1\n"
        "agent: programmer\n"
        "summary: second reply wins.\n"
        "END CBIM-RECEIPT -->\n"
    )
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert t.summary == "second reply wins."
    assert "_shadowed_blocks" in t.extras
    assert "first reply." in t.extras["_shadowed_blocks"]


# ---------------------------------------------------------------------------
# Case 6 — unknown extra key preserved in extras
# ---------------------------------------------------------------------------

def test_unknown_key_lands_in_extras():
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: did the thing.",
        "foo: bar",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert t.extras["foo"] == "bar"


# ---------------------------------------------------------------------------
# Case 7 — truncated trailer (no END sentinel)
# ---------------------------------------------------------------------------

def test_truncated_trailer_collapses_to_failed_with_raw():
    text = (
        "some prose\n\n"
        "<!-- BEGIN CBIM-RECEIPT v1\n"
        "status: ok\n"
        "task_id: t1\n"
        "agent: programmer\n"
        # missing END sentinel
    )
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "other"
    assert "END sentinel" in t.summary
    assert "_raw" in t.extras
    assert "BEGIN CBIM-RECEIPT v1" in t.extras["_raw"]


# ---------------------------------------------------------------------------
# Case 8 — artifacts with whitespace + trailing comma noise
# ---------------------------------------------------------------------------

def test_artifacts_splits_and_strips_whitespace():
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: done.",
        "artifacts: a.py, b.py , c.py",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.artifacts == ("a.py", "b.py", "c.py")


def test_artifacts_drops_empty_segments():
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: done.",
        "artifacts: a.py, ,b.py,",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.artifacts == ("a.py", "b.py")


# ---------------------------------------------------------------------------
# Case 9 — trailing prose after END is tolerated but recorded
# ---------------------------------------------------------------------------

def test_trailing_prose_after_end_lands_in_extras():
    text = (
        _trailer([
            "status: ok",
            "task_id: t1",
            "agent: programmer",
            "summary: done.",
        ])
        + "\n\nstray prose after the trailer"
    )
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert "stray prose" in t.extras["_trailing_after_end"]


# ---------------------------------------------------------------------------
# Non-spec but defensive: parse_trailer must never raise on hostile input
# ---------------------------------------------------------------------------

def test_parser_does_not_raise_on_none_or_empty():
    assert parse_trailer("", dispatch_task_id="t1").status == "ok"
    assert parse_trailer(None, dispatch_task_id="t1").status == "ok"  # type: ignore[arg-type]
    huge = "x" * 100_000
    assert parse_trailer(huge, dispatch_task_id="t1").status == "ok"


def test_is_terminal_ok_helper():
    t = ReceiptTrailer(status="ok", task_id="t1", agent="a", summary="s")
    assert t.is_terminal_ok() is True
    t2 = ReceiptTrailer(status="failed", task_id="t1", agent="a", summary="s",
                        failure_kind="other")
    assert t2.is_terminal_ok() is False


def test_unknown_failure_kind_collapses_to_parse_error():
    text = _trailer([
        "status: failed",
        "task_id: t1",
        "agent: programmer",
        "summary: blew up.",
        "failure_kind: meltdown",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "failed"
    assert t.failure_kind == "other"
    assert "unknown failure_kind" in t.summary
