SKILL: str = """\
# Skill: 写记忆（用户显式请求）

**主 agent 专用。** 当用户说"记下/记住/remember this/save this"等显式触发词时使用本技能。

memory v2 已废弃 short 层；所有写入直接进 **medium**。原"短期入站缓冲 → 蒸馏成 medium"两段式被合并成一段：用户一旦说"记一下"，就是希望这条信息长期保留，没有再走一层中间缓冲的必要。

绝不要把记忆写到 `~/.claude/projects/<project>/memory/`（Claude Code 自带的自动记忆在 CBIM 项目里已关；详见 CLAUDE.md 的 Memory Routing 节）。

---

## 触发词

只在用户**显式**说出以下任一短语时调用本技能：

- 中文：`记下` / `记住` / `记一下` / `备忘` / `保存记忆` / `存到记忆里`
- 英文：`remember this` / `save this` / `save to memory` / `note this down`

如果用户只是描述一个事实却没明确说"记一下"，**不要主动写**——等他明确开口再说。

---

## 自动入库渠道（与本技能无关，仅作背景）

memory v2 还有一个非用户触发的入库渠道：Stop hook 把 CC 整段 transcript 索引到 `engine.retrieval` 的 `transcript` 源；治理循环（dream tick）的记忆步在午夜窗口把过期 transcript 派给主 agent 用 `memory_distill` 技能蒸馏为 medium 条目，蒸馏成功后删除原 JSONL。

这条流水线全自动、不需要主 agent 在用户对话里主动触发。本技能只处理用户主动开口的那条路径。

---

## 写入流程（4 步）

1. **确认触发词**——见上文清单。模糊的描述不算，等用户明说。

2. **判定信号象限**——MUST / WANT / HOW / IS 四选一（见下文"四象限"）。如果一时分不清，先问一句澄清问题，再写。

3. **取一个 slug**——短横线分隔、≤30 字符、描述主题而非日期。例：`v2-phase1-start`、`combat-damage-formula`、`auth-token-policy`。

4. **写入 medium**——调 MCP 工具 `memory_create`：

   ```
   memory_create(slug="<slug>", content="<markdown 正文>", tier="medium")
   ```

   `tier` 参数缺省就是 `medium`；显式写出来便于审计。返回值是相对 `.cbim/memory/` 的路径，回一句给用户："Saved to <path>" 即可。

   CLI 等价命令（如果显式让你用 shell 写而不是 MCP）：

   ```bash
   cbim memory create --slug <slug> --tier medium --content "..."
   ```

   PowerShell 多行 here-doc：

   ```powershell
   cbim memory create --slug <slug> --tier medium --content @'
   ---
   tier: medium
   tags: decision
   ---

   ## 信号
   - [x] WANT: <module>: <决策> / <理由> / <代价>
   '@
   ```

---

## 条目格式

文件路径：`.cbim/memory/medium/YYYY-MM-DD-HHMMSS-manual-<slug>.md`

```markdown
---
tier: medium
tags: <decision | fact | rule | flow>     # 单个；按象限选
modules: combat pathfinding                # 可选；空格分隔，涉及的模块
---

## 标题（一句话说清这条记忆是什么）

## 信号
- [x] <QUADRANT>: <subject>: <内容>

## 背景 / 推理（可选）
为什么这条值得长期记。比"是什么"少花字、比"凭空写一行"多花一点点。
```

每条记忆**至少**含 1 个信号；多个信号同时出现说明本条偏粗——能拆就拆，不能拆就保留。

---

## 信号四象限（分类指南）

四象限不是装饰——它决定这条记忆未来会被蒸馏到哪里。

| 象限 | 类型 | 回答什么 | 跨项目 | 最终归宿 |
|------|------|----------|--------|----------|
| **MUST** | 准则 | 什么绝对不能违反？ | **是**——跨项目跨语言通用 | Agent soul / `.cbim/cbi/skills/` |
| **WANT** | 决策 | 为什么选这个方案？ | 否——当前项目的活权衡 | `.dna/module.md`（ADR 段） |
| **HOW** | 流程 | 这件事按什么步骤走？ | 看情况 | 跨项目→`.cbim/cbi/skills/`；项目内→`.dna/workflows/` |
| **IS** | 事实 | 现在它是什么？ | 否——可验证的系统事实 | `.dna/contract.md`（如果是协议边界）或 `module.md` |

---

## 各象限写法

### MUST — 绝对原则（跨项目）

记录 agent 必不能违反的约束或必须遵守的行为规范。

**典型触发：**
- 用户纠正了 agent 行为（人类纠正——最高优先级信号）
- Agent 的操作产生了不可逆后果（删除 / 覆写 / 外发）
- 发现 agent 越界了

**格式：** `MUST: <agent-id>: <内容>`

```
- [x] MUST: programmer: 批量删除前必须显示预计变更范围并取得确认
- [x] MUST: architect: 不得直接改代码，只产架构建议
- [x] MUST: all-agents: 遇到未定义术语必须先澄清，不得自行解释
```

### WANT — 项目决策（当前项目的权衡）

记录"为什么选 A 不选 B"——有理由、有承担的代价。

**典型触发：**
- 做了技术选型（框架 / 协议 / 存储）
- 定了服务边界 / 接口设计
- 做了一个偏离默认方案的取舍

**格式：** `WANT: <module-name or scope>: <决策>`

```
- [x] WANT: memory-module: 选 FileBackend 而非 ChromaDB；接受没有语义检索换零外部依赖
- [x] WANT: combat-module: 选 ECS 而非 OOP；接受开发复杂度换性能和组合性
- [x] WANT: auth-module: Token 用自包含 JWT 不进 Redis；接受没有主动吊销换无状态服务
```

### HOW — 流程模式（可能跨项目）

记录"这种事按什么步骤走有效"——已验证的执行方法。

**典型触发：**
- 某做法显著提升效率或减少错误
- 发现 agent 处理某类任务的固定模式
- 某流程在多次 session 里反复出现

**格式：** `HOW: <agent-id or module-name>: <流程>`

```
- [x] HOW: architect: 先 contract 后 architecture；接口稳定性更高
- [x] HOW: programmer: 新模块顺序：接口定义 → 单测 → 实现 → 集成测试
- [x] HOW: combat-module: 伤害计算流程：收输入 → 验证 → 算 → 广播，不得跳步
```

### IS — 当前事实（可验证的系统状态）

记录"它现在是什么"——接口 / 配置 / 规则的当前版本。

**典型触发：**
- 接口签名变了
- 业务规则定义变了（记下新旧两个值）
- 配置调了（限流 / 超时 / 阈值）
- 依赖版本变了

**格式：** `IS: <module-name>: <事实> (旧值 → 新值，若适用)`

```
- [x] IS: auth-module: Token 有效期 24h → 8h (2026-05-18)
- [x] IS: combat-module: 伤害计算接口签名改为 calculate(actor, target, context)
- [x] IS: api-gateway: 限流阈值 100 req/min（按 user_id）
- [x] IS: business-rule: "活跃用户"定义改了——旧：90 天内登录过；新：90 天内下过单
```

---

## 哪些信号最值得记

按重要性排序：

1. **用户纠正 agent 行为**（correction）—— 必记；落 MUST 或 HOW
2. **IS 类变更**（接口 / 规则 / 配置变了）—— 必记；防止下次按旧事实判断
3. **WANT 类决策**（有代价的选择）—— 必记；记下"为什么"
4. **MUST 类负面模式**（agent 做了不该做的）—— 必记
5. **HOW 类正面模式**（反复奏效的做法）—— 推荐记

**不值得记：**
- 中间推理步骤、临时计算
- 可即时再查的实时数据（天气、股价等）
- 一次性高度依赖上下文的细节（无泛化价值）
- 闲聊性内容

---

## 与 memory_distill 的关系

| 技能 | 触发方 | 输入 | 输出 |
|------|--------|------|------|
| `memory_write`（本） | 用户显式开口 | 一句话 / 一段决策 | 单条 medium 条目 |
| `memory_distill` | 治理循环派给主 agent | 过期的 transcript JSONL | 多条 medium 条目 |

两者落点相同（`.cbim/memory/medium/`），象限分类规则也共用同一套。本技能只处理人类主动开口的那条路径——transcript 自动蒸馏走 `memory_distill`，不要在本技能里去碰。

---
"""
