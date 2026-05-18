# `.dna/` Business Layer Convention

> The business layer is governed by the architect, strictly separated from the capability layer (`.claude/agents/`).

## Core Concepts

**Module**: Any directory containing a `.dna/` subdirectory is a module.

**Root module**: The project root directory itself must contain `.dna/`, making it the root module.

**Module tree**: Implicitly defined by the filesystem directory hierarchy. Parent module = the nearest ancestor directory that contains `.dna/`. No explicit hierarchy declaration is needed.

---

## Module Directory Structure

```
<project>/
└── <module>/
    └── .dna/
        ├── module.json         # metadata (required: name, owner)
        ├── architecture.md     # internal architecture design
        ├── contract.md         # external API / protocol / interface
        └── workflows/          # deterministic processes within the module
            └── <workflow-name>/
                └── workflow.md
```

> **Change logs are not inside the module directory.** Module changelogs are written into session memory (`cbim/memory/store/`); the architect periodically distills and promotes them back to `.dna/`.

**Root-module-only file**:

```
<project>/
└── .dna/
    └── index.md    # list of relative paths of all modules in the tree (root module only)
```

---

## `module.json` Fields

```json
{
  "name": "module name (required)",
  "owner": "responsible agent (required, usually architect or programmer)",
  "description": "(optional) brief module description",
  "keywords": ["(optional) keywords for search"],
  "dependencies": ["(optional) paths of other modules this module depends on"],
  "includeDirs": ["(optional) additional directories to include in context"]
}
```

---

## Knowledge Three-Pack

| File | Content | Constraint |
|------|---------|-----------|
| `module.json` | Metadata, dependency declarations | Structured metadata only; no design descriptions |
| `architecture.md` | Internal structure, design constraints, key decisions | Current final working state only; no change history; high-density, one file to cover the whole module |
| `contract.md` | External API / protocol / interface signatures | Currently valid external interfaces only; no change history; high-density, interface signatures as primary content |

**Business hard rules**:

1. **No history** — `architecture.md` and `contract.md` describe only the current final state. Never write what changed or why it changed. Changes go into session memory (`cbim/memory/store/`); the architect periodically distills and promotes them.

2. **Parent module writes only relationships and positioning** — A parent module's `architecture.md` describes only: the relationships between child modules (dependency / composition / aggregation) and each child module's positioning. Never write any child module's internal details. Each child module's internal design is the responsibility of its own `architecture.md`.

3. **Capability and business separated** — The knowledge three-pack contains only project/module knowledge; it must not reference agent capability specs.

---

## `index.md` Format (Root Module Only)

```markdown
# Module Index

- . (root module)
- src/combat
- src/inventory
- src/ui/hud
```

One module relative path per line. The architect updates this whenever a module is created or deprecated.

---

## Workflow Structure

```
.dna/workflows/<workflow-name>/
└── workflow.md     # trigger conditions + steps + output format
```

A workflow describes a **deterministic process within the module** — it contains no agent capability descriptions. Trigger conditions are explicit, steps are self-contained, and execution requires no additional human instructions.

---

## CRUD Commands

```bash
# List all modules in the project
python cbim/knowledge/engine/cli.py modules list

# View module details
python cbim/knowledge/engine/cli.py modules show <module-dir>

# Initialize a new module
python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner <owner>
```
