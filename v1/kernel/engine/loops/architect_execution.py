"""loops/architect_execution.py — Architect execution sub-loop descriptor.

The architect execution sub-loop runs inside the architect agent's mind,
not the Python BT engine. We describe its topology as a flat NodeSpec
list so:

  - design-doc Mermaid labels are checked in (WORKFLOW-ARCHITECT §2);
  - compose_prompt() renders the list into the prompt embedded in the
    yielded DispatchRequest for agent_type="architect";
  - parse_response() decodes whatever the agent returns into a normalized
    dict the parent loop can put on bb (typically bb.arch_plan).

The Mermaid topology is a branching DAG (StateCheck splits into 4 states,
Worth splits "build vs skip"), but for prompt scaffolding we keep the
list flat — order matches the design doc's narrative flow.
"""
from __future__ import annotations

import json
from typing import Any

from ._spec import NodeSpec


NODE_SPECS: list[NodeSpec] = [
    NodeSpec("scan",        "读取相关模块知识/扫工作区代码", "action"),
    NodeSpec("state_check", "知识与代码同步状态判断",         "decision"),
    NodeSpec("worth",       "值得为这块代码建立模块知识?",     "decision"),
    NodeSpec("create",      "懒式建立新模块知识",             "action"),
    NodeSpec("extract",     "直接提取模块路径与约束",         "action"),
    NodeSpec("diff",        "定位变更点/补齐知识",            "action"),
    NodeSpec("validate",    "验证设计可行性/标记待实现规约",   "action"),
    NodeSpec("map",         "子任务到模块映射",               "action"),
    NodeSpec("assemble",    "装配 ContextPack",              "action"),
]


def compose_prompt(bb) -> str:
    """Render the NodeSpec list into a step-by-step prompt for the architect.

    The blackboard is the execution-root Blackboard; we pull `user_request`
    and any prior arch_plan slot to give the architect context. Pure
    string construction — no I/O.
    """
    user_request = getattr(bb, "user_request", None) or ""
    prior_plan = getattr(bb, "arch_plan", None)

    lines = [
        "## 模式：执行（Architect 执行子循环）",
        "",
        "你接到一个 yield 派工。按以下流程图节点顺序推进，每节点产出一行进展，",
        "最终以 JSON dict（顶层键 `arch_plan`）回执整个 ContextPack。",
        "",
        "### 用户请求",
        user_request.strip() or "(空)",
        "",
    ]
    if prior_plan:
        lines += ["### 已有 arch_plan（如有）", json.dumps(prior_plan, ensure_ascii=False)[:2000], ""]

    lines += ["### 流程节点（按序）"]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        lines.append(f"{i:>2}. [{marker}] {spec.label}")

    lines += [
        "",
        "### 回执格式",
        '{"arch_plan": {"context_pack": "...", "modules": [...], "notes": "..."}}',
        "若无法完成，回 JSON `{\"error\": \"原因\"}`。",
    ]
    return "\n".join(lines)


def parse_response(payload: str | dict | None) -> dict:
    """Normalize architect's response into a dict the parent loop can store.

    Accepted shapes (in priority order):
      - dict with "arch_plan" key  → return that subdict
      - dict (any other shape)     → wrap as {"arch_plan": payload}
      - JSON string                → parse, then re-route
      - plain text                 → return {"arch_plan": {"raw": text}}
      - None / empty               → return {"arch_plan": None, "error": "empty response"}
    """
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return {"arch_plan": None, "error": "empty response"}

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"arch_plan": {"raw": payload}}

    if isinstance(payload, dict):
        if "error" in payload and "arch_plan" not in payload:
            return {"arch_plan": None, "error": str(payload["error"])}
        if "arch_plan" in payload:
            return {"arch_plan": payload["arch_plan"]}
        return {"arch_plan": payload}

    if isinstance(payload, list):
        return {"arch_plan": {"items": payload}}

    return {"arch_plan": {"raw": repr(payload)}}


__all__ = ["NODE_SPECS", "compose_prompt", "parse_response"]
