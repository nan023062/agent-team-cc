using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using CBIM.Memory.Bridge.Tools;

namespace CBIM.Memory.Bridge
{
    /// <summary>
    /// <see cref="IMemoryService"/> 的 MCP（Model Context Protocol）stdio 桥——
    /// 在一个进程里对外提供 <c>memory_write / memory_query / memory_get / memory_scan / memory_stats</c>
    /// 五个工具，让外部 LLM 客户端（例如 ClaudeCode subprocess）通过 stdin/stdout 走 JSON-RPC 2.0
    /// 调用 CBIM 的中期记忆。
    ///
    /// <para><b>定位：</b>只是 wrap，不持业务逻辑——不做权限校验、不做配额、不做生命周期管理；
    /// 这些归调用方（task-5 AgentSystem.OpenInstanceAsync）控制。本类的唯一职责是「把 MCP 协议帧
    /// 译成对 <see cref="IMemoryService"/> 的五个方法调用」。</para>
    ///
    /// <para><b>协议子集：</b>实现 MCP 必备的握手三件套——
    /// <c>initialize</c> / <c>tools/list</c> / <c>tools/call</c>，配合 <c>notifications/initialized</c>
    /// 与 <c>ping</c> 两个空操作。不实现 resources / prompts / 采样回调。</para>
    ///
    /// <para><b>传输：</b>仅 stdio（每行一个 JSON-RPC 帧，行尾 LF）。MCP 规范允许 line-delimited
    /// JSON 与 LSP-style Content-Length 两种帧；本实现选行分隔（最简，最广兼容）。</para>
    ///
    /// <para><b>退出条件：</b>stdin EOF（对端关闭）或外部 <c>CancellationToken</c> 取消，二者任一即清理退出。</para>
    /// </summary>
    public sealed class MemoryBridgeMcpServer : IAsyncDisposable
    {
        // MCP 协议本身是版本化的；我们声明支持的版本。当前公开版本 = 2024-11-05。
        private const string McpProtocolVersion = "2024-11-05";

        // JSON-RPC 2.0 标准错误码（节选）
        private const int ErrParseError = -32700;
        private const int ErrInvalidRequest = -32600;
        private const int ErrMethodNotFound = -32601;
        private const int ErrInvalidParams = -32602;
        private const int ErrInternal = -32603;

        private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
        {
            WriteIndented = false,
        };

        private readonly IMemoryService _memory;
        private readonly MemoryBridgeMcpServerConfig _config;
        private readonly Dictionary<string, IMemoryBridgeTool> _tools;
        private CancellationTokenSource _cts;
        private bool _disposed;

        /// <summary>
        /// 构造 server，绑定上游 <see cref="IMemoryService"/>。
        /// </summary>
        /// <param name="memory">中期记忆服务实例（per-Agent）；不为 null。</param>
        /// <param name="config">协议握手字段；null 走默认（serverName=cbim-memory-bridge-mcp / version=1.0.0）。</param>
        public MemoryBridgeMcpServer(IMemoryService memory, MemoryBridgeMcpServerConfig config = null)
        {
            _memory = memory ?? throw new ArgumentNullException(nameof(memory));
            _config = (config ?? new MemoryBridgeMcpServerConfig()).Validate();
            _tools = BuildToolTable(memory);
        }

        /// <summary>
        /// 在调用方进程里运行 MCP server——从 <c>Console.In</c> 读 JSON-RPC 帧，回到 <c>Console.Out</c>。
        /// 直到外部 <paramref name="ct"/> 取消或 stdin EOF 才返回；任何单个请求的异常都被译成
        /// JSON-RPC error 帧而不会拖垮 loop。
        /// </summary>
        /// <param name="ct">外部取消信号（如 client 端 CloseInstanceAsync 触发）。</param>
        public Task RunAsync(CancellationToken ct = default)
        {
            return RunAsync(Console.In, Console.Out, ct);
        }

        /// <summary>
        /// 测试 / 嵌入入口——传入任意 <see cref="TextReader"/>/<see cref="TextWriter"/>（例如内存管道），
        /// 用同一套 loop 跑。生产路径走的就是 <c>Console.In</c>/<c>Console.Out</c> 重载。
        /// </summary>
        public async Task RunAsync(TextReader input, TextWriter output, CancellationToken ct)
        {
            if (input == null) throw new ArgumentNullException(nameof(input));
            if (output == null) throw new ArgumentNullException(nameof(output));

            ThrowIfDisposed();

            // 内置 cts 串联外部 ct，DisposeAsync 时也能切断。
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct);
            _cts = linked;

            try
            {
                while (!linked.IsCancellationRequested)
                {
                    string line;
                    try
                    {
                        line = await input.ReadLineAsync().ConfigureAwait(false);
                    }
                    catch (Exception) when (linked.IsCancellationRequested)
                    {
                        return;
                    }

                    if (line == null)
                    {
                        // EOF——对端关闭 stdin，按 MCP 约定退出。
                        return;
                    }

                    if (line.Length == 0)
                    {
                        // 空行容忍——某些 client 会发心跳空行。
                        continue;
                    }

                    string response = ProcessLine(line);
                    if (response != null)
                    {
                        await output.WriteLineAsync(response).ConfigureAwait(false);
                        await output.FlushAsync().ConfigureAwait(false);
                    }
                }
            }
            finally
            {
                _cts = null;
            }
        }

        /// <summary>
        /// 处理单条 JSON-RPC 帧——返回应写回的响应字符串；notification（无 id）返回 null（不回复）。
        /// 解析失败时返回 JSON-RPC parse error 帧。
        /// </summary>
        internal string ProcessLine(string line)
        {
            JsonNode root;
            try
            {
                root = JsonNode.Parse(line);
            }
            catch (JsonException ex)
            {
                return BuildError(null, ErrParseError, "解析 JSON 失败：" + ex.Message);
            }

            var req = root as JsonObject;
            if (req == null)
            {
                return BuildError(null, ErrInvalidRequest, "请求必须是 JSON 对象");
            }

            // id 可为 null（notification）、字符串或数字——按原节点透传。
            JsonNode id = req["id"];
            bool isNotification = id == null;

            string method = (req["method"] is JsonValue mv && mv.TryGetValue<string>(out var ms)) ? ms : null;
            if (string.IsNullOrEmpty(method))
            {
                return isNotification ? null : BuildError(id, ErrInvalidRequest, "缺少 'method' 字段");
            }

            JsonNode @params = req["params"];

            try
            {
                JsonNode result = DispatchMethod(method, @params, isNotification);
                if (isNotification) return null;
                // result 允许为 null（理论上不会，但兜底）→ 序列化成 JSON null
                return BuildResult(id, result);
            }
            catch (McpProtocolException pex)
            {
                return isNotification ? null : BuildError(id, pex.Code, pex.Message);
            }
            catch (ArgumentException aex)
            {
                return isNotification ? null : BuildError(id, ErrInvalidParams, aex.Message);
            }
            catch (FormatException fex)
            {
                return isNotification ? null : BuildError(id, ErrInvalidParams, fex.Message);
            }
            catch (Exception ex)
            {
                return isNotification ? null : BuildError(id, ErrInternal, ex.GetType().Name + ": " + ex.Message);
            }
        }

        // ===== JSON-RPC 方法分发 =====

        private JsonNode DispatchMethod(string method, JsonNode @params, bool isNotification)
        {
            switch (method)
            {
                case "initialize":
                    return HandleInitialize(@params);

                case "notifications/initialized":
                case "initialized":
                    // 通知，无返回值；isNotification 时根本不响应。
                    return new JsonObject();

                case "ping":
                    return new JsonObject();

                case "tools/list":
                    return HandleToolsList();

                case "tools/call":
                    return HandleToolsCall(@params);

                default:
                    throw new McpProtocolException(ErrMethodNotFound, "未实现的方法：" + method);
            }
        }

        private JsonNode HandleInitialize(JsonNode @params)
        {
            // 不验证 client 端协议版本——MCP 标准让 server 在 result 里回报自己支持的版本，
            // 由 client 决定是否继续。我们也把客户端版本当 best-effort 信息丢弃。
            return new JsonObject
            {
                ["protocolVersion"] = McpProtocolVersion,
                ["capabilities"] = new JsonObject
                {
                    // 只声明 tools 能力——明确告诉客户端 resources / prompts / sampling 一律没有。
                    ["tools"] = new JsonObject
                    {
                        ["listChanged"] = false,
                    },
                },
                ["serverInfo"] = new JsonObject
                {
                    ["name"] = _config.ServerName,
                    ["version"] = _config.ServerVersion,
                },
            };
        }

        private JsonNode HandleToolsList()
        {
            var arr = new JsonArray();
            foreach (var tool in _tools.Values)
            {
                arr.Add(new JsonObject
                {
                    ["name"] = tool.Name,
                    ["description"] = tool.Description,
                    ["inputSchema"] = tool.BuildInputSchema(),
                });
            }
            return new JsonObject { ["tools"] = arr };
        }

        private JsonNode HandleToolsCall(JsonNode @params)
        {
            var po = @params as JsonObject;
            if (po == null)
                throw new McpProtocolException(ErrInvalidParams, "tools/call 需要 params 对象");

            string name = (po["name"] is JsonValue nv && nv.TryGetValue<string>(out var ns)) ? ns : null;
            if (string.IsNullOrEmpty(name))
                throw new McpProtocolException(ErrInvalidParams, "tools/call 缺少 'name' 字段");

            if (!_tools.TryGetValue(name, out var tool))
                throw new McpProtocolException(ErrMethodNotFound, "未注册的工具：" + name);

            JsonNode args = po["arguments"];

            // 执行工具——输入级异常按 MCP 规约转为 result.isError=true（而非 JSON-RPC error 层），
            // 让 LLM 能看见错误内容并自我修正。
            try
            {
                JsonNode handled = tool.Handle(args, JsonOptions);
                string serialized = handled == null ? "null" : handled.ToJsonString(JsonOptions);
                return new JsonObject
                {
                    ["content"] = new JsonArray
                    {
                        new JsonObject
                        {
                            ["type"] = "text",
                            ["text"] = serialized,
                        },
                    },
                    ["isError"] = false,
                };
            }
            catch (ArgumentException aex)
            {
                return BuildToolErrorResult(aex.Message);
            }
            catch (FormatException fex)
            {
                return BuildToolErrorResult(fex.Message);
            }
        }

        private static JsonObject BuildToolErrorResult(string message)
        {
            // 工具内部的输入校验失败——以工具结果错误形式返回，附带错误描述
            // 给 LLM 看。这与 JSON-RPC 系统错误（method 不存在等）分开。
            return new JsonObject
            {
                ["content"] = new JsonArray
                {
                    new JsonObject
                    {
                        ["type"] = "text",
                        ["text"] = message,
                    },
                },
                ["isError"] = true,
            };
        }

        // ===== JSON-RPC 帧构造 =====

        private static string BuildResult(JsonNode id, JsonNode result)
        {
            var frame = new JsonObject
            {
                ["jsonrpc"] = "2.0",
                ["id"] = id?.DeepClone(),
                ["result"] = result ?? new JsonObject(),
            };
            return frame.ToJsonString(JsonOptions);
        }

        private static string BuildError(JsonNode id, int code, string message)
        {
            var frame = new JsonObject
            {
                ["jsonrpc"] = "2.0",
                ["id"] = id?.DeepClone(),
                ["error"] = new JsonObject
                {
                    ["code"] = code,
                    ["message"] = message ?? string.Empty,
                },
            };
            return frame.ToJsonString(JsonOptions);
        }

        // ===== 工具表 =====

        private static Dictionary<string, IMemoryBridgeTool> BuildToolTable(IMemoryService memory)
        {
            // 显式列举 5 个——避免反射；新增 / 删减一目了然。
            var tools = new IMemoryBridgeTool[]
            {
                new MemoryWriteTool(memory),
                new MemoryQueryTool(memory),
                new MemoryGetTool(memory),
                new MemoryScanTool(memory),
                new MemoryStatsTool(memory),
            };
            var table = new Dictionary<string, IMemoryBridgeTool>(tools.Length, StringComparer.Ordinal);
            foreach (var t in tools) table[t.Name] = t;
            return table;
        }

        // ===== Dispose =====

        /// <summary>
        /// 取消正在运行的 loop（如果有）；多次调用幂等。<see cref="IMemoryService"/> 的生命周期不归本类
        /// 管理——调用方自行 dispose。
        /// </summary>
        public ValueTask DisposeAsync()
        {
            if (_disposed) return default;
            _disposed = true;

            try
            {
                _cts?.Cancel();
            }
            catch (ObjectDisposedException)
            {
                // 已被 RunAsync 的 using 释放——无需再处理。
            }
            return default;
        }

        private void ThrowIfDisposed()
        {
            if (_disposed) throw new ObjectDisposedException(nameof(MemoryBridgeMcpServer));
        }

        // ===== 私有异常类——区分「方法级错误」与「参数级错误」====

        private sealed class McpProtocolException : Exception
        {
            public int Code { get; }
            public McpProtocolException(int code, string message) : base(message)
            {
                Code = code;
            }
        }
    }
}
