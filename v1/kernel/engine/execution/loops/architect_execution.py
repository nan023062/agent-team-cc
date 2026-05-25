"""loops/architect_execution.py — Architect execution sub-loop descriptor.

Topology source: WORKFLOW-ARCHITECT.zh-CN.md §2 (执行子循环).

The execution sub-loop now runs as an in-process Python BT subtree
(`ArchitectExecSubtree`) mounted directly inside the execution root — no
Architect agent yield is involved. This module retains:

  - `NODE_SPECS` — the design-doc-aligned flat node list, pinned by topology
    tests as the single source of truth for sub-loop shape;
  - `_NODE_GUIDE` — per-node guidance text consumed by the live arch_exec
    subtree's prompt-rendering helper (`actions/arch_exec/_helpers.py`);
  - `build_architect_execution_subtree` — re-exported from
    `engine.execution.actions.arch_exec` for convenient access alongside
    the descriptor.
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Per-node guidance — keyed by NodeSpec.id, content sourced from
# design/WORKFLOW-ARCHITECT.zh-CN.md §2 执行子循环.
#
# Consumed by `engine.execution.actions.arch_exec._helpers.render_guide`,
# which builds the per-leaf prompt body inside the in-process subtree.
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
        "- 高风险提示：若涉及改公开契约 / 删模块 / 跨层依赖倒置,",
        "  在对应 task 的 `arch_context` 里以「高风险:」开头点明，便于审计。",
    ],
}


__all__ = ["NODE_SPECS", "build_architect_execution_subtree"]


# Python BT subtree — the source of truth going forward. Tail import so the
# NODE_SPECS / _NODE_GUIDE module-level data above loads even if the
# subtree's internal imports drift, and to break the circular import with
# `arch_exec/_helpers.py` (which lazily imports `_NODE_GUIDE` from here).
from engine.execution.actions.arch_exec import build_architect_execution_subtree  # noqa: E402, F401
