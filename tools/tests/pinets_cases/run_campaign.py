"""Capability probe: run one engine on the generic cases and RECORD results.

This is not a test suite. An engine outcome — concordance, divergence,
failure reported by the engine — is a result. Nothing here changes a source,
an expected value, a calibration, a capability status or a validation
status, and nothing here grants any gating. The canonical comparator of the
thin adapter is not used across versions.

What this launcher guarantees about ITSELF:

  * a fresh attempt never reads the report of an earlier one: the output
    directory must be new or empty, and a report file that exists before its
    own attempt stops the campaign;
  * the files actually used are fingerprinted and must match the manifest;
    every run report must name the same source and dataset fingerprints;
  * engine identity, schemas, statuses and payload integrity of BOTH
    executions are checked before any concordance or determinism is stated;
  * the configuration DECLARED by each run report must equal the one that
    was requested ({} when the case has no configuration file): a missing,
    malformed or different configuration is a problem of the attempt;
  * a failure reported by the engine (valid report, execution status FAIL,
    error message) is distinguished from a failure of the launcher or a
    missing / invalid report;
  * a campaign with an unusable attempt is UNUSABLE: non-zero exit, and no
    durable record is written.

Usage (from the repository root):
    python3 -m tools.tests.pinets_cases.run_campaign --out-dir NEW_DIR \
        --campaign-id ID --observed-on YYYY-MM-DD \
        [--executor tools/pine_exec] [--cases ID,ID] [--observations FILE]

Exit codes: 0 campaign complete / 1 campaign unusable / 2 usage or refusal.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.tests.pinets_cases import cases_lib as lib

HARNESS_FILES = ("run_campaign.py", "cases_lib.py")
ENGINE_FILES = ("package.json", "dist/pinets.min.es.js")
TIMEOUT_S = 180


class Refusal(Exception):
    """The campaign cannot even start (usage or material problem)."""


def relative_label(path):
    try:
        return Path(path).resolve().relative_to(lib.REPO.resolve()).as_posix()
    except ValueError:
        return "outside-workspace/" + Path(path).name


def prepare_out_dir(out_dir):
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        if not out_dir.is_dir() or any(out_dir.iterdir()):
            raise Refusal("output directory %s is not empty: a campaign "
                          "writes in a new or empty directory, so no earlier "
                          "report can be taken for a new result" % out_dir)
    else:
        out_dir.mkdir(parents=True)
    return out_dir


def select_cases(manifest, wanted):
    cases = manifest["cases"]
    if wanted:
        known = {c["id"] for c in cases}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            raise Refusal("unknown case(s): %s" % ", ".join(unknown))
        cases = [c for c in cases if c["id"] in wanted]
    return cases


def check_material(cases):
    """Fingerprints of the files ACTUALLY on disk against the manifest."""
    scope, problems = [], []
    for case in cases:
        entry = {"case": case["id"]}
        for key in ("source", "dataset", "expected", "config"):
            if key not in case:
                continue
            path = lib.resolve(case[key])
            if not path.is_file():
                problems.append("%s: %s missing (%s)" % (case["id"], key, case[key]))
                continue
            actual = lib.sha256_file(path)
            entry[key + "_sha256"] = actual
            if actual != case[key + "_sha256"]:
                problems.append("%s: %s differs from the manifest fingerprint"
                                % (case["id"], key))
        scope.append(entry)
    if problems:
        raise Refusal("case material does not match the manifest: "
                      + "; ".join(problems))
    return scope


def engine_facts(executor):
    """Identity facts read from the executor directory itself, independent
    of what the run reports declare."""
    executor = Path(executor)
    facts = {"executor": relative_label(executor), "files": {}}
    pkg = executor / "node_modules" / "pinets" / "package.json"
    try:
        facts["installed_pinets_version"] = \
            lib.loads_strict(pkg.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        facts["installed_pinets_version"] = None
    for rel in ENGINE_FILES:
        path = executor / "node_modules" / "pinets" / rel
        facts["files"]["node_modules/pinets/" + rel] = \
            lib.sha256_file(path) if path.is_file() else None
    for rel in ("package.json", "package-lock.json", "runner.mjs", "normalize.mjs"):
        path = executor / rel
        facts["files"][rel] = lib.sha256_file(path) if path.is_file() else None
    return facts


def recompute_payload_sha(executor, report_path):
    """Integrity of a normalized payload, recomputed with the canonical
    function of the SAME executor (no second normalizer is written here)."""
    script = ("import { readFileSync } from 'node:fs';"
              "import { payloadSha256 } from './normalize.mjs';"
              "const r = JSON.parse(readFileSync(process.argv[1], 'utf8'));"
              "process.stdout.write(payloadSha256(r.normalized));")
    try:
        proc = subprocess.run(["node", "--input-type=module", "-e", script,
                               str(report_path)], cwd=str(executor),
                              capture_output=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", "replace")[-300:]
    return proc.stdout.decode("utf-8").strip(), None


def requested_configuration(case):
    """Configuration asked for this case: the content of its configuration
    file, or {} when it has none. Raises ValueError when the file is not a
    JSON object."""
    if "config" not in case:
        return {}
    config = lib.loads_strict(lib.resolve(case["config"]).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("configuration file of %s is not a JSON object" % case["id"])
    return config


def attempt(executor, case, out_path, facts):
    """One execution. Returns {returncode, report, problems}: `problems`
    non-empty means the ATTEMPT is unusable — this is never an engine
    result."""
    result = {"returncode": None, "report": None, "problems": []}
    problems = result["problems"]
    if out_path.exists():
        problems.append("report file already present before its own attempt")
        return result
    try:
        requested = requested_configuration(case)
    except (OSError, ValueError) as exc:
        problems.append("requested configuration unreadable: %s" % exc)
        return result
    cmd = ["node", "runner.mjs", "run", "--source", str(lib.resolve(case["source"])),
           "--dataset", str(lib.resolve(case["dataset"])), "--out", str(out_path)]
    if "config" in case:
        cmd += ["--config", str(lib.resolve(case["config"]))]
    try:
        proc = subprocess.run(cmd, cwd=str(executor), capture_output=True,
                              timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        problems.append("launcher timeout after %d s" % TIMEOUT_S)
        return result
    except OSError as exc:
        problems.append("launcher could not start: %s" % exc)
        return result
    result["returncode"] = proc.returncode
    stderr_tail = proc.stderr.decode("utf-8", "replace").strip()[-300:]
    if proc.returncode not in (0, 1):
        problems.append("launcher exit code %d (infrastructure, not an engine "
                        "result): %s" % (proc.returncode, stderr_tail))
        return result
    if not out_path.is_file():
        problems.append("no run report produced: %s" % stderr_tail)
        return result
    try:
        report = lib.loads_strict(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append("run report unreadable or invalid: %s" % exc)
        return result
    if not isinstance(report, dict):
        problems.append("run report is not a JSON object")
        return result
    result["report"] = report
    if report.get("schema") != lib.RUN_SCHEMA:
        problems.append("run report schema %r, expected %r"
                        % (report.get("schema"), lib.RUN_SCHEMA))
    for key in ("source", "dataset"):
        if report.get(key + "_sha256") != case[key + "_sha256"]:
            problems.append("run report names another %s fingerprint" % key)
    if "configuration" not in report:
        problems.append("run report declares no configuration")
    elif not isinstance(report["configuration"], dict):
        problems.append("run report configuration is malformed (%s in place "
                        "of an object)" % type(report["configuration"]).__name__)
    elif report["configuration"] != requested:
        problems.append("run report declares a configuration different from "
                        "the one requested: declared %s, requested %s"
                        % (json.dumps(report["configuration"], sort_keys=True),
                           json.dumps(requested, sort_keys=True)))
    if not isinstance(report.get("run_id"), str) or not report["run_id"]:
        problems.append("run report has no run_id")
    if not isinstance(report.get("pinets_version"), str) or not report["pinets_version"]:
        problems.append("run report has no engine version")
    elif report["pinets_version"] != facts["installed_pinets_version"]:
        problems.append("run report engine version %r differs from the "
                        "installed engine %r" % (report["pinets_version"],
                                                 facts["installed_pinets_version"]))
    if not lib.is_hex64(report.get("executor_fingerprint")):
        problems.append("run report has no valid executor fingerprint")
    if not isinstance(report.get("normalization_schema"), str) \
            or not report["normalization_schema"]:
        problems.append("run report has no normalization schema")
    status = report.get("execution_status")
    if status == lib.EXECUTION_PASS:
        if proc.returncode != 0:
            problems.append("status PASS with exit code %d" % proc.returncode)
        if report.get("error") is not None:
            problems.append("status PASS with an error recorded")
        payload = report.get("normalized")
        if not isinstance(payload, dict):
            problems.append("status PASS without a normalized payload")
        else:
            if payload.get("schema") != report.get("normalization_schema"):
                problems.append("payload schema differs from the declared "
                                "normalization schema")
            if not lib.is_hex64(report.get("normalized_payload_sha256")):
                problems.append("status PASS without a payload fingerprint")
            else:
                sha, err = recompute_payload_sha(executor, out_path)
                if sha is None:
                    problems.append("payload fingerprint could not be "
                                    "recomputed: %s" % err)
                elif sha != report["normalized_payload_sha256"]:
                    problems.append("payload fingerprint does not match the "
                                    "payload")
    elif status == lib.EXECUTION_FAIL:
        if proc.returncode != 1:
            problems.append("status FAIL with exit code %d" % proc.returncode)
        error = report.get("error")
        if not isinstance(error, dict) or not isinstance(error.get("message"), str) \
                or not error["message"].strip():
            problems.append("status FAIL without an error message")
        if report.get("normalized") is not None:
            problems.append("status FAIL with a normalized payload")
    else:
        problems.append("execution status %r is not admitted" % (status,))
    return result


def identity_of(report):
    return {k: report.get(k) for k in
            ("pinets_version", "executor_fingerprint", "normalization_schema")}


def observe_case(executor, case, out_dir, facts):
    expected = lib.loads_strict(lib.resolve(case["expected"]).read_text(encoding="utf-8"))
    obs = {"case": case["id"], "family": case["family"]}
    for key in ("source", "dataset", "expected", "config"):
        if key in case:
            obs[key + "_sha256"] = case[key + "_sha256"]
    runs = [attempt(executor, case, out_dir / ("%s.run%d.json" % (case["id"], n)), facts)
            for n in (1, 2)]
    unusable = ["run %d: %s" % (n + 1, p) for n, r in enumerate(runs)
                for p in r["problems"]]
    reports = [r["report"] for r in runs]
    if not unusable:
        if identity_of(reports[0]) != identity_of(reports[1]):
            unusable.append("engine identity differs between the two runs")
        if reports[0]["run_id"] == reports[1]["run_id"]:
            unusable.append("the two runs carry the same run_id")
    if unusable:
        obs["outcome"] = lib.CASE_HARNESS_FAILURE
        obs["harness_problems"] = unusable
        return obs, None
    first, second = reports
    identity = identity_of(first)
    obs.update(identity)
    obs.update({
        "execution_status": [first["execution_status"], second["execution_status"]],
        "capabilities_used": first.get("capabilities_used"),
        "unclassified_tokens": first.get("unclassified_tokens"),
        "calibration_environment_match": first.get("calibration_environment_match"),
    })
    statuses = set(obs["execution_status"])
    if statuses == {lib.EXECUTION_FAIL}:
        messages = [first["error"]["message"], second["error"]["message"]]
        obs["error"] = messages[0]
        obs["error_reported_by"] = "engine"
        if messages[0] == messages[1]:
            obs["outcome"] = lib.CASE_EXECUTION_FAIL
        else:
            obs["outcome"] = lib.CASE_NOT_DETERMINISTIC
            obs["errors"] = messages
        return obs, identity
    if statuses != {lib.EXECUTION_PASS}:
        obs["outcome"] = lib.CASE_NOT_DETERMINISTIC
        obs["errors"] = [(r.get("error") or {}).get("message") for r in reports]
        return obs, identity
    invalid = ["run %d: %s" % (n + 1, p) for n, r in enumerate(reports)
               for p in lib.payload_problems(r["normalized"])]
    if invalid:
        obs["outcome"] = lib.CASE_INVALID_PAYLOAD
        obs["payload_problems"] = invalid
        return obs, identity
    obs["normalized_payload_sha256"] = first["normalized_payload_sha256"]
    obs["deterministic"] = (first["normalized_payload_sha256"]
                            == second["normalized_payload_sha256"])
    payload = first["normalized"]
    comparison = lib.compare_case(expected, payload)
    obs["series"] = comparison["series"]
    obs["unexpected_payload_keys"] = comparison["unexpected_payload_keys"]
    obs["alerts_recorded"] = len(payload.get("alerts") or [])
    obs["warnings_recorded"] = list(payload.get("warnings") or [])
    obs["internal_keys_present"] = list(payload.get("internal_keys_present") or [])
    obs["outcome"] = lib.case_outcome(comparison) if obs["deterministic"] \
        else lib.CASE_NOT_DETERMINISTIC
    return obs, identity


def run(args):
    out_dir = prepare_out_dir(args.out_dir)
    executor = Path(args.executor).resolve()
    if not (executor / "runner.mjs").is_file():
        raise Refusal("no runner.mjs in executor directory %s" % executor)
    manifest = lib.load_manifest()
    wanted = [c for c in (args.cases or "").split(",") if c]
    cases = select_cases(manifest, wanted)
    scope = check_material(cases)
    facts = engine_facts(executor)
    observations, identities = [], []
    for case in cases:
        obs, identity = observe_case(executor, case, out_dir, facts)
        observations.append(obs)
        if identity and identity not in identities:
            identities.append(identity)
    reasons = []
    for obs in observations:
        if obs["outcome"] in lib.UNUSABLE_OUTCOMES:
            reasons.append("%s: %s" % (obs["case"], obs["outcome"]))
    if len(identities) > 1:
        reasons.append("several engine identities inside one campaign")
    if not identities and not reasons:
        reasons.append("no engine identity could be established")
    status = lib.CAMPAIGN_UNUSABLE if reasons else lib.CAMPAIGN_COMPLETE
    summary = {
        "schema": lib.OBSERVATION_SCHEMA_V2,
        "nature": "observation d'un moteur sur des cas generiques ; ni test "
                  "du dispositif, ni calibration, ni validation TradingView ; "
                  "aucun statut gating",
        "campaign": {
            "id": args.campaign_id,
            "observed_on": args.observed_on,
            "status": status,
            "unusable_reasons": reasons,
            "scope": scope,
            "scope_note": "cette campagne porte sur ces cas et ces empreintes "
                          "seulement ; elle ne dit rien d'un cas ajoute ou "
                          "modifie ensuite",
            "manifest_sha256": lib.sha256_file(lib.MANIFEST),
            "harness": {name: lib.sha256_file(lib.HERE / name)
                        for name in HARNESS_FILES},
            "engine": facts,
        },
        "engine_identities": identities,
        "counts": {o: sum(1 for x in observations if x["outcome"] == o)
                   for o in lib.CASE_OUTCOMES},
        "observations": observations,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    (out_dir / "campaign.json").write_text(text, encoding="utf-8")
    written = None
    if args.observations and status == lib.CAMPAIGN_COMPLETE:
        target = Path(args.observations)
        if target.exists():
            raise Refusal("durable record %s already exists: a new campaign is "
                          "recorded separately, an earlier record is never "
                          "overwritten" % target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written = str(target)
    print(json.dumps({"campaign_status": status, "unusable_reasons": reasons,
                      "counts": summary["counts"],
                      "durable_record_written": written}, ensure_ascii=False))
    return 0 if status == lib.CAMPAIGN_COMPLETE else 1


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--observed-on", required=True)
    parser.add_argument("--executor", default=str(lib.PINE_EXEC))
    parser.add_argument("--cases")
    parser.add_argument("--observations")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Refusal as exc:
        print("campaign refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
