# Agent-Team Benchmark Report #002

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目体量 | 66 个源文件，约 15,562 行 TypeScript |
| 测试日期 | 2026-05-19 |
| 模型 | claude-sonnet-4-6 |
| 提示词版本 | v2 |
| 基线 | 14 fail / 8 pass (22 tests) |
| 总测试数 | 33 tests |

## 测试方式

**近乎 Vibe Coding**：提示词全部使用自然语言需求描述，不包含任何文件路径、类名、函数名提示。模型需要完全自主定位相关代码文件，理解现有结构后实现功能。

这是对 Base 模型最不利的测试设计——Base 需要从零探索一个 66 文件、15k 行的陌生 TypeScript 项目；CBIM 通过 `.dna/` 模块索引直接定位，差距才能真实体现。

本轮 CBIM 测试期间还进行了多项框架迭代（dispatch 流程、permissions 策略、知识先行原则），导致部分测试轮次中途打断重跑。最终记录的是框架稳定后的一轮完整 CBIM 测试结果。

---

## 测试结果

### 通过率

| | Task A (6) | Task B (16) | Task C (11) | **总计 (33)** |
|--|:-:|:-:|:-:|:-:|
| **Base** | 1/6 | 8/16 | 5/11 | **14/33 (42%)** |
| **CBIM** | 0/6 | 13/16 | 5/11 | **18/33 (55%)** |

### 失败分析

**Task A（CBIM 0/6，Base 1/6）**
- CBIM：architect → programmer 两阶段链路耗时，Task A 未能在 session 内完成实现
- Base：dryRun() 返回对象字段名不匹配（totalAttempts / detectedIssues 等为 undefined）

**Task B（CBIM 13/16，Base 8/16）**
- 两者均漏改 `classifyPath()`：`/tmp` 路径未识别为 temp zone（3 条失败）
- Base 额外失败：auditor/hr write 权限、worker/secretary execute 权限（5 条）

**Task C（CBIM 5/11，Base 5/11）**
- 两者 getStats() 返回结构字段名不匹配（startedCount / completedCount 等为 undefined）

### Token 与费用

| 指标 | Base | CBIM | 变化 |
|------|------|------|------|
| Sonnet input | 2,800 | 9,900 | +254%（多了 architect 子 agent） |
| Cache read | 10,700,000 | 2,800,000 | **-74%** |
| Cache write | 232,600 | 372,700 | +60% |
| Sonnet output | 53,800 | 39,200 | -27% |
| **总费用** | **$4.90** | **$2.85** | **-42%** |
| API 耗时 | 15m 28s | 13m 1s | -16% |
| **墙钟时间** | **36m 13s** | **15m 25s** | **-57%** |
| 代码变更 | +955 / -164 | +848 / -14 | |

---

## 观察与分析

### CBIM 本轮表现

1. **墙钟时间快 57%**：$2.85 vs $4.90，效率优势明显
2. **Task B 显著改善**：13/16 vs 8/16，CBIM 在权限矩阵双文件修改上更准确
3. **Task A 全失败**：两阶段 dispatch（architect→programmer）引入额外耗时，Turn 1 未能在对话时间内完成实现；这是框架本轮迭代的副作用

### 本轮 CBIM 框架变化（测试期间同步迭代）

- 新增 `.claudeignore` 和 `permissions.deny`（cbim/ 和 .dna/ 只读）
- 修复 coordinator 直接执行问题（dispatch SKILL.md 反模式清单）
- 引入知识先行原则（architect 先建档再 dispatch programmer）
- 修复 programmer agent 无蓝图也可执行

### 下一轮建议

- Task A 失败根因需排查：两阶段 dispatch 是否真的导致超时，还是实现本身有 bug
- 重跑一轮记录稳定后的 CBIM 基准数据
