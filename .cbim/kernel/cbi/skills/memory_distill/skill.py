SKILL: str = """\
# Skill: Memory Distillation (Transcript → Medium)

**只由主 agent 调用。** 输入是 Claude Code 原生会话 JSONL；输出是 `.cbim/memory/medium/` 下的四象限条目。

蒸馏只产出分析素材；是否触发后续治理（HR 评估 / architect 知识更新）由治理循环或用户决定，本 skill 不负责。

---

## 触发场景

| 场景 | 说明 |
|------|------|
| 用户显式请求 | "整理记忆" / "蒸馏最近 session" / "distill" |
| 阈值提示 | 主 agent 注意到 transcript 积累过多，主动建议 |
| 治理循环 yield | `dream_tick` 的 `DispatchMemDistill` 节点 yield 给主 agent，prompt 里会列出 `paths` |

---

## 步骤 1 — 定位 transcript 目录

Claude Code 把每次 session 的对话流写在 `~/.claude/projects/<slug>/<session-id>.jsonl`。

**slug 规则**：当前项目 CWD 中 `:` → `-`，`\\` 或 `/` → `-`，其余字符保留。

示例：

| CWD | slug |
|-----|------|
| `D:\\GitRepository\\cbim-kernel` | `D--GitRepository-cbim-kernel` |
| `/home/linan/proj` | `-home-linan-proj` |

拼接 home 目录跨平台脚本（Bash 工具）：

```bash
# Linux / macOS
echo "$HOME/.claude/projects/<slug>/"
# Windows (PowerShell)
echo "$env:USERPROFILE\\.claude\\projects\\<slug>\\"
```

---

## 步骤 2 — 选出待蒸馏的 JSONL

两种入口，路径来源不同：

| 调用来源 | 路径列表来源 |
|---------|------------|
| 治理循环 yield | prompt 里已带 `paths` 字段（mtime > 1 天的 transcript）——**直接用，不要重扫** |
| 用户手动触发 | 主 agent 用 Glob 自扫 `~/.claude/projects/<slug>/*.jsonl`，**全部纳入**（含近期） |

不论哪种来源，跳过明显无意义的文件（大小 < 2KB 视作 too-short）。

---

## 步骤 3 — 读取并理解 transcript 内容

每个 `.jsonl` 是一次 session 的逐行 JSON 记录（用户轮、助手轮、tool calls、tool results）。

用 `Read` 工具逐文件读取，按行解析。重点关注：

- **用户消息**——尤其是纠正、要求改变行为、明确决策的语句
- **subagent 执行结果**——成功模式、踩坑点
- **文件改动记录**——接口签名、契约、配置变化
- **决策语句**——"我们选 A 不选 B 因为 ..."

> v2 不再依赖任何 `- [x]` 预选信号。主 agent 直接读原文推断。

---

## 步骤 4 — 提炼 MUST / WANT / HOW / IS 四象限

| 象限 | 含义 | 收集键 | 归属 medium 文件 |
|------|------|--------|-----------------|
| MUST | 行为约束（用户纠正、必须遵守） | agent-id | `capability-<agent-id>.md` |
| HOW（能力向） | 跨项目仍成立的有效流程 | agent-id | `capability-<agent-id>.md` |
| WANT | 业务决策（为什么选 A 不选 B） | 模块名 / scope | `decision-<scope>.md` |
| HOW（业务向） | 强绑当前业务的流程 | 模块名 | `business-<module>.md` |
| IS | 事实 / 接口 / 规则变更 | 模块名 | `business-<module>.md` |

**HOW 归属判断**：换个项目还成立 → 能力向；强依赖当前业务上下文 → 业务向。

**判断该不该蒸馏（borderline 时的五条标尺）**：

1. 丢失代价：将来决策会不会因为没有这条而变差？
2. 普适性：是一次性细节还是跨任务可复用？
3. 稳定性：超出当前 session 还成立吗？
4. 根因价值：解释了 "why" 而不只是 "what" 吗？
5. 防错价值：记下能防止过去那个错重现吗？

任何一条强 yes → 蒸馏。

---

## 步骤 5 — 写入 medium 条目

调 `memory_create` MCP 工具，`tier="medium"`（v2 记忆服务不再接受 `short`）。**文件已存在则更新；不存在则创建。**

### 能力 medium 条目（MUST + 能力向 HOW）

文件：`capability-<agent-id>.md`

```markdown
---
tier: medium
type: capability
keyword: programmer
updated: YYYY-MM-DD
sources: 5
---

## Summary

对该 agent 当前能力模式的整体判断（一段话，每次更新重写、不追加）。

## MUST 记录（行为约束）

| 日期 | 来源 transcript | 内容 | 触发原因 |
|------|----------------|------|---------|
| 2026-05-10 | <session-id>.jsonl | 批量删除前必须先展示影响范围 | 用户纠正了一次误删 |

## HOW 记录（有效流程）

| 日期 | 来源 transcript | 内容 |
|------|----------------|------|
| 2026-05-12 | <session-id>.jsonl | 先契约后架构，接口更稳 |
```

### 决策 medium 条目（WANT）

文件：`decision-<scope>.md`

```markdown
---
tier: medium
type: decision
keyword: memory-module
updated: YYYY-MM-DD
sources: 2
---

## 决策记录

ADR (Y-statement) 格式：

### [决策标题]
在 [背景] 下，
面对 [核心约束]，
我们选择 [方案 A] 而非 [方案 B]，
以达成 [目标]，
接受 [代价]。

决策人：linan，日期：2026-05-18
```

### 业务 medium 条目（业务向 HOW + IS）

文件：`business-<module>.md`

```markdown
---
tier: medium
type: business
keyword: combat
updated: YYYY-MM-DD
sources: 4
---

## Summary

模块当前状态与关键模式的整体描述（每次更新重写）。

## IS 记录（当前事实）

| 日期 | 来源 transcript | 内容 | 变更类型 |
|------|----------------|------|---------|
| 2026-05-15 | <session-id>.jsonl | Damage 接口签名改为 calculate(actor, target, context) | 接口变更 |

## HOW 记录（业务流程）

| 日期 | 来源 transcript | 内容 | 次数 |
|------|----------------|------|------|
| 2026-05-12 | <session-id>.jsonl | 伤害结算：接收 → 校验 → 计算 → 广播，不能跳步 | 3 |
```

---

## 步骤 6 — 更新已有 medium 条目的规则

1. 把新行追加到对应的记录表
2. `sources` 加上新来源数量
3. `updated` 改为今天
4. **重写 `## Summary`** 以反映最新信号——不要追加堆积

---

## 步骤 7 — 不要碰 transcript 原文件

主 agent **不删** transcript、**不改** transcript、**不加** 任何标记。

删除是治理循环 `TranscriptDelete` 节点的职责，它依赖本 skill 报告里的 `distilled_paths`。
用户手动触发（非治理循环）时不删 transcript，只回报蒸馏结果。

---

## 步骤 8 — 回报蒸馏摘要

返回给调用方（治理循环用 `dream_tick_resume` 的 `dispatch_result`；用户手动调用直接回报）的 JSON：

```json
{
  "distilled_paths":          ["<absolute path>", ...],
  "medium_entries_written":   ["<absolute path>", ...],
  "skipped_paths":            [{"path": "...", "reason": "no-signal|too-short|parse-error"}],
  "errors":                   ["..."]
}
```

同时给用户一段人话摘要：

```
## 蒸馏摘要（{N} 个 transcript）

### MUST（{N} 条原则）
| Agent | 内容 | 触发原因 |
|-------|------|---------|
| programmer | 批量删除前先确认 | 用户纠正误删 |

### WANT（{N} 条决策）
| Scope | 决策摘要 |
|-------|---------|
| memory-module | FileBackend vs ChromaDB，选零依赖 |

### HOW（{N} 条流程）
| 维度 | 内容 | 次数 |
|------|------|------|
| architect（能力） | 先契约后架构 | 3 |
| combat（业务） | 伤害结算四步流程 | 2 |

### IS（{N} 条事实变更）
| 模块 | 变更 |
|------|------|
| combat | 接口签名更新 |

### 跳过
- <path>：too-short
```

后续治理动作（HR 评估 / architect 更新知识）由用户或治理循环决定，本 skill 到此为止。
"""
