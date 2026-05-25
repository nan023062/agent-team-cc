"""Topology assertions for the loop catalog.

Loops now live under two scoped registries:
  - engine.execution.loops (execution_root, architect_execution, memory_crud)
  - engine.dream.loops    (dream_root, architect_governance, hr_governance, memory_governance)

Pure structural checks: no LLM calls, no Runner ticks, no MCP roundtrips.
Each test reads either a BT subtree's node names or a descriptor module's
NODE_SPECS labels and asserts the design-doc Mermaid labels are present.

When a design doc changes a label, this file is the single place to update.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.node import Node
from engine.core.loop_spec import NodeSpec
from engine.execution.loops import (
    architect_execution,
    execution_root,
    memory_crud,
)
from engine.execution.loops import get_loop as get_exec_loop
from engine.execution.loops import loop_names as exec_loop_names
from engine.dream.loops import (
    architect_governance,
    dream_root,
    hr_governance,
    memory_governance,
)
from engine.dream.loops import get_loop as get_gov_loop
from engine.dream.loops import loop_names as gov_loop_names


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXPECTED_EXEC_LOOP_NAMES = {
    "execution_root",
    "architect_execution",
    "memory_crud",
}

EXPECTED_GOV_LOOP_NAMES = {
    "dream_root",
    "architect_governance",
    "hr_governance",
    "memory_governance",
}


def test_execution_registry_lists_all_loops():
    assert set(exec_loop_names()) == EXPECTED_EXEC_LOOP_NAMES


def test_governance_registry_lists_all_four_loops():
    assert set(gov_loop_names()) == EXPECTED_GOV_LOOP_NAMES


def test_get_loop_returns_modules_for_every_name():
    for name in EXPECTED_EXEC_LOOP_NAMES:
        mod = get_exec_loop(name)
        assert mod is not None
        assert hasattr(mod, "__name__")
    for name in EXPECTED_GOV_LOOP_NAMES:
        mod = get_gov_loop(name)
        assert mod is not None
        assert hasattr(mod, "__name__")


def test_get_loop_unknown_raises():
    with pytest.raises(KeyError):
        get_exec_loop("not_a_loop")
    with pytest.raises(KeyError):
        get_gov_loop("not_a_loop")


def test_scoped_registries_are_disjoint():
    """Execution and governance registries must not share keys."""
    assert EXPECTED_EXEC_LOOP_NAMES.isdisjoint(EXPECTED_GOV_LOOP_NAMES)
    assert set(exec_loop_names()).isdisjoint(set(gov_loop_names()))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _walk_names(node: Node) -> list[str]:
    """Collect every node name reachable from `node`, depth-first."""
    out: list[str] = []

    def rec(n: Node) -> None:
        out.append(n.name)
        for ch in n.children():
            rec(ch)

    rec(node)
    return out


def _labels(specs: list[NodeSpec]) -> set[str]:
    return {s.label for s in specs}


def _ids(specs: list[NodeSpec]) -> set[str]:
    return {s.id for s in specs}


# ---------------------------------------------------------------------------
# Root loops — re-exports of bt and dream
# ---------------------------------------------------------------------------

def test_execution_root_reexports_bt_root():
    from engine.execution.tree.main_loop import ROOT as BT_ROOT
    assert execution_root.ROOT is BT_ROOT
    assert callable(execution_root.build_root)


def test_dream_root_reexports_dream_builder():
    from engine.dream.tree.dream_loop import build_dream_root as DREAM_BUILD
    assert dream_root.build_dream_root is DREAM_BUILD


# ---------------------------------------------------------------------------
# Memory CRUD — in-process BT
# ---------------------------------------------------------------------------

MEM_CRUD_EXPECTED_LABELS = {
    "MemoryCrudRoot",
    "触发",
    "读or写?",
    "ReadPathSeq",
    "构造查询条件",
    "调用记忆服务(只读)",
    "把结果填入上下文",
    "WritePathSeq",
    "组装记忆条目",
    "批写场景?",
    "EnqueueSeq",
    "入队等待",
    "ImmediateWriteSeq",
    "写入",
    "确认落盘",
}


def test_memory_crud_topology_has_design_labels():
    root = memory_crud.ROOT
    names = set(_walk_names(root))
    missing = MEM_CRUD_EXPECTED_LABELS - names
    assert not missing, f"missing memory_crud nodes: {missing}\nactual: {names}"


def test_memory_crud_read_path_order():
    """ReadPathSeq children must be ordered: 构造查询条件 → 只读 → 填入上下文."""
    root = memory_crud.ROOT
    read_seq = _find_node_by_name(root, "ReadPathSeq")
    assert read_seq is not None
    child_names = [c.name for c in read_seq.children()]
    assert child_names == ["构造查询条件", "调用记忆服务(只读)", "把结果填入上下文"], \
        f"unexpected read-path order: {child_names}"


def test_memory_crud_write_path_order():
    """WritePathSeq: 组装记忆条目 → 批写分支."""
    root = memory_crud.ROOT
    write_seq = _find_node_by_name(root, "WritePathSeq")
    assert write_seq is not None
    child_names = [c.name for c in write_seq.children()]
    assert child_names == ["组装记忆条目", "批写场景?"], \
        f"unexpected write-path order: {child_names}"


def test_memory_crud_immediate_write_order():
    """即时写入序列：写入 → 确认落盘."""
    root = memory_crud.ROOT
    imm = _find_node_by_name(root, "ImmediateWriteSeq")
    assert imm is not None
    child_names = [c.name for c in imm.children()]
    assert child_names == ["写入", "确认落盘"], \
        f"unexpected immediate-write order: {child_names}"


def _find_node_by_name(root: Node, target: str) -> Node | None:
    if root.name == target:
        return root
    for ch in root.children():
        found = _find_node_by_name(ch, target)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# Memory governance — re-export of dream/actions/mem_steps
# ---------------------------------------------------------------------------

MEM_GOV_EXPECTED_NAMES = {
    "MemoryGovernanceStep",
    "MemHealthScan",
    "MemCompact",
    "MemDistillGate",
    "DispatchMemDistill",
    "CollectMemDistill",
    "MemSweepExpired",
    "MemRebuildIndex",
}


def test_memory_governance_subtree_has_seven_steps(tmp_path: Path):
    subtree = memory_governance.build_memory_governance_subtree(store_dir=tmp_path)
    names = set(_walk_names(subtree))
    missing = MEM_GOV_EXPECTED_NAMES - names
    assert not missing, f"missing memory_governance nodes: {missing}\nactual: {names}"


def test_memory_governance_order_matches_dream_loop(tmp_path: Path):
    """Sub-loop order must match dream/tree/dream_loop.py's inner sequence."""
    subtree = memory_governance.build_memory_governance_subtree(store_dir=tmp_path)
    child_names = [c.name for c in subtree.children()]
    assert child_names == [
        "MemHealthScan", "MemCompact",
        "MemDistillGate", "DispatchMemDistill", "CollectMemDistill",
        "MemSweepExpired", "MemRebuildIndex",
    ], f"unexpected memory_governance order: {child_names}"


# ---------------------------------------------------------------------------
# Agent-side descriptor loops
# ---------------------------------------------------------------------------

ARCH_EXEC_EXPECTED_LABELS = {
    "读取相关模块知识/扫工作区代码",
    "知识与代码同步状态判断",
    "值得为这块代码建立模块知识?",
    "懒式建立新模块知识",
    "直接提取模块路径与约束",
    "定位变更点/补齐知识",
    "验证设计可行性/标记待实现规约",
    "子任务到模块映射",
    "装配 ContextPack",
}


def test_architect_execution_node_specs():
    labels = _labels(architect_execution.NODE_SPECS)
    missing = ARCH_EXEC_EXPECTED_LABELS - labels
    assert not missing, f"missing architect_execution labels: {missing}"
    # ids must be unique
    ids = _ids(architect_execution.NODE_SPECS)
    assert len(ids) == len(architect_execution.NODE_SPECS), "duplicate spec ids"


ARCH_GOV_EXPECTED_LABELS = {
    "加载全量模块索引/读近期执行日志与中期记忆候选",
    "扫孤立模块",
    "扫过期模块",
    "扫依赖冲突",
    "扫已发约束与代码背离",
    "扫记忆提升候选",
    "扫模块裂变需求",
    "扫模块合并冗余",
    "扫依赖重组需求",
    "按动作类别归类",
    "立即执行/计入已落动作",
    "只产建议/计入待裁决建议",
    "装配治理报告",
}


def test_architect_governance_eight_scans_present():
    labels = _labels(architect_governance.NODE_SPECS)
    missing = ARCH_GOV_EXPECTED_LABELS - labels
    assert not missing, f"missing architect_governance labels: {missing}"
    # Must have at least the eight scan steps.
    scan_count = sum(1 for s in architect_governance.NODE_SPECS if s.id.startswith("scan_"))
    assert scan_count == 8, f"expected 8 scan_ specs, got {scan_count}"


HR_GOV_EXPECTED_LABELS = {
    "加载能力册与近期派工/评估痕迹",
    "扫闲置",
    "扫失能",
    "扫累计能力缺口",
    "扫声明与表现漂移",
    "扫能力重复",
    "扫职责过宽",
    "按动作类别归类",
    "立即执行（幂等）",
    "只产建议/不执行",
    "装配治理报告",
}


def test_hr_governance_six_scans_present():
    labels = _labels(hr_governance.NODE_SPECS)
    missing = HR_GOV_EXPECTED_LABELS - labels
    assert not missing, f"missing hr_governance labels: {missing}"
    scan_count = sum(1 for s in hr_governance.NODE_SPECS if s.id.startswith("scan_"))
    assert scan_count == 6, f"expected 6 scan_ specs, got {scan_count}"


# ---------------------------------------------------------------------------
# Descriptor contract — every agent-side loop exposes NODE_SPECS.
# Governance descriptors (architect_governance / hr_governance) also expose
# compose_prompt + parse_response, consumed by the dream-loop dispatch /
# collect leaves to render the architect / HR governance prompts and parse
# the returned reports. architect_execution remains in-process subtree and
# carries _NODE_GUIDE instead.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mod", [
    architect_execution,
    architect_governance,
    hr_governance,
])
def test_descriptor_modules_expose_node_specs(mod):
    assert hasattr(mod, "NODE_SPECS"), f"{mod.__name__}: missing NODE_SPECS"
    assert isinstance(mod.NODE_SPECS, list) and mod.NODE_SPECS
    assert all(isinstance(s, NodeSpec) for s in mod.NODE_SPECS)


@pytest.mark.parametrize("mod", [architect_governance, hr_governance])
def test_governance_descriptors_expose_compose_and_parse(mod):
    """Governance loops are yield-based: dispatch leaves render the prompt
    through compose_prompt(bb); collect leaves parse the reply through
    parse_response(payload). Both must exist as module-level callables."""
    assert callable(getattr(mod, "compose_prompt", None)), \
        f"{mod.__name__}: missing compose_prompt"
    assert callable(getattr(mod, "parse_response", None)), \
        f"{mod.__name__}: missing parse_response"


# ---------------------------------------------------------------------------
# Cross-cutting — engine.execution and engine.dream public APIs unchanged
# ---------------------------------------------------------------------------

def test_bt_public_api_frozen():
    """Sanity guard: the four symbols loops/ depends on must still exist."""
    from engine.execution.tree.main_loop import ROOT, build_root  # noqa: F401
    from engine.execution.api.result import BtResult, DispatchRequest  # noqa: F401


def test_dream_public_api_frozen():
    from engine.dream.tree.dream_loop import build_dream_root  # noqa: F401
    from engine.dream.api.result import DreamResult, DispatchRequest  # noqa: F401
