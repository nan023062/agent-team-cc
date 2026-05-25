# ModeClassify v3.7 — 精度修复草案

> 关联：[执行根流程图](./WORKFLOW-EXECUTION.zh-CN.md) · `v1/kernel/engine/execution/.dna/module.md`
>
> 本文档承载 v3.7 ModeClassify 精度修复的完整草案：问题诊断、修复策略、pattern 表全文、回归用例与 programmer 交付清单。`module.md` Key Decisions 中只保留摘要 bullet 引用本文。

---

## v3.7 — ModeClassify 精度修复：执行意图优先 + 收紧核心 agent 触发词

**问题（背景）。** v3.5/v3.6 的 `ModeClassify` 精度优先序是 `architect > hr > audit > execution-verb > conversation`，且核心 agent 三表使用裸关键词（`design` / `architecture` / `module.md` / `audit` / `recruit` / `code review` / …）。后果是"执行类请求被核心 agent 关键词误抢"：

| 用户请求 | 旧分类 | 实际意图 |
|----------|--------|----------|
| `implement audit logging` | `audit` | execution |
| `refactor the architecture module` | `architect` | execution |
| `add agent recruitment endpoint` | `hr` | execution |
| `fix the design doc typo` | `architect` | execution |
| `build a code review pipeline` | `audit` | execution |
| `create module.md template` | `architect` | execution |
| `把审计模块的 bug 修一下` | `audit` | execution |
| `重构招聘流程代码` | `hr` | execution |

根因：核心 agent 三表把"主题词"（架构 / 招聘 / 审计的领域名词）当成了"派给该 agent 的信号"。但主题词只是话题归属，不等于派工目标——"修改 audit 代码"是 execution 任务，不是 audit 任务。

**v3.7 修复（已落 `actions/mode_classify.py`）。**

1. **精度优先序翻转为：`execution-verb > architect-request > hr-request > audit-request > conversation`。** 执行动词率先短路；只有当用户没用执行动词，但显式表达"派给核心 agent"时，才进核心 agent 分支。

2. **核心 agent 三表只匹配"显式请求该核心 agent"的短语，不接受裸主题词。** 必须出现以下两类信号之一：
   - **直呼角色名 + 派工动词**：`ask/let/dispatch/send to/consult the architect`、`让/请/找/问 架构师 帮我…`
   - **明确的元任务动词 + 该角色专属产出**：`design a (new) module`、`draw the architecture`、`propose a blueprint`、`split/merge a module`、`update .dna`、`画/出 一份 设计/蓝图/架构`、`拆分/合并/废弃 模块`、`定义契约`
   裸名词如 `audit`（领域名）、`architecture`（领域名）、`recruit`（功能名）不再单独触发；必须与对应元任务动词共现或与角色称呼共现。

3. **执行动词表保持现状**（`implement|add|fix|refactor|build|wire|create|split|merge|deprecate|update|delete|remove`，中文 `实现|新增|修复|重构|加|创建|拆分|合并|废弃|更新|删除|改写|重写`），但其中 `split/merge/update/create` 既出现在执行表也出现在 architect 元任务表——**翻转后由 architect 表内的"动词 + 该角色专属产出"组合保证 architect 任务依然命中**（如 `split a module` 同时命中 execution `split` 与 architect `split.*module`；翻转后命中 execution，故需要 architect 表使用更窄的"组合"短语，且执行表中 `split/merge` 要求显式存在"module"等架构产出名词以外的对象，或由架构师任务主动绕过；本次修复采用更直接的方案——见下条）。

4. **关键平衡：`design / draw / propose blueprint / split a module` 等 architect 元任务不在 execution 动词表中**——execution 表里只有 `implement/add/fix/refactor/build/wire/create/split/merge/deprecate/update/delete/remove`。`design`、`draw`、`blueprint`、`sketch`、`架构`、`蓝图`、`设计` 都不在 execution 表内，因此 "design a new module" 不触发 execution，可被 architect 表的 `design\s+(a\s+)?(new\s+)?(module|system|component|service|API|architecture|blueprint)` 命中，路由到 architect。

5. **关于 `split/merge/create + module`**：这是真正的歧义点。"split a module"
   - 在 v3.7 中视为**架构任务**（拆模块是架构师职责），故 architect 表显式列出 `(split|merge|deprecate)\s+(a\s+)?module`；execution 表的裸 `split` 仍存在但被 architect 表先命中——这是**唯一**的"核心 agent 表优先于 execution 表"的例外，理由是"拆/并/废弃模块"语义上无 execution 落点（拆模块的实际产出是 .dna 改动而非源码改动）。
   - 实现方式：把这一组 architect-specific 短语放在 execution 表之前的**预检表**（`_ARCHITECT_PREEMPT_PATTERNS`），单独一级；其余 architect 短语（design/blueprint/draw/etc.）仍在 execution 之后。

6. **新精度优先序最终落地**：
   ```
   architect-preempt（split/merge/deprecate a module、拆/合并/废弃模块、update .dna）
     > execution-verb（implement/fix/refactor/…）
     > architect-request（design a module、draw architecture、ask architect、让架构师 …）
     > hr-request（recruit a X agent、ask HR、招 X agent、让 HR …）
     > audit-request（audit X、ask auditor、独立审查 X、让审计员 …）
     > conversation（what/why/how、什么/为什么/怎么）
     > LLM 兜底（NullLLM → execution）
   ```

**Schema 不变**：`bb.mode` 取值仍为 `{conversation, architect, hr, audit, execution}` 五种；`DispatchRequest.agent_type` 枚举不动；契约不动。本变更纯为规则表精度修复，不动接口、不动黑板字段、不动持久化。

**回归一例**：`test_mode_classify_architect_wins_over_execution_verb`（输入 `design and implement a new auth module`，旧期望 `architect`）在 v3.7 下应改期望为 `execution`——既然用户已明确说要 `implement`，就是 execution 任务（架构师子树由 `ArchitectExecution` 在 ExecutionSeq 头部自动接入完成蓝图阶段）。该测试期望在 v3.7 中翻转为 `execution`，**这是已知且故意的语义变化**。

### v3.7 具体 pattern 表草案（交 programmer 落代码）

**预检层（架构师独占动作，优先于 execution 动词）。** 只收 .dna 相关、拆/合/废弃模块三类语义上不可能是"代码执行"的表达。

```python
_ARCHITECT_PREEMPT_PATTERNS = [
    # 中文：拆/合并/废弃 模块
    re.compile(r"(拆分|拆|合并|废弃|下架)\s*[一个]?\s*\S*\s*模块"),
    # 中文：更新/修订/重写 .dna
    re.compile(r"(更新|修订|重写|调整)\s*\.?dna"),
    re.compile(r"更新\s*(module|contract)\.md", re.IGNORECASE),
    # English: split/merge/deprecate (a) module
    re.compile(
        r"\b(split|merge|deprecate|retire|archive)\s+(an?\s+|the\s+)?\w*\s*module\b",
        re.IGNORECASE,
    ),
    # English: update/edit/touch .dna (and friends)
    re.compile(
        r"\b(update|edit|modify|touch|fix|amend|rewrite)\s+(the\s+)?"
        r"(\.dna|module\.md|contract\.md|dna\s+(doc|entry|record|module))\b",
        re.IGNORECASE,
    ),
]
```

**Execution 动词表（第二优先，现状不动）。**

```python
_EXECUTION_PATTERNS = [
    re.compile(
        r"\b(implement|add|fix|refactor|build|wire|create|split|merge|deprecate|"
        r"update|delete|remove)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(实现|新增|修复|重构|加(一?个|入)|创建|拆分|合并|废弃|更新|删除|改写|重写)"
    ),
]
```

**Architect-request 表（第三优先）。** 严格要求两类信号：(a) 直呼 `architect` 角色名 + 派工动词；(b) 架构师专属元任务动词短语。裸词如 `architecture` / `module.md` / `contract.md` 不再单独触发。

```python
_ARCHITECT_PATTERNS = [
    # (a1) English: 直呼 architect + 派工动词
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?architect\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让/请/找/问/叫 架构师
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*架构师"),
    # (b1) English: design + 架构师专属产出名词
    re.compile(
        r"\bdesign\s+(an?\s+|the\s+)?(new\s+)?"
        r"(module|sub-?module|system|component|service|API|architecture|"
        r"blueprint|contract|interface|boundary|layer)\b",
        re.IGNORECASE,
    ),
    # (b2) English: draw / propose / sketch / re-architect + architecture/blueprint
    re.compile(
        r"\b(draw|sketch|propose|outline|re-?architect|redesign)\s+"
        r"(an?\s+|the\s+)?(architecture|blueprint|design|module\s+shape|"
        r"module\s+boundary|component\s+diagram)\b",
        re.IGNORECASE,
    ),
    # (b3) English: define a contract / module boundary
    re.compile(
        r"\bdefine\s+(an?\s+|the\s+)?(contract|interface|module\s+boundary|"
        r"sub-?module\s+boundaries)\b",
        re.IGNORECASE,
    ),
    # (b4) English: knowledge pack / context pack 产出
    re.compile(
        r"\b(produce|write|prepare|build|generate)\s+(an?\s+|the\s+)?"
        r"(knowledge\s+pack|context\s*pack)\b",
        re.IGNORECASE,
    ),
    # (b5) Chinese: 架构师元任务动词 + 产出名词
    re.compile(
        r"(画|出|做|提供|写|准备|生成)\s*(一?份|一?张|一?套)?\s*"
        r"(设计|蓝图|架构|知识包|context\s*pack|模块划分|模块边界|契约设计)"
    ),
    # (b6) Chinese: 模块化 / 重构架构
    re.compile(r"(模块化|重构架构|拆分模块|合并模块|定义契约|架构设计)"),
]
```

**HR-request 表（第四优先）。**

```python
_HR_PATTERNS = [
    # (a1) English: 直呼 HR + 派工动词
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?hr\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让/请/找/问/叫 HR
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*HR", re.IGNORECASE),
    # (b1) English: recruit/hire/onboard … agent
    re.compile(
        r"\b(recruit|hire|onboard|train|coach|mentor|assess|evaluate|fire|"
        r"retire|promote)\s+(an?\s+|the\s+)?\w*\s*(work\s+)?agent\b",
        re.IGNORECASE,
    ),
    # (b2) Chinese: 招/聘/上岗/培训/带教/考核/裁撤/晋升 + agent
    re.compile(
        r"(招募|招聘|招(一?个)?|聘请|入职|上岗|培训|带教|考核|评估|"
        r"裁撤|晋升|下岗)\s*\S*\s*(work\s*)?agent",
        re.IGNORECASE,
    ),
    # (b3) Chinese: 能力管理 / 人员管理 / 峗位调整
    re.compile(r"(能力管理|人员管理|峗位调整|招聘 agent|入职 agent)"),
]
```

**Audit-request 表（第五优先）。**

```python
_AUDIT_PATTERNS = [
    # (a1) English: 直呼 auditor + 派工动词
    re.compile(
        r"\b(ask|let|have|tell|dispatch|send|consult|get|find|invoke)\s+"
        r"(the\s+)?auditor\b",
        re.IGNORECASE,
    ),
    # (a2) Chinese: 让/请/找/问/叫 审计员
    re.compile(r"(让|请|找|问|叫|派给|交给)\s*审计员"),
    # (b1) English: 独立审查 / second opinion / sanity / governance check
    re.compile(
        r"\b(independent\s+(review|audit|critique)|second\s+opinion|"
        r"sanity\s+check|governance\s+check|gov\s+check)\b",
        re.IGNORECASE,
    ),
    # (b2) English: audit + 对象名词（避开 "implement/build/fix audit ..."）
    # 仅当 audit 作为动词出现于句首或请求动词后面
    re.compile(
        r"(^|\b(please|kindly|could you|can you|let'?s|let us)\s+)"
        r"audit\s+(the\s+|this\s+|our\s+|my\s+)?\w+",
        re.IGNORECASE,
    ),
    # (b3) English: do/run/perform a code-review / design-review
    re.compile(
        r"\b(do|run|perform|conduct|kick\s*off)\s+(an?\s+|the\s+)?"
        r"(code\s*review|design\s*review|architecture\s*review|audit)\b",
        re.IGNORECASE,
    ),
    # (b4) Chinese: 独立审查 / 复盘 / 质疑 / code review
    re.compile(
        r"(审计|独立审查|独立审核|独立复核|独立评审|独立审查|"
        r"复盘|挑刺|找问题|质疑|提出反对意见|做\s*code\s*review)"
    ),
]
```

**Conversation 表与 LLM 兜底保持现状。**

**新分类主循环顺序（`ModeClassify.tick`）：**

```
1. text.strip() == "" → conversation
2. 预检层 _ARCHITECT_PREEMPT_PATTERNS 命中 → architect
3. _EXECUTION_PATTERNS 命中 → execution
4. _ARCHITECT_PATTERNS 命中 → architect
5. _HR_PATTERNS 命中 → hr
6. _AUDIT_PATTERNS 命中 → audit
7. _CONVERSATION_PATTERNS 命中 → conversation
8. LLM 兜底（NullLLM → execution）
```

**Programmer 交付要点：**

1. 只改 `actions/mode_classify.py`一个文件：替换三张 pattern 表 + 新增 `_ARCHITECT_PREEMPT_PATTERNS` + 调整 `tick()` 顺序。
2. 同步更新文件顶部 docstring：精度优先序从 v3.5 的 `architect > hr > audit > execution-verb` 改为 v3.7 的 `architect-preempt > execution-verb > architect > hr > audit`。
3. 更新 `v1/tests/test_bt_l1_nodes.py`：
   - `test_mode_classify_architect_wins_over_execution_verb` 期望值改为 `execution`（含 implement 即为 execution，同时重命名为 `test_mode_classify_execution_verb_wins_over_design_keyword` 以反映新语义）。
   - 新增反回归用例（至少以下 8 条，覆盖三表）：
     | 输入 | 期望 mode |
     |------|-----------|
     | `implement audit logging` | execution |
     | `refactor the architecture module` | execution |
     | `add agent recruitment endpoint` | execution |
     | `fix the design doc typo` | execution |
     | `build a code review pipeline` | execution |
     | `重构招聘流程代码` | execution |
     | `拆分 auth 模块` | architect（预检命中） |
     | `update .dna for auth module` | architect（预检命中） |
4. 运行 `pytest v1/tests/test_bt_l1_nodes.py -k mode_classify` 确认全绿。
5. **不要**动 contract.md / DispatchRequest / agent_type 枚举；**不要**动 `engine/dream`、`mcp_server`、`arch_exec` 子模块。
