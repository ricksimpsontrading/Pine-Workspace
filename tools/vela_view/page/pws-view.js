// SPDX-License-Identifier: Apache-2.0
// Pine Workspace — EXPERIMENTAL browser chart of a local test (isolated study copy).
//
// Vela draws the chart. It NEVER runs PineTS here: the scripting engine registered below
// ('pws') only REPLAYS the series that the PWS adapter (tools/pine_exec) already computed for
// one run — delivered by frame.js after the reader contract v1 checks (report, annex, dataset).
// Work page: frame.js is re-read every `poll_ms`; a new run updates the same indicator in this
// tab (handle.updateCode), without reloading the page. Pinned page (history): read once.
/* global Vela, PWS_VIEW */
(function () {
  'use strict';
  var cfg = window.PWS_VIEW || {};
  var LOAD = Math.random().toString(36).slice(2, 8);        // identity of this page load (same tab check)
  var frames = {};                                          // run_id -> chart model of the frame
  var state = { seq: null, runId: null, chart: null, handle: null, bars: null, updates: 0, frame: null,
                bar: null, timeIndex: {} };

  function el(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fmt(v, lang, d) {
    if (v === null || v === undefined || typeof v !== 'number' || !isFinite(v)) return 'NA';
    var s = v.toFixed(d == null ? 2 : d);
    return lang === 'fr' ? s.replace('.', ',') : s;
  }
  function date(ms) { return new Date(ms).toISOString().slice(0, 16).replace('T', ' ') + ' UTC'; }

  // ---------------------------------------------------------------- replay engine (no computation)
  function modelOf(c, instanceId) {
    var series = c.series.map(function (s, i) {
      return { id: instanceId + ':' + s.key, title: s.title, paneId: 'unrouted', kind: s.kind,
               style: { color: s.color, width: s.width, lineStyle: 'solid' },
               points: s.values.map(function (v, j) { return { time: c.times[j], value: v }; }) };
    });
    var priceLines = c.levels.map(function (l) {
      return { id: instanceId + ':' + l.key, paneId: 'unrouted', price: l.price, color: l.color,
               lineStyle: 'dashed', width: 1, title: l.title };
    });
    return { id: instanceId, title: c.title, overlay: c.overlay, paneHint: c.overlay ? 'price' : 'new',
             series: series, fills: [], backgrounds: [], priceLines: priceLines,
             inputs: [], inputValues: {} };
  }
  var engine = {
    language: 'pws',
    capabilities: { streaming: false, visibleRange: false, inputs: false },
    prepare: function (source, instanceId) {
      var runId = String(source).replace(/^pws-run:/, '');
      var c = frames[runId];
      if (!c) return Promise.reject(new Error('PWS: no result for run ' + runId));
      return Promise.resolve({ language: 'pws', inputs: [], meta: { title: c.title, overlay: c.overlay },
                               reactsToViewport: false, token: { runId: runId, instanceId: instanceId } });
    },
    execute: function (req, handlers) {
      var tok = req.prepared.token, c = frames[tok.runId];
      setTimeout(function () {
        handlers.onModel(modelOf(c, tok.instanceId));
        if (handlers.onDone) handlers.onDone();
      }, 0);
      return {
        stop: function () {}, update: function () {}, setVisibleRange: function () {}, notifyBars: function () {},
        getContext: function () {
          var plots = {};
          c.series.forEach(function (s) { plots[s.key] = s.values.map(function (v, j) { return { time: c.times[j], value: v }; }); });
          return Promise.resolve({ language: 'pws', phase: 'idle', barIndex: c.times.length - 1,
                                   meta: { title: c.title, overlay: c.overlay }, plots: plots, variables: {} });
        }
      };
    }
  };

  // ---------------------------------------------------------------- chart
  function barsOf(c) {
    return c.bars.map(function (b, j) { return { time: c.times[j], open: b[0], high: b[1], low: b[2], close: b[3],
                                                 volume: b[4] == null ? undefined : b[4] }; });
  }
  function sameBars(c) {
    return state.bars && state.bars.length === c.times.length && state.bars[0].time === c.times[0]
      && state.bars[state.bars.length - 1].time === c.times[c.times.length - 1]
      && state.bars[state.bars.length - 1].close === c.bars[c.bars.length - 1][3];
  }
  function show(c) {
    frames[c.run_id] = c;
    c.times.forEach(function (t, j) { state.timeIndex[t] = j; });
    if (!state.chart) {
      state.bars = barsOf(c);
      state.chart = new Vela.Vela('#chart', { symbol: 'PWS', timeframe: '60', data: state.bars, live: false,
                                               theme: 'dark', volume: false, locale: cfg.lang === 'fr' ? 'fr' : 'en' });
      state.chart.registerEngine('pws', engine);
      state.handle = state.chart.addIndicator('pws-run:' + c.run_id, { language: 'pws', id: 'pws-work' });
      state.handle.on('error', function (e) { state.velaError = (e && e.error && e.error.message) || 'error'; panel(); });
      state.handle.on('ready', function () { state.velaError = null; panel(); });
      try {
        state.chart.renderer.onCrosshairMove(function (e) {
          if (e && e.time != null && state.timeIndex[e.time] != null) { state.bar = state.timeIndex[e.time]; panel(); }
        });
      } catch (err) { /* crosshair readout is optional */ }
    } else {
      if (!sameBars(c)) { state.bars = barsOf(c); state.chart.setMarket({ data: state.bars }); }
      state.handle.updateCode('pws-run:' + c.run_id);        // same tab, same indicator: no reload
      state.updates += 1;
    }
    state.runId = c.run_id;
  }

  // ---------------------------------------------------------------- text panel (exact values)
  function panel() {
    var f = state.frame, T = (f && f.texts) || {}, lang = cfg.lang, c = f && f.chart;
    var head = '<b>' + esc(T.title || 'PWS') + '</b> <span class="dim">' + esc(cfg.mode === 'work' ? T.work : T.pinned) + '</span>';
    el('head').innerHTML = head;
    var m = el('msg');
    if (f && f.message) { m.style.display = 'block'; m.textContent = f.message; } else { m.style.display = 'none'; }
    if (!c) { el('side').innerHTML = ''; title(); return; }
    var n = c.times.length, b = state.bar == null ? n - 1 : Math.max(0, Math.min(n - 1, state.bar)), o = c.bars[b];
    var h = '<h3>' + esc(T.bar) + ' ' + b + '</h3><div class="dim">' + esc(date(c.times[b])) + '</div>'
      + '<div class="v">O ' + fmt(o[0], lang) + ' &nbsp;H ' + fmt(o[1], lang) + '<br>L ' + fmt(o[2], lang)
      + ' &nbsp;C ' + fmt(o[3], lang) + '</div><h3>' + esc(c.title) + '</h3>';
    c.series.forEach(function (s) { h += '<div class="v"><span class="k">' + esc(s.title) + '</span> ' + fmt(s.values[b], lang) + '</div>'; });
    c.levels.forEach(function (l) { h += '<div class="v"><span class="k">' + esc(l.title) + '</span> ' + fmt(l.price, lang) + '</div>'; });
    if (c.not_shown.length) h += '<div class="dim">' + esc(c.not_shown.join(', ')) + '</div>';
    h += '<h3>Run</h3><div class="v">' + esc(c.run_id) + (f.chart_is_last_good ? ' <span style="color:#f5a623">●</span>' : '') + '</div>'
      + '<h3>' + esc(T.revision) + '</h3><div class="v">' + esc(c.source_sha256.slice(0, 12)) + '</div>'
      + '<h3>' + esc(T.data) + '</h3><div>' + esc(c.dataset_label[lang] || c.dataset_label.en) + '</div>'
      + '<div class="dim">' + esc(c.dataset_id) + ' · ' + esc(c.dataset_sha256.slice(0, 12)) + '</div>'
      + '<h3>' + esc(T.engine) + '</h3><div class="dim">PineTS ' + esc(c.pinets_version) + ' · ' + esc((c.executor_fingerprint || '').slice(0, 8))
      + ' · annexe ' + esc(c.annex_version) + '</div>'
      + '<div class="dim">Vela ' + esc((window.__PWS_INTEGRITY || {}).vela_version) + ' · '
      + esc(((window.__PWS_INTEGRITY || {}).vela_sha256 || '').slice(0, 12)) + ((window.__PWS_INTEGRITY || {}).ok ? ' ✓' : ' ✗') + '</div>'
      + '<p class="dim">' + esc(T.final) + '</p><p class="dim">' + esc(T.not_tv) + '</p>'
      + '<p class="dim">' + (cfg.mode === 'work' ? state.updates + ' ' + esc(T.updates) + ' · ' : '') + 'page ' + LOAD + '</p>';
    el('side').innerHTML = h;
    title();
  }
  // the tab title mirrors what the page shows (read by Claude Code through AppleScript)
  function title() {
    var f = state.frame, c = f && f.chart, parts = ['PWS', cfg.mode, f ? f.state : 'loading'];
    if (c) {
      var n = c.times.length, b = state.bar == null ? n - 1 : state.bar;
      parts.push('run ' + c.run_id.slice(6, 14) + (f.chart_is_last_good ? ' (last good)' : ''));
      parts.push('bar ' + b);
      c.series.forEach(function (s) { parts.push(s.key + '=' + (s.values[b] == null ? 'NA' : s.values[b].toFixed(6))); });
    }
    if (state.chart) {
      try {
        var t = state.chart.inspect().totals;                  // what Vela itself reports as mounted
        parts.push('scene panes ' + t.panes + ' series ' + t.series + ' levels ' + t.priceLines);
      } catch (err) { parts.push('scene ?'); }
    }
    if (state.velaError) parts.push('VELA ERROR ' + state.velaError);
    if (state.exports) parts.push('export ' + state.exports + ' ' + state.lastExport);
    var I = window.__PWS_INTEGRITY || {};                    // set by the inline loader of index.html
    parts.push('vela ' + I.vela_version + ' ' + (I.vela_sha256 || '').slice(0, 12) + (I.ok ? ' verified' : ' UNVERIFIED'));
    var NET = window.__PWS_NET || [], hosts = {};
    NET.forEach(function (x) { var m = /^(\S+) [a-z]+:\/\/([^/:?#]+)/i.exec(x); if (m) hosts[m[1] + ':' + m[2]] = 1; });
    parts.push('net ' + NET.length + (NET.length ? ' ' + Object.keys(hosts).join(',') : ''));
    parts.push('upd ' + state.updates, 'load ' + LOAD);
    document.title = OB ? (obsState.title || 'PWS-OBS v1 | req=' + OB.req + ' | status=pending') : parts.join(' | ');
  }

  // ---------------------------------------------------------------- PNG export (Vela's native screenshot)
  // The image is Vela's own raster (chart.renderer.screenshot()): never a recomputation. The file
  // name carries the run shown at the moment of the click; the browser picks the folder (its
  // download settings).
  function note(text) { var m = el('msg'); m.style.display = 'block'; m.textContent = text; }
  function exportPng() {
    var X = cfg.texts || {};
    if (!state.chart || !state.runId) { note(X.export_no_chart || 'No chart shown.'); return; }
    var url = null;
    try { url = state.chart.renderer.screenshot(); } catch (err) { url = null; }
    if (!url || url.indexOf('data:image/png') !== 0) { note(X.export_none || 'No image.'); state.lastExport = 'none'; title(); return; }
    var name = 'pws-' + state.runId + '.png';
    var bin = atob(url.split(',')[1]), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var href = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    var a = document.createElement('a'); a.href = href; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(href); }, 60000);
    state.exports = (state.exports || 0) + 1; state.lastExport = name;
    note((X.export_done || '{name}').replace('{name}', name));
    title();
  }
  var btn = el('export');
  btn.textContent = (cfg.texts && cfg.texts.export) || 'Export PNG';
  btn.addEventListener('click', exportPng);


  // ---------------------------------------------------------------- observation in Vela (on request only)
  // Only when the page was opened for an observation (cfg.observe, written by PWS for ONE request):
  // simulated pointer moves bring Vela's crosshair onto the requested bar, then the value comes from
  // Vela's OWN crosshair event (CrosshairEvent.values), with its pane, and the data window text.
  // Bounded attempts; the answer goes to the tab title, read back by PWS (AppleScript), and ends
  // with 'end' so that a partial title is never taken for an answer.
  var OB = cfg.observe || null, obsState = { title: null };
  function obsTitle(fields) {
    var p = ['PWS-OBS v1', 'req=' + OB.req];
    Object.keys(fields).forEach(function (k) { p.push(k + '=' + String(fields[k]).replace(/\|/g, '/')); });
    p.push('end');                                         // final answer marker: a partial title has none
    obsState.title = p.join(' | '); document.title = obsState.title;
  }
  function pause(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  async function observeNow() {
    var c = state.frame.chart, bar = OB.bar, target = c.times[bar], key = OB.series;
    var I = window.__PWS_INTEGRITY || {}, vela = I.vela_version + ' ' + (I.vela_sha256 || '').slice(0, 12) + (I.ok ? ' verified' : ' UNVERIFIED');
    if (c.run_id !== OB.run_id || target !== OB.t) {
      obsTitle({ status: 'target-mismatch', run: c.run_id, series: key, bar: bar, t: target, pane: '', cursor_pane: '', value: '', datawindow: '', vela: vela });
      return;
    }
    var ind = (state.chart.inspect().indicators || [])[0] || {}, paneId = ind.paneId || '';
    var R = document.querySelector('#chart').getBoundingClientRect(), last = null;
    var y = R.top + R.height * (c.overlay ? 0.4 : 0.85);
    state.chart.renderer.onCrosshairMove(function (e) { last = e; });
    var lo = R.left + 2, hi = R.right - 80, tries = 0, x;
    while (lo <= hi && tries < 40) {
      tries += 1; x = (lo + hi) / 2; last = null;
      var el2 = document.elementFromPoint(x, y) || document.querySelector('#chart canvas');
      ['pointermove', 'mousemove'].forEach(function (type) {
        var Ev = type === 'pointermove' && window.PointerEvent ? PointerEvent : MouseEvent;
        el2.dispatchEvent(new Ev(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerType: 'mouse', isPrimary: true, view: window }));
      });
      await pause(60);
      if (!last || last.time == null) { hi = x - 1; continue; }
      if (last.time === target) break;
      if (last.time < target) lo = x + 1; else hi = x - 1;
    }
    if (!last || last.time !== target) {
      obsTitle({ status: 'not-reached', run: c.run_id, series: key, bar: bar, t: target, pane: paneId, cursor_pane: '', value: '', datawindow: '', vela: vela });
      return;
    }
    var v = last.values && last.values.get ? last.values.get('pws-work:' + key) : undefined, dw = '';
    try { (state.chart.renderer.dataWindowReadout().groups || []).forEach(function (g) { (g.rows || []).forEach(function (r) {
      var s = c.series.filter(function (z) { return z.key === key; })[0];
      if (s && r.label === s.title) dw = r.value; }); }); } catch (err) { dw = 'unavailable'; }
    obsTitle({ status: v === undefined ? 'no-value' : 'observed', run: c.run_id, series: key, bar: bar, t: last.time,
               pane: paneId, cursor_pane: (last.paneKind || '') + '/' + (last.paneId || ''), value: v === undefined ? '' : String(v),
               datawindow: dw, vela: vela });
  }
  // ---------------------------------------------------------------- frame intake
  window.PWS_FRAME = function (f) {
    if (state.seq === f.seq && state.frame && state.frame.state === f.state) return;
    state.seq = f.seq; state.frame = f;
    if (state.bar == null && cfg.bar != null) state.bar = cfg.bar;
    try { if (f.chart && f.chart.run_id !== state.runId) show(f.chart); }
    catch (err) { f.message = (f.message ? f.message + ' ' : '') + 'Vela: ' + err.message; }
    panel();
    if (OB && !OB.started && state.handle && f.chart) {
      OB.started = true;
      var go = function () { if (OB.running) return; OB.running = true; observeNow().catch(function (e) {
        obsTitle({ status: 'error ' + e.message }); }); };
      state.handle.on('ready', function () { setTimeout(go, 400); });
      setTimeout(go, 4000);                                  // bounded: if 'ready' was missed
    }
  };
  function poll() {
    var s = document.createElement('script');
    s.src = 'frame.js?t=' + Date.now();
    s.onload = s.onerror = function () { s.remove(); };
    document.head.appendChild(s);
  }
  poll();
  if (cfg.mode === 'work' && cfg.poll_ms > 0) setInterval(poll, cfg.poll_ms);
}());
