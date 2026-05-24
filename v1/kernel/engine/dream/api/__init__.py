"""dream.api — public surface mirrored by mcp_server/tools/dream.py.

4 entry points per .dna/contract.md:
  dream_tick(reason, run_id=None)             → DreamResult
  dream_tick_resume(run_id, dispatch_result)  → DreamResult
  dream_list_runs(limit=10)                   → list[DreamRunSummary]
  dream_abort(run_id, reason)                 → AbortResult
"""

from .result import (
    AbortResult,
    DispatchRequest,
    DreamResult,
    DreamRunSummary,
    DREAM_AGENT_TYPE_TO_LEAF,
)

# Note: dream_tick / dream_tick_resume / dream_list_runs / dream_abort are NOT
# re-exported at package level — that import chain (api → tree → actions → api)
# is circular. Callers MUST import from `engine.dream.api.dream_tick` directly.

__all__ = [
    "AbortResult",
    "DispatchRequest",
    "DreamResult",
    "DreamRunSummary",
    "DREAM_AGENT_TYPE_TO_LEAF",
]
