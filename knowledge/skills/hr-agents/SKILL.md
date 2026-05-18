# Skill: 能力层 CRUD（HR）

> 管理 `.claude/agents/` 下的 work agent 定义。核心 4 个（architect / hr / auditor 和助手）只读，不得修改。

## 工具

```bash
python cbim/knowledge/engine/cli.py agents list                              # 列出所有 agents
python cbim/knowledge/engine/cli.py agents show <name>                       # 查看 agent 详情
python cbim/knowledge/engine/cli.py agents scaffold <name> --description "..." [--model claude-sonnet-4-6]
```

---

## 招募新 Agent

**触发**：助手申请新 agent、现有 agent 能力裂变。

1. 用 `agents.py scaffold` 生成骨架文件
2. 补充 `.claude/agents/<id>/<id>.md`：
   - frontmatter：`name / description / model / tools`
   - `## 职责` — 一句话定位
   - `## 原则` — 2-4 条行为边界
   - `## 触发场景` — 助手何时派发此 agent
3. 创建 `skills/` 目录（暂时为空即可，按需添加）
4. 向助手汇报：新 agent 名称、定位、触发场景

**可移植性铁律**：soul/identity 只含专业能力，不含任何项目特定内容。放到另一个项目里还有意义 → 可写入；否则 → 留在 memory。

---

## 更新 Agent 定义

**触发**：培训结论落地、soul 内化、职责范围调整。

- 新增 skill：在 `.claude/agents/<id>/skills/` 下创建 `<skill-name>.md`
- 更新 soul：直接编辑 `.claude/agents/<id>/<id>.md` 的职责/原则部分
- 扩展 tools：修改 frontmatter `tools:` 字段（需用户确认）

---

## 归档 Agent

**触发**：agent 长期闲置、职责已被其他 agent 覆盖、裂变后旧 agent 退役。

```bash
# 重命名加 .archived 后缀
mv .claude/agents/<id>/<id>.md .claude/agents/<id>/<id>.md.archived
```

向助手汇报归档理由和时间，由助手决定是否同步更新 CLAUDE.md。

---

## 裂变（一拆多）

**触发**：agent 上下文膨胀、职责域过宽、考核发现专注度不足。

1. 分析现有 agent 职责，划分子域
2. 为每个子域 `scaffold` 新 agent
3. 将旧 agent 的 skills 按归属分发到各新 agent
4. 归档旧 agent
5. 向助手汇报裂变方案，确认后执行
