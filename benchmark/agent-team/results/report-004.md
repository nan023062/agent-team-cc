# Agent-Team Benchmark Report #004

## 测试环境

| 项目 | 值 |
|------|-----|
| 测试项目 | agent-team (`packages/core`) |
| 项目体量 | 66 个源文件，约 15,562 行 TypeScript |
| 测试日期 | 2026-05-19 |
| 模型 | claude-sonnet-4-6（coordinator/programmer）+ claude-opus-4-6（architect） |
| 提示词版本 | v3 |
| 测试任务 | Task D / E / F（共 39 tests） |
| 基线 | 20 fail / 7 pass（27 counted，F file error） |

## 测试方式

**近乎 Vibe Coding**：提示词全部使用自然语言需求描述，不包含任何文件路径、类名、函数名提示。

v3 设计原则：每个 turn 必须产出代码变更，无纯问答 turn。

---

## 测试结果

### 通过率

| | Task D (15) | Task E (12) | Task F (12) | **总计 (39)** |
|--|:-:|:-:|:-:|:-:|
| **Base** | 8/15 | 10/12 | 0/12 | **18/39 (46%)** |
| **CBIM** | 15/15 | 12/12 | 12/12 | **39/39 (100%)** |

### 失败分析

**Task D（Base: 8/15）**
- 优先级排序 4 fail：`on()` 第三参数未生效，监听器仍按注册顺序执行
- 历史记录 3 fail：`getHistory(type)` 过滤和 `limit` 参数未实现
- 通配符 5/5 pass：Base 正确实现了通配符订阅

**Task E（Base: 10/12）**
- 优先级调度 2 fail：`critical > high > normal > low` 排序未实现
- 超时、指数退避全部通过

**Task F（Base: 0/12）**
- 根因：文件放错位置
  - 测试期望：`agent/agent-resource-manager.ts`（类名 `AgentResourceManager`）
  - Base 实现：`orchestration/resource-manager.ts`（类名 `ResourceManager`）
- import 失败 → 12 个测试全部 error，无法运行
- CBIM 通过架构师确认模块归属，程序员在正确路径创建文件 → 12/12

---

## Token 与费用

| 指标 | Base | CBIM | 对比 |
|------|------|------|------|
| Sonnet input | 144.2k | 2.0k | — |
| Sonnet cache read | 9.3m | 6.9m | — |
| Sonnet cache write | 327.0k | 691.0k | — |
| Sonnet output | 155.5k | 100.4k | — |
| Opus input | — | 5.9k | — |
| Opus cache read | — | 1.4m | — |
| Opus cache write | — | 424.0k | — |
| Opus output | — | 39.4k | — |
| **总费用** | **$6.79** | **$10.54** | CBIM +55% |
| API 耗时 | 47m 3s | 49m 27s | 相近 |
| **墙钟时间** | **49m 50s** | **55m 47s** | CBIM +12% |
| 代码变更 | +2245 / -267 | +367 / -105 | Base 写了 6× 更多代码 |

---

## 观察与分析

### 通过率：46% vs 100%

差距主要来自两个维度：

**1. 文件归属判断（Task F，0 vs 12）**

最直接的架构治理信号。提示词只说"新建一个资源管控类"，没有指定路径：
- Base：自主判断 → `orchestration/resource-manager.ts`（语义上合理，但与测试期望不符）
- CBIM：架构师先确认模块归属 → `agent/agent-resource-manager.ts`（与测试完全匹配）

这 12 分的差距与实现能力无关，完全是"知道代码该放哪里"的差距。

**2. 实现完整度（Task D/E 局部失败）**

Base 在 Task D 漏实现了优先级排序逻辑（4 fail）和 getHistory 过滤/limit（3 fail），Task E 漏实现了优先级调度（2 fail）。CBIM 的架构师蓝图明确了接口契约，程序员逐项对照实现，覆盖率更完整。

### 代码量：+2245 vs +367

Base 写了约 6 倍的代码，但通过率更低。原因：
- Base 单 session 累积上下文，**触发了 Compacting**（Turn 7 附近）
- Compacting 导致部分早期设计细节丢失，后续 turn 重复探索、补丁式修改
- CBIM 每次任务用独立 subagent，上下文干净，实现精准，无冗余代码

### Compacting 不对称性

| | Base | CBIM |
|--|--|--|
| 触发 Compacting | 是（Turn 7） | 否 |
| 知识外化 | 无（全在对话上下文） | `.dna/` 文件持久化 |
| 压缩后知识恢复 | 不可恢复 | architect 可重读 `.dna/` |

Compacting 对 Base 的实质伤害：上下文压缩后，agent 遗忘了前几个 turn 的实现细节，导致 Task F 的接口约定（路径、类名）没能继承下来。

### 费用结构

CBIM 贵 $3.75，其中 Opus architect 贡献 $4.37——如果只算 Sonnet，CBIM 的 Sonnet 费用（$6.17）与 Base（$6.79）基本持平。Opus 是架构决策的固定成本，换来了 Task F 的 12 分和整体 100% 通过率。

---

## 汇总对比

| | Base | CBIM | 差值 |
|--|--|--|--|
| 通过率 | 18/39 (46%) | 39/39 (100%) | **+54pp** |
| 费用 | $6.79 | $10.54 | +$3.75 |
| 墙钟时间 | 49m 50s | 55m 47s | +6min |
| 代码变更 | +2245/-267 | +367/-105 | Base 6× 更多 |
| Compacting | 触发 | 未触发 | — |
| Task F 文件归属 | ❌ 路径错误 | ✅ 路径正确 | — |
