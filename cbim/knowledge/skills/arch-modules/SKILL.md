# Skill: 业务层模块 CRUD（架构师）

> 管理项目 `.dna/` 知识体系。知识先行——先建档，再动工。

## 工具

```bash
python cbim/knowledge/engine/cli.py modules list [--root <path>]            # 列出所有模块
python cbim/knowledge/engine/cli.py modules show <module-dir>               # 查看模块详情
python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner <owner> [--description "..."]
```

---

## 新建模块

**触发**：新功能目录需要知识归档、父模块职责过重需拆分子模块。

1. 确认目录存在（或先创建目录）
2. 初始化：
   ```bash
   python cbim/knowledge/engine/cli.py modules init <dir> --name <name> --owner architect
   ```
3. 填写 `.dna/module.json`（description / keywords / dependencies）
4. 填写 `.dna/architecture.md`，遵守以下规则：
   - 只写当前最终工作状态，不写修改记录或历史背景
   - 高密度：用最简洁的文字概括整个模块，能一文说清
   - 若为父模块：只描述子模块之间的关系与各自定位，不写任何子模块内部细节
   - 若为叶子模块：描述内部结构、设计约束、关键决策
5. 填写 `.dna/contract.md`，遵守以下规则：
   - 只写当前对外有效接口，不写修改记录或废弃接口
   - 高密度：以接口签名为主，描述精简
6. 更新根模块 `.dna/index.md`，追加新模块路径
7. 运行合规检查：执行 `arch-governance.md`

**命名约定**：`name` 用 kebab-case，`owner` 填负责的 agent id。

---

## 更新模块

**触发**：接口变更、架构调整、设计决策更新。

- **内部变更** → 编辑 `architecture.md`
- **接口变更** → 编辑 `contract.md`，同步通知依赖方模块
- **元数据变更** → 编辑 `module.json`（keywords / dependencies / owner）
- **确定性流程沉淀** → 在 `.dna/workflows/<name>/workflow.md` 新建 workflow

变更后运行合规检查。

---

## 废弃模块

**触发**：模块被合并、功能下线、重构后职责消失。

1. 在 `module.json` 中标记：`"status": "deprecated"`
2. 在 `architecture.md` 顶部注明废弃原因和替代模块
3. 更新根模块 `index.md`，移除或标注该模块路径
4. 检查其他模块的 `dependencies` 是否引用了此模块，逐一更新

---

## 拆分模块

**触发**：模块职责过重（C2 违规）、上下文膨胀、单一职责失守。

1. 识别可独立的子域
2. 为每个子域 `init` 新模块
3. 将原模块内容按归属分发到各子模块
4. 原模块 `architecture.md` 保留：自己的定位 + 子模块清单 + 子模块间关系
5. 更新 `index.md`

**铁律**：子模块间不允许循环依赖；父模块不得写入子模块的内部实现细节。
