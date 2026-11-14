"""Generic PineTS capability cases — shared library (no product dependency).

TWO DIFFERENT THINGS LIVE SIDE BY SIDE, never to be confused:

  * tooling tests (tools/tests/test_pinets_cases.py): they check THIS
    material — manifest integrity, expected values reproducible from their
    independent references, comparator logic. They must pass.
  * capability probes (run_campaign.py): they run an engine on the cases and
    RECORD what happens — concordance, divergence or execution failure. A
    probe has no "must pass": an engine failure is a result, not a defect of
    the workspace, and never a reason to change a source or an expected
    value.

Independence contract: an expected value is never produced by the engine
under observation. Every expected series states its provenance. When an
expectation cannot be established with the authorized means, the series is
kept as an exploration and names the missing proof.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PINE_EXEC = REPO / "tools" / "pine_exec"
MANIFEST = HERE / "cases.json"

EXPECTED_SCHEMA = "pws-pinets-case-expected-v1"
MANIFEST_SCHEMA = "pws-pinets-cases-v1"
OBSERVATION_SCHEMA = "pws-pinets-case-observations-v1"     # initial records
OBSERVATION_SCHEMA_V2 = "pws-pinets-case-observations-v2"  # identified campaign
OBSERVATION_SCHEMAS = (OBSERVATION_SCHEMA, OBSERVATION_SCHEMA_V2)
RUN_SCHEMA = "pws-pinets-run-v1"
EXECUTION_PASS = "PINETS_EXECUTION_PASS"
EXECUTION_FAIL = "PINETS_EXECUTION_FAIL"

ESTABLISHED = "established"
EXPLORATION = "exploration"
SERIES_STATUSES = (ESTABLISHED, EXPLORATION)

# outcome of ONE expected series against one engine payload
CONCORDANT = "CONCORDANT"                  # every point equal
CLOSE = "CONCORDANT_WITHIN_TOLERANCE"      # same na pattern, tiny float gap
DIVERGENT = "DIVERGENT"
MISSING = "MISSING_IN_PAYLOAD"
OBSERVED = "OBSERVED_ONLY"
SERIES_OUTCOMES = (CONCORDANT, CLOSE, DIVERGENT, MISSING, OBSERVED)

# Relative tolerance used ONLY to describe a gap, never to move an expected
# value. It is the tolerance already recorded for floating accumulation order
# in the calibration manifest of the thin adapter (capability ta-ema).
RELATIVE_TOLERANCE = 1e-9

# outcome of ONE case
CASE_EXECUTION_FAIL = "EXECUTION_FAIL"
CASE_CONCORDANT = "CONCORDANT"
CASE_CLOSE = "CONCORDANT_WITHIN_TOLERANCE"
CASE_DIVERGENT = "DIVERGENT"
CASE_NOT_DETERMINISTIC = "NOT_DETERMINISTIC"
CASE_OBSERVED_ONLY = "OBSERVED_ONLY"  # no established series: no verdict
# EXECUTION_FAIL is a failure REPORTED BY THE ENGINE in a valid run report.
# The two outcomes below are not engine results: the attempt itself is
# unusable (launcher failure, missing or invalid report, identity mismatch)
# or the normalized result breaks its own contract.
CASE_HARNESS_FAILURE = "HARNESS_FAILURE"
CASE_INVALID_PAYLOAD = "INVALID_PAYLOAD"
CASE_OUTCOMES = (CASE_EXECUTION_FAIL, CASE_CONCORDANT, CASE_CLOSE, CASE_DIVERGENT,
                 CASE_NOT_DETERMINISTIC, CASE_OBSERVED_ONLY,
                 CASE_HARNESS_FAILURE, CASE_INVALID_PAYLOAD)
UNUSABLE_OUTCOMES = (CASE_HARNESS_FAILURE, CASE_INVALID_PAYLOAD)

CAMPAIGN_COMPLETE = "COMPLETE"
CAMPAIGN_UNUSABLE = "UNUSABLE"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def round12(v):
    """Mirror of the normalizer rounding: 12 significant digits, -0 -> 0."""
    if v is None:
        return None
    r = float("%.12g" % v)
    return 0.0 if r == 0 else r


def _reject_constant(token):
    raise ValueError("non-finite number %r is not admitted" % token)


def loads_strict(text):
    """JSON parsing that refuses NaN / Infinity / -Infinity tokens."""
    return json.loads(text, parse_constant=_reject_constant)


def load_manifest():
    return loads_strict(MANIFEST.read_text(encoding="utf-8"))


def is_hex64(value):
    return isinstance(value, str) and len(value) == 64 \
        and all(c in "0123456789abcdef" for c in value)


def payload_problems(payload):
    """Contract of a normalized payload: every plot is a list of points
    {t: integer, v: finite number or null}. A boolean is not a number; NaN
    and infinities are not values. Returns a list of problems."""
    problems = []
    if not isinstance(payload, dict) or not isinstance(payload.get("plots"), dict):
        return ["normalized payload has no 'plots' object"]
    for key, points in sorted(payload["plots"].items()):
        if not isinstance(points, list):
            problems.append("plot %r is not a list" % key)
            continue
        for i, pt in enumerate(points):
            if not isinstance(pt, dict) or set(pt) != {"t", "v"}:
                problems.append("plot %r point %d is not {t, v}" % (key, i))
                break
            t, v = pt["t"], pt["v"]
            if isinstance(t, bool) or not isinstance(t, int):
                problems.append("plot %r point %d: time %r is not an integer"
                                % (key, i, t))
                break
            if v is None:
                continue
            if isinstance(v, bool):
                problems.append("plot %r point %d: boolean %r in place of a "
                                "number" % (key, i, v))
                break
            if not isinstance(v, (int, float)):
                problems.append("plot %r point %d: %s in place of a number"
                                % (key, i, type(v).__name__))
                break
            if v != v or v in (float("inf"), float("-inf")):
                problems.append("plot %r point %d: non-finite value" % (key, i))
                break
    for field in ("alerts", "warnings"):
        if not isinstance(payload.get(field, []), list):
            problems.append("'%s' is not a list" % field)
    return problems


def resolve(rel):
    """Manifest paths are relative to the repository root."""
    return REPO / rel


def series_equal(expected_values, actual_points):
    """Strict comparison of one expected series with one payload series.
    Returns (equal, detail). When the only differences are numeric, detail
    carries the largest relative gap and whether it stays within
    RELATIVE_TOLERANCE — a description of the gap, not a second verdict."""
    if len(expected_values) != len(actual_points):
        return False, {"reason": "length", "expected": len(expected_values),
                       "actual": len(actual_points)}
    diffs, na_mismatch, worst = [], 0, 0.0
    for i, (exp, act) in enumerate(zip(expected_values, actual_points)):
        if exp["t"] != act.get("t"):
            return False, {"reason": "time", "first_index": i,
                           "expected": exp, "actual": act}
        ev, av = exp["v"], act.get("v")
        if ev == av:
            continue
        diffs.append(i)
        if ev is None or av is None or isinstance(av, bool) \
                or not isinstance(av, (int, float)):
            na_mismatch += 1
        else:
            scale = max(abs(ev), abs(av))
            worst = max(worst, abs(ev - av) / scale if scale else 0.0)
    if diffs:
        i = diffs[0]
        return False, {"reason": "values", "differing_points": len(diffs),
                       "na_pattern_mismatches": na_mismatch,
                       "largest_relative_gap": worst,
                       "within_tolerance": na_mismatch == 0
                       and worst <= RELATIVE_TOLERANCE,
                       "first_index": i, "expected": expected_values[i],
                       "actual": actual_points[i]}
    return True, None


def _verdict(variants, actual):
    """(outcome, extra) of one payload series against named candidate value
    lists. Exact equality first; failing that, closeness is reported."""
    exact = [n for n, vals in sorted(variants.items())
             if series_equal(vals, actual)[0]]
    if exact:
        return CONCORDANT, {"equals": exact}
    details = {n: series_equal(vals, actual)[1] for n, vals in sorted(variants.items())}
    close = [n for n, d in details.items() if d.get("within_tolerance")]
    if close:
        return CLOSE, {"close_to": close, "detail": {n: details[n] for n in close}}
    return DIVERGENT, {"detail": details}


def compare_case(expected, payload):
    """Compare the expected document of a case with a normalized payload.

    Returns {"series": {name: {...}}, "unexpected_payload_keys": {...}}.
    An exploration series is only OBSERVED: what the engine returned is
    described against the candidate values, no verdict is given. A payload
    key that no expected series claims is described too."""
    plots = (payload or {}).get("plots") or {}
    out = {}
    claimed = set()
    for name, spec in sorted(expected["series"].items()):
        keys = [k for k in sorted(plots)
                if k == name or k.startswith(name + "#")] \
            if spec.get("match") == "title-and-suffixes" else \
            ([name] if name in plots else [])
        claimed.update(keys)
        variants = spec.get("variants") or {"expected": spec["values"]}
        entry = {"status": spec["status"], "payload_keys": keys}
        if spec["status"] == EXPLORATION:
            entry["outcome"] = OBSERVED
            entry["observed"] = {}
            for k in keys:
                verdict, extra = _verdict(variants, plots[k])
                entry["observed"][k] = dict(extra, compared_to_candidates=verdict,
                                            points=len(plots[k]))
            if not keys:
                entry["observed_absent"] = True
            out[name] = entry
            continue
        if not keys:
            entry["outcome"] = MISSING
            out[name] = entry
            continue
        verdict, extra = _verdict(variants, plots[keys[0]])
        entry["outcome"] = verdict
        entry.update(extra)
        out[name] = entry
    unexpected = {}
    for k in sorted(plots):
        if k in claimed:
            continue
        values = [pt.get("v") for pt in plots[k]]
        unexpected[k] = {"points": len(values),
                         "all_null": all(v is None for v in values),
                         "distinct_values_sample": sorted(
                             {v for v in values if v is not None})[:5]}
    return {"series": out, "unexpected_payload_keys": unexpected}


def case_outcome(comparison):
    """Verdict of a case from its ESTABLISHED series only."""
    verdicts = [s["outcome"] for s in comparison["series"].values()
                if s["status"] == ESTABLISHED]
    if not verdicts:
        return CASE_OBSERVED_ONLY
    if any(v in (DIVERGENT, MISSING) for v in verdicts):
        return CASE_DIVERGENT
    if any(v == CLOSE for v in verdicts):
        return CASE_CLOSE
    return CASE_CONCORDANT
