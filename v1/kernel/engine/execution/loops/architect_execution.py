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

from engine.core.loop_spec import NodeSpec


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

    Single source of truth for node semantics: `design/WORKFLOW-ARCHITECT.zh-CN.md`
    §2 (执行子循环). Each of the nine NodeSpec entries gets an explicit
    input / decision-basis / output / fallback paragraph so the agent does
    not need to re-derive the flowchart from labels alone.

    The receipt schema at the tail is the contract consumed by
    `dispatch_architect.py::_extract_plan`. Do not drift from the field
    names `id / description / required_capability / params / arch_context`
    — those map 1:1 onto `Task.from_dict`.

    Pure string construction. No I/O.
    """
    user_request = getattr(bb, "user_request", None) or ""
    prior_plan = getattr(bb, "arch_plan", None)
    knowledge_snapshot = getattr(bb, "knowledge_snapshot", None) or getattr(bb, "dna_snapshot", None)

    lines: list[str] = [
        "## 模式：执行（Architect 执行子循环）",
        "",
        "你接到执行根派来的一个 yield。本子循环只产出一份 ContextPack",
        "（一组带模块上下文的子任务），不要在此阶段调用任何外部 agent。",
        "把流程跑完，按文末「回执 schema」回一份 JSON——只回 JSON，不要散文。",
        "",
        "### 用户请求",
        user_request.strip() or "(空)",
        "",
        "### 知识快照（bb.knowledge_snapshot）",
        _format_snapshot(knowledge_snapshot),
        "",
    ]
    if prior_plan:
        lines += [
            "### 已有 arch_plan（上一轮回执，若需修订请基于它增量更新）",
            json.dumps(prior_plan, ensure_ascii=False)[:2000],
            "",
        ]

    lines += ["### 流程节点（按序走，每节点心里走一遍即可，不必逐行汇报）", ""]
    for i, spec in enumerate(NODE_SPECS, start=1):
        marker = {"action": "·", "decision": "?", "terminal": "■"}[spec.role]
        lines.append(f"#### {i}. [{marker}] {spec.label}")
        guide = _NODE_GUIDE.get(spec.id)
        if guide:
            lines += guide
        lines.append("")

    lines += [
        "### 回执 schema（写死，违反则下游解析失败）",
        "",
        "正常完成 → 返回任务清单：",
        "```json",
        "{",
        '  "arch_plan": [',
        "    {",
        '      "id": "t1",',
        '      "description": "一句话说明这个子任务要做什么（祈使句）",',
        '      "required_capability": "programmer | tester | doc_writer | generalist",',
        '      "params": {"file_path": "...", "其它参数": "..."},',
        '      "arch_context": "相关模块 DNA 摘要 + 不能改的约束 + 依赖方向"',
        "    }",
        "  ]",
        "}",
        "```",
        "",
        "需要先澄清才能继续 → 返回单问句：",
        "```json",
        '{"need_clarify": true, "question": "唯一一个问句，不要罗列多个问题"}',
        "```",
        "",
        "硬性失败（知识/代码冲突无法消解、超出 Architect 职责） → 返回错误：",
        "```json",
        '{"error": "一行原因"}',
        "```",
        "",
        "### 字段约束",
        "- `arch_plan` 必须是 list，元素是 dict；空 list 视为「没必要派工」由父循环兜底。",
        "- `id` 在本回执内唯一，建议 `t1 / t2 / ...`。",
        "- `description` 是给 Work Agent 看的祈使句，不要写「需要…」「应当…」。",
        "- `required_capability` 用小写英文短串；未知能力写 `generalist`，HR 会再裁。",
        "- `arch_context` 是字符串，把模块路径 + 约束 + 依赖方向写进来；不要塞结构化对象。",
        "- 顶层不要混入额外键；`arch_plan` 与 `need_clarify` / `error` 三选一。",
    ]
    return "\n".join(lines)


def _format_snapshot(snapshot) -> str:
    """Render the knowledge snapshot into a short, prompt-friendly block.

    Accepts whatever the execution root puts on bb (dict, list, str, None).
    Truncated hard at ~2k chars so prior plan + snapshot together don't
    blow the prompt budget.
    """
    if snapshot is None:
        return "(无快照——按需走 scan 节点自行读取 .dna/)"
    if isinstance(snapshot, str):
        return snapshot.strip()[:2000] or "(空字符串)"
    try:
        return json.dumps(snapshot, ensure_ascii=False, indent=2)[:2000]
    except (TypeError, ValueError):
        return repr(snapshot)[:2000]


# ---------------------------------------------------------------------------
# Per-node guidance — keyed by NodeSpec.id, content sourced from
# design/WORKFLOW-ARCHITECT.zh-CN.md §2 执行子循环.
# ---------------------------------------------------------------------------

_NODE_GUIDE: dict[str, list[str]] = {
    "scan": [
        "- 输入：`bb.user_request` + `bb.knowledge_snapshot`（上文已给）。",
        "- 做什么：只读取与本请求相关的模块 DNA 与工作区代码现状，不要全量巡检。",
        "- 输出：心里得出「当前理解的用户意图」一句话——后续所有节点都围绕它推进。",
        "- 失败回退：知识快照为空 → 走 worth 节点判定是否懒式新建；不要在 scan 阶段创建知识。",
    ],
    "state_check": [
        "- 判定依据：把每个受影响的模块归入四态之一——",
        "  · 状态 0 = 知识缺失（.dna/ 里没这块）→ 走 worth",
        "  · 状态 1 = 知识与代码同步 → 走 extract",
        "  · 状态 2 = 代码超前于知识（代码已动、文档未更）→ 走 diff",
        "  · 状态 3 = 知识超前于代码（设计已写、未实现）→ 走 validate",
        "- 不确定阈值：如果 1 个以上核心参数（受影响模块、变更类型）无法判定，",
        "  视为意图模糊 → 走「需要澄清」分支（回执 `need_clarify`）。",
    ],
    "worth": [
        "- 判定依据：复杂度高 / 多处引用 / 有明确设计意图 → 值得；",
        "  一次性脚本 / 临时调试代码 → 不值得。",
        "- 值得 → 走 create；不值得 → 跳过新建，直接进入 map（不写 .dna/）。",
        "- 注意：此节点只决策，不真正写 .dna/——写动作由 Architect 在 ContextPack 外的 MCP 调用承担。",
    ],
    "create": [
        "- 输入：状态 0 且 worth=值得的模块清单。",
        "- 输出：在 `arch_context` 里写明「新建模块边界 / 接口契约 / 依赖规则」，",
        "  让 Work Agent 知道这是新地盘、可以从零写。",
        "- 失败回退：边界划不清 → 改回 `need_clarify`，问用户「这块归在哪个父模块下」。",
    ],
    "extract": [
        "- 输入：状态 1 模块的 DNA 文件路径。",
        "- 输出：把模块路径 + 必须遵守的约束（公开契约、禁止改的字段）写入 `arch_context`。",
        "- 不做什么：不复述完整 DNA，只挑与子任务直接相关的约束。",
    ],
    "diff": [
        "- 输入：状态 2 模块——代码已动、文档未更。",
        "- 输出：在 `arch_context` 里标出「变更点位置 + 待补齐的知识条目」，",
        "  让 Work Agent 在实现时顺手补 DNA（或单独产一个 doc 子任务）。",
        "- 失败回退：代码已偏离设计意图过远 → 标记为 `error`，请用户裁决是回滚还是接纳现状。",
    ],
    "validate": [
        "- 输入：状态 3 模块——设计已写、未实现。",
        "- 输出：核对设计可行性；可行 → 在 `arch_context` 标「待实现规约」并继续；",
        "  不可行 → 回 `error`，说明设计的哪一条约束物理上做不到。",
    ],
    "map": [
        "- 输入：以上节点产出的「受影响模块 + 变更类型」清单。",
        "- 输出：把子任务拆出来，每条对应一个 `arch_plan` 元素，",
        "  字段 `{id, description, required_capability, params, arch_context}`。",
        "- 拆分上限：task 总数 ≤ 8；超过 8 视为拆分粒度过细，回到本节点重新合并。",
        "- 依赖：若子任务之间有依赖，把上游 id 写进 `params.depends_on`（list[str]）。",
    ],
    "assemble": [
        "- 自检：依赖关系不能成环；每条 task 的 `arch_context` 必须非空；",
        "  required_capability 在 {programmer, tester, doc_writer, generalist} 之内（其它值会被 HR 兜底）。",
        "- 输出：把整张 `arch_plan` 按文末 schema 序列化为 JSON。",
        "- 高风险提示：若涉及改公开契约 / 删模块 / 跨层依赖倒置，",
        "  在对应 task 的 `arch_context` 里以「高风险:」开头点明，便于审计。",
    ],
}


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


# Python BT subtree (v4) — kept as a tail import so the compatibility shim above
# (NODE_SPECS / compose_prompt / parse_response) loads even if the subtree's
# imports drift. The Python tree is built via:
#     from engine.execution.actions.arch_exec import build_architect_execution_subtree
# and is the source of truth going forward; this prompt-scaffold file is kept
# for the existing dispatch_architect path until t6 main_loop migration lands.
from engine.execution.actions.arch_exec import build_architect_execution_subtree  # noqa: E402, F401
