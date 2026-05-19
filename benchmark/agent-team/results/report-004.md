# Agent-Team Benchmark Report #004

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目体量 | 66 个源文件，约 15,562 行 TypeScript |
| 测试日期 | 2026-05-19 |
| 提示词版本 | v3 |
| 测试任务 | Task D / E / F（共 39 tests） |
| 基准 commit | e01dc92（所有组相同起点） |
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
| **Base（Opus 4.7）** | 15/15 | 12/12 | 12/12 | **39/39 (100%)** |
| **CBIM（Sonnet+Opus 4.7）** | 15/15 | 12/12 | 12/12 | **39/39 (100%)** |

### 失败分析

**Task D（Base Sonnet: 8/15）**
- 优先级排序 4 fail：`on()` 第三参数实现有误，高优先级未能先于低优先级执行
- 历史记录 3 fail：`getHistory(type)` 过滤和 `limit` 参数未正确实现
- 通配符 5/5 pass：Base Sonnet 正确实现了通配符订阅

**Task E（Base Sonnet: 10/12）**
- 优先级调度 2 fail：`critical > high > normal > low` 排序未实现
- 超时、指数退避全部通过

**Task F（Base Sonnet: 0/12）**
- 根因：文件放错位置
  - 测试期望：`agent/agent-resource-manager.ts`（类名 `AgentResourceManager`）
  - Base Sonnet 实现：`orchestration/resource-manager.ts`（类名 `ResourceManager`）
- import 失败 → 12 个测试全部 error，无法运行
- Base Opus / CBIM 均在正确路径创建文件 → 12/12

---

## Token 与费用

| 指标 | Base（Sonnet） | Base（Opus 4.7） | CBIM（Sonnet+Opus 4.7） |
|------|:---:|:---:|:---:|
| Sonnet input | 150.0k | — | 2.6k |
| Sonnet cache read | 10.2m | — | 5.4m |
| Sonnet cache write | 609.4k | — | 487.2k |
| Sonnet output | 164.4k | — | 55.7k |
| Opus 4.7 input | — | 4.2k | 9.4k |
| Opus 4.7 cache read | — | 13.1m | 2.4m |
| Opus 4.7 cache write | — | 169.0k | 394.2k |
| Opus 4.7 output | — | 76.6k | 50.7k |
| **总费用** | **$8.36** | **$9.54** | **$9.25** |
| **API 耗时** | 44m 15s | **16m 9s** | 31m 42s |
| **墙钟时间** | 4h+※ | **20m 27s** | 36m 43s |
| 代码变更 | +2006/-134 | +507/-76 | +719/-100 |
| Compacting | 触发 | 未触发 | 未触发 |

> ※ Base Sonnet 墙钟时间含大量用户暂停，不具直接对比意义。

---

## 观察与分析

### 核心发现：通过率差距来自模型能力，不是框架

三组同样是 39 tests，结论清晰：

| 变量 | 影响 |
|------|------|
| Sonnet → Opus | 46% → 100%（+54pp） |
| Base → CBIM（同为 Opus 参与） | 100% → 100%（无差异） |

在这个规模的项目和单 session 场景下，**模型能力是决定性因素**，CBIM 的框架没有在通过率上带来额外增益。

### 速度：Base Opus 最快

| | API 耗时 | 原因 |
|--|--|--|
| Base Opus | **16m 9s** | 单 session，Opus 强推理，无 Compacting |
| CBIM (Sonnet+Opus) | 31m 42s | 多 agent 调度开销 + Sonnet programmer |
| Base Sonnet | 44m 15s | 单 session 上下文膨胀，触发 Compacting |

CBIM 的多 agent 调度在小项目单 session 场景下是**固定开销**，抵消了上下文最小化的优势。

### 文件归属：Opus 两者都对

Task F 提示词只说"新建一个资源管控类"：

| | 文件路径 | 正确？ |
|--|--|--|
| Base Sonnet | `orchestration/resource-manager.ts` | ❌ |
| Base Opus | `agent/agent-resource-manager.ts` | ✅ |
| CBIM | `agent/agent-resource-manager.ts` | ✅ |

Opus 单 agent 的判断能力足够，不需要架构师辅助定位。

### 上下文膨胀

| | Sonnet input | Compacting |
|--|--|--|
| Base Sonnet | 150.0k | 触发 |
| Base Opus | 4.2k | 未触发 |
| CBIM | 2.6k（Sonnet） | 未触发 |

Base Opus 的 4.2k input 远低于 Base Sonnet 的 150k——Opus 的长上下文处理更高效，或者因为推理更快、输出更精准，历史上下文增长慢。

### 代码量

| | 代码变更 | 通过率 |
|--|--|--|
| Base Sonnet | +2006/-134 | 46% |
| Base Opus | +507/-76 | 100% |
| CBIM | +719/-100 | 100% |

Opus 写得更少、更准，与模型推理能力直接相关。

---

## 汇总对比

| | Base Sonnet | Base Opus 4.7 | CBIM (Sonnet+Opus 4.7) |
|--|:-:|:-:|:-:|
| 通过率 | 18/39 (46%) | **39/39 (100%)** | **39/39 (100%)** |
| 费用 | $8.36 | $9.54 | $9.25 |
| API 耗时 | 44m 15s | **16m 9s** | 31m 42s |
| 代码变更 | +2006/-134 | +507/-76 | +719/-100 |
| Compacting | ❌ 触发 | ✅ 未触发 | ✅ 未触发 |
| Task F 归属 | ❌ | ✅ | ✅ |

## 结论

在 66 文件、单 session、9 turn 的条件下，**Opus 单 agent（Base）与 CBIM（Sonnet+Opus）通过率相同，且速度更快、费用相近**。

CBIM 的价值在这个 benchmark 维度上未能体现——其架构治理、上下文最小化、跨 session 记忆的优势需要更大规模项目、更长周期、多 session 场景才能显现。

当前 benchmark 本质上测的是**模型能力**，而非框架价值。
