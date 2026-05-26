/* app.js -- CBIM Dashboard UI (Memory / Agents / Knowledge / Log) */

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------

const LANG = { current: 'zh' };

const I18N = {
  zh: {
    nav_memory:      '记忆',
    nav_agents:      '能力',
    nav_knowledge:   '知识',
    nav_log:         '日志',
    filter_all:      '全部',
    filter_medium:   '中期',
    search_memory:   '搜索记忆...',
    search_agents:   '搜索能力...',
    search_knowledge:'搜索知识模块...',
    placeholder:     '从左侧选择一条记录查看详情',
    empty_memory:    '无匹配条目',
    empty_agents:    '无匹配能力',
    empty_knowledge: '未发现 .dna/ 知识模块。在项目中创建 .dna/ 模块后将在此显示。',
    empty_log:       '当前会话尚无日志输出',
    error_connect:   '无法连接到本地服务\n请通过 CLI 启动 dashboard',
    badge_medium:    '中期',
    section_user:    '用户能力',
    section_framework:'框架能力',
    log_clear:       '清空',
    log_path:        '当前日志',
    log_no_session:  '尚无活动会话',
    stat_entries:    n => `${n} 条`,
    stat_agents:     n => `${n} 个能力`,
    stat_modules:    n => `${n} 个模块`,
    stat_log:        n => `${n} 行`,
    meta_entries:    n => `${n} entries`,
    lang_toggle:     'EN',
    info_server:     '服务',
    info_project:    '项目',
  },
  en: {
    nav_memory:      'Memory',
    nav_agents:      'Agents',
    nav_knowledge:   'Knowledge',
    nav_log:         'Log',
    filter_all:      'All',
    filter_medium:   'Medium',
    search_memory:   'Search memory...',
    search_agents:   'Search agents...',
    search_knowledge:'Search modules...',
    placeholder:     'Select an item on the left to view details',
    empty_memory:    'No matching entries',
    empty_agents:    'No matching agents',
    empty_knowledge: 'No knowledge modules found. Create .dna/ modules to populate this view.',
    empty_log:       'No log output for the current session yet',
    error_connect:   'Cannot connect to local server\nPlease start dashboard via CLI',
    badge_medium:    'Medium',
    section_user:    'User agents',
    section_framework:'Framework',
    log_clear:       'Clear',
    log_path:        'Active log',
    log_no_session:  'No active session',
    stat_entries:    n => `${n} entr${n === 1 ? 'y' : 'ies'}`,
    stat_agents:     n => `${n} agent${n === 1 ? '' : 's'}`,
    stat_modules:    n => `${n} module${n === 1 ? '' : 's'}`,
    stat_log:        n => `${n} line${n === 1 ? '' : 's'}`,
    meta_entries:    n => `${n} entries`,
    lang_toggle:     '中',
    info_server:     'Server',
    info_project:    'Project',
  },
};

function md(text) {
  marked.setOptions({ breaks: true, gfm: true });
  return DOMPurify.sanitize(marked.parse(String(text || '')));
}

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
  renderLogFilters();
}

function applyI18n() {
  document.getElementById('lang-btn').textContent        = t('lang_toggle');
  document.getElementById('nav-memory').textContent      = t('nav_memory');
  document.getElementById('nav-agents').textContent      = t('nav_agents');
  document.getElementById('nav-knowledge').textContent   = t('nav_knowledge');
  document.getElementById('nav-log').textContent         = t('nav_log');
  document.getElementById('filter-all').textContent      = t('filter_all');
  document.getElementById('filter-medium').textContent   = t('filter_medium');
  document.getElementById('search-memory').placeholder   = t('search_memory');
  document.getElementById('search-agents').placeholder   = t('search_agents');
  document.getElementById('search-knowledge').placeholder= t('search_knowledge');
  document.getElementById('log-clear').textContent       = t('log_clear');
  const ph = document.getElementById('placeholder-text');
  if (ph) ph.textContent = t('placeholder');
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (I18N[LANG.current][key] !== undefined) el.textContent = t(key);
  });
}

// ---------------------------------------------------------------------------
// Data & state
// ---------------------------------------------------------------------------

// Tag set - keep in sync with engine/session_log.py
const LOG_TAGS = ['SESSION', 'USER', 'TOOL', 'RESULT', 'TURN', 'MCP', 'SCHED', 'ENG', 'IMP'];
const LOG_MAX_LINES = 2000;

const DATA = { memory: [], agents: [], knowledge: [] };
const INFO = { host: '', port: 0, root: '', cbim: '' };
const LOG = {
  lines: [],           // each entry: { tag: string, raw: string }
  offset: 0,
  path: '',
  timer: null,
  autoScroll: true,
  enabledTags: new Set(LOG_TAGS),
};
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
  ['memory', 'agents', 'knowledge', 'log'].forEach(s => {
    const tb = document.getElementById('toolbar-' + s);
    if (tb) tb.classList.toggle('hidden', s !== section);
  });
  if (section === 'log') startLogPolling();
  else stopLogPolling();
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
    const medium = DATA.memory.filter(e => e.tier === 'medium').length;
    el.innerHTML =
      `<span>${t('stat_entries', DATA.memory.length)}</span>` +
      `<span class="badge badge-medium">${t('badge_medium')} ${medium}</span>`;
  } else if (s === 'agents') {
    const totalSkills = DATA.agents.reduce((n, a) => n + a.skills.length, 0);
    el.innerHTML = `<span>${t('stat_agents', DATA.agents.length)}</span>` +
      (totalSkills ? `<span class="badge badge-agent">${totalSkills} skills</span>` : '');
  } else if (s === 'knowledge') {
    el.innerHTML = `<span>${t('stat_modules', DATA.knowledge.length)}</span>`;
  } else {
    const pathPart = LOG.path
      ? `<span class="log-path">${esc(LOG.path)}</span>`
      : `<span class="log-path muted">${t('log_no_session')}</span>`;
    el.innerHTML = `<span>${t('stat_log', LOG.lines.length)}</span>${pathPart}`;
  }
}

// ---------------------------------------------------------------------------
// Footer info strip
// ---------------------------------------------------------------------------

function renderInfo() {
  const addr = INFO.host && INFO.port ? `${INFO.host}:${INFO.port}` : '-';
  document.getElementById('info-server').textContent = addr;
  document.getElementById('info-project').textContent = INFO.root || '-';
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function renderSidebar() {
  const s = STATE.section;
  if (s === 'memory')        renderMemorySidebar();
  else if (s === 'agents')   renderAgentsSidebar();
  else if (s === 'knowledge')renderKnowledgeSidebar();
  else                       renderLogSidebar();
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
  if (!items.length) { sb.innerHTML = `<div class="empty">${esc(t('empty_memory'))}</div>`; return; }
  sb.innerHTML = items.map(e => {
    const tierLabel = t('badge_medium');
    const badge = `<span class="badge badge-${e.tier}">${tierLabel}</span>`;
    const kw    = e.keyword ? `<span class="entry-keyword">#${esc(e.keyword)}</span>` : '';
    const sel   = STATE.selected.memory === e.id ? ' selected' : '';
    return `<div class="entry-item${sel}" onclick="selectItem('memory','${esc(e.id)}')">
      <div class="entry-meta">${badge}<span class="entry-date">${esc(e.date)}</span>${kw}</div>
      <div class="entry-title">${esc(e.title)}</div>
    </div>`;
  }).join('');
}

// Framework agents are tagged by server-side include_builtin; we recognise
// them client-side by id (kept in sync with services.agent_service).
const FRAMEWORK_AGENT_IDS = new Set(['architect', 'hr', 'auditor', 'programmer']);

function renderAgentsSidebar() {
  const q = STATE.queries.agents.toLowerCase();
  const matches = a => !q || a.name.toLowerCase().includes(q) ||
                       a.description.toLowerCase().includes(q);
  const userAgents      = DATA.agents.filter(a => !FRAMEWORK_AGENT_IDS.has(a.id) && matches(a));
  const frameworkAgents = DATA.agents.filter(a =>  FRAMEWORK_AGENT_IDS.has(a.id) && matches(a));

  const sb = document.getElementById('sidebar');
  if (!userAgents.length && !frameworkAgents.length) {
    sb.innerHTML = `<div class="empty">${esc(t('empty_agents'))}</div>`;
    return;
  }
  const renderRow = a => {
    const sc  = a.skills.length
      ? `<span class="badge badge-skill">${a.skills.length} skills</span>` : '';
    const sel = STATE.selected.agents === a.id ? ' selected' : '';
    return `<div class="entry-item${sel}" onclick="selectItem('agents','${esc(a.id)}')">
      <div class="entry-meta"><span class="badge badge-agent">agent</span>${sc}</div>
      <div class="entry-title">${esc(a.name)}</div>
      <div class="entry-desc">${esc(a.description.slice(0, 60))}</div>
    </div>`;
  };
  const sections = [];
  if (userAgents.length) {
    sections.push(`<div class="sidebar-section">${esc(t('section_user'))}</div>`);
    sections.push(userAgents.map(renderRow).join(''));
  }
  if (frameworkAgents.length) {
    sections.push(`<div class="sidebar-section sidebar-section-framework">${esc(t('section_framework'))}</div>`);
    sections.push(frameworkAgents.map(renderRow).join(''));
  }
  sb.innerHTML = sections.join('');
}

function renderKnowledgeSidebar() {
  const q = STATE.queries.knowledge.toLowerCase();
  const items = DATA.knowledge.filter(m =>
    !q || m.name.toLowerCase().includes(q) || m.description.toLowerCase().includes(q) ||
    m.keywords.join(' ').toLowerCase().includes(q)
  );
  const sb = document.getElementById('sidebar');
  if (!items.length) { sb.innerHTML = `<div class="empty">${esc(t('empty_knowledge'))}</div>`; return; }
  sb.innerHTML = items.map(m => {
    const kws = m.keywords.map(k => `<span class="entry-keyword">#${esc(k)}</span>`).join('');
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

function renderLogSidebar() {
  // Log view uses the main panel only - sidebar shows a brief legend.
  const sb = document.getElementById('sidebar');
  sb.innerHTML = `<div class="log-legend">
    <div class="log-legend-title">${esc(t('log_path'))}</div>
    <div class="log-legend-path">${LOG.path ? esc(LOG.path) : `<span class="muted">${esc(t('log_no_session'))}</span>`}</div>
  </div>`;
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function renderMainForSelected() {
  const s  = STATE.section;
  const el = document.getElementById('main');
  if (s === 'log') {
    renderLogPane(el);
    return;
  }
  const id = STATE.selected[s];
  if (!id) {
    el.className = 'empty-state';
    el.innerHTML = `<div class="placeholder"><div style="font-size:32px">\u{1F4CB}</div><p id="placeholder-text">${esc(t('placeholder'))}</p></div>`;
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
  const tierLabel = t('badge_medium');
  const pairs = [
    ['tier', tierLabel], ['date', entry.date],
    ...(entry.keyword ? [['keyword', entry.keyword]] : []),
    ...(entry.type    ? [['type',    entry.type]]    : []),
    ...(entry.modules ? [['modules', entry.modules]] : []),
    ...(entry.sources ? [['sources', t('meta_entries', entry.sources)]] : []),
  ];
  const meta = pairs.map(([k, v]) =>
    `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`).join('');
  el.className = '';
  el.innerHTML = `
    <div class="content-header">
      <h2>${esc(entry.id)}</h2>
      <div class="meta-grid">${meta}</div>
    </div>
    <div class="content-body markdown-body">${md(entry.body)}</div>`;
}

function renderAgentDetail(el, agent) {
  const pairs = [
    ...(agent.model ? [['model', agent.model]] : []),
    ...(agent.tools ? [['tools', agent.tools]] : []),
  ];
  const meta = pairs.map(([k, v]) =>
    `<div class="meta-item"><strong>${k}</strong>: ${esc(v)}</div>`).join('');
  const soulSection = agent.body
    ? `<div class="doc-section"><h3>soul</h3><div class="content-body markdown-body">${md(agent.body)}</div></div>`
    : '';
  const skillSections = agent.skills.map(s =>
    `<div class="doc-section">
      <h3><span class="skill-tag">${esc(s.id)}</span></h3>
      <div class="content-body markdown-body">${md(s.body)}</div>
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
    `<div class="doc-section"><h3>module.md</h3>` +
    `<div class="content-body markdown-body">${md(mod.architecture)}</div></div>`);
  if (mod.contract) sections.push(
    `<div class="doc-section"><h3>contract.md</h3>` +
    `<div class="content-body markdown-body">${md(mod.contract)}</div></div>`);
  mod.workflows.forEach(w => sections.push(
    `<div class="doc-section">` +
    `<h3><span class="workflow-tag">${esc(w.id)}</span>&nbsp;workflow</h3>` +
    `<div class="content-body markdown-body">${md(w.body)}</div></div>`));
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
// Log view
// ---------------------------------------------------------------------------

function renderLogFilters() {
  const el = document.getElementById('log-filters');
  if (!el) return;
  el.innerHTML = LOG_TAGS.map(tag => {
    const active = LOG.enabledTags.has(tag) ? ' active' : '';
    return `<button class="filter-btn log-tag-btn log-tag-${tag.toLowerCase()}${active}" onclick="toggleLogTag('${tag}', this)">${tag}</button>`;
  }).join('');
}

function toggleLogTag(tag, btn) {
  if (LOG.enabledTags.has(tag)) LOG.enabledTags.delete(tag);
  else                          LOG.enabledTags.add(tag);
  btn.classList.toggle('active');
  renderLogPane(document.getElementById('main'));
}

function clearLog() {
  LOG.lines = [];
  LOG.offset = 0;       // request full log again on next poll
  renderHeader();
  renderLogPane(document.getElementById('main'));
}

function renderLogPane(el) {
  el.className = 'log-pane';
  const visible = LOG.lines.filter(line => LOG.enabledTags.has(line.tag));
  const body = visible.length
    ? visible.map(line => `<span class="log-line log-tag-${line.tag.toLowerCase()}">${esc(line.raw)}</span>`).join('\n')
    : `<span class="muted">${esc(t('empty_log'))}</span>`;
  el.innerHTML = `<pre id="log-body" class="log-body" onscroll="onLogScroll(event)">${body}</pre>`;
  if (LOG.autoScroll) {
    const pre = document.getElementById('log-body');
    if (pre) pre.scrollTop = pre.scrollHeight;
  }
}

function onLogScroll(ev) {
  const pre = ev.currentTarget;
  // Allow ~8px tolerance so floating-point scroll positions still pin.
  const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 8;
  LOG.autoScroll = atBottom;
}

// Parse a session_log line: "[YYYY-MM-DD HH:MM:SS] [TAG] message"
// Returns {tag, raw}; unrecognised lines fall through with tag='ENG'.
const LOG_LINE_RE = /^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[([A-Z]+)\]/;
function parseLogLine(raw) {
  const m = raw.match(LOG_LINE_RE);
  return { tag: m ? m[1] : 'ENG', raw };
}

function startLogPolling() {
  if (LOG.timer) return;
  const tick = async () => {
    try {
      const r = await fetch(`/api/log?since=${LOG.offset}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data.rotated) {
        LOG.lines = [];
        LOG.offset = 0;
      }
      LOG.path = data.path || '';
      LOG.offset = data.offset || 0;
      if (data.lines && data.lines.length) {
        for (const raw of data.lines) {
          if (!raw) continue;
          LOG.lines.push(parseLogLine(raw));
        }
        if (LOG.lines.length > LOG_MAX_LINES) {
          LOG.lines.splice(0, LOG.lines.length - LOG_MAX_LINES);
        }
        if (STATE.section === 'log') {
          renderHeader();
          renderSidebar();
          renderLogPane(document.getElementById('main'));
        }
      } else if (STATE.section === 'log') {
        renderHeader();
        renderSidebar();
        renderLogPane(document.getElementById('main'));
      }
    } catch (_) { /* swallow; next tick will retry */ }
  };
  tick();
  LOG.timer = setInterval(tick, 2000);
}

function stopLogPolling() {
  if (LOG.timer) { clearInterval(LOG.timer); LOG.timer = null; }
}

// ---------------------------------------------------------------------------
// Interaction
// ---------------------------------------------------------------------------

function selectItem(section, id) {
  if (!window.getSelection().isCollapsed) return;  // user is selecting text
  STATE.selected[section] = id;
  renderSidebar();
  renderMainForSelected();
}

function setFilter(f, btn) {
  STATE.filter = f;
  document.querySelectorAll('#toolbar-memory .filter-btn').forEach(b => b.classList.remove('active'));
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

renderLogFilters();
applyI18n();

fetch('/api/info').then(r => r.json()).then(d => {
  INFO.host = d.host; INFO.port = d.port; INFO.root = d.root_dir; INFO.cbim = d.cbim_dir;
  renderInfo();
}).catch(() => {});

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
    `<div class="empty">${esc(t('error_connect'))}</div>`;
});
