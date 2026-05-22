/* CBIM docs — bilingual toggle */
(function () {
  var KEY = 'cbim-docs-lang';
  var root = document.documentElement;

  function applyLang(lang) {
    if (lang !== 'zh' && lang !== 'en') lang = 'zh';
    root.setAttribute('data-lang', lang);
    try { localStorage.setItem(KEY, lang); } catch (e) {}
  }

  function initLang() {
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    applyLang(saved || 'zh');
  }

  function toggleLang() {
    var current = root.getAttribute('data-lang') || 'zh';
    applyLang(current === 'zh' ? 'en' : 'zh');
  }

  // Init immediately so initial render has no FOUC
  initLang();

  window.toggleLang = toggleLang;
  window.cbimI18n = { apply: applyLang, toggle: toggleLang };
})();
