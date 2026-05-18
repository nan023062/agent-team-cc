[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

# CBIM — Capability-Business Independence + Memory

> Claude Code 的上下文管理框架。多 Agent 不是團隊模擬，而是按能力維度隔離上下文的機制。

**CBIM** = **CBI**（Capability-Business Independence，能力-業務獨立性）+ **M**（Memory，記憶系統）

## 解決什麼問題

最常見的 Claude Code 工作模式：**一個預設 agent + 大量 CLAUDE.md + 大量 skill**。

這個模式有一個隨時間惡化的結構性問題：隨著對話輪次增加，CLAUDE.md 和 skill 檔案逐漸被全量載入上下文，token 暴增、幻覺概率上升、輸出品質下降，糾正錯誤又進一步污染上下文。

重置 session 能清上下文，卻帶來另一個問題：記憶遺失，需要重新 grep 專案代碼、重新理解結構，沒有結構化的專案知識可以恢復。

CBIM 同時解決這兩個問題：

| 問題 | 解法 |
|------|------|
| 上下文隨輪次暴增 | 多 Agent × 模組拓撲樹：每次任務只載入目標 agent soul + 任務子樹 `.dna/` |
| 重置後記憶遺失 | SessionStart hook 自動注入模組快照 + 近期記憶，重置 session 零成本恢復 |

---

## 設計哲學

核心 = **多 Agent（能力軸）× 模組拓撲樹（業務軸）**

- **能力軸**：多個專精 Agent，每次任務只載入目標 agent 的 soul，無多餘能力上下文
- **業務軸**：`.dna/` 按模組邊界組成拓撲樹，只載入任務所在子樹，無多餘業務上下文
- **記憶**（Memory）：跨會話積累的原始素材 — session 恢復、能力治理（HR 提煉 → skills → soul）、業務治理（架構師提煉 → `.dna/` workflows）的共同來源

每次任務上下文 = 專精 agent soul × 任務子樹 `.dna/`，與專案總規模無關。  
少上下文 → 少幻覺 → 少錯誤 → 少糾正 → 淨 token 低於單體大 agent 方案。

---

## 執行角色（上下文隔離機制）

CBIM 用多個專精 agent 實現能力維度的上下文隔離——每次任務只載入目標 agent 的 soul，無多餘能力上下文。這不是團隊模擬，是上下文控制機制。

```
使用者
  ↓
助手（CLAUDE.md — 唯一對外介面，任務拆解與排程）
  ├── 架構師   業務層治理：設計並維護專案知識體系（.dna/）
  ├── HR       能力層治理：work agent 全生命週期管理
  ├── 評審官   獨立批判審查（對抗性視角，唯讀）
  └── work agents   執行具體任務（按需由 HR 建立）
```

你只需要和助手說話。助手負責理解意圖、拆解任務、路由給目標 agent、匯總結果。

---

## 快速開始

### 方式一：一句話交給 Claude Code（推薦）

在目標專案目錄打開 Claude Code，發送這條訊息，Agent 會自動完成全部安裝步驟：

```
請訪問 https://raw.githubusercontent.com/nan023062/cbim/master/INSTALL.md 獲取 CBIM 安裝 SOP，從第一條分隔線之後的內容開始，在當前專案執行所有步驟完成安裝
```

### 方式二：手動執行安裝腳本

```bash
# 1. 複製 CBIM 到目標專案的 cbim/ 目錄
git clone https://github.com/nan023062/cbim.git cbim

# 2. 執行安裝腳本
python3 cbim/install.py        # macOS / Linux
# 或雙擊 cbim/install.bat      # Windows

# 3. 重啟 Claude Code
claude
```

---

## 安裝後首次使用

重啟 Claude Code 後，發送：

> **"請初始化本專案的模組知識體系"**

助手派發架構師建立 `.dna/` 知識體系，之後即可正常使用。

---

## 後續怎麼用

直接告訴助手要做什麼，不用指定 agent：

| 你想做 | 直接說 |
|--------|--------|
| 初始化知識體系 | 請初始化本專案的模組知識體系 |
| 新建功能模組 | 新建一個 combat 模組 |
| 實現功能 | 按當前藍圖實現登入介面 |
| 審查設計 | 審一下這次改動 |
| 查歷史決策 | 查一下 combat 模組的歷史決策 |
| 招募新 agent | 幫我招募一個 AI 工程師 |

---

## 目錄結構（部署後）

```
your-project/
├── CLAUDE.md                      ← 助手身份（主 session）
├── .venv/                         ← Python 虛擬環境（gitignore）
│
├── .claude/
│   ├── settings.json              ← 權限設定 + hook 註冊
│   └── agents/
│       ├── architect/             ← 架構師
│       ├── hr/                    ← HR
│       ├── auditor/               ← 評審官
│       └── programmer/            ← 程式設計師（預設 work agent）
│
├── .dna/                          ← 專案知識根模組（架構師建立）
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   └── contract.md
│
└── cbim/                          ← 框架本體（git clone 到此目錄）
    ├── install.py                 ← 自動安裝腳本
    ├── install.bat                ← Windows 安裝入口
    ├── cc-template/               ← Claude Code 安裝範本
    ├── knowledge/                 ← 知識庫引擎（能力層 + 業務層 CRUD）
    ├── memory/                    ← 記憶引擎（FileBackend）
    └── preview/                   ← 本地視覺化服務
```

---

## 兩層治理 · 兩類 Skill

| 層級 | 治理者 | 管轄 | 鐵律 |
|------|--------|------|------|
| **能力層** | HR | `.claude/agents/`（soul）+ `cbim/knowledge/skills/`（能力向 skill） | soul/skills 不含任何專案特定內容 |
| **業務層** | 架構師 | 專案各級 `.dna/`（模組知識三件套 + workflows/） | 知識三件套不引用 agent 規範 |

| 類型 | 儲存 | 特徵 |
|------|------|------|
| **能力向 skill** | `cbim/knowledge/skills/` | agent 私有能力，可移植，HR 治理 |
| **業務向 skill** | `.dna/workflows/` | 模組確定性流程，與專案綁定，架構師治理 |

---

## 記憶系統

記憶是三階段蒸餾管道，不只是上下文恢復：

| 階段 | 路徑 | 目的 |
|------|------|------|
| 短期 | `cbim/memory/store/short/` | 原始 session 記錄；提煉後標記 `distilled`，至少保留 3 天後清理 |
| 中期 | `cbim/memory/store/medium/` | 壓縮提煉後的模式摘要；升格至知識層後歸檔 |
| 知識（核心） | `cbim/knowledge/skills/` + `.dna/` | 固化結構：能力進 skills/soul，業務進 workflows |

SessionStart hook 在每次會話開始時自動注入：專案知識快照（模組樹 + agent 清單）+ 上次恢復點 + 近期記憶。

---

## 架構詳解

見 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [docs/ARCHITECTURE.zh-CN.md](docs/ARCHITECTURE.zh-CN.md)

---

## 相依套件

- Python 3.10+
- Claude Code CLI
- 無額外相依（記憶引擎預設使用 FileBackend，純標準函式庫）

---

## License

[MIT](LICENSE)
