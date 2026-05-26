---
name: cbim-unity-dna
owner: architect
description: Long-term memory · business dimension: module knowledge graph of the .dna/ tree and inter-module dependencies. Unity-side mirror of v1/kernel/cbi/_primitives/dna + per-module .dna/.
keywords: []
dependencies: []
status: spec
---

## Positioning

长期记忆 · **业务维度**。模块知识图谱——承载 `.dna/` 模块树与模块间依赖关系。这是 CBIM 三层记忆体系里的第 3 层，专门管「**系统由哪些模块组成、它们如何依赖**」这类描述系统业务结构的稳定知识。

对齐 Python 侧 `v1/kernel/cbi/_primitives/dna/` + 各业务模块根目录下的 `.dna/` 文件夹。Unity 移植起步只发被动读写门面，与 Memory / AgentRegistry 同构——**不是 actor**，不开循环、不持有定时器、不发通知。

## Responsibility（一句话）

基于 Storage 在磁盘上存取 `.dna/module.md` / `contract.md` 等模块文档，提供按路径 / 关键词 / 依赖关系的查询表面。

## Three-Layer Memory Context

本模块只覆盖三层记忆里的第 3 层，**业务维度**那一支。完整切分见 `Memory/.dna/module.md`，此处只列与本模块相关的边界：

| 层 | 形态 | 归属 |
|----|------|------|
| 短期记忆 | 会话 transcript | LLM host 适配层（进程内） |
| 中期记忆 | distill 后的事实条目 | `Memory/` |
| 长期记忆 · 能力维度 | agent 能力、角色、关系 | `AgentRegistry/` |
| **长期记忆 · 业务维度** | 模块树 + 依赖图 | **本模块** |

**铁律**：本模块只读写 `.dna/` 下的模块文档，不读写记忆条目、不读写 agent 定义。任何「记忆 distill」「agent 招新」需求一律走对应模块。

## Contract Surface（规划）

暴露一个公共类 `DnaService`，承载六个方法。全部同步——批量 / 缓存是调用方的事。

| 方法 | 用途 |
|------|------|
| `IReadOnlyList<DnaModule> List()` | 全量枚举，按路径排序 |
| `DnaModule Get(string path)` | 按相对路径查；不存在返回 null |
| `IReadOnlyList<DnaModule> Query(string text, int topK)` | 自由文本检索 module.md body |
| `IReadOnlyList<DnaModule> Children(string parentPath)` | 列出某父模块的直接子模块 |
| `IReadOnlyList<DnaDependency> Dependencies(string path)` | 列出某模块声明的依赖边（出边） |
| `DnaStats Stats()` | 模块数、平均深度、孤立模块计数等健康指标 |

维护接口（`Reindex()` / `ValidateGraph()` / `DetectCycles()`）独立于公共查询表面，通过内部接口 `IDnaMaintenance` 暴露——只有 Kernel 的治理子循环持有它。这是 C4（接口隔离原则）：查询调用方不会意外触发全量重建。

## Storage Layout（规划）

模块文档分散在业务模块根目录下；本服务通过一个集中索引快速定位：

```
<project>/<module-path>/.dna/
  module.md          ← YAML frontmatter（元数据）+ markdown body（架构 + Mermaid）
  contract.md        ← 外部 API / 协议（可选，仅协议边界模块）

Application.persistentDataPath/.cbim/dna/
  index.json         ← 路径 → 模块摘要 + 依赖边的扁平索引
```

单条模块的 schema 由 `DnaModule` 定义（数据类，字段 `path` / `name` / `owner` / `kind` / `description` / `dependencies` / `body_excerpt`），与 Python 侧 `v1/kernel/cbi/_primitives/dna/modules.py` 的 schema 一一对应——跨运行时的工具能同时读两边。

## Dependencies

- `CBIM.Storage`——原子写、JSON / Markdown frontmatter 解析、路径遍历。
- **此外什么都不依赖。** Dna 不准引用 Kernel、不准引用 Memory、不准引用 AgentRegistry——asmdef 层面强约束。

## 铁律

- Service 对象没有 `Update()`、没有 `StartCoroutine`、不开 `Task.Run` 做后台。每个公共方法**同步返回**。
- **不持有任何记忆条目。** 与 `MemoryEntry` 是不同 schema。
- **不持有 agent 定义。** `.claude/agents/*.md` 的事归 `AgentRegistry/` 模块。
- **不是模块 CRUD 写侧的执行者。** 新建 / 拆分 / 弃用模块的工作流由 architect agent 在 Kernel 治理循环里跑；本模块只提供"读取当前模块图快照"的能力。Unity 侧暂无写侧 API；写操作通过 Python 侧 `dna_*` MCP 工具完成，本服务定期 reindex 拉取最新快照。

## Mirror in Python kernel

Python 对应物是 `v1/kernel/cbi/_primitives/dna/` + 各业务模块的 `.dna/`。C# 移植保持同样的查询表面（list / get / query / children / dependencies），落地路径对齐 `.dna/module.md` 的 frontmatter + body 规范。差异：Unity 侧暂无模块写侧 API（init / edit / split / reindex 都不发）——只读门面，写侧后续切片再发，或永远保留为「Python 写、Unity 读」的单向同步。
