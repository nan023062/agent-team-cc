SKILL: str = """\
# Skill: Architecture Review (Architect)

> Simulates a senior leader review: structured inspection of the project module tree across two dimensions:
> 1. **Architecture soundness** — module boundaries, responsibility allocation, dependency direction
> 2. **Knowledge–workspace consistency** — whether `.dna/` docs align with actual content, preventing drift in either direction
>
> Output is equivalent to a leader review comment: identify issues, assess severity, give fix recommendations.

## DNA Principle (review lens)

Every DNA is a single module's self-description and must contain **only two things**: this module's positioning on its parent's axis, and this module's own design body (which sub-modules it cut and how they relate at the boundary). Nothing else belongs.

When reviewing, watch for these violations and treat them as MUST-fix:

- **Down-drill** — DNA describes a child's internals (classes, fields, dependency graphs, key decisions scoped to one child). Lift that content out and push it into the child's own `.dna/`; do not leave it in the parent.
- **Noise** — implementation details, call timing, wiring order, completion status, future work, narrative preamble, repeated restatements. Strip it.
- **Vague positioning** — positioning sentence does not place this module on its parent's axis. Rewrite it.

Factors `#12 #19 #20 #21` and the "decision smell" warning are the concrete script / LLM checks that enforce this principle.

## Trigger Scenarios

- After any module is created / updated / deprecated (quick check required)
- Assistant-initiated periodic inspection
- After the auditor flags an architecture issue

---

## Quick Check (After Each Module Change)

Run basic format checks (factors 1–3) on only the changed modules:

```bash
cbim dna list
```

- [ ] `module.md` frontmatter has `name` (kebab-case) and `owner` filled in
- [ ] `module.md` body contains real content, not a template placeholder
- [ ] `contract.md` (if present) contains real content, not a template placeholder
- [ ] Root module `index.md` is in sync

---

## Full Architecture Review

### Preparation: Run the Script First

```bash
PYTHONPATH=<install_root> python -m cbi.agents.architect.skills.arch_governance.check --root .
```

The script automatically handles deterministic checks for factors **#1 #2 #3 #4 #10 #14 #15 #17 #19 #20 #21**, outputting a MUST / SUGGEST list.
**MUST issues must be fixed before the LLM analysis phase.**

```bash
cbim dna list --root .
```

Obtain all module paths, hierarchy, and dependency lists as input for the three-traversal steps below.

---

### Step 1 — Basic Format (Pre-pass, Any Module)

Check factors 1–4 per module; fix non-compliant issues before proceeding.

| # | Factor | Compliance Standard | Check Method |
|---|--------|--------------------|----|
| 1 | `name` format | kebab-case, no uppercase, no spaces | **Script** |
| 2 | Document content | `module.md` body has real content, not a template placeholder; `contract.md` checked only if present | **Script** |
| 3 | No change history | `module.md` body (and `contract.md` if present) contains only the current final state — no history, no changelog, no superseded designs | **Script** |
| 4 | Index in sync | Root module `index.md` corresponds one-to-one with actual module directories | **Script** |

---

### Step 2 — Pre-order Traversal (Parent → Child, Top-down)

**Purpose**: Check whether architectural intent propagates downward accurately.

Start from the root module; review each parent before entering its children.

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 5 | Parent's view of children is accurate | The child module list in `module.md` matches actual subdirectories | LLM |
| 6 | Dependency direction description compliant | Parent-described dependencies conform to C3: unidirectional; stable side owns interface definitions | LLM |

**When issues found**: Record module path + violated factor number; continue traversal and fix collectively at the end.

---

### Step 3 — In-order Traversal (Same-level Siblings, Horizontal Comparison)

**Purpose**: Check whether sibling responsibilities are well divided and dependencies are unidirectional.

Scan layer by layer; compare all child modules under the same parent side by side.

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 7 | No responsibility overlap | Any two sibling modules have no substantive overlap in their responsibility descriptions | LLM |
| 8 | No responsibility gap | The parent's business scope is fully covered by child modules with no obvious missing domains | LLM |
| 9 | Consistent abstraction level | Sibling modules are at the same granularity; no mixing of concept layer and implementation layer | LLM |
| 10 | Unidirectional sibling dependencies | Dependencies among siblings flow in only one direction — no cycles (A→B→A) | **Script** |

**Sibling dependency detection**: Extract entries in `dependencies` pointing to sibling modules, build a local directed graph, check for cycles.

---

### Step 4 — Post-order Traversal (Leaf → Root, Bottom-up)

**Purpose**: Check encapsulation quality and contract completeness, aggregating upward from leaf nodes.

Start from leaf modules; review upward layer by layer.

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 11 | Clean leaf encapsulation | If `contract.md` exists, it exposes only necessary interfaces; no internal implementation details leaked | LLM |
| 12 | Parent writes only relationships and positioning | Parent `module.md` body describes only child module relationships (dependency/composition/aggregation) and their positioning; no internal details of any child | LLM (also: #19 #20 script-level smell tests) |
| 13 | Parent contract correctly aggregates (if present) | If parent has `contract.md`, it covers all child module external interfaces — no omissions, no over-exposure | LLM |
| 14 | No circular dependencies in the full tree | Topological sort of all modules' `dependencies`; report complete cycle paths if found | **Script** |
| 15 | Index fully inclusive | Root module `index.md` lists all leaf module paths | **Script** |
| 18 | Knowledge–workspace consistency | Leaf modules only: compare `.dna/` docs with actual workspace content; detect both drift directions (see below) | LLM |

**#18 Consistency Check Method**:

Read the leaf module's `module.md` body (and `contract.md` if present), then read key workspace files (entry files, main interface files, core directory structure). Compare item by item:

| Check Item | Reference Source | Comparison Target |
|-----------|-----------------|------------------|
| Interface signatures / API names | `contract.md` (if present) | Actual exported functions / classes / interfaces in workspace |
| Internal structure description | `module.md` body | Actual file structure and core components in workspace |
| Workflow steps | `.dna/workflows/*/workflow.md` | Actual execution path in workspace |

**Two drift directions**:

- **Workspace ahead of knowledge** (high risk) — Workspace has changed; `module.md` still describes the old state. Usually caused by "skip knowledge, edit code directly." Must update knowledge immediately.
- **Knowledge ahead of workspace** (medium risk) — `module.md` describes content not yet implemented. If intentional blueprint-first, annotate accordingly; otherwise treat as missing implementation and escalate to assistant.

When consistency issues are found, record: drift direction + specific inconsistencies + recommended fix.

---

### Step 5 — Global Factors (Applied to Every Module During Traversal)

During the three traversals above, check every module visited:

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 16 | Single responsibility (relative) | Module responsibility can be stated in one sentence at current granularity; if description requires "and" / "also" connectors, responsibility is too broad | LLM |
| 17 | Leaf size check | Leaf modules only: if `module.md` body line count, workflow count, or `contract.md` interface count (when present) exceeds thresholds, suggest splitting (thresholds in `config.json`) | **Script** |
| WF1 | Workflow not placeholder | Each `workflow.md` has real content, not a template shell (threshold in `config.json`) | **Script** |
| WF2 | Workflow required sections | Each `workflow.md` contains required sections (`## Trigger Conditions`, `## Steps`, per `config.json`) | **Script** |
| 19 | Parent uses leaf-shaped diagram | Parent module body must not contain `classDiagram` — sub-component internals belong in each sub-module's own `.dna/` | **Script** |
| 20 | Phantom sub-modules in graph | Nodes in a parent's `graph`/`flowchart` that match an immediate sub-directory name must have a corresponding `.dna/`; otherwise promote to sub-module or remove from diagram | **Script** |
| 21 | Leaf uses parent-shaped diagram (parent in disguise) | Leaf module body must not contain `graph`/`flowchart` mermaid with ≥3 nodes — that's a parent describing sub-components without registering them. Either promote those nodes to real sub-modules with their own `.dna/`, or replace with a real `classDiagram`. Renaming the section header alone is not a fix. | **Script** |

---

## Output: Review Report

The review report simulates leader review comment style: each issue includes severity, location, rationale, and fix recommendation.

```
Review Date: <YYYY-MM-DD>
Module Count: <N> (leaf: <M>)

── Dimension 1: Architecture Soundness ─────────────────────

Basic Format (#1–4):
  - [MUST] <module-path>: [#factor] <issue> → <recommendation>

Boundary Definition · Pre-order (#5–6):
  - [MUST/SUGGEST] <module-path>: [#factor] <issue> → <recommendation>

Responsibility Allocation · In-order (#7–10):
  - [MUST/SUGGEST] <module-path>: [#factor] <issue> → <recommendation>

Encapsulation & Contract · Post-order (#11–15):
  - [MUST/SUGGEST] <module-path>: [#factor] <issue> → <recommendation>

Global (#16–17):
  - [SUGGEST] <module-path>: [#factor] <issue> → <recommendation>

── Dimension 2: Knowledge–Workspace Consistency (#18) ──────

  - [MUST] <leaf-module-path>: Workspace ahead — <specific inconsistency> → Update knowledge immediately
  - [WARN] <leaf-module-path>: Knowledge ahead — <specific inconsistency> → Confirm whether intentional blueprint-first

── Summary ─────────────────────────────────────────────────

MUST (must fix): <N>
SUGGEST (recommended): <N>
WARN (needs confirmation): <N>

Fixed autonomously: <list>
Awaiting user confirmation: <list>
```

**Severity definitions**:
- `MUST` — Violates architecture laws (circular dependency, parent writes child internals, knowledge–workspace inconsistency); must fix before continuing
- `SUGGEST` — Design can be improved (responsibility too broad, inconsistent abstraction levels, oversized module); recommended
- `WARN` — Requires human judgment (knowledge ahead of workspace, ambiguous boundaries); escalate to assistant or user

---

## Fix Principles

- **Self-fixable**: Fill in missing doc content, update index, fix format, add missing owner, sync knowledge to workspace
- **Requires user confirmation**: Interface refactoring, module splitting, dependency direction changes, major workspace changes
- After fixing, re-run the quick check (factors #1–4) on changed modules; confirm pass before submitting report
"""
