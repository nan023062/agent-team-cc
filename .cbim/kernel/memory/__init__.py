"""kernel/memory — 项目本地的独立存储+查询服务。

对外契约（见 .dna/contract.md）：4 个只读接口 query/scan/get/stats
写入入口（不在对外契约）：memory_write MCP / CLI 两条，都进 crud/

The parent facade exposes the 4 read-only contract surfaces. Writes go
through crud/ directly (the two legitimate entry points construct a backend
and call `crud.primitives.write`). The legacy `MemoryEngine` adapter, the
`memory.engine.*` alias shims, and the co-located `memory/engine/` directory
have all been removed. v2 dropped the short tier entirely — short-term
memory is now Claude Code's per-session transcript JSONL, owned by Claude
Code and surfaced via `engine.retrieval` (source="transcript"), not by
this module.
"""

from ._facade import query, scan, get, stats

__all__ = ["query", "scan", "get", "stats"]
