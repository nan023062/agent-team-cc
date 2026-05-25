"""loops/dream_root.py — Governance (dream) root loop, re-export only.

The governance root lives at engine.dream.tree.dream_loop. This module is
its canonical entry under engine.loops.*; it adds no logic.
"""
from __future__ import annotations

from engine.dream.tree.dream_loop import build_dream_root

__all__ = ["build_dream_root"]
