# kernel/engine/execution — 对外契约

> 本契约定义行为树引擎对外暴露的全部接口。**只有 3 个接口**：2 个驱动入口（`bt_tick` / `bt_tick_resume`）+ 1 个观测辅助（`bt_list_running_ticks`）。任何"派 agent / 写黑板 / 读节点内部"的路径都不在本契约——它们要么经协程式 yield/resume 回路、要么归子模块内部。

签名细节以 [`../README.md §6`](../README.md#6-l7-协程式-yieldresume-协议细节) 为准；本文档固化这些签名为公共契约级稳定承诺。

---

## 契约硬约束

| 约束 | 说明 |
|------|------|
| **不暴露黑板直接写** | 黑板字段写者由 design §2.1 表锁定；外部不能跨过 Action 直接写 bb。需要影响树行为只能通过 `user_request` / `context` 两个入参。 |
| **不返回可执行回调** | `BtResult.Yield` 只返回数据描述（`DispatchRequest`）；引擎不交出任何"主 agent 调一下就能跑 Action"的函数引用。控制权要么在引擎、要么在主 agent，无中间态。 |
| **接口集稳定** | 这 3 个接口签名按公共契约级别管理：新增字段可向后兼容追加，删除/重命名/语义变更需走 contract 变更流程。新增第 4 个接口同走变更流程。 |
| **Action 调子 agent 必须经 yield** | 引擎进程内**不**持有"直接调其他 agent 的客户端"。任何 Action 需要派子 agent → `BtResult.Yield(DispatchRequest)` → 主 agent Task tool → `bt_tick_resume` 回交结果。绕开 Task tool 直派是破窗。 |
| **黑板 JSON 快照路径是公开契约** | `.cbim/scheduler/bt/<tick_id>/{bb.json, trace.jsonl, resume.json}` 三个文件名、目录布局、`bb.json.schema_version` 字段**进入公共契约**——外部观测工具（dashboard / 调试 / 审计回放）依赖这套布局。Schema 升级走 `schema_version` 递增 + 向后兼容读取策略。 |

---

## `bt_tick` — 启动新 tick

| 字段 | 内容 |
|------|------|
| 用途 | 接收用户一次新 prompt，启动新 tick，驱动到第一个 yield 或 Done |
| 输入 | `user_request: str`（用户原始 prompt，写入 `bb.user_request`）；`context: dict \| None`（预留扩展位，v2 首版可忽略） |
| 输出 | `BtResult`（三态联合，见下表） |
| 副作用 | 生成新 `tick_id`（UUID v4 短形式）；创建 `.cbim/scheduler/bt/<tick_id>/` 目录；首次落 `bb.json`；append `trace.jsonl` |
| 失败语义 | 启动失败（如目录创建权限不足）返回 `BtResult.Error(error_code="...", error_message="...")`；不抛 |
| 稳定承诺 | 函数签名锁死；`tick_id` 生成策略可换实现但格式（短 UUID 字符串）锁定；新增可选参数走追加 |

## `bt_tick_resume` — 恢复 yielded tick

| 字段 | 内容 |
|------|------|
| 用途 | 主 agent 拿到 Task tool 结果后，把结果回交给指定 `tick_id` 的 RUNNING 树，继续驱动到下一个 yield 或 Done |
| 输入 | `tick_id: str`（前次 `BtResult.Yield` 返回的 ID）；`dispatch_result: dict`（Task tool 的原始返回，schema 与 `DispatchRequest.agent_type` 匹配） |
| 输出 | `BtResult`（三态联合，见下表） |
| 副作用 | 读 `bb.json` + `resume.json` 还原树状态；按 `runner_resume_path` 重建调用栈；通过 `on_resume(bb, payload)` 把 `dispatch_result` 交给路径末端 Action；继续 `tick(bb)`；视情况重写 `bb.json` / `resume.json` / 删除 `resume.json`（Done 时） |
| 失败语义 | `tick_id` 不存在或非 running → `BtResult.Error(error_code="tick_not_found_or_done")`；`dispatch_result` schema 不符 → `BtResult.Error(error_code="dispatch_result_schema_mismatch")`；不抛 |
| 稳定承诺 | 函数签名锁死；两个 error_code 字符串值锁定（外部脚本会枚举判断） |

## `bt_list_running_ticks` — 列出未完成 tick

| 字段 | 内容 |
|------|------|
| 用途 | 观测辅助：列出 `.cbim/scheduler/bt/` 下所有 `bb_status=running` 的 tick；用于主 agent 重启后的孤儿排查、dashboard 显示、调试 |
| 输入 | 无 |
| 输出 | `list[TickStatus]`，每条至少包含：`tick_id`、`created_at`、`updated_at`、`user_request`（摘要）、`last_yield_dispatch_agent`（最后一次 yield 派给谁） |
| 副作用 | 仅读盘；不修改任何状态；不自动续跑孤儿 tick |
| 失败语义 | 目录不存在或为空返回空列表；不抛 |
| 稳定承诺 | `TickStatus` 字段名锁定；新增字段可向后兼容追加；**不**承诺孤儿 tick 自动续跑——是否续跑由部署策略 / 主 agent 决定，本接口只提供清单 |

---

## `BtResult` — 三态联合返回

design §6.2 的精确结构进入契约。

| kind | 必填字段 | 主 agent 收到时应做 |
|------|----------|---------------------|
| `done` | `user_message: str` | 把 `user_message` 输出给用户；丢弃 `tick_id`，本逻辑 tick 结束 |
| `yield` | `tick_id: str`、`dispatch_request: DispatchRequest` | 按 `dispatch_request` 用 Task tool 派出对应 agent；拿到结果后调 `bt_tick_resume(tick_id, result)` |
| `error` | `error_code: str`、`error_message: str`、可选 `interrupt_reason: str` | 把 `error_message` 渲染给用户；若 `interrupt_reason` 非空（软中断），按其语义提示用户后续操作 |

**稳定承诺**：三个 `kind` 字符串值锁定（`"done"` / `"yield"` / `"error"`），不会新增第四态；字段集向后兼容追加。

## `DispatchRequest` — yield 时的派工描述

design §6.3 的精确结构进入契约。

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_type` | `str` | 枚举值见下表；主 agent 据此决定走哪条 Task tool 路径 |
| `agent_file` | `str \| None` | 三大核心 agent（architect / hr / auditor）由引擎查 `CORE_AGENT_FILES` 填定；Work Agent **始终为 None**，由主 agent 收到 yield 后据 `required_capability` 调 MCP `agent_list` 即时匹配 |
| `required_capability` | `str \| None` | **仅 `agent_type="work"` 携带**；架构师 `Assemble` 节点从 `arch_plan.task` 写入的能力枚举值（见 `arch_exec/assemble.py::_VALID_CAPS`）；主 agent 据此调 MCP `agent_list` 在 `.claude/agents/*.md` 中匹配 agent_file，匹配不到回退默认 `.claude/agents/programmer/programmer.md` |
| `prompt` | `str` | 嗂给 Task tool 的完整 prompt，主 agent **原样**嗂入，不解释、不修改 |
| `subtask_id` | `str \| None` | `WorkAgentLeaf` 派工时携带，用于 `bt_tick_resume` 时定位 `bb.subtask_results[id]` |
| `timeout_hint_s` | `int \| None` | 主 agent 可参考的超时建议；非强制 |

**`agent_type` 枚举值（informative — 与 mode 分支一一对应）**：

| 值 | 由哪个 mode 子树产出 | 主 agent 应走的 Task tool 路径 |
|----|----------------------|------------------------------|
| `"architect"` | DispatchArchitect | `.claude/agents/architect/architect.md` |
| `"hr"` | DispatchHR | `.claude/agents/hr/hr.md` |
| `"auditor"` | DispatchAuditor | `.claude/agents/auditor/auditor.md` |
| `"work"` | DispatchWork | 主 agent 据 `required_capability` 调 MCP `agent_list` 在 `.claude/agents/*.md` 中匹配；匹配不到回退默认 `.claude/agents/programmer/programmer.md`（该查表职责不在引擎进程内） |

`direct` mode 不产生 yield（引擎内直接 Respond），故不出现 `agent_type` 值。

**稳定承诺**：现有字段名与语义锁定；现有 4 个 `agent_type` 枚举值（`"architect"` / `"hr"` / `"auditor"` / `"work"`）锁定；`required_capability` 字段语义（仅 work 携带、主 agent 右侧匹配、回退 programmer）锁定；新增字段向后兼容追加；**新增 `agent_type` 枚举值**等同于新增 mode 分支，需走 contract 变更流程（且必须证明无法塞进现有 5 个 mode 之一，见 module.md Non-Goals）。

## 不在契约内的部分

| 项 | 归属 |
|----|------|
| 黑板 schema 与字段写者表 | 归 design `WORKFLOW-EXECUTION.zh-CN.md §2`；通过 `bb.json.schema_version` 管理演进，不通过本契约暴露 |
| 节点 ABC、组合节点、装饰器实现 | 归 `core/` 子模块内部；外部不可见、不可继承（C1 单接口原则） |
| Action 实现内部的 LLM 调用 | 归 `actions/<each>` 内部；通过构造器注入 LLM 客户端，对外只通过 `tick(bb) → Status` 暴露 |
| 树拓扑（节点排列、装饰器叠加顺序） | 归 `tree/main_loop.py`；可静态审计但不通过运行时 API 暴露——审计请直读源码 |
| `trace.jsonl` 单条事件结构 | 归 `persistence/trace.py` 内部；事件类型 (`enter/exit/yield/resume/retry/timeout/catch/trace_self_error`) 是观测约定，不是 RPC 契约——下游消费者按 best-effort 解析 |
| 孤儿 tick 自动恢复策略 | **明确不做**；如需主 agent 重启续跑由部署侧自行实现（基于 `bt_list_running_ticks` + `bt_tick_resume`） |
| 直派 agent 的回调接口 | **明确不做**；任何派工一律经 yield → Task tool → resume 回路 |
