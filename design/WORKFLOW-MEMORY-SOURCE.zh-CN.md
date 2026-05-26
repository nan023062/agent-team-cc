# Memory 子系统原料源切换 — 设计蓝图

> 关联文档：[`WORKFLOW-MEMORY.zh-CN.md`](./WORKFLOW-MEMORY.zh-CN.md)（现行记忆双子循环）、[`WORKFLOW-DREAM.zh-CN.md`](./WORKFLOW-DREAM.zh-CN.md)（治理根，distill 在此被拉起）。
>
> 本文件只产蓝图，不动代码、不动 `.dna/`。蓝图落地后由 programmer 按"实施切片"分批改造。

---

## 0. 一句话定位

**Stop hook 不再被动地把会话摘要灌进 `.cbim/memory/short/`；`memory_distill` 改为主动地把 Claude Code 自带的 session JSONL 当作原料源**。`short/` 的语义由"自动落盘的会话流水"收窄为"用户手动 `memory_write` 的备忘"。Medium / candidates / index 保持不动。

---

## 1. 翻转前后对比

| 维度 | 翻转前（旧） | 翻转后（新） |
|------|------------|------------|
| 原料从哪里来 | Stop hook 在每次会话结束时把摘要写进 `short/YYYY-MM-DD-session-*.md` | distill 主动去 `~/.claude/projects/<slug>/*.jsonl` 拉原始转录 |
| `short/` 写入者 | Stop hook（自动）+ memory_write（手动） | 仅 memory_write（手动）——"记下"/"备忘"专属 |
| Distill 输入 | `short/` 的 N 条摘要 | session JSONL（主线 + 子 agent）的原始转录 |
| Distill 输出 | `medium/`（不变） | `medium/`（不变） |
| 增量边界 | 时间窗（近 N 天 short） | 已 distill 过的 session uuid 集合 |
| 子 agent 视角 | 不可见（hook 只看到主线） | 可见（`subagents/agent-*.jsonl` 同被纳入） |
| 数据真实度 | 二次抽样（hook 自己造摘要） | 原始转录（用户原话 + 工具调用） |

**核心收益**：原料从"hook 自己生成的二手货"换成"Claude Code 自己持久化的一手转录"，distill 看到的是真实对话流，包括 NEEDS_ARCH_DECISION、用户反悔、API 断线等高价值信号；同时把 hook 的写盘逻辑彻底退役，减少同步竞争面。

---

## 2. 关键决策（逐项配反例）

### D1 — JSONL 解析层归属：新建 `memory/jsonl_source/` 子模块

**选项**：(a) 新建 `memory/jsonl_source/` 子模块；(b) 塞进 `memory/compaction/`；(c) 放在 `memory/crud/`。

**决策**：(a) 新建 `memory/jsonl_source/`，作为 `kernel/memory` 的第三个 leaf 子模块。

**理由**：JSONL 是 Claude Code 的实现细节，不是 Anthropic 公开稳定契约——任何升级都可能改字段名、改文件位置、改子 agent 分目录规则。**破坏面必须被一个 adapter 模块吸收**，由它统一翻译为内部的 `RawSessionRecord`/`RawTurn` 中性数据结构。`compaction/` 和 `crud/` 不应感知任何 `~/.claude/projects/...` 的路径形状。

**为什么不是 (b)**：`compaction/` 的职责是"识别候选 + 压缩升级"，它消费 distill 的输入，不应该既负责"取原料"又负责"压原料"。两件事的稳定性周期完全不同——JSONL schema 一年变三次，compaction 算法可以稳半年。塞一起会让 compaction 跟着 Claude Code 升级一起抖。

**为什么不是 (c)**：`crud/` 的职责是"对 `.cbim/memory/` 的落盘原语"。JSONL 在 `~/.claude/projects/` 不在 `.cbim/`，从存储边界上就不是 crud 的事。强行塞进去会污染 crud 的"被动数据层"定位。

**职责清单**（jsonl_source 子模块内）：
- 项目 slug 推导（见 D2）
- 主线 session JSONL 路径枚举与读取
- 子 agent JSONL 路径枚举与读取
- JSONL 行解析（容错：跳过坏行、未知 schema 字段宽容）
- 合并视角下的 `RawSessionRecord` 装配（见 D4）
- **不**持有任何 distill 算法，**不**写 `.cbim/memory/`

**契约面**：对内（`compaction/distill` 调用）暴露两个函数级接口：
- `list_pending_sessions() -> [session_uuid, ...]` —— 列出"存在 jsonl 但未在 distilled_sessions 中"的会话
- `read_session(session_uuid) -> RawSessionRecord` —— 取一份合并视角的原料

---

### D2 — slug 推导归属：jsonl_source 独占

**选项**：(a) jsonl_source 独占；(b) 提为 hook + memory 共享的小工具（如 `kernel/_primitives/cc_paths.py`）；(c) 复刻两份。

**决策**：(a) 由 `jsonl_source/` 独占。

**理由**：翻转后 hook 不再需要知道 slug——stop hook 进入 no-op 或仅排队 session uuid（见 D5）。slug 只有 distill 这条链路用得到，独占即可，不必抽公共。

**为什么不是 (b)**：抽到 `_primitives/` 等于承认"hook 也要用"，但翻转后 hook 已经不写 `short/`。提前做共享抽象违反 YAGNI，反而把 jsonl_source 的破坏面外溢到 primitives 层。

**为什么不是 (c)**：两份复刻是 anti-pattern，slug 推导一旦不一致就会"hook 看到的 session 和 distill 找到的 session 对不上"。直接拒绝。

**实现要点（不展开行号）**：
- 输入：项目绝对路径（distill 启动时已知，等价 `cwd`）
- 算法：把 `/` 替换为 `-`，前置 `-`；忽略尾部 `/`
- 边界：路径包含 `.` / 空格时与 Claude Code 实现保持一致——programmer 落地前需用真实样本对齐一次

---

### D3 — 增量状态指针：新文件 `.cbim/memory/jsonl_state.json`

**选项**：(a) 复用 `candidates/distilled_sessions.json`；(b) 在 `index.md` 扩字段；(c) 新文件 `.cbim/memory/jsonl_state.json`。

**决策**：(c) 新建 `.cbim/memory/jsonl_state.json`，归 `jsonl_source/` 子模块独占。

**结构（示意）**：
```
{
  "schema_version": 1,
  "main": {
    "<session_uuid>": {"distilled_at": "ISO-8601", "byte_offset": 12345, "last_seen_size": 67890}
  },
  "subagents": {
    "<session_uuid>/<agent_id>": {"distilled_at": "...", "byte_offset": ..., "last_seen_size": ...}
  }
}
```

`byte_offset` 字段为未来"同一 session 多次增量 distill"留口子；首版可只用 `distilled_at` 存在性判断。

**为什么不是 (a)**：`candidates/` 是 `compaction/` 独占的工作区（见现行 `memory/compaction/.dna/module.md` 的 G3 决议）。把 "session 已 distill" 这种**来源侧的水位线**塞进 `candidates/` 会把两个子模块的关注点搅一起——compaction 不应该需要知道 jsonl 这个概念存在。

**为什么不是 (b)**：`index.md` 的稳定性等级是公共契约级别，扩"已 distill 会话"字段会让契约面跟着 Claude Code 抖。同时 index.md 设计为"条目索引"，加 session-级别指针在语义上错位。

**与现行子模块边界的兼容**：`jsonl_state.json` 与 `candidates/` 路径独立，物理隔离；读写权限归 `jsonl_source/`，`compaction/` 通过函数接口拿"待 distill 列表"，看不到这个文件的存在。

---

### D4 — 子 agent 转录纳入策略：合并视角 + 优先级加权

**选项**：(a) 不纳入；(b) 独立 distill（子 agent 单独一条 medium）；(c) 合并到主线 session 的视角。

**决策**：(c) **合并视角**——一份 `RawSessionRecord` 同时携带主线轮次与子 agent 转录；子 agent 出现的高价值信号（`NEEDS_ARCH_DECISION:`、用户拒绝、API 断线、tool error）享受**优先权重**，distill prompt 显式要求"先抽这些信号，再补 happy-path 摘要"。

**理由**：主线只能看到子 agent 的最终 result 字符串，丢失了过程中的纠正与升级信号。独立 distill 又会让同一件事被记两遍（主线 happy-path 摘要 + 子 agent 完整转录），互相重复且时间线对不上。合并视角是唯一保留时间因果、又不重复的方式。

**为什么不是 (a)**：直接丢掉 NEEDS_ARCH_DECISION / 用户纠正信号，这些恰是 distill 最该抓的东西，浪费原料。

**为什么不是 (b)**：会出现一段对话两份 medium 条目，distill 后期合并复杂度爆炸；且 distilled_sessions 指针要按"(session_uuid, agent_id)"组合存，状态空间膨胀且容易出现"主线已 distill / 某子 agent 未 distill"的卡死态。

**合并算法（蓝图层面，不展开实现）**：
1. jsonl_source 读主线 jsonl 得 `MainTurn[]`
2. 扫描同目录下 `<session_uuid>/subagents/agent-*.jsonl`，每份得 `SubTurn[]`
3. 按时间戳归并成单个时间线
4. 子 agent 转录段标记 `source="subagent:<agent_id>"`，主线段标记 `source="main"`
5. 抽信号阶段对 `source="subagent:*"` 的轮次做关键字扫描（NEEDS_ARCH_DECISION / 用户拒绝模式 / tool error），命中则在 distill prompt 中加 `[HIGH-SIGNAL]` 前缀

---

### D5 — Stop hook 新职责：(b) 排队 session uuid 待 distill

**选项**：(a) 完全 no-op；(b) 只追加当前 session uuid 到待 distill 队列；(c) 改名/退役 hook。

**决策**：(b) Stop hook 退化为**最小职责的状态追加**——在 `.cbim/memory/jsonl_state.json` 的 main 桶里登记一条 `{"<session_uuid>": {"distilled_at": null, "noticed_at": "ISO-8601"}}` 占位。

**理由**：
- 完全 no-op 意味着 distill 必须每次扫描整个 `~/.claude/projects/<slug>/` 目录，I/O 重复且要靠 mtime 比对——脆弱。
- 排队 session uuid 把"会话发生过"的事实在最准确的时点（stop 瞬间）记一笔，distill 端只需要做集合差。
- 改名/退役会让 hook 与 distill 之间多一层接口失约面；保留 hook 文件但收窄职责更平滑。

**为什么不是 (a)**：distill 端反推 session uuid 需要枚举目录、解析文件名、与 active session 区分，复杂度高且易漏（如多设备同步、Claude Code 升级目录布局）。Stop hook 用"刚刚结束的会话"作为权威信号最准。

**为什么不是 (c)**：hook 文件的存在也是契约的一部分。`.claude/settings.local.json` 注册了它，外部工具（dashboard / audit）可能扫描 hook 清单。改名/删除属于破坏性变更，没必要。

**Hook 退化后的写权限**：hook 通过 in-process 导入 kernel 写 `.cbim/memory/jsonl_state.json`，**不**再写 `short/`。`session_writer.py` 的"自动落 short"路径整段废弃。

---

### D6 — SessionStart hook 注入源：medium top-K + 最近一次 distill 摘要

**选项**：(a) 切到 medium top-K；(b) 切到"最近一次 distill 的输出 digest"；(c) 不再 inject，交给 snapshot。

**决策**：**(a) + (b) 组合**——SessionStart 注入两段：
- 段 1：**medium 的 top-K**（K=5 起，可配），按相关性或最近性，与现行 short 注入相同的体感
- 段 2：**最近一次 distill 的产出 digest**（一行：`今日 distill 处理 N 个 session，新增 M 条 medium，主题：[topic1, topic2, ...]`）

**理由**：用户翻新 session 时最关心两件事——"我们之前到底沉淀了什么"（medium top-K）和"上次自动整理后变了什么"（distill digest）。short 不再自动写后，单独注入"用户手动备忘"价值不高（用户自己写的他自己记得）。

**为什么不是 (c)**：snapshot 是 dashboard 视角，不在 SessionStart 上下文里出现；让用户每次新会话都要去看 snapshot 等于打回"用户自己找记忆"，违背记忆系统的存在价值。

**注入源切换的接口面**：`cbim_load_memory.py` 改为调 `memory_query(filter=tier:medium, sort=recency, limit=K)` 与 `memory_stats(filter=last_distill_summary)`。**不**新增 MCP 工具，**复用** `query` + `stats` 现有契约。

---

### D7 — MemHealthScan 重定义：双指标 + 阈值改名

**选项**：(a) 仅"未 distill session 数 ≥ N"；(b) 仅"未 distill jsonl 总字节 ≥ M"；(c) 两者都监控。

**决策**：(c) 两者并存，触发条件 `OR`：
- `UNDISTILLED_SESSIONS ≥ N`（默认 N=20）—— 防止长时间不开 Claude Code 后积压
- `UNDISTILLED_BYTES ≥ M`（默认 M=2 MiB）—— 防止单 session 过长（如连续 8 小时排错）

**理由**：单一阈值都有盲点。session 数防"积量"，字节数防"积重"。两者 OR 触发，确保任一维度异常都能被发现；阈值都进 `stats()` 输出，audit 自取。

**旧阈值 `SHORT_OVERFLOW` 重命名为 `MANUAL_NOTES_OVERFLOW`**，含义收窄为"用户手动备忘条目过多"（默认 200 条），独立报。

**为什么不是 (a) 或 (b)**：单指标都会被另一维的极端绕过。例：一个用户每天开一次 Claude Code 但每次 6 小时，session 数永远低于 20，但 jsonl 字节早爆。

---

### D8 — 查询面：默认包含 medium；不新增 `query_sessions`

**选项**：(a) `query/scan/get` 默认包含 medium（手动 short + medium）；(b) 新增 `query_sessions(filter)` 直读 jsonl；(c) 让 medium 蒸馏产物本身就是查询面。

**决策**：(a) + (c) 组合——`query/scan/get` 默认查 `manual_short + medium`，**不**新增 `query_sessions`。jsonl 不是查询面，只是原料源。

**理由**：契约级别的对外接口稳定性优先（见 `memory/contract.md` "稳定优先" 硬约束）。让 jsonl 出现在对外查询面意味着把 Claude Code 私有 schema 泄漏到契约，违反 D1 的破坏面隔离原则。jsonl 的全部价值由 distill 转换为 medium 后被查询面消费。

**为什么不是 (b)**：新增 `query_sessions` 会让上层养成"绕过 medium 直接捞原料"的习惯，distill 失去存在意义。同时引入对 `~/.claude/projects/` 的对外接口依赖，跨平台/跨用户场景（多机同步、容器化）立刻崩。

**为什么不是 (c) 单独**：medium top-K 解决"语义查询"，但用户偶尔需要查自己手动备忘（`memory_write` 写的），所以 manual_short 必须也在默认查询面里。

**`scan(filter=...)` 现有过滤维度保持不变**；新增过滤位：`source ∈ {"manual", "distilled"}`，区分手动条目 vs distill 产物。

---

### D9 — 老 105 条 short 的删除：蓝图独立、立刻删

**选项**：(a) 一次性 `cbim memory cleanup --keep-days 0`；(b) 蓝图落地后写迁移脚本；(c) 立刻就删（蓝图独立）。

**决策**：(c) **立刻删，与蓝图实施解耦**。

**理由**：用户已明确"已 distill 一轮 medium，老 short 已落 11 条 medium，信息可恢复"。立刻删的两点好处：
1. 避免 distill 路径切换期间，旧 short 与新 jsonl 原料"双源对账"的复杂度
2. 让健康巡检的基线干净，第一次跑新阈值就是真实读数

**为什么不是 (a)**：CLI 方式与立刻删无差异，本质都是删；但走 CLI 路径要先验证 `--keep-days 0` 是否覆盖所有 105 条（含未来 7 天的 mtime），徒增风险。

**为什么不是 (b)**：迁移脚本是过度工程——既然信息已在 medium 里，没什么"迁"的，"清"就行。脚本反而留一层维护负担。

**执行方式**：由 architect 在治理 tick 中走 `memory_*` MCP 删除工具（如尚无批删工具，作为 advice_pending 让 assistant 派 programmer 加一个 `memory_purge_short_auto` 一次性命令）。本设计不规定具体命令名。

---

### D10 — 影响清单

| 文件 / 模块 | 动作 | 理由 |
|------------|------|------|
| `.claude/hooks/cbim_stop.py`（即 `cbim_write_memory` 等价物） | **改** | 退化为"仅排队 session uuid 到 jsonl_state.json"；删除自动写 short 的整段逻辑 |
| `.claude/hooks/cbim_session_start.py`（即 `cbim_load_memory`） | **改** | 注入源从近期 short 切到 medium top-K + 最近 distill digest（D6） |
| `v1/kernel/memory/session_loader.py` | **删** | 旧的"会话→short"加载器，新流程不再走这条路径；如有外部引用先标 deprecated 再删 |
| `v1/kernel/memory/crud/session_writer.py` | **删** | 仅服务于 hook 的自动写 short；hook 退化后无调用方 |
| `v1/kernel/memory/_facade.py` | **改** | 暴露 `list_pending_sessions` / `read_session` 给 distill；增加 `manual_short + medium` 默认查询合并逻辑；移除 session_writer 相关入口 |
| `v1/kernel/memory/compaction/identifier.py` | **不动** | identify 仍然是 write 一体两步的第 2 步；与 jsonl 原料无关 |
| `v1/kernel/memory/compaction/compactor.py` | **改** | distill 主流程改从 `jsonl_source.list_pending_sessions()` 取输入；distill 完成后更新 `jsonl_state.json` |
| `v1/kernel/memory/compaction/health.py` | **改** | 新增 `UNDISTILLED_SESSIONS` / `UNDISTILLED_BYTES` 双指标；保留 `MANUAL_NOTES_OVERFLOW`（原 SHORT_OVERFLOW 改名） |
| `v1/kernel/memory/jsonl_source/`（新建子模块） | **新** | 详见 D1；含 paths.py / reader.py / merger.py / state.py 等 leaf 文件（具体由 programmer 切） |
| `v1/kernel/cbi/skills/memory_*.md` 中的 `memory_distill` skill | **改** | skill 文档要说明新原料源是 jsonl，不再是 short；写一段"distill 是 jsonl→medium 的提炼" |
| `v1/kernel/cbi/skills/memory_*.md` 中的 `memory_write` skill | **改** | 强调写入路径只剩"手动"语义；short 不再有自动条目 |
| `v1/kernel/engine/dream/actions/dispatch_mem_distill.py` | **不动** | 分发逻辑不变，只是被分发的 distill 内部换了原料源 |
| `v1/kernel/engine/audit/`（含 MemHealthScan check） | **改** | 阈值名同步：`SHORT_OVERFLOW` → `MANUAL_NOTES_OVERFLOW`；新增 `UNDISTILLED_*` 两条 |
| `v1/kernel/memory/.dna/module.md` | **改** | "Sub-module Relationships" Mermaid 图加入 `jsonl_source`；"Key Decisions" 加一条"jsonl 是原料源、不是查询面" |
| `v1/kernel/memory/.dna/contract.md` | **改** | `scan` 过滤位增 `source ∈ {manual, distilled}`；其余 4 接口签名不变 |
| `v1/kernel/memory/compaction/.dna/module.md` | **改** | 关键决策加一条"distill 输入由 `jsonl_source` 提供，不直读 `short/`" |
| `v1/kernel/memory/crud/.dna/module.md` | **改** | 删除 `session_writer` 相关描述（如有） |
| `v1/kernel/memory/jsonl_source/.dna/module.md` | **新** | 新子模块的 module.md + contract.md（leaf） |
| MCP 工具集 `memory_*` | **不新增** | 复用 query/scan/get/stats；distill 内部直接调 jsonl_source（不暴露到 MCP 面）。**例外**：删 105 条 short 若需 `memory_purge_short_auto` 一次性命令，单独评估（见 D9） |
| `.claude/hooks/cbim_session_end.py` | **不动** | 与原料源无关 |
| `.claude/hooks/cbim_user_prompt_submit.py` / `cbim_pre_tool_use.py` / `cbim_post_tool_use.py` / `cbim_auto_preview.py` | **不动** | 与本翻转无关 |

---

## 3. 读取权限边界（重要）

JSONL 在 `~/.claude/projects/` 不在 `.cbim/`：

- **Hook（in-process）**：天然可读 home dir，无权限问题。
- **MCP 工具入口**：MCP server 进程的工作目录是项目根，**默认不读 home dir**。Distill 这条路径上的 MCP 工具（如有）需要明确允许：
  - 方案 1（推荐）：distill 不通过 MCP 工具触发，由 dream tick 内部直接调 kernel 函数（dispatch_mem_distill.py 已经是这条路径），jsonl_source 在 kernel 进程内运行，**无需新 MCP 工具**。
  - 方案 2（不推荐）：如果未来要让 LLM 显式触发 distill，再新增 `memory_distill_now` MCP 工具，并在工具 docstring 明确"读 `~/.claude/projects/<slug>/`"。本蓝图不引入此工具。
- **CLI（`cbim memory distill`）**：用户在自己 shell 里跑，天然有 home dir 权限，无问题。

结论：**本翻转不引入新 MCP 工具**，权限边界天然清晰。

---

## 4. 失败语义与降级

| 失败场景 | 行为 |
|---------|------|
| `~/.claude/projects/<slug>/` 不存在（首次安装 / 路径变化） | jsonl_source 返回空列表，distill 跳过；健康巡检报"无原料源"提示 |
| 单个 jsonl 文件读到一半坏行 | reader 跳过坏行继续；distill 用已读部分；日志登记被跳行数 |
| `jsonl_state.json` 损坏 / 不存在 | 视作空集合，下次 distill 把所有 session 当作未 distill 重跑一次；medium 端要靠 dedupe 防重复（已是 compaction 现有能力） |
| Hook 写 `jsonl_state.json` 时锁冲突（多会话并发） | atomic rename + retry（与 crud 现有原子写一致） |
| 子 agent jsonl 与主 session jsonl 时间戳错乱 | 合并器以子 agent jsonl 的轮次为权威，主线只看到的 result 字符串作为对齐锚点 |

---

## 5. 实施切片（提交颗粒度）

按以下 commit 顺序提交，每个 commit 都可独立测试、独立回滚。

| # | Commit 标题（建议） | 范围 | 验收 |
|---|--------------------|------|------|
| 1 | `chore(memory): purge legacy auto-written short entries` | 立刻删 105 条老 short（D9） | `short/` 只剩用户手动条目 |
| 2 | `feat(memory): add jsonl_source submodule scaffold` | 新建 `memory/jsonl_source/` 子模块（D1）；含 `.dna/module.md` + `.dna/contract.md`；含 paths / reader 空实现 | dna_list 看到新模块；import 可通过 |
| 3 | `feat(jsonl_source): implement slug + reader + merger` | D2 + D4 实现 | 单元测试：给一份样本 jsonl 能解出 RawSessionRecord，含子 agent 合并 |
| 4 | `feat(memory): add jsonl_state.json + pending list api` | D3 实现；jsonl_source 暴露 list_pending_sessions / read_session | 测试：state 文件 atomic 写入；pending 列表正确 |
| 5 | `refactor(hooks): retire auto-write short, append session uuid to jsonl_state` | D5 实现；cbim_stop.py 退化；session_writer.py 标 deprecated | 跑一次 session，jsonl_state 出现新条目，`short/` 无新文件 |
| 6 | `refactor(memory): switch distill input from short to jsonl_source` | compaction/compactor.py 改输入；distill 完成后更新 jsonl_state | 跑一次 distill，medium 增长来自 jsonl 原料 |
| 7 | `refactor(memory): merge query default to manual_short + medium` | D8 实现；contract 加 source 过滤位 | 现有 memory_query 调用结果包含 medium |
| 8 | `refactor(hooks): SessionStart inject medium top-K + distill digest` | D6 实现 | SessionStart 上下文里看到新两段 |
| 9 | `feat(audit): redefine MemHealthScan with undistilled metrics` | D7 实现；阈值改名 | audit 报新指标 |
| 10 | `chore(memory): remove session_loader.py + session_writer.py` | 老死代码清理 | grep 无引用 |
| 11 | `docs(dna): update memory + crud + compaction module.md & contract.md` | dna_edit 全部架构文档同步 | dna_show 显示新架构 |

**总切片数：11**。前 5 个建议合并到一个 PR（"原料源建立"），后 6 个一个 PR（"消费侧切换 + 清理"）。assistant 派 programmer 时按 PR 颗粒度派两轮。

---

## 6. 自检清单

- [x] 无循环依赖：`jsonl_source` ← `compaction` ← `crud`（compaction 仍按现有规则反向调 crud 回写；jsonl_source 仅被 compaction 调）
- [x] 单一职责：jsonl_source 只翻译 Claude Code 私有 schema → 中性数据结构
- [x] 内部细节封装：jsonl 路径形状不出 jsonl_source 模块；jsonl_state.json 不被外部读
- [x] C1 开闭：父模块对外契约仍是 4 个只读接口，未变；新增内部子模块不影响对外
- [x] C3 单向依赖：从易变（jsonl_source，跟着 Claude Code 抖）→ 稳定（compaction）→ 最稳定（crud）
- [x] 与现有 sibling 无责任重叠：jsonl_source ≠ crud（不写 .cbim/）≠ compaction（不识别候选）

---

## 7. 附加发现（治理观察，非本任务交付物）

本任务在 BT 引擎中**两次被错路由到 programmer**，programmer 两次正确返回 `NEEDS_ARCH_DECISION:` 升级。观察到的可能原因：

1. **Decompose 节点疑似硬编码 `required_capability=programmer`**：包含"切换"/"改造"/"重构"等关键词的任务被默认归类为编码任务，未识别"产蓝图"信号。
2. **ConvergeJudge 不识别"programmer 反弹设计任务"模式**：programmer 升级 `NEEDS_ARCH_DECISION:` 后，下一轮 tick 仍走 programmer 路径，没有把 `agent_type` 切到 architect。

**建议（advice_pending 候选）**：
- Decompose 节点引入"工件类型"启发：任务文本中出现"设计稿"/"蓝图"/"blueprint"/"不动代码"等词时优先选 architect
- ConvergeJudge 引入"反弹检测"：上一轮 dispatch_result 含 `NEEDS_ARCH_DECISION:` 时下一轮强制切换 agent_type
- 或在 main_loop.py 增加 architect 与 programmer 之间的 ping-pong 防护，连续 2 次反弹直接 escalate 给用户

下轮治理 tick 由 architect 自己 sweep 时纳入 `advice_pending`。
