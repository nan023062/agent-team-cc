# PR-D — Remove all in-kernel LLM calls

**Scope:** Excise every direct LLM client from the kernel. After this PR, the kernel is a pure scheduler — it builds the BT, drives ticks, yields dispatch requests, parses receipts. All language understanding is performed by the architect / HR / auditor / work agents through the Claude Code Task tool. The kernel never holds an `anthropic.Anthropic` client, never reads `ANTHROPIC_API_KEY`, never embeds prompt templates whose output is parsed as JSON.

**Depends on:** PR-A (receipt trailer schema — the architect's reply will carry `arch_plan` inside a structured trailer the kernel already knows how to parse), PR-C (ConvergeJudge + WorkLoop + EscalationGate — WorkLoop already re-enters its first child on `arch_redo`, so swapping that child is the only topology change needed).

**Out of scope:** Receipt schema changes (PR-A is reused as-is — see §3.2 for the field-mapping discussion). Convergence semantics (PR-C is reused as-is). ModeClassify rule table tuning (the v3.7 patterns from `design/MODE-CLASSIFY-V3.7.md` stand; only the LLM-fallback branch is cut). Dream / governance loop (separate root, no LLM in it).

**Status:** spec, ready for implementation.
**Owner:** architect (this doc) → programmer (implementation) → auditor (review).

---

## 1. Background and Positioning

In the CBIM Claude Code edition the agent surface is Claude Code itself — every dispatch becomes a Task-tool invocation that wakes a real model. The kernel's job is to decide who to wake, with what prompt, in what order, and to consolidate the receipts. Holding a separate LLM client inside the kernel buys us nothing in that environment and costs us five concrete problems:

1. **Dual budget.** Every tick of the architect-execution subtree fires 5–9 Anthropic API calls (Scan + StateCheck + one of {Worth+Create, Extract, Diff, Validate} + Map + Assemble), paid from a different bucket than the Task-tool subagent budget. The user sees the same wall-clock cost twice.
2. **Two routing brains.** ModeClassify's rule miss falls through to `llm.classify_mode`, which makes a second classification decision the user cannot audit. The route the engine took is opaque unless we log it; the engine's static topology (`design/WORKFLOW-EXECUTION.zh-CN.md`) implies one classification, the live behavior produces another.
3. **NullLLM masks failures.** When `ANTHROPIC_API_KEY` is unset (the common case in tests and in fresh installs), every LLM call silently returns a stub — `{"result": null}` for `LlmActionLeaf.run`, `"execution"` for `classify_mode`, a passthrough for `reply_conversation`. The engine appears to work; the symptom only surfaces three levels down when `extract_json` returns None and the architect-execution Selector falls through to its fallback. By the time the user notices, the trace is buried.
4. **Schema drift.** Each of the nine arch_exec leaves carries its own prompt template, JSON shape, and parser. The architect agent (`.claude/agents/architect/architect.md`) carries its own duplicate procedural knowledge for the same workflow. Two sources of truth, both editable, both drift independently. The architect agent is the canonical seat of "how do I decompose this request" — the kernel's copy is a stale shadow.
5. **Kernel-only-writes rule is undermined.** CLAUDE.md forbids the LLM from writing to `.dna/` directly; the architect agent enforces this via MCP tools. The arch_exec subtree bypasses that — its LLM call is in-process, not a dispatch, so the architect persona is never loaded and the MCP-only-writes discipline is never applied. Any "create" decision in `worth.py → create.py` produces no `.dna/` writes at all (those leaves only fill `bb.arch_context`), which means the "knowledge first" rule is silently violated on every cold path.

PR-D resolves all five by deleting the LLM client and replacing the nine-node chain with one yield to the existing architect agent. The agent is already wired (`CORE_AGENT_FILES["architect"]`), already has the MCP toolset, already speaks the receipt-trailer protocol — it just needs to carry `arch_plan` in its reply.

---

## 2. Deletion manifest

All paths relative to `D:/GitRepository/cbim-kernel/`.

### 2.1 Delete entirely

```
v1/kernel/engine/execution/actions/arch_exec/                 (whole directory)
  ├── __init__.py
  ├── _helpers.py
  ├── assemble.py
  ├── create.py
  ├── diff.py
  ├── extract.py
  ├── map_tasks.py
  ├── scan.py
  ├── state_check.py
  ├── validate.py
  └── worth.py

v1/kernel/engine/execution/loops/architect_execution.py        (descriptor + _NODE_GUIDE)

v1/kernel/engine/execution/actions/llm_client.py               (AnthropicLLM)
v1/kernel/engine/execution/actions/llm_hook.py                 (NullLLM)
v1/kernel/engine/core/llm_leaf.py                              (LlmActionLeaf — sole consumer was arch_exec/*)
```

Grep confirms `LlmActionLeaf` has no consumer outside `arch_exec/*` and its own tests (`v1/tests/test_core_llm_leaf.py`, `v1/tests/test_bt_llm_integration.py`).

### 2.2 Edit in place

| File | Edit |
|------|------|
| `v1/kernel/engine/core/__init__.py` | Drop the `LlmActionLeaf` import and `__all__` entry. |
| `v1/kernel/engine/execution/loops/__init__.py` | Drop any re-export of `architect_execution` / `build_architect_execution_subtree`. |
| `v1/kernel/engine/execution/actions/mode_classify.py` | Drop the `llm` constructor parameter, the `from .llm_hook import NullLLM` import, the §7 LLM fallback block (lines ~299–306). Rule miss falls straight to `DEFAULT_MODE` ("execution"). See §4. |
| `v1/kernel/engine/execution/actions/direct_reply.py` | Drop the `llm` constructor parameter, the `from .llm_hook import NullLLM` import, the LLM call. Reply is the deterministic passthrough `f"（对话模式）{text}"` (which is exactly what NullLLM already returned today) — keep the empty-text early return. See §5. |
| `v1/kernel/engine/execution/tree/main_loop.py` | Drop `_default_llm`, the `from ..actions.llm_hook import NullLLM` import, the `llm` parameter on `build_root`, the `llm=llm` kwargs on `ModeClassify` / `DirectReply`, and the `arch_exec = build_architect_execution_subtree(llm)` call. Replace `arch_exec` with the new `ArchExecYield` leaf. The `ArchExecOrFallback` Selector that previously wrapped `arch_exec` collapses to a direct child reference; keep the name `ArchExecOrFallback` (with `ArchExecYield` as its sole child) only if the existing topology tests pin that node name — otherwise drop the Selector. See §6. |
| `v1/kernel/engine/execution/actions/__init__.py` (if it re-exports any of the deleted symbols) | Drop those re-exports. |

### 2.3 Add

```
v1/kernel/engine/execution/actions/arch_exec_yield.py          (new — see §3)
```

That is the entire new-code footprint of this PR. One file, one class, ~80 lines.

### 2.4 .dna updates (architect-side, post-merge)

These are not source-code edits — they are knowledge-system updates that the architect performs through `dna_edit` after the code lands:

- `v1/kernel/engine/execution/.dna/module.md` — strike the in-process arch_exec subtree from the topology diagram; the body now shows `WorkLoop` first child as `ArchExecYield (dispatch → architect agent)`.
- `v1/kernel/engine/execution/.dna/contract.md` — drop the `LlmActionLeaf` / `AnthropicLLM` mentions if present.
- `v1/kernel/engine/core/.dna/module.md` — drop the `LlmActionLeaf` row from the primitives list.
- `design/WORKFLOW-EXECUTION.zh-CN.md`, `design/WORKFLOW-ARCHITECT.zh-CN.md` — update the topology + sub-loop sections to match. Out of code scope; tracked in the architect's follow-up task.

---

## 3. ArchExecYield — the new leaf

### 3.1 Position in the tree

`ArchExecYield` is the **first child of `WorkLoop`**, replacing the entire `ArchExecOrFallback (Selector [ArchitectExecution])` block. PR-C's LoopSeq semantics are unchanged: on `bb.convergence == "arch_redo"` WorkLoop re-enters its first child, which means a second architect yield with the redo context in the prompt. On the first iteration there is no redo context — the agent works from `bb.user_request` alone.

### 3.2 Contract

```python
class ArchExecYield(Node):
    """Single-yield leaf — dispatches the architect agent and parses
    `arch_plan` out of the receipt trailer.

    First tick: fills bb.pending_dispatch with a DispatchRequest to
    .claude/agents/architect/architect.md, returns RUNNING.

    on_resume: parses the trailer via receipt.parse_trailer, extracts
    arch_plan from trailer.extras["arch_plan"] (JSON-encoded list[dict]),
    writes bb.arch_plan, clears bb.pending_dispatch.

    Re-tick after resume: SUCCESS if bb.arch_plan is non-empty, FAILURE
    otherwise (malformed trailer / missing arch_plan / parse error).
    """

    name: str = "ArchExecYield"

    def tick(self, bb) -> Status: ...
    def on_resume(self, bb, payload) -> None: ...
```

### 3.3 Dispatch prompt shape

The prompt sent to the architect is the user request augmented with three signals the agent needs to produce a coherent plan:

```
## 执行模式 · ArchExec

### 用户请求
{bb.user_request}

### 知识快照
{bb.knowledge_snapshot or "(无快照 — 自行调用 dna_list / dna_show 查询)"}

### 重入上下文
{json.dumps(bb.arch_redo_context, ensure_ascii=False, indent=2) if bb.arch_redo_context else "(首次进入)"}

### 任务
扫描受影响模块、判断知识/代码同步状态、必要时通过 MCP 写入 .dna/，
最终产出 arch_plan（list[dict]）作为给 Work Agent 的 ContextPack 来源。

每条 task 字段：
  id (str, 唯一)
  description (str)
  required_capability (str, ∈ {programmer, tester, doc_writer, generalist})
  params (dict)
  arch_context (str, 非空)

约束：
  - task 总数 ≤ 8
  - 依赖关系写入 params.depends_on (list[str])，不能成环
  - 不可执行 → arch_plan 留空 list，receipt status=needs_user_input + question

### 回执格式
按 PR-A 回执 trailer 规范，并在 trailer 中追加一行：
  arch_plan: <JSON-encoded list[dict]>
```

This prompt is composed inside `ArchExecYield.tick`; it is intentionally short — the heavy lifting (decomposition heuristics, module-state reasoning, `.dna/` writes) is the architect persona's job, and the persona has its own skills (`architect.arch_modules`, `architect.arch_governance`) for that. The kernel does not duplicate them.

### 3.4 arch_plan extraction from the receipt

PR-A's `parse_trailer` (in `actions/receipt.py`) already collects unknown trailer fields into `ReceiptTrailer.extras`. The architect's reply will look like:

```
<!-- BEGIN CBIM-RECEIPT v1
status: ok
task_id: <ArchExecYield's stable subtask_id, e.g. "arch:1">
agent: architect
summary: 拆出 3 个 Work Agent 子任务
arch_plan: [{"id":"t1","description":"...","required_capability":"programmer","params":{},"arch_context":"..."}, ...]
END CBIM-RECEIPT -->
```

`on_resume` reads `trailer.extras["arch_plan"]`, runs `json.loads`, validates per the same shape `arch_exec/assemble.py:_parse` enforced today (every item has `id` / `description` / `required_capability` / `params` / `arch_context`; unknown capabilities collapse to `"generalist"`; list length ≤ 8). On any validation failure: `bb.arch_plan = []` and the next `tick` returns FAILURE — WorkLoop bubbles FAILURE to the outer ExecutionSeq, which surfaces as a coordinator-visible error via the existing CatchFlush path. There is no fallback plan and no silent degradation; an unparseable architect reply is treated like any other agent failure.

Status enum mapping on the receipt:
- `status="ok"` + non-empty `arch_plan` → SUCCESS, WorkLoop proceeds to DispatchWork.
- `status="ok"` + empty `arch_plan` → bb.arch_plan = [], DispatchWork no-ops (existing behavior for empty plan), ConvergeJudge writes `convergence="done"`, Respond renders a "no work needed" reply.
- `status="needs_user_input"` → bb.arch_plan = [], bb.convergence is set directly to `"user_input"` by `on_resume` (bypassing ConvergeJudge — the architect already determined human input is required); WorkLoop SUCCESS, EscalationGate routes to `Respond#need_user`. The `question` field from the trailer is surfaced.
- `status="needs_arch_decision"` is not legal here (the architect is already deciding) — coerced to `failed`.
- `status="failed"` → bb.arch_plan = [], FAILURE bubbles, the existing CatchFlush handles cleanup.

### 3.5 Cross-tick state

Same iron rule as every other leaf: no field on `self` survives across ticks. The leaf inspects `bb.arch_plan` on each tick to decide whether to yield again or short-circuit. The result-key scheme follows `DispatchCoreAgent`: subtask_id is `"arch:<iter>"` where `<iter>` is the current `bb.work_loop_iter` value (PR-C field), so the second-and-later architect yields produced by `arch_redo` re-entry get distinct subtask_ids and the runner's resume path can disambiguate.

---

## 4. ModeClassify — rule-only

The v3.7 pattern tables (`_ARCHITECT_PREEMPT_PATTERNS`, `_EXECUTION_PATTERNS`, `_ARCHITECT_PATTERNS`, `_HR_PATTERNS`, `_AUDIT_PATTERNS`, `_CONVERSATION_PATTERNS`) stay as-is — they are pure regex, no LLM. The change is the tail of `ModeClassify.tick`:

**Before** (lines 298–306):
```python
# 7. Rule miss — defer to LLM (NullLLM returns DEFAULT_MODE).
try:
    verdict = self._llm.classify_mode(text)
except Exception:
    verdict = DEFAULT_MODE
if verdict not in MODES:
    verdict = DEFAULT_MODE
bb.mode = verdict
return Status.SUCCESS
```

**After**:
```python
# 7. Rule miss — default to execution (the safe "send through the
# Architect → Work pipeline" path). The kernel performs no LLM
# classification; the architect itself reroutes if the request turns
# out to be conversational on closer inspection.
bb.mode = DEFAULT_MODE
return Status.SUCCESS
```

Constructor change:
```python
class ModeClassify(Node):
    def __init__(self, *, name: str = "ModeClassify") -> None:
        self.name = name
```

The `llm` parameter is removed. `MODES` and `DEFAULT_MODE` constants stay; downstream code still imports them.

**Why DEFAULT_MODE = "execution" is the right miss-bucket.** Rule miss means the regex tables found no explicit "ask the architect / hire someone / audit X / question" signal and no execution verb. In practice that's an ambiguous request like "the API is slow" or "看一下这块". Routing it through the execution pipeline gives the architect a chance to clarify (it can return `status="needs_user_input"` with a question), whereas routing it to conversation forces a one-shot reply with no follow-up. The cost of an unnecessary execution pass is a single architect yield that produces an empty plan; the cost of a missed execution is the user re-asking.

---

## 5. DirectReply — passthrough

`DirectReply` is the conversation-mode fast path. Today it calls `llm.reply_conversation` and falls back to `f"（对话模式）{text}"` on any exception. After PR-D the LLM call is gone — the deterministic passthrough is the full implementation:

```python
class DirectReply(Node):
    def __init__(self, *, name: str = "DirectReply") -> None:
        self.name = name

    def tick(self, bb) -> Status:
        text = (bb.user_request or "").strip()
        if not text:
            bb.final_response = "请描述你的需求。"
            return Status.SUCCESS
        bb.final_response = f"（对话模式）{text}"
        return Status.SUCCESS
```

This is identical to the NullLLM path that runs today whenever `ANTHROPIC_API_KEY` is unset. In the Claude Code edition the coordinator (main agent) is itself the conversational voice — when the user asks a question, the user is already talking to a model. Adding a second model behind `DirectReply` would only matter if the kernel were running headless; that is not its environment. The passthrough is the deliberate design, not a degradation.

If the project ever needs a richer conversational reply, the right pattern is to route conversation mode through a core-agent dispatch (same shape as `DispatchCoreAgent#architect`), targeting a yet-to-be-recruited `.claude/agents/assistant/assistant.md`. That is out of scope for PR-D and noted here only to forestall the "but we lose the LLM reply" objection.

---

## 6. main_loop.py — new topology

### 6.1 New shape

```
Root (Trace > Timeout > RootSeq)
  InitTick
  ModeClassify                                  -- no llm param
  ModeSwitch (SwitchBranch on bb.mode)
    conversation → DirectReply                  -- no llm param
    architect    → ArchitectBranch (Sequence)
        DispatchCoreAgent#architect             -- unchanged
        Respond#architect                       -- unchanged
    hr           → HrBranch (Sequence)
        DispatchCoreAgent#hr                    -- unchanged
        Respond#hr                              -- unchanged
    audit        → AuditBranch (Sequence)
        DispatchCoreAgent#auditor               -- unchanged
        Respond#audit                           -- unchanged
    execution    → ExecutionSeq (Sequence)
        WorkLoop (LoopSeq, max_iters=3)
          ArchExecYield                         -- NEW: replaces arch_exec subtree
          DispatchWork                          -- unchanged
          ConvergeJudge                         -- unchanged
        EscalationGate (SwitchBranch on bb.convergence)
          "done"       → Respond                -- unchanged
          "user_input" → Respond#need_user      -- unchanged
          "exhausted"  → Respond#exhausted      -- unchanged
        CatchFlush(FlushMemory)                 -- unchanged
    default      → ExecutionSeq (mirror)
```

### 6.2 build_root signature

```python
def build_root(*, global_timeout_s: int = 1800):
    # No llm parameter — the kernel holds no LLM client.
    init = InitTick(name="InitTick")
    classify = ModeClassify(name="ModeClassify")
    direct   = DirectReply(name="DirectReply")
    ...
    arch_exec_yield = ArchExecYield(name="ArchExecYield")
    work_loop = LoopSeq(
        [arch_exec_yield, dispatch_work, converge_judge],
        max_iters=DEFAULT_MAX_ITERS,
        name="WorkLoop",
    )
    ...
```

The `ArchExecOrFallback` Selector is dropped — it existed to wrap the nine-node subtree so a single LLM parse failure would surface as Selector fallthrough. With one leaf and no LLM, the Selector has nothing to choose from. If the topology test `test_loops_topology.py` pins the name `"ArchExecOrFallback"`, the test is wrong post-PR-D and must be updated; the architectural answer is to use the leaf directly.

### 6.3 _default_llm — deleted

The whole helper (lines 60–74) is removed. The module no longer imports `os`, `AnthropicLLM`, or `NullLLM`. `engine.execution.tree.main_loop` becomes import-clean against environments without the `anthropic` SDK installed — which it already was via the deferred import in `llm_client.py`, but now becomes structurally so.

---

## 7. Acceptance criteria

A clean PR-D merge satisfies all of the following. Each is mechanically checkable.

### 7.1 Grep gates

Run from `D:/GitRepository/cbim-kernel/`:

```
rg "AnthropicLLM"           v1/kernel/        # expect 0 matches
rg "NullLLM"                v1/kernel/        # expect 0 matches
rg "ANTHROPIC_API_KEY"      v1/kernel/        # expect 0 matches
rg "LlmActionLeaf"          v1/kernel/        # expect 0 matches
rg "llm_client"             v1/kernel/        # expect 0 matches
rg "llm_hook"               v1/kernel/        # expect 0 matches
rg "classify_mode"          v1/kernel/        # expect 0 matches (was on AnthropicLLM/NullLLM)
rg "reply_conversation"     v1/kernel/        # expect 0 matches
rg "build_architect_execution_subtree" v1/kernel/  # expect 0 matches
rg "import anthropic"       v1/kernel/        # expect 0 matches
rg "_default_llm"           v1/kernel/        # expect 0 matches
```

### 7.2 Import sanity

```
python -c "from engine.execution.tree.main_loop import build_root; build_root()"
```

must succeed on a machine where `anthropic` is not installed and `ANTHROPIC_API_KEY` is unset. No deferred-import escape hatches — the import graph must be structurally clean.

### 7.3 Directory state

```
v1/kernel/engine/execution/actions/arch_exec/        does not exist
v1/kernel/engine/execution/actions/llm_client.py     does not exist
v1/kernel/engine/execution/actions/llm_hook.py       does not exist
v1/kernel/engine/execution/loops/architect_execution.py  does not exist
v1/kernel/engine/core/llm_leaf.py                    does not exist
v1/kernel/engine/execution/actions/arch_exec_yield.py    exists
```

### 7.4 Behavioral

- `bt_tick("hello")` → mode resolves to `conversation` via rule path → `Respond` returns `"（对话模式）hello"`. No agent dispatch, no error.
- `bt_tick("implement foo")` → mode resolves to `execution` via rule path → first yield's `dispatch_request.agent_type == "architect"`, `agent_file == ".claude/agents/architect/architect.md"`, prompt begins with `"## 执行模式 · ArchExec"`.
- `bt_tick_resume(tick_id, dispatch_result=<architect reply with valid trailer + arch_plan>)` → next yield's `agent_type == "work"`, `subtask_id` equals the first arch_plan task's `id`.
- `bt_tick("当用户说点完全跑不出规则的话")` (rule miss) → mode is `execution` (no LLM fallback), first yield dispatches the architect.

### 7.5 Public surface unchanged

`BtResult`, `DispatchRequest`, `Task`, `TickStatus` (in `api/result.py`) are not edited by PR-D. The MCP boundary in `mcp_server/tools/bt.py` is untouched. The coordinator workflow described in `CLAUDE.md` "## Workflow" remains correct verbatim.

---

## 8. Impacted tests

The following test files reference at least one of the symbols PR-D deletes. Each must be updated or removed; "remove" candidates are the ones whose entire purpose was to exercise the in-kernel LLM path.

| File | Disposition | Reason |
|------|-------------|--------|
| `v1/tests/test_core_llm_leaf.py`             | **Delete** | Tests `LlmActionLeaf` directly; primitive is gone. |
| `v1/tests/test_bt_llm_integration.py`        | **Delete** | End-to-end smoke for the arch_exec nine-node chain; that chain is gone. |
| `v1/tests/stub_llm.py`                       | **Delete** | Helper that returned stub JSON for `LlmActionLeaf.run`; no consumer left. |
| `v1/tests/test_loops_topology.py`            | **Update** | Pins `NODE_SPECS` from `architect_execution.py` (deleted). Drop the sub-loop topology assertions; keep the top-level main_loop shape pins and update the WorkLoop-children expectation to `[ArchExecYield, DispatchWork, ConvergeJudge]`. |
| `v1/tests/test_bt_l1_nodes.py`               | **Update** | Heavy `LlmActionLeaf` / `NullLLM` / `AnthropicLLM` usage (29 matches). Replace `LlmActionLeaf`-specific cases with a small `ArchExecYield` unit test (mock receipt → bb.arch_plan); strip `NullLLM` references from `ModeClassify` / `DirectReply` cases (constructors no longer take `llm`). |
| `v1/tests/test_bt_l2_tree.py`                | **Update** | References `arch_exec` / `ArchitectExecution` in tree-shape assertions. Update to assert `ArchExecYield` as WorkLoop's first child. |
| `v1/tests/test_bt_l3_persistence.py`         | **Update** | Constructs `build_root(llm=...)`. Drop the `llm` kwarg; the function signature no longer accepts it. |
| `v1/tests/test_bt_l4_e2e.py`                 | **Update** | Same — drop `llm` kwarg from `build_root` calls. |
| `v1/tests/conftest.py`                       | **Update** | If it provides an `llm_stub` fixture, mark it removed (or repurpose to a fake architect-receipt fixture for the new `ArchExecYield` test). |
| `v1/tests/workflow/conftest.py`              | **Update** | Same — drop any LLM stub plumbing; the workflow-bench harness now drives via `bt_tick` and supplies a fake Task-tool that responds with canned receipts. |
| `v1/tests/test_main_loop_workloop.py`        | **Update** | Asserts WorkLoop child sequence. Update first-child name to `"ArchExecYield"`. |
| `v1/tests/test_bt_l4_e2e.py` (already listed)| — | — |

Tests not in this table (e.g. `test_receipt.py`, `test_converge_judge.py`, `test_dispatch_work_receipt.py`, the dream-side tests, the audit tests) are unaffected — they exercise modules PR-D does not touch.

**New tests to add** (one file, ~3 cases):

- `v1/tests/test_arch_exec_yield.py`:
  - `tick_first_call_yields_architect_dispatch`: fresh bb → tick returns RUNNING, `bb.pending_dispatch.agent_type == "architect"`, `agent_file == ".claude/agents/architect/architect.md"`.
  - `on_resume_with_valid_trailer_populates_arch_plan`: feed a fake architect reply with a well-formed trailer containing `arch_plan: [...]` → `bb.arch_plan` is the parsed list, next tick is SUCCESS.
  - `on_resume_with_malformed_trailer_fails`: feed garbage → `bb.arch_plan == []`, next tick is FAILURE.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| **Architect agent doesn't emit `arch_plan` in trailer.** | The architect agent file (`.claude/agents/architect/architect.md`) needs a small addition documenting the trailer contract — one short section: "When dispatched in execution mode (prompt starts with `## 执行模式 · ArchExec`), append `arch_plan: <JSON>` to your receipt trailer." This edit is done via `agent_edit` MCP tool post-merge; not a code change. |
| **Rule miss now defaults silently to execution instead of an LLM-classified mode.** | This is the documented behavior (§4). The architect agent itself can return `status="needs_user_input"` if it sees the request was conversational — that path already exists (§3.4). |
| **Workflow benchmarks (`v1/tests/workflow/`) compare end-to-end behavior across iterations.** | They will need fake-receipt fixtures instead of a live LLM. The benchmark harness (`v1/tests/workflow/cli.py`) already supports stubbing Task-tool outputs per spec; the wiring change is mechanical. |
| **Some downstream tool consumes `engine.core.LlmActionLeaf` from outside the kernel.** | Grep across the repo (`rg LlmActionLeaf D:/GitRepository/cbim-kernel/`) shows only kernel-internal consumers + the tests in §8. No external consumers. Safe to delete. |
| **`extras["arch_plan"]` in the receipt could overflow line length.** | The trailer is line-oriented but values can be arbitrarily long (the parser splits only on the first `:`). JSON-encoded plans up to 8 × ~300 chars = ~2400 chars sit comfortably on one line; if it ever exceeds the practical line limit, the trailer schema can be extended to support continuation in a follow-up PR — out of scope here. |

---

## 10. Open questions

None blocking. The architect agent's prompt-side documentation edit (Risk #1) is the only follow-up that must land alongside this PR; everything else is mechanical code change.

---

## 11. One-line summary

**Strip the kernel of every LLM call; replace the nine-leaf in-process architect subtree with one yield to the architect agent that already lives in `.claude/agents/architect/architect.md`.**
