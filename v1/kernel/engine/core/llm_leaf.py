"""core/llm_leaf.py — LlmActionLeaf primitive.

A BT leaf that performs exactly one LLM call per tick (or zero, when the
caller-supplied `skip_if` predicate gates it out). Designed so any node that
needs LLM-derived output can be built by composition rather than subclassing:
prompt construction, response parsing, and bb-write target are all injected
as callables / strings.

Iron rules (per node ABC):
  - At most one LLM call per tick; no cross-tick state on `self`.
  - On parse failure, return FAILURE so an outer Retry decorator can rerun.
  - Tracing is opportunistic: appends to bb.trace iff bb has a list-typed
    trace attribute, never crashes if absent.

This module deliberately does NOT import anthropic (or any LLM SDK) — the
client is injected, the test suite passes a stub. The real wiring lives in
engine.execution.actions.llm_client.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .node import Node, Status


class LlmActionLeaf(Node):
    """Leaf node that runs prompt_builder → llm_client.run → response_parser,
    then writes the parsed value to ``bb.<output_field>``.

    Constructor parameters
    ----------------------
    name : str
        Node name (used in trace events).
    llm_client : object
        Any object with ``run(prompt: str) -> str``.
    prompt_builder : Callable[[bb], str]
        Pure function that reads bb and returns a prompt string.
    response_parser : Callable[[str], Any | None]
        Returns the parsed value, or None to signal parse failure.
    output_field : str
        Attribute name on bb where the parsed value is written on success.
    skip_if : Callable[[bb], bool] | None
        Optional predicate; when truthy the LLM call is skipped and the
        node returns SUCCESS without touching bb.
    """

    def __init__(
        self,
        *,
        name: str,
        llm_client: Any,
        prompt_builder: Callable[[Any], str],
        response_parser: Callable[[str], Any],
        output_field: str,
        skip_if: Callable[[Any], bool] | None = None,
    ) -> None:
        self.name = name
        self._llm = llm_client
        self._build_prompt = prompt_builder
        self._parse = response_parser
        self._output_field = output_field
        self._skip_if = skip_if

    def tick(self, bb) -> Status:
        if self._skip_if is not None and self._skip_if(bb):
            return Status.SUCCESS

        prompt = self._build_prompt(bb)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

        _trace_append(bb, {
            "ts": _now_iso(),
            "node": self.name,
            "event": "llm_call_start",
            "prompt_hash": prompt_hash,
        })

        start = time.monotonic()
        output = self._llm.run(prompt)
        duration_ms = int((time.monotonic() - start) * 1000)

        _trace_append(bb, {
            "ts": _now_iso(),
            "node": self.name,
            "event": "llm_call_end",
            "duration_ms": duration_ms,
            "output_chars": len(output) if output is not None else 0,
        })

        parsed = self._parse(output)
        if parsed is None:
            _trace_append(bb, {
                "ts": _now_iso(),
                "node": self.name,
                "event": "parse_fail",
                "output_field": self._output_field,
            })
            return Status.FAILURE

        _write_bb_field(bb, self._output_field, parsed)
        _trace_append(bb, {
            "ts": _now_iso(),
            "node": self.name,
            "event": "parse_ok",
            "output_field": self._output_field,
        })
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trace_append(bb, event: dict) -> None:
    """Append `event` to bb.trace iff bb has a list-typed trace attribute.

    Graceful: missing attribute, non-list, or write errors are swallowed —
    tracing is observational and must not fail the tick.
    """
    trace = getattr(bb, "trace", None)
    if not isinstance(trace, list):
        return
    try:
        bb.trace = trace + [event]
    except Exception:
        pass


def _write_bb_field(bb, field: str, value: Any) -> None:
    """Write value to bb.<field>. Prefer setattr; fall back to __dict__ for
    blackboards that disallow arbitrary attributes via __slots__.
    """
    try:
        setattr(bb, field, value)
        return
    except (AttributeError, TypeError):
        pass
    bb.__dict__[field] = value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
