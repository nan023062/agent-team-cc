"""
mcp_server/scheduler.py — Async task scheduler embedded in the MCP server.

A scheduler instance is owned by the FastMCP lifespan. On startup it:
  1. Discovers Task subclasses under .cbim/mcp_server/tasks/*.py
  2. Loads run-state from .cbim/scheduler/state.json
  3. Spawns a background asyncio task ticking every TICK_SECONDS

Each Task declares:
  name              kebab-case identifier (also state-file key)
  description       one-line human summary
  interval_seconds  fire every N seconds; 0 = manual only
  respect_cc_idle   if True, only fire when CC is idle (per .cbim/.cc-status)
  async def run(ctx) → str: actual work; return a one-line result summary

Scheduler results are appended to the current session log with [SCHED] tag.

Lifetime: tied to the MCP server process. CC starts the server → scheduler starts.
CC exits → scheduler dies. For tasks that need to run when CC is offline, launch
the server standalone (`python .cbim/mcp_server/server.py`).
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import json
import time
from datetime import datetime
from pathlib import Path


TICK_SECONDS = 30


class Task:
    """Base class for a scheduled task. Subclass and override `run()`."""

    name: str = ""
    description: str = ""
    interval_seconds: int = 0      # 0 = manual only
    respect_cc_idle: bool = False  # True = only fire when CC is idle

    async def run(self, context: dict) -> str:
        raise NotImplementedError


class Scheduler:
    def __init__(self, cbim_root: Path):
        from context import project_root as _project_root
        self.cbim_root = cbim_root
        self.project_root = _project_root()
        # Task code ships with the kernel package; discovered via importlib
        # against the mcp_server.tasks package (no filesystem path needed —
        # see _reload_tasks).
        self.state_dir = cbim_root / "scheduler"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "state.json"
        self.tasks: dict[str, Task] = {}
        self.state: dict = self._load_state()
        self._stop = asyncio.Event()
        self._tick_task: asyncio.Task | None = None
        self._reload_tasks()

    # ------------------------------------------------------------------ state

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self) -> None:
        try:
            self.state_path.write_text(
                json.dumps(self.state, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    # --------------------------------------------------------------- discovery

    def _reload_tasks(self) -> None:
        """Walk mcp_server.tasks.*.py and instantiate every Task subclass found."""
        self.tasks.clear()
        import pkgutil
        try:
            from . import tasks as tasks_pkg
        except ImportError:
            return
        for info in pkgutil.iter_modules(tasks_pkg.__path__):
            if info.name.startswith("_"):
                continue
            mod_name = f"{tasks_pkg.__name__}.{info.name}"
            try:
                mod = importlib.import_module(mod_name)
            except Exception as exc:
                self._log("SCHED", f"failed to import {info.name}: {exc}")
                continue
            for name, obj in inspect.getmembers(mod):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Task)
                    and obj is not Task
                    and obj.__module__ == mod_name
                ):
                    instance = obj()
                    if not instance.name:
                        instance.name = name.lower()
                    self.tasks[instance.name] = instance

    # ------------------------------------------------------------------ status

    def _cc_idle(self) -> bool:
        status_file = self.cbim_root / ".cc-status"
        if not status_file.exists():
            return True  # unknown → permissive
        try:
            return status_file.read_text(encoding="utf-8").strip().startswith("idle")
        except OSError:
            return True

    def _is_due(self, task: Task) -> bool:
        if task.interval_seconds <= 0:
            return False
        last = self.state.get(task.name, {}).get("last_run_ts", 0)
        return (time.time() - last) >= task.interval_seconds

    # ---------------------------------------------------------------- run loop

    async def _fire(self, task: Task) -> str:
        ctx = {
            "project_root": str(self.project_root),
            "cbim_root": str(self.cbim_root),
            "cc_idle": self._cc_idle(),
        }
        started = datetime.now().isoformat(timespec="seconds")
        try:
            result = await task.run(ctx)
            ok = True
            msg = str(result) if result is not None else "ok"
        except Exception as exc:  # noqa: BLE001
            ok = False
            msg = f"ERROR: {exc}"
        finished = datetime.now().isoformat(timespec="seconds")
        self.state[task.name] = {
            "last_run_ts": time.time(),
            "last_run_at": finished,
            "last_ok": ok,
            "last_result": msg[:200],
        }
        self._save_state()
        self._log("SCHED", f"{task.name} {'ok' if ok else 'fail'} | {msg[:200]}")
        return msg

    async def tick(self) -> None:
        """One tick of the loop — fire every task that is due and allowed."""
        for task in self.tasks.values():
            if not self._is_due(task):
                continue
            if task.respect_cc_idle and not self._cc_idle():
                continue
            await self._fire(task)

    async def loop(self) -> None:
        """Run forever until stop() is called."""
        self._log("SCHED", f"scheduler started; tasks={list(self.tasks)}")
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001
                self._log("SCHED", f"tick error: {exc}")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_SECONDS)
            except asyncio.TimeoutError:
                pass
        self._log("SCHED", "scheduler stopped")

    def start(self) -> None:
        if self._tick_task is None or self._tick_task.done():
            self._stop.clear()
            self._tick_task = asyncio.create_task(self.loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._tick_task:
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------- intro

    def list_tasks(self) -> list[dict]:
        out = []
        for name, task in self.tasks.items():
            s = self.state.get(name, {})
            out.append(
                {
                    "name": name,
                    "description": task.description,
                    "interval_seconds": task.interval_seconds,
                    "respect_cc_idle": task.respect_cc_idle,
                    "last_run_at": s.get("last_run_at"),
                    "last_ok": s.get("last_ok"),
                    "last_result": s.get("last_result"),
                }
            )
        return out

    async def trigger(self, name: str) -> str:
        task = self.tasks.get(name)
        if task is None:
            return f"ERROR: task not found: {name}"
        return await self._fire(task)

    # ---------------------------------------------------------- log helper

    def _log(self, tag: str, msg: str) -> None:
        pass  # scheduler internals are not user-visible; no session log entry
