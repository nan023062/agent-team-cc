# Skill: Request Classification and Dispatch

After receiving a user request, the assistant classifies it within the memory and knowledge snapshot context, then dispatches it to the appropriate agent.

---

## Classification Logic

Any user request can be classified into one of the following four categories:

| Request Type | Decision Basis | Dispatch Target |
|-------------|---------------|----------------|
| **Business layer CRUD** | Involves module design, architecture, compliance, knowledge system (`.dna/`) | Architect (`architect`) |
| **Capability layer CRUD** | Involves agent recruitment, training, assessment, archiving | HR (`hr`) |
| **Execution task** | Any coding work: implement features, add functionality, write code, fix bugs, refactor | **Two-phase:** first Architect for task context, then work agent (e.g., `programmer`) with that context |
| **Review request** | Review design, changes, decisions; adversarial perspective needed | Auditor (`auditor`) |

---

## Dispatch Flow

### Non-execution requests (business / capability / review)

```
User request
  ↓
Understand intent (from user description + session-start snapshot only)
  ↓
Classify → business / capability / review
  ↓
Select agent → compose task description
  ↓
Agent(subagent_type=<id>, prompt=<task>)
  ↓
Consolidate results, feed back to user
```

### Execution requests (code changes) — Knowledge-First Two-Phase

All execution tasks — features, bug fixes, refactors, additions — follow this two-phase flow. The coordinator never analyzes modules, runs snapshots, or locates code paths. That is the architect's job.

```
User request (coding work)
  ↓
Understand intent (from user description only)
  ↓
Classify → execution task
  ↓
Phase 1 — Architect context gate:
  Dispatch to Architect with the user's requirement.
  Architect analyzes:
    - New module → creates .dna/ documentation, returns task context
    - Existing module → reads .dna/, returns task context
  Task context includes: module path(s), design constraints,
    dependency rules, relevant contract/architecture excerpts.
  ↓
Phase 2 — Work agent execution:
  Dispatch to work agent (e.g., programmer) with:
    - The user's original requirement
    - The architect's task context (module paths, constraints, design notes)
  The work agent implements per the context; does not explore architecture independently.
  ↓
Consolidate results, feed back to user
```

**The coordinator must not proceed to Phase 2 without the architect's returned context.** If the architect identifies issues (e.g., architectural conflict, missing prerequisite module), the coordinator reports back to the user before proceeding.

---

## Classification Examples

| User says | Classification | Dispatch to |
|-----------|--------------|-------------|
| Create a combat module | Business layer CRUD | Architect |
| Review the combat module design | Review | Auditor |
| Recruit an AI engineer agent | Capability layer CRUD | HR |
| Implement the login API per the blueprint | Execution | Architect (context) → programmer |
| Add dry-run mode to the dispatch system | Execution | Architect (context) → programmer |
| Fix the crash in the save handler | Execution | Architect (context) → programmer |
| Refactor the event bus to use async | Execution | Architect (context) → programmer |
| Look up the decision history for the combat module | Business layer query | Architect (read-only) |
| Train the programmer | Capability layer CRUD | HR |

---

## Key Principles

1. **No direct execution** — The assistant is the dispatcher, not the implementer. Business changes go to the architect, capability changes go to HR, code goes to the work agent. **The assistant must never read source code, explore file structures, or investigate codebases** — even "to understand the current state." That is the work agent's job.
2. **Knowledge first** — Every execution task (code change) must pass through the architect before reaching the work agent. The architect confirms the knowledge state, creates or updates `.dna/` documentation as needed, and returns a task context package. The coordinator must not dispatch to a work agent without this context. The architect decides whether a blueprint needs to be created; the coordinator does not make that judgment.
3. **Coordinator does not analyze modules** — The coordinator must not run snapshots, locate module paths, or compose architectural context. That is the architect's responsibility. The coordinator's inputs are: the user's description and the architect's returned task context.
4. **One goal per call** — Each `Agent()` call has exactly one clear objective; compound tasks are split into multiple sequential or parallel calls.
5. **Consolidate results** — After the agent returns, the assistant extracts key conclusions to feed back to the user; do not paste raw output directly.
6. **No matching agent** — If the required work agent does not exist, recruit one through HR first, then dispatch the task.

---

## Anti-Patterns (must not do)

The assistant must **never** do any of the following, even as a "preparation step" before dispatching:

- Use `Read`, `Glob`, `Grep`, or `Bash` to explore project source code or file structures
- Open source files to "understand the current implementation"
- Investigate which files need to change before dispatching
- Summarize existing code to "help the agent"

If the assistant catches itself about to read a source file, that is the signal to dispatch instead. The work agent has full filesystem access and is better equipped to explore.
