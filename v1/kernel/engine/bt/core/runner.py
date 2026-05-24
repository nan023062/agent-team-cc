"""core/runner.py — Tree driver: tick / yield / resume / persistence orchestration.

Single source of truth for:
  - calling root.tick(bb)
  - detecting yield (bb.pending_dispatch != None after RUNNING)
  - persisting bb.json + resume.json + trace.jsonl through persistence/
  - reconstructing the runner_resume_path by walking the tree post-yield

The Runner is itself stateless across `run()` calls — bb.json + resume.json
on disk is the only continuity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..persistence import snapshot, trace as trace_mod
from .blackboard import Blackboard
from .node import Node, Status


class RunResult:
    """Internal: what Runner.run returns. Translated to BtResult by api layer."""

    __slots__ = ("kind", "user_message", "dispatch_request", "interrupt_reason",
                 "error_code", "error_message")

    def __init__(self, kind: str, **kw) -> None:
        self.kind = kind
        self.user_message = kw.get("user_message")
        self.dispatch_request = kw.get("dispatch_request")
        self.interrupt_reason = kw.get("interrupt_reason")
        self.error_code = kw.get("error_code")
        self.error_message = kw.get("error_message")


DEFAULT_AGENT_TYPE_TO_LEAF: dict[str, str] = {
    "architect": "ArchGate",
    "hr": "CallHR",
    "auditor": "Audit",
    "work": "WorkAgentLeaf",
}


class Runner:
    def __init__(
        self,
        root: Node,
        *,
        scheduler_root: Path,
        subdir: str = "bt",
        agent_type_to_leaf: dict[str, str] | None = None,
    ) -> None:
        """Drive `root` through ticks, persisting under `scheduler_root/<subdir>/`.

        `agent_type_to_leaf` maps `pending_dispatch.agent_type` strings to
        the leaf node name the resume path should target. Defaults to the
        bt main-loop mapping (ArchGate/CallHR/Audit/WorkAgentLeaf). Foreign
        trees (e.g. dream governance loop) pass their own mapping.
        """
        self._root = root
        self._scheduler_root = scheduler_root
        self._subdir = subdir
        self._agent_type_to_leaf = (
            agent_type_to_leaf
            if agent_type_to_leaf is not None
            else DEFAULT_AGENT_TYPE_TO_LEAF
        )

    # ------------------------------------------------------------------
    # Tick driver
    # ------------------------------------------------------------------

    def run(self, bb: Blackboard) -> RunResult:
        """Drive the root to its next yield or terminal state, persisting bb
        + trace + resume.json appropriately."""
        tick_dir = self._scheduler_root / self._subdir / (bb.identifier or "_unset")
        tick_dir.mkdir(parents=True, exist_ok=True)

        # Clear stale pending_dispatch from prior tick (resume sets results
        # then we re-drive).
        bb.pending_dispatch = None

        try:
            status = self._root.tick(bb)
        except Exception as e:
            bb.bb_status = "error"
            self._persist(bb, tick_dir)
            return RunResult(
                "error", error_code="engine_internal",
                error_message=f"{type(e).__name__}: {e}",
                interrupt_reason=bb.interrupt_reason,
            )

        if status is Status.RUNNING and bb.pending_dispatch is not None:
            # Yield path. Compute resume_path first so it lands in bb.json.
            bb.bb_status = "running"
            bb.runner_resume_path = self._build_resume_path(self._root, bb)
            self._persist(bb, tick_dir)
            self._persist_resume(bb, tick_dir)
            self._append_trace(bb, tick_dir, {
                "event": "yield",
                "dispatch": _summarize_dispatch(bb.pending_dispatch),
            })
            return RunResult(
                "yield",
                dispatch_request=bb.pending_dispatch,
            )

        # Terminal — done or error.
        if bb.interrupt_reason and not bb.final_response:
            bb.bb_status = "error"
            self._persist(bb, tick_dir)
            self._clear_resume(tick_dir)
            return RunResult(
                "error", error_code="interrupt",
                error_message=bb.interrupt_reason,
                interrupt_reason=bb.interrupt_reason,
            )

        bb.bb_status = "done"
        self._persist(bb, tick_dir)
        self._clear_resume(tick_dir)
        return RunResult("done", user_message=bb.final_response or "")

    # ------------------------------------------------------------------
    # Resume entry
    # ------------------------------------------------------------------

    def resume(self, bb: Blackboard, dispatch_result: Any) -> RunResult:
        """Deliver a dispatch_result to the path-tail Action via on_resume,
        then continue driving."""
        resume_path = bb.runner_resume_path or []
        # Prime any composite that depends on bb to expose its children
        # (e.g. DispatchParallel rebuilds leaves from bb.dispatch_plan).
        _prime_bb_dependent_composites(self._root, bb)
        target = _find_node_by_path(self._root, resume_path)
        if target is None:
            return RunResult(
                "error",
                error_code="dispatch_result_schema_mismatch",
                error_message=f"resume path not found in tree: {resume_path}",
            )
        try:
            target.on_resume(bb, dispatch_result)
        except Exception as e:
            return RunResult(
                "error",
                error_code="dispatch_result_schema_mismatch",
                error_message=f"on_resume failed for {target.name}: {e}",
            )
        # Clear pending_dispatch — the engine consumed it.
        bb.pending_dispatch = None
        # Re-enter run loop. The resume_path stays on bb so that composites
        # know to skip to the right child on this tick.
        return self.run(bb)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist(self, bb: Blackboard, tick_dir: Path) -> None:
        if not bb.dirty:
            return
        snapshot.write_bb(tick_dir, bb)
        bb.clear_dirty()

    def _persist_resume(self, bb: Blackboard, tick_dir: Path) -> None:
        # runner_resume_path was computed and assigned before _persist, so
        # bb.runner_resume_path is the canonical source.
        snapshot.write_resume(tick_dir, {
            "runner_resume_path": bb.runner_resume_path or [],
            "pending_dispatch": _dispatch_to_dict(bb.pending_dispatch),
        })

    def _clear_resume(self, tick_dir: Path) -> None:
        snapshot.delete_resume(tick_dir)
        # Also clear the in-bb resume path so the next tick (if any reuses the
        # bb object) does not skip children.
        # Caller already advanced bb_status to done/error.

    def _append_trace(self, bb: Blackboard, tick_dir: Path, entry: dict) -> None:
        trace_mod.append(tick_dir, entry)

    # ------------------------------------------------------------------
    # Resume-path construction
    # ------------------------------------------------------------------

    def _build_resume_path(self, root: Node, bb) -> list[str]:
        """Walk the tree and find the path to the deepest RUNNING leaf —
        identified by `bb.pending_dispatch.subtask_id` (if set) for Parallel
        cases (e.g. WorkAgentLeaf#t1), then by the leaf-name registered for
        `pending_dispatch.agent_type` in `self._agent_type_to_leaf`.

        Leaf names are tree-specific; the mapping is injected at Runner
        construction so foreign trees (dream's governance loop) can plug
        their own dispatch leaves without modifying this code.
        """
        pd = bb.pending_dispatch
        target_names: list[str] = []
        if pd is not None:
            if pd.subtask_id:
                base = self._agent_type_to_leaf.get("work", "WorkAgentLeaf")
                target_names.append(f"{base}#{pd.subtask_id}")
            mapped = self._agent_type_to_leaf.get(pd.agent_type, "")
            if mapped:
                target_names.append(mapped)

        for tname in target_names:
            if not tname:
                continue
            path = _find_path_to_name(root, tname)
            if path:
                return path
        # Fallback: empty path means "restart from root" — Runner will re-tick
        # cleanly because Actions check bb state to short-circuit.
        return []


def _prime_bb_dependent_composites(root: Node, bb) -> None:
    """Inject bb into composites that build their children list from bb
    (currently: DispatchParallel). Walk both children() and known
    decorator/composite slots.
    """
    visited: set[int] = set()
    stack: list[Node] = [root]
    while stack:
        n = stack.pop()
        if id(n) in visited:
            continue
        visited.add(id(n))
        # Duck-typed bb injection point.
        if hasattr(n, "_bb_ref"):
            try:
                n._bb_ref = bb
            except Exception:
                pass
        for ch in n.children():
            stack.append(ch)


def _find_path_to_name(node: Node, target: str, acc: list[str] | None = None) -> list[str]:
    acc = (acc or []) + [node.name]
    if node.name == target:
        return acc
    # Allow target like "WorkAgentLeaf" matching any name starting with it.
    if target and not target.endswith("#") and "#" in node.name:
        base = node.name.split("#", 1)[0]
        if base == target:
            return acc
    for ch in node.children():
        sub = _find_path_to_name(ch, target, acc)
        if sub:
            return sub
    return []


def _find_node_by_path(root: Node, path: list[str]) -> Node | None:
    if not path:
        return None
    if root.name != path[0]:
        return None
    cur = root
    for seg in path[1:]:
        matched = None
        for ch in cur.children():
            if ch.name == seg:
                matched = ch
                break
            if "#" in seg and ch.name == seg.split("#", 1)[0]:
                matched = ch
                break
        if matched is None:
            return None
        cur = matched
    return cur


def _summarize_dispatch(pd) -> dict:
    if pd is None:
        return {}
    return {
        "agent_type": pd.agent_type,
        "agent_file": pd.agent_file,
        "subtask_id": pd.subtask_id,
        "prompt_len": len(pd.prompt or ""),
    }


def _dispatch_to_dict(pd) -> dict | None:
    if pd is None:
        return None
    return {
        "agent_type": pd.agent_type,
        "agent_file": pd.agent_file,
        "prompt": pd.prompt,
        "subtask_id": pd.subtask_id,
        "timeout_hint_s": pd.timeout_hint_s,
    }
