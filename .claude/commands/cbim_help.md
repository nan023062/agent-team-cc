---
description: Show CBIM commands overview + workflow summary
---

Display the following overview to the user verbatim (in Chinese):

---

# CBIM 总览

**框架定位：** Capability-Business Independence + Memory。能力层（agent + skill）与业务层（.dna 模块）解耦，所有沉淀经记忆系统持续提炼。

## 工作流

```
用户 → 协调者（CLAUDE.md）
         │
         ├─ 派发任务 → architect / hr / auditor / programmer (agent，.claude/agents/)
         │              │
         │              └─ 调用 skill (python .cbim/engine skill show <name>) 执行
         │
         ├─ 写记忆 → .cbim/memory/store/short/  (Stop hook 自动)
         ├─ 蒸馏  → .cbim/memory/store/medium/ (architect 周期)
         └─ 知识  → .dna/ + .cbim/cbi/skills/   (architect 提升)
```

## Slash Commands（本地）

| 命令 | 作用 |
|---|---|
| `/cbim_help` | 本帮助 |
| `/cbim_debug on\|off\|status` | 控制 `.cbim/.debug` 标志——开启/关闭额外的 `[ENG]`/`[IMP]` 引擎内部日志（基础信号永远开启） |
| `/cbim_log [N]` | 查看当前会话日志最近 N 条（默认 50，所有信号类型在同一文件） |

## CBIM Engine 命令 (`python .cbim/engine <domain> <cmd>`)

| 域 | 命令 | 说明 |
|---|---|---|
| `memory` | `write-session` / `load-context` / `create` / `add` / `query` / `delete` / `reindex` / `cleanup` | 记忆 CRUD + 查询 |
| `dashboard` | `--port` / `--no-browser` | 启动本地仪表盘 |
| `dna` | `list` / `show` / `init` / `reindex` | 业务模块（`.dna/`）管理 |
| `agent` | `list` / `show` / `scaffold` / `archive` | Agent 注册表 |
| `skill` | `list` / `show <name>` | 列出/查看 skill 内容 |
| `soul` | `list` / `show <name>` | 列出/查看 agent 灵魂模板 |
| `snapshot` | `[--root PATH]` | 生成项目知识快照 |
| `config` | `get <key>` / `set <key> <value>` / `show` | 读写 `.cbim/config.json` |
| `debug` | `on` / `off` / `status` | 切换 PreToolUse 工具调用日志 |
| `log` | `show` / `tail` | 查看合并的 debug 日志 |

## 关键路径

- `.cbim/` — 框架代码（read-only，由 `.claudeignore` + deny 保护）
- `.cbim/memory/store/short/` — 原始会话记录（3 天后清理）
- `.cbim/memory/store/medium/` — 蒸馏后的模式
- `.cbim/.dna/index.md` — 模块注册表（architect 维护）
- `.claude/agents/` — agent 定义（架构师/审计/HR/程序员 + 自定义）
- `.claude/commands/` — slash command 定义
- `.claude/settings.json` — hooks + permissions
- `CLAUDE.md` — 协调者指令（每次会话自动加载）

## 钩子

- **SessionStart** — 加载记忆上下文 + 生成知识快照
- **Stop** — 蒸馏本轮会话写入 `memory/store/short/`
- **PreToolUse** — 工具调用日志（受 `.cbim/.debug` 控制）

详见 `python .cbim/engine skill show dispatch`（派发流程）和各 agent 的 `.md`（性格/职责/skill 表）。
