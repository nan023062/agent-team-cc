# Agent-Team Benchmark

CBIM vs Base（单 Agent）开发效率对比测试。

---

## 测试目标

| 指标 | 说明 |
|------|------|
| Token 消耗 | Input / Cache read / Cache write / Output |
| 开发速度 | 墙钟时间（用户实际等待时间） |
| 代码正确率 | 测试通过率（/33） |
| 导航能力 | 模型自主定位相关文件的效率 |

---

## 设计原则

**所有 benchmark 资产保存在 cbim 项目**，而非被测项目（agent-team）。benchmark 是 CBIM 框架的组成部分，结果数据长期沉淀在此以证明 CBIM 的实际价值。

## 目录结构

```
cbim/benchmark/agent-team/        ← 本目录（在 cbim 项目中）
├── README.md                     ← 本文件
├── reset-bench.sh                ← 重置脚本（操作 agent-team）
├── prompts/
│   ├── task-a-prompts-v2.md     ← Task A 提示词 v2（纯自然语言）
│   ├── task-b-prompts-v2.md     ← Task B 提示词 v2（纯自然语言）
│   └── task-c-prompts-v2.md     ← Task C 提示词 v2（纯自然语言）
├── tests/                        ← 测试用例源文件（需部署到 agent-team 运行）
│   ├── task-a.bench.test.ts
│   ├── task-b.bench.test.ts
│   └── task-c.bench.test.ts
└── results/                      ← 历史测试数据（长期积累）
    └── report-001.md
```

---

## 三个测试任务

| 任务 | 功能描述 | 测试文件 | 用例数 |
|------|---------|---------|-------|
| **Task A** | 调度器试运行模式 `Scheduler.dryRun()` | `task-a.bench.test.ts` | 6 |
| **Task B** | 权限系统新增 temp zone（/tmp/） | `task-b.bench.test.ts` | 16 |
| **Task C** | 任务监控器 `TaskMonitor` 类 | `task-c.bench.test.ts` | 11 |

**基线**：14 fail / 8 pass（还原后的状态）
**目标**：33/33 pass

### 关键陷阱（用于验证理解深度）

- **Task A**：`maxRetries=1` → 每任务执行 **2 次**（`attempt <= maxRetries` 循环），10 个任务 = 20 次总执行
- **Task B**：`DEFAULT_PERMISSION_MATRIX` 在 **两个文件** 中都有定义，必须同时修改；`/tmp/.aiworkspace/x` 归 `aiworkspace` 不归 `temp`；temp zone 无 execute 权限
- **Task C**：`EventBus.on()` 返回取消订阅函数，`stop()` 必须调用它；`StageCompletedEvent` 只有 `stageIndex`，无任务结果；`successRate` 分母为 0 时返回 0

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
bash benchmark/reset-bench.sh

# 确认输出：14 failed | 8 passed
```

### Base 测试

```bash
# 2. 新开 Claude Code session（不要用 claude clear，直接关掉重开）
#    在 agent-team 项目根目录打开，不要有 CBIM hooks

# 3. 按顺序粘贴提示词（三个任务连续在同一 session）
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
bash benchmark/reset-bench.sh

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

测试通过率：___ / 33
  Task A: ___ / 6
  Task B: ___ / 16
  Task C: ___ / 11

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
