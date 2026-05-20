SKILL: str = """\
# Skill: Capability Layer CRUD (HR)

> Manage work agent definitions under `.claude/agents/`. The 4 core agents (architect / hr / auditor and the assistant) are read-only and must not be modified.

## Tools

```bash
python .cbim-prompt/engine agent list                              # list all agents
python .cbim-prompt/engine agent show <name>                       # view agent details
python .cbim-prompt/engine agent scaffold <name> --description "..." [--model claude-sonnet-4-6]
```

---

## Recruit a New Agent

**Trigger**: Assistant requests a new agent, or an existing agent's capabilities need to split.

1. Generate scaffold file with `agents.py scaffold`
2. Fill in `.claude/agents/<id>/<id>.md`:
   - frontmatter: `name / description / model / tools`
   - `## Responsibilities` — one-line positioning
   - `## Principles` — 2–4 behavioral boundaries
   - `## Trigger Scenarios` — when should the assistant dispatch this agent
3. Create `skills/` directory (can be empty initially; add as needed)
4. Report to the assistant: new agent name, positioning, trigger scenarios

**Portability rule**: soul/identity contains only professional capability — no project-specific content whatsoever. If it still makes sense in a different project → write it; otherwise → leave in memory.

---

## Update Agent Definition

**Trigger**: Training conclusions implemented, soul internalized, responsibility scope adjusted.

- Add skill: create `<skill-name>.md` under `.claude/agents/<id>/skills/`
- Update soul: directly edit the responsibilities/principles section of `.claude/agents/<id>/<id>.md`
- Expand tools: modify the frontmatter `tools:` field (requires user confirmation)

---

## Archive an Agent

**Trigger**: Agent has been idle long-term, responsibilities already covered by another agent, or retired after a fission.

```bash
# Rename with .archived suffix
mv .claude/agents/<id>/<id>.md .claude/agents/<id>/<id>.md.archived
```

Report the archive reason and date to the assistant; the assistant decides whether to update CLAUDE.md accordingly.

---

## Fission (One → Many)

**Trigger**: Agent context bloating, responsibility scope too broad, assessment reveals insufficient focus.

1. Analyze the existing agent's responsibilities; identify sub-domains
2. `scaffold` a new agent for each sub-domain
3. Distribute the old agent's skills to each new agent by ownership
4. Archive the old agent
5. Report the fission plan to the assistant; execute after confirmation
"""
