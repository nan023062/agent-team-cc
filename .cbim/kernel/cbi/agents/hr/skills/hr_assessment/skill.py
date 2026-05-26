SKILL: str = """\
# Skill: Agent Assessment (HR)

> Simulates a senior leader review: structured inspection of agent definitions across two dimensions:
> 1. **Definition soundness** — format compliance, single responsibility, no capability overlap, professional focus
> 2. **Definition–behavior consistency** — whether `.claude/agents/` docs align with actual execution behavior
>
> Output is equivalent to a leader review comment: identify issues, assess severity, give remediation recommendations.

**Hard rule**: Agent definitions (soul + skills) contain only pure capability — no project-specific content whatsoever.
Project content (module names, business logic, specific paths) belongs in the business layer and exists only in the module knowledge base (`.dna/`).

## Trigger Scenarios

- After a batch of tasks completes (initiated by assistant or user)
- User explicitly reports that an agent's output is insufficient
- Auditor has rejected the same agent's deliverables ≥2 times in a row
- Periodic inspection (all work agents)

---

## Quick Check (After a Single Task)

Run basic format checks (factors 1–3) only on agents that participated in this task:

```bash
cbim agent show <name>
```

- [ ] Frontmatter fields complete (`name`, `description`, `model`, `tools`)
- [ ] `description` clearly states positioning in one sentence, directly usable for dispatch decisions
- [ ] All `SKILL.md` paths in the Skills table actually exist

---

## Full Agent Assessment

### Preparation: Run the Script First

```bash
PYTHONPATH=<install_root> python -m cbi.agents.hr.skills.hr_assessment.check --root .
```

The script automatically handles deterministic checks for factors **#1 #3 #7**, outputting a MUST / SUGGEST list.
**MUST issues must be fixed before the LLM analysis phase.**

```bash
cbim agent list
```

Run steps 1–5 for each work agent (single-agent review), then run step 6 (cross-agent horizontal comparison).

---

### Step 1 — Basic Format

| # | Factor | Compliance Standard | Check By |
|---|--------|--------------------|----|
| 1 | Frontmatter complete | `name`, `description`, `model`, `tools` all filled in | **Script** |
| 2 | Description usable | One-sentence positioning; assistant can dispatch without ambiguity | LLM |
| 3 | Skill paths valid and non-empty | Every `SKILL.md` path in the Skills table exists, is readable, and is not a placeholder (threshold in `config.json`) | **Script** |

---

### Step 2 — Single Responsibility (Vertical: Per-Agent Self-Check)

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 4 | Single responsibility | Responsibility description can be stated in one sentence within its professional domain; if it contains "and" / "also responsible for", responsibility is too broad | LLM |
| 5 | Trigger scenarios focused | All entries in the trigger scenarios list point to the same category of needs; no cross-domain moonlighting | LLM |

---

### Step 3 — Capability Focus (Per-Agent)

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 6 | Skills direction consistent | All skills point to the same professional direction; no capability drift (e.g., agent has business dev + ops + review skills simultaneously) | LLM |
| 7 | Skill count reasonable | When skill count reaches the threshold, suggest fission: capability too broad, should split into multiple specialized agents (threshold in `config.json`) | **Script** |
| 8 | Tools minimally necessary | Authorized tools include only what the responsibility actually requires; no excess authorizations | LLM |

---

### Step 4 — Business Purity (Hard Rule)

Agent definitions are **portable capability descriptions**, not project documents.

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 9 | Soul has no project content | `<id>.md` body does not contain: project names, module names, business logic, current task status, specific file paths (.cbim/ framework paths excepted) | LLM |
| 10 | Skills have no project content | Each `SKILL.md` describes only operation methods and judgment principles; does not reference specific project module names or business rules | LLM |
| 11 | Portability self-check | If this agent definition were placed in a completely different project, would it still make sense? Yes → compliant; No → project coupling exists and must be removed | LLM |

---

### Step 5 — Definition–Behavior Consistency

Collect recent execution records:

```bash
cbim memory query "<agent-name>" --top-k 15
cbim memory query "review <agent-name>" --top-k 5
```

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 12 | Boundary compliance | Actual execution did not exceed scope (did things outside definition) or miss scope (didn't do what it should) | LLM |
| 13 | Definition supports behavior | Frequently executed operations have corresponding descriptions in soul or skills; no "not in definition but always done" hidden responsibilities | LLM |
| 14 | Behavior supports definition | Defined responsibilities are actually used; directions with no tasks long-term are considered redundant — suggest trimming or archiving | LLM |

---

### Step 6 — Capability Overlap Check (Horizontal: Cross-Agent Comparison)

**Full assessment only.** After completing all single-agent reviews, compare all work agents pairwise to find capability overlap pairs.

**Comparison method**:
1. List all work agents' `description` + `skills`
2. Compare pairwise: do `description` fields describe similar responsibilities? Do `skills` have substantive overlap?
3. For each overlap pair, classify the overlap:

| Overlap Type | Criteria | Remediation |
|-------------|----------|-------------|
| **Full overlap** | Both descriptions are nearly equivalent; skills highly overlapping | Merge into one; retire the weaker |
| **Partial overlap** | 1–2 skills point to the same capability direction | Clarify boundary: which agent owns it; remove that skill from the other |
| **Scenario compatible** | Different descriptions but trigger scenarios intersect | Refine trigger conditions for each to avoid dispatch ambiguity |

| # | Factor | Check Method | Check By |
|---|--------|-------------|----------|
| 15 | No capability overlap | Any two work agents' core capability directions have no substantive overlap | LLM |
| 16 | No dispatch ambiguity | The assistant, facing the same type of request, can clearly determine which agent to dispatch — no ambiguity | LLM |

**When overlap is found**: Record the overlap pair + overlap type + recommended remediation, output to report.

---

## Output: Assessment Report

```
Assessment Date: <YYYY-MM-DD>

── Dimension 1: Definition Soundness ───────────────────────

  Basic Format (#1–3):
    - [MUST/SUGGEST] [#factor] <Agent-id>: <issue> → <recommendation>

  Single Responsibility (#4–5, vertical):
    - [MUST/SUGGEST] [#factor] <Agent-id>: <issue> → <recommendation>

  Capability Focus (#6–8):
    - [SUGGEST] [#factor] <Agent-id>: <issue> → fission / trim tools

  Business Purity (#9–11):
    - [MUST] [#factor] <Agent-id>: <specific coupled content> → remove; project content goes to .dna/

  Capability Overlap (#15–16, horizontal):
    - [MUST/SUGGEST] <Agent-A> × <Agent-B>: <overlap type> — <specific overlap> → <recommendation>

── Dimension 2: Definition–Behavior Consistency (#12–14) ────

    - [MUST/SUGGEST/WARN] [#factor] <Agent-id>: <issue> → <recommendation>

── Summary ─────────────────────────────────────────────────

MUST (must fix): <N>
SUGGEST (recommended): <N>
WARN (needs confirmation): <N>

Remediation conclusions (per agent):
  - <Agent-id>: train / fission / archive / no action needed
Follow-up actions:
  - Training → execute hr-training/SKILL.md
  - Fission / merge → execute hr-agents/SKILL.md fission flow
  - Archive → execute hr-agents/SKILL.md archive flow
```

**Severity definitions**:
- `MUST` — Violates hard rules (business coupling, full capability overlap) or severe format omission; must fix
- `SUGGEST` — Improvable (responsibility too broad, capability drift, redundant tools, partial overlap); recommended
- `WARN` — Requires human judgment (definition–behavior mismatch, long-term idle, scenario compatible); escalate to assistant
"""
