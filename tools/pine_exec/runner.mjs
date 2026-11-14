// SPDX-License-Identifier: AGPL-3.0-only
// Pine Workspace - PineTS thin adapter (runner: loads PineTS in this process and executes a Pine source on a local dataset).
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
// PineTS thin adapter runner (spec section 24.4).
//
// Responsibility, strictly bounded:
//   Pine source + local dataset + configuration + capability state
//     -> PineTS -> normalized output + fully identified run report.
// Not a platform, server, MCP, database, dashboard, backtesting framework or
// TradingView clone. PINETS_EXECUTION_PASS never means TV_VALIDATED.
//
// capabilities_used detection: closed-world LEXICAL classifier v2
// (capabilities_detection: "lexical-closed-world-v2"). Every token of the
// comment/string-stripped source must be accounted for: known constructs map
// to capabilities, neutral tokens (literals, punctuation, named-argument
// labels, locally defined names) are covered, and ANYTHING else lands in
// unclassified_tokens. An empty unclassified list therefore means every
// token was recognized — but the classifier remains lexical: any pertinent
// ambiguity or unclassified token forces the non-gating / INCONCLUSIVE path
// (spec section 24.4.6); it is never a semantic proof.
//
// Calibration freshness is DERIVED PER RUN (audit F4): the manifest's
// calibration_status is only trusted when the CURRENT triplet
// (pinets_version + executor_fingerprint + normalization_schema) matches the
// calibrated one AND every calibration case artifact hash verifies;
// otherwise CURRENT degrades to STALE for this run. capability_status is
// always preserved (an environment drift never rewrites it).
//
// Usage:
//   node runner.mjs run --source F.pine --dataset F.json [--config F.json]
//                       [--calibration DIR] [--out F.json]
//   node runner.mjs matrix --manifest M.json --out-dir DIR [--calibration DIR]
//   node runner.mjs compare --a run1.json --b run2.json
// Writing under any validation/ directory is REFUSED (spec section 24.4.11).
// Matrix runs are explicit and bounded. No hook ever invokes this runner.

import { createHash, randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { loadDataset } from './datasets.mjs';
import { computeFingerprint, enforceControlledEnv } from './fingerprint.mjs';
import { NORMALIZATION_SCHEMA, normalizeContext, payloadSha256 } from './normalize.mjs';

enforceControlledEnv();

const HERE = dirname(fileURLToPath(import.meta.url));

function sha256(buf) { return createHash('sha256').update(buf).digest('hex'); }

function sortKeys(obj) {
  if (Array.isArray(obj)) return obj.map(sortKeys);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const k of Object.keys(obj).sort()) out[k] = sortKeys(obj[k]);
    return out;
  }
  return obj;
}

function pinetsVersion() {
  const p = join(HERE, 'node_modules', 'pinets', 'package.json');
  if (!existsSync(p)) return null;
  return JSON.parse(readFileSync(p, 'utf8')).version;
}

// --- closed-world lexical classifier (v2) ----------------------------------
const KNOWN_NAMESPACES = new Set(['ta', 'math', 'request', 'array', 'matrix', 'map',
  'str', 'color', 'input', 'strategy', 'syminfo', 'barstate', 'timeframe', 'chart',
  'label', 'line', 'box', 'table', 'polyline', 'linefill', 'runtime', 'ticker',
  'session', 'time', 'dayofweek', 'log', 'alert', 'adjustment', 'backadjustment',
  'barmerge', 'currency', 'dividends', 'earnings', 'font', 'format', 'hline',
  'location', 'order', 'plot', 'position', 'scale', 'settlement', 'shape',
  'size', 'splits', 'text', 'xloc', 'yloc', 'display', 'extend']);
const PLOT_FUNCS = new Set(['plot', 'plotshape', 'plotchar', 'plotcandle', 'plotbar',
  'plotarrow', 'bgcolor', 'barcolor', 'fill', 'hline']);
const DECL_FUNCS = new Set(['indicator', 'strategy', 'library']);
const SERIES_BUILTINS = new Set(['close', 'open', 'high', 'low', 'volume', 'hl2',
  'hlc3', 'ohlc4', 'bar_index', 'last_bar_index', 'time', 'time_close',
  'timenow', 'last_bar_time']);
const GLOBAL_FUNCS = new Set(['alertcondition', 'alert', 'nz', 'na', 'fixnan',
  'timestamp', 'fixnan', 'max_bars_back', 'barssince']);
const KEYWORD_CAPS = {
  var: 'state-var', varip: 'state-varip',
  if: 'control-flow', else: 'control-flow', for: 'control-flow', to: 'control-flow',
  by: 'control-flow', while: 'control-flow', switch: 'control-flow',
  and: 'logic-op', or: 'logic-op', not: 'logic-op',
  import: 'library-import', export: 'library-export',
  method: 'declaration-method', type: 'declaration-type', enum: 'declaration-enum',
};
const TYPE_KEYWORDS = new Set(['int', 'float', 'bool', 'string', 'color', 'line',
  'label', 'box', 'table', 'linefill', 'polyline', 'array', 'matrix', 'map',
  'chart', 'const', 'simple', 'series']);
const NEUTRAL_IDENTIFIERS = new Set(['true', 'false', 'na', 'in']);

function stripCommentsAndStrings(line) {
  let out = '', inStr = null;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (c === '\\') { i++; continue; }
      if (c === inStr) { inStr = null; out += '\x00'; continue; }
      continue;
    }
    if (c === '"' || c === "'") { inStr = c; continue; }
    if (c === '/' && line[i + 1] === '/') break;
    out += c;
  }
  return out;
}

function parenBalance(line) {
  let bal = 0;
  for (const c of line) {
    if (c === '(' || c === '[') bal++;
    else if (c === ')' || c === ']') bal--;
  }
  return bal;
}

function collectLocalNames(lines) {
  // Declarations are only collected on lines that START at paren balance 0:
  // a continuation line of a wrapped call (e.g. a named argument `foo="X"`)
  // must never register `foo` as a local — that would hide genuinely
  // unknown constructs (adversarial review 2026-09-05, locals pollution).
  const locals = new Set();
  let balance = 0;
  for (const line of lines) {
    const startsAtTopLevel = balance === 0;
    balance += parenBalance(line);
    if (balance < 0) balance = 0;
    if (!startsAtTopLevel) continue;
    let m;
    // function/method definition + parameters
    m = line.match(/^\s*(?:export\s+)?(?:method\s+)?([A-Za-z_]\w*)\s*\(([^)]*)\)\s*=>/);
    if (m) {
      locals.add(m[1]);
      for (const part of m[2].split(',')) {
        const words = part.trim().split(/\s+/).filter(Boolean);
        if (words.length) locals.add(words[words.length - 1].replace(/=.*$/, ''));
      }
      continue;
    }
    // variable declaration / reassignment target (optionally typed / var)
    m = line.match(/^\s*(?:var(?:ip)?\s+)?(?:[A-Za-z_]\w*(?:<[^>]*>)?\s+)?([A-Za-z_]\w*)\s*(?::=|=)(?![=>])/);
    if (m) locals.add(m[1]);
    // tuple destructuring
    m = line.match(/^\s*\[([^\]]+)\]\s*=(?![=>])/);
    if (m) for (const name of m[1].split(',')) locals.add(name.trim());
    // for loops
    m = line.match(/^\s*for\s+(?:\[([^\]]+)\]|([A-Za-z_]\w*))/);
    if (m) {
      if (m[1]) for (const name of m[1].split(',')) locals.add(name.trim());
      if (m[2]) locals.add(m[2]);
    }
    // type declaration fields: "  <type> <name>" inside a type block is
    // covered by member access on the local instance, no collection needed.
  }
  locals.delete('');
  return locals;
}

export function classifyCapabilities(sourceText) {
  const rawLines = sourceText.split('\n');
  const lines = rawLines.map(stripCommentsAndStrings);
  const locals = collectLocalNames(lines);
  const used = new Set();
  const unclassified = new Set();

  const memberRe = /[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)+/g;
  const tokenRe = /[A-Za-z_]\w*|\d+(?:\.\d+)?|#[0-9A-Fa-f]+|:=|==|!=|<=|>=|=>|\?\?|[+\-*\/%<>=\[\](),?:@\x00]|\S/g;

  for (let line of lines) {
    if (/^\s*\/\/@/.test(line)) continue; // annotations live in comments
    // member chains first (namespace access OR call: both count — audit F5)
    line = line.replace(memberRe, chain => {
      const parts = chain.split('.').map(s => s.trim());
      const head = parts[0];
      // full dotted tail: strategy.risk.allow_entry_in must not collapse to
      // 'strategy-risk' (granularity, spec 24.4.4)
      if (KNOWN_NAMESPACES.has(head)) used.add([head, ...parts.slice(1)].join('-'));
      else if (locals.has(head)) used.add('udt-member-access');
      else unclassified.add(chain.replace(/\s+/g, ''));
      return ' ';
    });

    const tokens = line.match(tokenRe) || [];
    for (let i = 0; i < tokens.length; i++) {
      const t = tokens[i];
      const prev = tokens[i - 1] ?? '';
      const next = tokens[i + 1] ?? '';
      if (/^[A-Za-z_]/.test(t)) {
        // named-argument label: ident '=' right after '(' or ','
        if (next === '=' && (prev === '(' || prev === ',')) continue;
        if (t in KEYWORD_CAPS) { used.add(KEYWORD_CAPS[t]); continue; }
        if (NEUTRAL_IDENTIFIERS.has(t)) continue;
        if (SERIES_BUILTINS.has(t)) { used.add('series-builtin'); continue; }
        if (PLOT_FUNCS.has(t)) { used.add(`plot-${t}`); continue; }
        if (DECL_FUNCS.has(t)) { used.add(`declaration-${t}`); continue; }
        if (t === 'alertcondition' || t === 'alert') { used.add('alert'); continue; }
        if (GLOBAL_FUNCS.has(t)) { used.add(`builtin-${t}`); continue; }
        if (TYPE_KEYWORDS.has(t)) { used.add('type-annotation'); continue; }
        if (locals.has(t)) continue; // locals shadow namespace-like names
        if (KNOWN_NAMESPACES.has(t)) { used.add(t); continue; } // legacy bare call
        unclassified.add(t);
        continue;
      }
      if (/^\d/.test(t) || /^#[0-9A-Fa-f]+$/.test(t) || t === '\x00') continue; // literals
      switch (t) {
        case '+': case '-': case '*': case '/': case '%':
          used.add('math-arith'); break;
        case '==': case '!=': case '<': case '>': case '<=': case '>=':
          used.add('compare-op'); break;
        case '?': used.add('control-ternary'); break;
        case ':': break; // ternary else-branch / switch arm — covered
        case ':=': used.add('state-reassign'); break;
        case '=>': used.add('declaration-function'); break;
        case '[':
          if (/[\w\)\]]$/.test(prev)) used.add('series-history');
          break; // tuple bracket otherwise — covered
        case ']': case '(': case ')': case ',': case '=': break;
        default:
          unclassified.add(`op:${t}`);
      }
    }
  }
  return { used: [...used].sort(), unclassified: [...unclassified].sort() };
}

// --- calibration state, derived per run ------------------------------------
export function loadCalibrationState(calibrationDir) {
  const dir = calibrationDir ?? join(HERE, 'calibration');
  const manifestPath = join(dir, 'capabilities.json');
  if (!existsSync(manifestPath)) return null;
  let manifest;
  const manifestBytes = (() => { try { return readFileSync(manifestPath); } catch { return null; } })();
  try { manifest = JSON.parse(manifestBytes.toString('utf8')); }
  catch { return { manifest: null, manifest_sha256: null, environment_match: false, artifact_failures: ['capabilities.json unreadable'], verified_artifacts: new Set() }; }
  if (typeof manifest !== 'object' || manifest === null || Array.isArray(manifest)) {
    return { manifest: null, manifest_sha256: sha256(manifestBytes), environment_match: false, artifact_failures: ['capabilities.json is not an object'], verified_artifacts: new Set() };
  }
  const env = (manifest.environment && typeof manifest.environment === 'object') ? manifest.environment : {};
  const environment_match =
    env.pinets_version === pinetsVersion() &&
    env.executor_fingerprint === computeFingerprint().executor_fingerprint &&
    env.normalization_schema === NORMALIZATION_SCHEMA;
  const artifact_failures = [];
  const verified_artifacts = new Set();
  const artifacts = (manifest.case_artifacts && typeof manifest.case_artifacts === 'object')
    ? manifest.case_artifacts : {};
  // artifact paths are PHYSICALLY confined to the calibration directory
  // (targeted review 2026-09-06): a traversal or symlink escaping it is an
  // artifact failure, never calibration evidence — same rule as the doctor.
  let realDir;
  try { realDir = realpathSync(dir); } catch { realDir = resolve(dir); }
  for (const [name, art] of Object.entries(artifacts)) {
    if (!art || typeof art.path !== 'string' || typeof art.sha256 !== 'string') {
      artifact_failures.push(name);
      continue;
    }
    try {
      const real = realpathSync(join(dir, art.path));
      if (real !== realDir && !real.startsWith(realDir + sep)) {
        artifact_failures.push(name);
        continue;
      }
      if (sha256(readFileSync(real)) === art.sha256) verified_artifacts.add(name);
      else artifact_failures.push(name);
    } catch {
      artifact_failures.push(name);
    }
  }
  return { manifest, manifest_sha256: sha256(manifestBytes), environment_match,
           artifact_failures, verified_artifacts };
}

function deriveCapabilityState(entry, calibState) {
  // capability_status is PRESERVED; only the calibration freshness is
  // derived against the current triplet + artifact integrity.
  //
  // Common contract (3rd external audit, item 5): CURRENT requires the
  // capability's EXPLICIT evidence_artifacts list to be (a) non-empty,
  // (b) fully verified (hash-checked), and (c) contain at least one artifact
  // carrying reference_provenance — the independent reference of spec
  // 24.4.5; a case source file alone is NOT calibration evidence. Staleness
  // is scoped: a failing artifact only stales the capabilities that list it,
  // never unconcerned ones. An environment mismatch stales every CURRENT.
  const status = entry?.capability_status ?? 'EXPERIMENTAL';
  let calib = entry?.calibration_status ?? 'MISSING';
  if (calib === 'CURRENT') {
    const evidence = Array.isArray(entry?.evidence_artifacts) ? entry.evidence_artifacts : [];
    const artifacts = (calibState?.manifest?.case_artifacts
      && typeof calibState.manifest.case_artifacts === 'object')
      ? calibState.manifest.case_artifacts : {};
    const allVerified = evidence.length > 0
      && evidence.every(name => calibState?.verified_artifacts?.has(name));
    const hasIndependentReference = evidence.some(name =>
      artifacts[name] && typeof artifacts[name].reference_provenance === 'string'
      && artifacts[name].reference_provenance);
    if (!calibState || !calibState.environment_match
        || !allVerified || !hasIndependentReference) {
      calib = 'STALE';
    }
  }
  return { capability_status: status, calibration_status: calib };
}

// --- validation/ write refusal (spec section 24.4.11, audit F6c) -----------
// Physical, symlink-resolving and case-insensitive: the adversarial review
// (2026-09-05) bypassed the lexical check via APFS case-insensitivity
// (VALIDATION/) and via a symlinked directory pointing into validation/.
function deepestExistingRealpath(path) {
  let p = resolve(path);
  const missing = [];
  while (!existsSync(p)) {
    missing.unshift(p.split(sep).pop());
    const parent = dirname(p);
    if (parent === p) break;
    p = parent;
  }
  try { p = realpathSync(p); } catch { /* keep resolved form */ }
  return missing.length ? join(p, ...missing) : p;
}

export function refusesValidationDestination(path) {
  return deepestExistingRealpath(path).split(sep)
    .some(seg => seg.toLowerCase() === 'validation');
}

function assertWritableDestination(path, what) {
  if (refusesValidationDestination(path)) {
    console.error(`pine_exec: refusing to write ${what} under a validation/ `
      + `directory (${path}) — validation/ is exclusively for TradingView `
      + 'observations (spec 24.4.11).');
    process.exit(4);
  }
}

// --- single run ------------------------------------------------------------
export async function runOnce({ sourcePath, datasetPath, config, calibrationDir }) {
  const sourceBytes = readFileSync(sourcePath);
  const sourceText = sourceBytes.toString('utf8');
  const dataset = loadDataset(datasetPath);
  const caps = classifyCapabilities(sourceText);
  const calibState = loadCalibrationState(calibrationDir);
  const calibEntries = calibState?.manifest?.capabilities ?? {};
  const capabilitiesUsed = {};
  for (const cap of caps.used) {
    capabilitiesUsed[cap] = deriveCapabilityState(calibEntries[cap], calibState);
  }

  const report = {
    schema: 'pws-pinets-run-v1',
    run_id: `pexec-${randomUUID()}`,
    timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    source: resolve(sourcePath),
    source_sha256: sha256(sourceBytes),
    dataset: resolve(datasetPath),
    dataset_sha256: dataset.dataset_sha256,
    dataset_descriptor: dataset.descriptor,
    configuration: config ?? {},
    pinets_version: pinetsVersion(),
    executor_fingerprint: computeFingerprint().executor_fingerprint,
    normalization_schema: NORMALIZATION_SCHEMA,
    capabilities_used: capabilitiesUsed,
    capabilities_detection: 'lexical-closed-world-v2',
    unclassified_tokens: caps.unclassified,
    calibration_environment_match: calibState ? calibState.environment_match : null,
    calibration_artifact_failures: calibState ? calibState.artifact_failures : null,
    calibration_manifest_sha256: calibState ? calibState.manifest_sha256 : null,
    execution_status: null,
    error: null,
    normalized: null,
    normalized_payload_sha256: null,
  };

  try {
    const { PineTS, Indicator } = await import('pinets');
    const pineTS = new PineTS(dataset.candles);
    let code = sourceText;
    if (config?.inputs && Object.keys(config.inputs).length > 0) {
      const ind = new Indicator(sourceText);
      for (const [k, v] of Object.entries(config.inputs)) ind.input[k] = v;
      code = ind;
    }
    const ctx = await pineTS.run(code, config?.periods);
    report.execution_status = 'PINETS_EXECUTION_PASS';
    report.normalized = normalizeContext(ctx);
    report.normalized_payload_sha256 = payloadSha256(report.normalized);
  } catch (err) {
    report.execution_status = 'PINETS_EXECUTION_FAIL';
    report.error = { message: String(err?.message ?? err) };
  }
  return report;
}

// --- regression comparison (spec section 24.4.9, audit F6f) ----------------
export function compareRuns(a, b) {
  const reasons = [];
  // shape validation BEFORE semantics (a malformed report must never yield a
  // false UNCHANGED). Common contract, 3rd external audit item 4: BOTH runs
  // must carry present, well-typed identities AND their normalized payload —
  // equality of self-declared hashes alone proves nothing.
  const HEX64 = /^[0-9a-f]{64}$/;
  const isPlainObject = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  for (const [tag, r] of [['a', a], ['b', b]]) {
    if (!r || typeof r !== 'object' || r.schema !== 'pws-pinets-run-v1') {
      reasons.push(`malformed_report_${tag}:schema`);
      continue;
    }
    // FULL run identity (spec 24.4.6) must be PRESENT and typed — absence is
    // never defaulted away (4th external audit, item 3). source_sha256 is
    // required on both sides but MAY differ (comparing two source versions).
    if (typeof r.run_id !== 'string' || !r.run_id) reasons.push(`malformed_report_${tag}:run_id`);
    if (typeof r.timestamp !== 'string'
        || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(r.timestamp)) {
      reasons.push(`malformed_report_${tag}:timestamp`);
    }
    if (!HEX64.test(r.source_sha256 ?? '')) reasons.push(`malformed_report_${tag}:source_sha256`);
    if (!HEX64.test(r.dataset_sha256 ?? '')) reasons.push(`malformed_report_${tag}:dataset_sha256`);
    if (!isPlainObject(r.dataset_descriptor)) reasons.push(`malformed_report_${tag}:dataset_descriptor`);
    if (!isPlainObject(r.configuration)) reasons.push(`malformed_report_${tag}:configuration`);
    if (!isPlainObject(r.capabilities_used)) reasons.push(`malformed_report_${tag}:capabilities_used`);
    if (typeof r.pinets_version !== 'string' || !r.pinets_version) reasons.push(`malformed_report_${tag}:pinets_version`);
    if (!HEX64.test(r.executor_fingerprint ?? '')) reasons.push(`malformed_report_${tag}:executor_fingerprint`);
    if (typeof r.normalization_schema !== 'string' || !r.normalization_schema) reasons.push(`malformed_report_${tag}:normalization_schema`);
    if (!r.normalized || typeof r.normalized !== 'object' || Array.isArray(r.normalized)) {
      reasons.push(`malformed_report_${tag}:normalized`);
      continue;
    }
    if (!HEX64.test(r.normalized_payload_sha256 ?? '')) {
      reasons.push(`malformed_report_${tag}:normalized_payload_sha256`);
    } else if (payloadSha256(r.normalized) !== r.normalized_payload_sha256) {
      reasons.push(`malformed_report_${tag}:payload_sha_mismatch`);
    }
  }
  if (reasons.length) {
    return { comparable: false, status: 'PINETS_INCONCLUSIVE', reasons,
             note: 'malformed run report(s) — a regression conclusion would be unfounded' };
  }
  for (const k of ['dataset_sha256', 'pinets_version', 'executor_fingerprint',
                   'normalization_schema']) {
    if (a[k] !== b[k]) reasons.push(k);
  }
  if (JSON.stringify(sortKeys(a.configuration))
      !== JSON.stringify(sortKeys(b.configuration))) reasons.push('configuration');
  if (a.execution_status !== 'PINETS_EXECUTION_PASS'
      || b.execution_status !== 'PINETS_EXECUTION_PASS') reasons.push('execution_status');
  if (reasons.length) {
    return { comparable: false, status: 'PINETS_INCONCLUSIVE',
             reasons,
             note: 'runs are not comparable — a regression conclusion would be unfounded' };
  }
  if (a.normalized_payload_sha256 === b.normalized_payload_sha256) {
    return { comparable: true, status: 'PINETS_REGRESSION_UNCHANGED', changed: [] };
  }
  const changed = [];
  const keys = new Set([...Object.keys(a.normalized?.plots ?? {}),
                        ...Object.keys(b.normalized?.plots ?? {})]);
  for (const k of [...keys].sort()) {
    const sa = a.normalized?.plots?.[k] ?? null;
    const sb = b.normalized?.plots?.[k] ?? null;
    if (JSON.stringify(sa) !== JSON.stringify(sb)) {
      let idx = null;
      if (Array.isArray(sa) && Array.isArray(sb)) {
        const n = Math.max(sa.length, sb.length);
        for (let i = 0; i < n; i++) {
          if (JSON.stringify(sa[i]) !== JSON.stringify(sb[i])) { idx = i; break; }
        }
      }
      changed.push({ plot: k, first_divergence_index: idx });
    }
  }
  // non-plot payload sections must stay actionable: a CHANGED verdict with an
  // empty diff list would hide WHERE the divergence lives (targeted review
  // 2026-09-06 — alerts/warnings-only differences)
  for (const section of ['alerts', 'warnings', 'internal_keys_present']) {
    if (JSON.stringify(a.normalized?.[section] ?? null)
        !== JSON.stringify(b.normalized?.[section] ?? null)) {
      changed.push({ section });
    }
  }
  if (changed.length === 0) {
    // the payload hashes differ but no enumerated section explains it
    // (crafted or future payload keys): never a CHANGED with an empty diff
    changed.push({ section: 'payload' });
  }
  return { comparable: true, status: 'PINETS_REGRESSION_CHANGED', changed,
           note: 'a difference is not automatically a bug — classify '
               + 'EXPECTED / UNEXPECTED / UNRESOLVED against the objective '
               + 'and impact inventory (spec 24.4.9)' };
}

// --- explicit bounded matrix ----------------------------------------------
export async function runMatrix({ manifestPath, outDir, calibrationDir }) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const base = dirname(resolve(manifestPath));
  const cells = [];
  if (Array.isArray(manifest.cells)) {
    manifest.cells.forEach((c, i) => cells.push({ index: i, dataset: c.dataset, config: c.config ?? {} }));
  } else if (Array.isArray(manifest.datasets)) {
    const configs = Array.isArray(manifest.configs) && manifest.configs.length ? manifest.configs : [{}];
    let i = 0;
    for (const d of manifest.datasets) for (const cfg of configs) cells.push({ index: i++, dataset: d, config: cfg });
  } else {
    throw new Error('matrix manifest needs cells[] or datasets[]');
  }
  mkdirSync(outDir, { recursive: true });
  const sourcePath = resolve(base, manifest.source);
  const out = {
    schema: 'pws-pinets-matrix-v1',
    matrix_id: `pmx-${randomUUID()}`,
    source: sourcePath,
    source_sha256: sha256(readFileSync(sourcePath)),
    cells: [],
  };
  for (const cell of cells) {
    const report = await runOnce({
      sourcePath,
      datasetPath: resolve(base, cell.dataset),
      config: cell.config,
      calibrationDir,
    });
    const reportFile = join(outDir, `cell-${cell.index}-${report.run_id}.json`);
    writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n', 'utf8');
    out.cells.push({
      index: cell.index,
      dataset: cell.dataset,
      dataset_sha256: report.dataset_sha256,
      config: cell.config,
      run_id: report.run_id,
      report: reportFile,
      execution_status: report.execution_status,
    });
  }
  const manifestOut = join(outDir, 'matrix.json');
  writeFileSync(manifestOut, JSON.stringify(out, null, 2) + '\n', 'utf8');
  return { manifest: manifestOut, cells: out.cells.length, matrix_id: out.matrix_id };
}

// --- CLI -------------------------------------------------------------------
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [cmd, ...rest] = process.argv.slice(2);
  const opts = {};
  for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = rest[i + 1];
  if (cmd !== 'compare' && !existsSync(join(HERE, 'node_modules', 'pinets'))) {
    console.error('pine_exec: node_modules missing — run `npm ci` in tools/pine_exec '
      + '(fresh checkout or worktree). This is never a defect of any Pine source.');
    process.exit(3);
  }
  // exit codes: 0 PASS / 1 PINETS_EXECUTION_FAIL (source-attributable) /
  // 2 usage / 3 node_modules missing / 4 validation-destination refused /
  // 5 infrastructure or input error (never a Pine source result)
  const infra = err => {
    console.error('pine_exec: infrastructure/input error, not a Pine source '
      + `result: ${String(err?.message ?? err)}`);
    process.exit(5);
  };
  if (cmd === 'run') {
    if (opts.out) assertWritableDestination(opts.out, 'a run report');
    let config = {};
    try {
      config = opts.config ? JSON.parse(readFileSync(opts.config, 'utf8')) : {};
    } catch (err) { infra(err); }
    runOnce({ sourcePath: opts.source, datasetPath: opts.dataset, config,
              calibrationDir: opts.calibration }).then(report => {
      const text = JSON.stringify(report, null, 2) + '\n';
      if (opts.out) writeFileSync(opts.out, text, 'utf8'); else process.stdout.write(text);
      process.exit(report.execution_status === 'PINETS_EXECUTION_PASS' ? 0 : 1);
    }).catch(infra);
  } else if (cmd === 'matrix') {
    assertWritableDestination(opts['out-dir'], 'matrix outputs');
    runMatrix({ manifestPath: opts.manifest, outDir: opts['out-dir'],
                calibrationDir: opts.calibration }).then(res => {
      console.log(JSON.stringify(res));
    }).catch(infra);
  } else if (cmd === 'compare') {
    let a, b;
    try {
      a = JSON.parse(readFileSync(opts.a, 'utf8'));
      b = JSON.parse(readFileSync(opts.b, 'utf8'));
    } catch (err) { infra(err); }
    console.log(JSON.stringify(compareRuns(a, b), null, 2));
  } else {
    console.error('usage: runner.mjs run --source F --dataset F [--config F] '
      + '[--calibration DIR] [--out F] | matrix --manifest F --out-dir D '
      + '[--calibration DIR] | compare --a RUN.json --b RUN.json');
    process.exit(2);
  }
}
