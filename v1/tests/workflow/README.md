# Workflow Tests

[English](README.md) | [中文](README.zh-CN.md)

Architecture-verification tests for CBIM's four design loops — EXECUTION /
ARCHITECT / HR / MEMORY (see `design/WORKFLOW-*.zh-CN.md`). **Not a benchmark**:
the goal is to assert the coordinator drives the right loop on each prompt,
not to score model performance.

| Loop       | Positive                                       | Negative                                |
|------------|------------------------------------------------|-----------------------------------------|
| EXECUTION  | implement `greet(name)` + unit test            | one-sentence read of CLAUDE.md          |
| ARCHITECT  | `cbim dna init` a new `combat` leaf module     | list existing DNA modules (read-only)   |
| HR         | recruit a `frontend` agent                     | list existing agents (read-only)        |
| MEMORY     | "remember: hooks go in-process, not MCP"       | "你好" greeting                         |

Plus 5 **AUDIT** cases (one per registered check) — positive-only, since
audit is a cross-cutting concern that should always be honored when the user
asks for a governance check; there is no "should not call" semantics:

| Audit check        | Expected agent | Prompt summary                                |
|--------------------|----------------|-----------------------------------------------|
| `index_consistency`| architect      | check `.dna/index.md` matches actual modules  |
| `dna_tree`         | architect      | audit DNA dep graph (cycle / orphan / ancestor)|
| `dna_fission`      | architect      | flag DNA modules over body/workflow threshold |
| `agent_fission`    | hr             | flag agents over skill/body threshold         |
| `memory_threshold` | architect      | check memory compaction / promotion thresholds|

Each case is a real `claude` invocation against the real Anthropic API.
**A full 13-case run costs roughly $2–$15** and takes 5–15 minutes. CI does
not run them.

## Framework architecture

`framework/` is a reusable harness; the 13 static tests are its first user,
Phase 14b's A/B benchmark will be its second.

```
framework/
  target.py        TestTarget (Protocol) + TmpProject + ExternalProject
  runner.py        run(target, prompt, timeout) -> Result
  result.py        Result dataclass (exit, wall, tokens, session log, ...)
  log_assert.py    parse_log + Verdict + 5 assert_*_loop (4 loops + audit)
  stats.py         CaseStats + AggregateStats + aggregate(cases, group_fn)
  reporter.py      render_markdown / render_markdown_single / render_stdout
  generators/      PromptGenerator Protocol + registry (default: `static`)
```

Two target modes (anything implementing the `TestTarget` Protocol works):

- `TmpProject` — fresh CBIM install in a tempdir; setup/teardown per call
- `ExternalProject` — points at an existing project; setup/teardown are no-ops

Two prompt sources (anything implementing `PromptGenerator` works):

- `static` (default) — read a `.md` file
- *future* — dynamic generators registered the same way

## How to run

### 1. pytest (the 13 static cases)

```bash
ANTHROPIC_API_KEY=sk-... pytest v1/tests/workflow/ -m workflow -v

# one loop only
pytest v1/tests/workflow/test_loop_memory.py -m workflow -v

# one case only
pytest v1/tests/workflow/test_loop_memory.py::test_loop_memory_negative -m workflow -v
```

Auto-skip when `ANTHROPIC_API_KEY` is unset or `claude` is not on `PATH`.
Without `-m workflow`, no case is selected.

### 2. run-bench.sh (one-shot batch + report)

```bash
ANTHROPIC_API_KEY=sk-... ./v1/tests/workflow/run-bench.sh
```

Allocates the next `results/report-NNN.md` slot, runs all 13 cases, copies
each session log to `results/report-NNN/logs/`, and writes the markdown
report via `framework.reporter`.

### 3. CLI (one prompt against any project)

```bash
# Fresh tmp install + a prompt file
python -m v1.tests.workflow.cli run --prompt my-prompt.md

# Existing project on disk
python -m v1.tests.workflow.cli run \
  --project /path/to/some-cbim-project \
  --prompt my-prompt.md \
  --output run-report.md

# List registered prompt generators
python -m v1.tests.workflow.cli list-generators

# Just print a generated prompt (no claude call)
python -m v1.tests.workflow.cli generate --project /path --generator static --prompt foo.md
```

Use `--project` to skip the fresh-install path and point at an existing
on-disk CBIM project; nothing is cleaned up afterwards.

## Results & history

- `results/report-NNN.md` — committed to git (history is a project asset).
- `results/report-NNN/` — per-case session logs + raw pytest output;
  **gitignored** (volume + noise). See `.gitignore`.

Report numbering is monotonically increasing; never reused.

## Adding a new case

1. Drop a new prompt under `prompts/<loop>_<flavor>.md`.
2. Add a test function in `test_loop_<loop>.py` modeled after the existing two.
   Take the `workflow_target: TmpProject` fixture and call
   `framework.run(target, prompt)`.
3. If the assertion shape is new, extend the matching `assert_<loop>_loop`
   in `framework/log_assert.py`.

Keep prompts narrow: one verifiable behavior per case.

## Adding a new prompt generator

1. Write a class implementing the `PromptGenerator` Protocol (a `name`,
   `description`, and `generate(target) -> str`).
2. Call `framework.generators.register(my_generator)` at module import time
   (mirror `framework/generators/static.py`).
3. Surface it from `list-generators` automatically; the CLI `run --generator`
   path picks it up by name.
