# Agent Capability Layer Convention

> The capability layer is governed by HR, strictly separated from the business layer (`.dna/`).

## Core Concepts

**Agent**: An execution unit defined under `.claude/agents/<id>/`, described by a single `<id>.md` file that specifies its identity, principles, and skills.

**Core Agents** (permanently read-only; HR must not modify): `architect`, `hr`, `auditor`, and the main session (`CLAUDE.md`).

**Work Agent**: An executor created, trained, assessed, and archived by HR on demand. Capability scope is constrained by the single-responsibility principle.

---

## Agent Directory Structure

```
.claude/agents/
└── <id>/
    └── <id>.md          # complete agent definition (frontmatter + soul)
```

> **Skills are not inside the agent directory.** Operation skill documents are stored uniformly in `cbim/knowledge/skills/`; the agent's Skills table references them by path.

---

## `<id>.md` Format

```markdown
---
name: <display name>
description: <one-line positioning, used by the assistant when deciding dispatch>
model: claude-opus-4-7
tools: Read, Write, Edit, Glob, Grep, Bash
---

## Responsibilities

<what this agent does and does not do>

## Principles

1. <behavioral boundary>
2. <decision criterion>
3. <collaboration norm>

## Trigger Scenarios

- <when should the assistant dispatch this agent>

## Skills

| Scenario | Skill File |
|----------|-----------|
| <scenario description> | `cbim/knowledge/skills/<skill-name>/SKILL.md` |
```

---

## Frontmatter Fields

| Field | Required | Notes |
|-------|----------|-------|
| `name` | ✅ | Display name |
| `description` | ✅ | Dispatch decision basis for the assistant; concise and accurate |
| `model` | ✅ | Recommend `claude-sonnet-4-6`; use `claude-opus-4-6` for high-complexity tasks |
| `tools` | ✅ | Minimum necessary permissions; do not grant tools that are not needed |

---

## Soul / Identity Writing Principles

**Portability hard rule**: the soul contains only professional capability — no project-specific content whatsoever.

Self-check: if this content is placed in a completely different project, does it still make sense?
- Yes → can be written into the soul
- No → leave it in `cbim/memory/store/`, do not promote

**What to write**:
- Personality and communication style (makes the agent recognizable, collaboration more natural)
- Responsibility boundaries (what it does / does not do)
- Decision principles (how to decide when facing ambiguity)
- Trigger scenarios (when should the assistant dispatch this agent)

**What NOT to write**:
- Project names, module names, business logic
- Current task status, temporary rules
- Hard-coded dependencies on specific agents (describe collaboration by role, not by id)

---

## Agent Lifecycle

```
Recruit (scaffold)
    ↓
Execute tasks (dispatched by assistant)
    ↓
Assessment (periodic HR evaluation)
    ├─ Capability gap ──→ Training (distill skill / update soul)
    ├─ Responsibility too broad ──→ Split (into multiple specialized agents)
    └─ Long-term idle ──→ Archive (.md.archived)
```

---

## CRUD Commands

```bash
# List all agents
python cbim/knowledge/engine/cli.py agents list

# View agent details
python cbim/knowledge/engine/cli.py agents show <name>

# Create new agent (generate scaffold file)
python cbim/knowledge/engine/cli.py agents scaffold <name> --description "..."

# Archive agent
python cbim/knowledge/engine/cli.py agents archive <name>
```
