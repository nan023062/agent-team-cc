SKILL: str = """\
# Skill: Request Classification and Dispatch (engine-internal resource)

> **NOTE (v2)**: As of phase 4C this skill is no longer read by the coordinator.
> Control flow has moved into the behavior-tree engine (`engine/execution/`). This file
> is retained as a static data source consumed by:
>
>   - `engine.execution.actions.intent_analyze.IntentRules` — the classification table
>   - `engine.execution.actions.aggregate.Aggregate` — the conflict-detection thresholds
>   - `engine.execution.actions.converge_judge.ConvergeJudge` — the interruption table
>
> The coordinator MUST NOT read this skill. Coordinator behavior is in
> `CLAUDE.md ## Workflow` and the tree topology in
> `engine/execution/tree/main_loop.py`.

---

## Classification Table (consumed by IntentAnalyze)

| Request Type | Decision Basis | Dispatch Target |
|-------------|---------------|----------------|
| **Business layer CRUD** | Involves module design, architecture, compliance, knowledge system (`.dna/`) | Architect (`architect`) |
| **Capability layer CRUD** | Involves agent recruitment, training, assessment, archiving | HR (`hr`) |
| **Execution task** | Any coding work: implement features, add functionality, write code, fix bugs, refactor | **Two-phase:** first Architect for task context, then work agent (e.g., `programmer`) with that context |
| **Review request** | Review design, changes, decisions; adversarial perspective needed | Auditor (`auditor`) |

---

## Classification Examples (consumed by IntentAnalyze.rules)

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

## Interruption Thresholds (consumed by Aggregate + ConvergeJudge)

| Condition | Trigger | Engine action |
|-----------|---------|---------------|
| **Intent ambiguity** | One round of clarifying questions has already happened, and the routing target (which agent? which module scope?) is still not determinable. | Stop dispatch. Surface one focused question naming the specific ambiguity (e.g. "Did you mean module X or module Y?") via `BtResult(kind="done", user_message=<question>)`. Do not guess. |
| **Result conflict** | Two or more agents returned results that contradict each other (different conclusions, incompatible designs, mutually exclusive file edits) and the conflict cannot be mechanically merged (e.g. it is not a textual diff conflict but a semantic one). | Stop consolidation. Surface the divergence via `BtResult(kind="error", interrupt_reason="conflict: <details>")`. The coordinator relays it to the user with each agent's position stated neutrally; do not pick a side. |
| **Destructive out-of-scope action** | The flow is about to perform an irreversible operation — data deletion, remote-state mutation, rewriting git history, force-push, dropping a module, archiving memory — and that operation was **not** in the user's original authorization. | Stop before the destructive call. Surface via `BtResult(kind="error", interrupt_reason="destructive_unauthorized: <op>")` naming the exact operation and the blast radius; require explicit user confirmation before proceeding. |

**Outside these three, do not interrupt.**
"""
