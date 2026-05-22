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

## [1.0.2] - 2026-05-22 —— 修复 `cbim migrate` PYTHONPATH bug + 收紧 updater 同级切分铁律

纯补丁版本。无对外接口变化，无 schema 变化。修复 `cbim migrate` 的一处回归，并消除长期存在的、违反 updater↔kernel 同级铁律的反向 import。

### Bug

- `cbim migrate --version <v>` 在调用方未手动设置 `PYTHONPATH` 指向内核快照路径时，会以 `ModuleNotFoundError: No module named 'cbim_kernel'` 直接崩溃。端到端 migrate 在无该未文档化 workaround 时实际上不可用。

### Root cause

- `v1/src/updater/migrate.py` 写了 `from cbim_kernel.project import sync as project_sync` —— 一处 updater → kernel 的反向 import。这违反 `.dna` 中**不容谈判**的铁律：updater 与 kernel 是 launcher 之下的同级模块，唯一耦合面是磁盘契约（`versions.json` / `kernel/<ver>/` / `.cbim/.pin`），跨边界的 Python import **任一方向**都被禁止。

### Fix

- 新增私有模块 `v1/src/updater/sync.py`，承载 `KERNEL_AGENT_NAMES` / `KERNEL_COMMAND_NAMES` 两个常量与 `sync_settings` / `sync_agents` / `sync_commands` 三个函数。三者均以显式 `kernel_root: Path` 参数注入，通过 `updater.registry` 解析路径，不再 import kernel 包。
- `v1/src/updater/migrate.py` 重构为只依赖 `updater.sync`。默认版本回退（原先 `from cbim_kernel import __version__`）改为 `updater.registry.get_default()`。
- 验收：`grep -r "cbim_kernel" v1/src/updater/` 返回 **0 行 import**；剩余命中均为磁盘路径字符串或 `python -m cbim_kernel` 子进程调用（合法的磁盘契约方向）。

### Notes

- `v1/src/kernel/cbim_kernel/project/sync.py` 暂留 —— kernel 内部仍有 2 处消费者（`project/init.py`、`engine/cli.py` 经 `sync_templates` / `read_template`），**不是**死代码。两个 sync 表面的去重留作后续 PR。
- 本补丁不覆盖：launcher 注入 PYTHONPATH（属于错误方向的修复）；`a49b62b` 引入的 kernel 门面 `_fwd`（无关，方向本就正确）。

---

## [1.0.1] - 2026-05-22 —— 执行循环机制层

本次发布把执行循环从"协调者临场发挥"提升为"显式的、由 soul prompt 驱动的机制"。不新增 CLI、不新增 hook —— 纪律完全落在 skill 文本与 `cbim init` 铺设的项目级 `CLAUDE.md` 模板里。已存在的项目通过 `cbim update --reinstall` + 重新 `init` 模板拉取。

### `arch_modules` skill

- **Execution Gate** —— DNA 状态分诊（0 / 1 / 2 / 3），配套显式的 state→action 矩阵与 Worth0 决策步骤，让架构师按知识状态路由，而不是按直觉。
- **ContextPack Schema** —— 4 个顶层字段 + `modules[]` 子 schema + Markdown 示例 + Work Agent 消费规则（缺失即拒绝，不做改写）。

### `dispatch` skill

- **Decomposition Heuristics** —— 并行 vs 串行分诊，保守默认（拿不准就串行）。
- **Phase 2 Input Contract** —— ContextPack 原文转发，用统一的 `<!-- BEGIN ContextPack -->` / `<!-- END ContextPack -->` 包裹；Work Agent 收到不含此块的 prompt 直接 reject。
- **Interruption Thresholds** —— 三条显式停机条件：意图歧义、结果冲突、破坏性越权。

### `CLAUDE.md` 模板（kernel 生成，永不由用户编辑）

- **Workflow 重写。** Step 6 分出 Branch A 回环路径：Work Agent → Architect，通过 `NEEDS_ARCH_DECISION:` 升级标记触发。Step 7 改为三分支汇总：done / follow-up / conflict。
- **循环终止。** 5 次软上限 + 显式 convergence 信号 —— 循环必须终止，不允许静默自旋。
- **Requirement-type 任务定义。** 代码 / 模块 / 契约 / `.dna` 写入被列为一等需求类型。
- **升级标记格式。** Work Agent 升级走固定的 `NEEDS_ARCH_DECISION:` 前缀。
- **Hard Rules +3。** 每次循环都先走 knowledge-first；尊重升级标记；循环必须终止。

### 架构决策强化

- 所有配置由 kernel 生成，永不复制 —— `cbim init` / `cbim update` 从模板覆盖 `CLAUDE.md`；用户对该文件的编辑不被保留。
- CBIM 执行循环作为 soul-prompt-driven 的 LLM 自律运行。不新增 CLI 命令、不新增 hook，纪律完全在文本里。

### 升级路径

```bash
cbim update --reinstall --local <kernel-src>   # 把 1.0.1 拉进 install root
cbim migrate --version 1.0.1                   # 项目重新 pin
```

然后在每个项目里重跑 `cbim init`（或等模板刷新路径）以拿到新的 `CLAUDE.md`。

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
