# Third-party notices and dependency licences

Pine Workspace's own components are under the Apache License 2.0 (the core, see `LICENSE`) and
the GNU AGPL v3 only (the PineTS thin adapter, see `tools/pine_exec/LICENSE`) — see `NOTICE` and
`docs/licensing/LICENSING.md`. The components below are third-party components, **not** covered by
those licences; each keeps its own terms.
The tooling inventories them so that no user has to redo this study (`python3 -m
tools.pws_workspace tooling-status`, `pinets verify`, the doctor's `pinets-license-basis`).

## Runtime dependencies (technical)

| Component | Role in PWS | Licence | How it reaches the user | Status in the distribution |
|---|---|---|---|---|
| Python 3 (standard library) | deterministic tooling | PSF | system interpreter | not shipped |
| Git | local history, worktrees | GPL-2.0 | system binary (optional, degraded mode without it) | not shipped |
| Node.js / npm | runs the PineTS thin adapter; installs PineTS and Vela at installation (`npm ci --ignore-scripts`) | MIT (Node.js), Artistic-2.0 (npm) | system binaries, required for local tests and charts | not shipped |
| Claude Code | the assistant harness (skills, rules, agents, hooks) | Anthropic terms | user's own subscription | not shipped |
| **PineTS** (`pinets` npm package) | local behavioural execution of Pine sources (laboratory only, never a TradingView validation) | **AGPL-3.0-only** (`tools/pine_exec/PINETS_LICENSE`, `PROVENANCE.json`) | installed by the user with `npm ci --ignore-scripts` from the exact pinned version in `tools/pine_exec/package-lock.json` | **not shipped**: only the pin, the lockfile, the licence notice and the thin adapter are distributed |
| **Vela** (`@luxalgo/vela` 0.10.15, LuxAlgo) and `@luxalgo/vela-ui` 0.4.4 | browser chart of the local tests: displays the series computed by PWS (never computes; the PineTS connector `@luxalgo/vela-pinets` is not installed) | **Apache-2.0** (licence field of the locked packages; the installed provenance is `tools/vela_view/PROVENANCE.json`) | installed by the installer into the user's installation with `npm ci --ignore-scripts` from `tools/vela_view/package-lock.json`; the page loads a local copy of `vela.global.min.js` checked by SHA-256 | **not shipped**: only the page script, the pin and the lockfile are distributed |
| Dependencies of Vela (`@zag-js/*`, `@internationalized/*`, `@swc/helpers`, …; 32 packages) | used by `vela-ui` | MIT (30), Apache-2.0 (`@internationalized/number`, `@swc/helpers`) per the lockfile | installed by npm with Vela | not shipped |

### PineTS — engine, adapter and licence stop

`PROVENANCE.json` records `license_basis: AGPL-3.0-only` and `commercial_license_held: false` for
the engine. The distribution of Pine Workspace does **not** ship PineTS: each user installs it from
npm (`npm ci --ignore-scripts`, exact pinned version) under PineTS's own licence. It ships the thin
adapter that uses it — original Pine Workspace code (`tools/pine_exec/runner.mjs`, `normalize.mjs`, `datasets.mjs`, `fingerprint.mjs`, and its package metadata), placed under
the **GNU AGPL v3 only** by decision of the Pine Workspace copyright holder (2026-11-13): official
licence text in `tools/pine_exec/LICENSE`, SPDX identifier and notice in each adapter file — and
the dependency **declaration** (pin + lockfile).

Architecture, as implemented: `runner.mjs` imports PineTS (`await import('pinets')`, inside its run
function) and runs it in its own Node.js process, together with the three adapter modules it
imports. The Apache-2.0 core never loads PineTS: its Python tooling starts adapter programs as
separate processes (the doctor runs `node fingerprint.mjs`; local runs `node runner.mjs …` are started
by the assistant and by the tests) and exchanges files and JSON reports with them. The Apache-2.0
test suite also contains short JavaScript test snippets, run with Node.js, that import adapter
modules (`datasets.mjs`, `normalize.mjs`, `runner.mjs`) into the same process — never PineTS itself.

PineTS's licensor (LuxAlgo) states that PineTS is dual licensed (AGPL 3.0 or a commercial licence)
and that, under AGPL 3.0, an application using PineTS that is distributed or offered as a network
service must also be released under the AGPL 3.0, with its full source code (README and
`LICENSE-COMMERCIAL.md` of https://github.com/LuxAlgo/PineTS, read on 2026-11-13). The adapter is
distributed in source form under AGPL-3.0-only. Whether the Apache-2.0 core forms a single work with
the adapter — its tooling exchanges files and JSON with adapter processes, and its test snippets
import adapter modules into a Node.js process — is a legal question that this notice does not
settle (the FSF considers that the mechanism and the semantics of the communication decide;
command lines and pipes are normally used between separate programs, while modules designed to run
linked together in a shared address space almost surely form one program). Anyone
who redistributes PineTS (with or without Pine Workspace), modifies it, integrates it into a
distributed product or exposes it as a network service must comply with AGPL-3.0-only or hold a
commercial licence; such a change, or any other form of distribution, requires a STOP and a new
licence analysis (spec §24.4.13).

## PINE-WORKSPACE banner — text constants prepared once, nothing shipped

`tools/pws_workspace/banner.py` stores text constants: the three PINE-WORKSPACE variants of the
`banner` subcommand and the fixed "PWS" banner of the /pws menu. The adaptive artistic variants and
the former "Pine-WS" menu banner were rendered **once**, while preparing the module (2026-11-07 and
2026-11-08), with two fonts of the FIGlet distribution: "Standard" (`standard.flf`, Glenn Chappell &
Ian Chai, March 1993, FIGlet release 2.1) for the large PINE-WORKSPACE variant and the former
Pine-WS banner, and "Small" (`small.flf`, Glenn Chappell, April 1993, based on Standard) for the
compact variant, through pyfiglet 1.0.4 (MIT licence, a Python port of FIGlet) reading the official,
unmodified font files. The "PWS" banner (2026-11-14) was composed without running any tool, from
the same "Standard" glyph shapes (P, W, S) joined by that font's horizontal smushing rules. The FIGlet distribution (figlet 2.2.5,
https://github.com/cmatsuoka/figlet) is published under the BSD-3-Clause licence — "Copyright (C)
1991, 1993, 1994 Glenn Chappell and Ian Chai; Copyright (C) 1996, 1997, 1998, 1999, 2000, 2001 John
Cowan; Copyright (C) 2002 Christiaan Keet; Copyright (C) 2011 Claudio Matsuoka. All rights
reserved." — and each font file carries its authors' comment: "Permission is hereby given to modify
this font, as long as the modifier's name is placed on a comment line." Pine Workspace ships **no
font file, no FIGlet and no pyfiglet**, and modifies no font: it only stores the resulting text of
its own name and displays it from constants with the standard library; nothing is downloaded,
imported or generated at run time. These mentions are kept so that the origin of the glyph shapes
stays documented.

## Third-party content studied for Pine scripts

Scripts studied legally (public open-source scripts, Editors' Picks) are studied to understand
concepts and compare behaviours. PWS's default produces an **original implementation**: no
copy-paste, no line-by-line translation, no mere renaming or reformatting of third-party code.
The trace of references studied belongs to the design tracking of the product, never to
automatic credits in the script. Legitimate existing notices in a source are never removed
retroactively by this rule; questions of attribution or licence specific to a product are
handled in that product's own decisions.

## Licence templates and rendered documents

The licence templates under `docs/licensing/templates/` are original texts of Pine Workspace. They
are part of the Apache-2.0 core **and**, in addition, covered by the **Template Permission**
(`docs/licensing/TEMPLATE_PERMISSION.md`): any user may copy, modify, translate and distribute
them, in whole or in part, in the headers, notices, grants, EULAs and other documents of their own
scripts and products, **without adding the Pine Workspace attribution or the Apache License** to
those documents. The permission does not transfer the copyright in the common template text, grants
no exclusive right in it, and leaves third-party licences unchanged. The user holds the rights in
their own additions and remains responsible for the legal content they publish; rendered documents
are not universal legal instruments, and a document with unfilled fields is a flagged DRAFT.
