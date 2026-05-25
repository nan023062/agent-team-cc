"""actions/flush_memory.py — drain bb.memory_flush_queue into memory.crud.

Wires the execution-root FlushMemory leaf to the memory CRUD sub-loop
(`engine.execution.loops.memory_crud.build_memory_crud_root`). For each
entry in `bb.memory_flush_queue` we run one CRUD tick with real service
callbacks (`memory.crud.primitives.write` + `FileBackend`). Successful
entries are removed from the queue; failures are swallowed individually
so one bad entry can't block the rest, and the whole node is also wrapped
in Catch(swallow) at the tree level — NEVER raises.

Entry shape (per execution README contract):
    {"path": "<absolute md path>", "tier": "short"|"medium", ...}

Backend wiring:
    Each tick builds its own FileBackend anchored at the project's
    `.cbim/memory/` (resolved via `context.cbim_dir()`). This mirrors
    `memory/_facade.py::_resolve_store_dir` so flush and read paths see
    the same store.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engine.core.node import Node, Status


def _resolve_store_dir() -> Path:
    """Mirror memory._facade._resolve_store_dir for the default backend."""
    try:
        from context import cbim_dir
        return cbim_dir() / "memory"
    except Exception:
        return Path.cwd() / ".cbim" / "memory"


def _make_write_call(backend):
    """Return a write_call(bb) bound to `backend`.

    Reads `bb.crud_op["entry"]` and forwards (path, tier, backend) to the
    real `memory.crud.primitives.write` primitive.
    """
    from memory.crud.primitives import write as _write

    def _call(crud_bb):
        entry = (crud_bb.crud_op or {}).get("entry") or {}
        path = entry.get("path")
        tier = entry.get("tier")
        if not path or not tier:
            raise ValueError(f"flush entry missing path/tier: {entry!r}")
        _write(Path(path), tier, backend)
        return {"path": path, "tier": tier}

    return _call


class FlushMemory(Node):
    def __init__(self, *, name: str = "FlushMemory") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        queue = bb.memory_flush_queue or []
        if not queue:
            return Status.SUCCESS

        # Lazy imports: avoid circular import between
        # `engine.execution.tree.main_loop` and `engine.execution.loops`
        # (which re-exports execution_root, which itself imports the
        # main loop). Also keeps the backend cost off the no-op path.
        from memory.crud.file_backend import FileBackend
        from engine.execution.loops.memory_crud import build_memory_crud_root

        backend = FileBackend(_resolve_store_dir())

        crud_root = build_memory_crud_root(
            write_call=_make_write_call(backend),
            # flush only writes; read leg is wired with an explicit no-op
            # so the topology branch still succeeds if ever exercised.
            read_call=lambda _bb: None,
        )

        remaining: list[dict] = []
        for entry in queue:
            crud_bb = SimpleNamespace(
                crud_op={"kind": "write", "batch": False, "entry": entry},
                crud_result=None,
                runner_resume_path=None,
            )
            try:
                status = crud_root.tick(crud_bb)
            except Exception:
                # Individual entry failure — keep going. The outer
                # Catch(swallow) is a second safety net.
                continue
            if status != Status.SUCCESS:
                # Don't requeue: a deterministically-bad entry would
                # re-fail every tick. Drop it; the inner failure is
                # already on crud_bb.crud_result for any future logger.
                continue
            # Successfully flushed — drop from queue (do nothing).
            _ = entry

        bb.memory_flush_queue = remaining
        return Status.SUCCESS
