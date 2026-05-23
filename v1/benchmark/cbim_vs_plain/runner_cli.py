"""CLI driver for the CBIM-vs-plain benchmark.

Loads every `tasks/task_*.py` module, runs A/B on each, writes session logs to
--logs-dir and a side-by-side markdown report to --report.
"""

from __future__ import annotations

import argparse
import importlib
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from ._report import render_ab_markdown
from .runner import AbResult, ModeResult, run_ab


def _discover_tasks(tasks_dir: Path) -> list:
    mods = []
    for p in sorted(tasks_dir.glob("task_*.py")):
        if p.name.startswith("_"):
            continue
        modname = f"v1.benchmark.cbim_vs_plain.tasks.{p.stem}"
        mods.append(importlib.import_module(modname))
    return mods


def _persist_logs(ab: AbResult, logs_dir: Path) -> None:
    """Copy session logs out of ephemeral project dirs into logs_dir."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    for mode in (ab.plain, ab.cbim):
        src_log = mode.result.session_log_path
        dst = logs_dir / f"{ab.task_name}.{mode.mode}.log"
        if src_log and src_log.exists():
            try:
                shutil.copy2(src_log, dst)
            except OSError as e:
                dst.write_text(f"[runner] could not copy session log: {e!r}\n")
        else:
            # No session log (plain mode has no .cbim/, so this is expected).
            dst.write_text(
                f"[runner] no session log for {ab.task_name} {mode.mode}\n"
                f"exit_code={mode.result.exit_code}\n"
                f"wall={mode.result.wall_time_s:.2f}s\n"
                f"--- stdout (truncated 4kB) ---\n"
                f"{(mode.result.stdout or '')[:4096]}\n"
                f"--- stderr (truncated 4kB) ---\n"
                f"{(mode.result.stderr or '')[:4096]}\n"
            )


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m v1.benchmark.cbim_vs_plain.runner_cli",
        description="Run CBIM-vs-plain A/B benchmark across all task files.",
    )
    ap.add_argument("--fixture", required=True, type=Path,
                    help="Path to fixture/ project root (the shared test target)")
    ap.add_argument("--tasks-dir", required=True, type=Path,
                    help="Path to tasks/ directory containing task_*.py")
    ap.add_argument("--logs-dir", required=True, type=Path,
                    help="Where to copy session logs after each run")
    ap.add_argument("--report", required=True, type=Path,
                    help="Output path for the markdown report")
    ap.add_argument("--ts-start", default="",
                    help="Run-start timestamp (passed in from shell script)")
    ap.add_argument("--timeout", type=int, default=300,
                    help="Per-claude-call timeout in seconds (default 300)")
    args = ap.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_dir():
        print(f"[runner_cli] fixture not found: {fixture}", file=sys.stderr)
        return 2

    tasks_dir = args.tasks_dir.resolve()
    if not tasks_dir.is_dir():
        print(f"[runner_cli] tasks_dir not found: {tasks_dir}", file=sys.stderr)
        return 2

    tasks = _discover_tasks(tasks_dir)
    if not tasks:
        print(f"[runner_cli] no task_*.py modules found in {tasks_dir}", file=sys.stderr)
        return 2

    print(f"[runner_cli] {len(tasks)} task(s) × 2 modes = {len(tasks) * 2} runs", flush=True)

    ab_results: list[AbResult] = []
    for i, mod in enumerate(tasks, 1):
        print(f"[runner_cli] ({i}/{len(tasks)}) {mod.NAME} ...", flush=True)
        try:
            ab = run_ab(mod, fixture, timeout=args.timeout)
        except Exception:  # noqa: BLE001
            print(f"[runner_cli] {mod.NAME} crashed:", file=sys.stderr)
            traceback.print_exc()
            continue
        _persist_logs(ab, args.logs_dir)
        print(
            f"[runner_cli]   plain: {'PASS' if ab.plain.success else 'FAIL'} "
            f"({ab.plain.result.wall_time_s:.1f}s, exit={ab.plain.result.exit_code})  "
            f"cbim: {'PASS' if ab.cbim.success else 'FAIL'} "
            f"({ab.cbim.result.wall_time_s:.1f}s, exit={ab.cbim.result.exit_code})",
            flush=True,
        )
        ab_results.append(ab)

    metadata = {
        "Start": args.ts_start or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "End": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Fixture": str(fixture),
        "Logs": str(args.logs_dir),
    }
    title = f"CBIM vs Plain Agent Benchmark — {args.report.stem}"
    md = render_ab_markdown(ab_results, title=title, metadata=metadata)
    args.report.write_text(md, encoding="utf-8")
    print(f"[runner_cli] wrote {args.report}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
