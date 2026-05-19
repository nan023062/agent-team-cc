# Skill: Business Layer Module CRUD (Architect)

> Manage the project's `.dna/` knowledge system. Knowledge first — document before you build.

## Commands

```bash
python cbim/knowledge/engine/cli.py modules list [--root <path>]            # list all modules
python cbim/knowledge/engine/cli.py modules show <module-dir>               # view module details
python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner <owner> [--description "..."]
```

---

## Create Module

**Trigger**: A new feature directory needs knowledge documentation, or a parent module's responsibilities are too heavy and need to be split into sub-modules.

1. Confirm the directory exists (or create it first)
2. Initialize:
   ```bash
   python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner architect
   ```
3. Fill in `.dna/module.md`, following these rules:
   - **Frontmatter**: fill in `description`, `keywords`, `dependencies` as needed
   - **Body**: write only the current final working state; no change history or background
   - High-density: describe the entire module as concisely as possible in a single document
   - If parent module: Positioning + sub-module relationship diagram (Mermaid) + key decisions; never write child module internal details
   - If leaf module: Positioning + class diagram (Mermaid `classDiagram`) + key decisions
4. (Optional) If this is a protocol-boundary module (REST/gRPC/cross-language/public SDK), add `--with-contract` to the init command above, then fill in `.dna/contract.md`:
   - Write only the currently valid external interfaces; no change history or deprecated interfaces
   - High-density: interface signatures are the primary content, descriptions are concise
   - **Do NOT create contract.md for ordinary internal modules** — in strongly-typed languages, source code is the contract
5. Update the root module's `.dna/index.md`, appending the new module path
6. Run compliance check: execute `arch-governance.md`

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

**Hard rule**: No circular dependencies between sub-modules; parent module must never write the internal implementation details of any child module.
