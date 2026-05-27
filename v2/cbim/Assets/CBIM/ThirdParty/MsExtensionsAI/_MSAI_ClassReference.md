# Microsoft Agent Framework — 类参考手册（C#）

逐类说明文档。架构图见 [`MSAI_Architecture.md`](./MSAI_Architecture.md)。

格式约定：
- **职责**：一句话
- **关键方法 / 属性**：只列 public 核心
- **扩展点**：子类化 / 装饰器 / 直接 new / Builder
- **CBIM 用法**：在 CBIM 中怎么用（如果适用）

---

## Agent 层（Microsoft.Agents.AI）

### `AIAgent`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `abstract class` |
| 程序集 | `Microsoft.Agents.AI.Abstractions` |

**职责**：所有 AI agent 的根抽象类。定义 `RunAsync` / `RunStreamingAsync` / `CreateSessionAsync` / 序列化 session 等核心契约。

**关键方法**：
```csharp
Task<AgentResponse> RunAsync(
    IEnumerable<ChatMessage>? messages = null,
    AgentSession? session = null,
    AgentRunOptions? options = null,
    CancellationToken cancellationToken = default);

IAsyncEnumerable<AgentResponseUpdate> RunStreamingAsync(
    IEnumerable<ChatMessage>? messages = null,
    AgentSession? session = null,
    AgentRunOptions? options = null,
    CancellationToken cancellationToken = default);

Task<AgentSession> CreateSessionAsync(CancellationToken ct = default);
Task<JsonElement> SerializeSessionAsync(AgentSession session, CancellationToken ct = default);
Task<AgentSession> DeserializeSessionAsync(JsonElement json, CancellationToken ct = default);
```

**关键属性**：
- `Id : string` — 实例唯一 ID
- `Name : string?` — 人类可读名
- `Description : string?` — 描述
- `CurrentRunContext : AgentRunContext?` — AsyncLocal 当前调用上下文

**扩展点**：子类化（少见）或更常见的——直接用 `ChatClientAgent`。中间件场景子类化 `DelegatingAIAgent`。

**CBIM 用法**：CBIM 不子类化 AIAgent，而是通过 `IChatClient.AsAIAgent(ChatClientAgentOptions)` 工厂得到 `ChatClientAgent` 实例。

---

### `AgentRunOptions`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `class`（可继承） |
| 程序集 | `Microsoft.Agents.AI.Abstractions` |

**职责**：每次 `RunAsync` / `RunStreamingAsync` 调用的**运行时选项**——区别于 `ChatClientAgentOptions`（agent 构造期一次性配置），这个是按调用变化的参数。

**关键方法**：
```csharp
public virtual AgentRunOptions Clone();  // 浅克隆（含 AdditionalProperties）
```

**关键属性**：
- `ContinuationToken : ResponseContinuationToken?` — 后台响应续行令牌（长任务恢复 / 轮询）
- `AllowBackgroundResponses : bool?` — 允许异步后台响应（OpenAI Responses API 特性）
- `ResponseFormat : ChatResponseFormat?` — 强制响应格式（Text / JSON / JsonSchema）
- `AdditionalProperties : AdditionalPropertiesDictionary?` — provider-specific 透传

**与 `ChatClientAgentOptions` 的关系**：
- `ChatClientAgentOptions` — agent 一次性配置（Instructions / Tools / Providers）
- `ChatOptions`（在 ChatClientAgentOptions 里）— LLM 调用层选项（Temperature / MaxTokens / ToolMode）
- `AgentRunOptions` — 每次调用的运行时控制（续行令牌 / 后台模式 / 响应格式）

**不能设的字段**：Instructions、Tools、ContextProviders — 这些只在 `ChatClientAgentOptions` 里。

**扩展点**：子类化（AIAgent 实现可定义自己的 AgentRunOptions 子类透传 provider 专属选项）。

**CBIM 用法**：默认 `null` 即可。需要 OpenAI Responses API 的后台模式时填 `AllowBackgroundResponses = true`。

---

### `AgentRunContext`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `sealed class` |
| 程序集 | `Microsoft.Agents.AI.Abstractions` |

**职责**：agent 运行**中**的只读上下文快照。通过 `AIAgent.CurrentRunContext`（AsyncLocal）拿到。给中间件 / 工具 / Provider 内部访问当前调用信息。

**关键属性**：
- `Agent : AIAgent` — 当前执行的 agent 实例
- `Session : AgentSession?` — 关联 session（可空）
- `RequestMessages : IReadOnlyCollection<ChatMessage>` — 本次输入消息
- `RunOptions : AgentRunOptions?` — 传入的运行选项

**扩展点**：不可继承（sealed），只读。

**CBIM 用法**：CBIM Provider 内部需要拿"当前是哪个 task / 哪个 agent"时可读取，避免显式构造时传参。

---

### `ChatClientAgent`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `sealed class` |
| 继承 | `AIAgent` |
| 程序集 | `Microsoft.Agents.AI` |

**职责**：通过 `IChatClient` 委托聊天能力的主力 Agent 实现。承载工具列表、context providers、history provider 的装配。

**关键属性**：
- `ChatClient : IChatClient` — 底层调用入口
- `ChatHistoryProvider : ChatHistoryProvider` — 历史管理器
- `AIContextProviders : IReadOnlyList<AIContextProvider>` — provider 链

**扩展点**：不应子类化，sealed。配置走 `ChatClientAgentOptions`。

**CBIM 用法**：所有 CBIM agent 实例本质都是 `ChatClientAgent`。CBIM 不直接 `new ChatClientAgent`，而是 `chatClient.AsAIAgent(opts)`。

---

### `ChatClientAgentOptions`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `class` |
| 程序集 | `Microsoft.Agents.AI` |

**职责**：`ChatClientAgent` 的所有配置项容器。

**关键属性**：
- `Id : string?` — 显式指定 agent ID
- `Name : string?` — agent 名
- `Description : string?` — 描述
- `Instructions : string?` — 系统提示词（人设）
- `ChatOptions : ChatOptions?` — 底层 chat 选项（模型、温度、工具）
- `ChatHistoryProvider : ChatHistoryProvider?` — 自定义历史后端
- `AIContextProviders : IList<AIContextProvider>?` — provider 列表

**扩展点**：直接 `new` 后填字段。

**CBIM 用法**：
```csharp
var opts = new ChatClientAgentOptions
{
    Name = agentDesc.Name,
    Description = agentDesc.Description,
    Instructions = agentDesc.Instructions,
    ChatOptions = new ChatOptions { Tools = systemTools.AsAIFunctions() },
    AIContextProviders = new[]
    {
        new WorkspaceContextProvider(workspaceService, currentTask),
        new MemoryContextProvider(memoryService, currentTask),
        new SessionContextProvider(agentSystem, currentTask),
    },
};
AIAgent agent = chatClient.AsAIAgent(opts);
```

---

### `DelegatingAIAgent`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `abstract class` |
| 继承 | `AIAgent` |
| 程序集 | `Microsoft.Agents.AI.Abstractions` |

**职责**：装饰器基类，通过持有 `InnerAgent` 透传调用，允许在前后插桩。

**关键属性**：
- `InnerAgent : AIAgent` — 被装饰的 agent

**扩展点**：子类化，覆写 `RunCoreAsync` / `RunCoreStreamingAsync`，在调用前后做事。

**CBIM 用法**：可子类化做 "每次 RunAsync 前后写 Session 日志" 中间件。

```csharp
class SessionLoggingAgent : DelegatingAIAgent
{
    public SessionLoggingAgent(AIAgent inner) : base(inner) { }
    protected override async Task<AgentResponse> RunCoreAsync(...)
    {
        sessionWriter.AppendEvent("call_start", ...);
        var resp = await base.RunCoreAsync(...);
        sessionWriter.AppendEvent("call_end", resp.Text);
        return resp;
    }
}
```

---

### `AnonymousDelegatingAIAgent`

| namespace | `Microsoft.Agents.AI` |
|---|---|
| 修饰 | `sealed class` |
| 继承 | `DelegatingAIAgent` |

**职责**：用 delegate 函数代替子类化，做一次性 / 内联中间件。

**用法**：
```csharp
var wrapped = new AnonymousDelegatingAIAgent(
    inner,
    runFunc: async (messages, session, opts, next, ct) =>
    {
        // pre
        var resp = await next(messages, session, opts, ct);
        // post
        return resp;
    });
```

---

### `LoggingAgent`

| 修饰 | `sealed class` |
|---|---|
| 继承 | `DelegatingAIAgent` |

**职责**：把每次 RunAsync 调用写到 `ILogger`。

**关键属性**：
- `JsonSerializerOptions : JsonSerializerOptions` — 日志序列化配置

---

### `OpenTelemetryAgent`

| 修饰 | `sealed class` |
|---|---|
| 继承 | `DelegatingAIAgent`，实现 `IDisposable` |

**职责**：按 OpenTelemetry GenAI semantic conventions 给 agent 调用打追踪 / metrics。

---

### `FunctionInvocationDelegatingAgent`

| 修饰 | `sealed internal class` |
|---|---|
| 继承 | `DelegatingAIAgent` |

**职责**：把工具调用循环封装到 agent 侧。`ChatClientAgent` 检测到 `tools` 非空时自动插入这一层，调用方不必手工 `.AsBuilder().UseFunctionInvocation()`。

---

### `AIAgentBuilder`

| 修饰 | `sealed class` |
|---|---|
| 程序集 | `Microsoft.Agents.AI` |

**职责**：装饰器链组装（agent 级 middleware）。

**关键方法**：
```csharp
AIAgentBuilder Use(Func<AIAgent, IServiceProvider, AIAgent> factory);
AIAgentBuilder UseAIContextProviders(params AIContextProvider[] providers);
AIAgent Build(IServiceProvider? services = null);
```

**用法**：
```csharp
var agent = new AIAgentBuilder(innerAgent)
    .Use((inner, sp) => new LoggingAgent(inner, logger))
    .Use((inner, sp) => new OpenTelemetryAgent(inner))
    .Build();
```

---

### `AgentSession`

| 修饰 | `abstract class` |
|---|---|

**职责**：单次对话的状态容器。承载消息历史、provider state、tool state 等。可序列化为 `JsonElement` 供持久化。

**关键属性**：
- `StateBag : AgentSessionStateBag` — 任意 KV 字典，支持序列化

**关键方法**：
- `GetService<T>() : T?` — 取服务

**CBIM 用法**：CBIM Channel 持有一个 `AgentSession`。多轮对话用同一 session 维持上下文。

---

### `AgentSessionStateBag`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `class`（可继承） |
| 程序集 | `Microsoft.Agents.AI.Abstractions` |

**职责**：**线程安全**的 session 级 KV 存储，所有值可 JSON 序列化反序列化。`AgentSession.StateBag` 就是它。

**关键方法**：
```csharp
bool TryGetValue<T>(string key, out T? value, JsonSerializerOptions? opts = null) where T : class;
T?   GetValue<T>(string key, JsonSerializerOptions? opts = null) where T : class;
void SetValue<T>(string key, T? value, JsonSerializerOptions? opts = null) where T : class;
bool TryRemoveValue(string key);

JsonElement                Serialize();
static AgentSessionStateBag Deserialize(JsonElement json);
```

**关键属性**：
- `Count : int` — 当前 KV 对数

**Provider 存储自己 state 的标准模式**：
```csharp
class MyProvider : AIContextProvider
{
    private const string MyStateKey = "MyProvider.cursor";
    
    public override IReadOnlyList<string> StateKeys { get; } = new[] { MyStateKey };

    protected override ValueTask<AIContext> ProvideAIContextAsync(InvokingContext ctx, ...)
    {
        var session = ctx.Session;
        var cursor = session.StateBag.GetValue<MyCursorState>(MyStateKey) ?? new();
        // 用 cursor 拉数据...
        cursor.LastReadId = newId;
        session.StateBag.SetValue(MyStateKey, cursor);
        return new ValueTask<AIContext>(new AIContext { ... });
    }
}
```

**可存什么**：任意 JSON-serializable 类型（普通 C# 类 / record / 字典 / 数组 / 标量 / null）。内部用懒缓存——`GetValue<T>` 第一次反序列化后缓存对象，之后重复 Get 直接拿缓存（除非 SetValue 覆盖）。

**`StateKeys` 协议**：Provider 应在 `StateKeys` 属性里声明自己用的 key，方便 session 序列化时知道这些 key 归哪个 provider 管。

**CBIM 用法**：
- WorkspaceContextProvider：存"当前 task 的模块列表 hash"，下次调用如果 hash 变就重新拉
- MemoryContextProvider：存"上次检索的 query embedding"避免重复嵌入
- SessionContextProvider：存"上次读到的 SessionEvent 索引"避免重复读取

---

### `AgentResponse`

| 修饰 | `class` |
|---|---|

**职责**：一次 `RunAsync` 调用的返回结果。

**关键属性**：
- `Messages : IList<ChatMessage>` — 完整返回消息列表（含 tool call、tool result、文本等）
- `Text : string` — 所有 `TextContent` 拼接（最常用）
- `FinishReason : ChatFinishReason?` — `Stop` / `Length` / `ToolCalls` / `ContentFilter`
- `Usage : UsageDetails?` — token 消耗
- `AgentId : string?` / `CreatedAt : DateTimeOffset?` / `RawRepresentation : object?`

**关键方法**：
- `ToAgentResponseUpdates() : AgentResponseUpdate[]` — 拆成流式片段

---

### `AgentResponseUpdate`

| 修饰 | `class` |
|---|---|

**职责**：流式调用的单个增量片段。`RunStreamingAsync` 产出 `IAsyncEnumerable<AgentResponseUpdate>`。

**关键属性**：
- `Role : ChatRole?`
- `AuthorName : string?`
- `Contents : IList<AIContent>` — 此片段的内容
- `Text : string` — 文本聚合
- `FinishReason : ChatFinishReason?` — 末片段才有

---

### `AIContextProvider`

| 修饰 | `abstract class` |
|---|---|

**职责**：在 agent 调用生命周期中**注入额外上下文**（指令 / 消息 / 工具）+ **存储调用结果**。CBIM 的核心扩展点。

**关键方法**：
```csharp
public virtual ValueTask<AIContext> InvokingAsync(InvokingContext ctx, CancellationToken ct = default);
public virtual ValueTask InvokedAsync(InvokedContext ctx, CancellationToken ct = default);

protected abstract ValueTask<AIContext> ProvideAIContextAsync(InvokingContext ctx, CancellationToken ct);
protected virtual ValueTask StoreAIContextAsync(InvokedContext ctx, CancellationToken ct);
```

**关键属性**：
- `StateKeys : IReadOnlyList<string>` — 此 provider 在 AgentSessionStateBag 里用的 key

**扩展点**：子类化覆写 `ProvideAIContextAsync` / `StoreAIContextAsync`。

**CBIM 用法**：CBIM 三个 Provider 都子类化此类：
- `WorkspaceContextProvider`
- `MemoryContextProvider`
- `SessionContextProvider`

```csharp
class WorkspaceContextProvider : AIContextProvider
{
    protected override ValueTask<AIContext> ProvideAIContextAsync(
        InvokingContext ctx, CancellationToken ct)
    {
        var modules = workspace.GetDescriptions(task.Where);
        return new ValueTask<AIContext>(new AIContext
        {
            Instructions = "当前任务作用域模块：\n" +
                string.Join("\n", modules.Select(m => $"- {m.Path}: {m.Description}")),
        });
    }
}
```

---

### `AIContext`

| 修饰 | `sealed class` |
|---|---|

**职责**：`AIContextProvider` 调用前注入的 payload。可注入指令 / 消息 / 工具，三者均可空。

**关键属性**：
- `Instructions : string?` — 临时加的系统提示
- `Messages : IEnumerable<ChatMessage>?` — 临时加的对话上下文
- `Tools : IEnumerable<AITool>?` — 临时加的工具

---

### `InvokingContext` / `InvokedContext`

`AIContextProvider` 方法的入参。`InvokingContext` 含本次调用的 messages，`InvokedContext` 还含 LLM 返回的 response。

> ⚠️ `InvokingContext` 构造标了 `[Experimental(MAAI001)]`。继承 `AIContextProvider` 不需要构造它，只是消费——无须警告抑制。

---

### `ChatHistoryProvider`

| 修饰 | `abstract class` |
|---|---|

**职责**：管理对话历史的检索 / 存储。比 `AIContextProvider` 更专门——专管 message 序列的持久化与压缩。

**关键方法**：
```csharp
public virtual ValueTask<...> InvokingAsync(...);
public virtual ValueTask InvokedAsync(...);
protected abstract ValueTask<...> ProvideChatHistoryAsync(...);
protected abstract ValueTask StoreChatHistoryAsync(...);
```

**扩展点**：子类化绑定具体后端。MSAI 自带 `InMemoryChatHistoryProvider`。

**CBIM 用法**：CBIM Memory 可子类化此类，把对话历史存到 `.cbim/memory/medium/` 实现跨 session 持久化。

---

### `InMemoryChatHistoryProvider`

| 修饰 | `sealed class` |
|---|---|
| 继承 | `ChatHistoryProvider` |

**职责**：内存存储，session 销毁即丢失。开箱即用，适合短对话或测试。

---

### `AgentSkill`

| 修饰 | `abstract class` |
|---|---|

**职责**：表示一个领域能力（SKILL.md 形态）：含 frontmatter + instructions + resources + scripts。

**关键方法**：
- `GetContentAsync() : Task<string>` — 拿完整内容
- `GetResourceAsync(name) : Task<...>` — 按名拿资源
- `GetScriptAsync(name) : Task<...>` — 按名拿脚本

**关键属性**：
- `Frontmatter : AgentSkillFrontmatter` — name / description / license 等

**CBIM 关系**：CBIM 的 skill 概念跟 MSAI 的 AgentSkill 完全同形态。可以子类化把 `.claude/agents/<agent>/skills/<skill>.md` 映射进来。

**Skill 三类资产**：
- 主体：`GetContentAsync()` → 返回完整 SKILL.md 内容
- 资源：`GetResourceAsync(name)` → 返回 `AgentSkillResource?`（参考文档 / 静态数据）
- 脚本：`GetScriptAsync(name)` → 返回 `AgentSkillScript?`（可执行脚本）

子类已有：`AgentFileSkill`（从文件系统加载 .md）、`AgentInlineSkill`（内存定义）、`AgentClassSkill<TSelf>`（C# 类定义）。

---

### `AgentSkillFrontmatter`

| 修饰 | `sealed class` |
|---|---|

**职责**：SKILL.md 的 YAML frontmatter 解析 + 校验。L1 发现层元数据。

**关键属性**：
- `Name : string` — kebab-case，≤ 64 字符
- `Description : string` — ≤ 1024 字符
- `License : string?` / `Compatibility : string?` — 可选
- `AllowedTools : string?` — 空格分隔的预批工具列表
- `Metadata : AdditionalPropertiesDictionary?` — 任意扩展字段

**校验静态方法**：`ValidateName` / `ValidateDescription` / `ValidateCompatibility` — 都返回 `bool` + `out string? reason`。

---

### `AgentSkillResource` / `AgentSkillScript`

| 修饰 | 都是 `abstract class` |
|---|---|

**职责**：Skill 拥有的资源和可执行脚本基类。

**关键方法**：
```csharp
// AgentSkillResource
abstract Task<object?> ReadAsync(IServiceProvider? sp = null, CancellationToken ct = default);

// AgentSkillScript
abstract Task<object?> RunAsync(
    AgentSkill skill, JsonElement? arguments,
    IServiceProvider? sp, CancellationToken ct = default);
virtual JsonElement? ParametersSchema { get; }  // 脚本参数 schema，可覆写
```

**关键属性**：`Name : string`、`Description : string?`。

---

### `AgentSkillsSource`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `abstract class` |
| 程序集 | `Microsoft.Agents.AI` |

**职责**：Skill 的**来源**抽象——可以是文件系统目录、内存集合、数据库、远程服务等。

**关键方法**：
```csharp
abstract Task<IList<AgentSkill>> GetSkillsAsync(CancellationToken ct = default);
```

**已有子类**：
- `AgentFileSkillsSource` — 扫描目录读 .md 文件
- `AgentInMemorySkillsSource` — 内存集合
- `AggregatingAgentSkillsSource` — 多个 source 聚合
- `DeduplicatingAgentSkillsSource` — 去重装饰器
- `FilteringAgentSkillsSource` — 谓词过滤装饰器

**扩展点**：子类化做自定义后端（如 CBIM Workspace 里 module 绑定的 skill）。

---

### `AgentSkillsProvider`

| 字段 | 内容 |
|------|------|
| namespace | `Microsoft.Agents.AI` |
| 修饰 | `sealed class` |
| 继承 | `AIContextProvider` |
| 程序集 | `Microsoft.Agents.AI` |

**职责**：把多个 Skill 源**包装成一个 AIContextProvider**，实现**渐进式披露**——先在系统提示里列出 skill 名/描述，agent 按需调三个工具加载具体内容。

**关键构造重载**：
```csharp
// 单目录文件
new AgentSkillsProvider(string skillPath, ...);
// 多目录文件
new AgentSkillsProvider(IEnumerable<string> skillPaths, ...);
// 内存集合
new AgentSkillsProvider(params AgentSkill[] skills);
new AgentSkillsProvider(IEnumerable<AgentSkill> skills, ...);
// 自定义源
new AgentSkillsProvider(AgentSkillsSource source, ...);
```

**核心方法**（覆写 AIContextProvider）：
```csharp
protected override ValueTask<AIContext> ProvideAIContextAsync(
    InvokingContext ctx, CancellationToken ct = default);
```

返回的 `AIContext` 包含：
1. **Instructions** —— 拼接的"可用 skill 列表 + 加载指引"
2. **Tools** —— 三个内置 AIFunction：
   - `load_skill(name)` — 拉取某 skill 的完整 content
   - `read_skill_resource(skill, name)` — 拉取某 skill 的资源
   - `run_skill_script(skill, name, args)` — 执行某 skill 的脚本

**Skill → AITool 的标准流程**：单个 Skill 不直接变成多个工具；而是统一通过这 3 个工具按名访问，让 LLM 自己选 skill。

**CBIM 用法**：CBIM 的 module 绑定 skill 可以走 AgentSkillsSource 子类，给当前 task 的 agent 注入"这次任务相关的 skill 集合"。

---

### `AgentSkillsProviderBuilder`

| 修饰 | `sealed class` |
|---|---|

**职责**：流式 Builder，灵活组合多源 + 过滤 + 配置。

**关键方法**（链式）：
```csharp
.UseFileSkill(string path, ...)
.UseFileSkills(IEnumerable<string> paths, ...)
.UseSkill(AgentSkill)
.UseSkills(params AgentSkill[])
.UseSource(AgentSkillsSource)
.UsePromptTemplate(string)        // 必须含 {skills} {resource_instructions} {script_instructions} 占位符
.UseScriptApproval(bool enabled = true)
.UseFileScriptRunner(AgentFileSkillScriptRunner)
.UseLoggerFactory(ILoggerFactory)
.UseFilter(Func<AgentSkill, bool>)
.UseOptions(Action<AgentSkillsProviderOptions>)
.Build() : AgentSkillsProvider
```

---

### `AgentSkillsProviderOptions`

| 修饰 | `sealed class` |
|---|---|

**职责**：Provider 行为配置。

**关键属性**：
- `SkillsInstructionPrompt : string?` — 自定义系统提示模板（含 3 个占位符）
- `ScriptApproval : bool` — 脚本执行是否需要 human-in-the-loop 审批（默认 false）
- `DisableCaching : bool` — 关闭工具/指令缓存（默认 false——开启缓存）

---

## Compaction（Microsoft.Agents.AI.Compaction）

### `CompactionStrategy`

| 修饰 | `abstract class` |
|---|---|

**职责**：对 `ChatHistoryProvider` 中的消息索引做压缩（删除 / 摘要 / 截断），防止上下文窗口爆炸。

**关键方法**：
```csharp
public Task CompactAsync(CompactionMessageIndex index, ILogger? logger = null);
protected abstract Task CompactCoreAsync(CompactionMessageIndex index, ILogger? logger);
```

**关键属性**：
- `Trigger : CompactionTrigger` — 触发压缩的条件
- `Target : CompactionTrigger` — 压缩到此条件停止

**扩展点**：子类化。MSAI 提供 6 个开箱策略。

---

### `SummarizationCompactionStrategy`

LLM 摘要旧消息。

**关键属性**：
- `MinimumPreservedGroups : int` — 保留最近 N 组消息（默认 8）

---

### `TruncationCompactionStrategy`

直接删旧消息组。

---

### `SlidingWindowCompactionStrategy`

维持固定大小的滑动窗口。

---

### `ContextWindowCompactionStrategy`

按 token 数算压缩边界。

---

### `ToolResultCompactionStrategy`

专门压缩 tool result（保留 call 和最终 response，中间结果折叠）。

---

### `PipelineCompactionStrategy`

按序应用多个策略。

**关键属性**：
- `Strategies : IReadOnlyList<CompactionStrategy>`

---

## Chat 层（Microsoft.Extensions.AI）

### `IChatClient`

| 修饰 | `interface` |
|---|---|
| 程序集 | `Microsoft.Extensions.AI.Abstractions` |

**职责**：所有 LLM 调用的统一抽象。不同 LLM provider（OpenAI / Anthropic / Azure / 本地）都实现这个接口。

**关键方法**：
```csharp
Task<ChatResponse> GetResponseAsync(
    IEnumerable<ChatMessage> messages,
    ChatOptions? options = null,
    CancellationToken cancellationToken = default);

IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
    IEnumerable<ChatMessage> messages,
    ChatOptions? options = null,
    CancellationToken cancellationToken = default);

object? GetService(Type serviceType, object? serviceKey = null);
```

**CBIM 用法**：
```csharp
IChatClient client = openAIChatClient.AsIChatClient();
// 然后 client.AsAIAgent(...) 包成 AIAgent
```

---

### `DelegatingChatClient`

| 修饰 | `abstract class` |
|---|---|
| 实现 | `IChatClient` |

**职责**：装饰器基类，所有 chat 层中间件的根。

**关键属性**：
- `InnerClient : IChatClient`

---

### `FunctionInvokingChatClient`

| 修饰 | `sealed class` |
|---|---|
| 继承 | `DelegatingChatClient` |

**职责**：自动工具调用循环。LLM 返回 `FunctionCallContent` → 它反射调对应 C# 方法 → 把 `FunctionResultContent` 回喂 LLM → 直到没有更多 tool call。

**关键属性**：
- `MaximumIterationsPerRequest : int` — 防死循环上限
- `AllowConcurrentInvocation : bool` — 并行调多个工具

> ⚠️ ChatClientAgent 自动加这一层，**不需要** `.AsBuilder().UseFunctionInvocation()`。

---

### `CachingChatClient` / `DistributedCachingChatClient`

按请求 hash 缓存响应。

---

### `LoggingChatClient`

把每次 LLM 调用写到 `ILogger`。

---

### `OpenTelemetryChatClient`

OpenTelemetry GenAI semantic conventions 追踪。

---

### `ChatClientBuilder`

链式装配 `IChatClient` 装饰器。

**关键方法**：
```csharp
ChatClientBuilder Use(Func<IChatClient, IServiceProvider, IChatClient> factory);
ChatClientBuilder UseFunctionInvocation(Action<FunctionInvokingChatClient>? configure = null);
ChatClientBuilder UseCaching(IDistributedCache cache);
ChatClientBuilder UseLogging(ILoggerFactory? loggerFactory = null);
ChatClientBuilder UseOpenTelemetry(string? sourceName = null, Action<OpenTelemetryChatClient>? configure = null);
IChatClient Build(IServiceProvider? services = null);
```

**用法**：
```csharp
IChatClient chained = baseClient
    .AsBuilder()
    .UseLogging(loggerFactory)
    .UseOpenTelemetry()
    .UseCaching(cache)
    .Build();
```

---

### `ChatMessage` / `ChatRole`

`ChatMessage`：一条消息。

**关键属性**：
- `Role : ChatRole` — `User` / `Assistant` / `System` / `Tool`
- `AuthorName : string?`
- `Contents : IList<AIContent>` — 多模态内容（文本 / 工具调用 / 图片等）
- `Text : string` — 仅 TextContent 聚合

**构造**：
```csharp
new ChatMessage(ChatRole.User, "hello")
new ChatMessage(ChatRole.Assistant, new List<AIContent> { new TextContent("ok") })
```

---

### `ChatResponse` / `ChatResponseUpdate`

`IChatClient` 的返回。和 `AgentResponse` 几乎同构（前者是 chat 层，后者 agent 层包装）。

---

### `ChatOptions`

`IChatClient` 调用时传的选项。

**关键属性**：
- `Instructions : string?` — 系统提示
- `Temperature : float?` / `TopP : float?` / `MaxOutputTokens : int?`
- `Tools : IList<AITool>?` — 工具列表
- `ToolMode : ChatToolMode?` — auto / required / specific
- `ModelId : string?` — 模型 override
- `AdditionalProperties : AdditionalPropertiesDictionary?` — provider-specific 透传

---

## 内容类型（AIContent 子类）

### `AIContent`

| 修饰 | `abstract class` |

**职责**：消息内容的多态基类。

**关键属性**：
- `RawRepresentation : object?` — 原始 provider 返回
- `AdditionalProperties : AdditionalPropertiesDictionary?`

### `TextContent`

文本内容。属性 `Text : string`。

### `FunctionCallContent`

工具调用请求（LLM 输出）。

**属性**：
- `CallId : string` — 配对 ID
- `Name : string` — 工具名
- `Arguments : IDictionary<string, object?>?` — 参数

### `FunctionResultContent`

工具调用结果（喂回 LLM）。

**属性**：
- `CallId : string` — 对应 call
- `Result : object?` — 返回值
- `Exception : Exception?` — 失败时

### `DataContent`

内联二进制（图片 / 音频）。`Data : ReadOnlyMemory<byte>` + `MediaType`。

### `UriContent`

外链资源。`Uri` + `MediaType`。

### `UsageContent`

token 使用统计。

### `ErrorContent`

错误信息。

---

## 工具（Tool）

### `AITool`

| 修饰 | `abstract class` |

**职责**：所有工具的基类。

**关键属性**：
- `Name : string`
- `Description : string`

### `AIFunction`

| 修饰 | `abstract class` |
| 继承 | `AITool` |

**职责**：可调用的工具（带 schema + invoke 逻辑）。

**关键方法**：
```csharp
ValueTask<object?> InvokeAsync(
    AIFunctionArguments? arguments = null,
    CancellationToken cancellationToken = default);
```

**关键属性**：
- `JsonSchema : JsonElement` — 参数 schema
- `ReturnJsonSchema : JsonElement?` — 返回值 schema

### `AIFunctionFactory`

| 修饰 | `static class` |

**职责**：把 C# 方法 / delegate 包成 `AIFunction`。

**关键方法**：
```csharp
public static AIFunction Create(
    Delegate method,
    string? name = null,
    string? description = null,
    JsonSerializerOptions? serializerOptions = null);

public static AIFunction Create(
    MethodInfo method,
    object? target = null,
    string? name = null,
    string? description = null);
```

**用法**（Unity 2020.3 老 C# 编译器需显式 cast）：
```csharp
AIFunction f1 = AIFunctionFactory.Create((Func<string>)GetCurrentTime);
AIFunction f2 = AIFunctionFactory.Create((Func<int, int>)RollDice);
```

`[Description]` attribute 提供 schema 描述（System.ComponentModel.Description）：
```csharp
[Description("Roll a dice and return the result")]
static int RollDice([Description("Number of sides")] int sides = 6) => ...;
```

---

## Workflows（Microsoft.Agents.AI.Workflows）

### `Workflow`

DAG 定义。由 `WorkflowBuilder` 产出。

---

### `WorkflowBuilder`

| 修饰 | `class` |

**职责**：组装 workflow DAG。

**关键方法**：
```csharp
public WorkflowBuilder(Executor startExecutor);
public WorkflowBuilder AddEdge(Executor from, Executor to);
public WorkflowBuilder AddEdge(Executor from, Executor to, Func<...> condition);
public Workflow Build();
```

**用法**：
```csharp
var workflow = new WorkflowBuilder(classifierAgent)
    .AddEdge(classifierAgent, responderAgent)
    .Build();
```

> AIAgent 直接可作 Executor 传入，不需手工子类化。

---

### `Executor<TInput, TOutput>` / `Executor<TInput>`

| 修饰 | `abstract class` |

**职责**：workflow 中的一个节点。

**关键方法**：
```csharp
protected abstract ValueTask<TOutput> HandleAsync(
    TInput input, ExecutorContext context, CancellationToken ct);
```

**扩展点**：子类化。

**CBIM 用法**：CBIM `CbimTaskExecutor : Executor<CbimTask, AgentResponse>`，HandleAsync 内拼 ContextProviders + 调 `task.Who.RunAsync()` + 写 Session。

---

### `InProcessExecution`

| 修饰 | `static class` |

**职责**：跑 workflow。

**关键方法**：
```csharp
public static Task<StreamingRun> RunStreamingAsync(
    Workflow workflow,
    ChatMessage input,
    CancellationToken ct = default);
```

---

### `StreamingRun`

| 修饰 | `sealed class`，`IAsyncDisposable` |

**职责**：一次 workflow 运行的句柄。

**关键方法**：
```csharp
Task<bool> TrySendMessageAsync(object message, CancellationToken ct = default);
IAsyncEnumerable<WorkflowEvent> WatchStreamAsync(CancellationToken ct = default);
```

**关键约定**：
> agent 作 executor 时会缓存消息直到收到 `TurnToken`。所以发送 input 后必须再 `TrySendMessageAsync(new TurnToken(emitEvents: true))` 才会真正开始流转。

---

### `TurnToken`

发给 agent-as-executor 的"开始处理"信号。

**构造**：`new TurnToken(emitEvents: bool)` —— `emitEvents=true` 时会发 `AgentResponseUpdateEvent` 流式。

---

### Workflow 事件

| 类 | 用途 |
|---|------|
| `WorkflowEvent` | 基类，`Data : object?` |
| `ExecutorEvent` | 执行器范围，有 `ExecutorId` |
| `ExecutorInvokedEvent` | 节点开始 |
| `ExecutorCompletedEvent` | 节点完成 |
| `ExecutorFailedEvent` | 节点抛异常 |
| `AgentResponseUpdateEvent` | agent 流式输出（含 `Update : AgentResponseUpdate`） |
| `WorkflowStartedEvent` | 整体启动 |
| `WorkflowErrorEvent` | 整体出错（含 `Exception`） |
| `WorkflowOutputEvent` | 输出基类 |
| `SuperStepEvent` | 超步事件 |

**遍历模式**：
```csharp
await foreach (WorkflowEvent evt in run.WatchStreamAsync())
{
    switch (evt)
    {
        case AgentResponseUpdateEvent u: ...; break;
        case ExecutorCompletedEvent c:   ...; break;
        case WorkflowErrorEvent e:        ...; break;
        case ExecutorFailedEvent f:       ...; break;
    }
}
```

---

## Provider 桥接（关键扩展方法）

### `OpenAI.Chat.ChatClient.AsIChatClient()`

| namespace | `Microsoft.Extensions.AI` |
| 程序集 | `Microsoft.Extensions.AI.OpenAI` |

**签名**：`this OpenAI.Chat.ChatClient → IChatClient`

**用途**：把 OpenAI SDK 原生 `ChatClient` 包成 MSAI 标准的 `IChatClient`。

**用法**：
```csharp
var openAi = new OpenAIClient(new ApiKeyCredential(apiKey), new OpenAIClientOptions
{
    Endpoint = new Uri("https://llm-proxy.tapsvc.com/v1")
});
OpenAI.Chat.ChatClient cc = openAi.GetChatClient("gpt-5.4-mini");
IChatClient client = cc.AsIChatClient();
```

---

### `OpenAI.Chat.ChatClient.AsAIAgent()`

| namespace | `Microsoft.Agents.AI` |
| 程序集 | `Microsoft.Agents.AI.OpenAI` |

**签名**：
```csharp
public static ChatClientAgent AsAIAgent(
    this OpenAI.Chat.ChatClient chatClient,
    string? instructions = null,
    string? name = null,
    string? description = null,
    IEnumerable<AITool>? tools = null);
```

**用途**：一步把 OpenAI ChatClient 包成 ChatClientAgent。

---

### `OpenAI.Responses.ResponsesClient.AsAIAgent()` / `AsIChatClient()` — **OpenAI 新 API**

| namespace | `OpenAI.Responses` |
| 程序集 | `Microsoft.Agents.AI.OpenAI` |

**用途**：把 OpenAI **Responses API**（`/v1/responses`）端点包成 IChatClient / AIAgent。**和上面的 ChatClient 走的是完全不同的 HTTP 端点**。

**关键扩展方法**：
```csharp
// 直接到 AIAgent
public static ChatClientAgent AsAIAgent(
    this ResponsesClient client,
    string? model = null,
    string? instructions = null,
    string? name = null,
    string? description = null,
    IList<AITool>? tools = null,
    Func<IChatClient, IChatClient>? clientFactory = null,
    ILoggerFactory? loggerFactory = null,
    IServiceProvider? services = null);

// 带完整 options
public static ChatClientAgent AsAIAgent(
    this ResponsesClient client,
    ChatClientAgentOptions options,
    string? model = null,
    Func<IChatClient, IChatClient>? clientFactory = null,
    ILoggerFactory? loggerFactory = null,
    IServiceProvider? services = null);

// 特殊：禁用服务端存储 + 包含加密推理内容
public static IChatClient AsIChatClientWithStoredOutputDisabled(
    this ResponsesClient responseClient,
    string? model = null,
    bool includeReasoningEncryptedContent = true);
```

**Chat Completions vs Responses 区别**：

| 维度 | ChatClient（旧） | ResponsesClient（新） |
|------|----------------|---------------------|
| HTTP 端点 | `/v1/chat/completions` | `/v1/responses` |
| 服务端存储 | 无 | 支持 store=true 缓存对话状态 |
| 推理内容 | 不返回 | 支持加密推理内容透传 |
| 后台模式 | 不支持 | 支持 `AllowBackgroundResponses` |
| 续行令牌 | 不支持 | 支持 `ResponseContinuationToken` |
| 适用模型 | 全部 OpenAI 模型 | 较新的 reasoning 模型（o1/o3 系列、新模型） |

**用法**：
```csharp
var openAi = new OpenAIClient(new ApiKeyCredential(apiKey), opts);
ResponsesClient responseClient = openAi.GetResponsesClient();
ChatClientAgent agent = responseClient.AsAIAgent(
    model: "gpt-5.4-mini",
    instructions: "...");
```

**⚠️ 代理服务场景**：某些 OpenAI 兼容代理（如团队 LLM 代理）**只支持 `/v1/responses`，不支持 `/v1/chat/completions`**。这种代理下必须用 ResponsesClient 路径，不能用 ChatClient。判别方法：先试 ChatClient，如返回 404 endpoint not found，切到 ResponsesClient。

**CBIM 用法**：CBIM 的 LLM Provider 装配层会根据代理类型选择 ChatClient 或 ResponsesClient——封装到 AgentSystem.OpenInstance 内部，对调用方透明。

---

### `IChatClient.AsAIAgent()`

| namespace | `Microsoft.Agents.AI` |
| 程序集 | `Microsoft.Agents.AI` |

把任意 `IChatClient` 包成 `ChatClientAgent`。

```csharp
ChatClientAgent agent = chatClient.AsAIAgent(opts);  // ChatClientAgentOptions
```

---

### Anthropic 系列（`Microsoft.Agents.AI.Anthropic`）

| namespace | `Anthropic` / `Anthropic.Services` |
| 程序集 | `Microsoft.Agents.AI.Anthropic` |

**桥接两条路径**：
- 主接口 `IAnthropicClient`（高级）→ `AsAIAgent()`
- Beta 服务 `IBetaService`（访问最新特性）→ `AsAIAgent()`

**关键扩展方法**：
```csharp
// 通用客户端
namespace Anthropic;
public static class AnthropicClientExtensions
{
    public static int DefaultMaxTokens { get; set; } = 4096;

    public static ChatClientAgent AsAIAgent(
        this IAnthropicClient client,
        string model,                            // 必填，如 "claude-sonnet-4-6"
        string? instructions = null,
        string? name = null,
        string? description = null,
        IList<AITool>? tools = null,
        int? defaultMaxTokens = null,
        Func<IChatClient, IChatClient>? clientFactory = null,
        ILoggerFactory? loggerFactory = null,
        IServiceProvider? services = null);

    public static ChatClientAgent AsAIAgent(
        this IAnthropicClient client,
        ChatClientAgentOptions options,
        Func<IChatClient, IChatClient>? clientFactory = null,
        ILoggerFactory? loggerFactory = null,
        IServiceProvider? services = null);
}

// Beta 服务（同形态）
namespace Anthropic.Services;
public static class AnthropicBetaServiceExtensions
{
    public static int DefaultMaxTokens { get; set; } = 4096;
    public static ChatClientAgent AsAIAgent(this IBetaService betaService, ...);  // 同上参数
}
```

**`IAnthropicClient.AsIChatClient()`** 来自 `Microsoft.Extensions.AI.Anthropic`（基础桥接），把 Anthropic SDK 转成 `IChatClient`。

**Anthropic SDK 类结构**：
- `AnthropicClient` — 顶层客户端（包含 ApiKey 配置）
- `IAnthropicClient` — 主接口，`AnthropicClient` 实现
- `Messages` 端点 — 通过 `client.Messages` 访问（或 `MessagesClient`）
- `Beta` 端点 — 通过 `client.Beta` 访问（最新特性）

**用法**：
```csharp
// 1. 构造客户端（含代理 endpoint 覆写）
var anthropic = new AnthropicClient(new AnthropicClientOptions
{
    ApiKey = apiKey,
    BaseUrl = new Uri("https://llm-proxy.tapsvc.com/v1"),  // 代理走这里
});

// 2. 直接到 AIAgent
ChatClientAgent agent = anthropic.AsAIAgent(
    model: "claude-sonnet-4-6",
    instructions: "你是 CBIM 的架构师。",
    tools: toolList,
    defaultMaxTokens: 4096);

// 3. 或先拿 IChatClient 再包
IChatClient client = anthropic.AsIChatClient(model: "claude-sonnet-4-6");
ChatClientAgent agent2 = client.AsAIAgent(opts);
```

**`defaultMaxTokens` 关键差异**：Anthropic API **要求**每次调用必须指定 `max_tokens`，OpenAI 不强制。`AsAIAgent` 接受 `defaultMaxTokens` 参数（不填则用全局 `DefaultMaxTokens = 4096`）。CBIM 集成 Anthropic 时记得显式传。

**`/v1/messages` 端点**：Anthropic 原生 API 路径。你的团队代理表里明确列了支持，是当前最稳的接入通道。

**CBIM 用法**：CBIM AgentDescription 里 `chat_client_config.provider = "anthropic"` + `model = "claude-..."` → AgentSystem.OpenInstance 根据这个走 Anthropic 桥接路径。

---

## CBIM 实施时高频引用清单

按出现频率：

| 类 / 接口 | CBIM 怎么用 |
|----------|------------|
| `ChatClientAgentOptions` | AgentDescription → AIAgent 装配的载体 |
| `AIContextProvider` (子类化 × 3) | Workspace / Memory / Session 注入 |
| `AIFunctionFactory.Create` | C# 方法 → 工具 |
| `IChatClient.AsAIAgent` | 构造 agent 实例 |
| `AIAgent.RunAsync` | TaskRunner 唯一调用入口 |
| `AgentSession` | Channel 持有，跨轮维持上下文 |
| `AgentResponse.Text` | 拿最终回答 |
| `Executor<TIn, TOut>` (子类化) | CbimTaskExecutor，FlowGraph 节点 |
| `WorkflowBuilder` | 装配业务流程 |
| `StreamingRun.WatchStreamAsync` | 跟踪 workflow 执行 |
| `DelegatingAIAgent` (可选子类化) | Session 日志中间件 |
| `ChatHistoryProvider` (可选子类化) | Memory 接管对话历史 |
| `CompactionStrategy` (可选子类化) | 中期记忆 distill 策略 |
