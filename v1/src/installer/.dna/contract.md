# Installer Contract

This contract is the **public surface** that `cbim_kernel/project/upgrade/` (and the launcher) depend on. Changes here are breaking changes.

## Path Entrypoints (the 5 stable doors)

| Entry | Returns | Purpose |
|-------|---------|---------|
| `installer.paths.install_root()` | `Path` | The absolute install root. |
| `installer.registry.cbim_home()` | `Path` | Alias for `install_root()` (lazy). |
| `installer.registry.versions_file()` | `Path` | `<install_root>/versions.json`. |
| `installer.venv_mgr.venv_path()` | `Path` | Shared Python venv. |
| `installer.bootstrap.bin_dir()` | `Path` | Where the launcher binary is installed. |

Callers must use these entries. Hard-coding `Path.home() / ".cbim"` or any other path is forbidden.

## Versions Registry Schema

File: `<install_root>/versions.json`. Atomic writes only.

```json
{
  "active_default": "1.2.3",
  "installed": {
    "1.2.3": {
      "installed_at": "2026-05-21T10:30:00Z",
      "kernel_path": "<install_root>/kernel/1.2.3",
      "venv_path": "<install_root>/venv",
      "source": "local | git | github | tarball"
    }
  }
}
```

`active_default` is null when no kernel is installed.

## Registry Read API

| Function | Signature | Notes |
|----------|-----------|-------|
| `registry.load()` | `() -> dict` | Returns empty schema if file missing — never raises. |
| `registry.list_installed()` | `() -> list[str]` | Sorted version strings. |
| `registry.get_default()` | `() -> str \| None` | The pinned default, or None. |
| `registry.get_kernel_path(version)` | `(str) -> Path \| None` | None if version not installed. |

## Registry Write API

| Function | Signature | Notes |
|----------|-----------|-------|
| `registry.register(version, kernel_path, venv_path, source)` | atomic | Adds/updates entry; does NOT touch `active_default`. |
| `registry.set_default(version)` | atomic | Raises `ValueError` if version not installed. |
| `registry.save(data)` | atomic | Full overwrite. Last resort; prefer `register` / `set_default`. |

## Install Entrypoint (subprocess only)

The kernel-side `upgrade.apply` MUST shell out to the installer; it MUST NOT `import installer.install`. The on-disk launcher delegates `cbim install <ver>` to `python -m installer install <ver>` under the install root.

```
python -m installer install <version> [--source local|git|github] [--from <path-or-url>]
python -m installer use <version>     # set active_default
python -m installer versions          # list
python -m installer uninstall <version>
```

Exit code 0 = success; non-zero = failure with stderr diagnostic. Callers must inspect exit code, not parse stdout.

## Forbidden

- Importing `cbim_kernel` from any installer module.
- Modifying `versions.json` outside of `registry.save()` / `register()` / `set_default()`.
- Writing to `<install_root>/` from kernel-side code without going through this contract.
- Assuming the install root location; always resolve through `paths.install_root()`.
