# Microsoft Agent Framework — 架构类图

C# 范围。覆盖 `Microsoft.Agents.AI*` + `Microsoft.Extensions.AI*` + `Microsoft.Agents.AI.Workflows` 的核心类拓扑与扩展点。

类的详细说明见 [`MSAI_ClassReference.md`](./MSAI_ClassReference.md)。

---

## 一、整体分层

```mermaid
flowchart TB
    subgraph Workflow[Microsoft.Agents.AI.Workflows]
        Workflow_cls[Workflow]
        Executor[Executor&lt;TIn,TOut&gt;]
        WorkflowBuilder[WorkflowBuilder]
        InProcExec[InProcessExecution]
        WfEvent[WorkflowEvent]
    end

    subgraph AgentLayer[Microsoft.Agents.AI]
        AIAgent[AIAgent abstract]
        ChatClientAgent[ChatClientAgent]
        DelegatingAIAgent[DelegatingAIAgent abstract]
        AIAgentBuilder[AIAgentBuilder]
        ChatClientAgentOptions[ChatClientAgentOptions]
        AgentSession[AgentSession abstract]
        AgentResponse[AgentResponse]
        AgentResponseUpdate[AgentResponseUpdate]
        AIContextProvider[AIContextProvider abstract]
        ChatHistoryProvider[ChatHistoryProvider abstract]
        AgentSkill[AgentSkill abstract]
        Compaction[CompactionStrategy abstract]
    end

    subgraph ChatLayer[Microsoft.Extensions.AI]
        IChatClient[IChatClient]
        DelegatingChatClient[DelegatingChatClient]
        FunctionInvokingChatClient[FunctionInvokingChatClient]
        ChatMessage[ChatMessage]
        ChatResponse[ChatResponse]
        ChatOptions[ChatOptions]
        AIContent[AIContent abstract]
        AITool[AITool abstract]
        AIFunction[AIFunction abstract]
        AIFunctionFactory[AIFunctionFactory static]
    end

    subgraph Providers[Provider SDKs]
        OpenAIChat[OpenAI.Chat.ChatClient]
        AnthropicMsg[Anthropic.MessagesClient]
    end

    Workflow_cls --> Executor
    WorkflowBuilder --> Workflow_cls
    InProcExec --> WfEvent
    Executor -.may wrap.-> AIAgent

    AIAgent --> ChatClientAgent
    AIAgent --> DelegatingAIAgent
    DelegatingAIAgent --> AIAgent
    ChatClientAgent --> IChatClient
    ChatClientAgent --> ChatHistoryProvider
    ChatClientAgent --> AIContextProvider
    AIAgentBuilder --> AIAgent
    ChatClientAgentOptions -.config.-> ChatClientAgent
    ChatHistoryProvider -.uses.-> Compaction

    IChatClient --> ChatMessage
    IChatClient --> ChatResponse
    DelegatingChatClient --> IChatClient
    FunctionInvokingChatClient --> DelegatingChatClient
    ChatMessage --> AIContent
    AIFunction --> AITool
    AIFunctionFactory --> AIFunction

    OpenAIChat -.AsIChatClient.-> IChatClient
    AnthropicMsg -.AsIChatClient.-> IChatClient
```

---

## 二、AIAgent 继承树

```mermaid
classDiagram
    class AIAgent {
        <<abstract>>
        +Id: string
        +Name: string?
        +Description: string?
        +RunAsync(messages, session, options) Task~AgentResponse~
        +RunStreamingAsync(messages, session, options) IAsyncEnumerable~AgentResponseUpdate~
        +CreateSessionAsync() Task~AgentSession~
        +SerializeSessionAsync() Task~JsonElement~
        +DeserializeSessionAsync(json) Task~AgentSession~
        #RunCoreAsync()*
        #RunCoreStreamingAsync()*
    }

    class ChatClientAgent {
        <<sealed>>
        +ChatClient: IChatClient
        +ChatHistoryProvider: ChatHistoryProvider
        +AIContextProviders: IReadOnlyList~AIContextProvider~
    }

    class DelegatingAIAgent {
        <<abstract>>
        +InnerAgent: AIAgent
    }

    class AnonymousDelegatingAIAgent {
        <<sealed>>
        +AnonymousDelegatingAIAgent(inner, runFunc, runStreamFunc)
    }

    class LoggingAgent {
        <<sealed>>
        +JsonSerializerOptions
    }

    class OpenTelemetryAgent {
        <<sealed>>
        +Dispose()
    }

    class FunctionInvocationDelegatingAgent {
        <<sealed internal>>
    }

    AIAgent <|-- ChatClientAgent
    AIAgent <|-- DelegatingAIAgent
    DelegatingAIAgent <|-- AnonymousDelegatingAIAgent
    DelegatingAIAgent <|-- LoggingAgent
    DelegatingAIAgent <|-- OpenTelemetryAgent
    DelegatingAIAgent <|-- FunctionInvocationDelegatingAgent
```

---

## 三、IChatClient 装饰器链

```mermaid
classDiagram
    class IChatClient {
        <<interface>>
        +GetResponseAsync(messages, options, ct) Task~ChatResponse~
        +GetStreamingResponseAsync(messages, options, ct) IAsyncEnumerable~ChatResponseUpdate~
        +GetService(type, key) object
    }

    class DelegatingChatClient {
        <<abstract>>
        +InnerClient: IChatClient
    }

    class FunctionInvokingChatClient {
        <<sealed>>
        +MaximumIterationsPerRequest: int
        +AllowConcurrentInvocation: bool
    }

    class CachingChatClient {
        <<abstract>>
    }

    class DistributedCachingChatClient { }
    class LoggingChatClient { }
    class OpenTelemetryChatClient { }

    class ChatClientBuilder {
        +Use(factory) ChatClientBuilder
        +UseFunctionInvocation() ChatClientBuilder
        +UseCaching(cache) ChatClientBuilder
        +UseLogging(logger) ChatClientBuilder
        +UseOpenTelemetry() ChatClientBuilder
        +Build() IChatClient
    }

    IChatClient <|.. DelegatingChatClient
    DelegatingChatClient <|-- FunctionInvokingChatClient
    DelegatingChatClient <|-- CachingChatClient
    DelegatingChatClient <|-- LoggingChatClient
    DelegatingChatClient <|-- OpenTelemetryChatClient
    CachingChatClient <|-- DistributedCachingChatClient
    ChatClientBuilder ..> IChatClient : builds
```

---

## 四、Provider 体系（CBIM 扩展核心）

```mermaid
classDiagram
    class AIContextProvider {
        <<abstract>>
        +StateKeys: IReadOnlyList~string~
        +InvokingAsync(ctx, ct) ValueTask~AIContext~
        +InvokedAsync(ctx, ct) ValueTask
        #ProvideAIContextAsync()*
        #StoreAIContextAsync()*
    }

    class AIContext {
        <<sealed>>
        +Instructions: string?
        +Messages: IEnumerable~ChatMessage~?
        +Tools: IEnumerable~AITool~?
    }

    class InvokingContext {
        +Messages
        +CancellationToken
    }

    class InvokedContext {
        +Messages
        +Response
    }

    class ChatHistoryProvider {
        <<abstract>>
        +StateKeys: IReadOnlyList~string~
        +InvokingAsync(ctx) ValueTask
        +InvokedAsync(ctx) ValueTask
        #ProvideChatHistoryAsync()*
        #StoreChatHistoryAsync()*
    }

    class InMemoryChatHistoryProvider {
        <<sealed>>
    }

    class CompactionStrategy {
        <<abstract>>
        +Trigger: CompactionTrigger
        +Target: CompactionTrigger
        +CompactAsync(index, logger) Task
        #CompactCoreAsync()*
    }

    AIContextProvider ..> AIContext : returns
    AIContextProvider ..> InvokingContext : receives
    AIContextProvider ..> InvokedContext : receives
    ChatHistoryProvider --> CompactionStrategy : uses
    ChatHistoryProvider <|-- InMemoryChatHistoryProvider
```

---

## 五、CompactionStrategy 子类

```mermaid
classDiagram
    class CompactionStrategy {
        <<abstract>>
    }
    class SummarizationCompactionStrategy {
        <<sealed>>
        +MinimumPreservedGroups: int
    }
    class TruncationCompactionStrategy { <<sealed>> }
    class SlidingWindowCompactionStrategy { <<sealed>> }
    class ContextWindowCompactionStrategy { <<sealed>> }
    class ToolResultCompactionStrategy { <<sealed>> }
    class PipelineCompactionStrategy {
        <<sealed>>
        +Strategies: IReadOnlyList~CompactionStrategy~
    }

    CompactionStrategy <|-- SummarizationCompactionStrategy
    CompactionStrategy <|-- TruncationCompactionStrategy
    CompactionStrategy <|-- SlidingWindowCompactionStrategy
    CompactionStrategy <|-- ContextWindowCompactionStrategy
    CompactionStrategy <|-- ToolResultCompactionStrategy
    CompactionStrategy <|-- PipelineCompactionStrategy
```

---

## 六、AIContent 层级（Microsoft.Extensions.AI）

```mermaid
classDiagram
    class AIContent {
        <<abstract>>
        +RawRepresentation: object?
        +AdditionalProperties: AdditionalPropertiesDictionary?
    }
    class TextContent {
        +Text: string
    }
    class FunctionCallContent {
        +CallId: string
        +Name: string
        +Arguments: IDictionary~string,object?~?
    }
    class FunctionResultContent {
        +CallId: string
        +Result: object?
        +Exception: Exception?
    }
    class DataContent {
        +Data: ReadOnlyMemory~byte~
        +MediaType: string
    }
    class UriContent {
        +Uri: Uri
        +MediaType: string
    }
    class UsageContent {
        +Details: UsageDetails
    }
    class ErrorContent {
        +Message: string
        +Details: string?
    }

    AIContent <|-- TextContent
    AIContent <|-- FunctionCallContent
    AIContent <|-- FunctionResultContent
    AIContent <|-- DataContent
    AIContent <|-- UriContent
    AIContent <|-- UsageContent
    AIContent <|-- ErrorContent
```

---

## 七、工具与函数

```mermaid
classDiagram
    class AITool {
        <<abstract>>
        +Name: string
        +Description: string
    }
    class AIFunction {
        <<abstract>>
        +InvokeAsync(args, ct) Task~object?~
        +JsonSchema: JsonElement
        +ReturnJsonSchema: JsonElement?
    }
    class AIFunctionFactory {
        <<static>>
        +Create(Delegate, name?, desc?) AIFunction
        +Create(MethodInfo, target?, name?) AIFunction
    }

    AITool <|-- AIFunction
    AIFunctionFactory ..> AIFunction : produces
```

---

## 八、Workflow 事件树

```mermaid
classDiagram
    class WorkflowEvent {
        +Data: object?
    }
    class ExecutorEvent {
        +ExecutorId: string
    }
    class ExecutorInvokedEvent { }
    class ExecutorCompletedEvent { }
    class ExecutorFailedEvent { }
    class WorkflowOutputEvent { }
    class AgentResponseUpdateEvent {
        <<sealed>>
        +Update: AgentResponseUpdate
        +AsResponse() AgentResponse
    }
    class WorkflowStartedEvent { }
    class WorkflowErrorEvent {
        +Exception: Exception?
    }
    class WorkflowWarningEvent { }
    class SuperStepEvent { }

    WorkflowEvent <|-- ExecutorEvent
    ExecutorEvent <|-- ExecutorInvokedEvent
    ExecutorEvent <|-- ExecutorCompletedEvent
    ExecutorEvent <|-- ExecutorFailedEvent
    WorkflowEvent <|-- WorkflowOutputEvent
    WorkflowOutputEvent <|-- AgentResponseUpdateEvent
    WorkflowEvent <|-- WorkflowStartedEvent
    WorkflowEvent <|-- WorkflowErrorEvent
    WorkflowEvent <|-- WorkflowWarningEvent
    WorkflowEvent <|-- SuperStepEvent
```

---

## 九、Workflow 装配

```mermaid
classDiagram
    class WorkflowBuilder {
        +WorkflowBuilder(startExecutor)
        +AddEdge(from, to) WorkflowBuilder
        +AddEdge(from, to, condition) WorkflowBuilder
        +Build() Workflow
    }
    class Workflow {
        +StartExecutor
        +Edges
    }
    class Executor~TIn_TOut~ {
        <<abstract>>
        +HandleAsync(input, ctx) ValueTask~TOut~
    }
    class InProcessExecution {
        <<static>>
        +RunStreamingAsync(workflow, input) Task~StreamingRun~
    }
    class StreamingRun {
        +TrySendMessageAsync(token) Task~bool~
        +WatchStreamAsync() IAsyncEnumerable~WorkflowEvent~
    }
    class TurnToken {
        +TurnToken(emitEvents: bool)
    }

    WorkflowBuilder ..> Workflow : builds
    Workflow --> Executor
    InProcessExecution ..> Workflow : runs
    InProcessExecution ..> StreamingRun : returns
    StreamingRun ..> TurnToken : accepts
```

---

## 十、`AIAgent.RunAsync()` 数据流时序

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Agent as ChatClientAgent
    participant CHP as ChatHistoryProvider
    participant CP as AIContextProvider
    participant CC as IChatClient
    participant FIC as FunctionInvokingChatClient
    participant Tool as C# tool method

    User->>Agent: RunAsync(messages, session)
    Agent->>CHP: InvokingAsync(ctx) — 拉历史
    CHP-->>Agent: historic messages
    Agent->>CP: InvokingAsync(ctx) — 注入上下文
    CP-->>Agent: AIContext{Instructions,Messages,Tools}
    Agent->>CC: GetResponseAsync(merged)
    CC->>FIC: 中间件链
    FIC-->>Tool: 自动 tool call
    Tool-->>FIC: FunctionResultContent
    FIC-->>CC: 把 result 回喂 LLM
    CC-->>Agent: ChatResponse
    Agent->>CP: InvokedAsync(ctx) — 存结果
    Agent->>CHP: InvokedAsync(ctx) — 存历史
    Agent-->>User: AgentResponse{Messages,Text,Usage}
```

---

## 十一、CBIM 扩展点定位

| 层 | CBIM 扩展方式 | 写多少代码 |
|----|-------------|----------|
| AgentDescription → AIAgent | 调 `IChatClient.AsAIAgent(opts)` | 工厂方法 ~30 行 |
| Workspace / Memory / Session 注入 | 实现 `AIContextProvider` × 3 | 每个 ~30 行 |
| C# 方法 → 工具 | `AIFunctionFactory.Create((Func<...>)Method)` | 1 行 |
| 每次调用前后日志 | 子类化 `DelegatingAIAgent` | ~20 行 |
| 跨 session 对话历史 | 实现 `ChatHistoryProvider` | ~50 行 |
| 中期记忆 distill 策略 | 子类化 `CompactionStrategy` | ~50 行 |
| 业务流程图 | 实现 `Executor<TIn,TOut>` | 每节点 ~30 行 |

---

## 包到 namespace 速查

| NuGet 包 | namespace |
|---------|-----------|
| `Microsoft.Agents.AI.Abstractions` | `Microsoft.Agents.AI` |
| `Microsoft.Agents.AI` | `Microsoft.Agents.AI` + `Microsoft.Agents.AI.Compaction` |
| `Microsoft.Agents.AI.Workflows` | `Microsoft.Agents.AI.Workflows` |
| `Microsoft.Agents.AI.OpenAI` | `Microsoft.Agents.AI` (扩展) + `OpenAI.Chat` (扩展) |
| `Microsoft.Agents.AI.Anthropic` | `Microsoft.Agents.AI` (扩展) |
| `Microsoft.Extensions.AI.Abstractions` | `Microsoft.Extensions.AI` |
| `Microsoft.Extensions.AI` | `Microsoft.Extensions.AI` |
| `Microsoft.Extensions.AI.OpenAI` | `Microsoft.Extensions.AI` + `OpenAI.Chat` (扩展) |
