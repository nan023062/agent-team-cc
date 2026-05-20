# CBIM v2 初始规划

> 状态：二次修订 · 2026-05-20
> 范围：master 分支后续开发
> 关联：v1 已固化于 `v1-claude-code` 分支

## 一、目标与定位

把 v1 的"多 Agent × 模块知识 × 三阶段记忆"哲学搬到 **VS Code 插件**形态，**底层用 `@anthropic-ai/sdk` 的 Managed Agents API 替代 Claude Code 的 subagent + hooks 机制**，为用户提供 GUI 化的 CBIM 协作环境。

**不是简单"打包 v1"**，而是利用 Managed Agents 的能力做 v1 做不到的事：

- 自定义 subagent 调度——Managed Agents 原生支持 multiagent coordinator/subagent 拓扑，上下文自动隔离
- 自定义 tool 装配——每个 agent role 只装配该角色需要的 `cbim_*` tools，无通用文件 tool，封闭性是设计天然属性
- IDE 集成：文件树联动、diff 预览、状态可视化
- 跨 IDE 复用潜力（engine 包独立于 VS Code）

## 二、设计哲学

继承 v1 的核心，调整必要部分：

| 维度 | v1 | v2 |
|--|--|--|
| 多 Agent | 4 内置 + work agents | 沿用（5 内置：assistant / architect / hr / auditor / programmer） |
| 业务/能力分离 | `.dna/` ↔ agents/ | 沿用 |
| 模块约定 | `module.md`（frontmatter+body） | 沿用 |
| 三阶段记忆 | short → medium → distilled | 沿用，distilled 独立目录 |
| 模型 | Claude Code 默认链 | `@anthropic-ai/sdk` Managed Agents API（仅 Claude，MVP） |
| 状态存储 | 分散（`.claude/`、`cbim/`、`.dna/`、`CLAUDE.md`） | 收敛到 `.cbim/` + 子模块 `.dna/` |

## 三、技术栈

| 层 | 选型 | 理由 |
|--|--|--|
| 宿主 | VS Code Extension API（TypeScript） | 标配 |
| 模型链 | `@anthropic-ai/sdk` — Managed Agents API | Anthropic 官方 SDK，2026-04 GA；原生 multiagent + custom tools |
| Tool Schema | `zod` + `zod-to-json-schema` | custom tool 的 `input_schema` 定义；运行时校验 + 静态类型一体化 |
| Engine | TypeScript（重写，不再用 Python） | 与 SDK 同语言，零 IPC 开销 |
| UI | Webview + React | 复杂面板必备 |
| 包管理 | pnpm workspaces | monorepo 标配 |
| 构建 | tsup / vite（按包决定） | 简单可靠 |

**核心调用层**：Managed Agents API 提供三个关键能力——

1. **`agents.create()`**：上传 agent 配置（system prompt + tools + multiagent 拓扑）到 Anthropic 服务端
2. **`sessions.create()` / `sessions.events.stream()`**：创建会话、流式接收事件
3. **Custom Tools 事件循环**：监听 `agent.custom_tool_use` 事件 → 本地执行 → `sessions.events.send()` 回传结果

## 四、仓库结构（Monorepo）

```
agent-team-cc/                       # master 分支
├── docs/                            # 设计文档
├── packages/
│   ├── engine/                      # @cbim/engine — 纯 TS，无 VS Code 依赖
│   │   ├── knowledge/              # 模块 CRUD、snapshot 构建
│   │   ├── memory/                 # 三阶段蒸馏
│   │   ├── dispatch/               # 事件监听 + custom tool handler 路由
│   │   ├── tools/                  # cbim_* tool handler 集（按 role 装配）
│   │   └── migration/              # v1 → v2 迁移工具
│   ├── extension/                   # @cbim/vscode-extension
│   │   ├── activation.ts           # 扩展激活
│   │   ├── commands/               # Command Palette
│   │   ├── views/                  # Sidebar TreeView
│   │   └── webview/                # Webview host（加载 ui 包）
│   ├── ui/                          # @cbim/ui — React webview 应用
│   │   ├── chat/                   # 对话面板
│   │   ├── modules/                # 模块浏览器
│   │   └── memory/                 # 记忆 preview
│   └── cli/                         # @cbim/cli — 独立命令行（迁移、调试）
└── pnpm-workspace.yaml
```

**关键**：`engine` 包不依赖 VS Code API，未来可复用为 CLI / Web 工具 / 其他 IDE 插件的底层。

## 五、用户工程文件布局

v2 在用户工程内的文件结构：

```
<project>/
├── .cbim/                          # 框架工作区（项目级状态）
│   ├── config.yaml                 # 项目级配置
│   ├── agents/                     # work agent 配置（取代 .claude/agents/）
│   │   ├── architect.md
│   │   └── programmer.md
│   ├── memory/
│   │   ├── short/                  # 短期会话记忆
│   │   ├── medium/                 # 中期蒸馏（四象限：MUST/WANT/HOW/IS）
│   │   └── distilled/              # 已固化归档（懒创建：迁移时不创建，由 memory engine 首次写入时按需创建）
│   ├── .runtime/                   # 运行时状态（.gitignore）
│   │   └── agent-ids.json          # Managed Agents 返回的 agent ID 缓存
│   ├── snapshots/                  # 每次 session 的上下文快照（调试用）
│   └── dna/                        # 根模块（项目级模块知识）
│       ├── module.md               # 必需
│       ├── contract.md             # 可选
│       └── workflows/              # 可选
└── src/<module>/
    └── .dna/                       # 子模块（与代码同行同迁）
        ├── module.md               # 必需
        ├── contract.md             # 可选
        └── workflows/              # 可选
```

**设计原则**：

- **`.cbim/`** = 框架工作区，存放项目级状态（agents、memory、根模块知识、snapshots）
- **`.dna/`** = 模块身份标识，与代码 co-located；代码迁移它跟着迁移
- **根模块知识**在 `.cbim/dna/`（不在项目根贴 `.dna/`，保持源码根整洁）
- **根模块路径不对称**：根模块 `module.md` 位于 `<root>/.cbim/dna/module.md`（直接在 `dna/` 下），子模块位于 `<src>/<x>/.dna/module.md`（在模块目录内的 `.dna/` 下）。`loadModule` 必须处理这一结构差异——当路径以 `.cbim/dna` 结尾时，直接在该目录内查找 `module.md`，而非再进入 `.dna/` 子目录
- **模块树索引**由 engine 自动从文件系统扫描生成，不再手动维护 `index.md`
- **`.cbim/.runtime/`** = 运行时临时状态（agent IDs、session cache），不入版本控制

## 六、模块约定（沿用 v1）

完全沿用 v1 的 `module.md` 约定（参见 `cbim/knowledge/dna-convention.md` on `v1-claude-code` 分支）：

- `.dna/` 内**唯一硬要求**：`module.md` 存在
- `module.md` = YAML frontmatter（元数据）+ Markdown 正文（设计）
- 正文内容：
  - 叶子模块：Positioning + Mermaid classDiagram + Key Decisions
  - 父模块：Positioning + 子模块关系图 + Key Decisions
- 可选扩展：`contract.md`、`workflows/`、任意自定义文件

## 七、知识访问的封闭性原则

**v2 的封闭性是设计天然属性，不是事后 deny 规则。** 每个 agent 通过 Managed Agents API 注册时，其 tool 列表是**显式装配**的——只包含该角色需要的 `cbim_*` tools，根本不包含通用 Read/Write/Edit/Glob/Grep/Bash。Agent 不可能访问未装配的 tool，封闭性由 SDK 基础设施保证。

这是 v2 与 v1 最大的架构差异——v1 靠提示词约束约定，v2 靠 tool 装配强制约定。

### 7.1 封闭性机制

| 层级 | 机制 | 效果 |
|--|--|--|
| SDK 层 | `agents.create()` 的 `tools` 参数只列 `{ type: 'custom' }` 工具 | Agent 根本看不到通用文件 tool |
| Engine 层 | `getToolSet(role)` 按角色返回 tool 子集 | 不同角色 tool 集不同 |
| 运行时 | `agent.custom_tool_use` 事件 → 本地 handler 执行 | 所有 `.cbim/` 和 `.dna/` 访问走 handler 的 engine 函数 |

### 7.2 各角色 Tool 装配

| 角色 | 装配的 `cbim_*` Tools | 设计意图 |
|--|--|--|
| **assistant** | `cbim_dispatch`, `cbim_audit_log`, `cbim_memory_query` | 只调度、只查询，不触碰知识和源码 |
| **architect** | `cbim_module_*`, `cbim_source_read`（限源码区域） | 知识 CRUD 全权限 + 只读源码参考 |
| **programmer** | `cbim_module_get`, `cbim_source_*`, `cbim_run_test`, `cbim_run_build`, `cbim_git_*` | 只读知识 + 源码全操作 + 构建测试 |
| **auditor** | `cbim_module_get`, `cbim_source_read`（read-only） | 只读知识 + 只读源码，不可修改任何内容 |
| **hr** | `cbim_agent_*`, `cbim_skill_*`, `cbim_memory_query` | agent/skill 管理 + 记忆查询 |

### 7.3 为什么天然封闭优于路径守卫

| 路径守卫模式（v2 早期草案） | 天然封闭模式（最终方案） |
|--|--|
| 需要 `canUseTool` 拦截每次 Read/Write/Edit 调用 | Agent 的 tool 列表里根本没有 Read/Write/Edit |
| 拦截逻辑是 deny 规则，需要维护路径匹配 | 无 deny 逻辑，无路径匹配，零维护成本 |
| Agent 仍"知道"通用 tool 存在，可能尝试绕过 | Agent 不知道通用 tool 存在，无绕过动机 |
| 错误处理需返回提示消息 | 无错误路径 |

### 7.4 Custom Tools 域划分

五大实体域 + 跨实体 tool：

| 域 | Tools（CRUD 按需裁剪） |
|--|--|
| **agent** | `cbim_agent_list` / `_get` / `_create` / `_update` / `_archive` |
| **skill** | `cbim_skill_list` / `_get` / `_create` / `_update` / `_delete` |
| **module** | `cbim_module_list` / `_get` / `_init` / `_update` / `_deprecate` |
| **workflow** | `cbim_workflow_list` / `_get` / `_create` / `_update` / `_delete` |
| **memory** | `cbim_memory_query` / `_write_short` / `_distill_to_medium` / `_promote_to_distilled` |
| **source** | `cbim_source_read` / `_write` / `_edit` / `_glob` / `_grep` |
| **build** | `cbim_run_test` / `_run_build` |
| **git** | `cbim_git_status` / `_git_diff` / `_git_commit` |
| **跨实体** | `cbim_snapshot_build` / `cbim_dispatch` / `cbim_audit_log` |

详细 schema 与行为契约见 `docs/v2-tools-spec.md`（Phase 0 完成时落定）。

### 7.5 Tool 设计准则

1. **单一职责**：每个动作一个 tool，禁止"瑞士军刀"式 `action: 'create' | 'update'`
2. **JSON Schema 强约束**：输入用 zod 定义 → `zod-to-json-schema` 转换为 SDK 需要的 `input_schema`
3. **结构化输出**：返回解析后的对象，不返 raw markdown
4. **副作用集中**：tool 内部完成级联（如 init 子模块时自动更新父模块）
5. **权限分级**：read-only / mutating / privileged 三级，绑定 agent role（由 `getToolSet(role)` 实现）

### 7.6 实现位置

```
@cbim/engine/
├── knowledge/        ← 核心 CRUD 函数（纯 TS，无 SDK 依赖）
├── memory/
└── tools/            ← ★ custom tool handler 集
    ├── agent-tools.ts
    ├── module-tools.ts
    ├── source-tools.ts
    ├── memory-tools.ts
    └── index.ts      ← getToolSet(role) 按角色过滤导出
```

**`tools/` 是 handler 集**——每个 `cbim_*` tool 定义 zod schema + 调 engine 函数 + 格式化输出。engine 主体逻辑与 SDK 解耦，CLI 复用同一套函数。

### 7.7 例外

- **`@cbim/cli migrate`**：迁移工具直接读写 `.cbim/`，不是 agent，不走 SDK，不受 tool 装配约束
- **v2 extension 自身**：扩展进程通过 engine API 直接读写，LLM 始终走 custom tool

### 7.8 反推到 Tool Set 完备性

既然 agent 只能通过 `cbim_*` tool 操作，tool set 必须**功能完备**到能覆盖所有合法操作场景，否则 agent 卡死。Tool Set 完备性是 Phase 0 的硬验收指标。

---

## 八、内置 Agent IP 保护策略

v2 有 5 个内置 agent（assistant / architect / hr / auditor / programmer），其 system prompt 是 CBIM 的核心 IP。保护策略：

### 8.1 保护机制

| 环节 | 措施 | 效果 |
|--|--|--|
| 编译 | system prompt 以 TypeScript 字符串常量编译进 `packages/extension` | 不以 .md 文件形式落盘 |
| 上传 | 扩展首次启动调 `agents.create()` 上传到用户 Anthropic 账户 | 本地永不存储明文 prompt |
| 缓存 | 保存返回的 agent ID 到 `.cbim/.runtime/agent-ids.json` | 后续启动直接用 ID，不重新 create |
| 更新 | prompt 改版时检测 hash 变化 → 调 `agents.update()` 同步 | 扩展升级自动生效 |
| 用户可见性 | 用户可在 Anthropic Console 看到 agent 详情 | 接受的代价——门槛远高于 .md 文件 |

### 8.2 生命周期流程

```
扩展激活
  ↓
读取 .cbim/.runtime/agent-ids.json
  ↓
┌── 有缓存 ID ──→ 比对本地 prompt hash 与缓存 hash
│   ├── 一致 → 直接使用 agent ID
│   └── 不一致 → agents.update() 更新 → 刷新缓存
│
└── 无缓存 ──→ 对每个内置 agent 调 agents.create()
    ↓
    保存 { agentName: { id, promptHash } } 到 agent-ids.json
```

### 8.3 v1 对比

| v1 | v2 |
|--|--|
| `.claude/agents/<id>/<id>.md` 明文落盘 | 编译进 vsix + 上传到 Anthropic 服务端 |
| 用户可直接打开、复制、修改 | 用户最多在 Console 看到（需登录 + 导航） |
| 无版本校验 | hash 变化自动同步 |

### 8.4 进一步加固（Phase 2+ 考虑）

- Prompt 分段 + 服务端模板补完：将 prompt 拆分，部分关键段落仅存于服务端模板，create 时引用模板 ID 而非传完整文本
- 此方案需 Anthropic 支持 agent prompt templates——目前 API 尚未提供此功能

---

## 九、v1 → v2 能力映射

| v1 机制 | v2 实现 |
|--|--|
| `CLAUDE.md` 启动注入 | agent system prompt 编译进扩展 + `agents.create()` 注入服务端 |
| `.claude/agents/<id>.md` subagent 配置 | `agents.create()` with `multiagent: { type: 'coordinator', agents: [...] }` |
| `Stop` hook 写记忆 | 监听 `session.status_idle` 事件 → 写 `.cbim/memory/short/` |
| `SessionStart` hook 注入快照 | 首条 user message prepend snapshot（system prompt 锁定在 create 时，动态上下文走首条 message） |
| `python cbim/knowledge/engine/cli.py` | VS Code Command Palette + Sidebar 操作（也可走 `@cbim/cli`） |
| Python `cbim.preview` HTTP 服务 | 同进程 Webview panel（无独立服务） |
| Python `memory/engine` | `packages/engine/memory/` TS 移植 |
| `.dna/index.md` 手维护 | engine 自动扫描生成，不入库 |

## 十、v1 → v2 迁移路径

绿地重写，但提供迁移 CLI 帮助现有 v1 项目升级：

```bash
npx @cbim/cli migrate <project-path>
```

**迁移动作**：

| v1 位置 | v2 位置 | 动作 |
|--|--|--|
| `<project>/.dna/` | `<project>/.cbim/dna/` | 整体搬迁 |
| `<project>/.dna/index.md` | （删除） | 不再需要，engine 自动生成 |
| `<project>/.claude/agents/<id>/<id>.md` | `<project>/.cbim/agents/<id>.md` | 单文件直接复制（+ 可选 frontmatter 补全） |
| `<project>/cbim/memory/store/` | `<project>/.cbim/memory/` | 整体搬迁 |
| `<project>/CLAUDE.md` | `<project>/.cbim/config.yaml`（角色定义部分）+ 保留（用户自由内容部分） | 拆分 |
| `<project>/src/x/.dna/` | `<project>/src/x/.dna/` | 不变 |
| `<project>/cbim/` 框架文件 | （删除） | v2 用 npm 包，不入用户库 |

**CLAUDE.md 拆分规则**（权威约定）：

迁移时按 `## ` 标题将 CLAUDE.md 分为"系统"和"用户"两类内容：

| 标题（精确匹配或包含关键词） | 分类 | 去向 |
|--|--|--|
| `Role`、`Execution Roles`、`Workflow`、`Skills`、`Hard Rules`、`Stance` | system | `.cbim/config.yaml` 的 `assistant.sections` |
| 标题含 "Personality" 或 "Communication" | system | `.cbim/config.yaml` 的 `assistant.sections` |
| 标题含 "Emotional" | system | `.cbim/config.yaml` 的 `assistant.sections` |
| 首个 `## ` 之前的内容（标题 + 前言） | system | `.cbim/config.yaml` 的 `assistant.preamble` |
| 其他所有章节 | user | 保留在 CLAUDE.md |

如果 CLAUDE.md 无 `## ` 标题（非结构化纯文本），整体保留为 user 内容，不提取，生成警告。

**用户行动**：

1. 安装 v2 插件：`code --install-extension cbim.vsix`
2. 在项目内运行：`npx @cbim/cli migrate .`
3. 在 VS Code 内打开侧边栏 CBIM 视图，验证模块树、agents、memory 加载正常

## 十一、Phase 路线

| Phase | 周期 | 交付 | 关键依赖 |
|--|--|--|--|
| **0** — 骨架 + 迁移 | 1 周 | monorepo（pnpm workspaces）+ `@cbim/engine/knowledge`（读 `.cbim/dna/` + 子模块 `.dna/`）+ `@cbim/cli migrate`（v1→v2）+ tools/ 契约落定 | tsup, pnpm |
| **1** — 单 agent + 知识浏览 | 2 周 | VS Code extension 框架 + Sidebar 模块树 + 单个 chat panel + `agents.create()` 接入 + 第一个 `cbim_*` tool handler 跑通 | `@anthropic-ai/sdk` |
| **2** — 多 agent 协作 | 2 周 | `@cbim/engine/dispatch` 事件路由 + 5 个内置 agent 注册 + multiagent coordinator 拓扑 + chat panel 显示活跃 agent + 任务进度 | Phase 1 完成 |
| **3** — 记忆系统 | 2 周 | `@cbim/engine/memory` 三阶段蒸馏 TS 移植 + `session.status_idle` 触发自动写入 + Webview preview tab | Phase 2 完成 |

**MVP（Phase 0+1）目标**：6 周可发布的"v2 alpha"——一个能浏览模块、与单 agent 对话、能从 v1 项目迁移的最小可用插件。

## 十二、Engine 详细设计要点

`@cbim/engine` 是 v2 的核心抽象，必须做到：

- **无 VS Code 依赖**：可以被 CLI、Web、其他 IDE 复用
- **子模块独立可用**：knowledge、memory、tools 之间靠接口耦合
- **Migration 单独成包**：一次性使用，不污染运行时
- **`discoverModules` 默认跳过目录**：递归扫描模块树时，以下目录永远不进入：`node_modules`、`dist`、`build`、`out`、`.git`、`.cbim`（已在步骤 1 作为根模块单独处理）、以及其他 dotfiles 目录（`.` 开头但不是 `.dna` 的目录）。此列表硬编码于 engine，不可由 config.yaml 覆盖

### 12.1 dispatch 子模块定位

**dispatch 不再自己实现 subagent spawn / 上下文隔离 / 消息路由**——这些全部由 Managed Agents 原生处理。dispatch 的职责缩减为：

| 职责 | 说明 |
|--|--|
| Agent 注册管理 | 调用 `agents.create()` / `agents.update()`，管理 agent ID 生命周期 |
| Session 管理 | 调用 `sessions.create()`，管理会话生命周期 |
| 事件循环 | 监听 `sessions.events.stream()` 的事件流 |
| Custom tool 路由 | 接收 `agent.custom_tool_use` 事件 → 查找对应 handler → 执行 → `sessions.events.send()` 回传结果 |
| 记忆触发 | 监听 `session.status_idle` → 触发 memory 写入 |

```typescript
// dispatch 核心循环草图
async function runSession(sessionId: string, handlers: ToolHandlerMap): Promise<void> {
  const stream = await client.beta.sessions.events.stream(sessionId)

  for await (const event of stream) {
    switch (event.type) {
      case 'agent.custom_tool_use':
        const handler = handlers[event.name]
        const result = await handler(event.input)
        await client.beta.sessions.events.send(sessionId, {
          events: [{ type: 'user.custom_tool_result', tool_use_id: event.id, content: result }]
        })
        break
      case 'session.status_idle':
        await onSessionIdle(sessionId)
        break
    }
  }
}
```

### 12.2 tools 子模块定位

**tools 是 v2 的核心 IP**——封装所有 `cbim_*` tool handler，按 agent role 装配 toolset。

```typescript
// tools 接口草图
interface ToolDefinition {
  name: string                           // e.g. 'cbim_module_get'
  description: string
  input_schema: JsonSchema               // 由 zod schema 转换而来
  handler: (input: unknown) => Promise<string>
}

/**
 * 按角色返回该角色可用的 tool 列表。
 * 注册 agent 时传给 agents.create() 的 tools 参数。
 */
function getToolSet(role: AgentRole): ToolDefinition[]

/**
 * 返回所有 tool 的 handler 映射，供 dispatch 事件循环查找。
 */
function getToolHandlerMap(): Record<string, ToolHandler>
```

### 12.3 knowledge / memory 子模块

知识和记忆子模块的定位不变。具体接口契约已在 `packages/engine/.dna/contract.md`，不在此重复。

### 12.4 Streaming 行为

Managed Agents 的流式输出给完整 text block（非细粒度 delta）。UI 层收到后直接渲染整块，无需 delta 拼接逻辑。

---

## 十三、待决与风险

**待决：**

- Webview 与扩展主进程的通信协议（postMessage 协议设计）—— Phase 1 决策
- 跨 IDE 兼容（Cursor / Windsurf / Continue）—— 暂不考虑，保持 VS Code 原生 API；engine 独立性留口子

**风险：**

| 风险 | 影响 | 缓解 |
|--|--|--|
| Managed Agents API 费用模型（per session？per token？）不明 | 可能影响用户使用成本预期 | Phase 0 末调研定价，必要时提供 token 预算控制 |
| 内置 agent 通过用户 API key 上传服务端，用户可在 Anthropic Console 看到 prompt | IP 保护不完全（门槛远高于 .md 文件，但非零） | §八 已阐述；Phase 2+ 探索 prompt 分段加固 |
| 上下文窗口压缩：SDK 是否自动 compact？ | 长会话可能超窗口限制 | Phase 1 实测，必要时在 dispatch 层实现手动 compact |
| v1 用户的迁移成本 | `.claude/agents/<id>/<id>.md` 单文件直接复制到 `.cbim/agents/<id>.md`，风险低；主要复杂度在 CLAUDE.md 拆分 | 迁移 CLI 自动化 + 手动验证 |
| 多 agent 协作的并发模型 | v1 靠 Claude Code 进程隔离，v2 在一个 Node 进程内 | Managed Agents 的 coordinator/subagent 拓扑天然处理上下文隔离；Node 层面无需 worker 隔离 |

**不再适用的待决项（已由 Managed Agents 路线解决）：**

- ~~Claude Agent SDK 的 subagent 机制深度~~ → Managed Agents 原生 multiagent
- ~~`canUseTool` 路径守卫验证~~ → 天然封闭，无需路径守卫
- ~~SDK API 不稳定~~ → 2026-04 已 GA

## 十四、下一步

1. **Phase 0 剩余**：
   - 把 `packages/engine/dispatch/` 和 `packages/engine/tools/` 的 `.dna/` 契约更新到 Managed Agents 事件驱动设计
   - 落定 `getToolSet(role)` 的完整 tool 清单和每个 tool 的 zod schema
2. **Phase 1 起点**：
   - Scaffold `agents.create()` + 注册第一个内置 agent（architect）
   - 实现第一个 `cbim_*` tool handler（`cbim_module_get`）
   - 跑通 single agent 对话：user → extension → Managed Agent → custom_tool_use → handler → tool_result → response
3. **engine/knowledge 继续实现**：先把"读 `.cbim/dna/` + 递归 `.dna/`、构建 ModuleNode 树"跑通

---

> 本文档为 v2 启动阶段的总体设计依据。后续每个 Phase 完成时，应回头修订本文或新增 phase-N-report.md 记录实际偏差。
