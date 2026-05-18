# CBIM 安装指南

在目标项目里打开 Claude Code，把下面 **"SOP 正文"** 一节（从 `---` 分隔线到文末）整段复制，粘贴为一条消息发送即可。Claude Code 会自动完成全部安装步骤。

> **前提**：目标项目已有 Git 仓库，Python ≥ 3.10，网络可访问 GitHub。

---

# 任务：将 CBIM 框架安装到本项目

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
- 复制 agent 定义到 `.claude/agents/`
- 注册 SessionStart / Stop hooks 到 `.claude/settings.json`
- 初始化 `CLAUDE.md`
- 创建记忆目录 `cbim/memory/store/{short,medium}/`
- 补全 `.gitignore`

脚本每步输出 `+`（完成）或 `-`（跳过/已存在），最后打印 `Done. Restart Claude Code to activate hooks.`

如果脚本报错，停下来向用户报告错误内容，不要继续。

## 第 4 步 — 验证安装

运行以下检查，向用户展示结果：

```bash
ls CLAUDE.md cbim/ .claude/agents/ .venv/
```

CLAUDE.md、cbim/、.claude/agents/、.venv/ 全部存在则安装成功。

## 第 5 步 — 最终汇报

向用户简明汇报：

1. ✅/❌ 各步骤结果
2. **下一步操作**：
   - 完全退出并重启 Claude Code（必须重启才能激活 hooks）
   - 重启后首句推荐：**"请初始化本项目的模块知识体系"**
   - 助手会派发架构师建立 `.dna/` 项目知识体系，之后即可正常使用

## 失败处理原则

- 任何步骤失败 → 立即停止，报告失败原因和已完成步骤，等待用户决定
- 不执行 `git push`、`git commit`、`rm -rf 用户已有文件` 等不可逆操作（除非用户明确要求）
