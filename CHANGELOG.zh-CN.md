# 更新日志

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

记录 CBIM 所有值得关注的版本变更。格式大致遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，内核遵循语义化版本。

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
