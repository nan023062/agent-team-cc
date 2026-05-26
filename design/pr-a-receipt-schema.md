# PR-A — Work Agent Receipt Trailer Schema

**Scope:** Decision Point 1 (work agent receipt schema) + Side-finding 2 (arch_exec failure reason exposure).
**Out of scope:** Decision Point 2 (ConvergeJudge / loop-back), Decision Point 3 (FallbackPlan three-way split). Those land in PR-B and PR-C respectively.
**Status:** spec, ready for implementation.
**Owner:** architect (design) → programmer (implementation) → auditor (review).

---

## 1. Background and Positioning

Today every work agent's reply is dumped verbatim into `bb.work_results[task_id] = {"status": "ok", "output": text, "raw": …}` (`v1/kernel/engine/execution/actions/dispatch_work.py:48-59`). The `status` is hard-coded `"ok"`. As a result the engine cannot tell apart:

- a clean delivery,
- a programmer that escalated `NEEDS_ARCH_DECISION`,
- a programmer that needs the user to clarify,
- a programmer that gave up.

Downstream nodes (ConvergeJudge / re-dispatch / escalation) therefore have no machine-readable signal to branch on.

PR-A introduces a **physical receipt trailer**: a stable, append-only HTML-comment block at the end of every work agent reply. The trailer is the **sole contract** between work agents and the engine; everything before the trailer is human prose for the user.

This unblocks PR-B (ConvergeJudge needs a status enum to switch on) and PR-C (FallbackPlan three-way needs `arch_exec_failed_reason` to route).

---

## 2. Trailer Physical Format

### 2.1 Wire format

A single fenced block at the **absolute end** of the work agent's reply:

```
<!-- BEGIN CBIM-RECEIPT v1
status: <enum>
<field>: <value>
<field>: <value>
...
END CBIM-RECEIPT -->
```

Rules:

- **Sentinels are exact strings.** `<!-- BEGIN CBIM-RECEIPT v1` and `END CBIM-RECEIPT -->`. Version (`v1`) is part of the begin sentinel — a future v2 will not collide.
- **Block placement.** Must be the last non-whitespace content in the reply. Any text after the end sentinel is ignored by `parse_trailer`; a lint warning is logged.
- **Body format.** YAML-style `key: value` lines, one per line, no nesting, no multi-line values. Keys are lowercase snake_case.
- **Unknown keys** are preserved into `ReceiptTrailer.extras: dict[str, str]` and do not cause a parse error — forward-compatible by design.
- **Whitespace.** Leading/trailing whitespace inside values is stripped. Empty value is treated as missing.
- **Encoding.** UTF-8. Markdown content (e.g. backticks) inside values is fine because the host block is an HTML comment.

Why HTML comment, not fenced code block:
- Invisible to users reading the Markdown reply in any renderer (Claude Code, GitHub PR, IDE preview).
- Cannot be confused with a real code sample the user pasted.
- The `<!-- … -->` sentinels are uniquely matchable with a single regex — no ambiguity with nested code fences.

### 2.2 Status enum

Exactly four values. The set is closed; PR-B's ConvergeJudge will exhaustively switch on it.

| `status`                | Meaning                                                                 | Who triggers it                                                                       |
|-------------------------|-------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `ok`                    | Task finished, deliverable in the prose body above the trailer.         | Default success path.                                                                 |
| `needs_arch_decision`   | Work agent refuses to proceed because the spec / design is incomplete.  | Programmer hitting a missing module boundary, ambiguous contract, etc.                |
| `needs_user_input`      | Work agent needs a clarifying answer from the human user before acting. | Programmer cannot infer intent; question is for the human, not the architect.         |
| `failed`                | Work agent attempted the task and failed in an unrecoverable way.       | Build/test error the agent cannot fix; tool crash; out-of-scope environment failure.  |

Any other value is a parse error → see §4.4.

### 2.3 Per-status field table

Legend: **R** = required, **O** = optional, **—** = MUST be absent.

| field             | `ok` | `needs_arch_decision` | `needs_user_input` | `failed` | Description                                                                                  |
|-------------------|:----:|:---------------------:|:------------------:|:--------:|----------------------------------------------------------------------------------------------|
| `status`          |  R   |          R            |         R          |    R     | Enum, see §2.2.                                                                              |
| `task_id`         |  R   |          R            |         R          |    R     | Echoed verbatim from the dispatch (`subtask_id`). Lets the engine match reply ↔ leaf.        |
| `agent`           |  R   |          R            |         R          |    R     | Short agent slug, e.g. `programmer`. Matches `.claude/agents/<slug>/<slug>.md`.              |
| `summary`         |  R   |          R            |         R          |    R     | One-line human summary (≤ 200 chars). What was done / why escalating / what failed.          |
| `question`        |  —   |          R            |         R          |    —     | The exact question that needs answering. For `needs_arch_decision`, addressed to architect; for `needs_user_input`, addressed to the human. |
| `blocking_module` |  —   |          O            |         —          |    —     | Path of the `.dna/` module whose spec is insufficient (if any). Used by arch_exec re-entry.  |
| `failure_kind`    |  —   |          —            |         —          |    R     | One of `tool_error` / `test_failed` / `build_failed` / `timeout` / `other`.                  |
| `artifacts`       |  O   |          —            |         —          |    O     | Comma-separated list of file paths the agent created/edited. Informational; not parsed deeply. |

Notes:
- `task_id` is required on every status because the engine matches replies to leaves by task_id, not by dispatch order (work agents may be parallelized in a future tick).
- `question` on `needs_arch_decision` and `needs_user_input` is the canonical handoff payload — PR-B's ConvergeJudge / EscalateBranch will read it directly.
- `failure_kind` is deliberately small and closed. "Why" lives in `summary`. Granular taxonomy is YAGNI today.

### 2.4 Minimal complete samples (one per status)

**`ok`**

```
The Stop hook has been upgraded; tests pass.

<!-- BEGIN CBIM-RECEIPT v1
status: ok
task_id: t1
agent: programmer
summary: Stop hook now flushes pending dream_tick before exit; added two unit tests.
artifacts: .claude/hooks/cbim_stop.py, tests/hooks/test_cbim_stop.py
END CBIM-RECEIPT -->
```

**`needs_arch_decision`**

```
I cannot proceed. The receipt trailer schema is not specified in any .dna/ module, so I have no contract to implement against.

<!-- BEGIN CBIM-RECEIPT v1
status: needs_arch_decision
task_id: t1
agent: programmer
summary: Missing receipt trailer schema in execution/.dna/contract.md.
question: What are the required fields for status=failed? Does the trailer go inside or after the prose body?
blocking_module: v1/kernel/engine/execution
END CBIM-RECEIPT -->
```

**`needs_user_input`**

```
Two valid interpretations of "tidy up memory" exist; I need you to pick.

<!-- BEGIN CBIM-RECEIPT v1
status: needs_user_input
task_id: t1
agent: programmer
summary: "tidy up memory" is ambiguous.
question: Do you want (a) distill short → medium tier, or (b) archive all entries older than 30 days? Reply a or b.
END CBIM-RECEIPT -->
```

**`failed`**

```
The integration test suite crashed; the failure is reproducible but I cannot diagnose the root cause.

<!-- BEGIN CBIM-RECEIPT v1
status: failed
task_id: t1
agent: programmer
summary: pytest tests/engine/ segfaults on macOS in CI; runs fine locally.
failure_kind: test_failed
artifacts: tests/engine/conftest.py
END CBIM-RECEIPT -->
```

---

## 3. Backward Compatibility — Legacy Reply Handling

Old work agents and out-of-tree agents (e.g. ad-hoc subagents dispatched before this PR lands) will return replies **without any trailer**. The parser MUST NOT reject them — that would break every in-flight task.

### 3.1 Fallback rule

> **No trailer present → synthesize a `ReceiptTrailer` with `status="ok"`, `task_id` taken from the dispatch, `agent="unknown"`, `summary=""`, `extras={"_legacy": "no_trailer"}`.**

Rationale: the historical default was already "treat any reply as ok". The fallback preserves that behaviour exactly while flagging the entry as legacy so dashboards / logs can surface the migration debt without breaking flow.

### 3.2 Malformed trailer

If the BEGIN sentinel is found but the body cannot be parsed (unknown status enum, missing required field for the declared status, truncated block missing END sentinel), the parser MUST:

1. Log a warning to `bb.trace` with kind=`receipt_parse_error` and the raw block.
2. Return `ReceiptTrailer(status="failed", task_id=<from dispatch>, agent="unknown", summary="receipt parse error: <reason>", failure_kind="other", extras={"_raw": <raw block>})`.

This collapses malformed receipts into the `failed` path so ConvergeJudge (PR-B) handles them uniformly with real failures.

### 3.3 Multiple trailers

If two or more `BEGIN CBIM-RECEIPT v1` blocks appear, only the **last** one is parsed. The earlier blocks are kept in `extras["_shadowed_blocks"]` for debugging. This rule prevents a work agent from accidentally winning by writing the receipt twice with conflicting status.

---

## 4. Module: `receipt.py`

### 4.1 Location

```
v1/kernel/engine/execution/actions/receipt.py
```

Co-located with `dispatch_work.py` because it is the only consumer. Not promoted to a shared `engine/core/` utility until a second caller appears (YAGNI).

### 4.2 Public surface

```python
# v1/kernel/engine/execution/actions/receipt.py

from dataclasses import dataclass, field
from typing import Literal

ReceiptStatus = Literal["ok", "needs_arch_decision", "needs_user_input", "failed"]
FailureKind   = Literal["tool_error", "test_failed", "build_failed", "timeout", "other"]


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

    Contract:
      - `text` is the raw string returned by the Task tool.
      - `dispatch_task_id` is the task_id the engine dispatched (used for
        the legacy-fallback and parse-error paths where the trailer is
        absent or malformed and cannot supply its own task_id).
      - Always returns a ReceiptTrailer; never raises on user input.
        Hard failures (unparseable, schema-violating) are folded into
        status="failed" per §3.2.
    """
```

### 4.3 Parse algorithm (informative)

1. Scan `text` for the last occurrence of `<!-- BEGIN CBIM-RECEIPT v1` (regex `r"<!--\s*BEGIN\s+CBIM-RECEIPT\s+v1"`). If absent → §3.1 legacy fallback.
2. Find the matching `END CBIM-RECEIPT -->` after that position. If absent → §3.2 malformed.
3. Extract the body between BEGIN sentinel newline and END sentinel.
4. Parse each non-empty line as `key: value` (split on first `:`).
5. Validate `status` is in the four-value enum; otherwise §3.2 malformed.
6. Validate the per-status required field table (§2.3); missing required → §3.2 malformed.
7. Unknown keys → `extras`.
8. `artifacts` value is split on commas and whitespace-stripped.

### 4.4 What `parse_trailer` MUST NOT do

- MUST NOT raise.
- MUST NOT touch the network or filesystem.
- MUST NOT mutate `text`.
- MUST NOT call an LLM. (This is a deterministic parser; LLM-style fuzzy receipt parsing is explicitly rejected — auditor would gut it.)

---

## 5. `dispatch_work.py` — `on_resume` Changes

### 5.1 Current behaviour (to be replaced)

`v1/kernel/engine/execution/actions/dispatch_work.py:48-59`:

```python
def on_resume(self, bb, payload) -> None:
    text = payload if isinstance(payload, str) else (
        payload.get("output", "") if isinstance(payload, dict) else str(payload)
    )
    new_results = dict(bb.work_results or {})
    new_results[self.task_id] = {
        "status": "ok",
        "output": text,
        "raw": payload if not isinstance(payload, str) else None,
    }
    bb.work_results = new_results
    bb.pending_dispatch = None
```

### 5.2 New behaviour

```python
def on_resume(self, bb, payload) -> None:
    from .receipt import parse_trailer

    text = payload if isinstance(payload, str) else (
        payload.get("output", "") if isinstance(payload, dict) else str(payload)
    )
    trailer = parse_trailer(text, dispatch_task_id=self.task_id)

    new_results = dict(bb.work_results or {})
    new_results[self.task_id] = {
        "status": trailer.status,             # one of the four enum values
        "summary": trailer.summary,
        "question": trailer.question,
        "blocking_module": trailer.blocking_module,
        "failure_kind": trailer.failure_kind,
        "artifacts": list(trailer.artifacts),
        "agent": trailer.agent,
        "output": text,                       # full prose body kept for the user
        "extras": dict(trailer.extras),
        "raw": payload if not isinstance(payload, str) else None,
    }
    bb.work_results = new_results
    bb.pending_dispatch = None
```

### 5.3 Tick-time contract changes

`WorkAgentLeaf.tick` (lines 28-46) currently routes `status == "ok"` → SUCCESS and any other value → FAILURE. That stays correct for PR-A: `ok` → SUCCESS, `failed` / `needs_arch_decision` / `needs_user_input` → FAILURE. PR-B will replace the FAILURE bubble with a proper ConvergeJudge / EscalateBranch — but PR-A does **not** need to change `tick`. The status enum widening is contained inside `on_resume` and the `bb.work_results` schema.

This is the explicit seam that lets PR-A ship independently of PR-B.

### 5.4 Schema-version note

`bb.work_results[task_id]` is now an open-ended dict with a known field set. The Blackboard FIELDS tuple in `v1/kernel/engine/core/blackboard.py` is unchanged (work_results is already listed). No schema version bump required because the previous shape was `{"status", "output", "raw"}` — all three keys are preserved with identical semantics.

---

## 6. Side-finding 2 — `arch_exec_failed_reason`

### 6.1 Problem

When the architect-execution subtree fails (truncated LLM JSON, missing API key, malformed schema, …) the outer Selector silently swallows the failure and the deterministic `FallbackPlan` writes a one-task `programmer` plan (`v1/kernel/engine/execution/actions/arch_exec/fallback_plan.py:28-37`). From the session log it is impossible to tell **why** the architect path was skipped. PR-C (FallbackPlan three-way split) needs this signal to route correctly.

### 6.2 Solution

Each LLM-driven leaf in the architect-execution subtree (`scan`, `state_check`, `worth`, `create`, `extract`, `diff`, `validate`, `map_tasks`, `assemble`) MUST, on FAILURE return, write `bb.arch_exec_failed_reason` exactly once with one of the four enum values below. `FallbackPlan.tick` reads the field; if absent it writes `"unknown"`.

### 6.3 Enum

| Value                    | When                                                                                            |
|--------------------------|-------------------------------------------------------------------------------------------------|
| `no_llm`                 | LLM client is `NullLLM` / no API key configured / connectivity probe failed before first call.  |
| `llm_truncated`          | LLM call returned but the response was truncated (max_tokens hit, EOF mid-JSON, etc.).           |
| `llm_parse_error`        | LLM call returned a complete response but it was not valid JSON / did not match the leaf schema. |
| `internal_error`         | Anything else — exception inside the leaf, missing input field, blackboard precondition unmet.  |

Closed set. Any future addition requires a PR-A amendment.

### 6.4 Storage

`arch_exec_failed_reason` is **not** added to the canonical Blackboard FIELDS tuple. It is a transient diagnostic field, written to `bb.__dict__` via the existing scratch-field mechanism (`v1/kernel/engine/core/blackboard.py:78-85` explicitly permits this). This avoids a schema_version bump.

PR-C will lift it to a first-class FIELDS entry if and only if the three-way fallback needs to persist it across resume.

### 6.5 Logging

In addition to writing the bb field, each failing leaf MUST append a `bb.trace` entry with kind=`arch_exec_failed` and the same reason, so session post-mortems are possible without rebuilding the blackboard.

---

## 7. Skill: `work.receipt_trailer`

### 7.1 Purpose

Every work-class agent (today: `programmer`; tomorrow: any agent recruited by HR for execution work) needs to know **how to write the trailer**. The skill is the single source of truth that the agent's `.md` system prompt points to.

### 7.2 Location and filename

Following the repo convention (`v1/kernel/cbi/agents/<agent>/skills/<skill>/skill.py` per `v1/kernel/cbi/agents/architect/skills/arch_modules/`), and because the trailer is shared across **all** work agents — not specific to programmer — the skill lives under a new shared work-class skill bucket:

```
v1/kernel/cbi/agents/work/skills/receipt_trailer/
├── __init__.py
└── skill.py
```

- The `work` directory is a new sibling of `architect`, `hr`, `programmer`. It holds skills shared by every agent whose `agent_type` is `"work"` in dispatch (currently only programmer, but the field is plural by design).
- The skill key, as exposed by `cbim skill show`, is **`work.receipt_trailer`** (agent_dir `.` skill_name).
- `skill.py` content is the canonical write-side spec: the four status enums, the field table from §2.3, and the four samples from §2.4. It is the mirror image of `receipt.py` (read-side parser).

### 7.3 Agent prompt wiring

`.claude/agents/programmer/programmer.md` gains a new line in its skills table:

| Scenario | Run |
|----------|-----|
| Closing out any dispatched task | `cbim skill show work.receipt_trailer` |

When HR recruits new work agents post-PR-A, the recruitment template must include this row by default. (HR template update is tracked separately, outside PR-A scope, but noted here so it is not lost.)

---

## 8. Acceptance Criteria

### 8.1 Static checks (grep-able)

Each of the following commands MUST return the indicated result on the final PR-A diff:

1. Trailer sentinel exists exactly twice in code (parser + skill):
   ```
   rg -n "BEGIN CBIM-RECEIPT v1" v1/ .claude/
   ```
   Expect: 1 hit in `v1/kernel/engine/execution/actions/receipt.py`, 1+ hits in `v1/kernel/cbi/agents/work/skills/receipt_trailer/skill.py` (samples). No other locations.

2. The old hard-coded `"status": "ok"` is gone from `dispatch_work.py`:
   ```
   rg -n '"status": "ok"' v1/kernel/engine/execution/actions/dispatch_work.py
   ```
   Expect: 0 hits.

3. The four status enums are defined in exactly one place:
   ```
   rg -n 'needs_arch_decision' v1/
   ```
   Expect: hits only in `receipt.py`, the skill, and tests. No stringly-typed usage elsewhere.

4. `arch_exec_failed_reason` is written by every LLM-driven leaf:
   ```
   rg -n 'arch_exec_failed_reason' v1/kernel/engine/execution/actions/arch_exec/
   ```
   Expect: ≥ 9 hits (one per leaf: scan / state_check / worth / create / extract / diff / validate / map_tasks / assemble) plus 1 read in `fallback_plan.py`.

5. Programmer agent prompt references the skill:
   ```
   rg -n 'work.receipt_trailer' .claude/agents/programmer/programmer.md
   ```
   Expect: ≥ 1 hit.

### 8.2 Unit tests required

New file `tests/engine/execution/actions/test_receipt.py` (path mirrors source). Mandatory cases:

| # | Case                                                                  | Assertion                                                                                |
|---|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| 1 | Each of the four §2.4 samples parses cleanly                          | `status`, required fields populated; `extras` empty; no warnings.                        |
| 2 | Legacy reply (no trailer, just prose)                                 | Returns `status="ok"`, `agent="unknown"`, `extras["_legacy"] == "no_trailer"`.           |
| 3 | Trailer with unknown status value                                     | Returns `status="failed"`, `failure_kind="other"`, summary contains `"parse error"`.      |
| 4 | Trailer missing `question` when status=`needs_arch_decision`          | Returns `status="failed"` per §3.2.                                                       |
| 5 | Two trailer blocks back-to-back                                       | The **last** block wins; first block kept in `extras["_shadowed_blocks"]`.                |
| 6 | Trailer with unknown extra key `foo: bar`                             | `extras["foo"] == "bar"`; status still parses cleanly.                                    |
| 7 | Trailer present but truncated (no END sentinel)                       | Returns `status="failed"` per §3.2; raw block in `extras["_raw"]`.                        |
| 8 | `artifacts: a.py, b.py , c.py` (whitespace + trailing)                | Parsed as `("a.py", "b.py", "c.py")`.                                                     |
| 9 | Trailing prose after END sentinel                                     | Parser ignores trailing prose; warning logged.                                            |

New file `tests/engine/execution/actions/test_dispatch_work_receipt.py`. Mandatory cases:

| #  | Case                                                                  | Assertion                                                                                |
|----|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| 10 | `on_resume` with a clean `ok` reply                                   | `bb.work_results["t1"]["status"] == "ok"`, `summary` populated, `tick` returns SUCCESS.   |
| 11 | `on_resume` with `needs_arch_decision` reply                          | `bb.work_results["t1"]["status"] == "needs_arch_decision"`, `question` populated, `tick` returns FAILURE. |
| 12 | `on_resume` with `failed` reply                                       | `failure_kind` populated; `tick` returns FAILURE.                                         |
| 13 | `on_resume` with legacy (no trailer) reply                            | Equivalent to case 10 — backward compatible.                                              |

New file `tests/engine/execution/actions/arch_exec/test_failed_reason.py`. Mandatory cases:

| #  | Case                                                                  | Assertion                                                                                |
|----|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| 14 | NullLLM injected → each of the 9 leaves runs in isolation             | Each leaf's FAILURE writes `bb.arch_exec_failed_reason == "no_llm"`.                      |
| 15 | LLM stub returns truncated JSON                                       | Leaf writes `"llm_truncated"`.                                                            |
| 16 | LLM stub returns valid JSON failing schema                            | Leaf writes `"llm_parse_error"`.                                                          |
| 17 | LLM stub raises a Python exception                                    | Leaf writes `"internal_error"`.                                                           |
| 18 | `FallbackPlan.tick` after a leaf failure                              | `bb.arch_exec_failed_reason` preserved; `bb.trace` contains kind=`arch_exec_failed` entry. |

### 8.3 Non-regression

- Full existing test suite passes unchanged.
- `bb.work_results` schema version is **not** bumped (additive only — old keys preserved).
- Blackboard FIELDS tuple in `core/blackboard.py` is **not** modified.

---

## 9. Out of Scope (deferred to PR-B / PR-C)

The following are explicitly **not** in PR-A and MUST NOT be touched:

- `WorkAgentLeaf.tick` routing logic (PR-B will replace the binary SUCCESS/FAILURE with ConvergeJudge).
- Re-dispatch / loop-back when status is `needs_arch_decision` (PR-B).
- ESCALATE branch to architect or user (PR-B).
- FallbackPlan splitting into three branches based on `arch_exec_failed_reason` (PR-C).
- Any change to `ModeClassify` or `mode_classify` rule table (separate PR).
- HR recruitment template update for new work agents (separate PR; mentioned in §7.3 for traceability only).

PR-A is intentionally a pure plumbing PR: it introduces the contract and the parser, switches one writer (`on_resume`), and exposes one diagnostic field (`arch_exec_failed_reason`). Nothing in this PR changes the engine's control flow.

---

## 10. Implementation Order (suggested)

1. `receipt.py` + `tests/engine/execution/actions/test_receipt.py` — pure unit, no engine coupling. Land first; review independently.
2. Wire `dispatch_work.on_resume` to call `parse_trailer`; add `test_dispatch_work_receipt.py`. The `tick` behaviour stays binary (ok=SUCCESS, anything else=FAILURE) — verified by tests 10–13.
3. Add `arch_exec_failed_reason` writes to each of the 9 arch_exec leaves; add `test_failed_reason.py`.
4. Create the `work.receipt_trailer` skill module and update `.claude/agents/programmer/programmer.md` skills table.
5. Run the §8.1 grep checks; fix any drift.

End of PR-A spec.
