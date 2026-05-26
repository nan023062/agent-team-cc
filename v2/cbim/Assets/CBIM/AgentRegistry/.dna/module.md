---
name: cbim-unity-agent-registry
owner: architect
description: Long-term memory · capability dimension: organizational graph of agent capabilities, roles, and relationships. Unity-side mirror of v1/kernel/cbi/agents + .claude/agents/*.md.
keywords: []
dependencies: []
status: spec
---

## Positioning

长期记忆 · **能力维度**。组织架构图谱——承载 agent 的能力、角色、关系。这是 CBIM 三层记忆体系里的第 3 层，专门管「**谁能干什么、谁向谁汇报**」这类描述系统组织结构的稳定知识。

对齐 Python 侧 `v1/kernel/cbi/agents/` + `.claude/agents/*.md` 的拓扑。Unity 移植起步只发被动读写门面，与 Memory 子模块同构——**不是 actor**，不开循环、不持有定时器、不发通知。

## Responsibility（一句话）

基于 Storage 在磁盘上存取 agent 定义文件（系统提示词、能力描述、技能清单），提供按 name / capability / keywords 的查询表面。

## Three-Layer Memory Context

本模块只覆盖三层记忆里的第 3 层，**能力维度**那一支。完整切分见 `Memory/.dna/module.md`，此处只列与本模块相关的边界：

| 层 | 形态 | 归属 |
|----|------|------|
| 短期记忆 | 会话 transcript | LLM host 适配层（进程内） |
| 中期记忆 | distill 后的事实条目 | `Memory/` |
| **长期记忆 · 能力维度** | agent 能力、角色、关系 | **本模块** |
| 长期记忆 · 业务维度 | 模块树 + 依赖图 | `Dna/` |

**铁律**：本模块只读写 agent 定义文件，不读写记忆条目、不读写模块文档。任何「记忆 distill」「模块 CRUD」「依赖图」需求一律走对应模块。

## Contract Surface（规划）

暴露一个公共类 `AgentRegistryService`，承载四个方法。全部同步——批量 / 缓存是调用方的事。

| 方法 | 用途 |
|------|------|
| `IReadOnlyList<AgentRecord> List()` | 全量枚举，按 name 排序 |
| `AgentRecord Get(string name)` | 按 name 查；不存在返回 null |
| `IReadOnlyList<AgentRecord> Match(string capability, int topK)` | 按能力关键词匹配（先纯关键词，向量检索是后续切片） |
| `AgentStats Stats()` | 计数、按 role 分布、最近变更时间 |

维护接口（`Reload()` / `Validate()`）独立于公共查询表面，通过内部接口 `IAgentRegistryMaintenance` 暴露——只有 Kernel 的治理子循环持有它。这是 C4（接口隔离原则）：查询调用方不会意外触发重载。

## Storage Layout（规划）

落到 `Application.persistentDataPath/.cbim/agents/` 之下：

```
agents/
  <name>.md          ← 单 agent 定义（YAML frontmatter + 系统提示词 body）
  index.json         ← 名称 → 文件路径 + 摘要字段的快速索引
```

单条 agent 的 schema 由 `AgentRecord` 定义（数据类，字段 `name` / `role` / `description` / `capabilities` / `keywords` / `system_prompt`），与 Python 侧 `.claude/agents/*.md` 的 frontmatter 一一对应——跨运行时的工具能同时读两边。

## Dependencies

- `CBIM.Storage`——原子写、JSON / Markdown frontmatter 解析、路径解析。
- **此外什么都不依赖。** AgentRegistry 不准引用 Kernel、不准引用 Memory、不准引用 Dna——asmdef 层面强约束。

## 铁律

- Service 对象没有 `Update()`、没有 `StartCoroutine`、不开 `Task.Run` 做后台。每个公共方法**同步返回**。
- **不持有任何记忆条目。** 与 `MemoryEntry` 是不同 schema，不接受隐式多态使用。
- **不持有模块依赖图。** `.dna/` 的事归 `Dna/` 模块。
- **不是招聘 / 训练流程的执行者。** HR agent 的工作流（招新、训练、考核）在 Kernel 治理循环里跑；本模块只提供"读取当前组织快照"的能力。

## Mirror in Python kernel

Python 对应物是 `v1/kernel/cbi/agents/` + `v1/kernel/cbi/_primitives/agents.py`。C# 移植保持同样的查询表面（list / get / match），落地路径对齐 `.claude/agents/*.md` 的 frontmatter 规范。差异：Unity 侧暂无 agent 创建 / 修改 API（只读门面）——agent 定义在 Unity 项目中由人工编辑或由 Python 侧导出落地；写侧 API 后续切片再发。
