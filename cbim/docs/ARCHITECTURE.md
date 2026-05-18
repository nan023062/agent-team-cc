# CBIM 架构文档

## 这是什么

CBIM（Capability × Content + Memory）是一个可部署到任意项目的多 Agent 协作框架。安装后，在项目根目录启动 Claude Code，主 session 就是"助手"——它是你与整个 Agent 团队之间唯一的对话入口。

你只需要和助手说话。助手负责理解意图、拆解任务、派发给合适的 Agent、汇总结果。

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
│  .dna/     │    │ .claude/agents/│    │  按蓝图实现交付      │
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
| **架构师** | 设计并维护项目知识体系，确保架构合规 | `.dna/`（内容层） |
| **HR** | Work agent 全生命周期：招募、培训、考核、归档 | `.claude/agents/`（能力层） |
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

---

## 两层治理

| 层级 | 治理者 | 管辖范围 |
|------|--------|---------|
| **能力层** | HR | `.claude/agents/`（agent 定义与 skills） |
| **内容层** | 架构师 | 项目各级 `.dna/`（模块知识三件套） |

**铁律**：能力进 `.claude/agents/`，内容进 `.dna/`，不得混入对方。

---

## 记忆系统

**助手是唯一的记忆持有者。** Subagent 专注执行，不直接操作记忆。

| 层级 | 路径 | 生命周期 |
|------|------|---------|
| 短期 | `cbim/memory/store/short/` | 按天自动清理 |
| 中期 | `cbim/memory/store/medium/` | 长期保留，手动管理 |

- **自动写入** — session 结束时，Stop hook 自动提炼本次调度内容写入短期记忆
- **自动加载** — session 启动时，SessionStart hook 自动注入近期相关记忆作为上下文
- **按需查询** — session 中途可主动通过 `cbim/memory/engine/cli.py query` 检索历史

---

## 能力进化路径（HR 侧）

```
session 记录 / 用户反馈 / 评审官报告
    ↓ HR 从 cbim/memory/store/ 提炼
.claude/agents/<id>/skills/   新增 Skill
    ↓ 多次验证后内化
.claude/agents/<id>/<id>.md   更新 Soul / Identity
```

## 知识进化路径（架构师侧）

```
cbim/memory/store/            session 原始记录
    ↓ 架构师提炼
.dna/architecture.md + contract.md
    ↓ 出现 ≥2 次的确定性流程
.dna/workflows/          新增 Workflow
    ↓ 模块职责过重
拆分为多个子模块
```

---

## 目录结构（部署后）

```
<project>/
├── CLAUDE.md                          ← 助手身份（主 session）
│
├── .claude/
│   ├── settings.json                  ← 权限配置 + hook 注册
│   └── agents/                        ← 从 cbim/cc-template/agents/ 安装
│       ├── architect/
│       │   ├── architect.md
│       │   └── skills/
│       ├── hr/
│       │   ├── hr.md
│       │   └── skills/
│       ├── auditor/
│       │   └── auditor.md
│       └── programmer/
│           └── programmer.md
│
├── .dna/                          ← 架构师创建，项目知识根模块
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   └── contract.md
│
└── cbim/                              ← 框架本体
    ├── install.py / install.bat
    ├── cc-template/                   ← Claude Code 安装模板（hooks + agent 模板）
    ├── knowledge/                     ← 知识库 CRUD（engine/cli.py）
    ├── memory/                        ← 记忆引擎
    │   ├── engine/                    ← Python 包（ChromaDB 驱动）
    │   └── store/
    │       ├── short/                 ← 短期记忆（gitignore）
    │       └── medium/               ← 中期记忆（gitignore）
    └── preview/                       ← 本地预览服务（记忆 / 能力 / 知识）
```
