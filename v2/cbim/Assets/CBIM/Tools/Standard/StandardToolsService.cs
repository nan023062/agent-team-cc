using System;
using System.Collections.Generic;
using System.Diagnostics;
using CBIM.Storage;
using Microsoft.Extensions.AI;

namespace CBIM.Tools.Standard
{
    // 无状态门面：把一组族名 + 沙箱转成一份扁平的 AIFunction 列表。
    // 没有任何可变静态状态——可以在任意线程并发调用。
    //
    // 族注册表是一张固定的 IToolFamilyFactory 表。要加新族就扩这张表；
    // 按设计不开放插件点（module.md "Iron Rule 1"）。
    public static class StandardToolsService
    {
        private static readonly IToolFamilyFactory[] Factories = new IToolFamilyFactory[]
        {
            new FilesFamilyFactory(),
            new SearchFamilyFactory()
        };

        public static IReadOnlyList<string> ListFamilies()
        {
            var names = new string[Factories.Length];
            for (int i = 0; i < Factories.Length; i++)
            {
                names[i] = Factories[i].Name;
            }
            return names;
        }

        public static IReadOnlyList<AIFunction> CreateFamily(
            string familyName,
            ToolSandbox sandbox,
            FileBackend storage = null)
        {
            if (sandbox == null) throw new ArgumentNullException(nameof(sandbox));
            if (string.IsNullOrEmpty(familyName))
            {
                throw new ArgumentException("familyName must be non-empty", nameof(familyName));
            }

            IToolFamilyFactory factory = FindFactory(familyName);
            if (factory == null)
            {
                throw new ArgumentException(
                    "unknown tool family: " + familyName +
                    " (known: " + string.Join(", ", AsArray(ListFamilies())) + ")",
                    nameof(familyName));
            }
            if (factory.RequiresStorage && storage == null)
            {
                throw new ArgumentException(
                    "family '" + factory.Name + "' requires a FileBackend storage instance",
                    nameof(storage));
            }
            return factory.Create(sandbox, storage);
        }

        public static IReadOnlyList<AIFunction> CreateFamilies(
            IEnumerable<string> familyNames,
            ToolSandbox sandbox,
            FileBackend storage = null)
        {
            if (familyNames == null) throw new ArgumentNullException(nameof(familyNames));
            if (sandbox == null) throw new ArgumentNullException(nameof(sandbox));

            var merged = new List<AIFunction>();
            var seenNames = new HashSet<string>(StringComparer.Ordinal);

            foreach (string raw in familyNames)
            {
                if (string.IsNullOrEmpty(raw)) continue;
                string familyName = raw.Trim();
                if (familyName.Length == 0) continue;

                IReadOnlyList<AIFunction> familyTools;
                try
                {
                    familyTools = CreateFamily(familyName, sandbox, storage);
                }
                catch (ArgumentException ex)
                {
                    Debug.WriteLine("[StandardTools] skipping family '" + familyName + "': " + ex.Message);
                    continue;
                }

                for (int i = 0; i < familyTools.Count; i++)
                {
                    AIFunction fn = familyTools[i];
                    string toolName = fn != null ? fn.Name : null;
                    if (string.IsNullOrEmpty(toolName))
                    {
                        merged.Add(fn);
                        continue;
                    }
                    if (!seenNames.Add(toolName))
                    {
                        Debug.WriteLine(
                            "[StandardTools] duplicate tool name '" + toolName +
                            "' from family '" + familyName + "' — keeping first occurrence");
                        continue;
                    }
                    merged.Add(fn);
                }
            }

            return merged;
        }

        private static IToolFamilyFactory FindFactory(string name)
        {
            for (int i = 0; i < Factories.Length; i++)
            {
                if (string.Equals(Factories[i].Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    return Factories[i];
                }
            }
            return null;
        }

        private static string[] AsArray(IReadOnlyList<string> list)
        {
            var arr = new string[list.Count];
            for (int i = 0; i < list.Count; i++) arr[i] = list[i];
            return arr;
        }

        private sealed class FilesFamilyFactory : IToolFamilyFactory
        {
            public string Name { get { return "Files"; } }
            public bool RequiresStorage { get { return true; } }
            public IReadOnlyList<AIFunction> Create(ToolSandbox sandbox, FileBackend storage)
            {
                return new FilesToolFamily(sandbox, storage).Build();
            }
        }

        private sealed class SearchFamilyFactory : IToolFamilyFactory
        {
            public string Name { get { return "Search"; } }
            public bool RequiresStorage { get { return false; } }
            public IReadOnlyList<AIFunction> Create(ToolSandbox sandbox, FileBackend storage)
            {
                return new SearchToolFamily(sandbox).Build();
            }
        }
    }
}
