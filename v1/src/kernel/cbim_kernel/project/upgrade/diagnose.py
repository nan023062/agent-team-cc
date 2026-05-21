"""Pure 7-scenario diagnostic.

NO I/O, NO subprocess, NO filesystem access. Receives pre-fetched
``AppState`` / ``ProjectState`` / ``RemoteState`` and returns a ``Diagnosis``.

The 7 scenarios are spec'd in ``upgrade/.dna/module.md``. Any change to the
matrix MUST be reflected here, in the contract, and in tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from cbim_kernel.project.upgrade.app_state import AppState
from cbim_kernel.project.upgrade.project_state import ProjectState
from cbim_kernel.project.upgrade.remote import RemoteState


@dataclass
class Command:
    cmd: str
    description: str

    # Compatibility alias for the contract's "shell" key.
    @property
    def shell(self) -> str:
        return self.cmd


@dataclass
class Diagnosis:
    scenario: int
    scenario_name: str
    app: AppState
    project: ProjectState
    remote: RemoteState
    recommendation: str
    commands: list  # list[Command]
    ordered: bool = False


def _version_key(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _newer(a: Optional[str], b: Optional[str]) -> bool:
    """True if ``a`` is strictly newer than ``b`` (both non-None)."""
    if not a or not b:
        return False
    return _version_key(a) > _version_key(b)


def scenario_id(
    app_installed: bool,
    app_outdated: bool,
    pin_installed: bool,
    pin_outdated: bool,
    remote_reachable: bool,
) -> int:
    """Classify into 1..7. See module.md matrix for the truth table.

    Inputs collapse the joint state:
      - app_installed:    any kernel installed in <install_root>/
      - app_outdated:     remote_reachable AND remote > app.latest_local
      - pin_installed:    project pin is in app.installed_versions
      - pin_outdated:     pin exists AND app.latest_local > pin
      - remote_reachable: remote ls-remote succeeded
    """
    # 1) cold-start: nothing on app side, nothing on project side.
    if not app_installed and not pin_installed:
        return 1

    # Project has no pin (pin_installed False AND no pin string present is the
    # "not initialized" axis). Distinguish 2 vs 3 by app freshness.
    # The caller is responsible for setting pin_installed=False when no
    # project pin exists at all.
    if app_installed and not pin_installed:
        # Differentiate "project new" by checking pin: handled by caller via
        # project_state.pin is None. If pin is None we are in row 2/3.
        # If pin exists but is not installed, that's a different bug
        # (broken pin); diagnose() routes that through the "project_state has
        # pin but not in installed" branch — caller must classify accordingly.
        return 3 if app_outdated else 2

    # Both sides present. Distinguish 4/5/6/7.
    if app_installed and pin_installed:
        if not pin_outdated and not app_outdated:
            return 7  # all-aligned
        if not pin_outdated and app_outdated:
            return 6  # app-stale-project-aligned
        if pin_outdated and not app_outdated:
            return 4  # project-stale-vs-app
        # pin_outdated AND app_outdated
        return 5  # both-stale

    # Fallback (shouldn't be reached given the truth table). Treat as 1.
    return 1


_SCENARIO_NAMES = {
    1: "cold-start",
    2: "app-ready-project-new",
    3: "app-stale-project-new",
    4: "project-stale-vs-app",
    5: "both-stale",
    6: "app-stale-project-aligned",
    7: "all-aligned",
}


def diagnose(
    app: AppState,
    project: ProjectState,
    remote: RemoteState,
) -> Diagnosis:
    """Return a Diagnosis for the joint state. Pure function."""
    app_installed = bool(app.installed)
    pin = project.pin
    latest_local = app.latest_local
    remote_latest = remote.latest if remote.reachable else None

    pin_installed = bool(pin and pin in app.installed)
    app_outdated = remote.reachable and _newer(remote_latest, latest_local)
    pin_outdated = bool(pin and latest_local and _newer(latest_local, pin))

    # If pin exists but is NOT installed, treat it like "project pinned to
    # something the app doesn't have" — closest scenario is 4 (project drift).
    # That's not strictly one of the 7, but the user action is the same:
    # either install the pinned version or migrate to current app.
    if pin and not pin_installed:
        # Reuse scenario 4 path: project-stale-vs-app, but recommend install.
        sid = 4
    else:
        sid = scenario_id(
            app_installed=app_installed,
            app_outdated=app_outdated,
            pin_installed=pin_installed,
            pin_outdated=pin_outdated,
            remote_reachable=remote.reachable,
        )

    rec, cmds, ordered = _build_recommendation(
        sid=sid,
        app=app,
        project=project,
        remote=remote,
        latest_local=latest_local,
        remote_latest=remote_latest,
    )

    return Diagnosis(
        scenario=sid,
        scenario_name=_SCENARIO_NAMES.get(sid, "unknown"),
        app=app,
        project=project,
        remote=remote,
        recommendation=rec,
        commands=cmds,
        ordered=ordered,
    )


def _build_recommendation(
    sid: int,
    app: AppState,
    project: ProjectState,
    remote: RemoteState,
    latest_local: Optional[str],
    remote_latest: Optional[str],
) -> tuple:
    pin = project.pin
    if sid == 1:
        return (
            "No CBIM install and no project. Bootstrap both.",
            [
                Command(
                    cmd="python install.py",
                    description="Bootstrap the CBIM installer (download or run from a kernel checkout)",
                ),
                Command(
                    cmd="cbim init",
                    description="Initialize a new CBIM project in the target directory",
                ),
            ],
            True,
        )

    if sid == 2:
        return (
            f"App is current at {latest_local}; project not yet initialized.",
            [Command(cmd="cbim init", description="Initialize the project in cwd")],
            False,
        )

    if sid == 3:
        target = remote_latest or "<latest>"
        return (
            f"App is at {latest_local}, remote latest is {remote_latest}; "
            "upgrade the app first, then initialize the project.",
            [
                Command(
                    cmd=f"cbim upgrade apply --to {target}",
                    description="Upgrade app to remote latest",
                ),
                Command(cmd="cbim init", description="Initialize the project in cwd"),
            ],
            True,
        )

    if sid == 4:
        app_current = latest_local or "<app-current>"
        cmds: list = [
            Command(
                cmd=f"cbim migrate --to {app_current}",
                description="Recommended: migrate project schema to the app's current version",
            ),
            Command(
                cmd=f"cbim pin {pin}" if pin else "cbim pin <X>",
                description="Alternative: keep the project pinned and install the pinned version instead",
            ),
        ]
        return (
            f"Project pin ({pin}) is older than the app's current version ({app_current}). "
            "Either migrate the project, or keep the pin and install it.",
            cmds,
            False,
        )

    if sid == 5:
        target = remote_latest or "<latest>"
        return (
            "App is older than remote; project pin is older than app.",
            [
                Command(
                    cmd=f"cbim upgrade apply --to {target}",
                    description="Upgrade app to remote latest",
                ),
                Command(
                    cmd=f"cbim migrate --to {target}",
                    description=f"Migrate project schema to {target}",
                ),
            ],
            True,
        )

    if sid == 6:
        target = remote_latest or "<latest>"
        return (
            f"App and project are aligned at {pin}, but remote has a newer version ({remote_latest}).",
            [
                Command(
                    cmd=f"cbim upgrade apply --to {target}",
                    description=(
                        "Upgrade app to remote latest; project pin stays at "
                        f"{pin} unless you also run `cbim migrate --to {target}`"
                    ),
                ),
            ],
            False,
        )

    if sid == 7:
        return (
            f"All aligned at version {pin}.",
            [],
            False,
        )

    return ("Unknown state.", [], False)
