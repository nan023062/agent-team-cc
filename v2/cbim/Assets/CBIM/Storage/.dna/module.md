---
name: cbim-unity-storage
owner: architect
description: 本地 IO 原语：原子写 / JSON 快照 / append-only trace。root path 由调用方注入 （去 Unity 耦合），可在 Unity 环境默认 Application.persistentDataPath/.cbim，亦可在纯 C# Edit Mode 指临时目录。依赖图最底层。
keywords: []
dependencies: []
status: spec
---
## Positioning

C# 移植的文件系统原语层。CBIM 唯一调用 `System.IO` 的模块。原子写、JSON 序列化、append-only trace、路径解析。

**本轮变动**：root path 由调用方注入，不再硬编码 `Application.persistentDataPath`——彻底解 Unity 耦合。Unity 场景层在 Composition Root 注入 `Application.persistentDataPath/.cbim/`，纯 C# 测试 / CLI 注入临时目录或自定义路径。

## Responsibility（一句话）

给高层一份小而平台中立的 IO 表面。

## Contract Surface

```csharp
namespace CBIM.Storage;

public sealed class FileBackend
{
    public FileBackend(string rootPath);    // 调用方注入根路径

    string ResolvePath(params string[] segments);  // 拼到 root 之下，确保父目录存在
    void WriteAtomic(string path, string content);  // 先写 .tmp 后 rename
    string? ReadOrNull(string path);
    void AppendLine(string path, string line);
    void Delete(string path);
    bool Exists(string path);
}

public static class StorageJson
{
    string Serialize<T>(T obj);
    T Deserialize<T>(string json);
}
```

## Internal Decisions

1. **原子写 = 写 `.tmp` 然后 rename**——扛 Unity Editor 域重载。
2. **JSON 助手内置**——避免每个消费方各引一次 Newtonsoft / System.Text.Json。
3. **root path 注入构造器**——纯 C# 测试 / Unity 主线 / CLI 可各自指定根。
4. **不引用 `UnityEngine`**——`Application.persistentDataPath` 由 Unity 侧 Composition Root 读取后注入。

## Dependencies

无。本模块是依赖图最底层。`CBIM.Storage.asmdef` 的 `references: []` 永远为空，不引用 `UnityEngine`。

## Not in this module

- 记忆条目 schema（归 `Memory/`）
- 模块 / Agent 描述 schema（归 `Workspace/` / `AgentSystem/`）
- 任何「session」/「agent」/「流程图」概念
- IO 工具（Agent 与外部世界交互）——`SystemTools/` 已整体废弃，由 Microsoft AIFunction 生态接管

## Mirror in Python kernel

对应 Python 侧 `v1/kernel/engine/persistence/snapshot.py` + `v1/kernel/memory/crud/*` 的原子写部分。C# 移植合并为一个 Storage 模块，比 Python 侧更干净。
