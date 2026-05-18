# Skill: 写短期记忆（Session Entry）

**主 agent 专用。由 Stop hook 自动触发，通常无需手动执行。**

---

## 触发方式

| 方式 | 说明 |
|------|------|
| 自动（推荐） | Session 结束时 Stop hook 自动解析 transcript，写入 entry |
| 手动 | Hook 未触发 / 需要补充重要信息时，主 agent 手动写入 |

---

## Entry 格式

文件路径：`memory/store/short/YYYY-MM-DD-main-<slug>.md`

```markdown
---
tier: short
tags: session
modules: combat pathfinding   # 可选，涉及的模块名（空格分隔）
---

## 任务概述
（用户的原始请求，一两句话概括）

## Subagent 执行记录

### <subagent 描述>
结果：<关键输出摘要>

## 写入/修改文件
- path/to/file

## 信号
- [ ] MUST: agent-id: 描述
- [ ] WANT: 模块名: 描述
- [ ] HOW: agent-id 或 模块名: 描述
- [ ] IS: 模块名: 描述
```

---

## 信号四象限

信号是提炼中期记忆和治理决策的原料。每条信号标注所属象限，决定后续流向：

| 象限 | 类型 | 回答什么 | 跨项目 | 最终流向 |
|------|------|---------|--------|---------|
| **MUST** | maxim（原则） | 什么绝对不能违反？ | **是**——换项目换语言仍成立 | agent soul / `cbim/knowledge/skills/` |
| **WANT** | decision（决策） | 为什么选这个方案？ | 否——当前项目的主动取舍 | `.dna/architecture.md`（ADR 格式） |
| **HOW** | pipeline（流程） | 这个流程应该怎么跑？ | 视情况 | 跨项目 → `cbim/knowledge/skills/` / 项目专属 → `.dna/workflows/` |
| **IS** | knowledge（事实） | 当前事实是什么？ | 否——可验证的系统事实 | `.dna/contract.md` |

---

## 信号填写规范

### MUST — 绝对原则（跨项目成立）

记录 agent 不能违反的约束，或应该始终遵守的行为准则。

**典型触发场景：**
- 用户纠正了 agent 的行为（human correction — 最高优先级信号）
- agent 的操作产生了不可逆后果（删除、覆盖、外发）
- 发现 agent 越出了角色边界

**格式：** `MUST: agent-id: 描述`

```
- [x] MUST: programmer: 执行批量删除前必须展示预期变更范围并获得确认
- [x] MUST: architect: 不得直接修改代码，只能提出架构建议
- [x] MUST: 所有agent: 遇到未定义的业务术语必须先澄清再执行，不得自行解读
- [x] MUST: programmer: 调用写操作 API 前必须先执行 dry-run 验证
```

### WANT — 项目决策（当前项目取舍）

记录"为什么选 A 而不选 B"——有理由、有代价的主动选择。

**典型触发场景：**
- 做了技术选型（框架、协议、存储）
- 划定了服务边界或接口设计
- 做了和"默认做法"不同的取舍

**格式：** `WANT: 模块名或范围: 决策描述`

```
- [x] WANT: memory模块: 选择 FileBackend 而非 ChromaDB；接受无语义检索，换取零外部依赖
- [x] WANT: combat模块: 选择 ECS 架构而非 OOP；接受开发复杂度，换取性能和可组合性
- [x] WANT: auth模块: token 不存 Redis，存 JWT 自包含；接受无法主动吊销，换取无状态服务
```

### HOW — 流程模式（可能跨项目）

记录"这件事应该按什么步骤来"——验证有效的执行方式。

**典型触发场景：**
- 某个做法显著提升了效率或减少了错误
- 发现了一个 agent 处理某类任务的固定模式
- 某个流程在多个 session 中重复出现

**格式：** `HOW: agent-id 或 模块名: 流程描述`

```
- [x] HOW: architect: 先出 contract 再出 architecture，接口稳定性更高
- [x] HOW: programmer: 新模块开发顺序：接口定义 → 单测 → 实现 → 集成测试
- [x] HOW: combat模块: 伤害计算流程：接收输入 → 验证 → 计算 → 广播结果，不可跳步
```

### IS — 当前事实（可验证的系统状态）

记录"现在是什么样的"——接口、配置、规则的当前版本。

**典型触发场景：**
- 接口签名发生变更
- 业务规则定义更新（新旧定义需都记录）
- 配置项调整（限流、超时、阈值等）
- 依赖版本变更

**格式：** `IS: 模块名: 事实描述（旧值 → 新值，如有）`

```
- [x] IS: auth模块: token 有效期从 24h 改为 8h（2026-05-18）
- [x] IS: combat模块: 伤害计算接口签名变更为 calculate(actor, target, context)
- [x] IS: API网关: 限流阈值 100 req/min（按 user_id）
- [x] IS: 业务规则: "活跃用户"定义变更——旧：90天内登录；新：90天内有购买行为
```

---

## 优先级：什么信号最值得填

按重要性排序：

1. **用户对 agent 的纠正**（correction）— 必填，属于 MUST 或 HOW
2. **IS 类变更**（接口、规则、配置变化）— 必填，防止后续决策基于过时事实
3. **WANT 类决策**（有权衡取舍的选择）— 必填，记录"为什么"
4. **MUST 类负向模式**（agent 做了不该做的事）— 必填
5. **HOW 类正向模式**（重复出现的有效做法）— 建议填

**不值得填写：**
- 中间推理步骤、临时计算结果
- 可以重新查询的实时数据（天气、股价等）
- 一次性的特殊情境细节（无泛化价值）
- 闲聊性质的对话内容

---

## 手动写入后更新索引

写入文件后，通知引擎：

```bash
.venv/bin/python -m memory.engine.cli add memory/store/short/<filename>.md --tier short
```
