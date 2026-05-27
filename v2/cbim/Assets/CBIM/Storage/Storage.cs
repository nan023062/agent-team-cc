using System;
using System.IO;
using System.Text;

namespace CBIM.Storage
{
    // CBIM 的文件系统存储原语。
    //
    // 根目录由调用方提供。CBIM 是纯 .NET 库，不假设任何特定宿主环境——
    // Unity、.NET CLI、服务端进程、测试都需要自己构造根路径并注入这里。
    public class FileBackend
    {
        private readonly string _root;

        public FileBackend(string root)
        {
            if (string.IsNullOrEmpty(root))
            {
                throw new ArgumentNullException(nameof(root));
            }
            _root = root;
        }

        public string ResolveCbimPath(params string[] segments)
        {
            string full = _root;
            if (segments != null)
            {
                for (int i = 0; i < segments.Length; i++)
                {
                    string seg = segments[i];
                    if (string.IsNullOrEmpty(seg))
                    {
                        continue;
                    }
                    full = Path.Combine(full, seg);
                }
            }

            string parent = Path.GetDirectoryName(full);
            if (!string.IsNullOrEmpty(parent) && !Directory.Exists(parent))
            {
                Directory.CreateDirectory(parent);
            }
            return full;
        }

        public void WriteAtomic(string path, string content)
        {
            EnsureParent(path);
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, content ?? string.Empty, Utf8NoBom);
            if (File.Exists(path))
            {
                File.Replace(tmp, path, null);
            }
            else
            {
                File.Move(tmp, path);
            }
        }

        public string ReadOrNull(string path)
        {
            if (!File.Exists(path))
            {
                return null;
            }
            return File.ReadAllText(path, Utf8NoBom);
        }

        public void AppendLine(string path, string line)
        {
            EnsureParent(path);
            using (var fs = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read))
            using (var sw = new StreamWriter(fs, Utf8NoBom))
            {
                sw.Write(line);
                sw.Write('\n');
            }
        }

        public void Delete(string path)
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }

        public bool Exists(string path)
        {
            return File.Exists(path);
        }

        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        private static void EnsureParent(string path)
        {
            string parent = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(parent) && !Directory.Exists(parent))
            {
                Directory.CreateDirectory(parent);
            }
        }
    }
}
