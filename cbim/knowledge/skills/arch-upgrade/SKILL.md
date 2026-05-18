# Skill: 知识升格（架构师）

> 从中期记忆的业务条目和决策条目中提炼信号，将已验证的事实、决策、流程沉淀回 `.dna/`，形成持久业务知识。

## 触发场景

- 一批任务完成，涉及接口变更或重要架构决策
- 同一业务流程出现 ≥2 次（值得 workflow 化）
- 助手要求整理某模块的知识
- 中期记忆 `business-*.md` 或 `decision-*.md` 的治理建议出现未勾选项

---

## 升格流程

### Step 1 — 读取中期业务条目和决策条目

列出 medium tier 的全部条目：

```bash
.venv/bin/python -m memory.engine.cli query "" --tier medium --top-k 20
```

找到与目标模块相关的 `business-<module>.md` 和 `decision-<scope>.md`，用 Read 工具读取完整内容。

重点读取：
- `## IS 记录`：接口变更、业务规则变更、配置变更（→ `contract.md`）
- `## HOW 记录`：重复出现的确定性执行流程（→ `workflows/`）
- `## 决策记录`：WANT 类的选型与权衡（→ `architecture.md`）
- `## 治理建议`：上次提炼时标记的待处理项

### Step 2 — 按四象限判断升格目标

| 象限 | 信号内容 | 升格目标 | 升格条件 |
|------|---------|---------|---------|
| **IS** | 接口签名、业务规则定义、配置值 | `contract.md` | 有变更即升格，同步当前事实 |
| **WANT** | 选型决策及权衡理由（ADR 格式） | `architecture.md` | 决策已落地即升格 |
| **HOW**（业务） | 模块内确定性执行流程 | `workflows/<name>/workflow.md` | 出现 ≥2 次，步骤稳定 |
| HOW（仅 1 次） | 流程尚未验证 | 保留在中期，继续观察 | 继续积累 |

**不升格的内容**：一次性的调试记录、尚未验证的假设、项目内的临时方案。

### Step 3 — 写入知识三件套

**`contract.md`**（处理 IS 信号）

同步当前最新事实，包含旧值和新值：

```markdown
## <接口或规则名称>

当前值：<新值>
变更记录：
- YYYY-MM-DD：<旧值> → <新值>，原因：<变更原因>

示例：
## 伤害计算接口
当前签名：calculate(actor, target, context)
变更记录：
- 2026-05-15：calculate(actor, target) → calculate(actor, target, context)
  原因：引入 context 支持 buff 叠加计算

## "活跃用户"定义
当前：90 天内有购买行为
变更记录：
- 2026-05-18：90 天内有登录 → 90 天内有购买行为
  原因：财务审计要求与营收挂钩
  注：2026-Q2 前的历史数据仍按旧定义计算
```

**`architecture.md`**（处理 WANT 信号）

使用 ADR（Y-statement）格式追加决策条目：

```markdown
## 决策：<标题>

在 <情境背景> 下，
面对 <核心约束>，
选择 <方案A> 而非 <方案B>，
以实现 <目标>，
接受 <权衡代价>。

决策人：<人/agent>，日期：YYYY-MM-DD
```

**新建 Workflow**（处理 HOW 信号，出现 ≥2 次）：

```
.dna/workflows/<workflow-name>/workflow.md

# Workflow: <名称>

## 触发条件
（什么情况下运行此流程）

## 前提
（运行前需满足的条件）

## 步骤
1. ...
2. ...

## 输出
（期望的交付物）

## 注意事项
（不该跳过的步骤、已知边界）
```

### Step 4 — 更新中期条目的治理建议

勾选已完成的治理建议项，防止重复处理：

```markdown
## 治理建议
- [x] IS 变更写入 `.dna/contract.md`（接口签名已更新）   ← 已完成
- [x] HOW 流程提炼为 `.dna/workflows/`（出现 ≥2 次）    ← 已完成
- [ ] 通知架构师评审（有接口变更）                        ← 待处理
```

### Step 5 — 运行合规检查

升格完成后，执行 `arch-governance` 快速检查，确认写入内容符合规范。

### Step 6 — 汇报

向助手汇报：

```
## 知识升格汇报 — <模块名>

### contract.md 更新
- <接口/规则名>：<变更摘要>（来源：business-<module>.md IS 记录 × N 次）

### architecture.md 更新
- 新增决策：<标题>（来源：decision-<scope>.md WANT 记录）

### 新增 Workflow
- <workflow-name>：<一句话描述>（来源：HOW 记录 × N 次）

### 保留观察
- <内容>：仅出现 N 次，继续积累

### 建议后续动作
- [ ] 评审官审查新增的 workflow
- [ ] 通知程序员接口签名已变更
```
