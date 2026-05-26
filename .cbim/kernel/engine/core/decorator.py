"""core/decorator.py — Trace / Timeout / Retry / Catch.

Decorators wrap a single child and cross-cut concerns (observability,
timeouts, idempotent retries, error swallowing).

Locked stacking order outermost → innermost per WORKFLOW-EXECUTION §5:
  Trace > Timeout > {Retry | Catch}.

v3 note: LoopUntilConverge and IterationGuard were removed alongside the
iteration-loop topology — v3 has no main-loop iteration to cap or repeat.

Iron rule: decorators are STATELESS across ticks (per-tick try counters
are tick-local locals; no `self.tries` field surviving the tick).
"""

from __future__ import annotations

import time
from typing import Any

from .node import Node, Status


class _Decorator(Node):
    def __init__(self, child: Node, *, name: str) -> None:
        self.name = name
        self._child = child

    def children(self) -> list[Node]:
        return [self._child]


class Trace(_Decorator):
    """Record enter/exit events into bb.trace. Never fails."""

    def __init__(self, child: Node, *, name: str = "Trace") -> None:
        super().__init__(child, name=name)

    def tick(self, bb) -> Status:
        start = time.monotonic()
        try:
            bb.trace = (bb.trace or []) + [{
                "ts": _now_iso(),
                "node": self._child.name,
                "event": "enter",
            }]
        except Exception:
            pass
        try:
            status = self._child.tick(bb)
        except Exception as e:
            try:
                bb.trace = (bb.trace or []) + [{
                    "ts": _now_iso(),
                    "node": self._child.name,
                    "event": "trace_self_error",
                    "error": str(e)[:200],
                }]
            except Exception:
                pass
            raise
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            bb.trace = (bb.trace or []) + [{
                "ts": _now_iso(),
                "node": self._child.name,
                "event": "exit",
                "status": status.value,
                "duration_ms": duration_ms,
            }]
        except Exception:
            pass
        return status


class Timeout(_Decorator):
    """Wall-clock timeout. Does NOT kill subprocesses (engines per spec).

    Measures only synchronous wall time spent inside one tick() chain.
    Yielded-out waits do not count (the engine yields and returns control
    to the main agent; this decorator's tick has already returned).
    """

    def __init__(self, child: Node, *, seconds: int, name: str = "Timeout") -> None:
        super().__init__(child, name=name)
        self._seconds = seconds

    def tick(self, bb) -> Status:
        start = time.monotonic()
        status = self._child.tick(bb)
        elapsed = time.monotonic() - start
        if elapsed >= self._seconds and status is not Status.SUCCESS:
            try:
                bb.trace = (bb.trace or []) + [{
                    "ts": _now_iso(),
                    "node": self._child.name,
                    "event": "timeout",
                    "elapsed_s": int(elapsed),
                }]
            except Exception:
                pass
            return Status.FAILURE
        return status


class Retry(_Decorator):
    """Retry on FAILURE up to n times. ONLY wrap idempotent nodes.

    `only="idempotent"` is a marker for human review; the decorator does
    not introspect the child. Misuse (wrapping a non-idempotent node) is
    a code-review violation, not a runtime check.
    """

    def __init__(self, child: Node, *, n: int = 2,
                 only: str = "idempotent",
                 name: str | None = None) -> None:
        super().__init__(child, name=name or f"Retry({child.name})")
        self._n = n
        self._only = only

    def tick(self, bb) -> Status:
        last = Status.FAILURE
        for attempt in range(1, self._n + 1):
            status = self._child.tick(bb)
            if status is Status.RUNNING:
                return Status.RUNNING
            if status is Status.SUCCESS:
                return Status.SUCCESS
            last = status
            if attempt < self._n:
                try:
                    bb.trace = (bb.trace or []) + [{
                        "ts": _now_iso(),
                        "node": self._child.name,
                        "event": "retry",
                        "attempt": attempt,
                    }]
                except Exception:
                    pass
        return last


class Catch(_Decorator):
    """Swallow exceptions / convert FAILURE → SUCCESS per `fallback`.

    fallback semantics:
      - "swallow": exceptions caught, FAILURE passed through silently
      - dict: exceptions caught, returns SUCCESS (writes nothing to bb)
    """

    def __init__(self, child: Node, *, fallback: Any = "swallow",
                 name: str | None = None) -> None:
        super().__init__(child, name=name or f"Catch({child.name})")
        self._fallback = fallback

    def tick(self, bb) -> Status:
        try:
            status = self._child.tick(bb)
            return status
        except Exception as e:
            try:
                bb.trace = (bb.trace or []) + [{
                    "ts": _now_iso(),
                    "node": self._child.name,
                    "event": "catch",
                    "error": str(e)[:200],
                }]
            except Exception:
                pass
            if self._fallback == "swallow":
                return Status.FAILURE
            return Status.SUCCESS


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
