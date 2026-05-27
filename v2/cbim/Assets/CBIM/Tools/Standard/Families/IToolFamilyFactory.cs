using System.Collections.Generic;
using CBIM.Storage;
using Microsoft.Extensions.AI;

namespace CBIM.Tools.Standard
{
    // 工具族工厂的内部契约。每个族对应一个实现；
    // StandardToolsService 的分派表以名字（大小写不敏感）做键。
    // 不需要持久化存储的族直接忽略 `storage` 参数即可。
    internal interface IToolFamilyFactory
    {
        string Name { get; }
        bool RequiresStorage { get; }
        IReadOnlyList<AIFunction> Create(ToolSandbox sandbox, FileBackend storage);
    }
}
