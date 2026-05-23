# 工作流测试

[English](README.md) | [中文](README.zh-CN.md)

CBIM 4 个设计循环的**架构验证测试** —— EXECUTION / ARCHITECT / HR / MEMORY（详见 `design/WORKFLOW-*.zh-CN.md`）。**不是 benchmark**：目的是断言协调中枢在每个 prompt 上能驱动正确的循环，不是给模型打分。

| 循环 | 正例 | 反例 |
|------|------|------|
| EXECUTION  | 实现 `greet(name)` + 单元测试 | 一句话读 CLAUDE.md |
| ARCHITECT  | `cbim dna init` 一个新的 `combat` leaf 模块 | 列出已有 DNA 模块（只读）|
| HR         | 招一个 `frontend` agent | 列出已有 agent（只读）|
| MEMORY     | "记一下：hook 走 in-process 不走 MCP" | "你好" |

外加 5 个 **AUDIT** case（每个 audit check 一个）—— 只有正例。audit 是横切关注点，用户明确请求治理检查时永远应当被采纳，没有"该不调"的反例语义：

| Audit 检查        | 期望派给 | Prompt 摘要                                  |
|-------------------|----------|---------------------------------------------|
| `index_consistency`| architect | 检查 `.dna/index.md` 与实际模块是否一致     |
| `dna_tree`         | architect | 审计 DNA 依赖图（环 / 孤儿 / 祖先误声明） |
| `dna_fission`      | architect | 标记体积或 workflow 过载的 DNA 模块         |
| `agent_fission`    | hr        | 标记 skill 数或正文过载的 agent             |
| `memory_threshold` | architect | 检查 memory 压缩 / 提炼阈值                 |

每个 case 都是真实的 `claude` 调用打到 Anthropic API。**完整 13 case 跑一次约 $2-$15**，耗时 5-15 分钟。CI 不跑。

## 框架架构

`framework/` 是可复用的测试基础设施；13 个静态测试是它的第一批用户，Phase 14b 的 A/B benchmark 是第二批。

```
framework/
  target.py        TestTarget (Protocol) + TmpProject + ExternalProject
  runner.py        run(target, prompt, timeout) -> Result
  result.py        Result dataclass（exit / wall / tokens / session log / ...）
  log_assert.py    parse_log + Verdict + 5 个 assert_*_loop（4 个循环 + audit）
  stats.py         CaseStats + AggregateStats + aggregate(cases, group_fn)
  reporter.py      render_markdown / render_markdown_single / render_stdout
  generators/      PromptGenerator Protocol + registry（默认：`static`）
```

**两种 target 模式**（任何实现 `TestTarget` Protocol 的类都行）：

- `TmpProject` —— 临时目录新装 CBIM；每次调用都 setup/teardown
- `ExternalProject` —— 指向已存在的项目；setup/teardown 都是 no-op

**两种 prompt 来源**（任何实现 `PromptGenerator` 的类都行）：

- `static`（默认）—— 读 `.md` 文件
- *未来* —— 动态 generator 同样注册即可

## 怎么跑

### 1. pytest（跑 13 个静态 case）

```bash
ANTHROPIC_API_KEY=sk-... pytest v1/tests/workflow/ -m workflow -v

# 只跑某个循环
pytest v1/tests/workflow/test_loop_memory.py -m workflow -v

# 只跑某个 case
pytest v1/tests/workflow/test_loop_memory.py::test_loop_memory_negative -m workflow -v
```

`ANTHROPIC_API_KEY` 未设或 `claude` 不在 `PATH` 时自动 skip。不带 `-m workflow` 时不选中任何 case。

### 2. run-bench.sh（一键批跑 + 出报告）

```bash
ANTHROPIC_API_KEY=sk-... ./v1/tests/workflow/run-bench.sh
```

自动分配下一个 `results/report-NNN.md` 序号，跑全部 13 case，把每个 session log copy 到 `results/report-NNN/logs/`，调 `framework.reporter` 生成 markdown 报告。

### 3. CLI（任意 prompt 跑任意项目）

```bash
# 临时新装 + prompt 文件
python -m v1.tests.workflow.cli run --prompt my-prompt.md

# 指向已存在的项目
python -m v1.tests.workflow.cli run \
  --project /path/to/some-cbim-project \
  --prompt my-prompt.md \
  --output run-report.md

# 列出已注册的 prompt generator
python -m v1.tests.workflow.cli list-generators

# 只打印生成的 prompt（不调 claude）
python -m v1.tests.workflow.cli generate --project /path --generator static --prompt foo.md
```

加 `--project` 即跳过新装路径、指向已有 CBIM 项目；跑完不清理。

## 结果与历史

- `results/report-NNN.md` —— 入 git（历史是项目资产）
- `results/report-NNN/` —— 每 case 的 session log + 原始 pytest 输出；**gitignore**（体积大、噪声多）。见 `.gitignore`

报告编号单调递增，不重用。

## 添加新 case

1. 在 `prompts/<loop>_<flavor>.md` 加新 prompt 文件
2. 在 `test_loop_<loop>.py` 加测试函数（仿现有 2 个的形态）。接 `workflow_target: TmpProject` fixture，调 `framework.run(target, prompt)`
3. 如果断言形态是新的，扩 `framework/log_assert.py` 里对应的 `assert_<loop>_loop`

Prompt 保持狭窄：每 case 验一个可证伪的行为。

## 添加新 prompt generator

1. 写一个实现 `PromptGenerator` Protocol 的类（含 `name` / `description` / `generate(target) -> str`）
2. 在模块 import 时调 `framework.generators.register(my_generator)`（仿 `framework/generators/static.py`）
3. CLI 的 `list-generators` 自动显示；`run --generator` 按名字索引
