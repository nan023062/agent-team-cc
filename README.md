# agent-team-cc

为 Claude Code 项目部署一套开箱即用的 Agent Team 工作流。

## 是什么

一个可复制部署的 agent team 模板。将本仓库内容覆盖到任意目标项目的根目录，该项目即获得完整的多 agent 协作能力。

```
用户
  ↓
助手（CLAUDE.md — 唯一对外接口）
  ├── 架构师   模块设计、知识体系维护
  ├── HR       Agent 全生命周期管理
  ├── 评审官   独立批判审查
  └── 程序员   按蓝图实现代码
```

## 快速开始

5 步完成本地启用。手动安装看下面;**想让 AI agent 一键安装**,把 `INSTALL.md` 的 SOP 正文贴给目标项目里的 Claude Code 即可。

**1. 复制到目标项目**

```bash
cp -r agent-team-cc/. your-project/
cd your-project
```

或直接在本仓库目录内继续。

**2. 创建虚拟环境**

Homebrew Python 默认禁止全局 pip 安装，统一用项目内的 `.venv`：

```bash
python3 -m venv .venv
```

**3. 安装依赖**

```bash
.venv/bin/pip install -r memory/requirements.txt
```

只需要 `chromadb`（记忆系统向量索引）。

**4. 配置 `.env`**

```bash
cp .env.example .env
# 编辑 .env，把 ANTHROPIC_API_KEY 替换为你的真实 key（sk-ant-...）
```

ChromaDB 向量索引默认存 `memory/chroma_db/`，无需额外配置；如需团队共享再取消注释 `CHROMA_HOST/PORT`。

**5. 启动 Claude Code**

在项目根目录 `claude`，主 session 即助手。首句对话推荐：

> 请初始化本项目的模块知识体系

助手会派发架构师创建 `.aimodule/` 知识体系，之后即可进入正常使用。

---

### 后续怎么用

所有交互都通过助手，**直接说要做的事**，不用指定 agent。常见话术：

| 你想做 | 直接说 |
|--------|--------|
| 让架构师设计/初始化模块 | "新建一个 combat 模块" / "重新设计支付流程" |
| 让程序员实现某功能 | "按当前模块蓝图实现登录接口" |
| 启动独立审查 | "审一下这次改动" / "评一下这个设计" |
| 招人 / 培训 / 考核 | `/hr-daily-signal`、`/hr-weekly-assessment`（slash 命令） |
| 查记忆 | "查一下 combat 模块的历史决策" |

助手会自动判断派发给谁、是否并行、要不要找 HR 招人。

## 目录结构

```
CLAUDE.md                    ← 助手身份（主 session）
.claude/
  agents/
    architect/               ← 架构师
    hr/                      ← HR
    auditor/                 ← 评审官
    programmer/              ← 程序员
  commands/
    hr-daily-signal.md       ← /hr-daily-signal
    hr-weekly-assessment.md  ← /hr-weekly-assessment
  hooks/
    load-memory.py           ← SessionStart hook：自动注入近期记忆
    write-memory.py          ← Stop hook：自动写入 session 记忆
  skills/
    memory/
      SKILL.md               ← 主 agent 记忆操作接口（内部封装脚本）
      scripts/               ← 向量查询脚本（安装到 memory/）
memory/
  entries/                   ← 主 agent session 记录（明文 md，可提交 git）
  chroma_db/                 ← 向量索引（不提交 git，可随时重建）
  memory_index.py            ← 构建向量索引
  memory_query.py            ← 向量查询（返回文件路径）
  requirements.txt
docs/
  ARCHITECTURE.md            ← 架构详解
  aimodule-convention.md     ← 内容层约定
  INSTALL.md                 ← 安装指南
.env.example                 ← 环境变量模板（复制为 .env 后填写）
.venv/                       ← Python 虚拟环境（自行创建，已 gitignore）
```

## 核心机制

- **助手** — `CLAUDE.md` 定义，主 session 本身即助手，无需额外启动
- **Subagent 派发** — 所有业务 agent 通过 `Agent` tool 以独立 context spawn
- **两层治理** — 架构师管内容层（`.aimodule/`），HR 管能力层（`.claude/agents/`）
- **记忆系统** — `memory/entries/` 存明文 md（可提交 git），ChromaDB 仅作向量索引；本地存 `memory/chroma_db/`，团队服务器设 `CHROMA_HOST`
- **venv 约定** — skill 内命令使用 `.venv/bin/python` 调用，确保依赖隔离

详见 `ARCHITECTURE.md`。

## 常见问题

**Q：跳过 venv，直接全局 pip 装 chromadb 行不行？**
不行（Homebrew Python 默认拒绝），且 skill 写死走 `.venv/bin/python`，必须在项目根创建 `.venv`。

**Q：换其他项目目录部署，还要重做 venv 吗？**
要。每个部署的项目根都需要自己的 `.venv`。如不想重装，可以在新项目 `.venv/bin/` 软链到统一安装位置的 python。

**Q：API key 安全吗？**
`.env` 已加入 `.gitignore`，不会被提交。请勿把 key 写入任何被追踪的文件。
