"""tree/dream_loop.py — build_dream_root: governance loop root constructor.

Topology (per WORKFLOW-DREAM §三):

    Root (Sequence) @Trace @Timeout(global=30min)
      ├── InitDreamTick
      ├── GovernanceSteps (SequenceTolerant)
      │     ├── MemoryGovernanceStep (Sequence) @Timeout(10min) @Catch
      │     │     ├── MemHealthScan
      │     │     ├── MemCompact
      │     │     ├── MemSweepExpired
      │     │     └── MemRebuildIndex
      │     ├── ArchitectGovernanceStep (Sequence) @Timeout(10min) @Catch
      │     │     ├── DispatchArchGovern
      │     │     └── CollectArchAdvice
      │     └── HRGovernanceStep (Sequence) @Timeout(10min) @Catch
      │           ├── DispatchHRGovern
      │           └── CollectHRAdvice
      ├── EmitReport
      └── FinalizeDreamTick

EmitReport + FinalizeDreamTick live OUTSIDE the SequenceTolerant container
so they ALWAYS run, even if all three governance steps failed.
"""

from __future__ import annotations

from pathlib import Path

from engine.bt.core.composite import Sequence
from engine.bt.core.decorator import Catch, Timeout, Trace
from engine.dream.core.composite_tolerant import SequenceTolerant

from memory.crud.backend import MemoryBackend
from memory.crud.file_backend import FileBackend

from ..actions.collect_advice import CollectArchAdvice, CollectHRAdvice
from ..actions.dispatch_arch import DispatchArchGovern
from ..actions.dispatch_hr import DispatchHRGovern
from ..actions.emit_report import EmitReport
from ..actions.finalize import FinalizeDreamTick
from ..actions.init_tick import InitDreamTick
from ..actions.mem_steps import (
    MemCompact,
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

    # ---- Knowledge governance step ----
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

    # ---- Capability governance step ----
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
