# CBIM

[English](README.md) | [中文](README.zh-CN.md)

---

## English

CBIM (Capability–Business Independence + Memory) is a context-management framework for Claude Code. It splits an LLM agent project along two axes — capability (specialized agents and their skills) and business (a per-module `.dna/` knowledge tree) — and adds a session-spanning memory pipeline so each task loads only `target-agent-soul × task-subtree.dna`, never the whole project. The result: bounded context, fewer hallucinations, durable cross-session knowledge.

### Install (one line)

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.sh | bash
```

No `git clone` required. Installs the kernel + venv into your user data directory
(`%LOCALAPPDATA%\Cbim-CC\` on Windows, `~/.local/share/Cbim-CC/` on POSIX)
and puts `cbim` on your PATH.

Windows / no-bash environments:

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.py | python3
```

Pin a specific version: `CBIM_VERSION=1.0.4 curl ... | bash`

Then, in any project you want CBIM in:

```bash
cd /path/to/your/project
cbim init
```

Restart Claude Code there and send:

> Please bootstrap the module knowledge system for this project.

**Upgrading:** inside Claude Code type `/cbim_update`, or run
`cbim update -y && cbim migrate --version <latest>`.

### Core Commands

| Command | What it does |
|---|---|
| `cbim init` | Bootstrap `.cbim/`, `.claude/`, `CLAUDE.md`, `.claudeignore` in the current project. |
| `cbim migrate --version <v>` | Migrate the current project's layout and pin to a target kernel version. |
| `cbim upgrade check` | Compare the project's pinned schema against the installed kernel. |
| `cbim upgrade apply` | Apply pending schema upgrades to the current project. |
| `cbim update` | Update the installed kernel to the latest released version. |
| `cbim release-notes <v>` | Print GitHub release notes for any installed kernel version. |
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
| **Status** | Available — current release `v1.0.4` | Design phase — see [`v2/`](v2/) |
| **Install** | one-line bootstrap above | — |

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

### 安装（一行）

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.sh | bash
```

无需 `git clone`。会把内核和虚拟环境装到用户数据目录
（Windows 是 `%LOCALAPPDATA%\Cbim-CC\`，POSIX 是 `~/.local/share/Cbim-CC/`），
并把 `cbim` 加入 PATH。

Windows / 无 bash 环境：

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.py | python3
```

固定版本：`CBIM_VERSION=1.0.4 curl ... | bash`

随后，在任何想启用 CBIM 的项目里：

```bash
cd /path/to/your/project
cbim init
```

在该项目里重启 Claude Code，然后发：

> 请帮我初始化本项目的模块知识系统

**升级**：在 Claude Code 里输入 `/cbim_update`；或命令行
`cbim update -y && cbim migrate --version <latest>`。

### 核心命令

| 命令 | 作用 |
|---|---|
| `cbim init` | 在当前项目中铺设 `.cbim/`、`.claude/`、`CLAUDE.md`、`.claudeignore`。 |
| `cbim migrate --version <v>` | 把当前项目的布局与 pin 迁移到目标内核版本。 |
| `cbim upgrade check` | 比对项目固定的 schema 与已装内核。 |
| `cbim upgrade apply` | 对当前项目执行待升级的 schema。 |
| `cbim update` | 把已装内核更新到最新发布版本。 |
| `cbim release-notes <v>` | 打印任意已安装 kernel 版本的 GitHub 发布说明。 |
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
| **状态** | 已可用，当前发布 `v1.0.4` | 设计阶段，见 [`v2/`](v2/) |
| **安装** | 上方一行 bootstrap | — |

### 环境要求

- Python 3.10+
- Claude Code CLI

### 文档

- 安装后：`.cbim/README.md`（用户手册）与 `.cbim/docs/ARCHITECTURE.md`（架构详解）
- 版本历史：[`CHANGELOG.md`](CHANGELOG.md) / [`CHANGELOG.zh-CN.md`](CHANGELOG.zh-CN.md)

### 许可

[MIT](LICENSE)
