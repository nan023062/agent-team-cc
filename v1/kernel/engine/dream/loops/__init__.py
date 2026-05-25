"""engine.dream.loops — governance-class loop catalog.

Holds the four loops that run under the governance root (dream_tick):

  dream_root           → engine.dream.tree.dream_loop  (re-export)
  architect_governance → NodeSpec descriptor + subtree builder re-export
  hr_governance        → NodeSpec descriptor + subtree builder re-export
  memory_governance    → engine.dream.actions.mem_steps (re-export + builder)

`get_loop(name)` returns the module object — callers pick what they need
from it (a builder, ROOT, NODE_SPECS, etc.). Returning the module rather
than a single artifact keeps the registry agnostic to the loop's category
(Python BT vs in-agent descriptor).

Scope is intentionally governance-only; execution-class loops live in
`engine.execution.loops` and have their own registry.
"""
from __future__ import annotations

from types import ModuleType

from . import (
    architect_governance,
    dream_root,
    hr_governance,
    memory_governance,
)


_REGISTRY: dict[str, ModuleType] = {
    "dream_root":           dream_root,
    "architect_governance": architect_governance,
    "hr_governance":        hr_governance,
    "memory_governance":    memory_governance,
}


def get_loop(name: str) -> ModuleType:
    """Return the governance-class loop module for the given canonical name.

    Raises KeyError with the full list of valid names when `name` is
    unknown — fail-fast, no silent fallback.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown governance loop {name!r}; known: {known}") from None


def loop_names() -> list[str]:
    """Return the governance-class canonical loop names in registration order."""
    return list(_REGISTRY.keys())


__all__ = [
    "get_loop",
    "loop_names",
    "dream_root",
    "architect_governance",
    "hr_governance",
    "memory_governance",
]
