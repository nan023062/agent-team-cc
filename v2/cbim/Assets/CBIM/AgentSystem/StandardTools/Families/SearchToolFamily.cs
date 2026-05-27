using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.FileSystemGlobbing;

namespace CBIM.AgentSystem.StandardTools
{
    // Search 工具族——纯 C# 实现的 Grep + Glob，不启动外部进程。
    //
    // Grep：
    //   - .NET Regex，按行处理。
    //   - 如果 `path` 是目录则递归（跳过隐藏目录和 .git）。
    //   - 输出行格式 "file:line: content"；当 context > 0 时，
    //     前后上下文行以 "file-line- content" 前缀（ripgrep 约定），
    //     不同命中组之间用 "--" 分隔。
    //
    // Glob：
    //   - Microsoft.Extensions.FileSystemGlobbing.Matcher——支持 "**/*.cs"、
    //     "src/**/*.{cs,json}" 等。每行返回一个绝对路径。
    public sealed class SearchToolFamily
    {
        private readonly ToolSandbox _sandbox;

        public SearchToolFamily(ToolSandbox sandbox)
        {
            _sandbox = sandbox ?? throw new ArgumentNullException(nameof(sandbox));
        }

        [Description("Search files for lines matching a .NET regular expression. Returns one match per line in 'file:line: content' form. Recurses into directories.")]
        public string Grep(
            [Description(".NET regular expression.")] string pattern,
            [Description("Absolute path to a file or directory. Must lie inside the sandbox.")] string path,
            [Description("Case-insensitive match when true.")] bool ignoreCase = false,
            [Description("Lines of context to include before and after each match. 0 = no context.")] int context = 0,
            [Description("Maximum matches to return. 0 = no cap (still subject to byte cap).")] int maxMatches = 100)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            if (string.IsNullOrEmpty(pattern))
            {
                return "ERROR: InvalidArgument: pattern must be non-empty";
            }

            Regex regex;
            try
            {
                var opts = RegexOptions.CultureInvariant | RegexOptions.Compiled;
                if (ignoreCase) opts |= RegexOptions.IgnoreCase;
                regex = new Regex(pattern, opts);
            }
            catch (ArgumentException ex)
            {
                return "ERROR: InvalidPattern: " + ex.Message;
            }

            try
            {
                bool isFile = File.Exists(full);
                bool isDir = Directory.Exists(full);
                if (!isFile && !isDir)
                {
                    return "ERROR: NotFound: " + full;
                }

                int contextN = context < 0 ? 0 : context;
                long byteBudget = _sandbox.MaxResultBytes > 0 ? _sandbox.MaxResultBytes : long.MaxValue;
                var sb = new StringBuilder();
                int matches = 0;
                bool capped = false;

                if (isFile)
                {
                    GrepFile(full, regex, contextN, maxMatches, ref matches, ref capped,
                             sb, ref byteBudget);
                }
                else
                {
                    foreach (string file in EnumerateFiles(full))
                    {
                        if (capped) break;
                        GrepFile(file, regex, contextN, maxMatches, ref matches, ref capped,
                                 sb, ref byteBudget);
                    }
                }

                if (matches == 0)
                {
                    return "[no matches]";
                }
                if (capped)
                {
                    sb.Append('\n').Append("[truncated: limits reached after ")
                      .Append(matches).Append(" matches]");
                }
                return sb.ToString();
            }
            catch (UnauthorizedAccessException)
            {
                throw;
            }
            catch (Exception ex)
            {
                return "ERROR: " + ex.GetType().Name + ": " + ex.Message;
            }
        }

        [Description("Find files matching a glob pattern (e.g. '**/*.cs', 'src/**/*.{cs,json}'). Returns one absolute path per line.")]
        public string Glob(
            [Description("Glob pattern, relative to root. Supports ** and brace expansion.")] string pattern,
            [Description("Absolute search root. Must lie inside the sandbox.")] string root)
        {
            string fullRoot = PathGuard.Normalize(root, _sandbox);

            if (string.IsNullOrEmpty(pattern))
            {
                return "ERROR: InvalidArgument: pattern must be non-empty";
            }

            try
            {
                if (!Directory.Exists(fullRoot))
                {
                    return "ERROR: NotFound: directory does not exist: " + fullRoot;
                }

                var matcher = new Matcher(StringComparison.OrdinalIgnoreCase);
                matcher.AddInclude(pattern);

                var result = matcher.GetResultsInFullPath(fullRoot);

                long byteBudget = _sandbox.MaxResultBytes > 0 ? _sandbox.MaxResultBytes : long.MaxValue;
                var sb = new StringBuilder();
                int emitted = 0;
                bool capped = false;
                var sorted = new List<string>(result);
                sorted.Sort(StringComparer.Ordinal);

                for (int i = 0; i < sorted.Count; i++)
                {
                    string p = sorted[i];
                    int approxBytes = Encoding.UTF8.GetByteCount(p) + 1;
                    if (sb.Length > 0 && byteBudget - approxBytes < 0)
                    {
                        capped = true;
                        break;
                    }
                    if (emitted > 0) sb.Append('\n');
                    sb.Append(p);
                    byteBudget -= approxBytes;
                    emitted++;
                }

                if (emitted == 0)
                {
                    return "[no matches]";
                }
                if (capped)
                {
                    sb.Append('\n').Append("[truncated: byte cap reached after ")
                      .Append(emitted).Append(" of ").Append(sorted.Count).Append(" paths]");
                }
                return sb.ToString();
            }
            catch (UnauthorizedAccessException)
            {
                throw;
            }
            catch (Exception ex)
            {
                return "ERROR: " + ex.GetType().Name + ": " + ex.Message;
            }
        }

        public IReadOnlyList<AIFunction> Build()
        {
            return new AIFunction[]
            {
                AIFunctionFactory.Create((Func<string, string, bool, int, int, string>)Grep),
                AIFunctionFactory.Create((Func<string, string, string>)Glob)
            };
        }

        private static IEnumerable<string> EnumerateFiles(string root)
        {
            var stack = new Stack<string>();
            stack.Push(root);
            while (stack.Count > 0)
            {
                string dir = stack.Pop();
                string[] subs;
                try { subs = Directory.GetDirectories(dir); }
                catch { continue; }
                Array.Sort(subs, StringComparer.Ordinal);
                for (int i = subs.Length - 1; i >= 0; i--)
                {
                    string name = Path.GetFileName(subs[i]);
                    if (string.IsNullOrEmpty(name)) continue;
                    if (name[0] == '.') continue;
                    if (string.Equals(name, "node_modules", StringComparison.OrdinalIgnoreCase)) continue;
                    stack.Push(subs[i]);
                }

                string[] files;
                try { files = Directory.GetFiles(dir); }
                catch { continue; }
                Array.Sort(files, StringComparer.Ordinal);
                for (int i = 0; i < files.Length; i++)
                {
                    yield return files[i];
                }
            }
        }

        private static void GrepFile(
            string file,
            Regex regex,
            int context,
            int maxMatches,
            ref int matches,
            ref bool capped,
            StringBuilder sb,
            ref long byteBudget)
        {
            string[] lines;
            try
            {
                if (IsLikelyBinary(file)) return;
                lines = File.ReadAllLines(file);
            }
            catch
            {
                return;
            }

            int lastEmittedLine = -1;
            for (int i = 0; i < lines.Length; i++)
            {
                if (!regex.IsMatch(lines[i])) continue;

                if (matches > 0 && context > 0 && lastEmittedLine >= 0 && lastEmittedLine < i - context - 1)
                {
                    if (!AppendLine(sb, "--", ref byteBudget)) { capped = true; return; }
                }

                int ctxStart = Math.Max(0, i - context);
                int ctxEnd = Math.Min(lines.Length - 1, i + context);

                for (int j = ctxStart; j < i; j++)
                {
                    if (j <= lastEmittedLine) continue;
                    if (!AppendLine(sb, file + "-" + (j + 1) + "- " + lines[j], ref byteBudget))
                    { capped = true; return; }
                    lastEmittedLine = j;
                }
                if (!AppendLine(sb, file + ":" + (i + 1) + ": " + lines[i], ref byteBudget))
                { capped = true; return; }
                lastEmittedLine = i;

                for (int j = i + 1; j <= ctxEnd; j++)
                {
                    if (!AppendLine(sb, file + "-" + (j + 1) + "- " + lines[j], ref byteBudget))
                    { capped = true; return; }
                    lastEmittedLine = j;
                }

                matches++;
                if (maxMatches > 0 && matches >= maxMatches)
                {
                    capped = true;
                    return;
                }
            }
        }

        private static bool AppendLine(StringBuilder sb, string line, ref long byteBudget)
        {
            int approxBytes = Encoding.UTF8.GetByteCount(line) + 1;
            if (sb.Length > 0 && byteBudget - approxBytes < 0)
            {
                return false;
            }
            if (sb.Length > 0) sb.Append('\n');
            sb.Append(line);
            byteBudget -= approxBytes;
            return true;
        }

        private static bool IsLikelyBinary(string file)
        {
            try
            {
                using (var fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read))
                {
                    int probeLen = (int)Math.Min(fs.Length, 8 * 1024);
                    if (probeLen <= 0) return false;
                    byte[] buf = new byte[probeLen];
                    int read = 0;
                    while (read < probeLen)
                    {
                        int n = fs.Read(buf, read, probeLen - read);
                        if (n <= 0) break;
                        read += n;
                    }
                    if (read < probeLen)
                    {
                        byte[] trimmed = new byte[read];
                        Array.Copy(buf, trimmed, read);
                        return BinaryDetector.IsBinary(trimmed);
                    }
                    return BinaryDetector.IsBinary(buf);
                }
            }
            catch
            {
                return true;
            }
        }
    }
}
