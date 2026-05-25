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

    Walks the 13-node flow as three phases (前置 / per-task 循环 / 后置)
    so HR sees the loop structure explicitly. The reply schema written at
    the tail is line-format and aligned with
    `dispatch_hr._extract_assignments` — one line per task plus optional
    `agent_gap:` lines.
    """
    arch_plan = getattr(bb, "arch_plan", None)
    user_request = getattr(bb, "user_request", None) or ""

    lines = [
        "## 模式：执行（HR 执行子循环）",
        "",
        "你接到一个派工。按下面三段式流程推进——前置一次性盘点 → 对每个",
        "子任务跑一遍 per_task → match → decide → all_done 的循环 → 后置",
        "汇总一次性回执。前向式：只看当前任务清单，不回头评估已有 agent",
        "的健康度（那是治理子循环的事）。",
        "",
        "### 用户请求",
        user_request.strip() or "(空)",
        "",
    ]
    if arch_plan:
        lines += [
            "### Architect ContextPack（待分配的子任务清单在此）",
            json.dumps(arch_plan, ensure_ascii=False)[:2000],
            "",
        ]

    lines += [
        "### 流程节点（13 项，分三段执行）",
        "",
        "**前置（整轮只跑一次）**",
        " 1. [·] scan / 盘点现有能力册 — 读取 `.claude/agents/` 目录，",
        "    建立当前工作 agent 清单（id / capability / description）。",
        "    若 arch_plan 为空，直接跳到节点 13 回空分配。",
        "",
        "**per-task 循环（对清单里每个子任务依次重复 2 → 11）**",
        " 2. [·] per_task / 逐子任务匹配 — 取下一个未分配的子任务；",
        "    读 task.required_capability 与 task.description。",
        " 3. [?] match / 匹配结果 — 遍历 agent 清单，对每个 agent 与",
        "    task.required_capability 打分：perfect fit / acceptable /",
        "    weak / miss；保留最高分 agent。",
        " 4. [·] fit / 有且胜任 — perfect 或 acceptable：进入节点 7。",
        " 5. [·] weak / 有但能力不足 — 仅 weak 命中：进入节点 7 附注。",
        " 6. [·] miss / 无匹配 — 完全无命中：进入节点 7 登记 gap。",
        " 7. [?] decide / 训练/招募/临时兜底 — 由上节点决定动作：胜任",
        "    → 直接 use；偏弱 → use + 建议后续训练；缺失 → 登记",
        "    agent_gap + 建议后续招募。**不在本轮真去训练或招募。**",
        " 8. [·] train / 针对性训练已有 agent — 仅标记建议，不执行。",
        " 9. [·] recruit / 懒式招募新 agent — 仅标记建议，不创建。",
        "10. [·] temp / 通用 agent 临时承接/登记为能力缺口 —",
        "    通用 agent 临时承接，同时登记为能力缺口。",
        "11. [·] add_one / 登入承接清单 — 把本任务的分配结果（或 gap）",
        "    登入承接清单；",
        "    [?] all_done / 清单覆盖全部子任务? — 还有未处理 → 回节点 2；",
        "    全部完成 → 进入节点 12。",
        "",
        "**后置（整轮只跑一次）**",
        "12. [·] build / 装配承接清单 — 汇总承接清单与 gap 列表。",
        "13. [■] respond — 按下方「回执格式」写出。",
        "",
        "### 核心 agent 直通规则（重要）",
        "对 capability 为以下之一的子任务，直接返回对应核心 agent 文件",
        "路径，**不要**报 agent_gap：",
        "  - architect  → .claude/agents/architect/architect.md",
        "  - hr         → .claude/agents/hr/hr.md",
        "  - auditor    → .claude/agents/auditor/auditor.md",
        "  - programmer → .claude/agents/programmer/programmer.md",
        "只有当某能力既不在工作 agent 清单、也不属于上述核心 agent 时，",
        "才允许报 agent_gap。",
        "",
        "### 回执格式（严格，逐行）",
        "为每个分配成功的子任务写一行：",
        "    task_id=<id> agent_file=<path> capability=<tag>",
        "为每个无法承接的能力写一行（紧跟在相关任务行后或集中在末尾）：",
        "    agent_gap: <capability> — <reason>",
        "",
        "示例：",
        "    task_id=t1 agent_file=.claude/agents/programmer/programmer.md capability=programmer",
        "    task_id=t2 agent_file=.claude/agents/architect/architect.md capability=architect",
        "    task_id=t3 agent_file=.claude/agents/specialists/shader.md capability=shader",
        "    agent_gap: motion_capture — 当前清单与核心 agent 均无该能力",
        "",
        "硬约束：",
        "  - 每个 task_id 必须有 agent_file，否则视为缺失并报 agent_gap。",
        "  - capability 字段必填，便于上游统计与后续治理。",
        "  - 不要输出 JSON、Markdown 表格或额外说明，只输出上述两类行。",
        "  - 若整体无法完成，单独输出一行 `agent_gap: <reason>` 即可。",
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
