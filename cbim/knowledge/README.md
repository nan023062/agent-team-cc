# Knowledge — 项目长期记忆知识库

> 能力（Capability）× 内容（Content）双维度知识管理系统。

---

## 四象限架构

```
                        内容层（Content）
                    .dna/ 知识三件套
                            │
              低成熟度       │       高成熟度
              ─────────────┼─────────────
  高          │  探索期      │  成熟期      │
  能          │             │             │
  力          │  新 agent   │  专精 agent  │
  层          │  + 草稿模块  │  + 完整知识  │
  （         ─┼─────────────┼─────────────┤
  Ca-         │  空白期      │  知识驱动期  │
  pa-         │             │             │
  bi-  低     │  无 agent   │  有模块知识  │
  li-  能     │  无知识      │  缺执行能力  │
  ty)  力     │             │             │
              └─────────────┴─────────────┘
```

| 象限 | 能力层 | 内容层 | 状态 | 行动 |
|------|--------|--------|------|------|
| **空白期** | 无 agent | 无模块 | 项目刚开始 | 先建根模块，再招募第一个 work agent |
| **知识驱动期** | 无/弱 agent | 有 `.dna/` | 有蓝图缺执行 | HR 招募对应能力的 work agent |
| **探索期** | 有 agent | 无/草稿模块 | 有执行缺沉淀 | 架构师从记忆中提炼知识建档 |
| **成熟期** | 专精 agent | 完整知识体系 | 健康状态 | 持续治理，按需裂变 |

**健康目标**：每个活跃模块都有对应的 work agent；每个 work agent 都有对应的知识蓝图。

---

## 目录结构

```
knowledge/
├── README.md               # 本文件
├── engine/                 # 运行时引擎（CRUD 原语 + 统一 CLI）
│   ├── cli.py              # 统一入口：agents / modules 双域命令
│   ├── agents.py           # list_agents / load_agent / scaffold_agent / archive_agent
│   └── modules.py          # list_modules / load_module / init_module / update_index
└── skills/                 # 操作 skill（SKILL.md + 可选运行时脚本）
    ├── hr-agents/          # 招募 / 更新 / 归档 / 裂变
    ├── hr-training/        # agent 培训（记忆 → skill/soul）
    ├── hr-assessment/      # agent 考核
    ├── arch-modules/       # 模块 CRUD
    ├── arch-upgrade/       # 知识升格（memory → .dna/）
    ├── arch-governance/    # 合规治理巡检
    └── audit-review/       # 对抗性审查（评审官）
```

---

## 快速使用

```bash
CLI=python cbim/knowledge/engine/cli.py

# 能力层
$CLI agents list
$CLI agents show <name>
$CLI agents scaffold <name> --description "..."
$CLI agents archive <name>

# 内容层
$CLI modules list
$CLI modules show <module-dir>
$CLI modules init <dir> --name <name> --owner <owner>
$CLI modules reindex
```

---

## 两层治理边界

| | 能力层 | 内容层 |
|---|---|---|
| **数据源** | `.claude/agents/` | 项目各级 `.dna/` |
| **治理者** | HR | 架构师 |
| **生命周期** | 招募 → 培训 → 考核 → 裂变 / 归档 | 建档 → 更新 → 升格 → 废弃 |
| **铁律** | soul 只含专业能力，不含项目细节 | 三件套只含模块知识，不引用 agent 规范 |
