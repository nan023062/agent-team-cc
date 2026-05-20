[English](README.md) | [中文](README.zh-CN.md)

# CBIM — Capability-Business Independence + Memory

> Claude Code 的上下文管理框架。多 agent 不是团队模拟——而是沿能力维度隔离上下文的机制。

**CBIM** = **CBI**（能力-业务独立）+ **M**（记忆）

---

## 解决的问题

最常见的 Claude Code 用法——**一个默认 agent + 一堆 CLAUDE.md 规则 + 一堆 skill**——有一个会越用越糟的结构性缺陷：

- 轮次累积 → CLAUDE.md 和 skill 文件被全量加载 → token 爆炸、LLM "lost in the middle"、幻觉增加、修正污染上下文。
- 重置 session → 上下文清空，但项目记忆也丢了。每次都得重新 grep、重新理解结构、重新对 agent 介绍项目。

## 解法原理

**上下文 = 目标 agent 灵魂 × 任务子树 `.dna/`**——与项目总大小无关。

| 问题 | CBIM 解法 |
|---------|---------------|
| 上下文随轮次膨胀 | **多 agent（能力轴）× 模块拓扑树（业务轴）**。每个任务只加载目标 agent + 相关模块子树。 |
| 重置 session 后项目记忆丢失 | **SessionStart 钩子**自动注入：模块快照 + 近期记忆。零成本恢复。 |
| 跨会话知识散落 | **三段式蒸馏管道**：短期记忆 → 中期模式 → 结晶知识（能力 skill / `.dna/` workflow）。 |

```
用户 → 助手（CLAUDE.md，唯一外部接口）
         ├── 架构师     业务层治理（.dna/ 知识）
         ├── HR        能力层治理（agent / skill）
         ├── 评审       独立批判审查（只读）
         └── 工作 agent  任务执行（HR 按需创建）
```

你只跟助手对话。它分解意图、路由到正确 agent、汇总结果。

---

## 两种交付形态

本仓库同时承载 CBIM 同一套模型的两种实现：

| 版本 | 形态 | 状态 | 位置 |
|---------|------|--------|-------|
| **V1 — 提示词版** | Claude Code 提示词、agent 定义、Python 钩子 | **现已可用** | `install/` + `.cbim/`（下方快速开始装的就是它） |
| **V2 — 原生运行时** | C# / .NET 8 独立运行时 + Avalonia UI；用确定性状态机调度替代提示词驱动派发 | **即将推出** | [`CBIM/`](CBIM/) — 设计规格与架构白皮书 |

V1 在 Claude Code 内验证了 CBIM 的理论（能力-业务独立 + 记忆分页）；V2 把同一套模型上升到强类型原生运行时，让上下文剪裁、派发路由和状态变更从概率性变为确定性。

---

## 快速开始（V1 提示词版）

### 方式一：通过 Claude Code 一键安装（推荐）

在目标项目里打开 Claude Code，粘贴这条消息：

```
Please fetch https://raw.githubusercontent.com/nan023062/cbim/master/INSTALL.md to get the CBIM installation SOP, then execute all steps starting after the first divider line to install in the current project.
```

### 方式二：复制式手动安装

按 [`INSTALL.md`](INSTALL.md) 操作——克隆本仓库到临时目录，把四件套（`.cbim/`、`.claude/`、`CLAUDE.md`、`.claudeignore`）复制到目标项目，创建 venv。合并语义会保留用户自定义的 settings.json 键和 `.claudeignore` 条目。

### 方式三：一键安装脚本（遗留）

```bash
git clone --branch master https://github.com/nan023062/cbim.git
cd cbim
python3 install/install.py --root /path/to/your/project
```

安装完成后重启 Claude Code。然后发送：**"请初始化本项目的模块知识体系"**。

---

## 安装之后

安装好的框架自带用户手册：

- **使用手册**：[`.cbim/README.md`](.cbim/README.md) | [`.cbim/README.zh-CN.md`](.cbim/README.zh-CN.md) — 怎么用、目录布局、slash 命令、治理模型
- **架构详解**：[`.cbim/docs/ARCHITECTURE.md`](.cbim/docs/ARCHITECTURE.md) | [`.cbim/docs/ARCHITECTURE.zh-CN.md`](.cbim/docs/ARCHITECTURE.zh-CN.md)

---

## 环境要求

- Python 3.10+
- Claude Code CLI
- 无额外依赖（记忆引擎默认用 FileBackend，纯标准库）

## License

[MIT](LICENSE)
