# memory/ 统一记忆系统约定

> 记忆层是团队的原始素材库，存放未压缩的执行记录与变更记录。  
> 压缩（提炼升格）由 HR（能力维度）和架构师（内容维度）定期执行。

---

## 目录结构

```
memory/
├── sessions/                              ← agent 执行记录（能力维度）
│   └── YYYY-MM-DD-<agent-id>-<slug>.md
└── changelogs/                            ← 模块变更记录（内容维度）
    └── YYYY-MM-DD-<type>-<module-name>-<slug>.md
```

---

## sessions/ — agent 执行记录

记录 agent 在某次任务中发生的值得关注的事实：做了什么、卡在哪、用户反馈、评审官标记。

**命名规则**：`YYYY-MM-DD-<agent-id>-<slug>.md`

**写入方**：任何 agent 在任务结束后自行写入，或由秘书代写。

**文件结构**：

```markdown
# <agent-id> · <任务简述> · <日期>

## 任务概述
（做了什么）

## 关键事件
（完成情况、阻塞点、用户反馈、评审官标记——只写非平凡的事实）

## 信号标记
- [ ] 能力缺口：（描述）
- [ ] 定位偏差：（描述）
- [ ] 优秀模式：（描述）
```

**升格路径**：HR 定期读取 `memory/sessions/`，提炼反复出现的模式 → 写入 agent skill 或更新 soul/identity。

---

## changelogs/ — 模块变更记录

记录模块在某次工作中产生的架构决策、踩坑经验、模块特有约束。

**命名规则**：`YYYY-MM-DD-<type>-<module-name>-<slug>.md`

| `<type>` | 含义 | 升格目标 |
|----------|------|---------|
| `decision` | 架构决策（为什么这样设计） | `architecture.md` 关键决策节 |
| `incident` | 反复踩坑的问题 | `workflow` 或 `architecture.md` 约束 |
| `constraint` | 模块特有约束 | `module.json` 或 `architecture.md` |

**写入方**：架构师或程序员在任务结束后写入。

**文件结构**：

```markdown
# <type> · <module-name> · <slug> · <日期>

## 模块
（模块名 + 相对路径）

## 事实描述
（发生了什么，只写非平凡的非代码事实）

## 影响范围
（哪些接口/组件受影响）

## 升格候选
- [ ] 升格到 architecture.md
- [ ] 升格到 workflow
- [ ] 无需升格
```

只装模块特有的非代码事实：
- 代码模式 → `architecture.md`
- 一次性 bug → commit 历史
- 跨模块约束 → `.claude/agents/architect/architect.md` 信念节

**升格路径**：架构师定期读取 `memory/changelogs/`（按 module-name 过滤），提炼反复出现的模式 → 更新模块 `architecture.md` / `contract.md` / `workflows/`。

---

## 压缩节奏

| 维度 | 执行者 | 触发方式 | 来源 | 目标 |
|------|--------|---------|------|------|
| 能力 | HR | `/hr-weekly-assessment` | `memory/sessions/` | agent skill / soul |
| 内容 | 架构师 | 模块健康考核 / 手动触发 | `memory/changelogs/` | `architecture.md` / `contract.md` / `workflows/` |

---

## 铁律

- `memory/` 只写原始记录，不写已压缩的结论（结论进 `.aimodule/` 或 `.claude/agents/`）
- 单条记录只描述一个事件，不做跨事件总结
- 记录写完即可，不在记录文件内做升格判断
