# CBIM 记忆治理循环

> **v1**（基于 Claude Code）与 **v2**（原生实现）共享的设计蓝图。  
> 网页版：`design/web/loops.html` → 记忆治理循环标签。

执行经验自动沉淀为知识。全程由 Hook 驱动，对用户完全透明。

```mermaid
flowchart TD
    SessionStart(["⚡ SessionStart Hook"])
    Load["load_memory.py<br/>读取 memory/short/ + memory/medium/<br/>注入当前会话上下文"]
    Session["🗣 会话进行中<br/>Coordinator + Agents 执行任务"]
    PrePost["⚡ PreToolUse / PostToolUse Hook<br/>logger.py<br/>记录 CALL · RET · USER · ASSIST · agent:name"]
    Log[("📄 session_YYYY-MM-DD.log<br/>结构化会话日志")]
    StopHook["⚡ Stop Hook<br/>write_memory.py<br/>提炼本轮对话要点"]
    Short[("📁 memory/short/<br/>原始会话提炼")]
    Threshold{"short/ 积累<br/>达到阈值?"}
    Distill["🏛 Architect 蒸馏<br/>识别跨会话重复模式"]
    Medium[("📁 memory/medium/<br/>跨会话规律<br/>用户偏好 · 常见决策")]
    Promote{"发现稳定原则?"}
    DNA[("📁 .dna/<br/>架构约束 · 设计原则<br/>模块契约")]
    NextSession(["⚡ 下次 SessionStart"])

    SessionStart --> Load
    Load --> Session
    Session --> PrePost
    PrePost --> Log
    Log --> Session
    Session -->|"每轮回复结束"| StopHook
    StopHook --> Short
    Short --> Threshold
    Threshold -->|"否"| NextSession
    Threshold -->|"是"| Distill
    Distill --> Medium
    Medium --> Promote
    Promote -->|"否"| NextSession
    Promote -->|"是"| DNA
    DNA --> NextSession
    NextSession --> Load
```

## 三层沉淀

| 层级 | 路径 | 内容 | 触发 |
|------|------|------|------|
| 原始层 | `memory/short/` | 每次会话的要点提炼 | Stop Hook 自动 |
| 模式层 | `memory/medium/` | 跨会话的重复规律、用户偏好、常见决策 | Architect 蒸馏 |
| 原则层 | `.dna/` | 稳定架构约束、设计原则、模块契约 | Architect 提升 |

## Hook 一览（v1 Claude Code 实现）

| Hook | 脚本 | 作用 |
|------|------|------|
| `SessionStart` | `load_memory.py` | 读取 short/ + medium/，注入上下文 |
| `PreToolUse` | `log_pre_tool.py` | 记录工具调用（CALL） |
| `PostToolUse` | `log_post_tool.py` | 记录工具返回（RET） |
| `Stop` | `write_memory.py` | 提炼本轮对话写入 short/ |

## 日志格式

```
[2026-05-22T10:30:00] [USER] 用户消息内容
[2026-05-22T10:30:01] [CALL] [agent:programmer] Read(path=...)
[2026-05-22T10:30:02] [RET]  [agent:programmer] Read → 文件内容...
[2026-05-22T10:30:05] [ASSIST] 助手回复
```

主 session 无 agent 标签；子 agent 通过 `transcript_path` 旁的 `.meta.json` 识别 `agentType`。
