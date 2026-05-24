"""core/decorator.py — Trace / Timeout / Retry / Catch / IterationGuard
+ LoopUntilConverge.

Decorators wrap a single child and cross-cut concerns (observability,
timeouts, idempotent retries, error swallowing, iteration capping).

Locked stacking order outermost → innermost per WORKFLOW-EXECUTION §3:
  Trace > Timeout > {Retry | IterationGuard | Catch}.

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


class IterationGuard(_Decorator):
    """Increment-and-check iteration; on overrun, set converge_signal=interrupt
    + interrupt_reason and return SUCCESS so the parent LoopUntilConverge
    can exit cleanly on its next pass.

    Counts entries to the wrapped sequence; child increments via Decompose's
    own iteration += 1 (per the design write-side rule); this guard ONLY
    checks the cap, it doesn't write iteration itself.
    """

    def __init__(self, child: Node, *, name: str = "IterationGuard") -> None:
        super().__init__(child, name=name)

    def tick(self, bb) -> Status:
        cap = bb.iteration_cap or 5
        cur = bb.iteration or 0
        if cur >= cap:
            bb.converge_signal = "interrupt"
            bb.interrupt_reason = bb.interrupt_reason or "iteration_cap_exceeded"
            try:
                bb.trace = (bb.trace or []) + [{
                    "ts": _now_iso(),
                    "node": self.name,
                    "event": "iteration_cap_exceeded",
                    "iteration": cur, "cap": cap,
                }]
            except Exception:
                pass
            return Status.SUCCESS
        return self._child.tick(bb)


class LoopUntilConverge(_Decorator):
    """Loop the child until bb.converge_signal in {'done','interrupt'} or
    iteration_cap is exceeded.

    Once child returns RUNNING, we propagate immediately (the engine
    yields out to the main agent); on the next tick the Runner re-enters
    via the resume path and re-evaluates the converge condition.
    """

    def __init__(self, child: Node, *, name: str = "LoopUntilConverge") -> None:
        super().__init__(child, name=name)

    def tick(self, bb) -> Status:
        # Safety net to prevent infinite Python-level loops if a child
        # forgets to set converge_signal. The real cap is iteration_cap;
        # this is a defensive ceiling.
        for _ in range(100):
            if bb.converge_signal in ("done", "interrupt"):
                return Status.SUCCESS
            cap = bb.iteration_cap or 5
            if (bb.iteration or 0) > cap:
                bb.converge_signal = "interrupt"
                bb.interrupt_reason = bb.interrupt_reason or "iteration_cap_exceeded"
                return Status.SUCCESS
            status = self._child.tick(bb)
            if status is Status.RUNNING:
                return Status.RUNNING
            if status is Status.FAILURE:
                # Aggregate / Converge write interrupt_reason themselves on
                # FAILURE; treat as terminate.
                bb.converge_signal = bb.converge_signal or "interrupt"
                return Status.SUCCESS
            # SUCCESS → re-check converge_signal at loop top.
            # CRITICAL: a SUCCESS pass ends one iteration of the main loop;
            # the resume_path (if any) was consumed during this pass, so
            # the next iteration must start fresh from Decompose. Clear it
            # before re-entering the child.
            bb.runner_resume_path = None
        # Defensive fallthrough
        bb.converge_signal = "interrupt"
        bb.interrupt_reason = bb.interrupt_reason or "loop_safety_cap_hit"
        return Status.SUCCESS


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
