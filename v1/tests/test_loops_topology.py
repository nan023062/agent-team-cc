"""Topology assertions for engine.loops — the eight-loop catalog.

Pure structural checks: no LLM calls, no Runner ticks, no MCP roundtrips.
Each test reads either a BT subtree's node names or a descriptor module's
NODE_SPECS labels and asserts the design-doc Mermaid labels are present.

When a design doc changes a label, this file is the single place to update.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.bt.core.node import Node
from engine.loops import (
    NodeSpec,
    architect_execution,
    architect_governance,
    dream_root,
    execution_root,
    get_loop,
    hr_execution,
    hr_governance,
    loop_names,
    memory_crud,
    memory_governance,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXPECTED_LOOP_NAMES = {
    "execution_root",
    "dream_root",
    "memory_crud",
    "memory_governance",
    "architect_execution",
    "architect_governance",
    "hr_execution",
    "hr_governance",
}


def test_registry_lists_all_eight_loops():
    assert set(loop_names()) == EXPECTED_LOOP_NAMES


def test_get_loop_returns_modules_for_every_name():
    for name in EXPECTED_LOOP_NAMES:
        mod = get_loop(name)
        assert mod is not None
        assert hasattr(mod, "__name__")


def test_get_loop_unknown_raises():
    with pytest.raises(KeyError):
        get_loop("not_a_loop")


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
    from engine.bt.tree.main_loop import ROOT as BT_ROOT
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
    "MemSweepExpired",
    "MemRebuildIndex",
}


def test_memory_governance_subtree_has_four_steps(tmp_path: Path):
    subtree = memory_governance.build_memory_governance_subtree(store_dir=tmp_path)
    names = set(_walk_names(subtree))
    missing = MEM_GOV_EXPECTED_NAMES - names
    assert not missing, f"missing memory_governance nodes: {missing}\nactual: {names}"


def test_memory_governance_order_matches_dream_loop(tmp_path: Path):
    """Sub-loop order must match dream/tree/dream_loop.py's inner sequence."""
    subtree = memory_governance.build_memory_governance_subtree(store_dir=tmp_path)
    child_names = [c.name for c in subtree.children()]
    assert child_names == [
        "MemHealthScan", "MemCompact", "MemSweepExpired", "MemRebuildIndex",
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


HR_EXEC_EXPECTED_LABELS = {
    "盘点现有能力册",
    "逐子任务匹配",
    "匹配结果",
    "有且胜任",
    "有但能力不足",
    "无匹配",
    "训练/招募/临时兜底",
    "针对性训练已有 agent",
    "懒式招募新 agent",
    "通用 agent 临时承接/登记为能力缺口",
    "登入承接清单",
    "清单覆盖全部子任务?",
    "装配承接清单",
}


def test_hr_execution_node_specs():
    labels = _labels(hr_execution.NODE_SPECS)
    missing = HR_EXEC_EXPECTED_LABELS - labels
    assert not missing, f"missing hr_execution labels: {missing}"
    ids = _ids(hr_execution.NODE_SPECS)
    assert len(ids) == len(hr_execution.NODE_SPECS), "duplicate spec ids"


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
# Descriptor contract — every agent-side loop has the three-piece kit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mod", [
    architect_execution,
    architect_governance,
    hr_execution,
    hr_governance,
])
def test_descriptor_modules_have_three_piece_kit(mod):
    assert hasattr(mod, "NODE_SPECS"), f"{mod.__name__}: missing NODE_SPECS"
    assert hasattr(mod, "compose_prompt"), f"{mod.__name__}: missing compose_prompt"
    assert hasattr(mod, "parse_response"), f"{mod.__name__}: missing parse_response"
    assert isinstance(mod.NODE_SPECS, list) and mod.NODE_SPECS
    assert all(isinstance(s, NodeSpec) for s in mod.NODE_SPECS)


@pytest.mark.parametrize("mod", [
    architect_execution,
    architect_governance,
    hr_execution,
    hr_governance,
])
def test_compose_prompt_returns_nonempty_string(mod):
    class _BB:
        user_request = "test request"
        arch_plan = None
        dna_snapshot = None
        agent_snapshot = None
    out = mod.compose_prompt(_BB())
    assert isinstance(out, str) and out.strip()
    # Every NODE label should appear in the rendered prompt.
    for spec in mod.NODE_SPECS:
        assert spec.label in out, f"{mod.__name__}: label {spec.label!r} not in prompt"


@pytest.mark.parametrize("mod,empty_key", [
    (architect_execution, "arch_plan"),
    (architect_governance, "arch_governance_report"),
    (hr_execution, "agent_assignments"),
    (hr_governance, "hr_governance_report"),
])
def test_parse_response_handles_empty(mod, empty_key):
    out = mod.parse_response(None)
    assert empty_key in out
    assert out[empty_key] is None
    assert "error" in out


@pytest.mark.parametrize("mod,key", [
    (architect_execution, "arch_plan"),
    (architect_governance, "arch_governance_report"),
    (hr_execution, "agent_assignments"),
    (hr_governance, "hr_governance_report"),
])
def test_parse_response_handles_json_string(mod, key):
    import json as _json
    if key == "agent_assignments":
        payload = _json.dumps({key: [{"subtask_id": "t1", "agent_file": "x.md"}]})
    else:
        payload = _json.dumps({key: {"safe_done": [], "pending_advice": []}})
    out = mod.parse_response(payload)
    assert key in out and out[key] is not None


# ---------------------------------------------------------------------------
# Cross-cutting — engine.bt and engine.dream public APIs unchanged
# ---------------------------------------------------------------------------

def test_bt_public_api_frozen():
    """Sanity guard: the four symbols loops/ depends on must still exist."""
    from engine.bt.tree.main_loop import ROOT, build_root  # noqa: F401
    from engine.bt.api.result import BtResult, DispatchRequest  # noqa: F401


def test_dream_public_api_frozen():
    from engine.dream.tree.dream_loop import build_dream_root  # noqa: F401
    from engine.dream.api.result import DreamResult, DispatchRequest  # noqa: F401
