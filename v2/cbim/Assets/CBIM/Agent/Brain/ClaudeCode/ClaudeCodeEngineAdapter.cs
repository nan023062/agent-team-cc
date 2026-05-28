using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace CBIM.AgentSystem.Brain.ClaudeCode
{
    /// <summary>
    /// 把对 Claude Code CLI 的调用收敛到一处的 <see cref="IExternalEngineAdapter"/> 实现。
    ///
    /// <para>一次 Submit 启一个 subprocess（CLI 路径 / WorkingDirectory / stream-json 输出），
    /// 一次 Await 等其退出再解析 transcript + git diff，转译为
    /// <see cref="BrainOutcome"/>。Adapter 内部维护 jobId → <see cref="ClaudeCodeJob"/> 字典。</para>
    ///
    /// <para>「Adapter 不起 MCP server」铁律：本类仅消费 <see cref="ClaudeCodeAdapterConfig.MemoryMcpEndpoint"/>——
    /// task-5 装配胶水期把 cbim-memory-bridge-mcp 的 stdio command 透传进来；
    /// 本类把它写进一份 --mcp-config 临时文件即可。</para>
    ///
    /// <para>「Dispose 必须强制收尾」铁律：所有未退出的 subprocess 在 DisposeAsync
    /// 中被 Kill（Windows 下额外用 taskkill /T /F 杀整棵进程树），5 秒内若仍未退出则强行返回。</para>
    /// </summary>
    public sealed class ClaudeCodeEngineAdapter : IExternalEngineAdapter
    {
        private const string McpServerName = "cbim-memory-bridge-mcp";
        private static readonly TimeSpan DisposeGracePeriod = TimeSpan.FromSeconds(5);
        private static readonly TimeSpan TranscriptFlushGrace = TimeSpan.FromSeconds(1);

        private readonly ClaudeCodeAdapterConfig _config;
        private readonly Dictionary<string, ClaudeCodeJob> _jobs = new Dictionary<string, ClaudeCodeJob>();
        private readonly object _lock = new object();
        private int _disposed;

        public ClaudeCodeEngineAdapter(ClaudeCodeAdapterConfig config)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _config.Validate();

            EnsureCliInPath(_config.CliPath);
        }

        /// <inheritdoc/>
        public Task<string> SubmitAsync(BrainInvocation invocation, CancellationToken ct)
        {
            if (_disposed != 0)
                throw new ObjectDisposedException(nameof(ClaudeCodeEngineAdapter));
            if (invocation == null)
                throw new ArgumentNullException(nameof(invocation));
            ct.ThrowIfCancellationRequested();

            var jobId = Guid.NewGuid().ToString("N");
            var transcriptDirAbs = Path.Combine(_config.WorkspaceRoot, _config.TranscriptDir);
            Directory.CreateDirectory(transcriptDirAbs);
            var transcriptPath = Path.Combine(transcriptDirAbs, jobId + ".jsonl");

            // 提前创建空文件——OutputDataReceived 流式追加不会 race。
            File.WriteAllText(transcriptPath, string.Empty);

            string? mcpConfigPath = null;
            if (!string.IsNullOrWhiteSpace(_config.MemoryMcpEndpoint))
            {
                mcpConfigPath = Path.Combine(transcriptDirAbs, jobId + ".mcp.json");
                WriteMcpConfig(mcpConfigPath!, _config.MemoryMcpEndpoint!);
            }

            var psi = BuildStartInfo(invocation.Intent, mcpConfigPath);
            var process = new Process
            {
                StartInfo = psi,
                EnableRaisingEvents = true,
            };

            var transcriptWriter = new StreamWriter(
                new FileStream(transcriptPath, FileMode.Append, FileAccess.Write, FileShare.Read),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            transcriptWriter.AutoFlush = true;

            var stderrBuffer = new StringBuilder();

            process.OutputDataReceived += (sender, e) =>
            {
                if (e.Data == null) return;
                lock (transcriptWriter)
                {
                    transcriptWriter.WriteLine(e.Data);
                }
            };
            process.ErrorDataReceived += (sender, e) =>
            {
                if (e.Data == null) return;
                lock (stderrBuffer)
                {
                    stderrBuffer.AppendLine(e.Data);
                }
            };

            var job = new ClaudeCodeJob(jobId, process, transcriptPath, invocation, DateTimeOffset.UtcNow);

            process.Exited += (sender, args) =>
            {
                try { transcriptWriter.Dispose(); } catch { /* ignore */ }
                // Process.ExitCode 在 EnableRaisingEvents=true + Exited 触发时可读。
                try { job.ExitTcs.TrySetResult(process.ExitCode); }
                catch (InvalidOperationException) { job.ExitTcs.TrySetResult(-1); }
            };

            if (!process.Start())
            {
                transcriptWriter.Dispose();
                throw new InvalidOperationException(
                    $"启动 Claude Code CLI 失败（CliPath='{_config.CliPath}'）。");
            }
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            lock (_lock)
            {
                _jobs[jobId] = job;
            }

            return Task.FromResult(jobId);
        }

        /// <inheritdoc/>
        public async Task<BrainOutcome> AwaitResultAsync(string jobId, CancellationToken ct)
        {
            if (_disposed != 0)
                throw new ObjectDisposedException(nameof(ClaudeCodeEngineAdapter));
            if (string.IsNullOrWhiteSpace(jobId))
                throw new ArgumentException("jobId 不能为空", nameof(jobId));

            ClaudeCodeJob job;
            lock (_lock)
            {
                if (!_jobs.TryGetValue(jobId, out var found))
                    return ErrorOutcome($"未知 jobId '{jobId}'——可能已被回收。");
                job = found;
            }

            bool timedOut = false;
            try
            {
                using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                cts.CancelAfter(_config.Timeout);
                await WaitWithCancellationAsync(job.ExitTcs.Task, cts.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested)
            {
                // 超时——不抛，作为 IsError BrainOutcome 返回。
                timedOut = true;
                TryKillProcessTree(job.Process);
                // 等 Exited 事件落地（最多 1 秒），让 transcript 写完。
                try
                {
                    using var graceCts = new CancellationTokenSource(TranscriptFlushGrace);
                    await WaitWithCancellationAsync(job.ExitTcs.Task, graceCts.Token).ConfigureAwait(false);
                }
                catch { /* ignore */ }
            }
            catch (OperationCanceledException)
            {
                // 上游显式取消——杀掉子进程后抛回去（语义保留）。
                TryKillProcessTree(job.Process);
                throw;
            }

            string summary;
            List<SideEffect> sideEffects;
            try
            {
                (summary, sideEffects) = ParseTranscript(job.TranscriptPath);
            }
            catch (Exception ex)
            {
                summary = string.Empty;
                sideEffects = new List<SideEffect>
                {
                    new SideEffect(
                        Kind: "transcript-parse-error",
                        Target: job.TranscriptPath,
                        Detail: ex.Message,
                        At: DateTimeOffset.UtcNow),
                };
            }

            // git diff 摘要——尽力而为；不是 git 仓库则跳过。
            var diffSummary = TryCaptureGitDiff(_config.WorkspaceRoot);
            if (diffSummary != null)
            {
                sideEffects.Add(new SideEffect(
                    Kind: "git-diff",
                    Target: _config.WorkspaceRoot,
                    Detail: diffSummary,
                    At: DateTimeOffset.UtcNow));
            }

            int exitCode;
            try { exitCode = job.Process.ExitCode; }
            catch { exitCode = -1; }

            lock (_lock)
            {
                _jobs.Remove(jobId);
            }
            try { job.Process.Dispose(); } catch { /* ignore */ }

            bool isError = timedOut || exitCode != 0;
            string? errorMessage = timedOut
                ? $"claude-code 超时 ({_config.Timeout})，已 Kill 进程树。"
                : (exitCode != 0 ? $"claude-code 退出码 {exitCode}。" : null);

            return new BrainOutcome(
                Summary: summary,
                StructuredOutput: null,
                SideEffects: sideEffects,
                IsError: isError,
                ErrorMessage: errorMessage);
        }

        /// <inheritdoc/>
        public async ValueTask DisposeAsync()
        {
            if (Interlocked.Exchange(ref _disposed, 1) != 0) return;

            List<ClaudeCodeJob> snapshot;
            lock (_lock)
            {
                snapshot = _jobs.Values.ToList();
                _jobs.Clear();
            }

            foreach (var job in snapshot)
            {
                TryKillProcessTree(job.Process);
            }

            if (snapshot.Count > 0)
            {
                var waitAll = Task.WhenAll(snapshot.Select(j => j.ExitTcs.Task));
                try
                {
                    using var graceCts = new CancellationTokenSource(DisposeGracePeriod);
                    await WaitWithCancellationAsync(waitAll, graceCts.Token).ConfigureAwait(false);
                }
                catch { /* 5 秒后强行返回——不让 Dispose 卡死调用方 */ }
            }

            foreach (var job in snapshot)
            {
                try { job.Process.Dispose(); } catch { /* ignore */ }
            }
        }

        // --- private helpers --------------------------------------------------

        /// <summary>
        /// .NET Standard 2.0 / Framework 4.7.1 缺 <c>Task.WaitAsync</c>——用 WhenAny + Delay 模拟。
        /// token 触发时抛 <see cref="OperationCanceledException"/>；task 先完成则正常返回。
        /// </summary>
        private static async Task WaitWithCancellationAsync(Task task, CancellationToken token)
        {
            if (task.IsCompleted)
            {
                await task.ConfigureAwait(false);
                return;
            }

            var tcs = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            using (token.Register(state => ((TaskCompletionSource<bool>)state!).TrySetResult(true), tcs))
            {
                var finished = await Task.WhenAny(task, tcs.Task).ConfigureAwait(false);
                if (finished == tcs.Task)
                    throw new OperationCanceledException(token);
            }
            await task.ConfigureAwait(false);
        }

        private static void EnsureCliInPath(string cliPath)
        {
            // 绝对路径直接验文件存在。
            if (Path.IsPathRooted(cliPath))
            {
                if (!File.Exists(cliPath))
                    throw new InvalidOperationException(
                        $"Claude Code CLI 未找到（CliPath='{cliPath}'）。");
                return;
            }

            bool isWindows = RuntimeInformation.IsOSPlatform(OSPlatform.Windows);
            var probeFile = isWindows ? "where" : "which";
            try
            {
                using var probe = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = probeFile,
                        Arguments = QuoteArg(cliPath),
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true,
                    },
                };
                probe.Start();
                if (!probe.WaitForExit(5000))
                {
                    try { probe.Kill(); } catch { /* ignore */ }
                    throw new InvalidOperationException(
                        $"探测 Claude Code CLI 超时（探测命令 '{probeFile} {cliPath}'）。");
                }
                if (probe.ExitCode != 0)
                    throw new InvalidOperationException(
                        $"Claude Code CLI 在 PATH 中未找到（CliPath='{cliPath}'）。" +
                        $"探测命令 '{probeFile} {cliPath}' 退出码 {probe.ExitCode}。");
            }
            catch (InvalidOperationException) { throw; }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"无法探测 Claude Code CLI（CliPath='{cliPath}'）: {ex.Message}", ex);
            }
        }

        private ProcessStartInfo BuildStartInfo(string intent, string? mcpConfigPath)
        {
            var psi = new ProcessStartInfo
            {
                FileName = _config.CliPath,
                WorkingDirectory = _config.WorkspaceRoot,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };

            // 顺序：ExtraArgs（用户自定义）→ 内置参数。
            // .NET Standard 2.0 / Framework 4.7.1 无 ArgumentList——手写 quoting 拼接到 Arguments。
            var args = new List<string>(_config.ExtraArgs.Count + 5);
            foreach (var a in _config.ExtraArgs)
                args.Add(a);
            if (mcpConfigPath != null)
            {
                args.Add("--mcp-config");
                args.Add(mcpConfigPath);
            }
            args.Add("-p");
            args.Add(intent);
            args.Add("--output-format");
            args.Add("stream-json");

            psi.Arguments = string.Join(" ", args.Select(QuoteArg));
            return psi;
        }

        /// <summary>
        /// 跨平台命令行参数 quoting（Win32 CommandLineToArgvW 兼容规则）：
        /// 内含空格 / tab / 引号 / 反斜杠 时用双引号包裹；内部反斜杠按 MSVCRT 规则转义。
        /// </summary>
        private static string QuoteArg(string arg)
        {
            if (arg == null) return "\"\"";
            if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"', '\\' }) < 0)
                return arg;

            var sb = new StringBuilder();
            sb.Append('"');
            for (int i = 0; i < arg.Length; i++)
            {
                int backslashes = 0;
                while (i < arg.Length && arg[i] == '\\')
                {
                    backslashes++;
                    i++;
                }
                if (i == arg.Length)
                {
                    sb.Append('\\', backslashes * 2);
                    break;
                }
                if (arg[i] == '"')
                {
                    sb.Append('\\', backslashes * 2 + 1);
                    sb.Append('"');
                }
                else
                {
                    sb.Append('\\', backslashes);
                    sb.Append(arg[i]);
                }
            }
            sb.Append('"');
            return sb.ToString();
        }

        private static void WriteMcpConfig(string path, string command)
        {
            // 把 endpoint 整串当作 command 写入（task-5 注入的 stdio 启动命令）。
            // 后续若需 args 拆分，由 task-5 注入端把命令转 JSON 后写入。
            var doc = new
            {
                mcpServers = new Dictionary<string, object>
                {
                    [McpServerName] = new { command = command }
                }
            };
            var json = JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = false });
            File.WriteAllText(path, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        }

        private static (string Summary, List<SideEffect> SideEffects) ParseTranscript(string transcriptPath)
        {
            var sideEffects = new List<SideEffect>();
            string finalAssistantText = string.Empty;

            if (!File.Exists(transcriptPath))
                return (finalAssistantText, sideEffects);

            foreach (var line in File.ReadLines(transcriptPath))
            {
                if (string.IsNullOrWhiteSpace(line)) continue;

                JsonDocument doc;
                try { doc = JsonDocument.Parse(line); }
                catch { continue; }

                using (doc)
                {
                    var root = doc.RootElement;
                    if (root.ValueKind != JsonValueKind.Object) continue;

                    var type = root.TryGetProperty("type", out var t) && t.ValueKind == JsonValueKind.String
                        ? t.GetString()
                        : null;

                    if (type == "assistant" &&
                        root.TryGetProperty("message", out var msg) &&
                        msg.ValueKind == JsonValueKind.Object &&
                        msg.TryGetProperty("content", out var content) &&
                        content.ValueKind == JsonValueKind.Array)
                    {
                        var sb = new StringBuilder();
                        foreach (var block in content.EnumerateArray())
                        {
                            if (block.ValueKind != JsonValueKind.Object) continue;
                            var blockType = block.TryGetProperty("type", out var bt) && bt.ValueKind == JsonValueKind.String
                                ? bt.GetString()
                                : null;

                            if (blockType == "text" &&
                                block.TryGetProperty("text", out var textProp) &&
                                textProp.ValueKind == JsonValueKind.String)
                            {
                                sb.Append(textProp.GetString());
                            }
                            else if (blockType == "tool_use")
                            {
                                var toolName = block.TryGetProperty("name", out var n) && n.ValueKind == JsonValueKind.String
                                    ? n.GetString() ?? string.Empty
                                    : string.Empty;
                                var input = block.TryGetProperty("input", out var inp) ? inp : default;
                                var (target, detail) = ExtractToolUseTarget(toolName, input);
                                sideEffects.Add(new SideEffect(
                                    Kind: MapToolNameToKind(toolName),
                                    Target: target,
                                    Detail: detail,
                                    At: DateTimeOffset.UtcNow));
                            }
                        }

                        var text = sb.ToString();
                        if (!string.IsNullOrWhiteSpace(text))
                            finalAssistantText = text; // 取最后一条 assistant 文本
                    }
                    else if (type == "result" &&
                             root.TryGetProperty("result", out var resultProp) &&
                             resultProp.ValueKind == JsonValueKind.String)
                    {
                        // 部分 CLI 版本会在末尾再输出 "result" 行——若有，覆盖为最终摘要。
                        var resultText = resultProp.GetString();
                        if (!string.IsNullOrWhiteSpace(resultText))
                            finalAssistantText = resultText!;
                    }
                }
            }

            return (finalAssistantText, sideEffects);
        }

        private static string MapToolNameToKind(string toolName)
        {
            return toolName switch
            {
                "Edit" or "Write" or "MultiEdit" => "file-write",
                "Bash" => "process-spawn",
                "Read" or "Glob" or "Grep" => "file-read",
                _ => "tool-use",
            };
        }

        private static (string Target, string? Detail) ExtractToolUseTarget(string toolName, JsonElement input)
        {
            if (input.ValueKind != JsonValueKind.Object)
                return (toolName, null);

            // 常见参数：file_path / path / command。
            if (input.TryGetProperty("file_path", out var fp) && fp.ValueKind == JsonValueKind.String)
                return (fp.GetString() ?? toolName, null);
            if (input.TryGetProperty("path", out var p) && p.ValueKind == JsonValueKind.String)
                return (p.GetString() ?? toolName, null);
            if (input.TryGetProperty("command", out var c) && c.ValueKind == JsonValueKind.String)
                return (toolName, c.GetString());

            return (toolName, null);
        }

        private static string? TryCaptureGitDiff(string workspaceRoot)
        {
            try
            {
                var args = string.Join(" ", new[] { "-C", workspaceRoot, "diff", "--stat", "HEAD" }.Select(QuoteArg));
                using var proc = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "git",
                        Arguments = args,
                        WorkingDirectory = workspaceRoot,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true,
                    },
                };
                if (!proc.Start()) return null;
                var stdout = proc.StandardOutput.ReadToEnd();
                if (!proc.WaitForExit(3000))
                {
                    try { proc.Kill(); } catch { /* ignore */ }
                    return null;
                }
                if (proc.ExitCode != 0) return null;
                return string.IsNullOrWhiteSpace(stdout) ? null : stdout.Trim();
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 杀进程树——.NET Framework 4.7.1 / .NET Standard 2.0 无 <c>Process.Kill(bool)</c>。
        /// Windows 走 <c>taskkill /T /F /PID</c> 杀整棵树；POSIX 退回 <c>Process.Kill()</c>
        /// （CLI 子进程一般跟随父进程退出；如有遗漏属 v1 已知妥协）。
        /// </summary>
        private static void TryKillProcessTree(Process process)
        {
            int pid;
            try { pid = process.Id; }
            catch { pid = 0; }

            try
            {
                if (process.HasExited) return;
            }
            catch { return; }

            if (pid > 0 && RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                try
                {
                    using var killer = new Process
                    {
                        StartInfo = new ProcessStartInfo
                        {
                            FileName = "taskkill",
                            Arguments = $"/T /F /PID {pid}",
                            UseShellExecute = false,
                            CreateNoWindow = true,
                            RedirectStandardOutput = true,
                            RedirectStandardError = true,
                        },
                    };
                    killer.Start();
                    killer.WaitForExit(3000);
                    return;
                }
                catch { /* taskkill 缺失或失败——退回 Process.Kill() */ }
            }

            try { process.Kill(); }
            catch { /* 已退出 / 已 Dispose / 无权限——忽略 */ }
        }

        private static BrainOutcome ErrorOutcome(string message) =>
            new BrainOutcome(
                Summary: string.Empty,
                StructuredOutput: null,
                SideEffects: Array.Empty<SideEffect>(),
                IsError: true,
                ErrorMessage: message);
    }
}
