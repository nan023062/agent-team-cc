"""core/node.py — Node ABC + Status three-state enum.

Design constraints (locked in .dna/contract.md + design BEHAVIOR-TREE-ENGINE §2):
  - Node.tick(bb) -> Status is the ONLY entry; no business return values, only bb writes.
  - Status is closed at {SUCCESS, FAILURE, RUNNING} — no fourth state.
  - Nodes MUST NOT hold cross-tick state on `self`. tick-local variables are fine.
  - on_resume is optional; only Actions that yield need to implement it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class Status(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class Node(ABC):
    """Behavior-tree node abstract base.

    Concrete subclasses MUST:
      - set `self.name` to a string unique within the tree (used in trace +
        runner_resume_path)
      - implement `tick(bb) -> Status`
      - implement `on_resume(bb, payload)` only if the node ever returns RUNNING

    Concrete subclasses MUST NOT add any field on `self` that survives between
    tick() invocations of different ticks (the "no cross-tick state" rule from
    BEHAVIOR-TREE-ENGINE §2). tick-local locals are unrestricted.
    """

    name: str = ""

    @abstractmethod
    def tick(self, bb) -> Status:  # noqa: D401
        ...

    def on_resume(self, bb, payload: Any) -> None:  # default: no-op
        return None

    # ------------------------------------------------------------------
    # Tree-walk helpers used by Runner.
    #
    # A node either has children (composite/decorator) or is a leaf.
    # Decorators have exactly one child; composites have many.
    # Default: no children (leaf).
    # ------------------------------------------------------------------

    def children(self) -> list["Node"]:
        return []

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
