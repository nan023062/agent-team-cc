"""actions/receipt.py — Parse the receipt trailer at the end of a work agent reply.

Wire format (PR-A spec §2.1):

    <!-- BEGIN CBIM-RECEIPT v1
    status: <enum>
    <key>: <value>
    ...
    END CBIM-RECEIPT -->

Closed status enum: ``ok`` / ``needs_arch_decision`` / ``needs_user_input`` /
``failed``. Per-status required fields per spec §2.3.

Hard contract: ``parse_trailer`` never raises and never touches the
filesystem / network / LLM. Malformed input collapses into a synthesized
``status="failed"`` ReceiptTrailer per spec §3.2; absent trailer collapses
into ``status="ok"`` legacy fallback per spec §3.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


ReceiptStatus = Literal["ok", "needs_arch_decision", "needs_user_input", "failed"]
FailureKind = Literal["tool_error", "test_failed", "build_failed", "timeout", "other"]


_VALID_STATUSES: frozenset[str] = frozenset(
    {"ok", "needs_arch_decision", "needs_user_input", "failed"}
)
_VALID_FAILURE_KINDS: frozenset[str] = frozenset(
    {"tool_error", "test_failed", "build_failed", "timeout", "other"}
)

# Sentinels are exact strings; the regex tolerates internal whitespace.
_BEGIN_RE = re.compile(r"<!--\s*BEGIN\s+CBIM-RECEIPT\s+v1")
_END_RE = re.compile(r"END\s+CBIM-RECEIPT\s*-->")

# Per-status required fields beyond the four always-required (status,
# task_id, agent, summary). See spec §2.3.
_PER_STATUS_REQUIRED: dict[str, tuple[str, ...]] = {
    "ok": (),
    "needs_arch_decision": ("question",),
    "needs_user_input": ("question",),
    "failed": ("failure_kind",),
}

_ALWAYS_REQUIRED: tuple[str, ...] = ("task_id", "agent", "summary")

# Fields recognized in the body; everything else lands in extras.
_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "status",
        "task_id",
        "agent",
        "summary",
        "question",
        "blocking_module",
        "failure_kind",
        "artifacts",
    }
)


@dataclass(frozen=True)
class ReceiptTrailer:
    status: ReceiptStatus
    task_id: str
    agent: str
    summary: str
    question: str | None = None
    blocking_module: str | None = None
    failure_kind: FailureKind | None = None
    artifacts: tuple[str, ...] = ()
    extras: dict[str, str] = field(default_factory=dict)

    def is_terminal_ok(self) -> bool:
        return self.status == "ok"


def parse_trailer(text: str, *, dispatch_task_id: str) -> ReceiptTrailer:
    """Parse a work agent reply and extract the receipt trailer.

    Always returns a ReceiptTrailer; never raises. See module docstring for
    the contract.
    """
    if text is None:
        text = ""

    begin_matches = list(_BEGIN_RE.finditer(text))
    if not begin_matches:
        # Spec §3.1 — legacy fallback (no trailer present).
        return ReceiptTrailer(
            status="ok",
            task_id=dispatch_task_id,
            agent="unknown",
            summary="",
            extras={"_legacy": "no_trailer"},
        )

    # Spec §3.3 — only the last block wins; earlier blocks are shadowed.
    last_begin = begin_matches[-1]
    shadowed_blocks: list[str] = []
    if len(begin_matches) > 1:
        for prev in begin_matches[:-1]:
            shadowed_blocks.append(_extract_block(text, prev.start()))

    body_start = last_begin.end()
    end_match = _END_RE.search(text, body_start)
    if end_match is None:
        # Spec §3.2 — truncated / missing END sentinel.
        raw_block = text[last_begin.start():]
        return _malformed(
            dispatch_task_id,
            reason="missing END sentinel",
            raw_block=raw_block,
            shadowed=shadowed_blocks,
        )

    body = text[body_start:end_match.start()]
    trailing = text[end_match.end():].strip()
    # NB: trailing prose is tolerated per spec §2.1 but flagged via extras
    # so dashboards can surface it without breaking flow.

    fields_parsed, extras = _parse_body(body)

    status_raw = fields_parsed.get("status")
    if status_raw not in _VALID_STATUSES:
        return _malformed(
            dispatch_task_id,
            reason=f"unknown status {status_raw!r}",
            raw_block=text[last_begin.start():end_match.end()],
            shadowed=shadowed_blocks,
        )

    # Required-field presence per status.
    missing: list[str] = []
    for f in _ALWAYS_REQUIRED:
        if not fields_parsed.get(f):
            missing.append(f)
    for f in _PER_STATUS_REQUIRED[status_raw]:
        if not fields_parsed.get(f):
            missing.append(f)
    if missing:
        return _malformed(
            dispatch_task_id,
            reason=f"missing required field(s): {', '.join(missing)}",
            raw_block=text[last_begin.start():end_match.end()],
            shadowed=shadowed_blocks,
        )

    # failure_kind enum check (only meaningful when present).
    failure_kind_raw = fields_parsed.get("failure_kind")
    if failure_kind_raw is not None and failure_kind_raw not in _VALID_FAILURE_KINDS:
        return _malformed(
            dispatch_task_id,
            reason=f"unknown failure_kind {failure_kind_raw!r}",
            raw_block=text[last_begin.start():end_match.end()],
            shadowed=shadowed_blocks,
        )

    artifacts_tuple = _parse_artifacts(fields_parsed.get("artifacts"))

    if shadowed_blocks:
        extras["_shadowed_blocks"] = "\n---\n".join(shadowed_blocks)
    if trailing:
        extras["_trailing_after_end"] = trailing[:500]

    return ReceiptTrailer(
        status=status_raw,  # type: ignore[arg-type]
        task_id=fields_parsed["task_id"],
        agent=fields_parsed["agent"],
        summary=fields_parsed["summary"],
        question=fields_parsed.get("question"),
        blocking_module=fields_parsed.get("blocking_module"),
        failure_kind=failure_kind_raw,  # type: ignore[arg-type]
        artifacts=artifacts_tuple,
        extras=extras,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _parse_body(body: str) -> tuple[dict[str, str], dict[str, str]]:
    """Parse the receipt body into (known fields, extras).

    Supports multi-line continuation values: a line whose first non-whitespace
    token is NOT ``<known-or-prior-key>:`` is appended to the current field's
    value buffer (preserving its newline so JSON-encoded values survive
    pretty-printing). The continuation rule is keyed on "unknown prefix", not
    "no colon" — JSON object keys contain colons.
    """
    fields_parsed: dict[str, str] = {}
    extras: dict[str, str] = {}
    # Insertion order: each entry is (bucket, key) where bucket is the dict
    # that owns the value. Used to append continuation lines to whichever
    # field was last opened.
    last_bucket: dict[str, str] | None = None
    last_key: str | None = None

    for raw_line in body.splitlines():
        if _looks_like_new_field(raw_line):
            line = raw_line.strip()
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if not key:
                # Defensive; _looks_like_new_field already filtered this.
                continue
            bucket = fields_parsed if key in _KNOWN_FIELDS else extras
            bucket[key] = value
            last_bucket = bucket
            last_key = key
        else:
            # Continuation line — append raw (with newline) to the active
            # field's buffer. Blank lines inside a multi-line value are
            # preserved; stray lines before any field is opened are dropped.
            if last_bucket is None or last_key is None:
                continue
            current = last_bucket[last_key]
            # Append the line verbatim, separated by a newline. JSON parsers
            # ignore internal whitespace, so this round-trips cleanly.
            last_bucket[last_key] = current + "\n" + raw_line

    return fields_parsed, extras


# A trailer field name is an identifier-shaped prefix: ASCII letters,
# digits, and underscore, starting with a letter or underscore. Anything
# else before the first ``:`` (e.g. ``"id"`` with quotes, ``{"id"``, or
# ``  - "field"``) is JSON / prose detritus and treated as continuation,
# not a new field. This is what makes pretty-printed JSON values
# (``arch_plan``) round-trip cleanly: their internal ``"key":`` lines all
# start with a quote, so they never look like trailer fields.
_FIELD_PREFIX_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:")


def _looks_like_new_field(raw_line: str) -> bool:
    """True iff ``raw_line`` opens a new ``key: value`` field rather than
    continues the previous one.

    Rule: after stripping leading whitespace, the line must begin with an
    identifier followed by ``:``. Lines that don't (blank lines, prose,
    JSON-internal ``"key":`` lines, ``- "x"`` array items, closing ``]``,
    etc.) are continuations of the currently-open field. A known field
    name or a previously-seen extras key is always an identifier, so they
    satisfy the rule by construction — the unknown-prefix case the spec
    cares about (an ``agent:`` line embedded inside a multi-line value)
    is also handled correctly: ``agent`` is an identifier, so it opens a
    new field.
    """
    line = raw_line.lstrip()
    if not line:
        return False
    return _FIELD_PREFIX_RE.match(line) is not None


def _parse_artifacts(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    items = [p.strip() for p in raw.split(",")]
    return tuple(p for p in items if p)


def _extract_block(text: str, begin_pos: int) -> str:
    """Slice from the BEGIN match to the next END (or EOF) for shadowing."""
    end_m = _END_RE.search(text, begin_pos)
    if end_m is None:
        return text[begin_pos:]
    return text[begin_pos:end_m.end()]


def _malformed(
    dispatch_task_id: str,
    *,
    reason: str,
    raw_block: str,
    shadowed: list[str],
) -> ReceiptTrailer:
    extras: dict[str, str] = {"_raw": raw_block}
    if shadowed:
        extras["_shadowed_blocks"] = "\n---\n".join(shadowed)
    return ReceiptTrailer(
        status="failed",
        task_id=dispatch_task_id,
        agent="unknown",
        summary=f"receipt parse error: {reason}",
        failure_kind="other",
        extras=extras,
    )
