"""engine.loops — eight-loop catalog.

CBIM has eight flowcharts (see design/LOOPS-OVERVIEW.zh-CN.md). This
package gives each one a single canonical module so they sit on one
shelf — no logic added beyond re-exports and a thin registry.

Loop map (loop_name → module)
  execution_root        → engine.execution.tree.main_loop      (re-export)
  dream_root            → engine.dream.tree.dream_loop  (re-export)
  memory_crud           → in-process BT built here (bt.core primitives)
  memory_governance     → engine.dream.actions.mem_steps (re-export + builder)
  architect_execution   → NodeSpec descriptor (compose_prompt + parse_response)
  architect_governance  → NodeSpec descriptor (compose_prompt + parse_response)
  hr_execution          → NodeSpec descriptor (compose_prompt + parse_response)
  hr_governance         → NodeSpec descriptor (compose_prompt + parse_response)

`get_loop(name)` returns the module object — callers pick what they need
from it (a builder, ROOT, NODE_SPECS, compose_prompt, etc.). Returning
the module rather than a single artifact keeps the registry agnostic to
the loop's category (Python BT vs in-agent descriptor).
"""
from __future__ import annotations

from importlib import import_module
from types import ModuleType

from . import (
    architect_execution,
    architect_governance,
    dream_root,
    execution_root,
    hr_execution,
    hr_governance,
    memory_crud,
    memory_governance,
)
from ._spec import NodeSpec


_REGISTRY: dict[str, ModuleType] = {
    "execution_root":       execution_root,
    "dream_root":           dream_root,
    "memory_crud":          memory_crud,
    "memory_governance":    memory_governance,
    "architect_execution":  architect_execution,
    "architect_governance": architect_governance,
    "hr_execution":         hr_execution,
    "hr_governance":        hr_governance,
}


def get_loop(name: str) -> ModuleType:
    """Return the loop module for the given canonical loop name.

    Raises KeyError with the full list of valid names when `name` is
    unknown — fail-fast, no silent fallback.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown loop {name!r}; known loops: {known}") from None


def loop_names() -> list[str]:
    """Return the canonical loop names in registration order."""
    return list(_REGISTRY.keys())


__all__ = [
    "NodeSpec",
    "get_loop",
    "loop_names",
    "execution_root",
    "dream_root",
    "memory_crud",
    "memory_governance",
    "architect_execution",
    "architect_governance",
    "hr_execution",
    "hr_governance",
]
