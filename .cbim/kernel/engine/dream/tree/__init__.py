"""dream.tree — static topology for the governance root.

Wires actions into the DreamRoot per WORKFLOW-DREAM §三. Stacking order
locked: Trace > Timeout > Catch (mirrors bt/core/decorator §3).
"""

from .dream_loop import build_dream_root

__all__ = ["build_dream_root"]
