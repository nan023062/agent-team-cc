# CBIM

[English](README.md) | [中文](README.zh-CN.md)

> CBIM（Capability–Business Independence + Memory）是 Claude Code 的 cc-prompt-pack。沿**能力**（专精 agent 及其 skill）与**业务**（按模块切分的 `.dna/` 知识树）两个维度切分项目，并提供跨会话的**记忆**管道，让每个任务的上下文 = 目标 agent 灵魂 × 任务子树 `.dna/`，与项目总大小无关。结果：上下文有界、幻觉减少、跨会话知识沉淀。

仓库中并存两套实现：

| | [V1 — CC Kernel](v1/) | [V2 — Native Agent](v2/) |
|---|---|---|
| **是什么** | 跑在 Claude Code 之上的 CBIM —— prompt、agent 定义、Python hook、MCP server | 独立的 C# / .NET 8 运行时，确定性调度器 |
| **状态** | 已可用 —— 见下方安装 | 设计阶段，见 [`v2/`](v2/) |

下文均针对 **V1**。

---

## 安装

1. 进入你要装 CBIM 的项目根目录（`cd` 到那里）。
2. 在项目根执行：

   ```bash
   curl -sSL https://raw.githubusercontent.com/nan023062/cbim/master/install.sh | bash
   ```

3. 脚本会把仓库 clone 到临时目录，把 `v1/src/kernel/` 拷贝到 `<project>/.cbim/kernel/`（扁平布局 —— `engine/`、`cbi/`、`memory/`、`project/` 是直接子目录），然后跑 `python3 -m engine init` 完成项目落地（启动 shim、agents、slash 命令、钩子、MCP server、`CLAUDE.md`、`.gitignore`）。`init` 还会在 `<project>/.cbim/.venv/` 建一个项目本地 venv 并把 `mcp` SDK 装进去 —— 你的系统 Python 不会被动到。要求 PATH 上有 `git` 与 `python3` ≥ 3.10；不做全局 `pip install`。
4. **重启 Claude Code**，让 `SessionStart` 钩子触发。

Windows 原生不支持 `install.sh`（POSIX bash），请用 WSL。

安装完成后，项目根目录会出现：

- `.cbim/run`（POSIX，0755）+ `.cbim/run.cmd`（Windows）—— 启动 shim；运行时解析自身目录，设置 `PYTHONPATH=<project>/.cbim/kernel` 后执行 `.cbim/.venv/bin/python -m engine "$@"`。不再烧入系统 Python 绝对路径 —— `.cbim/` 自包含、可拷贝。
- `.cbim/.venv/`（gitignored）—— 项目本地 venv，由 `engine init` 用 bootstrap 的 `python3` 建好，里面装着 `mcp` 以及 CBIM 后续可能新增的 Python 依赖。你的系统 Python 不会被动到。
- `.cbim/kernel/` —— 内核安装（gitignored）
- `.cbim/config.json`、`.cbim/logs/`、`.cbim/memory/{short,medium}/` —— 引擎状态（gitignored）
- `.claude/agents/{architect,auditor,hr,programmer}/` —— 4 个核心 agent
- `.claude/commands/cbim_{install,help,dashboard,debug,log,sched}.md` —— 6 个 slash 命令
- `.claude/settings.json` —— 钩子（注册为 `.cbim/run hook <event>`）+ `mcpServers.cbim` 注册（运行 `.cbim/run mcp`）+ `permissions.deny`（`Write(.cbim/**)` / `Edit(.cbim/**)`）
- `CLAUDE.md` —— 助手身份（协调中枢）；每次 `/cbim_install` 都会重新生成
- `.claudeignore` —— Claude Code 读取范围排除清单
- `.gitignore` —— 追加 `.cbim/`

**刷新 / 升级**：首次安装完成后，`/cbim_install` slash 命令已注册到 `.claude/commands/`。后续直接在 Claude 输入框重跑该命令即可 —— 幂等操作。shim 与内核会被重新生成；`.dna/` 与 `.cbim/memory/` 会被保留。没有 `cbim update` CLI；slash 命令是规范刷新路径。（重跑步骤 2 的 `install.sh` curl 命令也合法 —— 它会覆盖 `.cbim/kernel/` 并重跑 `engine init`，`.cbim/memory/`、`.cbim/scheduler/`、`.cbim/config.json` 与 `.dna/` 都会被保留。）

**卸载**：`rm -rf .cbim/`，然后删除 `.claude/agents/{architect,auditor,hr,programmer}/`、6 个 `.claude/commands/cbim_*.md`、`.claude/settings.json` 里的 `mcpServers.cbim` + 钩子注册、`CLAUDE.md` 里的 CBIM 段，以及 `.gitignore` 里的 `.cbim/` 行。没有卸载 CLI。

**从早期布局迁移**：如果 `<project>/cbim-cc/` 是旧版安装留下的，`rm -rf cbim-cc/` 后重跑 `/cbim_install`。shim 会自动重新生成，指向新的 `.cbim/kernel/` 路径。没有自动化迁移脚本 —— 这就是迁移流程的全部。

PATH 上**没有 `cbim` 命令**，**无需全局 `pip install`**，**没有项目级版本 pin**。唯一的运行时入口是 `.cbim/run <subcommand>`，它通过 `.cbim/.venv/` 这个项目本地 venv 完成分发。

完整安装规范见 [`v1/src/kernel/project/commands/cbim_install.md`](v1/src/kernel/project/commands/cbim_install.md)。

---

## 首次使用

重启 Claude Code，然后发送：

> **"请初始化本项目的模块知识体系"**

助手会派发架构师构建 `.dna/` 知识体系。完成后就可以正常使用了。

---

## 怎么用

直接告诉助手你要做什么，不用指定 agent：

| 你想做的事 | 直接说 |
|----------|--------|
| 初始化知识体系 | 请初始化本项目的模块知识体系 |
| 新建一个功能模块 | 新建一个 combat 模块 |
| 按蓝图实现某个功能 | 按当前蓝图实现登录接口 |
| 审查一次设计 | 审一下这次改动 |
| 查历史决策 | 查一下 combat 模块的历史决策 |
| 招募工作 agent | 帮我招一个 AI 工程师 agent |

---

## Slash 命令

| 命令 | 用途 |
|---|---|
| `/cbim_install` | 在当前项目安装或刷新 CBIM（下载内核到 `.cbim/kernel/`，写入 `.cbim/run` shim，注册钩子 + MCP server） |
| `/cbim_help` | 框架总览（工作流 + 命令清单 + 关键路径） |
| `/cbim_dashboard` | 打开本地仪表盘（记忆 / 能力 / 知识 / 日志） |
| `/cbim_debug on\|off\|status` | 切换/查看引擎内部日志 |
| `/cbim_log [N]` | 查看当前 session 日志（agent loop 信号） |
| `/cbim_sched status\|trigger <name>` | 查看 / 触发调度器任务 |

## MCP 工具

CBIM 同时以 MCP server 形式提供，注册在 `.claude/settings.json` 的 `mcpServers.cbim` 下。助手可以直接调用以下工具，无需走 `cbim ...` Bash：

| 工具 | 用途 |
|---|---|
| `memory_query` / `memory_list` / `memory_create` / `memory_delete` | CBIM 记忆库访问 |
| `dna_list` / `dna_show` / `dna_reindex` | 模块知识（.dna/） |
| `agent_list` / `agent_show` | Claude Code agent 注册表 |
| `skill_list` / `skill_show` | CBIM skill 目录 |
| `project_snapshot` | 完整项目知识快照 |
| `scheduler_status` / `scheduler_trigger` | 查看与触发调度任务 |

Server 基于官方 `mcp` Python SDK（FastMCP）实现，通过项目本地的 `.cbim/run mcp` shim 启动 —— 无需全局安装，无需额外 `pip install`。Shim 设置 `PYTHONPATH=<project>/.cbim/kernel` 后执行 `python -m engine mcp`。

## 调度器

MCP server 内嵌一个异步任务调度器（在其 lifespan 中启动）。每 30 秒 tick 一次，派发随内核包一起出厂的内置任务（`mcp_server.tasks`）。

每个任务继承 `mcp_server.scheduler.Task`，声明 `name`、`description`、`interval_seconds`（0 = 仅手动）、`respect_cc_idle`（True = 仅在 CC 空闲时触发，依据 `.cbim/.cc-status`）。任务目前内置于内核包中，尚未提供项目本地的任务投放路径。

`UserPromptSubmit` 与 `Stop` 钩子维护 `.cbim/.cc-status`（`busy` / `idle`），让 opt-in 任务只在轮次之间触发。状态持久化在 `.cbim/scheduler/state.json`；结果以 `[SCHED]` 前缀写入 session 日志。

**生命周期**：调度器与 MCP server 进程同生命周期。CC 通过 `.cbim/run mcp` shim（在 `.claude/settings.json` 的 `mcpServers.cbim` 下注册）启动 server → 调度器启动；CC 退出 → 调度器停止。

---

## 目录结构

`.dna/` 目录是**模块**，散落在代码任意深度的位置（哪里有模块就在哪里）；它们按文件系统层级形成一棵树。项目根**不需要**一定有 `.dna/`。唯一硬要求是框架管理的注册表 `.cbim/.dna/index.md`（install 时创建，`init_module` 时更新）。

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + 钩子注册 + MCP server 注册
│   ├── agents/                    ← 架构师 / HR / 评审官 / 程序员（由 /cbim_install 安装）
│   └── commands/                  ← Slash 命令 /cbim_install, /cbim_help, /cbim_dashboard, /cbim_debug, /cbim_log, /cbim_sched
│
├── src/                           ← 你的代码（任意结构）
│   ├── combat/
│   │   ├── .dna/                  ← 模块（parent）：描述子模块 + 边界
│   │   │   ├── module.md          ← 必需：frontmatter + 架构正文
│   │   │   ├── contract.md        ← 可选：协议边界
│   │   │   ├── workflows/         ← 可选：确定性流程定义
│   │   │   └── ...                ← 可选：任意用户自定义文件
│   │   ├── skill/.dna/            ← 模块（leaf）：具体实现
│   │   └── buff/.dna/             ← 模块（leaf）
│   └── economy/.dna/              ← 模块
│
├── .dna/                          ← 可选的「项目根模块」
│   └── module.md                  ←   （仅当项目根本身是一个模块 ——
│                                  ←    单应用形态；monorepo 通常省略）
│
└── .cbim/                         ← 框架（即本目录）
    ├── run                        ← POSIX 启动 shim（设置 PYTHONPATH，执行 `python -m engine`）
    ├── run.cmd                    ← Windows 启动 shim
    ├── config.json                ← 本地框架配置
    ├── .dna/index.md              ← 模块注册表（框架管理）
    ├── logs/                      ← 引擎日志（gitignored）
    ├── memory/                    ← 记忆存储（gitignored）
    │   ├── short/                 ← 短期 session 记忆
    │   └── medium/                ← 中期蒸馏记忆
    └── kernel/                    ← 内核安装（由 /cbim_install 下载）
        ├── engine/                ← 统一 CLI 分发器（memory / dna / agent / skill / hook / mcp / dashboard ...）
        ├── cbi/                   ← 能力 + 业务原语 + 资源
        ├── memory/                ← 记忆引擎
        ├── hooks/                 ← SessionStart / Stop / UserPromptSubmit / PreToolUse 钩子脚本
        ├── mcp_server/            ← FastMCP server + 调度器 + 内置任务
        ├── dashboard/             ← 本地仪表盘服务
        ├── services/              ← 横切服务（frontmatter、ids ……）
        ├── project/               ← Init / sync / 模板
        └── context.py             ← 共享根目录解析模块
```

长期记忆说明：`.cbim/memory/short/` 与 `.cbim/memory/medium/` 在安装时创建。长期层（若从 medium 蒸馏出现）由 distill 流程按需创建，`init` 不创建。

---

## 两层治理

| 层级 | 治理者 | 范围 | 规则 |
|------|--------|------|------|
| **能力层** | HR | `.claude/agents/` + `.cbim/kernel/cbi/skills/` | 不含项目特定内容 |
| **业务层** | 架构师 | `.dna/`（`module.md` = 唯一硬约束；扩展可选） | 不引用 agent 规范 |

`.dna/` 约定遵循**约定最小化 + 扩展开放**：目录存在即标志模块；`module.md` 是唯一必需文件（YAML frontmatter + 架构正文合一）；`contract.md`、`workflows/` 及任何用户自定义文件均为可选。

| Skill 类型 | 存储 | 特征 |
|----------|------|------|
| **能力向 skill** | `.cbim/kernel/cbi/skills/` | Agent 私有能力；可移植；HR 治理 |
| **业务向 skill** | `.dna/workflows/` | 模块确定性流程；项目绑定；架构师治理 |

---

## 记忆系统

| 阶段 | 路径 | 用途 |
|------|------|------|
| 短期 | `.cbim/memory/short/` | 原始 session 记录（3 天后清理） |
| 中期 | `.cbim/memory/medium/` | 压缩后的模式摘要 |
| 知识 | `.cbim/kernel/cbi/skills/` + `.dna/` | 结晶为治理结构 |

`SessionStart` 钩子在会话开始时自动注入：项目知识快照 + 上次 session 恢复点 + 近期记忆。
`Stop` 钩子将刚结束的 session 蒸馏写入 `memory/short/`。
`PreToolUse` 钩子（默认 inert）在 `/cbim_debug on` 时将工具调用日志写入 `.cbim/logs/tools.txt`。

---

## 仪表盘

运行 `/cbim_dashboard`（或 `.cbim/run dashboard`）—— 打开 http://127.0.0.1:8765，含 Memory / Capability / Knowledge / Log 多个标签页。CC 空闲时，`auto_preview` 钩子也会在后台自动启动仪表盘。

---

## 架构详解

参见 [v1/docs/ARCHITECTURE.md](v1/docs/ARCHITECTURE.md) | [架构文档（中文）](v1/docs/ARCHITECTURE.zh-CN.md)

---

## 环境要求

- Python 3.10+（安装时 PATH 上需有 `python3`；其绝对路径会被烧入 shim）
- Claude Code CLI

## 许可

[MIT](LICENSE)
