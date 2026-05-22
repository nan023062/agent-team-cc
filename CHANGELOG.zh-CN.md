# 更新日志

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

记录 CBIM 所有值得关注的版本变更。格式大致遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，内核遵循语义化版本。

---

## [2.1.0] - 2026-05-22

### 内建 Slash 命令 — OWNED Kernel 资产

`cbim init` 现在会将 6 个内建 slash 命令安装到 `.claude/commands/`。这些命令由 kernel 持有（OWNED 策略）：`cbim migrate` 和 `cbim update` 在升级时会覆盖它们，确保命令内容始终与 kernel 版本同步。非内建的用户自定义命令永不触碰。

### 新增

- `v1/src/kernel/cbim_kernel/project/commands/` — 新模板目录，存放 6 个内建 slash 命令：`cbim_dashboard`、`cbim_debug`、`cbim_help`、`cbim_log`、`cbim_sched`、`cbim_update`。
- `sync.py` 中的 `KERNEL_COMMAND_NAMES` 常量 — 内建命令的显式枚举，与 `KERNEL_AGENT_NAMES` 对仗。
- `sync.py` 中的 `sync_command()` / `sync_commands()` — 内建命令的 OWNED 同步函数，镜像 `sync_agent` / `sync_agents` 语义。
- `migrate.py` 中的 `_update_commands()` — 每次 `cbim migrate` / `cbim update` 时覆盖内建命令。

### 变更

- `sync_templates()` 现在在 `sync_agents()` 之后、`sync_settings()` 之前插入 `sync_commands()`。
- `cbim init` 随 `.claude/agents/` 一起安装 `.claude/commands/`；非 `--force` 时已有文件跳过。
- UPDATE-FLOW 文档：OWNED 行扩展为包含 6 个内建命令；UNTOUCHED 行改为 `.claude/commands/<user-owned>`（非内建命令仍然不动）。
- 升级提示文案：在 overwrites 中区分 `.claude/commands/ (6 built-in)`，在 preserves 中区分 `.claude/commands/<user-owned>`。

---

## [2.0.0] - 2026-05-22

### 架构 — Updater / Kernel 兄弟拆分

这是一次重大架构版本。Updater 与 Kernel 现在是**兄弟关系**，不再是单体。跨版本操作（install、upgrade、migrate、pin）完全归属全新的 `updater` 包；Kernel 是纯粹的单版本运行时，不再知道自己如何被安装或升级。

### 新增

- `v1/src/updater/` — 新建机器级 updater 包，从 `installer/` 和 kernel 的 upgrade 子模块提取而来，持有所有跨版本操作。
- `cbim pin <version>` 子命令 — 将当前项目锁定到任意已安装版本（Bug C 修复）。
- updater CLI 的 `cbim migrate` 子命令 — 项目 schema 迁移现在可以直接通过 `python -m updater migrate` 触发。
- `cbim self-update` 通过 launcher 路由到 updater。
- `.claudeignore` 项目模板（OWNED 策略）— 由 `cbim init` 生成，`cbim migrate` 时刷新。默认内容：`.cbim/`、`**/.dna/`、`.venv/`、`__pycache__/`、`*.pyc`。
- `sync.read_template(name)` — kernel 管理的模板文件公开访问器，供 `cbim soul show assistant` 使用。
- `v1/docs/UPDATE-FLOW.md` / `UPDATE-FLOW.zh-CN.md` — 完整更新闭环流程图与组件边界参考。

### 变更

- `installer/` 降级为 deprecated reexport shim，所有逻辑移入 `updater/`，未来版本将删除。
- Launcher `INSTALLER_COMMANDS` → `UPDATER_COMMANDS`，新增 `update`、`upgrade`、`migrate`、`check`、`apply`、`self-update`；launcher 现在启动 `python -m updater` 而非 `python -m installer`。
- `write_pin` 从 `kernel/project/pin.py` 移除；kernel 对 `.cbim/.pin` 只读，只有 updater 负责写入。
- `kernel/project/upgrade/cli.py` 替换为 subprocess facade，将 `cbim upgrade check|apply` 和 `cbim update` 转发给 `python -m updater`。
- `kernel/project/migrate.py` 移入 `updater/migrate.py`；kernel 的 `_cmd_migrate` 改为 subprocess facade。
- Snapshot 范围收窄为仅覆盖 `versions.json` + `kernel/<ver>/`，排除 `updater/`、`bin/`、`venv/`。
- `cbim soul show assistant` 现在读取 `project/templates/CLAUDE.md.tmpl`，而非过时的 `cbi/claude_md.py` 常量。

### 修复

- **Bug A** — `upgrade apply` 的 preflight 现在能检测 legacy schema（`config.json` 有 `cbim_version` 但无 `.pin` 文件），并给出明确错误提示，引导用户先跑 `cbim migrate`。
- **Bug B** — `cbim update` 现在在内核升级成功后自动触发 `cbim migrate`，确保项目配置在同一次操作中同步跟进。
- **Bug C** — `cbim pin <version>` 子命令现已实现（此前 `cbim upgrade check` 输出中已推荐但 CLI 中不存在）。

### 移除

- `v1/src/install/` legacy installer 目录（已被 `v1/src/installer/` 和 `v1/src/updater/` 取代）。
- `v1/src/kernel/cbim_kernel/cbi/claude_md.py` 死代码（过时的 CLAUDE_MD 常量，无任何活引用）。
- `kernel/project/upgrade/{app_state,apply_flow,config,diagnose,notify,project_state,remote}.py` — 全部移入 `updater/upgrade/`。

---

## [1.3.5] - 2026-05-22

### 修复

- Launcher 现在先从 `.cbim/.pin`（1.3.3 之后的位置）读取项目 pin，再回退到 `.cbim/config.json` 中遗留的 `cbim_version` 字段。1.3.5 之前，全新安装会以 `no kernel version resolved` 失败 —— 因为 1.3.3 之后的 `cbim init` 模板不再向 `config.json` 写 `cbim_version`。**现有的 1.3.4 安装在未重装之前都是坏的**：请重新跑 `python install.py`（重新 bootstrap 或拉新 tarball），以更新带补丁的 launcher。仅 `cbim install 1.3.5` **不会**刷新 `<install_root>/bin/cbim_launcher.py`。
- Launcher 在既无项目 pin 也无 `CBIM_DEFAULT_VERSION` 时，现在回退到 `versions.json[active_default]`，而不是直接报错退出。

### 变更

- 文档：README 调度器章节回归现实（任务随内核包 `cbim_kernel.mcp_server.tasks` 出厂；目标项目里不存在 `.cbim/mcp_server/`；尚未提供项目本地任务投放路径）。
- 内部：`ARCHITECTURE.md`/`ARCHITECTURE.zh-CN.md`、`install/cli.py`、`install/install.py`、`install/settings.py`、`cbi/claude_md.py` 以及 `CLAUDE.md.tmpl` 顶部 banner 里残留的 `INSTALL.md` 引用，全部改指 `README.md`。

---

## [1.3.4] - 2026-05-22

### 新增

- `bootstrap.sh` / `bootstrap.py`：从仓库一行命令安装，无需 `git clone`。支持 `CBIM_VERSION` / `CBIM_REF` 环境变量，并通过 `CBIM_BOOTSTRAP_DRY_RUN` 进行校验。

### 变更

- README 快速开始改为以一行 bootstrap 为首选；原先的 `git clone` + `python v1/src/install.py` 路径仍然可用，但不再是主推方式。

### 移除

- `v1/INSTALL.md` 与 `v1/INSTALL.zh-CN.md` —— 这份手工 SOP 已与仓库结构发生漂移（引用了不存在的顶层 `.cbim/mcp_server/`，并手动覆盖了 `cbim init` 已能安全合并的 `.claude/settings.json`）。bootstrap 脚本 + `install.py` + `cbim init` 现已端到端独占安装入口。

---

## [1.3.3] - 2026-05-22

### 动机

项目 schema pin —— 标记"本项目处于 schema X"的项目级版本号 —— 是项目状态里写得最频繁的一项。每次 `cbim update`、`cbim upgrade apply`、`cbim migrate` 都会推进它。把它放在 `.cbim/config.json` 里意味着每次推进都：

- 让 `git diff` 出现整个 config 文件的 JSON 重新序列化，即便没有任何用户设置发生变化；
- 仅为翻一个整数就被迫做一次 JSON load-modify-dump 往返；
- 让"机器持有的游标"与"用户持有的配置"挤在同一个文件里，使得"该提交什么"变得含糊。

### 变更

- 项目 schema pin 从 `.cbim/config.json` 抽离到独立纯文本文件 `.cbim/.pin`。
  - 单行：版本号字符串，行尾带一个换行。没有 JSON、没有字段、没有注释。
  - 该文件已加入 `.gitignore` —— pin 属于本地项目状态，不属于源码。
- 所有 pin 的读写都经唯一访问器模块 `project/pin.py`（铁律 —— 其他任何代码都不得直接触碰 `.cbim/.pin`）。
- `cbim_version` 从 `.cbim/config.json` 中移除，内核不再读写该字段。

### 迁移

每个项目跑一次以下任一命令即可，二者均幂等：

```bash
cbim update -y
# 或者，如果你只想迁移而不拉取新内核：
cbim migrate --version 1.3.3
```

迁移器会：

1. 从 `.cbim/config.json` 读取旧的 `cbim_version`。
2. 将其写入 `.cbim/.pin`（单行，行尾换行）。
3. 从 `.cbim/config.json` 删除 `cbim_version`。
4. 若 `.gitignore` 中尚未包含 `.cbim/.pin`，自动追加。

迁移完成后，`git diff` 不再因 pin 推进出现噪音。

---

## [1.3.2] - 2026-05-22

### 修复

- `cbim migrate` 即使项目布局已是新版也始终推进 pin。现在没有可迁移项时直接 no-op。
- `cbim upgrade apply` 的 preflight 错误信息引用了已删除的 `--to` 标志。现已统一指向正确的 `--version`。
- `diagnose.py` 与 `/cbim_update` 斜杠命令的标志命名不一致。两者均统一为 `--version`。

---

## [1.3.1] - 2026-05-22

### 修复

- `cbim upgrade apply` 仍在向下游调用透传已删除的 `--set-default` 标志，导致每次升级都回滚。现已移除该残留标志，升级可正常应用。

---

## [1.3.0] - 2026-05-21

### 变更

- 基线版本号推进。对最终用户无行为变化；本版本用于让内核版本线与 1.3.1+ 中落地的 schema pin 工作对齐。
