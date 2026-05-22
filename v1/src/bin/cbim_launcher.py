#!/usr/bin/env python3
"""CBIM launcher — version-agnostic entry point installed on PATH.

This file is intentionally minimal and extremely stable. It must work across
kernel upgrades without itself being updated. It depends only on the Python
stdlib and never imports from cbim_kernel (or installer — the launcher
bootstraps PATH before installer is reachable).

Resolution order:
  1. Detect installer-style commands (version/install/help) that bypass project lookup.
  2. Walk up from cwd to find .cbim/config.json (the project root marker).
  3. Read the project's pinned kernel version from config.json.
  4. Resolve kernel path (CBIM_KERNEL_OVERRIDE wins, else <install_root>/kernel/<version>/).
  5. Resolve Python interpreter (shared venv at <install_root>/venv/ if present, else sys.executable).
  6. Export CBIM_* env vars and exec the kernel's __main__.

Install-root resolution mirrors installer/paths.py:install_root():
  1. CBIM_INSTALL_ROOT env var
  2. Windows: %LOCALAPPDATA%\\Cbim-CC\\  (fallback: ~/AppData/Local/Cbim-CC)
  3. POSIX: $XDG_DATA_HOME/Cbim-CC/      (default: ~/.local/share/Cbim-CC)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

LAUNCHER_VERSION = "1.0.2"


# Mirror of installer/paths.py:install_root(). Keep in sync.
# Launcher must not import from installer (it bootstraps PATH before the
# installer package is on sys.path).
def _install_root() -> Path:
    env = os.environ.get("CBIM_INSTALL_ROOT")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Cbim-CC"
        return Path.home() / "AppData" / "Local" / "Cbim-CC"
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "Cbim-CC"
    return Path.home() / ".local" / "share" / "Cbim-CC"


CBIM_HOME = _install_root()

UPDATER_COMMANDS = {"install", "uninstall", "use", "versions", "pin",
                    "update", "upgrade", "migrate", "check", "apply", "self-update"}
INSTALLER_COMMANDS = UPDATER_COMMANDS  # back-compat alias
VERSION_FLAGS = {"version", "--version", "-V"}
HELP_FLAGS = {"help", "--help", "-h"}

USAGE = """\
cbim -- CBIM kernel launcher (v{ver})

Usage:
  cbim <command> [args...]      Run a kernel command in the current project
  cbim version                  Show launcher version and installed kernels
  cbim install <version>        Install a kernel version (requires installer)
  cbim init                     Initialize a new CBIM project in cwd
  cbim --help                   Show this message

Project resolution:
  The launcher walks up from the current directory looking for .cbim/config.json
  and reads the pinned kernel version from .cbim/.pin (falling back to the
  legacy 'cbim_version' field in .cbim/config.json for pre-1.3.3 projects, then
  to versions.json[active_default]).

Development overrides:
  CBIM_KERNEL_OVERRIDE   Path to a kernel checkout (bypasses version lookup)
  CBIM_DEFAULT_VERSION   Fallback version when config.json lacks 'cbim_version'
  CBIM_DEBUG             Set to any value to log resolution decisions to stderr
"""


def debug(msg):
    if os.environ.get("CBIM_DEBUG"):
        sys.stderr.write("[cbim:debug] " + msg + "\n")


def die(msg, code=1):
    sys.stderr.write("cbim: " + msg + "\n")
    sys.exit(code)


def find_project_root(start):
    """Walk up from `start` looking for `.cbim/config.json`.

    Hard boundary: the user's home directory is never returned as a project
    root, even if `~/.cbim/config.json` happens to exist. Historically the
    global kernel install lived under `~/.cbim/`; even though the new install
    root is `<install_root>/Cbim-CC/` (outside home), we keep this guard to
    protect users who still have a legacy `~/.cbim/` lying around. If the walk
    would cross home, bail out and return None so the caller treats this as
    "not in a project".
    """
    cur = Path(start).resolve()
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    while True:
        if home is not None and cur == home:
            debug("find_project_root: refusing to treat user home as project root ({})".format(cur))
            return None
        if (cur / ".cbim" / "config.json").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def read_versions_json():
    path = CBIM_HOME / "versions.json"
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        debug("failed to read {}: {}".format(path, exc))
        return None


def _active_default_version():
    """Fallback to <install_root>/versions.json[active_default] when no
    project pin is available. Returns None if versions.json is missing or
    has no active_default registered."""
    versions = read_versions_json()
    if versions and isinstance(versions.get("active_default"), str):
        v = versions["active_default"].strip()
        return v or None
    return None


def read_project_pin(project_root):
    """Read `.cbim/.pin` — the post-1.3.3 location for the project pin.

    Inlined copy of cbim_kernel.project.pin:read_pin. The launcher cannot
    import from cbim_kernel (it bootstraps PATH before kernel is on sys.path).
    Keep in sync with v1/src/kernel/cbim_kernel/project/pin.py.
    """
    pin_path = project_root / ".cbim" / ".pin"
    try:
        text = pin_path.read_text(encoding="utf-8").strip()
        return text if text else None
    except (OSError, UnicodeDecodeError) as exc:
        debug("failed to read {}: {}".format(pin_path, exc))
        return None


def read_project_version(project_root):
    """Resolve the project's pinned kernel version.

    Priority:
      1. `.cbim/.pin` (post-1.3.3 — single-line plain text).
      2. `.cbim/config.json[cbim_version]` (legacy, pre-1.3.3 layout).
    Returns None if neither is present.
    """
    pinned = read_project_pin(project_root)
    if pinned:
        return pinned
    cfg_path = project_root / ".cbim" / "config.json"
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        debug("failed to read {}: {}".format(cfg_path, exc))
        return None
    ver = cfg.get("cbim_version")
    if isinstance(ver, str) and ver.strip():
        return ver.strip()
    return None


def resolve_kernel_path(version):
    override = os.environ.get("CBIM_KERNEL_OVERRIDE")
    if override:
        p = Path(override)
        debug("using CBIM_KERNEL_OVERRIDE={}".format(p))
        if not p.is_dir():
            die("CBIM_KERNEL_OVERRIDE points to non-existent directory: {}".format(p))
        return p
    if not version:
        die("no kernel version resolved (project has no .cbim/.pin, "
            "CBIM_DEFAULT_VERSION not set, and no active_default in versions.json)")
    p = CBIM_HOME / "kernel" / version
    if not p.is_dir():
        die("Kernel version {} not installed. Run: cbim install {}".format(version, version))
    return p


def resolve_interpreter():
    venv = CBIM_HOME / "venv"
    if sys.platform == "win32":
        candidate = venv / "Scripts" / "python.exe"
    else:
        candidate = venv / "bin" / "python"
    if candidate.is_file():
        debug("using shared venv interpreter: {}".format(candidate))
        return str(candidate)
    debug("using current interpreter: {}".format(sys.executable))
    return sys.executable


def cmd_version():
    lines = ["cbim launcher {}".format(LAUNCHER_VERSION)]
    project_root = find_project_root(Path.cwd())
    if project_root:
        proj_ver = read_project_version(project_root) or os.environ.get("CBIM_DEFAULT_VERSION")
        if proj_ver:
            kpath = CBIM_HOME / "kernel" / proj_ver
            status = str(kpath) if kpath.is_dir() else "(not installed)"
            lines.append("kernel (current project): {}  -> {}".format(proj_ver, status))
        else:
            lines.append("kernel (current project): <unpinned>")
        if os.environ.get("CBIM_KERNEL_OVERRIDE"):
            lines.append("CBIM_KERNEL_OVERRIDE: {}".format(os.environ["CBIM_KERNEL_OVERRIDE"]))
    versions = read_versions_json()
    if versions is None:
        lines.append("installed kernels: (none -- {}/versions.json missing)".format(CBIM_HOME))
    else:
        installed = versions.get("installed")
        active = versions.get("active_default")
        # Schema: installed is a dict {version: {kernel_path, source, ...}}.
        # Old code treated it as a list which silently printed "(none)" forever.
        if isinstance(installed, dict) and installed:
            names = sorted(installed.keys())
            marked = [(n + " *" if n == active else n) for n in names]
            lines.append("installed kernels: " + ", ".join(marked))
        elif isinstance(installed, list) and installed:
            lines.append("installed kernels: " + ", ".join(str(v) for v in installed))
        else:
            lines.append("installed kernels: (none)")
        if active:
            lines.append("active_default: {}".format(active))
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def cmd_installer(name, args):
    """Route updater commands through <install_root>/updater (installed by install.py)."""
    updater_dir = CBIM_HOME / "updater"
    if not updater_dir.is_dir():
        sys.stderr.write(
            "cbim: updater package not found at {}.\n"
            "      Run: python install.py  (from a kernel checkout) to bootstrap.\n".format(
                updater_dir
            )
        )
        return 1
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(CBIM_HOME) + (os.pathsep + existing_pp if existing_pp else "")
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "updater", name] + list(args),
            env=env,
        )
        return result.returncode
    except OSError as exc:
        sys.stderr.write("cbim: failed to run updater: {}\n".format(exc))
        return 1


def resolve_version_for_init():
    versions = read_versions_json()
    if versions and isinstance(versions.get("active_default"), str):
        return versions["active_default"]
    env_ver = os.environ.get("CBIM_DEFAULT_VERSION")
    if env_ver:
        return env_ver
    die("No kernel installed. Run: python install.py")


def main(argv):
    if not argv or argv[0] in HELP_FLAGS:
        sys.stdout.write(USAGE.format(ver=LAUNCHER_VERSION))
        return 0

    cmd = argv[0]
    rest = argv[1:]

    if cmd in VERSION_FLAGS:
        return cmd_version()

    if cmd in INSTALLER_COMMANDS:
        return cmd_installer(cmd, rest)

    # Find project root (cwd-walk).
    project_root = find_project_root(Path.cwd())

    if project_root is None:
        if cmd == "init":
            project_root = Path.cwd().resolve()
            version = resolve_version_for_init()
        else:
            die("Not a CBIM project. Run 'cbim init' to initialize.")
            return 1  # unreachable, keeps linters happy
    else:
        version = (
            read_project_version(project_root)
            or os.environ.get("CBIM_DEFAULT_VERSION")
            or _active_default_version()
        )

    kernel_path = resolve_kernel_path(version)
    interpreter = resolve_interpreter()

    os.environ["CBIM_PROJECT_ROOT"] = str(project_root)
    os.environ["CBIM_KERNEL_ROOT"] = str(kernel_path)
    os.environ["CBIM_LAUNCHER_VERSION"] = LAUNCHER_VERSION

    kernel_main = kernel_path / "cbim_kernel" / "__main__.py"
    if not kernel_main.is_file():
        die("Kernel entry point missing: {}".format(kernel_main))

    # Inject kernel_path into PYTHONPATH so `python -m cbim_kernel` resolves.
    existing_pp = os.environ.get("PYTHONPATH", "")
    if existing_pp:
        os.environ["PYTHONPATH"] = str(kernel_path) + os.pathsep + existing_pp
    else:
        os.environ["PYTHONPATH"] = str(kernel_path)

    # Forward the full argv (including cmd) to the kernel — the launcher
    # only intercepts version/install/help/init; everything else goes through.
    cmd_list = [interpreter, "-m", "cbim_kernel"] + list(argv)
    debug("exec: {}".format(cmd_list))
    debug("PYTHONPATH: {}".format(os.environ["PYTHONPATH"]))

    if sys.platform == "win32":
        try:
            result = subprocess.run(cmd_list)
        except OSError as exc:
            die("failed to launch interpreter {}: {}".format(interpreter, exc))
        return result.returncode
    else:
        try:
            os.execv(interpreter, cmd_list)
        except OSError as exc:
            die("failed to exec interpreter {}: {}".format(interpreter, exc))
        return 1  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
