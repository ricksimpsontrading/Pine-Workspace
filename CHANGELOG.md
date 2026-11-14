# Changelog

All notable changes to the Pine Workspace **core** (tooling, menu, skills, rules, authorities,
licence templates, installer, documentation). Pine scripts carry their own `// Version:` header
and are not covered here.

Versions follow MAJOR.MINOR.PATCH: MAJOR for a compatibility break, MINOR for a compatible
evolution, PATCH for a compatible correction. The number lives in `tools/pws_workspace/version.py`
only; the top entry of this file must carry the same number (checked by `build-release` and the
doctor). A published version is never replaced silently: a corrected delivery gets a new number.
Each entry lists what changed and the limits that remain, so that the guided update path can show
them before anything is applied.

## [2.1.1] — PWS menu banner, English reference documentation, language rule (prepared 2026-11-14)

### What this version is

A compatible patch of the 2.1.0 core. It changes the text of the `/pws` menu banner, makes English
the reference language of the documentation under `docs/` and `standards/`, and states the
language rule of the assistant. No data migration: products, configuration, evidence and the
installed PineTS engine are untouched by the update.

### Changed

- `/pws` menu banner: the fixed ASCII-art banner of the main menu now reads "PWS" (FIGlet font
  "Standard", 23 columns, 5 lines, printable ASCII, no trailing space) instead of "Pine-WS". Same
  mechanism as before: `menu --json` carries it in `banner.question`, which the menu passes verbatim
  as the text of the main-menu question, at the opening of `/pws` and on every return to the main
  menu only — never in front of a submenu, a result or an intermediate question, never as free
  text, never resized. The product name (Pine Workspace), the repository, the commands and the
  identifiers are unchanged. The `banner` subcommand keeps its adaptive PINE-WORKSPACE variants
  for a terminal.
- English reference documentation: the specification (`docs/architecture/BOOTSTRAP_SPEC.md`), the
  architecture, file contracts, operations and migration guides (`docs/architecture/`), the Pine
  Script v6 master standard (`standards/PINE_SCRIPT_V6_STANDARD.md`) with its index and
  traceability, and the licence profiles guide (`docs/licensing/PROFILES.md`, formerly bilingual,
  now one complete English version) are written in English. Faithful translation: requirements,
  prohibitions, exceptions, conditions, limits, section numbers, rule identifiers and decision
  references are unchanged; commands, configuration keys, paths and identifiers are untouched. The
  generated standard index (`standards/INDEX.md`) uses English headings.
- Documentation accuracy: obsolete active descriptions corrected — schema 3 stated as the current
  `SCRIPT.json` schema, legacy schemas 1 and 2 being read and flagged (specification §32.2, §44.3,
  §61.11 and §65, architecture document, doctor skill); the neutral edition completed in two places
  of the specification (the holder instead of a personal name); the record of ratified amendments in
  the header of the master standard completed with those of 2026-11-13.
- Language rule: menus, explanations, questions, confirmations and reports follow the configured
  language (`language` in `pws.config.json`: `en` or `fr`), whatever the language of the files read;
  no language is inferred from the holder, the operating system or a document; an explicit request
  for a translation or for content in another language does not change the configuration; after an
  explicit change, the next exchanges use the new value. The reference documentation is English in
  both cases and is explained in the configured language. Ratified exceptions are unchanged:
  generated legal texts in English, third-party documents in their original language and content,
  commands, identifiers, code and external diagnostics quoted literally. The rule is stated in
  `CLAUDE.md` and in master §4.1; the session-start summary now states the configured language
  explicitly; the skills render their screen labels in the configured language, the agents never
  infer the language of their report from the language of their mission, and the installer
  describes the setting as the language of the conversation and of the menus. New installations
  still propose English by default, with French as a choice.
- Stop hook in the configured language: the blocking reason, the non-blocking information, the
  categories and the warning on licence notices, attributions and legal references are worded in
  English or French according to `language` (English when the configuration is absent); the
  information handed to the next session summary is worded in the language in force when it is shown,
  even after a change of language; records of earlier versions are shown as recorded. The blocking
  conditions, the checks and the hook protocol are unchanged.
- Specification §40.5 aligned on the menu the tooling really generates ("Quality / publication",
  "Maintenance / configuration", TradingView mode under Configuration, update and licence paths); the
  original bootstrap tree is kept as a marked historical note. The menus themselves are unchanged.
- README: the English getting-started guide published on `main` after 2.1.0 is part of this
  release, with the documentation-language statement updated.

### Limits

- The Claude Code instruction files (`CLAUDE.md`, skills, rules and agents) and a few internal notes
  remain in French, and the Template Permission stays bilingual; the assistant is instructed to
  answer in the configured language whatever the language of a file. Guard finding details quoted in
  the Stop hook messages (for example `no '// Version: X.Y.Z' line in header`) stay in English in both
  languages, like the other technical diagnostics.
- The instructions and the tooling were checked; how the assistant actually phrases its answers is a
  model behaviour that no test of this release establishes.
- How the Claude Code dialog renders the leading spaces of the banner is established only by
  observation in a real session.
- The limits listed for 2.1.0 still apply (offline identity check of GitHub destinations, PineTS as a
  local laboratory and never a TradingView validation, SHA-256 integrity without signature, Windows
  deferred and Linux not verified).

### Licence

Unchanged: Apache License 2.0 for the core (`LICENSE`) and GNU AGPL v3 only for the PineTS thin
adapter (`tools/pine_exec/LICENSE`); third-party notices in `THIRD_PARTY_NOTICES.md`; the Template
Permission for the licence templates (`docs/licensing/TEMPLATE_PERMISSION.md`).

## [2.1.0] — First public release (prepared 2026-11-08, hardened 2026-11-13)

### What this version is

The first public release of the Pine Workspace core: a Claude Code workspace for developing,
maintaining, documenting, validating and preparing the publication of Pine Script v6 indicators,
strategies and libraries. The core ships no product, no personal configuration and no private
history: every user installs it with `install.py` from the downloaded package, configures their
own identity and language, and keeps their scripts under `scripts/`.

### Included

- Deterministic tooling (`python3 -m tools.pws_workspace …`, standard library only): session
  status, doctor, guard, scan, licence templates and guided licence path, configuration,
  migrations, core upgrade with verified backups and two-stage restoration, PineTS lifecycle,
  GitHub export of a product, distribution build, release build and guided update.
- The `/pws` menu generated from the real state (French and English), with the fixed Pine-WS
  banner, four options per screen and Back on every screen below the first level.
- Skills, rules and read-only agents for the Pine workflows (new script, import, develop,
  documentation, research, review, audit, local test, TradingView validation, licence, release,
  GitHub export, doctor, tools, maintenance, update).
- Licence profiles FREE (CC BY-NC-SA 4.0, public source), FREE with closed source, PRIVATE and
  COMMERCIAL (configurable EULA), with rendered documents flagged DRAFT until complete.
- The PineTS thin adapter (local behavioural execution, capability-gated). The engine itself is
  **not shipped**: each user installs the exact pinned version with `npm ci --ignore-scripts`.
- Guided update of an installation from the official releases or from a local package: explicit
  search, dated result, plan before application, grouped confirmation, `upgrade` then `migrate`,
  verification, rollback information.

### Safety and reliability (hardening before the first publication)

- Distribution build, installer and archive import never delete or overwrite an installation, its
  data or the source tree; the installer copies only the files listed and hashed by
  `PWS_DISTRIBUTION.json`, checks every fingerprint first and installs through a hidden work folder
  renamed at the end. Release artefacts are built only from a committed, clean tree.
- GitHub export: the plan is bound to the effective destination and to the fingerprint of every
  file; diff and publish re-check them; the local clone must match the configured repository; links,
  special files and the code of a closed source never go to a public destination.
- GitHub export of a closed source: nothing is sent until GitHub itself (`gh repo view`, current gh
  authentication) reports the configured repository as private, checked again immediately before the
  push; the clone must push to that single github.com repository — several push URLs, a pushurl or an
  insteadOf/pushInsteadOf rewriting toward another place, another host, a renamed or transferred
  repository, gh missing or not authenticated, or an invalid answer is refused. Only the exact forms
  `https://github.com/<owner>/<repo>[.git]`, `git@github.com:<owner>/<repo>[.git]` and
  `ssh://git@github.com/<owner>/<repo>[.git]` are accepted (no credentials, port, query or fragment);
  a refusal names the host git would contact. The declared source of a public product that copies a
  closed source is closed content. Credentials embedded in a URL are never displayed; `github
  status` shows the credential helper by its name only.
- GitHub export, every send (public content included): the destination's URL and the clone's single
  fetch and push URLs, as git really uses them (pushurl and rewritings applied), must designate the
  repository configured for the destination, in the same strict forms — checked before anything is
  written into the clone and read again right before the push; when the destination changed after the
  local commit, nothing is pushed and the result describes the state left on disk. Identity of the
  authorized repository and privacy required by closed content are two distinct checks: public
  content may go to a public destination or to a private repository chosen explicitly. What is sent
  is exactly the plan: an empty URL entry or a setting that makes git connect elsewhere or without
  verification (ssh or proxy command, remote helper, pinned address, TLS verification off) is
  refused; a file whose bytes git would change when committing (end-of-line conversion, filters) is
  refused before any write; a target differing only by case from an entry of the repository is
  refused; no hook runs in the publication clone; the local commit is checked before the push.
- GitHub export of an imported script: its original legal documents (licence text, NOTICE,
  attributions — LICENSE, COPYING, COPYRIGHT, NOTICE, PATENTS, AUTHORS, CREDITS, ATTRIBUTION,
  CONTRIBUTORS, THIRD_PARTY_NOTICES and their variants, or a REUSE `LICENSES/` folder), declared by the
  holder (`license confirm --license-document`, or `--no-license-documents`),
  are exported verbatim (name, bytes, encoding, language), never replaced by a PWS template; the
  export waits, with the resolution, while a document is not declared, missing, changed, refused by a
  safety check, or while a file with a legal-document name is left undeclared — never an incomplete
  set. The recorded SPDX identifier alone does not establish which documents a redistribution
  requires.
- Distribution build: the target is compared with the source by physical identity; only
  `tools/**/__pycache__/*.pyc` are ignored in a previous build; the licence files must be committed;
  shipped files and archive entries are 0644 (0755 when executable).
- Guided update: every kept local file is verified separately, recurring migrations are applied at
  every update, `migrate` answers are validated strictly, a migration still due or an internal error
  is never reported as a success, interrupted upgrades are restored or stay resumable explicitly.
- Rollbacks first copy the versions they replace (`<backup>.replaced-<date>/`); backups are ordered by
  their precise creation time; symbolic links are never followed in the runtime.
- Destructive and publication commands ask for confirmation (project permission rules).
- Licence path and guard: writes stay inside the product's `release/` folder and to the documents of
  its licence axes; only the current, complete rendering of a terms document can be attached; the
  guard reads the validated manifest, checks the CC mention, URL and copyright line exactly, blocks
  unrendered template fields, and admits third-party licence notices through a targeted rule (never a
  general URL exemption).
- The existing licence of an imported script is recorded as such (MPL-2.0 — the Pine Editor's
  default header —, MIT, Apache-2.0, BSD-2/3-Clause, GPL/LGPL/AGPL "only" or "or later", CC BY-NC-SA
  4.0): exact SPDX identifiers confirmed by the holder, a header detection being only a proposal; any
  other licence stays explicitly "to analyse" (current work continues, release preparation and export
  wait). No PWS terms document is imposed on it and the guard checks its existing notice instead of
  the CC or proprietary header. Existing manifests are unchanged (compatible extension of schema 3).
- A TradingView mode inherited from an older installation never silently replaces the mode in effect:
  when both differ and nothing shows an explicit choice, the conflict waits for the owner's choice.
- Licences: the PineTS thin adapter is under the GNU AGPL v3 only, the rest of the core under the
  Apache License 2.0 (see the Licence section).
- Several Claude Code sessions can share one workspace without erasing each other's import records
  or Stop information; a failure of the Stop hook is recorded and announced.

### Requirements and platforms

- Python 3.9 or later (standard library only); Git optional (degraded mode without it); Node.js
  and npm optional, for local PineTS tests only.
- macOS supported first. Windows deferred (the installer stops). Linux not verified.
- Claude Code, with the user's own subscription.

### Limits

- The real visibility of a GitHub repository is checked immediately before a closed source is
  pushed, with no atomic guarantee: it can change between the check and the push. Exports go to
  github.com only (not GitHub Enterprise Server); a destination whose URL is not a github.com URL of
  its repository can be fetched but never receives a send. The clone's git configuration is read
  again right before the push; a change made in the instant between that reading and the push itself
  is not detected. The identity check is offline: it does not see a repository renamed or transferred
  on GitHub, nor the SSH client configuration (`~/.ssh/config`); the authenticity of github.com rests
  on SSH host-key or TLS certificate verification.
- Local PineTS execution is a laboratory: it is never a TradingView validation. TradingView
  remains the only empirical validation authority.
- Instruction files (skills, rules, authorities) are written in French; the assistant answers in
  the configured language.
- Release integrity relies on the SHA-256 of the archive published with the release: an
  integrity check, not a proof of authenticity (no cryptographic signature chain exists).
- Release search uses the public GitHub API without authentication (rate-limited per address);
  nothing is searched at session start and nothing is updated automatically.
- A core upgrade followed by data migrations is two operations, not one atomic step: the guided
  path stops between them when a migration outside the approved plan appears.

### Licence

Apache License 2.0 for the core (`LICENSE`) and GNU AGPL v3 only for the PineTS thin adapter
(`tools/pine_exec/LICENSE`): the distribution as a whole is not under a single licence (`NOTICE`,
`docs/licensing/LICENSING.md`). Third-party notices in `THIRD_PARTY_NOTICES.md`; the Template
Permission for the licence templates (`docs/licensing/TEMPLATE_PERMISSION.md`).
