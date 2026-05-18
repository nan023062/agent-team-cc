# INSTALL.md — 安装指南

## 前提

- Python 3.10+
- Git
- Claude Code CLI（`npm install -g @anthropic-ai/claude-code` 或参考官方文档）

---

## 方式一：自动安装（推荐）

将本仓库克隆（或复制）到目标项目根目录，然后运行安装脚本：

**macOS / Linux：**
```bash
python cbim/install.py
```

**Windows：**
```
双击 cbim/install.bat
```

脚本自动完成以下步骤：

| 步骤 | 动作 |
|------|------|
| 1 | 创建 `.venv` 虚拟环境 |
| 2 | 安装 `cbim/memory/engine/requirements.txt`（chromadb） |
| 3 | 复制 `cbim/cc-template/agents/` → `.claude/agents/` |
| 4 | 注册 Claude Code hooks 到 `.claude/settings.json` |
| 5 | 初始化 `CLAUDE.md`（从 `cbim/cc-template/CLAUDE-template.md`） |
| 6 | 创建 `cbim/memory/store/{short,medium}/` 目录 |
| 7 | 补全 `.gitignore`（`cbim/memory/store/`、`.venv/`、`__pycache__/`） |

脚本幂等：已存在的文件/目录自动跳过，不覆盖。

---

## 方式二：手动安装

```bash
TARGET=$(pwd)   # 目标项目根目录
CBIM="$TARGET/cbim"

# 1. 虚拟环境
python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install -q -r "$CBIM/memory/engine/requirements.txt"

# 2. 复制 agent 定义
mkdir -p "$TARGET/.claude/agents"
cp -r "$CBIM/cc-template/agents/." "$TARGET/.claude/agents/"

# 3. 注册 hooks（写入 .claude/settings.json）
#    Stop hook:         python cbim/cc-template/hooks/write-memory.py
#    SessionStart hook: python cbim/cc-template/hooks/load-memory.py

# 4. CLAUDE.md
cp "$CBIM/cc-template/CLAUDE-template.md" "$TARGET/CLAUDE.md"

# 5. 记忆目录
mkdir -p "$CBIM/memory/store/short" "$CBIM/memory/store/medium"

# 6. .gitignore 补充
echo -e "\ncbim/memory/store/\n.venv/\n__pycache__/\n*.pyc\n.env" >> "$TARGET/.gitignore"
```

**Windows（PowerShell）：**
```powershell
python cbim\install.py
```

---

## 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填写：
# ANTHROPIC_API_KEY=sk-ant-...
```

`.env` 已在 `.gitignore`，不会被提交。

---

## 启动

```bash
claude
```

首句推荐：**"请初始化本项目的模块知识体系"**

助手会派发架构师在项目根建立 `.dna/` 知识体系。

---

## AI Agent 一键安装（SOP）

将以下内容复制到**目标项目**的 Claude Code 对话框，作为单条消息发送。Agent 会逐步执行，遇到需要确认的节点会主动询问。

```markdown
# 任务：在本项目安装 CBIM 框架

执行下面的步骤，中途如遇阻塞或不确定，停下来向用户确认。所有命令默认在用户当前项目根目录执行。

## 前置检查

1. 运行 `pwd && ls`，向用户确认这就是要安装框架的目标目录。
2. 确认 `cbim/` 目录存在（框架已随项目提交）。
3. 运行 `python3 --version`，确认 Python ≥ 3.10。

## 步骤 1：运行安装脚本

```bash
python cbim/install.py
```

Windows 环境改为：双击 `cbim/install.bat`，或在 PowerShell 执行 `python cbim\install.py`。

脚本输出应显示各步骤 `+` 标记，最后打印 `Done. Restart Claude Code to activate hooks.`

如果脚本失败，报告错误原因，停下来等用户处理。

## 步骤 2：配置 .env

```bash
[ -e .env ] || cp .env.example .env
```

如果 `.env` 已存在，检查是否含 `ANTHROPIC_API_KEY`，有则跳过。

新创建的 `.env`：
- 向用户索要 `ANTHROPIC_API_KEY`（`sk-ant-...` 开头），拿到后写入；
- 用户暂不提供 → 保留占位符，最终汇报必须明确告知用户须自行填写才能启动。

**绝不**把真实 API key 写入任何被 git 追踪的文件。

## 步骤 3：验证安装

运行以下命令检查关键文件：

```bash
ls CLAUDE.md .claude/agents/ .venv/ cbim/memory/store/
```

全部存在则安装成功。

## 步骤 4：最终汇报

向用户简明汇报：
- 安装状态（成功 / 哪步失败）
- `.venv` 已创建，chromadb 版本号
- `.env` 状态（已填真实 key / 仍是占位符，后者必须明确提示用户去填）
- 下一步：在本目录运行 `claude`，首句推荐"请初始化本项目的模块知识体系"

## 失败处理

- 任何步骤失败，不要继续。报告失败原因 + 已完成步骤，等用户决定。
- 不要执行 `git push`、`git commit`、`rm -rf` 用户文件等不可逆操作。
- 不要把 API key 写入任何被 git 追踪的文件。
```

---

## 安装后目录结构

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
├── .env                           ← API Key（gitignore）
├── .venv/                         ← Python 虚拟环境（gitignore）
├── .claude/
│   ├── settings.json              ← 权限配置 + hook 注册
│   └── agents/
│       ├── architect/
│       ├── hr/
│       ├── auditor/
│       └── programmer/
└── cbim/                          ← 框架本体（已随项目提交）
    ├── memory/store/              ← 本地记忆（gitignore）
    └── ...
```

## 常见问题

**Q：`.venv` 创建失败？**
确认 Python ≥ 3.10：`python3 --version`。Windows 上可能需要 `python` 替换 `python3`。

**Q：chromadb 安装报错？**
确保 pip 版本最新：`python -m pip install --upgrade pip`，再重跑 `install.py`。

**Q：Hooks 不生效？**
安装后必须**重启** Claude Code（完全退出再进入），hooks 需要新会话才能加载。

**Q：换其他项目目录部署，还要重做 venv 吗？**
是的。每个部署项目根都需要自己的 `.venv`。`cbim/` 框架目录本身随项目一起移动即可。
