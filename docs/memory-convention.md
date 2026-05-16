# memory/ 统一记忆系统约定

> 记忆层是团队的原始素材库，存放未压缩的执行记录与变更记录。  
> 压缩（提炼升格）由 HR（能力维度）和架构师（内容维度）定期执行。

---

## 目录结构

```
memory/
└── entries/
    └── YYYY-MM-DD-<type>-<agent-or-module>-<slug>.md
```

所有 entry 平铺在 `entries/` 下，通过 frontmatter 字段区分维度，不分子目录。  
每条 entry 对应一个独立事件，每天可产生多条，命名唯一，多人团队无冲突。

---

## Entry frontmatter

```yaml
---
date: YYYY-MM-DD
type: session       # session | changelog
agent: <agent-id>   # type=session 时必填
module: <module-name>  # type=changelog 时必填
tags: [tag1, tag2]
---
```

| 字段 | 说明 |
|------|------|
| `date` | 事件发生日期 |
| `type` | `session`（能力维度）或 `changelog`（内容维度） |
| `agent` | type=session 时填写 agent-id |
| `module` | type=changelog 时填写模块名（module.json 中的 name） |
| `tags` | 自由标签，便于脚本过滤 |

---

## 两类 Entry

### session — agent 执行记录（能力维度）

记录 agent 在某次任务中值得关注的事实。

**文件命名**：`YYYY-MM-DD-session-<agent-id>-<slug>.md`

**写入方**：任意 agent 任务结束后自行写入，或由秘书代写。

```markdown
---
date: 2026-05-16
type: session
agent: programmer
tags: [combat, fix, blocked]
---

## 任务概述
（做了什么）

## 关键事件
（完成情况、阻塞点、用户反馈、评审官标记——只写非平凡的事实）

## 信号标记
- [ ] 能力缺口：（描述）
- [ ] 定位偏差：（描述）
- [ ] 优秀模式：（描述）
```

**升格路径**：HR 过滤 `type=session` 的 entries，提炼反复出现的模式 → agent skill / soul 升格。

---

### changelog — 模块变更记录（内容维度）

记录模块在某次工作中产生的架构决策、踩坑经验、模块特有约束。

**文件命名**：`YYYY-MM-DD-changelog-<module-name>-<slug>.md`

**Changelog 类型**（写在 tags 中）：

| tag | 含义 | 升格目标 |
|-----|------|---------|
| `decision` | 架构决策（为什么这样设计） | `architecture.md` 关键决策节 |
| `incident` | 反复踩坑的问题 | `workflow` 或 `architecture.md` 约束 |
| `constraint` | 模块特有约束 | `module.json` 或 `architecture.md` |

**写入方**：架构师或程序员在任务结束后写入。

```markdown
---
date: 2026-05-16
type: changelog
module: combat
tags: [decision, pathfinding]
---

## 事实描述
（发生了什么，只写非平凡的非代码事实）

## 影响范围
（哪些接口 / 组件受影响）

## 升格候选
- [ ] 升格到 architecture.md
- [ ] 升格到 workflow
- [ ] 无需升格
```

只装模块特有的非代码事实：
- 代码模式 → `architecture.md`
- 一次性 bug → commit 历史
- 跨模块约束 → `.claude/agents/architect/architect.md` 信念节

**升格路径**：架构师过滤 `type=changelog` + `module=<name>` 的 entries，提炼反复出现的模式 → `.aimodule/` 知识三件套 / workflows 升格。

---

## 压缩节奏

| 维度 | 执行者 | 触发方式 | 过滤条件 | 升格目标 |
|------|--------|---------|---------|---------|
| 能力 | HR | `/hr-weekly-assessment` | `type=session` | agent skill / soul |
| 内容 | 架构师 | 模块健康考核 / 手动触发 | `type=changelog` + `module=<name>` | `.aimodule/` 三件套 / workflows |

---

## 铁律

- `memory/entries/` 只写原始记录，不写压缩后的结论
- 单条 entry 只描述一个事件，不做跨事件总结
- 压缩后的结论进 `.aimodule/` 或 `.claude/agents/`，不回写 `memory/`
- 每条 entry 独立命名，多人团队并行写入无冲突
