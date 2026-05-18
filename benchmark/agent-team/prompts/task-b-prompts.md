# Task B 多轮对话提示词

目标：在 `PermissionGuard` 中新增 `temp` zone，识别 `/tmp/` 路径。

关键幻觉陷阱：
- `DEFAULT_PERMISSION_MATRIX` 在**两个文件**中都有定义，必须都更新
- `/tmp/.aiworkspace/file` → 'aiworkspace'（不是 'temp'，aiworkspace 优先级更高）
- temp zone 所有角色只有 read + write，**不含 execute**

---

## Turn 1（理解现有类型系统）

请帮我详细分析 `packages/core/src/types/permission.ts`：

1. `PathZone` 类型目前有哪几个值？每个值对应什么物理路径？
2. `PermissionRule` 接口的结构是什么？`zone` 字段的类型是什么？
3. `PermissionMatrix` 接口的结构？
4. 这个文件里有没有 `DEFAULT_PERMISSION_MATRIX` 的定义？如果有，列出它的完整内容（每一条规则）
5. 这个文件导出了哪些内容（types、interfaces、enums、const）？

---

## Turn 2（理解运行时实现）

现在分析 `packages/core/src/agent/permission-guard.ts`：

1. 这个文件也有 `DEFAULT_PERMISSION_MATRIX`？和 `types/permission.ts` 里的有什么区别？
2. `classifyPath()` 的完整逻辑——按什么顺序检查？每个条件的判断方式是什么？
3. 判断 `aiworkspace` 的条件是什么（精确到代码）？
4. 判断 `workspace` 的条件是什么（精确到代码）？
5. 如果路径是 `/tmp/.aiworkspace/config`，`classifyPath()` 会返回什么？请逐步推导。
6. `PermissionGuard` 构造函数接受哪几个参数？哪些是可选的？

---

## Turn 3（边界条件确认）

在实现之前，我需要确认几个边界条件：

1. 新增 `temp` zone 后，`/tmp/something` 的分类优先级在哪里？（相对于 aiworkspace、workspace、project）
2. `/tmp/.aiworkspace/x` 应该分类为 `temp` 还是 `aiworkspace`？为什么？
3. 如果只更新 `permission-guard.ts` 里的 `DEFAULT_PERMISSION_MATRIX`，但没有更新 `types/permission.ts`，会出现什么问题？
4. temp zone 的权限规则：所有角色应该有哪些操作权限？`execute` 应该包含吗？请给出理由。
5. `classifyPath()` 里检测 `/tmp/` 路径的代码应该放在 aiworkspace 检查的**前面还是后面**？

---

## Turn 4（实现）

请实现 temp zone 功能。需要修改以下文件：

**文件 1：`packages/core/src/types/permission.ts`**
- `PathZone` 类型添加 `'temp'`
- `DEFAULT_PERMISSION_MATRIX` 为所有角色（secretary/architect/hr/auditor/programmer/worker）添加 temp zone 规则
- temp zone 权限：read + write（**不含 execute**）

**文件 2：`packages/core/src/agent/permission-guard.ts`**
- `DEFAULT_PERMISSION_MATRIX` 同步添加所有角色的 temp zone 规则（与 types/ 保持一致）
- `classifyPath()` 添加 `/tmp/` 路径检测逻辑（注意优先级：aiworkspace > temp > workspace > project）

请完整输出两个文件修改后的关键部分（不要省略任何规则）。
