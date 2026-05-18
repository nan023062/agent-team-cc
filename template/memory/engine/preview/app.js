/* app.js — Memory Preview UI. Fetches entries from local API server. */

let ENTRIES = [];
let filter = 'all';
let query = '';
let selected = null;

function renderStats() {
  const short = ENTRIES.filter(e => e.tier === 'short').length;
  const medium = ENTRIES.filter(e => e.tier === 'medium').length;
  document.getElementById('stat-total').textContent = `共 ${ENTRIES.length} 条`;
  document.getElementById('stat-short').textContent = `短期 ${short}`;
  document.getElementById('stat-medium').textContent = `中期 ${medium}`;
}

function visible() {
  return ENTRIES.filter(e => {
    if (filter !== 'all' && e.tier !== filter) return false;
    if (query) {
      const q = query.toLowerCase();
      return e.title.toLowerCase().includes(q) ||
             e.body.toLowerCase().includes(q) ||
             e.keyword.toLowerCase().includes(q) ||
             e.date.includes(q);
    }
    return true;
  });
}

function renderSidebar() {
  const items = visible();
  const sb = document.getElementById('sidebar');
  if (!items.length) {
    sb.innerHTML = '<div class="empty">无匹配条目</div>';
    return;
  }
  sb.innerHTML = items.map(e => {
    const isSelected = selected === e.id;
    const badge = `<span class="badge badge-${e.tier}">${e.tier}</span>`;
    const keyword = e.keyword ? `<span class="entry-keyword">#${e.keyword}</span>` : '';
    return `<div class="entry-item${isSelected ? ' selected' : ''}" onclick="select('${e.id}')">
      <div class="entry-meta">
        ${badge}
        <span class="entry-date">${e.date}</span>
        ${keyword}
      </div>
      <div class="entry-title">${esc(e.title)}</div>
    </div>`;
  }).join('');
}

function renderMain(entry) {
  const pairs = [
    ['tier', entry.tier],
    ['date', entry.date],
    ...(entry.keyword ? [['keyword', entry.keyword]] : []),
    ...(entry.type    ? [['type',    entry.type]]    : []),
    ...(entry.modules ? [['modules', entry.modules]] : []),
    ...(entry.sources ? [['sources', entry.sources + ' entries']] : []),
  ];
  const meta = pairs
    .map(([k, v]) => `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`)
    .join('');

  const highlighted = esc(entry.body)
    .replace(/^(## .+)$/gm, '<span class="section-head">$1</span>')
    .replace(/^(- \[x\].+)$/gm, '<span class="signal-done">$1</span>')
    .replace(/^(- \[ \].+)$/gm, '<span class="signal-todo">$1</span>');

  const el = document.getElementById('main');
  el.classList.remove('empty-state');
  el.innerHTML = `
    <div class="content-header">
      <h2>${esc(entry.id)}</h2>
      <div class="meta-grid">${meta}</div>
    </div>
    <pre class="content-body">${highlighted}</pre>`;
}

function select(id) {
  selected = id;
  const entry = ENTRIES.find(e => e.id === id);
  renderSidebar();
  if (entry) renderMain(entry);
}

function setFilter(f, btn) {
  filter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderSidebar();
}

function onSearch(v) {
  query = v;
  renderSidebar();
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

fetch('/api/entries')
  .then(r => r.json())
  .then(data => {
    ENTRIES = data;
    renderStats();
    renderSidebar();
    if (ENTRIES.length) select(ENTRIES[0].id);
  })
  .catch(() => {
    document.getElementById('sidebar').innerHTML =
      '<div class="empty">无法连接到本地服务<br>请通过 CLI 启动 preview</div>';
  });
