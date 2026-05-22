# 更新日志

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

记录 CBIM 所有值得关注的版本变更。格式大致遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，内核遵循语义化版本。

---

## 版本治理原则

CBIM 早期阶段修复频率高。为降低用户的迁移摩擦：

- **大版本 / 小版本 bump**：发布新特性或 schema 变更时使用，用户用 `cbim migrate --version <v>` 切换。
- **补丁**（bug 修复、文档微调、内部重构）**不 bump 版本**。用户用 `cbim update --reinstall --local <kernel-src>`（或远端等价命令）拉取最新源码，pin 保持不动。CHANGELOG 在事后记录"已 rolled into 当前 pin 版本"。

这让版本号保持有意义（每个 tag 都是真正的接口变化），避免每次小修复都强制用户重装。

---

## [1.0.0] - 2026-05-22

首个公开发布版本。版本号从内部迭代中重置。

### 架构

CBIM（Capability–Business Independence + Memory）沿两轴切分 LLM agent 项目：
- **业务轴** —— 按模块切分的 `.dna/` 知识树，由 Architect 角色治理。
- **能力轴** —— 专精 agent 与其 skill，由 HR 角色治理。

跨会话记忆管道让每个任务的上下文 = 目标 agent 灵魂 × 任务子树 `.dna/` —— 上下文有界、幻觉减少、跨会话知识沉淀。

仓库中并存两套实现：
- **V1 — CC Kernel**（本次发布）：跑在 Claude Code 之上的 Python 扩展。
- **V2 — Native Agent**：独立的 C# / .NET 8 运行时；设计阶段。

### 内核 CLI

- `cbim init` —— 在当前项目铺设 `.cbim/`、`.claude/`、`CLAUDE.md`、`.claudeignore`。
- `cbim migrate --version <v>` —— 把当前项目的布局与 pin 迁移到目标内核版本。
- `cbim update [--reinstall] [--local <path>]` —— 更新已装内核；`--reinstall`（别名 `--force`）跳过版本号比对，强制重装快照。
- `cbim upgrade {check, apply}` —— 比对并应用 schema 升级。
- `cbim dna {list, show, init, edit, reindex, write-doc, write-section}` —— 模块知识 CRUD。`edit --target {frontmatter|body|section|contract|contract-section|workflow}` 为统一入口；`--value-list` 写入块式 YAML 列表，用于 list 类型字段。`write-doc` / `write-section` 保留为 deprecated 别名。
- `cbim agent {list, show, scaffold, archive}` —— agent 定义 CRUD。
- `cbim memory {add, query, cleanup, reindex}` —— 记忆条目；会话开始/结束的记忆刷新由 hook 进程内处理。
- `cbim skill {list, show}` —— 内置 skill 发现。
- `cbim snapshot`、`cbim config`、`cbim log`、`cbim dashboard`、`cbim debug`、`cbim hook`、`cbim mcp`、`cbim project`、`cbim release-notes`。

### 内部架构

- `cbi/resources/` —— 统一资源对象模型：`Agent`、`DNAModule`、`Skill`、`Workflow`、`Memory`。每个 façade 暴露 `.frontmatter` / `.body` / 子集合访问器，以及原子 `.save()`。
- `cbi/_primitives/` —— 内部引擎原语（load / parse / write）。不应被直接 import；请使用 `cbi.resources`。
- `services/_fm.py` —— 唯一的 frontmatter 解析/渲染实现。
- 依赖方向严格单向：`cli → resources → _primitives → services/_fm`。
- hooks（`write_memory`、`load_memory`）进程内运行，降低会话边界延迟。

### 滚动补丁（rolled into pinned 1.0.0）

依据上面的版本治理原则，以下修复已被 roll into 1.0.0 源码线，未 bump 版本。用 `cbim update --reinstall --local <kernel-src>` 即可拉取。

- `cbim upgrade` / `cbim update` 通过 kernel facade 调用时，会把 `<install_root>` 加到子进程 `python -m updater` 的 `PYTHONPATH`，修复装了 1.0.0 的项目里报 `ModuleNotFoundError: No module named 'updater'` 的问题。
- `cbim install`（`--local` 与 GitHub release 路径）现在会刷新位于 PATH 上的 launcher（`cbim_launcher.py`、`cbim`、`cbim.cmd`）到 `<install_root>/bin/`。此前 launcher 只在首次安装时写入、之后永不更新，导致源码中 launcher 的路由变更（例如新增 `upgrade` / `check` / `apply` 到 `UPDATER_COMMANDS`）永远到不了用户机器。刷新通过 `os.replace` 原子完成，Windows 下安全。

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.sh | bash
```

Windows / 无 bash 环境：

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.py | python3
```

固定版本：`CBIM_VERSION=1.0.0 curl ... | bash`

### 环境要求

- Python 3.10+
- Claude Code CLI
