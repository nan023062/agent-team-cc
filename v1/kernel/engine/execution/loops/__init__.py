"""engine.execution.loops — execution-class loop catalog.

Holds the three loops that run under the execution root (bt_tick):

  execution_root      → engine.execution.tree.main_loop      (re-export)
  architect_execution → NodeSpec descriptor + subtree builder re-export
  memory_crud         → in-process BT built here (core primitives)

`get_loop(name)` returns the module object — callers pick what they need
from it (a builder, ROOT, NODE_SPECS, etc.). Returning the module rather
than a single artifact keeps the registry agnostic to the loop's category
(Python BT vs in-agent descriptor).

Scope is intentionally execution-only; governance-class loops live in
`engine.dream.loops` and have their own registry.
"""
from __future__ import annotations

from types import ModuleType

from . import (
    architect_execution,
    execution_root,
    memory_crud,
)


_REGISTRY: dict[str, ModuleType] = {
    "execution_root":      execution_root,
    "architect_execution": architect_execution,
    "memory_crud":         memory_crud,
}


def get_loop(name: str) -> ModuleType:
    """Return the execution-class loop module for the given canonical name.

    Raises KeyError with the full list of valid names when `name` is
    unknown — fail-fast, no silent fallback.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown execution loop {name!r}; known: {known}") from None


def loop_names() -> list[str]:
    """Return the execution-class canonical loop names in registration order."""
    return list(_REGISTRY.keys())


__all__ = [
    "get_loop",
    "loop_names",
    "execution_root",
    "architect_execution",
    "memory_crud",
]
