Pine Workspace (PWS)
Copyright 2026 Rick Simpson Trading

This product includes software developed as the Pine Workspace project
(tooling, skills, rules, agents, documentation and the master Pine Script V6
development standard). Its original components are licensed as follows
(per-component detail: docs/licensing/LICENSING.md):

- the core — every original component not listed below — under the Apache
  License, Version 2.0 (see LICENSE; SPDX: Apache-2.0);
- the PineTS thin adapter — tools/pine_exec/runner.mjs, normalize.mjs,
  datasets.mjs and fingerprint.mjs, with the package metadata that declares
  it (tools/pine_exec/package.json) — under the GNU Affero General Public
  License, version 3 only (see tools/pine_exec/LICENSE; SPDX: AGPL-3.0-only).

The adapter loads the third-party PineTS engine (AGPL-3.0-only, installed by
each user, never shipped) inside its own Node.js process. The Apache-2.0 core
never loads PineTS: its Python tooling starts the adapter as a separate
Node.js process (the doctor runs fingerprint.mjs; local runs are started by
the assistant and by the tests) and exchanges files and JSON with it; the
Apache-2.0 test suite also contains short JavaScript test snippets that import
adapter modules (never PineTS itself) into a Node.js process. The
distribution as a whole is therefore NOT under a single licence.

The attribution above identifies the authors of Pine Workspace itself. It is
never used as the identity of the scripts a user creates with Pine Workspace:
the copyright holder of a script created with Pine Workspace is the user
configured in `pws.config.json`, and its licence is chosen per project
(FREE / PRIVATE / COMMERCIAL profiles); an imported script keeps its original
authors, notices and existing licence. Using Pine Workspace does not place
the user's indicators under the Apache License.

The licence templates under docs/licensing/templates/ may be reused in the
user's own product documents without this attribution, under the Template
Permission (docs/licensing/TEMPLATE_PERMISSION.md).

Third-party components keep their own licences — see THIRD_PARTY_NOTICES.md.
