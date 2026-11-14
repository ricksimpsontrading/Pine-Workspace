# SPDX-License-Identifier: Apache-2.0
"""Integrated tools — PineTS lifecycle (status, verify, check-update,
install, rollback, recalibration plan).

Rules (ratified 2026-11-06): no silent update at startup; `check-update`
is an explicit network call that never installs; `install` runs only with
`--yes`, backs up the current engine first, re-pins exactly, checks that the
engine on disk IS the target (pin, lockfile, node_modules, artifact) before
refreshing PROVENANCE and marking every dependent calibration STALE (CURRENT
is never GATING by itself, and a new engine identity is never calibrated by
inheritance); `rollback` restores a VERIFIED saved engine point in two stages
(validation of the whole point before any write, then atomic renames and a
final verification — see `rollback`); `recalibrate`
produces the guided plan — calibration itself stays an explicit, reviewed
act (spec section 24.4). TradingView remains the validation authority;
PineTS is a local laboratory; no indicator is ever modified to satisfy an
engine divergence.

Identity of the engine actually executed = exact pin + lockfile version +
registry integrity + SHA-256 of the installed artifact + executor
fingerprint — never the declared version number alone. `verify`, the doctor
and `tooling-status` give the same fact the same reading: an installed
artifact that differs from the recorded hash is an integrity failure
(BLOCKING), never a CURRENT engine.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import core, restore
from .version import compare as _compare_versions, is_prerelease as _is_prerelease, \
    parse_version as _parse_version

PINE_EXEC_REL = Path("tools/pine_exec")
ROLLBACK_REL = core.RUNTIME_REL / "pinets-rollback"
ARTIFACT_REL = "node_modules/pinets/dist/pinets.min.es.js"
EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
ENGINE_FILES = ("package.json", "package-lock.json", "PROVENANCE.json",
                "calibration/capabilities.json")
# result of the last EXPLICIT update check (network), reused with its date by
# the Tools menu — without it, whether a newer version exists is unknown
UPDATE_CHECK_REL = core.RUNTIME_REL / "tooling" / "last-update-check.json"
# the only repair command the tooling ever prints: a clean install from the
# lockfile with dependency scripts disabled (INSTALL.md, install.py)
NPM_CI = "`npm ci --ignore-scripts` in tools/pine_exec"
ROLLBACK_TREE_REFUSED = ("%s (or one of its parent folders) is a symbolic link or leaves the workspace: "
                         "rollback points are neither listed, written nor restored through it" % ROLLBACK_REL)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd, cwd=None, timeout=120):
    """Run a command; never raises (returns rc 127 when the binary is missing)."""
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                              text=True, timeout=timeout,
                              env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
                                   "TZ": "UTC", "LANG": "C", "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _tool_version(binary):
    rc, out, _ = _run([binary, "--version"], timeout=20)
    return out if rc == 0 else None


def _pe(root):
    return Path(root) / PINE_EXEC_REL


def engine_identity(root):
    """Facts about the engine on disk (no network)."""
    pe = _pe(root)
    pkg, perr = core.read_json(pe / "package.json")
    lock, lerr = core.read_json(pe / "package-lock.json")
    prov, prerr = core.read_json(pe / "PROVENANCE.json")
    calib, cerr = core.read_json(pe / "calibration" / "capabilities.json")
    inst, ierr = core.read_json(pe / "node_modules" / "pinets" / "package.json")
    pinned = None
    if isinstance(pkg, dict) and isinstance(pkg.get("dependencies"), dict):
        pinned = pkg["dependencies"].get("pinets")
    locked_version = locked_integrity = None
    if isinstance(lock, dict) and isinstance(lock.get("packages"), dict):
        entry = lock["packages"].get("node_modules/pinets")
        if isinstance(entry, dict):
            locked_version = entry.get("version")
            locked_integrity = entry.get("integrity")
    artifact = pe / ARTIFACT_REL
    artifact_sha = core.sha256_file(artifact) if artifact.is_file() else None
    env = (calib or {}).get("environment") if isinstance(calib, dict) else None
    env = env if isinstance(env, dict) else {}
    caps = (calib or {}).get("capabilities") if isinstance(calib, dict) else None
    caps = caps if isinstance(caps, dict) else {}
    return {
        "pinned_version": pinned if isinstance(pinned, str) else None,
        "package_error": perr,
        "locked_version": locked_version,
        "locked_integrity": locked_integrity,
        "lock_error": lerr,
        "installed_version": inst.get("version") if isinstance(inst, dict) else None,
        "installed": (pe / "node_modules" / "pinets").is_dir(),
        "installed_artifact": {"path": ARTIFACT_REL, "sha256": artifact_sha},
        "provenance": prov if isinstance(prov, dict) else None,
        "provenance_error": prerr,
        "calibration_environment": env,
        "calibration_error": cerr,
        "capabilities": {k: {"capability_status": v.get("capability_status"),
                             "calibration_status": v.get("calibration_status")}
                         for k, v in caps.items() if isinstance(v, dict)},
    }


def _current_fingerprint(root):
    from . import doctor
    return doctor._current_fingerprint(_pe(root))


def _artifact_state(ident):
    """Live reading of the installed artifact against the hash recorded in
    PROVENANCE — one rule for `verify`, `tooling-status` (and the doctor's
    severities): `not-installed` (node_modules/pinets absent), `missing`
    (node_modules/pinets present, artifact absent), `not-recorded`, `match`
    or `differs`. Returns (state, actual sha256, recorded sha256)."""
    prov = ident["provenance"] or {}
    rec = prov.get("installed_artifact")
    recorded = rec.get("sha256") if isinstance(rec, dict) and isinstance(rec.get("sha256"), str) else None
    actual = ident["installed_artifact"]["sha256"]
    if not ident["installed"]:
        state = "not-installed"
    elif actual is None:
        state = "missing"
    elif recorded is None:
        state = "not-recorded"
    else:
        state = "match" if recorded == actual else "differs"
    return state, actual, recorded


ARTIFACT_CHECK_NOTES = {
    "match": "installed artifact hashed now: equal to the hash recorded in PROVENANCE.json",
    "differs": ("installed artifact hashed now: DIFFERENT from the hash recorded in PROVENANCE.json — the "
                "engine on disk is not the one installed and calibrated (`pinets verify`: BLOCKING); reinstall "
                "it from the lockfile (%s) or restore a verified point" % NPM_CI),
    "not-recorded": ("installed artifact hashed now, but PROVENANCE.json records no hash to compare it with — "
                     "identity by version only until `pinets verify --record`"),
    "missing": ("node_modules/pinets is present but the artifact %s is missing — reinstall from the "
                "lockfile (%s)" % (ARTIFACT_REL, NPM_CI)),
    "not-installed": ("engine not installed here (node_modules/pinets absent): nothing to compare — "
                      "install it with %s" % NPM_CI),
}
VERIFIED_AT_NOTE = ("date written in PROVENANCE.json by whoever recorded that file (shipped as is with a "
                    "distribution, reset to null by `pinets install`, updated by no command): it is NOT a "
                    "verification performed on this machine — the integrity of the installed engine is "
                    "`artifact_check`, computed by this command")
FRESHNESS_BASIS = ("derived here from the calibrated environment against the pin, the installed version, the "
                   "installed artifact (compared with PROVENANCE) and the executor fingerprint; the runner "
                   "derives the freshness of each run from the triplet pinets_version + executor_fingerprint + "
                   "normalization_schema and the calibration artifacts — it does not compare the installed "
                   "artifact")


def _freshness(ident, env, fp, art_state, leftovers):
    """Calibration freshness as displayed by the Tools menu: CURRENT only for
    an installed engine whose version, artifact and executor fingerprint all
    match what was calibrated (audit G-07) — never for an absent engine or an
    artifact that is not the recorded one."""
    pin = ident["pinned_version"]
    if not (env.get("pinets_version") and pin):
        return "unknown"
    if env.get("pinets_version") != pin:
        return "STALE (engine version differs from the calibrated one)"
    if art_state == "not-installed":
        return ("unknown (engine not installed%s: nothing executes here, so the calibration cannot be "
                "called CURRENT)" % (" — interrupted rollback, see rollback_leftovers" if leftovers else ""))
    if ident["installed_version"] != pin:
        return "STALE (installed engine version %r differs from the pin)" % (ident["installed_version"],)
    if art_state == "missing":
        return "unknown (installed artifact missing: the engine cannot execute as installed)"
    if art_state == "differs":
        return ("STALE (installed artifact differs from the hash recorded in PROVENANCE: the engine on disk "
                "is not the one installed and calibrated)")
    if fp and env.get("executor_fingerprint") and fp != env.get("executor_fingerprint"):
        return "STALE (executor fingerprint differs from the calibrated one)"
    if fp is None:
        return "unknown (fingerprint not computable here)"
    if art_state == "not-recorded":
        return ("CURRENT (triplet matches the calibrated environment; installed artifact not recorded in "
                "PROVENANCE — identity by version only)")
    return "CURRENT (triplet matches the calibrated environment; installed artifact matches the recorded hash)"


def status(root):
    """Read-only consolidated view for the Tools menu."""
    ident = engine_identity(root)
    fp = _current_fingerprint(root)
    env = ident["calibration_environment"]
    caps = ident["capabilities"]
    gating = sum(1 for v in caps.values() if v["capability_status"] == "GATING")
    current = sum(1 for v in caps.values() if v["calibration_status"] == "CURRENT")
    art_state, art_actual, art_recorded = _artifact_state(ident)
    leftovers = rollback_leftovers(root)
    freshness = _freshness(ident, env, fp, art_state, leftovers)
    prov = ident["provenance"] or {}
    tree_ok = _rollback_tree_ok(root)
    points = list_rollback_points(root)          # empty when the rollback tree is refused
    return {
        "node": _tool_version("node"), "npm": _tool_version("npm"),
        "pinets": {
            "pinned": ident["pinned_version"], "locked": ident["locked_version"],
            "installed": ident["installed_version"],
            "installed_artifact_sha256": art_actual,
            "recorded_artifact_sha256": art_recorded,
            # integrity read NOW on this machine (not a recorded date)
            "artifact_check": art_state,
            "artifact_check_note": ARTIFACT_CHECK_NOTES[art_state],
            "license_basis": ((prov.get("license") or {}).get("license_basis")
                              if isinstance(prov.get("license"), dict) else None),
            "provenance_pinned": prov.get("pinned_version") if isinstance(prov.get("pinned_version"), str) else None,
            "provenance_verified_at": prov.get("verified_at"),
            "provenance_verified_at_note": VERIFIED_AT_NOTE,
            "previous_pin": ((prov.get("provenance") or {}).get("previous_pin")
                             if isinstance(prov.get("provenance"), dict) else None),
        },
        "calibration": {"environment": env, "capabilities": len(caps), "gating": gating,
                        "current": current, "freshness": freshness, "freshness_basis": FRESHNESS_BASIS,
                        "current_fingerprint": fp},
        # local state above; update availability below comes ONLY from an
        # explicit, dated check — never from the installed version alone
        "update_check": read_update_check(root, ident["pinned_version"]),
        "rollback_points": points,
        "rollback_points_usable": [p["version"] for p in points if p["usable"]],
        "rollback_tree_refused": None if tree_ok else ROLLBACK_TREE_REFUSED,
        "rollback_leftovers": leftovers,
        "rollback_leftovers_note": _leftovers_note(leftovers) if leftovers else None,
        "other_tools": {
            "pinets-cli": "not installed — optional interface to compare with the existing runner (documented only)",
            "vela": "not installed — optional local preview (documented only)",
            "edge-stats": "not installed — statistical research (documented only)",
            "luxalgo-mcp": "not installed — future need to justify (spec §59 gate)",
        },
        "rules": ["no silent update at startup", "install only with --yes",
                  "update ⇒ dependent calibrations STALE", "CURRENT is never GATING by itself",
                  "TradingView remains the validation authority"],
    }


def verify(root, record=False):
    """Integrity + identity findings. With record=True, writes the installed
    artifact hash into PROVENANCE.json when it was not recorded yet (never
    overwrites a recorded hash). Severities are those of the doctor for the
    same facts: integrity failures (lockfile, registry integrity, installed
    artifact) BLOCKING; provenance or installation out of step WARNING; an
    absent engine INFO (never a defect of a Pine source)."""
    ident = engine_identity(root)
    findings = []
    leftovers = rollback_leftovers(root)

    def add(check, status_, detail=""):
        findings.append({"check": check, "status": status_, "detail": detail})

    pin = ident["pinned_version"]
    if not pin:
        add("pin", "BLOCKING", "no exact pinets pin in package.json")
        if leftovers:
            add("rollback-leftovers", "WARNING", _leftovers_note(leftovers))
        return findings
    if not EXACT_VERSION_RE.match(pin):
        add("pin", "BLOCKING", "pin %r is not an exact version" % pin)
    else:
        add("pin", "OK", pin)
    if ident["locked_version"] == pin:
        add("lockfile", "OK", "lockfile version matches the pin")
    else:
        add("lockfile", "BLOCKING", "lockfile version %r != pin %r" % (ident["locked_version"], pin))
    prov = ident["provenance"] or {}
    reg_int = (prov.get("provenance") or {}).get("registry_integrity") \
        if isinstance(prov.get("provenance"), dict) else None
    if reg_int and ident["locked_integrity"]:
        if reg_int == ident["locked_integrity"]:
            add("registry-integrity", "OK", "lockfile integrity equals the recorded registry integrity")
        else:
            add("registry-integrity", "BLOCKING",
                "lockfile integrity differs from the registry integrity recorded in PROVENANCE")
    else:
        add("registry-integrity", "INFO", "registry integrity not comparable (missing in provenance or lockfile)")
    # the provenance must describe the pinned engine (audit G-04) — same reading as the doctor
    if ident["provenance"] is None:
        add("provenance", "WARNING", "PROVENANCE.json %s — the installed engine cannot be related to a "
            "recorded provenance" % (ident["provenance_error"] or "is not a JSON object"))
    elif not isinstance(prov.get("pinned_version"), str):
        add("provenance-pin", "INFO", "PROVENANCE.json records no pinned_version")
    elif prov["pinned_version"] != pin:
        add("provenance-pin", "WARNING",
            "PROVENANCE pinned_version %r != pin %r — the provenance (registry integrity, artifact hash) does "
            "not describe the pinned engine: provenance not updated" % (prov["pinned_version"], pin))
    else:
        add("provenance-pin", "OK", "PROVENANCE describes the pinned version")
    if not ident["installed"]:
        add("installed", "INFO", "node_modules absent after an interrupted rollback — see rollback-leftovers"
            if leftovers else "node_modules absent — run %s (never a defect of a Pine source)" % NPM_CI)
    elif ident["installed_version"] != pin:
        add("installed", "WARNING", "installed version %r != pin %r — reinstall from the lockfile: %s"
            % (ident["installed_version"], pin, NPM_CI))
    else:
        add("installed", "OK", ident["installed_version"])
    state, actual, recorded = _artifact_state(ident)
    if state == "not-installed":
        add("installed-artifact", "INFO", "artifact %s not present (engine not installed) — identity checked "
            "after %s" % (ARTIFACT_REL, NPM_CI))
    elif state == "missing":
        add("installed-artifact", "WARNING", "artifact %s missing although node_modules/pinets exists — "
            "reinstall from the lockfile: %s" % (ARTIFACT_REL, NPM_CI))
    elif state == "not-recorded":
        if record:
            r = _record_artifact(root, actual)
            add("installed-artifact", "OK" if r["ok"] else "WARNING",
                "recorded now: %s" % actual if r["ok"] else r["error"])
        else:
            add("installed-artifact", "INFO",
                "artifact sha256 %s not recorded in PROVENANCE — run `pinets verify --record`" % actual)
    elif state == "match":
        add("installed-artifact", "OK", actual)
    else:
        add("installed-artifact", "BLOCKING",
            "installed artifact sha256 %s differs from the recorded %s — the engine on disk "
            "is not the one that was installed/calibrated; reinstall it from the lockfile (%s) or restore a "
            "verified point (`pinets rollback <point> --yes`), then `pinets verify`" % (actual, recorded, NPM_CI))
    if leftovers:
        add("rollback-leftovers", "WARNING", _leftovers_note(leftovers))
    env = ident["calibration_environment"]
    fp = _current_fingerprint(root)
    if env.get("pinets_version") != pin:
        add("calibration-version", "WARNING",
            "calibrated pinets_version %r != pin %r — calibrations STALE" % (env.get("pinets_version"), pin))
    else:
        add("calibration-version", "OK")
    if fp is None:
        add("fingerprint", "INFO", "fingerprint not computable (Node unavailable)")
    elif fp == env.get("executor_fingerprint"):
        add("fingerprint", "OK", fp)
    else:
        add("fingerprint", "WARNING", "executor fingerprint differs from the calibrated one — STALE")
    stale_persisted = [k for k, v in ident["capabilities"].items()
                       if v["calibration_status"] not in ("CURRENT", "STALE", "MISSING")]
    if stale_persisted:
        add("calibration-statuses", "WARNING", "unexpected calibration_status: %s" % ", ".join(stale_persisted))
    return findings


def _record_artifact(root, sha):
    pe = _pe(root)
    path = pe / "PROVENANCE.json"
    prov, err = core.read_json(path)
    if err or not isinstance(prov, dict):
        return {"ok": False, "error": "PROVENANCE.json %s" % (err or "invalid")}
    if isinstance(prov.get("installed_artifact"), dict) and prov["installed_artifact"].get("sha256"):
        return {"ok": False, "error": "installed_artifact already recorded — never overwritten by verify"}
    prov["installed_artifact"] = {"path": ARTIFACT_REL, "sha256": sha, "recorded_at": _now(),
                                  "note": "recorded by `pinets verify --record` from the artifact on disk"}
    core.atomic_write_json(path, prov)
    return {"ok": True}


def _usable_version(value):
    """An exact npm version (MAJOR.MINOR.PATCH[-pre]) that can be compared, else None."""
    if isinstance(value, str) and EXACT_VERSION_RE.match(value) and _parse_version(value) is not None:
        return value
    return None


def _availability(latest, pinned):
    """(result, update_available, note) of the version published under the
    `latest` tag against the pin — numeric SemVer comparison, never a string
    inequality (audit G-01): only a STABLE version strictly newer than the pin
    is an update; a version older than the pin is never one; a pre-release is
    never proposed by default (installing one stays an explicit choice)."""
    cmp = _compare_versions(latest, pinned) if _usable_version(pinned) else None
    if cmp is None:
        return ("not-comparable", None,
                "the current pin %r is not an exact version: whether %s is newer cannot be decided"
                % (pinned, latest))
    if cmp < 0:
        return ("ahead", False,
                "the pin %s is newer than the version published under the `latest` tag (%s): not an update — "
                "a version older than the pin is never proposed" % (pinned, latest))
    if cmp == 0:
        return ("up-to-date", False, "the `latest` tag designates the pinned version %s" % pinned)
    if _is_prerelease(latest):
        return ("prerelease", False,
                "the `latest` tag designates a pre-release (%s): never proposed by default — installing it "
                "would be an explicit choice (`pinets install %s --yes`)" % (latest, latest))
    return ("update-available", True,
            "a newer stable version is published (%s, pin %s); nothing installed — choose it explicitly with "
            "`pinets install %s --yes`" % (latest, pinned, latest))


_PIN_UNSET = object()


def read_update_check(root, pinned=_PIN_UNSET):
    """Last explicit update check, if one was recorded (never a guess). The
    dated answer is RE-EVALUATED against the pin in force now (audit G-03):
    after `pinets install` or `pinets rollback`, `update_available` describes
    the current pin, and `pinned_at_check` tells which pin the search was made
    for. A record without a usable version (edited, or written by an earlier
    tool) is reported UNKNOWN — never "no update"."""
    path = Path(root) / UPDATE_CHECK_REL
    data = None
    if core.runtime_tree_is_real(root, UPDATE_CHECK_REL.parts) and path.is_file():
        data, _ = core.read_json(path)
    if pinned is _PIN_UNSET:
        pinned = engine_identity(root)["pinned_version"]
    if isinstance(data, dict) and data.get("checked_at"):
        checked_at, at_check = data.get("checked_at"), data.get("pinned")
        latest = _usable_version(data.get("latest"))
        published = data.get("latest_published_at")
        out = {"checked_at": checked_at, "latest": latest, "latest_is_prerelease": None,
               "latest_published_at": published if isinstance(published, str) else None,
               "pinned_at_check": at_check, "pinned_now": pinned}
        if latest is None:
            out.update(result="unknown", update_available=None,
                       note="the explicit check dated %s recorded no usable version — whether a newer version "
                            "exists is UNKNOWN; run `pinets check-update` (network) for a fresh answer" % checked_at)
            return out
        res, available, why = _availability(latest, pinned)
        reuse = ("result of an explicit check dated %s, reused with its date and re-evaluated against the "
                 "current pin %s" % (checked_at, pinned))
        if at_check != pinned:
            reuse += " (the search was made while the pin was %s)" % at_check
        out.update(latest_is_prerelease=_is_prerelease(latest), result=res, update_available=available,
                   note="%s: %s — run `pinets check-update` (network) for a fresh answer" % (reuse, why))
        return out
    return {"checked_at": None, "latest": None, "latest_is_prerelease": None, "latest_published_at": None,
            "pinned_at_check": None, "pinned_now": pinned, "result": "not-searched", "update_available": None,
            "note": "no explicit check recorded — whether a newer version exists is UNKNOWN until "
                    "`pinets check-update` (network) is run; the installed version is not known to be the latest"}


def check_update(root, runner=None):
    """Explicit network query of the npm registry. Never installs; records
    the dated result so the Tools menu can reuse it honestly. Only an object
    carrying an exact, comparable `version` is a result (audit G-02): an npm
    error, a non-JSON output, another JSON shape or a missing/unusable version
    is an error — nothing recorded (a previous dated result stays as it was),
    never "no update"."""
    ident = engine_identity(root)
    pinned = ident["pinned_version"]
    run = runner or _run

    def failed(message):
        return {"ok": False, "error": message, "pinned": pinned, "latest": None, "result": "error",
                "update_available": None, "checked_at": None, "recorded": None,
                "note": "the search failed: whether a newer version exists is still UNKNOWN (nothing "
                        "recorded; a previous dated result, if any, is unchanged)"}

    rc, out, err = run(["npm", "view", "pinets", "version", "dist-tags", "time", "--json"], timeout=60)
    if rc != 0:
        return failed("npm view failed: %s" % (err or out)[:300])
    try:
        data = json.loads(out)
    except ValueError:
        return failed("npm view returned non-JSON output")
    if not isinstance(data, dict):
        return failed("npm view returned JSON of an unexpected shape (%s, expected an object)"
                      % type(data).__name__)
    latest = _usable_version(data.get("version"))
    if latest is None:
        return failed("npm view returned no usable `version` (%s is not an exact version)"
                      % repr(data.get("version"))[:80])
    dist_tags = data.get("dist-tags") if isinstance(data.get("dist-tags"), dict) else None
    times = data.get("time") if isinstance(data.get("time"), dict) else {}
    res, available, why = _availability(latest, pinned)
    result = {"ok": True, "pinned": pinned, "latest": latest, "latest_is_prerelease": _is_prerelease(latest),
              "latest_published_at": times.get(latest) if isinstance(times.get(latest), str) else None,
              "dist_tags": dist_tags, "result": res, "update_available": available,
              "checked_at": _now(), "note": why}
    if core.runtime_tree_is_real(root, UPDATE_CHECK_REL.parts):
        core.atomic_write_json(Path(root) / UPDATE_CHECK_REL, result)
        result["recorded"] = str(UPDATE_CHECK_REL)
    else:
        result["recorded"] = None
    return result


# ---- rollback points: verified format (2026-11-07) ---------------------------
# A point saved by `pinets install` / `pinets rollback` records, in
# ROLLBACK_MANIFEST.json (format 2), the SHA-256 of EVERY saved regular file
# (engine files + the whole node_modules tree) and every symlink of that tree
# with its target. `usable` is true only when the manifest is present, in the
# current format, complete, and when every recorded hash matches the saved
# content (nothing unlisted in the backup tree, every path confined). A point
# without such a manifest (hand-made layout, or format 1 which recorded file
# NAMES and the artifact hash only) is listed with its reason and is never
# restored by this command — and never "upgraded" by hashing its current
# content, which would fabricate a proof of integrity after the fact.
ROLLBACK_FORMAT = 2
ROLLBACK_MANIFEST = "ROLLBACK_MANIFEST.json"
NODE_MODULES = "node_modules"
MUTATION_LOCK_REL = core.RUNTIME_REL / "pws-mutation.lock"   # shared with `upgrade` and `migrate`
MANUAL_NOTE = ("not produced by `pinets install` in the current format: restore it only with the "
               "documented manual procedure (never converted by hashing its current content)")
CORRUPT_NOTE = "do not restore this point with this command until it is re-saved from a sound engine"
# what a rollback leaves beside the engine when it is interrupted or ends
# `incomplete`: its staging tree and the engine tree it moved aside
LEFTOVER_KINDS = ((".restore-", "staging"), (NODE_MODULES + ".replaced-", "replaced-node_modules"))


def _lock(root):
    return core.file_lock(Path(root) / MUTATION_LOCK_REL, timeout=0.5)


def _rollback_tree_ok(root):
    """The rollback tree and every parent up to the root are real folders
    inside the workspace (spec 6.1.5, audit G-05) — the same guard as the
    other writers of `.claude/runtime`; checked before any listing, write,
    lock or restoration."""
    return core.runtime_tree_is_real(root, ROLLBACK_REL.parts)


def rollback_leftovers(root):
    """Folders left in tools/pine_exec by an interrupted or incomplete
    `pinets rollback` (audit G-11): the staging tree `.restore-<stamp>` and the
    moved-aside engine tree `node_modules.replaced-<stamp>`. Each names the
    pre-rollback point saved under the same stamp. Reported by `verify`, the
    doctor and `tooling-status`; NEVER removed automatically (one of them may
    be the only copy of a state to recover)."""
    pe = _pe(root)
    out = []
    if pe.is_symlink() or not pe.is_dir():
        return out
    tree_ok = _rollback_tree_ok(root)
    for p in sorted(pe.iterdir(), key=lambda q: q.name):
        for prefix, kind in LEFTOVER_KINDS:
            if p.name.startswith(prefix):
                point = "before-rollback-%s" % p.name[len(prefix):]
                out.append({"name": p.name, "kind": kind, "before_rollback_point": point,
                            "before_rollback_point_present":
                                tree_ok and (Path(root) / ROLLBACK_REL / point).is_dir()})
    return out


def _leftovers_note(leftovers):
    points = sorted({x["before_rollback_point"] for x in leftovers if x["before_rollback_point_present"]})
    back = ("the engine as it was before that rollback is the point %s (`pinets rollback <that point> --yes` "
            "returns to it), or retry the rollback" % " / ".join(points)) if points else \
        "no pre-rollback point with the same stamp is present: retry the rollback or reinstall (%s)" % NPM_CI
    return ("%d folder(s) left in tools/pine_exec by an interrupted or incomplete `pinets rollback` (unless one "
            "is running now): %s — the active engine may be incomplete; %s; remove these folders by hand only "
            "once `pinets verify` passes (never removed automatically)"
            % (len(leftovers), ", ".join(x["name"] for x in leftovers), back))


def _symlink_target_ok(rel, target):
    """A symlink recorded at `rel` (under node_modules/) must point inside
    node_modules: relative target, normalized path staying under the tree."""
    if not isinstance(target, str) or not target or Path(target).is_absolute():
        return False
    joined = os.path.normpath(os.path.join(os.path.dirname(rel), target))
    return joined == NODE_MODULES or joined.startswith(NODE_MODULES + "/")


def _walk_tree(base):
    """(rel, kind, info) for every entry under `base` without following
    symlinks: kind 'file' → sha256, 'symlink' → target, 'other' → None."""
    out = []
    base = Path(base)
    for dirpath, dirnames, filenames in os.walk(str(base), followlinks=False):
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            q = d / name
            if q.is_symlink():
                out.append((q.relative_to(base).as_posix(), "symlink", os.readlink(str(q))))
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            q = d / name
            rel = q.relative_to(base).as_posix()
            if q.is_symlink():
                out.append((rel, "symlink", os.readlink(str(q))))
            elif q.is_file():
                out.append((rel, "file", core.sha256_file(q)))
            else:
                out.append((rel, "other", None))
    return out


def _read_manifest(pdir):
    manifest, err = core.read_json(Path(pdir) / ROLLBACK_MANIFEST)
    if err == "missing":
        return None, "no ROLLBACK_MANIFEST.json"
    if err or not isinstance(manifest, dict):
        return None, "ROLLBACK_MANIFEST.json unreadable or not an object"
    return manifest, None


def check_rollback_point(root, pdir):
    """Validate a saved point WITHOUT touching the active engine: manifest
    present, in the current format and complete; every path confined on the
    backup side and on the engine side; every needed copy present with a
    valid hash matching its content; nothing unlisted in the saved
    node_modules tree; symlinks confined to node_modules; destinations sound.
    Returns {usable, problems, plan, format, manual}. `plan` holds what a
    restoration would do; `manual` is true when the point is structurally
    foreign to this command (hand-made layout or old format)."""
    root, pdir, pe = Path(root), Path(pdir), _pe(root)
    plan = {"engine_actions": [], "files": {}, "links": {}, "node_modules": None,
            "artifact_sha256": None, "version": None}
    base = {"plan": plan, "format": None, "manual": True}
    if pdir.is_symlink() or not pdir.is_dir():
        return dict(base, usable=False, problems=["rollback point is not a real directory"])
    problems = []
    missing_top = [rel for rel in ENGINE_FILES if not (pdir / rel).is_file()]
    if missing_top:
        problems.append("engine files missing at the top level: %s" % ", ".join(missing_top))
    manifest, merr = _read_manifest(pdir)
    fmt = manifest.get("format") if manifest else None
    if merr:
        problems.append(merr)
    elif fmt != ROLLBACK_FORMAT:
        if fmt is None and isinstance(manifest.get("files"), list):
            problems.append("manifest format 1 (file names and artifact hash only, no per-file hash): "
                            "the saved content cannot be verified")
        elif fmt is None:
            problems.append("manifest in no recognized format (no `format` field, no file list): "
                            "the saved content cannot be verified")
        else:
            problems.append("unknown manifest format %r" % (fmt,))
    if problems:
        return dict(base, usable=False, problems=problems,
                    format=fmt if isinstance(fmt, int) and not isinstance(fmt, bool) else None)
    base["format"], base["manual"] = ROLLBACK_FORMAT, False
    entries, engine_files = manifest.get("entries"), manifest.get("engine_files")
    nm_declared, art = manifest.get("node_modules"), manifest.get("installed_artifact_sha256")
    plan["node_modules"], plan["version"] = nm_declared, manifest.get("version")
    if not isinstance(entries, list) or not isinstance(engine_files, list) or not isinstance(nm_declared, bool):
        return dict(base, usable=False, problems=["manifest incomplete (entries, engine_files, node_modules)"])
    files, links, seen = {}, {}, set()
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str):
            problems.append("%r: invalid manifest entry" % (e,))
            continue
        rel = e["path"]
        if rel in seen:
            problems.append("%s: duplicate entry" % rel)
            continue
        seen.add(rel)
        if restore.confined(pdir, rel) is None:
            problems.append("%s: unsafe path" % rel)
            continue
        is_engine, is_nm = rel in ENGINE_FILES, rel.startswith(NODE_MODULES + "/")
        if not (is_engine or is_nm):
            problems.append("%s: unexpected entry (neither an engine file nor under node_modules/)" % rel)
            continue
        if "symlink" in e:
            if is_engine:
                problems.append("%s: an engine file cannot be a symlink" % rel)
            elif not _symlink_target_ok(rel, e.get("symlink")):
                problems.append("%s: symlink target %r leaves node_modules" % (rel, e.get("symlink")))
            elif (pdir / rel).exists() or (pdir / rel).is_symlink():
                problems.append("%s: a recorded symlink must not exist as a file in the backup" % rel)
            else:
                links[rel] = e["symlink"]
            continue
        h = e.get("sha256")
        if not isinstance(h, str) or not restore.SHA256_RE.match(h):
            problems.append("%s: no valid recorded hash" % rel)
            continue
        src = pdir / rel
        if src.is_symlink() or not src.is_file():
            problems.append("%s: backup copy missing" % rel)
            continue
        if core.sha256_file(src) != h:
            problems.append("%s: backup copy does not match the recorded hash" % rel)
            continue
        files[rel] = h
    unknown = [x for x in engine_files if x not in ENGINE_FILES]
    if unknown:
        problems.append("engine_files lists unknown files: %s" % ", ".join(map(str, unknown)))
    missing_engine = [rel for rel in ENGINE_FILES if rel not in engine_files or rel not in files]
    if missing_engine:
        problems.append("engine files missing from the verified manifest: %s" % ", ".join(missing_engine))
    nm_files = {k: v for k, v in files.items() if k.startswith(NODE_MODULES + "/")}
    nm_dir = pdir / NODE_MODULES
    if nm_declared:
        for req in (ARTIFACT_REL, NODE_MODULES + "/pinets/package.json"):
            if req not in nm_files:
                problems.append("%s: required entry missing" % req)
        if not isinstance(art, str) or not restore.SHA256_RE.match(art):
            problems.append("installed_artifact_sha256 missing or invalid")
        elif nm_files.get(ARTIFACT_REL, art) != art:
            problems.append("installed_artifact_sha256 does not match the saved artifact entry")
        if nm_dir.is_symlink() or not nm_dir.is_dir():
            problems.append("node_modules declared but absent from the backup")
        else:
            for rel, kind, _info in _walk_tree(nm_dir):
                full = NODE_MODULES + "/" + rel
                if kind != "file":
                    problems.append("%s: %s in the backup tree (only recorded regular files are allowed)" % (full, kind))
                elif full not in nm_files:
                    problems.append("%s: present in the backup but not recorded in the manifest" % full)
    else:
        if nm_files or links:
            problems.append("node_modules entries recorded although node_modules is declared absent")
        if nm_dir.exists() or nm_dir.is_symlink():
            problems.append("node_modules present in the backup although declared absent")
    # engine side (destinations), through the shared restoration check
    if pe.is_symlink() or not pe.is_dir():
        problems.append("active engine folder is not a real directory")
    nm_active = pe / NODE_MODULES
    if nm_active.is_symlink() or (nm_active.exists() and not nm_active.is_dir()):
        problems.append("active node_modules is a symlink or not a directory")
    actions, eproblems = restore.check(pe, pdir, {"files": [
        {"path": rel, "existed": True, "sha256": files[rel]} for rel in ENGINE_FILES if rel in files]})
    problems.extend(eproblems)
    plan.update({"engine_actions": actions, "files": files, "links": links,
                 "artifact_sha256": art if nm_declared else None})
    return dict(base, usable=not problems, problems=problems)


def list_rollback_points(root):
    """Saved engine points. `usable` is true only for a point whose manifest
    (current format) is complete and whose saved content matches every
    recorded hash — the same validation `pinets rollback` repeats under the
    lock before restoring. Other points are listed with their reason. Nothing
    is listed through a rollback tree that is a symlink or leaves the
    workspace (`tooling-status` reports it as `rollback_tree_refused`)."""
    rdir = Path(root) / ROLLBACK_REL
    out = []
    if not _rollback_tree_ok(root) or not rdir.is_dir():
        return out
    for d in sorted(p for p in rdir.iterdir() if p.is_dir() and not p.is_symlink()):
        pkg, _ = core.read_json(d / "package.json")
        deps = pkg.get("dependencies") if isinstance(pkg, dict) else None
        manifest, _ = _read_manifest(d)
        chk = check_rollback_point(root, d)
        reason = None
        if not chk["usable"]:
            reason = "; ".join(chk["problems"][:3])
            if len(chk["problems"]) > 3:
                reason += " (+%d more)" % (len(chk["problems"]) - 3)
            reason += " — " + (MANUAL_NOTE if chk["manual"] else CORRUPT_NOTE)
        out.append({"version": d.name, "path": str(d),
                    "has_node_modules": (d / NODE_MODULES / "pinets").is_dir(),
                    "pinned": deps.get("pinets") if isinstance(deps, dict) else None,
                    "manifest": manifest is not None, "format": chk["format"],
                    # label given at saving: the pinned version for a point saved by
                    # `pinets install`, `before-rollback-<stamp>` for one saved by a rollback
                    "label": manifest.get("version") if manifest else None,
                    "saved_at": manifest.get("saved_at") if manifest else None,
                    "usable": chk["usable"], "reason": reason, "problems": chk["problems"][:10]})
    return out


def _copy_engine(pe, dest):
    """Copy the engine files and the whole node_modules tree into `dest`,
    each copy verified against the hash of its source; symlinks of
    node_modules are recorded with their target (never copied as files).
    Returns (entries, engine_files, problems, node_modules_saved)."""
    entries, engine_files, problems, nm_saved = [], [], [], False
    try:
        for rel in ENGINE_FILES:
            src = pe / rel
            if src.is_symlink():
                problems.append("%s: engine file is a symlink — not saved" % rel)
                continue
            if not src.is_file():
                continue          # absent: reported by the validation of the saved point
            h = core.sha256_file(src)
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest / rel))
            if core.sha256_file(dest / rel) != h:
                problems.append("%s: copy does not match the source" % rel)
                continue
            entries.append({"path": rel, "sha256": h})
            engine_files.append(rel)
        nm = pe / NODE_MODULES
        if nm.is_symlink():
            problems.append("node_modules is a symlink — not saved")
        elif nm.is_dir():
            nm_saved = True
            for rel, kind, info in _walk_tree(nm):
                full = NODE_MODULES + "/" + rel
                if kind == "symlink":
                    if not _symlink_target_ok(full, info):
                        problems.append("%s: symlink target %r leaves node_modules — not saved" % (full, info))
                    else:
                        entries.append({"path": full, "symlink": info})
                elif kind == "file":
                    target = dest / full
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(nm / rel), str(target))
                    if core.sha256_file(target) != info:
                        problems.append("%s: copy does not match the source" % full)
                    else:
                        entries.append({"path": full, "sha256": info})
                else:
                    problems.append("%s: unsupported file type — not saved" % full)
    except OSError as exc:
        problems.append("copy failed: %s" % exc)
    return entries, engine_files, problems, nm_saved


def save_rollback_point(root, label=None):
    """Save the current engine (engine files + the whole node_modules tree)
    under the rollback tree with a verified manifest (format 2): every copy
    is hashed from the source and verified after the copy; symlinks of
    node_modules are recorded with their target (never copied as files);
    the saved point is then validated like any point. A copy that cannot be
    verified means NO point (the folder is removed and the error returned).
    An existing point of the same version is never overwritten: kept when it
    is usable, otherwise left untouched and a new stamped point is saved
    beside it (an old-format point is never converted). Refused before any
    write when the rollback tree is a symlink or leaves the workspace; an
    interruption (Ctrl-C) never leaves a partial point behind."""
    if not _rollback_tree_ok(root):
        return {"ok": False, "error": "rollback point not saved — refused before any write: %s"
                                      % ROLLBACK_TREE_REFUSED}
    pe = _pe(root)
    ident = engine_identity(root)
    ver = label or ident["pinned_version"] or "unknown"
    rdir = Path(root) / ROLLBACK_REL
    dest, note = rdir / ver, None
    if dest.exists() or dest.is_symlink():
        chk = check_rollback_point(root, dest)
        if chk["usable"]:
            return {"ok": True, "path": str(dest), "usable": True,
                    "note": "rollback point already exists and is verified — kept"}
        dest = rdir / ("%s-%s" % (ver, _now().replace(":", "")))
        if dest.exists():
            return {"ok": False, "error": "rollback point %s already exists" % dest.name}
        note = ("existing point %s kept untouched (not usable by this command: %s); "
                "new verified point saved as %s" % (ver, "; ".join(chk["problems"][:2]), dest.name))
    try:
        dest.mkdir(parents=True)
    except OSError as exc:
        return {"ok": False, "error": "cannot create %s: %s" % (dest, exc)}
    try:
        entries, engine_files, problems, nm_saved = _copy_engine(pe, dest)
        if not problems:
            art = next((e["sha256"] for e in entries if e["path"] == ARTIFACT_REL), None)
            core.atomic_write_json(dest / ROLLBACK_MANIFEST, {
                "format": ROLLBACK_FORMAT, "saved_at": _now(), "version": ver,
                "pinned_version": ident["pinned_version"], "engine_files": engine_files,
                "node_modules": nm_saved, "installed_artifact_sha256": art,
                "counts": {"files": sum(1 for e in entries if "sha256" in e),
                           "symlinks": sum(1 for e in entries if "symlink" in e)},
                "entries": entries})
            problems = check_rollback_point(root, dest)["problems"]
    except KeyboardInterrupt:
        shutil.rmtree(str(dest), ignore_errors=True)       # an interrupted copy is never a point
        raise
    if problems:
        shutil.rmtree(str(dest), ignore_errors=True)
        return {"ok": False, "problems": problems,
                "error": "rollback point not saved (it could not be verified): %s" % "; ".join(problems[:3])}
    return {"ok": True, "path": str(dest), "usable": True, "note": note,
            "saved": engine_files + ([NODE_MODULES] if nm_saved else []), "entries": len(entries)}


def install_plan(root, target_version):
    ident = engine_identity(root)
    problems = []
    if not isinstance(target_version, str) or not EXACT_VERSION_RE.match(target_version):
        problems.append("target version must be an exact version (e.g. 0.10.1)")
    if target_version == ident["pinned_version"]:
        problems.append("target version equals the current pin — nothing to install "
                        "(use `pinets verify`, or %s to repair)" % NPM_CI)
    steps = [
        "1. save a rollback point of the current engine (%s) under %s" % (ident["pinned_version"], ROLLBACK_REL),
        "2. npm install --save-exact --ignore-scripts pinets@%s (updates package.json + lockfile)" % target_version,
        "3. npm ci --ignore-scripts (clean install from the lockfile)",
        "4. check the engine on disk: package.json, the lockfile (with its integrity) and node_modules/pinets all "
        "carry %s and the artifact is present — otherwise stop: PROVENANCE and calibrations unchanged, way back "
        "= the point of step 1" % target_version,
        "5. record PROVENANCE: pinned_version, previous_pin (with the point actually saved), registry integrity "
        "from the lockfile, installed artifact sha256",
        "6. mark every CURRENT calibration STALE (new engine identity) — recalibration is a separate explicit act",
        "7. run `pinets verify` and the tooling tests",
    ]
    return {"current": ident["pinned_version"], "target": target_version,
            "problems": problems, "steps": steps,
            "requires": "--yes (nothing happens without it)"}


def install(root, target_version, yes=False, npm_runner=None):
    """Execute the install plan. `npm_runner(cmd, cwd)` is injectable for
    tests; default runs npm. Returns a report; stops at the first failure
    (the rollback point already exists at that moment)."""
    plan = install_plan(root, target_version)
    if plan["problems"]:
        return {"ok": False, "plan": plan, "error": "; ".join(plan["problems"])}
    if not yes:
        return {"ok": False, "plan": plan, "error": "refused without --yes"}
    if not _rollback_tree_ok(root):          # checked before the lock: nothing is written through a link
        return {"ok": False, "plan": plan,
                "error": "rollback point cannot be saved — aborting before any change: %s" % ROLLBACK_TREE_REFUSED}
    try:
        with _lock(root):
            return _install_locked(root, target_version, plan, npm_runner)
    except TimeoutError:
        return {"ok": False, "plan": plan, "error": "another PWS mutation holds the lock — nothing changed"}


def _engine_state(ident):
    return {"pinned": ident["pinned_version"], "locked": ident["locked_version"],
            "locked_integrity": ident["locked_integrity"], "installed": ident["installed_version"],
            "installed_artifact_sha256": ident["installed_artifact"]["sha256"]}


def _install_postconditions(ident, target):
    """What must hold on disk before an installation is declared (audit G-04):
    npm returning 0 is not a proof that the engine changed."""
    problems = []
    if ident["pinned_version"] != target:
        problems.append("package.json pins %r" % (ident["pinned_version"],))
    if ident["locked_version"] != target:
        problems.append("the lockfile records %r" % (ident["locked_version"],))
    elif not ident["locked_integrity"]:
        problems.append("the lockfile records no integrity for pinets")
    if not ident["installed"]:
        problems.append("node_modules/pinets is absent")
    elif ident["installed_version"] != target:
        problems.append("node_modules/pinets is version %r" % (ident["installed_version"],))
    if ident["installed_artifact"]["sha256"] is None:
        problems.append("the installed artifact %s is missing" % ARTIFACT_REL)
    return problems


def _install_locked(root, target_version, plan, npm_runner):
    pe = _pe(root)
    run = npm_runner or (lambda cmd, cwd: _run(cmd, cwd=cwd, timeout=600))
    report = {"ok": False, "plan": plan, "steps": []}
    rb = save_rollback_point(root)
    report["steps"].append({"step": "rollback-point", "result": rb})
    if not rb["ok"]:
        report["error"] = "rollback point not saved — aborting before any change: %s" % rb.get("error")
        return report
    point = Path(rb["path"]).name           # the point ACTUALLY saved (may be a stamped name)
    report["rollback_point"] = point
    back = "the way back is the saved point %s: `pinets rollback %s --yes`" % (point, point)
    rc, out, err = run(["npm", "install", "--save-exact", "--ignore-scripts",
                        "pinets@%s" % target_version], pe)
    report["steps"].append({"step": "npm-install", "rc": rc, "stderr": err[-500:]})
    if rc != 0:
        report["state"] = _engine_state(engine_identity(root))
        report["error"] = ("npm install failed — PROVENANCE and calibrations unchanged; if the engine changed "
                           "(see `state`, `pinets verify`), %s" % back)
        return report
    rc, out, err = run(["npm", "ci", "--ignore-scripts"], pe)
    report["steps"].append({"step": "npm-ci", "rc": rc, "stderr": err[-500:]})
    if rc != 0:
        report["state"] = _engine_state(engine_identity(root))
        report["error"] = ("npm ci --ignore-scripts failed — PROVENANCE and calibrations unchanged; the engine "
                           "on disk is not verified (see `state`, `pinets verify`); %s" % back)
        return report
    ident = engine_identity(root)
    report["state"] = _engine_state(ident)
    unmet = _install_postconditions(ident, target_version)
    report["steps"].append({"step": "postconditions", "ok": not unmet, "problems": unmet})
    if unmet:
        report["error"] = ("npm reported success but the engine on disk is not pinets %s (%s) — PROVENANCE.json "
                           "and the calibrations were NOT changed; %s"
                           % (target_version, "; ".join(unmet), back))
        report["next"] = ["python3 -m tools.pws_workspace pinets rollback %s --yes" % point,
                          "python3 -m tools.pws_workspace pinets verify"]
        return report
    prov_path = pe / "PROVENANCE.json"
    prov, perr = core.read_json(prov_path)
    prov = prov if isinstance(prov, dict) else {}
    previous = {"pinned_version": plan["current"],
                "registry_integrity": ((prov.get("provenance") or {}).get("registry_integrity")
                                       if isinstance(prov.get("provenance"), dict) else None),
                "replaced_on": _now()[:10],
                # the point really saved above (audit G-06), not a folder named after the pin
                "rollback": "%s/%s" % (ROLLBACK_REL, point), "rollback_point": point}
    prov["package"] = "pinets"
    prov["pinned_version"] = target_version
    pv = prov.get("provenance") if isinstance(prov.get("provenance"), dict) else {}
    pv.update({"registry": "https://registry.npmjs.org/pinets",
               "tarball": "https://registry.npmjs.org/pinets/-/pinets-%s.tgz" % target_version,
               "registry_integrity": ident["locked_integrity"],
               "lockfile_integrity_matches_registry": None,
               "installed_on": _now()[:10], "previous_pin": previous,
               "github_tag_note": "not verified — the pin is authoritative on the npm registry artifact"})
    prov["provenance"] = pv
    prov["installed_artifact"] = {"path": ARTIFACT_REL, "sha256": ident["installed_artifact"]["sha256"],
                                  "recorded_at": _now()}
    lic = prov.get("license") if isinstance(prov.get("license"), dict) else {}
    lic.setdefault("license_basis", None)
    lic["reverify_note"] = ("licence of the new version to re-read (PINETS_LICENSE to refresh "
                            "from node_modules/pinets/LICENSE); until then license_basis is "
                            "the previous assessment, not a verification")
    prov["license"] = lic
    prov["verified_at"] = None
    core.atomic_write_json(prov_path, prov)
    report["steps"].append({"step": "provenance", "ok": True})
    stale = mark_calibrations_stale(root, "engine changed from %s to %s" % (plan["current"], target_version))
    report["steps"].append({"step": "calibrations-stale", "result": stale})
    report["ok"] = True
    report["next"] = ["python3 -m tools.pws_workspace pinets verify",
                      "python3 -m tools.pws_workspace pinets recalibrate-plan",
                      "python3 -m unittest discover -s tools/tests -t ."]
    return report


def mark_calibrations_stale(root, reason):
    """Persist STALE on every CURRENT calibration (capability_status is never
    touched; effective_gating stays derived)."""
    path = _pe(root) / "calibration" / "capabilities.json"
    calib, err = core.read_json(path)
    if err or not isinstance(calib, dict) or not isinstance(calib.get("capabilities"), dict):
        return {"ok": False, "error": "capabilities.json %s" % (err or "invalid")}
    changed = []
    for name, entry in calib["capabilities"].items():
        if isinstance(entry, dict) and entry.get("calibration_status") == "CURRENT":
            entry["calibration_status"] = "STALE"
            entry["stale_reason"] = reason
            entry["stale_since"] = _now()
            changed.append(name)
    if changed:
        calib.setdefault("history", []).append({"at": _now(), "event": "marked STALE", "reason": reason,
                                                "capabilities": changed})
        core.atomic_write_json(path, calib)
    return {"ok": True, "marked_stale": changed}


def rollback(root, version=None, yes=False):
    """Restore a saved engine point (engine files + node_modules tree) in two
    stages, under the mutation lock shared with `upgrade`/`migrate`:

      check   — the WHOLE point is validated again (manifest, paths, every
                hash on the saved content, destinations) before anything is
                written; the current engine is saved to a verified point; the
                restoration is STAGED beside the engine and every staged copy
                is verified. One anomaly refuses the whole restoration: the
                active engine is unchanged (stage 'refused').
      perform — a short sequence of atomic renames puts the staged files in
                place, then the active engine is verified file by file against
                the manifest (artifact included). Success is declared only when
                that verification passes (stage 'verified'). An error met
                after the first rename, an interruption (Ctrl-C) during the
                renames, or a failed verification, is reported as 'incomplete'
                with every recovery element kept (the point, the pre-rollback
                point, the staged and the replaced trees).

    Without a version, the point restored is the one recorded by the last
    installation (see `_default_point`). Refused when the rollback tree is a
    symlink or leaves the workspace.
    """
    if not _rollback_tree_ok(root):
        return {"ok": False, "stage": "refused", "version": version, "restored": [],
                "error": "rollback refused — nothing changed: %s" % ROLLBACK_TREE_REFUSED}
    points = list_rollback_points(root)
    if not points:
        return {"ok": False, "error": "no rollback point under %s" % ROLLBACK_REL}
    usable = ", ".join(p["version"] for p in points if p["usable"]) or "none"
    if version is None:
        chosen, previous = _default_point(root, points)
        if chosen is None:
            return {"ok": False, "error": "no rollback point for the previous pin %r recorded in PROVENANCE "
                                          "(available: %s; usable: %s) — name the point explicitly"
                    % (previous, ", ".join(p["version"] for p in points), usable)}
        version = chosen["version"]
    else:
        chosen = next((p for p in points if p["version"] == version), None)
        if chosen is None:
            return {"ok": False, "error": "no rollback point for version %r (available: %s; usable: %s)"
                    % (version, ", ".join(p["version"] for p in points), usable)}
    if not chosen["usable"]:
        return {"ok": False, "stage": "refused", "version": version, "restored": [],
                "error": "rollback point %s is not usable by this command: %s — nothing changed (usable "
                         "points: %s)" % (version, chosen["reason"], usable), "point": chosen}
    if not yes:
        return {"ok": False, "error": "refused without --yes", "would_restore": chosen}
    try:
        with _lock(root):
            return _rollback_locked(root, chosen)
    except TimeoutError:
        return {"ok": False, "stage": "refused", "version": version, "restored": [],
                "error": "another PWS mutation holds the lock — nothing changed"}


def _default_point(root, points):
    """Point restored by `pinets rollback` without a version (audit G-06):
      1. the point recorded by the last installation (`previous_pin.rollback_point`,
         or the folder named by `previous_pin.rollback`) when it is usable and
         carries the previous pin;
      2. otherwise the most recent usable point saved by an installation for
         that pin (label = the pin; a `before-rollback-*` point is never chosen
         by default);
      3. otherwise the folder named after the previous pin — refused with its
         reason when it is not usable.
    Returns (point or None, previous pinned version)."""
    prov = engine_identity(root)["provenance"] or {}
    pv = prov.get("provenance") if isinstance(prov.get("provenance"), dict) else {}
    prev = pv.get("previous_pin") if isinstance(pv.get("previous_pin"), dict) else {}
    previous = prev.get("pinned_version") if isinstance(prev.get("pinned_version"), str) else None
    by_name = {p["version"]: p for p in points}
    named = []
    if isinstance(prev.get("rollback_point"), str):
        named.append(prev["rollback_point"])
    if isinstance(prev.get("rollback"), str):
        head, _, tail = prev["rollback"].rpartition("/")
        if head == ROLLBACK_REL.as_posix() and tail:
            named.append(tail)
    for name in named:
        p = by_name.get(name)
        if p is not None and p["usable"] and (previous is None or p["pinned"] == previous):
            return p, previous
    if previous:
        saved = [p for p in points if p["usable"] and p["pinned"] == previous and p.get("label") == previous]
        if saved:
            return max(saved, key=lambda p: (p.get("saved_at") or "", p["version"])), previous
    return by_name.get(previous), previous


def _refused(version, problems, pdir, before=None, interrupted=False):
    out = {"ok": False, "stage": "refused", "version": version, "restored": [], "problems": problems,
           "point": str(pdir), "before_rollback_point": before, "artifact_check": "not performed",
           "error": "rollback refused before any change to the active engine — nothing changed: %s"
                    % "; ".join(problems[:5])}
    if interrupted:
        out["interrupted"] = True
    return out


def _cleanup_staging(stage_dir):
    if stage_dir is not None and stage_dir.exists():
        shutil.rmtree(str(stage_dir), ignore_errors=True)


def _verify_active(pe, plan):
    """Compare the active engine with the restored point: engine files,
    the exact node_modules tree (files, hashes, symlinks) and the artifact."""
    problems = []
    for rel in ENGINE_FILES:
        expected = plan["files"].get(rel)
        target = pe / rel
        if expected is None:
            continue
        if target.is_symlink() or not target.is_file() or core.sha256_file(target) != expected:
            problems.append("%s: restored file missing or does not match the recorded hash" % rel)
    nm = pe / NODE_MODULES
    prefix = NODE_MODULES + "/"
    exp_files = {k[len(prefix):]: v for k, v in plan["files"].items() if k.startswith(prefix)}
    exp_links = {k[len(prefix):]: v for k, v in plan["links"].items()}
    if plan["node_modules"]:
        if nm.is_symlink() or not nm.is_dir():
            problems.append("node_modules absent after restoration")
        else:
            found_files, found_links = {}, {}
            for rel, kind, info in _walk_tree(nm):
                if kind == "file":
                    found_files[rel] = info
                elif kind == "symlink":
                    found_links[rel] = info
                else:
                    problems.append("%s%s: unexpected entry type after restoration" % (prefix, rel))
            for rel, h in exp_files.items():
                if found_files.get(rel) != h:
                    problems.append("%s%s: restored file missing or does not match" % (prefix, rel))
            for rel in found_files:
                if rel not in exp_files:
                    problems.append("%s%s: unexpected file after restoration" % (prefix, rel))
            for rel, t in exp_links.items():
                if found_links.get(rel) != t:
                    problems.append("%s%s: restored symlink missing or different" % (prefix, rel))
            for rel in found_links:
                if rel not in exp_links:
                    problems.append("%s%s: unexpected symlink after restoration" % (prefix, rel))
        artifact = pe / ARTIFACT_REL
        actual = core.sha256_file(artifact) if artifact.is_file() and not artifact.is_symlink() else None
        if actual != plan["artifact_sha256"]:
            problems.append("artifact %s: sha256 %s differs from the recorded %s"
                            % (ARTIFACT_REL, actual, plan["artifact_sha256"]))
    elif nm.exists() or nm.is_symlink():
        problems.append("node_modules still present although the point recorded none")
    return problems


def _rollback_locked(root, chosen):
    pe, pdir, version = _pe(root), Path(chosen["path"]), chosen["version"]
    if not _rollback_tree_ok(root):                     # the tree may have changed since the listing
        return _refused(version, [ROLLBACK_TREE_REFUSED], pdir)
    chk = check_rollback_point(root, pdir)              # fresh validation under the lock
    if not chk["usable"]:
        return _refused(version, chk["problems"], pdir)
    plan = chk["plan"]
    # unique staging folder beside the engine (a leftover of a failed attempt never collides)
    try:
        stage_dir = Path(tempfile.mkdtemp(prefix=".restore-%s-" % _now().replace(":", ""), dir=str(pe)))
    except OSError as exc:
        return _refused(version, ["cannot create the staging folder: %s" % exc], pdir)
    stamp = stage_dir.name[len(".restore-"):]
    try:
        before = save_rollback_point(root, label="before-rollback-%s" % stamp)
    except KeyboardInterrupt:                           # the active engine is untouched at this stage
        _cleanup_staging(stage_dir)
        return _refused(version, ["interrupted (KeyboardInterrupt) while saving the current engine"], pdir,
                        interrupted=True)
    if not before["ok"]:
        _cleanup_staging(stage_dir)
        return _refused(version, ["current engine not saved to a verified point: %s" % before["error"]], pdir)
    # ---- stage: every copy verified, nothing in the active engine changes ----
    staged, problems, stage_nm, interrupted = [], [], None, False
    prefix = NODE_MODULES + "/"
    try:
        for a in plan["engine_actions"]:
            tmp = stage_dir / a["path"]
            tmp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(a["src"]), str(tmp))
            if core.sha256_file(tmp) != a["sha256"]:
                problems.append("%s: staged copy does not match the recorded hash" % a["path"])
            staged.append((tmp, a["target"], a["path"]))
        if plan["node_modules"]:
            stage_nm = stage_dir / NODE_MODULES
            stage_nm.mkdir()
            for rel, h in plan["files"].items():
                if not rel.startswith(prefix):
                    continue
                t = stage_nm / rel[len(prefix):]
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(pdir / rel), str(t))
                if core.sha256_file(t) != h:
                    problems.append("%s: staged copy does not match the recorded hash" % rel)
            for rel, target in plan["links"].items():
                t = stage_nm / rel[len(prefix):]
                t.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(target, str(t))
    except OSError as exc:
        problems.append("staging failed: %s" % exc)
    except KeyboardInterrupt:                           # staging writes only inside stage_dir
        problems.append("interrupted (KeyboardInterrupt) while staging")
        interrupted = True
    if problems:
        _cleanup_staging(stage_dir)
        return _refused(version, problems, pdir, before=before["path"], interrupted=interrupted)
    # ---- perform: atomic renames; after the first one, a failure is 'incomplete' ----
    mutated, restored, replaced_nm = False, [], None
    nm_active = pe / NODE_MODULES
    try:
        for tmp, target, rel in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(tmp), str(target))
            mutated = True
            restored.append(rel)
        if nm_active.exists() or nm_active.is_symlink():
            replaced_nm = pe / ("%s.replaced-%s" % (NODE_MODULES, stamp))
            os.rename(str(nm_active), str(replaced_nm))
            mutated = True
        if stage_nm is not None:
            os.rename(str(stage_nm), str(nm_active))
            mutated = True
    except OSError as exc:
        problems.append("execution error: %s" % exc)
        if not mutated:
            _cleanup_staging(stage_dir)
            return _refused(version, problems, pdir, before=before["path"])
    except KeyboardInterrupt:
        # never "nothing changed" here: a rename may have completed just before
        # the interruption — the run stops, reported incomplete, everything kept
        interrupted = True
        problems.append("interrupted (KeyboardInterrupt) during the renames — the active engine may be "
                        "partly restored")
    if not problems:
        problems = _verify_active(pe, plan)
    recovery = {"point": str(pdir), "before_rollback_point": before["path"],
                "staging": str(stage_dir) if stage_dir.exists() else None,
                "replaced_node_modules": str(replaced_nm) if replaced_nm and replaced_nm.exists() else None}
    if problems:
        out = {"ok": False, "stage": "incomplete", "version": version, "restored": restored,
               "node_modules": "NOT verified", "artifact_check": "not verified", "problems": problems,
               "recovery": recovery,
               "error": "rollback incomplete — the active engine is NOT verified: %s; recovery elements kept "
                        "(point, pre-rollback point, staged and replaced trees) — `pinets verify`, the doctor "
                        "and `tooling-status` report them until they are removed by hand"
                        % "; ".join(problems[:5])}
        if interrupted:
            out["interrupted"] = True
        return out
    leftovers = []
    for extra in (replaced_nm, stage_dir):
        if extra is not None and extra.exists():
            shutil.rmtree(str(extra), ignore_errors=True)
            if extra.exists():
                leftovers.append(str(extra))
    return {"ok": True, "stage": "verified", "version": version, "restored": restored,
            "node_modules": ("restored" if plan["node_modules"] else
                             ("removed" if replaced_nm is not None else "none")),
            "artifact_check": "match", "checked": {"files": len(plan["files"]), "symlinks": len(plan["links"])},
            "before_rollback_point": before["path"], "leftovers": leftovers}


def recalibrate_plan(root):
    """Guided recalibration plan — never executed automatically."""
    pe = _pe(root)
    cases = sorted(p.name for p in (pe / "calibration" / "cases").glob("*.pine")) \
        if (pe / "calibration" / "cases").is_dir() else []
    ident = engine_identity(root)
    return {
        "engine": {"pinned": ident["pinned_version"], "installed": ident["installed_version"],
                   "artifact_sha256": ident["installed_artifact"]["sha256"]},
        "calibrated_environment": ident["calibration_environment"],
        "cases": cases,
        "steps": [
            "1. node fingerprint.mjs (tools/pine_exec) — new executor_fingerprint",
            "2. for each calibration case: node runner.mjs run --source calibration/cases/<case>.pine "
            "--dataset calibration/datasets/<dataset>.json --out .claude/runtime/pine-local-test/calib-<case>.json",
            "3. compare each normalized payload with the INDEPENDENT reference (*.expected.json, "
            "reference_provenance recorded) — a divergence is documented in known_divergences, never hidden",
            "4. update calibration/capabilities.json: environment triplet (pinets_version, "
            "executor_fingerprint, normalization_schema), calibration_status CURRENT only for "
            "capabilities actually re-exercised; capability_status unchanged unless a reviewed "
            "promotion decision says otherwise (never GATING by inheritance)",
            "5. re-record case_artifacts hashes; run the tooling tests; `pinets verify`",
        ],
        "rules": ["CURRENT ≠ GATING", "effective_gating derived, never persisted",
                  "no Pine source modified to satisfy PineTS", "TradingView remains the authority"],
    }
