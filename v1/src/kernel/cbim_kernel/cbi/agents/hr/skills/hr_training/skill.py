SKILL: str = """\
# Skill: Agent Training (HR)

> Extract signals from medium-memory capability entries, and promote validated patterns to Skills or internalize them into the Soul, raising a work agent's capability ceiling.

## Trigger Scenarios

- Assessment conclusion is "capability gap, needs training"
- Assistant reports that an agent repeatedly makes the same type of error
- Auditor continuously rejects the same agent's deliverables
- Medium-memory `capability-<agent-id>.md` has unchecked governance items

---

## Training Process

### Step 1 — Read Medium Capability Entry

List the agent's medium-tier entries:

```bash
cbim memory query "" --tier medium --top-k 20
```

Find `capability-<agent-id>.md`; read its full content with the Read tool.

Focus on:
- `## MUST Records`: violated behavioral constraints (negative signals)
- `## HOW Records`: validated effective flows (positive signals)
- `## Summary`: overall assessment of the agent's current capability state
- `## Governance Recommendations`: unchecked items from the last distillation

### Step 2 — Determine Promotion Target by Four-Quadrant

| Quadrant | Signal Content | Promotion Target | Condition |
|----------|---------------|-----------------|-----------|
| **MUST** | Behavioral constraints that must not be violated | Soul (`## Principles` section) | Appeared ≥`distill.must_review_threshold` times (default 2, see `memory/config.json`) |
| **HOW** (validated) | Effective flows reusable across tasks | Skill file | Appeared ≥`distill.how_to_skill_threshold` times and holds across projects (default 3, see `memory/config.json`) |
| **HOW** (unvalidated) | Appeared only 1–2 times | Keep in medium, continue observing | Continue accumulating |

**Portability self-check** (required before promoting MUST / HOW):
> If this content were placed in a different project, a different language codebase — does it still make sense?
- Yes → promote (soul / skill)
- No, depends on current project context → keep in medium, do not promote

### Step 3 — Write to Soul or Add New Skill

**Update Soul** (handling MUST signals):

Edit `.claude/agents/<id>/<id>.md`:

```markdown
## Principles
(append new behavioral constraints; keep concise, one line each)
- Before executing bulk deletes, must display expected change scope and get confirmation
- When encountering undefined business terms, must clarify before executing — do not self-interpret
```

Do not modify frontmatter (`model`, `tools` require user confirmation).

**Add New Skill** (handling HOW signals):

```
.claude/agents/<id>/skills/<skill-name>.md

# Skill: <Scenario Name>

## Trigger Conditions
(when to activate this skill)

## Steps
1. ...
2. ...

## Output Format
(expected deliverable format)

## Boundaries and Notes
(what not to do, known boundary conditions)
```

### Step 4 — Update Governance Recommendations in Medium Entry

Check off completed governance items to prevent re-processing:

```markdown
## Governance Recommendations
- [x] Distilled to Skill (HOW pattern appeared ≥`how_to_skill_threshold` times)  ← done
- [x] Internalized to Soul (MUST principle validated as stable)                    ← done
- [ ] Trigger HR assessment (capability gap repeated ≥`must_review_threshold` times) ← pending
```

### Step 5 — Report

Report to the assistant:

```
## Training Report — <agent-id>

### Soul Updates
- New principle: [content] (source: capability-<id>.md MUST records × N times)

### New Skills
- <skill-name>: [one-line description] (source: HOW records × N times)

### Retained for Observation
- [content] (appeared only N times, continue accumulating)

### Not Promoted — Reason
- [content]: project-specific details; does not meet cross-project portability requirement
```
"""
