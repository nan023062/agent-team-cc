SKILL: str = """\
# Skill: Query Memory

**Main agent only. Use when historical retrieval is needed mid-session.**

---

## Command Format

Run from the CBIM root directory (where `memory/` package lives):

```bash
# Default: return top-k most recently modified entries (short + medium combined, sorted by time)
cbim memory query "" --top-k 5

# Single tier only
cbim memory query "" --tier short --top-k 5
cbim memory query "" --tier medium --top-k 3
```

If CBIM is installed as a subdirectory (e.g. `.cbim/`), prefix with that path:

```bash
cbim memory query "" --top-k 5
```

The default backend (FileBackend) sorts by modification time; the query text argument is ignored.
If switched to a semantic backend (ChromaBackend), the query text participates in similarity ranking.

---

## Usage Flow

1. Run the commands above to get a list of file paths
2. Read the markdown content at each path (Read tool)
3. Extract context relevant to the current task from the content

---

## Common Scenarios

| What to find | Recommended Command |
|-------------|---------------------|
| What happened in recent sessions | `query "" --tier short --top-k 5` |
| Agent capability pattern summary | `query "" --tier medium --top-k 10`, then Read capability-*.md |
| Historical decisions for a module | `query "" --tier medium`, then Read business-<module>.md |

---

## Rebuild Index

After switching to a semantic backend, reindex existing files:

```bash
cbim memory reindex
```
"""
