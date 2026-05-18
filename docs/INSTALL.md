# INSTALL.md — 安装指南

## 两种安装方式

### 方式一：AI Agent 一键安装（推荐）

把下面 **"SOP 正文"** 一节（从 `# 任务` 到文末）整段复制，粘贴到**目标项目**里的 Claude Code 对话框作为单条消息发送。

Agent 会逐步执行，遇到需要确认的节点（文件覆盖、API key）会主动询问你。

### 方式二：手动安装

**前提**：Python ≥ 3.10，git 可用。

```bash
# 1. 克隆模板到临时目录
git clone https://github.com/nan023062/agent-team-cc.git /tmp/agent-team-cc-src
SRC=/tmp/agent-team-cc-src
TARGET=$(pwd)   # 你的目标项目根目录

# 2. 创建必要目录
mkdir -p "$TARGET/.claude" "$TARGET/.claude/hooks" "$TARGET/.claude/skills" "$TARGET/memory"

# 3. 复制文件
cp "$SRC/template/CLAUDE-template.md"  "$TARGET/CLAUDE.md"
cp "$SRC/template/skills/memory/.env.example"        "$TARGET/.env.example"
cp -R "$SRC/template/agents"           "$TARGET/.claude/agents"
cp -R "$SRC/template/commands"         "$TARGET/.claude/commands"
cp -R "$SRC/template/hooks"            "$TARGET/.claude/hooks"
cp -R "$SRC/template/skills"           "$TARGET/.claude/skills"
cp    "$SRC/.claude/settings.json"     "$TARGET/.claude/settings.json"
cp    "$SRC/template/skills/memory/scripts/memory_index.py"  "$TARGET/memory/"
cp    "$SRC/template/skills/memory/scripts/memory_query.py"  "$TARGET/memory/"
cp    "$SRC/template/skills/memory/scripts/requirements.txt" "$TARGET/memory/"

# 4. 合并 .gitignore（确保这几条存在）
# chroma_db/  .env  .venv/
# 注意：memory/entries/ 是明文文件，可提交 git，无需 gitignore

# 5. 创建虚拟环境并装依赖
cd "$TARGET"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r memory/requirements.txt

# 6. 配置 .env
cp .env.example .env
# 编辑 .env，把 ANTHROPIC_API_KEY 替换为你的真实 key（sk-ant-...）

# 7. 清理
rm -rf /tmp/agent-team-cc-src
```

完成后在项目根目录运行 `claude`，首句推荐：**"请初始化本项目的模块知识体系"**

---

## 安装白名单（说明）

只安装运行时必需的文件，不污染目标项目：

| 来源（模板仓库） | 目标路径 | 说明 |
|----------------|---------|------|
| `template/CLAUDE-template.md` | `CLAUDE.md` | 助手身份 |
| `template/skills/memory/.env.example` | `.env.example` | 记忆系统环境变量模板 |
| `template/agents/` | `.claude/agents/` | 4 类 agent 定义和 skills |
| `template/commands/` | `.claude/commands/` | slash 命令 |
| `template/hooks/` | `.claude/hooks/` | 记忆 hook 脚本（读/写自动化） |
| `template/skills/` | `.claude/skills/` | 主 agent skills（memory/SKILL.md 为记忆接口） |
| `.claude/settings.json` | `.claude/settings.json` | 权限配置 + hook 注册 |
| `template/skills/memory/scripts/memory_index.py` | `memory/memory_index.py` | 构建向量索引 |
| `template/skills/memory/scripts/memory_query.py` | `memory/memory_query.py` | 向量查询（返回文件路径） |
| `template/skills/memory/scripts/requirements.txt` | `memory/requirements.txt` | Python 依赖 |

**不安装**：`.git/`、`README.md`、`INSTALL.md`、`ARCHITECTURE.md`、`aimodule-convention.md`、`.claude/settings.local.json`

> `memory/entries/` 是明文 markdown，可直接提交 git，无需特殊处理。

---

## SOP 正文

> 以下内容供 AI agent 执行。直接复制从 `# 任务` 开始的全部内容粘贴给 Claude Code。

```markdown
# 任务：在本项目安装 agent-team-cc 框架

执行下面的步骤，中途如遇阻塞或不确定，停下来向用户确认。所有命令默认在用户当前项目根目录执行。

## 前置检查

1. 运行 `pwd && ls -la`，向用户确认这就是要安装框架的目标目录。
2. 运行 `python3 --version`，确认 Python ≥ 3.10。否则提示用户先装 Python。
3. 运行 `git --version`，确认 git 可用。

## 步骤 1：拉取模板到临时目录

```bash
rm -rf /tmp/agent-team-cc-src
git clone https://github.com/nan023062/agent-team-cc.git /tmp/agent-team-cc-src
```

## 步骤 2：按白名单复制运行时必需文件

**只**复制下面这份明确列表中的文件，不要批量 `cp -R` 整个仓库。
对每一项，若目标已存在同名文件/目录，**停下来向用户确认**（覆盖 / 跳过 / 备份后覆盖），不要默默覆盖。

白名单：
```
template/CLAUDE-template.md      → CLAUDE.md
template/skills/memory/.env.example            → .env.example
template/agents/                 → .claude/agents/
template/commands/               → .claude/commands/
template/hooks/                  → .claude/hooks/
template/skills/                 → .claude/skills/
.claude/settings.json            → .claude/settings.json
template/skills/memory/scripts/memory_index.py   → memory/memory_index.py
template/skills/memory/scripts/memory_query.py   → memory/memory_query.py
template/skills/memory/scripts/requirements.txt  → memory/requirements.txt
```

参考写法（请逐项确认目标是否存在再决定动作）：

```bash
TARGET=<用户确认的目标目录绝对路径>
SRC=/tmp/agent-team-cc-src

mkdir -p "$TARGET/.claude" "$TARGET/.claude/hooks" "$TARGET/.claude/skills" "$TARGET/memory"

# 顶层
cp -i "$SRC/template/CLAUDE-template.md" "$TARGET/CLAUDE.md"
cp -i "$SRC/template/skills/memory/.env.example"       "$TARGET/.env.example"

# .claude/（不要碰 settings.local.json）
cp -R "$SRC/template/agents"          "$TARGET/.claude/agents"
cp -R "$SRC/template/commands"        "$TARGET/.claude/commands"
cp -R "$SRC/template/hooks"           "$TARGET/.claude/hooks"
cp -R "$SRC/template/skills"          "$TARGET/.claude/skills"
cp -i "$SRC/.claude/settings.json"    "$TARGET/.claude/settings.json"

# memory/（工具脚本）
cp -i "$SRC/template/skills/memory/scripts/memory_index.py"  "$TARGET/memory/"
cp -i "$SRC/template/skills/memory/scripts/memory_query.py"  "$TARGET/memory/"
cp -i "$SRC/template/skills/memory/scripts/requirements.txt" "$TARGET/memory/"
```

> `cp -i` 在目标存在时会询问；若在非交互环境，请先 `[ -e ... ]` 判断后停下来问用户。

执行完毕后 `ls -la "$TARGET"` 给用户确认结构。

## 步骤 3：合并 `.gitignore` 条目

确保下列条目存在于目标 `.gitignore`（缺哪条加哪条，**不要覆盖**目标已有内容）：

```
memory/chroma_db/
.env
.venv/
```

目标若没有 `.gitignore`，直接创建一个只含上述条目的文件。

> `memory/entries/` 是明文 markdown，可提交 git，无需 gitignore。

## 步骤 4：创建虚拟环境并装依赖

Homebrew Python 不允许全局 pip 安装，必须用 venv（skill 内的命令前缀就是 `.venv/bin/python`）：

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r memory/requirements.txt
```

验证：
```bash
.venv/bin/python -c "import chromadb; print('chromadb', chromadb.__version__, 'OK')"
```

预期输出 `chromadb 1.x.x OK`。失败则报告错误，停下来等用户处理。

## 步骤 5：创建 `.env`

```bash
[ -e .env ] || cp .env.example .env
```

如果 `.env` 已存在，不要覆盖，直接告知用户检查内容是否含 `ANTHROPIC_API_KEY`。

新创建的 `.env`：
1. 向用户索要 `ANTHROPIC_API_KEY`（`sk-ant-...` 开头），拿到后写入；或
2. 用户暂不提供 → 保留 `your-anthropic-api-key` 占位符，**最终汇报必须明确告知用户须自己填写**才能启动。

**绝不**把真实 API key 写入任何被 git 追踪的文件，也不要回显到日志。

ChromaDB 默认本地 `./chroma_db/`，`CHROMA_HOST/PORT` 保持注释。如用户需团队共享，改为取消注释并填写。

## 步骤 6：清理临时目录

```bash
rm -rf /tmp/agent-team-cc-src
```

## 步骤 7：最终汇报

向用户简明汇报：
- 已安装文件清单（对照白名单逐项确认）
- `.venv` 已创建、`chromadb` 版本号
- `.env` 状态（已填真实 key / 仍是占位符，**后者必须明确提示用户去填**）
- 下一步：在本目录运行 `claude`，主 session 即助手；首句推荐"请初始化本项目的模块知识体系"

## 失败处理

- 任何步骤失败，**不要继续**。报告失败原因 + 已完成步骤，等用户决定回滚还是修正。
- 不要执行 `git push`、`git commit`、`rm -rf` 用户文件等不可逆操作，除非用户明确同意。
- 不要把 API key 写入任何被 git 追踪的文件。
```
