---
name: cbim-unity-storage
owner: architect
description: File-system primitives: atomic writes, JSON snapshot, append-only trace log. Stable bottom layer — no deps on Memory or Kernel.
keywords: []
dependencies: []
status: spec
---

## Positioning

C# 移植的文件系统原语层。Unity 侧 CBIM **唯一**调用 `System.IO` 的模块。承载原子写、JSON 快照、append-only trace 日志，以及以 `Application.persistentDataPath` 为根的路径解析。**不感知** `.dna/` 概念、**不感知**记忆条目结构、**不感知** BT 引擎概念——那些都属于更高层。

## Responsibility（一句话）

给高层一个小而平台可移植的 IO 表面，让它们再不必自己去调 `File.WriteAllText`。

## Contract Surface（规划）

暴露一个公共类 `FileBackend`（或拆为 `FileBackend` + `PathResolver` 两个），承载以下方法：

| 方法 | 用途 |
|------|------|
| `string ResolveCbimPath(params string[] segments)` | 把分段拼到 `Application.persistentDataPath/.cbim/` 之下并确保父目录存在 |
| `void WriteAtomic(string path, string content)` | 先写后改名；能扛 Unity Editor 写到一半触发域重载的场景 |
| `string ReadOrNull(string path)` | 文件不存在返回 null，只在真正 IO 异常时抛 |
| `void AppendLine(string path, string line)` | JSONL trace 的 append-only 写入 |
| `void Delete(string path)` | 文件不存在视为成功 |
| `bool Exists(string path)` |  |

文件命名与目录布局由调用方（Memory / Kernel）决定；Storage 不知道 `bb.json` 或一条 `memory short` 文件**是什么**。

## Internal Decisions

1. **原子写 = 写 `<path>.tmp` 然后 `File.Move`。** 真正要防的失败模式是 Unity Editor 写到一半触发域重载——不是断电。
2. **JSON 序列化助手放在本模块**，不放 Kernel/Memory。因为 asmdef 已经引用 `com.unity.nuget.newtonsoft-json`，统一一个 `Storage.Json` 静态类（Serialize / Deserialize<T>）能避免每个消费方各自再 import 一次依赖。
3. **根路径默认 `Application.persistentDataPath/.cbim/`**；构造器接受路径覆盖参数（让 Edit Mode 测试能指向临时目录）。

## Dependencies

无。本模块是依赖图最底层。`CBIM.Storage.asmdef` 的 `references: []` 永远保持为空。

## Not in this module

- 记忆条目 schema（归 `Memory/`）
- 黑板 / Tick 目录布局（归 `Kernel/`）
- 任何 "session" / "agent" / "流程图" 概念

## Mirror in Python kernel

对应的 Python 关注点散落在 `v1/kernel/engine/persistence/snapshot.py` 与 `v1/kernel/memory/crud/*`（其中的原子写部分）。C# 移植把它们合并成一个 Storage 模块——比 Python 那侧切得更干净。能这么切是因为 Unity 移植可以从零开始，直接拿正确的边界落地。
