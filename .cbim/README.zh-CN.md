# CBIM — 用户手册

> 本文件随框架分发。安装完成后阅读，了解如何使用 CBIM。
>
> 完整文档: https://github.com/nan023062/cbim
> English: [README.md](README.md)

---

## 安装后首次使用

重启 Claude Code，然后输入：

> **"请为本项目初始化模块知识体系"**

协调者会派架构师建立 `.dna/` 知识系统，之后即可开始使用。

---

## 怎么用

直接告诉协调者你想要什么——不需要指定 agent：

| 你想做什么 | 直接说 |
|---------------|----------|
| 初始化知识系统 | 请为本项目初始化模块知识体系 |
| 创建功能模块 | 创建一个 combat 模块 |
| 实现功能 | 按当前蓝图实现 login API |
| 评审设计 | 评审一下这次改动 |
| 查询历史决策 | combat 模块的决策历史是什么 |
| 招募 work agent | 帮我招一个 AI 工程师 agent |

---

## Slash 命令

| 命令 | 作用 |
|---|---|
| `/cbim_help` | 框架总览（工作流 + 命令清单 + 关键路径） |
| `/cbim_debug on\|off\|status` | 开启/关闭/查看工具调用日志 |
| `/cbim_log [N]` | 查看最近 N 条工具调用日志 |

---

## 目录结构

`.dna/` 目录是**模块**，散落在代码任意深度的子目录下，按文件系统层级形成模块树。项目根**不需要**一定有 `.dna/`。唯一硬要求是框架管理的注册表 `.cbim/.dna/index.md`（install 时创建，`init_module` 时更新）。

```
your-project/
├── CLAUDE.md                      ← 协调者身份（主会话）
├── .venv/                         ← Python 虚拟环境（gitignored）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + 钩子注册
│   ├── agents/                    ← 架构师 / HR / 评审 / 程序员
│   └── commands/                  ← Slash 命令（/cbim_*）
│
├── src/                           ← 你的代码（任意结构）
│   ├── combat/
│   │   ├── .dna/                  ← 模块（parent）：描述子模块 + 边界
│   │   │   ├── module.md          ← 必需：frontmatter + 架构主体
│   │   │   ├── contract.md        ← 可选：协议边界
│   │   │   ├── workflows/         ← 可选：确定性流程定义
│   │   │   └── ...                ← 可选：任意自定义文件
│   │   ├── skill/.dna/            ← 模块（leaf）：具体实现
│   │   └── buff/.dna/             ← 模块（leaf）
│   └── economy/.dna/              ← 模块
│
├── .dna/                          ← 可选的「项目根模块」
│   └── module.md                  ←   （仅当项目根本身是模块时——
│                                  ←    单应用形态适合；monorepo 通常省略）
│
└── .cbim/                         ← 框架（即本目录）
    ├── .dna/index.md              ← 模块注册表（框架管，install 后必有）
    ├── cbi/                       ← 能力 + 业务定义、agents、skills
    ├── engine/                    ← 统一 CLI 入口（python .cbim/engine ...）
    ├── hooks/                     ← SessionStart / Stop / PreToolUse 钩子脚本
    ├── memory/                    ← 记忆引擎 + 存储
    ├── preview/                   ← 本地可视化服务
    ├── docs/                      ← 架构文档
    └── config.json                ← 本地框架配置
```

---

## 双层治理

| 层 | 治理者 | 范围 | 规则 |
|-------|-------------|-------|------|
| **能力层** | HR | `.claude/agents/` + `.cbim/cbi/skills/` | 不含任何项目专属内容 |
| **业务层** | 架构师 | `.dna/`（`module.md` = 唯一硬约束；扩展可选） | 不引用 agent 规格 |

`.dna/` 约定遵循「**最小约束 + 开放扩展**」：目录存在即为模块；`module.md` 是唯一必需文件（YAML frontmatter + 架构主体合一）；`contract.md`、`workflows/` 及任何自定义文件可选。

| Skill 类型 | 存储位置 | 特征 |
|------------|---------|----------------|
| **能力 skill** | `.cbim/cbi/skills/` | Agent 私有能力；可移植；HR 治理 |
| **业务 skill** | `.dna/workflows/` | 模块确定性流程；项目绑定；架构师治理 |

---

## 记忆系统

| 阶段 | 路径 | 用途 |
|-------|------|---------|
| 短期 | `.cbim/memory/store/short/` | 原始会话记录（3 天后清理） |
| 中期 | `.cbim/memory/store/medium/` | 压缩后的模式摘要 |
| 知识 | `.cbim/cbi/skills/` + `.dna/` | 结晶为治理结构 |

`SessionStart` 钩子在会话开始时自动注入：项目知识快照 + 上次会话恢复点 + 近期记忆。
`Stop` 钩子把刚结束的会话蒸馏到 `memory/store/short/`。
`PreToolUse` 钩子（默认沉默）在 `/cbim_debug on` 后把工具调用写入 `.cbim/logs/tools.txt`。

---

## 预览

```bash
python -m preview.preview      # macOS / Linux （在 .cbim/ 下运行）
preview\preview.bat            # Windows
```

打开 http://127.0.0.1:8765 — Memory / Capability / Knowledge 三个 tab。

---

## 架构详解

参见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
