"""loops/execution_root.py — Execution root loop, re-export only.

The execution root lives at engine.execution.tree.main_loop. This module is its
canonical entry under engine.loops.* so the eight loops have one shelf;
it adds no logic — see the bt/ subpackage for the real topology.
"""
from __future__ import annotations

from engine.execution.tree.main_loop import ROOT, build_root

__all__ = ["ROOT", "build_root"]
