"""core/_trace_utils.py — Shared trace-emission helpers for BT nodes.

Extracted from ``core/runner.py`` so composite nodes (SwitchBranch, Selector,
etc.) can emit decision events into ``bb.trace`` without circular-importing
the Runner. The behavior is byte-identical to the original Runner-internal
helpers; only the home moved.

Both helpers are best-effort: they never raise into the caller, because
trace is observational and must not break a tick.

In debug mode (CBIM_DEBUG=1 or `.cbim/.debug` present), every event written
to ``bb.trace`` is *additionally* mirrored to the current session log under
the ``[BT]`` tag — same data, plain text, grep-friendly. This is purely
additive: the bb.trace / _trace_flushed_idx / trace.jsonl pipeline is
unchanged. The session-log write is best-effort and never propagates errors.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _now_iso_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# Fields rendered as the bareword "header" of a session-log line. Everything
# else in the event dict becomes "key=value" tail tokens. `ts` is dropped —
# the logger stamps its own timestamp on every line.
_BT_HEADER_KEYS = ("event", "node")
_BT_SKIP_KEYS = frozenset({"ts"})


def _format_bt_line(event: dict) -> str:
    """Render a trace event as a single grep-friendly line.

    Shape: ``<event> <node> key1=val1 key2=val2 ...``
    Missing event/node falls back to ``?``. Values are coerced to str and
    inline-quoted only when they contain a space.
    """
    head_parts: list[str] = []
    for k in _BT_HEADER_KEYS:
        head_parts.append(str(event.get(k, "?")))
    tail_parts: list[str] = []
    for k, v in event.items():
        if k in _BT_HEADER_KEYS or k in _BT_SKIP_KEYS:
            continue
        s = str(v)
        if " " in s:
            s = f'"{s}"'
        tail_parts.append(f"{k}={s}")
    if tail_parts:
        return " ".join(head_parts) + " " + " ".join(tail_parts)
    return " ".join(head_parts)


def _mirror_to_session_log(event: dict) -> None:
    """Best-effort: in debug mode, mirror the event to session_*.log as [BT].

    Lazy-imports engine.debug + engine.logger to keep this module pure
    (no top-level coupling to context / logger / session-file lifecycle).
    Any failure — import error, missing .cbim, logger glitch — is swallowed;
    trace mirroring must never break a tick.
    """
    try:
        from engine.debug import is_debug
        if not is_debug():
            return
        from engine.logger import append as _log_append
        _log_append("BT", _format_bt_line(event))
    except Exception:
        pass


def _append_trace_event(bb, event: dict) -> None:
    """Best-effort append to bb.trace. Silently no-ops if bb has no trace.

    Uses object.__setattr__ to avoid dirtying canonical FIELDS (the bb's
    ``trace`` already lives in FIELDS, so direct assignment would tick the
    dirty flag once per node tick — undesirable churn). We mutate the
    existing list in place instead; the Runner snapshots bb on dirty
    boundaries anyway and bb.trace is captured by reference in to_dict.

    In debug mode the same event is additionally mirrored to the session
    log as a ``[BT]`` line. The mirror is independent of the bb.trace
    append — even if bb has no trace list (foreign blackboard), the
    session-log mirror still fires, because it is the human-readable
    audit channel and does not depend on bb state.
    """
    try:
        events = bb.trace
        if isinstance(events, list):
            events.append(event)
    except (AttributeError, TypeError):
        pass
    _mirror_to_session_log(event)
