# CBIM Installation Guide

Open Claude Code in the target project and paste the entire **"SOP Body"** section (from the `---` divider to the end) as a message. Claude Code will complete all installation steps automatically.

> **Prerequisites**: Target project has a Git repository, Python ≥ 3.10, network access to GitHub.

---

# Task: Install CBIM Framework in This Project

This is a copy-based install — no installer script is run. Clone the source repo to a temp directory, copy four artifacts into the target project, create a venv, done.

Execute the steps below one by one. Stop and ask the user for confirmation if blocked or uncertain — do not skip silently.

## Step 0 — Confirm Target Directory

```bash
pwd && ls
```

Show the user the current directory contents and confirm this is the project root. If wrong, stop and wait for the user to `cd` to the correct location.

## Step 1 — Check Prerequisites

```bash
python3 --version
git --version
```

- Python must be ≥ 3.10.
- Git must be available.

## Step 2 — Clone Source Repo to Temp

Linux / macOS:
```bash
TMP=$(mktemp -d)
git clone --depth=1 --branch master https://github.com/nan023062/cbim.git "$TMP/src"
```

Windows (PowerShell):
```powershell
$TMP = (New-Item -ItemType Directory -Path ([System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid())).FullName
git clone --depth=1 --branch master https://github.com/nan023062/cbim.git "$TMP\src"
```

Verify the four required artifacts exist in the clone:
```bash
ls "$TMP/src/.cbim" "$TMP/src/.claude" "$TMP/src/CLAUDE.md" "$TMP/src/.claudeignore"
```

If any is missing, stop and report — the upstream repo is incomplete.

## Step 3 — Install the Four Artifacts (merge-aware)

Two artifacts are overwritten cleanly; two are merged to preserve user data.

| Artifact | Strategy | Why |
|---|---|---|
| `.cbim/` | clean replace, **preserve** `memory/store/`, `.dna/`, `config.json` | framework files must match upstream; runtime data must survive |
| `.claude/agents/` | clean replace | agents are framework-defined |
| `.claude/settings.json` | **merge** — overwrite only `hooks` and `permissions` keys | preserve user-added MCP servers, env, model, theme, custom permissions |
| `CLAUDE.md` | overwrite, backup to `CLAUDE.md.bak` if different | template owned by framework |
| `.claudeignore` | **append-if-missing** per line | preserve user-added ignore patterns |

### 3a. Back up runtime data and CLAUDE.md

Linux / macOS:
```bash
[ -d .cbim/memory/store ] && cp -r .cbim/memory/store "$TMP/_store_bak"
[ -d .cbim/.dna ]         && cp -r .cbim/.dna         "$TMP/_dna_bak"
[ -f .cbim/config.json ]  && cp    .cbim/config.json  "$TMP/_config_bak"
[ -f CLAUDE.md ] && cp CLAUDE.md "$TMP/_claude_md_bak"
```

Windows (PowerShell):
```powershell
if (Test-Path .cbim\memory\store) { Copy-Item -Recurse .cbim\memory\store "$TMP\_store_bak" }
if (Test-Path .cbim\.dna)         { Copy-Item -Recurse .cbim\.dna         "$TMP\_dna_bak" }
if (Test-Path .cbim\config.json)  { Copy-Item          .cbim\config.json  "$TMP\_config_bak" }
if (Test-Path CLAUDE.md) { Copy-Item CLAUDE.md "$TMP\_claude_md_bak" }
```

### 3b. Clean-replace framework + agents

Linux / macOS:
```bash
rm -rf .cbim .claude/agents
mkdir -p .claude
cp -R "$TMP/src/.cbim"   .cbim
cp -R "$TMP/src/.claude/agents" .claude/agents
```

Windows (PowerShell):
```powershell
Remove-Item -Recurse -Force .cbim, .claude\agents -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path .claude | Out-Null
Copy-Item -Recurse "$TMP\src\.cbim"   .cbim
Copy-Item -Recurse "$TMP\src\.claude\agents" .claude\agents
```

### 3c. Restore runtime data + ensure required dirs

`.cbim/memory/store/{short,medium}/` and `.cbim/.dna/index.md` are gitignored or runtime-managed and won't be in the clone — create them if missing.

Linux / macOS:
```bash
# Restore preserved data
[ -d "$TMP/_store_bak" ]  && { rm -rf .cbim/memory/store; mkdir -p .cbim/memory; cp -r "$TMP/_store_bak" .cbim/memory/store; }
[ -d "$TMP/_dna_bak" ]    && { rm -rf .cbim/.dna;          cp -r "$TMP/_dna_bak"   .cbim/.dna; }
[ -f "$TMP/_config_bak" ] && cp "$TMP/_config_bak" .cbim/config.json

# Ensure required runtime dirs/files exist (no-op if already restored)
mkdir -p .cbim/memory/store/short .cbim/memory/store/medium
mkdir -p .cbim/.dna
[ -f .cbim/.dna/index.md ] || printf "# Module Index\n" > .cbim/.dna/index.md
[ -f .cbim/config.json ]   || printf '{\n  "target_project": "",\n  "memory": {\n    "short_term": {"keep_days": 3}\n  }\n}\n' > .cbim/config.json
```

Windows (PowerShell):
```powershell
if (Test-Path "$TMP\_store_bak")  { Remove-Item -Recurse -Force .cbim\memory\store -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force -Path .cbim\memory | Out-Null; Copy-Item -Recurse "$TMP\_store_bak" .cbim\memory\store }
if (Test-Path "$TMP\_dna_bak")    { Remove-Item -Recurse -Force .cbim\.dna -ErrorAction SilentlyContinue; Copy-Item -Recurse "$TMP\_dna_bak" .cbim\.dna }
if (Test-Path "$TMP\_config_bak") { Copy-Item "$TMP\_config_bak" .cbim\config.json }

New-Item -ItemType Directory -Force -Path .cbim\memory\store\short, .cbim\memory\store\medium, .cbim\.dna | Out-Null
if (-not (Test-Path .cbim\.dna\index.md)) { Set-Content -Path .cbim\.dna\index.md -Value "# Module Index" -NoNewline; Add-Content -Path .cbim\.dna\index.md -Value "" }
if (-not (Test-Path .cbim\config.json))   { Set-Content -Path .cbim\config.json   -Value '{"target_project":"","memory":{"short_term":{"keep_days":3}}}' }
```

### 3d. Merge .claude/settings.json (preserve user keys)

Replace only `hooks` and `permissions`; leave everything else (MCP servers, env, model, theme, etc.) untouched.

```bash
python3 - "$TMP/src/.claude/settings.json" .claude/settings.json <<'PY'
import json, sys
from pathlib import Path
src = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
dst_path = Path(sys.argv[2])
dst = json.loads(dst_path.read_text(encoding="utf-8")) if dst_path.exists() else {}
dst["hooks"] = src["hooks"]
dst["permissions"] = src["permissions"]
dst_path.parent.mkdir(parents=True, exist_ok=True)
dst_path.write_text(json.dumps(dst, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"merged hooks + permissions into {dst_path}")
PY
```

(Same command works on Windows — just use `python` instead of `python3`.)

### 3e. CLAUDE.md (overwrite with backup)

```bash
if [ -f "$TMP/_claude_md_bak" ] && ! cmp -s "$TMP/_claude_md_bak" "$TMP/src/CLAUDE.md"; then
  cp "$TMP/_claude_md_bak" CLAUDE.md.bak
fi
cp "$TMP/src/CLAUDE.md" CLAUDE.md
```

Windows (PowerShell):
```powershell
if (Test-Path "$TMP\_claude_md_bak") {
  $srcHash = (Get-FileHash "$TMP\src\CLAUDE.md").Hash
  $bakHash = (Get-FileHash "$TMP\_claude_md_bak").Hash
  if ($srcHash -ne $bakHash) { Copy-Item "$TMP\_claude_md_bak" CLAUDE.md.bak }
}
Copy-Item "$TMP\src\CLAUDE.md" CLAUDE.md
```

### 3f. .claudeignore (append-if-missing per line)

```bash
SRC_IGNORE="$TMP/src/.claudeignore"
touch .claudeignore
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  grep -qxF -- "$line" .claudeignore || printf "%s\n" "$line" >> .claudeignore
done < "$SRC_IGNORE"
```

Windows (PowerShell):
```powershell
if (-not (Test-Path .claudeignore)) { New-Item -ItemType File -Path .claudeignore | Out-Null }
$existing = Get-Content .claudeignore -ErrorAction SilentlyContinue
Get-Content "$TMP\src\.claudeignore" | ForEach-Object {
  if ($_ -and ($existing -notcontains $_)) { Add-Content -Path .claudeignore -Value $_ }
}
```

## Step 4 — Create the Virtual Environment

The framework's hooks shell out to `python` — a project-local `.venv` is the convention.

Linux / macOS:
```bash
[ -d .venv ] || python3 -m venv .venv
```

Windows (PowerShell):
```powershell
if (-not (Test-Path .venv)) { python -m venv .venv }
```

(FileBackend uses stdlib only — no `pip install` step required.)

## Step 5 — Update .gitignore

Append these lines if missing:
```
.cbim/memory/store/
__pycache__/
*.pyc
.venv/
```

Linux / macOS one-liner:
```bash
touch .gitignore
for line in '.cbim/memory/store/' '__pycache__/' '*.pyc' '.venv/'; do
  grep -qxF -- "$line" .gitignore || printf "%s\n" "$line" >> .gitignore
done
```

## Step 6 — Verify

```bash
ls CLAUDE.md .cbim/ .claude/agents/ .claude/settings.json .claudeignore .venv/ .cbim/.dna/index.md .cbim/memory/store/short .cbim/memory/store/medium
```

All paths must exist.

## Step 7 — Cleanup

```bash
rm -rf "$TMP"
```

Windows:
```powershell
Remove-Item -Recurse -Force "$TMP"
```

## Step 8 — Final Report

Briefly report to the user:

1. ✅/❌ Result of each step
2. **Next steps**:
   - Fully exit and restart Claude Code (required to activate hooks)
   - Recommended first message after restart: **"Please initialize the module knowledge system for this project"**
   - The assistant will dispatch the architect to build the `.dna/` project knowledge system

## Failure Handling Principles

- Any step fails → stop immediately, report the failure reason and completed steps, wait for user decision
- Do not execute irreversible operations like `git push`, `git commit`, `rm -rf` on user files (unless explicitly requested)
- If the cloned source repo is missing `.cbim/`, `.claude/`, `CLAUDE.md`, or `.claudeignore`, abort — the upstream repo must commit these four artifacts for the copy-based install to work
