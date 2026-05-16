# Skill: 知识治理

## Changelog 条目类型

模块相关记录统一存放于 `memory/entries/`，由执行任务的 agent 写入，tags 中标记 `module-<name>` 以便过滤。

常见 tag 含义：
- `decision` — 架构决策（为什么这样设计）
- `incident` — 踩坑或问题
- `constraint` — 新发现的约束

只装模块特有的非代码事实；代码模式 → architecture.md；一次性 bug → commit 历史；跨模块约束 → `.claude/agents/architect.md` 的信念节。

详见 `.claude/agents/architect/skills/memory-convention.md`(同目录)。

---

## 一、模块记录治理

**Step 1 — 查询相关 entries**
运行 `.venv/bin/python tools/chroma_query.py --module <name> --query "决策 踩坑 约束" --top-k 20`，按时间窗梳理：
- 发生了哪些架构决策（decision）？
- 出现了哪些反复踩坑的问题（incident）？
- 新增了哪些模块特有约束（constraint）？

**Step 2 — 提炼 Workflow 候选**
寻找重复出现（≥2次）的作业模式：
- 有清晰触发条件？
- 步骤自包含、无需额外人类指令？
- 与项目无关，只描述该模块的工作流程？

候选通过 → 起草 workflow.md，提交用户确认后写入：
```
<module-dir>/.aimodule/workflows/<name>/workflow.md
```

**Step 3 — 升格决策 / 约束到知识三件套**
- 架构决策 → 写入 architecture.md 的「关键决策」节
- 模块约束 → 写入 module.json.constraints 或 architecture.md

---

## 二、知识对齐检查

检查 architecture.md / contract.md 是否与代码现实一致：

- **签名漂移** — contract.md 记录的接口与实际代码是否一致？
- **结构漂移** — architecture.md 的内部结构图是否仍然准确？
- **依赖漂移** — module.json.dependencies 是否反映代码中的实际引用？

发现漂移 → 附文件:行号，输出对齐报告，用户确认后更新知识文件。

---

## 输出报告格式

```
## 知识治理报告（{模块} · {日期范围}）

### Changelog 概览（{N} 条）
### Workflow 升格候选（{M} 条）
### 知识三件套升格（{K} 条）
### 知识漂移（{L} 处）

### 结论 + 待确认事项
```

---

## 三、模块健康考核

### 触发条件

| 信号来源 | 说明 |
|---------|------|
| 一批变更完成后 | 模块经历多轮修改，定期复盘 |
| 评审官发现问题 | auditor 标记知识漂移或契约混乱 |
| 用户主动请求 | 用户直接要求评估某模块健康度 |

### 步骤

**Step 1 — 读取模块现状**

读取模块三件套：
- `module.json` — 核查 name、owner、dependencies、includeDirs
- `architecture.md` — 内部结构图、设计约束、关键决策
- `contract.md` — 对外接口签名与使用方声明

同时扫描：
- `memory/entries/`（`tags=module-<name>`）— 未升格的 decision / incident / constraint 积压量
- `workflows/` — 已有 workflow 覆盖度

**Step 2 — 判断健康状态**

| 状态 | 表现 |
|------|------|
| 健康 | contract 稳定无漂移；architecture 结构图与实现一致；changelog 无长期积压；workflow 覆盖主要场景 |
| 需治理 | 发现漂移（签名 / 结构 / 依赖）；changelog 有未升格的决策或约束；有成熟 workflow 候选未提炼 |
| 需拆分 | architecture.md 包含多个互相独立的职责域；contract.md 接口分属不相关功能域；agent 每次只用模块知识的一小部分 |

**Step 3 — 输出考核结论**

| 结论 | 后续行动 |
|------|---------|
| 健康 | 记录本次评估时间，无需额外操作 |
| 需治理 | 触发「知识治理」skill（Changelog / 知识对齐检查） |
| 需拆分 | 触发「拆分模块」流程（需用户确认） |

**Step 4 — 汇报秘书**

```
## 模块健康考核报告（{模块} · {日期}）
### 现状概览（contract / architecture / changelog / workflow）
### 健康状态判断（健康 / 需治理 / 需拆分）
### 建议后续行动
```
