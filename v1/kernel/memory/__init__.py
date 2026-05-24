"""kernel/memory — 项目本地的独立存储+查询服务。

对外契约（见 .dna/contract.md）：4 个只读接口 query/scan/get/stats
写入入口（不在对外契约）：Hook / memory_write MCP / CLI 三条，都进 crud/

Phase 4C: the parent facade exposes the 4 read-only contract surfaces.
Writes go through crud/ directly (the three legitimate entry points construct
a backend and call `crud.primitives.write` / `crud.session_writer.write_session`).
The legacy `MemoryEngine` adapter, the `memory.engine.*` alias shims, and the
co-located `memory/engine/` directory have all been removed.
"""

from ._facade import query, scan, get, stats

__all__ = ["query", "scan", "get", "stats"]
