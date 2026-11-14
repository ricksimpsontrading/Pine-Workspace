// SPDX-License-Identifier: AGPL-3.0-only
// Pine Workspace - PineTS thin adapter (local reproducible datasets, loaded by the runner).
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
// Deterministic local datasets for the PineTS thin adapter.
//
// Single canonical writer: dataset files are ALWAYS produced by this module
// so dataset_sha256 (SHA-256 of the file bytes) is stable. All generator
// arithmetic is 32-bit integer (Math.imul) so an independent implementation
// (tools/tests/ref_indicators.py) can reproduce bars exactly.
// Prices are stored as integer cents (price_scale = 100); consumers divide.
//
// No network providers, ever. Imported snapshots are consumed as local files
// with explicit provenance in their descriptor.

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const GENERATOR_ID = 'lcg-ohlcv-v1';

function lcg(seed) {
  let x = seed >>> 0;
  return () => {
    x = (Math.imul(1664525, x) + 1013904223) >>> 0;
    return x;
  };
}

export function generateBars({ seed, bars, baseCents, volCents, t0Ms, tfMs }) {
  const next = lcg(seed);
  const out = [];
  let prevClose = baseCents;
  for (let i = 0; i < bars; i++) {
    const delta = (next() % (2 * volCents + 1)) - volCents;
    const o = prevClose;
    const c = o + delta;
    const h = Math.max(o, c) + (next() % volCents);
    const l = Math.min(o, c) - (next() % volCents);
    const v = 1000 + (next() % 9000);
    out.push({ t: t0Ms + i * tfMs, o, h, l, c, v });
    prevClose = c;
  }
  return out;
}

// Canonical serialization: fixed key order, no whitespace variance.
export function canonicalDatasetText(descriptor, bars) {
  const lines = [];
  lines.push('{"schema":"pws-dataset-v1",');
  lines.push('"descriptor":' + JSON.stringify(sortKeys(descriptor)) + ',');
  lines.push('"bars":[');
  lines.push(bars.map(b =>
    `{"t":${b.t},"o":${b.o},"h":${b.h},"l":${b.l},"c":${b.c},"v":${b.v}}`).join(',\n'));
  lines.push(']}');
  return lines.join('\n') + '\n';
}

function sortKeys(obj) {
  if (Array.isArray(obj)) return obj.map(sortKeys);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const k of Object.keys(obj).sort()) out[k] = sortKeys(obj[k]);
    return out;
  }
  return obj;
}

export function sha256(text) {
  return createHash('sha256').update(text).digest('hex');
}

export function writeSyntheticDataset(path, params) {
  const bars = generateBars(params);
  const descriptor = {
    type: 'synthetic',
    generator: GENERATOR_ID,
    params: {
      seed: params.seed, bars: params.bars, base_cents: params.baseCents,
      vol_cents: params.volCents, t0_ms: params.t0Ms, tf_ms: params.tfMs,
    },
    symbol: 'SYNTH',
    timeframe_ms: params.tfMs,
    timezone: 'UTC',
    price_scale: 100,
  };
  const text = canonicalDatasetText(descriptor, bars);
  writeFileSync(path, text, 'utf8');
  return { path, dataset_sha256: sha256(text), bars: bars.length };
}

export function loadDataset(path) {
  const raw = readFileSync(path);
  const data = JSON.parse(raw.toString('utf8'));
  if (data.schema !== 'pws-dataset-v1') {
    throw new Error(`unsupported dataset schema: ${data.schema}`);
  }
  const scale = data.descriptor.price_scale || 100;
  const candles = data.bars.map(b => ({
    open: b.o / scale, high: b.h / scale, low: b.l / scale, close: b.c / scale,
    volume: b.v, openTime: b.t,
  }));
  return {
    descriptor: data.descriptor,
    bars: data.bars,
    candles,
    dataset_sha256: createHash('sha256').update(raw).digest('hex'),
  };
}

// --- minimal CLI -----------------------------------------------------------
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [cmd, ...rest] = process.argv.slice(2);
  const opts = {};
  for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = rest[i + 1];
  if (cmd === 'gen') {
    const res = writeSyntheticDataset(opts.out, {
      seed: Number(opts.seed), bars: Number(opts.bars),
      baseCents: Number(opts['base-cents']), volCents: Number(opts['vol-cents']),
      t0Ms: Number(opts['t0-ms'] ?? Date.UTC(2020, 0, 1)), tfMs: Number(opts['tf-ms'] ?? 3600000),
    });
    console.log(JSON.stringify(res));
  } else if (cmd === 'hash') {
    const raw = readFileSync(opts.file ?? rest[0]);
    console.log(JSON.stringify({ dataset_sha256: createHash('sha256').update(raw).digest('hex') }));
  } else {
    console.error('usage: datasets.mjs gen --seed N --bars N --base-cents N --vol-cents N --out FILE | hash FILE');
    process.exit(2);
  }
}
