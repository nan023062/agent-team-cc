"""
previewer.py — Generate a self-contained HTML preview of all memory entries.

Scans store/short/ and store/medium/, embeds all entries as JSON,
and produces a single HTML file that works offline with no external deps.
"""

import json
import re
from pathlib import Path

from .engine import TIERS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_html(store_dir: Path) -> str:
    """Return full HTML string for the memory preview page."""
    entries = _collect_entries(store_dir)
    data = json.dumps(entries, ensure_ascii=False)
    stats = _stats(entries)
    return _HTML_TEMPLATE.format(data=data, **stats)


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect_entries(store_dir: Path) -> list[dict]:
    entries = []
    for tier in TIERS:
        tier_dir = store_dir / tier
        if not tier_dir.exists():
            continue
        for md_file in sorted(tier_dir.glob("*.md"), reverse=True):
            entries.append(_parse_entry(md_file, tier))
    return entries


def _parse_entry(path: Path, tier: str) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        raw = ""

    meta = _parse_frontmatter(raw)
    body = _strip_frontmatter(raw)
    title = _extract_title(body, path.name)

    return {
        "id": path.name,
        "path": str(path),
        "tier": tier,
        "date": meta.get("date") or _date_from_name(path.name),
        "keyword": meta.get("keyword", ""),
        "type": meta.get("type", ""),
        "modules": meta.get("modules", ""),
        "sources": meta.get("sources", ""),
        "title": title,
        "body": body,
        "meta": meta,
    }


def _parse_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:80]
        if line.startswith("## "):
            return line[3:].strip()
    return fallback


def _date_from_name(name: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def _stats(entries: list[dict]) -> dict:
    short = sum(1 for e in entries if e["tier"] == "short")
    medium = sum(1 for e in entries if e["tier"] == "medium")
    return {"total": len(entries), "short": short, "medium": medium}


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Memory Preview</title>
<style>
:root {{
  --bg: #f5f5f5;
  --surface: #ffffff;
  --border: #e0e0e0;
  --text: #1a1a1a;
  --muted: #6b7280;
  --short: #2563eb;
  --short-bg: #eff6ff;
  --medium: #7c3aed;
  --medium-bg: #f5f3ff;
  --accent: #0f172a;
  --hover: #f1f5f9;
  --selected: #e0e7ff;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: "Fira Code", "Cascadia Code", Consolas, monospace;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: var(--font); background: var(--bg); color: var(--text);
        height: 100vh; display: flex; flex-direction: column; }}
header {{ background: var(--accent); color: #fff; padding: 12px 20px;
          display: flex; align-items: center; gap: 16px; flex-shrink: 0; }}
header h1 {{ font-size: 16px; font-weight: 600; }}
.stats {{ font-size: 13px; color: #94a3b8; margin-left: auto; }}
.stats span {{ margin-left: 12px; }}
.badge {{ display: inline-block; padding: 1px 7px; border-radius: 10px;
           font-size: 11px; font-weight: 600; }}
.badge-short {{ background: var(--short-bg); color: var(--short); }}
.badge-medium {{ background: var(--medium-bg); color: var(--medium); }}
.toolbar {{ background: var(--surface); border-bottom: 1px solid var(--border);
            padding: 8px 16px; display: flex; gap: 8px; flex-shrink: 0; }}
.filter-btn {{ padding: 4px 12px; border-radius: 6px; border: 1px solid var(--border);
               background: var(--bg); cursor: pointer; font-size: 13px;
               font-family: var(--font); color: var(--muted); }}
.filter-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
#search {{ flex: 1; padding: 5px 10px; border-radius: 6px;
           border: 1px solid var(--border); font-size: 13px;
           font-family: var(--font); outline: none; max-width: 280px; }}
#search:focus {{ border-color: var(--short); }}
.layout {{ display: flex; flex: 1; overflow: hidden; }}
#sidebar {{ width: 320px; flex-shrink: 0; overflow-y: auto;
            border-right: 1px solid var(--border); background: var(--surface); }}
.entry-item {{ padding: 12px 16px; border-bottom: 1px solid var(--border);
               cursor: pointer; transition: background 0.1s; }}
.entry-item:hover {{ background: var(--hover); }}
.entry-item.selected {{ background: var(--selected); }}
.entry-meta {{ display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }}
.entry-date {{ font-size: 11px; color: var(--muted); }}
.entry-keyword {{ font-size: 11px; color: var(--medium); font-weight: 500; }}
.entry-title {{ font-size: 13px; color: var(--text); line-height: 1.4;
                overflow: hidden; display: -webkit-box;
                -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
.empty {{ padding: 40px 20px; text-align: center; color: var(--muted); font-size: 14px; }}
#main {{ flex: 1; overflow-y: auto; padding: 24px; }}
#main.empty-state {{ display: flex; align-items: center; justify-content: center; }}
.placeholder {{ text-align: center; color: var(--muted); }}
.placeholder p {{ font-size: 14px; margin-top: 8px; }}
.content-header {{ margin-bottom: 20px; padding-bottom: 16px;
                    border-bottom: 1px solid var(--border); }}
.content-header h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 8px; word-break: break-all; }}
.meta-grid {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.meta-item {{ font-size: 12px; color: var(--muted); background: var(--bg);
              padding: 2px 8px; border-radius: 4px; border: 1px solid var(--border); }}
.meta-item strong {{ color: var(--text); }}
.content-body {{ font-size: 14px; line-height: 1.7; white-space: pre-wrap;
                  font-family: var(--mono); background: var(--bg);
                  padding: 16px; border-radius: 8px; border: 1px solid var(--border); }}
.content-body .section-head {{ color: var(--short); font-weight: 600; }}
.content-body .signal-done {{ color: #16a34a; }}
.content-body .signal-todo {{ color: var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>Memory Preview</h1>
  <div class="stats">
    <span>共 {total} 条</span>
    <span class="badge badge-short">短期 {short}</span>
    <span class="badge badge-medium">中期 {medium}</span>
  </div>
</header>
<div class="toolbar">
  <button class="filter-btn active" onclick="setFilter('all', this)">全部</button>
  <button class="filter-btn" onclick="setFilter('short', this)">短期</button>
  <button class="filter-btn" onclick="setFilter('medium', this)">中期</button>
  <input id="search" type="text" placeholder="搜索条目..." oninput="onSearch(this.value)">
</div>
<div class="layout">
  <div id="sidebar"></div>
  <div id="main" class="empty-state">
    <div class="placeholder">
      <div style="font-size:32px">📋</div>
      <p>从左侧选择一条记忆条目查看详情</p>
    </div>
  </div>
</div>
<script>
const ENTRIES = {data};

let filter = 'all';
let query = '';
let selected = null;

function visible() {{
  return ENTRIES.filter(e => {{
    if (filter !== 'all' && e.tier !== filter) return false;
    if (query) {{
      const q = query.toLowerCase();
      return e.title.toLowerCase().includes(q) ||
             e.body.toLowerCase().includes(q) ||
             e.keyword.toLowerCase().includes(q) ||
             e.date.includes(q);
    }}
    return true;
  }});
}}

function renderSidebar() {{
  const items = visible();
  const sb = document.getElementById('sidebar');
  if (!items.length) {{
    sb.innerHTML = '<div class="empty">无匹配条目</div>';
    return;
  }}
  sb.innerHTML = items.map(e => {{
    const isSelected = selected === e.id;
    const badge = `<span class="badge badge-${{e.tier}}">${{e.tier}}</span>`;
    const keyword = e.keyword ? `<span class="entry-keyword">#${{e.keyword}}</span>` : '';
    return `<div class="entry-item${{isSelected ? ' selected' : ''}}"
                 onclick="select('${{e.id}}')">
      <div class="entry-meta">
        ${{badge}}
        <span class="entry-date">${{e.date}}</span>
        ${{keyword}}
      </div>
      <div class="entry-title">${{esc(e.title)}}</div>
    </div>`;
  }}).join('');
}}

function renderMain(entry) {{
  const meta = Object.entries({{
    tier: entry.tier,
    date: entry.date,
    ...(entry.keyword && {{keyword: entry.keyword}}),
    ...(entry.type && {{type: entry.type}}),
    ...(entry.modules && {{modules: entry.modules}}),
    ...(entry.sources && {{sources: entry.sources + ' entries'}}),
  }}).map(([k, v]) =>
    `<div class="meta-item"><strong>${{k}}</strong>: ${{esc(v)}}</div>`
  ).join('');

  const highlighted = esc(entry.body)
    .replace(/^(## .+)$/gm, '<span class="section-head">$1</span>')
    .replace(/^(- \\[x\\].+)$/gm, '<span class="signal-done">$1</span>')
    .replace(/^(- \\[ \\].+)$/gm, '<span class="signal-todo">$1</span>');

  const el = document.getElementById('main');
  el.classList.remove('empty-state');
  el.innerHTML = `
    <div class="content-header">
      <h2>${{esc(entry.id)}}</h2>
      <div class="meta-grid">${{meta}}</div>
    </div>
    <pre class="content-body">${{highlighted}}</pre>`;
}}

function select(id) {{
  selected = id;
  const entry = ENTRIES.find(e => e.id === id);
  renderSidebar();
  if (entry) renderMain(entry);
}}

function setFilter(f, btn) {{
  filter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderSidebar();
}}

function onSearch(v) {{
  query = v;
  renderSidebar();
}}

function esc(s) {{
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

renderSidebar();
if (ENTRIES.length) select(ENTRIES[0].id);
</script>
</body>
</html>
"""
