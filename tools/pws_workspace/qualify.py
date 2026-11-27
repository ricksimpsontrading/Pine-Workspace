# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL qualification of a change between two results ALREADY COMPUTED by the local test
loop (isolated study copy). Reproducible findings only, never a verdict:

- values and signals: the runner's own `compareRuns` (`node runner.mjs compare`, which never loads
  PineTS) on the two run reports — comparable only with the same dataset, configuration, PineTS
  version, executor fingerprint and normalization schema, both PASS; otherwise INCONCLUSIVE with
  its reasons;
- chart: the USEFUL content of the two graphics annexes (declaration, series kinds, options,
  per-point styles and values, drawing objects in their final state), read only after both
  passed the reader contract v1 (`local_test.check`); identity fields (run id, source / dataset /
  payload hashes, engine) are left out, so a recomputation alone never looks like a change;
- source: comment-only or not, keeping strings, `//@` directives and indentation significant;
- capabilities: the state recorded in the report, with effective_gating = GATING AND CURRENT.

A difference is never a confirmed regression, an accepted baseline or a TradingView validation:
EXPECTED / UNEXPECTED / UNRESOLVED is Claude Code's interpretation against the impact inventory
(spec 24.4.9), UNRESOLVED when the evidence does not decide.
"""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import annex_reader, local_test

IDENTITY_KEYS = ("schema", "run_id", "source_sha256", "dataset_sha256", "pinets_version", "executor_fingerprint",
                 "normalization_schema", "normalized_payload_sha256")
SIGNAL_KINDS = ("shape", "char", "arrow")
STYLE_KEY = re.compile(r"(color|colour|style|width|size|font|transp|border|bgcolor|textcolor|text_size|"
                       r"halign|valign|wrap|extend|display|editable|linestyle|shape|char)", re.I)
TEMPORAL_PREFIXES = ("request-", "barstate-", "timeframe-", "session-", "time-", "ticker-")
TEMPORAL_CAPS = ("state-varip",)
AUTHORITY = ("Observation only: a difference is neither a confirmed regression nor an accepted baseline nor a "
             "TradingView validation. EXPECTED / UNEXPECTED / UNRESOLVED is decided by Claude Code against the "
             "impact inventory of the request (spec 24.4.9); UNRESOLVED when the evidence does not decide.")
INCONCLUSIVE_EXPLAINED = {
    "dataset_sha256": "the two runs used different datasets",
    "pinets_version": "the PineTS version differs",
    "executor_fingerprint": "the executor (adapter, Node, platform) differs",
    "normalization_schema": "the normalization schema differs",
    "configuration": "the run configuration differs",
    "execution_status": "one of the runs is not PINETS_EXECUTION_PASS",
    "compare-unavailable": "the runner's comparison of the two reports could not be run",
}
COMPARABILITY_REASONS = ("dataset_sha256", "pinets_version", "executor_fingerprint", "normalization_schema",
                         "configuration", "execution_status")


# ------------------------------------------------------------------------------- source
def _code_part(line):
    """The line without its trailing `//` comment, strings kept verbatim; a `//@` directive line
    (e.g. //@version=6) is kept whole. Leading whitespace (indentation) is kept."""
    if line.lstrip().startswith("//@"):
        return line.rstrip()
    out, q, i = [], None, 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < len(line):
                out.append(line[i + 1]); i += 2; continue
            if c == q:
                q = None
        elif c in ("'", '"'):
            q = c; out.append(c)
        elif c == "/" and line[i + 1:i + 2] == "/":
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def source_change(old_text, new_text):
    """'identical' | 'comment-only' | 'code'. Blank lines are not significant; everything else
    outside comments is (strings, `//@` directives, indentation)."""
    if old_text == new_text:
        return "identical"
    norm = lambda t: [x for x in (_code_part(l) for l in t.splitlines()) if x.strip()]
    return "comment-only" if norm(old_text) == norm(new_text) else "code"


# ------------------------------------------------------------------------------- annex
def _useful(annex):
    return {k: v for k, v in annex.items() if k not in IDENTITY_KEYS}


def _split_style(obj):
    style = {k: v for k, v in obj.items() if STYLE_KEY.search(k)}
    content = {k: v for k, v in obj.items() if not STYLE_KEY.search(k) and k not in ("id", "_id", "channel")}
    return content, style


def annex_diff(a, b):
    """Useful-content differences between two graphics annexes, by facet: values, signals,
    objects, styles. Each entry names where."""
    a, b = _useful(a), _useful(b)
    out = {"values": [], "signals": [], "objects": [], "styles": []}
    da, db = a.get("declaration") or {}, b.get("declaration") or {}
    for k in sorted(set(da) | set(db)):
        if da.get(k) != db.get(k):
            out["styles"].append("declaration.%s" % k)
    sa = {s["key"]: s for s in a.get("series") or []}
    sb = {s["key"]: s for s in b.get("series") or []}
    for k in sorted(set(sa) | set(sb)):
        x, y = sa.get(k), sb.get(k)
        sig = (x or y).get("kind") in SIGNAL_KINDS
        if x is None or y is None:
            out["signals" if sig else "values"].append("series %s %s" % (k, "added" if x is None else "removed"))
            continue
        if x.get("kind") != y.get("kind"):
            out["styles"].append("series %s kind %s -> %s" % (k, x.get("kind"), y.get("kind")))
        if x.get("title") != y.get("title"):
            out["styles"].append("series %s title" % k)
        if x.get("options") != y.get("options"):
            keys = sorted(set(x.get("options") or {}) | set(y.get("options") or {}))
            out["styles"].append("series %s options %s" % (k, ",".join(
                o for o in keys if (x.get("options") or {}).get(o) != (y.get("options") or {}).get(o))))
        px, py = x.get("points") or [], y.get("points") or []
        vdiff = next((i for i in range(max(len(px), len(py)))
                      if (px[i:i + 1] or [{}])[0].get("v") != (py[i:i + 1] or [{}])[0].get("v")
                      or (px[i:i + 1] or [{}])[0].get("ohlc") != (py[i:i + 1] or [{}])[0].get("ohlc")), None)
        if vdiff is not None:
            out["signals" if sig else "values"].append("series %s first index %d" % (k, vdiff))
        # per-point style attributes are compared only where the value itself is equal: a signal shown on
        # one side and absent on the other carries its shape attributes with it (a signal change, not a style)
        sdiff = next((i for i in range(min(len(px), len(py)))
                      if px[i].get("v") == py[i].get("v") and px[i].get("ohlc") == py[i].get("ohlc")
                      and (px[i].get("color") != py[i].get("color") or px[i].get("o") != py[i].get("o"))), None)
        if sdiff is not None:
            out["styles"].append("series %s per-point style first index %d" % (k, sdiff))
    ga, gb = a.get("drawings") or {}, b.get("drawings") or {}
    for fam in sorted(set(ga) | set(gb)):
        la, lb = ga.get(fam) or [], gb.get(fam) or []
        if len(la) != len(lb):
            out["objects"].append("%s count %d -> %d" % (fam, len(la), len(lb)))
            continue
        content_changed = style_changed = 0
        for x, y in zip(la, lb):
            cx, stx = _split_style(x); cy, sty = _split_style(y)
            content_changed += cx != cy; style_changed += stx != sty
        if content_changed:
            out["objects"].append("%s content of %d object(s)" % (fam, content_changed))
        if style_changed:
            out["styles"].append("%s style of %d object(s)" % (fam, style_changed))
    return out


def _explain(reason):
    if reason.startswith("malformed_report_"):
        side, _, field = reason[len("malformed_report_"):].partition(":")
        return "report %s is not usable for a comparison (%s)" % ("of the comparison run" if side == "a" else "of the result", field)
    return INCONCLUSIVE_EXPLAINED.get(reason, reason)


def series_divergences(a, b):
    """Per series whose values differ between two annexes (useful content, after the reader
    contract): key, kind, facet (signals for shape / char / arrow, else values), the first index
    where the values differ, and the time of that point on each side. The normalized payload drops
    the booleans of signal plots (`normalize.mjs`); the annex keeps them, so a signal change is
    established here, not by compareRuns."""
    sa = {s["key"]: s for s in (a or {}).get("series") or []}
    sb = {s["key"]: s for s in (b or {}).get("series") or []}
    out = []
    for k in sorted(set(sa) & set(sb)):
        px, py = sa[k].get("points") or [], sb[k].get("points") or []
        idx = next((i for i in range(max(len(px), len(py)))
                    if (px[i:i + 1] or [{}])[0].get("v") != (py[i:i + 1] or [{}])[0].get("v")
                    or (px[i:i + 1] or [{}])[0].get("ohlc") != (py[i:i + 1] or [{}])[0].get("ohlc")), None)
        if idx is None:
            continue
        ta = (px[idx:idx + 1] or [{}])[0].get("t"); tb = (py[idx:idx + 1] or [{}])[0].get("t")
        out.append({"series": k, "kind": sb[k].get("kind"), "facet": "signals" if sb[k].get("kind") in SIGNAL_KINDS else "values",
                    "first_index": idx, "time_reference": ta, "time_result": tb,
                    "reference_value": (px[idx:idx + 1] or [{}])[0].get("v"), "result_value": (py[idx:idx + 1] or [{}])[0].get("v"),
                    "differing_points": sum(1 for i in range(min(len(px), len(py))) if px[i].get("v") != py[i].get("v"))
                                        + abs(len(px) - len(py))})
    return out


# ------------------------------------------------------------------------------- comparability
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TS = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")


def report_reasons(ra, rb):
    """Python mirror of the runner's compareRuns checks (runner.mjs, compareRuns): the well-formedness
    of both reports first (malformed_report_<a|b>:<field>), then the comparability identity (same
    dataset, PineTS version, executor fingerprint, normalization schema, configuration, both PASS).
    No program is started. Returns the list of reasons; empty = comparable."""
    reasons = []
    for tag, r in (("a", ra), ("b", rb)):
        if not isinstance(r, dict) or r.get("schema") != "pws-pinets-run-v1":
            reasons.append("malformed_report_%s:schema" % tag); continue
        hexok = lambda v: isinstance(v, str) and _HEX64.fullmatch(v) is not None
        if not isinstance(r.get("run_id"), str) or not r.get("run_id"):
            reasons.append("malformed_report_%s:run_id" % tag)
        if not isinstance(r.get("timestamp"), str) or _TS.fullmatch(r.get("timestamp")) is None:
            reasons.append("malformed_report_%s:timestamp" % tag)
        for k in ("source_sha256", "dataset_sha256"):
            if not hexok(r.get(k)):
                reasons.append("malformed_report_%s:%s" % (tag, k))
        for k in ("dataset_descriptor", "configuration", "capabilities_used"):
            if not isinstance(r.get(k), dict):
                reasons.append("malformed_report_%s:%s" % (tag, k))
        if not isinstance(r.get("pinets_version"), str) or not r.get("pinets_version"):
            reasons.append("malformed_report_%s:pinets_version" % tag)
        if not hexok(r.get("executor_fingerprint")):
            reasons.append("malformed_report_%s:executor_fingerprint" % tag)
        if not isinstance(r.get("normalization_schema"), str) or not r.get("normalization_schema"):
            reasons.append("malformed_report_%s:normalization_schema" % tag)
        if not isinstance(r.get("normalized"), dict):
            reasons.append("malformed_report_%s:normalized" % tag); continue
        if not hexok(r.get("normalized_payload_sha256")):
            reasons.append("malformed_report_%s:normalized_payload_sha256" % tag)
        else:
            try:
                same = annex_reader.payload_sha256(r["normalized"]) == r["normalized_payload_sha256"]
            except Exception:  # noqa: BLE001 — an unhashable payload is a malformed one
                same = False
            if not same:
                reasons.append("malformed_report_%s:payload_sha_mismatch" % tag)
    if reasons:
        return reasons
    for k in ("dataset_sha256", "pinets_version", "executor_fingerprint", "normalization_schema"):
        if ra.get(k) != rb.get(k):
            reasons.append(k)
    try:
        differs = annex_reader.canonical_payload_text(ra["configuration"]) != annex_reader.canonical_payload_text(rb["configuration"])
    except Exception:  # noqa: BLE001 — a key or value the port cannot write: structural equality, never a false refusal
        differs = ra["configuration"] != rb["configuration"]
    if differs:
        reasons.append("configuration")
    if ra.get("execution_status") != "PINETS_EXECUTION_PASS" or rb.get("execution_status") != "PINETS_EXECUTION_PASS":
        reasons.append("execution_status")
    return reasons


def _span(ms):
    sign = "+" if ms >= 0 else "-"; ms = abs(ms)
    for unit, n in (("day", 86400000), ("hour", 3600000), ("minute", 60000), ("second", 1000)):
        if ms % n == 0:
            k = ms // n
            return "%s%d %s%s" % (sign, k, unit, "" if k == 1 else "s")
    return "%s%d ms" % (sign, ms)


def dataset_relation(ref_dir, cur_dir, ra, rb):
    """How the two datasets differ, read from each run's own dataset snapshot (each checked against
    the dataset SHA-256 its report records). Describes; never compares outputs."""
    def load(d, r):
        f = Path(d or "") / "dataset.json"
        try:
            raw = f.read_bytes()
        except OSError:
            return None, "missing"
        if hashlib.sha256(raw).hexdigest() != (r or {}).get("dataset_sha256"):
            return None, "not the dataset its report records"
        try:
            return json.loads(raw), "ok"
        except ValueError:
            return None, "unreadable"
    (da, sa), (db, sb) = load(ref_dir, ra), load(cur_dir, rb)
    if sa != "ok" or sb != "ok":
        return "dataset snapshot of the %s" % " and of the ".join(
            "%s: %s" % (role, st) for role, st in (("reference", sa), ("result", sb)) if st != "ok")
    ba, bb = da.get("bars") or [], db.get("bars") or []
    if len(ba) != len(bb):
        return "%d bars in the reference, %d in the result" % (len(ba), len(bb))
    if not ba:
        return "no bars"
    strip = lambda b: {k: v for k, v in b.items() if k != "t"}
    same_prices = all(strip(x) == strip(y) for x, y in zip(ba, bb))
    offsets = {y.get("t", 0) - x.get("t", 0) for x, y in zip(ba, bb)}
    if len(offsets) == 1 and offsets != {0}:
        return "same %d bars%s, every timestamp shifted by %s" % (
            len(ba), " and prices" if same_prices else " count, prices differ", _span(offsets.pop()))
    if offsets == {0}:
        first = next((i for i, (x, y) in enumerate(zip(ba, bb)) if strip(x) != strip(y)), None)
        if first is not None:
            return "same timestamps, prices differ from bar %d" % first
        dd = sorted(k for k in set(da.get("descriptor") or {}) | set(db.get("descriptor") or {})
                    if (da.get("descriptor") or {}).get(k) != (db.get("descriptor") or {}).get(k))
        return ("same bars, other descriptor (%s)" % ", ".join(dd)) if dd else "same bars and descriptor, other file bytes"
    first = next(i for i, (x, y) in enumerate(zip(ba, bb)) if x.get("t") != y.get("t"))
    return "same bar count, timestamps differ from bar %d" % first


def _short(v):
    return v[:12] if isinstance(v, str) and len(v) == 64 else v


def explain_reason(code, ra, rb, ref_dir=None, cur_dir=None, ids=None):
    missing = {"a": not isinstance(ra, dict), "b": not isinstance(rb, dict)}
    ra, rb = ra if isinstance(ra, dict) else {}, rb if isinstance(rb, dict) else {}
    ids = ids or {}
    if code.startswith("malformed_report_"):
        side, _, field = code[len("malformed_report_"):].partition(":")
        r = ra if side == "a" else rb
        rid = (r.get("run_id") if isinstance(r.get("run_id"), str) else None) or ids.get(side) or "?"
        role = "reference" if side == "a" else "result"
        if missing.get(side):
            return "the report of the %s %s is missing or unreadable (run.json)" % (role, rid)
        return "the report of the %s %s is not usable for a comparison (%s)" % (role, rid, field)
    if code == "recorded-refusal":
        return "a refusal recorded earlier for these runs"
    base = INCONCLUSIVE_EXPLAINED.get(code, code)
    if code == "dataset_sha256":
        try:
            rel = dataset_relation(ref_dir, cur_dir, ra, rb)
        except Exception:  # noqa: BLE001 — a description, never a reason to fail
            rel = "the dataset snapshots could not be described"
        return "%s (%s)" % (base, rel)
    if code in ("pinets_version", "executor_fingerprint", "normalization_schema", "execution_status"):
        return "%s (reference %s, result %s)" % (base, _short(ra.get(code)), _short(rb.get(code)))
    if code == "configuration":
        ca, cb = ra.get("configuration") or {}, rb.get("configuration") or {}
        keys = sorted(k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k)) if isinstance(ca, dict) and isinstance(cb, dict) else []
        return "%s (%s)" % (base, ", ".join(keys) or "values")
    return base


def _read_report(path):
    """A run report read as strictly as the runner's JSON.parse (NaN / Infinity refused); None if
    missing, unreadable or malformed."""
    def refuse(c):
        raise ValueError("non-standard JSON constant %s" % c)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=refuse)
    except (OSError, ValueError, RecursionError, UnicodeDecodeError):
        return None


def comparability(ref_dir, cur_dir, compare=None, recorded=None, run_ids=None):
    """May the comparison run (ref_dir) and the result (cur_dir) be compared output by output?
    Recomputed from the two run reports now (report_reasons: no program started), united with any
    refusal already recorded (the runner's compareRuns verdict `compare`, an earlier `recorded`
    comparability): fail-closed. A runner that could not run ("compare-unavailable") is not a refusal.
    Returns {comparable, reasons, explanation, runs}; the explanation names both runs and the reason."""
    ra, rb = _read_report(Path(ref_dir or "") / "run.json"), _read_report(Path(cur_dir or "") / "run.json")
    try:
        reasons = report_reasons(ra, rb)
    except RecursionError:
        reasons = ["malformed_report_a:schema" if not isinstance(ra, dict) else "malformed_report_b:schema"]
    recorded_refusal = (((compare or {}).get("reasons") or ["recorded-refusal"]) if (compare or {}).get("status") == "PINETS_INCONCLUSIVE" else []) + \
                       ((((recorded or {}).get("reasons") or ["recorded-refusal"])) if (recorded or {}).get("comparable") is False else [])
    for extra in recorded_refusal:
        if extra != "compare-unavailable" and extra not in reasons:
            reasons.append(extra)
    known = run_ids or {}
    ida = (ra.get("run_id") if isinstance(ra, dict) and isinstance(ra.get("run_id"), str) else None) or known.get("reference")
    idb = (rb.get("run_id") if isinstance(rb, dict) and isinstance(rb.get("run_id"), str) else None) or known.get("result")
    out = {"comparable": not reasons, "reasons": reasons, "runs": {"reference": ida, "result": idb}, "explanation": None,
           "established_by": "PWS checks of the two run reports (mirror of the runner's compareRuns), now"}
    if reasons:
        ids = {"a": ida, "b": idb}
        out["explanation"] = ("the reference %s and the result %s are not comparable: %s; no equality, difference or "
                              "first divergence between them can be established, for any output"
                              % (ida or "?", idb or "?", "; ".join(explain_reason(c, ra, rb, ref_dir, cur_dir, ids) for c in reasons)))
    return out


def withheld(q, comp):
    """The part of a stored qualification that may still be shown when the runs are not comparable:
    nothing compared between them (change, facets, divergences withheld)."""
    return {"change": "not-comparable", "comparability": comp, "source": (q or {}).get("source"),
            "withheld": "change, facets and divergences are not stated between runs that are not comparable",
            "gating_note": "the runs are not comparable: no conclusion between them, blocking or not",
            "authority": AUTHORITY}


# ------------------------------------------------------------------------------- compareRuns
def compare_runs(root, run_a, run_b, runner=None):
    """The runner's compareRuns on two reports (`node runner.mjs compare`: no engine import)."""
    pe = Path(root) / "tools" / "pine_exec"
    cmd = [shutil.which("node") or "node", str(pe / "runner.mjs"), "compare",
           "--a", str(Path(run_a) / "run.json"), "--b", str(Path(run_b) / "run.json")]
    if runner:
        return runner(cmd)
    p = subprocess.run(cmd, cwd=str(pe), capture_output=True, text=True, timeout=60)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"comparable": False, "status": "PINETS_INCONCLUSIVE", "reasons": ["compare-unavailable"],
                "note": (p.stderr or p.stdout).strip()[:300]}


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _snapshot_text(run_dir):
    lt = _read(Path(run_dir) / "local-test.json") or {}
    f = Path(run_dir) / (lt.get("source_snapshot") or "")
    return f.read_text(encoding="utf-8") if lt.get("source_snapshot") and f.is_file() else None


def capabilities(rep):
    caps = (rep or {}).get("capabilities_used") if isinstance(rep, dict) else None
    caps = caps if isinstance(caps, dict) else {}
    out = {k: dict(v, effective_gating=v.get("capability_status") == "GATING" and v.get("calibration_status") == "CURRENT")
           for k, v in caps.items() if isinstance(v, dict)}
    return out


def accepted_baselines(root, slug):
    d = Path(root) / "scripts" / slug / "tests" / "behavioral"
    return sorted(str(p.relative_to(root)) for p in d.glob("**/*.json")) if d.is_dir() else []


def qualify(root, cur_dir, ref_dir, slug=None, runner=None):
    """Findings between the result `cur_dir` and the comparison run `ref_dir` (both already
    computed). Never computes; never decides EXPECTED / UNEXPECTED."""
    root = Path(root)
    ra, rb = _read(Path(ref_dir) / "run.json") or {}, _read(Path(cur_dir) / "run.json") or {}
    out = {"compared_with": {"run_id": ra.get("run_id"), "revision_sha256": ra.get("source_sha256"),
                             "timestamp": ra.get("timestamp"), "run_dir": str(ref_dir)},
           "result": {"run_id": rb.get("run_id"), "revision_sha256": rb.get("source_sha256"), "timestamp": rb.get("timestamp")},
           "authority": AUTHORITY}
    # source
    ta, tb = _snapshot_text(ref_dir), _snapshot_text(cur_dir)
    out["source"] = source_change(ta, tb) if ta is not None and tb is not None else "unknown"
    out["divergences"] = []
    # values / signals: compareRuns
    cmp_ = compare_runs(root, ref_dir, cur_dir, runner=runner)
    out["compare_runs"] = cmp_
    comp = comparability(ref_dir, cur_dir, compare=cmp_)
    out["comparability"] = comp
    facets = {"values": [], "signals": [], "objects": [], "styles": []}
    uncertain = []
    if not comp["comparable"]:
        uncertain.append(comp["explanation"])
    elif cmp_.get("status") == "PINETS_INCONCLUSIVE":
        uncertain.append("values not comparable: " + "; ".join(_explain(r) for r in cmp_.get("reasons") or ["unknown reason"]))
    # chart: useful annex content, after the reader contract v1 on both sides — only between comparable runs
    ca = local_test.check(root, ref_dir) if (Path(ref_dir) / "graphics.json").exists() else None
    cb = local_test.check(root, cur_dir) if (Path(cur_dir) / "graphics.json").exists() else None
    if not comp["comparable"]:
        out["annex"] = "not compared: the runs are not comparable"
    elif ca and cb and ca["ok"] and cb["ok"]:
        ga_, gb_ = _read(Path(ref_dir) / "graphics.json"), _read(Path(cur_dir) / "graphics.json")
        d = annex_diff(ga_, gb_)
        for k in facets:
            facets[k] += d[k]
        out["divergences"] = series_divergences(ga_, gb_)
        out["annex"] = "compared (reader contract v1 passed on both)"
    else:
        out["annex"] = "not compared: " + ("no annex" if not (ca and cb) else "refused [%s/%s]" % (
            (ca or {}).get("code"), (cb or {}).get("code")))
        uncertain.append("chart content not compared (%s)" % out["annex"][len("not compared: "):])
    kind = {}
    for s in (_read(Path(cur_dir) / "graphics.json") or {}).get("series") or []:
        kind[s["key"]] = s.get("kind")
    for c in (cmp_.get("changed") or []) if comp["comparable"] else []:
        if "plot" in c:
            f = "signals" if kind.get(c["plot"]) in SIGNAL_KINDS else "values"
            entry = "plot %s first index %s" % (c["plot"], c.get("first_divergence_index"))
            if not any(e.startswith("series %s " % c["plot"]) for e in facets[f]):
                facets[f].append(entry)
        elif c.get("section") == "alerts":
            facets["signals"].append("alerts")
        elif c.get("section"):
            uncertain.append("payload section %s changed" % c["section"])
    out["facets"] = facets
    changed = [k for k in ("values", "signals", "objects", "styles") if facets[k]]
    out["changed_facets"] = changed
    if not comp["comparable"]:
        out["change"] = "not-comparable"
    elif not changed and not uncertain:
        out["change"] = "comment-only" if out["source"] == "comment-only" else "unchanged"
    elif changed == ["styles"] and not uncertain:
        out["change"] = "presentation-only"
    elif changed:
        out["change"] = "+".join(changed)
    else:
        out["change"] = "uncertain"
    # capabilities and authority boundaries
    caps = capabilities(rb)
    out["capabilities_used"] = caps
    out["all_effectively_gating"] = bool(caps) and all(v["effective_gating"] for v in caps.values())
    ref_caps = capabilities(ra)
    added = sorted(set(caps) - set(ref_caps))
    removed = sorted(set(ref_caps) - set(caps))
    out["capabilities_delta"] = {"added": added, "removed": removed}
    if rb.get("unclassified_tokens"):
        uncertain.append("unclassified tokens: %s" % ", ".join(rb["unclassified_tokens"][:8]))
    temporal = sorted(k for k in caps if k.startswith(TEMPORAL_PREFIXES) or k in TEMPORAL_CAPS)
    if temporal:
        uncertain.append("time / MTF / realtime capabilities (%s): the local dataset is historical only" % ", ".join(temporal))
    out["uncertain"] = uncertain
    out["gating_note"] = ("every capability used is GATING and CURRENT: a bounded local conclusion is possible"
                          if out["all_effectively_gating"] else
                          "at least one capability used is not GATING+CURRENT: no blocking conclusion")
    out["accepted_baselines"] = accepted_baselines(root, slug) if slug else []
    return out


def expectation_facts(expectation, qualification):
    """Facts comparing what pine-develop declared for this revision with what was observed. The
    interpretation (EXPECTED / UNEXPECTED / UNRESOLVED) stays with Claude Code."""
    if not expectation or not qualification:
        return None
    if qualification.get("change") == "not-comparable" or (qualification.get("comparability") or {}).get("comparable") is False:
        return None                                   # nothing was compared between the two runs
    obs = set(qualification.get("changed_facets") or [])
    want = set(expectation.get("change") or []); keep = set(expectation.get("unchanged") or [])
    return {"declared_change_observed": sorted(want & obs), "declared_change_not_observed": sorted(want - obs),
            "declared_unchanged_but_changed": sorted(keep & obs),
            "observed_not_declared": sorted(obs - want - keep),
            "uncertain": qualification.get("uncertain") or []}
