# PINE WORKSPACE
# CLAUDE CODE PINE WORKSPACE — FINAL BOOTSTRAP SPECIFICATION

Construction document of the Claude Code workspace dedicated to Pine Script V6 development.

Specification reference date: 2026-09-04  
Scope: local Claude Code environment + local Git + Pine Script development + PineTS local behavioural execution + TradingView validation  
Initial TradingView validation mode: `manual`  
PineTS amendment ratified: 2026-08-23  
Controlled `chrome-experimental` operational learning amendment ratified: 2026-08-24  
PWS contextual menu amendment ratified: 2026-08-24  
PineTS local authority, capability granularity and reproducible datasets amendment ratified: 2026-08-27  
Global pre-bootstrap corrective amendment ratified: 2026-08-28  
Project independence amendment ratified: 2026-09-04  
§19.3 / §61.8 amendment (scope of the guarantees of `settings.local.json` against an uncoordinated external writer) ratified: 2026-09-06  
Maintenance amendment (attribution of the Stop hook findings, run reports version 2, group confirmations, minimal compilation, proportionate re-readings, provenances, tracking artefact, reconstructed research, tooling tests) ratified: 2026-09-27  
Maintenance supplement (alignment of the re-readings in §35.3 and of the statuses in §50.4, import recording, recording and promotion of a minimal compilation, §24.2 correspondence) ratified: 2026-09-27  
Consolidated evolution amendment (personal configuration `pws.config.json` §19A, licence profiles and schema 2 manifest §45, verification levels §24.2/§26, configured language, deterministic menu, PineTS tools, guided GitHub export path §43.5, archives and cleanup, public distribution and migrations §55, neutral edition: the "holder" replaces the named identity) ratified: 2026-11-06  
Verification levels alignment amendment (§24.2 steps 15-16, §26.1, §35.3, §41.1, flows §68 and §69; master §9.2; findings D-02 to D-04 of the audit of 2026-11-12/13) authorized by the holder: 2026-11-13  
PineTS adapter licence amendment (§24.4.13: adapter under AGPL-3.0-only, core under Apache-2.0; finding G-09) decided by the holder: 2026-11-13  
Legacy TradingView mode amendment (§19A: provenance of an explicit choice; conflict without provenance blocked until the holder's choice; finding F-14) decided by the holder: 2026-11-13  
Amendment of the licences of imported scripts (§45.2, §45.4, §45.4bis: compatible extension of schema 3, finding C-19) and of the actual-visibility check before sending a closed source (guided GitHub export path, finding I-06) decided by the holder: 2026-11-13  
Amendment of the original legal documents of imported scripts (§45.2, §45.4, §45.4bis, guided GitHub export path: `license.documents`, compatible extension of schema 3, export as is) and of the destination identity check for every send (guided GitHub export path) requested by the holder: 2026-11-14  
Reference-documentation language amendment (this specification translated into English, faithfully: requirements, section numbers, identifiers and decision references unchanged) and explicit statement of the configured language at session start (§40.2, §40.3) requested by the holder: 2026-11-14  
Amendment aligning the PWS menu description on the generated menu (§1.3, §40.5, with the TradingView mode route in the `tv-mode` section and §61) and wording the Stop hook messages in the configured language (§41.3) requested by the holder: 2026-11-14

---

## 0. PURPOSE OF THIS DOCUMENT

This document is the bootstrap specification of the Claude Code workspace used to develop, maintain, document, validate and prepare the publications of the Pine Script scripts of the workspace holder (identity and language configured in `pws.config.json`).

It does not replace the Pine Script master standard.

The Pine Script master standard remains the canonical authority on the development conventions of the scripts.

This specification governs something else:

- how Claude Code must organize the workspace;
- which Claude Code primitives must be used;
- how the context must be loaded;
- how an existing script must be onboarded;
- how a new script must be designed;
- how persistent information must be stored;
- which checks can be deterministic;
- how a local PineTS behavioural execution layer must be separated from the deterministic checks and from TradingView;
- how the real TradingView validation must be linked to the tested code;
- how to preserve autonomy without creating an unnecessarily complex system.

The bootstrap must be executed with one central rule:

> Design before writing.

The presence of a file in the target architecture defines a responsibility to fulfil, not a generic text to copy.

No operational file must be created simply to visually complete a directory tree.

Every file created must have a demonstrable function.

---

## 1. EXPECTED RESULT

At the end of the bootstrap, the workspace must enable two main product workflows, accessible directly or through a guided PWS facade.

### 1.1 Existing Pine script

The holder creates, for example:

```text
scripts/zigzag-orderblock/
└── ZigZag OrderBlock Retracement.pine
```

At the next startup, Claude Code automatically detects that the `.pine` is not onboarded.

Claude Code triggers the appropriate workflow, actually analyses the script, then creates only the specific context needed for THIS script.

The content of this context must be derived:

- from the real code;
- from the master standard;
- from the holder's decisions already known;
- from the current official documentation when necessary.

It must not be produced from a generic template filled in mechanically.

### 1.2 New script

The holder describes the objective of the new product.

Claude Code must use a workflow distinct from onboarding.

It must:

1. understand the objective;
2. clarify only the product decisions that are impossible to determine;
3. determine the distribution model;
4. carry out the current Pine research;
5. carry out the required TradingView benchmark;
6. define how the holder's solution can surpass the best relevant references without copying them;
7. design the product;
8. design its architecture;
9. create its specific context;
10. only then start the Pine code;
11. develop;
12. review;
13. run the deterministic local checks;
14. run the applicable PineTS behavioural tests according to their level of evidence;
15. actually validate in TradingView.

A new product must therefore not normally start with an empty `.pine` file created manually.

### 1.3 PWS contextual menu

The workspace must also provide a guided entry point, inside an interactive Claude Code session, in the form of a PWS contextual menu.

This menu:

- uses, as a priority, the native `AskUserQuestion` primitive when the current Claude Code surface provides it;
- is navigated with the native keyboard interface of Claude Code;
- opens submenus when several structured decisions are needed;
- adapts its choices to the real state of the workspace;
- routes to the same skills and contracts as the direct commands; for a user-only action that Claude cannot invoke, passes the explicit choice to the shared deterministic controller provided for by the contract;
- duplicates no Pine, product, validation or release logic;
- never becomes a second source of truth.

Conceptual example:

```text
PWS
  ↓
New script
  ↓
Indicator / Strategy / Library
  ↓
FREE  |  FREE with closed source  |  PRIVATE  |  COMMERCIAL
  ↓
Library → FREE with public source derived automatically
  ↓
summary and confirmation (Start / Modify / Cancel)
  ↓
pine-new
```

The menu remains explicitly reopenable during the session.

---

## 2. NON-NEGOTIABLE PRINCIPLES

### 2.1 A single Pine constitution

The master standard exists in a single canonical copy:

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Do not copy its content into:

- `CLAUDE.md`;
- the rules;
- the skills;
- the agents;
- the context files of the scripts;
- the deterministic tools.

The other elements of the workspace must apply, route, summarize locally or check subsets of this standard without becoming competing authorities.

### 2.2 No gigantic `CLAUDE.md`

The root `CLAUDE.md` must remain concise.

The current Claude Code documentation recommends aiming for fewer than 200 lines per `CLAUDE.md`.

Multi-step procedures go into skills.

Path-dependent instructions go into `.claude/rules/`.

Large reading/research/review tasks may be isolated in subagents.

### 2.3 No `@` import of the master standard

Do not import the master standard from `CLAUDE.md` with `@`.

An import is loaded into the context; it does not save the context cost.

The master standard is consulted on demand through its index and the workflows.

### 2.4 No decorative generic files

Prohibitions:

- fake example scripts;
- `.gitkeep` added only to materialize a folder;
- empty `TODO.md`;
- `CHANGELOG_TEMPLATE.md` without a real release;
- empty `release/` folder;
- empty `docs/` folder;
- empty `research/` folder;
- `PRODUCT.md` skeleton identical for all scripts;
- `ARCHITECTURE.md` filled with headings without real content;
- placeholders intended to be "filled in later" without an immediate need.

### 2.5 Git local-first

The workspace uses local Git.

The bootstrap:

- initializes local Git if necessary;
- creates no remote;
- does not configure GitHub or GitHub Actions;
- does not depend on the `gh` CLI;
- pushes nothing to a remote service.

GitHub is never a default dependency. Since the ratified decision of 2026-11-06, an **explicit guided export path** exists (§43.5): destinations configured in `pws.config.json`, list of contents allowed per licence profile, plan and preview of the included/excluded files, publication or update only after explicit authorization from the holder; `gh` is used for reading (`auth status`, `repo view`) and never for a destructive act; no token is stored by the workspace. This guided path introduces neither a remote in the workspace, nor remote CI, nor implicit push.

### 2.6 TradingView remains the final empirical truth for TradingView

No local verification constitutes a TradingView validation.

The workspace strictly distinguishes three layers:

```text
STATIC / DETERMINISTIC CHECKS
≠
LOCAL BEHAVIORAL EXECUTION
≠
TRADINGVIEW VALIDATION
```

`STATIC / DETERMINISTIC CHECKS` verifies only what can be established locally in a mechanical and reliable way.

`LOCAL BEHAVIORAL EXECUTION` executes the Pine source outside TradingView in order to observe its behaviour on controlled and reproducible data. This layer can in particular detect execution errors, behavioural divergences, regressions, stability anomalies or edge cases according to the capabilities actually qualified by its engine.

PineTS is the initial backend selected for this layer.

PineTS is a local behavioural execution laboratory. It is neither a normative authority on the official Pine Script syntax or semantics, nor an official TradingView implementation, nor general evidence of TradingView compatibility.

Within a strictly bounded local contract, PineTS can nevertheless produce a locally gating behavioural conclusion when all the materially necessary capabilities are `GATING`, their calibration is `CURRENT`, and the source, the dataset, the configuration and the execution environment are exactly identified.

`TRADINGVIEW VALIDATION` remains the final empirical validation of any behaviour specific to the TradingView platform and of any `tv-validate` step.

No PineTS result, whatever its quality, can:

- become a TradingView validation;
- satisfy a `tv-validate` step on its own;
- turn a persisted `unverified` or `in-progress` state into a successful validation;
- prove a TradingView parity that has not actually been observed in TradingView.

Conversely, a locally gating PineTS conclusion is not cancelled merely because it is not a TradingView validation: it can block the local cycle as long as the local behavioural contract concerned is not resolved, requalified or explicitly made non-gating according to the rules of this specification.

Claude Code must never declare a script validated in TradingView when no real validation has been run on the exact source concerned.

### 2.7 Two TradingView modes

The workspace must support:

```text
manual
chrome-experimental
```

`manual` is the initial and stable mode.

`chrome-experimental` automates as much as possible the same validation protocol in TradingView through the browser capabilities of Claude Code.

In case of ambiguity, failure, login, CAPTCHA, interface change, unverifiable action or uncertain visual result:

```text
chrome-experimental
        ↓
run fallback
        ↓
manual
```

The fallback of a run does not automatically modify the recorded mode.

Only the holder changes the persistent mode.

### 2.8 Publication never implicit

Automated Pine Editor validation does not give Claude the authorization to publish.

The initial bootstrap must not create any automation that:

- automatically clicks on a public publication;
- publishes a new version;
- modifies an `invite-only` access;
- modifies a commercial relationship;
- changes a visibility;
- performs an action that is hard to reverse.

Publication remains under the explicit control of the holder.

### 2.9 Non-normative automatic memory

If Claude Code auto-memory is active, it may retain:

- debugging learnings;
- practical particularities of the repo;
- useful commands;
- non-normative observations.

It never becomes the sole source of:

- product decision;
- signal contract;
- distribution model;
- release rule;
- Personal Convention;
- licence decision;
- durable business invariant.

Any durable information of this nature must be promoted into an appropriate versioned file.

Operational learnings related to `chrome-experimental` additionally follow the contract of §31.9. The auto-memory may temporarily retain a candidate observation, but any operational knowledge intended to be reused durably must be explicitly qualified, then promoted into `.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md`.

An observation that has not been promoted remains non-normative and must not be assumed to be true during a future run.

The bootstrap must not force the activation or deactivation of the user's auto-memory.

### 2.10 PINE WORKSPACE PROJECT-INDEPENDENCE INVARIANT

Pine Workspace is an autonomous Pine Script V6 development environment.

Its bootstrap, its operation, its validation, its tools, its documentation and its organization must not depend on the existence, the name, the path or the state of another external project.

Pine Workspace can coexist with other projects in the same parent directory, but this coexistence constitutes neither a dependency nor an authorization to scan, modify or follow symlinks to these other projects.

---

## 3. SOURCES OF AUTHORITY

Do not reduce these sources to a simplistic hierarchy that would destroy their own role.

Their responsibilities are complementary:

- the explicit product objective and the ratified decisions define the desired result;
- the current official documentation is the technical authority for Claude Code, Pine Script and TradingView within their respective scopes;
- this ratified specification is the construction contract of the workspace;
- the master standard defines the method, the quality, the conventions, the UX, the documentation and the Pine product identity;
- the specific context of the script defines the local applicability and the invariants of the product concerned.

A source must not be used to usurp the responsibility of another. Any real or apparent conflict must be reported explicitly to the holder with the passages concerned; it must never be resolved silently by an invented priority order.

### 3.1 Holder's objective

Defines WHAT the product must accomplish.

### 3.2 Current official TradingView / Pine Script documentation

Technical authority for:

- syntax;
- APIs;
- semantics;
- limitations;
- runtime;
- historical/realtime;
- requests;
- MTF;
- publication;
- current technical rules.

### 3.3 The holder's Pine Script master standard

Defines the development, quality, UX, architecture, documentation and product conventions.

### 3.4 Specific context of the script

Describes the reality and the invariants specific to the product concerned.

### 3.5 Explicit decisions of the holder

Govern the ratified product decisions that cannot be deduced from the code or from the technical documentation.

In case of a Pine/TradingView conflict, apply the resolution method defined in the master standard. For a conflict concerning the construction of the workspace or a Claude Code primitive, compare the specification with the current official documentation, report the gap and request a decision when it cannot be resolved without modifying the ratified contract.

---

## 4. FILE CATEGORIES

The bootstrap must explicitly assign a category to each durable artefact.

### 4.1 Pine normative

Example:

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Cannot be regenerated from a summary.

### 4.2 Workspace architecture normative

This bootstrap specification constitutes the construction contract of the workspace.

The canonical instance is kept under:

```text
docs/architecture/BOOTSTRAP_SPEC.md
```

It is not loaded automatically in every session.

### 4.3 Derived

Examples:

- `standards/INDEX.md`;
- `standards/TRACEABILITY.md`;
- research syntheses;
- validation states;
- maps produced from the code.

A derived artefact must be able to be declared stale.

### 4.4 Operational

Examples:

- `CLAUDE.md`;
- rules;
- skills;
- agents;
- settings;
- deterministic tools.

An operational artefact materializes a procedure or a mechanism.

It must not become a second constitution.

### 4.5 Evidence

Examples:

- TradingView validation report;
- useful screenshot;
- test log;
- hash of the source actually tested.

Evidence describes a real observation.

It is not an opinion.

### 4.6 Ephemeral

Examples:

- session state of a hook;
- local cache;
- temporary files.

These elements are gitignored and never become a durable authority.

---

## 5. MINIMAL INITIAL STATE

The bootstrap must accept an almost empty project.

Required inputs:

1. this specification;
2. the holder's Pine Script master file;
3. Claude Code installed;
4. Git available or installable locally;
5. an appropriate local runtime for the small deterministic tools.

The bootstrap must identify the master file unambiguously.

If it finds several plausible candidates, it asks the holder which one is canonical.

It does not choose silently.

The master file is then moved explicitly, without normative duplication, to:

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Compute its SHA-256 before and after the move and verify that the content is identical.

This specification is likewise moved explicitly to:

```text
docs/architecture/BOOTSTRAP_SPEC.md
```

Compute its SHA-256 before and after the move and verify that the content is identical.

Record in `BOOTSTRAP_REPORT.md` the two `old path → canonical path` mappings, the before/after hashes and any reason exceptionally preventing a move. An input copy kept for a demonstrated necessity must be explicitly marked non-normative; no silent double authority is allowed.

---

## 6. DISCOVERY BEFORE ANY WRITING

Before creating the final directory tree, Claude Code must carry out a genuine discovery phase.

### 6.1 Environment

Detect in particular:

- OS;
- shell;
- possible presence of WSL;
- Claude Code version;
- project path;
- Git version;
- Git state;
- current branch;
- existing remotes;
- Python 3 runtime or local alternative;
- Node.js runtime and package manager available for the PineTS layer;
- possible presence of a pre-existing PineTS installation, configuration or version in the workspace;
- Claude Code browser capabilities actually available;
- already existing local Claude configuration;
- `.claude/` files already present.

Before any writing, also establish the physical boundary of the workspace:

1. resolve the physical path of the workspace without losing support for spaces;
2. determine the effective Git root, in particular with `git rev-parse --show-toplevel` when applicable;
3. check whether a parent repository encloses the `pine workspace` folder;
4. if an enclosing Git root exists above the expected workspace, stop before any mutation and ask the holder for a decision;
5. refuse any recursive scan, any mutation or any symlink following from the workspace to the content of another project or to a location outside its physical root;
6. handle paths through path objects or structured arguments, never through fragile shell concatenation.

The discovery and the tests must cover a workspace root and a source name containing spaces.

The absence of Node.js or PineTS must never be interpreted as a defect of the Pine source.

If the PineTS layer cannot be initialized cleanly, the workspace remains functional and TradingView validations remain available according to their normal workflow.

Before any initial installation or upgrade of PineTS, check the current version, documentation, licence and limitations of the upstream project. The version choice must start from the current npm registry and from the exact artefact actually installable, then be confirmed by the package metadata, the installed tarball and the lockfile; do not deduce the version from `main`, a README, a badge or the Releases page alone.

### 6.2 Current Claude Code documentation

Check in the current official documentation which primitives are actually available before generating their configuration.

At a minimum:

- `CLAUDE.md`;
- `.claude/rules/`;
- project skills;
- custom subagents;
- hooks;
- project/local settings;
- permission rules;
- worktrees;
- `.worktreeinclude`;
- Chrome integration;
- configuration diagnostics.

Also check the effective resolution of critical skill names and the current precedence between personal skills, project skills and other sources in order to detect any collision that would hijack `/pws`, `/tv-mode` or another critical command.

Do not rely only on this specification if Claude Code has evolved.

### 6.3 Current TradingView documentation

Check at a minimum that the current Pine V6 documentation is accessible.

The construction of the workspace must not freeze Pine numerical limits that can evolve.

### 6.4 Complete analysis of the master standard

Read the master standard in full before designing:

- rules;
- skills;
- agents;
- checks;
- workflows.

Build an internal matrix:

```text
requirement
→ permanence
→ application context
→ suitable Claude Code primitive
→ type of check
→ responsible artefact
```

Conceptual examples:

```text
Current Pine research
→ per task
→ Pine development
→ skill + researcher
→ semantic

Prohibition of shorttitle
→ mechanical rule
→ Pine source
→ local guard
→ deterministic

Local behavioural execution
→ depending on applicability
→ modified Pine source
→ pine-local-test + thin adapter PineTS
→ local behavioural, capability-gated

TradingView validation
→ end of cycle
→ modified Pine source
→ tv-validate
→ empirical
```

---

## 7. DESIGN GATE BEFORE CREATING THE FILES

Before writing the final architecture, Claude Code must justify each artefact considered.

For each file or folder:

1. What responsibility does it hold?
2. Which source of authority feeds its content?
3. Who reads it?
4. When is it loaded?
5. Who modifies it?
6. Is it normative, derived, operational, evidence or ephemeral?
7. Does its content already exist elsewhere?
8. Is a native Claude Code primitive better?
9. Can it be created only at the moment it becomes necessary?
10. How can one detect that it is stale?
11. What concrete defect appears if it does not exist?

If the answers do not justify the artefact, do not create it.

---

## 8. INDEPENDENT CRITIQUE BEFORE IMPLEMENTATION

Before the definitive creation, run an independent review of the proposed architecture.

This review must look for:

- duplication of the master standard;
- contradictory rules;
- rules always loaded when they could be conditional;
- skills that are too long;
- unnecessary agents;
- hooks that attempt to judge semantics;
- generic files;
- duplicated states;
- central registries that could drift;
- unnecessary external dependencies;
- over-automation;
- invented or obsolete Claude Code features;
- responsibilities without an owner;
- conventions of the standard that are not operationalized.

Correct the architecture before writing.

---

## 9. TARGET ARCHITECTURE

The architecture below is the expected result at maturity.

Folders marked "on demand" must not be created as long as they serve no purpose.

```text
<workspace-root>/
│
├── CLAUDE.md
├── README.md
├── .gitignore
├── .worktreeinclude
│
├── .claude/
│   ├── settings.json
│   ├── settings.local.json              # local, gitignored
│   │
│   ├── rules/
│   │   ├── pine-source.md
│   │   ├── script-context.md
│   │   ├── research.md
│   │   ├── validation.md
│   │   ├── pinets-behavioral.md
│   │   ├── documentation.md
│   │   └── release.md
│   │
│   ├── skills/
│   │   ├── pws/
│   │   │   └── SKILL.md
│   │   ├── pine-onboard/
│   │   │   └── SKILL.md
│   │   ├── pine-new/
│   │   │   └── SKILL.md
│   │   ├── pine-develop/
│   │   │   └── SKILL.md
│   │   ├── pine-research/
│   │   │   └── SKILL.md
│   │   ├── pine-review/
│   │   │   └── SKILL.md
│   │   ├── pine-local-test/
│   │   │   └── SKILL.md
│   │   ├── pine-release/
│   │   │   └── SKILL.md
│   │   ├── tv-validate/
│   │   │   ├── SKILL.md
│   │   │   ├── MANUAL.md
│   │   │   └── CHROME_EXPERIMENTAL.md
│   │   ├── tv-mode/
│   │   │   └── SKILL.md
│   │   └── project-doctor/
│   │       └── SKILL.md
│   │
│   └── agents/
│       ├── pws-pine-cartographer.md
│       ├── pws-pine-researcher.md
│       ├── pws-pine-reviewer.md
│       └── pws-release-reviewer.md
│
├── standards/
│   ├── PINE_SCRIPT_V6_STANDARD.md
│   ├── INDEX.md
│   └── TRACEABILITY.md
│
├── scripts/
│   └── <script-slug>/                   # only for a real product
│       ├── CLAUDE.md
│       ├── SCRIPT.json
│       ├── <actual-source>.pine
│       ├── PRODUCT.md
│       ├── ARCHITECTURE.md
│       ├── DECISIONS.md                 # on demand
│       ├── research/                    # on demand
│       │   ├── CURRENT.md
│       │   └── runs/
│       ├── tests/                       # on demand
│       │   └── behavioral/              # on demand
│       │       ├── config.json          # only if a test contract exists
│       │       ├── fixtures/            # only if specific to the product
│       │       └── baselines/           # only for accepted baselines
│       ├── validation/
│       │   ├── current.json
│       │   ├── runs/                    # at the first validation
│       │   └── evidence/                # only if file evidence is useful
│       ├── docs/                        # on demand
│       └── release/                     # on demand
│
├── docs/
│   └── architecture/
│       ├── BOOTSTRAP_SPEC.md
│       ├── ARCHITECTURE.md
│       ├── FILE_CONTRACTS.md
│       ├── OPERATIONS.md
│       └── BOOTSTRAP_REPORT.md
│
└── tools/
    ├── pws_workspace/
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── core.py
    │   ├── scan.py
    │   ├── standard.py
    │   ├── guard.py
    │   ├── validation.py
    │   └── tv_mode.py
    ├── pine_exec/
    │   ├── package.json
    │   ├── package-lock.json
    │   ├── runner.mjs
    │   ├── normalize.mjs
    │   └── calibration/
    └── tests/
        ├── test_scan.py
        ├── test_standard.py
        ├── test_guard.py
        ├── test_validation.py
        ├── test_tv_mode.py
        └── test_pine_exec.py             # or an equivalent, justified factorization
```

The exact internal breakdown of the Python package may be slightly adjusted if the real analysis demonstrates a better factorization.

It must not, however, become a bulky framework.

`tools/pine_exec/` is a minimal Node thin adapter around PineTS.

It must not become:

- a local platform;
- a server;
- a network service;
- an MCP;
- a database;
- a dashboard;
- a general-purpose backtesting framework;
- a functional clone of TradingView or of LuxAlgo Quant.

The internal breakdown of the thin adapter may be slightly adjusted if the real implementation justifies it, but its responsibility remains limited to:

```text
Pine source
+
dataset
+
configuration
+
capability state
        ↓
PineTS
        ↓
normalized output
```

Temporary execution results must not be stored durably in the product tree by default.

`tests/behavioral/` contains only the contracts, specific fixtures and baselines that have a durable use.

`validation/` remains exclusively reserved for TradingView validation and its evidence.

### 9.1 Conventions common to rules

All the rules of the initial foundation must have a real `paths` scope.

A rule without `paths` would be loaded in every session and must therefore be rejected unless an exceptional justification is demonstrated.

### 9.2 Conventions common to skills

For each skill:

- write a short, specific `description` that is distinct enough to avoid ambiguous triggering;
- use only the tools actually needed;
- keep `SKILL.md` concise; the current Claude Code documentation recommends fewer than 500 lines;
- move detailed references into supporting files only when they bring real value;
- do not create a supporting file that would only be a copy of part of the master standard;
- reserve `disable-model-invocation: true` for the actions that the holder must trigger themselves.

Skill descriptions are part of the discovery context. They must therefore be informative without becoming mini-prompts.

### 9.3 Conventions common to subagents

Each agent must have:

- a mission that does not overlap that of another agent;
- the minimum of required tools;
- an explicit write policy;
- an explicit memory policy;
- a return format useful to the parent.

The four agents of the initial foundation are specialized in reading, research or review. They must not modify the Pine source.

---

## 10. ROOT `CLAUDE.md` — CONTRACT

### 10.1 Role

Permanent router of the workspace.

### 10.2 Size

Aim for well under 200 lines.

### 10.3 Necessary content

It must contain only what Claude must know in almost every session:

- identity of the workspace;
- general mission;
- invariant of independence from any other external project and confinement to the physical root of the workspace;
- roles of the sources of authority;
- canonical path of the master standard;
- very short map of the repo;
- universal language rules;
- prohibition on inventing facts;
- prohibition on modifying the constitution without an explicit request;
- local-first Git policy;
- non-normative memory policy;
- detection/onboarding rule for unregistered `.pine` files;
- routing to the PWS contextual menu and the main skills;
- strict separation between deterministic checks, PineTS local behavioural execution and TradingView validation;
- reminder that PineTS is capability-gated, can produce a local gate on a strictly bounded contract, and never replaces the official Pine Script authority or the TradingView empirical validation;
- prohibition on declaring a fictitious TradingView success;
- prohibition on implicit publication.

### 10.4 What does not belong there

Do not copy:

- detailed Pine conventions;
- tooltip rules;
- palettes;
- complete SemVer;
- release procedures;
- complete research workflow;
- MTF checklist;
- TradingView guide;
- content of the master standard.

### 10.5 Import

Do not import the master standard with `@`.

Reference its path as inline code.

---

## 11. `README.md` — CONTRACT

### 11.1 Audience

Human.

### 11.2 Function

Present briefly:

- purpose of the workspace;
- autonomy of the workspace and absence of any required sibling project;
- location of the scripts;
- how to add an existing script;
- how to request a new script;
- how to launch Claude Code;
- how to change the TradingView mode;
- how to run `project-doctor`;
- local Git principle.

### 11.3 Non-duplication

Detailed procedures go into `docs/architecture/OPERATIONS.md`.

The README does not become a second manual.

---

## 12. `standards/INDEX.md` — CONTRACT

### 12.1 Status

Derived, non-normative.

### 12.2 Source

`PINE_SCRIPT_V6_STANDARD.md`.

### 12.3 Content

Include:

- SHA-256 of the source standard;
- generation date;
- sections;
- exact titles;
- current lines or useful ranges;
- routing keywords;
- main operational consumers.

### 12.4 Freshness rule

If:

```text
SHA(master) != SHA recorded in INDEX
```

the index is `STALE`.

It must no longer be used as a reliable representation until it is regenerated.

### 12.5 Generation

Generate automatically from the real headings of the standard.

Do not invent sections.

---

## 13. `standards/TRACEABILITY.md` — CONTRACT

### 13.1 Status

Derived, architectural, non-normative.

### 13.2 Purpose

Show where each part of the master standard is operationalized.

Example structure:

```text
Section of the standard
→ context/rule
→ skill
→ agent, if any
→ deterministic check, if any
→ local behavioural execution, if any
→ empirical validation, if any
```

### 13.3 Usefulness

Prevent:

- omission of a convention;
- unnecessary duplication;
- creation of competing rules;
- forgetting a mechanism during a future evolution of the standard.

### 13.4 Freshness

Store the SHA-256 of the master standard.

Any modification of the master makes the traceability `STALE` until review.

Regeneration requires a semantic analysis.

Do not claim that a simple parser can correctly recreate this mapping.

---

## 14. WORKSPACE `ARCHITECTURE.md` — CONTRACT

Explain the decisions and above all their reasons.

Include in particular:

- why the master is unique;
- why the workspace does not depend on the existence, the name, the path or the state of any other project;
- why it is not imported into `CLAUDE.md`;
- why the rules are path-scoped;
- why procedures go into skills;
- why large tasks use fresh subagents;
- why review agents have no persistent memory;
- why local checks remain mechanical;
- why local behavioural execution is separated from deterministic checks;
- why PineTS can be a capability-gated local execution authority on a bounded contract without competing with the official Pine Script documentation or with TradingView as the authority on the behaviour specific to the platform;
- why TradingView is a separate empirical layer;
- why Git is local-first;
- why no central registry of scripts exists;
- why script contexts are co-located;
- why the release/docs/research folders are on demand;
- why GitHub, MCP, Agent Teams, dynamic workflows and remote CI are not initial dependencies.

Do not rephrase the entire Pine standard.

---

## 15. `FILE_CONTRACTS.md` — CONTRACT

For each durable artefact of the workspace, document:

- responsibility;
- category;
- source of authority;
- reader;
- writer;
- creation trigger;
- update trigger;
- freshness status, if any;
- forbidden content;
- duplicates it must avoid;
- usefulness test.

This file serves as a guard against decorative artefacts.

---

## 16. `OPERATIONS.md` — CONTRACT

Concise human document for recurring operations.

Must describe:

- that Pine Workspace works autonomously, without any required sibling project, and must be launched from its own physical root;
- opening or reopening the PWS contextual menu;
- adding an existing `.pine`;
- creating a new product with Claude Code;
- running the doctor;
- understanding the `source_registration_status`, `product_structure_status` and `validation_effective_status` axes, in particular `UNREGISTERED`, `INCOMPLETE`, `BROKEN` and `stale`;
- changing the TradingView mode;
- running a manual validation;
- running an experimental Chrome validation;
- running `pine-local-test` when a local behavioural test is applicable;
- interpreting `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL`, `PINETS_INCONCLUSIVE` and regression changes without confusing them with a TradingView validation;
- performing a controlled upgrade of PineTS with mandatory recalibration;
- using a worktree when a piece of work justifies it;
- local Git behaviour;
- optional local backup strategy.

Do not copy the Pine development rules.

---

## 17. `.gitignore` — CONTRACT

Must ignore at a minimum the truly local or ephemeral elements produced by this workspace.

Applicable examples:

```text
.claude/settings.local.json
CLAUDE.local.md
.claude/runtime/
tools/pine_exec/node_modules/
.claude/worktrees/
.claude/runtime/pine-local-test/
__pycache__/
*.pyc
```

Add the OS/editor artefacts actually present only if necessary.

Do not copy a huge generic `.gitignore` from the Internet.

Never ignore:

- `.pine`;
- versioned script contexts;
- master standard;
- rules;
- skills;
- agents;
- validation reports intended to persist;
- `tools/pine_exec/package.json`;
- `tools/pine_exec/package-lock.json`;
- `tools/pine_exec/calibration/`;
- `scripts/**/tests/behavioral/config.json`, fixtures and baselines when they exist and have a durable use.

---

## 18. `.worktreeinclude` — CONTRACT

Purpose: preserve in the worktrees the gitignored local files on which the workflow depends.

Include at a minimum, when they exist:

```text
.claude/settings.local.json
CLAUDE.local.md
```

Do not copy unnecessary secrets.

`.worktreeinclude` never constitutes a backup mechanism.

---

## 19. `.claude/settings.local.json` — CONTRACT

### 19.1 Status

Local, gitignored. Since the amendment of 2026-11-06, this file belongs to Claude Code alone (approvals and local settings of the tool): the workspace no longer writes to it. The PWS-specific configuration lives in `pws.config.json` (§19A).

### 19.2 Initial value

No PWS value is initialized there. History: until 2026-11-06, the TradingView mode was persisted there under `env.PWS_TV_VALIDATION_MODE`; this key is read for compatibility as long as it exists (never through a symbolic link), then settled by the migration (`migrate --apply`, steps m001/m003, §19A rule of 2026-11-13: copied if `pws.config.json` has no usable mode, kept in the configuration if the values match or if the holder has chosen explicitly, otherwise conflict blocked until the holder's choice) and removed only afterwards, without touching any other key.

### 19.3 Evolution

This file receives the local approvals that Claude Code keeps there. The workspace never overwrites them; the only PWS write allowed is the removal, once, of the legacy key above by the migration, under lock, with preservation of all the other keys and refusal in case of conflict.

### 19A. `pws.config.json` — CONTRACT (ratified on 2026-11-06)

Personal file at the root of the workspace, gitignored, copied into the worktrees via `.worktreeinclude`, never included in a distribution. Schema 1: `schema_version`, `workspace_version` (core version recorded by `init`/`migrate`), `language` (`en` by default in a new installation, `fr` kept by the migrated installation), `identity` (`copyright_holder`, `header_aliases`, `default_profile`), `tv_validation_mode` (`manual` by default, `chrome-experimental` explicitly optional; optional `tv_validation_mode_choice` = provenance of an explicit choice of the holder through `tv-mode` or `config set`, which alone resolves a conflict with a legacy value — migration m001, rule decided by the holder on 2026-11-13), `github.destinations`, `maintenance.startup_cleanup`, `migrations`. Tolerant reading: missing file → default values (never an error); invalid file → defaults plus actionable diagnostic (doctor BLOCKING). Writes: `init`, `config set`, `tv-mode <mode>`, `github destination-*`, `migrate`, all through the same configuration controller (`tools/pws_workspace/config.py`).

The persisted source of the TradingView mode is `pws.config.json`, not a variable inherited by the process. Every mutation must:

1. read the current file;
2. validate that it has not changed between reading and writing;
3. perform a read-modify-write that preserves all the other keys, in particular the approvals;
4. write a temporary file in the same filesystem, then perform an atomic replacement;
5. re-read and validate the resulting JSON;
6. report a conflict instead of silently overwriting any concurrent modification detected between the initial read and the re-read preceding the atomic replacement.

The scope of these guarantees:

- between workspace writers (the configuration controller and any PWS tool), serialization is guaranteed by a shared exclusive lock (`pws.config.json.lock`) covering the entire read-check-write transaction;
- `pws.config.json` has no known external writer (Claude Code does not write to it): the residual window documented on 2026-09-06 for `settings.local.json` no longer applies to the TradingView mode; it remains true for `settings.local.json` itself, which the workspace no longer writes outside the legacy migration;
- if a future version of Claude Code exposes a coordination mechanism for its files, the controller must be re-evaluated in order to use it.

After writing, re-read through the controller (`tv-mode` without an argument) to check that the persisted value is the expected one. A process variable is never a read path.

---

## 20. `.claude/settings.json` — CONTRACT

### 20.1 Worktrees

Configure:

```json
{
  "worktree": {
    "baseRef": "head"
  }
}
```

if this syntax is still valid in the installed version.

The purpose is to make the worktrees start from the local `HEAD`, without depending on a remote.

### 20.2 Permissions

Configure a cautious local policy.

Principles:

- routine Git reading: allowable;
- `git diff`, `git status`, `git log`, `git show`: normal use;
- `git commit`: user confirmation;
- creation/modification/deletion of a remote: user confirmation;
- `git push`: user confirmation (never a general authorization; `--force` refused);
- `gh`: read-only allowed (`auth status`, `repo view`); `auth login`, `repo create`: confirmation; `repo delete`, `api`, `secret`, `auth token`: refusal;
- read-only PWS subcommands: allowable; mutating subcommands with an external or irreversible effect (`github publish`, `github fetch`, `pinets install`, `pinets rollback`, `pinets check-update`, `migrate --apply`, `migrate --rollback`, `maintenance archives-remove-source`): confirmation;
- destructive Git commands: confirmation or refusal depending on severity;
- permission bypass: do not enable it from the project.

Check the current `allow` / `ask` / `deny` syntax.

Never add a broad permission only to avoid prompts.

### 20.3 Hooks

Configure only the hooks justified in this specification.

### 20.4 Sandbox

Do not arbitrarily enable or disable a system sandbox without checking:

- OS;
- support;
- impact;
- existing configuration of the holder.

The bootstrap may recommend a configuration, but must not modify a system policy outside the project without necessity and consent.

---

## 21. PATH-SCOPED RULES

Rules must remain short.

They must not contain the whole of the master.

### 21.1 `pine-source.md`

Scope:

```yaml
paths:
  - "scripts/**/*.pine"
```

Mission:

- recognize a Pine source of the holder;
- check that the product is onboarded before substantive modification;
- point to the local context of the script;
- point to the master standard without importing it;
- recall the `pine-develop` workflow;
- recall that deterministic checks, PineTS behavioural execution and TradingView validation are three distinct layers;
- route to `pine-local-test` when the workflow or the risk of the modification justifies a local execution;
- forbid any modification of the Pine source whose only justification would be to satisfy a PineTS incompatibility, limitation or divergence.

Do not copy all the Pine conventions.

### 21.2 `script-context.md`

Scope covering:

- `SCRIPT.json`;
- `PRODUCT.md`;
- `ARCHITECTURE.md`;
- `DECISIONS.md` when it exists;
- `CLAUDE.md` in the product folders.

Main rule:

> Never turn an observation or an inference into a decision of the holder.

Distinguish:

- observed;
- confirmed;
- inferred;
- to be confirmed.

The following provenances remain distinct and never substitute for one another: observation in the source; dated official documentation fact; dated benchmark observation; inference; confirmation by the holder of an observation; ratification by the holder of a product decision. Absent evidence means not demonstrated, never not performed.

### 21.3 `research.md`

Scope:

```text
scripts/**/research/**
```

Require:

- date;
- question;
- sources;
- facts;
- conclusions;
- observation/inference distinction;
- freshness status.

### 21.4 `validation.md`

Scope:

```text
scripts/**/validation/**
```

Forbid:

- `validated` without a real run;
- evidence not linked to the hash of the source;
- confusion between local test and TradingView;
- misleading manual modification of the state.

### 21.5 `documentation.md`

Scope covering the user-facing docs of the scripts.

Must route to the applicable sections of the standard.

Do not duplicate the complete style of the tutorials.

### 21.6 `release.md`

Scope covering the release artefacts.

Must enforce:

- re-reading of the current TradingView rules;
- application of `pine-release`;
- prohibition of implicit automatic publication.

### 21.7 `pinets-behavioral.md`

Scopes:

```yaml
paths:
  - "tools/pine_exec/calibration/**"
  - "scripts/**/tests/behavioral/**"
```

This rule remains concise and protects only the invariants capable of modifying a local gate:

- no `GATING` promotion without sufficient independent calibration;
- application of the staleness causes of §24.4.5;
- durable baseline only after an acceptance compliant with §24.4.10;
- no writing of PineTS evidence under `validation/`;
- no modification of the Pine source whose only justification would be to satisfy PineTS.

It routes to the `pine-local-test` contract instead of copying the whole PineTS doctrine.

---

## 22. SKILL `pine-onboard`

### 22.1 Trigger

Claude may invoke it automatically when a `.pine` under `scripts/**` is detected as not onboarded or partially onboarded.

### 22.2 Principle

Onboarding = understanding and contextualization.

Onboarding ≠ refactoring.

### 22.3 Steps

1. Identify the product root.
2. Identify the `.pine` file or files.
3. If several sources make the root ambiguous, ask the holder.
4. Read the main source in full.
5. Read the applicable parts of the master via the index.
6. Map the script.
7. Identify:
   - Pine type;
   - main declaration;
   - modules;
   - inputs;
   - dependencies;
   - types/enums/UDTs;
   - state;
   - arrays/maps/matrices;
   - requests;
   - MTF;
   - signals;
   - objects;
   - tables;
   - alerts;
   - sensitive performance;
   - historical/realtime/repaint risks.
8. Determine the licence profile and its axes (§45) if the real header of the code or a reliable decision allows it; note the existing legal notices without removing them.
9. If `script_kind = library`, derive FREE with public source according to §45.4 and report any incompatible existing value.
10. If the profile, the access or the publication mode remains ambiguous for an indicator or a strategy, ask the holder; never guess.
11. Define what is observed, confirmed and to be confirmed.
12. Create `SCRIPT.json`.
13. Create `PRODUCT.md`.
14. Create `ARCHITECTURE.md`.
15. Create the local `CLAUDE.md`.
16. Create `validation/current.json` in the non-validated state.
17. Create `DECISIONS.md` only if at least one real durable decision exists.
18. Create `research/` only if real research has been carried out and deserves to be kept.
19. Run the structural checks.
20. Review the new files to remove generic content.
21. Mark the onboarding complete only if the minimal context is consistent.

### 22.4 Prohibitions

During onboarding alone:

- do not modify the `.pine` to "correct" what is discovered;
- do not invent a product intention;
- do not invent a distribution model;
- do not record an inference as a decision;
- do not create a release/docs folder without need;
- do not declare the script validated.

### 22.5 Result

The product obtains `product_structure_status = REGISTERED` only after structural validation of its context.

---

## 23. SKILL `pine-new`

### 23.1 Trigger

Use when no Pine source exists yet and the holder requests the creation of a new product.

### 23.2 Mandatory workflow

1. Understand the functional objective.
2. Define the audience.
3. Determine `script_kind` among `indicator`, `strategy` and `library`.
4. Determine the licence profile and its axes according to §45 (FREE, FREE with closed source, PRIVATE, COMMERCIAL). For `library`, automatically derive FREE with public source and never propose or accept paid access or a closed source as long as the current TradingView rule requires the open-source publication of libraries.
5. Check that the objective is sufficiently complete, mature and differentiated for the intended product — the ambition depends on the product, not on the profile (master §5).
6. Check the relevant current Pine V6 documentation.
7. Search for the best public open-source scripts in the domain.
8. Give priority to relevant Editors’ Picks.
9. Analyse the best accessible references.
10. Identify their strengths, limits, trade-offs and weaknesses.
11. Define how an original solution by the holder can surpass them.
12. Define the product before the code.
13. Define the user decisions that are actually necessary.
14. Design the architecture.
15. Design the settings.
16. Design the states and data flows.
17. Design MTF/realtime/repaint if applicable.
18. Design visualization and alerts only if useful.
19. Define the risks.
20. Obtain the holder's confirmation for non-delegable product decisions.
21. Create the stable folder `scripts/<slug>/`.
22. Create the specific product context.
23. Create the first research run.
24. Determine the initial product version according to a decision by the holder or an explicitly ratified policy.
25. Never invent a universal initial-version convention if it does not exist.
26. Create the `.pine` with its appropriate header.
27. Develop section by section.
28. Review.
29. Run the deterministic local checks.
30. Run `pine-local-test` according to applicability, the capabilities actually used, the current calibration and proportionality.
31. Qualify any behavioural result before deducing a fix from it.
32. Actually validate in TradingView.
33. Synchronize the final context.

### 23.3 Slug

The product folder uses a slug:

- stable;
- ASCII;
- in kebab-case;
- descriptive;
- not dependent on the product version.

Do not automatically rename an existing slug without a structural reason.

---

## 24. SKILL `pine-develop`

Main orchestrator of modifications.

### 24.1 Input

A request from the holder concerning an onboarded script.

### 24.2 Sequence

1. Read the required local context.
2. Understand the request precisely.
3. Classify the task according to the master standard; the verification level (master §9.1) is routine work (this skill) except in a deep audit requested by the holder (`pine-audit`, announced scope) or in publication preparation (`pine-release`).
4. Read the product map (`ARCHITECTURE.md`), then the blocks concerned and their relevant dependencies, extended according to the class of the task; full read only in an explicitly requested audit (amendment of 2026-11-06: no full read, no agent, no cascade of reviews triggered automatically by a modification, whatever its class — a structural change included).
5. Use `pws-pine-cartographer` only in a requested audit or an onboarding, when the size/complexity justifies isolating the volume.
6. Establish the impact inventory.
7. Check the relevant current Pine documentation.
8. Perform the benchmark relevance check.
9. Run `pine-research` if necessary.
10. Define the minimal coherent modification.
11. Plan.
12. Implement.
13. Re-read according to the coverage of master §9.2.
14. Synchronize the dependent artefacts.
15. Independent review (`pine-review`) only in a requested deep audit, in publication preparation or at the holder's request; never triggered by the class of the task (amendment of 2026-11-13).
16. Fix the retained findings.
17. Run the deterministic local checks.
18. Run `pine-local-test` according to applicability, the capabilities actually used, the current calibration, the impact inventory and a depth proportionate to the modification.
19. Qualify the PineTS results. If a fix of the source is actually justified by the objective, the standard, the Pine documentation or the expected behavioural contract, fix it, then rerun the applicable local steps.
20. Prepare/run `tv-validate` according to applicability: intermediate minimal compilation when the impact inventory justifies it (§30.5), functional campaign on the stabilized source.
21. Revalidate after any fix that changes the source.
22. Update only the context files that have actually become obsolete.

Correspondence with master §38: spec 1 (local context) → workspace-specific; 2 → §38.1; 3 → §38.2; 4 → §38.4; 5 → §38.5; 6 → §38.6; 7 → §38.7; 8 → §38.8; 9 → §38.9 and §38.10; 10 → §38.11 to §38.13; 11 (plan) → workspace-specific; 12 → §38.14; 13 → §38.15; 14 → §38.18; 15 → §38.16 and §38.17; 16 (fix after the review) → workspace-specific; 17 (deterministic checks), 18 and 19 (PineTS) → workspace-specific; 20 → §38.19 and §38.20; 21 → §38.21 and §38.22; 22 → spec §53. Master §38.23 (deliverables) falls under `pine-release`. Master §38.3 (distribution model) is read via `SCRIPT.json` at step 1.

### 24.3 No scope creep

Unrequested improvements are proposed to the holder before implementation when they constitute a product decision.


### 24.4 Skill `pine-local-test` — contract

This subsection constitutes the normative contract of the skill:

```text
.claude/skills/pine-local-test/SKILL.md
```

#### 24.4.1 Mission

`pine-local-test` provides a local behavioural execution of the exact Pine source by means of PineTS.

Its mission is to produce reproducible observations and, when a local contract allows it, locally gating behavioural conclusions before `tv-validate`.

It never constitutes:

- a TradingView validation;
- an authority on official Pine Script syntax or semantics;
- a universal proof of non-repaint;
- a general proof of parity with the Strategy Tester or with TradingView;
- a proof of TradingView performance;
- an automatic instruction to modify the code.

A PineTS conclusion may be locally blocking only when it is precisely bounded to the source, the dataset, the configuration, the environment and the `capabilities_used` of the run, and when all the capabilities materially necessary to this conclusion are effectively gating.

This local authority covers the tested local behavioural contract. It creates no TradingView status, replaces no required TradingView observation and never allows extrapolating a general compatibility of PineTS with TradingView.

#### 24.4.2 Backend

The durable integration uses a local Node thin adapter around a direct dependency on PineTS.

The PineTS version must be pinned exactly.

Forbid floating ranges such as:

```text
^X.Y.Z
~X.Y.Z
latest
*
```

The lockfile must be versioned.

No auto-upgrade of PineTS is allowed.

A PineTS upgrade constitutes an explicit maintenance operation. It invalidates the freshness of the calibrations tied to the previous environment identity and requires a recalibration before an affected capability can again produce an effectively gating conclusion.

`pinets-cli` may be used occasionally for a proof of concept or a diagnostic, but is not the canonical durable backend of the workspace, except by a later explicit decision of the holder.

#### 24.4.3 Executor fingerprint

Each behavioural execution environment has an `executor_fingerprint` representing all the local artefacts likely to influence the normalized result.

The fingerprint must cover at least, when they exist or influence the behaviour:

- `runner.mjs`;
- `normalize.mjs`;
- `package.json`;
- `package-lock.json`;
- the behavioural configuration of the runner that does not belong to the run's own configuration;
- any local auxiliary module loaded by the executor and likely to modify the execution or the normalization;
- exact Node.js version;
- platform and architecture;
- relevant Node.js options;
- relevant, non-secret environment variables;
- timezone and locale, either explicitly controlled or recorded when they can influence the execution or the normalization.

The exact computation must be deterministic and reproducible. An acceptable implementation consists in producing a canonical manifest `relative path → SHA-256` of the elements concerned, integrating into it the relevant environment facts and executor parameters in canonical form, then computing the SHA-256 of this manifest.

Do not blindly fingerprint the whole environment. Include only the facts likely to influence the execution or the normalization, without ever recording a secret value. These facts remain absorbed by `executor_fingerprint`: they do not create a fourth dimension competing with the ratified triplet.

`executor_fingerprint` does not replace `source_sha256`, `dataset_sha256` or the run's own `configuration`. These identities remain separate.

#### 24.4.4 Capability gate, granularity and calibration freshness

The workspace never assumes that every feature announced by PineTS is sufficiently compatible to become gating.

The status is assigned to capabilities fine-grained enough to represent the behaviour actually tested. Do not classify an entire family such as `MTF`, `request.*`, `strategy.*`, historical/realtime, inputs or objects as `GATING`, `EXPERIMENTAL` or `UNSUPPORTED` when its sub-capabilities can have different compatibility profiles.

No family of Pine features is durably condemned to remain `EXPERIMENTAL` or `UNSUPPORTED`, nor promoted to `GATING`, by its category alone. The statuses must be able to evolve capability by capability when the calibration and the real evidence justify it.

A newly encountered capability without sufficient qualification may be recorded provisionally as `EXPERIMENTAL` with `calibration_status = MISSING`. This provisional status means only "no established gating authority"; it does not constitute evidence that the capability is incorrect. `UNSUPPORTED` requires a demonstrable reason, for example a functional absence, a reproducible divergence or a current inability to execute the contract with sufficient fidelity.

Two independent dimensions are kept for each capability:

```text
capability_status
calibration_status
```

`capability_status` accepts only:

```text
GATING
EXPERIMENTAL
UNSUPPORTED
```

`calibration_status` accepts at least:

```text
CURRENT
STALE
MISSING
```

`capability_status = GATING` means that this capability is authorized to produce gating conclusions when a current independent calibration exists for the exact environment.

A change of environment does not automatically turn `GATING` into `EXPERIMENTAL` or `UNSUPPORTED`.

The ability to actually block is derived:

```text
effective_gating =
    capability_status == GATING
    AND calibration_status == CURRENT
```

For `EXPERIMENTAL` or `UNSUPPORTED`, `effective_gating` is always false.

The identity of the calibrated environment is determined by the exact triplet:

```text
pinets_version
+
executor_fingerprint
+
normalization_schema
```

Any modification of one of these three elements results in `calibration_status = STALE` for the calibrations that relied on the previous identity.

The environment identity is not the only cause of obsolescence. The freshness of each capability also depends on the identity and integrity of its cases, inputs, expected results, independent references and any evidence according to §24.4.5.

During a recalibration, `capability_status` may be revised if the compatibility evidence justifies it; it is never rewritten automatically only because the environment has changed.

A `GATING` capability can become effectively gating again only after a successful recalibration against the current environment identity.

#### 24.4.5 Calibration

The folder:

```text
tools/pine_exec/calibration/
```

must contain a durable calibration state making it possible to identify at least:

- exact PineTS version;
- `executor_fingerprint`;
- identity of the normalization schema;
- calibration date;
- capabilities examined;
- `capability_status` of each capability;
- `calibration_status` of each capability;
- cases used;
- hashes or canonical identities of the cases and inputs;
- hashes or canonical identities of the expected results;
- provenance of the independent reference;
- hash and durable reference of the independent reference;
- reference and hash of any TradingView evidence used to support the claim;
- known divergences;
- known limitations.

A `GATING` capability requires an independent calibration with:

- the exact installed PineTS version;
- the exact `executor_fingerprint`;
- the exact normalization schema;
- representative cases;
- an expected reference independent of PineTS.

A calibration reference can come, in particular:

- from a properly established TradingView observation;
- from an independent computation whose result can be determined without using PineTS as an oracle.

The reference must correspond to the type of claim that the capability is authorized to produce. A capability intended only to establish a local mathematical or behavioural contract may be calibrated against an appropriate independent reference. A capability used to support a claim of correspondence with a behaviour specific to TradingView must be calibrated against a TradingView observation that is sufficiently conclusive for this precise claim.

A previous PineTS output is never sufficient, on its own, to calibrate PineTS.

A `STALE` or `MISSING` calibration does not change the `capability_status`, but forbids any effectively gating use of this capability.

A calibration becomes `STALE`, capability by capability, in particular when:

- a calibration case or input changes;
- an expected result changes;
- an independent reference or a required piece of evidence disappears, changes or no longer passes its integrity check;
- a new reproducible divergence contradicts the previously calibrated contract;
- a relevant change in the official documentation makes the calibration contract invalid.

The age of a calibration alone is not evidence of staleness. Do not apply an arbitrary TTL.

The calibration must not become a second Pine Script standard.

It describes only what this precise version of PineTS, with this executor and this normalization schema, is authorized to prove locally.

#### 24.4.6 Identity and capabilities of a run

Any behavioural result used for a comparison or a conclusion must be linked at least to:

```text
source_sha256
dataset_sha256
dataset_descriptor
pinets_version
executor_fingerprint
normalization_schema
configuration
capabilities_used
run_id
timestamp
```

`dataset_descriptor` describes the provenance and the semantics needed to interpret the dataset without replacing its hash. It distinguishes at least a synthetic dataset from an imported snapshot and records, depending on applicability:

- dataset type;
- generator and parameters when synthetic;
- source or provenance when imported;
- symbol, timeframe and time range;
- timezone, session or other relevant time semantics;
- acquisition/export date or reference when useful;
- licence or usage-right information needed when the source is external.

`timestamp` uses RFC 3339 in UTC. `run_id` is collision-resistant and does not depend on a local date alone.

`capabilities_used` must record the PineTS capabilities actually exercised by the behaviour or the conclusion concerned, as well as their state at the time of the run.

A valid representation is, for example:

```json
{
  "capabilities_used": {
    "series-history": {
      "capability_status": "GATING",
      "calibration_status": "CURRENT"
    },
    "ta-ema": {
      "capability_status": "GATING",
      "calibration_status": "CURRENT"
    },
    "request-security-udf": {
      "capability_status": "EXPERIMENTAL",
      "calibration_status": "CURRENT"
    }
  }
}
```

`effective_gating` is derived from the two statuses and must not be persisted as a third source of truth when it can be recomputed without ambiguity.

A run can execute successfully while using one or more capabilities that are not effectively gating.

In this case, `PINETS_EXECUTION_PASS` remains valid, but no behavioural conclusion that materially depends on a capability that is not effectively gating may be used as a gate.

When a conclusion can be isolated to a subset of capabilities that are all effectively gating, only this precisely bounded conclusion may be gating.

If the `capabilities_used` cannot be determined with sufficient confidence for the conclusion concerned, this conclusion is `PINETS_INCONCLUSIVE` or otherwise non-gating; detection uncertainty must never be turned into evidence.

When the dataset is generated synthetically, its definition must be deterministic and make it possible to reproduce exactly the same OHLCV.

An OHLCV snapshot imported from an independent source may also be used when it is kept or reconstructible in a sufficiently reliable way, its `dataset_sha256` is stable, its provenance is recorded and its terms of use allow the intended use.

The bootstrap must not integrate a network data provider by default, nor create a new market data platform. It must only allow the thin adapter to consume controlled local datasets according to a documented contract.

The PineTS layer must not automate the extraction of TradingView data, content or states for the sole purpose of feeding the local runtime, except by a later decision explicitly ratified after analysis of the current terms applicable to this precise use.

#### 24.4.7 Statuses: execution and behavioural observations

Execution statuses and behavioural observations are two distinct axes.

The execution status describes only the ability of the PineTS runtime to execute the source in the environment concerned:

```text
PINETS_EXECUTION_PASS
PINETS_EXECUTION_FAIL
```

Behavioural observations describe what was observed after or during a usable execution:

```text
PINETS_REGRESSION_UNCHANGED
PINETS_REGRESSION_CHANGED

PINETS_STABILITY_NO_ANOMALY
PINETS_STABILITY_ANOMALY
```

The evidence qualification statuses include:

```text
PINETS_EXPERIMENTAL
PINETS_UNSUPPORTED
PINETS_INCONCLUSIVE
```

The axes must never be merged.

The following combination is perfectly valid:

```text
PINETS_EXECUTION_PASS
+
PINETS_REGRESSION_CHANGED
```

It means that the runtime executed the source and that a behavioural change was observed. It does not mean an execution failure.

`PINETS_EXECUTION_PASS` means only that the source executed successfully in the PineTS environment concerned.

It never means `TV_VALIDATED`.

`PINETS_EXECUTION_FAIL` can become a blocking failure of the local workflow only if:

1. the capabilities materially necessary to interpret this failure are effectively gating;
2. their calibration is `CURRENT`;
3. the failure is attributable to the behaviour of the source or to an explicit test contract;
4. no known PineTS divergence makes the interpretation uncertain.

Otherwise, use an appropriate non-gating status.

`PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` and `PINETS_INCONCLUSIVE` are never equated with a failure of the script.

They mean that the local layer cannot provide sufficient evidence on this point.

The workflow may then proceed to TradingView.

#### 24.4.8 Fix boundary

Claude Code never modifies the Pine source only to get the code accepted by PineTS.

Before any fix triggered by a PineTS result, ask the question:

> Would the code be incorrect or contrary to the objective, the standard, the current Pine documentation or the expected behavioural contract if PineTS did not exist?

If the answer is no or cannot be determined, do not modify the Pine only to satisfy PineTS.

Qualify the result as a limitation, divergence, experimental, unsupported or inconclusive, as the case may be.

#### 24.4.9 Regressions

A behavioural difference is not automatically a bug.

`PINETS_REGRESSION_CHANGED` means only that a difference was observed between two comparable executions.

Any difference must be checked against:

- the objective requested by the holder;
- the impact inventory;
- the behaviours announced as having to remain unchanged;
- the behaviours explicitly intended to change.

Classify the difference as:

```text
EXPECTED
UNEXPECTED
UNRESOLVED
```

`EXPECTED` is not a failure.

`UNRESOLVED` must not produce a speculative fix.

`UNEXPECTED` may block the local cycle only when the conclusion concerned depends exclusively on effectively gating capabilities and rests on a valid regression contract.

#### 24.4.10 Accepted behavioral baseline

A durable baseline carries the status:

```text
ACCEPTED_BEHAVIORAL_BASELINE
```

A first PineTS execution is never automatically an accepted baseline.

Any `ACCEPTED_BEHAVIORAL_BASELINE` must be linked at least to:

```text
source_sha256
dataset_sha256
dataset_descriptor
normalized_payload_sha256
pinets_version
executor_fingerprint
normalization_schema
configuration
capabilities_used
acceptance_basis
accepted_at
acceptance_evidence_ref
acceptance_rationale
```

The baseline must ideally come from a source whose same SHA has already passed the relevant TradingView validation.

Failing that, it may be promoted as `ACCEPTED_BEHAVIORAL_BASELINE` only by an explicit decision of the holder with a recorded justification.

`acceptance_basis` must make it possible to distinguish in particular:

```text
TRADINGVIEW_VALIDATED_SOURCE
RICK_EXPLICIT_ACCEPTANCE
```

`normalized_payload_sha256` is required when the normalized payload is separate from its descriptor. For `TRADINGVIEW_VALIDATED_SOURCE`, `acceptance_evidence_ref` must reference the durable evidence of the same SHA when it is the basis of the acceptance. For `RICK_EXPLICIT_ACCEPTANCE`, `acceptance_rationale` must explain the decision; the non-applicable fields may be `null`, but their presence and their semantics remain normative.

An accepted baseline means:

> this behaviour is accepted as a non-regression reference for this precise context.

It does not mean:

> PineTS has proven that this output is universally correct.

A baseline remains a valid historical artefact when the environment evolves, but it can no longer directly support a gating comparison if its `pinets_version`, its `executor_fingerprint`, its `normalization_schema`, its dataset or its configuration do not match the comparison context.

In this case, the reference source must be re-executed in the current environment, or the baseline must be regenerated and then accepted according to the contract above.

No baseline is migrated automatically.

#### 24.4.11 Persistence

The durable artefacts specific to a product reside exclusively under:

```text
scripts/<slug>/tests/behavioral/
```

They must never be written under:

```text
scripts/<slug>/validation/
```

Temporary execution outputs belong to a gitignored runtime space.

Do not automatically keep every run.

Promote an output to a durable artefact only if it has a real usefulness for regression, reproducing a bug, calibration or understanding the product.

#### 24.4.12 Proportionality and explicit matrices

`pine-local-test` does not impose a heavy matrix for every fix.

The depth depends on:

- the nature of the modification;
- the affected modules;
- the identified risks;
- the existing baselines;
- the available capabilities;
- the reasonable cost of the test.

A small fix can justify a simple smoke run.

A refactoring meant to be semantically neutral can justify an in-depth regression comparison.

An MTF, historical, realtime or strategy modification can call for more targeted tests, but only within the limits of the effectively gating capabilities or as an explicitly experimental/non-gating observation.

When a real need justifies it, an explicit workflow may run a bounded matrix comprising in particular several datasets, symbols, timeframes, configurations or input values. A local parameter sweep is therefore allowed as an exploration, diagnostic or regression technique when the runtime and the capabilities concerned allow it.

Each elementary execution of the matrix keeps its own run identity. The matrix itself must have a deterministic manifest describing the executed combinations, so that an aggregated result can be traced back to the runs that compose it.

A ranking of configurations, an apparent optimum or a best metric observed locally never constitutes on its own a proof of signal quality, out-of-sample robustness, TradingView performance or product superiority. Any decision to modify the product's parameters remains an explicit product decision or a justified consequence of an already ratified objective.

The bootstrap does not build a generic optimizer, a backtesting platform or a market data engine. Matrices are a bounded capability of `pine-local-test`, triggered only by an explicit workflow. No hook of the foundation automatically launches a matrix of datasets, parameters or stability probes.

#### 24.4.13 Licence, data, terms of use and distribution

PineTS remains a third-party dependency independent of the holder's Pine source.

Before the initial installation and any upgrade:

- check the current upstream licence of PineTS;
- keep the required notices and licence files;
- do not assume that the licence terms will remain identical over time.

Record the licence basis actually used, without artificially summarizing it as "dual licence":

```text
license_basis = AGPL-3.0-only
```

or, only if the holder actually holds an applicable separate commercial licence:

```text
license_basis = separate-commercial-license
license_evidence = <appropriate, non-secret local reference>
```

The existence of an upstream commercial licence offer does not prove that such a licence is held. The provenance report must record the exact version, the integrity of the installed artefact, its licence metadata and the lockfile. This provenance contract does not replace a legal analysis.

The applicable rights and terms must be assessed according to the resource actually used:

1. PineTS licence and terms for the runtime and its integration;
2. licence, contract or terms of the data source for any external dataset;
3. TradingView terms for any interaction, automation, extraction, content or data actually coming from TradingView services.

Do not reflexively extend a restriction specific to an external service to every independent local execution; conversely, do not assume that a local execution frees content or data coming from a service subject to its own terms.

The integration ratified here targets a local/internal use of the workspace. No external data provider is imposed or configured by default by the bootstrap.

If the thin adapter, PineTS or a derived application is to be distributed to third parties, integrated into a distributed product or exposed as a network service, stop the operation and carry out a new analysis of the licence and of the applicable terms of use before continuing.

Holder's decision of 2026-11-13, after the analysis required above for public distribution: the thin adapter (`tools/pine_exec/runner.mjs`, `normalize.mjs`, `datasets.mjs`, `fingerprint.mjs` and the metadata of its package) is distributed under **AGPL-3.0-only** (official text in `tools/pine_exec/LICENSE`, SPDX identifier and notice in each file); the rest of the core remains under Apache-2.0; PineTS is never shipped. Observed architecture: the adapter loads PineTS in its own Node process; the Apache-2.0 core never loads PineTS: its Python tooling launches the adapter's programs as separate processes and exchanges files and JSON, and its tests contain short JavaScript programs that import modules of the adapter (never PineTS directly). This decision sets the licence of the Pine Workspace code; it does not legally settle the boundary between the components. Any other form (PineTS or an embedded derivative, modified PineTS, integration of the engine into a distributed product, network service) remains subject to the stop and to a new analysis.

---

## 25. SKILL `pine-research`

### 25.1 Mission

Produce current, traceable research that is useful to the script.

### 25.2 Priority sources

For Pine facts:

- official TradingView/Pine Script documentation;
- official release notes;
- official publication rules when relevant.

For the benchmark:

- relevant public open-source scripts;
- relevant Editors’ Picks;
- other high-quality open-source references.

### 25.3 Reuse

The benchmark does not authorize code reuse.

Strictly apply the benchmark/reuse boundary of the master standard.

### 25.4 Persistence

Do not write a research run for trivial research.

When a result deserves to be reused:

```text
scripts/<slug>/research/runs/<timestamp>-<topic>.md
```

Then update:

```text
research/CURRENT.md
```

with a routing summary.

When a researcher agent is invoked, the parent persists its report as a research run upon receipt, with the consultation date and the provenance. A run written after the fact carries the initial research date, the reconstruction date and the provenance, without an invented time; its freshness remains that of its initial date as long as no dated re-verification is made. Research that was not carried out is never dated.

### 25.5 Freshness

No arbitrary universal TTL.

Freshness depends on:

- the subject;
- its volatility;
- the date;
- the risk of change;
- the release phase.

Any TradingView publication rule must be re-verified immediately before a real release, regardless of how old a previous run is.

---

## 26. SKILL `pine-review`

### 26.1 Mission

Implement the four review axes of the master standard.

Trigger: requested deep audit (`pine-audit`), publication preparation (`pine-release`) or explicit request from the holder; never chained automatically after a creation or a modification, whatever the class of the task; a single review per unit of work, without a cascade of counter-reviews (master §9.1, §36; amendment of 2026-11-13).

### 26.2 Execution

Delegate the independent perspective to the `pws-pine-reviewer` subagent.

The reviewer:

- does not modify the code;
- has no persistent memory;
- receives the request, the source, the necessary context and the useful diff;
- receives the expected coverage (targeted, extended, global) and returns the coverage actually read;
- does not needlessly receive the developer's whole conversation.

### 26.3 Output

Structured feedback:

- problem;
- impact;
- location;
- justification;
- rule or objective concerned;
- confidence level.

The parent decides on the fixes and implements them.

---

## 27. SKILL `pine-release`

### 27.1 Mission

Prepare a release, not publish implicitly.

### 27.2 Steps

Depending on applicability:

- determine the SemVer impact;
- check the version in the source header;
- prepare the changelog;
- prepare the release notes;
- prepare the tutorial if required;
- prepare the initial description if it is a new publication;
- check the dependent documentation;
- note the state of the licences and terms of use (`license status`; the information is completed through the `pine-license` guided path, independent of this skill): a missing piece of information is flagged and blocks only the finalization concerned, never completed by invention;
- revalidate the current TradingView rules;
- run the applicable PineTS behavioural tests when effectively gating capabilities or relevant `ACCEPTED_BEHAVIORAL_BASELINE` exist;
- qualify and resolve any `UNEXPECTED` local regression that is actually gating before the final TradingView validation;
- run `pws-release-reviewer`;
- check the TradingView validation of the final hash;
- prepare the publication artefacts;
- for any `invite-only` publication, prepare and check the `Author's instructions` content required by the current TradingView rules.

### 27.3 Gate

A release cannot be declared ready if the final source has not passed the required TradingView validation.

A `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` or `PINETS_INCONCLUSIVE` status does not on its own prevent a release from proceeding to TradingView.

The final release gate remains the TradingView validation of the final source.

### 27.4 Publication

The skill does not automatically finalize a public publication.

---

## 28. SKILL `tv-mode`

### 28.1 Invocation

This skill is reserved for the holder.

Use the current frontmatter that makes it possible to prevent automatic invocation, for example:

```yaml
disable-model-invocation: true
```

if this field still exists.

### 28.2 Commands

Support:

```text
/tv-mode manual
/tv-mode chrome-experimental
```

### 28.3 Effect

The skill calls the shared deterministic controller:

```text
python -m tools.pws_workspace tv-mode <mode>
```

or its equivalent final form validated by the bootstrap. This controller is the sole owner of the mutation and modifies only:

```text
tv_validation_mode
```

in `pws.config.json` (§19A). Claude Code settings are never touched.

Preserve all the other existing keys.

Apply the atomic contract of §19A (serialization guaranteed between workspace writers by the configuration lock; refusal of detected concurrent modifications).

### 28.4 Prohibition

Claude never changes the persistent mode on its own initiative.

`disable-model-invocation: true` forbids Claude from calling the `/tv-mode` skill. When the holder explicitly chooses the TradingView mode in `/pws` (Maintenance / configuration → Configuration → TradingView mode), the facade therefore does not attempt `Skill(tv-mode)`: it passes this user choice to the same shared deterministic controller. This explicit route gives no authorization for a spontaneous change outside this choice.

---

## 29. SKILL `tv-validate`

### 29.1 Source of the mode

Read the mode through the controller (`python3 -m tools.pws_workspace tv-mode`, configuration `pws.config.json`; source `config`, `legacy` or `default`) — never the process variable:

```text
tv_validation_mode
```

### 29.2 Matrix

The validation matrix is derived from:

- the master standard;
- the script type;
- the product context;
- the actual change.

It is never a fixed checklist imposing N/A tests.

### 29.3 Source identity

Before any run:

1. compute the SHA-256 of the `.pine`;
2. capture the current Git commit if it exists;
3. capture the dirty/clean state;
4. generate a `run_id`.

The central evidence is the hash of the source.

### 29.4 After a modification

Any modification of the `.pine` after a run invalidates the ability of this run to prove the new source.

The last run remains historical.

The effective state becomes `STALE`.

### 29.5 PineTS boundary

`tv-validate` never consumes a PineTS result as a substitute for a TradingView observation.

An effectively gating PineTS conclusion may block the local cycle before `tv-validate` when it demonstrates the violation of a valid local behavioural contract. This local block must be resolved, explained or requalified before proceeding as if the test had passed; it does not, however, create any TradingView status.

The results of `pine-local-test` can:

- help prepare the validation matrix;
- target a scenario to reproduce;
- explain an anomaly;
- identify a risk to check.

They cannot:

- satisfy a TradingView step;
- create TradingView evidence;
- directly modify the TradingView status;
- turn a validation whose effective state is `stale`, or whose persisted state is `unverified` / `in-progress`, into `passed`.

When a TradingView validation is required by the workflow, it remains mandatory on the exact source concerned, regardless of the PineTS result.

---

## 30. TRADINGVIEW MODE `manual`

### 30.1 Status

Default mode.

### 30.2 Operation

Claude:

1. completes the local checks;
2. builds a specific test matrix;
3. gives the holder precise steps;
4. waits for the real observations;
5. records the results;
6. persists `passed` only when all the applicable mandatory checks have actually succeeded.

### 30.3 Possible tests depending on applicability

- Pine Editor compilation;
- runtime;
- historical;
- realtime;
- Replay;
- MTF;
- symbol change;
- timeframe change;
- extreme settings;
- dark theme;
- light theme;
- labels/tables/boxes/lines/fills;
- alerts;
- strategy/report if strategy script;
- performance/Profiler when relevant.

Do not mechanically run a test that has no purpose.

### 30.4 Evidence

Keep only the useful evidence.

A precise report from the holder can constitute a real observation.

A screenshot is useful when it proves a visual state or an error, but must not become an artificial obligation for each test.

A report from the holder may cover a group of checks when the exact list of the group's checks has been presented to the holder before their confirmation. The run keeps this list, the text presented and the confirmation received. The confirmation does not extend to any unlisted check and does not authorize any unreported measurement or value.

### 30.5 Minimal compilation and functional campaign

The minimal compilation is the observation, in the Pine Editor, of the compilation result of the exact source identified by its SHA-256: errors and warnings, reported separately. It does not cover any behaviour. The functional campaign is the execution of the applicable behavioural checks of the matrix; it may be grouped on the stabilized source of a series of modifications.

An intermediate minimal compilation is requested when the impact inventory identifies a cross-cutting transformation presenting a typing, history-depth or compiled-size risk. It is recorded with the risk that justifies it. It is requested neither after each micro-edit nor after a local fix without this risk. No compiled-size margin is deduced without a reported measurement.

A successful minimal compilation does not count as validation: the run that records it lists the applicable behavioural checks as `not-run` and cannot be `passed`. The absence of an error does not prove the absence of a warning.

The run records errors and warnings separately. For each, it states explicitly whether an observation was reported; an absence of observation is recorded as such, never deduced. The results of the behavioural checks are not invented.

Recording and promotion are distinct. A valid report is always kept as an immutable run. Without a recognized current run, its initial promotion follows the normal protocol. On the same SHA as the recognized current run, a minimal compilation that is not `failed` does not replace that run; a `failed` minimal compilation may replace it, with explicit flagging of a contradiction if that run was `passed`. On another SHA, the promotion follows the normal protocol and freshness remains computed against the declared source. None of these rules bypasses the protections of §51.4. A failure not promoted because of a conflict remains kept and clearly flagged.

The grouping of the functional campaign and the frequency of requests fall under the organization decided by the holder for each product and are recorded in its decisions. Such a decision does not extend to other products.

---

## 31. TRADINGVIEW MODE `chrome-experimental`

### 31.1 Status

Experimental and optional.

### 31.2 Preflight

Before the run, check the capabilities actually available:

- Claude Code version;
- compatible Chrome/Chromium;
- compatible extension;
- compatible Claude authentication;
- browser tools present;
- TradingView login already established or possibility for the holder to complete it;
- current platform restrictions.

As of the date of this specification, the Claude Code documentation states in particular that the Chrome integration shares the browser's authenticated session, stops at login/CAPTCHA and is not supported under WSL.

Always re-verify the current documentation.

### 31.3 Activation

Do not enable Chrome globally if it is not necessary.

The browser integration increases the context when its tools are loaded.

Use `--chrome` only for the sessions/runs that need it, unless the holder decides otherwise.

### 31.4 Execution

The experimental mode attempts to run the same matrix as the manual mode.

Before any mutation of the Pine Editor, apply a pre-write gate. It must establish with sufficient confidence:

1. the expected Chrome window;
2. the target TradingView tab and its domain;
3. the identity of the open editor;
4. the identity of the active script or buffer;
5. the possible presence of unsaved foreign modifications;
6. the correspondence between this buffer and the expected local product/source.

If an identity remains ambiguous:

```text
NO WRITE
→ fallback manual / human action
```

After any write, re-observe the buffer and the target context. A successful click or command proves neither that the right script was modified nor that the expected content is present.

It may, when technically reliable:

- open TradingView;
- open Pine Editor;
- enter/update the source;
- save;
- compile;
- add to chart;
- change symbol/timeframe;
- manipulate settings;
- observe the runtime;
- inspect console/DOM if useful;
- take useful screenshots.

### 31.5 Boundary

Do not confuse the ability to click with the ability to prove.

If Claude cannot establish in a sufficiently reliable way that a step has succeeded, this step is not `passed`.

### 31.6 Fallback

Trigger the manual fallback in particular if:

- login required;
- CAPTCHA;
- extension not connected;
- Pine Editor inaccessible;
- different UI;
- ambiguous result;
- failed browser action;
- uncertain visual check;
- necessary element impossible to automate;
- step requiring human judgement;
- risk of a publication action.

The run records:

```text
requested_mode = chrome-experimental
effective_mode = manual
fallback_reason = ...
```

The persistent mode remains unchanged.

### 31.7 Screenshots

Save a screenshot to disk only when it constitutes useful evidence.

Validation screenshots belong in the `validation/evidence/` folder of the run concerned.

### 31.8 Publication excluded

`chrome-experimental` stops before any public publication or commercial modification.

### 31.9 Controlled operational learning

`chrome-experimental` must be able to progressively capitalize on the operational knowledge actually useful to TradingView validation, without introducing any autonomous learning model, opaque memory, new authority or new architecture layer.

The objective is to reduce repetitive explorations, to improve the reliability of interactions and to better recognize ambiguous or obsolete states, while keeping the same evidence requirement for each real run.

#### 31.9.1 Admissible knowledge

The following may in particular become operational learnings:

- TradingView workflows actually observed and reusable;
- reliable semantic UI landmarks;
- robust means of establishing that Pine Editor is actually open and usable;
- expected visual states after a known action;
- reliable signs of success or failure;
- known dialogs, transitions and intermediate states;
- ambiguities already encountered;
- reproducible causes of manual fallback;
- differences observed after a change in the UI;
- evidence methods that improve the quality of a run without lowering its validation threshold.

Do not confuse operational learning with statistical learning or machine learning.

#### 31.9.2 Preference for robust reference points

When a workflow can be described in several ways, prefer, in general order:

```text
observable semantic state
> accessible role / label
> stable structural relation in the UI
> stable DOM relation
> fragile selector
> absolute pixel coordinate
```

Fragile selectors and absolute coordinates must be kept only as a last resort clearly identified as such.

#### 31.9.3 Promotion of a learning

A one-off observation does not automatically become durable knowledge.

Before promotion, check to a proportionate depth that the observation:

1. comes from a real run or a real TradingView check;
2. is reusable beyond the one-off case that revealed it;
3. is sufficiently established by repetition, corroboration, current documentation or clear reproduction of the behaviour;
4. does not turn an accidental detail of the UI into an invariant;
5. does not turn a result specific to one script into a general TradingView rule;
6. actually improves navigation, observation, ambiguity detection or evidence quality.

Do not impose a fixed number of repetitions when an observation can be established otherwise in a sufficiently reliable way.

#### 31.9.4 Persistence

The versioned guide:

```text
.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md
```

is the durable place for the explicitly promoted operational knowledge of this mode.

It must clearly distinguish:

- the stable instructions of the mode;
- the actually qualified workflows or landmarks;
- the known limits and failure modes;
- the elements that are fragile or likely to become stale.

The Claude Code auto-memory may serve as a temporary staging area for candidate observations, but never replaces this deliberate promotion when knowledge must be reused durably.

Run-specific evidence remains in the intended validation system; it must not be copied into `CHROME_EXPERIMENTAL.md` as general truths.

#### 31.9.5 Knowledge / evidence boundary

A piece of learned knowledge describes how to observe or navigate better. It never proves that the current state still corresponds to what was learned.

In particular:

```text
known workflow
≠ successful current step

known landmark
≠ automatic evidence

historical absence of ambiguity
≠ current absence of ambiguity
```

Each run must re-observe the state actually present.

Learning must never lower the evidence threshold of §31.5, nor convert an assumption based on history into `passed`.

#### 31.9.6 Obsolescence detection and revision

The mode must be capable of recognizing that a learned workflow or landmark no longer corresponds to the current UI.

When a learning becomes contradictory, absent, ambiguous or clearly obsolete:

1. do not force the old workflow;
2. consider the knowledge concerned as unreliable for the current run;
3. carefully explore the current state or trigger the manual fallback according to §31.6;
4. correct, qualify as fragile or remove the durable knowledge that has become false when a sufficiently established new observation justifies it.

A change in TradingView, Chrome, Claude Code or the browser integration can justify this reassessment without a version change on its own being automatically equated with evidence of obsolescence.

#### 31.9.7 Forbidden content

Never promote into the durable operational knowledge:

- password;
- cookie;
- token;
- credential or authentication secret;
- product decision by the holder that belongs to another artefact;
- result of a specific validation presented as a general rule;
- proprietary content of a script kept only to learn the UI;
- screenshot or other run evidence when it has no distinct durable function;
- fragile coordinates or selectors presented as reliable invariants.

#### 31.9.8 No new layer

This learning remains an internal capability of the `chrome-experimental` mode and of the `tv-validate` skill.

It does not justify the creation of a database, registry, new memory folder, new server, MCP, agent, skill, dashboard or other parallel platform.

The initial bootstrap must build the mechanism and the promotion rules in `CHROME_EXPERIMENTAL.md`, but must not invent any landmark, workflow or failure mode presented as observed if it has not actually been verified.

---

## 32. SKILL `project-doctor`

### 32.1 Two layers

The doctor has:

1. a deterministic layer;
2. an optional semantic layer for configuration consistency.

### 32.2 Deterministic checks

At a minimum:

- master standard present;
- current index hash;
- current traceability hash;
- valid JSON;
- valid manifests;
- manifest source present;
- consistent product root;
- normative conformity of `SCRIPT.json`, including `schema_version` (3; 2 and 1 read and flagged for migration), unknown fields, `id == slug`, case-insensitive uniqueness, consistency of the licence axes (§45.4) and confinement of the source path;
- personal configuration (`pws.config.json`): presence (absence = INFO, defaults), validity, workspace version, configured identity; legacy key of the TradingView mode flagged;
- identity of the installed PineTS executor: pin, lockfile, registry integrity, SHA of the installed artefact recorded in `PROVENANCE.json`, fingerprint;
- Git missing or folder not initialized: degraded mode flagged (WARNING), never an exception;
- orphan `.pine` files;
- partial contexts;
- missing source;
- ambiguous additional source;
- readable local settings;
- valid TV mode;
- stale effective validation;
- integrity of `validation/current.json`, of its referenced run and of the evidence hashes;
- baseline references, dataset descriptors and durable behavioural hashes;
- executable hooks;
- tooling tests;
- Git available;
- remotes present;
- worktree config;
- `.claude/worktrees/` actually ignored by Git;
- absence of a path or symlink leading out of the physical workspace;
- absence of a configuration or contract requiring the existence, the name, the path or the state of another external project;
- known placeholder folders/files;
- presence and readability of the PineTS thin adapter when it is configured;
- PineTS dependency pinned to an exact version;
- `package.json` / lockfile consistency;
- absence of a floating range for PineTS;
- consistency between `pinets_version`, `executor_fingerprint`, `normalization_schema` and the calibration state;
- consistency of the identities of the cases, inputs, expected results, references and evidence that support the freshness of the calibrations;
- absence of a capability used as effectively gating when its calibration is not `CURRENT`;
- absence of a PineTS integration in the form of a server, MCP, database or persistent service not ratified;
- effective resolution of the critical skills to the expected project skills, with an explicit diagnostic of any collision;
- provenance of the installed PineTS version and `license_basis` actually recorded.

`project-doctor` does not automatically run the heavy behavioural matrices.

It checks the integrity and the freshness of the PineTS layer.

A `STALE` or `MISSING` calibration only forbids using the capabilities concerned as effectively gating.

It does not automatically classify the Pine source as `BROKEN` and does not replace the TradingView validation.

### 32.3 Semantic check

When an evolution of the architecture has taken place, check:

- duplications of instructions;
- responsibilities that have become competing;
- files with no use;
- inconsistencies between contracts and implementation.

### 32.4 Output

Concise statuses with severity:

```text
OK
INFO
WARNING
BLOCKING
```

A `BLOCKING` must be actionable.

---

## 33. SUBAGENT `pws-pine-cartographer`

### 33.1 Tools

Read-only.

### 33.2 Memory

No persistent memory.

### 33.3 Role

Read a large script without saturating the main context.

Produce:

- structural map;
- dependencies;
- state;
- requests;
- MTF;
- rendering;
- alerts;
- hotspots;
- risks;
- important consumers.

### 33.4 Prohibition

Do not modify the code.

Do not invent a product intention.

---

## 34. SUBAGENT `pws-pine-researcher`

### 34.1 Tools

Local reading + web/search depending on the available capabilities.

No direct writing to the project, except for a necessity explicitly decided by the final architecture.

The preferred mode is to return the result to the parent, which persists what deserves to be persisted.

### 34.2 Memory

No persistent memory.

### 34.3 Role

Check:

- official documentation;
- current Pine behaviour;
- relevant benchmark;
- TradingView rules when they are concerned.

### 34.4 Output

Separate:

- official facts;
- benchmark observation;
- inference;
- recommendation.

---

## 35. SUBAGENT `pws-pine-reviewer`

### 35.1 Context

Non-fork subagent when the current version of Claude Code thereby allows a suitable fresh context.

### 35.2 Memory

None.

### 35.3 Role

Be a genuinely fresh perspective.

The reviewer is invoked only in the cases of §26.1. It re-reads according to the coverage indicated in the mission (targeted, extended or global, master §9.2) and the product context actually necessary; without an indication, the complete source.

The diff may serve as a point of attention; it does not define the coverage.

### 35.4 Tools

Read-only.

### 35.5 Prohibition

Do not directly apply its own fixes.

The parent keeps the implementation responsibility.

---

## 36. SUBAGENT `pws-release-reviewer`

### 36.1 Tools

Reading + web.

### 36.2 Memory

None.

### 36.3 Role

Just before release:

- check the current TradingView rules;
- check the requirements specific to the script type;
- check the consistency of the artefacts;
- look for divergences between the final source, the docs and the publication;
- flag any unverified point.

---

## 37. LOCAL DETERMINISTIC TOOL

Create a small local package, without any ambition of reproducing TradingView.

Conceptual command:

```text
python -m tools.pws_workspace <subcommand>
```

The bootstrap must adapt the launcher to the actual runtime detected.

Do not add an external dependency when a standard library suffices.

### 37.1 Minimal subcommands

Provide functions equivalent to:

```text
version
session-status
menu
scan
doctor
standard-index
standard-status
guard
source-fingerprint
validation-status
tv-mode
import-register
hook-session-start
hook-stop
init | config show | config set            (pws.config.json — §19A)
migrate --plan | --apply | --rollback      (§55)
tooling-status | pinets <action>           (PineTS: status, verify, check-update, install, rollback, recalibrate-plan)
github <action>                            (status, destinations, destination-add/remove, export-plan, fetch, export-diff, publish — §43.5)
maintenance <action>                       (cleanup, archives-plan/import/verify/remove-source)
license <action>                           (status, render, write, fields-skeleton, templates)
build-distribution --target <dir>          (public distribution — common core, allowlist)
```

The exact name may be adjusted for consistency. `menu` provides the deterministic and localized tree of the PWS menu (applicable entries, ≤ 4 options per screen, action → script path): the `pws` skill renders it without redefining it.

### 37.2 Responsibilities of the package

Only mechanical facts:

- filesystem;
- local Git;
- JSON;
- hash;
- structure;
- simple header;
- mechanically forbidden strings;
- validation state;
- state of the standard.

`session-status` must be able to provide a structured representation usable by the `pws` skill so that the menu derives its choices from mechanical facts already computed instead of reimplementing the workspace scan.

### 37.3 What it does not judge

It is forbidden to claim to determine:

- signal quality;
- relevance of a tooltip;
- actual repaint;
- business correctness;
- good UX;
- originality;
- quality of the benchmark;
- optimal Pine architecture;
- TradingView visual conformity.

---

## 38. LOCAL PINE GUARD

### 38.1 Scope

Only the deterministic checks that are truly reliable.

### 38.2 Candidate checks

Depending on what the bootstrap can implement cleanly:

- existing source;
- `//@version=6` according to the standard;
- absence of `shorttitle`;
- absence of `short_title`;
- header structure matching the distribution model;
- product version in the source header;
- absence of a product version explicitly repeated in the checkable user-facing files;
- title verifiable as ASCII when it can be extracted reliably;
- source/manifest consistency;
- valid contextual JSON;
- manifestly forbidden URLs in the header/source if a reliable mechanical rule exists.

### 38.3 Principle of caution

A deterministic check that produces too many false positives must be reduced or removed.

Do not turn a fragile heuristic into a blocking gate.

---

## 39. TOOLING TESTS

The local package must have real tests.

Prefer `unittest` from the standard library if this avoids a dependency.

The tests must cover in particular:

- detection of a registered script;
- detection of an orphan `.pine`;
- incomplete manifest;
- manifest with an unknown field;
- slug/ID collision differing only by case;
- absolute source, `..` traversal and symlink leading out of the product root;
- type/distribution matrix, in particular rejection of `library + paid-closed-source`;
- missing source;
- several ambiguous sources;
- `shorttitle` detection;
- distinction between an actual `shorttitle` and an occurrence in a comment, a string or documentation;
- legitimate Creative Commons URL and forbidden promotional URL;
- extractable multi-line title and non-extractable title syntax without a false blocking verdict;
- free header;
- paid header;
- source hash;
- stale validation;
- missing/invalid validation run and evidence whose hash diverges;
- atomic update where an older run does not replace a more recent run;
- valid/invalid TV mode;
- stale standard index;
- Stop hook behaviour;
- structured output of `session-status` sufficient to feed the PWS menu without semantic logic;
- read-modify-write of `settings.local.json` preserving approvals, according to the scope of §19.3: serialization between workspace writers and refusal of detectable external modifications;
- workspace and source whose paths contain spaces;
- detection of an enclosing parent repository and of an outgoing symlink;
- operation with an arbitrarily named sibling, present or absent, without any dependency, scan or mutation of its content;
- durable tests of the thin adapter and of the PineTS contracts of §61.10;
- attribution of the Stop hook findings: move without modification, pre-existing anomaly, introduced anomaly, undetermined provenance, line shift, multiple occurrences; consistency of the verdicts of a version 2 report: precedence of `failed`, coverage, unique identifiers, refusal to promote a report of an earlier version; group confirmations; minimal compilation never `passed`, errors and warnings recorded separately, recording without promotion on the same SHA, replacement by a failure with the contradiction flagged, protections of §51.4 never bypassed; import record: import declared then onboarded without modification, modification after import, refusal of re-registration after modification, hash equality without exemption, ambiguous attachment.

Principle of the textual guards:

```text
parser uncertainty
≠ evidence of violation
```

A non-extractable case must produce an honest diagnostic or a complementary verification, not a false `BLOCKING`.

Do not create five test files each containing a trivial test only to satisfy the tree structure.

Real factorization prevails.

---

## 40. HOOK `SessionStart`

### 40.1 Mission

Give Claude a small dynamic state at startup and provide the mechanical facts needed by the PWS contextual menu.

### 40.2 Actions

The hook must:

1. scan `scripts/**`;
2. determine the registration statuses;
3. detect the orphan `.pine` files;
4. check the state of the standard index;
5. check the TV mode;
6. check the Git state;
7. identify the stale validations;
8. create an ephemeral session snapshot of the registered sources;
9. inject a short summary into the context, whose line following the title states the configured language explicitly (amendment of 2026-11-14);
10. make available a structured state small enough for the `pws` skill to be able to build its menu without semantically rescanning the project.

### 40.3 Output example

```text
PWS
Configured language: en — menus, explanations, questions, confirmations and reports in English
Git: local / branch main / dirty
TV validation mode: manual
Registered scripts: 12
Unregistered scripts: 1
Incomplete products: 0
Stale TradingView validations: 2
Master index: current

UNREGISTERED
scripts/new-indicator/New Indicator.pine

Required action before substantive edits: pine-onboard
```

### 40.4 Automatic onboarding

The hook does not claim to invoke a skill itself.

It makes the status visible.

The description of `pine-onboard` and the root instructions must allow Claude to invoke it automatically when an orphan script must be processed.

### 40.5 PWS contextual menu

Create the project skill:

```text
.claude/skills/pws/SKILL.md
```

Its user command is:

```text
/pws
```

It constitutes the guided facade of the workspace. It replaces no business skill.

#### 40.5.1 Interaction primitive

Use `AskUserQuestion` as a priority, the native Claude Code primitive intended for multiple choices, as long as it is available and suitable on the current interactive surface.

The exact limits of `AskUserQuestion` may change. Recheck them during the discovery and test the primitive actually installed. In all cases, design the menu as a short tree of submenus rather than an overloaded flat list.

Do not create at bootstrap:

- competing Python TUI;
- Electron application;
- local server;
- web dashboard;
- navigation database;
- MCP dedicated to the menu;
- custom plugin only to display this menu.

If `AskUserQuestion` becomes unavailable or insufficient in a future surface, first use a simple conversational fallback, then reassess any new layer according to §59.

#### 40.5.2 Startup model

The menu lives INSIDE the Claude Code session.

Ratified architecture:

```text
Interactive Claude Code
        ↓
SessionStart
        ↓
compact PWS state
        ↓
pws skill
        ↓
AskUserQuestion
        ↓
user choice
        ↓
corresponding business skill
```

A `SessionStart` hook must not attempt to drive an interactive TTY directly or to simulate keystrokes. It provides the context; the interaction belongs to the `pws` skill in the conversation.

For a new CLI session where the holder wishes to land immediately on the menu, document the current native form:

```text
claude "Open the PWS menu."
```

Claude Code then starts in interactive mode with this request as the first prompt.

The classic `claude` startup remains valid; `/pws` then opens the menu at any time.

A resume, a compact or a clear must not force the reopening of the menu and interrupt the work in progress. The holder can always use `/pws` explicitly.

#### 40.5.3 Contextual menu

The menu must derive its choices from the real state of the workspace.

Examples of useful facts, keeping the distinct axes of §44:

- no registered product;
- one or more `REGISTERED` products;
- presence of `UNREGISTERED` `.pine` files;
- `INCOMPLETE` or `BROKEN` product;
- `STALE` TradingView validation;
- current TV mode;
- relevant Git state.

Do not artificially display an action that has no purpose. For example, do not offer a release of a non-existent product.

The first level must remain short. The menu is generated by the deterministic tooling (`python3 -m tools.pws_workspace menu --json`, `tools/pws_workspace/menu.py`), with its labels and descriptions taken from the catalogue `tools/pws_workspace/i18n.py` in the configured language; the `pws` skill renders it as it is and never rebuilds it. Current tree, English labels (with French menus, the labels of the same catalogue — for example "Qualité / publication", "Maintenance / configuration" — with the same identifiers and routes; description aligned on the generated menu on 2026-11-14):

```text
PWS                                   (first level: work, new, quality, maintenance)
├── Work on a script                  (action first, then the script)
│   ├── Develop / fix                 → pine-develop
│   ├── Documentation / tutorial      → pine-docs
│   ├── Research                      → pine-research
│   ├── Review                        → pine-review
│   └── Deep audit                    → pine-audit
├── New / import
│   ├── New script                    → pine-new
│   └── Import a script               → pine-onboard
├── Quality / publication             (action first, then the script)
│   ├── Local test (PineTS)           → pine-local-test
│   ├── TradingView validation        → tv-validate
│   ├── Licence and terms of use      → pine-license (independent of "Prepare a publication")
│   ├── Prepare a publication         → pine-release
│   └── GitHub export                 → pine-github
└── Maintenance / configuration
    ├── Workspace diagnostic          → project-doctor
    ├── Detailed state                → session-status
    ├── Configuration
    │   ├── Language                  → config set language
    │   ├── Copyright holder          → config set identity.copyright_holder
    │   ├── Default profile           → config set identity.default_profile
    │   ├── TradingView mode          → tv-mode <mode>
    │   ├── GitHub destinations       → github destinations
    │   └── Startup cleanup           → config set maintenance.startup_cleanup
    ├── Tools and updates
    │   ├── PineTS                    → pine-tools
    │   └── Update Pine-Workspace     → pws-update
    └── Archives and cleanup          → pine-maintenance
```

The tooling paginates every level: at most four options per screen, "More…" opens the next screen of the same level, and "Back" closes every screen below the first level (the first level has none). Each branch opens only the sub-options that are actually applicable; an inapplicable entry is hidden with its reason (for example "Work on a script" while no script is ready).

Then, for a new script (choices of the catalogue, canonical values passed to `pine-new`):

```text
Type
├── Indicator
├── Strategy
├── Library
└── Back

Profile
├── FREE — public source, CC BY-NC-SA 4.0
├── FREE with closed source — proprietary, free use granted
├── PRIVATE — proprietary, personal or limited sharing
├── COMMERCIAL — proprietary, configurable EULA
└── Back
```

These screens are paginated like the others. For `Library`, no other profile is offered: the profile is derived and displayed ("a library is always FREE with public source (TradingView rule)"), then confirmed.

The constraint must be rechecked before publication, but the menu, `pine-new` and the machine schema apply the current official rule as long as it remains in force.

The labels are user-facing; the values passed to the workflow remain the canonical values of the workspace, for example:

```text
script_kind = indicator
profile = COMMERCIAL
```

The licence axes and publication dimensions passed with the profile are its default values (`profile_defaults`; for FREE with closed source, profile FREE with the `free_closed_defaults` axes); nothing is created before "Start".

Historical: the bootstrap design of 2026-08-24 described another first level ("Quality / validation", "Maintenance / other"), a "Distribution" screen (Free / open-source, Paid / closed-source) and a "Change TV mode" entry; it was superseded by the deterministic menu of 2026-11-06. The current description is the one above.

#### 40.5.4 Navigation and effects

The menu must respect the following invariants:

- `Retour` (Back) produces no side effect;
- cancelling the menu modifies no file;
- a selection does not amount to an implicit authorization to publish;
- a workflow choice routes to the corresponding existing skill;
- a durable decision taken in the menu is persisted only in the canonical artefact provided for by the workflow;
- no business logic is duplicated in `pws/SKILL.md`;
- the menu bypasses neither the holder's confirmations already required, nor the gates, nor the TradingView validation;
- if free-form information is needed, leave the menu and ask for this information conversationally instead of turning the menu into a general-purpose form.

For a product creation, display before any creation a short summary of the structured choices and ask for confirmation:

```text
Type: Indicator
Profile: COMMERCIAL — proprietary, configurable EULA

Start / Modify / Cancel
```

For an action that needs a script, the action is chosen first, then the script: with a single registered script, its label is shown ("Script: <slug> (<type>, <profile>)") with "Continue with this script" and "Back"; with several, the "Choose the script" screens (four scripts per screen, "Others…", "Back"); a product that is not ready leads to onboarding, never to a silent selection.

#### 40.5.5 Reference routing

The menu routes in particular to:

```text
Develop / fix               → pine-develop
Documentation / tutorial    → pine-docs
Research                    → pine-research
Review                      → pine-review
Deep audit                  → pine-audit
New script                  → pine-new
Import a script             → pine-onboard
Local test (PineTS)         → pine-local-test
TradingView validation      → tv-validate
Licence and terms of use    → pine-license (independent of pine-release)
Prepare a publication       → pine-release
GitHub export               → pine-github
Workspace diagnostic        → project-doctor
Detailed state              → deterministic state (`session-status`)
Configuration settings      → the deterministic subcommand of each setting (`config set …`, `github destinations`)
TradingView mode            → explicit user choice → shared deterministic controller `pws_workspace tv-mode`
PineTS                      → pine-tools
Update Pine-Workspace       → pws-update
Archives and cleanup        → pine-maintenance
```

The TradingView mode setting (Maintenance / configuration → Configuration → TradingView mode; "Change TV mode" in the historical bootstrap design) does not route to `Skill(tv-mode)`, since `/tv-mode` remains user-only with `disable-model-invocation: true`. The facade and the direct skill share the same controller; no mutation logic is duplicated in the menu.

The direct commands remain available. The menu is a UX facade, not an obligation for Claude nor a layer of authority.

#### 40.5.6 Freshness

When a `/pws` is invoked long after `SessionStart` or after significant changes, refresh the necessary mechanical facts through the deterministic tooling, preferably `session-status`, before building the menu.

Do not use an old session observation as the current truth if it may have changed.

### 40.6 Snapshot

The session snapshot is ephemeral and associated with the `session_id`.

It is used by the Stop hook to distinguish:

- files already present at the first startup of the session;
- sources actually changed during this session.

Create the baseline only once for a `session_id`.

If `SessionStart` fires again because of a resume, a compact, a clear or another mechanism that keeps the same logical work, do not silently overwrite an already existing baseline.

Subagent sessions must use a separate state or ignore this baseline when they are read-only; they must never reset the state of the main session.

Do not version this snapshot.

---

## 41. HOOK `Stop`

### 41.1 Mission

Prevent closing with a repairable mechanical violation introduced during the session.

Mechanical safeguard of routine work (master §9.1, level 1): it triggers neither a full reading, nor an agent, nor a review (amendment of 2026-11-13).

### 41.2 Source of the changes

Compare with the SessionStart snapshot and the Git state to identify the `.pine` files actually modified since startup. The snapshot keeps, per file, the path, the SHA-256, the blocking guard findings evaluated at startup and the checks not evaluable at that moment. Each file present at Stop is attached to the baseline by path, otherwise by SHA-256 (moved, unchanged), otherwise by a rename detected by Git when the correspondence between the baseline file and the current file is unambiguous (moved and modified); failing that, its provenance is undetermined. A rename detected by Git is a technical correspondence; it does not on its own prove the actual history of the file. Neither the file name nor membership of the same product is sufficient; any ambiguous correspondence remains undetermined. The absence of correspondence does not prove that a file is new. Attribution is done finding by finding, a finding being identified by its check and by the object of the anomaly (missing element, value or URL in question), regardless of its position in the file; multiple occurrences of the same object are counted. A finding is introduced if the file is new or if the check was evaluable at startup without this finding; pre-existing if the same finding existed at startup, even if the file has changed elsewhere; made visible by the context if the check was not evaluable at startup; undetermined if the provenance of the file cannot be established. The guard is always re-run with the current context; a known hash does not exempt from any check.

A source imported during the session may be the subject of an import record (§52.5). The file attached to this record is compared with the guard state recorded at import, according to the same rules: a finding already present at import is pre-existing at import, a finding that appeared afterwards is introduced, a check not evaluable at import is made visible by the context. A record is attached to a single file; a mere hash equality exempts no other file from the checks, and any ambiguous attachment remains undetermined. A file absent from the baseline and without an import record remains new.

### 41.3 Behaviour

For the `.pine` files changed during the session:

- check that they belong to an onboarded product;
- run the mechanical guard;
- flag a stale TradingView validation;
- block only on the truly blocking mechanical violations introduced during the session; flag without blocking the violations that are pre-existing, made visible by the context or of undetermined attribution, with their category;
- word its messages — blocking reason, non-blocking information and its category, warning on legal mentions — in the configured language in force when they are shown (`language`; English when the configuration is absent or the value unknown); the non-blocking information handed to the next summary is recorded as structured items and worded when it is shown; information recorded as text by an earlier version is shown as recorded, marked as such; paths, check identifiers and guard details are reproduced exactly (amendment of 2026-11-14).

### 41.4 Stale TradingView validation

A stale validation does not automatically prevent every Claude response.

It prevents presenting the script as finally validated/ready if the task requires this validation.

The Stop hook may add informative context without a needless loop.

### 41.5 Loops

Respect `stop_hook_active` or the current equivalent.

Do not create a condition that is impossible to satisfy.

Claude Code currently limits the successive continuations of a Stop hook.

The hook must be:

- fast;
- deterministic;
- actionable;
- low-noise.

---

## 42. NO SEMANTIC HOOK BY DEFAULT

Do not create initially:

- prompt hook judging the quality of the Pine at every edit;
- review agent hook after every line;
- network hook;
- publication hook;
- automatic benchmark hook at every change;
- hook launching PineTS;
- hook running behavioural regressions;
- hook running a matrix of datasets, parameters or stability probes.

Semantic checks belong to the workflows/agents.

PineTS is run neither by `SessionStart`, nor by `PostToolUse`, nor by the `Stop` hook of the foundation.

Behavioural execution belongs exclusively to explicit workflows such as `pine-new`, `pine-develop`, `pine-release` or `pine-local-test`.

Hooks remain mechanical or context safeguards.

---

## 43. LOCAL GIT

### 43.1 Initialization

Before `git init` or any mutation, apply the physical boundary of §6.1. If `pine workspace` is already enclosed by a parent repository, do not initialize a nested repository nor silently accept the parent root: stop and ask the holder for a decision.

If the workspace is not a Git repo:

- initialize locally;
- use the machine's Git default when it is sound;
- otherwise use a conventional working branch such as `main`;
- do not create a remote.

If a remote already exists in a pre-existing workspace:

- flag it;
- do not remove it silently;
- do not use it to push without an explicit decision of the holder.

### 43.2 Commit

Do not automatically create a commit without explicit approval from the holder.

The bootstrap may prepare the changes and propose the first commit.

### 43.3 Worktrees

Use worktrees for:

- risky structural change;
- experimentation;
- parallel work;
- future modifying agent;
- useful isolation.

Do not impose a worktree for a typo.

Git worktrees are usable only after a usable base commit exists. Before the first authorized commit, document this limitation instead of claiming that worktree isolation is operational.

### 43.4 Current subagents

The four base subagents are read-only.

They therefore do not need a worktree.

Any future subagent authorized to modify code must be evaluated for `isolation: worktree`.

### 43.5 Backup

Local Git on the same disk is not a hardware backup.

`OPERATIONS.md` may recommend, without imposing it:

- a second local bare repo;
- an external disk;
- a NAS;
- other private storage decided by the holder.

Do not introduce GitHub by default. The local archives grouped under `docs/maintenance/archives/` do not stand in for a backup independent of the disk.

**Guided GitHub export path (ratified on 2026-11-06)**: destinations declared in `pws.config.json` (`name`, `repo`, `visibility`, `path_prefix`, `branch`); `github export-plan` builds, for a REGISTERED product, the exported set from a list of allowed contents (source only if `source_visibility = public` or destination `private`; release documents, tutorial, referenced terms) and lists the justified exclusions (manifest, internal context, decisions, research, validation evidence, tracking); never the workspace, `pws.config.json`, `.claude/`, `docs/maintenance/`, archives or secrets. `github fetch` (local clone, explicit network act) then `github export-diff` show added/modified/unchanged; `github publish --yes` copies, commits and pushes in the clone after explicit authorization from the holder for this precise plan (`git push` remains subject to confirmation). Any send, public content included, requires before any write in the clone that the URL of the destination and the clone (a single fetch and push URL, `pushurl` and rewrites applied) designate the github.com repository configured for the destination, in strict URL forms; the remote is re-read just before the push and, if it has changed after the local commit, nothing is pushed and the state left on disk is described (holder's request of 2026-11-14: identity of the authorized repository, distinct from privacy; public content may go to a private repository chosen explicitly). What leaves is exactly the plan: an empty URL entry or a setting that makes Git connect elsewhere than the displayed URL or without verifying it (replaced SSH or connection program, remote helper, imposed address, disabled TLS verification, in the configuration or the environment) is refused; a target that differs only by case from an entry of the repository or that requires a folder where it has a file is refused; a file whose bytes Git would modify at commit is refused before any write; no hook runs in the publication clone; the local commit is verified before the push. A send that contains a closed source additionally requires, immediately before the push, that GitHub report the configured repository itself as `PRIVATE` (`gh repo view`, current authentication); failing that, refusal (holder's decision of 2026-11-13, finding I-06). The visibility may change between this check and the send: no atomic guarantee. An imported script is exported with its declared original legal documents (`license.documents`, §45.2), as is (name, bytes, encoding, language), never replaced by a PWS template; a file with a legal name is never included on the strength of its name alone nor discarded silently: as long as a document is not declared, is missing, modified since the plan or refused by a check (link, special file, uncheckable content, PWS template syntax, code of a closed source to a public destination), the entire export waits, with the resolution. A private folder in a public repository is never assumed possible; an existing repository is a destination to configure, never to restructure; removal of files, rewriting of history and change of visibility remain acts of the holder outside the workflow.

---

## 44. SCRIPT REGISTRATION MODEL

Do not maintain a separate central registry.

The truth is distributed per product:

```text
scripts/<slug>/SCRIPT.json
```

The workspace rebuilds the list of products by scanning these manifests.

This avoids:

```text
central registry ≠ actual folders
```

### 44.1 Deterministic state axes

Do not reduce several independent findings to a single status. The scanner exposes at a minimum:

```text
product_structure_status:
  REGISTERED
  INCOMPLETE
  BROKEN
  AMBIGUOUS

source_registration_status:
  REGISTERED
  UNREGISTERED

validation_status persisted:
  unverified
  in-progress
  passed
  failed
  partial

validation_integrity_status:
  OK
  BROKEN

validation_effective_status derived:
  applicable persisted value
  stale
  null if the integrity is BROKEN
```

A product root can therefore be `BROKEN` while containing an `UNREGISTERED` `.pine`, without one finding overwriting the other.

In the `product_structure_status` axis, apply the following deterministic order only to produce the synthetic value:

```text
AMBIGUOUS
> BROKEN
> INCOMPLETE
> REGISTERED
```

`AMBIGUOUS` means that the reliable identity of the product or of its source cannot be established; `BROKEN` that a present contract is invalid or inconsistent; `INCOMPLETE` that a required element is missing without ambiguity or broken contract; `REGISTERED` that the mechanical criteria are satisfied. The scanner keeps in parallel a structured list of all the applicable findings so that the synthetic value does not mask the secondary causes.

### 44.2 `product_structure_status = REGISTERED`

A product is structurally onboarded if:

- valid product root;
- valid `SCRIPT.json`;
- declared source present in this root;
- `PRODUCT.md` present, readable, non-empty and without an explicitly known placeholder;
- `ARCHITECTURE.md` present, readable, non-empty and without an explicitly known placeholder;
- local `CLAUDE.md` present, readable, non-empty and without an explicitly known placeholder;
- `validation/current.json` present;
- distribution model resolved;
- no ambiguity about the main source.

The scanner does not claim to judge mechanically that these documents are semantically "substantial" or of good quality. This review belongs to the onboarding, to the reviewer or to an explicit semantic check of the doctor.

### 44.3 `source_registration_status`

`REGISTERED` means that the `.pine` is the canonical source of a valid `SCRIPT.json` (schema 3, or a legacy schema 2 or 1 manifest still read and flagged until `migrate --apply`, §45.2) whose path resolves within the same product root.

`UNREGISTERED` means that a `.pine` exists under `scripts/**` but belongs to no valid manifest.

The same `.pine` cannot be claimed by several manifests. Any multiple claim is flagged as a structural ambiguity without a silent choice.

### 44.4 `product_structure_status = INCOMPLETE`

Onboarding elements exist but the minimal context is incomplete.

### 44.5 `product_structure_status = BROKEN`

The manifest points to a missing source or an inconsistent structure.

### 44.6 `product_structure_status = AMBIGUOUS`

Several `.pine` files or several contexts prevent reliably determining the main product/source.

### 44.7 `.pine` directly under `/scripts`

Flag it as structurally not onboarded.

Do not move it silently if the target slug is not obvious.

---

## 45. `SCRIPT.json` — CONTRACT

### 45.1 Purpose

Minimal machine routing.

### 45.2 Normative schema 3 (ratified on 2026-11-06, separate publication dimensions)

```json
{
  "schema_version": 3,
  "id": "zigzag-orderblock-retracement",
  "source": "ZigZag OrderBlock Retracement.pine",
  "script_kind": "indicator",
  "profile": "COMMERCIAL",
  "license": {
    "id": "PROPRIETARY",
    "grant": "eula",
    "source_visibility": "closed",
    "access": "paid",
    "copyright_holder": null,
    "created_year": 2024,
    "terms_ref": "release/EULA.md",
    "terms_url": null
  },
  "publication": { "state": "published", "privacy": "public", "mode": "invite-only" },
  "migration": { "from_schema": 2, "from_publication": "tradingview-invite-only", "on": "2026-11-06", "note": "…" }
}
```

For `schema_version = 3`, the seven fields `schema_version`, `id`, `source`, `script_kind`, `profile`, `license`, `publication` are mandatory, `migration` is optional, and any other field is rejected. `license` carries four mandatory axes (`id`, `grant`, `source_visibility`, `access`) and four optional fields (`copyright_holder`: null → configured identity; `created_year`: creation year, kept during updates; `terms_ref`: relative path, confined to the product root, to the rendered terms; `terms_url`: https URL of the declared legal reference of the product, the only non-standard URL admitted by the guard, by exact match). `publication` carries exactly three independent dimensions, each nullable (null = unknown, flagged, never inferred): `state` ∈ `unpublished`, `published`; `privacy` ∈ `public`, `private` (privacy of the TradingView publication); `mode` ∈ `open`, `protected`, `invite-only` (script mode: source visible, source hidden, access by invitation). None of these values is derived from another; the consistency rules of §45.4 check them against each other. Any extension goes through an explicit evolution of the schema.

Earlier schemas, read for compatibility and migrated explicitly (`migrate --apply`, step m005): schema 1 (`distribution` ∈ `free-open-source`, `paid-closed-source` → profile and axes derived from the defaults, publication state unknown); schema 2 (`license.publication` as a single string that conflated privacy and mode → `tradingview-open|protected|invite-only` = corresponding mode and UNKNOWN privacy (never inferred), `tradingview-private` = private privacy and UNKNOWN mode, `unpublished` = unpublished state; the state remains unknown except for `unpublished`); schema 1 → publication entirely unknown (the profile defaults are proposals for a new project, never facts of a migrated project). Both forms are flagged (`MANIFEST_LEGACY_SCHEMA`); the migration keeps only the recorded information, leaves the unknowns null and reports them as ambiguities; an earlier migration that inferred a value is rectified in a traced way (`migration.rectifications`) without touching a value confirmed by the holder (`migration.holder_confirmed`, `license confirm`). An unknown creation year is never replaced by the current year.

`id` is exactly equal to the slug of the product root. IDs/slugs are unique in the workspace with a case-insensitive comparison in order to avoid collisions on the generally case-insensitive macOS filesystems.

`source` is a path relative to the product root to a `.pine` file. Its final physical resolution must remain within this root. The following are rejected:

- absolute path;
- outgoing `..` traversal;
- symlink or chain of symlinks leading out of the product root;
- reference to a source located in another product root, another project or any location outside the product root;
- ambiguous path or non-unique main source.

No tool reads a source whose resolved path leaves the product root (scanner, guard, `validation-status`, hooks); an invalid manifest never causes a read outside the perimeter.

`SCRIPT.json` is the canonical machine source of `script_kind`, of the profile and of the licence axes. `PRODUCT.md` and `CLAUDE.md` may explain them, but do not redefine them as competing authorities.

**Existing licence of an imported script** (explicit evolution decided by the holder on 2026-11-13, finding C-19; compatible extension: `schema_version` remains 3, any earlier manifest remains valid and unchanged, no migration). `license` admits two additional optional fields: `origin` ∈ `profile` (default when it is absent or null: licence of a profile) | `imported` (existing licence of an imported script, kept); `status` ∈ `confirmed` | `to-analyse`, mandatory when `origin = imported` and forbidden otherwise. With `origin = imported`: `status = confirmed` ⇒ `id` ∈ closed list of exact SPDX identifiers confirmed by the holder (`CC-BY-NC-SA-4.0`, `MPL-2.0`, `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `GPL-2.0-only`, `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later`, `LGPL-2.1-only`, `LGPL-2.1-or-later`, `LGPL-3.0-only`, `LGPL-3.0-or-later`, `AGPL-3.0-only`, `AGPL-3.0-or-later`); `status = to-analyse` ⇒ `id = null`; `grant = license` (rights defined by the licence itself; `cc` for `CC-BY-NC-SA-4.0`). `grant = license` is reserved for `origin = imported`; `PROPRIETARY` is never an imported licence. Deprecated SPDX identifiers (`GPL-2.0`, `GPL-3.0`, `LGPL-2.1`, `LGPL-3.0`, `AGPL-3.0` and their "+" forms) are never recorded; "only" and "or later" are never treated as equivalent. A schema 2 manifest never carries these fields. The validated view exposes `origin` and `status` only when they are recorded. Original legal documents (holder's request of 2026-11-14, same compatible extension): `license.documents`, optional and reserved for `origin = imported`, lists the files that accompany the existing licence (licence text, `NOTICE`, attributions), declared by the holder — paths relative to the root of the product or directly under `release/` bearing a legal name (`LICENSE`, `LICENCE`, `COPYING`, `COPYRIGHT`, `NOTICE`, `PATENTS`, `AUTHORS`, `CREDITS`, `ATTRIBUTION`, `CONTRIBUTORS`, `THIRD_PARTY_NOTICES` and their variants), or `LICENSES/<licence>.txt` texts (REUSE layout); never a hidden file, a Pine source, a JSON, a lock, an internal Pine Workspace file or a name bearing an invisible character; a file with a legal name located elsewhere in the product (except internal folders), a folder with a legal name or a `release/` / `LICENSES/` that is a link makes the export wait until the holder moves it; `[]` = no separate document; absent or null = not declared. The recorded SPDX identifier does not on its own say which documents a redistribution requires.

```json
"license": { "id": "MPL-2.0", "grant": "license", "source_visibility": "public", "access": "free",
             "origin": "imported", "status": "confirmed",
             "copyright_holder": null, "created_year": null, "terms_ref": null, "terms_url": null }
```

### 45.3 `script_kind` values

Support according to current Pine:

```text
indicator
strategy
library
```

### 45.4 Profiles, licence axes and publication dimensions

Profiles (starting configurations, never quality levels or imposed modes — master §5):

| Profile | `license.id` / `grant` | `source_visibility` | `access` | default `publication` (state / privacy / mode) |
| --- | --- | --- | --- | --- |
| `FREE` | `CC-BY-NC-SA-4.0` / `cc` | `public` | `free` | `unpublished` / `public` / `open` |
| `FREE` with closed source (same profile, adjusted axes) | `PROPRIETARY` / `free-use` | `closed` | `free` | `unpublished` / `public` / `protected` |
| `PRIVATE` | `PROPRIETARY` / `none` | `closed` | `restricted` | `unpublished` / null / null |
| `COMMERCIAL` | `PROPRIETARY` / `eula` | `closed` | `paid` | `unpublished` / `public` / `invite-only` |

`PRIVATE` is a usage profile: it designates neither a private TradingView publication (`publication.privacy`) nor a private GitHub repository. TradingView rules consulted on 2026-11-06 (Pine Script User Manual, "Publishing scripts"): privacy and mode are two distinct settings of the publication; only a public `invite-only` script may be paid; selling access to a private script is forbidden, as is charging for an `open` or `protected` script.

**Existing licence of an imported script.** The profiles are the configurations proposed to new projects; they never force the licence of an imported script. Four notions remain distinct: usage profile, licence (exact `license.id`), visibility of the source, publication (state, privacy, mode). An imported licence keeps its text, its notices and its attributions; no licence is assigned automatically; a header detection is a proposal to be confirmed by the holder, never legal evidence. Proposal: "either version N of the License, or (at your option) any later version" → `-or-later`; "version N" alone → `-only`; any other wording → to analyse (in particular several versions or a choice between versions — "version 2 or 3", "v2 or v3", SPDX expression `GPL-2.0-only OR GPL-3.0-only` — never a single `-only` or `-or-later` identifier; a deprecated SPDX identifier, on an SPDX line as in the text of the notice); `MIT` designates the Expat text (X11 notice or the "MIT License" mention alone → to analyse).

Imported licence — BROKEN: `grant = license` without `origin = imported`; `origin = imported` without `status`, with a grant other than `license` (`cc` for CC-BY-NC-SA-4.0), with `status = confirmed` and an identifier outside the closed list or deprecated, or with `status = to-analyse` and a filled-in identifier; `documents` without `origin = imported`, that is not a list of paths, or of which an entry falls outside the admitted names and locations or is declared twice. Warnings (never blocking for development): `LICENSE_DOCUMENT_UNAVAILABLE` (declared document missing, symbolic link or non-regular file: the export waits); `LICENSE_TO_ANALYSE` (imported licence to analyse: publication preparation and the export do not treat it as settled as long as the holder has not recorded the exact identifier); `IMPORTED_LICENSE_CONFLICT` (copyleft licence — MPL, GPL, LGPL, AGPL — with closed source, `protected` or `invite-only` mode, or paid access; CC BY-NC-SA with `protected` or `invite-only` mode, or paid access (NonCommercial clause) — an imported CC BY-NC-SA with closed source remains BROKEN by the mechanical rule CC ⇒ public source; permissive licence whose notice must accompany the work: points to analyse, never an automatic block nor a legal conclusion); `IMPORTED_LICENSE_TERMS` (`terms_ref` declared: no PWS document applies). For an imported licence, `PROFILE_AXES_DIVERGENCE` compares only the access; `ACCESS_PAID_WITHOUT_EULA` and `TERMS_URL_WITHOUT_TERMS` do not apply. Guard: the existing notice must remain present and consistent with `license.id` (read in the header and in the initial comment block that follows `//@version`, up to the first line of code; never moved) (missing, or establishing another licence of the same family → blocking; the record is corrected with the holder, never the notice; a notice that does not establish exactly the recorded identifier — several versions or a choice between versions, deprecated identifier, ambiguous wording → warning, never a block nor a silent acceptance); neither a CC header, nor `All Rights Reserved`, nor a © line of the configured copyright holder is required (the original authors remain cited; absence of any copyright line → warning); licence to analyse → header template not verifiable; the targeted licence URL rule remains that of decision D.

Mechanical consistency rules (BROKEN): `CC-BY-NC-SA-4.0` ⇒ `grant = cc` and `source_visibility = public`; `grant = cc` ⇒ CC licence; `publication.mode = open` ⇒ `source_visibility = public`; `library` ⇒ `source_visibility = public`, `mode` ∈ `open`, null and `access ≠ paid` (library open-source rule as recorded by the master at its verification date, rechecked before publication; an official evolution requires an amendment of the contract rather than a silent local workaround); `terms_url` must be an https URL. Warnings (never blocking for development, flagged before a publication): `access = paid` without `grant = eula`; `access = paid` with `privacy ≠ public` or `mode ≠ invite-only`; `grant = eula` without `terms_ref` (draft EULA); `terms_url` without `terms_ref`; `state = published` with unknown `privacy` or `mode`; unknown `state` (migrated manifest, to be confirmed). The scanner, `pine-new`, `pine-onboard`, the PWS menu, `project-doctor`, `license status`, the `pine-license` guided path and the self-tests apply the same rules.

### 45.4bis Guided path "Licence and terms of use" (ratified on 2026-11-07)

Entry `Qualité / publication → Licence et conditions d'utilisation → choix du script` (Quality / publication → Licence and terms of use → script choice; skill `pine-license`), independent of `pine-release`: it triggers no release check, no review, neither PineTS nor TradingView. Functions: view the profile, the licence, the legal references and the information already recorded; identify what is missing or remains to be confirmed; complete or modify through a guided dialogue in consistent groups (product identification, provider and contact, beneficiary or authorized account, commercial model and term, renewal and termination, support, refunds, governing law, additional terms — only the fields actually provided for by the templates of the profile); preview the documents; save the information and generate the documents on explicit choice. Documents served without imposing an EULA on everyone: FREE with public source → CC header; FREE with closed source → free-use grant; PRIVATE → proprietary notice and optional particular permission; COMMERCIAL → configurable EULA. Data and commands reused: manifest (`license confirm`, including `--terms-ref` / `--terms-url`), `release/eula-fields.json` (`license set-fields`, existing values kept, explicit deletion), templates (`license preview` / `license write`) — neither a second logic nor a second storage. Rules: nothing invented (year, legal identity, jurisdiction, commercial terms, URL); copyright holder distinct from the legal identity of the provider; licence profile, source visibility and publication dimensions never conflated; unknown information left empty and taken up again later; draft status as long as indispensable information is missing; summary then grouped confirmation before saving; viewing and previewing without writing; Back or Cancel discards the unsaved changes; a technically complete document is never presented as a legally validated contract. Interface in the configured language, documents in English.

Existing licence of an imported script: no PWS terms document (neither a template header, nor an EULA, notice or grant: `license write` and `license confirm --terms-ref` refuse); `overview` and `status` display it as "existing licence kept" (`kept`) or "to analyse" (`to-analyse`) with the proposal read in the header; `license confirm --license-id` records the exact identifier confirmed by the holder (closed list; deprecated, ambiguous, off-list or profile licence refused), `--clear license_id` resets it to "to analyse"; `license detect --source` gives the proposal for a source not yet onboarded (read-only); it reads the header (`header_lines`) and the initial comment block that follows `//@version` (`after_version_lines`), and lists the files with a legal name in the product folder (`legal_document_candidates`, a proposal never recorded). `license confirm --license-document <path>` (repeatable; the declaration lists all the documents and replaces the previous one) records `license.documents` after checking each file (admitted name and location, regular file of the product without a link, checkable UTF-8 or single-byte text, no shared exported name); `--no-license-documents` records that no separate document accompanies the script; `--clear license_documents` returns to "not declared"; refused for a profile licence. `overview` and `status` show the declared documents, the files with a legal name found, those that are not declared and what makes the export wait; the documents are never rewritten, translated or replaced by a template.

### 45.5 Prohibitions

Never store here:

- product version number;
- algorithmic details;
- secrets;
- benchmark;
- decision history;
- duplication of PRODUCT.md;
- current validation hash.

---

## 46. `PRODUCT.md` — CONTRACT

### 46.1 Purpose

Describe the product actually built.

### 46.2 Construction

Must be written after analysis of the real script or design of the new product.

### 46.3 Useful content depending on applicability

- trader problem solved;
- audience;
- functional promise;
- main behaviour;
- user workflow;
- differentiating elements;
- configuration philosophy;
- boundaries;
- non-goals;
- distribution model;
- proprietary aspects not to be exposed for a paid product.

### 46.4 Provenance

Clearly distinguish:

```text
Confirmed by the holder
Observed in source
Pending confirmation
```

Use only the categories that are actually useful.

### 46.5 Prohibition

Do not fill empty sections.

Do not present an inference as a decision.

---

## 47. SCRIPT `ARCHITECTURE.md` — CONTRACT

### 47.1 Status

Living map derived from the code.

### 47.2 Content depending on applicability

- logical sections;
- types/enums/UDTs;
- central helpers;
- calculation flow;
- input dependency tree;
- persistent state;
- collections;
- requests;
- MTF flow;
- signal pipeline;
- rendering pipeline;
- object lifecycle;
- tables;
- alert dependencies;
- performance hotspots;
- repaint-sensitive zones;
- consumers of the important functions;
- script-specific invariants.

### 47.3 Names rather than lines

Prefer the names of symbols, sections and relations.

Line numbers may be added as a derived aid, but must not constitute the identity of a component.

### 47.4 Update

Update only when a modification makes the map incorrect.

Do not rewrite this file mechanically after each micro-edit.

---

## 48. LOCAL `CLAUDE.md` OF THE SCRIPT — CONTRACT

### 48.1 Loading

Designed to be loaded on demand when Claude works in the product root.

### 48.2 Size

Aim for about 30 to 80 lines.

### 48.3 Content

Only the information Claude must have in context when it touches THIS product:

- identity;
- main source;
- short objective;
- distribution;
- critical product invariants;
- risk areas;
- contextual files to consult;
- important non-goals;
- product-specific rules not covered by the master.

### 48.4 Non-duplication

Do not summarize in full:

- PRODUCT.md;
- ARCHITECTURE.md;
- master standard.

The local file is a router and a reminder of the critical invariants.

---

## 49. `DECISIONS.md` — CREATION ON DEMAND

### 49.1 Trigger

Create only when a first durable decision must be persisted.

### 49.2 Valid entries

Examples:

- product decision of the holder;
- durable architectural decision;
- intentional behaviour whose future preservation matters;
- explicit derogation.

### 49.3 Invalid entries

Do not record:

- micro-refactor;
- trivial renaming;
- session summary;
- mere observation of the source;
- temporary discovery;
- unratified hypothesis.

### 49.4 Structure

Each decision contains at least:

```text
ID
Date
Status
Decision
Rationale
Scope
Supersedes (if applicable)
Evidence/context
```

### 49.5 History

Prefer append-only and `SUPERSEDED` rather than a silent rewrite of the past.

---

## 50. RESEARCH PER SCRIPT

### 50.1 Creation

`research/` appears only when genuinely useful research is persisted.

### 50.2 Run

Recommended name:

```text
runs/YYYY-MM-DDTHHMMSS-<topic>.md
```

### 50.3 Content

- question;
- context;
- date;
- sources consulted;
- facts;
- benchmark;
- limits;
- conclusion;
- implications;
- topics to re-verify.

### 50.4 `CURRENT.md`

Navigation summary.

It does not replace the runs.

Include:

- currently relevant topics;
- date of last verification;
- source run;
- status `CURRENT`, `STALE` or `NON REVÉRIFIÉ`.

Statuses allowed in `CURRENT.md`: `CURRENT` (dated re-verification), `STALE` (known change or re-verification due), `NON REVÉRIFIÉ` (reconstructed or old research, without re-verification since its initial date). A reconstructed run never receives `CURRENT` without re-verification.

---

## 51. VALIDATION PER SCRIPT

### 51.1 Minimal folder

After onboarding:

```text
validation/
└── current.json
```

Create `runs/` and `evidence/` only when they serve a purpose. As soon as a durable real run exists, use the convention:

```text
validation/current.json
validation/runs/<run_id>.json
validation/evidence/<run_id>/<evidence-file>
```

`validation/` is exclusively reserved for TradingView observations, runs and evidence. PineTS artefacts belong to `tests/behavioral/` or to the appropriate ephemeral runtime space and must never be mixed in here.

### 51.2 `current.json`

Represents the last known validation state, not an eternal truth.

Normative initial example:

```json
{
  "schema_version": 1,
  "status": "unverified",
  "last_run": null
}
```

`last_run` is either `null` or a deterministic reference object containing at least:

```json
{
  "run_id": "<collision-resistant-id>",
  "report": "runs/<run_id>.json",
  "source_sha256": "<sha256>",
  "completed_at": "<RFC-3339 UTC>"
}
```

`current.json` designates the recognized current run; it does not contain a competing copy of the whole report.

### 51.3 Run states

Support at least:

```text
unverified
in-progress
passed
failed
partial
```

A single taxonomy is persisted: the five values above. Historical or display tokens such as `PENDING`, `TV_VALIDATION_PENDING`, `PASSED` or `TV_VALIDATED` are not additional machine values; they must be removed or explicitly mapped to this taxonomy.

Normative mapping when a legacy label or a human display must be interpreted:

| Historical label / display | Machine value |
| --- | --- |
| `PENDING`, `TV_VALIDATION_PENDING` | `unverified` or `in-progress` depending on whether a started run exists |
| `PASSED`, human claim `TV_VALIDATED` | `passed`, only if §51.5 is satisfied |
| `STALE` | derived `stale`, never persisted |

The effective status becomes `stale` when the SHA-256 of the current source differs from the `source_sha256` of the recognized current run. The comparison applies to the source declared by `SCRIPT.json`. A run recorded on another SHA remains historical and does not validate the current source.

`stale` is derived and is not persisted as a sixth status, so as not to mutate a file at each edit.

If `current.json` references a report that is missing, invalid or whose identity does not match, set `validation_integrity_status = BROKEN`, never consider the validation as `passed` and do not invent a new persisted value. `validation_effective_status` then remains null/unavailable and an actionable diagnostic explains the broken/incomplete validation.

### 51.4 Run report

Each real run keeps at least:

- collision-resistant `run_id`;
- RFC 3339 UTC timestamps;
- persistable status among `in-progress`, `passed`, `failed` or `partial`;
- source;
- SHA-256;
- Git commit or null;
- working tree clean/dirty;
- requested mode;
- effective mode;
- fallback reason;
- applied matrix;
- results; for a version 2 report, each check of the matrix carries a unique identifier and each applicable check a verdict among `passed`, `failed`, `not-run` or `indeterminate`, with the observation, the author and the timestamp; `n-a` is reserved for checks explicitly not applicable. Amendment of 2026-11-06: for a `not-run` or `n-a` verdict, no observation took place, so the author (`observed_by`) may be null — the observation then records why the check was not executed, and the timestamp remains required; an observer, an observation or a compilation is never invented to satisfy the schema. An existing report that violated the contract is never rewritten: a corrigendum is a new file next to the original, which cites its hash and describes each fix;
- anomalies;
- evidence items, each with a relative path under `evidence/<run_id>/`, type and SHA-256;
- conclusion.

The report references the evidence; a screenshot is not mandatory when it provides no useful evidence.

The run report is written immutably before the update of `current.json`. The controller:

1. remembers the identity or the hash of the `current.json` read at the start of the run;
2. writes and verifies the complete report;
3. re-reads `current.json` before promotion;
4. refuses the promotion if the pointer has changed concurrently or if the order of the runs cannot be established;
5. prevents a run whose `completed_at` is earlier than the recognized current run from replacing it;
6. performs the final replacement of `current.json` atomically.

A clock tie or clock anomaly produces an actionable conflict rather than a silent choice.

A minimal compilation run additionally follows the recording and promotion rules of §30.5, applied after these protections.

### 51.5 `passed`

`passed` means:

> All the mandatory TradingView checks applicable to this run have actually succeeded on the source identified by this hash.

The verdicts are examined before the coverage. An applicable `failed` check imposes the `failed` status, even if other checks have no result; it is never reduced to `in-progress` or to `partial`. In the absence of `failed`, an applicable check that is `not-run`, `indeterminate` or without a result forbids `passed`; a check without a result, or the absence of any `passed`, admits only `in-progress`. `partial` requires at least one `passed` and at least one `not-run` or `indeterminate`, all the applicable checks having a result. A check without a result is "not filled in": nothing is asserted about its execution. No run without an applicable check can be `passed`. Reports recorded under an earlier version of the schema remain readable and admissible on their SHA without rewriting; a new report uses the current version. This read compatibility does not establish the creation date of a file.

---

## 52. AUTOMATIC DETECTION OF ORPHAN `.pine` FILES — RATIFIED

This function is mandatory.

### 52.1 At each session

`SessionStart` scans `scripts/**`.

### 52.2 Doctor

`project-doctor` performs the same detection independently.

### 52.3 Claude's behaviour

When a `.pine` is `UNREGISTERED`:

- flag it;
- automatically use `pine-onboard` before any substantial functional modification;
- ask the holder only what cannot be determined properly.

### 52.4 Silence forbidden

An orphan `.pine` must never be silently ignored.

### 52.5 Non-destructive onboarding

The onboarding process does not alter the existing source.

Any fix of the code constitutes a separate task.

When a source is imported during the session, the onboarding records the import before any modification: path, SHA-256 and guard state at that moment, kept in the session state. Moving the unchanged file moves the record. A record is never renewed: once the content is modified, the import can no longer be recorded again. The record is declarative; it distinguishes an import from a creation and does not prove the origin of the file.

---

## 53. CONTEXT UPDATE AFTER A MODIFICATION

Do not regenerate the whole context by reflex.

After a change:

- `PRODUCT.md` only if the product has changed;
- `ARCHITECTURE.md` if the map has become incorrect;
- `DECISIONS.md` if a real durable decision has been made;
- `research/` if durable research has been done;
- `validation` through a real run;
- docs/release only if affected.

The context must remain useful, not become a log of every edit.

Each product designates in its local `CLAUDE.md` a tracking artefact; it records, per coherent modification, the task class, the re-reading coverage read, the benchmark conclusion and the provenance of the agent reports used. Its form is free; it replaces neither `DECISIONS.md` nor `validation/`.

---

## 54. REDUNDANCY — MANDATORY GATE

After the bootstrap, then after any restructuring of the workspace, perform a non-redundancy pass.

### 54.1 Question for each repeated rule

Does the repetition have a distinct function?

Acceptable example:

```text
master
→ normative convention

rule
→ concise contextual routing

guard
→ mechanical enforcement
```

Useless example:

```text
master
→ 20 lines

CLAUDE.md
→ same 20 lines

skill
→ same 20 lines

agent
→ same 20 lines
```

### 54.2 Reference rather than copy

Workflows must refer to the standard or to the traceability when the detail does not need to be repeated.

### 54.3 Workflows

Some repetition of steps in a workflow is acceptable if it makes the sequence executable.

Duplication of doctrine is not.

---

## 55. BOOTSTRAP IDEMPOTENCE

The specification must be re-executable without destroying a mature workspace.

### 55.1 Before any re-execution

Detect:

- existing files;
- local modifications;
- version of the standard;
- current architecture;
- script contexts;
- hooks;
- skills;
- agents;
- local settings.

### 55.2 Prohibitions

Do not:

- overwrite `DECISIONS.md`;
- reset `validation/`;
- delete the research runs;
- replace a `PRODUCT.md` with a generic one;
- rewrite the skills without diff/review;
- overwrite `settings.local.json`;
- delete the local approvals.

### 55.3 Migration

If the architecture must evolve, first produce:

- expected diff;
- risks;
- migration plan;
- compatibility;
- affected files.

A significant migration requires the holder's validation.

---

## 56. NO PRODUCT VERSION OUTSIDE THE SOURCE

The workspace respects the Personal Convention:

> The product version appears only in the source code header, except by explicit derogation.

Consequently, do not include the product version in:

- `SCRIPT.json`;
- `PRODUCT.md`;
- `ARCHITECTURE.md`;
- local `CLAUDE.md`;
- research;
- validation state;
- tutorial;
- changelog;
- release notes;
- description;
- workspace architecture files.

The hash of the source and the Git commit suffice to identify a validation technically.

---

## 57. NEW FOLDERS ON DEMAND

### 57.1 `docs/`

Create when a real documentation deliverable exists.

### 57.2 `release/`

Create when a real release requires preparation artefacts.

### 57.3 `research/`

Create when research deserves persistence.

### 57.4 `validation/evidence/`

Create when an evidence file exists.

`scripts/<slug>/tests/behavioral/` is likewise created only when a real behavioural test contract, a specific fixture or an accepted baseline exists for this product. Do not create this folder during onboarding alone or to materialize the tree structure.

### 57.5 Dynamic workflows

Do not create `.claude/workflows/` at the initial bootstrap.

Add it only when a recurring multi-script need is demonstrated.

Legitimate future example:

> A Pine V6 evolution is published; analyse all of the holder's scripts and identify which ones are affected.

---

## 58. CAPABILITIES DELIBERATELY EXCLUDED FROM THE INITIAL FOUNDATION

Do not install by default:

- GitHub as a dependency of the workspace (remote, CI) — the explicit guided export path of §43.5 is not one;
- GitHub Actions;
- any MCP configured by the project or custom MCP server;
- Agent Teams;
- predefined dynamic workflows;
- remote CI;
- SQLite database;
- central registry;
- local server;
- web dashboard;
- custom Claude plugin;
- TradingView publication automation;
- parallel editing agent;
- persistent memory of the reviewers;
- large semantic rules engine;
- local copy of the entire TradingView documentation.

Any new layer must meet a real, demonstrated need.

The introduction of the PineTS thin adapter constitutes an exception to none of these exclusions.

In particular, it does not authorize the creation of a local server, MCP, database, dashboard, remote behavioural CI or parallel platform around PineTS.

The native Claude in Chrome integration can currently expose an internal transport named `claude-in-chrome` MCP. This transport, provided by Claude Code itself, is authorized only as an implementation detail of the native primitive used by `chrome-experimental`:

- PWS does not install it as a project dependency;
- PWS does not create a `.mcp.json` for it;
- this exception authorizes neither `tradingview-mcp`, nor a third-party MCP, nor an external CDP bridge;
- any project MCP, custom server, PineTS MCP or MCP dedicated to the menu remains excluded without explicit ratification.

---

## 59. CRITERION FOR ADDING A NEW LAYER

Before adding a tool, agent, skill, hook or storage:

1. What concrete gap does it remedy?
2. Does a current native primitive already cover the need?
3. Is the problem real or hypothetical?
4. What is the contextual cost?
5. What is the maintenance cost?
6. Does it create a second source of truth?
7. Can it become stale?
8. What incident does it prevent?
9. Can it be added later without significant debt?

If the need is not demonstrated, do not add the layer.

### 59.1 Ratified application — PineTS

The `LOCAL BEHAVIORAL EXECUTION` layer meets the gate of this section because it covers a concrete gap not covered by the existing primitives:

```text
deterministic checks
→ no real execution of the Pine
→ TradingView validation
```

The gap covered is the absence of a local runtime making it possible to observe the behaviour of the source programmatically before TradingView and, when the evidence allows it, to enforce a reproducible local behavioural contract.

The authority boundary is as follows:

- the official Pine Script documentation remains the authority on the syntax, the APIs and the official semantics of the language;
- TradingView remains the empirical authority on the behaviour specific to its platform and on any `tv-validate` step;
- PineTS can be a local execution authority for a strictly bounded conclusion when all the necessary capabilities are effectively gating and the exact source, dataset, configuration and environment are identified;
- a local PineTS conclusion, even a blocking one, never becomes `TV_VALIDATED` and never proves a general parity with TradingView.

This layer is admitted only under the following constraints:

- its use is capability-gated;
- the capabilities are qualified with sufficient granularity, without condemning or promoting an entire family on principle;
- `capability_status` and `calibration_status` remain two distinct dimensions;
- every effectively gating capability has an independent `CURRENT` calibration for the exact triplet `pinets_version + executor_fingerprint + normalization_schema`;
- the capabilities actually used by each run are recorded;
- the datasets are reproducible, hashed and accompanied by sufficient provenance;
- independent snapshots are admitted when their terms of use allow it;
- local matrices and parameter sweeps remain bounded, explicit and traceable, without a generic optimizer or automatic triggering by hook;
- the licences and terms of use of PineTS, of the data sources and of TradingView are assessed according to the resource actually used;
- the PineTS version is pinned exactly;
- no auto-upgrade;
- no fix of the Pine intended only to satisfy PineTS;
- no base hook launches PineTS;
- no server, MCP, database or dashboard architecture is created;
- behavioural artefacts remain separate from TradingView evidence;
- the integration remains a thin adapter and a skill, not a second platform.

If these constraints cease to be true, the integration must be re-evaluated according to the main gate of §59.

### 59.2 Ratified application — PWS contextual menu

The `pws` skill meets the gate of this section because it covers an explicit UX need: allowing the holder to choose a workflow and its short structured decisions in a Claude Code session without memorizing the direct commands or turning the conversation into a series of repetitive prompts.

The need is covered by a current native primitive, `AskUserQuestion`. The chosen architecture therefore uses this primitive instead of creating an application, an external TUI or a new platform.

This skill is admitted only under the following constraints:

- a single facade skill `pws`;
- no duplicated business logic;
- routing to the existing skills;
- state derived from the deterministic tooling already present;
- no additional database or registry;
- no fragile interactive hook;
- no server, MCP, custom plugin or dashboard;
- no menu-specific persistence except for decisions already provided for by the canonical artefacts;
- possibility of bypassing the menu entirely through the direct commands or the conversation;
- conversational fallback if the native primitive is not available.

Its contextual cost must remain low: short description always visible, skill body loaded only when it is invoked according to the current mechanism of Claude Code skills.

If the menu starts to acquire its own logic, its own storage or a distinct interface runtime, it must be re-evaluated according to the main gate of §59.

---

## 60. BOOTSTRAP — IMPLEMENTATION PHASE

After discovery, extraction, design gate and independent critique:

### 60.1 Build the authorities first

- `standards/PINE_SCRIPT_V6_STANDARD.md`
- move of this bootstrap spec to `docs/architecture/BOOTSTRAP_SPEC.md`

Apply the lifecycle and hash contract of §5; do not keep two ambiguous normative authorities.

### 60.2 Build the index and the traceability

- parse the real headings;
- generate INDEX;
- create TRACEABILITY after complete analysis.

### 60.3 Build the operational architecture

- `CLAUDE.md`
- rules
- skills, including the `pws` skill serving as the native contextual menu
- agents
- settings
- Git files
- tooling
- tests
- `pine-local-test` skill
- `tools/pine_exec` thin adapter
- exactly pinned PineTS dependency + lockfile
- initial calibration of the capabilities, without any obligation to promote a `GATING` capability
- controlled operational learning protocol of `chrome-experimental` in `tv-validate/CHROME_EXPERIMENTAL.md`, without fictitious learning
- architecture docs

Do not create `scripts/<slug>/tests/behavioral/` during the bootstrap if no real product requiring a behavioural contract exists yet.

The per-product behavioural folders remain on demand.

### 60.4 Do not create fake products

The `scripts/` folder may exist empty locally.

Do not create a `.gitkeep`.

Do not create an example script.

### 60.5 TV mode

Create the local settings with `manual`.

---

## 61. BOOTSTRAP SELF-VALIDATION

Before declaring the workspace built:

### 61.1 Syntax

Verify:

- JSON parse;
- YAML frontmatter;
- Markdown structure;
- Python compile;
- local imports.
- valid UTF-8, LF line endings and terminal newline for the canonical documents;
- continuous main headings and balanced code fences;
- all JSON blocks parsable.

### 61.2 Tooling

Run all the tests.

### 61.3 Standard

Verify:

- SHA;
- INDEX;
- TRACEABILITY;
- no unintended modification of the master.

### 61.4 Claude Code

Verify with the appropriate current commands:

- settings loaded;
- `CLAUDE.md` loaded;
- rules detected;
- skills detected;
- agents detected;
- hooks detected;
- `/pws`, `/tv-mode` and the other critical skills resolved to the expected project skills without silent collision;
- native Chrome transport distinguished from any project MCP and absence of a `.mcp.json` created for this transport.

Use in particular the available official diagnostics such as `/context`, `/status`, `/doctor` or their current equivalents.

### 61.5 Hooks

Test the hook scripts directly with fixture JSON inputs.

Then perform a real session restart if necessary to confirm `SessionStart`.

Test the Stop hook on a controlled fixture.

### 61.6 Orphan detection

Temporarily create, in a test space, a fake minimal tree containing an orphan `.pine`.

Verify that it is detected.

Do not leave this fake script in `/scripts`.

### 61.7 Stale validation

Test:

1. a run tied to hash A;
2. source modified to hash B;
3. `validation-status` must produce `STALE`.

Also test:

- `current.json` pointing to a missing or invalid report never produces `passed`;
- each referenced evidence item is verified by its SHA-256;
- an older run cannot atomically replace the more recent current run.

### 61.8 TV mode

Test:

```text
manual
→ chrome-experimental
→ manual
```

without losing the other keys of the local settings.

Test a detectable simulated concurrent modification (occurring before the pre-write re-read) and verify that the controller refuses the overwrite; document the undetectable window of §19.3 as a declared limitation. Confirm that the explicit route `/pws → Maintenance / configuration → Configuration → TradingView mode` calls the shared controller without invoking `Skill(tv-mode)`, while `/tv-mode` remains user-only.

Also verify that `.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md`:

- describes the controlled operational learning protocol of §31.9;
- distinguishes operational knowledge, current observation and validation evidence;
- provides for obsolescence detection and cautious revision;
- invents no landmark, workflow or failure mode presented as actually observed during the bootstrap if it was not.

### 61.9 PWS contextual menu

Verify in a real compatible interactive session:

1. that `.claude/skills/pws/SKILL.md` is detected and invocable through `/pws`;
2. that the skill uses `AskUserQuestion` when this native primitive is available;
3. that each question respects the current limits of the primitive and that the trees do not overload a single screen;
4. that the menu behaves correctly in at least four states: workspace without a product, registered products, presence of an `UNREGISTERED` `.pine`, mixed state with `STALE` validation;
5. that `Retour` (Back) and `Annuler` (Cancel) produce no side effect;
6. that `Nouveau script → Indicator → COMMERCIAL` (New script → Indicator → COMMERCIAL) transmits the expected canonical values (profile and axes) to `pine-new` without creating a product before the final confirmation;
7. that `Nouveau script → Library` (New script → Library) derives FREE with public source, offers no other profile and that the scanner rejects any other combination if it is injected otherwise;
7a. that the "Work on a script" guided path offers the action before the script, displays the explicit identity of the single script, and that the first level never presents a product as the only scope;
8. that an `UNREGISTERED` `.pine` routes to `pine-onboard`;
9. that the development, documentation/tutorial, research, review, audit, local test, TradingView validation, licence and terms of use, publication, GitHub export, diagnostic, tools and archives actions route to the existing skills instead of duplicating their logic, that the structure comes from `menu --json` (labels in the configured language) and that the mode change follows the shared controller;
10. that the menu can be reopened with `/pws` during a session;
11. that a resume, a compact or a clear does not force the reopening of the menu;
12. that `SessionStart` does not attempt to manipulate a TTY or to simulate keystrokes;
13. that a simple conversational fallback exists if `AskUserQuestion` is not available on the current surface.

The self-validation must also confirm the current CLI form of interactive startup with an initial prompt if it is documented in `OPERATIONS.md`.

### 61.10 PineTS

If the PineTS layer has been built, verify:

1. that PineTS is pinned to an exact version;
2. that no floating range is used;
3. that the lockfile matches the declared dependency;
4. that the installed version and artefact come from the npm registry and that their metadata, integrity, licence and lockfile are recorded without deduction from `main` alone;
5. that `license_basis` describes the basis actually used and never claims a commercial licence without applicable local evidence;
6. that the `executor_fingerprint` covers the actually influential execution and normalization artefacts, `package.json`, the exact Node version and the relevant environment facts without secrets;
7. that the runner can execute a minimal deterministic case;
8. that the normalized output is reproducible;
9. that the calibration manifest matches the current triplet `pinets_version + executor_fingerprint + normalization_schema`;
10. that a simulated modification of a case, input, expected result, reference or evidence makes only the calibrations concerned stale and that no arbitrary TTL is applied;
11. that a not yet qualified capability is neither promoted to `GATING` nor declared `UNSUPPORTED` without evidence, and may provisionally remain `EXPERIMENTAL` with `calibration_status = MISSING`;
12. that two sub-capabilities of the same family can receive different statuses when the calibrations justify it, without forced global classification of the family;
13. that a simulated change of `pinets_version`, of `executor_fingerprint` or of `normalization_schema` correctly yields `calibration_status = STALE` without automatically rewriting `capability_status`;
14. that `effective_gating` is false for any capability whose `capability_status != GATING` or `calibration_status != CURRENT`;
15. that the `capabilities_used` of a run prevent a gating conclusion when it materially depends on a capability that is not effectively gating;
16. apply the following conditional test:
    - if at least one capability has legitimately obtained `GATING + CURRENT`, verify that a deliberate violation of a contract resting only on effectively gating capabilities blocks the local cycle without producing or modifying any TradingView status;
    - otherwise, verify the non-gating path and confirm that no capability is artificially promoted to satisfy the self-validation;
17. that the total absence of a `GATING` capability is accepted as a valid result of the bootstrap and explicitly declared;
18. that `PINETS_EXECUTION_PASS` and `PINETS_REGRESSION_CHANGED` can coexist without being treated as an execution failure;
19. that `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` and `PINETS_INCONCLUSIVE` are not turned into a failure of the source;
20. that a deterministic synthetic dataset has a reproducible `dataset_descriptor` and a stable `dataset_sha256`;
21. that an imported OHLCV snapshot fixture can be consumed with explicit provenance and stable hash without requiring a network provider;
22. that a durable baseline has its dataset descriptor, its hashes and its verifiable acceptance evidence or justification;
23. that a small explicit matrix of configurations produces a deterministic manifest and keeps the identity of each elementary run;
24. that no hook of the foundation launches PineTS or a matrix of datasets, parameters or stability probes;
25. that no PineTS execution writes under `validation/`;
26. that the automatable PineTS tests are durably persisted under `tools/tests/` or a justified equivalent factorization and are executed by the test framework already chosen;
27. that the operational documentation distinguishes the terms of PineTS, those of any external data source and those of TradingView according to the actual use.

The bootstrap must never be obliged to produce a `GATING` capability. If one or more capabilities are classified `GATING`, each of those used as a gate must have an independent `CURRENT` calibration compliant with the contract. The absence of an initial local gate is an honest and valid result when the evidence is insufficient.

### 61.11 Physical boundaries and machine contracts

Explicitly verify:

- workspace whose path contains spaces;
- detection of, and stop on, an enclosing parent repository;
- identical operation in the absence of any sibling project and absence of scan or mutation of an arbitrarily named sibling;
- refusal of outgoing traversals and symlinks;
- case-insensitive uniqueness of the IDs/slugs;
- `SCRIPT.json` schema 3 and consistency rules of the axes (§45.4); legacy schemas 1 and 2 read and flagged;
- separation of the `product_structure_status`, `source_registration_status` and validation axes;
- `.claude/worktrees/` ignored;
- Chrome pre-write gate with an ambiguous case that produces `NO WRITE`;
- no temporary test entry or artefact left under `scripts/`.

---

## 62. BOOTSTRAP REPORT

Create:

```text
docs/architecture/BOOTSTRAP_REPORT.md
```

### 62.1 Content

Include:

- date;
- OS;
- Claude Code version;
- Git version;
- chosen local runtime;
- Node.js state;
- exact PineTS version chosen;
- registry/tarball provenance, integrity and metadata of the installed PineTS package;
- `license_basis` actually used and any applicable non-secret reference;
- current `executor_fingerprint`;
- identity of the normalization schema;
- PineTS calibration state;
- explicit declaration when zero capabilities are `GATING`, without presenting this result as a failure of the bootstrap;
- capabilities initially `GATING`, `EXPERIMENTAL` or `UNSUPPORTED`, chosen granularity and freshness of their calibration;
- supported local dataset types, provenance contract and any external source actually configured;
- support or limits of the explicit local matrices;
- current PineTS licence verified and chosen scope of use;
- terms of use applicable to any external data source actually configured and to any TradingView interaction concerned;
- master hash;
- hash of the bootstrap spec;
- mappings of the two input files to their canonical paths with before/after hashes;
- official documentation verified;
- available Claude Code primitives;
- unavailable capabilities;
- Chrome state;
- Git state;
- remotes;
- architecture created;
- specific justification of each file;
- files deliberately not created;
- permissions;
- hooks;
- test results;
- doctor result;
- orphan detection result;
- TradingView mode;
- state and self-validation of the PWS contextual menu;
- limitations;
- points still requiring the holder.

### 62.2 Quality

The report must make it possible to verify that Claude actually designed the environment.

It must not simply list:

```text
Created CLAUDE.md
Created skills
Created agents
```

Each significant choice must have a justification.

---

## 63. INITIAL COMMIT

At the end of the bootstrap:

- display at least `git status --short`;
- display the diff of the already tracked files when it exists;
- inventory the untracked files without staging them solely to fabricate a diff;
- display the useful totals;
- display the remotes;
- explicitly state whether the repository is unborn or identify the current commit;
- display a summary of the diff and of the files created;
- propose an initial commit;
- not create it without the holder's explicit approval.

No push.

---

## 64. BOOTSTRAP COMPLETION CRITERIA

The bootstrap is complete only if all the following statements are true.

### 64.1 Authorities

- the master is canonical and intact;
- the bootstrap spec is kept;
- INDEX matches the master;
- TRACEABILITY matches the master.

### 64.2 Context

- root `CLAUDE.md` is concise;
- no copy of the master is imported into it;
- no configuration or procedure requires the existence, the name, the path or the state of another external project;
- rules are path-scoped;
- skills are not bloated with unnecessary reference content;
- agents have distinct responsibilities.

### 64.3 Tooling

- tooling works;
- tests pass;
- doctor works;
- orphan detection works;
- stale validation works;
- PWS contextual menu detected, routed and self-validated;
- PineTS thin adapter functional or limitation explicitly declared;
- non-floating PineTS version;
- deterministic `executor_fingerprint`;
- calibration consistent with the current `pinets_version`, `executor_fingerprint` and `normalization_schema`;
- no capability used as effectively gating without `capability_status = GATING` and `calibration_status = CURRENT`;
- zero `GATING` capabilities is accepted when the initial evidence is insufficient;
- no broad family of capabilities promoted or condemned on principle when sub-capabilities must be distinguished;
- local datasets hashed and reproducible provenance;
- explicit matrices bounded and traceable when they are supported, without a generic optimizer or automatic hook;
- when a local PineTS gate legitimately exists, it may block locally without ever writing or satisfying a TradingView status;
- physical and semantic separation between `tests/behavioral/` and `validation/`.

### 64.4 Git

- local repo operational;
- no remote created by the bootstrap;
- appropriate local `worktree.baseRef`;
- `.claude/worktrees/` ignored and pre-first-commit limitation documented;
- no push possible implicitly according to the chosen policy.

### 64.5 TradingView

- initial mode `manual`;
- user-only switch operational;
- Chrome experimental clearly separated;
- fallback documented;
- publication out of scope.

### 64.6 Redundancy

- no decorative artefact;
- no product placeholder;
- no central registry;
- no massive duplication of the standard;
- non-competing responsibilities.

### 64.7 Honesty

- no invented TradingView validation;
- no PineTS result presented as TradingView validation;
- no invented Claude Code capability;
- no invented decision of the holder;
- no research allegedly performed without a real source.

---

## 65. CRITERIA FOR COMPLETE ONBOARDING OF AN EXISTING SCRIPT

An existing script is ready to be developed in the workspace when:

- the source has been read in full;
- the product root is stable;
- `SCRIPT.json` is valid;
- the licence profile and its axes are resolved (schema 3);
- `PRODUCT.md` is specific;
- `ARCHITECTURE.md` is specific;
- the local `CLAUDE.md` is specific and concise;
- validation state exists;
- the genuinely undeterminable questions have been put to the holder;
- no decision has been invented;
- no generic file has been created;
- the source has not been modified during onboarding;
- doctor classifies the product as `REGISTERED`.

---

## 66. CRITERIA FOR CORRECT CREATION OF A NEW SCRIPT

A new product has correctly gone through `pine-new` when:

- the objective is clear;
- the audience is clear;
- the `script_kind` is clear;
- the licence profile and its axes are clear;
- the consistency rules of §45.4 are respected, in particular `library → FREE with public source`;
- the current Pine research has been done;
- the relevant open-source / Editors’ Picks benchmark has been done;
- the differentiation is defined;
- the qualitative surpassing target is defined;
- the necessary product decisions have been made;
- the architecture is designed before the code;
- the specific context exists;
- the source has been created according to the master;
- the code is not a disguised adaptation of a reference;
- the local checks pass;
- the applicable PineTS behavioural tests have been executed when the layer has sufficient capabilities;
- the `capabilities_used` and their calibration freshness correctly bound any gating conclusion;
- any actually gating PineTS result has been qualified and may block the local cycle only within the exact limits of its contract;
- any non-gating PineTS status or applicable limitation is declared honestly rather than turned into an artificial failure;
- no local PineTS claim is broadened into a TradingView parity claim without corresponding TradingView evidence;
- the independent review is done;
- the TradingView validation is done before the final declaration.

---

## 67. FLOW EXAMPLE — EXISTING SCRIPT ADDED BY THE HOLDER

```text
the holder
│
├── creates scripts/zigzag-orderblock/
│
└── drops ZigZag OrderBlock Retracement.pine
        │
        ▼
new Claude Code session
        │
        ▼
SessionStart
        │
        ├── scan scripts/**
        └── UNREGISTERED detected
                │
                ▼
pine-onboard
                │
                ├── full read
                ├── mapping
                ├── applicable master analysis
                ├── distribution resolution
                ├── specific PRODUCT.md
                ├── specific ARCHITECTURE.md
                ├── specific local CLAUDE.md
                ├── SCRIPT.json
                └── validation = unverified
                        │
                        ▼
project-doctor
                        │
                        ▼
REGISTERED
```

---

## 68. FLOW EXAMPLE — NEW PRODUCT

```text
new menu-first session or `/pws`
        │
        ▼
PWS contextual menu
        │
        ├── New / import
        ├── New script
        ├── type
        ├── distribution
        └── confirmation
        │
        ▼
The holder describes / clarifies the objective
        │
        ▼
pine-new
        │
        ├── objective / audience / distribution
        ├── current Pine research
        ├── open-source benchmark
        ├── Editors’ Picks
        ├── strengths/weaknesses of the references
        ├── the holder's differentiation
        ├── product design
        ├── architecture
        ├── necessary decisions of the holder
        │
        ▼
creation of the product root
        │
        ├── specific context
        ├── research run
        └── Pine source
                │
                ▼
pine-develop (re-reading §9.2, self-review, diff check;
        │      independent review only at the holder's request)
        ▼
local guard
        │
        ▼
pine-local-test
        │
        ├── execution status separate from the observations
        ├── gating only if capabilities_used effectively gating
        ├── unsupported / experimental / inconclusive → non-blocking
        └── unexpected gating change → analysis / fix / re-run
        │
        ▼
tv-validate
      /     \
 manual   chrome-experimental
            │
            └── fallback manual if necessary
        │
        ▼
validation tied to the exact SHA
```

---

## 69. FLOW EXAMPLE — MODIFICATION OF A SCRIPT

```text
The holder gives the objective
        │
        ▼
product context loaded
        │
        ▼
pine-develop
        │
        ├── classification and level (routine work)
        ├── targeted reading starting from the map
        ├── impact
        ├── current research
        ├── benchmark if relevant
        ├── plan
        ├── editing
        ├── re-reading (§9.2) and diff check
        └── artefact sync
        │
        ▼
guard
        │
        ▼
pine-local-test depending on applicability
        │
        ▼
qualification of the results
        │
        ▼
tv-validate if required
        │
        ▼
final hash proven
```

---

## 70. FLOW EXAMPLE — RELEASE

```text
final source
    │
    ▼
pine-release
    │
    ├── SemVer impact
    ├── applicable artefacts
    ├── current TradingView rules
    ├── release reviewer
    └── pre-release checks
            │
            ├── applicable local behavioural tests
            │       └── qualified gating regressions
            │
            ▼
TradingView validation of the final hash
            │
            ▼
READY FOR HUMAN PUBLICATION
```

The last state is not:

```text
PUBLISHED
```

as long as the holder has not actually finalized or explicitly authorized the publication.

---

## 71. QUALITY RULES FOR THE CONTENT GENERATED BY THE BOOTSTRAP

Each file created must be re-read with these questions:

1. Could this content be copied as is into any repo?
   - If so, it is probably too generic.
2. Which part of the master standard or of the real environment justifies this content?
3. Does this file contain something already present elsewhere?
4. Did Claude write a section only because a document template contained one?
5. Is the content actionable?
6. Can a future Claude know when the file is stale?
7. Can a future Claude know who has authority over this content?
8. Is an inference presented as a fact?
9. Is a Claude Code capability assumed without verification?
10. Could a rule be path-scoped instead of being always-on?

---

## 72. NO "SOPHISTICATION" CLAIM WITHOUT USEFULNESS

The sophistication sought is that of the correct separation of responsibilities.

It is not measured by the number of files.

Preferred architecture:

```text
small core always loaded
+
conditional context
+
on-demand procedures
+
fresh specialized agents
+
mechanical checks
+
real evidence
```

Rejected architecture:

```text
huge CLAUDE.md
+
50 redundant rule files
+
10 overlapping agents
+
database
+
custom orchestrator
+
semantic hooks everywhere
```

---

## 73. OFFICIAL SOURCES TO RE-VERIFY DURING THE BOOTSTRAP

These URLs serve as starting points.

Always verify their current content.

### Claude Code

```text
https://code.claude.com/docs/en/memory
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/hooks
https://code.claude.com/docs/en/tools-reference
https://code.claude.com/docs/en/settings
https://code.claude.com/docs/en/worktrees
https://code.claude.com/docs/en/chrome
https://code.claude.com/docs/en/workflows
```

### TradingView / Pine Script

```text
https://www.tradingview.com/pine-script-docs/
https://www.tradingview.com/pine-script-docs/writing/style-guide/
https://www.tradingview.com/pine-script-docs/writing/publishing/
https://www.tradingview.com/pine-script-docs/writing/limitations/
https://www.tradingview.com/pine-script-docs/concepts/libraries/
https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/
https://www.tradingview.com/support/solutions/43000549951-vendor-requirements/
```

### PineTS upstream

```text
https://github.com/LuxAlgo/PineTS
https://www.npmjs.com/package/pinets
```

Before installation or upgrade, verify the current version, the documentation, the licence, the limitations and the compatibility changes.

---

## 74. STARTING INSTRUCTION TO CLAUDE CODE

When the holder provides this specification with the master standard, start as follows:

> Read this specification and the master standard in full before creating any structure.  
> First verify the current Claude Code and TradingView documentation for the primitives the bootstrap depends on.  
> Also verify the current PineTS upstream before installation: npm registry, exact installable artefact, version, integrity, actually applicable licence, limitations and relevant compatibility.  
> Inspect the real environment.  
> Treat the current folder as the autonomous root of Pine Workspace; do not assume the existence of any sibling project and neither scan nor modify the content of any sibling projects.  
> Build the matrix requirements → context → primitive → check.  
> Mentally propose the architecture, critique it in an independent context, and only then write the files.  
> Each file must have a specific responsibility and content grounded in the standard or the real environment.  
> Do not use any generic template to simulate completeness.  
> Do not add any layer whose usefulness is not demonstrated.  
> After construction, run all the self-tests, the doctor, the freshness checks, the detection of orphan `.pine` files and a non-redundancy pass.  
> Create no remote, no push, no TradingView publication and no commit without the holder's explicit authorization.  
> Finish with `BOOTSTRAP_REPORT.md` and a precise summary of what is ready, experimental, deliberately absent or still to be confirmed.

---

# END OF THE SPECIFICATION

The final workspace must make the right behaviour natural for Claude Code without loading the whole constitution into every context and without creating a second platform around Claude Code.

The PineTS layer respects this principle only as long as it remains a minimal local laboratory, capability-gated, exactly pinned and independently calibrated. It can enforce a precisely bounded local behavioural contract, but remains without normative authority over Pine Script and without authority over the behaviour specific to TradingView or over the `TV_VALIDATED` status.

The objective is:

```text
HOLDER OBJECTIVE
+
CURRENT TRADINGVIEW TECHNICAL TRUTH
+
ONE CANONICAL PINE STANDARD
+
SCRIPT-SPECIFIC CONTEXT
+
ON-DEMAND PROCEDURES
+
FRESH SPECIALIZED REVIEW
+
DETERMINISTIC LOCAL GUARDS
+
CAPABILITY-GATED LOCAL BEHAVIORAL EXECUTION
+
LOCAL GIT
+
REAL TRADINGVIEW VALIDATION
=
A SMARTER, MORE AUTONOMOUS, TRACEABLE PINE DEVELOPMENT WORKSPACE
```

The system must remain able to grow with the number of scripts without degrading:

- precision;
- context;
- maintainability;
- traceability;
- originality;
- the quality of the validations;
- the holder's ability to keep control of the product decisions.
