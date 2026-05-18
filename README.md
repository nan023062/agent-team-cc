# CBIM — Capability-Business Independence + Memory

> 一种多 Agent 协作的设计哲学，以及基于该哲学的 Claude Code 多 Agent 框架。

**CBIM** = **CBI**（Capability-Business Independence，能力-业务独立性）+ **M**（Memory，记忆系统）

核心理念：**能力与业务必须严格分离。**

- **能力**（Agent 定义、Skills）—— 可移植的专业技能，存于 `.claude/agents/`，由 HR 治理
- **业务**（模块知识、架构蓝图）—— 特定项目的知识图谱，存于 `.dna/`，由架构师治理
- **记忆**（Memory）—— 跨会话的上下文积累，短期 + 中期，自动注入每次会话

两者只通过任务接口协作，不相互耦合。Agent 定义放到任何项目仍然有意义 → 合规。

---

## Agent 团队

```
用户
  ↓
助手（CLAUDE.md — 唯一对外接口，任务拆解与调度）
  ├── 架构师   设计并维护项目知识体系（.dna/）
  ├── HR       Agent 全生命周期管理（招募 / 培训 / 考核 / 归档）
  ├── 评审官   独立批判审查（对抗性视角，只读）
  └── 程序员   按蓝图实现代码（可按需裂变为多个专精 agent）
```

你只需要和助手说话。助手负责理解意图、拆解任务、派发给合适的 Agent、汇总结果。

---

## 安装

### 自动安装（推荐）

**macOS / Linux：**
```bash
python cbim/install.py
```

**Windows：**
```
双击 cbim/install.bat
```

脚本自动完成：创建 `.venv`、安装依赖、复制 agent 定义、注册 hooks、初始化 `CLAUDE.md`。

### 手动安装

详见 [INSTALL.md](INSTALL.md)。

---

## 快速开始

```bash
# 1. 安装框架
python cbim/install.py

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填写 ANTHROPIC_API_KEY=sk-ant-...

# 3. 启动 Claude Code
claude
```

首句推荐：**"请初始化本项目的模块知识体系"**

助手会派发架构师在项目根建立 `.dna/` 知识体系，之后即可正常使用。

---

## 后续怎么用

直接告诉助手要做什么，不用指定 agent：

| 你想做 | 直接说 |
|--------|--------|
| 初始化知识体系 | 请初始化本项目的模块知识体系 |
| 新建功能模块 | 新建一个 combat 模块 |
| 实现功能 | 按当前蓝图实现登录接口 |
| 审查设计 | 审一下这次改动 |
| 查历史决策 | 查一下 combat 模块的历史决策 |
| 招募新 agent | 帮我招募一个 AI 工程师 |

---

## 目录结构（部署后）

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
├── .env                           ← API Key（gitignore）
├── .venv/                         ← Python 虚拟环境（gitignore）
│
├── .claude/
│   ├── settings.json              ← 权限配置 + hook 注册
│   └── agents/
│       ├── architect/             ← 架构师
│       ├── hr/                    ← HR
│       ├── auditor/               ← 评审官
│       └── programmer/            ← 程序员
│
├── .dna/                          ← 项目知识根模块（架构师创建）
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   └── contract.md
│
└── cbim/                          ← 框架本体（随项目提交 git）
    ├── install.py                 ← 自动安装脚本
    ├── install.bat                ← Windows 安装入口
    ├── cc-template/               ← Claude Code 安装模板
    ├── knowledge/                 ← 知识库引擎（能力层 + 业务层 CRUD）
    └── memory/                    ← 记忆引擎（ChromaDB）
```

---

## 两层治理 · 两类 Skill

| 层级 | 治理者 | 管辖 | 铁律 |
|------|--------|------|------|
| **能力层** | HR | `.claude/agents/`（soul）+ `cbim/knowledge/skills/`（能力向 skill） | soul/skills 不含任何项目特定内容 |
| **业务层** | 架构师 | 项目各级 `.dna/`（模块知识三件套 + workflows/） | 知识三件套不引用 agent 规范 |

CBIM 将 skill 按「谁拥有」一分为二，`.claude/` 下只有 `agents/`，不再堆积 `skills/`：

| 类型 | 存储 | 特征 |
|------|------|------|
| **能力向 skill** | `cbim/knowledge/skills/` | agent 私有能力，可移植，HR 治理 |
| **业务向 skill** | `.dna/workflows/` | 模块确定性流程，与项目绑定，架构师治理 |

---

## 记忆系统

| 层级 | 路径 | 触发 |
|------|------|------|
| 短期 | `cbim/memory/store/short/` | Stop hook 自动写入 |
| 中期 | `cbim/memory/store/medium/` | 助手定期提炼压缩 |

SessionStart hook 在每次会话开始时自动注入：项目知识快照（模块树 + agent 列表）+ 近期相关记忆。

---

## 架构详解

见 [cbim/docs/ARCHITECTURE.md](cbim/docs/ARCHITECTURE.md)

---

## 依赖

- Python 3.10+
- Claude Code CLI
- chromadb ≥ 0.6.0（记忆向量索引，`install.py` 自动安装）

---

## License

[MIT](LICENSE)
