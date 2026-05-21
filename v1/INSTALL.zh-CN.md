[English](INSTALL.md) | [中文](INSTALL.zh-CN.md)

# CBIM 安装指南

在目标项目里打开 Claude Code，把下面整段 **"SOP 正文"**（从 `---` 分隔线到文末）作为一条消息粘贴进去。Claude Code 会自动完成全部安装步骤。

> **前置条件**：目标项目已有 Git 仓库、Python ≥ 3.10、能访问 GitHub 的网络。

---

# 任务：在当前项目中安装 CBIM 框架

这是**复制式安装** —— 不运行任何 installer 脚本。把源仓库 clone 到临时目录，把四件套复制到目标项目，创建 venv，完成。

逐步执行以下步骤。遇到阻塞或不确定时**停下来请用户确认**，不要静默跳过。

## Step 0 —— 确认目标目录

```bash
pwd && ls
```

把当前目录内容展示给用户，确认这是项目根。若错了，停下来等用户 `cd` 到正确位置。

## Step 1 —— 检查前置条件

```bash
python3 --version
git --version
```

- Python 必须 ≥ 3.10。
- 必须有 Git。

## Step 2 —— 把源仓库 clone 到临时目录

Linux / macOS：
```bash
TMP=$(mktemp -d)
git clone --depth=1 --branch master https://github.com/nan023062/cbim.git "$TMP/src"
```

Windows (PowerShell)：
```powershell
$TMP = (New-Item -ItemType Directory -Path ([System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid())).FullName
git clone --depth=1 --branch master https://github.com/nan023062/cbim.git "$TMP\src"
```

校验 clone 出来的四件套都在：
```bash
ls "$TMP/src/.cbim" "$TMP/src/.claude" "$TMP/src/CLAUDE.md" "$TMP/src/.claudeignore"
```

如果有缺失，停下来上报 —— 上游仓库不完整。

## Step 3 —— 安装四件套（merge-aware）

两件套整洁覆盖；两件套合并，以保留用户数据。

| 件套 | 策略 | 原因 |
|---|---|---|
| `.cbim/` | 整洁替换，**保留** `memory/{short,medium,last-session.md}`、`index.md`、`config.json` | 框架文件必须与上游一致；运行时数据必须保留 |
| `.claude/agents/` | 整洁替换 | agents 由框架定义 |
| `.claude/settings.json` | **合并** —— 只覆盖 `hooks` 和 `permissions` 键 | 保留用户添加的 MCP servers、env、model、theme、自定义 permissions |
| `CLAUDE.md` | 覆盖；若与原内容不同则备份到 `CLAUDE.md.bak` | 模板归框架所有 |
| `.claudeignore` | **逐行 append-if-missing** | 保留用户添加的 ignore 规则 |

### 3a. 备份运行时数据和 CLAUDE.md

Linux / macOS：
```bash
[ -d .cbim/memory ] && cp -r .cbim/memory "$TMP/_memory_bak"
[ -f .cbim/index.md ]     && cp    .cbim/index.md     "$TMP/_index_bak"
[ -f .cbim/config.json ]  && cp    .cbim/config.json  "$TMP/_config_bak"
[ -f CLAUDE.md ] && cp CLAUDE.md "$TMP/_claude_md_bak"
```

Windows (PowerShell)：
```powershell
if (Test-Path .cbim\memory) { Copy-Item -Recurse .cbim\memory "$TMP\_memory_bak" }
if (Test-Path .cbim\index.md)     { Copy-Item          .cbim\index.md     "$TMP\_index_bak" }
if (Test-Path .cbim\config.json)  { Copy-Item          .cbim\config.json  "$TMP\_config_bak" }
if (Test-Path CLAUDE.md) { Copy-Item CLAUDE.md "$TMP\_claude_md_bak" }
```

### 3b. 整洁替换框架 + agents

Linux / macOS：
```bash
rm -rf .cbim .claude/agents
mkdir -p .claude
cp -R "$TMP/src/.cbim"   .cbim
cp -R "$TMP/src/.claude/agents" .claude/agents
```

Windows (PowerShell)：
```powershell
Remove-Item -Recurse -Force .cbim, .claude\agents -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path .claude | Out-Null
Copy-Item -Recurse "$TMP\src\.cbim"   .cbim
Copy-Item -Recurse "$TMP\src\.claude\agents" .claude\agents
```

### 3c. 还原运行时数据 + 确保必需目录存在

`.cbim/memory/{short,medium}/` 和 `.cbim/index.md` 是 gitignored 或运行时管理的，不会出现在 clone 里 —— 缺失时创建即可。

Linux / macOS：
```bash
# 还原备份的数据
[ -d "$TMP/_memory_bak" ] && { rm -rf .cbim/memory; cp -r "$TMP/_memory_bak" .cbim/memory; }
[ -f "$TMP/_index_bak" ]  && cp "$TMP/_index_bak"  .cbim/index.md
[ -f "$TMP/_config_bak" ] && cp "$TMP/_config_bak" .cbim/config.json

# 确保必需的运行时目录/文件存在（已还原时为 no-op）
mkdir -p .cbim/memory/short .cbim/memory/medium
[ -f .cbim/index.md ]    || printf "# Module Index\n" > .cbim/index.md
[ -f .cbim/config.json ] || printf '{\n  "memory": {\n    "short_term": {"keep_days": 3}\n  }\n}\n' > .cbim/config.json
```

Windows (PowerShell)：
```powershell
if (Test-Path "$TMP\_memory_bak") { Remove-Item -Recurse -Force .cbim\memory -ErrorAction SilentlyContinue; Copy-Item -Recurse "$TMP\_memory_bak" .cbim\memory }
if (Test-Path "$TMP\_index_bak")  { Copy-Item "$TMP\_index_bak"  .cbim\index.md }
if (Test-Path "$TMP\_config_bak") { Copy-Item "$TMP\_config_bak" .cbim\config.json }

New-Item -ItemType Directory -Force -Path .cbim\memory\short, .cbim\memory\medium | Out-Null
if (-not (Test-Path .cbim\index.md))    { Set-Content -Path .cbim\index.md    -Value "# Module Index" -NoNewline; Add-Content -Path .cbim\index.md -Value "" }
if (-not (Test-Path .cbim\config.json)) { Set-Content -Path .cbim\config.json -Value '{"memory":{"short_term":{"keep_days":3}}}' }
```

### 3d. 合并 .claude/settings.json（保留用户键）

只替换 `hooks` 和 `permissions`；其余（MCP servers、env、model、theme 等）保持不动。

```bash
python3 - "$TMP/src/.claude/settings.json" .claude/settings.json <<'PY'
import json, sys
from pathlib import Path
src = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
dst_path = Path(sys.argv[2])
dst = json.loads(dst_path.read_text(encoding="utf-8")) if dst_path.exists() else {}
dst["hooks"] = src["hooks"]
dst["permissions"] = src["permissions"]
dst_path.parent.mkdir(parents=True, exist_ok=True)
dst_path.write_text(json.dumps(dst, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"merged hooks + permissions into {dst_path}")
PY
```

（Windows 上同一条命令也能跑 —— 把 `python3` 换成 `python` 即可。）

### 3e. CLAUDE.md（覆盖并备份）

```bash
if [ -f "$TMP/_claude_md_bak" ] && ! cmp -s "$TMP/_claude_md_bak" "$TMP/src/CLAUDE.md"; then
  cp "$TMP/_claude_md_bak" CLAUDE.md.bak
fi
cp "$TMP/src/CLAUDE.md" CLAUDE.md
```

Windows (PowerShell)：
```powershell
if (Test-Path "$TMP\_claude_md_bak") {
  $srcHash = (Get-FileHash "$TMP\src\CLAUDE.md").Hash
  $bakHash = (Get-FileHash "$TMP\_claude_md_bak").Hash
  if ($srcHash -ne $bakHash) { Copy-Item "$TMP\_claude_md_bak" CLAUDE.md.bak }
}
Copy-Item "$TMP\src\CLAUDE.md" CLAUDE.md
```

### 3f. .claudeignore（逐行 append-if-missing）

```bash
SRC_IGNORE="$TMP/src/.claudeignore"
touch .claudeignore
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  grep -qxF -- "$line" .claudeignore || printf "%s\n" "$line" >> .claudeignore
done < "$SRC_IGNORE"
```

Windows (PowerShell)：
```powershell
if (-not (Test-Path .claudeignore)) { New-Item -ItemType File -Path .claudeignore | Out-Null }
$existing = Get-Content .claudeignore -ErrorAction SilentlyContinue
Get-Content "$TMP\src\.claudeignore" | ForEach-Object {
  if ($_ -and ($existing -notcontains $_)) { Add-Content -Path .claudeignore -Value $_ }
}
```

## Step 4 —— 创建虚拟环境 + 安装 MCP SDK

钩子和 CLI 引擎只用标准库，无依赖。**MCP server**（`.claude/settings.json` 里的 `mcpServers.cbim`）需要 `mcp` 包。

Linux / macOS：
```bash
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r .cbim/mcp_server/requirements.txt
```

Windows (PowerShell)：
```powershell
if (-not (Test-Path .venv)) { python -m venv .venv }
.venv\Scripts\pip install -q -r .cbim\mcp_server\requirements.txt
```

settings.json 中 MCP server 的注册项调用 `python .cbim/mcp_server/server.py`。启动 Claude Code 之前先激活 venv（`source .venv/bin/activate` / `.venv\Scripts\Activate.ps1`），让 `python` 解析到带有 `mcp` SDK 的 venv 解释器。或者把 `mcp` 装到 PATH 上的全局 Python 里。

## Step 5 —— 更新 .gitignore

缺失则追加这些行：
```
.cbim/memory/short/
.cbim/memory/medium/
.cbim/memory/last-session.md
.cbim/memory/.chroma/
__pycache__/
*.pyc
.venv/
```

Linux / macOS 单行命令：
```bash
touch .gitignore
for line in '.cbim/memory/short/' '.cbim/memory/medium/' '.cbim/memory/last-session.md' '.cbim/memory/.chroma/' '__pycache__/' '*.pyc' '.venv/'; do
  grep -qxF -- "$line" .gitignore || printf "%s\n" "$line" >> .gitignore
done
```

## Step 6 —— 验证

```bash
ls CLAUDE.md .cbim/ .claude/agents/ .claude/settings.json .claudeignore .venv/ .cbim/index.md .cbim/memory/short .cbim/memory/medium
```

所有路径都必须存在。

## Step 7 —— 清理

```bash
rm -rf "$TMP"
```

Windows：
```powershell
Remove-Item -Recurse -Force "$TMP"
```

## Step 8 —— 最终汇报

向用户简要汇报：

1. ✅/❌ 每个步骤的结果
2. **下一步**：
   - 完全退出并重启 Claude Code（激活钩子所必需）
   - 重启后推荐的第一条消息：**"请初始化本项目的模块知识体系"**
   - 助手会派发架构师构建 `.dna/` 项目知识体系

## 失败处理原则

- 任何步骤失败 → 立即停止，上报失败原因和已完成步骤，等用户决定
- 不要执行 `git push`、`git commit`、对用户文件的 `rm -rf` 等不可逆操作（除非用户明确要求）
- 若 clone 出来的源仓库缺少 `.cbim/`、`.claude/`、`CLAUDE.md` 或 `.claudeignore`，中止 —— 上游仓库必须把这四件套提交进去，复制式安装才能跑通
