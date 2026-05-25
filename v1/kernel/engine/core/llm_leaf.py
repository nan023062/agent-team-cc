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
        Any object with ``run(prompt: str) -> str``. May optionally accept
        a keyword ``max_tokens`` argument; if not, the kwarg is dropped
        silently (best-effort) so stub LLMs without that parameter remain
        compatible.
    prompt_builder : Callable[[bb], str]
        Pure function that reads bb and returns a prompt string.
    response_parser : Callable[[str], Any | None]
        Returns the parsed value, or None to signal parse failure.
    output_field : str
        Attribute name on bb where the parsed value is written on success.
    skip_if : Callable[[bb], bool] | None
        Optional predicate; when truthy the LLM call is skipped and the
        node returns SUCCESS without touching bb.
    max_tokens : int | None
        Optional per-leaf max-tokens cap passed to ``llm_client.run``. JSON-
        emitting leaves (Scan / Map / Assemble) should set this to a value
        large enough that the model's structured reply will not be cut off
        mid-array; otherwise ``extract_json`` will silently return None and
        the leaf will FAILURE. ``None`` defers to the client's default.
    retries : int
        Number of attempts on parse failure (default 1 — no retry). The
        retry is in-process and immediate; it exists to absorb transient
        flakiness in JSON emission (an occasional dropped fence, a stray
        token) without re-architecting the outer tree. Each retry emits a
        ``parse_retry`` trace event so audits can spot flaky stages.
        Retries do NOT mutate bb between attempts — the prompt is rebuilt
        from the same bb state every time, which is safe because
        ``prompt_builder`` is a pure function over bb.
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
        max_tokens: int | None = None,
        retries: int = 1,
    ) -> None:
        if retries < 1:
            raise ValueError(f"retries must be >= 1, got {retries}")
        self.name = name
        self._llm = llm_client
        self._build_prompt = prompt_builder
        self._parse = response_parser
        self._output_field = output_field
        self._skip_if = skip_if
        self._max_tokens = max_tokens
        self._retries = retries

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

        last_output_chars = 0
        for attempt in range(1, self._retries + 1):
            start = time.monotonic()
            output = _invoke_llm(self._llm, prompt, self._max_tokens)
            duration_ms = int((time.monotonic() - start) * 1000)
            last_output_chars = len(output) if output is not None else 0

            _trace_append(bb, {
                "ts": _now_iso(),
                "node": self.name,
                "event": "llm_call_end",
                "duration_ms": duration_ms,
                "output_chars": last_output_chars,
                "attempt": attempt,
            })

            parsed = self._parse(output)
            if parsed is not None:
                _write_bb_field(bb, self._output_field, parsed)
                _trace_append(bb, {
                    "ts": _now_iso(),
                    "node": self.name,
                    "event": "parse_ok",
                    "output_field": self._output_field,
                    "attempt": attempt,
                })
                return Status.SUCCESS

            # Parse failed; retry if budget remains.
            if attempt < self._retries:
                _trace_append(bb, {
                    "ts": _now_iso(),
                    "node": self.name,
                    "event": "parse_retry",
                    "output_field": self._output_field,
                    "attempt": attempt,
                    "output_chars": last_output_chars,
                })

        _trace_append(bb, {
            "ts": _now_iso(),
            "node": self.name,
            "event": "parse_fail",
            "output_field": self._output_field,
            "attempts": self._retries,
        })
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_llm(llm: Any, prompt: str, max_tokens: int | None) -> str:
    """Call ``llm.run(prompt)``; pass ``max_tokens`` as kwarg when supplied
    and the client accepts it. Stub LLMs whose ``run`` signature predates
    the kwarg fall back to the positional-only form silently.

    No exception swallowing — a misbehaving LLM (network error, runtime
    crash) still surfaces; only the kwarg-shape mismatch is tolerated.
    """
    if max_tokens is None:
        return llm.run(prompt)
    try:
        return llm.run(prompt, max_tokens=max_tokens)
    except TypeError:
        # Stub / older client without max_tokens kwarg — fall back.
        return llm.run(prompt)


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
