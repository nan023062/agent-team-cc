# Agent-Team Benchmark

CBIM vs Base（单 Agent）开发效率对比测试。

---

## 测试目标

| 指标 | 说明 |
|------|------|
| Token 消耗 | Input / Cache read / Cache write / Output |
| 开发速度 | 墙钟时间（用户实际等待时间） |
| 代码正确率 | 测试通过率（v3: /72） |
| 导航能力 | 模型自主定位相关文件的效率 |

---

## 设计原则

**所有 benchmark 资产保存在 cbim 项目**，而非被测项目（agent-team）。benchmark 是 CBIM 框架的组成部分，结果数据长期沉淀在此以证明 CBIM 的实际价值。

## 目录结构

```
cbim-prompt/benchmark/agent-team/        ← 本目录（在 cbim 项目中）
├── README.md                     ← 本文件
├── reset-bench.sh                ← 重置脚本（操作 agent-team）
├── prompts/
│   ├── task-a-prompts-v2.md     ← Task A 提示词 v2（纯自然语言）
│   ├── task-b-prompts-v2.md     ← Task B 提示词 v2（纯自然语言）
│   ├── task-c-prompts-v2.md     ← Task C 提示词 v2（纯自然语言）
│   ├── task-d-prompts-v3.md     ← Task D 提示词 v3（纯自然语言）
│   ├── task-e-prompts-v3.md     ← Task E 提示词 v3（纯自然语言）
│   └── task-f-prompts-v3.md     ← Task F 提示词 v3（纯自然语言）
├── tests/                        ← 测试用例源文件（需部署到 agent-team 运行）
│   ├── task-a.bench.test.ts
│   ├── task-b.bench.test.ts
│   ├── task-c.bench.test.ts
│   ├── task-d.bench.test.ts
│   ├── task-e.bench.test.ts
│   └── task-f.bench.test.ts
└── results/                      ← 历史测试数据（长期积累）
    └── report-001.md
```

---

## 六个测试任务（v3）

| 任务 | 功能描述 | 测试文件 | 用例数 |
|------|---------|---------|-------|
| **Task A** | 调度器试运行模式 `Scheduler.dryRun()` | `task-a.bench.test.ts` | 6 |
| **Task B** | 权限系统新增 temp zone（/tmp/） | `task-b.bench.test.ts` | 16 |
| **Task C** | 任务监控器 `TaskMonitor` 类 | `task-c.bench.test.ts` | 11 |
| **Task D** | EventBus 增强（优先级 / 历史记录 / 通配符） | `task-d.bench.test.ts` | 15 |
| **Task E** | Scheduler 调度策略（独立超时 / 指数退避 / 优先级） | `task-e.bench.test.ts` | 12 |
| **Task F** | Agent 资源管控（并发限制 / 速率限制 / 使用统计） | `task-f.bench.test.ts` | 12 |

**v3 基线**：34 fail / 15 pass（A+B+C=14/8, D=12fail/3pass, E=8fail/4pass, F=file error 12 untested）
**目标**：72/72 pass

### 关键陷阱（用于验证理解深度）

- **Task A**：`DEFAULT_SCHEDULER_CONFIG.maxRetries = 1`（scheduler.ts 第 43 行）→ `withRetry()` 循环 `attempt = 0; attempt <= maxRetries`，每任务执行 **2 次**；3 个任务 totalAttempts = **6**（不是 3）
- **Task B**：`DEFAULT_PERMISSION_MATRIX` 在 **两个文件** 中都有定义（types/permission.ts 和 agent/permission-guard.ts），必须同时修改；`/tmp-backup/config.json` → `project`（classifyPath 必须用 `startsWith('/tmp/')` 含斜杠，而非 `startsWith('/tmp')`）；temp zone 无 execute 权限，即使 secretary/worker/programmer
- **Task C**：`EventBus.on()` 返回 `() => void` 取消订阅函数（event-bus.ts 第 72 行），`start()` 必须保存、`stop()` 必须调用它；`StageCompletedEvent` 只有 `stageIndex`（types/events.ts 第 126 行），无任务结果；`successRate` 分母为 0 时返回 0（不是 NaN）
- **Task D**：优先级排序在每次 emit 时生效，高优先级先被调用；历史缓冲区上限 50 条；通配符只匹配"命名空间前缀"（`task:*` 不匹配 `stage:completed`）
- **Task E**：`task.timeoutMs` 只影响单个任务；`calcRetryDelay(0)` 返回 0（首次执行无延迟）；优先级排序只在同 stage 内生效，stage 边界仍然严格串行
- **Task F**：`call()` 排队不丢弃，超限任务最终都会执行；`peakConcurrency` 记录历史峰值；`getStats()` 不传参返回 `Record<string, AgentUsageStats>`，传参返回单个 `AgentUsageStats`

---

## v2 提示词设计原则

**v1（已废弃）的问题**：提示词中直接给出文件路径（如 `scheduler.ts`、`permission-guard.ts`），导致 Base 和 CBIM 起点相同，CBIM 的模块索引导航优势被中和。

**v2 原则**：只给自然语言需求，不包含任何文件路径或代码位置提示。

```
❌ v1：「请分析 packages/core/src/orchestration/scheduler.ts 的重试机制」
✅ v2：「调度系统默认配置下一个任务失败会重试几次？10 个任务总执行次数是多少？」
```

这样 Base 需要自行探索（Glob/Grep/Read），CBIM 通过 `.dna/` 模块索引直接定位——差距才能真实体现。

---

## 标准测试流程（SOP）

### 每轮测试前

```bash
# 1. 还原所有被测文件到基线
bash benchmark/agent-team/reset-bench.sh /path/to/target-project
# 或者
BENCH_TARGET_DIR=/path/to/target-project bash benchmark/agent-team/reset-bench.sh

# 确认输出：34 failed | 15 passed（v3 基线）
```

### Base 测试

```bash
# 2. 新开 Claude Code session（不要用 claude clear，直接关掉重开）
#    在 agent-team 项目根目录打开，不要有 CBIM hooks

# 3. 按顺序粘贴提示词（六个任务连续在同一 session）
#    Task A: benchmark/prompts/task-a-prompts-v2.md（Turn 1 → 2 → 3）
#    Task B: benchmark/prompts/task-b-prompts-v2.md（Turn 1 → 2 → 3 → 4）
#    Task C: benchmark/prompts/task-c-prompts-v2.md（Turn 1 → 2 → 3）

# 4. 运行测试
npx vitest run \
  packages/core/src/__tests__/task-a.bench.test.ts \
  packages/core/src/__tests__/task-b.bench.test.ts \
  packages/core/src/__tests__/task-c.bench.test.ts

# 5. 记录结果（截图 + /cost 输出）
```

### CBIM 测试

```bash
# 6. reset-bench.sh 还原文件
bash benchmark/agent-team/reset-bench.sh /path/to/target-project

# 7. 新开 Claude Code session（在 agent-team 项目根目录，CBIM hooks 已激活）
#    首条消息确认 hooks 加载：看到「记忆加载完成」或类似提示

# 8. 同样按顺序粘贴 v2 提示词（三个任务，同一 session）

# 9. 运行测试，记录结果
npx vitest run \
  packages/core/src/__tests__/task-a.bench.test.ts \
  packages/core/src/__tests__/task-b.bench.test.ts \
  packages/core/src/__tests__/task-c.bench.test.ts
```

---

## 数据记录表

每轮测试后填写：

```
轮次：___   模式：Base / CBIM   日期：___

测试通过率：___ / 72
  Task A: ___ / 6
  Task B: ___ / 16
  Task C: ___ / 11
  Task D: ___ / 15
  Task E: ___ / 12
  Task F: ___ / 12

Token（Sonnet）：
  Input:        ___
  Cache read:   ___
  Cache write:  ___
  Output:       ___

Token（Haiku）：
  Input:        ___
  Output:       ___

费用：$___
API 耗时：___
墙钟时间：___
代码变更：+___ / -___
```

---

## 历史结果

### v1 提示词（含文件路径，2026-05-18）

| 指标 | Base | CBIM |
|------|------|------|
| 通过率 | 25/33 | 25/33 |
| 总费用 | $1.33 | $1.10 |
| 墙钟时间 | 17m 11s | 8m 56s |
| Sonnet input | 3,600 | 47 |
| Cache read | 1,500,000 | 1,500,000 |
| Cache write | 91,500 | 57,200 |
| Sonnet output | 25,600 | 22,900 |

> **注**：v1 因提示词直接给出文件路径，CBIM 模块导航优势未能体现。v2 改用纯自然语言需求重测。
