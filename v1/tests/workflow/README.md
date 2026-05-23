# Workflow End-to-End Tests

End-to-end tests for CBIM's four design loops, defined in `design/WORKFLOW-*.zh-CN.md`:

| Loop       | Positive case                                  | Negative case                          |
|------------|------------------------------------------------|----------------------------------------|
| EXECUTION  | implement `greet(name)` + unit test            | one-sentence read of CLAUDE.md         |
| ARCHITECT  | `cbim dna init` a new `combat` leaf module     | list existing DNA modules (read-only)  |
| HR         | recruit a `frontend` agent                     | list existing agents (read-only)       |
| MEMORY     | "remember: hooks go in-process, not MCP"       | "你好" greeting                        |

## How it works

Each test:

1. Copies a freshly-installed CBIM project (`engine init` + `.cbim/kernel/` copy) from a session-scoped template into a per-test tempdir.
2. Runs `claude -p '<prompt>'` in that tempdir; the project's `.claude/settings.json` carries `defaultMode = bypassPermissions`, so no extra flags are needed.
3. Reads the latest `.cbim/logs/session_*.log` and asserts the right `[CBIM:agent]` / `[CBIM:dna|agent|memory]` / `[CALL]` patterns appeared (or, for negative cases, did not appear).

The assertion DSL lives in `log_assert.py`.

## Why these are off by default

Each case is a real `claude` invocation against a real Anthropic API, ~$0.10 – $1.00 per case and 1–10 minutes wall time. CI does not run them.

Auto-skip conditions (set in `conftest.py`):

- `ANTHROPIC_API_KEY` not in env → skip
- `claude` CLI not on `PATH`     → skip
- pytest invoked without `-m workflow` → not collected by selection

## Run it

```bash
# all 8 cases
ANTHROPIC_API_KEY=sk-... pytest v1/tests/workflow/ -m workflow -v

# just one loop
pytest v1/tests/workflow/test_loop_memory.py -m workflow -v

# just one case
pytest v1/tests/workflow/test_loop_memory.py::test_loop_memory_negative -m workflow -v
```

Collection-only sanity check (no spend):

```bash
pytest v1/tests/workflow/ --collect-only
```

## Adding a new case

1. Drop a new prompt under `prompts/<loop>_<flavor>.md`.
2. Add a test function in `test_loop_<loop>.py` modeled after the existing two.
3. If the assertion shape is new, extend the matching `assert_<loop>_loop` in `log_assert.py`.

Keep prompts narrow: one verifiable behavior per case. Wide prompts produce wide logs and flaky asserts.
