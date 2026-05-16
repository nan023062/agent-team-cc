# /new-project — 注册新项目并初始化知识体系

用法：`/new-project <name> <path>`

- `<name>`：项目显示名称（用于引用）
- `<path>`：项目根目录绝对路径

## 执行步骤

**Step 1 — 读取 config/projects.json**

检查项目是否已注册（按 path 匹配）：
- 已存在 → 提示用户，流程结束
- 不存在 → 进入 Step 2

**Step 2 — 写入 config/projects.json**

在 `projects` 数组末尾追加：

```json
{
  "name": "$ARGUMENTS[0]",
  "path": "$ARGUMENTS[1]",
  "status": "active"
}
```

**Step 3 — 派发架构师初始化根模块**

```
Agent(
  description="初始化 $ARGUMENTS[0] 项目的根模块知识体系",
  prompt="""
你是架构师。先读取 .claude/agents/architect.md 加载你的完整身份。

本次任务：为新项目初始化根模块。
项目路径：$ARGUMENTS[1]

执行 module-crud skill（.claude/agents/architect/skills/module-crud.md）中的「新建模块」流程：
- 在项目根目录创建 .aimodule/（即根模块）
- 创建 module.json、architecture.md、contract.md 三件套
- 创建 .aimodule/index.md（根模块专属，列出当前模块路径）
- 创建 changelogs/ 和 workflows/ 目录

module.json 的 name 填写 "$ARGUMENTS[0]"，owner 填写 "architect"。
"""
)
```

**Step 4 — 汇报结果**

告知用户：
- 项目已注册到 `config/projects.json`
- 根模块知识体系已初始化（或报告架构师的执行结果）
- 可以开始派发任务
