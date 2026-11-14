"""Compare two recorded campaigns, case by case.

Used to confront a re-run with an earlier record of the SAME engine, or to
describe a migration between two engines. It reads durable records only; it
runs nothing. It never uses the canonical comparator of the thin adapter.

A case is comparable only when both records observed the same fixture
(identical source, dataset, expected and configuration fingerprints).

Classification of a comparable case:
  UNCHANGED   same outcome, same error, same result fingerprint, same
              series outcomes
  PROGRESS    the verdict on established expectations is better in B
  REGRESSION  the verdict on established expectations is worse in B
  CHANGED     something differs without a better or worse verdict
              (exploration series, payload fingerprint, error text):
              unresolved, to be examined

Usage (from the repository root):
    python3 -m tools.tests.pinets_cases.compare_campaigns A.json B.json
"""
import json
import sys
from pathlib import Path

from tools.tests.pinets_cases import cases_lib as lib

UNCHANGED, PROGRESS, REGRESSION, CHANGED = "UNCHANGED", "PROGRESS", "REGRESSION", "CHANGED"
NOT_COMPARABLE = "NOT_COMPARABLE"
ONLY_IN_A, ONLY_IN_B = "ONLY_IN_A", "ONLY_IN_B"

# verdict order on ESTABLISHED expectations only; outcomes absent from this
# table carry no verdict (exploration only, or unusable attempt)
RANK = {lib.CASE_EXECUTION_FAIL: 0, lib.CASE_NOT_DETERMINISTIC: 0,
        lib.CASE_DIVERGENT: 1, lib.CASE_CLOSE: 2, lib.CASE_CONCORDANT: 3}
FIXTURE_KEYS = ("source_sha256", "dataset_sha256", "expected_sha256", "config_sha256")


def load_record(path):
    doc = lib.loads_strict(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") not in lib.OBSERVATION_SCHEMAS:
        raise ValueError("%s: not a campaign record" % path)
    return doc


def _series_view(obs):
    view = {}
    for name, s in sorted((obs.get("series") or {}).items()):
        entry = {"status": s["status"], "outcome": s["outcome"]}
        for key in ("equals", "close_to", "variant"):
            if s.get(key):
                entry["matches"] = s[key]
        if s.get("observed") is not None:
            entry["observed"] = {
                k: (v.get("equals") or v.get("equals_variant") or
                    v.get("close_to") or [])
                for k, v in sorted(s["observed"].items())}
        if s.get("observed_absent"):
            entry["observed_absent"] = True
        view[name] = entry
    return view


def _statuses(obs):
    status = obs.get("execution_status")
    return status if isinstance(status, list) else [status]


def compare_case(a, b):
    if any(a.get(k) != b.get(k) for k in FIXTURE_KEYS):
        return {"classification": NOT_COMPARABLE,
                "reason": "the fixture differs between the two records"}
    differences = {}
    for key in ("outcome", "error", "normalized_payload_sha256", "deterministic",
                "alerts_recorded", "warnings_recorded", "internal_keys_present"):
        if a.get(key) != b.get(key):
            differences[key] = {"a": a.get(key), "b": b.get(key)}
    if sorted(set(_statuses(a))) != sorted(set(_statuses(b))):
        differences["execution_status"] = {"a": _statuses(a), "b": _statuses(b)}
    sa, sb = _series_view(a), _series_view(b)
    series = {n: {"a": sa.get(n), "b": sb.get(n)}
              for n in sorted(set(sa) | set(sb)) if sa.get(n) != sb.get(n)}
    if series:
        differences["series"] = series
    ka = sorted(a.get("unexpected_payload_keys") or [])
    kb = sorted(b.get("unexpected_payload_keys") or [])
    if ka != kb:
        differences["unexpected_payload_keys"] = {"a": ka, "b": kb}
    if not differences:
        return {"classification": UNCHANGED}
    ra, rb = RANK.get(a["outcome"]), RANK.get(b["outcome"])
    if ra is not None and rb is not None and ra != rb:
        classification = PROGRESS if rb > ra else REGRESSION
    else:
        classification = CHANGED
    return {"classification": classification, "differences": differences}


def compare_records(a, b):
    ca = {o["case"]: o for o in a["observations"]}
    cb = {o["case"]: o for o in b["observations"]}
    cases = {}
    for case in sorted(set(ca) | set(cb)):
        if case not in cb:
            cases[case] = {"classification": ONLY_IN_A}
        elif case not in ca:
            cases[case] = {"classification": ONLY_IN_B}
        else:
            cases[case] = compare_case(ca[case], cb[case])
    counts = {}
    for entry in cases.values():
        counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
    return {"engine_a": a.get("engine_identities"),
            "engine_b": b.get("engine_identities"),
            "same_engine": a.get("engine_identities") == b.get("engine_identities"),
            "counts": counts, "cases": cases}


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    result = compare_records(load_record(argv[0]), load_record(argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
