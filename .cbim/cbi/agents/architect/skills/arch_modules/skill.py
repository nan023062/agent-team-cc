SKILL: str = """\
# Skill: Business Layer Module CRUD (Architect)

> Manage the project's `.dna/` knowledge system. Knowledge first — document before you build.

## Commands

```bash
python .cbim/engine dna list [--root <path>]            # list all modules
python .cbim/engine dna show <module-dir>               # view module details
python .cbim/engine dna init <dir> --type {root,parent,leaf} --name <name> --owner <owner> [--description "..."]
```

**`--type` is required and determines the body template:**

| Type | When to use | Template body |
|------|-------------|---------------|
| `root` | Project root only — single-app projects that have a top-level module. `target` must equal project root. Monorepos / mixed-system projects normally skip this. | Parent template |
| `parent` | Module that contains sub-modules (each with their own `.dna/`) | `## Positioning / ## Sub-module Relationships (graph) / ## Key Decisions` |
| `leaf` | Module with no sub-modules; self-contained | `## Positioning / ## Class Diagram (classDiagram) / ## Key Decisions` |

The CLI **refuses** to init any module before `cbim-prompt/.dna/index.md` exists (proves `install.py` ran), and refuses to init `--type root` anywhere except the project root. Every successful `init_module` auto-appends the new module to the registry.

---

## Project Initialization

**Trigger**: User requests to initialize the module knowledge system (e.g., "initialize module knowledge system", "initialize project knowledge").

The **registry** (`cbim-prompt/.dna/index.md`) is auto-created by `install.py` — that's the single hard requirement. A **project-root module** (`./.dna/module.md`) is OPTIONAL and depends on the project shape:

| Project shape | Recommended top-level setup |
|---------------|------------------------------|
| Single application (one app, one codebase) | `init . --type root` — project root IS the top-level module |
| Monorepo with a single workspace dir (e.g. all code lives in `packages/`) | `init packages --type parent` — workspace dir is the top-level parent |
| Mixed system (e.g. v1 framework code in `cbim-prompt/` + v2 packages in `packages/`) | **No top-level module** — multiple independent top-level parents is fine; the registry alone provides the tree |

### Steps

1. Confirm the registry exists (`ls cbim-prompt/.dna/index.md`). If missing, the user hasn't run `install.py` — stop and tell them.
2. Survey the project structure and decide top-level shape (see table above). Confirm with the user if ambiguous.
3. Create the chosen top-level module(s):
   - Single-app: `python .cbim/engine dna init . --type root --name <project-name> --owner architect`
   - Monorepo: `python .cbim/engine dna init packages --type parent --name <workspace> --owner architect` (substitute your workspace dir)
   - Mixed: skip this step; go straight to sub-module creation
4. Fill in each newly created `module.md` (positioning + sub-module/class diagram + key decisions per template).
5. Scan for sub-modules and run **Create Module** below for each. `init_module` auto-appends to `cbim-prompt/.dna/index.md` — no manual reindex needed.
6. Run compliance check: execute `arch-governance.md`.

**Registry rule** (CLI-enforced): `init_module` requires `cbim-prompt/.dna/index.md` to exist (proves install ran). It does NOT require a project-root module — sub-modules can be created freely once cbim is installed.

**Recovery**: if the registry drifts (e.g. someone hand-deleted entries, or modules were added without using `init_module`), run:
```bash
python .cbim/engine dna reindex
```
This rescans the filesystem and rebuilds `cbim-prompt/.dna/index.md`.

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
   python .cbim/engine dna init <dir> --type {parent|leaf} --name <name> --owner architect
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
6. The registry `cbim-prompt/.dna/index.md` is updated automatically by `init_module` — no manual step needed
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

1. Mark in `module.md` frontmatter: add `status: deprecated`
2. Add deprecation reason and replacement module at the top of `module.md` body
3. Update the root module's `index.md` — remove or annotate the module path
4. Check if other modules' `dependencies` reference this module; update each one

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
