# ARCHITECTURE.md — Agent Team 架构

## 这是什么

一个可部署到任意项目的多 Agent 协作框架。安装后，在项目根目录启动 Claude Code，主 session 就是"助手"——它是你与整个 Agent 团队之间唯一的对话入口。

你只需要和助手说话。助手负责理解你的意图、拆解任务、派发给合适的 Agent、汇总结果。

---

## 架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 所有交互
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  助手（主 session，CLAUDE.md）                                   │
│  · 唯一对外接口  · 任务拆解  · 派发调度  · 汇总结果             │
└──────┬───────────────────┬──────────────────┬───────────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
┌────────────┐    ┌────────────────┐    ┌──────────────────────┐
│  架构师    │    │      HR        │    │  Work Agents         │
│            │    │                │    │  (programmer, ...)   │
│ 内容层治理 │    │  能力层治理    │    │  执行具体任务        │
│ .aimodule/ │    │ .claude/agents/│    │  按蓝图实现交付      │
└────────────┘    └──────┬─────────┘    └──────────────────────┘
                         │
                    ┌────┴────┐
                    │  评审官  │
                    │  独立审查│
                    └─────────┘
```

---

## 四个核心 Agent

| Agent | 职责 | 管辖范围 |
|-------|------|---------|
| **助手** | 唯一对外接口，拆解调度，汇总结果 | 全局协调 |
| **架构师** | 设计并维护项目知识体系，确保架构合规 | `.aimodule/`（内容层） |
| **HR** | Work agent 全生命周期：招募、培训、考核、归档 | `.claude/agents/`、`memory/`（能力层） |
| **评审官** | 独立批判审查，只读，只由助手派发 | 全局只读 |

核心 4 个 Agent **永远不在 HR 的治理范围内**，用户可信任它们的行为边界不会被修改。

Work agents（如程序员）由 HR 按需创建，助手通过 HR 申请后派发。

---

## 如何使用

直接告诉助手你要做什么，不用指定具体 Agent：

| 你想做 | 直接说 |
|--------|--------|
| 初始化项目知识体系 | 请初始化本项目的模块知识体系 |
| 新建一个功能模块 | 新建一个 combat 模块 |
| 按蓝图实现代码 | 按当前蓝图实现登录接口 |
| 审查某个设计/改动 | 审一下这次改动 |
| 查历史决策 | 查一下 combat 模块的历史决策 |

**Slash 命令**（HR 例行任务，手动触发）：

| 命令 | 用途 | 建议频率 |
|------|------|---------|
| `/hr-daily-signal` | 采集 work agent 能力缺口信号 | 每日 |
| `/hr-weekly-assessment` | 周度考核与培训 | 每周 |

---

## 知识体系：.aimodule/

架构师在每个"模块"目录下维护一套知识三件套：

```
<任意目录>/
└── .aimodule/
    ├── module.json        # 元数据（name、owner 必填）
    ├── architecture.md    # 内部架构设计
    └── contract.md        # 对外接口/API
```

根模块还额外有：
```
<项目根>/
└── .aimodule/
    └── index.md           # 全树所有模块的路径列表
```

**铁律**：知识三件套只装项目/模块相关内容，不引用 agent 能力规范。

---

## 记忆系统

**主 agent 是唯一的记忆持有者。** Subagent 专注执行，不直接操作记忆。

记忆系统提供三项能力：

- **自动写入** — 每次 session 结束后，自动记录本次调度了哪些 subagent、任务内容、结果与遇到的问题
- **自动加载** — 每次 session 启动时，自动注入近期相关记忆作为上下文
- **按需查询** — session 中途可主动检索历史记录，辅助决策

实现细节封装在 `.claude/skills/memory/SKILL.md`，用户无需关心。

---

## 两层治理

| 层级 | 治理者 | 管辖范围 |
|------|--------|---------|
| **能力层** | HR | `.claude/agents/`（agent 定义与 skills）、`memory/` |
| **内容层** | 架构师 | 各项目 `.aimodule/`（模块知识三件套） |

**铁律**：能力进 `.claude/agents/`，内容进 `.aimodule/`，不得混入对方。

---

## 能力进化路径（HR 侧）

```
执行记录 / 用户反馈 / 评审官报告
    ↓ HR 提炼
memory/<agent-id>/         原始经验
    ↓ 出现 ≥2 次
.claude/agents/<id>/skills/  Skill
    ↓ 多次验证后内化
.claude/agents/<id>/<id>.md  Soul / Identity
```

## 知识进化路径（架构师侧）

```
memory/changelogs/          原始变更记录
    ↓ 架构师提炼
.aimodule/architecture.md + contract.md
    ↓ 出现 ≥2 次的确定性流程
.aimodule/workflows/        Workflow
    ↓ 模块职责过重
拆分为多个子模块
```

---

## 目录结构（部署后）

```
<project>/
├── CLAUDE.md                          ← 助手身份（主 session）
├── .env                               ← 环境变量（本地，不提交 git）
├── .venv/                             ← Python 虚拟环境（不提交 git）
│
├── .claude/
│   ├── settings.json                  ← 权限配置
│   ├── agents/
│   │   ├── architect/
│   │   │   ├── architect.md
│   │   │   └── skills/
│   │   ├── hr/
│   │   │   ├── hr.md
│   │   │   └── skills/
│   │   ├── auditor/
│   │   │   ├── auditor.md
│   │   │   └── skills/
│   │   └── programmer/
│   │       └── programmer.md
│   └── commands/
│       ├── hr-daily-signal.md         ← /hr-daily-signal
│       └── hr-weekly-assessment.md   ← /hr-weekly-assessment
│
├── .aimodule/                         ← 架构师创建，项目知识根模块
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   └── contract.md
│
└── memory/
    ├── entries/                       ← Agent 执行记录（明文 md，可提交 git）
    ├── chroma_db/                     ← 向量索引（不提交 git，可随时重建）
    ├── memory_index.py                ← 构建向量索引
    ├── memory_query.py                ← 向量查询（返回文件路径）
    └── requirements.txt
```
