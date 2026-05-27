using System;
using System.IO;

namespace CBIM.AgentSystem.StandardTools
{
    // 路径规范化 + 沙箱包含性校验。
    //
    // 契约：
    //   - 输入必须是非空的绝对路径。相对路径直接拒绝
    //     （沙箱内 LLM 始终应以绝对路径思考）。
    //   - 返回值是 `Path.GetFullPath(input)`——折叠 ".." 段、规范化分隔符。
    //     符号链接不会被解析（GetFullPath 不跟随），但包含性是基于规范化后的字符串
    //     做的判断，因此 "/allowed/link-to-outside" 这种路径在文本层面仍位于白名单内；
    //     真正的访问控制由操作系统对链接目标的 ACL 来强制。
    //   - 包含性判断使用带显式分隔符边界的前缀匹配，
    //     所以沙箱 "/foo" 不会放行 "/foobar/x"（防前缀碰撞）。
    //
    // 失败行为：抛 UnauthorizedAccessException。工具方法必须让它继续往上传——
    // FunctionInvokingChatClient 会捕获它并触发安全中止。
    public static class PathGuard
    {
        public static string Normalize(string path, ToolSandbox sandbox)
        {
            if (sandbox == null)
            {
                throw new ArgumentNullException(nameof(sandbox));
            }
            if (string.IsNullOrEmpty(path))
            {
                throw new UnauthorizedAccessException("path is empty");
            }
            if (!Path.IsPathRooted(path))
            {
                throw new UnauthorizedAccessException(
                    "path must be absolute: " + path);
            }

            string full;
            try
            {
                full = Path.GetFullPath(path);
            }
            catch (Exception ex)
            {
                throw new UnauthorizedAccessException(
                    "path cannot be normalized: " + path + " (" + ex.Message + ")");
            }

            if (sandbox.AllowedPathPrefixes == null ||
                sandbox.AllowedPathPrefixes.Count == 0)
            {
                throw new UnauthorizedAccessException(
                    "sandbox has no allowed path prefixes; cannot access: " + full);
            }

            for (int i = 0; i < sandbox.AllowedPathPrefixes.Count; i++)
            {
                string prefix = sandbox.AllowedPathPrefixes[i];
                if (string.IsNullOrEmpty(prefix))
                {
                    continue;
                }
                string prefixFull;
                try
                {
                    prefixFull = Path.GetFullPath(prefix);
                }
                catch
                {
                    continue;
                }
                if (IsWithin(full, prefixFull))
                {
                    return full;
                }
            }

            throw new UnauthorizedAccessException(
                "path escapes sandbox: " + full);
        }

        // 当 `candidate` 等于 `prefix`，或严格位于其下且以目录分隔符为边界时返回 true。
        // 在 Windows（本项目 Unity 6 主要面向的平台）上比较不区分大小写；
        // 在大小写敏感的文件系统上，路径大小写不匹配本来就会被操作系统拒绝，
        // 所以这里的文本宽松化是安全的。
        private static bool IsWithin(string candidate, string prefix)
        {
            string c = TrimTrailingSeparator(candidate);
            string p = TrimTrailingSeparator(prefix);

            StringComparison cmp = IsWindowsLike()
                ? StringComparison.OrdinalIgnoreCase
                : StringComparison.Ordinal;

            if (c.Equals(p, cmp))
            {
                return true;
            }
            if (c.Length <= p.Length)
            {
                return false;
            }
            if (!c.StartsWith(p, cmp))
            {
                return false;
            }
            char boundary = c[p.Length];
            return boundary == Path.DirectorySeparatorChar ||
                   boundary == Path.AltDirectorySeparatorChar;
        }

        private static string TrimTrailingSeparator(string s)
        {
            if (string.IsNullOrEmpty(s))
            {
                return s;
            }
            int end = s.Length;
            while (end > 0)
            {
                char ch = s[end - 1];
                if (ch == Path.DirectorySeparatorChar ||
                    ch == Path.AltDirectorySeparatorChar)
                {
                    end--;
                }
                else
                {
                    break;
                }
            }
            return end == s.Length ? s : s.Substring(0, end);
        }

        private static bool IsWindowsLike()
        {
            return Path.DirectorySeparatorChar == '\\' ||
                   Path.AltDirectorySeparatorChar == '\\';
        }
    }
}
