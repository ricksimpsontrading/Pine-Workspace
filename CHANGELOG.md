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

## [2.2.0] — Guided updates of Pine Workspace and PineTS, fewer permission prompts (prepared 2026-11-17)

### What this version is

A compatible evolution of the 2.1.1 core. It makes the update of Pine Workspace and of the PineTS
engine one continuous guided path from the existing menu entries, and it includes the lightening of
the shared permission rules prepared as 2.1.2 (never published: its changes are part of 2.2.0). The
existing commands, states and protections are reused: no second installer, migration engine or
restoration mechanism. No data migration other than the usual recording of the version (m004).

### Added — guided update paths

- `/pws → Maintenance / configuration → Tools and updates` now leads, for Pine Workspace and for
  PineTS, through the same seven steps: local state, explicit search at the official source, changes
  and limits, preparation and verification, a precise plan with ONE confirmation, application with the
  planned checks, and a faithful summary with the remaining action and the recovery elements. Claude
  Code chains the steps; the user does not have to know the subcommands. Each step returns a short
  summary in the configured language (what will change, what is kept, the planned checks, the result,
  the remaining action); the technical details stay in the JSON result.
- Pine Workspace (`update guide --stage state|search|prepare|apply`): orchestrates the existing
  `update check`, `fetch` / `prepare`, `plan` and `apply` (code by `upgrade`, then the planned data
  migrations by the new code, verification of the installed files, diagnostic). Release notes are
  classified available / absent / unusable and are never replaced by an invented description; a failed
  search or an absence of release is never "up to date"; pre-releases only on request. On the
  development upstream the path stops before any download and explains why.
- PineTS (`pinets guide --stage state|search|prepare|apply`): one exact version is prepared without
  installing anything — registry metadata, download of the npm archive outside the workspace (scripts
  disabled), integrity equal to the registry value, archive read without extraction (package.json,
  LICENSE, the artifact loaded by the adapter and its hash), Node / npm prerequisites, licence compared
  with the recorded assessment (a different licence identifier stops the plan for the holder's
  decision), release notes published on the repository declared by the package, recalibration cases.
  After the confirmation: re-check of the engine against the plan, verified rollback point (nothing is
  installed if it cannot be saved), installation by the existing `pinets install`, identity of the
  engine obtained against the archive of the plan, `pinets verify`, then the recalibration.
- Guided recalibration (`recalibration.py`, comparison contract
  `tools/pine_exec/calibration/comparisons.json`): the existing calibration case is executed by the
  adapter's runner and compared with its independent reference (exact, or within the documented
  tolerance of `ta-ema`). Only the capabilities actually re-exercised with success become CURRENT;
  `capability_status` and `known_divergences` are never changed (CURRENT never becomes GATING); the
  references are hash-checked and never rewritten; runs, comparison and the previous calibration file
  are kept with their provenance under `.claude/runtime/pinets-recalibration/`. A divergence or an
  unconcluded case leaves the capabilities STALE and asks for the holder's decision. A recalibration is
  declared successful only when the calibration file was written and re-read as decided; a run report
  is used only when coherent with its exit code and naming the engine executed, the adapter's
  normalization schema, the executor fingerprint and the calibrated source and dataset; NaN,
  infinities and wrongly typed values are invalid.
- A PineTS plan that includes the recalibration is bound to the comparison contract and to every
  artifact it names; a change refuses the application before any change of the engine (checked again
  under the shared lock). A LICENSE text that differs from the recorded examined copy (same identifier)
  stops the plan until an explicit decision of the holder bound to that exact text is recorded in a new
  plan; a different identifier, or no recorded reference, stops it for a new licence analysis. A recalibration of
  the current engine alone can be planned the same way.

### Changed

- The plan of a Pine Workspace update is also bound to the origin, the recorded provenance and the
  verified archive of the package: a change after the approval refuses the application, nothing
  changed.
- A core update whose backup folder cannot be created is refused before the first write ("nothing
  changed") instead of ending on an internal error.
- Ask rules added for the two guided application steps (`update guide --stage apply …`, `pinets guide
  --stage apply …`), like `update apply` and `pinets install`; the states, searches and preparations of
  the guided paths have none.
- Permissions (prepared as 2.1.2): PWS no longer imposes a systematic confirmation (ask rule) on
  local commits, local builds (`build-distribution`, `build-release`), update searches (`update check`, `pinets check-update`) and
  update downloads prepared locally without application (`update fetch`). Removing these rules grants
  nothing: Claude Code's normal mechanism decides, and in auto mode its classifier may still ask for
  confirmation or refuse.
- Git and GitHub readings are allowed: `git remote`, `git remote -v`, `git remote get-url`, `git tag`
  (listing), `gh release view`, `gh release list`. The former broad ask rules on `git remote`, `git tag`
  and `gh release` are narrowed to the modifying forms: adding, changing, removing or renaming a remote;
  deleting or force-replacing a tag; creating, editing, uploading to or deleting a release.
- Explicit ask rules are kept for the main publication, deletion, restoration, installation and
  update-application commands (`git push`, `github publish`, `github fetch`, `update apply`, `upgrade`,
  `migrate --apply` and `--rollback`, `pinets install`, `rollback` and `verify --record`, cleanup
  `--execute`, archive import and source removal, destination removal, licence writes, `gh repo create`,
  `gh auth login`, `init`). The deny rules and the hooks are unchanged; no general authorization of
  Bash, Python, Node or the PWS tool is added, and no permission mode is set by the project.
- Documentation: specification §20.2, file contracts and the operations guide (new "Permissions
  (Claude Code)" section) describe the rules and their limits; the operations guide also describes the
  guided update paths ("Guided updates" section), the skills `pws-update` and `pine-tools` follow them.

### Limits

- The guided paths do not make the code update and the data migrations atomic, and add no automatic
  rollback of the whole path: the summary names the backups and the existing restoration commands.
- PineTS compatibility is established only by the executed comparisons, within the calibration case
  (one synthetic dataset, a few capabilities); a version number or a successful npm installation never
  proves it. The release notes of PineTS come from the repository declared by the package; their
  correspondence with the npm artifact is not proven. The licence review is documentary, not a legal
  guarantee; the recorded licence copy is never updated automatically.
- The integrity checks (SHA-256 published with a release, npm registry integrity) do not prove
  authenticity: no signature chain exists.
- The tests of the paths use isolated installations and simulated network answers; the rendering of the
  summaries and of the confirmation question in Claude Code is an interface observation still to be made.
- The rules match the command text they recognize; they do not guarantee a confirmation for every
  possible variant of an act (for example `git -C <dir> remote add`, `git tag -fa`, `gh -R <repo> release
  create`). Personal and managed settings may change the result: an ask or deny rule from any settings
  file still applies, and an allow rule never outranks an ask rule.
- A technical permission never replaces the authorization of the mission: publishing still requires
  the holder's explicit agreement in the workflows concerned.
- An installation whose `.claude/settings.json` was modified locally keeps its file: the update plan
  lists it as kept locally (`keep-local`) and writes the new rules beside it as
  `.claude/settings.json.pws-new`, to merge by hand; they are not applied automatically to that file.
- The limits listed for 2.1.1 still apply.

### Licence

Unchanged: Apache License 2.0 for the core (`LICENSE`) and GNU AGPL v3 only for the PineTS thin
adapter (`tools/pine_exec/LICENSE`); third-party notices in `THIRD_PARTY_NOTICES.md`; the Template
Permission for the licence templates (`docs/licensing/TEMPLATE_PERMISSION.md`).

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
