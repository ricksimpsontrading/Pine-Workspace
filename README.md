# Pine Workspace

**A structured Claude Code workspace for developing, maintaining, and publishing Pine Script v6 projects.**

Pine Workspace (PWS) brings development workflows, coding standards, documentation, validation tools, and publication preparation into one self-contained workspace. Use it to create indicators, strategies, and libraries—or continue working on existing scripts.

Start with the guided `/pws` menu, choose an action, then select your project. Configure your own identity and choose English or French for the interface.

[Download a release](https://github.com/ricksimpsontrading/Pine-Workspace/releases) · [Installation guide](INSTALL.md) · [Changelog](CHANGELOG.md) · [Licensing](docs/licensing/LICENSING.md)

## What you can do

| Task | How Pine Workspace helps |
|---|---|
| **Create a script** | Define the purpose, research the approach, and plan the architecture before implementation. |
| **Import an existing script** | Examine its code, record its existing license, and establish project-specific context. |
| **Develop and maintain** | Make focused changes with proportionate checks and a review of the resulting differences. |
| **Document your work** | Prepare explanations and tutorials for free, private, and commercial projects. |
| **Validate behavior** | Prepare TradingView checks and optionally run local behavioral tests with PineTS. |
| **Request an audit** | Run a deeper review when explicitly requested. |
| **Prepare publication** | Review licensing, documentation, and readiness before authorizing an export to GitHub. |

The same development and documentation standards apply to free and commercial scripts.

## Requirements

| Component | Requirement |
|---|---|
| **macOS** | First supported platform. Linux has not been verified; Windows support is deferred. |
| **Python 3.9 or later** | Required for the installer and workspace tooling. The Python tooling uses the standard library. |
| **Claude Code** | Required for the guided assistant workflows. |
| **Git** | Recommended for local history and required for Git-based publication workflows. |
| **Node.js and npm** | Optional; needed only for PineTS local tests. |

Pine Workspace runs inside Claude Code. Install and configure Claude Code before starting a workspace session.

## Quick start

### 1. Download and verify

From the [Releases page](https://github.com/ricksimpsontrading/Pine-Workspace/releases), download the packaged ZIP and its matching `.sha256` file.

For version 2.2.0, place both files in the same folder and run this command from that folder:

```bash
shasum -a 256 -c pine-workspace-2.2.0.zip.sha256
```

The result should report `OK`. This checks download integrity; the release does not include a cryptographic signature.

### 2. Install

Extract the ZIP, open Terminal in the extracted package folder, and run:

```bash
python3 install.py
```

The installer lets you choose:

- an installation folder;
- English or French;
- the copyright holder for your own scripts.

**Choose a separate installation folder.** The extracted package is the installer source, not your working installation. The installer refuses to overwrite a non-empty destination.

See [INSTALL.md](INSTALL.md) for detailed instructions, verification steps, and known installation limitations.

### 3. Open your workspace

In Terminal, switch to the installation folder you selected:

```bash
cd "/path/to/your/pine-workspace"
python3 -m tools.pws_workspace doctor
claude
```

Once Claude Code is running, enter:

```text
/pws
```

`/pws` is a command inside Claude Code, not a shell command.

The guided menu helps you choose your next action and the script to work on.

## Your workspace, your identity

Personal settings are stored in `pws.config.json`, including your identity, language, and workspace preferences. This configuration is excluded from version control and public distributions.

- **English is the default interface language.** French is also available.
- **Your scripts use your identity.** Pine Workspace does not insert its author's identity as the owner of your projects.
- **Generated legal templates are in English.** Imported legal documents retain their original content and language.
- **Licensing is project-specific.** Existing licenses are recorded rather than silently replaced.

You can change your preferences through the configuration menu.

## Everyday workflows

### Start a new project

Open `/pws` or describe your goal to Claude Code. The development workflow considers research, architecture, and project requirements before writing code.

### Continue an existing script

Place the `.pine` file in a project folder under `scripts/<project-name>/` and ask Pine Workspace to import it. The onboarding workflow examines the actual code and establishes its context and licensing information.

### Request focused changes or a deeper review

Routine development uses checks proportionate to the change. A comprehensive audit is a separate, explicitly requested workflow.

Documentation and tutorials can be prepared at any stage; they do not require publication.

### Prepare a publication

Publication preparation and publication itself are separate steps. Review the proposed destination and files before authorizing an export.

Git commits and pushes require authorization. Preparing a publication does not automatically publish a script to GitHub or TradingView.

## Validation: TradingView and PineTS

**TradingView remains the authority for Pine Script compilation and chart behavior.**

The default `manual` mode prepares checks for you to perform in TradingView. The optional `chrome-experimental` mode supports partial browser automation with a manual fallback.

PineTS provides an optional local testing environment. It can help investigate behavior, but a successful PineTS test does not establish TradingView compatibility.

PineTS is not bundled with the distribution. See the [optional PineTS installation instructions](INSTALL.md#5-optional-local-pinets-tests) before installing it. Its installation, updates, verification, and rollback are managed explicitly; it is never updated silently. Once it is installed, **Tools and updates → PineTS** guides an update of the engine: search, changes and licence review, one confirmation of a verified plan, verified restore point, installation, checks, and recalibration against the existing independent references.

## Updates and maintenance

To update an existing installation, open `/pws`, navigate to **Maintenance / configuration → Tools and updates**, and choose **Update Pine-Workspace**.

The guided workflow lets you:

1. See the installed version and search the official releases (or select a local package).
2. Review the changes, limitations, and the verified update plan: what will change, what is kept, and the checks.
3. Confirm the plan once.
4. Let the update and the planned migrations be applied and checked, then read the summary: result, remaining action, and recovery.

**Do not reinstall over an existing workspace.** Follow the [migration and rollback guide](docs/architecture/MIGRATION.md).

Workspace archives are stored locally under `docs/maintenance/archives/`. Local archives and Git history do not replace a backup on a separate device or service.

### Useful diagnostics

Run these commands from your installed workspace:

```bash
# Read-only diagnostic report
python3 -m tools.pws_workspace doctor

# Compact workspace status
python3 -m tools.pws_workspace session-status

# Integrated tooling status
python3 -m tools.pws_workspace tooling-status
```

The diagnostic command reports findings; it does not automatically repair them.

## Licensing

Pine Workspace is distributed with component-specific licenses:

| Component | License |
|---|---|
| **Pine Workspace core** | [Apache License 2.0](LICENSE) |
| **PineTS adapter** | [GNU AGPL v3 only](tools/pine_exec/LICENSE) |
| **PineTS engine, installed separately** | Its own license; see [third-party notices](THIRD_PARTY_NOTICES.md) |
| **Reusable legal templates** | [Apache License 2.0](LICENSE), plus the [Template Permission](docs/licensing/TEMPLATE_PERMISSION.md) |

Your scripts have their own licensing terms. Pine Workspace provides **FREE**, **PRIVATE**, and **COMMERCIAL** profiles and supports recording recognized licenses for imported scripts. A profile does not by itself determine source visibility or publication mode.

See the [license profiles](docs/licensing/PROFILES.md), [licensing matrix](docs/licensing/LICENSING.md), and [NOTICE](NOTICE) for details.

The legal scope of the boundary between the Apache-licensed core and the AGPL-licensed adapter remains unresolved. The documented allocation of licenses and successful technical tests do not constitute legal clearance. Generated legal templates are starting points to adapt, not universally applicable legal advice.

## Documentation

| Guide | Purpose |
|---|---|
| [Installation](INSTALL.md) | Requirements, setup, configuration, and installation checks |
| [Operations](docs/architecture/OPERATIONS.md) | Detailed workspace procedures |
| [Migration and rollback](docs/architecture/MIGRATION.md) | Updating an existing installation and recovery procedures |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Workspace structure and design decisions |
| [Pine Script standard](standards/PINE_SCRIPT_V6_STANDARD.md) | Development conventions |
| [Standard index](standards/INDEX.md) | Navigation through the standard |
| [Licensing](docs/licensing/LICENSING.md) | Component licenses, notices, and documented uncertainties |

The reference documentation under `docs/` and `standards/` is written in English. The Claude Code instruction files (`CLAUDE.md` and the skills, rules and agents under `.claude/`) and a few internal notes are currently written in French, and the Template Permission is provided in English and French. Whatever the language of a file, Claude Code is instructed to answer in the language you configured.

## Reporting an issue

Use [GitHub Issues](https://github.com/ricksimpsontrading/Pine-Workspace/issues) to report a reproducible problem.

Include your Pine Workspace version, operating system, the steps to reproduce the issue, and the relevant error message. Use a minimal example where possible.

Before posting, remove credentials, personal configuration, private script source, and any other sensitive information from logs or screenshots.
