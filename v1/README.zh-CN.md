# CBIM — 用户手册

> 本文件随框架一同分发。安装后阅读，了解如何使用 CBIM。
>
> 完整文档：https://github.com/nan023062/cbim
> English: [README.md](README.md)

---

## 安装后首次使用

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
| `/cbim_help` | 框架总览（工作流 + 命令清单 + 关键路径） |
| `/cbim_debug on\|off\|status` | 切换/查看引擎内部日志 |
| `/cbim_log [N]` | 查看当前 session 日志（agent loop 信号） |
| `/cbim_sched status\|trigger <name>` | 查看 / 触发调度器任务 |
| `/cbim_update` | 升级 CBIM 内核到最新版（等价 `cbim update -y`） |

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

Server 基于官方 `mcp` Python SDK（FastMCP）实现，通过 `cbim mcp` launcher 跑在全局内核 venv 中 —— 无需项目本地 venv，也无需额外 `pip install`。

## 调度器

MCP server 内嵌一个异步任务调度器（在其 lifespan 中启动）。每 30 秒 tick 一次，派发位于 `.cbim/mcp_server/tasks/*.py` 下发现的任务。

每个任务继承 `mcp_server.scheduler.Task`：

```python
from mcp_server.scheduler import Task

class MyTask(Task):
    name = "my-task"
    description = "轮询某事或运行基准"
    interval_seconds = 600       # 0 = 仅手动
    respect_cc_idle = True       # 仅在 CC 空闲时触发（依据 .cbim/.cc-status）

    async def run(self, context: dict) -> str:
        # context: {project_root, cbim_root, cc_idle}
        return "summary line written to session log + state.json"
```

`UserPromptSubmit` 与 `Stop` 钩子维护 `.cbim/.cc-status`（`busy` / `idle`），让 opt-in 任务只在轮次之间触发。状态持久化在 `.cbim/scheduler/state.json`；结果以 `[SCHED]` 前缀写入 session 日志。

**生命周期**：调度器随 Claude Code 退出 MCP server 时一同终止。若任务必须在 CC 离线时运行，独立启动 server（`python .cbim/mcp_server/server.py`）—— 同一份代码，无需 CC。

---

## 目录结构

`.dna/` 目录是**模块**，散落在代码任意深度的位置（哪里有模块就在哪里）；它们按文件系统层级形成一棵树。项目根**不需要**一定有 `.dna/`。唯一硬要求是框架管理的注册表 `.cbim/index.md`（install 时创建，`init_module` 时更新）。

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
├── .venv/                         ← Python 虚拟环境（gitignored）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + 钩子注册
│   ├── agents/                    ← 架构师 / HR / 评审官 / 程序员
│   └── commands/                  ← Slash 命令（/cbim_*）
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
    ├── .dna/index.md              ← 模块注册表（框架管理，install 后必有）
    ├── .pin                       ← 项目锁定的 CBIM schema 版本（单行版本号）
    ├── cbi/                       ← 能力 + 业务定义、agents、skills
    ├── engine/                    ← 统一 CLI 入口（通过 `cbim ...` 调用）
    ├── hooks/                     ← SessionStart / Stop / PreToolUse 钩子脚本
    ├── memory/                    ← 记忆引擎 + 存储
    ├── dashboard/                 ← 本地仪表盘服务
    ├── docs/                      ← 架构文档
    └── config.json                ← 本地框架配置
```

---

## 版本 pin 与升级

从 1.3.3 起，项目锁定的 CBIM schema 版本存储在 `.cbim/.pin`（纯文本、单行版本号、行尾换行、列入 gitignore）。所有读写都走唯一访问器 `project/pin.py`（`read_pin` / `write_pin`）。`.cbim/config.json` 不再持有 `cbim_version` 字段。

升级与迁移：

| 操作 | 命令 |
|---|---|
| 升级 CBIM 内核 | `cbim update -y` 或 `/cbim_update` |
| 迁移当前项目到指定版本 | `cbim migrate --version <X>` |

---

## 两层治理

| 层级 | 治理者 | 范围 | 规则 |
|------|--------|------|------|
| **能力层** | HR | `.claude/agents/` + `.cbim/cbi/skills/` | 不含项目特定内容 |
| **业务层** | 架构师 | `.dna/`（`module.md` = 唯一硬约束；扩展可选） | 不引用 agent 规范 |

`.dna/` 约定遵循**约定最小化 + 扩展开放**：目录存在即标志模块；`module.md` 是唯一必需文件（YAML frontmatter + 架构正文合一）；`contract.md`、`workflows/` 及任何用户自定义文件均为可选。

| Skill 类型 | 存储 | 特征 |
|----------|------|------|
| **能力向 skill** | `.cbim/cbi/skills/` | Agent 私有能力；可移植；HR 治理 |
| **业务向 skill** | `.dna/workflows/` | 模块确定性流程；项目绑定；架构师治理 |

---

## 记忆系统

| 阶段 | 路径 | 用途 |
|------|------|------|
| 短期 | `.cbim/memory/short/` | 原始 session 记录（3 天后清理） |
| 中期 | `.cbim/memory/medium/` | 压缩后的模式摘要 |
| 知识 | `.cbim/cbi/skills/` + `.dna/` | 结晶为治理结构 |

`SessionStart` 钩子在会话开始时自动注入：项目知识快照 + 上次 session 恢复点 + 近期记忆。
`Stop` 钩子将刚结束的 session 蒸馏写入 `memory/short/`。
`PreToolUse` 钩子（默认 inert）在 `/cbim_debug on` 时将工具调用日志写入 `.cbim/logs/tools.txt`。

---

## 仪表盘

```bash
python -m dashboard.dashboard    # macOS / Linux  （在 .cbim/ 下运行）
dashboard\dashboard.bat          # Windows
```

打开 http://127.0.0.1:8765 —— Memory / Capability / Knowledge / Log 多个标签页。

---

## 架构详解

参见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
