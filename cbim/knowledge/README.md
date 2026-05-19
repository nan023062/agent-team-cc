# Knowledge — Long-Term Memory

> CBIM knowledge base: dual-domain management engine for the capability layer (`.claude/agents/`) and the business layer (`.dna/`), embodying the Capability-Business Independence design philosophy.

---

## Four-Quadrant Architecture

```
                        Business Layer
                    .dna/ knowledge pack
                            │
              Low maturity   │   High maturity
              ─────────────┼─────────────
  High        │  Exploration  │  Mature       │
  Capa-       │               │               │
  bility      │  New agent    │  Specialized  │
  Layer       │  + draft mod  │  agent        │
  (Ca-       ─┼─────────────┼─────────────┤
  pabi-       │  Blank        │  Knowledge-   │
  lity)       │               │  driven       │
  Low         │  No agent     │  Has modules  │
  Capa-       │  No knowledge │  Lacks exec   │
  bility      │               │               │
              └─────────────┴─────────────┘
```

| Quadrant | Capability Layer | Business Layer | State | Action |
|----------|-----------------|----------------|-------|--------|
| **Blank** | No agent | No module | Project just started | Build root module first, then recruit first work agent |
| **Knowledge-driven** | No/weak agent | Has `.dna/` | Blueprint exists, execution missing | HR recruits work agent with matching capability |
| **Exploration** | Has agent | No/draft module | Execution exists, documentation missing | Architect distills knowledge from memory |
| **Mature** | Specialized agent | Complete knowledge system | Healthy state | Continuous governance, split on demand |

**Health goal**: every active module has a corresponding work agent; every work agent has a corresponding knowledge blueprint.

---

## Directory Structure

```
knowledge/
├── README.md               # this file
├── engine/                 # runtime engine (CRUD primitives + unified CLI)
│   ├── cli.py              # unified entry: agents / modules dual-domain commands
│   ├── agents.py           # list_agents / load_agent / scaffold_agent / archive_agent
│   └── modules.py          # list_modules / load_module / init_module / update_index
└── skills/                 # operation skills (SKILL.md + optional runtime scripts)
    ├── hr-agents/          # recruit / update / archive / split
    ├── hr-training/        # agent training (memory → skill/soul)
    ├── hr-assessment/      # agent assessment
    ├── arch-modules/       # module CRUD
    ├── arch-upgrade/       # knowledge promotion (memory → .dna/)
    ├── arch-governance/    # compliance governance audit
    └── audit-review/       # adversarial review (auditor)
```

---

## Quick Reference

```bash
CLI=python cbim/knowledge/engine/cli.py

# Capability layer
$CLI agents list
$CLI agents show <name>
$CLI agents scaffold <name> --description "..."
$CLI agents archive <name>

# Business layer
$CLI modules list
$CLI modules show <module-dir>
$CLI modules init <dir> --name <name> --owner <owner>
$CLI modules reindex
```

---

## Two-Layer Governance Boundaries

| | Capability Layer | Business Layer |
|---|---|---|
| **Data source** | `.claude/agents/` | Each project's `.dna/` |
| **Governed by** | HR | Architect |
| **Lifecycle** | recruit → train → assess → split / archive | document → update → promote → deprecate |
| **Hard rule** | soul contains only professional capability, no project-specific content | knowledge pack contains only module knowledge, no agent specs |
