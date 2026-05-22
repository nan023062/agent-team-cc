---
description: Force update CBIM kernel to latest version and sync current project pin
allowed-tools: Bash
---

Force update the CBIM kernel to the latest available version (local or remote) and update the current project's pin. This is a coordinator-level system task — run it directly without agent dispatch.

## Steps

1. Run `cbim upgrade check` (with network) and show the current state to the user.

2. Determine the target version:
   - If `remote_latest` is available and newer than `app_latest_local`, the target is `remote_latest` (download required).
   - If only `app_latest_local` is newer than `project_pin`, the target is `app_latest_local` (already installed, no download needed).

3. Based on the target:
   - **Target already installed locally** (scenario 4: `app_latest_local > project_pin`):
     - Run `cbim migrate --version <target>` to update the project pin and apply any schema migrations.
   - **Target requires download** (scenario 5 or 6: remote newer than local):
     - Run `cbim update -y` to download and install, then update the project pin.

4. After completion, run `cbim upgrade check --no-network` again to confirm the new state, and show a brief summary to the user.

5. If the update was not a no-op (i.e., the version changed — not scenario 7), run `cbim release-notes <target>` (no additional flags) and print the output under a heading like "## Release notes for v<target>". If the command fails or returns empty, print a single fallback line: `(release notes unavailable — see https://github.com/nan023062/cbim/releases/tag/v<target>)`. Skip this step entirely if scenario 7 (all-aligned, nothing changed).

## Error handling

- If the network is unreachable and the local version is already up to date with what's installed, say so and offer to run `cbim migrate --version <app_latest_local>` to just advance the project pin.
- If `cbim migrate` is not available (older kernel), fall back to `cbim upgrade apply --to <target>`.

## Developer escape hatch

If the source has changed but the version was not bumped (so version comparison
short-circuits with "Already up to date") the installed snapshot will be stale.
In that case force a refresh of the current pinned version:

- `cbim update -y --reinstall` — re-download the current version from GitHub and overwrite the snapshot.
- `cbim update -y --reinstall --local <path>` — refresh the snapshot from a local kernel source directory (typical dev workflow).
- `--force` is an alias for `--reinstall`.

This is a dev-only escape hatch; it does not run project schema migration.
