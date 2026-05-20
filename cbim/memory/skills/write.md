# Skill: Write Short-term Memory (Session Entry)

**Main agent only.** Two first-class triggers — both write to `cbim/memory/store/short/`. Never write memory to `~/.claude/projects/<project>/memory/` (Claude Code's built-in auto-memory is disabled in CBIM projects; see CLAUDE.md > Memory Routing).

---

## Triggers

| Trigger | Slug | When |
|---------|------|------|
| **User explicit request** (e.g. "记下"/"记住"/"remember this"/"save this") | `manual-<topic>` | **Mid-session, in response to a user message** — assistant invokes this skill immediately. This is a first-class flow, not an exception. |
| **Stop hook (auto)** | `main-<auto-slug>` | At session end, `cbim/cc-template/hooks/write-memory.py` parses the transcript and writes a session summary. |

The Stop-hook flow is automatic — no action needed from the assistant. **This document is primarily for the user-explicit-request flow.**

---

## Manual User-Request Flow (5 steps)

When the user explicitly says to remember something:

1. **Detect the trigger** — these words count: `记下` / `记住` / `记一下` / `备忘` / `remember this` / `save this` / `save to memory` / `保存记忆` / `存到记忆里`. If the user just describes a fact without asking to remember, don't write — wait for an explicit ask.

2. **Classify the signal quadrant** — pick one of MUST / WANT / HOW / IS (see "Signal Four Quadrants" below). If ambiguous, ask **one** clarifying question first.

3. **Pick a slug** — short kebab-case, ≤30 chars, describes the topic (not the date). Examples: `v2-phase1-start`, `combat-damage-formula`, `auth-token-policy`. The full filename is `YYYY-MM-DD-manual-<slug>.md`.

4. **Write the file** to `cbim/memory/store/short/YYYY-MM-DD-manual-<slug>.md` using the entry format below. Include only the relevant signal(s); do not pad with empty Task Overview / Subagent Log sections — those are for the Stop-hook auto-entries.

5. **Update the index**:
   ```bash
   .venv/bin/python -m memory.engine.cli add cbim/memory/store/short/YYYY-MM-DD-manual-<slug>.md --tier short
   ```
   On Windows: `.venv\Scripts\python.exe -m memory.engine.cli add ...`

6. **Confirm to user** — one line: `Saved to cbim/memory/store/short/<filename>` so the user knows where it landed (not `~/.claude/...`).

---

## Entry Format

File path: `cbim/memory/store/short/YYYY-MM-DD-{main|manual}-<slug>.md`

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
| **WANT** | decision | Why choose this approach? | No — an active trade-off in the current project | `.dna/module.md` (ADR format) |
| **HOW** | pipeline (flow) | How should this flow run? | Depends | Cross-project → `cbim/knowledge/skills/`; project-specific → `.dna/workflows/` |
| **IS** | knowledge (fact) | What is the current fact? | No — a verifiable system fact | `.dna/contract.md` (if protocol-boundary) or `module.md` |

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

After writing the file, notify the engine (already covered in step 5 of the Manual User-Request Flow):

```bash
# Linux / macOS
.venv/bin/python -m memory.engine.cli add cbim/memory/store/short/<filename>.md --tier short

# Windows
.venv\Scripts\python.exe -m memory.engine.cli add cbim/memory/store/short/<filename>.md --tier short
```
