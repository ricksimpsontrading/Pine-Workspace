// SPDX-License-Identifier: AGPL-3.0-only
// Pine Workspace - PineTS thin adapter (EXPERIMENTAL graphics annex, isolated study copy only).
// Copyright (C) 2026 the copyright holder of Pine Workspace named in NOTICE.
//
// This program is free software: you can redistribute it and/or modify it
// under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, version 3 of the License only. It is
// distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
// without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
// PARTICULAR PURPOSE. See the GNU Affero General Public License in
// tools/pine_exec/LICENSE (https://www.gnu.org/licenses/agpl-3.0.html).
//
// Graphics annex — written by the SAME execution as the run report, next to it.
// It keeps what the canonical normalized payload drops: the declaration, the
// kind, options and per-point styles of every series, and the drawing objects.
// Experimental contract: GRAPHICS_SCHEMA below. The canonical payload and its
// hash are NOT changed by this module. v0.2: same content as v0.1; the run report now
// records the annex SHA-256 (runner.mjs, graphics_annex.sha256) and consumers require it.
//
// Known limits (engine 0.10.0): drawings are the FINAL state of the objects
// alive at the end of the run (deleted or moved objects keep no history);
// callsite ids follow the order of the plot-family calls; shapes, chars and
// bgcolor carry no callsite id.

export const GRAPHICS_SCHEMA = 'pws-pinets-graphics-v0.2-exp';

const DRAWING_KEYS = ['__labels__', '__lines__', '__boxes__', '__linefills__', '__polylines__', '__tables__'];

function cleanNumber(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'boolean') return v;
  if (v === null || v === undefined) return null;
  return null;
}

function cleanColor(c) {
  if (typeof c !== 'string' || c === '' || c === 'NaN') return null;
  return c;
}

function pickOptions(o) {
  const out = {};
  if (!o || typeof o !== 'object') return out;
  for (const k of ['style', 'color', 'linewidth', 'offset', 'location', 'shape', 'char', 'size', 'textcolor',
                   'plot1', 'plot2', 'display', 'force_overlay', 'overlay', 'trackprice', 'histbase', 'join',
                   'linestyle', 'editable', 'gradient']) {
    if (k in o && o[k] !== undefined) out[k] = k.endsWith('color') ? cleanColor(o[k]) : o[k];
  }
  return out;
}

// Per-point options other than the colour (kept separately): e.g. plotarrow
// shape/location, gradient fill top/bottom values and colours.
function pointOptions(o) {
  if (!o || typeof o !== 'object') return null;
  const out = {};
  for (const [k, v] of Object.entries(o)) {
    if (k === 'color' || v === undefined) continue;
    out[k] = k.endsWith('color') ? cleanColor(v) : (typeof v === 'number' ? cleanNumber(v) : v);
  }
  return Object.keys(out).length ? out : null;
}

function kindOf(options) {
  const s = options.style;
  if (!s) return 'line';
  return { shape: 'shape', char: 'char', hline: 'hline', background: 'background', fill: 'fill',
           barcolor: 'barcolor' }[s] || String(s);
}

export function extractGraphics(ctx) {
  const ind = ctx.indicator ?? {};
  const declaration = {};
  for (const k of ['title', 'shorttitle', 'overlay', 'format', 'precision', 'scale', 'max_bars_back',
                   'max_lines_count', 'max_labels_count', 'max_boxes_count', 'max_polylines_count']) {
    if (k in ind) declaration[k] = ind[k];
  }
  const series = [];
  const drawings = {};
  for (const key of Object.keys(ctx.plots ?? {}).sort()) {
    const p = ctx.plots[key];
    if (key.startsWith('__')) {
      const base = DRAWING_KEYS.find(d => key.startsWith(d.slice(0, -2)));
      if (!base) continue;
      const last = (p?.data ?? []).at(-1);
      const objs = Array.isArray(last?.value) ? last.value : [];
      const kind = base.slice(2, -2);
      drawings[kind] = (drawings[kind] ?? []).concat(objs.filter(o => !o?._deleted).map(o => ({
        ...JSON.parse(JSON.stringify(o, (k, v) => (typeof v === 'number' && !Number.isFinite(v) ? null : v))),
        channel: key,
      })));
      continue;
    }
    const options = pickOptions(p?.options);
    const baseColor = options.color ?? null;
    const points = (p?.data ?? []).map(pt => {
      const raw = pt?.value;
      const rec = { t: pt?.time ?? null, v: Array.isArray(raw) ? null : cleanNumber(raw) };
      if (Array.isArray(raw)) rec.ohlc = raw.map(cleanNumber);          // plotcandle / plotbar
      const c = cleanColor(pt?.options?.color);
      if (c !== baseColor) rec.color = c;
      const extra = pointOptions(pt?.options);                          // plotarrow shape, gradient fill
      if (extra) rec.o = extra;
      return rec;
    });
    series.push({ key, title: p?.title ?? key, callsite: p?._callsiteId ?? null, kind: kindOf(options),
                  options, points });
  }
  return {
    declaration,
    series,
    drawings,
    drawings_scope: 'final-state',
    limits: [
      'drawings: final state of the objects alive at the end of the run; no per-bar history',
      'callsite: order of plot-family calls in the transpiled source; absent for shapes, chars, bgcolor',
      'colors: as produced by the engine (#RRGGBB or #RRGGBBAA); null when na',
      'points: v is null and ohlc holds [o,h,l,c] for plotcandle/plotbar; o holds per-point options other than color',
    ],
  };
}
