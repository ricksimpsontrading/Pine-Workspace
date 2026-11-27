// SPDX-License-Identifier: AGPL-3.0-only
// Pine Workspace - PineTS thin adapter (execution environment fingerprint, loaded by the runner and run on its own).
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
// executor_fingerprint — deterministic identity of the local execution
// environment (spec section 24.4.3).
//
// Covers: canonical manifest (relative path -> SHA-256) of every local
// artifact that can influence execution or normalization, exact Node
// version, platform/arch, and the CONTROLLED environment facts. The runner
// controls TZ/LANG/LC_ALL (UTC / C / C) rather than recording ambient
// values; NODE_OPTIONS is recorded (empty when unset). No secrets are ever
// included. The fingerprint never replaces source_sha256, dataset_sha256 or
// the per-run configuration — identities stay separate.

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

export const FINGERPRINTED_FILES = [
  'runner.mjs',
  'normalize.mjs',
  'datasets.mjs',
  'fingerprint.mjs',
  'graphics.mjs',
  'package.json',
  'package-lock.json',
];

export const CONTROLLED_ENV = { TZ: 'UTC', LANG: 'C', LC_ALL: 'C' };

// The announced controlled environment is ENFORCED, not merely declared
// (audit F4): every entry point (runner, fingerprint CLI) applies it to the
// live process before any execution or formatting can observe the ambient
// values. The fingerprint therefore records the environment actually used.
export function enforceControlledEnv() {
  for (const [key, value] of Object.entries(CONTROLLED_ENV)) {
    process.env[key] = value;
  }
}

function sha256(buf) {
  return createHash('sha256').update(buf).digest('hex');
}

export function computeFingerprint() {
  const files = {};
  for (const rel of FINGERPRINTED_FILES) {
    files[rel] = sha256(readFileSync(join(HERE, rel)));
  }
  const facts = {
    files,
    node_version: process.version,
    platform: process.platform,
    arch: process.arch,
    controlled_env: CONTROLLED_ENV,
    node_options: process.env.NODE_OPTIONS ?? '',
    // behavior-altering CLI flags (--require, --loader, ...) are part of the
    // executor identity (spec 24.4.3 'options Node.js pertinentes')
    exec_argv: process.execArgv,
  };
  const canonical = JSON.stringify(sortKeys(facts));
  return { executor_fingerprint: sha256(canonical), facts };
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

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  enforceControlledEnv();
  console.log(JSON.stringify(computeFingerprint(), null, 2));
}
