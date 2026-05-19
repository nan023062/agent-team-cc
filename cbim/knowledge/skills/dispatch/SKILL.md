# Skill: Request Classification and Dispatch

After receiving a user request, the assistant classifies it within the memory and knowledge snapshot context, then dispatches it to the appropriate agent.

---

## Classification Logic

Any user request can be classified into one of the following four categories:

| Request Type | Decision Basis | Dispatch Target |
|-------------|---------------|----------------|
| **Business layer CRUD** | Involves module design, architecture, compliance, knowledge system (`.dna/`) | Architect (`architect`) |
| **Capability layer CRUD** | Involves agent recruitment, training, assessment, archiving | HR (`hr`) |
| **Execution task** | Implement features per blueprint, write code, fix bugs | Corresponding work agent (e.g., `programmer`) |
| **Review request** | Review design, changes, decisions; adversarial perspective needed | Auditor (`auditor`) |

---

## Dispatch Flow

```
User request
  ↓
Understand intent using snapshot context (module tree + agent list)
  ↓
Classify (business / capability / execution / review)
  ↓
Refresh knowledge snapshot — run before composing task description:
  Bash: python -m knowledge.engine.snapshot --root <project-root>
  cwd: cbim/  (or cbim root where knowledge package lives)
  Use output to locate current module paths; do not rely solely on session-start snapshot
  ↓
Select agent → compose task description (include relevant module paths, constraints, expected output)
  ↓
Agent(subagent_type=<id>, prompt=<task>)
  ↓
Consolidate results, feed back to user
```

---

## Classification Examples

| User says | Classification | Dispatch to |
|-----------|--------------|-------------|
| Create a combat module | Business layer CRUD | Architect |
| Review the combat module design | Review | Auditor |
| Recruit an AI engineer agent | Capability layer CRUD | HR |
| Implement the login API per the blueprint | Execution | programmer |
| Look up the decision history for the combat module | Business layer query | Architect (read-only) |
| Train the programmer | Capability layer CRUD | HR |

---

## Key Principles

1. **No direct execution** — The assistant is the dispatcher, not the implementer. Business changes go to the architect, capability changes go to HR, code goes to the work agent.
2. **Fresh snapshot before dispatch** — Always re-run the knowledge snapshot at decomposition time; the session-start snapshot is stale if the architect has made changes mid-session. Use the live module tree to populate module paths in the task description, minimizing the agent's source-file search overhead.
3. **One goal per call** — Each `Agent()` call has exactly one clear objective; compound tasks are split into multiple sequential or parallel calls.
4. **Consolidate results** — After the agent returns, the assistant extracts key conclusions to feed back to the user; do not paste raw output directly.
5. **No matching agent** — If the required work agent does not exist, recruit one through HR first, then dispatch the task.
