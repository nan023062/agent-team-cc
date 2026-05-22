SKILL: str = """\
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

## Decomposition Heuristics

Workflow step 4 — after the architect's ContextPack is in hand, the coordinator decides whether the subtasks run **in parallel** or **in sequence**. Use the heuristics below; when in doubt, default to **sequential** (conservative).

### Parallel — allowed when ALL of the following hold

- **No data dependency**: subtask B does not consume any output produced by subtask A within the same dispatch wave.
- **Disjoint write surface**: the subtasks write to different files and (preferably) to different modules. Two agents must never hold the write cursor on the same file or the same `.dna/` directory at the same time.
- **Read-heavy / write-light symmetry**: pure investigation, multi-module independent reads, or generating independent artifacts (e.g. one agent writes module A's tests, another writes module B's tests) are natural parallel candidates.
- **Independent failure domains**: a failure in one branch does not invalidate the work of the other; partial results remain useful.

### Sequential — required when ANY of the following hold

- **Output-as-context chain**: the next step needs the previous step's concrete output (e.g. file paths, generated identifiers, audit conclusion) as input. ContextPack hand-off itself is the canonical example: Architect → Work Agent is always sequential.
- **Shared governed-directory writes**: two steps both write under the same `.dna/`, `.claude/agents/`, or `.cbim/memory/` subtree — kernel writes are serialized by design; do not race them.
- **Auditor mid-stream**: when an intermediate result must be reviewed by Auditor before the next step proceeds, the chain is strictly serial (Work Agent → Auditor → next Work Agent).
- **Single-module mutation series**: multiple edits targeting the same module's source files — serialize to keep the diff coherent and reviewable.

### Default

If the parallel preconditions are not unambiguously met, **run sequentially**. Wrongly serialized work merely costs latency; wrongly parallelized work corrupts state.

---

## Phase 2 Input Contract — ContextPack Enforcement

Phase 2 (Work Agent execution) has one hard precondition: the **ContextPack** returned by the Architect in Phase 1 must travel verbatim into every Work Agent prompt. The field contract for the packet itself is defined in the `arch_modules` skill, section **`## ContextPack Schema`** — this skill does **not** repeat the schema; it specifies how the packet **flows** and how it is **validated** at the Work Agent boundary.

### Coordinator obligations

1. **Forward verbatim.** Take the Architect's ContextPack block as-is; do not summarize, paraphrase, re-order, or strip fields. Loss of fidelity here defeats the whole knowledge gate.
2. **Standard placement.** Embed the ContextPack as a top-level Markdown section in the Work Agent prompt, immediately after the user's original requirement and before any agent-specific instructions, using this exact wrapper so the placement is machine-checkable:

   ```markdown
   <!-- BEGIN ContextPack -->
   ## ContextPack

   - task_id: <id>

   ### Modules
   …
   ### Dependency rules
   …
   ### Work agent notes
   …
   <!-- END ContextPack -->
   ```

   The opening `## ContextPack` heading and the `BEGIN/END ContextPack` HTML comment fences are both required. The heading is the human anchor; the fences are the machine anchor.
3. **One ContextPack per Work Agent call.** When fanning out to multiple Work Agents (parallel decomposition), each prompt carries the same ContextPack block — do not split fields across agents.

### Work Agent obligations (reject-on-missing)

A Work Agent receiving an execution task MUST refuse to execute and report back to the Coordinator when any of the following is true:

- The `<!-- BEGIN ContextPack -->` … `<!-- END ContextPack -->` block is absent, or the `## ContextPack` heading is missing inside it.
- Any of the four required top-level fields defined in `arch_modules` → `## ContextPack Schema` is missing: `task_id`, `modules` (at least one entry), `dependency_rules`, `work_agent_notes`.
- A `modules[]` entry is missing any of its required sub-fields (`path`, `dna_state`, `action_taken`, `design_constraints`).

The refusal report goes back to the Coordinator with a one-line reason (e.g. `ContextPack missing field: dependency_rules`). The Coordinator then re-dispatches Phase 1 to the Architect to repair the packet — **never** improvises the missing fields itself.

### Anti-pattern

- Coordinator hand-edits the ContextPack before forwarding ("just trimming for brevity"). Forbidden. If the packet is too large, the fix is upstream in `arch_modules`, not here.
- Work Agent silently proceeds when ContextPack is malformed. Forbidden. Silent acceptance erases the knowledge gate's value.

---

## Interruption Thresholds — When to Stop and Ask the User

Workflow steps 6 (Track) and 7 (Consolidate) run on autopilot **except** when one of the three conditions below trips. These are the only sanctioned reasons to interrupt the user mid-flow; anything else, keep the flow moving and surface it in the final consolidated reply.

| Condition | Trigger | Coordinator action |
|-----------|---------|--------------------|
| **Intent ambiguity** | One round of clarifying questions has already happened, and the routing target (which agent? which module scope?) is still not determinable. | Stop dispatch. Ask the user one focused question naming the specific ambiguity (e.g. "Did you mean module X or module Y?"). Do not guess. |
| **Result conflict** | Two or more agents returned results that contradict each other (different conclusions, incompatible designs, mutually exclusive file edits) and the conflict cannot be mechanically merged (e.g. it is not a textual diff conflict but a semantic one). | Stop consolidation. Surface the divergence to the user with each agent's position stated neutrally; let the user decide. Do not pick a side. |
| **Destructive out-of-scope action** | The flow is about to perform an irreversible operation — data deletion, remote-state mutation, rewriting git history, force-push, dropping a module, archiving memory — and that operation was **not** in the user's original authorization. | Stop before the destructive call. Name the exact operation and the blast radius; require explicit user confirmation before proceeding. |

**Outside these three, do not interrupt.** Progress reporting (`dispatched to architect, standing by`) is not an interruption — it is transparency. A genuine interruption demands a user decision before the flow can continue.

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
"""
