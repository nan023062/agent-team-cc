"""actions/flush_memory.py — drain bb.memory_flush_queue into memory.crud.

4B baseline: hook subprocess (cbim_stop.py) is the canonical memory writer.
This Action exists so that future synchronous memory writes initiated from
inside a tick have a wired entry point. Default behavior: no-op when the
queue is empty.

Always wrapped in Catch(fallback="swallow") at the tree level so write
failures never break the tick. NEVER raises.
"""

from __future__ import annotations

from engine.core.node import Node, Status


class FlushMemory(Node):
    def __init__(self, *, name: str = "FlushMemory") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        queue = bb.memory_flush_queue or []
        if not queue:
            return Status.SUCCESS
        # 4B: deferred — see actions/flush_memory.py docstring.
        # When wired:
        #   from memory.crud.primitives import write
        #   from memory.crud.backend import FileBackend
        #   backend = FileBackend(store_dir=...)
        #   for entry in queue:
        #       write(Path(entry["path"]), entry["tier"], backend)
        bb.memory_flush_queue = []
        return Status.SUCCESS
