[English](README.md) | [中文](README.zh-CN.md)

# CBIM — Capability-Business Independence + Memory

> Claude Code 的上下文管理框架。多 Agent 不是团队模拟，而是按能力维度隔离上下文的机制。

**CBIM** = **CBI**（Capability-Business Independence，能力-业务独立性）+ **M**（Memory，记忆系统）

## 解决什么问题

最常见的 Claude Code 工作模式：**一个默认 agent + 大量 CLAUDE.md + 大量 skill**。

这个模式有一个随时间恶化的结构性问题：随着对话轮次增加，CLAUDE.md 和 skill 文件逐渐被全量加载进上下文，token 暴增、幻觉概率上升、输出质量下降，纠正错误又进一步污染上下文。

重置 session 能清上下文，却带来另一个问题：记忆丢失，需要重新 grep 项目代码、重新理解结构，没有结构化的项目知识可以恢复。

CBIM 同时解决这两个问题：

| 问题 | 解法 |
|------|------|
| 上下文随轮次暴增 | 多 Agent × 模块拓扑树：每次任务只加载目标 agent soul + 任务子树 `.dna/` |
| 重置后记忆丢失 | SessionStart hook 自动注入模块快照 + 近期记忆，重置 session 零成本恢复 |

---

## 设计哲学

核心 = **多 Agent（能力轴）× 模块拓扑树（业务轴）**

- **能力轴**：多个专精 Agent，每次任务只加载目标 agent 的 soul，无多余能力上下文
- **业务轴**：`.dna/` 目录按模块边界组成拓扑树（`module.md` = 每个模块的唯一硬约束），只加载任务所在子树，无多余业务上下文
- **记忆**（Memory）：跨会话积累的原始素材 — session 恢复、能力治理（HR 提炼 → skills → soul）、业务治理（架构师提炼 → `.dna/` workflows）的共同来源

每次任务上下文 = 专精 agent soul × 任务子树 `.dna/`，与项目总规模无关。  
少上下文 → 少幻觉 → 少错误 → 少纠正 → 净 token 低于单体大 agent 方案。

---

## 执行角色（上下文隔离机制）

CBIM 用多个专精 agent 实现能力维度的上下文隔离——每次任务只加载目标 agent 的 soul，无多余能力上下文。这不是团队模拟，是上下文控制机制。

```
用户
  ↓
助手（CLAUDE.md — 唯一对外接口，任务拆解与调度）
  ├── 架构师   业务层治理：设计并维护项目知识体系（.dna/）
  ├── HR       能力层治理：work agent 全生命周期管理
  ├── 评审官   独立批判审查（对抗性视角，只读）
  └── work agents   执行具体任务（按需由 HR 创建）
```

你只需要和助手说话。助手负责理解意图、拆解任务、路由给目标 agent、汇总结果。

---

## 快速开始

### 方式一：一句话交给 Claude Code（推荐）

在目标项目目录打开 Claude Code，发送这条消息，Agent 会自动完成全部安装步骤：

```
请访问 https://raw.githubusercontent.com/nan023062/cbim/v1-claude-code/INSTALL.md 获取 CBIM 安装 SOP，从第一条分隔线之后的内容开始，在当前项目执行所有步骤完成安装
```

### 方式二：手动运行安装脚本

```bash
# 1. 克隆 CBIM 到目标项目的 cbim/ 目录
git clone --branch v1-claude-code https://github.com/nan023062/cbim.git cbim

# 2. 运行安装脚本
python3 cbim/install.py        # macOS / Linux
# 或双击 cbim/install.bat      # Windows

# 3. 重启 Claude Code
claude
```

---

## 安装后首次使用

重启 Claude Code 后，发送：

> **"请初始化本项目的模块知识体系"**

助手派发架构师建立 `.dna/` 知识体系，之后即可正常使用。

---

## 后续怎么用

直接告诉助手要做什么，不用指定 agent：

| 你想做 | 直接说 |
|--------|--------|
| 初始化知识体系 | 请初始化本项目的模块知识体系 |
| 新建功能模块 | 新建一个 combat 模块 |
| 实现功能 | 按当前蓝图实现登录接口 |
| 审查设计 | 审一下这次改动 |
| 查历史决策 | 查一下 combat 模块的历史决策 |
| 招募新 agent | 帮我招募一个 AI 工程师 |

---

## 目录结构（部署后）

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
├── .venv/                         ← Python 虚拟环境（gitignore）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + hook 注册
│   └── agents/
│       ├── architect/             ← 架构师
│       ├── hr/                    ← HR
│       ├── auditor/               ← 评审官
│       └── programmer/            ← 程序员（默认 work agent）
│
├── .dna/                          ← 项目知识根模块（架构师创建）
│   ├── index.md                   ← 仅根模块：全树模块路径列表
│   ├── module.md                  ← 必需：唯一硬约束（frontmatter + 架构）
│   ├── contract.md                ← 可选：协议边界
│   ├── workflows/                 ← 可选：确定性流程定义
│   └── ...                        ← 可选：用户自定义文件
│
└── cbim/                          ← 框架本体（git clone 到此目录）
    ├── install.py                 ← 自动安装脚本
    ├── install.bat                ← Windows 安装入口
    ├── cc-template/               ← Claude Code 安装模板
    ├── knowledge/                 ← 知识库引擎（能力层 + 业务层 CRUD）
    ├── memory/                    ← 记忆引擎（FileBackend）
    └── preview/                   ← 本地可视化服务
```

---

## 两层治理 · 两类 Skill

| 层级 | 治理者 | 管辖 | 铁律 |
|------|--------|------|------|
| **能力层** | HR | `.claude/agents/`（soul）+ `cbim/knowledge/skills/`（能力向 skill） | soul/skills 不含任何项目特定内容 |
| **业务层** | 架构师 | 项目各级 `.dna/`（`module.md` = 唯一硬约束；扩展全部可选） | 知识文件不引用 agent 规范 |

`.dna/` 约定：**约定最小化 + 扩展开放**。目录存在 = 模块。`module.md` 是唯一必需文件（YAML frontmatter + 架构正文）。`contract.md`、`workflows/`、用户自定义文件全部可选。

CBIM 将 skill 按「谁拥有」一分为二，`.claude/` 下只有 `agents/`，不再堆积 `skills/`：

| 类型 | 存储 | 特征 |
|------|------|------|
| **能力向 skill** | `cbim/knowledge/skills/` | agent 私有能力，可移植，HR 治理 |
| **业务向 skill** | `.dna/workflows/` | 模块确定性流程，与项目绑定，架构师治理 |

---

## 记忆系统

记忆是三阶段蒸馏管道，不只是上下文恢复：

| 阶段 | 路径 | 目的 |
|------|------|------|
| 短期 | `cbim/memory/store/short/` | 原始 session 记录；提炼后标记 `distilled`，至少保留 3 天后清理 |
| 中期 | `cbim/memory/store/medium/` | 压缩提炼后的模式摘要；升格至知识层后归档 |
| 知识（核心） | `cbim/knowledge/skills/` + `.dna/` | 固化结构：能力进 skills/soul，业务进 workflows |

短期 → 中期 是**压缩**；中期 → 知识 是**最核心的一步**——将验证过的模式固化为治理结构，成为后续所有任务的基础。

SessionStart hook 在每次会话开始时自动注入：项目知识快照（模块树 + agent 列表）+ 上次恢复点 + 近期记忆。

---

## 架构详解

见 [docs/ARCHITECTURE.zh-CN.md](docs/ARCHITECTURE.zh-CN.md) | [Architecture (English)](docs/ARCHITECTURE.md)

---

## 依赖

- Python 3.10+
- Claude Code CLI
- 无额外依赖（记忆引擎默认使用 FileBackend，纯标准库）

---

## License

[MIT](LICENSE)
