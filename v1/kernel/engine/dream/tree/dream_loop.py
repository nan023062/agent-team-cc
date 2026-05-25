"""tree/dream_loop.py — build_dream_root: governance loop root constructor.

Topology (per WORKFLOW-DREAM §三 + MemDistill triad extension):

    Root (Sequence) @Trace @Timeout(global=30min)
      ├── InitDreamTick
      ├── GovernanceSteps (SequenceTolerant)
      │     ├── MemoryGovernanceStep (Sequence) @Timeout(10min) @Catch
      │     │     ├── MemHealthScan
      │     │     ├── MemCompact
      │     │     ├── MemDistillGate
      │     │     ├── DispatchMemDistill  (yields agent_type="main",
      │     │     │                        subtask_id="governance_memory_distill"
      │     │     │                        — coordinator executes the skill itself)
      │     │     ├── CollectMemDistill   (owns on_resume → bb.mem_distill_result)
      │     │     ├── MemSweepExpired
      │     │     └── MemRebuildIndex
      │     ├── ArchitectGovernanceStep (Sequence) @Timeout(10min) @Catch
      │     │     ├── DispatchArchGovern   (yields agent_type="architect")
      │     │     └── CollectArchAdvice    (owns on_resume → bb.arch_governance_report)
      │     └── HRGovernanceStep (Sequence) @Timeout(10min) @Catch
      │           ├── DispatchHRGovern    (yields agent_type="hr",
      │           │                        subtask_id="governance_capability")
      │           └── CollectHRAdvice     (owns on_resume → bb.hr_governance_report)
      ├── EmitReport
      └── FinalizeDreamTick

EmitReport + FinalizeDreamTick live OUTSIDE the SequenceTolerant container
so they ALWAYS run, even if every governance step failed.

The memory governance step is now 7 nodes: 4 pure-Python structural nodes
(Health / Compact / Sweep / Rebuild) plus the MemDistill triad
(Gate / Dispatch / Collect) which yields to the **main agent** (the
coordinator itself) for the ``memory_distill`` skill — semantic
short→medium compression is LLM-driven, but distillation is a memory-source
responsibility owned by the coordinator (HR lacks ``memory_get`` to read
short-term entry bodies; see prior run f1328bf4eb53).

Architect / HR governance steps remain sub-agent dispatches via the Task
tool; the MemDistill yield is a self-dispatch — on receiving a yield with
``agent_type="main"`` the coordinator runs the prompt in-place instead of
spawning a sub-agent. Combined with the optional MemDistill yield, a
single dream_tick can still yield up to **three** times before reaching Done.
"""

from __future__ import annotations

from pathlib import Path

from engine.core.composite import Sequence
from engine.core.decorator import Catch, Timeout, Trace
from engine.dream.core.composite_tolerant import SequenceTolerant

from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend

from ..actions.collect_arch_advice import CollectArchAdvice
from ..actions.collect_hr_advice import CollectHRAdvice
from ..actions.collect_mem_distill import CollectMemDistill
from ..actions.dispatch_arch import DispatchArchGovern
from ..actions.dispatch_hr import DispatchHRGovern
from ..actions.dispatch_mem_distill import DispatchMemDistill
from ..actions.emit_report import EmitReport
from ..actions.finalize import FinalizeDreamTick
from ..actions.init_tick import InitDreamTick
from ..actions.mem_steps import (
    MemCompact,
    MemDistillGate,
    MemHealthScan,
    MemRebuildIndex,
    MemSweepExpired,
)


def build_dream_root(
    *,
    scheduler_root: Path,
    memory_store_dir: Path,
    memory_backend: MemoryBackend | None = None,
    global_timeout_s: int = 1800,
    step_timeout_s: int = 600,
):
    """Construct the governance loop root.

    Parameters
    ----------
    scheduler_root : Path
        Root for persistence (`.cbim/scheduler/`). EmitReport + FinalizeDreamTick
        write under `<scheduler_root>/dream/`.
    memory_store_dir : Path
        `.cbim/memory/` directory; passed to each MemoryGovernanceStep child.
    memory_backend : MemoryBackend, optional
        Storage backend for sweep / rebuild. Defaults to FileBackend(memory_store_dir).
    global_timeout_s : int
        Hard ceiling for the whole tick (default 30min).
    step_timeout_s : int
        Per-step ceiling (default 10min).
    """
    backend = memory_backend or FileBackend(memory_store_dir)

    init = InitDreamTick(name="InitDreamTick")

    # ---- Memory governance step ----
    mem_seq = Sequence(
        [
            MemHealthScan(store_dir=memory_store_dir, name="MemHealthScan"),
            MemCompact(store_dir=memory_store_dir, name="MemCompact"),
            MemDistillGate(store_dir=memory_store_dir, name="MemDistillGate"),
            DispatchMemDistill(store_dir=memory_store_dir, name="DispatchMemDistill"),
            CollectMemDistill(store_dir=memory_store_dir, name="CollectMemDistill"),
            MemSweepExpired(store_dir=memory_store_dir, backend=backend, name="MemSweepExpired"),
            MemRebuildIndex(store_dir=memory_store_dir, backend=backend, name="MemRebuildIndex"),
        ],
        name="MemoryGovernanceStep",
    )
    mem_step = Catch(
        Timeout(mem_seq, seconds=step_timeout_s, name="MemoryStepTimeout"),
        fallback="swallow",
        name="MemoryStepCatch",
    )

    # ---- Knowledge governance step (yield to architect agent) ----
    arch_seq = Sequence(
        [
            DispatchArchGovern(name="DispatchArchGovern"),
            CollectArchAdvice(name="CollectArchAdvice"),
        ],
        name="ArchitectGovernanceStep",
    )
    arch_step = Catch(
        Timeout(arch_seq, seconds=step_timeout_s, name="ArchStepTimeout"),
        fallback="swallow",
        name="ArchStepCatch",
    )

    # ---- Capability governance step (yield to HR agent) ----
    hr_seq = Sequence(
        [
            DispatchHRGovern(name="DispatchHRGovern"),
            CollectHRAdvice(name="CollectHRAdvice"),
        ],
        name="HRGovernanceStep",
    )
    hr_step = Catch(
        Timeout(hr_seq, seconds=step_timeout_s, name="HRStepTimeout"),
        fallback="swallow",
        name="HRStepCatch",
    )

    governance_steps = SequenceTolerant(
        [mem_step, arch_step, hr_step],
        name="GovernanceSteps",
    )

    emit = EmitReport(scheduler_root=scheduler_root, name="EmitReport")
    finalize = FinalizeDreamTick(scheduler_root=scheduler_root, name="FinalizeDreamTick")

    body = Sequence(
        [init, governance_steps, emit, finalize],
        name="DreamBody",
    )

    return Trace(
        Timeout(body, seconds=global_timeout_s, name="DreamGlobalTimeout"),
        name="DreamRoot",
    )
