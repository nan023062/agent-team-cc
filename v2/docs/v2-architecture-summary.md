# CBIM V2 架构封板摘要

## 核心命题

V2 把 V1 中靠 CLAUDE.md 让 LLM 自行决定调度的概率性逻辑，固化为 C# 状态机 + 规则表 + 强类型工具协议的确定性调度。LLM 只在真正需要判断时（架构设计 / 代码实现 / 独立审查）发挥作用。

## 设计哲学（硬件比喻）

| 硬件层 | CBIM 语义层 | 物理特征 |
|--------|-------------|----------|
| CPU 寄存器 / L1 Cache | Active Context Window | 极昂贵、极小，LLM 当前轮次能触达的"思维空间" |
| L2/L3 Cache Controller | CBIM 运行时引擎 | 后台算计、拦截寻址、预测依赖、换入换出 |
| 物理 RAM | .cbim/index.md 注册表 + .dna/ 契约知识 + 人力知识 + 短中期记忆 | 晶体化提炼的高密度索引 |
| 外部冷源磁盘 | 项目 src/ 原始源码 | 海量、嘈杂、无语义索引；Cache Miss 才允许降级盲扫 |

## 程序集清单（8 个）

| 程序集 | 硬件比喻 | 职责 |
|--------|----------|------|
| CBIM.Contracts | — | 纯接口/记录/枚举，无逻辑 |
| CBIM.CacheController | L2/L3 Controller | 调度 + 语义分页 + 内置 agent 逻辑（coordinator/architect/HR/auditor 内化于此） |
| CBIM.PageStore | RAM | CBIM 所有结构化内容统一持有者（DNA + Agents + 短/中期记忆） |
| CBIM.Processor | Execution Unit | 自实现 agent 运行循环（Perceive → Think → Act → Observe → Stop） |
| CBIM.DiskAccess | Disk Controller | 物理工作区网关（Read/Edit/Write/Bash/Grep）+ 权限矩阵 |
| CBIM.Foundation.Llm | — | 多 Provider LLM 抽象（Anthropic/OpenAI/本地） |
| CBIM.Foundation.Storage | I/O Bus | 原子文件写，服务长期记忆（DNA/Agents） |
| CBIM.Foundation.Memory | Memory Bus | 短/中期记忆后端抽象（默认 FileBackend，可扩展 Vector/Graph） |
| CBIM.UI.Avalonia | Monitor | Avalonia 桌面 UI |

## 依赖方向（无环）

```
UI.Avalonia
    ↓
CacheController ──→ Processor ──→ DiskAccess
    ↓                   ↓
PageStore         Foundation.Llm
    ├──→ Foundation.Storage  (DNA/Agents)
    └──→ Foundation.Memory   (短/中期记忆)

所有模块 ──→ Contracts
```

## 七条关键设计约束

1. **内置 agent 不可见、不可编辑**：coordinator/architect/HR/auditor 是 CacheController 内部 C# 逻辑，UI 只显示名称和活动状态，无 soul/skill 配置文件
2. **用户 agent 完全自定义**：YAML/TOML 格式，与 V1 `.claude/agents/*.md` 无关
3. **Cache Miss 是异常路径**：扫 src/ 触发"晶体化补写 DNA"反馈循环
4. **Controller 主动预取**：根据任务标签预测并预取 `.dna/` 页，不等 LLM 要求
5. **写权限闸门**：PageStore 直连 Foundation.Storage（受信任内核写）；DiskAccess 是 agent 唯一物理文件入口（权限矩阵 + 路径白名单）
6. **调度兜底**：规则表无法分类时直接问用户澄清，不引入额外 LLM
7. **取代 V1**：V2 独立运行，知识库路径 `.cbim/`，不绑 V1

## V1↔V2 衔接

- **沿用**：`.dna/` 物理格式（YAML frontmatter + markdown）、`memory/` 格式
- **取代**：Claude Code 宿主、CLAUDE.md 调度规约、Python engine、`.claude/agents/*.md` 格式
- **迁移**：快速切换，不做双写校验过渡
