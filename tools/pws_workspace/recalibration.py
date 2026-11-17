# SPDX-License-Identifier: Apache-2.0
"""Guided recalibration of the PineTS engine (2.2.0) — the steps that
`pinets recalibrate-plan` listed for a manual run, executed by the tooling
within an approved plan, under the same rules (spec section 24.4):

- the cases, datasets and INDEPENDENT references are the existing ones,
  named in `calibration/comparisons.json` and hash-checked against
  `case_artifacts` of `capabilities.json` before anything runs; an artifact
  that does not match its recorded hash stops the recalibration (a reference
  is never re-hashed, rewritten or regenerated to fit a new engine);
- each case is executed by the adapter's own runner; its normalized result is
  compared with the reference by the rules of the comparison contract (exact,
  or relative within a DOCUMENTED tolerance) — never relaxed here;
- a capability becomes CURRENT only when every case it lists was re-executed
  successfully, concordant on every compared series, with no unclassified
  token, and the run detected the capability; every other capability that was
  CURRENT becomes STALE with its reason; `capability_status` is never touched
  (CURRENT is never GATING by itself) and `known_divergences` is never edited;
- the runs, the comparison and the calibration file before the change are kept
  with their provenance under .claude/runtime/pinets-recalibration/<stamp>/;
- a divergence, a failed or unusable run, or a missing reference stops the
  conclusion for the cases concerned and is reported as such: the decision
  belongs to the holder. No Pine source is ever modified.
"""
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import core

CONTRACT_NAME = "comparisons.json"
CONTRACT_SCHEMA = "pws-calibration-comparison-v1"
RESULTS_REL = core.RUNTIME_REL / "pinets-recalibration"
MODES = ("exact", "relative")
RUN_SCHEMA = "pws-pinets-run-v1"
PASS, FAIL = "PINETS_EXECUTION_PASS", "PINETS_EXECUTION_FAIL"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_RE = re.compile(r"""export\s+const\s+NORMALIZATION_SCHEMA\s*=\s*['"]([^'"]+)['"]""")


def _is_number(v):
    """A finite int or float — never a bool, NaN or an infinity."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def expected_schema(root):
    """The normalization schema the adapter actually emits, read from its own
    source (`normalize.mjs`) — the single source of truth, never a constant here."""
    path = Path(root) / "tools" / "pine_exec" / "normalize.mjs"
    try:
        m = SCHEMA_RE.search(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


def binding(root):
    """What a plan that includes the recalibration is bound to: the comparison
    contract and every artifact it names (source, dataset, reference), each by
    the hash of its content on disk now, plus the problems that would stop the
    recalibration. Compared again just before the first change."""
    c = contract(root)
    cdir = _calib_dir(root)
    arts = {}
    for case, info in sorted(c["cases"].items()):
        for role in ("source", "dataset", "reference"):
            p = Path(info["paths"][role])
            arts["%s:%s" % (case, role)] = core.sha256_file(p) if p.is_file() else None
    return {"contract_sha256": c["contract_sha256"], "contract_path": str((cdir / CONTRACT_NAME).relative_to(root)),
            "cases": sorted(c["cases"]), "artifacts": arts, "ok": c["ok"], "problems": c["problems"]}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _calib_dir(root):
    return Path(root) / "tools" / "pine_exec" / "calibration"


def _artifact(calib_dir, artifacts, name):
    """(path, problem): the case artifact `name`, physically confined to the
    calibration folder and matching its recorded hash."""
    art = artifacts.get(name)
    if not isinstance(art, dict) or not isinstance(art.get("path"), str) or not isinstance(art.get("sha256"), str):
        return None, "%s is not a recorded case artifact" % name
    path = calib_dir / art["path"]
    try:
        real = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "%s is missing (%s)" % (name, art["path"])
    if not core.is_within(calib_dir.resolve(), real) or path.is_symlink() or not real.is_file():
        return None, "%s leaves the calibration folder or is not a regular file" % name
    if core.sha256_file(real) != art["sha256"]:
        return None, "%s does not match its recorded hash — the reference set is not the calibrated one" % name
    return real, None


def contract(root):
    """Read and check the comparison contract against the calibration
    manifest. Returns {ok, cases: {case: {...}}, capabilities: {cap: [cases]},
    problems, uncovered}: `uncovered` lists the capabilities whose cases have
    no declared comparison (they can never become CURRENT here)."""
    cdir = _calib_dir(root)
    out = {"ok": False, "cases": {}, "capabilities": {}, "problems": [], "uncovered": [], "contract_sha256": None}
    calib, err = core.read_json(cdir / "capabilities.json")
    if err or not isinstance(calib, dict) or not isinstance(calib.get("capabilities"), dict):
        out["problems"].append("capabilities.json %s" % (err or "invalid"))
        return out
    doc, err = core.read_json(cdir / CONTRACT_NAME)
    if err or not isinstance(doc, dict) or doc.get("schema") != CONTRACT_SCHEMA or not isinstance(doc.get("cases"), dict):
        out["problems"].append("comparison contract %s %s" % (CONTRACT_NAME, err or "invalid or of another schema"))
        return out
    out["contract_sha256"] = core.sha256_file(cdir / CONTRACT_NAME)
    artifacts = calib.get("case_artifacts") if isinstance(calib.get("case_artifacts"), dict) else {}
    for case, spec in sorted(doc["cases"].items()):
        problems = []
        if not isinstance(spec, dict) or not isinstance(spec.get("series"), dict) or not spec["series"]:
            out["problems"].append("case %s: no series to compare" % case)
            continue
        paths = {}
        for role in ("source", "dataset", "reference"):
            path, problem = _artifact(cdir, artifacts, spec.get(role))
            if problem:
                problems.append("%s: %s" % (role, problem))
            paths[role] = path
        ref_art = artifacts.get(spec.get("reference")) if isinstance(artifacts.get(spec.get("reference")), dict) else {}
        if not (isinstance(ref_art.get("reference_provenance"), str) and ref_art["reference_provenance"].strip()):
            problems.append("reference %s carries no reference_provenance (independent reference required)"
                            % spec.get("reference"))
        for name, rule in spec["series"].items():
            if not isinstance(rule, dict) or not isinstance(rule.get("reference"), str) or rule.get("mode") not in MODES:
                problems.append("series %s: invalid rule" % name)
            elif rule["mode"] == "relative" and not (_is_number(rule.get("tolerance"))
                                                    and 0 < rule["tolerance"] < 1e-3 and rule.get("basis")):
                problems.append("series %s: a relative rule needs a small tolerance and its documented basis" % name)
        if problems:
            out["problems"].extend("case %s: %s" % (case, p) for p in problems)
            continue
        out["cases"][case] = {"paths": {k: str(v) for k, v in paths.items()}, "spec": spec,
                              "reference_name": spec["reference"]}
    for cap, entry in sorted(calib["capabilities"].items()):
        cases = entry.get("cases") if isinstance(entry, dict) and isinstance(entry.get("cases"), list) else []
        out["capabilities"][cap] = cases
        if not cases or any(c not in out["cases"] for c in cases):
            out["uncovered"].append(cap)
    out["ok"] = bool(out["cases"]) and not out["problems"]
    return out


def compare_points(got, ref, rule):
    """(ok, detail) for one series, never raising: both sides lists of the same
    length; every point an object with an integer timestamp `t` equal on both
    sides and a `v` field that is either a finite number or `null` (na, allowed
    only when both sides are na); NaN, infinities, booleans, strings and missing
    fields are invalid — on the obtained side AND on the reference side; exact
    values, or a relative difference within the contract's finite tolerance.
    Returns (state, detail): `ok`, `mismatch` (valid data outside the rule) or
    `invalid` (data or rule that cannot be compared)."""
    try:
        if rule.get("mode") not in MODES:
            return "invalid", "invalid rule mode %r" % (rule.get("mode"),)
        tol = rule.get("tolerance")
        if rule["mode"] == "relative" and not (_is_number(tol) and tol > 0):
            return "invalid", "invalid tolerance %r for a relative rule" % (tol,)
        if not isinstance(got, list) or not isinstance(ref, list):
            return "invalid", "series missing or not a list"
        if len(got) != len(ref):
            return "mismatch", "length %d != reference %d" % (len(got), len(ref))
        worst, mismatches = 0.0, 0
        for i, (g, e) in enumerate(zip(got, ref)):
            for side, point in (("obtained", g), ("reference", e)):
                if not isinstance(point, dict) or "t" not in point or "v" not in point:
                    return "invalid", "%s point %d: missing `t` or `v` field" % (side, i)
                t = point["t"]
                if isinstance(t, bool) or not isinstance(t, int):
                    return "invalid", "%s point %d: invalid timestamp %r" % (side, i, t)
                v = point["v"]
                if v is not None and not _is_number(v):
                    return "invalid", "%s point %d: invalid value %r (finite number or null required)" % (side, i, v)
            if g["t"] != e["t"]:
                return "mismatch", "point %d: timestamp %s differs from the reference %s" % (i, g["t"], e["t"])
            gv, ev = g["v"], e["v"]
            if gv is None or ev is None:
                if gv is not ev:
                    mismatches += 1
                continue
            if rule["mode"] == "exact":
                if gv != ev:
                    mismatches += 1
            else:
                rel = abs(gv - ev) / max(abs(ev), 1e-9)
                if not math.isfinite(rel):
                    return "invalid", "point %d: relative difference not finite" % i
                worst = max(worst, rel)
                if rel > tol:
                    mismatches += 1
        if mismatches:
            return "mismatch", "%d/%d point(s) outside the rule (%s)" % (mismatches, len(ref), rule["mode"])
        return "ok", ("exact" if rule["mode"] == "exact" else "within %g (worst %.3g)" % (tol, worst))
    except Exception as exc:  # noqa: BLE001 — a comparison never ends on a trace
        return "invalid", "comparison impossible: %s: %s" % (type(exc).__name__, str(exc)[:200])


def compare_series(got, ref, rule):
    """(ok, detail): `compare_points` reduced to a boolean."""
    state, detail = compare_points(got, ref, rule)
    return state == "ok", detail


def _node_env():
    return {"PATH": os.environ.get("PATH", ""), "TZ": "UTC", "LANG": "C", "LC_ALL": "C"}


def _node_run(pe, args, timeout=300):
    try:
        p = subprocess.run(["node"] + list(args), cwd=str(pe), capture_output=True, text=True, timeout=timeout,
                           env=_node_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return p.returncode, p.stdout, p.stderr


def check_run_report(doc, rc, expect):
    """(verdict, problem) for one run report against the runner's real contract
    and the facts of THIS execution (`expect`: source and dataset hashes, the
    installed engine version, the adapter's normalization schema, the executor
    fingerprint computed now). `pass` / `fail` only for a coherent report;
    `unusable` otherwise — fields are never defaulted to favourable values."""
    if not isinstance(doc, dict) or doc.get("schema") != RUN_SCHEMA:
        return "unusable", "run report missing or not of schema %s" % RUN_SCHEMA
    if isinstance(rc, bool) or not isinstance(rc, int):
        return "unusable", "runner exit code %r unusable" % (rc,)
    status = doc.get("execution_status")
    if status not in (PASS, FAIL):
        return "unusable", "execution_status %r unknown" % (status,)
    if (status, rc) not in ((PASS, 0), (FAIL, 1)):
        return "unusable", "runner exit code %s contradicts execution_status %s" % (rc, status)
    for field, kind in (("pinets_version", str), ("normalization_schema", str), ("executor_fingerprint", str),
                        ("source_sha256", str), ("dataset_sha256", str), ("unclassified_tokens", list),
                        ("capabilities_used", dict)):
        if not isinstance(doc.get(field), kind):
            return "unusable", "field %s missing or of a wrong type" % field
    for field in ("executor_fingerprint", "source_sha256", "dataset_sha256"):
        if not HEX64.match(doc[field]):
            return "unusable", "field %s is not a SHA-256" % field
    if not expect.get("pinets_version") or doc["pinets_version"] != expect["pinets_version"]:
        return "unusable", ("report names pinets %r, the engine executed here is %r"
                            % (doc["pinets_version"], expect.get("pinets_version")))
    if not expect.get("normalization_schema") or doc["normalization_schema"] != expect["normalization_schema"]:
        return "unusable", ("report names normalization schema %r, the adapter emits %r"
                            % (doc["normalization_schema"], expect.get("normalization_schema")))
    if doc["executor_fingerprint"] != expect.get("executor_fingerprint"):
        return "unusable", "report names another executor fingerprint than the one computed now"
    if doc["source_sha256"] != expect.get("source_sha256"):
        return "unusable", "the report does not name the calibrated source"
    if doc["dataset_sha256"] != expect.get("dataset_sha256"):
        return "unusable", "the report does not name the calibrated dataset"
    if status == FAIL:
        return "fail", None
    if doc["unclassified_tokens"]:
        return "unusable", "unclassified tokens %s: capability detection not closed" % doc["unclassified_tokens"][:5]
    plots = doc.get("normalized", {}).get("plots") if isinstance(doc.get("normalized"), dict) else None
    if not isinstance(plots, dict):
        return "unusable", "normalized plots missing"
    return "pass", None


def run(root, node_runner=None, results_dir=None, expected_binding=None):
    """Execute the declared cases, compare, then update capabilities.json for
    the capabilities actually re-exercised with success. Never raises on a
    failed case. Final statuses: `recalibrated` ONLY when every case is
    concordant AND the calibration file was written and verified; `divergent`
    when a case diverges (or the engine fails it); `incomplete` otherwise
    (unusable report, contract or environment problem, write or verification
    failure). `expected_binding` (from the approved plan) is compared with the
    contract and artifacts on disk before anything runs. COMPARISON.json is
    written with the FINAL result."""
    root = Path(root)
    pe = root / "tools" / "pine_exec"
    runner = node_runner or _node_run
    report = {"status": "incomplete", "cases": {}, "current": [], "stale": [], "uncovered": [], "problems": [],
              "calibration_written": False, "calibration_verified": False, "results_dir": None,
              "calibration_backup": None}
    if expected_binding is not None:
        now = binding(root)
        keys = ("contract_sha256", "cases", "artifacts")
        if not now["ok"] or any(now.get(k) != expected_binding.get(k) for k in keys):
            report["problems"].append("the comparison contract or its artifacts changed since the plan was approved: "
                                      "nothing executed")
            return report
    c = contract(root)
    report["uncovered"] = c["uncovered"]
    report["contract_sha256"] = c["contract_sha256"]
    if c["problems"]:
        report["problems"].extend(c["problems"])
    if not c["cases"]:
        report["problems"].append("no comparable case: nothing executed")
        return report
    if not core.runtime_tree_is_real(root, RESULTS_REL.parts):
        report["problems"].append("%s is a symlink or leaves the workspace: nothing executed" % RESULTS_REL)
        return report
    base = Path(results_dir) if results_dir else root / RESULTS_REL
    base.mkdir(parents=True, exist_ok=True)
    rdir = Path(tempfile.mkdtemp(prefix=_now().replace(":", "") + "-", dir=str(base)))
    report["results_dir"] = str(rdir)
    try:
        _run_cases(root, pe, runner, c, report, rdir)
    except Exception as exc:  # noqa: BLE001 — an account is always returned
        report["status"] = "incomplete"
        report["problems"].append("internal error during the recalibration: %s: %s" % (type(exc).__name__, str(exc)[:300]))
    try:
        core.atomic_write_json(rdir / "COMPARISON.json", report)
    except OSError as exc:
        report["problems"].append("COMPARISON.json not written: %s" % exc)
        if report["status"] == "recalibrated":
            report["status"] = "incomplete"
    return report


def _run_cases(root, pe, runner, c, report, rdir):
    rc, out, err = runner(pe, ["fingerprint.mjs"], 60)
    try:
        fingerprint = json.loads(out).get("executor_fingerprint") if rc == 0 else None
    except (ValueError, AttributeError, TypeError):
        fingerprint = None
    if not isinstance(fingerprint, str) or not HEX64.match(fingerprint):
        report["problems"].append("executor fingerprint not computable (node): nothing concluded")
        return
    from . import tooling
    installed = tooling.engine_identity(root)["installed_version"]
    schema = expected_schema(root)
    report["executor_fingerprint"] = fingerprint
    report["pinets_version"], report["normalization_schema"] = installed, schema
    if not installed or not schema:
        report["problems"].append("installed engine version or adapter normalization schema unreadable: "
                                  "nothing concluded")
        return
    for case, info in c["cases"].items():
        res = {"verdict": "incomplete", "series": {}, "capabilities_detected": [], "problem": None,
               "reference_name": info["reference_name"]}
        report["cases"][case] = res
        out_path = rdir / ("%s.run.json" % case)
        rc, out, err = runner(pe, ["runner.mjs", "run", "--source", info["paths"]["source"], "--dataset",
                                   info["paths"]["dataset"], "--out", str(out_path)], 300)
        res["runner_exit_code"] = rc
        doc, rerr = core.read_json(out_path) if out_path.is_file() else (None, "no report written")
        if rerr:
            res["problem"] = "run report unusable (exit code %s): %s %s" % (rc, rerr, (err or "")[-200:])
            continue
        res["run_report_sha256"] = core.sha256_file(out_path)
        expect = {"pinets_version": installed, "normalization_schema": schema, "executor_fingerprint": fingerprint,
                  "source_sha256": core.sha256_file(Path(info["paths"]["source"])),
                  "dataset_sha256": core.sha256_file(Path(info["paths"]["dataset"]))}
        verdict, problem = check_run_report(doc, rc, expect)
        res["execution_status"] = doc.get("execution_status") if isinstance(doc, dict) else None
        if verdict == "unusable":
            res["problem"] = problem
            continue
        if verdict == "fail":
            res["problem"] = "execution failed: %s" % str(((doc.get("error") or {}) if isinstance(doc.get("error"), dict)
                                                          else {}).get("message"))[:300]
            res["verdict"] = "divergent"      # the engine itself fails on the case: a behavioural difference
            continue
        res["capabilities_detected"] = sorted(doc["capabilities_used"].keys())
        reference, ferr = core.read_json(Path(info["paths"]["reference"]))
        if ferr or not isinstance(reference, dict):
            res["problem"] = "reference unreadable"
            continue
        plots = doc["normalized"]["plots"]
        for name, rule in info["spec"]["series"].items():
            state, detail = compare_points(plots.get(name), reference.get(rule["reference"]), rule)
            res["series"][name] = {"reference": rule["reference"], "mode": rule["mode"], "ok": state == "ok",
                                   "state": state, "detail": detail}
        all_ok = all(sres["state"] == "ok" for sres in res["series"].values())
        invalid = [n for n, sres in res["series"].items() if sres["state"] == "invalid"]
        if invalid:
            res["problem"] = "invalid data in series %s: %s" % (", ".join(invalid),
                                                               res["series"][invalid[0]]["detail"])
            res["verdict"] = "incomplete"
        else:
            res["verdict"] = "concordant" if all_ok else "divergent"
    verdicts = [r["verdict"] for r in report["cases"].values()]
    _write_statuses(root, report, rdir)
    if "divergent" in verdicts:
        report["status"] = "divergent"
    elif "incomplete" in verdicts or c["problems"] or not verdicts:
        report["status"] = "incomplete"
    elif report["calibration_written"] and report["calibration_verified"]:
        report["status"] = "recalibrated"
    else:
        report["status"] = "incomplete"
        report["problems"].append("every case is concordant, but the calibration file was not written and "
                                  "verified: recalibration NOT completed")


def _write_statuses(root, report, rdir):
    path = _calib_dir(root) / "capabilities.json"
    calib, err = core.read_json(path)
    if err or not isinstance(calib, dict) or not isinstance(calib.get("capabilities"), dict):
        report["problems"].append("capabilities.json unreadable at write time: nothing written")
        return
    concordant = {case for case, r in report["cases"].items() if r["verdict"] == "concordant"}
    current, stale = [], []
    for cap, entry in sorted(calib["capabilities"].items()):
        if not isinstance(entry, dict):
            continue
        cases = entry.get("cases") if isinstance(entry.get("cases"), list) else []
        evidence = entry.get("evidence_artifacts") if isinstance(entry.get("evidence_artifacts"), list) else []
        # CURRENT only when every listed case is concordant, the run detected the capability, and the
        # capability's own evidence names the independent references compared (the runner's contract)
        ok = bool(cases) and all(cs in concordant for cs in cases) \
            and any(cap in report["cases"][cs]["capabilities_detected"] for cs in cases) \
            and all(report["cases"][cs]["reference_name"] in evidence for cs in cases)
        (current if ok else stale).append(cap)
    report["stale"] = stale
    if not current:
        report["problems"].append("no capability re-exercised with success: capabilities.json left unchanged")
        return
    try:
        backup = rdir / "capabilities.before.json"
        shutil.copy2(str(path), str(backup))
        if core.sha256_file(backup) != core.sha256_file(path):
            report["problems"].append("backup of capabilities.json could not be verified: nothing written")
            return
        report["calibration_backup"] = str(backup)
        stamp = _now()
        for cap in current:
            e = calib["capabilities"][cap]
            e["calibration_status"] = "CURRENT"
            for k in ("stale_reason", "stale_since"):
                e.pop(k, None)
        for cap in stale:
            e = calib["capabilities"][cap]
            if isinstance(e, dict) and e.get("calibration_status") == "CURRENT":
                e["calibration_status"] = "STALE"
                e["stale_reason"] = "not re-exercised with success by the recalibration of %s" % stamp
                e["stale_since"] = stamp
        env = calib.get("environment") if isinstance(calib.get("environment"), dict) else {}
        env.update({"pinets_version": report["pinets_version"], "executor_fingerprint": report["executor_fingerprint"],
                    "normalization_schema": report["normalization_schema"], "calibrated_at": stamp[:10]})
        calib["environment"] = env
        calib.setdefault("history", []).append({
            "at": stamp, "event": "guided recalibration",
            "current": current, "stale": stale,
            "cases": {k: v["verdict"] for k, v in report["cases"].items()},
            "results": "%s/%s" % (RESULTS_REL.as_posix(), rdir.name), "contract_sha256": report["contract_sha256"],
            "note": "capability_status unchanged; CURRENT never implies GATING"})
        core.atomic_write_json(path, calib)
    except OSError as exc:
        report["problems"].append("capabilities.json could not be written: %s" % exc)
        return
    report["calibration_written"] = True
    report["current"] = current
    # final verification: what is on disk is what was decided
    after, aerr = core.read_json(path)
    caps = (after or {}).get("capabilities") if isinstance(after, dict) else None
    envd = (after or {}).get("environment") if isinstance(after, dict) else None
    ok = isinstance(caps, dict) and isinstance(envd, dict) \
        and all(caps.get(cp, {}).get("calibration_status") == "CURRENT" for cp in current) \
        and all(caps.get(cp, {}).get("calibration_status") != "CURRENT" for cp in stale) \
        and envd.get("pinets_version") == report["pinets_version"] \
        and envd.get("executor_fingerprint") == report["executor_fingerprint"] \
        and envd.get("normalization_schema") == report["normalization_schema"]
    report["calibration_verified"] = bool(ok)
    if not ok:
        report["problems"].append("capabilities.json re-read after writing does not match the decision")
