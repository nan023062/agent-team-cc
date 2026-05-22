/* CBIM docs — Mermaid renderer with svg-pan-zoom + toolbar + fullscreen.
 *
 * Markup expected:
 *   <div class="mermaid-wrap">
 *     <div class="mermaid-target" data-source="src-XYZ"></div>
 *     <div class="mermaid-toolbar"> ... buttons that call diagramZoom / diagramFullscreen ... </div>
 *   </div>
 *   <script type="text/x-mermaid" id="src-XYZ"> ...diagram source... </script>
 *
 * The script-tag source approach means the browser never parses the diagram
 * as HTML — <br/>, special chars and indentation are all preserved verbatim.
 */
(function () {
  function isDark() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
  }

  function themeVars(dark) {
    return {
      darkMode: dark,
      background:        dark ? '#0d1117' : '#ffffff',
      primaryColor:      dark ? '#161b22' : '#f6f8fa',
      primaryTextColor:  dark ? '#e6edf3' : '#1f2328',
      primaryBorderColor:dark ? '#30363d' : '#d1d9e0',
      lineColor:         dark ? '#7d8590' : '#59636e',
      secondaryColor:    dark ? '#21262d' : '#eaeef2',
      tertiaryColor:     dark ? '#21262d' : '#eaeef2',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
      fontSize: '14px'
    };
  }

  function showError(el, err) {
    var msg = (err && err.message) ? err.message : String(err);
    el.innerHTML =
      '<pre style="color:#cf222e;background:#ffebe9;padding:12px 16px;' +
      'border:1px solid #ffabaf;border-radius:8px;font-size:12px;' +
      'white-space:pre-wrap;text-align:left;max-width:100%;overflow:auto;margin:8px;">' +
      'Mermaid: ' + msg.replace(/</g, '&lt;') + '</pre>';
  }

  function attachPanZoom(el) {
    if (typeof svgPanZoom === 'undefined') return;
    var svg = el.querySelector('svg');
    if (!svg) return;
    // Strip Mermaid's max-width / fixed dims so it fills container
    svg.style.maxWidth = '100%';
    svg.style.width = '100%';
    svg.style.height = '100%';
    // Destroy previous instance (theme re-render)
    if (el._panZoom) {
      try { el._panZoom.destroy(); } catch (e) {}
      el._panZoom = null;
    }
    try {
      el._panZoom = svgPanZoom(svg, {
        zoomEnabled: true,
        panEnabled: true,
        controlIconsEnabled: false,
        fit: true,
        center: true,
        minZoom: 0.2,
        maxZoom: 10,
        zoomScaleSensitivity: 0.3
      });
    } catch (e) { /* swallow — diagram still readable without pan-zoom */ }
  }

  function renderOne(el, srcId, source) {
    var id = 'm-' + srcId + '-' + Date.now() + '-' + Math.floor(Math.random() * 1e6);
    try {
      var p = mermaid.render(id, source);
      if (p && typeof p.then === 'function') {
        p.then(function (r) {
          el.innerHTML = r.svg;
          if (r.bindFunctions) r.bindFunctions(el);
          attachPanZoom(el);
        }).catch(function (err) { showError(el, err); });
      } else if (p && p.svg) {
        el.innerHTML = p.svg;
        if (p.bindFunctions) p.bindFunctions(el);
        attachPanZoom(el);
      }
    } catch (err) { showError(el, err); }
  }

  function renderAll() {
    var dark = isDark();
    mermaid.initialize({
      startOnLoad: false,
      theme: dark ? 'dark' : 'default',
      themeVariables: themeVars(dark),
      flowchart: { htmlLabels: true, useMaxWidth: true, curve: 'basis' }
    });
    document.querySelectorAll('.mermaid-target[data-source]').forEach(function (el) {
      var srcId = el.getAttribute('data-source');
      var srcEl = document.getElementById(srcId);
      if (!srcEl) return;
      renderOne(el, srcId, srcEl.textContent.trim());
    });
  }

  /* ── Toolbar handlers (exposed on window) ── */
  function getTargetFrom(btn) {
    var wrap = btn.closest('.mermaid-wrap');
    return wrap ? wrap.querySelector('.mermaid-target') : null;
  }

  window.diagramZoom = function (btn, action) {
    var el = getTargetFrom(btn);
    if (!el || !el._panZoom) return;
    if (action === 'in')        el._panZoom.zoomBy(1.25);
    else if (action === 'out')  el._panZoom.zoomBy(0.8);
    else if (action === 'reset') {
      el._panZoom.resetZoom();
      el._panZoom.resetPan();
      el._panZoom.fit();
      el._panZoom.center();
    }
  };

  function refit(el) {
    if (!el || !el._panZoom) return;
    setTimeout(function () {
      try {
        el._panZoom.resize();
        el._panZoom.fit();
        el._panZoom.center();
      } catch (e) {}
    }, 100);
  }

  window.diagramFullscreen = function (btn) {
    var wrap = btn.closest('.mermaid-wrap');
    if (!wrap) return;
    wrap.classList.toggle('fullscreen');
    refit(wrap.querySelector('.mermaid-target'));
  };

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.mermaid-wrap.fullscreen').forEach(function (w) {
        w.classList.remove('fullscreen');
        refit(w.querySelector('.mermaid-target'));
      });
    }
  });

  /* ── Boot ── */
  renderAll();
  document.addEventListener('cbim-theme-changed', renderAll);

  // Re-fit on window resize (e.g. orientation change)
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      document.querySelectorAll('.mermaid-target').forEach(refit);
    }, 200);
  });
})();
