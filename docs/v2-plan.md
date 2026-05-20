# CBIM v2 初始规划

> 状态：三次修订（最终锁定） · 2026-05-20
> 范围：master 分支后续开发
> 关联：v1 已固化于 `v1-claude-code` 分支

## 一、目标与定位

把 v1 的"多 Agent × 模块知识 × 三阶段记忆"哲学搬到 **VS Code 插件**形态，**底层用 `@anthropic-ai/sdk` 的 Messages API（`client.messages.create()`）+ 客户端自实现 multiagent / tools / lifecycle / memory**，为用户提供 GUI 化的 CBIM 协作环境。

**不是简单"打包 v1"**，而是参考 Claude Code CLI 的成熟架构做 v1 做不到的事：

- 客户端 multiagent 编排——spawn 独立 Messages API 对话作为 subagent，独立 system prompt + tools + 历史，上下文天然隔离
- 自定义 tool 装配——每个 agent role 只装配该角色需要的 `cbim_*` tools，无通用文件 tool，封闭性是设计天然属性
- Provider 中立——通过 `ANTHROPIC_BASE_URL` 支持 Claude / GPT / Gemini / 本地模型，不锁死单一供应商
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
| 模型 | Claude Code 默认链 | `@anthropic-ai/sdk` Messages API + 客户端编排；通过 `ANTHROPIC_BASE_URL` 支持多 provider |
| 状态存储 | 分散（`.claude/`、`cbim/`、`.dna/`、`CLAUDE.md`） | 收敛到 `.cbim/` + 子模块 `.dna/` |

## 三、技术栈

| 层 | 选型 | 理由 |
|--|--|--|
| 宿主 | VS Code Extension API（TypeScript） | 标配 |
| 模型链 | `@anthropic-ai/sdk` — Messages API（`client.messages.create()`） | Anthropic 官方 SDK；Messages API 是最稳定、最广泛兼容的接口 |
| Provider 中立 | 通过 `ANTHROPIC_BASE_URL` 环境变量或扩展配置切换 | 支持 Claude / OpenRouter / Bedrock / Vertex / 本地代理等任何 Anthropic-compatible 端点 |
| Tool Schema | `zod` + `zod-to-json-schema` | tool 的 `input_schema` 定义；运行时校验 + 静态类型一体化 |
| Engine | TypeScript（重写，不再用 Python） | 与 SDK 同语言，零 IPC 开销 |
| UI | Webview + React | 复杂面板必备 |
| 包管理 | pnpm workspaces | monorepo 标配 |
| 构建 | tsup / vite（按包决定） | 简单可靠 |

**核心调用层**：Messages API + 客户端编排，参考 Claude Code CLI 的成熟模式——

1. **`client.messages.create()`**：发送对话请求，携带 system prompt + tools + messages 数组
2. **客户端 tool 循环**：收到 `tool_use` stop_reason → 执行本地 handler → 拼 `tool_result` → 继续请求，直到 `end_turn`
3. **客户端 multiagent**：dispatch 时 spawn 新 Messages API 对话，独立 system prompt + tools + 历史；子对话结果作为父对话的 tool_result 返回

**为什么不用 Managed Agents API**：Managed Agents 锁死 Anthropic 直连——不能通过 `ANTHROPIC_BASE_URL` 代理到 OpenRouter / Bedrock / 本地代理。第三方代理都只覆盖 Messages API 协议。Claude Code CLI 本身就是 Messages API + 客户端编排架构，这正是它能通过 base URL 重定向使用 GPT / Gemini / 本地模型的原因。v2 采用同款架构，代价是多 200-400 行客户端编排代码，换取多 provider + multiagent + 自定义 tool 三个能力完全在自己掌控之下。

## 四、仓库结构（Monorepo）

```
agent-team-cc/                       # master 分支
├── docs/                            # 设计文档
├── packages/
│   ├── engine/                      # @cbim/engine — 纯 TS，无 VS Code 依赖
│   │   ├── knowledge/              # 模块 CRUD、snapshot 构建
│   │   ├── memory/                 # 三阶段蒸馏
│   │   ├── dispatch/               # 客户端 multiagent 编排 + tool 循环
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

**v2 的封闭性是设计天然属性，不是事后 deny 规则。** 每个 agent 的 Messages API 对话在创建时，其 `tools` 数组是**显式装配**的——只包含该角色需要的 `cbim_*` tools，根本不包含通用 Read/Write/Edit/Glob/Grep/Bash。Agent 不可能调用未装配的 tool，封闭性由客户端编排代码保证。

这是 v2 与 v1 最大的架构差异——v1 靠提示词约束约定，v2 靠 tool 装配强制约定。

### 7.1 封闭性机制

| 层级 | 机制 | 效果 |
|--|--|--|
| 对话层 | `client.messages.create()` 的 `tools` 参数只列 role-specific 的 `cbim_*` tools | Agent 根本看不到通用文件 tool |
| Engine 层 | `getToolSet(role)` 按角色返回 tool 子集 | 不同角色 tool 集不同 |
| 运行时 | 收到 `tool_use` → 查找本地 handler → 执行 → 拼 `tool_result` 继续对话 | 所有 `.cbim/` 和 `.dna/` 访问走 handler 的 engine 函数 |

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
| 需要 `canUseTool` 拦截每次 Read/Write/Edit 调用 | Agent 的 `tools` 数组里根本没有 Read/Write/Edit |
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

**`tools/` 是 handler 集**——每个 `cbim_*` tool 定义 zod schema + 调 engine 函数 + 格式化输出。engine 主体逻辑与 Messages API 解耦，CLI 复用同一套函数。

### 7.7 例外

- **`@cbim/cli migrate`**：迁移工具直接读写 `.cbim/`，不是 agent，不走 Messages API，不受 tool 装配约束
- **v2 extension 自身**：扩展进程通过 engine API 直接读写，LLM agent 始终走 `cbim_*` tool

### 7.8 反推到 Tool Set 完备性

既然 agent 只能通过 `cbim_*` tool 操作，tool set 必须**功能完备**到能覆盖所有合法操作场景，否则 agent 卡死。Tool Set 完备性是 Phase 0 的硬验收指标。

---

## 八、内置 Agent IP 保护策略

v2 有 5 个内置 agent（assistant / architect / hr / auditor / programmer），其 system prompt 是 CBIM 的核心 IP。由于采用 Messages API + 客户端编排（prompt 不上传到 Anthropic 服务端），保护策略调整为编译时防护 + 运行时防护的组合。

### 8.1 保护机制

| 环节 | 措施 | 效果 |
|--|--|--|
| 编译 | 5 个内置 agent 的 system prompt 以 TypeScript 字符串常量编译进 `packages/extension` | 不以 .md 文件形式落盘用户磁盘 |
| 运行时 | Messages API 调用时，prompt 字符串仅在请求那一瞬间从内存中经过 | 不写入任何本地文件或缓存 |
| 分发 | 发布为 .vsix 包，prompt 字符串嵌入 minified JS bundle | 用户拿到的是编译产物，反编译门槛远高于打开 .md 文件 |

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

客户端编排意味着 prompt 不上传到 Anthropic 服务端存储，无法利用"服务端保管"的优势（这是 Managed Agents 路线才有的）。但接受这个 trade-off 换取多 provider 支持。实际上，v1 全明文 → v2 至少要反编译，这在 IP 防抄袭维度上已是显著提升。

---

## 九、v1 → v2 能力映射

| v1 机制 | v2 实现 |
|--|--|
| Claude Code CLI 的 `Agent` tool | v2 自己实现 `cbim_dispatch_to_agent` tool，spawn 新 Messages API 对话 |
| `CLAUDE.md` 启动注入 | 扩展启动时构造 coordinator 的 system prompt（含项目快照） |
| `.claude/agents/<id>.md` subagent 配置 | 每个 agent 一个独立的 Messages API 对话上下文，role-specific system prompt + tools 数组 |
| `Stop` hook 写记忆 | 监听 Messages API stream 完成事件，触发 memory 写入 |
| `SessionStart` hook 注入快照 | 首条 user message prepend snapshot |
| `settings.json` hooks | 完全不用，全部用扩展内事件订阅 |
| 内置 Read/Write/Edit/Glob/Grep/Bash tools | v2 自己实现 `cbim_source_*` / `cbim_run_*` tools，按 role 装配 |
| Permission per-agent | 每个 agent 一个不同的 `tools` 数组 |
| Context compaction | 自己监控 token，达阈值时主动总结 + 截断 |
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
| **1** — 单 agent 对话 | 2 周 | VS Code extension 框架 + Sidebar 模块树 + 单个 chat panel + scaffold Messages API 调用 + 第一个 `cbim_*` tool handler 跑通单 agent 对话 | `@anthropic-ai/sdk` |
| **2** — 多 agent 协作 | 2 周 | `@cbim/engine/dispatch` 客户端 multiagent 实现——`dispatch(toRole, task)` spawn 独立 Messages API 对话 + tool 循环 + 结果回传；5 个内置 agent 跑通 coordinator/subagent 拓扑；chat panel 显示活跃 agent + 任务进度（主要新增工作量：200-400 行 dispatch 编排代码） | Phase 1 完成 |
| **3** — 记忆系统 | 2 周 | `@cbim/engine/memory` 三阶段蒸馏 TS 移植 + stream 完成事件触发自动写入 + Webview preview tab | Phase 2 完成 |
| **4**（可选） — 加固 | 1-2 周 | Context compaction（自动总结 + 截断）+ Provider 切换 UI（base URL 配置界面）+ prompt 混淆加固 | Phase 3 完成 |

**MVP（Phase 0+1）目标**：可发布的"v2 alpha"——一个能浏览模块、与单 agent 对话、能从 v1 项目迁移的最小可用插件。

## 十二、Engine 详细设计要点

`@cbim/engine` 是 v2 的核心抽象，必须做到：

- **无 VS Code 依赖**：可以被 CLI、Web、其他 IDE 复用
- **子模块独立可用**：knowledge、memory、tools 之间靠接口耦合
- **Migration 单独成包**：一次性使用，不污染运行时
- **`discoverModules` 默认跳过目录**：递归扫描模块树时，以下目录永远不进入：`node_modules`、`dist`、`build`、`out`、`.git`、`.cbim`（已在步骤 1 作为根模块单独处理）、以及其他 dotfiles 目录（`.` 开头但不是 `.dna` 的目录）。此列表硬编码于 engine，不可由 config.yaml 覆盖

### 12.1 dispatch 子模块定位

**核心责任：实现 Claude Code CLI 同等的 multiagent 能力，完全在 v2 控制之下。**

dispatch 是客户端 multiagent 编排的核心，参考 Claude Code CLI 的成熟模式，自己实现 subagent spawn / 上下文隔离 / 消息路由 / tool 循环。

| 职责 | 说明 |
|--|--|
| Subagent spawn | `dispatch(toRole, task)` → 创建新 Messages API 对话，独立 system prompt + tools 装配 |
| Tool 循环 | 发请求 → 收响应 → 检测 `tool_use` → 执行本地 handler → 拼 `tool_result` → 继续，直到 `stop_reason='end_turn'` |
| 上下文隔离 | 父子 agent 各自维护独立 `messages` 数组，互不污染 |
| 结果返回 | 子对话最后一条 assistant message 作为父对话的 `tool_result` |
| 并发调度 | 多个子 agent 可以并发跑（不同 Messages API session，Node 异步 I/O 天然支持） |
| 生命周期 | 监听 stream 完成事件，触发 memory 写入 |

```typescript
// dispatch 核心循环草图
async function dispatch(
  role: AgentRole,
  task: string,
  client: Anthropic,
): Promise<string> {
  const tools = getToolSet(role)
  const systemPrompt = getSystemPrompt(role)
  const messages: MessageParam[] = [{ role: 'user', content: task }]

  while (true) {
    const response = await client.messages.create({
      model: getModel(),
      system: systemPrompt,
      tools: tools.map(t => ({ name: t.name, description: t.description, input_schema: t.input_schema })),
      messages,
    })

    // 累积 assistant 响应
    messages.push({ role: 'assistant', content: response.content })

    if (response.stop_reason === 'end_turn') {
      // 提取最终文本作为结果返回给父对话
      return extractTextResult(response.content)
    }

    if (response.stop_reason === 'tool_use') {
      // 执行所有 tool_use block，收集 tool_result
      const toolResults = await Promise.all(
        response.content
          .filter(b => b.type === 'tool_use')
          .map(async (block) => {
            const handler = tools.find(t => t.name === block.name)!.handler
            const result = await handler(block.input)
            return { type: 'tool_result', tool_use_id: block.id, content: result }
          })
      )
      messages.push({ role: 'user', content: toolResults })
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
 * 创建 agent 对话时传给 client.messages.create() 的 tools 参数。
 */
function getToolSet(role: AgentRole): ToolDefinition[]

/**
 * 返回所有 tool 的 handler 映射，供 dispatch tool 循环查找。
 */
function getToolHandlerMap(): Record<string, ToolHandler>
```

### 12.3 knowledge / memory 子模块

知识和记忆子模块的定位不变。具体接口契约已在 `packages/engine/.dna/contract.md`，不在此重复。

### 12.4 Streaming 行为

Messages API 支持 `client.messages.stream()` 细粒度 delta 流式输出。UI 层可以逐 token 渲染，提供实时反馈。dispatch 层可选择使用 `create()`（同步等待完整响应）或 `stream()`（流式），根据场景决定。

---

## 十三、待决与风险

**待决：**

- Webview 与扩展主进程的通信协议（postMessage 协议设计）—— Phase 1 决策
- 跨 IDE 兼容（Cursor / Windsurf / Continue）—— 暂不考虑，保持 VS Code 原生 API；engine 独立性留口子
- Provider 兼容性测试：OpenRouter / Bedrock / Vertex / 各种本地代理是否真的能跑 Messages API 协议——Phase 1 末必须测
- Context compaction 算法：Anthropic SDK 没自带 compaction，需要自己实现（监控 token → 主动总结 + 截断）
- Multiagent 调度的并发模型：Node 单线程下多 Messages API session 并发，需确认异步 I/O 是否足够（大概率足够，但需实测验证）

**风险：**

| 风险 | 影响 | 缓解 |
|--|--|--|
| Provider 兼容性差异 | 不同 provider 对 Messages API 的 tool_use 支持程度不一，可能出现行为差异 | Phase 1 末建立兼容性测试矩阵；MVP 阶段只承诺 Claude 直连 + OpenRouter |
| Context compaction 自己写 | 长会话可能超窗口限制，需要自实现总结 + 截断逻辑 | Phase 4（可选）实现；短期靠对话长度限制 |
| v1 用户的迁移成本 | `.claude/agents/<id>/<id>.md` 单文件直接复制到 `.cbim/agents/<id>.md`，风险低；主要复杂度在 CLAUDE.md 拆分 | 迁移 CLI 自动化 + 手动验证 |
| 多 agent 并发的资源消耗 | 多个 Messages API 并发请求，token 消耗可能较高 | 提供 token 预算控制；默认串行 dispatch，并发为可选 |
| 客户端编排代码维护成本 | 比 Managed Agents 多 200-400 行编排代码，需要自己处理 tool 循环、上下文管理 | 这是换取多 provider 的代价，可接受；Claude Code CLI 已验证此模式成熟 |

**不再适用的待决项：**

- ~~Managed Agents API 费用模型~~ → 不再使用 Managed Agents
- ~~Anthropic Console prompt 可见性~~ → prompt 不上传服务端，不适用
- ~~`canUseTool` 路径守卫验证~~ → 天然封闭，无需路径守卫

## 十四、下一步

1. **Phase 0 剩余**：
   - 把 `packages/engine/dispatch/` 和 `packages/engine/tools/` 的 `.dna/` 契约更新到客户端 multiagent 编排设计
   - 落定 `getToolSet(role)` 的完整 tool 清单和每个 tool 的 zod schema
2. **Phase 1 起点**：
   - Scaffold Messages API 调用（`client.messages.create()` + tool 循环）
   - 实现第一个 `cbim_*` tool handler（`cbim_module_get`）
   - 跑通单 agent 对话：user → extension → Messages API → tool_use → handler → tool_result → end_turn
3. **engine/knowledge 继续实现**：先把"读 `.cbim/dna/` + 递归 `.dna/`、构建 ModuleNode 树"跑通

---

> 本文档为 v2 启动阶段的总体设计依据。后续每个 Phase 完成时，应回头修订本文或新增 phase-N-report.md 记录实际偏差。
