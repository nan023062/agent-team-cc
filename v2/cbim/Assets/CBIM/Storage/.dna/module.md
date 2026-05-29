---
name: cbim-unity-storage
owner: architect
description: 本地 IO 原语：原子写 / JSON 快照 / append-only trace。root path 由调用方注入 （去 Unity 耦合），可在 Unity 环境默认 Application.persistentDataPath/.cbim，亦可在纯 C# Edit Mode 指临时目录。依赖图最底层。
keywords: []
dependencies: []
status: spec
---

## Positioning

- **依赖图最底层 IO 原语**——CBIM 唯一调用 `System.IO` 的模块。
- 三件能力：**原子写** + **JSON 序列化** + **append-only trace**。
- **root path 由调用方注入**——Unity 侧、纯 C# 测试、CLI 各自注入，不硬编码 `Application.persistentDataPath`。
- **不引用 `UnityEngine`**——`CBIM.Storage.asmdef` 依赖永远为空。
- **不持 schema / agent / module 概念**——只提供平台中立的 IO 表面。

## 架构图（依赖图最底层）

```mermaid
flowchart TD
    classDef self    fill:#fce4ec,stroke:#880e4f,stroke-width:2px,color:#000;
    classDef infra   fill:#fff9c4,stroke:#f57f17,color:#000;
    classDef sys     fill:#bbdefb,stroke:#0d47a1,color:#000;
    classDef boot    fill:#f3e5f5,stroke:#4a148c,color:#000;

    subgraph CONS["上层消费者"]
        MEM["CBIM.Memory\nFileMemoryBackend"]
        SKL["CBIM.Skills\nFileSkillStore"]
        MCP["CBIM.Mcp\nFileMcpStore"]
        TLS["CBIM.Tools.Standard\nFiles family"]
        AS["CBIM.AgentSystem\nAgentDescription / Session"]
        WS["CBIM.Workspace\nModuleDescription"]
    end

    subgraph SELF["本模块 · 基建层最底"]
        FB["FileBackend\n(WriteAtomic / Read / Append / Resolve)"]
        SJ["StorageJson\n(Serialize / Deserialize)"]
    end

    subgraph BOOT["Composition Root"]
        UR["Unity Bootstrap\nApplication.persistentDataPath/.cbim"]
        CR["CLI / Test Bootstrap\n临时目录"]
    end

    subgraph SYSTEM[".NET"]
        IO["System.IO\n(File / Directory / Path)"]
    end

    MEM --> FB
    SKL --> FB
    MCP --> FB
    TLS --> FB
    AS --> FB
    AS --> SJ
    WS --> FB
    WS --> SJ
    MEM --> SJ
    SKL --> SJ
    MCP --> SJ

    UR -. 注入 rootPath .-> FB
    CR -. 注入 rootPath .-> FB

    FB --> IO

    class FB,SJ self;
    class MEM,SKL,MCP,TLS,AS,WS infra;
    class IO sys;
    class UR,CR boot;
```

**依赖方向**：所有上层 → `CBIM.Storage` → `System.IO`。本模块不反向引用任何 CBIM 同级模块。

## 类图

```mermaid
classDiagram
    class FileBackend {
        +FileBackend(string rootPath)
        +ResolvePath(segments) string
        +WriteAtomic(path, content) void
        +ReadOrNull(path) string
        +AppendLine(path, line) void
        +Delete(path) void
        +Exists(path) bool
    }

    class StorageJson {
        <<static>>
        +Serialize~T~(obj) string
        +Deserialize~T~(json) T
    }

    class FileMemoryBackend {
        <<from CBIM.Memory>>
    }
    class FileSkillStore {
        <<from CBIM.Skills>>
    }
    class FileMcpStore {
        <<from CBIM.Mcp>>
    }
    class FilesToolFamily {
        <<from CBIM.Tools.Standard>>
    }

    FileMemoryBackend --> FileBackend
    FileSkillStore --> FileBackend
    FileMcpStore --> FileBackend
    FilesToolFamily --> FileBackend
    FileMemoryBackend ..> StorageJson
    FileSkillStore ..> StorageJson
    FileMcpStore ..> StorageJson
```

**关键关系**：FileBackend 提供平安 IO；StorageJson 提供统一序列化——避免消费方各引一次 Newtonsoft / System.Text.Json。

## 原子写序列

```mermaid
sequenceDiagram
    participant Caller as 消费方
    participant FB as FileBackend
    participant FS as System.IO

    Caller->>FB: WriteAtomic(path, content)
    FB->>FS: File.WriteAllText(path + ".tmp", content)
    FB->>FS: File.Move(path + ".tmp", path, overwrite: true)
    FB-->>Caller: ok

    Note over FB,FS: 域重载 / 进程崩潰中途中断
    Note over FB,FS: 只会丢 .tmp，原文件完整
```

## Contract Surface

```csharp
namespace CBIM.Storage;

public sealed class FileBackend
{
    public FileBackend(string rootPath);    // 调用方注入根路径

    public string ResolvePath(params string[] segments);  // 拼到 root 之下，确保父目录存在
    public void WriteAtomic(string path, string content); // 先写 .tmp 后 rename
    public string? ReadOrNull(string path);
    public void AppendLine(string path, string line);
    public void Delete(string path);
    public bool Exists(string path);
}

public static class StorageJson
{
    public static string Serialize<T>(T obj);
    public static T Deserialize<T>(string json);
}
```

## Dependencies

无。本模块是依赖图最底层。`CBIM.Storage.asmdef` 的 `references: []` 永远为空，不引用 `UnityEngine`。

## 铁律

- **C1 · 原子写 = 先写 `.tmp` 然后 rename**——扶 Unity Editor 域重载 / 进程崩潰下不丢原文件。
- **C2 · JSON 助手内置**——避免每个消费方各引一次 Newtonsoft / System.Text.Json。
- **C3 · root path 注入构造器**——不硬编码 Unity 路径；测试 / 主线 / CLI 可各自指定。
- **C4 · 不引用 `UnityEngine`**——`Application.persistentDataPath` 由 Unity 侧 Composition Root 读取后注入。
- **C5 · 不持任何上层概念**——没有 session / agent / 流程图 / schema。

## Non-Goals

- 不处理记忆条目 schema（归 `Memory/`）。
- 不处理模块 / Agent 描述 schema（归 `AgentSystem/` / `Workspace/`）。
- 不提供 session / agent / 流程图 概念。
- 不提供 IO 工具（过去的 `SystemTools/` 已废除，由 Microsoft AIFunction 生态接管）。

