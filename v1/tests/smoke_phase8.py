"""
Phase 8 smoke test — verify the managed `.cbim/.venv/` install flow.

Init builds a project-local venv at `.cbim/.venv/`, installs `mcp` into it,
and points the `.cbim/run` shim at `.venv/bin/python`. Behavior is idempotent
(skip when healthy), self-healing (rebuild when python is gone, re-pip when
mcp is missing), and never touches the user's system Python.

Four scenarios:
  A. Clean install — venv built, mcp present, shim points at .venv, run --help
     works, no [cbim] WARNING about mcp.
  B. Idempotent re-run — second init reports "skipped (already up to date)"
     for the venv; venv dir mtime unchanged; mcp not re-installed.
  C. Broken python self-heal — delete .venv/bin/python, re-init; venv is
     rebuilt and mcp is re-installed.
  D. Missing mcp self-heal — uninstall mcp inside the venv, re-init; venv
     is NOT rebuilt (python survives) but mcp is reinstalled.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
KERNEL_SRC = HERE.parent / "src" / "kernel"


def _stage_kernel(tmp: Path) -> None:
    """Mirror install.sh: copy the kernel tree into .cbim/kernel/ so the shim
    can resolve `$DIR/kernel` at runtime."""
    dst = tmp / ".cbim" / "kernel"
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in ("__pycache__", ".pytest_cache")]

    shutil.copytree(KERNEL_SRC, dst, ignore=_ignore)


def _run_init(tmp: Path, timeout: int = 180) -> tuple[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(KERNEL_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "engine", "init"],
        capture_output=True,
        cwd=str(tmp),
        env=env,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"init failed: stdout={proc.stdout.decode()!r} stderr={proc.stderr.decode()!r}"
        )
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def _venv_python(tmp: Path) -> Path:
    if os.name == "nt":
        return tmp / ".cbim" / ".venv" / "Scripts" / "python.exe"
    return tmp / ".cbim" / ".venv" / "bin" / "python"


def _import_mcp(venv_python: Path) -> int:
    proc = subprocess.run(
        [str(venv_python), "-c", "import mcp"],
        capture_output=True,
    )
    return proc.returncode


def _assert(cond: bool, msg: str, results: list[tuple[bool, str]]) -> None:
    results.append((cond, msg))
    marker = "PASS" if cond else "FAIL"
    print(f"  [{marker}] {msg}")


def scenario_a(results: list[tuple[bool, str]]) -> None:
    print("Scenario A — clean install:")
    with tempfile.TemporaryDirectory(prefix="cbim_p8a_") as raw:
        tmp = Path(raw)
        _stage_kernel(tmp)
        stdout, stderr = _run_init(tmp)

        vp = _venv_python(tmp)
        _assert(vp.exists(), ".cbim/.venv/bin/python exists", results)
        _assert(_import_mcp(vp) == 0, "venv python can `import mcp`", results)

        shim = tmp / ".cbim" / "run"
        _assert(shim.exists(), ".cbim/run exists", results)
        shim_text = shim.read_text(encoding="utf-8")
        _assert(".venv/bin/python" in shim_text, "shim invokes .venv/bin/python", results)

        # run --help should print engine help; we only care that it doesn't error.
        help_proc = subprocess.run(
            [str(shim), "--help"], capture_output=True, cwd=str(tmp), timeout=30
        )
        _assert(help_proc.returncode == 0,
                f".cbim/run --help exits 0 (stderr={help_proc.stderr.decode()!r})",
                results)

        merged = stdout + stderr
        _assert("[cbim] WARNING" not in merged or "mcp" not in merged.split("[cbim] WARNING", 1)[-1].splitlines()[0],
                "no [cbim] WARNING about mcp in init output", results)


def scenario_b(results: list[tuple[bool, str]]) -> None:
    print("Scenario B — idempotent re-run:")
    with tempfile.TemporaryDirectory(prefix="cbim_p8b_") as raw:
        tmp = Path(raw)
        _stage_kernel(tmp)
        _run_init(tmp)

        venv_dir = tmp / ".cbim" / ".venv"
        vp = _venv_python(tmp)
        mtime_before = venv_dir.stat().st_mtime
        # Capture a witness file inside site-packages to detect re-pip-install.
        # mcp installs `mcp/__init__.py` somewhere under site-packages.
        result = subprocess.run(
            [str(vp), "-c", "import mcp, os; print(os.path.dirname(mcp.__file__))"],
            capture_output=True, text=True,
        )
        mcp_dir = Path(result.stdout.strip())
        mcp_init_mtime_before = (mcp_dir / "__init__.py").stat().st_mtime

        stdout, stderr = _run_init(tmp)
        merged = stdout + stderr

        _assert("skipped (already up to date) .cbim/.venv" in merged,
                "second init reports venv 'skipped (already up to date)'", results)
        _assert(venv_dir.stat().st_mtime == mtime_before,
                "venv dir mtime unchanged on re-run", results)
        _assert((mcp_dir / "__init__.py").stat().st_mtime == mcp_init_mtime_before,
                "mcp package not re-installed (mcp/__init__.py mtime unchanged)",
                results)


def scenario_c(results: list[tuple[bool, str]]) -> None:
    print("Scenario C — broken venv python self-heal:")
    with tempfile.TemporaryDirectory(prefix="cbim_p8c_") as raw:
        tmp = Path(raw)
        _stage_kernel(tmp)
        _run_init(tmp)

        vp = _venv_python(tmp)
        _assert(vp.exists(), "venv python exists after first init", results)

        # Break the venv: remove the python interpreter symlink/binary.
        # On POSIX it's typically a symlink; unlink works for both.
        vp.unlink()
        _assert(not vp.exists(), "venv python removed (pre-condition)", results)

        _run_init(tmp)

        _assert(vp.exists(), "venv python restored after self-heal init", results)
        _assert(_import_mcp(vp) == 0,
                "mcp importable from rebuilt venv", results)


def scenario_d(results: list[tuple[bool, str]]) -> None:
    print("Scenario D — missing mcp self-heal:")
    with tempfile.TemporaryDirectory(prefix="cbim_p8d_") as raw:
        tmp = Path(raw)
        _stage_kernel(tmp)
        _run_init(tmp)

        vp = _venv_python(tmp)
        venv_dir = tmp / ".cbim" / ".venv"

        # Uninstall mcp from the venv. `pip uninstall -y` is the clean path.
        uninstall = subprocess.run(
            [str(vp), "-m", "pip", "uninstall", "-y", "mcp"],
            capture_output=True, text=True, timeout=60,
        )
        _assert(uninstall.returncode == 0,
                f"pip uninstall mcp succeeded (stderr={uninstall.stderr!r})",
                results)
        _assert(_import_mcp(vp) != 0,
                "import mcp fails before self-heal (pre-condition)", results)

        # Capture marker file inside venv to detect rebuild vs repair.
        # pyvenv.cfg is created once at venv build time; survives repair, dies on rebuild.
        pyvenv_cfg = venv_dir / "pyvenv.cfg"
        cfg_mtime_before = pyvenv_cfg.stat().st_mtime

        _run_init(tmp)

        _assert(vp.exists(), "venv python still present (not rebuilt)", results)
        _assert(pyvenv_cfg.stat().st_mtime == cfg_mtime_before,
                "pyvenv.cfg mtime unchanged (venv not rebuilt, only repaired)",
                results)
        _assert(_import_mcp(vp) == 0,
                "mcp re-installed into existing venv", results)


def main() -> int:
    results: list[tuple[bool, str]] = []
    scenario_a(results)
    scenario_b(results)
    scenario_c(results)
    scenario_d(results)

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    print()
    print(f"phase8_smoke: {passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
