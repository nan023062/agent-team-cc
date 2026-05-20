SKILL: str = """\
# Skill: Knowledge Promotion (Architect)

> Extract signals from medium-memory business and decision entries, and distill verified facts, decisions, and processes back into `.dna/` as persistent business knowledge.

## Trigger Scenarios

- A batch of tasks is complete and involves interface changes or important architecture decisions
- The same business flow has appeared ≥2 times (worth turning into a workflow)
- The assistant requests knowledge consolidation for a module
- Medium-memory `business-*.md` or `decision-*.md` has unchecked governance items

---

## Promotion Process

### Step 1 — Read Medium Business and Decision Entries

List all medium-tier entries:

```bash
python .cbim/engine memory query "" --tier medium --top-k 20
```

Find `business-<module>.md` and `decision-<scope>.md` related to the target module; read their full content with the Read tool.

Focus on:
- `## IS Records`: interface changes, business rule changes, config changes (→ `contract.md` if protocol-boundary module, otherwise `module.md`)
- `## HOW Records`: recurring deterministic execution flows (→ `workflows/`)
- `## Decision Records`: WANT-type selections and trade-offs (→ `module.md`)
- `## Governance Recommendations`: unchecked items from the last distillation

### Step 2 — Determine Promotion Target by Four-Quadrant

| Quadrant | Signal Content | Promotion Target | Condition |
|----------|---------------|-----------------|-----------|
| **IS** | Interface signatures, business rule definitions, config values | `contract.md` (if protocol-boundary module) or `module.md` | Promote on any change; sync current facts |
| **WANT** | Selection decision with trade-off rationale (ADR format) | `module.md` | Promote once decision is implemented |
| **HOW** (business) | Deterministic execution flow within the module | `workflows/<name>/workflow.md` | Appeared ≥`distill.how_to_workflow_threshold` times, steps stable (default 2, see `memory/config.json`) |
| HOW (once only) | Flow not yet validated | Keep in medium, continue observing | Continue accumulating |

**Do NOT promote**: one-time debug records, unvalidated assumptions, temporary project-specific solutions.

### Step 3 — Write to the Knowledge Pack (module.md + optional contract)

**`contract.md`** (handling IS signals -- only for protocol-boundary modules that have contract.md)

Sync the current latest facts, including old and new values:

```markdown
## <Interface or Rule Name>

Current value: <new value>
Change log:
- YYYY-MM-DD: <old value> → <new value>, reason: <change reason>

Example:
## Damage Calculation Interface
Current signature: calculate(actor, target, context)
Change log:
- 2026-05-15: calculate(actor, target) → calculate(actor, target, context)
  Reason: added context to support buff stacking

## "Active User" Definition
Current: purchased within 90 days
Change log:
- 2026-05-18: logged in within 90 days → purchased within 90 days
  Reason: finance audit requires revenue linkage
  Note: historical data before 2026-Q2 still uses the old definition
```

**`module.md`** (handling WANT signals)

Append decision entries using ADR (Y-statement) format:

```markdown
## Decision: <Title>

In the context of <background>,
facing <core constraint>,
we chose <option A> over <option B>,
to achieve <goal>,
accepting <trade-off>.

Decision by: <person/agent>, date: YYYY-MM-DD
```

**Create New Workflow** (handling HOW signals, appeared ≥2 times):

```
.dna/workflows/<workflow-name>/workflow.md

# Workflow: <Name>

## Trigger Conditions
(when to run this flow)

## Prerequisites
(conditions that must be met before running)

## Steps
1. ...
2. ...

## Output
(expected deliverables)

## Notes
(steps that must not be skipped, known boundaries)
```

### Step 4 — Update Governance Recommendations in Medium Entry

Check off completed governance items to prevent re-processing:

```markdown
## Governance Recommendations
- [x] IS changes written to `.dna/contract.md` or `module.md` (interface signature updated)   ← done
- [x] HOW flow distilled to `.dna/workflows/` (appeared ≥`how_to_workflow_threshold` times)       ← done
- [ ] Notify architect for review (interface changed)                                               ← pending
```

### Step 5 — Run Compliance Check

After promotion, run `arch-governance` quick check to confirm written content meets standards.

### Step 6 — Report

Report to the assistant:

```
## Knowledge Promotion Report — <module name>

### contract.md / module.md Updates
- <interface/rule name>: <change summary> (source: business-<module>.md IS records × N times)

### module.md Updates
- New decision: <title> (source: decision-<scope>.md WANT record)

### New Workflows
- <workflow-name>: <one-line description> (source: HOW records × N times)

### Retained for Observation
- <content>: only appeared N times, continue accumulating

### Recommended Next Actions
- [ ] Auditor review of new workflow
- [ ] Notify programmer that interface signature has changed
```
"""
