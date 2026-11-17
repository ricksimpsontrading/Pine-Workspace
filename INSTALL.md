# Installing Pine Workspace

Pine Workspace (PWS) is a Claude Code workspace for developing, maintaining, documenting,
validating and preparing the publication of Pine Script V6 scripts. This document covers a
**new installation** from a downloaded distribution package. An existing installation is
upgraded with the migration procedure (`docs/architecture/MIGRATION.md`), never by reinstalling
over it.

## Requirements

| Component | Required | Notes |
|---|---|---|
| macOS | yes (first supported platform) | Windows: deferred in this version. Linux: not verified. |
| Python 3.9 or later (standard library only) | yes | the deterministic tooling and the installer |
| Claude Code | yes | the assistant harness (skills, rules, agents, hooks) |
| Git | recommended | local history and worktrees; without it PWS runs in a documented degraded mode |
| Node.js + npm | optional | only for the local PineTS behavioural tests (`tools/pine_exec`) |

## 1. Check the downloaded archive

A release is published with the archive `pine-workspace-<version>.zip` and its SHA-256 in
`pine-workspace-<version>.zip.sha256`. Check it before extracting (integrity of the download;
not a proof of authenticity — no signature is published):

```bash
shasum -a 256 -c pine-workspace-<version>.zip.sha256
```

## 2. Choose the installation folder

The **downloaded package folder** (where `install.py` lives, the extracted archive) is not the
installation folder. The installer proposes a default target (`~/pine-workspace`), lets you
change it, accepts paths with spaces (typed, quoted or dropped into the Terminal), checks that
the folder is writable, detects an existing installation and never overwrites a non-empty
folder. The chosen path is recorded in `~/.config/pine-workspace/install.json` and proposed
again on later runs.

What gets installed: **exactly the files listed by the package's core manifest**
(`PWS_DISTRIBUTION.json`), each one checked against its SHA-256 before anything is written —
an incomplete or altered package installs nothing. Nothing else found beside the package is
ever copied: no Git history or remote (a clone of the public repository gets a fresh local
repository), no configuration, no products. `install.py` is part of the core manifest (compared
by `upgrade`), but it only runs from a downloaded package folder: it refuses to run from an
installation. The files are prepared in a hidden folder next to the target and renamed into
place once configured, so an interruption never leaves a half-installed target.

```bash
cd "/path/to/the/extracted/package"
python3 install.py                       # interactive: folder, language, copyright holder
python3 install.py --target "~/My Pine Workspace" --language en --yes   # non-interactive (--yes required)
```

## 3. First configuration

The installer runs the first configuration (`python3 -m tools.pws_workspace init`):

- **language** of the conversation and of the menus (menus, explanations, questions, confirmations,
  reports): `en` (default) or `fr` — changeable
  later with `config set language fr`;
- **identity**: the copyright holder of **your** scripts (`identity.copyright_holder`). It is
  used by the licence header templates and by the header checks. Leave it empty to set it
  later (`config set identity.copyright_holder "Your Name"`); until then copyright checks are
  reported UNVERIFIABLE, never as violations;
- **TradingView validation mode**: `manual` by default; `chrome-experimental` stays an explicit
  option you enable yourself (`tv-mode chrome-experimental`).

Everything personal lives in `pws.config.json` at the workspace root (not versioned, never part
of a distribution). Claude Code's own settings (`.claude/settings*.json`) hold permissions only.

## 4. Verify

```bash
cd "<installation folder>"
python3 -m tools.pws_workspace doctor
python3 -m unittest discover -s tools/tests -t .
```

The doctor is read-only: it reports, it never repairs automatically.

Known limitation of this step (A-09, deferred): the tests that build a distribution from your
installation run the same privacy check as a real build. If the copyright holder you configured
appears word for word in a shipped file (for example a name used by a test fixture), those
tests fail because the check refuses the build; it is the privacy check working, not a defect of
your installation. Tests that need Node.js and PineTS are reported as skipped until you install
them (section 5). Never weaken the check to make the suite pass.

## 5. Optional: local PineTS tests

```bash
cd tools/pine_exec && npm ci --ignore-scripts
```

PineTS is installed by **you**, from npm, at the exact version pinned in `package-lock.json`,
under PineTS's own licence (AGPL-3.0-only — see `THIRD_PARTY_NOTICES.md`). PWS never updates it
silently; `python3 -m tools.pws_workspace pinets check-update` is an explicit query, and
`pinets install <version> --yes` an explicit, reversible operation; the guided path
(`/pws → Maintenance / configuration → Tools and updates → PineTS`) chains them with one
confirmation. PineTS is a local laboratory;
TradingView remains the validation authority.

## 6. Start

```bash
claude            # the PWS state is shown at session start
/pws              # guided menu
```

## Licences

- Pine Workspace's own components: Apache License 2.0 for the core (`LICENSE`) and GNU AGPL v3 only
  for the PineTS thin adapter (`tools/pine_exec/LICENSE`) — see `NOTICE` and
  `docs/licensing/LICENSING.md`. PineTS itself is not shipped: installing it with npm is optional and
  happens under PineTS's own licence (`THIRD_PARTY_NOTICES.md`).
- Your scripts: **yours**. PWS never imposes its licence or its authors' identity on them; you
  choose a profile per project (FREE / PRIVATE / COMMERCIAL — see `docs/licensing/PROFILES.md`).
- Licence templates rendered for your scripts (headers, notices, grants, EULAs): reusable and
  modifiable in your product documents without PWS attribution, under the Template Permission
  (`docs/licensing/TEMPLATE_PERMISSION.md`).
- Third-party components: their own licences (`THIRD_PARTY_NOTICES.md`).

## Upgrading an existing installation

Never reinstall over an existing installation (`install.py` refuses it). Guided path, in Claude Code:
`/pws → Maintenance / configuration → Tools and updates → Update Pine-Workspace` (with French menus:
`… → Outils et mises à jour → Mettre à jour Pine-Workspace`) — an
explicit search of the official releases (or a local package you already downloaded), the changes
and limits of the new version, a plan, one grouped confirmation, then `upgrade` and `migrate` run
for you, followed by a verification. Nothing is searched at session start and nothing is applied
automatically; the same steps exist as commands (`update check`, `update fetch` or
`update prepare --package <zip>`, `update plan --package-dir …`, `update apply --plan-file … --yes`).
Manual commands, equivalent, from the installed workspace:

```bash
cd "<installation folder>"
python3 -m tools.pws_workspace upgrade --from "/path/to/new/package" --plan     # preview: add / update / remove / keep-local / conflict
python3 -m tools.pws_workspace upgrade --from "/path/to/new/package" --apply    # backup first; refuses locally modified core files unless --overwrite-local
python3 -m tools.pws_workspace migrate --plan && python3 -m tools.pws_workspace migrate --apply   # data migrations, separately
python3 -m tools.pws_workspace doctor
```

Your scripts, evidence, archives, `pws.config.json` and Claude Code approvals are never touched.
Rollback: `migrate --rollback <stamp>` (data) then `upgrade --rollback <stamp>` (code). Details:
`docs/architecture/MIGRATION.md`.

## Uninstall

Delete the installation folder and, if you wish, `~/.config/pine-workspace/install.json`.
Nothing else is written outside the installation folder.
