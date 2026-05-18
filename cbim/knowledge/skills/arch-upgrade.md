# Skill: 知识升格（架构师）

> 将 session 记忆中的设计决策、架构洞察提炼，沉淀回 `.aimodule/`，形成持久知识。

## 触发场景

- 一批任务完成，涉及重要架构决策
- 同一设计模式出现 ≥2 次（值得 workflow 化）
- 助手要求整理某模块的知识

---

## 升格流程

### Step 1 — 检索相关记忆

```bash
python cbim/memory/engine/cli.py query "<模块名> 架构 设计" --top-k 10
python cbim/memory/engine/cli.py query "<模块名> 接口 变更" --top-k 10
python cbim/memory/engine/cli.py query "<模块名> 决策" --top-k 5
```

### Step 2 — 判断升格目标

| 内容类型 | 升格目标 |
|---------|---------|
| 内部结构变化、设计约束、关键决策 | `architecture.md` |
| 接口 / API / 协议变更 | `contract.md` |
| 出现 ≥2 次的确定性执行流程 | `workflows/<name>/workflow.md` |
| 模块关系变化（新增依赖 / 解耦） | `module.json` 的 `dependencies` |

**不升格的内容**：项目特有的临时方案、一次性的调试记录、尚未验证的假设。

### Step 3 — 写入知识三件套

**`architecture.md`** — 追加或更新：
```markdown
## <决策主题>

### 背景
<为什么需要这个设计>

### 决策
<做了什么选择>

### 约束
<不允许做什么>
```

**`contract.md`** — 追加或更新接口描述，保持与实现一致。

**新建 Workflow**：
```
.aimodule/workflows/<workflow-name>/workflow.md

格式：
# Workflow: <名称>
## 触发条件
## 前提
## 步骤
## 输出
```

### Step 4 — 运行合规检查

升格完成后执行 `arch-governance.md` 的快速检查。

### Step 5 — 汇报

向助手汇报：
- 升格了哪个模块的哪部分知识
- 依据哪些 session 记忆
- 是否新增了 workflow
