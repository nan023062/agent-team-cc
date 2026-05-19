# CBIM v2 初始规划

> 状态：初稿 · 2026-05-20
> 范围：master 分支后续开发
> 关联：v1 已固化于 `v1-claude-code` 分支

## 一、目标与定位

把 v1 的"多 Agent × 模块知识 × 三阶段记忆"哲学搬到 **VS Code 插件**形态，**底层用 Claude Agent SDK 替代 Claude Code 的 subagent + hooks 机制**，为用户提供 GUI 化的 CBIM 协作环境。

**不是简单"打包 v1"**，而是利用 SDK 的能力做 v1 做不到的事：

- 自定义 subagent 调度（不再受 Claude Code 子代理黑盒限制）
- 自定义 tool gating / permission（更细粒度）
- IDE 集成：文件树联动、diff 预览、状态可视化
- 跨 IDE 复用潜力（engine 包独立于 VS Code）

## 二、设计哲学

继承 v1 的核心，调整必要部分：

| 维度 | v1 | v2 |
|--|--|--|
| 多 Agent | 4 内置 + work agents | 沿用 |
| 业务/能力分离 | `.dna/` ↔ agents/ | 沿用 |
| 模块约定 | `module.md`（frontmatter+body） | 沿用 |
| 三阶段记忆 | short → medium → distilled | 沿用，distilled 独立目录 |
| 模型 | Claude Code 默认链 | Claude Agent SDK（仅 Claude，MVP） |
| 状态存储 | 分散（`.claude/`、`cbim/`、`.dna/`、`CLAUDE.md`） | 收敛到 `.cbim/` + 子模块 `.dna/` |

## 三、技术栈

| 层 | 选型 | 理由 |
|--|--|--|
| 宿主 | VS Code Extension API（TypeScript） | 标配 |
| 模型链 | `@anthropic-ai/claude-agent-sdk` | Anthropic 官方 SDK，与 v1 推理路径一致 |
| Engine | TypeScript（重写，不再用 Python） | 与 SDK 同语言，零 IPC 开销 |
| UI | Webview + React | 复杂面板必备 |
| 包管理 | pnpm workspaces | monorepo 标配 |
| 构建 | tsup / vite（按包决定） | 简单可靠 |

## 四、仓库结构（Monorepo）

```
agent-team-cc/                       # master 分支
├── docs/                            # 设计文档
├── packages/
│   ├── engine/                      # @cbim/engine — 纯 TS，无 VS Code 依赖
│   │   ├── knowledge/              # 模块 CRUD、snapshot 构建
│   │   ├── memory/                 # 三阶段蒸馏
│   │   ├── dispatch/               # agent 调度（基于 Claude Agent SDK）
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
│   │   └── distilled/              # 已固化归档
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
- **模块树索引**由 engine 自动从文件系统扫描生成，不再手动维护 `index.md`

## 六、模块约定（沿用 v1）

完全沿用 v1 的 `module.md` 约定（参见 `cbim/knowledge/dna-convention.md` on `v1-claude-code` 分支）：

- `.dna/` 内**唯一硬要求**：`module.md` 存在
- `module.md` = YAML frontmatter（元数据）+ Markdown 正文（设计）
- 正文内容：
  - 叶子模块：Positioning + Mermaid classDiagram + Key Decisions
  - 父模块：Positioning + 子模块关系图 + Key Decisions
- 可选扩展：`contract.md`、`workflows/`、任意自定义文件

## 七、v1 → v2 能力映射

| v1 机制 | v2 实现 |
|--|--|
| `CLAUDE.md` 启动注入 | 扩展激活时读取 `.cbim/config.yaml` 并 assemble 为 system prompt |
| `.claude/agents/<id>.md` subagent 配置 | extension 自己解析 `.cbim/agents/`，调 SDK `query()` 启动子任务 |
| `Stop` hook 写记忆 | SDK 完成事件回调 → 写 `.cbim/memory/short/` |
| `SessionStart` hook 注入快照 | 扩展打开 chat 时构建 snapshot，作为 system prompt 一部分 |
| `python cbim/knowledge/engine/cli.py` | VS Code Command Palette + Sidebar 操作（也可走 `@cbim/cli`） |
| Python `cbim.preview` HTTP 服务 | 同进程 Webview panel（无独立服务） |
| Python `memory/engine` | `packages/engine/memory/` TS 移植 |
| `.dna/index.md` 手维护 | engine 自动扫描生成，不入库 |

## 八、v1 → v2 迁移路径

绿地重写，但提供迁移 CLI 帮助现有 v1 项目升级：

```bash
npx @cbim/cli migrate <project-path>
```

**迁移动作**：

| v1 位置 | v2 位置 | 动作 |
|--|--|--|
| `<project>/.dna/` | `<project>/.cbim/dna/` | 整体搬迁 |
| `<project>/.dna/index.md` | （删除） | 不再需要，engine 自动生成 |
| `<project>/.claude/agents/<id>/` | `<project>/.cbim/agents/<id>.md` | 整合多文件结构为单文件 |
| `<project>/cbim/memory/store/` | `<project>/.cbim/memory/` | 整体搬迁 |
| `<project>/CLAUDE.md` | `<project>/.cbim/config.yaml`（角色定义部分）+ 保留（用户自由内容部分） | 拆分 |
| `<project>/src/x/.dna/` | `<project>/src/x/.dna/` | 不变 |
| `<project>/cbim/` 框架文件 | （删除） | v2 用 npm 包，不入用户库 |

**用户行动**：

1. 安装 v2 插件：`code --install-extension cbim.vsix`
2. 在项目内运行：`npx @cbim/cli migrate .`
3. 在 VS Code 内打开侧边栏 CBIM 视图，验证模块树、agents、memory 加载正常

## 九、Phase 路线

| Phase | 周期 | 交付 | 关键依赖 |
|--|--|--|--|
| **0** — 骨架 + 迁移 | 1 周 | monorepo（pnpm workspaces）+ `@cbim/engine/knowledge`（读 `.cbim/dna/` + 子模块 `.dna/`）+ `@cbim/cli migrate`（v1→v2） | tsup, pnpm |
| **1** — 单 agent + 知识浏览 | 2 周 | VS Code extension 框架 + Sidebar 模块树 + 单个 chat panel + SDK `query()` 接入 + 自动注入激活模块 `module.md` | `@anthropic-ai/claude-agent-sdk` |
| **2** — 多 agent 协作 | 2 周 | `@cbim/engine/dispatch` + architect/programmer agents 导入 + chat panel 显示活跃 agent + 任务进度 | Phase 1 完成 |
| **3** — 记忆系统 | 2 周 | `@cbim/engine/memory` 三阶段蒸馏 TS 移植 + 自动 distill 触发 + Webview preview tab | Phase 2 完成 |

**MVP（Phase 0+1）目标**：6 周可发布的"v2 alpha"——一个能浏览模块、与单 agent 对话、能从 v1 项目迁移的最小可用插件。

## 十、Engine 详细设计要点

`@cbim/engine` 是 v2 的核心抽象，必须做到：

- **无 VS Code 依赖**：可以被 CLI、Web、其他 IDE 复用
- **三个子模块独立可用**：knowledge、memory、dispatch 之间靠接口耦合
- **Migration 单独成包**：一次性使用，不污染运行时

```typescript
// 接口草图（待 Phase 0 落地）
interface KnowledgeEngine {
  listModules(): ModuleNode[]
  loadModule(path: string): Module
  buildSnapshot(focusModule?: string): Snapshot
}

interface MemoryEngine {
  appendShort(session: SessionRecord): void
  distillToMedium(criteria: DistillCriteria): MediumRecord[]
  promoteToDistilled(record: MediumRecord): void
  query(intent: string): MemoryHit[]
}

interface DispatchEngine {
  dispatch(agent: AgentRef, task: TaskSpec): Promise<TaskResult>
  spawnSubagent(agent: AgentRef, parentCtx: Context): Subagent
}
```

具体接口在 Phase 0 完成时落定。

## 十一、待决与风险

**待决：**

- Claude Agent SDK 的 subagent 机制深度（用 SDK 默认 / 自己在 SDK 之上实现调度）—— Phase 0 启动前需先调研 SDK API
- Webview 与扩展主进程的通信协议（postMessage 协议设计）—— Phase 1 决策
- 跨 IDE 兼容（Cursor / Windsurf / Continue）—— 暂不考虑，保持 VS Code 原生 API；engine 独立性留口子

**风险：**

- Claude Agent SDK 的能力边界未知（不能像 Claude Code 那样自动注入 hook），可能需要在 extension 层补足
- v1 用户的迁移成本：`.claude/agents/` 多文件结构 → `.cbim/agents/` 单文件，要小心保留原 SOUL/IDENTITY/skills 内容
- 多 agent 协作的并发模型：v1 靠 Claude Code 进程隔离，v2 在一个 Node 进程内可能需要显式 worker 隔离

## 十二、下一步

1. **Phase 0 启动**：创建 monorepo 骨架（`pnpm-workspace.yaml` + `packages/{engine,extension,ui,cli}` + 基础 tsconfig + tsup）
2. **同步调研 Claude Agent SDK**：阅读官方文档与示例，确定 dispatch 设计的关键约束
3. **engine/knowledge 优先实现**：先把"读 `.cbim/dna/` + 递归 `.dna/`、构建 ModuleNode 树"跑通

---

> 本文档为 v2 启动阶段的总体设计依据。后续每个 Phase 完成时，应回头修订本文或新增 phase-N-report.md 记录实际偏差。
