---
name: cbim-unity-tools-standard
owner: architect
description: CBIM 内置标准工具家族——Files / Search（未来扩展 Web / Bash）。无状态门面 StandardToolsService 按家族名 + Sandbox 实例化为扁平 AIFunction 列表，挂到 ChatClientAgentOptions.ChatOptions.Tools。家族表硬编码 IToolFamilyFactory，不开放插件点。装配开销 ≈ 0（无 IPC、无握手）。原 AgentSystem/StandardTools/ 整体迁入此处，namespace 改为 CBIM.Tools.Standard。
keywords: []
dependencies: []
status: spec
---

## Positioning

CBIM 内置标准工具家族的**唯一实现处**——Files / Search 两个 AIFunction 家族（未来扩展 Web / Bash）。

**形态**：无状态门面 `StandardToolsService`，按家族名 + `ToolSandbox` 实例化为扁平 `IReadOnlyList<AIFunction>`，调用方直接挂到 `ChatClientAgentOptions.ChatOptions.Tools`。

**与父模块 `Tools/` 的分工**：

- 父模块只持 `ToolDescriptor` 抽象（家族名引用）。
- 本子模块提供具体家族注册表 + 实例化逻辑 + 沙盒约束。
- 父模块抽象稳定（API 几乎不变）；本子模块具体可扩（加家族即加一行 `Factories` 数组项）。

## 顶层迁移说明（本轮）

本子模块由 `AgentSystem/StandardTools/` **整体迁入** `Tools/Standard/`：

| 维度 | 上一轮 | 本轮 |
|------|--------|------|
| 物理路径 | `AgentSystem/StandardTools/` | `Tools/Standard/` |
| 命名空间 | `CBIM.AgentSystem.StandardTools` | `CBIM.Tools.Standard` |
| 父模块 | AgentSystem（能力维度） | Tools（顶层基础能力抽象） |
| 调用方 | 仅 AgentSystem.OpenInstance | AgentSystem.OpenInstance（合并 agent.SystemTools + module.Tools 后调） |

迁入后，业务侧 `ModuleDescription.Tools` 不再需要跨维度反向引用 `AgentSystem.StandardTools`——直接引用顶层 `CBIM.Tools.ToolDescriptor` + `CBIM.Tools.Standard.StandardToolsService` 即可。

## 家族注册表

硬编码 `IToolFamilyFactory[] Factories`：

```csharp
new IToolFamilyFactory[]
{
    new FilesFamilyFactory(),
    new SearchFamilyFactory(),
    // 未来：new WebFamilyFactory(), new BashFamilyFactory() ...
}
```

要加新家族：源码扩这张表。**不开放 IoC 插件点**——见父模块 `Tools/.dna/module.md` 铁律 2。理由：家族变更频率（季度级）低于代码 review 频率（PR 级），插件点反增维护成本。

## Files 家族

四只 AIFunction，全部沙盒守护（PathGuard）：

- `read_text`（按相对路径读，含二进制守门拒读图片 / 压缩包）
- `write_text`（仅写文本，含 max bytes 限制 + atomic write 经 FileBackend）
- `list_directory`（按相对路径列举，跳隐藏 + 限项数）
- `move_file` / `delete_file`（按相对路径移动 / 删除，仍受 PathGuard）

依赖 `FileBackend`（IO 抽象，来自 `CBIM.Storage`），调用方在 OpenInstance 时注入。

## Search 家族

关键词 + 模式匹配 + 简易语法。当前两只：

- `search_text`（按 query 在沙盒目录下 grep，限项数 + max bytes）
- `find_files`（按 glob 在沙盒下找文件路径）

不依赖 `FileBackend`——只用 `ToolSandbox` 路径 + `System.IO` 直读。

## ToolSandbox

来自父模块 `Tools/Standard/Sandbox/`，由调用方按 task 上下文构造：

```csharp
var sandbox = new ToolSandbox(
    projectRoot:  task.ProjectRoot,
    instanceRun:  task.InstanceRunDir,
    extraReads:   task.Where.SelectMany(m => m.ReadRoots));
```

Sandbox 内含 `PathGuard`，所有 family 工具方法第一步 `PathGuard.Resolve(relativePath)`——超出沙盒立即抛异常。

## Children

本子模块**无下级**（leaf）。物理目录结构：

```
Tools/Standard/
├── StandardToolsService.cs     ← 门面 + 家族注册表
├── Families/
│   ├── IToolFamilyFactory.cs   ← 家族工厂接口
│   ├── FilesToolFamily.cs      ← Files 家族实现
│   ├── SearchToolFamily.cs     ← Search 家族实现
│   └── BinaryDetector.cs       ← 共享：二进制守门
└── Sandbox/
    ├── ToolSandbox.cs          ← 沙盒数据 + 路径解析
    └── PathGuard.cs            ← 路径检查 + 越界抛异常
```

`Families/` 与 `Sandbox/` 是内部组织目录，不独立成模块（不创建 `.dna/`）——因为它们的稳定性 / 演化频率与本模块一致，没有独立模块边界的价值。

## Contract Surface

```csharp
namespace CBIM.Tools.Standard;

using Microsoft.Extensions.AI;
using CBIM.Storage;

public static class StandardToolsService
{
    static IReadOnlyList<string> ListFamilies();

    // 单家族实例化
    static IReadOnlyList<AIFunction> CreateFamily(
        string familyName,
        ToolSandbox sandbox,
        FileBackend storage = null);   // RequiresStorage 家族必传

    // 多家族实例化（去重 by AIFunction.Name）
    static IReadOnlyList<AIFunction> CreateFamilies(
        IEnumerable<string> familyNames,
        ToolSandbox sandbox,
        FileBackend storage = null);
}

public sealed class ToolSandbox
{
    string ProjectRoot { get; }
    string InstanceRunDir { get; }
    IReadOnlyList<string> ExtraReads { get; }

    PathGuard Guard { get; }
}

public static class PathGuard
{
    static string Resolve(ToolSandbox sandbox, string relativePath);  // 越界抛 IOException
}
```

所有方法同步、无可变静态状态——可在任意线程并发调用。

## Dependencies

- `Microsoft.Extensions.AI`——`AIFunction` / `AIFunctionFactory` / `[Description]` attribute。
- `CBIM.Storage`——`FileBackend`（Files 家族用）。
- `CBIM.Tools`（父模块）——`ToolDescriptor` 类型（调用侧通过它取 FamilyName 传给 CreateFamilies）。
- **不依赖** `AgentSystem` / `Workspace` / `Skills` / `Mcp`——本子模块对 CBIM 其他模块只读不写。

依赖单向：调用方（OpenInstance 等）→ Tools/Standard → Microsoft.Extensions.AI + Storage。

## 铁律

1. **无可变静态状态**——任意线程并发 safe。任何加 family-level 缓存的尝试请先审计。
2. **家族表硬编码，不开放插件点**——父模块铁律 2 重申。
3. **PathGuard 越界必抛异常**——绝不静默修正路径。任何 family 工具方法第一行：`var p = PathGuard.Resolve(sandbox, relativePath);`
4. **同名 AIFunction 取首出**——`CreateFamilies` 在合并时按 `AIFunction.Name` 去重，第一家族优先（FilesFamily.read_text 优先于后续家族的同名）。冲突时 Debug.WriteLine 警告。
5. **空家族名静默跳过**——`CreateFamilies` 不抛异常；未知家族名经 try/catch 转为 Debug 警告（保证 agent 装配不被 typo 阻塞）。
6. **不感知 agent / module 概念**——本模块只看 `FamilyName + ToolSandbox + FileBackend`。

## Origin Context

- **第一阶段**（CBIM v2 早期）：完全无 IO 工具——LLM 拿不到文件 / 搜索能力。
- **第二阶段**（Workspace 子模块）：误设计为 `Workspace/StandardTools/` —— 当时认为「这个 module 上需要读文件」，故工具挂在 module 上。维度错位。
- **第三阶段**（迁入 AgentSystem）：纠正——工具是 agent 的能力构成，不是 module 的业务属性。迁到 `AgentSystem/StandardTools/`，namespace `CBIM.AgentSystem.StandardTools`。
- **第四阶段**（本轮 · 顶层化）：再迁——发现业务侧也需要 `Tools` 抽象（`ModuleDescription.Tools` 是「业务专属内置工具家族」，与 Agent.SystemTools 同抽象）。能力侧 / 业务侧同时引用同一个 `Tools` 抽象时，再嵌在 `AgentSystem/` 下会引入跨维度反向引用——故提为顶层。

第四阶段的关键洞察：**「跨维度共享抽象」的物理位置不是「先有它的某个维度」，而是「两个维度对它的共同前置」**。Tool / Skill / Mcp 三者本质都是「LLM 可调能力的描述抽象」——这是两个维度的共同前置概念，不属于任何单一维度。

## Emergent Insights

1. **「Standard」既是命名也是承诺**——`Tools/Standard/` 是 CBIM 官方背书的家族集；后续如有 `Tools/Custom/` 或 `Tools/Project/` 等，明确区分「CBIM 官方提供」与「项目本地扩展」。当前只有 Standard。
2. **「无 IoC」是有意为之**——家族变更频率低（季度级）、调用方明确（OpenInstance 唯一）、单测可直接 mock factory 数组。引入 IoC 反而拉低可读性。
3. **「沙盒外置」让本模块完全可移植**——`StandardToolsService` 不感知 Unity / .NET 主机环境，只看 `ToolSandbox` 数据 + `FileBackend` 接口。可被 Python 侧 / 独立 CLI 直接复用（如果未来需要）。

## Non-Goals

- **不实现 Web / Bash 等额外家族**——Web 等 Microsoft.Extensions.AI 社区包逐步补齐；Bash 因 Shell 安全模型未定本轮不发。
- **不写远程工具调用**——远程工具是 MCP 的范畴，归 `Mcp/` 子模块。
- **不持工具调用历史**——历史记录归 `AgentSystem.Session` 写侧。
- **不实现工具搜索 / 推荐**——LLM 自己读 AIFunction 描述来决定调用。

