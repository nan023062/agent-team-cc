"""loops/hr_execution.py — HR execution sub-loop descriptor.

Topology source: WORKFLOW-HR.zh-CN.md §1 (扫描 → 逐子任务 → 匹配 →
胜任|偏弱|缺失 → 训练|招募|临时 → 登入清单 → 装配).

The execution sub-loop now runs as an in-process Python BT subtree
(`HRExecSubtree`) mounted directly inside the execution root — no HR
agent yield is involved. This module retains:

  - `NODE_SPECS` — the design-doc-aligned flat node list, pinned by topology
    tests as the single source of truth for sub-loop shape;
  - `build_hr_execution_subtree` — re-exported from
    `engine.execution.actions.hr_exec` for convenient access alongside
    the descriptor.
"""
from __future__ import annotations

from engine.core.loop_spec import NodeSpec


NODE_SPECS: list[NodeSpec] = [
    NodeSpec("scan",      "盘点现有能力册",        "action"),
    NodeSpec("per_task",  "逐子任务匹配",          "action"),
    NodeSpec("match",     "匹配结果",              "decision"),
    NodeSpec("fit",       "有且胜任",              "action"),
    NodeSpec("weak",      "有但能力不足",          "action"),
    NodeSpec("miss",      "无匹配",                "action"),
    NodeSpec("decide",    "训练/招募/临时兜底",    "decision"),
    NodeSpec("train",     "针对性训练已有 agent",   "action"),
    NodeSpec("recruit",   "懒式招募新 agent",       "action"),
    NodeSpec("temp",      "通用 agent 临时承接/登记为能力缺口", "action"),
    NodeSpec("add_one",   "登入承接清单",          "action"),
    NodeSpec("all_done",  "清单覆盖全部子任务?",   "decision"),
    NodeSpec("build",     "装配承接清单",          "action"),
]


__all__ = ["NODE_SPECS", "build_hr_execution_subtree"]


# Python BT subtree — the source of truth going forward. Tail import so the
# NODE_SPECS descriptor above loads even if the subtree's internal imports
# drift, and to break any latent circular import with action modules.
from engine.execution.actions.hr_exec import build_hr_execution_subtree  # noqa: E402, F401
