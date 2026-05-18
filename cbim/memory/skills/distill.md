# Skill: 记忆提炼（短期 → 中期）

**主 agent 专用。定期或按需触发。**

扫描短期记忆，按**能力关键字**和**业务关键字**压缩为中期记忆条目。

---

## 触发时机

| 频率 | 建议 |
|------|------|
| 每日 | 采集新 session 信号，压缩为中期条目 |
| 按需 | 用户主动触发 |

---

## 关键字规则

| 类型 | 来源 | 示例关键字 |
|------|------|----------|
| 能力关键字（capability） | 信号行中的 agent-id | `programmer`, `architect`, `hr` |
| 业务关键字（business） | frontmatter `modules` 字段 + "知识更新候选"信号中的模块名 | `combat`, `auth-module` |

---

## 步骤

**Step 1 — 扫描短期记忆**

读取 `memory/store/short/` 下近 N 天 entry 文件，提取：
- 「信号」区的每一条记录
- frontmatter `modules` 字段

**Step 2 — 按关键字分组并压缩**

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
（所有相关信号的压缩总结）

## 信号汇总
- 能力缺口 × 3: ...
- 优秀模式 × 2: ...
```

写入后更新索引：

```bash
.venv/bin/python -m memory.engine.cli add memory/store/medium/<file>.md --tier medium
```

**Step 3 — 清理已处理的短期 entry**

删除 3 天前的短期记忆（最近 3 天保留，供 session 连续性使用）：

```bash
.venv/bin/python -m memory.engine.cli cleanup --keep-days 3
```

**Step 4 — 输出提炼摘要**

向用户汇报本次提炼结果：

```
## 记忆提炼摘要（{日期范围}，{N} 条 entry）

### 能力信号（{N} 条）
- [agent-id] 信号类型：描述

### 内容信号（{N} 条）
- [模块名] 信号类型：描述
```

后续是否触发 HR 考核培训 / 架构师知识治理，由用户决定。
