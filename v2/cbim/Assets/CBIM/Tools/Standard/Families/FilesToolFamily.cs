using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Text;
using System.Text.Json;
using CBIM.Storage;
using Microsoft.Extensions.AI;

namespace CBIM.Tools.Standard
{
    // Files 工具族——5 个工具，让 agent 检视并修改沙箱内文件系统。
    // 所有入口都先把 path 参数过一遍 PathGuard；越界尝试会以
    // UnauthorizedAccessException 抛出（而不是 "ERROR:" 字符串），
    // 这样 FunctionInvokingChatClient 层可以硬中止调用链。
    //
    // 所有可恢复的失败（文件不存在、EditFile 命中多处、超出大小上限等）
    // 都返回 "ERROR: <kind>: <message>"——约定好的结构化错误形式，
    // 便于 LLM 自我纠正。
    public sealed class FilesToolFamily
    {
        private const int HeadProbeBytes = 8 * 1024;

        private readonly ToolSandbox _sandbox;
        private readonly FileBackend _storage;

        public FilesToolFamily(ToolSandbox sandbox, FileBackend storage)
        {
            _sandbox = sandbox ?? throw new ArgumentNullException(nameof(sandbox));
            _storage = storage ?? throw new ArgumentNullException(nameof(storage));
        }

        [Description("Read a UTF-8 text file. Binary files return a JSON metadata object instead of their contents. Large text files are truncated by line count and total bytes.")]
        public string ReadFile(
            [Description("Absolute path. Must lie inside the sandbox.")] string path,
            [Description("Maximum lines to return. 0 = no line cap (still subject to byte cap).")] int maxLines = 0,
            [Description("Line offset (0-indexed). Lines before this are skipped.")] int offset = 0)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            try
            {
                if (!File.Exists(full))
                {
                    return "ERROR: NotFound: file does not exist: " + full;
                }

                var info = new FileInfo(full);
                if (info.Length > _sandbox.MaxFileBytes)
                {
                    return "ERROR: TooLarge: file " + full + " is " + info.Length +
                           " bytes, exceeds MaxFileBytes=" + _sandbox.MaxFileBytes;
                }

                byte[] head = ReadHead(full, HeadProbeBytes);
                if (BinaryDetector.IsBinary(head))
                {
                    var meta = new Dictionary<string, object>
                    {
                        { "isBinary", true },
                        { "size", info.Length },
                        { "path", full }
                    };
                    return JsonSerializer.Serialize(meta);
                }

                string text = File.ReadAllText(full, Utf8NoBom);
                return TruncateByLines(text, offset, maxLines, _sandbox.MaxResultBytes);
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

        [Description("Write a UTF-8 text file atomically. Parent directories are created on demand. Overwrites any existing file at the path.")]
        public string WriteFile(
            [Description("Absolute path. Must lie inside the sandbox.")] string path,
            [Description("Full file contents.")] string content)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            try
            {
                if (IsBlockedExtension(full))
                {
                    return "ERROR: BlockedExtension: writing this file extension is not permitted: " + full;
                }
                string payload = content ?? string.Empty;
                _storage.WriteAtomic(full, payload);
                int bytes = Utf8NoBom.GetByteCount(payload);
                return "OK: wrote " + bytes + " bytes to " + full;
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

        [Description("Replace a single exact occurrence of oldStr with newStr in a UTF-8 text file. Fails if oldStr does not appear exactly once.")]
        public string EditFile(
            [Description("Absolute path. Must lie inside the sandbox.")] string path,
            [Description("Exact substring to find. Must appear exactly once in the file.")] string oldStr,
            [Description("Replacement substring.")] string newStr)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            try
            {
                if (IsBlockedExtension(full))
                {
                    return "ERROR: BlockedExtension: writing this file extension is not permitted: " + full;
                }
                if (!File.Exists(full))
                {
                    return "ERROR: NotFound: file does not exist: " + full;
                }
                if (oldStr == null || oldStr.Length == 0)
                {
                    return "ERROR: InvalidArgument: oldStr must be non-empty";
                }

                string existing = File.ReadAllText(full, Utf8NoBom);
                int count = CountOccurrences(existing, oldStr);
                if (count == 0)
                {
                    return "ERROR: NoMatch: oldStr not found in " + full;
                }
                if (count > 1)
                {
                    return "ERROR: AmbiguousMatch: oldStr appears " + count +
                           " times in " + full + "; oldStr must be unique";
                }

                int idx = existing.IndexOf(oldStr, StringComparison.Ordinal);
                string updated = existing.Substring(0, idx) + (newStr ?? string.Empty) +
                                 existing.Substring(idx + oldStr.Length);
                _storage.WriteAtomic(full, updated);
                return "OK: replaced 1 occurrence in " + full;
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

        [Description("Delete a file. A missing file is treated as success (idempotent).")]
        public string DeleteFile(
            [Description("Absolute path. Must lie inside the sandbox.")] string path)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            try
            {
                if (!File.Exists(full))
                {
                    return "OK: file already absent: " + full;
                }
                File.Delete(full);
                return "OK: deleted " + full;
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

        [Description("List a directory's immediate entries. Returns a JSON array of {name, isDir, size} sorted by name. size is -1 for directories.")]
        public string ListDirectory(
            [Description("Absolute directory path. Must lie inside the sandbox.")] string path)
        {
            string full = PathGuard.Normalize(path, _sandbox);

            try
            {
                if (!Directory.Exists(full))
                {
                    return "ERROR: NotFound: directory does not exist: " + full;
                }

                var entries = new List<Dictionary<string, object>>();

                string[] dirs = Directory.GetDirectories(full);
                Array.Sort(dirs, StringComparer.Ordinal);
                for (int i = 0; i < dirs.Length; i++)
                {
                    entries.Add(new Dictionary<string, object>
                    {
                        { "name", Path.GetFileName(dirs[i]) },
                        { "isDir", true },
                        { "size", -1L }
                    });
                }

                string[] files = Directory.GetFiles(full);
                Array.Sort(files, StringComparer.Ordinal);
                for (int i = 0; i < files.Length; i++)
                {
                    long size;
                    try { size = new FileInfo(files[i]).Length; }
                    catch { size = -1L; }
                    entries.Add(new Dictionary<string, object>
                    {
                        { "name", Path.GetFileName(files[i]) },
                        { "isDir", false },
                        { "size", size }
                    });
                }

                return JsonSerializer.Serialize(entries);
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

        // Unity 2020.3 的 C# 表面不支持方法组到 Delegate 的隐式转换，
        // 所以每个方法都用显式 Func<> 强转包一层。
        // 详见 _MSAI_ClassReference.md 中 "AIFunctionFactory.Create" 一节。
        public IReadOnlyList<AIFunction> Build()
        {
            return new AIFunction[]
            {
                AIFunctionFactory.Create((Func<string, int, int, string>)ReadFile),
                AIFunctionFactory.Create((Func<string, string, string>)WriteFile),
                AIFunctionFactory.Create((Func<string, string, string, string>)EditFile),
                AIFunctionFactory.Create((Func<string, string>)DeleteFile),
                AIFunctionFactory.Create((Func<string, string>)ListDirectory)
            };
        }

        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        private static byte[] ReadHead(string path, int maxBytes)
        {
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                long len = Math.Min(fs.Length, maxBytes);
                byte[] buf = new byte[len];
                int read = 0;
                while (read < buf.Length)
                {
                    int n = fs.Read(buf, read, buf.Length - read);
                    if (n <= 0) break;
                    read += n;
                }
                if (read == buf.Length) return buf;
                byte[] trimmed = new byte[read];
                Array.Copy(buf, trimmed, read);
                return trimmed;
            }
        }

        private static int CountOccurrences(string haystack, string needle)
        {
            if (string.IsNullOrEmpty(haystack) || string.IsNullOrEmpty(needle))
            {
                return 0;
            }
            int count = 0;
            int idx = 0;
            while (true)
            {
                int hit = haystack.IndexOf(needle, idx, StringComparison.Ordinal);
                if (hit < 0) break;
                count++;
                idx = hit + needle.Length;
            }
            return count;
        }

        private static string TruncateByLines(string text, int offset, int maxLines, long maxResultBytes)
        {
            if (text == null) return string.Empty;

            string[] lines = text.Split('\n');
            int start = offset < 0 ? 0 : offset;
            if (start >= lines.Length)
            {
                return "[empty: offset " + offset + " past end of file (" + lines.Length + " lines)]";
            }

            int end = (maxLines > 0)
                ? Math.Min(lines.Length, start + maxLines)
                : lines.Length;

            var sb = new StringBuilder();
            long byteBudget = maxResultBytes > 0 ? maxResultBytes : long.MaxValue;
            bool byteTruncated = false;
            int emitted = 0;

            for (int i = start; i < end; i++)
            {
                string ln = lines[i];
                int approxBytes = Utf8NoBom.GetByteCount(ln) + 1;
                if (sb.Length > 0 && byteBudget - approxBytes < 0)
                {
                    byteTruncated = true;
                    break;
                }
                if (i > start) sb.Append('\n');
                sb.Append(ln);
                byteBudget -= approxBytes;
                emitted++;
            }

            bool lineTruncated = end < lines.Length;
            if (lineTruncated || byteTruncated)
            {
                sb.Append('\n');
                sb.Append("[truncated: emitted ").Append(emitted)
                  .Append(" of ").Append(lines.Length).Append(" lines");
                if (byteTruncated)
                {
                    sb.Append(", byte cap reached");
                }
                sb.Append("]");
            }
            return sb.ToString();
        }

        private bool IsBlockedExtension(string path)
        {
            if (_sandbox.BlockedExtensions == null || _sandbox.BlockedExtensions.Count == 0)
            {
                return false;
            }
            string ext = Path.GetExtension(path);
            if (string.IsNullOrEmpty(ext)) return false;
            for (int i = 0; i < _sandbox.BlockedExtensions.Count; i++)
            {
                if (string.Equals(_sandbox.BlockedExtensions[i], ext, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }
    }
}
