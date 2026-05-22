/* CBIM docs — Mermaid renderer with svg-pan-zoom + toolbar + fullscreen.
 *
 * Markup expected:
 *   <div class="mermaid-wrap">
 *     <div class="mermaid-target" data-source="src-XYZ"></div>
 *     <div class="mermaid-toolbar"> ...buttons... </div>
 *   </div>
 *   <script type="text/x-mermaid" id="src-XYZ"> ...diagram source... </script>
 *
 * Visibility rule: svg-pan-zoom cannot initialize on a hidden container
 * (its computed width/height would be zero), so for hidden diagrams we
 * only inject the SVG and defer pan-zoom setup until the tab becomes
 * visible (loops.html's show() calls window.cbimRefitDiagram).
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

  function isVisible(el) {
    return !!(el && (el.offsetWidth > 0 || el.offsetHeight > 0));
  }

  function setupPanZoom(el) {
    if (typeof svgPanZoom === 'undefined') return;
    var svg = el.querySelector('svg');
    if (!svg) return;
    if (!isVisible(el)) {
      // Defer — will retry when tab becomes visible
      el._needsPanZoom = true;
      return;
    }
    // Container is visible; safe to size SVG + attach pan-zoom
    svg.removeAttribute('height');
    svg.removeAttribute('width');
    svg.style.maxWidth = '100%';
    svg.style.width = '100%';
    svg.style.height = '100%';

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
        zoomScaleSensitivity: 0.3,
        contain: false
      });
      el._needsPanZoom = false;
    } catch (e) {
      el._needsPanZoom = true;
    }
  }

  function refit(el) {
    if (!el || !el._panZoom) return;
    setTimeout(function () {
      try {
        el._panZoom.resize();
        el._panZoom.fit();
        el._panZoom.center();
      } catch (e) {}
    }, 50);
  }

  /* Exposed: called from tab switch — first-time setup or refit. */
  window.cbimRefitDiagram = function (el) {
    if (!el) return;
    if (el._needsPanZoom && !el._panZoom) {
      setupPanZoom(el);
    } else if (el._panZoom) {
      refit(el);
    } else if (el.querySelector('svg')) {
      // SVG present but pan-zoom not yet attached — try now
      setupPanZoom(el);
    }
  };

  /* Render diagrams sequentially (avoid races in mermaid internal state). */
  async function renderAll() {
    if (typeof mermaid === 'undefined') return;
    var dark = isDark();
    mermaid.initialize({
      startOnLoad: false,
      theme: dark ? 'dark' : 'default',
      themeVariables: themeVars(dark),
      flowchart: { htmlLabels: true, useMaxWidth: true, curve: 'basis' }
    });
    var targets = document.querySelectorAll('.mermaid-target[data-source]');
    for (var i = 0; i < targets.length; i++) {
      var el = targets[i];
      var srcId = el.getAttribute('data-source');
      var srcEl = document.getElementById(srcId);
      if (!srcEl) continue;
      var source = srcEl.textContent.trim();
      var id = 'm-' + srcId + '-' + Date.now() + '-' + i;
      try {
        // Reset any previous render state on theme switch
        if (el._panZoom) {
          try { el._panZoom.destroy(); } catch (e) {}
          el._panZoom = null;
        }
        el._needsPanZoom = false;

        var result = await mermaid.render(id, source);
        el.innerHTML = result.svg;
        if (result.bindFunctions) result.bindFunctions(el);
        setupPanZoom(el);
      } catch (err) {
        showError(el, err);
      }
    }
  }

  /* ── Toolbar handlers (exposed on window) ── */
  function getTargetFrom(btn) {
    var wrap = btn.closest('.mermaid-wrap');
    return wrap ? wrap.querySelector('.mermaid-target') : null;
  }

  window.diagramZoom = function (btn, action) {
    var el = getTargetFrom(btn);
    if (!el) return;
    // Lazy-init if needed
    if (!el._panZoom) setupPanZoom(el);
    if (!el._panZoom) return;
    if (action === 'in')        el._panZoom.zoomBy(1.25);
    else if (action === 'out')  el._panZoom.zoomBy(0.8);
    else if (action === 'reset') {
      el._panZoom.resetZoom();
      el._panZoom.resetPan();
      el._panZoom.fit();
      el._panZoom.center();
    }
  };

  window.diagramFullscreen = function (btn) {
    var wrap = btn.closest('.mermaid-wrap');
    if (!wrap) return;
    wrap.classList.toggle('fullscreen');
    var target = wrap.querySelector('.mermaid-target');
    setTimeout(function () {
      window.cbimRefitDiagram(target);
    }, 100);
  };

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.mermaid-wrap.fullscreen').forEach(function (w) {
        w.classList.remove('fullscreen');
        var t = w.querySelector('.mermaid-target');
        setTimeout(function () { window.cbimRefitDiagram(t); }, 100);
      });
    }
  });

  /* Boot */
  renderAll();
  document.addEventListener('cbim-theme-changed', renderAll);

  /* Refit on viewport resize */
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      document.querySelectorAll('.mermaid-target').forEach(function (el) {
        if (el._panZoom) refit(el);
        else if (isVisible(el) && el.querySelector('svg')) setupPanZoom(el);
      });
    }, 200);
  });
})();
