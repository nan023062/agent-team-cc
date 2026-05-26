---
tier: short
tags: manual, bug, engine, pending-fix
type: bug-context
---

# BT 执行引擎两个路由 bug（待修，下个 session 接手）

## 现象（本 session 实测）

同一 session 调 `bt_tick` 两次（分别是 Stop hook 升级 + memory 原料源切换设计任务），两次都路由错：
- 返回 `agent_type="work"` / `agent_file=null` / `required_capability="programmer"` / `subtask_id="t1"`
- programmer 两次正确升级 NEEDS_ARCH_DECISION 拒接
- 但 bt_tick_resume 收到拒接后立即返回 `kind="done"`，拒接文本原样回放给用户，不重路由 architect

## Bug 1：FallbackPlan 硬编码 programmer

**位置：** `v1/kernel/engine/execution/actions/arch_exec/fallback_plan.py:28-37`

**链路：** ModeClassify 把设计任务误判为 `execution`（NullLLM 兜底 DEFAULT_MODE="execution"，或 `_ARCHITECT_PATTERNS` 不命中）→ 进 `arch_exec_with_fallback` Selector → arch_exec LLM 链失败（或 NullLLM）→ FallbackPlan 兜底，硬编码 `required_capability="programmer"` + `subtask_id="t1"`。

**关键事实：** 架构师分发路径（`CORE_AGENT_FILES` + `ModeSwitch#architect`）**是存在的**，只是永远不被命中，因为 ModeClassify 永远不输出 `architect`。

## Bug 2：dispatch_work.on_resume 无脑标 ok

**位置：** `v1/kernel/engine/execution/actions/dispatch_work.py:48-59`

WorkAgentLeaf 收到任何 work agent 回执都标 `status="ok"`，下一 tick `tick()` 见 ok 直接 SUCCESS。整棵树 **没有** ConvergeJudge / escalation 识别 / LoopSeq / CallHR 节点（grep 全树确认）。NEEDS_ARCH_DECISION 文本被照原样塞进 final_response，tree 判 done。

## 文档与代码漂移（副发现 1，最痛）

- CLAUDE.md / 之前对话 / 之前 dna 都提到 `v1/kernel/engine/bt/` 与 `6 节点 LoopSeq + CallHR`。
- **实际：** `v1/kernel/engine/bt/` 目录只有空的 `actions/` 和 `tree/`（仅 `__pycache__/`）；真实代码全在 `v1/kernel/engine/execution/`。
- CLAUDE.md 工作流仍引 `bt_tick`，调的是 execution 引擎，不是 bt 目录。命名/文档统一是必修项。

## 副发现 2/3
- arch_exec LLM 链失败被 Selector 完全吞掉转 FallbackPlan，**无任何日志暴露**给用户。session 中"为什么没走 architect"完全不可观测。建议至少在 bb 写一个 `arch_exec_failed_reason`。
- CORE_AGENT_FILES 路径健康，bug 与它无关——bug 1 完全在 ModeClassify 判定 + FallbackPlan 兜底。

## 需 architect 拍板的 5 个决策点

1. Work agent 回执 schema —— 引入结构化 `NEEDS_ARCH_DECISION` / `NEEDS_USER_INPUT` 字段？还是 LLM 判定自由文本？
2. 收敛节点形态 —— ConvergeJudge 单节点 + LoopSeq 回环？Selector + EscalateBranch？最大循环次数？
3. FallbackPlan 行为 —— LLM 失败时：兜底 programmer / 升级 NEEDS_ARCH_DECISION / 回 conversation 让用户澄清？
4. ModeClassify 缺 LLM 时的 DEFAULT_MODE —— 继续 execution，还是改 architect / conversation？
5. mode_classify 规则表 —— 当前缺「升级…设计稿」「改…设计稿」类中文动词组合，导致 architect 性质的元任务被吞进 execution。

## 低垂果实（如果只想止血、不想根治）

- **决策点 5**：mode_classify 加正则 `升级|改|重写.*设计稿|蓝图|blueprint|module\.md|contract\.md` 进 `_ARCHITECT_PATTERNS`，本 session 两次任务都能路由对。
- **决策点 4** 配套：DEFAULT_MODE 改 conversation（让 LLM 不可用时回到用户协商），而不是默拍 execution。
- 二者合一 PR，1-2 小时可交，独立于其它 3 个决策点。

## 5 个关键文件

- `/Users/linan/cbim/v1/kernel/engine/execution/actions/arch_exec/fallback_plan.py`
- `/Users/linan/cbim/v1/kernel/engine/execution/actions/dispatch_work.py`
- `/Users/linan/cbim/v1/kernel/engine/execution/actions/mode_classify.py`
- `/Users/linan/cbim/v1/kernel/engine/execution/actions/respond.py`
- `/Users/linan/cbim/v1/kernel/engine/execution/tree/main_loop.py`

## 下个 session 推荐开局

读这份记忆 + 跑 `cbim skill show ...`（无）或直接 `dispatch architect` 出修复设计稿，从决策点 5 + 4 开始（快修），再单独 PR 处理决策点 1/2/3。
