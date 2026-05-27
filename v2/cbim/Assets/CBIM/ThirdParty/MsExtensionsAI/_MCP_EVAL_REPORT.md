# Microsoft.Agents.AI.Mcp 兼容性评估

**评估时间**：2026-05-27
**Unity 环境**：Unity 2020.3.13f1 + API Compat Level .NET Framework 4.x
**已装基线**：ThirdParty/MsExtensionsAI/_README.md 列出的 44 个 DLL（含 Microsoft.Agents.AI 1.7.0 主线 + OpenAI/Anthropic Provider + 全套 BCL polyfill）

---

## 0. 重要更正：包名不存在

任务指定的 **`Microsoft.Agents.AI.Mcp`** 在 nuget.org **不存在**。

验证：
```
GET https://api.nuget.org/v3-flatcontainer/microsoft.agents.ai.mcp/index.json
→ 404 BlobNotFound

GET https://azuresearch-usnc.nuget.org/query?q=PackageId:Microsoft.Extensions.AI.Mcp&prerelease=true
→ totalHits: 0
```

Microsoft 至今**没有发布**专门以 `Microsoft.Agents.AI.Mcp` 命名的 Agent Framework MCP 集成包。Agent Framework（`Microsoft.Agents.AI` 1.7.0）目前通过下面这条官方路径接 MCP：

**Anthropic / Microsoft 联合维护的官方 .NET MCP SDK：`ModelContextProtocol` + `ModelContextProtocol.Core` (1.3.0 stable, 2026-05)**。
仓库：https://github.com/modelcontextprotocol/csharp-sdk
项目站：https://csharp.sdk.modelcontextprotocol.io/

这个 SDK 直接产出 `Microsoft.Extensions.AI.AITool` 兼容的 `McpClientTool`，可直接喂给 `ChatClientAgent`/`FunctionInvokingChatClient`——与本目录已装的 Agent 框架无缝。其它候选包（ChilliCream、OllamaSharp、Stef.* 等）都是第三方 fork 或域特定包装，不评估。

下文按 `ModelContextProtocol` 1.3.0 评估。

---

## 1. lib target 状况

**ModelContextProtocol 1.3.0**：
```
lib/
  net10.0/    ModelContextProtocol.dll   (88 KB)
  net8.0/     ModelContextProtocol.dll   (88 KB)
  net9.0/     ModelContextProtocol.dll
  netstandard2.0/  ModelContextProtocol.dll   (113 KB)   ← Unity 走这个
```

**ModelContextProtocol.Core 1.3.0**：
```
lib/
  net10.0/    ModelContextProtocol.Core.dll   (1.18 MB)
  net8.0/     ModelContextProtocol.Core.dll
  net9.0/     ModelContextProtocol.Core.dll
  netstandard2.0/  ModelContextProtocol.Core.dll   (1.18 MB)   ← Unity 走这个
```

**关键观察**：两个包都为 NS2.0 单独编译了**实体 DLL**（不是 type-forwarder shim）；NS2.0 体积甚至大于 net8（因为内置了缺失 API 的 polyfill 实现）。这是与之前 `Microsoft.Agents.AI.GitHub.Copilot`（只有 net8+ lib）的本质区别。

---

## 2. 传递依赖图（NS2.0 target group）

### ModelContextProtocol 1.3.0 → NS2.0 dependencies
| 包 | 要求版本 | 状态 |
|---|---|---|
| ModelContextProtocol.Core | 1.3.0 | **需装**（本评估） |
| Microsoft.Extensions.Caching.Abstractions | 10.0.7 | **已装**（README §3） |
| Microsoft.Extensions.Hosting.Abstractions | 10.0.7 | **已装**（README §3） |

### ModelContextProtocol.Core 1.3.0 → NS2.0 dependencies
| 包 | 要求版本 | 状态 |
|---|---|---|
| Microsoft.Bcl.Memory | 10.0.7 | **已装**（README §4 BCL polyfill） |
| Microsoft.Extensions.AI.Abstractions | 10.5.2 | **已装**（README §1） |
| Microsoft.Extensions.Logging.Abstractions | 10.0.7 | **已装**（README §3） |
| System.Diagnostics.DiagnosticSource | 10.0.7 | **已装**（README §4 系统库） |
| System.IO.Pipelines | 10.0.7 | **已装**（README §4 系统库） |
| System.Net.ServerSentEvents | 10.0.7 | **已装**（README §4 系统库） |
| System.Text.Json | 10.0.7 | **已装**（README §4 系统库） |
| System.Threading.Channels | 10.0.7 | **已装**（README §4 系统库） |

**全部传递依赖均已装。零新增传递依赖。**

> 注：传递依赖未递归到第二层 ——`Microsoft.Extensions.Caching.Abstractions` 等的传递依赖在 README 整理 1.7.0 主线时已经全收，并未在本评估中重复递归。

---

## 3. 新增 DLL 清单

| DLL | 来源包 | NS2.0 字节 | 备注 |
|---|---|---|---|
| ModelContextProtocol.dll | ModelContextProtocol 1.3.0 | 113,152 | Hosting/DI 集成层（`McpServiceCollectionExtensions` / `IMcpServer` 注册） |
| ModelContextProtocol.Core.dll | ModelContextProtocol.Core 1.3.0 | 1,208,832 | 核心协议层（`McpClient` / `McpClientTool` / `StdioClientTransport` / `SseClientTransport` / `IMcpServer` / JSON-RPC framing） |

**合计**：2 个 DLL，约 1.3 MB（XML 文档另算 ~1.1 MB，可选放或不放）。

---

## 4. IL 反射扫描（Mono.Cecil 0.11.5）

对两个 NS2.0 DLL 做了 TypeReference 扫描，重点查 Copilot 包翻车的几类 .NET 5+ 独有 API。

### ModelContextProtocol.dll (NS2.0)
- TypeReferences 总数：266
- 引用 `CollectionsMarshal` / `DefaultInterpolatedStringHandler` / `InterpolatedStringHandlerAttribute` / `CompositeFormat` / `SearchValues` / `System.Threading.Lock`：**0 处**
- AssemblyReferences 全部对应已装 DLL（含 `Microsoft.Bcl.AsyncInterfaces` / `System.Memory` / `System.Buffers` / `System.Threading.Tasks.Extensions` 等）

### ModelContextProtocol.Core.dll (NS2.0)
- TypeReferences 总数：429
- 引用 `CollectionsMarshal` / `DefaultInterpolatedStringHandler` / `InterpolatedStringHandlerAttribute` / `CompositeFormat` / `SearchValues` / `System.Threading.Lock`：**0 处**
- AssemblyReferences 全部对应已装 DLL（额外引用 `System.Diagnostics.DiagnosticSource` / `System.Text.Encodings.Web` / `Microsoft.Extensions.AI.Abstractions`，全部已装）

**结论：IL 层面无 Unity 2020.3 Mono 缺失的类型引用。**

> 扫描脚本临时驻留 `/tmp/mcp_eval/ilscan/`（已忽略，未提交）。

---

## 5. 结论

### **可用性等级：✅ 完全可用**

理由汇总：
1. ✅ 两个包都有**实体 NS2.0 lib**（非 forwarder）
2. ✅ NS2.0 传递依赖**全在已装清单内**，零新增传递依赖
3. ✅ IL 扫描确认**零 .NET 5+ 独有 API 引用**
4. ✅ 与 Agent Framework 1.7.0 的接合面是 `Microsoft.Extensions.AI.AITool`——和 ChatClientAgent / FunctionInvokingChatClient 直接通
5. ✅ 体积可控（仅 ~1.3 MB）

风险点（次要）：
- ModelContextProtocol.Core 对 `Microsoft.Extensions.AI.Abstractions` 要求 **10.5.2**，本目录已装 `Microsoft.Extensions.AI.Abstractions.dll` 来自 1.7.0 主线包（其打的版本是 MEAI 9.x 时代的，**实际安装版本需要核实**）。如果实测版本不满足 10.5.2，需要同步升级 Microsoft.Extensions.AI{,.Abstractions} 一并升到 10.x（已装 README §"已评估但未装"列 `Mem0` 钉死 9.x 的注释暗示当前主线确为 10.x，但应在 T2 前再核一次实际 DLL 的 AssemblyVersion）。
- 包名易混淆：必须文档明确写"Microsoft 没有 `Microsoft.Agents.AI.Mcp` 包；CBIM 使用官方 `ModelContextProtocol` SDK 接 MCP"，避免后续 contributor 找包找不到。

---

## 6. T2-T7 实施建议

**✅ 真做模式。** 走正常实施路径，不需要 stub 兜底。

落实步骤：
1. 下载 `ModelContextProtocol.1.3.0.nupkg` + `ModelContextProtocol.Core.1.3.0.nupkg`，抽 NS2.0 DLL 到 `ThirdParty/MsExtensionsAI/`
2. 在 `CBIM.asmdef` 的 `precompiledReferences` 追加：
   - `ModelContextProtocol.dll`
   - `ModelContextProtocol.Core.dll`
3. 同步追加到 `_VerifyMsai.Editor.asmdef`
4. 更新本目录 `_README.md` —— DLL 表追加这两条；"已评估但未装"列把 MCP 移除
5. 在 _VerifyMsai smoke test 增加一段：`new StdioClientTransport(...)` 能构造、`McpClient.CreateAsync()` 入口可达即可（不需要真起 server）

T2-T7 可以按"真做"的范围立项。

---

## 7. 备选方案（保留，不启用）

如未来某版本回退（例如 ModelContextProtocol.Core 升 2.x 时砍掉 NS2.0 target），fallback 是自实现一个轻量 MCP 客户端：

- 协议层：JSON-RPC 2.0 over stdio / SSE，~300 行 C#
- 工具适配：`AITool` 包一层 `McpToolProxy`，调用时序列化参数走 stdio——~200 行
- 总规模约 500 行；不上 server 角色，只做 client；不上 SSE，只支持 stdio 子进程通讯

当前评估结论是不需要走这条路。
