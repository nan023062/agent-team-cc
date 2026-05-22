# CBIM 业务知识治理循环

> **v1**（基于 Claude Code）与 **v2**（原生实现）共享的设计蓝图。  
> 网页版：`design/web/loops.html` → 业务知识治理循环标签。

业务轴 · `.dna/` · 知识系统的更新与裂变。执行任务的必经门，懒式 DNA 管理。与能力知识治理循环对偶，共同构成双轴治理体系。

```mermaid
flowchart TD
    Trigger(["触发条件<br/>· 执行任务循环派入（必经门）<br/>· 用户显式请求模块设计 / 合规审查<br/>· Work Agent 上报设计决策"])

    Scan["🔍 读取相关模块 .dna/ 文件<br/>扫描工作区代码结构"]
    StateCheck{"DNA 状态判断"}

    S0["状态 0<br/>DNA 不存在"]
    S1["状态 1<br/>DNA 同步 ✅"]
    S2["状态 2<br/>代码超前<br/>DNA 未跟上"]
    S3["状态 3<br/>DNA 超前<br/>设计意图未实现"]

    Worth0{"值得建 DNA?<br/>复杂度高 / 多处引用<br/>有明确设计意图"}
    Init["cbim dna init<br/>生成 module.md + contract.md<br/>边界 · 接口契约 · 依赖规则"]
    Skip0["跳过<br/>一次性脚本 / 临时代码"]

    Extract["直接提取<br/>模块路径与约束"]

    Think2["分析变更点<br/>哪些接口/边界/依赖改变?"]
    Update["cbim dna update<br/>补齐变更内容"]

    Validate3["验证设计可行性<br/>上下游依赖是否就绪?"]
    MarkSpec["标记「待实现 spec」<br/>DNA 即任务书"]

    ContextPack["📦 返回任务上下文包<br/>模块路径 + 设计约束<br/>依赖规则 + DNA 状态标记"]

    WorkAgent(["⚙️ Work Agent 执行"])

    Review["📋 架构合规复查<br/>实现是否破坏约束?"]
    Compliant{"合规?"}
    UpdateDNA["更新 DNA<br/>记录实现细节<br/>知识闭环"]
    Escalate["上报 Coordinator<br/>要求修正后再复查"]

    Fission(["✨ 裂变<br/>新模块 DNA → 知识图谱扩展<br/>旧模块拆分 → 子模块 DNA<br/>跨模块契约更新 → 依赖图重构"])

    Trigger --> Scan
    Scan --> StateCheck
    StateCheck -->|"无 DNA"| S0
    StateCheck -->|"同步"| S1
    StateCheck -->|"代码超前"| S2
    StateCheck -->|"DNA 超前"| S3

    S0 --> Worth0
    Worth0 -->|"值得"| Init
    Worth0 -->|"不值得"| Skip0
    Init --> ContextPack
    Skip0 --> ContextPack

    S1 --> Extract
    Extract --> ContextPack

    S2 --> Think2
    Think2 --> Update
    Update --> ContextPack

    S3 --> Validate3
    Validate3 --> MarkSpec
    MarkSpec --> ContextPack

    ContextPack --> WorkAgent
    WorkAgent --> Review
    Review --> Compliant
    Compliant -->|"✅ 合规"| UpdateDNA
    Compliant -->|"❌ 违规"| Escalate
    Escalate -->|"修正后"| Review
    UpdateDNA --> Fission
```

## DNA 四状态

| 状态 | 含义 | Architect 动作 |
|------|------|----------------|
| **0 — 无** | DNA 文件不存在 | 评估是否值得建；值得则 `cbim dna init`，否则跳过 |
| **1 — 同步** | DNA 与代码一致 ✅ | 直接提取模块路径与约束，返回上下文包 |
| **2 — 代码超前** | 代码已变更，DNA 未跟上 | 分析变更点，`cbim dna update` 补齐 |
| **3 — DNA 超前** | 有设计意图尚未实现 | 验证可行性，标记「待实现 spec」，DNA 即任务书 |

## 懒式生成原则

DNA 文档**不是前置必做项**。Architect 根据以下条件判断是否值得建：

- 模块复杂度高（多文件、多依赖）
- 被多处引用（改动影响范围广）
- 有明确设计意图需要显式记录
- 一次性脚本、临时代码 → **跳过**

## 知识裂变路径

- **新模块 DNA 建立** → 知识图谱扩展，下次任务可直接定位
- **旧模块拆分** → 子模块独立 DNA，粒度更精确
- **跨模块契约更新** → 依赖图重构，减少耦合风险

## 与能力轴的对偶关系

业务轴（`.dna/`）与能力轴（`.claude/agents/`）互为镜像：

- 业务知识治理管「模块做什么、有什么约束」
- 能力知识治理管「谁来做、有什么能力」
- 两轴协同裂变，覆盖范围持续扩展
