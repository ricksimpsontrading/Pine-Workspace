# SPDX-License-Identifier: Apache-2.0
"""TradingView validation state: single mechanical owner.

`inspect_validation` is THE implementation of the validation axes — schema,
types, required fields, identities, status coherence, references, evidence
hashes and source freshness. scan.py and the validation-status CLI (used by
pine-release) both consume it: no divergent readers. Any incoherence yields
an actionable diagnostic and integrity BROKEN — never a false `passed`.

validation/ is exclusively for TradingView observations (spec section 51.1).
'stale' is DERIVED, never persisted (spec section 51.3).

Promotion protocol (spec section 51.4): the whole check-then-write
transaction runs under an exclusive file lock (current.json.lock) so two PWS
promotions cannot interleave; the run report is written immutably first;
current.json is re-read inside the lock; a concurrent pointer change, an
older run, or a timestamp tie refuses promotion with an actionable conflict.
run_id must be a safe identifier and every written/read path is physically
confined to validation/ before use.

Run report schema versions (spec sections 51.4 / 51.5):
  1  free-text results. READ compatibility only: reports already recorded
     stay readable and admissible on their SHA, never rewritten. A version-1
     report can no longer be promoted. Reading a version-1 file establishes
     nothing about the date it was created.
  2  one controlled verdict per control, unique control identifiers,
     optional group confirmations, optional scope. Verdicts are examined
     BEFORE coverage: a failed control is never hidden by missing results.
A control without a recorded result is "not reported": nothing is asserted
about whether it was executed.

Minimal compilation (spec section 30.5), scope "compilation": errors and
warnings are recorded SEPARATELY, each with an explicit `reported` flag (an
absence of observation is stated, never guessed); the applicable behavioural
controls are listed `not-run`, their results are never invented; such a run
is never `passed`. Recording and promotion are distinct: a valid report is
always kept as an immutable run; on the SAME SHA as the recognized current
run it replaces that run only when it is `failed`. Every existing
protection (integrity, confinement, lock, concurrent witness, older run,
clock tie) applies unchanged.
"""
import datetime
import re
import secrets
from pathlib import Path

from . import core

PERSISTABLE_RUN_STATUSES = ("in-progress", "passed", "failed", "partial")
RUN_SCHEMA_LEGACY = 1
RUN_SCHEMA_CURRENT = 2
# verdicts of an APPLICABLE control; "n-a" is reserved to controls explicitly
# declared not applicable in the matrix
APPLICABLE_VERDICTS = ("passed", "failed", "not-run", "indeterminate")
NOT_APPLICABLE_VERDICT = "n-a"
# scope "compilation": minimal compilation observation (spec section 30.5) —
# never a validation, so never `passed`
RUN_SCOPES = ("campaign", "compilation")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# spec 51.4 minimum content of a run report — SHARED CONTRACT enforced at
# promotion (refusal) AND at inspection (integrity BROKEN): an incomplete
# report is never promoted and never trusted as any status (3rd external
# audit, item 1). Keys must be PRESENT; None is allowed only where the spec
# allows it (git_commit, working_tree, fallback_reason).
RUN_REPORT_REQUIRED_KEYS = (
    "run_id", "status", "source", "source_sha256", "started_at",
    "completed_at", "git_commit", "working_tree", "requested_mode",
    "effective_mode", "fallback_reason", "matrix", "results", "anomalies",
    "evidence", "conclusion",
)


def report_schema_version(report):
    """Schema version of a run report: 1 when absent (reports written before
    the field existed), else the declared integer. None when invalid."""
    if not isinstance(report, dict):
        return None
    sv = report.get("schema_version", RUN_SCHEMA_LEGACY)
    if not isinstance(sv, int) or isinstance(sv, bool) \
            or sv not in (RUN_SCHEMA_LEGACY, RUN_SCHEMA_CURRENT):
        return None
    return sv


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _v2_controls(report, problems):
    """Validate matrix/results/groups of a version-2 report. Returns
    (applicable_ids, verdicts_by_id) or None when the structure is invalid."""
    matrix, results = report["matrix"], report["results"]
    if not isinstance(matrix, list):
        problems.append("matrix must be a list of control entries")
        return None
    if not isinstance(results, dict):
        problems.append("results must be an object mapping control ids to "
                        "recorded verdicts")
        return None
    ids, applicable, not_applicable = [], [], []
    for i, entry in enumerate(matrix):
        if not isinstance(entry, dict) or not _nonblank(entry.get("id")) \
                or not _nonblank(entry.get("test")) \
                or not isinstance(entry.get("applicable"), bool):
            problems.append("matrix entry %d must be an object with a non-empty "
                            "'id', a non-empty 'test' and a boolean "
                            "'applicable'" % i)
            return None
        if entry["id"] in ids:
            problems.append("duplicate control id %r in the matrix" % entry["id"])
            return None
        ids.append(entry["id"])
        (applicable if entry["applicable"] else not_applicable).append(entry["id"])
    ok = True
    verdicts = {}
    for key, value in results.items():
        if key not in ids:
            problems.append("result %r references a control id absent from "
                            "the matrix" % (key,))
            ok = False
            continue
        if not isinstance(value, dict):
            problems.append("result %r must be an object with a controlled "
                            "verdict (free text is not a verdict)" % (key,))
            ok = False
            continue
        verdict = value.get("verdict")
        admitted = APPLICABLE_VERDICTS if key in applicable \
            else (NOT_APPLICABLE_VERDICT,)
        if not isinstance(verdict, str) or verdict not in admitted:
            problems.append("result %r: verdict %r not admitted for %s control "
                            "(admitted: %s)"
                            % (key, verdict,
                               "an applicable" if key in applicable
                               else "a non-applicable",
                               ", ".join(admitted)))
            ok = False
            continue
        # A not-run / n-a verdict records that NO observation took place: the
        # author may be null (never invented), the observation states why and
        # the timestamp stays required (spec 51.4, amendment 2026-11-06).
        author_optional = verdict in ("not-run", NOT_APPLICABLE_VERDICT)
        author_ok = _nonblank(value.get("observed_by")) or (
            author_optional and value.get("observed_by") is None)
        if not _nonblank(value.get("observation")) or not author_ok \
                or _parse_ts(value.get("at")) is None:
            problems.append("result %r needs a non-blank observation, its "
                            "author (observed_by — may be null only for a "
                            "not-run or n-a verdict) and an RFC 3339 UTC "
                            "timestamp (at)" % (key,))
            ok = False
            continue
        if "group" in value and not _nonblank(value["group"]):
            problems.append("result %r: group must be a non-blank id" % (key,))
            ok = False
            continue
        verdicts[key] = verdict
    groups = report.get("groups", [])
    group_controls = {}
    if not isinstance(groups, list):
        problems.append("groups must be a list")
        return None
    for i, grp in enumerate(groups):
        if not isinstance(grp, dict) or not _nonblank(grp.get("id")):
            problems.append("group %d must be an object with a non-empty id" % i)
            ok = False
            continue
        gid = grp["id"]
        if gid in group_controls:
            problems.append("duplicate group id %r" % gid)
            ok = False
            continue
        controls = grp.get("controls")
        if not isinstance(controls, list) or not controls \
                or not all(isinstance(c, str) for c in controls):
            problems.append("group %r must list the exact controls presented" % gid)
            ok = False
            continue
        unknown = [c for c in controls if c not in ids]
        if unknown:
            problems.append("group %r references control(s) absent from the "
                            "matrix: %s" % (gid, ", ".join(unknown[:5])))
            ok = False
        if not _nonblank(grp.get("presented_text")) \
                or not _nonblank(grp.get("confirmation_text")):
            problems.append("group %r must keep the text presented before the "
                            "confirmation (presented_text) and the confirmation "
                            "received (confirmation_text)" % gid)
            ok = False
        if not _nonblank(grp.get("observed_by")) or _parse_ts(grp.get("at")) is None:
            problems.append("group %r needs its author (observed_by) and an "
                            "RFC 3339 UTC timestamp (at)" % gid)
            ok = False
        group_controls[gid] = controls
    for key, value in results.items():
        if isinstance(value, dict) and _nonblank(value.get("group")):
            gid = value["group"]
            if gid not in group_controls:
                problems.append("result %r references unknown group %r" % (key, gid))
                ok = False
            elif key not in group_controls[gid]:
                problems.append("result %r claims group %r but was not in the "
                                "list presented for that group — a confirmation "
                                "never extends to an unlisted control" % (key, gid))
                ok = False
    if not ok:
        return None
    return applicable, verdicts


def admitted_statuses(applicable, verdicts, scope="campaign"):
    """Statuses coherent with the recorded verdicts (spec section 51.5).
    Ordered evaluation — verdicts BEFORE coverage. Returns (statuses, reason)."""
    reported = [verdicts[c] for c in applicable if c in verdicts]
    unreported = [c for c in applicable if c not in verdicts]
    if "failed" in reported:
        return ("failed",), "at least one applicable control failed"
    if "passed" not in reported:
        return ("in-progress",), "no applicable control passed"
    if unreported:
        return ("in-progress",), ("applicable control(s) not reported: %s"
                                  % ", ".join(unreported[:5]))
    if all(v == "passed" for v in reported):
        if scope == "compilation":
            return ("in-progress",), ("a minimal compilation run is never a "
                                      "validation (spec 30.5)")
        return ("passed", "in-progress"), "every applicable control passed"
    return ("partial", "in-progress"), ("no failure, at least one control "
                                        "not-run or indeterminate")


def _compilation_problems(report, applicable, verdicts):
    """Contract of a minimal compilation run (scope 'compilation')."""
    problems = []
    kinds = {e["id"]: e.get("kind") for e in report["matrix"]}
    comp = [c for c in applicable if kinds.get(c) == "compilation"]
    if len(comp) != 1:
        problems.append("a minimal compilation run needs exactly one applicable "
                        "control of kind 'compilation' in the matrix (found %d)"
                        % len(comp))
        return problems
    behavioural = [c for c in applicable if c != comp[0]]
    if not behavioural:
        problems.append("a minimal compilation run lists the applicable "
                        "behavioural controls (as not-run): none is listed")
    invented = [c for c in behavioural if c in verdicts and verdicts[c] != "not-run"]
    if invented:
        problems.append("a minimal compilation run observes no behaviour: "
                        "control(s) %s must be 'not-run'" % ", ".join(invented[:5]))
    block = report.get("compilation")
    if not isinstance(block, dict):
        problems.append("a minimal compilation run needs a 'compilation' object "
                        "with separate 'errors' and 'warnings'")
        return problems
    parsed = {}
    for key in ("errors", "warnings"):
        part = block.get(key)
        if not isinstance(part, dict) or not isinstance(part.get("reported"), bool) \
                or not isinstance(part.get("items"), list) \
                or not all(_nonblank(i) for i in part["items"]):
            problems.append("compilation.%s must be an object with a boolean "
                            "'reported' and a list 'items' of non-blank texts"
                            % key)
            continue
        if not part["reported"] and part["items"]:
            problems.append("compilation.%s: items recorded while 'reported' is "
                            "false — an absence of observation carries no item"
                            % key)
            continue
        parsed[key] = part
    if len(parsed) != 2:
        return problems
    verdict = verdicts.get(comp[0])
    errors = parsed["errors"]
    if errors["reported"] and errors["items"] and verdict != "failed":
        problems.append("compilation errors are reported: the compilation "
                        "control must be 'failed', got %r" % (verdict,))
    if verdict == "failed" and not (errors["reported"] and errors["items"]):
        problems.append("compilation control 'failed' without any reported "
                        "error")
    if verdict == "passed" and not errors["reported"]:
        problems.append("compilation control 'passed' while no observation of "
                        "errors is reported — the absence of errors must have "
                        "been observed")
    return problems


def unreported_controls(report):
    """Applicable controls of a version-2 report WITHOUT a recorded result.
    'Not reported' asserts nothing about whether they were executed."""
    if report_schema_version(report) != RUN_SCHEMA_CURRENT:
        return []
    matrix, results = report.get("matrix"), report.get("results")
    if not isinstance(matrix, list) or not isinstance(results, dict):
        return []
    return [e["id"] for e in matrix
            if isinstance(e, dict) and e.get("applicable") is True
            and isinstance(e.get("id"), str) and e["id"] not in results]


def validate_run_report(report):
    """Mechanical validation of a run report against the spec 51.4 minimum.
    Returns a list of actionable problem strings (empty = valid)."""
    if not isinstance(report, dict):
        return ["report is not a JSON object"]
    problems = []
    version = report_schema_version(report)
    if version is None:
        return ["schema_version must be %d or %d, got %r"
                % (RUN_SCHEMA_LEGACY, RUN_SCHEMA_CURRENT,
                   report.get("schema_version"))]
    for key in RUN_REPORT_REQUIRED_KEYS:
        if key not in report:
            problems.append("missing key %s" % key)
    if problems:
        return problems
    if not core.is_safe_id(report["run_id"]):
        problems.append("run_id is not a safe identifier")
    if report["status"] not in PERSISTABLE_RUN_STATUSES:
        problems.append("status %r not persistable" % (report["status"],))
    if not isinstance(report["source"], str) or not report["source"]:
        problems.append("source must be a non-empty string")
    if not isinstance(report["source_sha256"], str) \
            or not HEX64_RE.match(report["source_sha256"] or ""):
        problems.append("source_sha256 must be a 64-hex string")
    started = _parse_ts(report["started_at"])
    completed = _parse_ts(report["completed_at"])
    for ts_key, parsed in (("started_at", started), ("completed_at", completed)):
        if parsed is None:
            problems.append("%s must be RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % ts_key)
    if started is not None and completed is not None and started > completed:
        problems.append("started_at is after completed_at")
    if report["git_commit"] is not None and not isinstance(report["git_commit"], str):
        problems.append("git_commit must be a string or null")
    if report["working_tree"] not in ("clean", "dirty", None):
        problems.append("working_tree must be 'clean', 'dirty' or null")
    for mode_key in ("requested_mode", "effective_mode"):
        if not isinstance(report[mode_key], str) or not report[mode_key]:
            problems.append("%s must be a non-empty string" % mode_key)
    if report["fallback_reason"] is not None \
            and not isinstance(report["fallback_reason"], str):
        problems.append("fallback_reason must be a string or null")
    if version == RUN_SCHEMA_CURRENT:
        scope = report.get("scope", "campaign")
        if scope not in RUN_SCOPES:
            problems.append("scope %r not in %s" % (scope, list(RUN_SCOPES)))
            scope = "campaign"
        controls = _v2_controls(report, problems)
        if controls is not None and report["status"] in PERSISTABLE_RUN_STATUSES:
            statuses, reason = admitted_statuses(controls[0], controls[1], scope)
            if report["status"] not in statuses:
                problems.append(
                    "status %r is incoherent with the recorded verdicts (%s) — "
                    "admitted: %s (spec 51.5)"
                    % (report["status"], reason, ", ".join(statuses)))
        if controls is not None and scope == "compilation":
            problems.extend(_compilation_problems(report, controls[0], controls[1]))
        if scope != "compilation" and "compilation" in report:
            problems.append("a 'compilation' object is reserved to runs of scope "
                            "'compilation'")
        _check_tail(report, problems)
        return problems
    # ---- version 1 (read compatibility) -----------------------------------
    # matrix/results contract (4th external audit, item 1). The mechanical
    # check verifies that results are RECORDED and coherent with the
    # applicable controls — it never claims to prove the observation actually
    # took place (that honesty boundary is the spec's, section 30.4: a
    # properly recorded manual observation from the holder is admissible, no
    # systematic screenshot is required).
    matrix_ok = isinstance(report["matrix"], list)
    if not matrix_ok:
        problems.append("matrix must be a list of control entries")
    results_ok = isinstance(report["results"], dict)
    if not results_ok:
        problems.append("results must be an object mapping controls to recorded outcomes")
    applicable = []
    if matrix_ok:
        for i, entry in enumerate(report["matrix"]):
            if not isinstance(entry, dict) \
                    or not isinstance(entry.get("test"), str) \
                    or not entry["test"].strip() \
                    or not isinstance(entry.get("applicable"), bool):
                problems.append("matrix entry %d must be an object with a "
                                "non-empty 'test' string and a boolean "
                                "'applicable'" % i)
                matrix_ok = False
                break
            if entry["applicable"]:
                applicable.append(entry["test"])
    if results_ok:
        for key, value in report["results"].items():
            if not isinstance(key, str) or not key.strip() \
                    or not isinstance(value, str) or not value.strip():
                problems.append("result %r must map a control name to a "
                                "non-blank recorded outcome/observation" % (key,))
                results_ok = False
                break
    if report["status"] in ("passed", "failed", "partial") \
            and matrix_ok and results_ok:
        if not applicable:
            problems.append("a completed run (%s) requires at least one "
                            "applicable control in the matrix (spec 51.5)"
                            % report["status"])
        uncovered = [t for t in applicable if t not in report["results"]]
        if uncovered:
            problems.append("applicable control(s) without a recorded result: %s "
                            "— a validation without recorded results is never "
                            "trusted" % ", ".join(uncovered[:5]))
        if report["status"] == "passed":
            # EVERY recorded result counts — a failure recorded outside the
            # matrix must not hide behind an omitted control entry
            failed = [k for k, v in report["results"].items()
                      if str(v).strip().lower() == "failed"]
            if failed:
                problems.append("status 'passed' is incoherent with failed "
                                "result(s): %s" % ", ".join(sorted(failed)[:5]))
    _check_tail(report, problems)
    return problems


def _check_tail(report, problems):
    """Anomalies, evidence and conclusion — common to both schema versions."""
    if not isinstance(report["anomalies"], list):
        problems.append("anomalies must be a list")
    if not isinstance(report["evidence"], list):
        problems.append("evidence must be a list")
    else:
        problems.extend(evidence_entry_problems(report["run_id"], report["evidence"]))
    if not isinstance(report["conclusion"], str) or not report["conclusion"].strip():
        problems.append("conclusion must be a non-blank string")


def evidence_entry_problems(run_id, evidence):
    """Structural validation of evidence entries — SHARED by promotion and
    inspection (mutation and read paths must agree). File existence and hash
    matching are checked at inspection, where the files must be present."""
    problems = []
    for ev in evidence:
        if not isinstance(ev, dict):
            problems.append("evidence entries must be objects, got %s"
                            % type(ev).__name__)
            continue
        ev_rel = ev.get("path")
        ev_sha = ev.get("sha256")
        ev_type = ev.get("type")
        if not isinstance(ev_rel, str) or not ev_rel or Path(ev_rel).is_absolute() \
                or not isinstance(ev_sha, str) or not HEX64_RE.match(ev_sha) \
                or not isinstance(ev_type, str) or not ev_type:
            problems.append("evidence entries need a relative path, a type and "
                            "a 64-hex sha256")
            continue
        if ".." in Path(ev_rel).parts:
            problems.append("evidence path %r contains a traversal segment — "
                            "the proof must live in its own run namespace" % ev_rel)
            continue
        if isinstance(run_id, str) and not ev_rel.startswith("evidence/%s/" % run_id):
            problems.append("evidence path %r must live under evidence/%s/ "
                            "(spec 51.4)" % (ev_rel, run_id))
    return problems


def utc_now_rfc3339():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id():
    """Collision-resistant run id, not derived from a local date alone."""
    return "run-%s" % secrets.token_hex(8)


def source_fingerprint(root, source_path):
    """SHA-256 of the source + git identity facts (spec section 29.3)."""
    p = Path(source_path)
    out = {
        "source": str(p),
        "source_sha256": core.sha256_file(p),
        "git_commit": None,
        "working_tree": None,
    }
    state = core.git_state(root)
    if state["is_repo"]:
        out["git_commit"] = state["commit"]
        out["working_tree"] = "dirty" if state["dirty"] else "clean"
    return out


def _lock_path(product_dir):
    """Promotion/init lock lives at the PRODUCT root (gitignored *.lock):
    validation/ stays exclusively for TradingView observations (spec 51.1).
    Lock files must never be deleted while writers may be active."""
    return Path(product_dir) / ".pws-validation.lock"


def _vdir_violation(product_dir):
    """The validation/ directory itself must be a real directory physically
    inside the product root — a symlinked validation/ (internal cross-product
    or external) would make every containment check compare inside the
    foreign tree (adversarial review 2026-09-05, BLOCKING)."""
    product_dir = Path(product_dir)
    if product_dir.is_symlink():
        return ("product root is a symlink — refused (a mutation through it "
                "would land outside the intended tree, spec 6.1.5)")
    vdir = product_dir / "validation"
    if vdir.is_symlink():
        return "validation/ is a symlink — refused (spec 6.1.5 / 51.1)"
    if vdir.exists() and not core.is_within(product_dir, vdir):
        return "validation/ resolves outside the product root — refused"
    current = vdir / "current.json"
    if current.is_symlink():
        return "validation/current.json is a symlink — refused"
    return None


def init_validation_state(product_dir):
    """Create validation/current.json at the unverified state (idempotent:
    refuses to overwrite an existing state). Runs under the same lock as
    promote_run so a concurrent first promotion is never silently lost."""
    product_dir = Path(product_dir)
    violation = _vdir_violation(product_dir)
    if violation:
        return {"created": False, "path": None, "reason": violation}
    target = product_dir / "validation" / "current.json"
    try:
        with core.file_lock(_lock_path(product_dir)):
            if target.exists():
                return {"created": False, "path": str(target), "reason": "already exists"}
            core.atomic_write_json(target, {
                "schema_version": 1,
                "status": "unverified",
                "last_run": None,
            })
    except TimeoutError as exc:
        return {"created": False, "path": str(target), "reason": "lock not acquired: %s" % exc}
    return {"created": True, "path": str(target)}


def _parse_ts(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Single mechanical owner of the validation axes
# ---------------------------------------------------------------------------

def inspect_validation(product_dir, source_path=None):
    """Full mechanical inspection of a product's validation state.

    Returns {persisted, integrity ('OK'|'BROKEN'|None), effective, run_id,
    findings: [{code, severity, path, detail}]}. integrity None means the
    state file is absent (INCOMPLETE, not BROKEN).
    """
    product_dir = Path(product_dir)
    vdir = product_dir / "validation"
    current_path = vdir / "current.json"
    findings = []
    notes = []
    result = {"persisted": None, "integrity": None, "effective": None,
              "run_id": None, "findings": findings, "notes": notes}

    def broken(code, path, detail):
        result["integrity"] = "BROKEN"
        result["effective"] = None
        findings.append({"code": code, "severity": "BROKEN",
                         "path": str(path), "detail": detail})

    violation = _vdir_violation(product_dir)
    if violation:
        broken("VALIDATION_DIR_SYMLINK", vdir, violation)
        return result

    data, err = core.read_json(current_path)
    if err == "missing":
        findings.append({"code": "VALIDATION_STATE_MISSING", "severity": "INCOMPLETE",
                         "path": str(product_dir), "detail": "validation/current.json missing"})
        return result
    if err:
        broken("VALIDATION_STATE_UNREADABLE", current_path, err)
        return result
    if not isinstance(data, dict):
        broken("VALIDATION_STATE_NOT_OBJECT", current_path, "current.json is not a JSON object")
        return result
    sv = data.get("schema_version")
    if sv is not True and sv is not False and sv == 1:
        pass
    else:
        broken("VALIDATION_SCHEMA_VERSION", current_path,
               "schema_version must be 1, got %r" % (sv,))
    status = data.get("status")
    if not isinstance(status, str) or status not in core.VALIDATION_STATUSES:
        broken("VALIDATION_STATUS_INVALID", current_path,
               "status %r not in %s" % (status, list(core.VALIDATION_STATUSES)))
        return result
    result["persisted"] = status

    last_run = data.get("last_run")
    if status == "unverified" and last_run is not None:
        broken("VALIDATION_STATUS_RUN_MISMATCH", current_path,
               "status 'unverified' with a recognized run — incoherent state")
        return result
    if status != "unverified" and last_run is None:
        broken("VALIDATION_STATUS_RUN_MISSING", current_path,
               "status %r implies a recognized run but last_run is null — "
               "a status is never trusted without its run" % status)
        return result
    if last_run is None:
        if result["integrity"] != "BROKEN":
            result["integrity"] = "OK"
            result["effective"] = status
        return result
    if not isinstance(last_run, dict):
        broken("VALIDATION_LASTRUN_INVALID", current_path,
               "last_run must be null or an object, got %s" % type(last_run).__name__)
        return result

    run_id = last_run.get("run_id")
    report_rel = last_run.get("report")
    run_sha = last_run.get("source_sha256")
    completed = last_run.get("completed_at")
    ok_fields = True
    if not core.is_safe_id(run_id):
        broken("VALIDATION_RUNID_UNSAFE", current_path,
               "run_id %r is not a safe identifier" % (run_id,))
        ok_fields = False
    else:
        result["run_id"] = run_id
    if not isinstance(report_rel, str) or not report_rel or Path(report_rel).is_absolute():
        broken("VALIDATION_LASTRUN_FIELDS", current_path,
               "report must be a relative path string, got %r" % (report_rel,))
        ok_fields = False
    if not isinstance(run_sha, str) or not HEX64_RE.match(run_sha or ""):
        broken("VALIDATION_LASTRUN_FIELDS", current_path,
               "source_sha256 must be a 64-hex string, got %r" % (run_sha,))
        ok_fields = False
    if _parse_ts(completed) is None:
        broken("VALIDATION_TIMESTAMP_INVALID", current_path,
               "completed_at %r is not RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ)" % (completed,))
        ok_fields = False
    if not ok_fields:
        return result

    # Normative pointer form (spec 51.2): the recognized report lives at
    # runs/<run_id>.json — a self-referential or loose report path would let
    # current.json carry its own "report" outside the immutable protocol.
    if report_rel != "runs/%s.json" % run_id:
        broken("VALIDATION_REPORT_PATH_FORM", current_path,
               "report must be exactly 'runs/<run_id>.json', got %r" % report_rel)
        return result
    report_path = vdir / report_rel
    if not core.is_within(vdir, report_path):
        broken("VALIDATION_REPORT_ESCAPES", current_path,
               "report path %r escapes validation/" % report_rel)
        return result
    report, rerr = core.read_json(report_path)
    if rerr or not isinstance(report, dict):
        broken("VALIDATION_REPORT_BROKEN", report_path,
               "referenced report %s" % (rerr or "is not a JSON object"))
        return result
    problems = validate_run_report(report)
    if problems:
        broken("VALIDATION_REPORT_INCOMPLETE", report_path,
               "run report violates the spec-51.4 minimum contract — never "
               "trusted as %r: %s" % (status, "; ".join(problems[:6])))
        return result
    if (report.get("run_id") != run_id or report.get("source_sha256") != run_sha
            or report.get("completed_at") != completed):
        broken("VALIDATION_REPORT_IDENTITY", report_path,
               "report identity (run_id/source_sha256/completed_at) does not match "
               "the current.json pointer")
        return result
    rstatus = report.get("status")
    if rstatus not in PERSISTABLE_RUN_STATUSES:
        broken("VALIDATION_REPORT_STATUS_INVALID", report_path,
               "report status %r not persistable" % (rstatus,))
        return result
    if rstatus != status:
        broken("VALIDATION_STATUS_INCOHERENT", current_path,
               "current.json says %r but the recognized run report says %r — "
               "never trusted as %r" % (status, rstatus, status))
        return result

    # Evidence STRUCTURE was already enforced by validate_run_report (the
    # shared contract also refused it at promotion); here only the physical
    # facts remain: containment, existence, hash.
    for ev in report["evidence"]:
        ev_rel = ev["path"]
        ev_path = vdir / ev_rel
        if not core.is_within(vdir, ev_path) or not ev_path.is_file():
            broken("EVIDENCE_MISSING", report_path,
                   "evidence %r missing or escapes validation/" % ev_rel)
            return result
        if core.sha256_file(ev_path) != ev["sha256"]:
            broken("EVIDENCE_HASH_DIVERGES", ev_path,
                   "evidence hash diverges from the recorded sha256")
            return result

    if result["integrity"] == "BROKEN":  # earlier structural finding stands
        return result
    result["integrity"] = "OK"
    if report_schema_version(report) == RUN_SCHEMA_LEGACY:
        notes.append("recognized run report uses an earlier schema version: "
                     "readable and admissible on its SHA; read compatibility "
                     "does not establish when the file was created")
    missing = unreported_controls(report)
    if missing:
        notes.append("control(s) not reported (no recorded result — nothing is "
                     "asserted about their execution): %s" % ", ".join(missing[:10]))
    # Freshness needs the CURRENT source: a deleted/unavailable source makes
    # the persisted value non-applicable — effective is None, never 'passed'
    # (3rd external audit, item 2).
    if source_path is None or not Path(source_path).is_file():
        result["effective"] = None
        findings.append({"code": "VALIDATION_SOURCE_UNAVAILABLE",
                         "severity": "WARNING",
                         "path": str(source_path) if source_path else str(product_dir),
                         "detail": "source unavailable — the persisted status is "
                                   "not applicable and the effective status is "
                                   "indeterminable (restore the source or fix "
                                   "the manifest)"})
    else:
        current_sha = core.sha256_file(source_path)
        result["effective"] = "stale" if current_sha != run_sha else status
        if current_sha != run_sha:
            notes.append("recognized run recorded on a SHA different from the "
                         "declared source: historical, it does not validate the "
                         "current source (effective status stale)")
    return result


def validation_status(product_dir, source_path=None):
    """Derived validation view (CLI / pine-release) — same owner as scan."""
    view = inspect_validation(product_dir, source_path)
    detail = None
    if view["findings"]:
        detail = " ; ".join("%s: %s" % (f["code"], f["detail"])
                            for f in view["findings"][:4])
    return {"persisted": view["persisted"], "integrity": view["integrity"],
            "effective": view["effective"], "detail": detail,
            "findings": view["findings"], "notes": view["notes"]}


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

def promote_run(product_dir, report, current_snapshot_bytes=None):
    """Record a run report then promote it when the protocol allows it.

    Result keys: promoted, recorded (the report was written as an immutable
    run by THIS call), report_path, conflict, notes, unreported_controls.
    A recorded report that is not promoted is never discarded; when it is a
    failure, the result says explicitly that the recognized current run does
    not reflect it."""
    state = {"written": False}
    result = _promote_run(product_dir, report, current_snapshot_bytes, state)
    result.setdefault("notes", [])
    result.setdefault("unreported_controls", [])
    result["recorded"] = state["written"]
    if state["written"] and not result["promoted"] and result.get("conflict") \
            and isinstance(report, dict) and report.get("status") == "failed":
        result["conflict"] += (" — the FAILED run report is kept on disk and "
                               "was NOT promoted: the recognized current run "
                               "does not reflect this failure")
    return result


def _promote_run(product_dir, report, current_snapshot_bytes, state):
    """Write an immutable run report then atomically promote current.json.

    The entire check-then-write transaction is serialized by an exclusive
    lock so concurrent PWS promotions cannot interleave (lost-update safe).
    current_snapshot_bytes: bytes of current.json as read when the run
    STARTED (witness against external mutation during the run).
    """
    product_dir = Path(product_dir)
    vdir = product_dir / "validation"
    current_path = vdir / "current.json"

    problems = validate_run_report(report)
    if problems:
        return {"promoted": False, "report_path": None,
                "conflict": "run report violates the spec-51.4 minimum contract "
                            "— promotion refused: %s" % "; ".join(problems[:6])}
    if report_schema_version(report) != RUN_SCHEMA_CURRENT:
        return {"promoted": False, "report_path": None,
                "conflict": "schema_version 1 is reserved to historical reports "
                            "already recorded — produce a schema_version 2 "
                            "report (spec 51.5)"}
    notes = []
    missing = unreported_controls(report)
    if missing:
        notes.append("control(s) not reported (no recorded result — nothing is "
                     "asserted about their execution): %s" % ", ".join(missing[:10]))
    declared_sha = _declared_source_sha(product_dir)
    if declared_sha is None:
        notes.append("source declared by SCRIPT.json unavailable: the run SHA "
                     "could not be compared, the effective status is "
                     "indeterminable")
    elif declared_sha != report["source_sha256"]:
        notes.append("run recorded on a SHA different from the source declared "
                     "by SCRIPT.json (%s): historical, effective status stale"
                     % declared_sha[:12])
    run_id = report["run_id"]
    status = report["status"]
    sha = report["source_sha256"]
    completed_at = report["completed_at"]

    violation = _vdir_violation(product_dir)
    if violation:
        return {"promoted": False, "report_path": None, "conflict": violation}

    runs_dir = vdir / "runs"
    report_path = runs_dir / ("%s.json" % run_id)
    if not core.is_within(vdir, report_path):
        return {"promoted": False, "report_path": None,
                "conflict": "report destination escapes validation/ — refused"}

    # Evidence files must physically exist and match their hashes AT
    # PROMOTION as well (targeted review 2026-09-06): the run just produced
    # them — promoting a report whose proofs are absent or divergent would
    # only manufacture an instantly-BROKEN state with a burned run_id.
    for ev in report["evidence"]:
        ev_path = vdir / ev["path"]
        if not core.is_within(vdir, ev_path) or not ev_path.is_file():
            return {"promoted": False, "report_path": None,
                    "conflict": "evidence %r missing or escaping validation/ — "
                                "promotion refused" % ev["path"]}
        if core.sha256_file(ev_path) != ev["sha256"]:
            return {"promoted": False, "report_path": None,
                    "conflict": "evidence %r hash diverges from the report — "
                                "promotion refused" % ev["path"]}

    try:
        with core.file_lock(_lock_path(product_dir)):
            if report_path.exists():
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "run report already exists — run reports are "
                                    "immutable; mint a new run_id for a retry "
                                    "(the existing report stays inert)"}
            core.atomic_write_json(report_path, report)
            state["written"] = True
            written, err = core.read_json(report_path)
            if err or written.get("run_id") != run_id:
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "report verification failed: %s" % (err or "identity mismatch")}

            now_bytes = current_path.read_bytes() if current_path.exists() else None
            if current_snapshot_bytes is not None and now_bytes != current_snapshot_bytes:
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "current.json changed since the run started — "
                                    "refusing silent overwrite"}

            current, cerr = core.read_json(current_path)
            if cerr and cerr != "missing":
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "current.json unreadable: %s" % cerr}
            if current is not None and not isinstance(current, dict):
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "current.json is not a JSON object (got %s) — "
                                    "resolve integrity first" % type(current).__name__}
            prev_run = (current or {}).get("last_run")
            if prev_run is not None and not isinstance(prev_run, dict):
                # a corrupt pointer must never be laundered into a silent
                # promotion (targeted review 2026-09-06, spec 51.4 steps 4-5)
                return {"promoted": False, "report_path": str(report_path),
                        "conflict": "recognized last_run is not an object — "
                                    "run order cannot be established, resolve "
                                    "integrity first"}
            if isinstance(prev_run, dict):
                prev_rel = prev_run.get("report")
                prev_path = vdir / str(prev_rel or "")
                if not isinstance(prev_rel, str) or not core.is_within(vdir, prev_path):
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "recognized current run reference invalid — "
                                        "resolve integrity first"}
                prev_report, perr = core.read_json(prev_path)
                if perr or not isinstance(prev_report, dict):
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "recognized current run report %s — "
                                        "resolve integrity first"
                                        % (perr or "is not a JSON object")}
                prev_ts = _parse_ts(prev_report.get("completed_at"))
                new_ts = _parse_ts(completed_at)
                if prev_ts is None:
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "recognized current run has no parseable "
                                        "completed_at — run order cannot be "
                                        "established, resolve integrity first"}
                if new_ts is None:
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "completed_at not parseable — run order "
                                        "cannot be established"}
                if new_ts < prev_ts:
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "run older than the recognized current run — "
                                        "refusing replacement"}
                if new_ts == prev_ts:
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": "clock tie with the recognized current run — "
                                        "actionable conflict, resolve manually"}

            # Minimal compilation (spec 30.5 / 51.4) — evaluated AFTER every
            # protection above: recording and promotion are distinct.
            if report.get("scope") == "compilation" and isinstance(prev_run, dict) \
                    and prev_run.get("source_sha256") == sha:
                if status != "failed":
                    notes.append("minimal compilation run recorded WITHOUT "
                                 "promotion: a recognized current run exists on "
                                 "the same SHA and is kept (status %r)"
                                 % (current or {}).get("status"))
                    return {"promoted": False, "report_path": str(report_path),
                            "conflict": None, "notes": notes,
                            "unreported_controls": missing}
                if (current or {}).get("status") == "passed":
                    notes.append("CONTRADICTION to examine: a failed minimal "
                                 "compilation replaces a recognized run that was "
                                 "'passed' on the same SHA (%s)"
                                 % prev_run.get("run_id"))

            core.atomic_write_json(current_path, {
                "schema_version": 1,
                "status": status,
                "last_run": {
                    "run_id": run_id,
                    "report": "runs/%s.json" % run_id,
                    "source_sha256": sha,
                    "completed_at": completed_at,
                },
            })
    except TimeoutError as exc:
        return {"promoted": False, "report_path": None,
                "conflict": "promotion lock not acquired: %s" % exc}
    return {"promoted": True, "report_path": str(report_path), "conflict": None,
            "notes": notes, "unreported_controls": missing}


def _declared_source_sha(product_dir):
    """SHA-256 of the source DECLARED by SCRIPT.json — never another .pine of
    the same folder. None when the manifest or the source is unavailable."""
    product_dir = Path(product_dir)
    if product_dir.is_symlink():
        return None
    manifest, err = core.read_json(product_dir / "SCRIPT.json")
    if err or not isinstance(manifest, dict):
        return None
    source = manifest.get("source")
    if not isinstance(source, str) or not source:
        return None
    path = product_dir / source
    if not core.is_within(product_dir, path) or not path.is_file():
        return None
    return core.sha256_file(path)
