"""engine.dream.core — dream-loop-specific core (Blackboard + SequenceTolerant).

The rest of the bt/core primitives (Node ABC, Composite base, Decorator, Runner,
persistence) are reused from engine.bt.core directly. Only the two things that
are governance-specific live here:
  - DreamBlackboard: 19-field schema, distinct from execution bt's 18 fields
  - SequenceTolerant: composite that does NOT short-circuit on FAILURE
"""

from .blackboard import DreamBlackboard
from .composite_tolerant import SequenceTolerant

__all__ = ["DreamBlackboard", "SequenceTolerant"]
