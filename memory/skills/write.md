# Skill: Write Short-term Memory (Session Entry)

**Main agent only. Automatically triggered by the Stop hook — manual execution is rarely needed.**

---

## Trigger Methods

| Method | Description |
|--------|-------------|
| Automatic (recommended) | Stop hook parses the transcript at session end and writes the entry |
| Manual | When hook didn't trigger / important information needs to be added, main agent writes manually |

---

## Entry Format

File path: `memory/store/short/YYYY-MM-DD-main-<slug>.md`

```markdown
---
tier: short
tags: session
modules: combat pathfinding   # optional; space-separated module names involved
---

## Task Overview
(User's original request, summarized in one or two sentences)

## Subagent Execution Log

### <subagent description>
Result: <key output summary>

## Files Written / Modified
- path/to/file

## Signals
- [ ] MUST: agent-id: description
- [ ] WANT: module-name: description
- [ ] HOW: agent-id or module-name: description
- [ ] IS: module-name: description
```

---

## Signal Four Quadrants

Signals are the raw material for distilling medium-term memory and governance decisions. Each signal is tagged with its quadrant, which determines its downstream destination:

| Quadrant | Type | Answers What | Cross-Project | Final Destination |
|----------|------|-------------|---------------|------------------|
| **MUST** | maxim (principle) | What must never be violated? | **Yes** — holds across projects and languages | Agent soul / `cbim/knowledge/skills/` |
| **WANT** | decision | Why choose this approach? | No — an active trade-off in the current project | `.dna/architecture.md` (ADR format) |
| **HOW** | pipeline (flow) | How should this flow run? | Depends | Cross-project → `cbim/knowledge/skills/`; project-specific → `.dna/workflows/` |
| **IS** | knowledge (fact) | What is the current fact? | No — a verifiable system fact | `.dna/contract.md` |

---

## Signal Writing Spec

### MUST — Absolute Principles (Cross-Project)

Record constraints an agent must not violate, or behavioral norms it should always follow.

**Typical triggers:**
- User corrected an agent's behavior (human correction — highest priority signal)
- Agent's action produced an irreversible consequence (deletion, overwrite, external send)
- Agent was found to have exceeded its role boundary

**Format:** `MUST: agent-id: description`

```
- [x] MUST: programmer: Before bulk deletes, must display expected change scope and get confirmation
- [x] MUST: architect: Must not modify code directly — only make architecture recommendations
- [x] MUST: all-agents: When encountering undefined business terms, must clarify before executing — do not self-interpret
- [x] MUST: programmer: Before calling write-operation APIs, must run a dry-run validation
```

### WANT — Project Decisions (Current Project Trade-offs)

Record "why A over B" — a deliberate choice with reason and accepted cost.

**Typical triggers:**
- Made a technology selection (framework, protocol, storage)
- Defined a service boundary or interface design
- Made a trade-off that differs from the "default approach"

**Format:** `WANT: module-name or scope: decision description`

```
- [x] WANT: memory-module: Chose FileBackend over ChromaDB; accepted no semantic search in exchange for zero external dependencies
- [x] WANT: combat-module: Chose ECS architecture over OOP; accepted development complexity in exchange for performance and composability
- [x] WANT: auth-module: Tokens stored as self-contained JWT, not in Redis; accepted no active revocation in exchange for stateless service
```

### HOW — Flow Patterns (May Be Cross-Project)

Record "what steps to follow for this" — validated effective execution methods.

**Typical triggers:**
- A certain approach significantly improved efficiency or reduced errors
- Discovered a fixed pattern in how an agent handles a type of task
- A flow has recurred across multiple sessions

**Format:** `HOW: agent-id or module-name: flow description`

```
- [x] HOW: architect: Contract first then architecture; interface stability is higher
- [x] HOW: programmer: New module sequence: interface definition → unit tests → implementation → integration tests
- [x] HOW: combat-module: Damage calculation flow: receive input → validate → calculate → broadcast result; no skipping steps
```

### IS — Current Facts (Verifiable System State)

Record "what it is right now" — current version of interfaces, configs, or rules.

**Typical triggers:**
- Interface signature changed
- Business rule definition updated (record both old and new values)
- Config adjusted (rate limits, timeouts, thresholds, etc.)
- Dependency version changed

**Format:** `IS: module-name: fact description (old value → new value, if applicable)`

```
- [x] IS: auth-module: Token validity changed from 24h to 8h (2026-05-18)
- [x] IS: combat-module: Damage calculation interface signature changed to calculate(actor, target, context)
- [x] IS: api-gateway: Rate limit threshold 100 req/min (by user_id)
- [x] IS: business-rule: "Active user" definition changed — old: logged in within 90 days; new: purchased within 90 days
```

---

## Priority: Which Signals Are Most Worth Recording

In order of importance:

1. **User corrections of agent behavior** (correction) — required; falls under MUST or HOW
2. **IS-type changes** (interface, rule, config changes) — required; prevents future decisions based on stale facts
3. **WANT-type decisions** (choices with trade-offs) — required; records "why"
4. **MUST-type negative patterns** (agent did something it shouldn't) — required
5. **HOW-type positive patterns** (effective approaches that recur) — recommended

**Not worth recording:**
- Intermediate reasoning steps, temporary calculations
- Real-time data that can be re-queried (weather, stock prices, etc.)
- One-time highly context-specific details (no generalization value)
- Casual conversational content

---

## Update Index After Manual Write

After writing the file, notify the engine:

```bash
.venv/bin/python -m memory.engine.cli add memory/store/short/<filename>.md --tier short
```
