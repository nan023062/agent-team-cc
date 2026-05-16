# Skill: 模块建档 / 废弃

## 产物格式参考

### module.json

```json
{
  "name": "module-unique-name",
  "owner": "agent-id",
  "description": "一句话定位",
  "keywords": ["keyword1", "keyword2"],
  "dependencies": ["other-module-name"],
  "includeDirs": ["relative/path/to/extra-dir"]
}
```

**必填：** `name`（全树唯一，kebab-case）、`owner`（维护该模块知识文档的 agent id）；其余字段均可缺省。
- `dependencies` — 程序层面真实依赖的其他模块（代码引用依赖，非概念关联）
- `includeDirs` — 除根物理目录外该模块额外包含的物理目录；不得与任何其他模块的根目录或 includeDirs 重叠

Workflow 列表通过读取 `.aiworkspace/workflows/` 目录获得，不在 module.json 中声明。

### architecture.md

模块定位 + 内部结构（ASCII 图）+ 设计约束 + 关键决策

### contract.md

对外 API / 接口签名 / 协议 / 使用方

### 加载策略

- `module.json` — 预加载
- 其余文件（architecture.md、contract.md、index.md、changelogs/、workflows/ 等）— 按需加载

---

## 模块定义标准

建模块之前先判断：**这个东西应不应该成为一个模块？**

**应该建模块，当满足以下全部条件：**

1. **职责单一** — 能用一句话说清它是什么，说不清说明职责不单一
2. **契约稳定** — 对外接口（contract.md）比内部实现稳定，其他模块依赖它的接口而非实现
3. **独立可寻址** — 其他模块通过 `dependencies` 引用它时，不需要了解其内部结构

**不应该建模块，当满足任意一条：**

- 职责完全属于父模块内部，外部不需要引用它
- 只是实现细节的目录分组，没有独立的对外契约
- 与现有模块职责高度重叠（先考虑合并到现有模块）

**子模块 vs 独立模块：**

```
父模块职责包含它 + 外部只通过父模块访问 → 子模块（物理目录嵌套）
父模块职责不包含它 + 外部直接依赖它     → 独立模块（同级或更高层级）
```

---

## 新建模块

**Step 1 — 确认定位**
- 模块职责能一句话说清？
- 与现有模块有无职责重叠？（读 index.md + 各模块 module.json）
- 父模块是哪个目录？

**Step 2 — 确认物理目录**
- 根物理目录 = 模块所在目录
- 如有额外目录 → 填入 `includeDirs`，并检查与其他模块的 includeDirs / 根目录无重叠

**Step 3 — 创建文件**

```
<module-dir>/
  .aiworkspace/
    module.json       ← 填写所有字段
    architecture.md   ← 内部结构、设计约束、关键决策
    contract.md       ← 对外 API / 协议 / 接口
```

**Step 4 — 更新根模块 index.md**
在路径列表中追加新模块的相对路径。

**Step 5 — 更新父模块 architecture.md**
在父模块的内部结构图中加入新子模块。

**Step 6 — 汇报秘书**，由秘书决定是否触发评审官审查。

---

## 更新模块

- 元数据变更 → 更新 module.json
- 架构变更 → 更新 architecture.md，检查 dependencies 是否需要同步
- 契约变更 → 更新 contract.md，通知依赖方模块 owner
- includeDirs 变更 → 重新执行重叠检查

---

## 废弃模块

**Step 1 — 影响分析**
- 扫描所有模块的 `dependencies`，找到依赖当前模块的模块列表
- 逐一评估影响，协商迁移方案

**Step 2 — 确认无依赖后执行**
- 从 index.md 中移除路径
- 归档或删除 `.aiworkspace/` 目录
- 更新父模块 architecture.md

**Step 3 — 汇报秘书**

---

## 拆分模块

对应 HR 的 agent 裂变流程——当一个模块膨胀到边界混乱时，拆分为多个职责单一的子模块。

### 拆分信号（出现任意两条即触发评估）

- `architecture.md` 篇幅过大，内部结构图包含多个互相独立的职责域
- `contract.md` 暴露的接口分属多个不相关的功能域
- `module.json.dependencies` 数量过多，且可以按功能域分组归属
- work agent 执行任务时每次只用到该模块知识的一小部分（上下文浪费）

### 拆分条件（必须同时满足，否则不拆分）

1. **可切分** — 两个职责域之间无强依赖，各自独立可运行
2. **各有价值** — 每个子模块拆出来后仍有独立的对外契约（contract.md 非空）
3. **更清晰** — 拆分后各自的 architecture.md / contract.md 比原来更精准、更小

### 拆分步骤

**Step 1 — 定义切分边界**
- 明确哪些接口 / 职责归子模块 A，哪些归子模块 B
- 确认边界处无强耦合（否则先重构再拆分）

**Step 2 — 为每个子模块创建文件**
- 复用「新建模块」流程为每个子模块创建三件套

**Step 3 — 更新父模块**
- 更新父模块 `architecture.md` 的内部结构图

**Step 4 — 更新依赖引用**
- 扫描所有模块的 `dependencies`，将对旧模块名的引用更新为对应的新子模块名

**Step 5 — 更新 index.md**
- 从 index.md 移除旧模块路径
- 追加各子模块路径

**Step 6 — 提交用户确认**
结构性变更，必须在执行前获得用户确认：
- 切分边界说明
- 子模块三件套草案
- 受影响的 dependencies 列表

**Step 7 — 归档原模块**
- 用户确认后执行目录重组
- 若原模块目录作为父目录保留：清空或归档其 `.aiworkspace/`
- 若原模块整体废弃：执行「废弃模块」流程
