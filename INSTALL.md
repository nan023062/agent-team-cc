# INSTALL.md — Agent-driven 安装 SOP

> 这份文档是给 **AI agent** 执行的安装 SOP,不是给人读的教程。
> 用法:把下面 `## SOP 正文` 整段(从 `# 任务` 到末尾)复制,粘贴到目标项目里的 Claude Code 或其他 AI agent 对话框,作为单条消息发送。
> agent 会逐步执行,关键节点(覆盖确认、API key)会向你提问。
>
> 人类用户想手动安装,看 `README.md` 的"快速开始"节即可。

---

## 设计原则

只安装运行时必需的文件,不污染目标项目:

**装(运行时必需)**
- `CLAUDE.md` — 秘书身份
- `.claude/agents/` — 4 类 agent 定义和 skills(记忆系统约定 `memory-convention.md` 已内置在架构师 skill 目录下)
- `.claude/commands/` — slash 命令
- `.claude/settings.json` — 权限配置
- `tools/chroma_write.py` / `chroma_query.py` / `requirements.txt` — 记忆系统
- `.env.example` — 环境变量模板

**不装(模板自身的元文档)**
- `README.md`、`INSTALL.md`、`tools/README.md` — 模板自身说明
- `ARCHITECTURE.md`、`aimodule-convention.md` — 介绍框架本身的架构文档
- `.git/` — 不污染目标项目的 git 历史
- `.gitignore` — 按条目合并到目标已有 `.gitignore`,不覆盖
- `.claude/settings.local.json` — 用户本地权限,保留目标已有

---

## SOP 正文

```markdown
# 任务:在本项目安装 agent-team-cc 框架

执行下面的步骤,中途如遇阻塞或不确定,停下来向用户确认。所有命令默认在用户当前项目根目录执行。

## 前置检查

1. 运行 `pwd && ls -la`,向用户确认这就是要安装框架的目标目录。
2. 运行 `python3 --version`,确认 Python ≥ 3.10。否则提示用户先装 Python。
3. 运行 `git --version`,确认 git 可用。

## 步骤 1:拉取模板到临时目录

```bash
rm -rf /tmp/agent-team-cc-src
git clone https://github.com/nan023062/agent-team-cc.git /tmp/agent-team-cc-src
```

## 步骤 2:按白名单复制运行时必需文件

**只**复制下面这份明确列表中的文件,不要批量 `cp -R` 整个仓库。
对每一项,若目标已存在同名文件/目录,**停下来向用户确认**(覆盖 / 跳过 / 备份后覆盖),不要默默覆盖。

白名单:
```
CLAUDE.md
.env.example
.claude/agents/             (整个目录,含架构师 skill 内的 memory-convention.md)
.claude/commands/           (整个目录)
.claude/settings.json
tools/chroma_write.py
tools/chroma_query.py
tools/requirements.txt
```

明确**不要**复制的内容:
- `.git/`(不污染目标 git 历史)
- `README.md`、`INSTALL.md`、`tools/README.md`(模板自身说明)
- `ARCHITECTURE.md`、`aimodule-convention.md`(介绍框架本身的根目录文档)
- `.claude/settings.local.json`(用户本地权限,保留目标已有)
- `.gitignore`(按条目合并,见步骤 3)

参考写法(请逐项确认目标是否存在再决定动作):

```bash
TARGET=<用户确认的目标目录绝对路径>
SRC=/tmp/agent-team-cc-src

mkdir -p "$TARGET/.claude" "$TARGET/tools"

# 顶层
cp -i "$SRC/CLAUDE.md"     "$TARGET/"
cp -i "$SRC/.env.example"  "$TARGET/"

# .claude/(不要碰 settings.local.json)
cp -R "$SRC/.claude/agents"        "$TARGET/.claude/"
cp -R "$SRC/.claude/commands"      "$TARGET/.claude/"
cp -i "$SRC/.claude/settings.json" "$TARGET/.claude/"

# tools/(只 3 个文件,不要复制 tools/README.md)
cp -i "$SRC/tools/chroma_write.py"  "$TARGET/tools/"
cp -i "$SRC/tools/chroma_query.py"  "$TARGET/tools/"
cp -i "$SRC/tools/requirements.txt" "$TARGET/tools/"
```

> `cp -i` 在目标存在时会询问;若 agent 在非交互环境下执行,请先 `[ -e ... ]` 判断后停下来问用户。

执行完毕后 `ls -la "$TARGET"` 给用户确认结构。

## 步骤 3:合并 `.gitignore` 条目

确保下列条目存在于目标 `.gitignore`(缺哪条加哪条,**不要覆盖**目标已有内容):

```
chroma_db/
memory/entries/
.env
.venv/
```

目标若没有 `.gitignore`,直接创建一个只含上述条目的文件。

## 步骤 4:创建虚拟环境并装依赖

Homebrew Python 不允许全局 pip 安装,必须用 venv(skill 内的 chroma 命令前缀就是 `.venv/bin/python`):

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r tools/requirements.txt
```

验证:
```bash
.venv/bin/python -c "import chromadb; print('chromadb', chromadb.__version__, 'OK')"
```

预期输出 `chromadb 1.x.x OK`。失败则报告错误,停下来等用户处理。

## 步骤 5:创建 `.env`

```bash
[ -e .env ] || cp .env.example .env
```

如果 `.env` 已存在,不要覆盖,直接告知用户检查内容是否含 `ANTHROPIC_API_KEY`。

新创建的 `.env`:
1. 向用户索要 `ANTHROPIC_API_KEY`(`sk-ant-...` 开头),拿到后用 sed/编辑器写入;或
2. 用户暂不提供 → 保留 `your-anthropic-api-key` 占位符,**最终汇报必须明确告知用户须自己填写**才能启动。

**绝不**把真实 API key 写入任何被 git 追踪的文件,也不要回显到日志。

ChromaDB 默认本地 `./chroma_db/`,`CHROMA_HOST/PORT` 保持注释。如用户需团队共享,改为取消注释并填写。

## 步骤 6:清理临时目录

```bash
rm -rf /tmp/agent-team-cc-src
```

## 步骤 7:最终汇报

向用户简明汇报:
- 已安装文件清单(对照白名单逐项确认)
- `.venv` 已创建、`chromadb` 版本号
- `.env` 状态(已填真实 key / 仍是占位符,**后者必须明确提示用户去填**)
- 下一步:在本目录运行 `claude`,主 session 即秘书;首句推荐"请初始化本项目的模块知识体系"

## 失败处理

- 任何步骤失败,**不要继续**。报告失败原因 + 已完成步骤,等用户决定回滚还是修正。
- 不要执行 `git push`、`git commit`、`rm -rf` 用户文件等不可逆操作,除非用户明确同意。
- 不要把 API key 写入任何被 git 追踪的文件。
```
