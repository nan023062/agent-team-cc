# .aiworkspace/ 内容层约定

> 内容层由架构师治理，与能力层（`.claude/agents/`）严格分离。

## 核心概念

**模块**：任何包含 `.aiworkspace/` 子目录的目录即为一个模块。

**根模块**：项目根目录本身必须包含 `.aiworkspace/`，即为根模块。

**模块树**：由文件系统目录层级隐式定义。父模块 = 最近的含 `.aiworkspace/` 的祖先目录。无需显式声明层级关系。

---

## 模块目录结构

```
<project>/
└── <module>/
    └── .aiworkspace/
        ├── module.json         # 元数据（必填：name、owner）
        ├── architecture.md     # 内部架构设计
        ├── contract.md         # 对外 API / 协议 / 接口
        ├── changelogs/         # 决策 / 踩坑 / 约束记录
        │   ├── 2024-01-15-decision-xxx.md
        │   └── 2024-01-20-incident-yyy.md
        └── workflows/          # 模块内确定性流程
            └── <workflow-name>/
                └── workflow.md
```

**根模块专属文件**：

```
<project>/
└── .aiworkspace/
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
| `architecture.md` | 内部结构图、设计约束、关键决策 | 只含本模块内部架构，不描述外部接口 |
| `contract.md` | 对外 API / 协议 / 接口签名 | 只含对外暴露的内容，无实现细节 |

**铁律**：知识三件套只装与项目/模块相关的内容，不引用 agent 能力规范。

---

## Changelog 条目类型

| 类型 | 说明 | 升格目标 |
|------|------|---------|
| `decision` | 架构决策（为什么这样设计）| architecture.md 关键决策节 |
| `incident` | 反复踩坑的问题 | 视频繁程度升格为 workflow 或 architecture.md 约束 |
| `constraint` | 模块特有约束 | module.json.constraints 或 architecture.md |

**文件命名**：`YYYY-MM-DD-<type>-<slug>.md`

只装模块特有的非代码事实：
- 代码模式 → `architecture.md`
- 一次性 bug → commit 历史
- 跨模块约束 → `.claude/agents/architect/architect.md` 信念节

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
.aiworkspace/workflows/<workflow-name>/
└── workflow.md     # 触发条件 + 步骤 + 输出格式
```

workflow 描述的是**模块内确定性流程**，不含 agent 能力描述。触发条件明确、步骤自包含、执行无需额外人类指令。
