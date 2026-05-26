"""loops/memory_crud.py — Memory CRUD sub-loop (in-process BT).

Topology mirrors WORKFLOW-MEMORY.zh-CN.md §"主 agent 记忆 CRUD 子循环":

    触发  →  读or写?
            ├─读→ 构造查询条件 → 调用只读接口 → 把结果填入上下文 → 结束
            └─写→ 组装记忆条目 → 批写场景? ├─是→ 入队等待  ─┐
                                          │              ├→ 结束
                                          └─否→ 即时写入 → 确认落盘 ─┘

Iron rules (per design doc and task brief):
  - Pure in-process: no Runner yield, no MCP roundtrip.
  - Only bt.core primitives (Sequence / Selector / custom Node leaves).
  - Each node's `name` field carries the Mermaid label so test topology
    assertions stay aligned with the design doc.

Caller contract (blackboard fields the tree consults):
  bb.crud_op = {"kind": "read"|"write", "batch": bool, "query": ..., "entry": ...}
  bb.crud_result is written by leaves; the tree never reads it back.

Leaves here intentionally do NOT call real memory services — they are
topology placeholders. Real service wiring (FileBackend etc.) is the
caller's job; inject service callables via build_memory_crud_root(
read_call=..., write_call=..., enqueue_call=...) when wiring is ready.
"""
from __future__ import annotations

from typing import Any, Callable

from engine.core.composite import Sequence, Selector
from engine.core.node import Node, Status


# ---------------------------------------------------------------------------
# Branch primitives (custom — not in bt.core, but pure Node subclasses)
# ---------------------------------------------------------------------------

class _CrudBranch(Node):
    """Two-way branch on `bb.crud_op["kind"]` ∈ {"read","write"}.

    Pattern mirrors ModeBranch from bt.core.composite — routes on a bb
    predicate, not on child return value.
    """

    def __init__(self, *, read_path: Node, write_path: Node,
                 name: str = "读or写?") -> None:
        self.name = name
        self._read = read_path
        self._write = write_path

    def children(self) -> list[Node]:
        return [self._read, self._write]

    def tick(self, bb) -> Status:
        op = getattr(bb, "crud_op", None) or {}
        kind = op.get("kind", "read")
        if kind == "read":
            return self._read.tick(bb)
        return self._write.tick(bb)


class _BatchBranch(Node):
    """Two-way branch on `bb.crud_op["batch"]` truthiness.

    True → enqueue path; False → immediate-write path. Matches the
    Mermaid "批写场景?" diamond.
    """

    def __init__(self, *, enqueue_path: Node, immediate_path: Node,
                 name: str = "批写场景?") -> None:
        self.name = name
        self._enqueue = enqueue_path
        self._immediate = immediate_path

    def children(self) -> list[Node]:
        return [self._enqueue, self._immediate]

    def tick(self, bb) -> Status:
        op = getattr(bb, "crud_op", None) or {}
        if op.get("batch"):
            return self._enqueue.tick(bb)
        return self._immediate.tick(bb)


# ---------------------------------------------------------------------------
# Leaf actions — stubs that always SUCCEED; real wiring is injected.
# ---------------------------------------------------------------------------

class _StubLeaf(Node):
    """Action leaf that runs an optional injected callable then succeeds.

    Used for every CRUD leaf so topology is testable without booting a
    real memory backend. When `call` is provided, the leaf invokes it
    with (bb) and stores the return value on `bb.crud_result` under the
    leaf's own `name` key. Exceptions surface as FAILURE.
    """

    def __init__(self, *, name: str, call: Callable[[Any], Any] | None = None) -> None:
        self.name = name
        self._call = call

    def tick(self, bb) -> Status:
        if self._call is None:
            return Status.SUCCESS
        try:
            result = self._call(bb)
        except Exception as e:
            bb.crud_result = {
                "node": self.name,
                "error": f"{type(e).__name__}: {e}",
            }
            return Status.FAILURE
        prev = getattr(bb, "crud_result", None) or {}
        if not isinstance(prev, dict):
            prev = {}
        prev[self.name] = result
        bb.crud_result = prev
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_memory_crud_root(
    *,
    trigger_call: Callable[[Any], Any] | None = None,
    build_query_call: Callable[[Any], Any] | None = None,
    read_call: Callable[[Any], Any] | None = None,
    use_read_call: Callable[[Any], Any] | None = None,
    build_entry_call: Callable[[Any], Any] | None = None,
    enqueue_call: Callable[[Any], Any] | None = None,
    write_call: Callable[[Any], Any] | None = None,
    confirm_call: Callable[[Any], Any] | None = None,
) -> Node:
    """Construct the CRUD sub-loop root.

    All call-injections are optional; without them every leaf simply
    SUCCEEDs, which is enough for topology tests. Callers wiring real
    memory services pass concrete callables here.
    """
    trigger = _StubLeaf(name="触发", call=trigger_call)

    # Read path
    build_query = _StubLeaf(name="构造查询条件", call=build_query_call)
    call_read = _StubLeaf(name="调用记忆服务(只读)", call=read_call)
    use_read = _StubLeaf(name="把结果填入上下文", call=use_read_call)
    read_seq = Sequence(
        [build_query, call_read, use_read],
        name="ReadPathSeq",
    )

    # Write path
    build_entry = _StubLeaf(name="组装记忆条目", call=build_entry_call)
    enqueue = _StubLeaf(name="入队等待", call=enqueue_call)
    write = _StubLeaf(name="写入", call=write_call)
    confirm = _StubLeaf(name="确认落盘", call=confirm_call)

    enqueue_seq = Sequence([enqueue], name="EnqueueSeq")
    immediate_seq = Sequence([write, confirm], name="ImmediateWriteSeq")
    batch_branch = _BatchBranch(
        enqueue_path=enqueue_seq,
        immediate_path=immediate_seq,
        name="批写场景?",
    )
    write_seq = Sequence(
        [build_entry, batch_branch],
        name="WritePathSeq",
    )

    branch = _CrudBranch(
        read_path=read_seq,
        write_path=write_seq,
        name="读or写?",
    )

    root = Sequence([trigger, branch], name="MemoryCrudRoot")
    return root


# Default root for callers that don't need injection (topology tests).
ROOT: Node = build_memory_crud_root()


__all__ = ["ROOT", "build_memory_crud_root"]
