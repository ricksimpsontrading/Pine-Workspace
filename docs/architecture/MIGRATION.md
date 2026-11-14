# MIGRATION — core version, upgrade, data migrations, rollback

Operational document (English since 2.1.1; stable commands and contracts). Normative contract: spec §55 (idempotence), §19A, §45 (amendments of 2026-11-06).

Three distinct operations, always in this order:

1. **Delivery of a new core version** (files: tools, skills, rules, authorities, templates, installer, documentation) → `upgrade`.
2. **Application of the data migrations** (configuration, manifests) → `migrate`.
3. **Rollback** → `migrate --rollback` (data) then `upgrade --rollback` (code).

## Guided `update` path (2026-11-08)

`/pws → Maintenance / configuration → Outils et mises à jour → Mettre à jour Pine-Workspace` (in English: Maintenance / configuration → Tools and updates → Update Pine-Workspace; skill `pws-update`, module `tools/pws_workspace/update.py`) chains these three operations without replacing them: `update status` (installed version, installation type, dated last search or "not searched", backups); `update check` (explicit search of the stable releases of the official repository `ricksimpsontrading/Pine-Workspace`, dated result, never "up to date" on an error or the absence of a release, pre-releases excluded by default, versions compared numerically); `update fetch` (download of the release found into a temporary folder outside the installation: provenance of the assets — official repository and tag —, `RELEASE.json` read first, SHA-256 hash of the archive compared with the published value, extraction verified before any write, core manifest checked file by file) or `update prepare --package <zip or folder>` (offline local package: integrity only, origin not verified online); `update plan --package-dir …` (read-only summary, tied to a hash: versions, origin, changes, conflicts, possible migrations, backups, restart of Claude Code); `update apply --plan-file … --yes` (refusal if the plan has changed, if the installation is the upstream or if a conflict remains; then `upgrade`, then `migrate --plan` executed by the **new** code: a blocked step stops the data phase before any migration; the migrations are applied only if they all appear in the approved plan, otherwise the guided path stops after the code and presents them; then verification of the files and of the version, and `doctor --json` interpreted according to its actual contract — content validated entry by entry before any verdict (non-empty list of findings each carrying a usable `check` identifier, a severity among OK / INFO / WARNING / BLOCKING and a textual `detail`; a single non-conforming entry makes the whole diagnostic unusable, without removal or default value), exit code 1 if and only if there is a BLOCKING finding, warnings alone do not block, an impossible execution, an unusable or non-conforming response, an empty list or a code inconsistent with the result never count as a successful diagnostic); `update rollback-info` (order and commands of rollback, existing backups, limitations — restores nothing). The outcome statuses are explicit and only `applied` is a success (exit code 0): `refused-before-mutation`, `failed-restored` / `failed-restore-*`, `incomplete`, `stopped-blocked-migrations`, `stopped-unplanned-migrations`, `diagnostic-blocking`, `diagnostic-unavailable`, `applied`; each report indicates what has been accomplished (`done`: code installed and verified, migrations applied / remaining / blocked, diagnostic), the backups (`recovery`) and the next useful action (`next_action`), and never claims that nothing has changed once the code is installed. The "code then data" sequence as a whole is **not** atomic and is never presented as such; no automatic rollback of the whole exists. The development upstream (no core manifest) can consult the releases but no public distribution applies to it.

**Fixes of 2026-11-13 (audit fix mission, `docs/maintenance/2026-11-13-corrections-audit/`)**:

- **Files kept locally** (`keep-local`, for example after `pinets install`, `pinets verify --record` or a recalibration): the final verification checks them separately — local file unchanged since the plan AND new version intact next to it (`<path>.pws-new`, package hash); an update that differs only by these files ends in `applied`, with `done.kept_local` and the invitation to examine the `.pws-new` files; a new plan of the same package is no longer applicable once the new version is in place.
- **Recurring steps**: the approval covers all the steps declared by the package; the log no longer removes a step based on the actual state (m004 comes back with each version); `migrate --plan` of the new code alone decides what is due. Several successive updates succeed.
- **Strictly validated responses**: `migrate --plan` (exit code, object, `config_error`, each step: `id`, boolean `blocked`, `detail`, `waits_for`) and `migrate --apply` (`applied`, `errors`, consistent exit code); any unusable response yields `incomplete`, never a success; after the application, `migrate --plan` is run again: a step still due yields `incomplete`. Any exception after the installation of the code still produces a report (`done`, `recovery`, `next_action`).
- **Interruptions**: each file is written to a temporary file then renamed; the backup is complete and marked `applying` before the first write; Ctrl-C is intercepted and the previous state restored then verified. An abrupt stop (SIGKILL, power cut) cannot be intercepted: the backup remains `applying`, `upgrade --plan` and `update plan` flag it (`interrupted`), and the resumption is explicit — `upgrade --rollback <stamp>` (accepted for this state, restoration validated before any write) or a new application of the same package.
- **Order of rollbacks**: each backup carries its precise creation date; an older backup is refused as long as a more recent one is still applied (from the most recent to the oldest); a restored backup is marked `rolled-back`. The migration log (`pws.config.json`) is always part of the migration backup: a rollback also removes its entries.
- **Nothing is lost through a rollback**: before writing, the current version of each file that the restoration replaces with a different content or deletes is copied and verified into `<backup>.replaced-<date>/` next to the backup (`PRESERVED.json` lists them; the report gives this folder in `preserved`); if this copy fails, nothing is written. A code backup that does not record the migrations present at its application causes its rollback to be refused as long as migrations are recorded (except with `--force`). Symbolic links are never followed: backup manifest, lock file, `settings.local.json`.
- **Legacy TradingView mode** (rule F-14 decided by the holder on 2026-11-13): an unrelated configuration write never materializes the default mode. m001: without a usable value in `pws.config.json`, the valid legacy value is taken over; if the two values match, the migration takes place without a question; if they diverge and no provenance distinguishes an explicit choice from a default value, the setting in force is kept and only the resolution of the conflict is blocked (m001 blocked, m003 waiting: the legacy value is never removed before) until the holder's choice through `tv-mode <mode>` (or `config set tv_validation_mode`), which records its provenance (`tv_validation_mode_choice`). The plan presents the two values and their origin; consulting it writes nothing; once the choice is recorded and the migration done, the question no longer comes back.

## Workspace version

Convention ratified on 2026-11-08: MAJOR.MINOR.PATCH (major = compatibility break, minor = compatible evolution, patch = compatible fix); the first public version is 2.1.0; a published version is never replaced silently, a corrected delivery receives a new number. The number lives in `tools/pws_workspace/version.py` only; `VERSION`, `workspace_version` of the core manifest, the tag `v<version>`, the package name and `RELEASE.json` derive from it, and the top entry of `CHANGELOG.md` must carry the same number (checked by `build-release` and by the doctor, check `version-sources`).

`python3 -m tools.pws_workspace version` displays the core version (`WORKSPACE_VERSION`, `tools/pws_workspace/version.py`), the configuration schema and the manifest schema. Each installation records the version to which it was migrated in `pws.config.json` (`workspace_version`) and the list of the applied steps (`migrations`). An installation that comes from a distribution also carries its **core manifest** (`PWS_DISTRIBUTION.json` at the root: version and hash of each shipped file); the original installation, from which the distribution is built, does not have one: it is the upstream and is not upgraded through `upgrade`.

## 1. Delivery of a new core version (`upgrade`)

Manual procedure, without network: download the new package (the folder produced by `build-distribution`, containing `PWS_DISTRIBUTION.json`), then from the installation:

```bash
python3 -m tools.pws_workspace upgrade --from "/path/to/new package" --plan
python3 -m tools.pws_workspace upgrade --from "/path/to/new package" --apply [--overwrite-local]
```

The plan (read-only) compares each file of the package with the installation and with the installed core manifest:

| Action | Condition | Effect of `--apply` |
|---|---|---|
| `unchanged` | identical | nothing |
| `update` | installed file = previously shipped version, new version different | replaced (backed up) |
| `add` | absent from the installation | added |
| `keep-local` | **locally mutable** core file modified in place (`tools/pine_exec/PROVENANCE.json`, `calibration/capabilities.json`, `package.json`, `package-lock.json`, `.claude/settings.json`) | kept; the new version is written next to it as `<name>.pws-new` for review |
| `conflict` | core file modified locally | **refused** as long as `--overwrite-local` is not passed; then replaced after backup |
| `remove` | core file removed by the new version, not modified locally | deleted (backed up) |
| `conflict-rm` | file removed by the new version but modified locally | kept unless `--overwrite-local` |

Never touched: `scripts/`, `docs/maintenance/`, `pws.config.json`, `.claude/settings.local.json`, `.claude/runtime/`, `node_modules`, and any file absent from both manifests. Any touched file is first copied into `.claude/runtime/upgrade-backup/<timestamp>/` (with `MANIFEST.json`); an error during the application automatically restores this backup and flags it. The installed core manifest is replaced by that of the package. `install.py` always refuses to overwrite an existing installation and refers to this procedure.

## 2. Data migrations (`migrate`)

```bash
python3 -m tools.pws_workspace migrate --plan      # read-only: applicable steps, files touched
python3 -m tools.pws_workspace migrate --apply     # backup + application in order
python3 -m tools.pws_workspace doctor
```

A migration is never deduced from a version number alone: each step checks the actual state and applies only if necessary; it is idempotent, backs up before writing and never touches `DECISIONS.md`, `validation/`, the research runs, a `PRODUCT.md`, the Claude Code approvals or any key of `settings.local.json` other than the old TradingView mode key that it moves.

| Step | Actual condition | Effect |
|---|---|---|
| `m001-tv-mode-to-config` | `.claude/settings.local.json` (real file, never a link) still carries `env.PWS_TV_VALIDATION_MODE` | without a usable mode in `pws.config.json`: copies the legacy value; matching values or explicit choice of the holder (`tv_validation_mode_choice`): keeps the configuration; divergence without provenance: **blocked** until the holder's choice (`tv-mode <mode>`), nothing is modified |
| `m003-remove-legacy-tv-key` | legacy key present; waits for m001 to be applied (never as long as m001 is blocked) | removes the legacy key (kept in the migration backup), preserves all the other keys |
| `m004-record-workspace-version` | `workspace_version` absent or different | records the current version |
| `m005-manifests-v3` | at least one `scripts/<slug>/SCRIPT.json` in schema 1 or 2 | rewrites to schema 3: licence axes kept (known creation year preserved, never invented); publication split into `state` / `privacy` / `mode`; only what was **recorded** is kept: `tradingview-open|protected|invite-only` → corresponding mode, **null** privacy (never deduced); `tradingview-private` → private privacy, null mode; `unpublished` → unpublished state; schema 1 → publication entirely null (the profile defaults are proposals for a new project, not facts of a migrated project). Every null appears in the reported ambiguities. Replaces `m002-manifests-v2` of 2026-11-06. |
| `m006-publication-derivations` | schema 3 manifest whose `migration` shows that a privacy (or, for a v1 → v2 → v3 chain, a mode) was **deduced** by the version of 2026-11-06 | resets these values to `null`, traces each rectification in `migration.rectifications` (field, old value, reason, date); never touches a value confirmed by the holder (`license confirm` → `migration.holder_confirmed`); idempotent. |

A blocked step is flagged and skipped; an error stops the sequence, the backup remains available.

## 3. Rollback

```bash
python3 -m tools.pws_workspace migrate --list-backups
python3 -m tools.pws_workspace migrate --rollback <timestamp>     # data, byte for byte (also restores pws.config.json; replaced versions copied first into <backup>.replaced-<date>/)
python3 -m tools.pws_workspace upgrade --list-backups
python3 -m tools.pws_workspace upgrade --rollback <timestamp>     # code: files restored, additions removed, previous core manifest reinstated
```

`upgrade --rollback` **refuses** as long as data migrations recorded after the upgrade are still applied (it indicates which ones): roll back the data first, then the code, so that the two remain consistent (`--force` overrides, at your own risk). The order is established by comparison with the list of the migrations recorded at the time of the upgrade (`migrations_at_apply` in the backup manifest), never by the clock: two operations within the same second remain ordered. The backups are kept in the ephemeral space: protect them like the rest of the runtime if a reconstruction must remain possible.

### Guarantees of the backups and of the mutating operations (fixed on 2026-11-06 after independent verification)

- **Physical confinement**: each path read or written by `upgrade` (package, installation, backups, `.pws-new` copies, manifests) is resolved physically with the shared primitives of the core; a folder or a file that is a symbolic link along the chain, a path that leaves its root, a symlinked backup location or an invalid manifest entry **refuse the entire plan before any mutation** and are listed (never silently ignored).
- **Unique backups**: folder created exclusively with a unique name (timestamp + random suffix), never reused, even within the same second; copies verified by hash before the first mutation; manifest written before the mutation then marked `applied`.
- **Serialization**: `upgrade --apply|--rollback` and `migrate --apply|--rollback` take the same lock (`.claude/runtime/pws-mutation.lock`); a concurrent operation is refused with an explicit message, never interleaved.
- **Restoration validated before any write, then verified** (fixed on 2026-11-06 after the second independent verification; shared module `tools/pws_workspace/restore.py`, used by `upgrade --rollback`, by the automatic restoration after a failure of `upgrade --apply` and by `migrate --rollback`): under the shared lock, the whole restoration is first validated — manifest, paths and physical confinement (installation side and backup side), destinations, presence and hash of each necessary copy; **a single invalid entry refuses the entire restoration** (`stage: refused`, `ok: false`, "nothing changed"): no installed file is replaced, created or deleted. Only then are the files copied and each copy verified again; success (`stage: verified`) is declared only if the restored state matches the manifest; an error occurring during execution despite a successful validation is flagged as an incomplete restoration (`stage: incomplete`, deviations listed) and the backup is kept for a new attempt. `migrate --apply` never restores automatically: it stops at the first failing step and keeps the backup for an explicit `migrate --rollback`.
- **Confirmations**: `python3 -m tools.pws_workspace license confirm --slug <slug> [--state …] [--privacy …] [--mode …] [--created-year …]` records facts confirmed by the holder; they are listed in `migration.holder_confirmed` and no rectification calls them into question.

## New installation vs existing installation

- New installation: `install.py` (see `INSTALL.md`) → `init` writes `pws.config.json` (English preselected, identity to be filled in, TradingView mode `manual`); the core manifest is copied.
- Existing installation: never a reinstallation over it; `upgrade --plan/--apply` then `migrate --plan/--apply`. The original installation (upstream) is updated through its own repository; `init --language fr --copyright-holder "…" --alias "…"` then `migrate --apply` preserved the language, the identity, the products, the evidence and the settings there on 2026-11-06.

## Trials carried out (2026-11-06, tests `tools/tests/test_upgrade.py` and `test_migration.py`)

Third series, after the second independent verification (order of the restorations), for `upgrade` and `migrate`, with comparison of the content and of the presence / absence of each file before and after each refusal: altered backup copy placed in last position behind valid entries including deletions (refusal before any mutation, added file still present, removed file still absent); missing necessary copy; entry leaving the scope added after the valid entries; installed destination replaced by a symbolic link to the outside (refusal, outside file intact); valid restoration (`verified`, exact `restored` / `removed` lists); automatic restoration after an application failure with a backup that has become unusable (refusal flagged honestly, installation left as it was at the time of the failure, backup kept, later explicit rollback refused for the same reason without any write).

Second series, after independent verification: `.claude/skills` folder as a symbolic link to the outside (plan refused, outside file intact, no backup created); core file as a symbolic link to the outside (refused, intact); symlinked package file (refused); symlinked backup location (refused before any mutation, tree unchanged); invalid manifest entry (entire plan refused); two applications with the same clock (two distinct backups, double rollback restoring the initial state); explicit name collision (no reuse); concurrent operation (refused for `upgrade` and `migrate`); altered backup copy (rollback declared not verified); failure during application (previous state restored and verified); code/data order within the same second (refusal then success after the rollback of the data); installation without manifest on a dedicated fixture.

Package v2.1.0 built from the core, installed by `install.py` in a temporary folder whose path contains spaces, with representative user data (FREE product, `fr` configuration + identity, note under `docs/maintenance`, Claude Code approvals, a rule modified locally, annotated `PROVENANCE.json`). Second package simulating a version 9.9.9 (modified skill, added document, two rules removed). Results: correct plan (update / add / remove / keep-local / conflict-rm); refusal without `--overwrite-local`; application with all user data kept, `.pws-new` for the mutable file, manifest and `VERSION` updated; refusal of the code rollback as long as a later data migration is recorded; complete rollback after that of the data; simulated failure during application → previous state restored identically.

## Known limitations

- The instruction files (`CLAUDE.md`, skills, rules, agents) are written in French; the reference documentation (`docs/`, `standards/`: master, spec, architecture, contracts, procedures, licence profiles) is in English since 2.1.1 (holder's decision of 2026-11-14). The assistant answers in the configured language whatever the language of a file (master §4.1).
- Windows: deferred. Linux: not verified.
- The historical reports of `docs/maintenance` keep their original paths; the index of moves (`docs/maintenance/archives/INDEX.md`) makes it possible to resolve them.
- `upgrade` does not handle an installation that predates the core manifests (none exists outside the upstream).
