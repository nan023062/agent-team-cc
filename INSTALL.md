# CBIM Installation Guide

Open Claude Code in the target project and paste the entire **"SOP Body"** section (from the `---` divider to the end) as a message. Claude Code will complete all installation steps automatically.

> **Prerequisites**: Target project has a Git repository, Python ≥ 3.10, network access to GitHub.

---

# Task: Install CBIM Framework in This Project

Execute the following steps one by one. Stop and ask the user for confirmation if blocked or uncertain — do not skip silently.

## Step 0 — Confirm Target Directory

Run the following command, show the user the current directory contents, and confirm this is the project root where the framework should be installed:

```bash
pwd && ls
```

If the user says the directory is wrong, stop and wait for the user to `cd` to the correct location before continuing.

## Step 1 — Check Prerequisites

```bash
python3 --version
git --version
```

- Python version must be ≥ 3.10; otherwise prompt the user to upgrade Python first.
- git must be available.

## Step 2 — Download CBIM Framework

Clone the repository into a temporary directory, then perform a clean replacement of the `cbim/` directory in the project root. On both first-time installs and upgrades, the old `cbim/` is fully removed before the new one is copied in, so no stale files from previous versions can linger. The one exception is `cbim/memory/store/`, which holds user memory data and is backed up before replacement and restored afterward.

Linux / macOS:
```bash
git clone https://github.com/nan023062/cbim.git _cbim_tmp
# 备份记忆数据
[ -d cbim/memory/store ] && cp -r cbim/memory/store _cbim_store_bak
# 完整替换
rm -rf cbim
cp -r _cbim_tmp/cbim .
rm -rf _cbim_tmp
# 还原记忆数据
if [ -d _cbim_store_bak ]; then
  rm -rf cbim/memory/store
  mv _cbim_store_bak cbim/memory/store
fi
```

Windows (PowerShell):
```powershell
git clone https://github.com/nan023062/cbim.git _cbim_tmp
# 备份记忆数据
if (Test-Path cbim\memory\store) {
    Copy-Item -Recurse cbim\memory\store _cbim_store_bak
}
# 完整替换
Remove-Item -Recurse -Force cbim -ErrorAction SilentlyContinue
Copy-Item -Recurse _cbim_tmp\cbim .\cbim
Remove-Item -Recurse -Force _cbim_tmp
# 还原记忆数据
if (Test-Path _cbim_store_bak) {
    Remove-Item -Recurse -Force cbim\memory\store -ErrorAction SilentlyContinue
    Move-Item _cbim_store_bak cbim\memory\store
}
```

## Step 3 — Run the Installer

```bash
python3 cbim/install.py
```

Windows:
```powershell
python cbim\install.py
```

The script will automatically:
- Create a `.venv` virtual environment
- Copy agent definitions to `.claude/agents/`
- Register SessionStart / Stop hooks in `.claude/settings.json`
- Initialize `CLAUDE.md`
- Create memory directories `cbim/memory/store/{short,medium}/`
- Update `.gitignore`

The script outputs `+` (done) or `-` (skipped/already exists) for each step, and prints `Done. Restart Claude Code to activate hooks.` at the end.

If the script errors, stop and report the error to the user — do not continue.

## Step 4 — Verify Installation

Run the following check and show the result to the user:

```bash
ls CLAUDE.md cbim/ .claude/agents/ .venv/
```

Installation is successful if CLAUDE.md, cbim/, .claude/agents/, and .venv/ all exist.

## Step 5 — Final Report

Briefly report to the user:

1. ✅/❌ Result of each step
2. **Next steps**:
   - Fully exit and restart Claude Code (required to activate hooks)
   - Recommended first message after restart: **"Please initialize the module knowledge system for this project"**
   - The assistant will dispatch the architect to build the `.dna/` project knowledge system, after which you're ready to use it

## Failure Handling Principles

- Any step fails → stop immediately, report the failure reason and completed steps, wait for user decision
- Do not execute irreversible operations like `git push`, `git commit`, `rm -rf` on user files (unless explicitly requested)
