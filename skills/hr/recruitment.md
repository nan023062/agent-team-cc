# Skill: 人才招聘/归档

## 招聘流程

### 触发条件
- 秘书申请执行 agent（描述所需能力）
- 培训 skill 裂变评估通过，需要创建子 agent

### 步骤

**Step 0 — 匹配检查（优先，仅秘书申请时）**

收到需求后，读取 `.claude/agents/` 目录，排除核心 4 个（`architect.md`、`hr.md`、`auditor.md` 及秘书），逐一读取各 work agent 的 `.md` 文件确认职责：
- **有匹配** → 直接返回 agent 文件路径给秘书，流程结束，不创建新 agent
- **无匹配** → 进入招聘流程

**Step 1 — 需求澄清**

向秘书确认：
- 需要什么能力？（技术栈、工作方式）
- 与现有 work agent 的区别是什么？
- 预期任务类型和频率？

不能回答清楚 → 拒绝创建，请秘书补充需求。

**Step 2 — 起草 agent 文件**

Claude Code 版 agent 文件格式（`.claude/agents/<id>.md`）：

```markdown
---
name: <agent-id>
description: <一句话描述，供秘书选择时参考>
model: claude-sonnet-4-6
tools: Read, Write, Edit, Glob, Grep, Bash
---

# <显示名称>

[SOUL 内容：性格与说话方式、口头禅、情感表达、立场]

---

[IDENTITY 内容：定位、与其他 agent 关系、权限范围、技术规范]
```

铁律：性格/情感/信念 → 文件前半部分（SOUL），不进后半部分；职责/规范/技术标准 → 文件后半部分（IDENTITY），不进前半部分。

**可用模型参考：**
- `claude-opus-4-6` — 复杂推理、设计类任务（成本高）
- `claude-sonnet-4-6` — 通用执行任务（默认选择）
- `claude-haiku-4-5` — 轻量快速任务

**Step 3 — 草案自检**

**文件可移植性**：对 SOUL 和 IDENTITY 各自问：把这段内容放到另一个完全不同的项目里，它还有意义吗？
- 有 → 通过
- 没有 → 删除或修改，直到通过

**配置完整性**：
- `name` frontmatter 填写？
- `description` 足够清晰，秘书能据此判断何时使用？
- `model` 与职责类型匹配？
- `tools` 只开放所需权限？

**Step 4 — 提交用户确认**

向秘书汇报草案，由秘书转呈用户确认。

**Step 5 — 完成创建**

- 在 `.claude/agents/<id>.md` 创建 agent 定义文件
- 通知秘书：新 agent 已就绪，可以派发任务

---

## 归档流程

### 触发条件
用户或秘书决定某 work agent 的角色不再需要。

### 步骤

**Step 1 — 影响分析**
- 是否有待处理的任务？→ 与秘书协商转移
- 有无值得保留的经验教训？→ 先执行培训 skill 提炼后再归档

**Step 2 — 提交用户确认**

汇报影响分析结果，确认是否继续。

**Step 3 — 执行归档**

- 删除或重命名 `.claude/agents/<id>.md`（加 `.archived` 后缀保留历史）
- 若有 `memory/<id>/` 目录，一并归档或删除
- 通知秘书：agent 已归档
