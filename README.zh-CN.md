# CBIM

[English](README.md) | [中文](README.zh-CN.md)

CBIM（Capability–Business Independence + Memory）是面向 Claude Code 的上下文管理框架。沿能力（专精 agent 及其 skill）与业务（按模块切分的 `.dna/` 知识树）两个维度切分项目，并提供跨会话记忆管道，让每个任务的上下文 = 目标 agent 灵魂 × 任务子树 `.dna/`，与项目总大小无关。结果：上下文有界、幻觉减少、跨会话知识沉淀。

---

## 5 分钟上手

```bash
git clone https://github.com/nan023062/cbim.git
cd cbim
python v1/src/install.py        # 安装内核 + venv，并把 `cbim` 加入 PATH
```

然后，在任何想启用 CBIM 的项目里：

```bash
cd /path/to/your/project
cbim init                       # 铺设 .cbim/、.claude/、CLAUDE.md、.gitignore
```

在该项目里重启 Claude Code，然后发一句：

> 请帮我初始化本项目的模块知识系统

Architect 会为这个项目创建第一棵 `.dna/` 知识树。

**升级**：在 Claude Code 里输入 `/cbim_update`；或命令行 `cbim update -y && cbim migrate --version <latest>`。

---

## 核心命令

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

---

## 架构总览

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

---

## 环境要求

- Python 3.10+
- Claude Code CLI

## 文档

- 安装后：`.cbim/README.md`（用户手册）与 `.cbim/docs/ARCHITECTURE.md`（架构详解）
- 版本历史：[`CHANGELOG.zh-CN.md`](CHANGELOG.zh-CN.md) / [`CHANGELOG.md`](CHANGELOG.md)

## 许可

[MIT](LICENSE)
