# CBIM v2 — Phase 1 起点

> 状态：Phase 0 已收尾 · 2026-05-20
> 上一节点：`docs/v2-plan.md`（v2 终版规划）
> 当前分支：`master`

## Phase 0 收尾确认

| 项 | 位置 | 状态 |
|--|--|--|
| Monorepo 骨架 | `packages/{engine,extension,ui,cli}` | ✅ |
| 5 份 module blueprint | `packages/{,*/}/.dna/module.md` | ✅ |
| `engine/knowledge` 契约 + 实现 | `packages/engine/.dna/contract.md`、`packages/engine/src/knowledge/` | ✅（35 tests） |
| `engine/migration` 契约 + 实现 | `packages/cli/.dna/contract.md`、`packages/engine/src/migration/` | ✅（28 tests） |
| `engine/dispatch` 契约 | `packages/engine/.dna/dispatch-contract.md` | ✅ |
| `engine/tools` 契约 | `packages/engine/.dna/tools-contract.md`（38 tool） | ✅ |
| v2-plan 终版 | `docs/v2-plan.md` | ✅（4 轮迭代后锁定） |
| 配置 schema | `docs/v2-config-schema.md` | ✅ |
| CBI 对称形式化 | `cbim/knowledge/dna-convention.md` + `docs/v2-plan.md §七` | ✅ |
| Agent SDK 计费核实 | API key 用户零额外成本（BYOK 模式） | ✅ |

## v2 技术核心（一句话）

> import Claude Code 作为库（`@anthropic-ai/claude-agent-sdk`）+ CBIM 编排层。SDK 负责 agent loop / tool 执行 / subagent / session 持久化 / 权限拦截；CBIM 只加 ~200 行 coordinator + ~38 个 cbim_* MCP tools + memory engine。

## Phase 1 起点（按顺序）

### Step 1 — 安装 SDK 依赖

在 `packages/engine` 和 `packages/extension` 加 `@anthropic-ai/claude-agent-sdk` 依赖。

```bash
pnpm --filter @cbim/engine add @anthropic-ai/claude-agent-sdk zod
pnpm --filter @cbim/vscode-extension add @anthropic-ai/claude-agent-sdk
```

### Step 2 — 5 个内置 agent system prompt 常量

位置：`packages/engine/src/dispatch/prompts/`（5 个 TS 文件）

| Agent | 参考来源（v1） |
|--|--|
| assistant | `cbim/cc-template/CLAUDE-template.md` 或 v1 `CLAUDE.md` |
| architect | `cbim/cc-template/agents/architect/architect.md` |
| programmer | `cbim/cc-template/agents/programmer/programmer.md` |
| hr | `cbim/cc-template/agents/hr/hr.md` |
| auditor | `cbim/cc-template/agents/auditor/auditor.md` |

**关键约束**：v1 提示词是给 Claude Code CLI 用的（含 settings.json / hooks 等 v1 概念）；改写时去掉 v1 特有引用，改为 v2 的 cbim_* MCP tool 语义。

### Step 3 — 首个 cbim_* MCP tool

推荐先做 `cbim_module_get`：
- `engine/knowledge` 已就绪，可直接包装
- 是最常被调用的 tool（任何 agent 读模块都用）
- 验证 `createSdkMcpServer` + `tool(...)` 集成路径

位置：`packages/engine/src/tools/domains/module.ts`

### Step 4 — scaffold dispatch + coordinator

按 `packages/engine/.dna/dispatch-contract.md` 实施：
- `loadAgentConfig(role, ctx): AgentConfig`
- `dispatch(req, ctx): AsyncIterable<DispatchEvent>` —— 包 SDK `query()`
- `runCoordinator(userInput, ctx): AsyncIterable<DispatchEvent>` —— assistant 入口

**dispatch 子模块只做 SDK 配置装配 + 事件转发**，不再发明 agent loop。

### Step 5 — 单 agent 端到端验证

最小 demo：
1. CLI 或 extension 触发 `runCoordinator("hello")`
2. assistant agent 通过 SDK `query()` 跑起来
3. 流式事件输出到 stdout / Webview
4. 任务完成（`session.status_idle`）触发 memory 写入 stub

证明 SDK 集成正确、coordinator 路径打通、event flow 透明。

## Phase 0 遗留的轻量项

1. **v1 SKILL.md 缺 frontmatter** —— `cbim/knowledge/skills/*/SKILL.md` 是 v1 格式（无 frontmatter）。`@cbim/cli migrate` 应该自动补 frontmatter（name 从目录名，keywords 启发式提取）。Phase 1 顺手做
2. **`docs/v2-tools-spec.md` 未创建** —— v2-plan §八.4 引用了，但 `tools-contract.md` 已经足够详细。可不写，或 Phase 1 末根据实际需要补

## 流程纪律

**严格 knowledge-first**：每个新代码任务先派 architect 写 blueprint / sketch，再派 programmer 实施。Phase 1 第一步（SDK 集成模式）就应该先让 architect 出一份"SDK 集成 sketch"——确定 `dispatch.ts` 怎么组织、`tools/mcp-server.ts` 怎么导出、role config 怎么装配——然后 programmer 按图施工。

## 关键 commits 索引

| Commit | 内容 |
|--|--|
| `1513aa3` | Formalize CBI symmetry（最新） |
| `1730c0a` | dispatch + tools contracts |
| `8935047` | v2-plan 锁定 claude-agent-sdk（终版路线） |
| `ffecd55` | finalize migrate + config schema |
| `e225eba` | engine/knowledge + migration 实现 |
| `7ac8891` | cli migrate 实现 |
| `2c6ce0c` | monorepo 骨架 |
| `11c1c83` | 4 packages architect blueprints |

## 已知风险（继续跟踪）

- 🔴 **Agent SDK 计费模型**：API key 用户当前不受影响，但 Anthropic 可能后续引入新规则。Phase 1 末再次核实
- 🟡 **OpenRouter 长期兼容性**：事实可用，非官方支持，未来 SDK 升级可能引入不兼容
- 🟡 **SDK 版本绑定**：pin 一个稳定版本，升级前要充分测试
- 🟡 **Context compaction**：SDK 不带，长 session 需要 v2 在 memory 子模块实现总结策略
