[English](INSTALL.md) | [中文](INSTALL.zh-CN.md)

# CBIM Installation Reference

For the install / refresh / uninstall / migration commands, see the [**Install** section in the repo root README](../../README.md#install). This document supplements it with the full post-deployment directory layout.

---

## Directory Structure (After Deployment)

`.dna/` directories are scattered through the codebase at any depth where a module exists; they form a tree by filesystem hierarchy. The project root **does not** require a `.dna/`. The framework-managed registry at `.cbim/.dna/index.md` is the only hard requirement (created by install, updated by `init_module`).

```
your-project/
├── CLAUDE.md                      ← Assistant identity (main session)
│
├── .claude/
│   ├── settings.json              ← Permission config + hook registration + MCP server registration
│   ├── agents/                    ← Architect / HR / Auditor / Programmer (installed by /cbim_install)
│   └── commands/                  ← Slash commands /cbim_install, /cbim_help, /cbim_dashboard, /cbim_debug, /cbim_log, /cbim_sched
│
├── src/                           ← Your code (any layout you like)
│   ├── combat/
│   │   ├── .dna/                  ← Module (parent): describes children + boundaries
│   │   │   ├── module.md          ← required: frontmatter + architecture body
│   │   │   ├── contract.md        ← optional: protocol boundary
│   │   │   ├── workflows/         ← optional: deterministic process definitions
│   │   │   └── ...                ← optional: any user-defined files
│   │   ├── skill/.dna/            ← Module (leaf): specific implementation
│   │   └── buff/.dna/             ← Module (leaf)
│   └── economy/.dna/              ← Module
│
├── .dna/                          ← OPTIONAL project-root module
│   └── module.md                  ←   (only if your project root is itself a module —
│                                  ←    single-app shape; monorepos often skip this)
│
└── .cbim/                         ← Framework (this directory)
    ├── run                        ← POSIX launcher shim (sets PYTHONPATH, execs `python -m engine`)
    ├── run.cmd                    ← Windows launcher shim
    ├── config.json                ← Local framework config
    ├── .dna/index.md              ← Module registry (framework-managed)
    ├── logs/                      ← Engine logs (gitignored)
    ├── memory/                    ← Memory store (gitignored)
    │   ├── short/                 ← Short-term session memory
    │   └── medium/                ← Medium-term distilled memory
    └── kernel/                    ← Kernel install (downloaded by /cbim_install)
        ├── engine/                ← Unified CLI dispatcher (memory / dna / agent / skill / hook / mcp / dashboard ...)
        ├── cbi/                   ← Capability + business primitives + resources
        ├── memory/                ← Memory engine
        ├── hooks/                 ← SessionStart / Stop / UserPromptSubmit / PreToolUse hook scripts
        ├── mcp_server/            ← FastMCP server + scheduler + built-in tasks
        ├── dashboard/             ← Local dashboard server
        ├── services/              ← Cross-cutting services (frontmatter, ids, ...)
        ├── project/               ← Init / sync / templates
        └── context.py             ← Shared root-resolution module
```

`agents/` depends on `skills/`; `engine/` reads `agents/` but never owns it.

The shim is the sole runtime entry point — `.cbim/run <subcommand>` sets `PYTHONPATH=<project>/.cbim/kernel` and execs `python -m engine <subcommand>`. There is no project-pinning, no global venv, and no `cbim` CLI on the user's PATH.

For the canonical install spec see [`v1/src/kernel/project/commands/cbim_install.md`](../src/kernel/project/commands/cbim_install.md).
