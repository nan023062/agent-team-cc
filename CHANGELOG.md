# Changelog

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

All notable changes to CBIM are recorded here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows semantic versioning at the kernel level.

---

## [1.3.3] - 2026-05-22

### Motivation

The project schema pin — the per-project version number that tells the kernel "this project is on schema X" — is the single most frequently written piece of project state. It moves every time you run `cbim update`, `cbim upgrade apply`, or `cbim migrate`. Living inside `.cbim/config.json` meant every pin bump:

- polluted `git diff` with a full JSON re-serialization of the whole config file, even when no user-visible setting changed;
- forced a JSON load-modify-dump round-trip just to flip one integer;
- mixed a machine-owned cursor with user-owned configuration in the same file, making "what should I commit?" ambiguous.

### Changed

- Project schema pin extracted from `.cbim/config.json` to a dedicated plain-text file `.cbim/.pin`.
  - One line: the version string, terminated with a single newline. No JSON, no fields, no comments.
  - The file is added to `.gitignore` — pin is local project state, not source.
- All reads and writes of the pin now go through a single accessor module `project/pin.py` (hard rule — no other code may touch `.cbim/.pin` directly).
- `cbim_version` is removed from `.cbim/config.json`. The kernel no longer reads or writes that key.

### Migration

Run either of the following once per project; both are idempotent:

```bash
cbim update -y
# or, if you only want to migrate without fetching a new kernel:
cbim migrate --version 1.3.3
```

The migrator will:

1. Read the legacy `cbim_version` from `.cbim/config.json`.
2. Write it into `.cbim/.pin` (single line, trailing newline).
3. Delete `cbim_version` from `.cbim/config.json`.
4. Append `.cbim/.pin` to `.gitignore` if not already present.

After migration, `git diff` no longer shows churn on every pin bump.

---

## [1.3.2] - 2026-05-22

### Fixed

- `cbim migrate` always advanced the project pin, even when the project layout was already on the latest schema. It now no-ops when there is nothing to migrate.
- `cbim upgrade apply` preflight error messages referenced a `--to` flag that no longer exists. They now correctly point users to `--version`.
- `diagnose.py` and the `/cbim_update` slash command had inconsistent flag names. Both now use `--version` everywhere.

---

## [1.3.1] - 2026-05-22

### Fixed

- `cbim upgrade apply` was still passing the removed `--set-default` flag through to a sub-call, causing every upgrade to roll back. The orphaned flag is removed and upgrade now applies cleanly.

---

## [1.3.0] - 2026-05-21

### Changed

- Baseline version bump. No behavior change for end users; this release exists to align the kernel version line with the new schema-pin work that lands in 1.3.1+.
