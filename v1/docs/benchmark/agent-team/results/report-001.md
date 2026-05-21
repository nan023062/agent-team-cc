# Agent-Team Benchmark Report #001

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目规模 | ~15,392 行源代码，66 文件，334 existing tests |
| 测试日期 | 2026-05-18 |
| 模型 | claude-sonnet-4-6 + claude-haiku-4-5 |
| 基线测试数 | 22 tests (14 fail / 8 pass) |
| 总测试数 | 33 tests（含 Task C 11 条） |

---

## 测试设计

### 三个任务（3-4 轮提示词，连续在同一 session 执行）

| 任务 | 功能 | 关键幻觉陷阱 |
|------|------|------------|
| **Task A** | `Scheduler.dryRun()` | `maxRetries=1` → `totalAttempts = taskCount × 2`（不是 × 1） |
| **Task B** | PermissionGuard temp zone | 需同时修改两个文件的 `DEFAULT_PERMISSION_MATRIX`；`.aiworkspace` 优先于 `temp`；无 execute 权限 |
| **Task C** | `TaskMonitor` 类 | `on()` 返回取消订阅函数必须调用；`StageCompletedEvent` 无任务结果；`successRate=0` when no tasks |

### 变量控制

- 每次测试前运行 `reset-bench.sh` 还原所有被测文件
- 新开 Claude Code session（完全清空上下文）
- 三个任务连续在同一 session 内执行（模拟真实开发场景）
- 使用相同的提示词脚本（`benchmark/prompts/`）

---

## 测试结果

### 测试通过率

| | Task A (6 tests) | Task B (16 tests) | Task C (11 tests) | **总计 (33)** |
|--|:-:|:-:|:-:|:-:|
| **Base** | ✅ 6/6 | ❌ 8/16 | ✅ 11/11 | **25/33 (76%)** |
| **CBIM** | ✅ 6/6 | ❌ 8/16 | ✅ 11/11 | **25/33 (76%)** |

Task B 失败的 8 条（两者相同）：
- `classifyPath('/tmp/...')` 仍返回 `'project'`（3 条）
- auditor/hr 在 temp zone 的 write 权限（2 条）
- worker/secretary 在 temp zone 的 execute 应被拒（2 条）
- `createGuard` hook 未正确放行（1 条）

### Token 消耗对比

| 指标 | Base | CBIM | 变化 |
|------|------|------|------|
| **Sonnet input** | 3,600 | 47 | **-98.7%** |
| **Cache read** | 1,500,000 | 1,500,000 | 持平 |
| **Cache write** | 91,500 | 57,200 | -37% |
| **Sonnet output** | 25,600 | 22,900 | -11% |
| Haiku input | 4,600 | 4,500 | 持平 |
| Haiku output | 25,900 | 18,400 | -29% |

### 费用与效率对比

| 指标 | Base | CBIM | 变化 |
|------|------|------|------|
| **总费用** | $1.33 | $1.10 | **-17%** |
| **API 耗时** | 9m 56s | 8m 28s | -15% |
| **墙钟时间** | 17m 11s | 8m 56s | **-48%** |
| 代码变更 | +189 / -3 | +234 / -40 | CBIM 更多 |

### 费用拆解（Sonnet）

| 费用项 | Base | CBIM |
|--------|------|------|
| Input ($3/M) | $0.01 | ~$0.00 |
| Cache write ($3.75/M) | $0.34 | $0.21 |
| Cache read ($0.30/M) | $0.45 | $0.45 |
| Output ($15/M) | $0.38 | $0.34 |
| **Sonnet 小计** | **$1.20** | **$1.01** |

---

## 结论

### CBIM 的优势

1. **Input tokens 减少 98.7%**：`.dna/` 模块知识替代了对话中的代码解释轮次，用户无需手动引导模型理解代码结构
2. **墙钟时间快 48%**：从 17 分钟降至 9 分钟，减少了探索性对话来回
3. **费用节省 17%**：主要来自 cache write（-37%）和 output（-11%）减少

### 本次测试的局限

1. **幻觉率无差异**：Task B 两者均失败。原因分析：
   - 本轮对话仅 9-11 轮，上下文未充分填满
   - Task B 属于"跨文件修改"陷阱，对话轮次不足时两者都容易遗漏
   - 真正的幻觉压力需要 6-8+ 轮对话填满 context window

2. **单次测试**：每种方法仅跑一次，存在随机波动

### 下一步建议

- 设计 6-8 轮的专项幻觉测试（Task B 或更复杂的跨模块任务）
- 多次重复测试取平均（至少 3 次）
- 测试更大规模的功能（跨 5+ 文件的重构）
