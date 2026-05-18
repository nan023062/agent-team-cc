# Skill: 记忆提炼（短期 → 中期）

**主 agent 专用。定期或按需触发。**

将短期 session 记录压缩为中期模式摘要，为 HR 能力治理和架构师业务治理提供原料。
中期记忆按**四象限**分类，每个象限决定信息最终流向哪个治理结构。

---

## 触发时机

| 场景 | 说明 |
|------|------|
| 用户主动要求 | "提炼一下记忆" / "整理最近的 session" |
| 积累阈值 | `store/short/` 出现 ≥5 条未提炼 entry 时主动建议 |
| 治理前置 | HR 考核 / 架构师治理前，先运行本 skill 确保中期记忆最新 |

---

## 前置：补全信号

Stop hook 自动写入的 entry，信号行默认为空。**提炼前必须先填写信号**（见 write.md 规范），否则无原料可提炼。

对每个待处理的 `store/short/*.md`，检查 `## 信号` 区，补全 `- [x]` 行。

---

## Step 1 — 扫描短期 entry，按象限分组

读取 `memory/store/short/` 下所有待提炼 entry，收集已勾选信号（`- [x]` 开头）。

按四象限分类：

| 象限 | 收集 key | 中期文件命名 |
|------|---------|------------|
| MUST | agent-id | `capability-<agent-id>.md` |
| HOW（能力向） | agent-id | `capability-<agent-id>.md` |
| WANT | 模块名 / 范围 | `decision-<scope>.md` |
| HOW（业务向） | 模块名 | `business-<module>.md` |
| IS | 模块名 | `business-<module>.md` |

> 判断 HOW 是能力向还是业务向：换到另一个项目仍然成立 → 能力向；强依赖当前业务上下文 → 业务向。

---

## Step 2 — 判断是否值得提炼

| 情形 | 处理方式 |
|------|---------|
| **用户纠正了 agent 的行为**（MUST） | **必须提炼**，最高优先级 |
| **IS 类变更**（接口、规则、配置） | **必须提炼**，防止后续决策基于过时事实 |
| **WANT 类决策** | **必须提炼**，记录"为什么"是架构知识的核心 |
| 同一 agent / 模块信号在多条 entry 中重复出现 | **必须提炼**，重复说明是规律不是偶然 |
| 单次出现，但描述明确的缺口或有效模式 | **建议提炼**，判断泛化价值 |
| 单次偶发，上下文极为特殊 | 可暂不提炼，保留在短期 |

**五个判断标准（用于边界情况）：**
1. 丢失代价：没有这条信息，未来决策会变差吗？
2. 泛化性：这是一次性细节，还是跨任务复用的原则？
3. 稳定性：有效期超过当前 session 吗？
4. 根因价值：能解释"为什么"而不只是"是什么"？
5. 防错价值：记录它能防止已发生过的错误再次发生吗？

---

## Step 3 — 写入或更新中期 entry

**若文件已存在 → 更新；若不存在 → 新建。**

### 能力类中期 entry（MUST + 能力向 HOW）

文件：`memory/store/medium/capability-<agent-id>.md`

```markdown
---
tier: medium
type: capability
keyword: programmer
updated: YYYY-MM-DD
sources: 5
---

## 摘要

对该 agent 当前能力模式的综合判断（一段话，每次更新时重写，不堆砌）。

示例：
programmer 在并发写入场景下缺乏主动加锁意识，需要用户提示才会处理竞争条件。
单线程顺序任务表现稳定，擅长拆解步骤和调用工具链。
已形成 dry-run 前置习惯，在过去 8 次写操作任务中零错误。

## MUST 记录（原则约束）

| 日期 | 来源 entry | 内容 | 触发原因 |
|------|-----------|------|---------|
| 2026-05-10 | 2026-05-10-main-xxx.md | 批量删除前必须展示变更范围 | 用户纠正了一次误删 |

## HOW 记录（有效流程）

| 日期 | 来源 entry | 内容 |
|------|-----------|------|
| 2026-05-12 | 2026-05-12-main-yyy.md | 先 contract 后 architecture，接口更稳定 |

## 治理建议

- [ ] 提炼为 Skill（HOW 模式出现 ≥3 次）
- [ ] 内化进 Soul（MUST 原则已验证稳定）
- [ ] 触发 HR 考核（能力缺口重复出现 ≥2 次）
```

### 决策类中期 entry（WANT）

文件：`memory/store/medium/decision-<scope>.md`

```markdown
---
tier: medium
type: decision
keyword: memory模块
updated: YYYY-MM-DD
sources: 2
---

## 决策记录

使用 ADR（Y-statement）格式：

### [决策标题]
在 [情境背景] 下，
面对 [核心约束]，
选择 [方案A] 而非 [方案B]，
以实现 [目标]，
接受 [权衡代价]。

示例：
在需要记忆检索的多 agent 系统中，
面对"零外部依赖"与"语义检索"的权衡，
选择 FileBackend（按时间排序）而非 ChromaDB（向量检索），
以实现安装即用、无网络依赖，
接受检索不支持语义相似度，仅按时间排序。

决策人：linan，日期：2026-05-18

## 治理建议

- [ ] 写入 `.dna/architecture.md`（决策已稳定，无需修改）
```

### 业务类中期 entry（业务向 HOW + IS）

文件：`memory/store/medium/business-<module>.md`

```markdown
---
tier: medium
type: business
keyword: combat
updated: YYYY-MM-DD
sources: 4
---

## 摘要

对该模块当前状态和关键模式的综合描述（每次更新重写，不堆砌）。

## IS 记录（当前事实）

| 日期 | 来源 entry | 内容 | 变更类型 |
|------|-----------|------|---------|
| 2026-05-15 | 2026-05-15-main-zzz.md | 伤害接口签名变更为 calculate(actor, target, context) | 接口变更 |
| 2026-05-10 | 2026-05-10-main-aaa.md | "活跃用户"定义：登录→购买 | 业务规则变更 |

## HOW 记录（业务流程）

| 日期 | 来源 entry | 内容 | 出现次数 |
|------|-----------|------|---------|
| 2026-05-12 | 2026-05-12-main-bbb.md | 伤害计算：接收→验证→计算→广播，不可跳步 | 3 |

## 治理建议

- [ ] IS 变更写入 `.dna/contract.md`（接口签名已更新）
- [ ] HOW 流程提炼为 `.dna/workflows/`（出现 ≥2 次）
- [ ] 通知架构师评审（有接口变更）
```

---

## Step 4 — 更新已有 entry 的规则

1. `## 信号记录` 表格末尾追加新行
2. `sources` 计数 + 新增 entry 数
3. `updated` 改为今天日期
4. **重新审视并改写 `## 摘要`**（反映最新信号，而不是追加堆砌）
5. 根据新增信号更新 `## 治理建议` 勾选状态

---

## Step 5 — 清理已处理的短期 entry

保留最近 3 天（供 session 连续性使用），删除更早的：

```bash
.venv/bin/python -m memory.engine.cli cleanup --keep-days 3
```

---

## Step 6 — 汇报并推荐后续动作

```
## 记忆提炼摘要（{日期范围}，{N} 条 entry）

### MUST（{N} 条原则）
| agent | 内容 | 触发原因 |
|-------|------|---------|
| programmer | 批量删除前需确认 | 用户纠正误删 |

### WANT（{N} 条决策）
| 范围 | 决策摘要 |
|------|---------|
| memory模块 | FileBackend vs ChromaDB，选零依赖 |

### HOW（{N} 条流程）
| 维度 | 内容 | 次数 |
|------|------|------|
| architect（能力） | 先 contract 后 architecture | 3 |
| combat（业务） | 伤害计算四步流程 | 2 |

### IS（{N} 条事实变更）
| 模块 | 变更 |
|------|------|
| combat | 接口签名更新 |
| auth | token 有效期 24h→8h |

### 建议后续动作
能力治理：
- HR 考核 programmer（MUST 缺口 × 2 次）
- HR 提炼 architect HOW 为 Skill（出现 × 3 次）

业务治理：
- 架构师更新 combat contract.md（接口签名变更）
- 架构师提炼 combat HOW 为 workflow（× 2 次）
- 架构师记录 memory模块 WANT 决策到 architecture.md
```

提炼完成后是否触发 HR 考核 / 架构师治理，由用户决定。
