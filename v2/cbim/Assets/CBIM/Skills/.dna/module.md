---
name: cbim-unity-skills
owner: architect
description: 基建层三抽象之「技能（Skill）」——本轮出两类抽象（1）描述符：SkillDescriptor（Id/Name/Description/Content · SKILL.md 风格内容）；（2）配置仓储：ISkillStore + FileSkillStore（默认本地后端，云后端预留）。不出「实例管理器」——Skill 是配置类资产（纯文本），「运行期实例」与「配置」同一物。能力侧 AgentDescription.Skills 与业务侧 ModuleDescription.Workflows 同抽象复用。
keywords: []
dependencies: []
status: spec
---

## Positioning

**Skills 是 CBIM 基建层四件套抽象之一**（v2 三层模型）——与 `Tools/` / `Mcp/` / `Memory/` 平级，同为顶层模块、同为「类型契约 / 抽象接口」。

**本轮重定位**：Skill 重新明确为「技能 / 工作流程描述的类型契约」——具体技能实例由 Agent 与 Workspace 各自派生持有。

本模块只承载**「技能」这个语义级抽象本身**：

- `SkillDescriptor`——技能描述符（Id / Name / Description / Content）。`Content` 是 SKILL.md 风格的使用指引 / 示例 / 注意事项，会被装配时注入 LLM 上下文。
- **Agent 侧与 Workspace 侧同抽象复用**：
  - `AgentDescription.Skills: IReadOnlyList<SkillDescriptor>`——agent 会的手艺。
  - `ModuleDescription.Workflows: IReadOnlyList<SkillDescriptor>`——同抽象在业务语境下叫「工作流」。

## 为什么「工作流 = 技能」

这是本轮重要裁决：**业务侧的 Workflow 与能力侧的 Skill 是同一抽象的业务别名**——不是两个独立抽象。

| 维度 | 语义 | 例 |
|------|------|------|
| Agent.Skills | 这个 agent 会什么手艺 | `code-review`、`pr-write`、`mermaid-diagram` |
| Module.Workflows | 这个业务 module 能走什么流程 | `cdn-upload`、`cdn-purge`、`cdn-stats-query` |

两者在**描述形态**上一致：都是「Id + 一句话用途 + SKILL.md 风格的详细描述」；LLM 看到描述都是「何时调 / 怎么调 / 有什么注意点」。语义区别仅在「归属不同」。

拒绝发明 `Workflow` 为独立类型——同抽象不应为了语义位置不同而重复描述。

## 在三大基础能力中的位置

```
CBIM 三大基础能力（顶层平级）：
  Tools/   ← 最小单位（AIFunction 直装）
  Skills/  ← 这里：语义级（Content 描述 · Skill 内可指引调 Tool）
  Mcp/     ← 协议级（外部 server / 远端 endpoint）
```

**Skill 与 Tool / Mcp 的关系**：

- Skill 本身**不直接挂 AIFunction**——Skill 是语义描述，含使用指引。
- Skill 描述里可以**语义上指引 LLM 何时调哪些 Tool / Mcp**（例：「pr-write 技能：请用 git-mcp 查看 diff，用 read_text 读 CHANGELOG」）。
- 运行期 LLM 看到 Skill 描述 + 可用 Tool / Mcp 列表后，自行决定调哪个。

所以 Skill **在语义上比 Tool / Mcp 高一级**，但在**描述抽象层**三者平级（AgentDescription 三字段并列引用）。

## 跨维度共享

`SkillDescriptor` 是 CBIM 的**跨维度共享抽象**之一：

| 使用侧 | 字段 | 语义 |
|--------|------|------|
| 能力维度 | `AgentDescription.Skills` | agent 会的手艺（跟人走） |
| 业务维度 | `ModuleDescription.Workflows` | 业务能走的流程（跟业务走） |

同抽象、同类型、同符号、同装配点（OpenInstance 合并 agent.Skills 与 module.Workflows 后一并注入 LLM 上下文），语义归属不同。

## Children

本模块**无下级**（leaf）。本轮新增后包含以下文件：

```
Skills/
├── SkillDescriptor.cs        ← 原有：描述符 POCO
├── ISkillStore.cs            ← 本轮新增：配置仓储接口
└── FileSkillStore.cs         ← 本轮新增：默认本地后端实现
```

**为什么不拆出子模块**：

- 三个文件的**演化频率一致**（SkillDescriptor / ISkillStore / FileSkillStore 同步变动）。
- 三者**使用上高度耦合**（Store 出 Descriptor，Store 的默认实现生产该抽象的唯一概徵才有意义）——符合 C5。
- 拆子模块会引入三个 `.dna/` + asmdef，为三个文件的高频联动增加杀伤过大。

后续可能出现的子模块（本轮不发）：

- `Cloud/`——云后端实现集（S3SkillStore / HttpSkillStore / CompositeSkillStore）。仅当云后端实现的体量 >2 文件 + 依赖云 SDK 时才拆出。
- `Loader/`——从某个目录加载 SKILL.md 转为 `SkillDescriptor` 实例的加载器。现阶段装配侧直读。

## Child Relationships

```mermaid
flowchart TD
    SD["SkillDescriptor\n(Id+Name+Description+Content)"]
    ISS["ISkillStore\n(配置仓储抽象\nGet/List/Query/Put/Delete)"]
    FSS["FileSkillStore\n(默认本地后端\nJSON 于 <root>/skills/)"]
    CLOUD["S3SkillStore / HttpSkillStore\n(云后端预留位)"]
    AD["AgentDescription.Skills\n(能力侧引用)"]
    MD["ModuleDescription.Workflows\n(业务侧引用)"]
    STG["CBIM.Storage\n(FileBackend + StorageJson)"]
    SKP["AgentSkillsProvider\n(未来装配侧：从 Store 拉取 + 注入 LLM 上下文)"]
    MS["Microsoft.Extensions.AI\n(AIContextProvider)"]

    AD --> SD
    MD --> SD
    ISS --> SD
    FSS -. 实现 .-> ISS
    CLOUD -. 实现 .-> ISS
    FSS --> STG
    SKP -. 读 .-> ISS
    SKP -. 实现 .-> MS

    classDef self fill:#fffbe6;
    classDef pending fill:#f0f0f0,stroke-dasharray:5 5;
    class SD,ISS,FSS self;
    class CLOUD,SKP pending;
```

依赖单向：`AgentDescription` / `ModuleDescription` → `SkillDescriptor`；`ISkillStore` → `SkillDescriptor`；`FileSkillStore` → `ISkillStore` + `CBIM.Storage`。本模块不反向依赖 CBIM 其他模块。

## Contract Surface

### 描述符（语义级抽象 · 已落地）

```csharp
namespace CBIM.Skills;

public sealed class SkillDescriptor
{
    public string Id { get; }            // kebab-case，全局唯一
    public string Name { get; }          // 人类可读
    public string Description { get; }   // 一句话：这个技能做什么
    public string Content { get; }       // SKILL.md 风格正文（可空）

    public SkillDescriptor(string id, string name, string description, string content = null);
}
```

描述符本身是不可变 POCO；不调 LLM、不启进程、不持 IO。

### 配置管理器（ISkillStore · 本轮新增）

Skill 是「配置类资产」——可被作者本地维护，也可统一在云端集中管理后下发各 Agent。本模块提供**配置仓储抽象**：

```csharp
namespace CBIM.Skills;

public interface ISkillStore
{
    // 查
    SkillDescriptor Get(string id);                  // 找不到返回 null
    IReadOnlyList<SkillDescriptor> List();           // 当前后端全量
    IReadOnlyList<SkillDescriptor> Query(string text, int topK);  // 可选简单子串匹配；后端可选实现

    // 增 / 改（按 Id upsert）
    void Put(SkillDescriptor descriptor);

    // 删
    bool Delete(string id);                          // 不存在返回 false
}
```

**实现规约**：

- 同步方法——本模块不引入 Task / async（Storage 也是同步）。云后端如需异步，包装层在 Agent / Workspace 侧自己处理。
- 描述符不可变——`Put` 替换整条记录；不支持 in-place 字段更新。
- `Query` 是可选能力——本地后端可只做最简 substring 匹配；接 Pinecone / Weaviate 时再做向量检索。

### 默认实现：FileSkillStore

```csharp
namespace CBIM.Skills;

using CBIM.Storage;

public sealed class FileSkillStore : ISkillStore
{
    public FileSkillStore(FileBackend backend, string subdir = "skills");
    // 落盘形态：<root>/skills/<id>.json （StorageJson 序列化）
    // 启动时全量扫一次进内存索引；Put/Delete 同步更新索引 + 落盘
}
```

**默认后端定位**：本地文件 + JSON 序列化，依赖 `CBIM.Storage.FileBackend`。**不预设 root 路径**——由调用方注入（Agent 装配根 / Unity Composition Root / 测试用临时目录）。

### 云后端预留位

`ISkillStore` 接口稳定后，**下切片**可派生：

- `S3SkillStore`（云对象存储后端 —— 后端如 AWS S3 / 阿里云 OSS / 七牛云）
- `HttpSkillStore`（基于 HTTP CDN 的只读后端）
- `CompositeSkillStore`（云上拉 + 本地缓存）

云后端无须改动 Agent / Workspace 调用代码——它们只看 `ISkillStore` 接口。这是 C6（稳定抽象）在本模块的具体兑现。

### 装配读侧（未来 `AgentSkillsProvider`）

装配侧从 `ISkillStore` 拉取 SkillDescriptor 实例集合，再合并 `AgentDescription.Skills` / `ModuleDescription.Workflows` 后注入 LLM 上下文。本模块只出 Store；装配方决定何时读、读哪几个 Id。

## 装配模型（后续落地）

```
OpenInstance:
  skills = desc.Skills ∪ module.Workflows  // 合并去重 by Id
  systemPromptAppend = Skills.Render(skills)
  // 或 chatOptions.AdditionalProperties["skills"] = skills
  agent = AIAgentBuilder.Create(...)
      .UseSkills(skills)   // 未来 extension
      .Build()
```

`Skills.Render` 可能的实现：拼接所有 Skill.Content 为一段（附列头）插入 system prompt；或者以 AIContextProvider 形式每次 turn 重新注入。具体选型后续设计。

## 铁律

1. **Skill 本身不挂 AIFunction**——不是 Tool。需要调用能力请另声明 Tool / Mcp。
2. **同一 SkillDescriptor 跨维度调用不重复表达**——agent.Skills 中 与 module.Workflows 中出现同 Id 的 Skill 是同一抽象实例，装配时去重。
3. **`Content` 可空但不可为孩子护魔包装形式**——设计上 Content 是 Markdown 纯文本，不期望 LLM 反复解析 frontmatter / yaml / xml。
4. **不持 hash / 版本**——现阶段代码 实例化即 source of truth。后续如从磁盘加载 SKILL.md才设计版本调识。

## Origin Context

- **上轮状态**：`Skill.cs` 裸露在 `AgentSystem/`，namespace `CBIM.Skills`。业务侧以 `Workflow.cs`（独立类型）在 Workspace 下描述业务流程。
- **本轮裁决**：提到顶层 + 同抽象复用。理由：
  1. **同抽象**——Workflow 与 Skill 描述形态与语义用途几乎一致（都是「该如何走这项难题」的描述 + 例子），不应双抽象并存。
  2. **跨维度共享**——提到顶层后能力侧 / 业务侧平等引用，不引入跨维度反向依赖。
  3. **与 Tool / Mcp 对称**——三大基础能力全部顶层。
- **代码同步**：原 `AgentSystem/Skills/Skill.cs` 文件已物理删除；新 `Skills/SkillDescriptor.cs` 主类名从原的 `Skill` 改名为 `SkillDescriptor`，与 `ToolDescriptor` / `McpDescriptor` 命名风格对齐。

## Emergent Insights

1. **「同抽象业务别名」是抽象复用的高阶形式**——不是「两者类似所以复用」，是「两者本质是同一件事，不同维度叫不同名」。识别这种同抽象需要看「描述形态 + 装配方式 + LLM 看到的体验」是否一致。
2. **Skill 不接管 Tool 调用，只提供「使用指引」**——这使 Skill 与 Tool 解耦：同一 Skill 可以被不同工具集实现（例：「code-review」技能在某 agent 上调 git-mcp，在另一个上调 svn-mcp）。这是 LLM 能力描述与能力实现的必要隔离。
3. **`Workflow` 独立类型被废弃是「抽象心智收敛」的体现**——“这个业务能走什么流程”与“这个 agent 会什么手艺”本质是同件事——“这件事能不能被走”。拍三个抽象（Skill / Workflow / Capability）、三个类型、三个语义是低阶设计。
4. **「Skill 只需 Store、不需 InstanceManager」是抽象本质决定的不对称**（本轮新增）——Skill 是纯文本配置，「读取」即「使用」，不存在「启动 / 接连 / 释放」生命周期。这与 Mcp（持有外部进程 / 连接，需 ref-count）与 Tool（实例化开销 ≈ 0，不需复用）并列看才出现：三大基建抽象的「是否需要实例管理器」是受「资源是否有进程 / 连接」决定，不是抽象级别决定。这个不对称是抽象忠实于资源本质的体现。

## Dependencies

- `SkillDescriptor` POCO：仅依赖自身（无外部依赖）。
- `ISkillStore` 接口：仅依赖自身 + `SkillDescriptor`。
- `FileSkillStore` 默认实现：依赖 `CBIM.Storage.FileBackend` + `CBIM.Storage.StorageJson`（读写 / 原子性 / JSON 序列化）。
- **不依赖** Tools / Mcp / AgentSystem / Workspace / Microsoft.Extensions.AI。
- `AgentSkillsProvider`（未来装配侧）落地时才侚依赖 `Microsoft.Extensions.AI.AIContextProvider`——不影响本模块抽象层。

依赖方向：`AgentDescription` / `ModuleDescription` → `CBIM.Skills`；`CBIM.Skills.FileSkillStore` → `CBIM.Storage`。不反向。

## Non-Goals

- **不实现 AgentSkillsProvider**——后续切片，本轮仅抽象。
- **不从磁盘加载 SKILL.md**——现阶段代码实例化即可；SKILL.md 加载器后续设计。
- **不实现技能推荐 / 补颁**——LLM 看到 Skill 描述后自行决定是否调。
- **不处理技能依赖**——Skill 之间不设依赖语义；agent 怎么组合由 LLM 决定。
- **不会变成「另一个工作流引擎」**——Skills 只是语义描述，执行在 Kernel.FlowGraph。
- **`ISkillStore` 不处理运行期实例生命周期**——Skill 是配置类资产（纯文本），装配侧读取后即丢引用，不存在「运行期实例」语义。这与 Mcp 需要 `IMcpInstanceManager` 的本质区别：Skill 的「实例」就是它的「配置」，二者合为一体。
