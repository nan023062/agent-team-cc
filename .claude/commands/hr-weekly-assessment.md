# /hr-weekly-assessment — 周度考核与培训

替代 OpenClaw HEARTBEAT（每周一 10:00）。手动执行，建议每周初触发。

## 执行步骤

派发 HR subagent 执行周度考核与培训：

```
Agent(
  description="执行 work agent 周度考核与培训",
  prompt="""
你是 HR。先读取 .claude/agents/hr.md 加载你的完整身份。

本次任务：执行周度考核与培训。

步骤：
1. 读取 memory/hr/agent-signals.md，统计近 7 天的信号：
   - 哪些 agent 有信号？信号类型分布？
   - 同一 agent 同类问题出现几次？

2. 逐一对有信号的 work agent 执行考核（assessment skill）：
   - 读取 skills/hr/assessment.md
   - 判断问题性质（能力缺口 / 定位错误）
   - 输出考核结论（良好 / 需培训 / 需重塑）

3. 按考核结论执行后续：
   - 良好 → 执行培训 skill 沉淀优秀模式（skills/hr/training.md）
   - 需培训 → 执行培训 skill 填补能力缺口
   - 需重塑 → 输出重塑方案，等待用户确认后执行

4. 输出周度考核汇总报告：
   - 本周考核 agent 列表 + 结论
   - Memory / Skill / Soul 变更清单
   - 待用户确认的重塑或裂变方案（如有）
"""
)
```
