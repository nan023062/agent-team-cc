# CBIM vs Plain Agent Benchmark

[English](README.md) | [中文](README.zh-CN.md)

可控的 A/B 对比：完全相同的一组编程任务跑两遍 —— 一次打到**裸 `claude -p`**（无 CBIM、无 agent、无 MCP、无 hook），一次打到**装好 CBIM** 的同一份项目副本。输出 side-by-side 数据表，可直接用于博客文章、README、决策备忘。

## 为什么有这个

核心问题：**CBIM 相对未增强的 agent 到底有没有帮助？** 同 prompt、同 fixture、两种配置 —— 裸 `claude -p` 和装好 CBIM 的 `claude -p`。side-by-side 数据让答案是实证的，不是断言的。

## 一行启动

```bash
ANTHROPIC_API_KEY=sk-... ./v1/tests/benchmark/run-bench.sh
```

输出：
- `results/report-NNN.md` —— side-by-side markdown 表
- `results/report-NNN/` —— 每个 task 每个 mode 的 session log

完整跑一次约 **5-15 分钟** wall time、约 **\$5-\$20** API 成本（5 task × 2 mode = 10 次 `claude` 调用）。

## 测什么

每个 task 在每个 mode 下：

| 指标 | 怎么测 | 为何重要 |
|---|---|---|
| 成功率 | `success_check(project_root)` —— 客观、基于文件 | agent 真的完成任务了吗 |
| Wall time | `claude -p` 前后 `time.perf_counter()` | CBIM 开销的延迟成本 |
| Input / output tokens | `claude -p --output-format json` | CBIM 开销的 token 经济成本 |
| 代码增删行数 | 相对 fixture baseline 的 diff（`src/` 与 `tests/` 下的 `.py`）| 改动的接触面 |
| Dispatch count | 启发式扫 session log 中 subagent 调用 | "架构稳定性" —— CBIM 是否按设计在派发 |
| `.dna/` 读取次数 | 启发式扫 session log 中 `.dna/` 路径 | 架构师是否真在咨询知识 |
| Turn count | session log 中的结构标记 | 迭代形态 |

所有启发式两边一致应用。Plain mode 由结构决定永远 0 dispatch / 0 `.dna/` 读（fixture 副本里没 `.cbim/`）；CBIM mode 显示装好的 agent 实际做了什么。

## 目录结构

```
v1/tests/benchmark/
├── README.md          （本文）
├── README.zh-CN.md    （中文版）
├── run-bench.sh       一键 driver
├── runner.py          A/B 编排（每个 task 跑 plain + cbim 两 mode）
├── runner_cli.py      CLI：发现 task、循环、写报告
├── _report.py         render_ab_markdown() —— side-by-side 表
├── fixture/           共享的 toy Python 项目（calculator + parser）
│   ├── src/calculator.py
│   ├── src/parser.py
│   ├── tests/test_calculator.py
│   └── README.md
├── tasks/             每个 task 一个文件
│   ├── _common.py     共享的 arch-metrics extractor + diff helper
│   ├── task_a.py      修除零 bug
│   ├── task_b.py      给 parser 加 eval()
│   ├── task_c.py      新增 validator 模块
│   ├── task_d.py      跨模块重构：共享错误层级
│   └── task_e.py      纯解释任务（不改代码）
└── results/
    ├── report-001.md
    └── report-001/    第 001 次 run 的 session logs
```

## 怎么读报告

报告以**中文**渲染（section 标题、表头、状态词）。代码标识符、文件路径、agent 名、MCP 工具名、mode 名（`plain` / `cbim`）、git hash 保持英文。

每份报告 3 段：

1. **运行** —— 何时、跑了什么、几个 task
2. **逐 task 对比** —— 每个 (task, mode) 对一行，能看每 task 的方差，不只是平均
3. **汇总** —— 跨所有 task 的均值 + `Delta` 列

一个有意思的 CBIM 故事大致长这样：
- 成功率列：CBIM ≥ plain（特别是跨模块的 task D 上）
- Wall / tokens 列：CBIM > plain（开销是真的）
- Dispatch / `.dna` 读：CBIM 在 requirement-type task 上 > 0，在 task_e（纯 query）上 ≈ 0；plain 在所有任务上都 = 0
- 代码行数：CBIM 通常多写一些（更好的测试覆盖、防御代码）—— 跟踪验证

## 添加新 task

新建 `tasks/task_<x>.py`，导出 3 个名字：

```python
NAME = "task_x"

PROMPT = """\
给 claude 的自然语言任务描述。
应按实际路径引用 fixture 文件（例如 `src/calculator.py`）。
"""

def success_check(project_root: Path) -> bool:
    """task 是否完成。基于文件、确定性。"""
    ...

def arch_metrics_extract(result, project_root, baseline_root) -> dict:
    """该 task 的架构稳定性指标。"""
    from ._common import base_arch_metrics
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
```

如果任务的答案在 model 的文字回复里而不是文件里，可选 export `stdout_check(stdout: str) -> bool`（见 `tasks/task_e.py`）。

Runner 自动发现 `tasks/task_*.py`，不用更新任何 registry。

## 注意事项

- 启发式指标（`dispatch_count` / `dna_read_count` / `turn_count`）读的是 CBIM session log，**这不是契约**，格式可能演化。同一份启发式两边一致应用，所以任何漂移对两侧偏差相同。
- Plain mode 没有 session log（没 `.cbim/`），它的启发式计数永远 0。这是对的：裸 `claude -p` 本来就没 subagent 可派发。
- Token 数取决于 `claude -p --output-format json` 是否暴露。CLI 改 JSON 形态时 token 可能在报告里显示 `?`。best-effort 解析见 `v1/tests/framework/runner.py:_parse_claude_json`。
- `success_check` 故意严格但窄：只检查 prompt 要求的具体结构性变化，不检查"品味"。
