"""memory.crud — write/update/delete primitives + storage backends.

v2: short/ tier removed. This is the only path that mutates medium/ on disk
and the local backend index. External callers (memory_write MCP / CLI) reach
here through the parent memory facade; compaction reaches here via the
`update`/`delete` re-export to bounce its products back into the store.
Each primitive also synchronously updates the external engine.retrieval
index — see crud/.dna/module.md Key Decision #3.
"""

from .backend import MemoryBackend
from .file_backend import FileBackend
from .primitives import (
    IndexMaintainer,
    MEDIUM,
    RETRIEVAL_SOURCE,
    TIERS,
    delete,
    update,
    write,
)
__all__ = [
    "MemoryBackend",
    "FileBackend",
    "IndexMaintainer",
    "MEDIUM",
    "RETRIEVAL_SOURCE",
    "TIERS",
    "delete",
    "update",
    "write",
]
