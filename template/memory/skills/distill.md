# Skill: 记忆提炼（短期 → 中期）

**主 agent 专用。定期或按需触发。**

扫描短期记忆，按**能力关键字**和**内容关键字**压缩为中期记忆条目。

---

## 触发时机

| 频率 | 建议 |
|------|------|
| 每日 | 采集信号，判断是否需要更新中期条目 |
| 每周 | 全量提炼，驱动 HR / 架构师执行升格 |
| 按需 | 用户主动触发，或感知到 agent / 模块质量下滑时 |

---

## 关键字规则

| 类型 | 来源 | 示例关键字 |
|------|------|----------|
| 能力关键字（capability） | 信号行中的 agent-id | `programmer`, `architect`, `hr` |
| 内容关键字（content） | frontmatter `modules` 字段 + "知识更新候选"信号中的模块名 | `combat`, `auth-module` |

---

## 步骤

**Step 1 — 扫描短期记忆**

读取 `memory/store/short/` 下全部（或近 N 天）entry 文件：
- 提取每个 entry 的「信号」区
- 提取 frontmatter `modules` 字段

**Step 2 — 提取关键字并分组**

```
能力关键字（按 agent-id 分组）
  - programmer: 缺口 × N，优秀模式 × M
  - architect:  缺口 × N，优秀模式 × M

内容关键字（按模块名分组）
  - combat:     知识更新候选 × N
  - auth:       知识更新候选 × N
```

**Step 3 — 压缩写入中期 entry**

对每个关键字，生成或更新 `memory/store/medium/<type>-<keyword>.md`：

```markdown
---
tier: medium
type: capability
keyword: programmer
updated: YYYY-MM-DD
sources: 12
---

## 摘要
（LLM 对所有相关信号的压缩总结）

## 信号汇总
- 能力缺口 × 3: ...
- 优秀模式 × 2: ...
```

写入后立即更新索引：

```bash
.venv/bin/python -m memory.engine.cli add memory/store/medium/<file>.md --tier medium
```

**Step 4 — 输出提炼摘要并决定后续行动**

```
## 记忆提炼摘要（{日期范围}，{N} 条 entry）

### 能力信号
- [agent-id] 信号类型：描述

### 内容信号
- [模块名] 信号类型：描述

### 建议后续行动
- 能力升格：派发 HR，执行 assessment / training skill
- 知识治理：派发架构师，执行 knowledge-governance skill
```

主 agent 根据摘要决定是否触发 HR 或架构师。
