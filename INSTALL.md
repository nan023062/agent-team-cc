# CBIM 安装指南

在目标项目里打开 Claude Code，把下面 **"SOP 正文"** 一节（从 `---` 分隔线到文末）整段复制，粘贴为一条消息发送即可。Claude Code 会自动完成全部安装步骤。

> **前提**：目标项目已有 Git 仓库，Python ≥ 3.10，网络可访问 GitHub。

---

# 任务：将 CBIM 多 Agent 框架安装到本项目

请按以下步骤逐一执行，遇到阻塞或不确定时停下来向用户确认，不要静默跳过。

## 第 0 步 — 确认目标目录

运行以下命令，向用户展示当前目录内容，确认这就是要安装框架的项目根目录：

```bash
pwd && ls
```

如果用户说目录不对，停下来等用户 `cd` 到正确位置后再继续。

## 第 1 步 — 检查前提条件

```bash
python3 --version
git --version
```

- Python 版本必须 ≥ 3.10，否则提示用户先升级 Python。
- git 必须可用。

## 第 2 步 — 下载 CBIM 框架

将 CBIM 仓库直接克隆到当前项目的 `cbim/` 目录：

```bash
git clone https://github.com/nan023062/cbim.git cbim
```

Windows 环境（PowerShell）：
```powershell
git clone https://github.com/nan023062/cbim.git cbim
```

如果 `cbim/` 目录已存在，停下来向用户确认是否覆盖（可先删除再克隆）。

## 第 3 步 — 运行安装脚本

```bash
python3 cbim/install.py
```

Windows：
```powershell
python cbim\install.py
```

脚本会自动完成：
- 创建 `.venv` 虚拟环境
- 安装 chromadb 依赖
- 复制 agent 定义到 `.claude/agents/`
- 注册 SessionStart / Stop hooks 到 `.claude/settings.json`
- 初始化 `CLAUDE.md`
- 创建记忆目录 `cbim/memory/store/{short,medium}/`
- 补全 `.gitignore`

脚本每步输出 `+`（完成）或 `-`（跳过/已存在），最后打印 `Done. Restart Claude Code to activate hooks.`

如果脚本报错，停下来向用户报告错误内容，不要继续。

## 第 4 步 — 配置 API Key

检查是否已有 `.env` 文件：

```bash
ls .env 2>/dev/null || cp .env.example .env
```

Windows：
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

询问用户：
1. 是否已有 `ANTHROPIC_API_KEY`？格式为 `sk-ant-...`
2. 如果有，将其写入 `.env` 文件（**绝不**将 key 写入任何被 git 追踪的文件）
3. 如果暂时没有，保留占位符，**必须明确告知用户后续需要自行填写才能启动**

## 第 5 步 — 清理临时目录

```bash
rm -rf /tmp/cbim-install-src
```

Windows：
```powershell
Remove-Item -Recurse -Force "$env:TEMP\cbim-install-src"
```

## 第 6 步 — 验证安装

运行以下检查，向用户展示结果：

```bash
ls CLAUDE.md cbim/ .claude/agents/ .venv/
python3 -c "import chromadb; print('chromadb', chromadb.__version__, 'OK')"
```

全部存在且 chromadb 可导入，则安装成功。

## 第 7 步 — 最终汇报

向用户简明汇报：

1. ✅/❌ 各步骤结果
2. chromadb 版本号
3. `.env` 状态（已填写真实 key / 仍是占位符——**后者必须明确提醒**）
4. **下一步操作**：
   - 完全退出并重启 Claude Code（必须重启才能激活 hooks）
   - 重启后首句推荐：**"请初始化本项目的模块知识体系"**
   - 助手会派发架构师建立 `.dna/` 项目知识体系，之后即可正常使用

## 失败处理原则

- 任何步骤失败 → 立即停止，报告失败原因和已完成步骤，等待用户决定
- 不执行 `git push`、`git commit`、`rm -rf 用户已有文件` 等不可逆操作（除非用户明确要求）
- 不将 API key 写入任何被 git 追踪的文件
