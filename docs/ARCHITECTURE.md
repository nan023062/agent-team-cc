# ARCHITECTURE.md — Claude Code 版 Agent Team 架构

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
│ .aiworkspace│   │  .claude/agents│    │                      │
└────────────┘    └────────────────┘    └──────────────────────┘
       │                   │
       │              ┌────┴────┐
       │              │  评审官  │
       │              │  独立审查│
       │              └─────────┘
```

---

## 与 OpenClaw 版本的关键差异

### 1. 秘书 = 主 session（CLAUDE.md）

OpenClaw 版本中秘书是一个独立 agent（`main/SOUL.md + IDENTITY.md`），通过 gateway 运行。

**Claude Code 版本**：秘书身份写入 `CLAUDE.md`，主 session 本身就是秘书。无需 spawn 秘书，直接就是秘书。

### 2. Subagent 派发：Agent tool

| OpenClaw | Claude Code |
|----------|-------------|
| `sessions_spawn(agentId=X, runtime="subagent")` | `Agent(description=..., prompt=...)` tool |
| `agents_list` | 读取 `.claude/agents/` 目录 |

派发模式（秘书 prompt 中）：
```
Agent(
  description="[子任务一句话描述]",
  prompt="""
你是[角色]。先读取 .claude/agents/<agent-id>.md 加载你的完整身份。

本次任务：[具体任务]
知识上下文：[project-path]/.aiworkspace/[module]/
"""
)
```

**关键**：每个 subagent 每次都从文件重新加载身份（fresh context），与 OpenClaw 行为一致。

### 3. Agent 注册：.claude/agents/ 目录

| OpenClaw | Claude Code |
|----------|-------------|
| `openclaw.json` agents 列表 | `.claude/agents/<id>.md` 文件 |
| 3 个文件（SOUL + IDENTITY + openclaw entry）| 1 个文件（含 YAML frontmatter） |

Agent 文件格式：
```markdown
---
name: <agent-id>
description: <一句话描述>
model: claude-<model>
tools: Read, Write, Edit, Glob, Grep, Bash
---

[SOUL 内容]
[IDENTITY 内容]
```

### 4. 权限约束：声明式（非系统强制）

OpenClaw 通过 runtime 强制隔离 agent 权限。Claude Code 无 per-subagent 文件系统沙箱。

**替代方案**：权限约束写入 agent 文件的 `tools` frontmatter 和 IDENTITY 铁律节，依赖 agent 自觉遵守。

| Agent | tools 权限 |
|-------|-----------|
| architect | Read, Write, Edit, Glob, Grep, Bash（Write 限 `.aiworkspace/`） |
| hr | Read, Write, Edit, Glob, Grep（Write 限 `.claude/agents/`, `memory/`） |
| auditor | Read, Glob, Grep, Bash（只读，无 Write/Edit） |
| programmer | Read, Write, Edit, Glob, Grep, Bash（Write 限物理工作区） |

### 5. HEARTBEAT → Slash Commands

| OpenClaw | Claude Code |
|----------|-------------|
| HEARTBEAT cron 每日 18:00 | `/hr-daily-signal` 手动触发 |
| HEARTBEAT cron 每周一 10:00 | `/hr-weekly-assessment` 手动触发 |

Slash commands 位于 `.claude/commands/`，无自动调度，需用户手动执行。

### 6. 项目注册：config/projects.json

| OpenClaw | Claude Code |
|----------|-------------|
| `workspace/projects.json` | `config/projects.json` |
| `_convention` + `_project_schema` + `projects` | 同结构，原样迁移 |

`/new-project <name> <path>` 命令自动完成注册 + 根模块初始化。

---

## 目录结构

```
D:\GitRepository\agentic-os-claude\
├── CLAUDE.md                          ← 秘书身份（主 session）
│
├── .claude/
│   ├── settings.json                  ← 权限配置
│   ├── agents/                        ← Claude Code 原生 subagent 定义
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
│   └── commands/                      ← slash commands
│       ├── new-project.md
│       ├── hr-daily-signal.md
│       └── hr-weekly-assessment.md
│
├── memory/                            ← 跨任务记忆（HR 写入）
│   └── hr/
│       └── agent-signals.md
│
├── config/
│   └── projects.json                  ← 项目注册表
│
└── docs/
    ├── ARCHITECTURE.md                ← 本文件
    └── aiworkspace-convention.md      ← 内容层 .aiworkspace/ 约定
```

---

## 双治理层

两层治理严格分离，铁律：

| 层级 | 治理者 | 管辖范围 |
|------|--------|---------|
| **能力层** | HR | `.claude/agents/`（agent 定义）、`memory/`（跨任务经验） |
| **内容层** | 架构师 | 各项目 `.aiworkspace/`（模块知识体系） |

能力进 `.claude/agents/`，内容进 `.aiworkspace/`，混入对方的内容一律不得升格。

---

## 验证检查清单

1. 打开 Claude Code，确认 `CLAUDE.md` 被加载（秘书身份体现在行为中）
2. 执行 `/new-project <name> <path>`，确认写入 `config/projects.json` 并触发架构师初始化根模块
3. 提一个编码需求，确认秘书能正确拆解并 spawn 架构师 + 程序员 subagent
4. 检查 subagent 是否正确读取了 `.claude/agents/<agent>.md` 并按身份行事
5. 执行 `/hr-daily-signal`，确认 HR subagent 被 spawn 并写入 `memory/hr/agent-signals.md`
