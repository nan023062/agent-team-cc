# /hr-daily-signal — 每日信号采集

替代 OpenClaw HEARTBEAT（每日 18:00）。手动执行，建议在每天结束时触发。

## 执行步骤

派发 HR subagent 执行信号采集：

```
Agent(
  description="采集今日 work agent 能力缺口信号",
  prompt="""
你是 HR。先读取 .claude/agents/hr.md 加载你的完整身份。

本次任务：执行每日信号采集。

步骤：
1. 读取 memory/hr/agent-signals.md，了解现有信号格式和历史记录
2. 回顾今日（或近期）各 work agent 的执行情况：
   - 用户在对话中提到的 agent 表现反馈
   - 是否有任务失败、重试、被退回的情况
   - 是否有边界混淆（agent 接手了不属于其职责的任务）
   - 是否有评审官打回记录
3. 将发现的信号按格式写入 memory/hr/agent-signals.md：
   `- [YYYY-MM-DD] [agent-id] 信号类型: 描述`
4. 清理 30 天前的过期信号条目
5. 汇报本次采集结果（新增信号数量、涉及 agent）

若无异常信号，记录一条「今日无异常」说明并汇报。
"""
)
```
