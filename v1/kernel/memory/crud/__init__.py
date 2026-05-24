"""memory.crud — write/update/delete primitives + storage backends.

Phase 4A: this is the only path that mutates short/ and medium/ on-disk.
External callers (Hook / memory_write MCP / CLI) reach here through the
parent memory facade; compaction reaches here via the `update`/`delete`
re-export to bounce its products back into the store.
"""

from .backend import MemoryBackend
from .file_backend import FileBackend
from .primitives import (
    IndexMaintainer,
    SHORT,
    MEDIUM,
    TIERS,
    delete,
    update,
    write,
)
from .session_writer import write_session

__all__ = [
    "MemoryBackend",
    "FileBackend",
    "IndexMaintainer",
    "SHORT",
    "MEDIUM",
    "TIERS",
    "delete",
    "update",
    "write",
    "write_session",
]
