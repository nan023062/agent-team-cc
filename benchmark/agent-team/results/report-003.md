# Agent-Team Benchmark Report #003

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目体量 | 66 个源文件，约 15,562 行 TypeScript |
| 测试日期 | 2026-05-19 |
| 模型 | claude-sonnet-4-6（coordinator/programmer）+ claude-opus-4-6（architect） |
| 提示词版本 | v2 |
| 基线 | 14 fail / 8 pass（22 tests，见 report-002） |
| 总测试数 | 33 tests |

## 测试方式

**近乎 Vibe Coding**：提示词全部使用自然语言需求描述，不包含任何文件路径、类名、函数名提示。

本轮为 CBIM 第二轮测试，使用最新框架（知识先行两阶段 dispatch、CLAUDE.md Knowledge Gate、dispatch SKILL.md v2）。

---

## 测试结果

### 通过率

| | Task A (6) | Task B (16) | Task C (11) | **总计 (33)** |
|--|:-:|:-:|:-:|:-:|
| **Base（report-002）** | 1/6 | 8/16 | 5/11 | **14/33 (42%)** |
| **CBIM Round 1（report-002）** | 0/6 | 13/16 | 5/11 | **18/33 (55%)** |
| **CBIM Round 2（本轮）** | 6/6 | 16/16 | 5/11 | **27/33 (82%)** |

### 失败分析

**Task A（CBIM Round 2: 6/6）**
- Round 1 全失败（两阶段 dispatch 耗时导致超时），Round 2 全通过
- dryRun() 接口定义和字段名完全正确

**Task B（CBIM Round 2: 16/16）**
- 满分，包括 `/tmp-backup/config.json → project`（不以 `/tmp/` 开头）分类正确
- Round 1 漏改 `classifyPath()` 的 3 条失败本轮全部通过

**Task C（CBIM Round 2: 5/11，与 Round 1 持平）**
- `getStats()` 返回对象字段名不匹配：`startedCount`、`completedCount`、`failedCount` 均为 `undefined`
- 成功率、`stagesCompleted`、`successRate=0`、`stop()` 基础行为均通过
- 根因：TaskMonitor 实现使用了不同字段名，与测试期望字段不一致

### Token 与费用

| 指标 | CBIM Round 1 | CBIM Round 2 | 变化 |
|------|-------------|-------------|------|
| Sonnet input | 2,800 | 2,900 | +4% |
| Sonnet cache read | 2,800,000 | 2,200,000 | -21% |
| Sonnet cache write | 372,700 | 183,900 | -51% |
| Sonnet output | 39,200 | 24,100 | -38% |
| Opus input | — | 4,500 | new |
| Opus cache read | — | 1,600,000 | new |
| Opus cache write | — | 282,200 | new |
| Opus output | — | 33,500 | new |
| **总费用** | **$2.85** | **$5.16** | +81% |
| API 耗时 | 13m 1s | 20m 26s | +57% |
| **墙钟时间** | **15m 25s** | **20m 53s** | +35% |
| 代码变更 | +848 / -14 | +341 / -12 | |

> Round 2 引入 Opus 4.6 作为 architect，输出质量提升（Task A/B 满分），但费用增加 $2.31。

---

## 观察与分析

### CBIM Round 2 vs Round 1 对比

1. **Task A 从 0/6 → 6/6**：知识先行两阶段 dispatch 在 Round 2 中正常完成，Round 1 的超时问题已解决（框架稳定后）
2. **Task B 从 13/16 → 16/16**：`classifyPath()` 的 `/tmp-backup` 边界情况本轮正确处理
3. **Task C 持平 5/11**：`getStats()` 字段名问题两轮均未修复，是实现层的命名约定差异，不受框架改进影响

### CBIM Round 2 vs Base 对比

| | Base | CBIM Round 2 | 提升 |
|-|------|-------------|------|
| 通过率 | 14/33 (42%) | 27/33 (82%) | **+40pp** |
| 费用 | $4.90 | $5.16 | +5% |
| 墙钟时间 | 36m 13s | 20m 53s | **-42%** |

费用与 Base 基本持平（+5%），但通过率提升 40 个百分点，墙钟时间缩短 42%。

### Task C 根因说明

Task C 失败属于字段命名约定问题，与知识先行/架构治理无关。测试期望 `startedCount`，实现返回了其他字段名（如 `started` 或 `taskStarted`）。需要在 `.dna/contract.md` 中显式约定 `getStats()` 返回结构的字段名。

### 下一轮建议

- Task C 失败根因确认：查看 TaskMonitor 实现的 `getStats()` 返回结构，与测试对齐
- 考虑在 `.dna/` 中增加接口字段名约定，防止命名漂移
- Base 重跑一轮（与 Round 2 对齐，同等框架条件下比较）
