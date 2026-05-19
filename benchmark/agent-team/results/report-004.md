# Agent-Team Benchmark Report #004

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目体量 | 66 个源文件，约 15,562 行 TypeScript |
| 测试日期 | 2026-05-19 |
| 提示词版本 | v3 |
| 测试任务 | Task D / E / F（共 39 tests） |
| 基准 commit | e01dc92（两组相同起点） |
| 基线 | 20 fail / 7 pass（27 counted，Task F file error） |

## 测试方式

**近乎 Vibe Coding**：提示词全部使用自然语言需求描述，不包含任何文件路径、类名、函数名提示。

v3 设计原则：每个 turn 产出代码变更，无纯问答 turn。

---

## 测试结果

### 通过率

| | Task D (15) | Task E (12) | Task F (12) | **总计 (39)** |
|--|:-:|:-:|:-:|:-:|
| **Base（Sonnet）** | 8/15 | 10/12 | 0/12 | **18/39 (46%)** |
| **CBIM（Sonnet+Opus 4.7）** | 15/15 | 12/12 | 12/12 | **39/39 (100%)** |

### 失败分析

**Task D（Base: 8/15）**
- 优先级排序 4 fail：`on()` 第三参数实现有误，高优先级未能先于低优先级执行
- 历史记录 3 fail：`getHistory(type)` 过滤和 `limit` 参数未正确实现
- 通配符 5/5 pass：Base 正确实现了通配符订阅

**Task E（Base: 10/12）**
- 优先级调度 2 fail：`critical > high > normal > low` 排序未实现
- 超时、指数退避全部通过

**Task F（Base: 0/12）**
- 根因：文件放错位置
  - 测试期望：`agent/agent-resource-manager.ts`（类名 `AgentResourceManager`）
  - Base 实现：`orchestration/resource-manager.ts`（类名 `ResourceManager`）
- import 失败 → 12 个测试全部 error，无法运行
- CBIM 通过架构师确认模块归属 → 正确路径创建文件 → 12/12

---

## Token 与费用

| 指标 | Base（Sonnet） | CBIM（Sonnet+Opus 4.7） | 对比 |
|------|--------------|------------------------|------|
| Sonnet input | 150.0k | 2.6k | Base 58× |
| Sonnet cache read | 10.2m | 5.4m | — |
| Sonnet cache write | 609.4k | 487.2k | — |
| Sonnet output | 164.4k | 55.7k | Base 3× |
| Haiku input | 44 | — | — |
| Haiku output | 3.6k | — | — |
| Opus 4.7 input | — | 9.4k | — |
| Opus 4.7 cache read | — | 2.4m | — |
| Opus 4.7 cache write | — | 394.2k | — |
| Opus 4.7 output | — | 50.7k | — |
| **总费用** | **$8.36** | **$9.25** | CBIM +$0.89 |
| API 耗时 | 44m 15s | 31m 42s | CBIM 快 12m |
| **墙钟时间** | **4h 7m 40s** | **36m 43s** | ※ |
| 代码变更 | +2006 / -134 | +719 / -100 | Base 写了 2.8× 更多 |

> ※ Base 墙钟时间含大量用户暂停，不具备直接对比意义；API 耗时（44m vs 31m）更能反映实际工作量。

---

## 观察与分析

### 通过率：46% vs 100%，费用几乎持平

这轮的核心结论：**在相同费用量级下（$8.36 vs $9.25），CBIM 通过率是 Base 的 2.2 倍**。

Opus 4.7 architect 的成本（$4.98）换来了：
- Task F 文件归属正确 → 12 分
- Task D/E 接口契约清晰 → 7 分（优先级、历史记录局部实现完整）

### 文件归属：架构治理的直接体现

Task F 提示词只说"新建一个资源管控类"，两组都没有给出路径：

| | 文件路径 | 类名 | Task F 结果 |
|--|--|--|--|
| Base | `orchestration/resource-manager.ts` | `ResourceManager` | 0/12 |
| CBIM | `agent/agent-resource-manager.ts` | `AgentResourceManager` | 12/12 |

这 12 分的差距不是实现能力的差距，是"知道代码该放哪里"的差距。架构师在实现前确认了模块归属，programmer 在正确路径下实现。

### 上下文膨胀与 Compacting

| | Base | CBIM |
|--|--|--|
| Sonnet input | 150.0k | 2.6k |
| 触发 Compacting | 是 | 否 |
| 知识外化 | 无 | `.dna/` 持久化 |

Base 的 150k input vs CBIM 的 2.6k——差距 58 倍。单 session 累积了所有历史上下文，到后期每轮都在携带巨量历史作为 input。CBIM 每个 subagent 独立启动，coordinator 只传递任务摘要。

### 代码量：写得多不代表写得对

| | 代码变更 | 通过率 |
|--|--|--|
| Base | +2006 / -134 | 46% |
| CBIM | +719 / -100 | 100% |

Base 写了约 2.8 倍的代码，通过率反而更低。Compacting 导致上下文丢失，后期 turn 存在重复探索和补丁式修改。

### 关于 Base Opus 对比

本轮原计划运行 Base Opus 做公平对比（CBIM 用了 Opus 4.7 做 architect），实际 Base session 使用了 Sonnet+Haiku。公平对比（同等模型能力）有待补充。

---

## 汇总对比

| | Base（Sonnet） | CBIM（Sonnet+Opus 4.7） | 差值 |
|--|--|--|--|
| 通过率 | 18/39 (46%) | 39/39 (100%) | **+54pp** |
| 费用 | $8.36 | $9.25 | +$0.89 |
| API 耗时 | 44m 15s | 31m 42s | CBIM 快 12m |
| 代码变更 | +2006/-134 | +719/-100 | Base 2.8× 更多 |
| Compacting | 触发 | 未触发 | — |
| Task F 文件归属 | ❌ 路径错误 | ✅ 路径正确 | — |
| Sonnet input | 150.0k | 2.6k | Base 58× |
