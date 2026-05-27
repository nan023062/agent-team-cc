---
name: cbim-unity-standard-tools
owner: architect
description: CBIM 内置通用能力工具集（C 维度子模块）：Files / Search / Web / Bash 工具家族，以 Microsoft.Extensions.AI AIFunction 形态实现，按 AgentDescription.tools 声明、OpenInstance 装配时按 per-agent 沙盒注入。归属能力维度——工具属于 agent 的能力构成，不属于业务 module。
keywords: []
dependencies: []
status: spec
---

## Positioning

**CBIM 内置通用能力工具集**——AgentSystem 子模块（C 维度）。补 Microsoft.Agents.AI.Tools 当前几乎缺位（仅 `Tools.Shell` 且 net8-only，Unity 不可用）的空白，为 CBIM 的「专业级编程 agent」提供基础的文件 / 搜索 / 网页 / Shell 能力。

本模块**不是全局工具栏**——每个 AgentDescription 在 frontmatter 显式声明自己装配哪些工具家族，OpenInstance 装配 AIAgent 时按 per-agent 沙盒注入。

## 维度归属（重要）

本模块**属于能力维度（C）**，挂在 `AgentSystem/` 下而非 `Workspace/` 下。理由：

- 工具是 **agent 的能力构成要素**——「能不能读文件 / 能不能联网」是 agent 是谁的一部分，与「该 agent 擅长什么」并列。
- 工具不是**业务 module 的属性**——module 描述的是「业务工作流程 + 领域知识」，不描述「拿什么工具做」。
- 装配链路：`Task.Who（agent）→ AgentDescription.tools → StandardToolsService.CreateFamilies → AIFunction 列表`。
- 与上一轮设计的差别：原把 `standard_tools` 放在 `ModuleDescription`，错。本轮迁回 `AgentDescription`——见 AgentSystem `.dna/module.md`「维度归属修正」一节。

### 工具来源分类（能力维度内三并列）

本模块是 CBIM 能力维度内工具来源三并列中的一个。三个来源同维度、同装配点（OpenInstance）、同生命周期（绑 AIAgent 实例），仅底层调用形态不同：

| 类型 | 形态 | 实现位置 | AgentDescription 声明字段 |
|------|------|---------|------------------------|
| **StandardTools（本模块）** | CBIM 内置纯 C# AIFunction（进程内，无子进程、无 IPC） | `StandardTools/`（本模块） | `tools: [Files, Search]` |
| **CLI 包装** | subprocess + stdin/stdout（fork 子进程） | 未来 Bash 家族 + `agent_extension_clis` 白名单 | `agent_extension_clis: [git]` |
| **MCP server** | MCP 协议 + IPC（独立长连接进程） | `AgentSystem/McpAdapter/` 子模块 | `mcp_servers: [unity-mcp]` |

**本模块的独特位置**：

- 与 CLI / MCP 并列，但**不接 MCP 协议、不开子进程、不走 IPC**——纯 C# 内嵌。
- 在三类中启动成本最低、生命周期最简单（随 AIAgent GC，无需显式释放）。
- 是「不依赖外部进程」场景的唯一选择（例：几乎所有 agent 都需要的 Files / Search）。
- **不朒越三者边界**——本模块不包装 CLI（那是 Bash 家族 + `agent_extension_clis` 的事），不接 MCP（那是 `McpAdapter/` 的事）。

**装配口径统一**：三源都由 OpenInstance 内部调用 → 拼接 → 传给 `AIAgentBuilder.Tools`。本模块不感知另两类，另两类也不感知本模块（C3 单向依赖，C4 接口隔离）。

## Responsibility（一句话）

按「工具家族」组织一组 `Microsoft.Extensions.AI.AIFunction` 实现，每族提供一个工厂方法 `Create(sandbox)` 返回该族的 AIFunction 列表；OpenInstance 收集 agent 声明的家族名 → 实例化 → 合并去重 → 注入 `OpenInstanceOptions.Tools`。

## 工具家族（首批）

| 家族名 | 工具 | 沙盒策略 | 备注 |
|--------|------|---------|------|
| **Files** | `ReadFile` / `WriteFile` / `EditFile` / `DeleteFile` / `ListDirectory` | allowed path prefix 白名单 | 默认 UTF-8，二进制文件返回元信息；大文件按行截断（默认 2000 行）|
| **Search** | `Grep`（ripgrep 风格正则）/ `Glob`（FileSystemGlobbing）| 同 Files 白名单 | Glob 走 `Microsoft.Extensions.FileSystemGlobbing`；Grep 走纯 C# 正则（不调外部进程）|
| **Web** | `WebFetch`（URL → HTML/markdown）/ `WebSearch`（关键词 → 摘要列表）| URL 黑/白名单可选 | **默认关闭**——agent 显式声明才挂；超时 / 大小硬上限 |
| **Bash**（可选）| `Bash` | sandbox 工作目录 + 命令白名单 | **暂搁置**——待 `Microsoft.Agents.AI.Tools.Shell` 在 Unity 6 支持的 .NET 版本可用时切过去，不重造 |

首批切片仅交付 **Files + Search**；Web 列入第二轮；Bash 第三轮（且优先评估 Microsoft 包是否可用）。

## 设计要点

### 1. AIFunction 形态

每个工具是带 `[Description]` 的 C# 方法，由 `AIFunctionFactory.Create(...)` 包成 `AIFunction`。例如：

```csharp
public sealed class FilesToolFamily
{
    public FilesToolFamily(ToolSandbox sandbox) { _sandbox = sandbox; }

    [Description("Read a UTF-8 text file. Returns up to maxLines lines (default 2000). Binary files return file metadata only.")]
    public string ReadFile(
        [Description("Absolute or sandbox-relative file path.")] string path,
        [Description("Max lines to return. 0 = no limit (capped at 10000).")] int maxLines = 2000,
        [Description("Starting line offset (1-based).")] int offset = 1) { /* ... */ }

    public IReadOnlyList<AIFunction> Build() => new[] {
        AIFunctionFactory.Create(ReadFile),
        AIFunctionFactory.Create(WriteFile),
        // ...
    };
}
```

### 2. 沙盒（ToolSandbox）

所有家族构造时注入 `ToolSandbox`——值对象，包含：

- `AllowedPathPrefixes`：绝对路径前缀白名单；任何工具的 path 参数必须以其中之一为前缀（规范化后），否则抛 `UnauthorizedAccessException`。
- `WorkingDirectory`：相对路径解析基点。
- `MaxFileBytes` / `MaxResultBytes`：单文件读取 / 结果返回硬上限（防 LLM 拉爆 context）。
- `BlockedExtensions`：禁写后缀（如 `.dll`、`.exe`）。
- `WebAllowedHosts`（Web 专用）：URL 域名白名单。

OpenInstance 装配时为每个 agent 构造一份 `ToolSandbox`——基点默认是项目根 + 该 agent 实例在 Unity persistentDataPath 下的工作目录（前者由调用方传入，后者由 Storage 模块决定）。**沙盒粒度 = agent 实例粒度**（不再是 module 粒度）——agent 的工具权限边界自描述。

### 3. 错误处理

- 工具方法不抛裸 `Exception` 给 LLM——内部 try/catch，返回结构化错误字符串（`ERROR: <kind>: <message>`），LLM 才能据此自我纠正。
- 唯一例外：沙盒越界等安全错误抛 `UnauthorizedAccessException`，由 `FunctionInvokingChatClient` 上报、流程中止。

### 4. 大文件 / 二进制 / 并发

- 读：先 `FileInfo.Length` 检查，超 `MaxFileBytes` 直接返回截断说明；二进制检测（前 8KB 中 NUL 字节比例 > 1%）→ 返回 `{path, sizeBytes, isBinary:true}` JSON。
- 写：原子写——复用 `CBIM.Storage` 的原子写原语，不重造。
- 并发：工具方法可重入；不持有跨调用状态（沙盒是只读值对象）。

## Contract Surface

```csharp
namespace CBIM.AgentSystem.StandardTools;

using Microsoft.Extensions.AI;

public sealed class StandardToolsService
{
    public StandardToolsService(IStorageRoot storageRoot);

    /// <summary>已知工具家族名集合（Files / Search / Web / Bash ...）。</summary>
    IReadOnlyList<string> ListFamilies();

    /// <summary>按家族名 + 沙盒构造该族的 AIFunction 列表；未知家族名抛 ArgumentException。</summary>
    IReadOnlyList<AIFunction> CreateFamily(string familyName, ToolSandbox sandbox);

    /// <summary>给定一组家族名 + 沙盒，返回合并去重的 AIFunction 列表（同名工具按首个家族赢，记 warning）。</summary>
    IReadOnlyList<AIFunction> CreateFamilies(IReadOnlyList<string> familyNames, ToolSandbox sandbox);
}

public sealed record ToolSandbox(
    IReadOnlyList<string> AllowedPathPrefixes,
    string WorkingDirectory,
    long MaxFileBytes = 10 * 1024 * 1024,
    long MaxResultBytes = 256 * 1024,
    IReadOnlyList<string>? BlockedExtensions = null,
    IReadOnlyList<string>? WebAllowedHosts = null);
```

## Dependencies

- `Microsoft.Extensions.AI`——`AIFunction` / `AIFunctionFactory`。
- `Microsoft.Extensions.FileSystemGlobbing`——Glob 实现（已在 ThirdParty）。
- `CBIM.Storage`——原子写、JSON 序列化、root 路径解析。
- **不依赖** AgentSystem 父服务 / Kernel / Memory / Workspace——纯被调侧。

## 与 AgentDescription / OpenInstance 的协议

本模块**不主动装配**——是被调侧。装配协议：

1. `AgentDescription` frontmatter 持有 `tools: [Files, Search]` 字段（schema 演进归 AgentSystem 父模块）。
2. `AgentSystem.OpenInstance(descriptionName, options)` 装配时：
   - 读 `AgentDescription.Tools` 拿家族名列表。
   - 为该 agent 构造一份 `ToolSandbox`（path prefix = 项目根 + agent 实例在 persistentDataPath 下的工作目录）。
   - 调 `StandardToolsService.CreateFamilies(familyNames, sandbox)` → AIFunction 列表。
   - 与 `options.Tools`（调用方额外传入的外插工具）拼接后传给 `AIAgentBuilder`。
3. AgentSystem 不感知工具内容——只是把列表透传给 `AIAgentBuilder`。

**装配点的归属**：CBIM 的「能力构成 → AIAgent」装配胶水唯一入口是 `AgentSystem.OpenInstance`，因此「按 agent 收集 tools → 构造沙盒 → 调 StandardToolsService」的责任落在 `AgentSystem.OpenInstance` 内部。CbimTaskExecutor 仅在调 OpenInstance 时把 `task.Who` 透传，不直接操作 StandardToolsService。

## 铁律

1. **不发明全局工具开关**——一切按 agent 声明，无环境变量 / 全局配置项。
2. **沙盒是构造期注入**——工具实例与沙盒一对一，不允许工具运行时切换沙盒。
3. **不调外部进程**（首批）——Bash 待 Microsoft 包可用再切，期间不允许内联 `System.Diagnostics.Process` 黑魔法。
4. **AIFunction 描述用英文**——LLM tool-calling 上下文成本最低；中文 Description 留给本文档与外层 AgentDescription。
5. **错误结构化**——工具不抛裸异常给 LLM，统一 `ERROR: <kind>: <msg>` 字符串。
6. **二进制 / 大文件 / 越界三条硬上限**——任何家族实现都必须先过这三道闸。
7. **不与 AgentSystem 父服务双向耦合**——本模块仅依赖 Storage；AgentSystem 父在 AgentDescription schema 中暴露 `tools` 字段读侧即可。

## Origin Context

上一轮顶层重构裁决「不造 IO 工具轮子」——前提是 Microsoft 生态会接管。随后发现 Microsoft.Agents.AI.Tools 当前几乎缺位（唯一 `Tools.Shell` 且 net8-only，Unity 不可用），CBIM 的「专业级编程 agent」（架构师、HR、auditor 等）失去最基本的文件 / 搜索能力——于是新增 StandardTools 子模块。

上一轮把本模块挂在 `Workspace/` 下、把 `standard_tools` 字段挂在 `ModuleDescription`——**错**。工具属于能力维度（agent 的能力构成），不属于业务维度（module 的工作流程 / 领域知识）。本轮裁决修正：

- 本模块物理位置：`Workspace/StandardTools/` → `AgentSystem/StandardTools/`。
- schema 字段：`ModuleDescription.standard_tools` 删除；`AgentDescription.tools` 新增。
- 装配链路：`Task.Where → 每 module 的 standard_tools` → `Task.Who → AgentDescription.tools`。
- 沙盒粒度：per-module → per-agent。
- 「动态注入」性质：从「按 module 动态」改为「通过 Task 选 agent 间接动态」——工具仍然不是全局，只是动态的发起点变了。

严守三条边界不变：

1. 形态对齐 Microsoft（`AIFunction` + `AIFunctionFactory`），不发明 CBIM 私有工具接口；
2. 按 agent 沙盒声明式挂载，不做全局工具栏；
3. Microsoft 包补齐后随时下沉（Bash / Shell 第一优先）。

## Non-Goals

- 不实现 Bash（首批）——等 Microsoft `Tools.Shell` 在 Unity 6 可用的 .NET 版本就绪后切过去。
- 不实现 WebSearch（首批）——需引擎接入决策，纳入第二轮。
- 不实现 MCP client 工具适配——若需挂第三方 MCP 工具，是 AgentSystem 装配层的事（`agent_extension_clis` schema 字段），不在本模块。
- 不实现工具调用日志——`FunctionInvokingChatClient` + AgentSession 已记录 ToolInvocation 事件。
- 不发明工具权限模型——沙盒之外的权限（如 RBAC）不属于本模块。

## Implementation Order

1. `ToolSandbox` 值对象 + 路径规范化 / 越界检测辅助。
2. `FilesToolFamily`——5 工具 + 二进制检测 + 截断 + 原子写。
3. `SearchToolFamily`——Grep（C# Regex 遍历）+ Glob（FileSystemGlobbing）。
4. `StandardToolsService` 门面——`ListFamilies` / `CreateFamily` / `CreateFamilies`。
5. AgentSystem 端补 OpenInstance 装配胶水（在 AgentSystem .dna 中描述）。
6. （后续）Web 家族；（更后）Bash 评估。

## Mermaid

```mermaid
flowchart TD
    AD["AgentDescription<br/>tools: [Files, Search]<br/>agent_extension_clis: [git, ...]"]
    AS["AgentSystem（父模块）<br/>暴露 schema 读侧"]
    ST["StandardToolsService<br/>(本模块)"]
    SB["ToolSandbox<br/>(per-agent 构造)"]
    FF["FilesToolFamily"]
    SF["SearchToolFamily"]
    WF["WebToolFamily<br/>(第二轮)"]
    BF["BashToolFamily<br/>(第三轮 / 等 MSAI Shell)"]
    OI["AgentSystem.OpenInstance"]
    MSAI["Microsoft.Extensions.AI<br/>AIFunction"]

    AD --> AS
    AS -. 读 AgentDescription.tools .-> OI
    OI -. 按 agent 构造 .-> SB
    OI -. CreateFamilies(names, sandbox) .-> ST
    ST --> FF
    ST --> SF
    ST -.-> WF
    ST -.-> BF
    FF -.AIFunctionFactory.-> MSAI
    SF -.AIFunctionFactory.-> MSAI
    OI -. Tools= .-> MSAI

    classDef future fill:#f5f5f5,stroke-dasharray: 4 4;
    class WF,BF future;
```

