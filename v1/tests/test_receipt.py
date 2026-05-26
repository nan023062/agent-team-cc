"""Unit tests for engine.execution.actions.receipt.parse_trailer.

Covers PR-A spec §8.2 cases 1-9.
"""
from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# Multi-line continuation values (pretty-printed JSON arch_plan etc.)
#
# The architect emits arch_plan as a JSON-encoded list[dict]. LLMs naturally
# pretty-print JSON across multiple lines; the line-oriented parser must
# treat lines whose prefix is not an identifier-shaped key as continuations
# of the currently-open field. See receipt.py::_looks_like_new_field.
# ---------------------------------------------------------------------------

_PLAN = [
    {
        "id": "t1",
        "description": "do the thing",
        "required_capability": "programmer",
        "params": {"depends_on": []},
        "arch_context": "ctx for t1",
    },
    {
        "id": "t2",
        "description": "do the other thing",
        "required_capability": "tester",
        "params": {"depends_on": ["t1"]},
        "arch_context": "ctx for t2",
    },
]


def test_single_line_arch_plan_still_parses_identically():
    """Baseline: a one-line arch_plan continues to parse exactly as before
    the continuation rule was added. Regression guard."""
    one_line = json.dumps(_PLAN, ensure_ascii=False)
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: architect",
        "summary: planned.",
        f"arch_plan: {one_line}",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert t.extras["arch_plan"] == one_line
    assert json.loads(t.extras["arch_plan"]) == _PLAN


def test_two_line_arch_plan_parses_to_same_json():
    """Opening ``[`` on the key line, contents + closing ``]`` on the next
    line. The closing line is a continuation (no identifier:value prefix)."""
    payload = json.dumps(_PLAN, ensure_ascii=False)
    # Split right after the first ``[`` so the head stays on the key line
    # and the tail wraps onto its own line.
    head = "["
    tail = payload[1:]  # everything from the first object onward, including ']'
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: architect",
        "summary: planned.",
        f"arch_plan: {head}",
        tail,
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    raw = t.extras["arch_plan"]
    # JSON tolerates whitespace; the value must round-trip to the same plan.
    assert json.loads(raw) == _PLAN


def test_fully_pretty_printed_multi_line_arch_plan_parses():
    """The natural LLM output format: indent=2 across many lines, including
    blank lines (which the parser must preserve as part of the value)."""
    pretty = json.dumps(_PLAN, ensure_ascii=False, indent=2)
    # Splice a blank line into the middle to confirm blank lines inside a
    # multi-line value survive (JSON parsers ignore them).
    lines = pretty.split("\n")
    midpoint = len(lines) // 2
    pretty_with_blank = "\n".join(lines[:midpoint] + [""] + lines[midpoint:])

    # Build the trailer with arch_plan spanning many lines.
    pretty_lines = pretty_with_blank.split("\n")
    body_lines = [
        "status: ok",
        "task_id: t1",
        "agent: architect",
        "summary: planned.",
        # Opening line: key + first JSON char.
        f"arch_plan: {pretty_lines[0]}",
        *pretty_lines[1:],
    ]
    text = _trailer(body_lines)
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert json.loads(t.extras["arch_plan"]) == _PLAN
    # Other fields are unaffected.
    assert t.summary == "planned."
    assert t.agent == "architect"


def test_known_field_prefix_inside_multi_line_value_starts_new_field():
    """Edge case (d): if a continuation line happens to begin with ``agent:``
    (unlikely but possible, e.g. an unquoted YAML-ish snippet inside a
    value), it MUST be recognized as a new field — the continuation rule
    is 'unknown identifier-shaped prefix', not 'no colon'."""
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "summary: first line of summary",
        # This line LOOKS like a continuation of summary, but its prefix is
        # the known field name ``agent`` — so it must open the agent field.
        "agent: programmer",
        # And the body remains valid: all required fields are present.
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.status == "ok"
    assert t.agent == "programmer"
    assert t.summary == "first line of summary"


def test_continuation_does_not_misclassify_json_internal_colons():
    """Defense in depth: pretty-printed JSON contains many ``"key":`` lines.
    Those start with a quote, not an identifier, so they must be treated
    as continuations — never as new trailer fields. If this regresses,
    arch_plan parsing silently truncates."""
    pretty = json.dumps(_PLAN, ensure_ascii=False, indent=2)
    pretty_lines = pretty.split("\n")
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: architect",
        "summary: planned.",
        f"arch_plan: {pretty_lines[0]}",
        *pretty_lines[1:],
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    # Sanity: arch_plan parses, and none of the JSON-internal keys
    # ("id", "description", "params", ...) leaked into extras.
    assert json.loads(t.extras["arch_plan"]) == _PLAN
    leaked = {"id", "description", "required_capability", "params", "arch_context"}
    assert leaked.isdisjoint(t.extras.keys())


def test_unknown_identifier_prefix_after_known_fields_still_lands_in_extras():
    """Regression: ``test_unknown_key_lands_in_extras`` already covers the
    happy path, but this pins the interaction with the new continuation
    code — a fresh ``foo: bar`` line after ``summary`` MUST open a new
    extras field, not be appended to summary's value buffer."""
    text = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: did the thing.",
        "foo: bar",
    ])
    t = parse_trailer(text, dispatch_task_id="t1")
    assert t.summary == "did the thing."
    assert t.extras["foo"] == "bar"


def test_parse_trailer_never_raises_on_pathological_multiline():
    """The never-raises contract must survive the continuation extension."""
    # Pile up enough hostile patterns to exercise the continuation buffer
    # without tripping the parser into an exception.
    weird = _trailer([
        "status: ok",
        "task_id: t1",
        "agent: programmer",
        "summary: starts here",
        "  ",  # blank-ish continuation
        "no colon at all just prose",
        '{"id": "x", "nested": {"k": "v"}}',
        "]",
        "}",
        "trailing: with: many: colons",  # 'trailing' is an identifier → new extras field
    ])
    t = parse_trailer(weird, dispatch_task_id="t1")
    assert t.status == "ok"
    # The non-identifier lines all attached to summary; the identifier-led
    # line opened a fresh extras field rather than blowing up.
    assert "trailing" in t.extras
    assert t.extras["trailing"] == "with: many: colons"
