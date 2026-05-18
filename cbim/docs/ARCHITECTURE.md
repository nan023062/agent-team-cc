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
| **架构师** | 设计并维护项目知识体系，架构评审 | `.dna/`（内容层） |
| **HR** | Work agent 全生命周期：招募、培训、考核、归档 | `.claude/agents/`（能力层） |
| **评审官** | 独立批判审查，只读，只由助手派发 | 全局只读 |

核心 4 个 Agent **永远不在 HR 的治理范围内**。

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

### 治理即评审

架构师和 HR 的治理过程均模拟资深 leader review，分两个维度：

| | 架构师（arch-governance） | HR（hr-assessment） |
|---|---|---|
| **维度一** | 架构设计合理性（18 因子，三序遍历） | 定义合理性（14 因子，纵横两层） |
| **维度二** | 知识与工作区一致性 | 定义与表现一致性 |
| **脚本化** | `arch-governance/check.py` 自动检查 8 项 | `hr-assessment/check.py` 自动检查 3 项 |
| **阈值配置** | `arch-governance/config.json` | `hr-assessment/config.json` |

---

## 记忆系统

**助手是唯一的记忆持有者。** Subagent 专注执行，不直接操作记忆。

| 层级 | 路径 | 生命周期 |
|------|------|---------|
| 短期 | `cbim/memory/store/short/` | 按天自动清理 |
| 中期 | `cbim/memory/store/medium/` | 长期保留，手动管理 |

- **SessionStart hook** — `load-memory.py` 自动执行两件事：
  1. 生成项目知识快照（模块树 + agent 列表），注入会话上下文
  2. 加载近期相关记忆，注入会话上下文
- **Stop hook** — `write-memory.py` 自动提炼本次调度内容写入短期记忆
- **按需查询** — 会话中途可通过 `cbim/memory/engine/cli.py query` 检索历史

---

## 能力进化路径（HR 侧）

```
session 记录 / 用户反馈 / 评审官报告
    ↓ HR 从 cbim/memory/store/ 提炼
cbim/knowledge/skills/<name>/SKILL.md   新增或更新 Skill
    ↓ 多次验证后内化
.claude/agents/<id>/<id>.md             更新 Soul / Identity
```

## 知识进化路径（架构师侧）

```
cbim/memory/store/            session 原始记录
    ↓ 架构师提炼
.dna/architecture.md + contract.md
    ↓ 出现 ≥2 次的确定性流程
.dna/workflows/<name>/        新增 Workflow
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
│       │   └── architect.md
│       ├── hr/
│       │   └── hr.md
│       ├── auditor/
│       │   └── auditor.md
│       └── programmer/
│           └── programmer.md
│
├── .dna/                              ← 架构师创建，项目知识根模块
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   ├── contract.md
│   └── workflows/
│
└── cbim/                              ← 框架本体
    ├── install.py / install.bat
    │
    ├── cc-template/                   ← Claude Code 安装模板
    │   ├── CLAUDE-template.md
    │   ├── agents/                    ← agent 模板（单 .md 文件）
    │   │   ├── architect/architect.md
    │   │   ├── hr/hr.md
    │   │   ├── auditor/auditor.md
    │   │   └── programmer/programmer.md
    │   └── hooks/
    │       ├── load-memory.py         ← SessionStart：快照 + 记忆注入
    │       └── write-memory.py        ← Stop：写入短期记忆
    │
    ├── knowledge/                     ← 知识库（能力层 + 内容层 CRUD）
    │   ├── README.md                  ← 四象限架构说明
    │   ├── agent-convention.md        ← agent 定义规范
    │   ├── dna-convention.md          ← .dna/ 内容规范
    │   ├── engine/                    ← CRUD 原语 + CLI
    │   │   ├── cli.py                 ← 统一入口（agents / modules 双域）
    │   │   ├── agents.py
    │   │   ├── modules.py
    │   │   └── snapshot.py            ← 项目知识快照生成
    │   └── skills/                    ← 操作 skill（SKILL.md + 运行时脚本）
    │       ├── dispatch/              ← 助手请求分类与派发
    │       ├── arch-modules/          ← 模块 CRUD
    │       ├── arch-upgrade/          ← 知识升格（memory → .dna/）
    │       ├── arch-governance/       ← 架构评审（含 check.py + config.json）
    │       ├── hr-agents/             ← agent CRUD
    │       ├── hr-training/           ← agent 培训
    │       ├── hr-assessment/         ← agent 评审（含 check.py + config.json）
    │       └── audit-review/          ← 评审官对抗性审查
    │
    ├── memory/                        ← 记忆引擎
    │   ├── engine/                    ← Python 包（ChromaDB 驱动）
    │   ├── skills/                    ← 记忆操作 skill（write / query / distill）
    │   └── store/
    │       ├── short/                 ← 短期记忆（gitignore）
    │       └── medium/               ← 中期记忆（gitignore）
    │
    └── preview/                       ← 本地预览服务（记忆 / 能力 / 知识）
        ├── server.py
        ├── preview.py / preview.bat
        ├── index.html / app.js / style.css
        └── __init__.py
```
