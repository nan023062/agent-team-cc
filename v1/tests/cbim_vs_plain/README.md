# CBIM vs Plain Agent Benchmark

[English](README.md) | [中文](README.zh-CN.md)

A controlled A/B comparison: the exact same set of coding tasks run twice — once
against **plain `claude -p`** (no CBIM, no agents, no MCP, no hooks) and once
against a **CBIM-installed** copy of the same project. Produces a side-by-side
data table suitable for blog posts, READMEs, and decision memos.

## Why this exists

The other benchmark in this repo (`v1/benchmark/agent-team/`) measures
CBIM-vs-CBIM permutations (different model mixes). This one is the missing
baseline: **does CBIM actually help vs. an unenhanced agent?** Same prompts,
same fixture, two configurations.

## Quick start

```bash
ANTHROPIC_API_KEY=sk-... ./v1/tests/cbim_vs_plain/run-bench.sh
```

Output:
- `results/report-NNN.md` — side-by-side markdown table
- `results/report-NNN/` — captured session logs (one per task per mode)

A full run is **5–15 minutes** of wall time and roughly **\$5–\$20** in API
cost (5 tasks × 2 modes = 10 `claude` invocations).

## What gets measured

Per task, in each mode:

| Metric | How | Why it matters |
|---|---|---|
| Success | `success_check(project_root)` — objective, file-based | Did the agent actually accomplish the task? |
| Wall time | `time.perf_counter()` around `claude -p` | Latency cost of CBIM overhead |
| Input / output tokens | `claude -p --output-format json` | Token-economy cost of CBIM overhead |
| Code lines added / removed | diff vs. fixture baseline (`.py` files in `src/` and `tests/`) | Surface area of the change |
| Dispatch count | heuristic scan of session log for subagent invocations | "Architecture stability" — is CBIM routing as designed? |
| `.dna/` reads | heuristic scan of session log for `.dna/` paths | Is the architect actually consulting knowledge? |
| Turn count | structural markers in session log | Iteration shape |

All heuristics are applied identically to both modes. Plain mode produces zero
dispatches and zero `.dna/` reads by construction (no `.cbim/` exists in the
fixture copy); CBIM mode shows whatever the installed agents actually do.

## Repo layout

```
v1/tests/cbim_vs_plain/
├── README.md          (this file)
├── run-bench.sh       one-shot driver
├── runner.py          A/B orchestration (plain + cbim modes per task)
├── runner_cli.py      CLI: discover tasks, loop, write report
├── _report.py         render_ab_markdown() — side-by-side table
├── fixture/           shared toy Python project (calculator + parser)
│   ├── src/calculator.py
│   ├── src/parser.py
│   ├── tests/test_calculator.py
│   └── README.md
├── tasks/             one file per task
│   ├── _common.py     shared arch-metrics extractor + diff helper
│   ├── task_a.py      fix divide-by-zero bug
│   ├── task_b.py      add eval() to parser
│   ├── task_c.py      add new validator module
│   ├── task_d.py      cross-module refactor: common error hierarchy
│   └── task_e.py      pure explanation task (no code change)
└── results/
    ├── report-001.md
    └── report-001/    session logs for run 001
```

## How to read the report

Each report has three sections:

1. **Run** — when, what, how many tasks
2. **Per-task side-by-side** — every (task, mode) pair on its own row, so you
   can see per-task variance, not just averages
3. **Summary** — averages across all tasks with a `Delta` column

A useful CBIM story looks like:
- Success column: CBIM ≥ plain (especially on cross-module tasks D)
- Wall / tokens columns: CBIM > plain (overhead is real)
- Dispatch / `.dna` reads: CBIM > 0 on requirement-type tasks, ≈ 0 on task_e
  (pure query); plain = 0 on all of them
- Code lines: CBIM typically writes a bit more (better test coverage,
  defensive code) — track to confirm

## Adding a new task

Create `tasks/task_<x>.py`. It must export three names:

```python
NAME = "task_x"

PROMPT = """\
Natural-language task description for claude.
Should reference fixture files by their actual paths (e.g. `src/calculator.py`).
"""

def success_check(project_root: Path) -> bool:
    """Return True iff the task was accomplished. File-based, deterministic."""
    ...

def arch_metrics_extract(result, project_root, baseline_root) -> dict:
    """Return per-task architectural-stability metrics."""
    from ._common import base_arch_metrics
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
```

Optionally also export `stdout_check(stdout: str) -> bool` for tasks whose
answer lives in the model's textual reply rather than on disk (see
`tasks/task_e.py`).

The runner auto-discovers any `tasks/task_*.py`; no registry to update.

## Caveats

- Heuristic metrics (`dispatch_count`, `dna_read_count`, `turn_count`) read the
  CBIM session log, which is not a contract — the format may evolve. Same
  heuristic is applied to both modes, so any drift biases both sides equally.
- Plain mode has no session log (no `.cbim/`), so its heuristic counts are
  always zero. That's correct: plain `claude -p` has no subagents to dispatch.
- Token counts depend on `claude -p --output-format json` exposing them. If
  the CLI changes the JSON shape, tokens may show as `?` in the report. See
  `v1/tests/workflow/framework/runner.py:_parse_claude_json` for the
  best-effort parser.
- `success_check` is intentionally strict-but-narrow: it checks for the
  specific structural changes the prompt asks for, not for "good taste."
