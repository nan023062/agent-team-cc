[English](ARCHITECTURE.md) | [中文](ARCHITECTURE.zh-CN.md)

# CBIM Architecture

## Why CBIM

For an agent to genuinely replace human labor and improve efficiency, two conditions must be met simultaneously:

```
Real efficiency gain = Can run autonomously × Runs healthily
```

Neither condition alone is sufficient:

- **Can run autonomously, but runs unhealthily**: Output is flat and chaotic — no layers, no boundaries, review costs more than writing the code manually, maintainability collapses at scale. Still requires heavy human intervention.
- **Runs healthily, but requires human driving**: Every step needs a human to prompt the conversation forward — no order-of-magnitude efficiency gain, cannot genuinely replace human labor.

The reason AI coding agents haven't yet replaced human labor at scale is not that models aren't powerful enough — it's that **no system architecture has existed that simultaneously satisfies "can run autonomously" and "runs healthily"**.

CBIM is designed specifically to solve both:

| Goal | CBIM's Solution |
|------|----------------|
| **Can run autonomously** | SessionStart/Stop hooks for zero-cost cross-session context recovery; assistant dispatch with no human routing needed; knowledge snapshot gives agents full project picture at startup; v2 task queue for autonomous consumption of requirement lists, bug reports, and test runs |
| **Runs healthily** | Architect Gate ensures layered, bounded output; `.dna/` knowledge base makes human review extremely low-cost; two-layer governance continuously ensures architecture quality; context minimization reduces hallucinations and rework |

Both conditions met simultaneously — **agents deliver autonomously, humans handle only final review**.

---

## What Is It

**CBIM** = **CBI** (Capability-Business Independence) + **M** (Memory)

**CBI** is the core design philosophy:

> Capability (agent definitions, skills) and business (project knowledge, module content) must be strictly separated — never contaminating each other.
> Capability is portable expertise; business is a project-specific knowledge blueprint. They collaborate only through task interfaces, never coupling directly.

**M** is the framework's memory infrastructure: session memory (short/medium-term) + SessionStart context injection, enabling CBIM to accumulate structured knowledge across sessions in any project.

This philosophy is reflected in every layer of the framework's design:

| Separation Dimension | Capability Side | Business Side |
|---------------------|-----------------|---------------|
| Storage | `.claude/agents/` (soul) + `.cbim/cbi/skills/` (capability skills) | `.dna/` directory = module identity; `module.md` = sole hard constraint; everything else optional |
| Governed by | HR | Architect |
| Hard rule | soul/skills must contain zero project-specific content | knowledge files must not reference agent specs |
| Verifiable | still meaningful when moved to another project → compliant | describes only current final working state, never describes agents |

You only talk to the assistant. The assistant understands intent, decomposes tasks, routes to the right agent, and consolidates results.

---

## CBIM Core — Multi-Agent × Module Topology Tree

CBIM's core is not just multi-agent — it's the two-dimensional structure of **Multi-Agent (capability axis) × Module Topology Tree (business axis)**. Both are indispensable:

- Multi-agent alone: business knowledge is still a monolith — unknown which context to load
- Module topology tree alone: capability is still monolithic — the agent must carry all skills for any node

Only with both axes can each task simultaneously pinpoint "which agent to use" and "which subtree to load."

### Two-Dimensional Context Minimization

```
Each task's context = specialized agent soul (capability axis)
                    × task subtree .dna/ (business axis)
```

Result: **context ≈ one specialized agent's soul × task subtree's `.dna/`**, independent of total project size. CBIM trades fixed multi-agent dispatch overhead for per-task two-dimensional context minimization.

→ see `src/kernel/cbi/.dna/`, `src/kernel/engine/.dna/`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          User                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ All interactions
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Assistant (main session, CLAUDE.md)                            │
│  · Sole external interface  · Task decomposition  · Routing  · Consolidation │
└──────┬───────────────────┬──────────────────┬───────────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
┌────────────┐    ┌────────────────┐    ┌──────────────────────┐
│  Architect │    │      HR        │    │  Work Agents         │
│            │    │                │    │  (programmer, ...)   │
│  Business  │    │  Capability    │    │  Execute tasks       │
│ governance │    │  governance    │    │  Deliver per blueprint│
│  .dna/     │    │ .claude/agents/│    │                      │
└────────────┘    └──────┬─────────┘    └──────────────────────┘
                         │
                    ┌────┴────┐
                    │ Auditor │
                    │Independent│
                    │  review  │
                    └─────────┘
```

---

## Four Core Agents

| Agent | Responsibility | Scope |
|-------|---------------|-------|
| **Assistant** | Sole external interface, routing, consolidation | Global coordination |
| **Architect** | Design and maintain project knowledge system, architecture review | `.dna/` (business layer) |
| **HR** | Work agent full lifecycle: recruit, train, assess, archive | `.claude/agents/` (capability layer) |
| **Auditor** | Independent critical review, read-only, dispatched only by assistant | Global read-only |

→ for usage examples see the [README](../../README.md)

---

## Two Types of Skills

Traditional Claude Code projects accumulate large numbers of skill files in `.claude/skills/`, becoming unmanageable over time. CBIM splits skills by "who owns and benefits from them" — `.claude/` only contains `agents/`, staying clean.

| Type | Owner | Storage | Governed by | Characteristics |
|------|-------|---------|-------------|----------------|
| **Capability skill** | Agent private capability | `.cbim/cbi/skills/<name>/skill.py` | HR | Describes how an agent does a category of operation; portable, meaningful in any project |
| **Business skill** | Module deterministic process | `.dna/workflows/<name>/workflow.md` | Architect | Describes specific module business steps; project-bound, evolves with the module |

→ see `src/kernel/cbi/.dna/`, `src/kernel/hooks/.dna/`

---

## Two-Layer Governance

| Layer | Governed by | Scope |
|-------|-------------|-------|
| **Capability layer** | HR | `.claude/agents/` (agent definitions and skills) |
| **Business layer** | Architect | Each project's `.dna/` (`module.md` + optional extensions) |

**Hard rule**: Capability goes into `.claude/agents/`; business goes into `.dna/`. Never mix.

→ see `src/kernel/cbi/agents/.dna/`

---

## Architectural Sustainability

CBIM solves more than just context efficiency — it solves a deeper problem: **even with pure vibe coding, the output is layered, bounded code with unidirectional dependencies**.

### Knowledge-First Principle (Architect Gate)

The Architect is not an optional review step — it is the **mandatory gateway** for every implementation task. Every requirement development cycle repeats the loop: user requirement → assistant → architect (confirm module placement, dependency direction, contract, update `.dna/`) → assistant → work agent (with explicit path and blueprint).

Architectural awareness doesn't depend on the user's technical knowledge or the programmer's experience. It is guaranteed by the process — and is embedded in every task's execution flow.

---

## Structured Auditability

CBIM's third core value serves **human reviewers**: after an agent team has been running autonomously for a while, humans don't need to read code — just `.dna/` and `agents/` to get a clear picture of the entire project state and virtual team progress.

CBIM treats knowledge as a first-class citizen of the architecture, not an appendage to code. `.dna/` is not after-the-fact documentation — it is a **living knowledge base that the Architect confirms before each task and updates after each change**. This means human reviewers encounter structured, dependable knowledge — not fragmented commit messages and scattered comments.

---

## Memory System

**The assistant is the sole memory holder.** Subagents focus on execution; they don't operate memory directly.

Memory in CBIM is a **three-stage distillation pipeline**:

| Stage | Path | Purpose |
|-------|------|---------|
| **Short-term** | `.cbim/memory/short/` | Raw session records; mainly for recent context recovery, auto-cleaned |
| **Medium-term** | `.cbim/memory/medium/` | Compressed pattern summaries; de-noised, preserves effective signals, long-term retention |
| **Knowledge** (core) | `.cbim/kernel/cbi/skills/` + `.dna/` | Structured crystallization: capability → skills/soul, business → `.dna/workflows/` |

Transformation: **Short → Medium** is compression (strip execution details, retain patterns); **Medium → Knowledge** is crystallization — the critical step that turns validated patterns into governance structures.

→ see `src/kernel/memory/.dna/`, `src/kernel/hooks/.dna/`, `src/kernel/memory/.dna/module.md` (distillation paths)

---

## Further Reading

- [INSTALL](./INSTALL.md) — post-deployment directory layout
- [MODULE-MD-EXAMPLE](./MODULE-MD-EXAMPLE.md) — leaf and parent `module.md` examples
- [README](../../README.md) — install, first use, slash commands, MCP tools, dashboard
- `src/kernel/cbi/.dna/` — capability + business primitives
- `src/kernel/cbi/agents/.dna/` — architect / hr / auditor / programmer definitions
- `src/kernel/memory/.dna/` — memory engine and distillation
- `src/kernel/hooks/.dna/` — SessionStart / Stop / UserPromptSubmit / PreToolUse
- `src/kernel/engine/.dna/` — unified CLI dispatcher
- `src/kernel/project/.dna/` — install / init / sync / templates
