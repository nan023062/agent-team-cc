SKILL: str = """\
# Skill: Receipt Trailer (Work Agents)

> Every dispatched task closes with a **receipt trailer** at the end of your
> reply. The trailer is the *only* machine-readable contract between you and
> the engine — everything before it is human prose for the user.

This skill is the write-side spec. The matching read-side parser lives in
`v1/kernel/engine/execution/actions/receipt.py`; the two MUST stay in lock-step.

---

## Wire format

A single block, the **absolute last** non-whitespace content of your reply:

```
<!-- BEGIN CBIM-RECEIPT v1
status: <enum>
<field>: <value>
<field>: <value>
END CBIM-RECEIPT -->
```

Rules:

- Sentinels are exact strings — `<!-- BEGIN CBIM-RECEIPT v1` and `END CBIM-RECEIPT -->`. Do not paraphrase.
- One `key: value` per line, lowercase snake_case keys, no nesting, no multi-line values.
- UTF-8. Backticks / Markdown inside values are fine (the host block is an HTML comment).
- Anything you write *after* the END sentinel is ignored by the engine. Don't put your real reply down there.
- Two trailers in one reply → only the **last** one is read. Don't write two.

---

## The four statuses (closed enum)

| `status`                | Meaning                                                                 | When                                                                                  |
|-------------------------|-------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `ok`                    | Task finished. Deliverable is the prose body above the trailer.         | Default success path.                                                                 |
| `needs_arch_decision`   | Spec / design is incomplete; you cannot proceed without an architect.   | Missing module boundary, ambiguous contract, gap in `.dna/`.                          |
| `needs_user_input`      | You need a clarifying answer from the **human user** before acting.     | Cannot infer intent; the question is for the human, not the architect.                |
| `failed`                | You attempted the task and failed in an unrecoverable way.              | Build / test error you cannot fix; tool crash; environment failure outside your scope.|

Any other value is a parse error — the engine will collapse it to `failed`.

---

## Required fields per status

Legend: **R** = required, **O** = optional, **—** = MUST be absent.

| field             | `ok` | `needs_arch_decision` | `needs_user_input` | `failed` | Description                                                                                  |
|-------------------|:----:|:---------------------:|:------------------:|:--------:|----------------------------------------------------------------------------------------------|
| `status`          |  R   |          R            |         R          |    R     | Enum, see table above.                                                                       |
| `task_id`         |  R   |          R            |         R          |    R     | Echo the `subtask_id` you were dispatched with. Required so the engine matches reply ↔ leaf. |
| `agent`           |  R   |          R            |         R          |    R     | Your agent slug, e.g. `programmer`.                                                          |
| `summary`         |  R   |          R            |         R          |    R     | One-line human summary (≤ 200 chars). What you did / why you're escalating / what failed.    |
| `question`        |  —   |          R            |         R          |    —     | The exact question that needs answering. Addressed to architect or to the human respectively.|
| `blocking_module` |  —   |          O            |         —          |    —     | Path of the `.dna/` module whose spec is insufficient (if any).                              |
| `failure_kind`    |  —   |          —            |         —          |    R     | One of `tool_error` / `test_failed` / `build_failed` / `timeout` / `other`.                  |
| `artifacts`       |  O   |          —            |         —          |    O     | Comma-separated file paths you created / edited. Informational.                              |

Unknown extra fields are preserved into `extras` and do not break parsing — so
forward-compatible additions are safe. Required fields missing → the engine
collapses your reply to `status=failed` with `failure_kind=other`.

---

## Samples — one per status

### `ok`

```
The Stop hook now flushes the pending dream tick before exit. Two unit tests
cover the new path; the full suite passes.

<!-- BEGIN CBIM-RECEIPT v1
status: ok
task_id: t1
agent: programmer
summary: Stop hook now flushes pending dream_tick before exit; added two unit tests.
artifacts: .claude/hooks/cbim_stop.py, tests/hooks/test_cbim_stop.py
END CBIM-RECEIPT -->
```

### `needs_arch_decision`

```
I cannot proceed. The receipt trailer schema is not specified in any .dna/
module, so I have no contract to implement against.

<!-- BEGIN CBIM-RECEIPT v1
status: needs_arch_decision
task_id: t1
agent: programmer
summary: Missing receipt trailer schema in execution/.dna/contract.md.
question: What are the required fields for status=failed? Does the trailer go inside or after the prose body?
blocking_module: v1/kernel/engine/execution
END CBIM-RECEIPT -->
```

### `needs_user_input`

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

### `failed`

```
The integration test suite crashed; the failure is reproducible but I cannot
diagnose the root cause.

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

## Common mistakes

- **Forgetting the trailer entirely.** The engine will treat your reply as a legacy `ok` — your status will silently misclassify if you actually failed.
- **Putting the trailer in the middle of the reply.** Only the *last* trailer is read; trailing prose after END is ignored.
- **Multi-line values.** Not supported. Collapse to one line; if you really need detail, put it in the prose body above and keep `summary` short.
- **Made-up `status` values** (`partial`, `blocked`, `pending`). The enum is closed at four values. Pick the closest match; use `summary` to explain nuance.
- **Skipping `task_id`.** The engine matches replies to leaves by `task_id`, not dispatch order. Always echo it.
"""
