# Skill: Request Classification and Dispatch

After receiving a user request, the assistant classifies it within the memory and knowledge snapshot context, then dispatches it to the appropriate agent.

---

## Classification Logic

Any user request can be classified into one of the following four categories:

| Request Type | Decision Basis | Dispatch Target |
|-------------|---------------|----------------|
| **Business layer CRUD** | Involves module design, architecture, compliance, knowledge system (`.dna/`) | Architect (`architect`) |
| **Capability layer CRUD** | Involves agent recruitment, training, assessment, archiving | HR (`hr`) |
| **Execution task** | Any coding work: implement features, add functionality, write code, fix bugs, refactor — with or without a pre-existing blueprint | Corresponding work agent (e.g., `programmer`) |
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
| Add dry-run mode to the dispatch system | Execution | programmer |
| Fix the crash in the save handler | Execution | programmer |
| Refactor the event bus to use async | Execution | programmer |
| Look up the decision history for the combat module | Business layer query | Architect (read-only) |
| Train the programmer | Capability layer CRUD | HR |

---

## Key Principles

1. **No direct execution** — The assistant is the dispatcher, not the implementer. Business changes go to the architect, capability changes go to HR, code goes to the work agent. **The assistant must never read source code, explore file structures, or investigate codebases** — even "to understand the current state." That is the work agent's job.
2. **Blueprint is not a prerequisite for dispatch** — When a user requests a code change and no blueprint exists, dispatch directly to the work agent. The work agent is responsible for exploring the codebase, understanding context, and implementing. The assistant's job is to relay the user's intent clearly, not to pre-digest the codebase.
3. **Fresh snapshot before dispatch** — Always re-run the knowledge snapshot at decomposition time; the session-start snapshot is stale if the architect has made changes mid-session. Use the live module tree to populate module paths in the task description, minimizing the agent's source-file search overhead.
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
