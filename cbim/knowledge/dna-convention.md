# .dna/ 业务层约定

> 业务层由架构师治理，与能力层（`.claude/agents/`）严格分离。

## 核心概念

**模块**：任何包含 `.dna/` 子目录的目录即为一个模块。

**根模块**：项目根目录本身必须包含 `.dna/`，即为根模块。

**模块树**：由文件系统目录层级隐式定义。父模块 = 最近的含 `.dna/` 的祖先目录。无需显式声明层级关系。

---

## 模块目录结构

```
<project>/
└── <module>/
    └── .dna/
        ├── module.json         # 元数据（必填：name、owner）
        ├── architecture.md     # 内部架构设计
        ├── contract.md         # 对外 API / 协议 / 接口
        └── workflows/          # 模块内确定性流程
            └── <workflow-name>/
                └── workflow.md
```

> **变更记录不在模块目录内。** 模块的 changelog 写入 session 记忆（`cbim/memory/store/`），由架构师定期从记忆中提炼升格回 `.dna/`。

**根模块专属文件**：

```
<project>/
└── .dna/
    └── index.md    # 全树所有模块的相对路径列表（仅根模块有）
```

---

## module.json 字段

```json
{
  "name": "模块名称（必填）",
  "owner": "负责的 agent（必填，通常为 architect 或 programmer）",
  "description": "（可选）模块功能简介",
  "keywords": ["（可选）关键词，便于检索"],
  "dependencies": ["（可选）依赖的其他模块路径"],
  "includeDirs": ["（可选）需要纳入上下文的额外目录"]
}
```

---

## 知识三件套

| 文件 | 内容 | 约束 |
|------|------|------|
| `module.json` | 元数据、依赖声明 | 只含结构化元数据，无设计描述 |
| `architecture.md` | 内部结构、设计约束、关键决策 | 只含当前最终工作状态；无修改记录；高密度，能一文概括整个模块 |
| `contract.md` | 对外 API / 协议 / 接口签名 | 只含当前对外有效接口；无修改记录；高密度，以接口签名为主 |

**业务铁律**：

1. **无历史记录** — `architecture.md` 和 `contract.md` 只写当前最终状态，不写曾经改过什么、为什么改。修改过程写入 session 记忆（`cbim/memory/store/`），由架构师定期提炼升格。

2. **父模块只写关系与定位** — 父模块的 `architecture.md` 只描述：子模块之间的关系（依赖 / 组合 / 聚合）与各子模块的定位；不写任何子模块的内部细节。子模块自己的内部设计由子模块自己的 `architecture.md` 负责。

3. **能力与业务分离** — 知识三件套只含项目 / 模块知识，不引用 agent 能力规范。

---

## index.md 格式（仅根模块）

```markdown
# 模块索引

- .（根模块）
- src/combat
- src/inventory
- src/ui/hud
```

每行一个模块相对路径。架构师在新建或废弃模块时同步更新。

---

## Workflow 结构

```
.dna/workflows/<workflow-name>/
└── workflow.md     # 触发条件 + 步骤 + 输出格式
```

workflow 描述的是**模块内确定性流程**，不含 agent 能力描述。触发条件明确、步骤自包含、执行无需额外人类指令。

---

## CRUD 工具

```bash
# 列出项目所有模块
python cbim/knowledge/engine/cli.py modules list

# 查看某模块详情
python cbim/knowledge/engine/cli.py modules show <module-dir>

# 初始化新模块
python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner <owner>
```
