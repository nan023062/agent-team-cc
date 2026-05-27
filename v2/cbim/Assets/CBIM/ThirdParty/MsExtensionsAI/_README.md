# Microsoft Agent Framework + BCL Polyfills - Portable .NET DLLs

**用途**：CBIM 的 LLM 调用底座 + Agent 抽象层 + Unity 2020.3 BCL 缺口补丁。所有以纯 .NET DLL 形式投放，**不依赖 NuGetForUnity / Unity Package Manager**。CBIM 设计为纯 .NET 库，Unity 是当前宿主，未来可剥离为独立库 / 后端进程。

**下载来源**：[nuget.org](https://www.nuget.org/) 官方仓库，通过 `https://api.nuget.org/v3-flatcontainer/{packageid-lower}/{version}/{packageid-lower}.{version}.nupkg` 直拉 `.nupkg`，解包抽 `lib/<target>/*.dll`。

**安装方式**：手工下载 + 解包，**不要用 NuGetForUnity**，**不要碰 `Packages/manifest.json`**，**不要写 `packages.config`**。

---

## DLL 总览（44 个，~16 MB）

按职能分四组：核心 Agent 框架 / LLM Provider / Microsoft 框架抽象 / 系统库与 BCL polyfill。

---

## 一、核心 Agent 框架（CBIM 直接 using）

| DLL | 用途 |
|-----|------|
| **Microsoft.Agents.AI.Abstractions.dll** | Agent 抽象层——`AIAgent` 基类 / `AgentThread` / `AgentResponse` / `AgentResponseUpdate` / `ChatClientAgentOptions`。CBIM `Kernel/` 主要 using 这一层。 |
| **Microsoft.Agents.AI.dll** | Agent 实现层——`ChatClientAgent`（把 `IChatClient` 包装成 `AIAgent`）/ `AIAgentBuilder` / `IChatClient.AsAIAgent()` 扩展方法 / `FunctionInvocationDelegatingAgent`。 |
| **Microsoft.Extensions.AI.Abstractions.dll** | Chat 抽象层——`IChatClient` / `ChatMessage` / `ChatResponse` / `ChatOptions` / `AITool` / `AIFunction` / `AIContextProvider`。CBIM `ContextProviders/` 实现的接口都在这里。 |
| **Microsoft.Extensions.AI.dll** | Chat 中间件——`FunctionInvokingChatClient`（工具调用循环）/ `CachingChatClient` / `OpenTelemetryChatClient` / `LoggingChatClient`。装饰器链由 CBIM `TaskRunner` 装配。 |
| **Microsoft.Agents.AI.Workflows.dll** | DAG 工作流引擎——CBIM `FlowGraph/` 通过实现 `Executor<TIn, TOut>` 接口扩展。Superstep 循环 / Edge 路由 / Fan-out/Fan-in 都现成。 |

---

## 二、LLM Provider（按账号 / 模型选用）

| DLL | 用途 |
|-----|------|
| **Microsoft.Agents.AI.OpenAI.dll** | OpenAI / Codex / Azure OpenAI 接入 Agent 框架的桥接层。 |
| **Microsoft.Extensions.AI.OpenAI.dll** | OpenAI IChatClient 实现层（被 Agents.AI.OpenAI 引用）。 |
| **OpenAI.dll** | 官方 OpenAI .NET SDK（4.6 MB）。 |
| **Microsoft.Agents.AI.Anthropic.dll** | Anthropic Claude API 接入 Agent 框架的桥接层。 |
| **Anthropic.dll** | 官方 Anthropic .NET SDK（4 MB）。 |

> 未装：`Microsoft.Agents.AI.GitHub.Copilot`（只发 net8+ lib，引用 `CollectionsMarshal` 等 .NET 6+ 独有 API，强投会运行时挂）；`Microsoft.Agents.AI.Tools.Shell`（只发 net8+ lib，待 NS2.0/NS2.1 变体发布）。详见末尾"已评估但未装"章节。

---

## 三、Microsoft 框架基础抽象（被上层间接依赖）

| DLL | 用途 |
|-----|------|
| **Microsoft.Extensions.DependencyInjection.Abstractions.dll** | DI 抽象（`IServiceProvider` / `ServiceLifetime`）。 |
| **Microsoft.Extensions.Logging.Abstractions.dll** | 日志抽象（`ILogger` / `ILoggerFactory`）。`LoggingChatClient` / `ChatClientAgentLogMessages` 用。 |
| **Microsoft.Extensions.Caching.Abstractions.dll** | 缓存抽象（`IMemoryCache`）。`CachingChatClient` 用。 |
| **Microsoft.Extensions.Compliance.Abstractions.dll** | 合规 / 数据分类（`DataClassification` / `Redactor`）。Agent 框架打 telemetry 字段敏感等级用。 |
| **Microsoft.Extensions.Configuration.Abstractions.dll** | 配置抽象（被 Hosting / DI 间接引用）。 |
| **Microsoft.Extensions.Hosting.Abstractions.dll** | 宿主抽象（被 OpenAI Provider 间接引用）。 |
| **Microsoft.Extensions.Diagnostics.Abstractions.dll** | 诊断抽象（被 Telemetry 链路引用）。 |
| **Microsoft.Extensions.FileProviders.Abstractions.dll** | 文件 Provider 抽象（被 Hosting 链路引用）。 |
| **Microsoft.Extensions.FileSystemGlobbing.dll** | glob 路径匹配。Agent 框架的 file-based 配置加载用。 |
| **Microsoft.Extensions.ObjectPool.dll** | 对象池。Redactor 内部复用 buffer。 |
| **Microsoft.Extensions.Options.dll** | Options pattern。被 DI 链路引用。 |
| **Microsoft.Extensions.Primitives.dll** | 基础类型集（`StringSegment` / `ChangeToken`）。被 Configuration / FileProviders 引用。 |
| **Microsoft.Extensions.VectorData.Abstractions.dll** | 向量数据库抽象（`IVectorStore` / `IVectorStoreRecordCollection`）。未来 RAG / memory store 接具体后端用。 |
| **Microsoft.ML.Tokenizers.dll** | Tokenizer——`BpeTokenizer` / `TiktokenTokenizer` / `WordPieceTokenizer` / `BertTokenizer`。Agent 层做 token 计数 / context window 截断用。 |

---

## 四、系统库与 BCL polyfill

### 系统库（Microsoft 官方包，Agent 框架内部用）

| DLL | 用途 |
|-----|------|
| **System.Text.Json.dll** | JSON 序列化。Agent 框架内部用它序列化工具参数 / Agent state / 函数 schema。**不是** Unity 内置的 Newtonsoft.Json，二者并存。 |
| **System.Numerics.Tensors.dll** | 张量数学（`Tensor<T>` / `TensorPrimitives`）。embedding cosine similarity 等。 |
| **System.Threading.Channels.dll** | 异步管道（`Channel<T>`）。streaming 响应 / async producer-consumer。 |
| **System.Diagnostics.DiagnosticSource.dll** | 诊断 / 遥测（`Activity` / `ActivitySource`）。`OpenTelemetryChatClient` 用。 |
| **System.IO.Pipelines.dll** | 高性能 IO（`PipeReader` / `PipeWriter`）。`Microsoft.ML.Tokenizers` 读模型文件用。 |
| **System.ClientModel.dll** | HTTP client model 基础。OpenAI / Anthropic SDK 底层。 |
| **System.Collections.Immutable.dll** | 不可变集合（`ImmutableArray` 等）。Anthropic SDK 内部用。 |
| **System.Net.ServerSentEvents.dll** | SSE 流式协议。LLM streaming 响应解析。 |
| **System.Memory.Data.dll** | `BinaryData` 类型。LLM 返回二进制资产时用（图片 / 音频）。 |

### 第三方 SDK

| DLL | 用途 |
|-----|------|
| **Google.Protobuf.dll** | Protobuf 序列化。`Microsoft.ML.Tokenizers` 解析 SentencePiece / Llama 模型 vocab 用。 |
| **OpenTelemetry.Api.dll** | OpenTelemetry API。`Microsoft.Agents.AI.Workflows` 内部追踪用。 |

### BCL polyfill（⚠️ Unity 2020.3 + .NET 4.x 特有，升级 Unity 6 后可全删）

Unity 2020.3 + .NET 4.x 兼容模式下，Mono 运行时缺以下 BCL 类型，需要补回：

| DLL | 补什么类型 |
|-----|----------|
| **Microsoft.Bcl.AsyncInterfaces.dll** | `IAsyncEnumerable<T>` / `IAsyncEnumerator<T>` / `IAsyncDisposable` |
| **Microsoft.Bcl.HashCode.dll** | `System.HashCode` |
| **Microsoft.Bcl.Memory.dll** | `System.Range` / `System.Index` + `Base64Url` 等 helper（NS2.0 变体） |
| **Microsoft.Bcl.Numerics.dll** | `Half` 半精度浮点 |
| **System.Memory.dll** | `Span<T>` / `Memory<T>` / `ReadOnlySpan<T>` |
| **System.Buffers.dll** | `ArrayPool<T>` / `IMemoryOwner<T>` |
| **System.Threading.Tasks.Extensions.dll** | `ValueTask<T>` |
| **System.Runtime.CompilerServices.Unsafe.dll** | `Unsafe` 类（指针 / 引用操作） |
| **System.Text.Encodings.Web.dll** | `HtmlEncoder` / `UrlEncoder` / `JavaScriptEncoder` |

另外还有一个独立的源码 polyfill 在 `Assets/CBIM/_Polyfills/EnumeratorCancellationAttribute.cs`，补 `[EnumeratorCancellation]` attribute（async iterator 用）。

---

## 升级路径

CBIM 设计目标是 Unity 当前宿主、未来可独立。三种迁移路径，全部预设好：

### 路径 A：升级 Unity 到 2022.3 LTS 或 Unity 6（最简单）

Unity 6 的 Mono 已完整实现 NS2.1 BCL，所有 polyfill 可清理：

```
1. Unity Hub 升级 Unity 版本，重新打开工程
2. PlayerSettings → API Compatibility Level 切回 ".NET Standard 2.1"
   （Unity 6 叫 "Standard"，下拉默认值）
3. 删 ThirdParty/MsExtensionsAI/ 下 9 个 BCL polyfill DLL：
   - Microsoft.Bcl.AsyncInterfaces.dll
   - Microsoft.Bcl.HashCode.dll
   - Microsoft.Bcl.Memory.dll
   - Microsoft.Bcl.Numerics.dll
   - System.Memory.dll
   - System.Buffers.dll
   - System.Threading.Tasks.Extensions.dll
   - System.Runtime.CompilerServices.Unsafe.dll
   - System.Text.Encodings.Web.dll
4. 删 Assets/CBIM/_Polyfills/ 整目录
5. 同步删除 CBIM.asmdef 与 _VerifyMsai.Editor.asmdef 的 precompiledReferences 里对应条目
6. 编译验证
```

CBIM 业务代码 **零改动**——这就是把 polyfill 集中在 `ThirdParty/` 和 `_Polyfills/` 两个目录的设计意图。

### 路径 B：剥离为独立 .NET 库

```
1. cp -r v2/cbim/Assets/CBIM/  →  CBIM-standalone/
2. 新建 CBIM.csproj：
   <Project Sdk="Microsoft.NET.Sdk">
     <PropertyGroup>
       <TargetFramework>netstandard2.1</TargetFramework>
     </PropertyGroup>
     <ItemGroup>
       <PackageReference Include="Microsoft.Agents.AI" Version="1.7.0" />
       <PackageReference Include="Microsoft.Agents.AI.OpenAI" Version="1.7.0" />
       <PackageReference Include="Microsoft.Agents.AI.Anthropic" Version="1.7.0-preview.*" />
       <PackageReference Include="Microsoft.Agents.AI.Workflows" Version="1.7.0" />
     </ItemGroup>
   </Project>
3. 删 ThirdParty/MsExtensionsAI/ 整目录（NuGet 自动管理传递依赖）
4. 删 _Polyfills/（standalone .NET 自带这些类型）
5. 删 CBIM.asmdef（standalone 用 .csproj 不用 asmdef）
6. dotnet build
```

**前提条件已满足**：
- `CBIM.asmdef noEngineReferences: true` — 已强制零 Unity 依赖
- Storage 构造器要求 root path 注入 — 没有 Unity-only 路径假设
- Unity 接缝全在 `Assets/Desktop/` 与 `Assets/Editor/` 两个目录，剥离时直接抛弃

### 路径 C：改为后端进程（gRPC / MCP / REST）

路径 B 基础上加一层 server 包装：

```
独立 CBIM 库  +  薄壳
                  ├── ASP.NET Core (REST/SignalR)
                  ├── gRPC server
                  ├── MCP server（与 v1 Python kernel 同形态）
                  └── Console EXE + named pipes / stdio
```

Unity 侧改为 client，移除 `Assets/CBIM/` 整目录，只留 `Assets/Desktop/`（变成调用 CBIM 后端的瘦客户端）。

---

## 升级方式（升级具体某个包）

手工重复下载：

```bash
# 1. 查最新 stable 版本
curl https://api.nuget.org/v3-flatcontainer/<packageid-lower>/index.json

# 2. 拿 .nuspec 看 dependencies
curl https://api.nuget.org/v3-flatcontainer/<id>/<ver>/<id>.nuspec

# 3. 下载 .nupkg
curl -LO https://api.nuget.org/v3-flatcontainer/<id>/<ver>/<id>.<ver>.nupkg

# 4. 解包
unzip <id>.<ver>.nupkg -d <id>

# 5. 抽 lib/netstandard2.0/*.dll（找不到就 NS2.1，再不行 net6.0/net8.0/net462）
#    覆盖此目录下同名文件

# 6. 更新本 README 的版本列与 CBIM.asmdef / _VerifyMsai.Editor.asmdef
```

升级 `Microsoft.Agents.AI*` 主线包时建议同步检查传递依赖是否还是本目录这份清单，多增少减都要相应调整。

---

## 已评估但未装的包

| 包 | 不装的原因 |
|---|---|
| `Microsoft.Agents.AI.GitHub.Copilot` | net8+ only，引用 `CollectionsMarshal` 等 .NET 5+ 独有 API，运行时必挂。等微软发 NS2.0/NS2.1 变体。 |
| `Microsoft.Agents.AI.Tools.Shell` | net8+ only，理论可投但 assembly forwarder 行为不稳定。CBIM 当前阶段用不上 shell 工具。 |
| `Microsoft.Agents.AI.Declarative` | 依赖图爆炸（PowerFx + ObjectModel 全家桶，10+ 新 DLL）。CBIM 自有 AgentDescription 够用。 |
| `Microsoft.Agents.AI.Mem0` | 钉死 MEAI 9.x，与本目录 10.x 主版本冲突。等 Mem0 升 10.x。 |
| `Microsoft.Agents.AI.DurableTask` | 引入完整 Durable Task 编排引擎。CBIM 用 Workflows 已够。 |

---

## asmdef 引用方式

`Assets/CBIM/CBIM.asmdef` 设置：

- `overrideReferences: true`——禁止 Unity auto-reference 所有 DLL，强制走 `precompiledReferences` 白名单
- `precompiledReferences` 列出本目录全部 DLL 文件名（**必须带 `.dll` 后缀**）
- `noEngineReferences: true`——禁止 CBIM using UnityEngine / UnityEditor

`Assets/Editor/_VerifyMsai/_VerifyMsai.Editor.asmdef` 同样列出全部 DLL，用于 Unity Editor 跑 smoke test（菜单 `CBIM/Verify/MsExtensionsAI`）。
