// SPDX-License-Identifier: AGPL-3.0-only
// Pine Workspace - PineTS thin adapter (normalization of the execution output, loaded by the runner).
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
// Normalization of a PineTS execution Context into a canonical payload.
//
// SCHEMA IDENTITY: pws-pinets-norm-v2. Any behavioral change to this module
// MUST bump the schema id — the id is the declared semantic identity of the
// normalization inside the calibration triplet
// (pinets_version + executor_fingerprint + normalization_schema), and the
// bump correctly stales calibrations.
//
// v2 (2026-09-05): identical to v1 except alert ordering uses locale-
// INDEPENDENT code-unit comparison. v1 used String.localeCompare, whose
// result depends on the Intl locale fixed from the AMBIENT environment at
// process startup — two machines with identical fingerprints could order
// alerts differently (adversarial review 2026-09-05). No other change.
//
// contract:
// - plots: user plot titles only; PineTS internal channels (keys starting
//   with "__", e.g. __labels__/__tables__) are EXCLUDED from the payload and
//   listed in internal_keys_present (drawing/table semantics are not part of
//   the v1 behavioral contract).
// - duplicate titles: PineTS already disambiguates collisions with a "#N"
//   callsite suffix; keys are kept verbatim and sorted lexicographically.
// - each point: { t: <bar openTime ms>, v: <number|null> }. Non-finite
//   numbers (NaN/±Infinity) and na are normalized to null.
// - values are rounded to 12 significant digits (documented determinism
//   guard against float formatting drift; IEEE754 doubles are already
//   platform-deterministic for the operations involved).
// - alerts: { bar_index, time, type, id, message } sorted by (time, id).
// - warnings: messages in emission order.

import { createHash } from 'node:crypto';

export const NORMALIZATION_SCHEMA = 'pws-pinets-norm-v2';

function codeUnitCompare(a, b) {
  const sa = String(a), sb = String(b);
  return sa < sb ? -1 : sa > sb ? 1 : 0;
}

export function roundValue(v) {
  if (v === null || v === undefined || typeof v !== 'number' || !Number.isFinite(v)) return null;
  if (v === 0) return 0;
  const rounded = Number(v.toPrecision(12));
  // avoid -0 in the canonical payload
  return Object.is(rounded, -0) ? 0 : rounded;
}

export function normalizeContext(ctx) {
  const plots = {};
  const internal = [];
  for (const key of Object.keys(ctx.plots ?? {}).sort()) {
    if (key.startsWith('__')) {
      internal.push(key);
      continue;
    }
    const series = ctx.plots[key]?.data ?? [];
    plots[key] = series.map(pt => ({ t: pt.time ?? null, v: roundValue(pt.value) }));
  }
  const alerts = (ctx.alerts ?? []).map(a => ({
    bar_index: a.bar_index ?? null,
    time: a.time ?? null,
    type: a.type ?? null,
    id: a.id ?? null,
    message: a.message ?? null,
  })).sort((a, b) => (a.time ?? 0) - (b.time ?? 0) || codeUnitCompare(a.id, b.id));
  const warnings = (ctx.warnings ?? []).map(w => (typeof w === 'string' ? w : w?.message ?? null));
  return {
    schema: NORMALIZATION_SCHEMA,
    plots,
    alerts,
    warnings,
    internal_keys_present: internal,
  };
}

export function canonicalPayloadText(payload) {
  return JSON.stringify(sortKeys(payload));
}

export function payloadSha256(payload) {
  return createHash('sha256').update(canonicalPayloadText(payload)).digest('hex');
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
