"""loops/hr_execution.py — HR execution sub-loop descriptor.

Topology source: WORKFLOW-HR.zh-CN.md §1 (扫描 → 逐子任务 → 匹配 →
胜任|偏弱|缺失 → 训练|招募|临时 → 登入清单 → 装配).

Runs inside the HR agent during execution mode. Returns an assignment
dict the parent execution-root loop puts on bb.agent_assignments.
"""
from __future__ import annotations

import json
from typing import Any

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


def compose_prompt(bb) -> str:
    """Render the HR execution NodeSpec list into a prompt.

    Inputs HR needs: the task list (typically arch_plan or its substructure
    on bb) and the existing agent registry. The prompt asks HR to walk
    per-task and produce a final assignment dict.
    """
    arch_plan = getattr(bb, "arch_plan", None)
    user_request = getattr(bb, "user_request", None) or ""

    lines = [
        "## 模式：执行（HR 执行子循环）",
        "",
        "你接到一个 yield 派工。按以下流程图节点顺序推进——前向式，",
        "只看当前任务，逐子任务做匹配/训练/招募/兜底决策，最终装配承接清单。",
        "",
        "### 用户请求",
        user_request.strip() or "(空)",
        "",
    ]
    if arch_plan:
        lines += ["### Architect ContextPack", json.dumps(arch_plan, ensure_ascii=False)[:2000], ""]

    lines += ["### 流程节点（按序，逐子任务循环执行 per_task → all_done）"]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        lines.append(f"{i:>2}. [{marker}] {spec.label}")

    lines += [
        "",
        "### 回执格式",
        '{"agent_assignments": [{"subtask_id": "...", "agent_file": "...", "fit": "fit|weak|miss", "action": "use|train|recruit|temp"}]}',
        "若无法完成，回 JSON `{\"error\": \"原因\"}`。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize HR's response into a dict with agent_assignments key.

    Accepted shapes:
      - dict with "agent_assignments" list → return as-is
      - dict that IS the assignment list (single)   → wrap into list
      - JSON string                        → parse, then re-route
      - list payload                       → wrap into agent_assignments
      - plain text / None                  → error path
    """
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"agent_assignments": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"agent_assignments": None, "error": "non-JSON response", "raw": payload}

    if isinstance(payload, list):
        return {"agent_assignments": payload}

    if isinstance(payload, dict):
        if "error" in payload and "agent_assignments" not in payload:
            return {"agent_assignments": None, "error": str(payload["error"])}
        if "agent_assignments" in payload:
            assigns = payload["agent_assignments"]
            if isinstance(assigns, dict):
                assigns = [assigns]
            return {"agent_assignments": assigns}
        # Dict but no assignments key — treat as single assignment record.
        return {"agent_assignments": [payload]}

    return {"agent_assignments": None, "error": f"unexpected payload type: {type(payload).__name__}"}


__all__ = ["NODE_SPECS", "compose_prompt", "parse_response"]
