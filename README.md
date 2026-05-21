# CBIM

[English](README.md) | [中文](README.zh-CN.md)

---

## English

CBIM (Capability–Business Independence + Memory) is a context-management framework for Claude Code. It splits an LLM agent project along two axes — capability (specialized agents and their skills) and business (a per-module `.dna/` knowledge tree) — and adds a session-spanning memory pipeline so each task loads only `target-agent-soul × task-subtree.dna`, never the whole project. The result: bounded context, fewer hallucinations, durable cross-session knowledge.

### 5-Minute Quickstart

Two install paths. Pick one. Option A is what most users want.

**Option A — One-liner via Claude Code (recommended)**

In your target project, paste this message to Claude Code:

```
Please fetch https://raw.githubusercontent.com/nan023062/cbim/master/v1/INSTALL.md and execute the installation SOP for the current project.
```

Claude Code will fetch the SOP and lay down `.cbim/`, `.claude/`, `CLAUDE.md`, and `.claudeignore` in the current project — merge-safe against existing settings.

**Option B — Global kernel install**

```bash
git clone https://github.com/nan023062/cbim.git
cd cbim
python v1/src/install.py
```

This installs the kernel and puts `cbim` on your PATH. Then, in any project you want to use CBIM in:

```bash
cd /path/to/your/project
cbim init
```

**After install — restart Claude Code, then in any project send:**

> 请帮我初始化本项目的模块知识系统
> *(Please help me bootstrap the module knowledge system for this project.)*

The Architect agent will create the first `.dna/` knowledge tree for you.

**Upgrading**

```bash
cbim update -y                 # fetch the latest kernel
cbim migrate --version <latest> # migrate the current project to it
```

Or, inside Claude Code, just type `/cbim_update`.

### Core Commands

| Command | What it does |
|---|---|
| `cbim init` | Bootstrap `.cbim/`, `.claude/`, `CLAUDE.md`, `.claudeignore` in the current project. |
| `cbim migrate --version <v>` | Migrate the current project's layout and pin to a target kernel version. |
| `cbim upgrade check` | Compare the project's pinned schema against the installed kernel. |
| `cbim upgrade apply` | Apply pending schema upgrades to the current project. |
| `cbim update` | Update the installed kernel to the latest released version. |
| `cbim dna` | Read / write module knowledge (`.dna/module.md`, `contract.md`, `index.md`). |
| `cbim agent` | Manage agent definitions under `.claude/agents/`. |
| `cbim memory` | Read / write / promote entries in `.cbim/memory/`. |
| `cbim skill` | Show or list skills. |
| `cbim soul` | Inspect agent souls (frontmatter + system prompt). |
| `cbim snapshot` | Capture / restore project state snapshots. |
| `cbim config` | Read / write `.cbim/config.json`. |
| `cbim log` | Tail engine and hook logs. |
| `cbim dashboard` | Local status dashboard. |
| `cbim debug` | Diagnostics for the kernel and current project. |
| `cbim hook` | Manage Claude Code hooks. |
| `cbim mcp` | Manage MCP server bindings. |
| `cbim project` | Per-project housekeeping (sync, repair, pin). |

### Architecture in One Picture

```
User → Assistant (CLAUDE.md, sole interface)
         ├── Architect    business layer governance (.dna/ knowledge)
         ├── HR           capability layer governance (agents, skills)
         ├── Auditor      independent critical review (read-only)
         └── Work agents  task execution (created by HR on demand)
```

Two implementations live in this repo:

| | [V1 — CC Kernel](v1/) | [V2 — Native Agent](v2/) |
|---|---|---|
| **What it is** | CBIM on top of Claude Code — prompts, agent definitions, Python hooks | Standalone C# / .NET 8 runtime with a deterministic scheduler |
| **Status** | Available — install and use today | Design phase — see [`v2/`](v2/) |
| **Install** | `python v1/src/install.py` | — |

### Requirements

- Python 3.10+
- Claude Code CLI

### Documentation

- After install: `.cbim/README.md` (user manual) and `.cbim/docs/ARCHITECTURE.md` (deep dive)
- Release history: [`CHANGELOG.md`](CHANGELOG.md)

### License

[MIT](LICENSE)

---

## 中文

CBIM（Capability–Business Independence + Memory）是面向 Claude Code 的上下文管理框架。沿能力（专精 agent 及其 skill）与业务（按模块切分的 `.dna/` 知识树）两个维度切分项目，并提供跨会话记忆管道，让每个任务的上下文 = 目标 agent 灵魂 × 任务子树 `.dna/`，与项目总大小无关。结果：上下文有界、幻觉减少、跨会话知识沉淀。

### 5 分钟上手

两种安装路径，任选其一。多数用户走 Option A。

**Option A — 通过 Claude Code 一行式安装（推荐）**

在你的目标项目里，向 Claude Code 粘贴：

```
请获取 https://raw.githubusercontent.com/nan023062/cbim/master/v1/INSTALL.md 并按其中的安装 SOP 在当前项目执行安装。
```

Claude Code 会自动拉取安装 SOP，并在当前项目中铺设 `.cbim/`、`.claude/`、`CLAUDE.md`、`.claudeignore` —— 会与现有配置安全合并。

**Option B — 全局内核安装**

```bash
git clone https://github.com/nan023062/cbim.git
cd cbim
python v1/src/install.py
```

会把内核装好并把 `cbim` 加入你的 PATH。然后在任何想启用 CBIM 的项目里：

```bash
cd /path/to/your/project
cbim init
```

**装完之后 —— 重启 Claude Code，在任意项目里发一句：**

> 请帮我初始化本项目的模块知识系统

Architect 会为这个项目创建第一棵 `.dna/` 知识树。

**升级**

```bash
cbim update -y                  # 拉取最新内核
cbim migrate --version <latest> # 把当前项目迁移到目标版本
```

或者在 Claude Code 里直接输入 `/cbim_update`。

### 核心命令

| 命令 | 作用 |
|---|---|
| `cbim init` | 在当前项目中铺设 `.cbim/`、`.claude/`、`CLAUDE.md`、`.claudeignore`。 |
| `cbim migrate --version <v>` | 把当前项目的布局与 pin 迁移到目标内核版本。 |
| `cbim upgrade check` | 比对项目固定的 schema 与已装内核。 |
| `cbim upgrade apply` | 对当前项目执行待升级的 schema。 |
| `cbim update` | 把已装内核更新到最新发布版本。 |
| `cbim dna` | 读写模块知识（`.dna/module.md`、`contract.md`、`index.md`）。 |
| `cbim agent` | 管理 `.claude/agents/` 下的 agent 定义。 |
| `cbim memory` | 读写、晋升 `.cbim/memory/` 下的记忆条目。 |
| `cbim skill` | 列出或查看 skill。 |
| `cbim soul` | 查看 agent 灵魂（frontmatter + system prompt）。 |
| `cbim snapshot` | 项目状态快照的创建与恢复。 |
| `cbim config` | 读写 `.cbim/config.json`。 |
| `cbim log` | 查看 engine 与 hook 日志。 |
| `cbim dashboard` | 本地状态面板。 |
| `cbim debug` | 内核与当前项目的诊断。 |
| `cbim hook` | 管理 Claude Code hook。 |
| `cbim mcp` | 管理 MCP server 绑定。 |
| `cbim project` | 项目级维护（sync、repair、pin）。 |

### 架构总览

```
用户 → Assistant（CLAUDE.md，唯一对外入口）
         ├── Architect   业务层治理（.dna/ 知识）
         ├── HR          能力层治理（agent、skill）
         ├── Auditor     独立审查（只读）
         └── Work agents 任务执行（由 HR 按需建立）
```

仓库中并存两套实现：

| | [V1 — CC Kernel](v1/) | [V2 — Native Agent](v2/) |
|---|---|---|
| **是什么** | 跑在 Claude Code 之上的 CBIM —— prompt、agent 定义、Python hook | 独立的 C# / .NET 8 运行时，确定性调度器 |
| **状态** | 已可用，今天就能装 | 设计阶段，见 [`v2/`](v2/) |
| **安装** | `python v1/src/install.py` | — |

### 环境要求

- Python 3.10+
- Claude Code CLI

### 文档

- 安装后：`.cbim/README.md`（用户手册）与 `.cbim/docs/ARCHITECTURE.md`（架构详解）
- 版本历史：[`CHANGELOG.md`](CHANGELOG.md) / [`CHANGELOG.zh-CN.md`](CHANGELOG.zh-CN.md)

### 许可

[MIT](LICENSE)
