# SPDX-License-Identifier: Apache-2.0
"""project-doctor deterministic layer (spec section 32).

Aggregates facts from scan/standard/validation/tv_mode/guard — never
re-derives them. Severities: OK, INFO, WARNING, BLOCKING. Every BLOCKING is
actionable. A STALE/MISSING calibration only forbids effective gating; it
never marks a Pine source BROKEN and never replaces TradingView validation.
"""
import json
import os
import re
import subprocess
from pathlib import Path

from . import config, core, scan, session, standard, tv_mode, version

CRITICAL_SKILLS = ("pws", "tv-mode", "tv-validate", "pine-onboard", "pine-new",
                   "pine-develop", "pine-research", "pine-review", "pine-audit",
                   "pine-docs", "pine-local-test", "pine-release", "project-doctor")
FLOATING_RANGE_RE = re.compile(r"^[~^]|^latest$|^\*$|[<>=|x ]")
PINE_EXEC_REL = Path("tools/pine_exec")


def _add(results, check, severity, detail=""):
    results.append({"check": check, "severity": severity, "detail": detail})


def run_doctor(root):
    root = Path(root)
    results = []

    # Physical boundary (spec sections 2.10 / 6.1)
    enclosing = core.find_enclosing_git_root(root)
    if enclosing:
        _add(results, "no-enclosing-repo", "BLOCKING",
             "workspace is enclosed by a parent git repository at %s — stop and ask the holder" % enclosing)
    else:
        _add(results, "no-enclosing-repo", "OK")
    outgoing = _outgoing_symlinks(root)
    if outgoing:
        _add(results, "no-outgoing-symlinks", "BLOCKING",
             "symlink(s) escaping the workspace: %s" % ", ".join(outgoing[:5]))
    else:
        _add(results, "no-outgoing-symlinks", "OK")

    # Standard authorities
    std = standard.standard_status(root)
    if not std["master_present"]:
        _add(results, "master-present", "BLOCKING",
             "standards/PINE_SCRIPT_V6_STANDARD.md missing")
    else:
        _add(results, "master-present", "OK")
    for key, name in (("index", "standard-index"), ("traceability", "traceability")):
        state = std.get(key)
        if state == "CURRENT":
            _add(results, "%s-current" % name, "OK")
        elif state == "STALE":
            _add(results, "%s-current" % name, "WARNING",
                 "%s STALE — regenerate/review against the current master" % name)
        else:
            _add(results, "%s-current" % name, "WARNING", "%s %s" % (name, state))

    # PWS configuration (personal) + TV mode
    cfg = config.read_config(root)
    if cfg["error"]:
        _add(results, "pws-config", "BLOCKING",
             "pws.config.json %s — fix it or recreate it with `init --force`" % cfg["error"])
    elif not cfg["present"]:
        _add(results, "pws-config", "INFO",
             "pws.config.json absent — defaults apply (language en, TradingView mode "
             "manual, identity not configured); run `python3 -m tools.pws_workspace init`")
    elif cfg["problems"]:
        _add(results, "pws-config", "BLOCKING",
             "pws.config.json invalid: %s" % "; ".join(cfg["problems"][:4]))
    else:
        wv = cfg["data"].get("workspace_version")
        if wv != version.WORKSPACE_VERSION:
            _add(results, "pws-config", "WARNING",
                 "configuration recorded for workspace version %r, tooling is %s — run "
                 "`migrate --plan`" % (wv, version.WORKSPACE_VERSION))
        else:
            _add(results, "pws-config", "OK", "workspace version %s" % wv)
        if not config.identity(root)["configured"]:
            _add(results, "identity-configured", "WARNING",
                 "no copyright holder configured — header copyright checks are "
                 "UNVERIFIABLE until `config set identity.copyright_holder \"...\"`")
        else:
            _add(results, "identity-configured", "OK", config.identity(root)["copyright_holder"])
    # Version sources (2026-11-08): version.py is the only source; the CHANGELOG top
    # entry and, in an installation, the installed core manifest must agree with it
    from . import release, upgrade   # local import: keeps the doctor's import graph light
    top = release.changelog_top_version(root)
    installed, _ierr = upgrade.installed_manifest(root)
    if top is None:
        _add(results, "version-sources", "WARNING",
             "CHANGELOG.md missing or without a `## [x.y.z]` entry (tooling %s)" % version.WORKSPACE_VERSION)
    elif top != version.normalized(version.WORKSPACE_VERSION):
        _add(results, "version-sources", "WARNING",
             "CHANGELOG.md top entry %s differs from version.py %s" % (top, version.WORKSPACE_VERSION))
    elif installed is not None and version.normalized(installed["version"]) != version.normalized(version.WORKSPACE_VERSION):
        _add(results, "version-sources", "WARNING",
             "installed core manifest says %s, tooling is %s — upgrade incomplete or manifest stale"
             % (installed["version"], version.WORKSPACE_VERSION))
    else:
        _add(results, "version-sources", "OK",
             "tooling %s, CHANGELOG %s%s" % (version.WORKSPACE_VERSION, top,
                                            (", core manifest %s" % installed["version"]) if installed
                                            else " (development upstream: no core manifest)"))
    mode_detail = tv_mode.read_mode_detail(root)
    if mode_detail["mode"]:
        _add(results, "tv-mode-valid", "OK", "%s (%s)" % (mode_detail["mode"], mode_detail["source"]))
        if mode_detail["source"] == "legacy":
            _add(results, "tv-mode-legacy-key", "INFO",
                 "TradingView mode still read from .claude/settings.local.json env.%s — "
                 "run `migrate --apply` to move it into pws.config.json" % core.TV_MODE_ENV_KEY)
    else:
        _add(results, "tv-mode-valid", "BLOCKING",
             "%s — set it with `python3 -m tools.pws_workspace tv-mode manual`"
             % mode_detail["error"])

    # Scan-based product checks
    s = scan.scan_workspace(root)
    if not s["scripts_dir_exists"]:
        _add(results, "products", "OK", "no scripts/ directory: zero products (valid state)")
    else:
        for p in s["products"]:
            status = p["product_structure_status"]
            sev = {"REGISTERED": "OK", "INCOMPLETE": "WARNING",
                   "BROKEN": "BLOCKING", "AMBIGUOUS": "BLOCKING"}[status]
            detail = status if status == "REGISTERED" else (
                "%s — findings: %s" % (status, "; ".join(
                    "%s(%s)" % (f["code"], f["detail"][:60]) for f in p["findings"][:4])))
            _add(results, "product:%s" % p["slug"], sev, detail)
            eff = p.get("validation_effective_status")
            integ = p.get("validation_integrity_status")
            if integ == "BROKEN":
                _add(results, "validation:%s" % p["slug"], "BLOCKING",
                     "validation integrity BROKEN — effective status unavailable, never 'passed'")
            elif eff == "stale":
                _add(results, "validation:%s" % p["slug"], "WARNING",
                     "TradingView validation stale (source changed since last recognized run)")
    for orphan in s["unregistered_pine"]:
        _add(results, "orphan-pine", "WARNING",
             "%s — run pine-onboard before substantive edits" % orphan)

    # Git facts — absence is a DEGRADED, understandable state (no local
    # history, no worktrees); every other function keeps working.
    g = core.git_state(root)
    if not g["available"]:
        _add(results, "git-available", "WARNING", g["error"] or "git not available on PATH")
    elif not g["is_repo"]:
        _add(results, "git-repo", "WARNING", g["error"] or "workspace is not a git repository")
    else:
        _add(results, "git-repo", "OK",
             "branch %s%s" % (g["branch"], " (unborn)" if g["unborn"] else ""))
        if g["remotes"]:
            _add(results, "git-remotes", "WARNING",
                 "remote(s) present: %s — never push without the holder's explicit decision"
                 % ", ".join(g["remotes"]))
        else:
            _add(results, "git-remotes", "OK", "no remote (local-first)")
        rc, out, _ = core.git(root, "check-ignore", "-q", ".claude/worktrees/probe")
        _add(results, "worktrees-ignored", "OK" if rc == 0 else "WARNING",
             "" if rc == 0 else ".claude/worktrees/ not ignored by git")

    # Settings / hooks
    settings, serr = core.read_json(root / ".claude/settings.json")
    if serr:
        _add(results, "settings-json", "BLOCKING", "settings.json %s" % serr)
    elif not isinstance(settings, dict):
        _add(results, "settings-json", "BLOCKING",
             "settings.json is not a JSON object (got %s) — restore it"
             % type(settings).__name__)
    else:
        _add(results, "settings-json", "OK")
        hooks = settings.get("hooks")
        hooks = hooks if isinstance(hooks, dict) else {}
        for event in ("SessionStart", "Stop"):
            if event in hooks:
                _add(results, "hook-%s" % event.lower(), "OK")
            else:
                _add(results, "hook-%s" % event.lower(), "WARNING",
                     "%s hook not configured" % event)
        wt_obj = settings.get("worktree")
        wt = wt_obj.get("baseRef") if isinstance(wt_obj, dict) else None
        _add(results, "worktree-baseref", "OK" if wt == "head" else "INFO",
             "worktree.baseRef=%r" % wt)

    # Placeholder artifacts (spec section 2.4)
    gitkeeps = list(root.glob("**/.gitkeep"))
    if gitkeeps:
        _add(results, "no-gitkeep", "WARNING",
             ".gitkeep found: %s" % ", ".join(str(x) for x in gitkeeps[:3]))
    else:
        _add(results, "no-gitkeep", "OK")

    # Project-level MCP exclusion (spec section 58)
    if (root / ".mcp.json").exists():
        _add(results, "no-project-mcp", "BLOCKING",
             ".mcp.json present — project MCP servers are excluded without explicit ratification")
    else:
        _add(results, "no-project-mcp", "OK")

    # Skill collision diagnostic (narrow documented boundary exception)
    user_skills = set(core.list_user_skill_names())
    collisions = [n for n in CRITICAL_SKILLS if n in user_skills]
    if collisions:
        _add(results, "skill-collisions", "BLOCKING",
             "personal skills shadow project skills (personal > project): %s — rename or remove "
             "them in ~/.claude/skills" % ", ".join(collisions))
    else:
        _add(results, "skill-collisions", "OK",
             "no personal-skill shadowing; enterprise-level collisions not verifiable from here")

    # Tooling tests presence
    tests = sorted((root / "tools" / "tests").glob("test_*.py"))
    _add(results, "tooling-tests", "OK" if tests else "BLOCKING",
         "%d test files" % len(tests) if tests else "tools/tests missing")

    results.extend(_pinets_checks(root))
    results.extend(_baseline_checks(root))
    return results


BASELINE_REQUIRED_FIELDS = (
    "source_sha256", "dataset_sha256", "dataset_descriptor",
    "normalized_payload_sha256", "pinets_version", "executor_fingerprint",
    "normalization_schema", "configuration", "capabilities_used",
    "acceptance_basis", "accepted_at", "acceptance_evidence_ref",
    "acceptance_rationale",
)
ACCEPTANCE_BASES = ("TRADINGVIEW_VALIDATED_SOURCE", "RICK_EXPLICIT_ACCEPTANCE")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _baseline_problems(product_dir, data):
    """Typed + semantic validation of one baseline (spec 24.4.10).

    Identity fields are NEVER null; the acceptance evidence for a
    TRADINGVIEW_VALIDATED_SOURCE basis must reference an EXISTING file inside
    the product root (a dangling reference is a broken proof — 3rd external
    audit, item 3). Only the fields the spec allows to be non-applicable may
    be null (evidence_ref for RICK basis, rationale for TV basis)."""
    from . import validation as _validation
    problems = []
    for field in BASELINE_REQUIRED_FIELDS:
        if field not in data:
            problems.append("missing field %s" % field)
    if problems:
        return problems
    for field in ("source_sha256", "dataset_sha256", "normalized_payload_sha256",
                  "executor_fingerprint"):
        v = data.get(field)
        if not isinstance(v, str) or not _HEX64.match(v):
            problems.append("%s must be a 64-hex string" % field)
    for field in ("pinets_version", "normalization_schema"):
        v = data.get(field)
        if not isinstance(v, str) or not v:
            problems.append("%s must be a non-empty string" % field)
    if _validation._parse_ts(data.get("accepted_at")) is None:
        problems.append("accepted_at must be RFC 3339 UTC")
    for field in ("dataset_descriptor", "configuration", "capabilities_used"):
        if not isinstance(data.get(field), dict):
            problems.append("%s must be an object (null is not applicable)" % field)
    basis = data.get("acceptance_basis")
    if basis not in ACCEPTANCE_BASES:
        problems.append("acceptance_basis %r not in %s" % (basis, list(ACCEPTANCE_BASES)))
    elif basis == "TRADINGVIEW_VALIDATED_SOURCE":
        # The durable proof of the accepted SHA is a TradingView RUN REPORT —
        # mere existence of some file proves nothing (4th external audit,
        # item 2). The referenced run may be HISTORICAL: it must match the
        # baseline's accepted source_sha256, not the product's current source.
        ref = data.get("acceptance_evidence_ref")
        if not isinstance(ref, str) or not ref:
            problems.append("TRADINGVIEW_VALIDATED_SOURCE requires a non-empty "
                            "acceptance_evidence_ref")
        else:
            ref_path = Path(product_dir) / ref
            if not core.is_within(product_dir, ref_path):
                problems.append("acceptance_evidence_ref escapes the product root")
            elif not ref_path.is_file():
                problems.append("acceptance_evidence_ref %r does not exist — a "
                                "dangling reference is not a durable proof" % ref)
            elif not (ref.startswith("validation/runs/") and ref.endswith(".json")
                      and core.is_within(Path(product_dir) / "validation" / "runs",
                                         ref_path)):
                problems.append("acceptance_evidence_ref %r must reference a "
                                "TradingView run report physically under "
                                "validation/runs/ — the existence of an arbitrary "
                                "file is not a proof of the accepted SHA" % ref)
            else:
                run_report, rerr = core.read_json(ref_path)
                if rerr or not isinstance(run_report, dict):
                    problems.append("referenced run report %s"
                                    % (rerr or "is not a JSON object"))
                else:
                    rp = _validation.validate_run_report(run_report)
                    if rp:
                        problems.append("referenced run report violates the "
                                        "spec-51.4 contract: %s" % "; ".join(rp[:3]))
                    else:
                        if run_report.get("status") != "passed":
                            problems.append("referenced run status is %r — the "
                                            "acceptance basis requires a passed "
                                            "TradingView validation"
                                            % run_report.get("status"))
                        if run_report.get("source_sha256") != data.get("source_sha256"):
                            problems.append("referenced run source_sha256 does not "
                                            "match the baseline's accepted source "
                                            "(the link may be historical, but it "
                                            "must be the SAME sha)")
                        vdir = Path(product_dir) / "validation"
                        for ev in run_report.get("evidence", []):
                            ev_path = vdir / ev["path"]
                            if not core.is_within(vdir, ev_path) or not ev_path.is_file():
                                problems.append("run evidence %r missing or "
                                                "escaping" % ev["path"])
                                break
                            if core.sha256_file(ev_path) != ev["sha256"]:
                                problems.append("run evidence %r hash diverges"
                                                % ev["path"])
                                break
    elif basis == "RICK_EXPLICIT_ACCEPTANCE":
        rationale = data.get("acceptance_rationale")
        if not isinstance(rationale, str) or not rationale:
            problems.append("RICK_EXPLICIT_ACCEPTANCE requires a non-empty "
                            "acceptance_rationale")
    return problems


def _baseline_checks(root):
    """Durable behavioral baselines (spec section 24.4.10): every persisted
    ACCEPTED_BEHAVIORAL_BASELINE must carry its full identity and acceptance
    contract — a malformed baseline could silently support a gate."""
    results = []
    scripts_dir = Path(root) / "scripts"
    if not scripts_dir.is_dir():
        return results
    found = False
    for product_dir in sorted(d for d in scripts_dir.iterdir()
                              if d.is_dir() and not d.is_symlink()):
        bdir = product_dir / "tests" / "behavioral" / "baselines"
        if not bdir.is_dir():
            continue
        for bfile in sorted(bdir.glob("*.json")):
            found = True
            name = "baseline:%s/%s" % (product_dir.name, bfile.name)
            data, err = core.read_json(bfile)
            if err or not isinstance(data, dict):
                _add(results, name, "BLOCKING",
                     "baseline %s — fix or remove it" % (err or "is not a JSON object"))
                continue
            problems = _baseline_problems(product_dir, data)
            if problems:
                _add(results, name, "BLOCKING",
                     "baseline contract violated: %s" % "; ".join(problems[:6]))
            else:
                _add(results, name, "OK")
    if not found:
        _add(results, "behavioral-baselines", "OK",
             "no durable baseline exists (valid state — never created automatically)")
    return results


def _outgoing_symlinks(root):
    out = []
    root = Path(root)
    skip_dirs = {"node_modules", ".git"}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if p.is_symlink() and not core.is_within(root, p):
                out.append(str(p))
    return out


def _pinets_checks(root):
    """PineTS layer. The facts shared with `pinets verify` get the SAME
    severity there and here (audit G-07): an integrity failure of the engine
    (floating pin, lockfile != pin, installed artifact != recorded hash) is
    BLOCKING; an installation or provenance out of step is WARNING; an absent
    engine is INFO — never a defect of a Pine source. Every repair command
    printed is the hardened `npm ci --ignore-scripts`."""
    from . import tooling      # local import: tooling imports this module lazily
    results = []
    pe = Path(root) / PINE_EXEC_REL
    leftovers = tooling.rollback_leftovers(root)
    if leftovers:
        _add(results, "pinets-rollback-leftovers", "WARNING", tooling._leftovers_note(leftovers))
    pkg, perr = core.read_json(pe / "package.json")
    if perr:
        _add(results, "pinets-package", "WARNING",
             "tools/pine_exec/package.json %s — PineTS layer not configured" % perr)
        return results
    if not isinstance(pkg, dict):
        _add(results, "pinets-package", "BLOCKING",
             "package.json is not a JSON object (got %s)" % type(pkg).__name__)
        return results
    deps = pkg.get("dependencies")
    dep = deps.get("pinets") if isinstance(deps, dict) else None
    if not dep:
        _add(results, "pinets-pinned", "WARNING", "no pinets dependency declared")
        return results
    if not isinstance(dep, str):
        _add(results, "pinets-pinned", "BLOCKING",
             "pinets dependency must be an exact version string, got %r" % (dep,))
        return results
    if FLOATING_RANGE_RE.search(dep):
        _add(results, "pinets-pinned", "BLOCKING",
             "pinets version %r is a floating range — pin an exact version" % dep)
    else:
        _add(results, "pinets-pinned", "OK", dep)
    lock, lerr = core.read_json(pe / "package-lock.json")
    if lerr or not isinstance(lock, dict):
        _add(results, "pinets-lockfile", "BLOCKING",
             "package-lock.json %s" % (lerr or "is not a JSON object"))
    else:
        packages = lock.get("packages")
        packages = packages if isinstance(packages, dict) else {}
        entry = packages.get("node_modules/pinets")
        locked = entry.get("version") if isinstance(entry, dict) else None
        if locked == dep:
            _add(results, "pinets-lockfile", "OK", "lockfile matches %s" % dep)
        else:
            _add(results, "pinets-lockfile", "BLOCKING",
                 "lockfile version %r != declared %r" % (locked, dep))
    if not (pe / "node_modules" / "pinets").is_dir():
        _add(results, "pinets-installed", "INFO",
             "node_modules absent after an interrupted rollback — see pinets-rollback-leftovers"
             if leftovers else
             "node_modules absent (fresh checkout or worktree) — run %s; never a defect of any "
             "Pine source" % tooling.NPM_CI)
    else:
        inst, ierr = core.read_json(pe / "node_modules" / "pinets" / "package.json")
        installed = inst.get("version") if isinstance(inst, dict) else None
        if ierr or installed != dep:
            _add(results, "pinets-installed", "WARNING",
                 "installed version %r != pinned %r — reinstall from the lockfile: %s"
                 % (installed, dep, tooling.NPM_CI))
        else:
            _add(results, "pinets-installed", "OK", installed)

    prov, prerr = core.read_json(pe / "PROVENANCE.json")
    if prerr or not isinstance(prov, dict):
        _add(results, "pinets-provenance", "WARNING",
             "PROVENANCE.json %s" % (prerr or "is not a JSON object"))
    else:
        lic = prov.get("license")
        lic = lic if isinstance(lic, dict) else {}
        basis = lic.get("license_basis") or prov.get("license_basis")
        if not isinstance(basis, str):
            basis = None
        if basis:
            _add(results, "pinets-license-basis", "OK", basis)
        else:
            _add(results, "pinets-license-basis", "WARNING", "license_basis not recorded")
        # Identity of the engine ACTUALLY installed (audit 2026-11-06 item 5):
        # the declared version number is not enough — the installed artifact
        # hash recorded at installation must still match the file on disk.
        art = prov.get("installed_artifact")
        if not isinstance(art, dict) or not isinstance(art.get("path"), str) \
                or not isinstance(art.get("sha256"), str):
            _add(results, "pinets-installed-artifact", "INFO",
                 "PROVENANCE.json has no structured installed_artifact {path, sha256} — "
                 "engine identity verified by version/lockfile only; `pinets verify` "
                 "records it")
        else:
            apath = pe / art["path"]
            if not (pe / "node_modules" / "pinets").is_dir():
                _add(results, "pinets-installed-artifact", "INFO",
                     "node_modules absent — artifact identity checked after `npm ci --ignore-scripts` "
                     "(declared limitation, never a defect of a Pine source)")
            elif not core.is_within(pe, apath) or not apath.is_file():
                _add(results, "pinets-installed-artifact", "WARNING",
                     "installed artifact %r missing although node_modules exists — reinstall from the "
                     "lockfile: %s" % (art["path"], tooling.NPM_CI))
            elif core.sha256_file(apath) != art["sha256"]:
                # integrity failure, BLOCKING like `pinets verify` (same fact, same severity)
                _add(results, "pinets-installed-artifact", "BLOCKING",
                     "installed artifact %r differs from the hash recorded at "
                     "installation — the engine on disk is not the one that was installed "
                     "and calibrated; reinstall it from the lockfile (%s) or restore a "
                     "verified point (`pinets rollback <point> --yes`), then `pinets verify`"
                     % (art["path"], tooling.NPM_CI))
            else:
                _add(results, "pinets-installed-artifact", "OK", art["path"])
        if isinstance(prov.get("pinned_version"), str) and prov["pinned_version"] != dep:
            _add(results, "pinets-provenance-pin", "WARNING",
                 "PROVENANCE pinned_version %r != package.json %r — provenance not updated"
                 % (prov["pinned_version"], dep))

    calib, cerr = core.read_json(pe / "calibration" / "capabilities.json")
    if cerr or not isinstance(calib, dict):
        _add(results, "pinets-calibration", "WARNING",
             "calibration manifest %s" % (cerr or "is not a JSON object"))
        return results
    caps = calib.get("capabilities", {})
    if not isinstance(caps, dict):
        _add(results, "pinets-calibration", "WARNING",
             "capabilities must be an object, got %s" % type(caps).__name__)
        return results
    malformed = [k for k, v in caps.items() if not isinstance(v, dict)]
    if malformed:
        _add(results, "pinets-calibration", "WARNING",
             "malformed capability entries (not objects): %s" % ", ".join(malformed))
        caps = {k: v for k, v in caps.items() if isinstance(v, dict)}
    if any("effective_gating" in (v or {}) for v in caps.values()):
        _add(results, "no-persisted-effective-gating", "BLOCKING",
             "effective_gating persisted in calibration manifest — it must stay derived")
    else:
        _add(results, "no-persisted-effective-gating", "OK")
    gating_not_current = [k for k, v in caps.items()
                          if v.get("capability_status") == "GATING"
                          and v.get("calibration_status") != "CURRENT"]
    if gating_not_current:
        _add(results, "gating-calibration-current", "WARNING",
             "GATING without CURRENT calibration (cannot be effectively gating): %s"
             % ", ".join(gating_not_current))
    else:
        _add(results, "gating-calibration-current", "OK")
    env = calib.get("environment", {})
    if not isinstance(env, dict):
        env = {}
    if env.get("pinets_version") != dep:
        _add(results, "calibration-env-version", "WARNING",
             "calibration pinets_version %r != pinned %r — calibrations for the old identity are stale"
             % (env.get("pinets_version"), dep))
    else:
        _add(results, "calibration-env-version", "OK")

    # Case/expected/reference artifact integrity feeds the OPERATIONAL
    # freshness (audit F6b): a diverging artifact makes the calibrations that
    # rely on it STALE — the runner derives the same per run.
    artifacts = calib.get("case_artifacts", {})
    failures = []
    if isinstance(artifacts, dict):
        for name, art in artifacts.items():
            if not isinstance(art, dict) or not isinstance(art.get("path"), str) \
                    or not isinstance(art.get("sha256"), str):
                failures.append("%s (malformed entry)" % name)
                continue
            path = pe / "calibration" / art["path"]
            if not core.is_within(pe / "calibration", path) or not path.is_file():
                failures.append("%s (missing or escaping)" % name)
            elif core.sha256_file(path) != art["sha256"]:
                failures.append("%s (hash diverges)" % name)
    else:
        failures.append("case_artifacts must be an object")
    if failures:
        _add(results, "calibration-artifact-integrity", "WARNING",
             "calibration artifacts diverge — the calibrations relying on them are "
             "STALE until recalibration: %s" % "; ".join(failures[:5]))
    else:
        _add(results, "calibration-artifact-integrity", "OK")

    # Provenance invariant (targeted review 2026-09-06): a case SOURCE file
    # must never be stamped as an independent reference, and every CURRENT
    # capability must draw on at least one non-.pine artifact carrying
    # reference_provenance (spec 24.4.5).
    prov_problems = []
    if isinstance(artifacts, dict):
        for name, art in artifacts.items():
            if isinstance(art, dict) and isinstance(art.get("path"), str) \
                    and art["path"].endswith(".pine") \
                    and art.get("reference_provenance"):
                prov_problems.append("%s: a .pine case source cannot carry "
                                     "reference_provenance" % name)
        for cap, entry in caps.items():
            if entry.get("calibration_status") != "CURRENT":
                continue
            ev = entry.get("evidence_artifacts")
            ok = isinstance(ev, list) and any(
                isinstance(artifacts.get(n), dict)
                and artifacts[n].get("reference_provenance")
                and not str(artifacts[n].get("path", "")).endswith(".pine")
                for n in ev)
            if not ok:
                prov_problems.append("%s: CURRENT without a non-.pine independent "
                                     "reference in evidence_artifacts" % cap)
    if prov_problems:
        _add(results, "calibration-reference-provenance", "WARNING",
             "; ".join(prov_problems[:4]))
    else:
        _add(results, "calibration-reference-provenance", "OK")

    fp = _current_fingerprint(pe)
    if fp is None:
        _add(results, "calibration-env-fingerprint", "INFO",
             "Node unavailable or fingerprint not computable here — declared limitation, not an error")
    elif fp != env.get("executor_fingerprint"):
        _add(results, "calibration-env-fingerprint", "WARNING",
             "current executor_fingerprint differs from the calibrated one — "
             "capabilities relying on the old identity are STALE until recalibration")
    else:
        _add(results, "calibration-env-fingerprint", "OK")
    return results


def _current_fingerprint(pine_exec_dir):
    try:
        proc = subprocess.run(
            ["node", str(Path(pine_exec_dir) / "fingerprint.mjs")],
            capture_output=True, text=True, timeout=60,
            env={"PATH": os.environ.get("PATH", ""), "TZ": "UTC",
                 "LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout).get("executor_fingerprint")
    except ValueError:
        return None
