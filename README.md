# agent-team-cc

为 Claude Code 项目部署一套开箱即用的 Agent Team 工作流。

## 是什么

一个可复制部署的 agent team 模板。将本仓库内容覆盖到任意目标项目的根目录，该项目即获得完整的多 agent 协作能力。

```
用户
  ↓
秘书（CLAUDE.md — 唯一对外接口）
  ├── 架构师   模块设计、知识体系维护
  ├── HR       Agent 全生命周期管理
  ├── 评审官   独立批判审查
  └── 程序员   按蓝图实现代码
```

## 部署方式

将本仓库文件复制到目标项目根目录（覆盖）：

```bash
cp -r agent-team-cc/. your-project/
```

之后在目标项目中打开 Claude Code，秘书即作为主 session 入口激活。

## 目录结构

```
CLAUDE.md                    ← 秘书身份（主 session）
.claude/
  agents/
    architect/               ← 架构师
    hr/                      ← HR
    auditor/                 ← 评审官
    programmer/              ← 程序员
  commands/
    hr-daily-signal.md       ← /hr-daily-signal
    hr-weekly-assessment.md  ← /hr-weekly-assessment
tools/
  chroma_write.py            ← 记忆写入
  chroma_query.py            ← 记忆检索
docs/
  ARCHITECTURE.md            ← 架构详解
  aimodule-convention.md     ← 内容层约定
  memory-convention.md       ← 记忆系统约定
```

## 核心机制

- **秘书** — `CLAUDE.md` 定义，主 session 本身即秘书，无需额外启动
- **Subagent 派发** — 所有业务 agent 通过 `Agent` tool 以独立 context spawn
- **两层治理** — 架构师管内容层（`.aimodule/`），HR 管能力层（`.claude/agents/`）
- **记忆系统** — ChromaDB 存储执行记录，支持语义检索；本地用 PersistentClient，团队服务器设 `CHROMA_HOST`

## 内容层初始化

目标项目部署后，让秘书派发架构师在项目根目录初始化 `.aimodule/` 知识体系：

> 请初始化本项目的模块知识体系

## 依赖

```bash
pip install -r tools/requirements.txt
```
