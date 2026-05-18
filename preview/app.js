/* app.js — CBIM Preview UI (Memory / Agents / Knowledge) */

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

const LANG = { current: 'zh' };

const I18N = {
  zh: {
    nav_memory:      '记忆',
    nav_agents:      '能力',
    nav_knowledge:   '知识',
    filter_all:      '全部',
    filter_short:    '短期',
    filter_medium:   '中期',
    search_memory:   '搜索记忆...',
    search_agents:   '搜索能力...',
    search_knowledge:'搜索知识模块...',
    placeholder:     '从左侧选择一条记录查看详情',
    empty_memory:    '无匹配条目',
    empty_agents:    '无匹配能力',
    empty_knowledge: '无匹配模块',
    error_connect:   '无法连接到本地服务\n请通过 CLI 启动 preview',
    badge_short:     '短期',
    badge_medium:    '中期',
    stat_entries:    n => `${n} 条`,
    stat_agents:     n => `${n} 个 work agent`,
    stat_modules:    n => `${n} 个模块`,
    meta_entries:    n => `${n} entries`,
    lang_toggle:     'EN',
  },
  en: {
    nav_memory:      'Memory',
    nav_agents:      'Agents',
    nav_knowledge:   'Knowledge',
    filter_all:      'All',
    filter_short:    'Short',
    filter_medium:   'Medium',
    search_memory:   'Search memory...',
    search_agents:   'Search agents...',
    search_knowledge:'Search modules...',
    placeholder:     'Select an item on the left to view details',
    empty_memory:    'No matching entries',
    empty_agents:    'No matching agents',
    empty_knowledge: 'No matching modules',
    error_connect:   'Cannot connect to local server\nPlease start preview via CLI',
    badge_short:     'Short',
    badge_medium:    'Medium',
    stat_entries:    n => `${n} entr${n === 1 ? 'y' : 'ies'}`,
    stat_agents:     n => `${n} work agent${n === 1 ? '' : 's'}`,
    stat_modules:    n => `${n} module${n === 1 ? '' : 's'}`,
    meta_entries:    n => `${n} entries`,
    lang_toggle:     '中',
  },
};

function t(key, ...args) {
  const v = I18N[LANG.current][key];
  return typeof v === 'function' ? v(...args) : v;
}

function toggleLang() {
  LANG.current = LANG.current === 'zh' ? 'en' : 'zh';
  applyI18n();
  renderHeader();
  renderSidebar();
  renderMainForSelected();
}

function applyI18n() {
  document.getElementById('lang-btn').textContent        = t('lang_toggle');
  document.getElementById('nav-memory').textContent      = t('nav_memory');
  document.getElementById('nav-agents').textContent      = t('nav_agents');
  document.getElementById('nav-knowledge').textContent   = t('nav_knowledge');
  document.getElementById('filter-all').textContent      = t('filter_all');
  document.getElementById('filter-short').textContent    = t('filter_short');
  document.getElementById('filter-medium').textContent   = t('filter_medium');
  document.getElementById('search-memory').placeholder   = t('search_memory');
  document.getElementById('search-agents').placeholder   = t('search_agents');
  document.getElementById('search-knowledge').placeholder= t('search_knowledge');
  const ph = document.getElementById('placeholder-text');
  if (ph) ph.textContent = t('placeholder');
}

// ---------------------------------------------------------------------------
// Data & state
// ---------------------------------------------------------------------------

const DATA = { memory: [], agents: [], knowledge: [] };
const STATE = {
  section: 'memory',
  filter: 'all',
  queries: { memory: '', agents: '', knowledge: '' },
  selected: { memory: null, agents: null, knowledge: null },
};

// ---------------------------------------------------------------------------
// Section switching
// ---------------------------------------------------------------------------

function switchSection(section, btn) {
  STATE.section = section;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ['memory', 'agents', 'knowledge'].forEach(s => {
    const tb = document.getElementById('toolbar-' + s);
    if (tb) tb.classList.toggle('hidden', s !== section);
  });
  renderHeader();
  renderSidebar();
  renderMainForSelected();
}

// ---------------------------------------------------------------------------
// Header stats
// ---------------------------------------------------------------------------

function renderHeader() {
  const el = document.getElementById('header-stats');
  const s = STATE.section;
  if (s === 'memory') {
    const short  = DATA.memory.filter(e => e.tier === 'short').length;
    const medium = DATA.memory.filter(e => e.tier === 'medium').length;
    el.innerHTML =
      `<span>${t('stat_entries', DATA.memory.length)}</span>` +
      `<span class="badge badge-short">${t('badge_short')} ${short}</span>` +
      `<span class="badge badge-medium">${t('badge_medium')} ${medium}</span>`;
  } else if (s === 'agents') {
    const totalSkills = DATA.agents.reduce((n, a) => n + a.skills.length, 0);
    el.innerHTML = `<span>${t('stat_agents', DATA.agents.length)}</span>` +
      (totalSkills ? `<span class="badge badge-agent">${totalSkills} skills</span>` : '');
  } else {
    el.innerHTML = `<span>${t('stat_modules', DATA.knowledge.length)}</span>`;
  }
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function renderSidebar() {
  const s = STATE.section;
  if (s === 'memory')    renderMemorySidebar();
  else if (s === 'agents') renderAgentsSidebar();
  else                   renderKnowledgeSidebar();
}

function renderMemorySidebar() {
  const q = STATE.queries.memory.toLowerCase();
  const items = DATA.memory.filter(e => {
    if (STATE.filter !== 'all' && e.tier !== STATE.filter) return false;
    if (!q) return true;
    return e.title.toLowerCase().includes(q) || e.body.toLowerCase().includes(q) ||
           e.keyword.toLowerCase().includes(q) || e.date.includes(q);
  });
  const sb = document.getElementById('sidebar');
  if (!items.length) { sb.innerHTML = `<div class="empty">${t('empty_memory')}</div>`; return; }
  sb.innerHTML = items.map(e => {
    const tierLabel = e.tier === 'short' ? t('badge_short') : t('badge_medium');
    const badge = `<span class="badge badge-${e.tier}">${tierLabel}</span>`;
    const kw    = e.keyword ? `<span class="entry-keyword">#${e.keyword}</span>` : '';
    const sel   = STATE.selected.memory === e.id ? ' selected' : '';
    return `<div class="entry-item${sel}" onclick="selectItem('memory','${esc(e.id)}')">
      <div class="entry-meta">${badge}<span class="entry-date">${e.date}</span>${kw}</div>
      <div class="entry-title">${esc(e.title)}</div>
    </div>`;
  }).join('');
}

function renderAgentsSidebar() {
  const q = STATE.queries.agents.toLowerCase();
  const items = DATA.agents.filter(a =>
    !q || a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
  );
  const sb = document.getElementById('sidebar');
  if (!items.length) { sb.innerHTML = `<div class="empty">${t('empty_agents')}</div>`; return; }
  sb.innerHTML = items.map(a => {
    const sc  = a.skills.length
      ? `<span class="badge badge-skill">${a.skills.length} skills</span>` : '';
    const sel = STATE.selected.agents === a.id ? ' selected' : '';
    return `<div class="entry-item${sel}" onclick="selectItem('agents','${esc(a.id)}')">
      <div class="entry-meta"><span class="badge badge-agent">agent</span>${sc}</div>
      <div class="entry-title">${esc(a.name)}</div>
      <div class="entry-desc">${esc(a.description.slice(0, 60))}</div>
    </div>`;
  }).join('');
}

function renderKnowledgeSidebar() {
  const q = STATE.queries.knowledge.toLowerCase();
  const items = DATA.knowledge.filter(m =>
    !q || m.name.toLowerCase().includes(q) || m.description.toLowerCase().includes(q) ||
    m.keywords.join(' ').toLowerCase().includes(q)
  );
  const sb = document.getElementById('sidebar');
  if (!items.length) { sb.innerHTML = `<div class="empty">${t('empty_knowledge')}</div>`; return; }
  sb.innerHTML = items.map(m => {
    const kws = m.keywords.map(k => `<span class="entry-keyword">#${k}</span>`).join('');
    const wfBadge = m.workflows.length
      ? `<span class="badge badge-workflow">${m.workflows.length} workflows</span>` : '';
    const sel = STATE.selected.knowledge === m.id ? ' selected' : '';
    return `<div class="entry-item${sel}" onclick="selectItem('knowledge','${esc(m.id)}')">
      <div class="entry-meta"><span class="badge badge-module">module</span>${wfBadge}${kws}</div>
      <div class="entry-title">${esc(m.name)}</div>
      <div class="entry-desc">${esc(m.description.slice(0, 60))}</div>
    </div>`;
  }).join('');
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function renderMainForSelected() {
  const s  = STATE.section;
  const id = STATE.selected[s];
  const el = document.getElementById('main');
  if (!id) {
    el.className = 'empty-state';
    el.innerHTML = `<div class="placeholder"><div style="font-size:32px">📋</div><p id="placeholder-text">${t('placeholder')}</p></div>`;
    return;
  }
  if (s === 'memory') {
    const entry = DATA.memory.find(e => e.id === id);
    if (entry) renderMemoryDetail(el, entry);
  } else if (s === 'agents') {
    const agent = DATA.agents.find(a => a.id === id);
    if (agent) renderAgentDetail(el, agent);
  } else {
    const mod = DATA.knowledge.find(m => m.id === id);
    if (mod) renderKnowledgeDetail(el, mod);
  }
}

function renderMemoryDetail(el, entry) {
  const tierLabel = entry.tier === 'short' ? t('badge_short') : t('badge_medium');
  const pairs = [
    ['tier', tierLabel], ['date', entry.date],
    ...(entry.keyword ? [['keyword', entry.keyword]] : []),
    ...(entry.type    ? [['type',    entry.type]]    : []),
    ...(entry.modules ? [['modules', entry.modules]] : []),
    ...(entry.sources ? [['sources', t('meta_entries', entry.sources)]] : []),
  ];
  const meta = pairs.map(([k, v]) =>
    `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`).join('');
  const body = esc(entry.body)
    .replace(/^(## .+)$/gm, '<span class="section-head">$1</span>')
    .replace(/^(- \[x\].+)$/gm, '<span class="signal-done">$1</span>')
    .replace(/^(- \[ \].+)$/gm, '<span class="signal-todo">$1</span>');
  el.className = '';
  el.innerHTML = `
    <div class="content-header">
      <h2>${esc(entry.id)}</h2>
      <div class="meta-grid">${meta}</div>
    </div>
    <pre class="content-body">${body}</pre>`;
}

function renderAgentDetail(el, agent) {
  const pairs = [
    ...(agent.model ? [['model', agent.model]] : []),
    ...(agent.tools ? [['tools', agent.tools]] : []),
  ];
  const meta = pairs.map(([k, v]) =>
    `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`).join('');
  const soulSection = agent.body
    ? `<div class="doc-section"><h3>soul</h3><pre class="content-body">${esc(agent.body)}</pre></div>`
    : '';
  const skillSections = agent.skills.map(s =>
    `<div class="doc-section">
      <h3><span class="skill-tag">${esc(s.id)}</span></h3>
      <pre class="content-body">${esc(s.body)}</pre>
    </div>`).join('');
  el.className = '';
  el.innerHTML = `
    <div class="content-header">
      <h2>${esc(agent.name)}</h2>
      <p class="agent-desc">${esc(agent.description)}</p>
      <div class="meta-grid">${meta}</div>
    </div>
    ${soulSection}${skillSections}`;
}

function renderKnowledgeDetail(el, mod) {
  const pairs = [
    ['path', mod.path],
    ...(mod.owner              ? [['owner',    mod.owner]]                          : []),
    ...(mod.keywords.length    ? [['keywords', mod.keywords.join(', ')]]            : []),
    ...(mod.dependencies.length ? [['deps',    mod.dependencies.join(', ')]]        : []),
    ...(mod.workflows.length    ? [['workflows', mod.workflows.map(w => w.id).join(', ')]] : []),
  ];
  const meta = pairs.map(([k, v]) =>
    `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`).join('');
  const sections = [];
  if (mod.architecture) sections.push(
    `<div class="doc-section"><h3>architecture.md</h3>` +
    `<pre class="content-body">${esc(mod.architecture)}</pre></div>`);
  if (mod.contract) sections.push(
    `<div class="doc-section"><h3>contract.md</h3>` +
    `<pre class="content-body">${esc(mod.contract)}</pre></div>`);
  mod.workflows.forEach(w => sections.push(
    `<div class="doc-section">` +
    `<h3><span class="workflow-tag">${esc(w.id)}</span>&nbsp;workflow</h3>` +
    `<pre class="content-body">${esc(w.body)}</pre></div>`));
  el.className = '';
  el.innerHTML = `
    <div class="content-header">
      <h2>${esc(mod.name)}</h2>
      <p class="agent-desc">${esc(mod.description)}</p>
      <div class="meta-grid">${meta}</div>
    </div>
    ${sections.join('')}`;
}

// ---------------------------------------------------------------------------
// Interaction
// ---------------------------------------------------------------------------

function selectItem(section, id) {
  STATE.selected[section] = id;
  renderSidebar();
  renderMainForSelected();
}

function setFilter(f, btn) {
  STATE.filter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderSidebar();
}

function onSearch(section, v) {
  STATE.queries[section] = v;
  renderSidebar();
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------

function beat() { fetch('/heartbeat').catch(() => {}); }
beat();
setInterval(beat, 10000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) beat(); });

// ---------------------------------------------------------------------------
// Initial data load
// ---------------------------------------------------------------------------

Promise.all([
  fetch('/api/entries').then(r => r.json()),
  fetch('/api/agents').then(r => r.json()),
  fetch('/api/knowledge').then(r => r.json()),
]).then(([entries, agents, knowledge]) => {
  DATA.memory    = entries;
  DATA.agents    = agents;
  DATA.knowledge = knowledge;
  renderHeader();
  renderSidebar();
  if (DATA.memory.length) selectItem('memory', DATA.memory[0].id);
}).catch(() => {
  document.getElementById('sidebar').innerHTML =
    `<div class="empty">${t('error_connect')}</div>`;
});
