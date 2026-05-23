---
name: audit
owner: architect
description: Architecture drift guard - five read-only checks (index/memory/agents/dna/tree) over .dna, .claude/agents, .cbim/memory
keywords: []
dependencies:
  - v1/kernel/services
  - v1/kernel/cbi/_primitives
status: spec
---

## Positioning

Read-only governance drift guard. Inspects the project's `.cbim/index.md`, every registered `.dna/module.md`, every project-level agent under `.claude/agents/`, and every entry under `.cbim/memory/`. Returns structured findings; never mutates anything.

Five checks, single dispatch surface:

- `index_consistency` — registry vs. on-disk module list
- `memory_threshold` — short tier volume / staleness, medium tier promotion signals
- `agent_fission` — project agent body & skill count oversize
- `dna_fission` — module body & workflow count oversize
- `dna_tree` — parent/child orphans, dep DAG (cycles, dangling, up-tree direction)

Lives **inside** the engine package because every check threads through `engine.config` (audit thresholds live in `.cbim/config.json`'s `audit` section) and because the CLI surface (`cbim audit ...`) is one more sub-domain of `python -m engine`.

## Class Diagram

```mermaid
classDiagram
    %% classes, interfaces, key method signatures, relationships
```

## Key Decisions

- **Read-only by construction.** No check writes to `.dna/`, `.claude/agents/`, `.cbim/memory/`, or `.cbim/index.md` — even the registry it audits. Mutation belongs to dedicated commands (`cbim dna reindex`, `cbim memory cleanup`, `cbim agent ...`). Audit reports drift; it does not heal it.
- **Embedded inside `engine/`, not a sibling package.** The CLI surface is a sub-domain of `cbim ...` and config thresholds live in `.cbim/config.json`; making audit a sibling of `engine` would require an extra cross-package import dance for no real boundary win. Reversible later if audit grows non-CLI consumers.
- **Three-band severity (info / warn / error) via `resolve_bands`.** `info` = 80% of threshold (early-warning), `warn` = at threshold, `error` = 150% of threshold. Single helper used by every quantitative check; no per-check threshold logic drift.
- **Hardcoded `DEFAULTS` are pure fallback.** `load_audit_config` deep-merges `.cbim/config.json`'s `audit` section over `DEFAULTS`; audit itself never writes the merged result back. Users can override thresholds; the defaults stay readable in source.
- **Skill counting is a heuristic, isolated.** `_agent_skill_parser.count_skills` does fragile markdown-table parsing plus a `cbim skill show <agent>.X` regex fallback. Lives in its own module so a future structured skill metadata can drop the heuristic without touching the check.
- **Medium-tier memory overflow emits TWO promotion findings.** `MEMORY_PROMOTE_TO_AGENT_SKILL` (HR view) and `MEMORY_PROMOTE_TO_DNA_KNOWLEDGE` (architect view) fire together. Audit deliberately does not pick a winner — the coordinator dispatches both reviewers and lets each decide what belongs in their tier.
- **Exit code follows max severity of the (filtered) findings.** 0 = clean / info, 1 = warn, 2 = error. `--severity X` filters display AND affects the exit code; that way CI can gate on `cbim audit run --severity error`.

- **`dependencies` frontmatter 语义**：仅声明跨边界、非祖先的依赖。同层兄弟、向下抽象层、外部模块都要列；任何祖先链上的模块一律不列。这一约定由 `dna_tree` 检查的 `TREE_DEP_ANCESTOR_DECLARED` 强制。

## Sub-module Relationships

```
audit/
  __init__.py        # run_audit, list_checks, AuditResult, AuditFinding
  cli.py             # register_audit_subparser + dispatch
  result.py          # AuditFinding / AuditResult dataclasses + JSON
  report.py          # to_stdout / to_markdown / to_json renderers
  config.py          # DEFAULTS + load_audit_config + resolve_bands
  registry.py        # CHECKS = {name: fn}
  checks/
    index_consistency.py
    memory_threshold.py
    agent_fission.py
    dna_fission.py
    dna_tree.py
    _agent_skill_parser.py   # fragile heuristic, isolated for easy swap
```

Inbound: `engine.cli.main` calls `register_audit_subparser` and routes `domain == "audit"` to `audit.cli.dispatch`.

Outbound:
- `services.list_modules` / `services.list_agents` — preferred read API for the project state.
- `cbi._primitives.modules` — `read_index`, `list_modules`, `index_path` for the registry-vs-disk diff.
- `engine.config.load_config` — pulls the optional `audit` section from `.cbim/config.json`.

Each `check_xxx(project_root: Path, config: dict) -> list[AuditFinding]` is registered in `registry.CHECKS`. The runner (`run_audit`) iterates the selected checks, aggregates findings, and packages them in an `AuditResult` together with a summary and the effective config snapshot.

## Non-Goals

- **No auto-fix.** Audit reports drift; it never rewrites `.dna/`, `.claude/agents/`, or `.cbim/memory/`. Fix commands stay in their owning modules.
- **No writes to `.dna/` from inside any check.** This includes the registry: even though `index_consistency` knows when `.cbim/index.md` is stale, it only emits a finding pointing at `cbim dna reindex`.
- **No semantic judgment.** Audit does not decide whether medium-tier memory belongs in agent skills or in `.dna/` — it emits both promotion findings and lets HR / architect adjudicate. Same for fission: audit reports oversize, it does not propose how to split.
- **No deep semantic import scan.** Dependency direction comes from `frontmatter.dependencies`. We do not parse Python imports, grep code references, or trace call graphs — that is a separate concern with very different cost/precision trade-offs.

