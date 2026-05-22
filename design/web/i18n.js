/* CBIM docs — language + theme controller
 *
 * Stores user prefs in localStorage:
 *   cbim-docs-lang  : "zh" | "en"            (default "zh")
 *   cbim-theme      : "system" | "light" | "dark"  (default "system")
 *
 * Dispatches `cbim-theme-changed` on document when theme resolves
 * (the page's inline mermaid script re-renders diagrams on this event).
 */
(function () {
  var LANG_KEY  = 'cbim-docs-lang';
  var THEME_KEY = 'cbim-theme';
  var root = document.documentElement;
  var mql  = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;

  /* ── Language ─────────────────────────────────────────── */
  function applyLang(lang) {
    if (lang !== 'zh' && lang !== 'en') lang = 'zh';
    root.setAttribute('data-lang', lang);
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) {}
  }

  function toggleLang() {
    var current = root.getAttribute('data-lang') || 'zh';
    applyLang(current === 'zh' ? 'en' : 'zh');
  }

  function getStoredLang() {
    try { return localStorage.getItem(LANG_KEY); } catch (e) { return null; }
  }

  /* ── Theme ────────────────────────────────────────────── */
  function resolveTheme(pref) {
    if (pref === 'light' || pref === 'dark') return pref;
    return mql && mql.matches ? 'dark' : 'light';
  }

  function applyTheme(pref, options) {
    options = options || {};
    if (pref !== 'system' && pref !== 'light' && pref !== 'dark') pref = 'system';
    var resolved = resolveTheme(pref);
    root.setAttribute('data-theme', resolved);
    try { localStorage.setItem(THEME_KEY, pref); } catch (e) {}
    updateThemeButtons(pref);
    if (!options.silent) {
      document.dispatchEvent(new CustomEvent('cbim-theme-changed', {
        detail: { pref: pref, resolved: resolved }
      }));
    }
  }

  function updateThemeButtons(pref) {
    var btns = document.querySelectorAll('.theme-switcher button[data-theme-pref]');
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      if (b.getAttribute('data-theme-pref') === pref) b.classList.add('active');
      else b.classList.remove('active');
    }
  }

  function getStoredTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
  }

  /* ── Init (runs before DOMContentLoaded to avoid FOUC) ── */
  applyLang(getStoredLang() || 'zh');

  // For theme, just set the data-theme attribute now; full apply (with
  // event dispatch + button highlight) happens after DOM is ready so the
  // mermaid listener and switcher buttons exist.
  var initialPref = getStoredTheme() || 'system';
  root.setAttribute('data-theme', resolveTheme(initialPref));

  function onReady() {
    // data-theme is already set above; just sync buttons without
    // dispatching (mermaid renders itself once on load).
    applyTheme(initialPref, { silent: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  // Track system pref changes when in "system" mode
  if (mql) {
    var handler = function () {
      if ((getStoredTheme() || 'system') === 'system') applyTheme('system');
    };
    if (mql.addEventListener) mql.addEventListener('change', handler);
    else if (mql.addListener) mql.addListener(handler);
  }

  /* ── Public API ───────────────────────────────────────── */
  window.toggleLang = toggleLang;
  window.setTheme   = applyTheme;
  window.cbimUi = { applyLang: applyLang, toggleLang: toggleLang, setTheme: applyTheme };
})();
