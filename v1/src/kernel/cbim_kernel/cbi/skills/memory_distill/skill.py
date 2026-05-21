SKILL: str = """\
# Skill: Memory Distillation (Short → Medium)

**Main agent only. Triggered periodically or on demand.**

Compress short-term session records into medium-term pattern summaries, providing raw material for HR capability governance and architect business governance.
Medium-term memory is organized by **four quadrants**, each determining where information ultimately flows in the governance structure.

---

## Trigger Timing

| Scenario | Description |
|----------|-------------|
| User explicitly requests | "Distill memory" / "Summarize recent sessions" |
| Accumulation threshold | `short/` has ≥`distill.suggest_threshold` unprocessed entries — proactively suggest (default 5, see `memory/config.json`) |
| Governance prerequisite | Before HR assessment / architect governance, run this skill first to ensure medium memory is current |

---

## Prerequisite: Complete Signal Fields

Entries written by the Stop hook have empty signal rows by default. **Signals must be filled in before distillation** (see write.md spec); otherwise there is no material to distill.

For each pending `short/*.md`, check the `## Signals` section and complete the `- [x]` lines.

---

## Step 1 — Scan Short-term Entries, Group by Quadrant

Read all pending entries under `memory/short/`; collect checked signals (`- [x]` prefix).

Classify by four quadrants:

| Quadrant | Collection Key | Medium File Name |
|----------|---------------|-----------------|
| MUST | agent-id | `capability-<agent-id>.md` |
| HOW (capability-oriented) | agent-id | `capability-<agent-id>.md` |
| WANT | module name / scope | `decision-<scope>.md` |
| HOW (business-oriented) | module name | `business-<module>.md` |
| IS | module name | `business-<module>.md` |

> To judge whether HOW is capability-oriented or business-oriented: still holds in another project → capability; strongly tied to current business context → business.

---

## Step 2 — Determine Whether to Distill

| Scenario | Action |
|----------|--------|
| **User corrected an agent's behavior** (MUST) | **Must distill** — highest priority |
| **IS-type change** (interface, rule, config) | **Must distill** — prevents future decisions based on stale facts |
| **WANT-type decision** | **Must distill** — recording "why" is the core of architectural knowledge |
| Same agent / module signal repeating across multiple entries | **Must distill** — repetition indicates pattern, not coincidence |
| Single occurrence, but describes a clear gap or effective pattern | **Recommended** — assess generalization value |
| Single occurrence, highly context-specific | May defer; keep in short-term |

**Five judgment criteria (for borderline cases):**
1. Cost of loss: would future decisions deteriorate without this information?
2. Generalizability: is this a one-time detail or a cross-task reusable principle?
3. Stability: does it remain valid beyond the current session?
4. Root-cause value: does it explain "why" rather than just "what"?
5. Error-prevention value: would recording it prevent a past error from recurring?

---

## Step 3 — Write or Update Medium Entry

**If file exists → update; if not → create.**

### Capability Medium Entry (MUST + capability-oriented HOW)

File: `memory/medium/capability-<agent-id>.md`

```markdown
---
tier: medium
type: capability
keyword: programmer
updated: YYYY-MM-DD
sources: 5
---

## Summary

Overall assessment of this agent's current capability patterns (one paragraph; rewrite on each update, do not append).

Example:
programmer lacks proactive locking awareness in concurrent write scenarios; needs user prompts to handle race conditions.
Performs stably on single-threaded sequential tasks; skilled at breaking down steps and calling tool chains.
Has established a dry-run prerequisite habit; zero errors in the past 8 write-operation tasks.

## MUST Records (Behavioral Constraints)

| Date | Source Entry | Content | Trigger Reason |
|------|-------------|---------|---------------|
| 2026-05-10 | 2026-05-10-main-xxx.md | Must display change scope before bulk deletes | User corrected a mistaken deletion |

## HOW Records (Effective Flows)

| Date | Source Entry | Content |
|------|-------------|---------|
| 2026-05-12 | 2026-05-12-main-yyy.md | Contract first then architecture; interface is more stable |

## Governance Recommendations

- [ ] Distill to Skill (HOW pattern appeared ≥`how_to_skill_threshold` times, see `memory/config.json`)
- [ ] Internalize to Soul (MUST principle validated as stable, appeared ≥`must_review_threshold` times)
- [ ] Trigger HR assessment (capability gap repeated ≥`must_review_threshold` times)
```

### Decision Medium Entry (WANT)

File: `memory/medium/decision-<scope>.md`

```markdown
---
tier: medium
type: decision
keyword: memory-module
updated: YYYY-MM-DD
sources: 2
---

## Decision Records

Using ADR (Y-statement) format:

### [Decision Title]
In the context of [background],
facing [core constraint],
we chose [option A] over [option B],
to achieve [goal],
accepting [trade-off].

Example:
In a multi-agent system requiring memory retrieval,
facing the trade-off between "zero external dependencies" and "semantic search",
we chose FileBackend (sorted by time) over ChromaDB (vector search),
to achieve install-ready, no network dependency,
accepting that retrieval does not support semantic similarity — sorted by time only.

Decision by: linan, date: 2026-05-18

## Governance Recommendations

- [ ] Write to `.dna/module.md` (decision is stable, no further changes needed)
```

### Business Medium Entry (business-oriented HOW + IS)

File: `memory/medium/business-<module>.md`

```markdown
---
tier: medium
type: business
keyword: combat
updated: YYYY-MM-DD
sources: 4
---

## Summary

Overall description of this module's current state and key patterns (rewrite on each update, do not append).

## IS Records (Current Facts)

| Date | Source Entry | Content | Change Type |
|------|-------------|---------|------------|
| 2026-05-15 | 2026-05-15-main-zzz.md | Damage interface signature changed to calculate(actor, target, context) | Interface change |
| 2026-05-10 | 2026-05-10-main-aaa.md | "Active user" definition: login → purchase | Business rule change |

## HOW Records (Business Flows)

| Date | Source Entry | Content | Count |
|------|-------------|---------|-------|
| 2026-05-12 | 2026-05-12-main-bbb.md | Damage calculation: receive → validate → calculate → broadcast, no skipping | 3 |

## Governance Recommendations

- [ ] IS changes written to `.dna/contract.md` or `module.md` (interface signature updated)
- [ ] HOW flow distilled to `.dna/workflows/` (appeared ≥`how_to_workflow_threshold` times, see `memory/config.json`)
- [ ] Notify architect for review (interface changed)
```

---

## Step 4 — Rules for Updating Existing Entries

1. Append new rows to the `## Signal Records` table
2. Increment `sources` count by the number of new entries
3. Update `updated` to today's date
4. **Rewrite `## Summary`** to reflect the latest signals — do not append and accumulate
5. Update `## Governance Recommendations` checkbox states based on new signals

---

## Step 5 — Mark Processed Short-term Entries

After distillation, **do not immediately delete** short-term entries — instead, add a `distilled` marker to the frontmatter.
The engine's periodic cleanup will delete entries that are "marked + older than 3 days", preserving recent memory.

For every entry scanned in Step 1 (whether or not signals were found), add the marker with the Edit tool:

```markdown
---
tier: short
tags: session
modules: combat
distilled: 2026-05-18     ← add this line
---
```

**Do not mark**:
- Entries intentionally skipped this round (signals pending confirmation) → leave as-is; process next distillation

**Fallback cleanup** (clean entries that are "marked + older than 3 days"):

```bash
python .cbim/engine memory cleanup --keep-days 3
```

`last-session.md` is an independent file not subject to this lifecycle.

---

## Step 6 — Report and Recommend Next Actions

```
## Memory Distillation Summary ({date range}, {N} entries)

### MUST ({N} principles)
| Agent | Content | Trigger Reason |
|-------|---------|---------------|
| programmer | Confirm before bulk delete | User corrected a mistaken deletion |

### WANT ({N} decisions)
| Scope | Decision Summary |
|-------|----------------|
| memory-module | FileBackend vs ChromaDB, chose zero dependencies |

### HOW ({N} flows)
| Dimension | Content | Count |
|-----------|---------|-------|
| architect (capability) | Contract first then architecture | 3 |
| combat (business) | Damage calculation four-step flow | 2 |

### IS ({N} fact changes)
| Module | Change |
|--------|--------|
| combat | Interface signature updated |
| auth | Token validity 24h→8h |

### Recommended Next Actions
Capability governance:
- HR assess programmer (MUST gap × 2 times)
- HR distill architect HOW to Skill (appeared × 3 times)

Business governance:
- Architect update combat contract.md / module.md (interface signature changed)
- Architect distill combat HOW to workflow (× 2 times)
- Architect record memory-module WANT decision to module.md
```

Whether to trigger HR assessment / architect governance after distillation is decided by the user.
"""
