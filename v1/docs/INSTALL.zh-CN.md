[English](INSTALL.md) | [中文](INSTALL.zh-CN.md)

# CBIM 安装参考

安装 / 刷新 / 卸载 / 迁移命令见仓库根 README 的 [**安装**章节](../../README.zh-CN.md#安装)。本文档补充完整的部署后目录布局。

---

## 目录结构（部署后）

`.dna/` 是**模块**，散落在代码任意深度的子目录下，按文件系统层级形成模块树。项目根**不需要**一定有 `.dna/`。唯一硬要求是框架管理的注册表 `.cbim/.dna/index.md`（install 时创建，`init_module` 时更新）。

```
your-project/
├── CLAUDE.md                      ← 助理身份（主会话）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + 钩子注册 + MCP server 注册
│   ├── agents/                    ← Architect / HR / Auditor / Programmer（由 /cbim_install 安装）
│   └── commands/                  ← Slash 命令 /cbim_install, /cbim_help, /cbim_dashboard, /cbim_debug, /cbim_log, /cbim_sched
│
├── src/                           ← 业务代码（任意布局）
│   ├── combat/
│   │   ├── .dna/                  ← 模块（父）：描述子模块 + 边界
│   │   │   ├── module.md          ← 必需：frontmatter + 架构正文
│   │   │   ├── contract.md        ← 可选：协议边界
│   │   │   ├── workflows/         ← 可选：确定性流程定义
│   │   │   └── ...                ← 可选：任意用户自定义文件
│   │   ├── skill/.dna/            ← 模块（叶）：具体实现
│   │   └── buff/.dna/             ← 模块（叶）
│   └── economy/.dna/              ← 模块
│
├── .dna/                          ← 可选：项目根模块
│   └── module.md                  ←   （仅当项目根本身就是模块 ——
│                                  ←    单应用形态；monorepo 通常不需要）
│
└── .cbim/                         ← 框架（即本目录）
    ├── run                        ← POSIX 启动 shim（设置 PYTHONPATH，执行 `python -m engine`）
    ├── run.cmd                    ← Windows 启动 shim
    ├── config.json                ← 本地框架配置
    ├── .dna/index.md              ← 模块注册表（框架管理）
    ├── logs/                      ← 引擎日志（gitignore）
    ├── memory/                    ← 记忆存储（gitignore）
    │   ├── short/                 ← 短期会话记忆
    │   └── medium/                ← 中期蒸馏记忆
    └── kernel/                    ← 内核安装（由 /cbim_install 下载）
        ├── engine/                ← 统一 CLI 调度（memory / dna / agent / skill / hook / mcp / dashboard ...）
        ├── cbi/                   ← 能力 + 业务原语 + 资源
        ├── memory/                ← 记忆引擎
        ├── hooks/                 ← SessionStart / Stop / UserPromptSubmit / PreToolUse 钩子脚本
        ├── mcp_server/            ← FastMCP server + scheduler + 内置任务
        ├── dashboard/             ← 本地仪表盘 server
        ├── services/              ← 横切服务（frontmatter、ids 等）
        ├── project/               ← Init / sync / 模板
        └── context.py             ← 共享根解析模块
```

`agents/` 依赖 `skills/`；`engine/` 只读 `agents/`，不拥有。

shim 是唯一的运行时入口 —— `.cbim/run <subcommand>` 设置 `PYTHONPATH=<project>/.cbim/kernel` 后执行 `python -m engine <subcommand>`。没有项目级 pin，没有全局 venv，用户 PATH 上也没有 `cbim` CLI。

完整安装规范参见 [`v1/src/kernel/project/commands/cbim_install.md`](../src/kernel/project/commands/cbim_install.md)。
