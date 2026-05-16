# ARCHITECTURE.md — Agent Team 架构

## 架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  秘书（CLAUDE.md / 主 session）                                  │
│  · 唯一对外接口    · 任务拆解    · 调度 subagent    · 汇总结果   │
└──────┬───────────────────┬──────────────────┬───────────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
┌────────────┐    ┌────────────────┐    ┌──────────────────────┐
│  架构师    │    │      HR        │    │  Work Agents         │
│            │    │                │    │  (programmer, ...)   │
│  内容层    │    │  能力层        │    │                      │
│  治理者    │    │  治理者        │    │  执行具体任务        │
│            │    │                │    │  按蓝图实现交付      │
│ .aimodule│   │  .claude/agents│    │                      │
└────────────┘    └────────────────┘    └──────────────────────┘
       │                   │
       │              ┌────┴────┐
       │              │  评审官  │
       │              │  独立审查│
       │              └─────────┘
```

---

## 目录结构

```
<repo-root>/
├── CLAUDE.md                          ← 秘书身份（主 session）
│
├── .claude/
│   ├── settings.json                  ← 权限配置
│   ├── agents/                        ← subagent 定义（递归扫描）
│   │   ├── architect/
│   │   │   ├── architect.md
│   │   │   └── skills/
│   │   │       ├── module-crud.md
│   │   │       ├── arch-compliance.md
│   │   │       └── knowledge-governance.md
│   │   ├── hr/
│   │   │   ├── hr.md
│   │   │   └── skills/
│   │   │       ├── recruitment.md
│   │   │       ├── training.md
│   │   │       └── assessment.md
│   │   ├── auditor/
│   │   │   ├── auditor.md
│   │   │   └── skills/
│   │   │       └── audit-review.md
│   │   └── programmer/
│   │       └── programmer.md
│   └── commands/                      ← slash commands（手动触发）
│       ├── new-project.md
│       ├── hr-daily-signal.md
│       └── hr-weekly-assessment.md
│
├── memory/                            ← 跨任务记忆（HR 写入）
│   └── hr/
│       └── agent-signals.md
│
└── docs/
    ├── ARCHITECTURE.md                ← 本文件
    └── aimodule-convention.md      ← 内容层 .aimodule/ 约定
```

---

## 核心机制

### 秘书 = 主 session

`CLAUDE.md` 即秘书身份。打开 Claude Code 后主 session 本身就是秘书，无需额外启动。

### Subagent 派发

所有业务 agent 以 subagent 模式运行，通过 `Agent` tool 调度：

```
Agent(
  description="[子任务一句话描述]",
  prompt="""
你是[角色名]。读取 .claude/agents/<id>/<id>.md 加载完整身份。

本次任务：[具体任务]
知识上下文：[project-path]/.aimodule/[module]/
"""
)
```

每次 spawn 均为独立 context（fresh load），执行完毕后散。

**并行**：无依赖子任务同时调用多个 `Agent` tool。**串行**：有依赖时前序结果作为后序输入。

### Agent 注册

每个 agent 存放在 `.claude/agents/<id>/` 目录下：

```
.claude/agents/<id>/
├── <id>.md       ← agent 定义（YAML frontmatter + SOUL + IDENTITY）
└── skills/       ← 该 agent 的 skill 文件
    └── <skill>.md
```

Agent 文件 frontmatter 字段：

| 字段 | 说明 |
|------|------|
| `name` | agent 唯一标识（与目录名一致） |
| `description` | 一句话描述，Claude 据此判断何时委托 |
| `model` | 使用的模型 |
| `tools` | 允许使用的工具列表 |

Claude Code 递归扫描 `.claude/agents/`，`name` 字段为唯一标识，子目录路径不影响识别。

### 权限约束

权限声明在 `tools` frontmatter 和 IDENTITY 铁律节中，agent 自觉遵守：

| Agent | tools | Write 范围 |
|-------|-------|-----------|
| architect | Read, Write, Edit, Glob, Grep, Bash | 限 `.aimodule/` |
| hr | Read, Write, Edit, Glob, Grep | 限 `.claude/agents/`, `memory/` |
| auditor | Read, Glob, Grep, Bash | 只读，无 Write/Edit |
| programmer | Read, Write, Edit, Glob, Grep, Bash | 限物理工作区 |

### HR 例行任务

HR 日常治理通过 slash commands 手动触发：

| 命令 | 用途 | 建议频率 |
|------|------|---------|
| `/hr-daily-signal` | work agent 能力缺口信号采集 | 每日 |
| `/hr-weekly-assessment` | 周度考核与培训 | 每周 |

### 项目初始化

当前仓库即当前项目，无多项目注册表。`/new-project` 命令在仓库根目录初始化 `.aimodule/` 知识体系，由架构师完成根模块结构创建。

---

## 双治理层

两层治理严格分离：

| 层级 | 治理者 | 管辖范围 |
|------|--------|---------|
| **能力层** | HR | `.claude/agents/`（agent 定义与 skills）、`memory/`（跨任务经验） |
| **内容层** | 架构师 | 各项目 `.aimodule/`（模块知识体系） |

**铁律**：能力进 `.claude/agents/`，内容进 `.aimodule/`，混入对方的内容一律不得升格。

---

## 能力进化金字塔（HR 侧）

```
执行记录（用户反馈、评审官报告、memory 文件）
    ↓ HR 提炼
Memory   memory/<id>/
    ↓ 反复出现 ≥2 次
Skill    .claude/agents/<id>/skills/<name>.md
    ↓ 多次验证后内化
Soul / Identity   .claude/agents/<id>/<id>.md
```

## 知识进化金字塔（架构师侧）

```
Changelog（decision / incident / constraint 原始记录）
    ↓ 架构师提炼
architecture.md / contract.md（知识三件套）
    ↓ 反复出现 ≥2 次
Workflow（模块内确定性流程）
    ↓ 模块边界超载
拆分（一模块 → 多子模块）
```
