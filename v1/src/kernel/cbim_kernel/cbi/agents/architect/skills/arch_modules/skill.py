SKILL: str = """\
# Skill: Business Layer Module CRUD (Architect)

> Manage the project's `.dna/` knowledge system. Knowledge first — document before you build.

This skill has **two invocation modes**:

1. **Execution Gate** — Coordinator dispatches the Architect as the mandatory gate for any execution task (code / feature / bugfix). The Architect performs DNA state triage and returns a **ContextPack** to the Coordinator before any Work Agent runs. See `## Execution Gate: DNA State Triage` and `## ContextPack Schema` below.
2. **Direct CRUD** — User or Architect itself initiates module create / update / deprecate / split. See `## Project Initialization` and below.

## Commands

```bash
cbim dna list [--root <path>]            # list all modules
cbim dna show <module-dir>               # view module details
cbim dna init <dir> --type {root,parent,leaf} --name <name> --owner <owner> [--description "..."]
```

**`--type` is required and determines the body template:**

| Type | When to use | Template body |
|------|-------------|---------------|
| `root` | Project root only — single-app projects that have a top-level module. `target` must equal project root. Monorepos / mixed-system projects normally skip this. | Parent template |
| `parent` | Module that contains sub-modules (each with their own `.dna/`) | `## Positioning / ## Sub-module Relationships (graph) / ## Key Decisions` |
| `leaf` | Module with no sub-modules; self-contained | `## Positioning / ## Class Diagram (classDiagram) / ## Key Decisions` |

The CLI **refuses** to init any module before `.cbim/index.md` exists (proves `install.py` ran), and refuses to init `--type root` anywhere except the project root. Every successful `init_module` auto-appends the new module to the registry.

---

## Execution Gate: DNA State Triage

**Trigger**: Coordinator dispatches the Architect with an execution task (code implementation, feature work, bugfix) and requests task context. This is the **mandatory gate** described in `design/WORKFLOW-EXECUTION.zh-CN.md` (步骤 4 「Architect 必经门」) and `design/WORKFLOW-ARCHITECT.zh-CN.md`.

The Architect does **not** start design work freely. The flow is fixed: **Scan → Triage → Act → Return ContextPack**.

### Step 1 — Scan

Locate the modules potentially related to the task:

1. **Read** `.cbim/index.md` to enumerate every existing module path in the project. This is the cheap, authoritative starting point.
2. For each candidate module path, **read** the corresponding `.dna/module.md` (and `.dna/contract.md` if present) to inspect positioning, dependencies, and current contract.
3. **Only if** the index + module.md cannot conclusively locate the task's surface area, fall back to `Glob` / `Grep` against the working tree to confirm where the affected code actually lives. Code scanning is the last resort, not the first move.

Outcome of Scan: a concrete list of `(module-dir, .dna/module.md absolute path or null)` candidate pairs.

### Step 2 — Triage: the DNA four states

For each candidate module, classify into exactly one state. Terminology copied verbatim from `design/WORKFLOW-ARCHITECT.zh-CN.md` §「DNA 四状态」:

| State | 含义 | How to recognise |
|-------|------|------------------|
| **0 — 无** | DNA 文件不存在 | No `.dna/module.md` at the candidate path |
| **1 — 同步** | DNA 与代码一致 ✅ | `.dna/module.md` exists and matches what the code actually does today |
| **2 — 代码超前** | 代码已变更，DNA 未跟上 | `.dna/module.md` exists but the code has diverged (new interfaces / removed classes / changed dependencies not reflected) |
| **3 — DNA 超前** | 有设计意图尚未实现 | `.dna/module.md` describes interfaces / behaviours that do not yet exist in code (DNA written as spec ahead of implementation). Such a module is normally flagged in its own frontmatter as `status: spec`. |

> **State vs. declared intent — orthogonal axes.** `dna_state` (0/1/2/3) is what the *Architect observes* by comparing DNA to code. `status` (`spec` / `planned` / `implemented`) is what the *Architect declared* in the module's own frontmatter. They are not synonyms:
>
> - `status: spec` + `dna_state: 3` → designed-but-not-built, expected (architect-ahead mode).
> - `status: spec` + `dna_state: 1` → contradiction: the spec field is stale; the programmer who shipped the code forgot to flip it. Update via `cbim dna edit ... --field status --value implemented`.
> - `status: implemented` + `dna_state: 2` → normal drift; DNA refresh needed.
> - `status: planned` → reserved for future; architect has named the module but neither designed nor built it yet. Rare.

### Step 3 — Act: state → action matrix

Each state has exactly one default action path. **Do not improvise.**

| State | Decision | Architect action |
|-------|----------|------------------|
| **0** | Apply the **Worth0 decision** (below). 「值得建?」 | If **worth** → `cbim dna init …` to create module.md (+ contract.md if protocol-boundary). If **not worth** → **skip**, record reason in ContextPack. |
| **1** | No DNA change needed | Directly extract module path + design constraints into ContextPack. |
| **2** | DNA must catch up before work proceeds | Analyse the divergence (which interfaces / boundaries / dependencies changed?), update `.dna/module.md` via `cbim dna edit --target body` (or `--target section` for targeted edits) to reflect current code, **then** build ContextPack. |
| **3** | Validate feasibility | Verify upstream / downstream dependencies are ready. Mark the module's frontmatter as a spec — concrete, machine-readable, via: `cbim dna edit <mod> --target frontmatter --field status --value spec`. Then carry `action_taken: mark_spec` in the ContextPack entry. DNA = task brief; Work Agent must implement to the spec, not modify it. After successful implementation the Work Agent flips it: `cbim dna edit <mod> --target frontmatter --field status --value implemented`. |

#### Worth0 decision (state-0 only)

Apply these criteria, copied from `design/WORKFLOW-ARCHITECT.zh-CN.md` §「懒式生成原则」. Any single positive signal is sufficient to declare **worth**:

- 模块复杂度高（多文件、多依赖）
- 被多处引用（改动影响范围广）
- 有明确设计意图需要显式记录

Negative signal — declare **not worth** and skip DNA creation:

- 一次性脚本 / 临时代码

When skipping, the ContextPack still carries the candidate path with `dna_state: 0` and `action: skip` + the reason — Coordinator and Work Agent must know the area was triaged and consciously left undocumented.

### Step 4 — Return ContextPack

Once all candidate modules have been classified and acted on, assemble the ContextPack (next section) and return it as the Architect's final message to the Coordinator. **No Work Agent runs before this packet exists.**

---

## ContextPack Schema

**Purpose**: The minimum-field contract returned by the Architect to the Coordinator at the end of the execution gate. The Coordinator forwards it verbatim into every Work Agent prompt. Work Agents consume it to know which modules to touch, what constraints bind them, and what they may or may not call.

The packet is a single Markdown block with the following structure. Fields marked **required** must always appear; **optional** fields may be omitted when not applicable.

### Required top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Short identifier echoing the Coordinator's task label. |
| `modules` | list of module entries | One entry per related module (see sub-schema below). At least one entry. |
| `dependency_rules` | structured text | Allow-list / deny-list of cross-module calls relevant to this task. |
| `work_agent_notes` | bulleted text | Architect's specific instructions to the Work Agent (per-module or task-wide). |

### `modules[]` sub-schema (per entry)

| Field | Required | Description |
|-------|----------|-------------|
| `path` | yes | **Absolute path** to `.dna/module.md` (or the directory if state = 0 and skipped). |
| `dna_state` | yes | One of `0`, `1`, `2`, `3` (as defined in the Triage section above). |
| `action_taken` | yes | What the Architect did: `init` / `skip` / `none` / `update` / `mark_spec`. `mark_spec` means the architect ran `cbim dna edit ... --field status --value spec` on this module — the frontmatter `status` field is now the machine-readable record; the ContextPack carries the human-readable echo. |
| `design_constraints` | yes | Plain-text summary of constraints extracted from `module.md` / `contract.md` (positioning, key decisions, public interface signatures). Quote verbatim where possible. |
| `notes` | optional | Module-specific hint for the Work Agent (e.g. "S1 — implement freely within existing contract", "S3 — DNA is the spec (status=spec), do not deviate; flip to implemented when done", "S0 skipped — one-shot script, no DNA needed"). |

### Example (Markdown form)

```markdown
## ContextPack

- task_id: fix-event-bus-replay

### Modules

- path: D:/proj/packages/core/event-bus/.dna/module.md
  dna_state: 1
  action_taken: none
  design_constraints: |
    Positioning: single in-process pub/sub.
    Key decisions: handlers are sync; replay is opt-in per topic.
    Public interface: IEventBus.on(topic, handler), IEventBus.emit(topic, payload).
  notes: S1 — extend implementation but do not change IEventBus signatures.

- path: D:/proj/packages/core/event-bus/replay/.dna/module.md
  dna_state: 2
  action_taken: update
  design_constraints: |
    Positioning: ring-buffer replay store for IEventBus.
    Key decisions: buffer size 1024; oldest-evicted-first.
  notes: DNA updated to reflect new ReplayCursor class; align implementation.

### Dependency rules

- event-bus/replay MAY depend on event-bus (stable side).
- event-bus MUST NOT depend on event-bus/replay (unidirectional, C3).
- Neither module may call packages/ui/* directly.

### Work agent notes

- Preserve IEventBus contract; any breaking change must come back to Architect.
- Add tests under packages/core/event-bus/replay/__tests__/.
- After implementation, report back so Architect can run arch_governance.
```

### Consumption rule for Work Agents

A Work Agent receiving this packet must:

1. Read every listed `path` before writing code.
2. Treat `dependency_rules` as hard constraints; any deviation requires escalating back through the Coordinator.
3. Treat `dna_state: 3` modules (and any module whose frontmatter carries `status: spec`) as **specs** — implement, do not redesign. After successful implementation, flip the frontmatter via `cbim dna edit <mod> --target frontmatter --field status --value implemented` so the declared intent matches the new code reality.
4. Honour every `notes` line scoped to a module it is about to touch.

---

## Project Initialization

**Trigger**: User requests to initialize the module knowledge system (e.g., "initialize module knowledge system", "initialize project knowledge").

The **registry** (`.cbim/index.md`) is auto-created by `install.py` — that's the single hard requirement. A **project-root module** (`./.dna/module.md`) is OPTIONAL and depends on the project shape:

| Project shape | Recommended top-level setup |
|---------------|------------------------------|
| Single application (one app, one codebase) | `init . --type root` — project root IS the top-level module |
| Monorepo with a single workspace dir (e.g. all code lives in `packages/`) | `init packages --type parent` — workspace dir is the top-level parent |
| Mixed system (e.g. v1 framework code in `.cbim/` + v2 packages in `packages/`) | **No top-level module** — multiple independent top-level parents is fine; the registry alone provides the tree |

### Steps

1. Confirm the registry exists (`ls .cbim/index.md`). If missing, the user hasn't run `install.py` — stop and tell them.
2. Survey the project structure and decide top-level shape (see table above). Confirm with the user if ambiguous.
3. Create the chosen top-level module(s):
   - Single-app: `cbim dna init . --type root --name <project-name> --owner architect`
   - Monorepo: `cbim dna init packages --type parent --name <workspace> --owner architect` (substitute your workspace dir)
   - Mixed: skip this step; go straight to sub-module creation
4. Fill in each newly created `module.md` (positioning + sub-module/class diagram + key decisions per template).
5. Scan for sub-modules and run **Create Module** below for each. `init_module` auto-appends to `.cbim/index.md` — no manual reindex needed.
6. Run compliance check: execute `arch-governance.md`.

**Registry rule** (CLI-enforced): `init_module` requires `.cbim/index.md` to exist (proves install ran). It does NOT require a project-root module — sub-modules can be created freely once cbim is installed.

**Recovery**: if the registry drifts (e.g. someone hand-deleted entries, or modules were added without using `init_module`), run:
```bash
cbim dna reindex
```
This rescans the filesystem and rebuilds `.cbim/index.md`.

---

## Create Module

**Trigger**: A new feature directory needs knowledge documentation, or a parent module's responsibilities are too heavy and need to be split into sub-modules.

1. Confirm the directory exists (or create it first)
2. **Decide module type first**: leaf or parent?

   | Signal | Type |
   |--------|------|
   | No sub-directories with distinct responsibilities; fully self-contained | `leaf` |
   | Contains sub-directories that each carry an independent responsibility | `parent` — those sub-directories must each become a CBIM module with its own `.dna/`; create them **first** (depth-first), then create this parent |

   **If you are drawing a component diagram whose boxes represent internal sub-components** → those components must be promoted to separate CBIM sub-modules first. Write this module's `module.md` only after their `.dna/` directories exist.

3. Initialize with the chosen type:
   ```bash
   cbim dna init <dir> --type {parent|leaf} --name <name> --owner architect
   ```
   The CLI installs a body template matching the type — leaf gets `classDiagram`, parent gets a `graph` placeholder with a "do not write sub-module internals" comment.

4. Fill in `.dna/module.md`:
   - **Frontmatter**: fill in `description`, `keywords`, `dependencies` as needed
   - **Body**: write only the current final working state; no change history or background
   - High-density: one document, maximum signal, minimum noise
   - The template already has the right section headers for your type — fill them in, do not change the structure

   **Leaf module** body (template provided):
   - `## Positioning` — one sentence: what this module is and why it exists
   - `## Class Diagram` — Mermaid `classDiagram`: classes, interfaces, key method signatures, and relationships
   - `## Key Decisions` — design choices whose *why* is invisible from the code; each decision applies to the module as a whole

   ⚠️ **Anti-pattern (check.py #21 will MUST-flag this)** — section header alone is not enough; the mermaid SYNTAX must match:

   ❌ Wrong (parent in disguise: section says Class Diagram but body draws sub-components):
   ````markdown
   ## Class Diagram
   ```mermaid
   graph TD
       KNOWLEDGE["knowledge/<br/>module CRUD"]
       MEMORY["memory/<br/>distillation"]
       DISPATCH["dispatch/<br/>coordinator"]
   ```
   ````

   ✅ Right (real classDiagram showing classes/interfaces):
   ````markdown
   ## Class Diagram
   ```mermaid
   classDiagram
       class IEventBus { <<interface>> +on() +emit() }
       class EventBus { -handlers +on() +emit() }
       IEventBus <|.. EventBus
   ```
   ````

   If you find yourself wanting to draw `graph TD` for internal components, **you're not in a leaf module** — promote those components to real sub-modules (each with its own `.dna/`) and write THIS module as a parent (see Parent module below).

   **Parent module** body (template provided):
   - `## Positioning` — one sentence: what this module is and why it exists
   - `## Sub-module Relationships` — Mermaid `graph`: sub-modules as nodes, inter-sub-module dependencies as edges, one-sentence positioning per node
   - `## Key Decisions` — **only** cross-sub-module emergent insights: why these sub-modules exist together, how they relate at boundaries
     - **Decision smell** (also enforced by `check.py #19/#20`): if a bullet is about a single sub-module's internal design ("Why X/ uses Y approach internally"), it belongs in *that sub-module's own* `.dna/`, not here. Move it.

5. (Optional) If this is a protocol-boundary module (REST/gRPC/cross-language/public SDK), add `--with-contract` to the init command above, then fill in `.dna/contract.md`:
   - Write only the currently valid external interfaces; no change history or deprecated interfaces
   - High-density: interface signatures are the primary content, descriptions are concise
   - **Do NOT create contract.md for ordinary internal modules** — in strongly-typed languages, source code is the contract
6. The registry `.cbim/index.md` is updated automatically by `init_module` — no manual step needed
7. Run compliance check: execute `arch-governance.md`

**Naming convention**: `name` uses kebab-case; `owner` is the responsible agent id.

---

## Update Module

**Trigger**: Interface changes, architecture adjustments, design decision updates.

- **Internal changes** → edit `module.md` body (architecture sections)
- **Interface changes** → edit `contract.md` (if present), notify dependent modules
- **Metadata changes** → edit `module.md` frontmatter (keywords / dependencies / owner)
- **Deterministic process crystallization** → create a new workflow at `.dna/workflows/<name>/workflow.md`

Run compliance check after changes.

---

## Deprecate Module

**Trigger**: Module merged, feature retired, responsibility eliminated after refactoring.

1. Annotate deprecation at the top of `module.md` body: reason + replacement module path.
2. Update the root module's `index.md` — remove or annotate the module path.
3. Check if other modules' `dependencies` reference this module; update each one.
4. (Optional) Leave the frontmatter `status` untouched — it records build-state, not lifecycle. A formal `lifecycle: deprecated` frontmatter field is reserved for a future kernel release; do not hand-write it.

---

## Split Module

**Trigger**: Module responsibilities too heavy (C2 violation), context bloat, single responsibility violated.

1. Identify independently separable sub-domains
2. `init` a new module for each sub-domain
3. Distribute original module content to sub-modules by ownership
4. Original module's `module.md` body retains: its own positioning + child module list + relationships between child modules
5. Update `index.md`

**Hard rule**: No circular dependencies between sub-modules. Parent module must never write any child module's internal implementation details — each child's internal design belongs exclusively in that child's own `.dna/module.md`.
"""
