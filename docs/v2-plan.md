# CBIM v2 初始规划

> 状态：锁定路线 · 终版 · 2026-05-20
> 范围：master 分支后续开发
> 关联：v1 已固化于 `v1-claude-code` 分支

## 一、目标与定位

把 v1 的"多 Agent × 模块知识 × 三阶段记忆"哲学搬到 **VS Code 插件**形态，**底层用 `@anthropic-ai/claude-agent-sdk`（Claude Code 的 npm 库化版本）+ CBIM 编排层（coordinator / tools / memory）**，为用户提供 GUI 化的 CBIM 协作环境。

**核心理念：复用 Claude Code 的完整 agent runtime，不重写。** `claude-agent-sdk` 就是 Claude Code CLI 打成的 npm 包——同一套 runtime、同一个底层 binary。v2 = "把 Claude Code 当库 import 进 VS Code 扩展" + CBIM 的 coordinator / tools / memory 编排层。

- 原生 subagent——SDK 内置 `agents` 配置 + `Agent` tool，上下文天然隔离，无需自己 spawn 对话
- 自定义 tool 装配——SDK 的 `allowedTools` / `disallowedTools`（支持 regex）按 role 精确装配，封闭性是设计天然属性
- Provider 中立——SDK 官方支持 `ANTHROPIC_BASE_URL`，覆盖 Claude / Bedrock / Vertex / Azure / Foundry；事实上 OpenRouter 也可用（用户已验证）
- 内置 tools——Read / Write / Edit / Bash / Glob / Grep / WebSearch / WebFetch / Monitor 等 SDK 自带，无需重写
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
| 模型 | Claude Code 默认链 | `@anthropic-ai/claude-agent-sdk`（Claude Code 库化）+ CBIM 编排层；通过 `ANTHROPIC_BASE_URL` 支持多 provider |
| 状态存储 | 分散（`.claude/`、`cbim/`、`.dna/`、`CLAUDE.md`） | 收敛到 `.cbim/` + 子模块 `.dna/` |

## 三、技术栈

| 层 | 选型 | 理由 |
|--|--|--|
| 宿主 | VS Code Extension API（TypeScript） | 标配 |
| Agent 运行时 | `@anthropic-ai/claude-agent-sdk` | Claude Code CLI 的 npm 库化版本；同一套 runtime，同一个底层 binary |
| Provider 中立 | SDK 官方支持 `ANTHROPIC_BASE_URL` | 覆盖 Claude / Bedrock / Vertex / Azure / Foundry；事实上 OpenRouter 也可用 |
| 自定义 Tool | `createSdkMcpServer` + `tool(name, desc, zodSchema, handler)` | SDK 内置 MCP server 包装，用于定义 `cbim_*` tools |
| Engine | TypeScript（重写，不再用 Python） | 与 SDK 同语言，零 IPC 开销 |
| UI | Webview + React | 复杂面板必备 |
| 包管理 | pnpm workspaces | monorepo 标配 |
| 构建 | tsup / vite（按包决定） | 简单可靠 |

**为什么用 Agent SDK 而不是 Messages API？**

`@anthropic-ai/claude-agent-sdk` 是 Messages API 之上的高层封装——它就是 Claude Code CLI 打包成 npm。SDK 已经内置了：

- **`query()` 主入口**：完整 agent loop（发请求 → tool_use 检测 → 执行 handler → 拼 tool_result → 继续，直到结束）
- **内置 tools**：Read / Write / Edit / Bash / Glob / Grep / WebSearch / WebFetch / Monitor / AskUserQuestion——无需重写
- **原生 subagent**：`agents: { architect: AgentDefinition, ... }` + `Agent` tool，上下文自动隔离
- **Hooks 回调**：PreToolUse / PostToolUse / Stop / SessionStart / SessionEnd / UserPromptSubmit
- **权限控制**：`allowedTools` / `disallowedTools`（支持 regex）
- **Session 持久化**：JSONL 自动管理

直接用 Messages API 手动实现 agent loop + tool 循环 + subagent spawn，需要额外 400+ 行编排代码，且要自己处理 streaming / 并发 / 错误恢复。SDK 把这些全包了，省约 60% 工程量。

SDK 仍走 Messages API 协议，仍享受 `ANTHROPIC_BASE_URL` 的 provider 中立性——这不是 Managed Agents API（那个锁死 Anthropic 直连），而是把 Claude Code 已验证的客户端编排封装成了可复用的库。

## 四、仓库结构（Monorepo）

```
agent-team-cc/                       # master 分支
├── docs/                            # 设计文档
├── packages/
│   ├── engine/                      # @cbim/engine — 纯 TS，无 VS Code 依赖
│   │   ├── knowledge/              # 模块 CRUD、snapshot 构建
│   │   ├── memory/                 # 三阶段蒸馏
│   │   ├── dispatch/               # coordinator 分发（SDK query() + intent 路由）
│   │   ├── tools/                  # cbim_* MCP server（createSdkMcpServer 包装）
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
- **`.cbim/.runtime/`** = 运行时临时状态（session cache），不入版本控制

## 六、模块约定（沿用 v1）

完全沿用 v1 的 `module.md` 约定（参见 `cbim/knowledge/dna-convention.md` on `v1-claude-code` 分支）：

- `.dna/` 内**唯一硬要求**：`module.md` 存在
- `module.md` = YAML frontmatter（元数据）+ Markdown 正文（设计）
- 正文内容：
  - 叶子模块：Positioning + Mermaid classDiagram + Key Decisions
  - 父模块：Positioning + 子模块关系图 + Key Decisions
- 可选扩展：`contract.md`、`workflows/`、任意自定义文件

## 七、知识访问的封闭性原则

**v2 的封闭性是设计天然属性，不是事后 deny 规则。** 每个 agent 通过 SDK 的 `allowedTools` / `disallowedTools` 配置精确控制可用 tool 集。`disallowedTools` 支持 regex，可以按路径模式禁止特定文件访问。配置写在扩展代码里，用户无法修改（与 Claude Code 用户能改 settings.json 不同），封闭性更强。

这是 v2 与 v1 最大的架构差异——v1 靠提示词约束约定，v2 靠 SDK 配置强制约定。

### 7.1 封闭性机制

| 层级 | 机制 | 效果 |
|--|--|--|
| SDK 配置层 | `allowedTools` 白名单：只列该 role 可用的 tool | Agent 看不到未授权的 tool |
| SDK 配置层 | `disallowedTools` 黑名单（regex）：禁止特定路径操作 | 即使 tool 可用，特定路径被拦截 |
| MCP Server 层 | `cbim_*` tools 通过 `createSdkMcpServer` 注册，按 role 装配 | 不同角色获得不同 tool 集 |
| 扩展代码层 | agent 配置硬编码在 `packages/extension` 的 TS 常量中 | 用户无法修改权限配置 |

```typescript
// 封闭性配置草图
const architectConfig = {
  systemPrompt: ARCHITECT_PROMPT,
  allowedTools: ['Read', 'Glob', 'Grep', 'mcp__cbim__module_*'],
  disallowedTools: [/Read\(\.cbim\/.*/, /Read\(.*\/\.dna\/.*/],
}
```

### 7.2 各角色 Tool 装配

| 角色 | `allowedTools` | `disallowedTools` | 设计意图 |
|--|--|--|--|
| **assistant** | `['Agent', 'mcp__cbim__dispatch', 'mcp__cbim__audit_log', 'mcp__cbim__memory_query']` | — | 只调度、只查询，不触碰知识和源码 |
| **architect** | `['Read', 'Glob', 'Grep', 'mcp__cbim__module_*']` | `[/Write/, /Edit/, /Bash/]` | 知识 CRUD + 只读源码参考 |
| **programmer** | `['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep', 'mcp__cbim__module_get', 'mcp__cbim__source_*', 'mcp__cbim__run_*', 'mcp__cbim__git_*']` | — | 只读知识 + 源码全操作 + 构建测试 |
| **auditor** | `['Read', 'Glob', 'Grep', 'mcp__cbim__module_get']` | `[/Write/, /Edit/, /Bash/]` | 只读知识 + 只读源码，不可修改 |
| **hr** | `['mcp__cbim__agent_*', 'mcp__cbim__skill_*', 'mcp__cbim__memory_query']` | — | agent/skill 管理 + 记忆查询 |

### 7.3 为什么 SDK 配置优于路径守卫

| 路径守卫模式（v2 早期草案） | SDK 配置模式（最终方案） |
|--|--|
| 需要 `canUseTool` 拦截每次 Read/Write/Edit 调用 | SDK 的 `allowedTools` / `disallowedTools` 在对话创建时静态装配 |
| 拦截逻辑是运行时 deny 规则，需要维护路径匹配 | 白名单 + regex 黑名单，SDK 框架层强制执行 |
| Agent 仍"知道"通用 tool 存在，可能尝试绕过 | 未授权 tool 对 agent 不可见 |
| 用户可通过 settings.json 修改 hook 逻辑 | 配置硬编码在扩展代码中，用户无法修改 |

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
5. **权限分级**：read-only / mutating / privileged 三级，绑定 agent role（由 `getToolConfig(role)` 返回 `allowedTools` / `disallowedTools` 实现）

### 7.6 实现位置

```
@cbim/engine/
├── knowledge/        ← 核心 CRUD 函数（纯 TS，无 SDK 依赖）
├── memory/
└── tools/            ← ★ cbim_* MCP server（用 createSdkMcpServer 包装）
    ├── agent-tools.ts
    ├── module-tools.ts
    ├── source-tools.ts
    ├── memory-tools.ts
    └── index.ts      ← createCbimMcpServer() 创建 MCP server + getToolConfig(role) 返回 allowedTools/disallowedTools
```

**`tools/` 是 MCP server**——每个 `cbim_*` tool 用 `tool(name, description, zodSchema, handler)` 定义，通过 `createSdkMcpServer` 包装成 SDK 可识别的 MCP server。agent 配置里通过 `mcp_servers: { cbim: cbimServer }` 注入。toolset 装配 = `allowedTools` 数组按 role 装配。engine 主体逻辑与 SDK 解耦，CLI 复用同一套 engine 函数。

### 7.7 例外

- **`@cbim/cli migrate`**：迁移工具直接读写 `.cbim/`，不是 agent，不走 SDK，不受 tool 装配约束
- **v2 extension 自身**：扩展进程通过 engine API 直接读写，LLM agent 始终走 `cbim_*` MCP tool

### 7.8 反推到 Tool Set 完备性

既然 agent 只能通过 `cbim_*` tool 操作，tool set 必须**功能完备**到能覆盖所有合法操作场景，否则 agent 卡死。Tool Set 完备性是 Phase 0 的硬验收指标。

---

## 八、内置 Agent IP 保护策略

v2 有 5 个内置 agent（assistant / architect / hr / auditor / programmer），其 system prompt 是 CBIM 的核心 IP。5 个 prompt 编译进 `packages/extension` 的 TS 常量，通过 SDK 的 `systemPrompt` 参数或 `agents: { name: { prompt, ... } }` 配置传入——不落用户磁盘。

### 8.1 保护机制

| 环节 | 措施 | 效果 |
|--|--|--|
| 编译 | 5 个内置 agent 的 system prompt 以 TypeScript 字符串常量编译进 `packages/extension` | 不以 .md 文件形式落盘用户磁盘 |
| SDK 传入 | 通过 `systemPrompt` 参数传入 SDK，prompt 仅在内存中存在 | 不写入任何本地文件或缓存 |
| 分发 | 发布为 .vsix 包，prompt 字符串嵌入 minified JS bundle | 用户拿到的是编译产物，反编译门槛远高于打开 .md 文件 |
| 隔离 | 内置 agent 不进入用户 `.claude/agents/` 目录 | 用户在 `.cbim/agents/` 看到的只有自己加的 work agent |

### 8.2 v1 对比

| v1 | v2 |
|--|--|
| `.claude/agents/<id>/<id>.md` 明文落盘 | 编译进 vsix 的 minified JS bundle |
| 用户可直接打开、复制、修改 | 用户需要反编译 JS bundle 才能提取（门槛提升一个量级） |
| 无版本校验 | 扩展更新自动生效 |

### 8.3 进一步加固（Phase 2+ 考虑）

- **Prompt 分段 + 运行时拼装**：将 prompt 拆分为多个片段，分散在不同源文件中，运行时动态拼装，增加反编译后还原完整 prompt 的难度
- **远程模板补完**：扩展启动时联网获取部分 prompt 片段，本地 bundle 中不包含完整版本
- **代码混淆**：对编译产物使用 uglify / javascript-obfuscator，进一步提高反编译成本

### 8.4 Trade-off 说明

SDK 的 `systemPrompt` 参数将 prompt 传给 SDK runtime，SDK 内部走 Messages API 发到 provider。prompt 在传输路径上仅存于内存。v1 全明文 → v2 至少要反编译，在 IP 防抄袭维度上已是显著提升。

---

## 九、v1 → v2 能力映射

| v1 机制 | v2 实现 |
|--|--|
| Claude Code CLI 的 `Agent` tool | **SDK 原生 subagent**（`agents: {...}` + Agent tool），无需自己实现 |
| `CLAUDE.md` 启动注入 | SDK 的 `systemPrompt` 参数（也可让 SDK 读 `.cbim/CLAUDE.md` 作为 user context） |
| `.claude/agents/<id>.md` subagent 配置 | SDK 的 `agents: { role: { prompt, allowedTools, ... } }` 配置 |
| `Stop` hook 写记忆 | SDK hooks 的 `Stop` 回调（程序回调，不是 shell 命令） |
| `SessionStart` hook 注入快照 | SDK hooks 的 `SessionStart` 回调 |
| `settings.json` hooks | SDK hooks 是程序回调函数，不是 settings.json shell 命令 |
| 内置 Read/Write/Edit/Glob/Grep/Bash tools | **SDK 自带，无需重写** |
| Permission per-agent | SDK `allowedTools` / `disallowedTools`（支持 regex） |
| Context compaction | SDK 不带，自己写（保留风险条目） |
| Session resume | SDK 内置 JSONL 持久化 |
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
| **0** — 骨架 + 迁移 | 1 周 | monorepo（pnpm workspaces）+ `@cbim/engine/knowledge`（读 `.cbim/dna/` + 子模块 `.dna/`）+ `@cbim/cli migrate`（v1→v2）+ dispatch / tools 子模块契约落定；Agent SDK 计费模型核实 | tsup, pnpm |
| **1** — 单 agent 对话 | 1.5 周 | VS Code extension 框架 + Sidebar 模块树 + 单个 chat panel + scaffold SDK `query()` 集成 + 第一个 `cbim_*` MCP tool（`createSdkMcpServer`）+ 跑通单 agent 对话 | `@anthropic-ai/claude-agent-sdk` |
| **2** — 多 agent 协作 | 1.5 周 | coordinator 分发层（~200 行：user intent → 选 role → 调起 sub agent）+ 5 个 agent 的 SDK 配置装配（`agents: {...}` + `allowedTools`）+ 多 agent 协作跑通；chat panel 显示活跃 agent + 任务进度 | Phase 1 完成 |
| **3** — 记忆系统 | 2 周 | `@cbim/engine/memory` 三阶段蒸馏 TS 移植 + SDK `Stop` hook 触发自动写入 + Webview preview tab | Phase 2 完成 |
| **4**（可选） — 加固 | 1-2 周 | Context compaction（SDK 不带，自实现总结策略）+ Provider 切换 UI（base URL 配置界面）+ prompt IP 加固 | Phase 3 完成 |

**MVP 预计 3-4 周**（Phase 0-2），相比之前估计的 4-6 周大幅缩减——SDK 包揽了 agent loop / tool execution / subagent spawning / session 持久化。

## 十二、Engine 详细设计要点

`@cbim/engine` 是 v2 的核心抽象，必须做到：

- **无 VS Code 依赖**：可以被 CLI、Web、其他 IDE 复用
- **子模块独立可用**：knowledge、memory、tools 之间靠接口耦合
- **Migration 单独成包**：一次性使用，不污染运行时
- **`discoverModules` 默认跳过目录**：递归扫描模块树时，以下目录永远不进入：`node_modules`、`dist`、`build`、`out`、`.git`、`.cbim`（已在步骤 1 作为根模块单独处理）、以及其他 dotfiles 目录（`.` 开头但不是 `.dna` 的目录）。此列表硬编码于 engine，不可由 config.yaml 覆盖

### 12.1 dispatch 子模块定位

**核心责任：把 user intent 路由到合适的 agent role；管理 5 agent 的 SDK 配置；监听 SDK 事件流写 memory。**

SDK 是 Claude Code 的库化版本，agent loop / tool execution / subagent spawning 全部由 SDK 处理。dispatch 不再需要自己实现 Messages API 循环、自己管 tool_use 拼接、自己 spawn 子 agent。

| 职责 | 说明 |
|--|--|
| Intent 路由 | user intent → 选择合适的 agent role |
| Config 装配 | 每个 role 的 `systemPrompt` + `allowedTools` + `disallowedTools` + `agents` 子配置 |
| SDK 调用 | 调用 `query()` 传入配置，SDK 处理完整 agent loop |
| 事件监听 | 监听 SDK 事件流（`result` / `assistant` / `tool_use`），写 memory + 推送 UI |
| MCP server 注入 | 将 `cbim_*` MCP server 注入 agent 配置 |

```typescript
// dispatch 核心草图（~200 行总量）
const AGENT_CONFIGS: Record<AgentRole, AgentConfig> = {
  architect: {
    systemPrompt: ARCHITECT_PROMPT,
    allowedTools: ['Read', 'Glob', 'Grep', 'mcp__cbim__module_*'],
    disallowedTools: [/Write/, /Edit/, /Bash/],
  },
  // ... 其他 role
}

async function dispatch(role: AgentRole, task: string, parentSession?: string) {
  const config = AGENT_CONFIGS[role]
  for await (const msg of query({
    prompt: task,
    options: { ...config, resume: parentSession },
  })) {
    if (msg.type === 'result') return msg
    if (msg.type === 'assistant') emitToUI(msg)
  }
}
```

### 12.2 tools 子模块定位

**tools 是 v2 的核心 IP**——用 `createSdkMcpServer` 包装所有 `cbim_*` tools 为 MCP server，按 agent role 装配。

```typescript
// tools MCP server 草图
import { createSdkMcpServer, tool } from '@anthropic-ai/claude-agent-sdk'

const cbimServer = createSdkMcpServer({
  name: 'cbim',
  tools: [
    tool('cbim_module_get', 'Load a module by path', moduleGetSchema, async (input) => {
      const mod = await loadModule(input.path)
      return formatModule(mod)
    }),
    tool('cbim_module_list', 'List all modules in the tree', moduleListSchema, async (input) => {
      const tree = await discoverModules(input.projectRoot)
      return formatTree(tree)
    }),
    // ... ~20 个 cbim_* tools
  ],
})

/**
 * 返回按 role 装配的 allowedTools / disallowedTools 配置。
 * 与 cbimServer 配合使用：agent 配置里注入 mcp_servers: { cbim: cbimServer }，
 * 然后用 allowedTools 控制该 role 可见哪些 tool。
 */
function getToolConfig(role: AgentRole): { allowedTools: string[]; disallowedTools: RegExp[] }
```

### 12.3 knowledge / memory 子模块

知识和记忆子模块的定位不变。具体接口契约已在 `packages/engine/.dna/contract.md`，不在此重复。

### 12.4 Streaming 行为

SDK 的 `query()` 返回 async iterable 事件流，UI 层可以逐事件渲染（assistant message / tool_use / result），提供实时反馈。SDK 内部处理 streaming 细节，dispatch 层只需消费事件流。

---

## 十三、待决与风险

**待决：**

- Webview 与扩展主进程的通信协议（postMessage 协议设计）—— Phase 1 决策
- 跨 IDE 兼容（Cursor / Windsurf / Continue）—— 暂不考虑，保持 VS Code 原生 API；engine 独立性留口子

**风险：**

| 等级 | 风险 | 影响 | 缓解 |
|--|--|--|--|
| :red_circle: | **Agent SDK 计费模型（2026-06-15 起）** | 独立月度积分池还是仍按 Messages API 计费？影响用户成本和 v2 商业模式 | Phase 0 末必须核实 |
| :yellow_circle: | **OpenRouter 长期兼容性** | Anthropic 不官方保证 OpenRouter；未来 SDK 升级可能引入 OpenRouter 不支持的特性 | 文档告知用户"OpenRouter 事实可用但非官方保证" |
| :yellow_circle: | **Context compaction** | SDK 不自带，长 session 需自实现总结策略 | Phase 4（可选）实现；短期靠对话长度限制 |
| :yellow_circle: | **SDK 版本绑定** | v2 与 SDK 版本耦合，SDK 升级需要 v2 跟版 | 锁定 SDK 主版本；升级前跑回归测试 |
| :white_circle: | v1 用户的迁移成本 | 主要复杂度在 CLAUDE.md 拆分 | 迁移 CLI 自动化 + 手动验证 |
| :white_circle: | 多 agent 并发资源消耗 | 多个 SDK session 并发，token 消耗可能较高 | 提供 token 预算控制；默认串行 dispatch，并发为可选 |

**不再适用的待决项：**

- ~~Managed Agents API 费用模型~~ → 不再使用 Managed Agents
- ~~Anthropic Console prompt 可见性~~ → prompt 不上传服务端，不适用
- ~~`canUseTool` 路径守卫验证~~ → SDK `allowedTools` / `disallowedTools` 取代
- ~~Provider 兼容性测试~~ → SDK 官方支持 base URL，事实可用
- ~~客户端 multiagent 实现（200-400 行）~~ → SDK 自带 subagent
- ~~Messages API 手动 tool 循环~~ → SDK `query()` 全包

## 十四、下一步

1. **Phase 0 收尾**：
   - 把 `packages/engine/dispatch/` 和 `packages/engine/tools/` 的 `.dna/` 契约更新到 SDK 集成设计
   - 落定 `getToolConfig(role)` 的完整 allowedTools / disallowedTools 清单
   - 落定 `cbim_*` MCP tool 清单和每个 tool 的 zod schema
   - **核实 Agent SDK 计费模型**（2026-06-15 起生效的新计费）
2. **Phase 1 起点**：
   - Scaffold SDK `query()` 集成
   - 用 `createSdkMcpServer` 实现首个 `cbim_*` MCP tool（`cbim_module_get`）
   - 跑通单 agent 对话：user → extension → SDK `query()` → tool_use → MCP handler → result
3. **engine/knowledge 继续实现**：先把"读 `.cbim/dna/` + 递归 `.dna/`、构建 ModuleNode 树"跑通

---

> 本文档为 v2 启动阶段的总体设计依据。后续每个 Phase 完成时，应回头修订本文或新增 phase-N-report.md 记录实际偏差。
