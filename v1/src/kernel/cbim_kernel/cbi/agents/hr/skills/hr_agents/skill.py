SKILL: str = """\
# Skill: Capability Layer CRUD (HR)

> Manage work agent definitions under `.claude/agents/`. The 4 core agents (architect / hr / auditor and the assistant) are read-only and must not be modified.

## Tools

All writes to `.claude/agents/` MUST go through the kernel CLI (Kernel-Only Writes hard rule). Never use `Write`/`Edit`/shell redirection against this directory.

```bash
cbim agent list                              # list all agents
cbim agent show <name>                       # view agent details
cbim agent scaffold <name> --description "..." [--model claude-sonnet-4-6]
cbim agent archive <name>                    # rename to .md.archived (atomic)

# Edit an existing agent (frontmatter / body / single section)
cbim agent update <name> --target frontmatter --field {description|model|tools} (--value VAL | --value-list ITEM ...)
cbim agent update <name> --target body (--content STR | --content-file PATH | --stdin)
cbim agent update <name> --target section --heading "TEXT" [--level {2,3}] [--mode {replace|append|insert-after|delete}] (--content STR | --content-file PATH | --stdin) [--create-if-missing]
cbim agent update <name> ... --dry-run       # print rendered result; no disk write

# Add a new per-agent skill markdown file
cbim agent add-skill <agent_name> <skill_name> (--content STR | --content-file PATH | --stdin) [--dry-run]
```

Notes on `agent update`:
- `--field name` is rejected (renaming an agent is a separate operation, not a frontmatter edit). Editable fields: `description`, `model`, `tools`.
- Editing one of the 4 kernel-managed agents (`architect / auditor / hr / programmer`) emits a warning — those files are overwritten by `cbim project sync`.

Notes on `agent add-skill`:
- Refuses to overwrite an existing skill; exits 2 with a clear message.

---

## Recruit a New Agent

**Trigger**: Assistant requests a new agent, or an existing agent's capabilities need to split.

1. Generate scaffold file with `cbim agent scaffold <name> --description "..."`
2. Fill in `.claude/agents/<id>/<id>.md` via the kernel CLI:
   - frontmatter `description / model / tools` via `cbim agent update <id> --target frontmatter --field <F> --value <V>`
   - body sections (`## Responsibilities`, `## Principles`, `## Trigger Scenarios`) via `cbim agent update <id> --target section --heading "..." --mode replace --content-file <path>` (use `--create-if-missing` for the initial fill)
3. Add per-agent skills as needed: `cbim agent add-skill <id> <skill-name> --content-file <path>`
4. Report to the assistant: new agent name, positioning, trigger scenarios

**Portability rule**: soul/identity contains only professional capability — no project-specific content whatsoever. If it still makes sense in a different project → write it; otherwise → leave in memory.

---

## Update Agent Definition

**Trigger**: Training conclusions implemented, soul internalized, responsibility scope adjusted.

- Add skill: `cbim agent add-skill <id> <skill-name> --content-file <path>`
- Update soul section (e.g. `## Principles`): `cbim agent update <id> --target section --heading "Principles" --mode {replace|append} --content-file <path>`
- Full body rewrite (rare): `cbim agent update <id> --target body --content-file <path>`
- Expand tools (requires user confirmation): `cbim agent update <id> --target frontmatter --field tools --value "Read, Grep, Bash"` (tools is currently a comma-string; preserve that shape — do not pass `--value-list`)

---

## Archive an Agent

**Trigger**: Agent has been idle long-term, responsibilities already covered by another agent, or retired after a fission.

```bash
cbim agent archive <name>
```

Report the archive reason and date to the assistant; the assistant decides whether to update CLAUDE.md accordingly.

---

## Fission (One → Many)

**Trigger**: Agent context bloating, responsibility scope too broad, assessment reveals insufficient focus.

1. Analyze the existing agent's responsibilities; identify sub-domains
2. `cbim agent scaffold` a new agent for each sub-domain
3. Distribute the old agent's skills to each new agent by ownership — read each skill from the old agent's `skills/` directory and republish via `cbim agent add-skill <new-id> <skill-name> --content-file <path>`
4. `cbim agent archive` the old agent
5. Report the fission plan to the assistant; execute after confirmation
"""
