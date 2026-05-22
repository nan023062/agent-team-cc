# CBIM 能力知识治理循环

> **v1**（基于 Claude Code）与 **v2**（原生实现）共享的设计蓝图。  
> 网页版：`design/loops.html` → 能力知识治理循环标签。

能力轴 · `.claude/agents/` · 能力系统的更新与裂变。与业务知识治理循环对偶，共同构成双轴治理体系。

```mermaid
flowchart TD
    Trigger(["触发条件\n· 执行任务发现能力缺口\n· 用户显式请求招募/训练/评估/归档\n· HR 定期评估能力覆盖度"])

    Scan["🔍 扫描 .claude/agents/\n盘点现有 agent 能力清单"]
    Match{"匹配结果"}

    HasFit["✅ 有且胜任"]
    HasWeak["⚠️ 有但能力不足"]
    NoAgent["❌ 无匹配 agent"]

    ReturnPath["返回 agent 路径\n给 Coordinator"]
    TrainOrRecruit{"训练 or 招募?"}
    Train["📚 训练\ncbim agent update\n更新技能 / 性格 / 行为规范"]
    WorthNew{"复杂度足够\n值得专属 agent?"}
    Scaffold["🌱 招募新 agent\ncbim agent scaffold\n定义角色 / 技能 / 性格 / 工具权限"]
    Temporary["使用现有通用\nagent 临时处理"]

    Execute(["⚙️ 任务执行"])
    Assess["📊 评估表现"]
    AssessResult{"表现如何?"}
    Improve["更新 agent.md\n记录最佳实践\n提升能力描述"]
    Retrain["🔧 再训练\n调整性格 / 技能 / 边界约束"]
    Archive["📦 归档\ncbim agent archive"]

    Fission(["✨ 裂变\n专用 agent 孵化 → 能力图谱扩展\n通用 agent 分化 → 专项独立\n老 agent 归档 → 能力沉淀 memory"])

    Trigger --> Scan
    Scan --> Match
    Match --> HasFit
    Match --> HasWeak
    Match --> NoAgent

    HasFit --> ReturnPath
    HasWeak --> TrainOrRecruit
    TrainOrRecruit -->|"训练"| Train
    TrainOrRecruit -->|"招募"| NoAgent
    Train --> ReturnPath

    NoAgent --> WorthNew
    WorthNew -->|"是"| Scaffold
    WorthNew -->|"否"| Temporary
    Scaffold --> ReturnPath
    Temporary --> ReturnPath

    ReturnPath --> Execute
    Execute --> Assess
    Assess --> AssessResult
    AssessResult -->|"优秀"| Improve
    AssessResult -->|"需改进"| Retrain
    AssessResult -->|"不再需要"| Archive

    Improve --> Fission
    Retrain --> ReturnPath
    Archive --> Fission
```

## 裂变路径

- **专用 agent 孵化** → 能力图谱扩展，新的专项能力进入体系
- **通用 agent 分化** → 专项 agent 独立，减少通用 agent 的职责蔓延
- **老 agent 归档** → 能力经验沉淀到 `memory/`，不消失只转形

## Agent 生命周期

| 阶段 | 操作 | 说明 |
|------|------|------|
| 招募 | `cbim agent scaffold` | 定义角色、技能、性格、工具权限 |
| 训练 | `cbim agent update` | 更新技能描述、行为规范、边界约束 |
| 评估 | HR 分析执行质量 | 比对任务结果与 agent 能力声明 |
| 归档 | `cbim agent archive` | 标记不再活跃，经验写入 memory |

## 与业务轴的对偶关系

能力轴（`.claude/agents/`）与业务轴（`.dna/`）互为镜像：

- 业务轴新增模块 → 可能触发能力轴招募对应专域 agent
- 能力轴新 agent 孵化 → 携带新的业务领域知识
- 两轴协同裂变，边界持续扩展
