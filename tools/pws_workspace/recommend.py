# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL next useful check of a local test session (isolated study copy) — ADVISORY.

From what PWS already holds for the session (status: requested revision, last finished result,
its qualification against the comparable reference, the expectation pine-develop declared for
that revision), say which check Claude Code should make next and why, with the command that makes
it. Reads files only: never computes, never compares again (zero PineTS call).

The recommendation is bound to the revision of the result it is about; when that result is not
the requested revision it says so and stays attached to its own revision. What is missing to
recommend (stale result, no comparable reference, no expectation, undeterminable bar) is named
precisely. EXPECTED / UNEXPECTED / UNRESOLVED remains Claude Code's judgement; nothing here is a
regression verdict, an accepted baseline, a TradingView validation or a calibration decision.
"""
import hashlib
import json
from pathlib import Path

from . import live, qualify

CMD = "python3 -m tools.pws_workspace local-test "
NOT_COVERED = ["TradingView rendering and TradingView validation (tv-validate keeps its authority)",
               "the drawn pixels (the comparison reads values, styles and objects, not the image)",
               "other datasets, symbols or timeframes than this session's dataset",
               "realtime, intrabar and multi-timeframe behaviour (the local dataset is historical)",
               "drawing objects other than in their final state"]


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _bar_facts(ref_dir, cur_dir, d):
    """What each run reports at the first divergence bar of series divergence `d`."""
    i = d["first_index"]
    ds = _read(Path(cur_dir) / "dataset.json") or {}
    bars = ds.get("bars") or []
    sc = (ds.get("descriptor") or {}).get("price_scale") or 1
    if not (0 <= i < len(bars)) or bars[i].get("t") != d["time_result"] or d["time_reference"] != d["time_result"]:
        return None, "bar impossible to determine: index %s does not match one dataset bar on both runs" % i
    def report_v(run_dir):
        p = (((_read(Path(run_dir) / "run.json") or {}).get("normalized") or {}).get("plots") or {}).get(d["series"]) or []
        return p[i].get("v") if i < len(p) else None
    b = bars[i]
    return {"bar": i, "time": b["t"], "ohlc": {"open": b["o"] / sc, "high": b["h"] / sc, "low": b["l"] / sc, "close": b["c"] / sc},
            "series": d["series"], "kind": d["kind"],
            "reference": {"chart_value": d["reference_value"], "report_value": report_v(ref_dir)},
            "result": {"chart_value": d["result_value"], "report_value": report_v(cur_dir)},
            "differing_points": d["differing_points"],
            "note": ("signal plots: the report (normalized payload) keeps numbers only, the chart value is the "
                     "annex value checked by the reader contract" if d["facet"] == "signals" else None)}, None


def _annex_state(root, run_dir, run_id, role):
    """The graphics annex of one run, checked NOW by the reader contract v1 (never from an earlier
    qualification): ok, or the exact reason it cannot be used."""
    from . import local_test
    if not run_dir or not (Path(run_dir) / "graphics.json").exists():
        return {"role": role, "run_id": run_id, "ok": False, "code": "MISSING",
                "reason": "graphics annex missing (graphics.json)"}
    c = local_test.check(root, run_dir)
    return {"role": role, "run_id": run_id, "ok": c["ok"], "code": c["code"], "reason": c["detail"]}


def _numeric_facts(q):
    """What the two reports establish (compareRuns on run.json; independent of the annexes)."""
    cr = q.get("compare_runs") or {}
    if cr.get("status") == "PINETS_REGRESSION_UNCHANGED":
        return {"status": cr["status"], "statement": "the numeric comparison of the two reports shows identical values",
                "scope": "numeric plots of the reports; the booleans of signal plots are not in the reports"}
    if cr.get("status") == "PINETS_REGRESSION_CHANGED":
        return {"status": cr["status"], "statement": "the numeric comparison of the two reports shows differences: %s"
                % ", ".join(c.get("plot") or c.get("section") for c in cr.get("changed") or []),
                "changed": cr.get("changed")}
    return {"status": cr.get("status"), "statement": "the numeric comparison is not established: %s"
            % "; ".join(cr.get("reasons") or ["unknown reason"])}


def _unverifiable(states, exp, q, cw, res):
    """Signals, styles and objects cannot be compared: say which run lacks a usable annex, its role
    and the exact reason; name signals and objects ONLY from an annex that passes the reader contract
    now; never designate a bar; keep the numeric facts of the reports apart."""
    bad = [s for s in states if not s["ok"]]
    good = [s for s in states if s["ok"]]
    signals, objects = [], []
    for s in good:
        g = _read(Path(s["run_dir"]) / "graphics.json") or {}
        signals = sorted({x["key"] for x in g.get("series") or [] if x.get("kind") in qualify.SIGNAL_KINDS} | set(signals))
        objects = sorted({k for k, v in (g.get("drawings") or {}).items() if v} | set(objects))
    expected_styles = "styles" in ((exp or {}).get("change") or [])
    parts = []
    if signals:
        parts.append("the signal%s %s" % ("s" if len(signals) > 1 else "", ", ".join(signals)))
    elif not good:
        parts.append("the signals (no usable annex to name them)")
    parts.append("the expected style change" if expected_styles else "the styles")
    if objects:
        parts.append("the drawing objects (%s)" % ", ".join(objects))
    lack = "; ".join("the annex of the %s %s is %s [%s: %s]" % (s["role"], s["run_id"],
                     "missing" if s["code"] == "MISSING" else "refused", s["code"], s["reason"]) for s in bad)
    num = _numeric_facts(q)
    for s in states:
        s.pop("run_dir", None)
    return {"kind": "unverifiable",
            "summary": "Cannot compare %s. %s. %s." % (" and ".join(parts) if len(parts) < 3 else ", ".join(parts[:-1]) + " and " + parts[-1],
                                                     lack[0].upper() + lack[1:], num["statement"][0].upper() + num["statement"][1:]),
            "unavailable_annexes": [{k: s[k] for k in ("role", "run_id", "code", "reason")} for s in bad],
            "not_comparable": {"signals": signals if good else "unknown (no usable annex)", "styles": True,
                               "objects": objects if good else "unknown (no usable annex)"},
            "names_from": [s["run_id"] for s in good],
            "numeric_facts": num,
            "runs": {"reference": cw.get("run_id"), "result": res.get("run_id")},
            "note": "no bar is designated and no earlier chart observation is reused: the annexes are checked at each call"}


def _series_inventory(run_dir):
    """Where each output of ONE run can be identified, and on how many bars: report (numeric plots)
    and graphics annex (all series, signal booleans included; read only when present — its validity
    is checked by the caller before any per-output conclusion)."""
    d = lambda x: x if isinstance(x, dict) else {}
    rep = d(_read(Path(run_dir or "") / "run.json"))
    plots = d(d(rep.get("normalized")).get("plots"))
    ann = d(_read(Path(run_dir or "") / "graphics.json"))
    bars = d(_read(Path(run_dir or "") / "dataset.json")).get("bars")
    inv = {"bars": len(bars) if isinstance(bars, list) else 0,
           "report": {k: (len(v) if isinstance(v, list) else 0) for k, v in plots.items()}, "annex": {}}
    series = ann.get("series") if isinstance(ann.get("series"), list) else []
    for s_ in series:
        if isinstance(s_, dict) and isinstance(s_.get("key"), str):
            pts = s_.get("points")
            inv["annex"].setdefault(s_["key"], []).append(len(pts) if isinstance(pts, list) else 0)
    return inv


def _proof(key, facet, ref_inv, cur_inv, ref_id, cur_id):
    """None when the output is identifiable once in both results and covered on every bar announced
    by both datasets; otherwise the exact limit, naming the runs concerned."""
    sides = (("reference", ref_id, ref_inv), ("result", cur_id, cur_inv))
    absent, ambiguous, partial = [], [], []
    for role, rid, inv in sides:
        a = inv["annex"].get(key) or []
        if len(a) > 1:
            ambiguous.append("%s %s has %d series named %r in its annex" % (role, rid, len(a), key)); continue
        if facet == "signals":
            n = a[0] if a else None                                   # signal booleans live in the annex only
            where = "annex"
        else:
            n = inv["report"].get(key, a[0] if a else None)
            where = "report" if key in inv["report"] else "annex"
        if n is None:
            absent.append((role, rid)); continue
        if n < inv["bars"]:
            partial.append("%s %s covers %d of its %d bars (%s)" % (role, rid, n, inv["bars"], where))
    if ref_inv["bars"] != cur_inv["bars"]:
        partial.append("the two datasets announce %d and %d bars" % (ref_inv["bars"], cur_inv["bars"]))
    if absent:
        if len(absent) == 2:
            lim = "absent from both results: the reference %s and the result %s have no series %r (report and annex)" % (
                ref_id, cur_id, key)
        else:
            lim = "absent from the %s %s (no series %r in its report or annex), present in the other run" % (
                absent[0][0], absent[0][1], key)
        return {"output": key, "limit": lim, "kind": "absent", "runs": [r for _, r in absent]}
    if ambiguous:
        return {"output": key, "limit": "ambiguous: " + "; ".join(ambiguous), "kind": "ambiguous"}
    if partial:
        return {"output": key, "limit": "partially covered: " + "; ".join(partial), "kind": "partial"}
    return None


def _per_output(out, exp, q, cw, res, facts):
    """D2: what each output did against what the static impact predicted for this revision
    (`expect --from-impact`). An equality is stated only when the output is identifiable once in both
    results and comparable on every bar announced; otherwise the output, the runs and the exact limit
    are named and no further check is called unnecessary. An output predicted to stay identical that
    differs is read at its first established divergence bar (D1); a 'may-change' output that stays
    identical on the tested bars is reported as such, never as an anomaly."""
    divs = {d["series"]: d for d in q.get("divergences") or []}
    changed = dict(divs)
    for c in (q.get("compare_runs") or {}).get("changed") or []:
        if c.get("plot") and c["plot"] not in changed:
            changed[c["plot"]] = {"series": c["plot"], "first_index": c.get("first_divergence_index"), "from": "reports"}
    ref_id, cur_id = cw.get("run_id"), res.get("run_id")
    ref_inv, cur_inv = _series_inventory(cw.get("run_dir")), _series_inventory(res.get("run_dir"))
    n_bars = cur_inv["bars"]
    observed, violations, uncertain_changed, unproven = [], [], [], []
    for key, pred in sorted(exp["outputs"].items()):
        because = next((x.get("because") for x in exp.get("impact") or [] if x.get("output") == key), None)
        row = {"output": key, "predicted": pred["status"], "because": because, "facet": pred["facet"]}
        limit = _proof(key, pred["facet"], ref_inv, cur_inv, ref_id, cur_id)
        if limit:
            row["observed"] = "not comparable: " + limit["limit"]
            unproven.append(limit); observed.append(row); continue
        d = changed.get(key)
        row["observed"] = ("changed, first divergence at bar %s" % d.get("first_index")) if d else \
                          "identical on the %d tested bars (measured in both results)" % n_bars
        if pred["status"] == "may-change" and not d:
            row["note"] = "depends on the change but stays identical on these bars (not an anomaly)"
        if pred["status"] == "stays-identical" and d:
            violations.append(key); row["note"] = "predicted to stay identical"
        if pred["status"] == "uncertain" and d:
            uncertain_changed.append(key); row["note"] = "relation uncertain: interpret before concluding"
        observed.append(row)
    unpredicted = sorted(k for k in changed if k not in exp["outputs"])
    out["outputs_observed"] = observed
    out["outputs_not_comparable"] = unproven
    out["impact_reference"] = exp.get("impact_reference")
    if (exp.get("impact_reference") or {}).get("run_id") not in (None, ref_id):
        out["missing"].append("the impact was analysed against run %s but the result is compared with run %s"
                              % (exp["impact_reference"]["run_id"], ref_id))
    for keys, why in ((violations, "was predicted to stay identical"), (uncertain_changed, "changed although its relation to the edit is uncertain")):
        for key in keys:
            d = divs.get(key)
            if not d:
                out["missing"].append("bar impossible to determine for %s: no divergence in the checked annexes" % key)
                out["next_check"] = {"kind": "review-output", "output": key, "reason": "%s %s" % (key, why)}
                return out
            facts_at, err = _bar_facts(cw.get("run_dir"), res.get("run_dir"), d)
            if not facts_at:
                out["missing"].append(err); out["next_check"] = {"kind": "review-output", "output": key, "reason": err}
                return out
            pred_why = next((r.get("because") for r in exp.get("impact") or [] if r.get("output") == key), None)
            out["next_check"] = {"kind": "read-bar", "series": key, "bar": d["first_index"], "at_bar": facts_at,
                                 "reason": "%s %s (%s); first established divergence at bar %d" % (key, why, pred_why, d["first_index"]),
                                 "runs": {"reference": ref_id, "result": cur_id},
                                 "also_not_comparable": unproven,
                                 "command": CMD + "inspect --run-id %s --bar %d --compare-run-id %s" % (cur_id, d["first_index"], ref_id)}
            return out
    if unpredicted:
        out["next_check"] = {"kind": "review-output", "outputs": unpredicted, "also_not_comparable": unproven,
                             "reason": "outputs changed that the impact analysis did not list: %s" % ", ".join(unpredicted)}
        return out
    for facet in ("objects", "styles"):
        if facet in facts["declared_unchanged_but_changed"]:
            out["next_check"] = {"kind": "review-%s" % facet, "also_not_comparable": unproven,
                                 "reason": "%s differ although not expected: %s" % (facet, "; ".join(q["facets"][facet]))}
            return out
    if unproven:
        out["missing"] += ["%s: %s" % (u["output"], u["limit"]) for u in unproven]
        out["next_check"] = {"kind": "incomplete-proof", "outputs": [u["output"] for u in unproven],
                             "runs": {"reference": ref_id, "result": cur_id},
                             "reason": "no equality can be stated for %s: %s; the other outputs are reported in "
                                       "outputs_observed" % (", ".join(u["output"] for u in unproven),
                                                              "; ".join("%s %s" % (u["output"], u["limit"]) for u in unproven))}
        return out
    if out["missing"]:
        out["next_check"] = {"kind": "none-possible", "reason": "the comparison is incomplete: see missing"}
        return out
    out["next_check"] = {"kind": "none", "reason": "every output behaved as the impact analysis allows: " + "; ".join(
        "%s %s (%s)" % (r["output"], r["observed"], r["predicted"]) for r in observed),
        "scope": "no further check is justified on the compared elements; see not_covered"}
    return out


SHORT_REASON = {"dataset_sha256": "different datasets", "configuration": "different run configurations",
                "pinets_version": "different PineTS versions", "executor_fingerprint": "different executors",
                "normalization_schema": "different normalization schemas", "execution_status": "a run is not PINETS_EXECUTION_PASS"}


def _short_reasons(codes):
    out = []
    for c in codes:
        t = SHORT_REASON.get(c) or ("unusable %s report" % ("reference" if c.startswith("malformed_report_a") else "result")
                                    if c.startswith("malformed_report_") else c)
        if t not in out:
            out.append(t)
    return ", ".join(out)


def _comparability_now(root, cw, res, q):
    """Comparability of the comparison run and the result, recomputed NOW from their two reports
    (qualify.comparability: no program started), united with any refusal recorded in the stored
    qualification. Without a workspace root (fixtures), only the recorded verdict is used."""
    if root is None:
        rec = q.get("comparability") or {}
        codes = list(rec.get("reasons") or []) if rec.get("comparable") is False else []
        cr = q.get("compare_runs") or {}
        if cr.get("status") == "PINETS_INCONCLUSIVE":
            codes += [c for c in cr.get("reasons") or [] if c != "compare-unavailable" and c not in codes]
        return {"comparable": not codes, "reasons": codes, "runs": {"reference": cw.get("run_id"), "result": res.get("run_id")},
                "explanation": None if not codes else
                "the reference %s and the result %s are not comparable: %s; no equality, difference or first divergence "
                "between them can be established, for any output" % (
                    cw.get("run_id"), res.get("run_id"), "; ".join(qualify.INCONCLUSIVE_EXPLAINED.get(c, c) for c in codes)),
                "established_by": "the verdict recorded in the qualification"}
    return qualify.comparability(cw.get("run_dir"), res.get("run_dir"), compare=q.get("compare_runs"),
                                 recorded=q.get("comparability"),
                                 run_ids={"reference": cw.get("run_id"), "result": res.get("run_id")})


def _iso(ms):
    import datetime
    try:
        dt = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + (".%03dZ" % (ms % 1000) if ms % 1000 else "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _run_facts(root, run_dir, run_id, role, keys):
    """What ONE run establishes about itself (no comparison with the other run): identity, its own
    dataset (checked against the SHA-256 its report records), its annex state now, and where each
    output is found and on how many points."""
    rep = qualify._read_report(Path(run_dir or "") / "run.json")
    try:
        rep_ok = isinstance(rep, dict) and not [r for r in qualify.report_reasons(rep, rep) if r.startswith("malformed_report_a")]
    except RecursionError:
        rep_ok = False
    rep = rep if isinstance(rep, dict) else {}
    ds = {"sha256": rep.get("dataset_sha256"), "matches_report": False, "bars": None, "first_time": None, "last_time": None}
    try:
        raw = (Path(run_dir or "") / "dataset.json").read_bytes()
        ds["matches_report"] = hashlib.sha256(raw).hexdigest() == rep.get("dataset_sha256")
        if ds["matches_report"]:
            data = json.loads(raw); bars = data.get("bars") if isinstance(data, dict) else None
            if isinstance(bars, list):
                t = lambda b: b.get("t") if isinstance(b, dict) else None
                ds.update(bars=len(bars), first_time=_iso(t(bars[0])) if bars else None,
                          last_time=_iso(t(bars[-1])) if bars else None)
    except (OSError, ValueError, AttributeError, RecursionError):
        pass
    annex = _annex_state(root, run_dir, run_id, role) if root is not None else {"ok": None, "code": None, "reason": "not checked"}
    inv = _series_inventory(run_dir)
    names = sorted(set(keys) | (set(inv["report"]) if rep_ok else set()) | (set(inv["annex"]) if annex.get("ok") else set()))
    series = {}
    for k in names:
        series[k] = {"report_points": (inv["report"].get(k, "absent") if rep_ok else "report not usable"),
                     "annex_points": (((lambda a: a[0] if len(a) == 1 else ("absent" if not a else {"ambiguous": a}))(inv["annex"].get(k) or []))
                                      if annex.get("ok") else
                                      "annex not usable (%s)" % (annex.get("code") or annex.get("reason")))}
    return {"role": role, "run_id": run_id or rep.get("run_id"), "revision_sha256": rep.get("source_sha256"),
            "execution_status": rep.get("execution_status"), "pinets_version": rep.get("pinets_version"),
            "executor_fingerprint": (rep.get("executor_fingerprint")[:12] if isinstance(rep.get("executor_fingerprint"), str) else None),
            "configuration": rep.get("configuration"), "report_usable": rep_ok, "dataset": ds,
            "annex": {k: annex.get(k) for k in ("ok", "code", "reason")}, "series": series}


def _not_comparable(out, exp, q, cw, res, comp, root):
    """The runs cannot be compared: the limit applies to every output. Both runs and the reason are
    named; each run's own facts are given separately; no equality, difference or first divergence
    between them is stated (no rows from the stored qualification, no expectation facts, no bar)."""
    ref_id, cur_id = cw.get("run_id"), res.get("run_id")
    outputs = sorted((exp or {}).get("outputs") or {})
    per_run = {"reference": _run_facts(root, cw.get("run_dir"), ref_id, "reference", outputs),
               "result": _run_facts(root, res.get("run_dir"), cur_id, "result", outputs)}
    short = _short_reasons(comp["reasons"])
    limit = "the runs are not comparable (%s): reference %s, result %s" % (short, ref_id, cur_id)
    if outputs:
        out["outputs_observed"] = [
            {"output": k, "predicted": exp["outputs"][k]["status"], "facet": exp["outputs"][k]["facet"],
             "because": next((x.get("because") for x in exp.get("impact") or [] if x.get("output") == k), None),
             "observed": "not comparable: " + limit,
             "per_run": {"reference": per_run["reference"]["series"].get(k), "result": per_run["result"]["series"].get(k)}}
            for k in outputs]
        out["outputs_not_comparable"] = [{"output": k, "limit": limit, "kind": "runs-not-comparable", "runs": [ref_id, cur_id]}
                                         for k in outputs]
    out["comparability"] = comp
    out["qualification"] = qualify.withheld(q, comp)
    out["facts"] = None
    out["missing"] = [comp["explanation"]]
    out["next_check"] = {"kind": "not-comparable", "runs": {"reference": ref_id, "result": cur_id},
                         "reasons": comp["reasons"], "reason": comp["explanation"], "per_run": per_run,
                         "note": "each run's facts are verified separately; any equality, difference or first divergence "
                                 "between the two runs is unverifiable",
                         "what_would_compare": ("usable reports for both runs (run.json)" if any(c.startswith("malformed_report_") for c in comp["reasons"])
                                                else "two PINETS_EXECUTION_PASS runs" if comp["reasons"] == ["execution_status"]
                                                else "two runs computed on the same dataset with the same configuration, PineTS "
                                                     "version, executor and normalization schema")}
    return out


def _for_result(st, lt, exp, root=None):
    """Recommendation about the last finished result (whatever its revision)."""
    res = st.get("result") or {}
    rev = res.get("revision_sha256")
    out = {"for_revision": rev, "result": {"run_id": res.get("run_id"), "state": res.get("state"),
                                         "timestamp": res.get("timestamp")},
           "reference": None, "expectation": exp, "facts": None, "next_check": None, "missing": [], "not_covered": NOT_COVERED}
    if res.get("state") == "failed":
        out["next_check"] = {"kind": "read-error", "reason": "the computation of this revision failed: %s"
                             % ((res.get("error") or {}).get("message") or res.get("execution_status")),
                             "command": CMD + "inspect --work"}
        return out
    if res.get("state") == "refused":
        out["next_check"] = {"kind": "read-refusal", "reason": "the chart annex of this revision was refused [%s]; "
                             "the numeric result stays valid" % ((res.get("refusal") or {}).get("code")),
                             "command": CMD + "inspect --work"}
        return out
    q = lt.get("qualification") if (lt.get("result") or {}).get("run_id") == res.get("run_id") else None
    if not q:
        out["missing"].append("no comparable reference: no earlier successful result in this session to compare with")
        out["next_check"] = {"kind": "none-possible", "reason": "nothing to compare this result with"}
        return out
    if q.get("error"):
        out["missing"].append("qualification unavailable: %s" % q["error"])
        return out
    cw = q.get("compared_with") or {}
    out["reference"] = {"run_id": cw.get("run_id"), "revision_sha256": cw.get("revision_sha256"), "timestamp": cw.get("timestamp")}
    # the comparability of the two runs is checked NOW, before anything is stated between them
    comp = _comparability_now(root, cw, res, q)
    if not comp["comparable"]:
        return _not_comparable(out, exp, q, cw, res, comp, root)
    out["comparability"] = comp
    out["qualification"] = {k: q.get(k) for k in ("change", "changed_facets", "facets", "source", "uncertain", "gating_note")}
    if root is not None:
        states = [dict(_annex_state(root, cw.get("run_dir"), cw.get("run_id"), "reference"), run_dir=cw.get("run_dir")),
                  dict(_annex_state(root, res.get("run_dir"), res.get("run_id"), "result"), run_dir=res.get("run_dir"))]
        if not all(s["ok"] for s in states) or str(q.get("annex", "")).startswith("not compared"):
            if all(s["ok"] for s in states):                         # usable now, but the qualification did not compare them
                for s in states:
                    s.update(ok=False, code="NOT_COMPARED_AT_QUALIFICATION", reason=q.get("annex"))
            out["next_check"] = _unverifiable(states, exp, q, cw, res)
            out["missing"].append(out["next_check"]["summary"])
            out["facts"] = None                                      # no expectation facts from uncomparable facets
            out["qualification"] = {"source": q.get("source"), "gating_note": q.get("gating_note"),
                                    "uncertain": [u for u in q.get("uncertain") or [] if not u.startswith("chart content not compared")],
                                    "withheld": "change, changed_facets and facets of the earlier qualification are not "
                                                "reused while an annex is not usable now"}
            return out
    if q.get("uncertain"):
        out["missing"] += ["comparison incomplete: %s" % u for u in q["uncertain"]]
    if not exp:
        out["missing"].append("no expectation declared for revision %s: declare it before examining the result (%sexpect "
                              "--change <facets> --unchanged <facets> --note ...)" % ((rev or "?")[:12], CMD))
        out["next_check"] = {"kind": "declare-expectation", "reason": "without the impact inventory's expectation, an "
                             "observed difference cannot be qualified", "command": CMD + "expect --change ... --unchanged ..."}
        return out
    facts = qualify.expectation_facts(exp, q); out["facts"] = facts
    if exp.get("outputs"):
        return _per_output(out, exp, q, cw, res, facts)
    unexpected = set(facts["declared_unchanged_but_changed"]) | set(facts["observed_not_declared"])
    divs = q.get("divergences") or []
    cur_dir, ref_dir = res.get("run_dir"), cw.get("run_dir")
    for facet in ("signals", "values"):
        if facet in unexpected:
            cand = sorted((d for d in divs if d["facet"] == facet), key=lambda d: d["first_index"])
            if not cand:
                out["missing"].append("bar impossible to determine: %s differ (%s) but no series divergence index is "
                                      "available" % (facet, "; ".join(q["facets"][facet])))
                out["next_check"] = {"kind": "review-%s" % facet, "reason": "%s differ although %s"
                                     % (facet, "declared unchanged" if facet in facts["declared_unchanged_but_changed"] else "not declared")}
                return out
            d = cand[0]
            facts_at, why = _bar_facts(ref_dir, cur_dir, d)
            if not facts_at:
                out["missing"].append(why); out["next_check"] = {"kind": "review-%s" % facet, "reason": why}
                return out
            same_bar = [s for s in q["facets"]["styles"] if s.endswith("first index %d" % d["first_index"])]
            out["next_check"] = {
                "kind": "read-bar",
                "reason": "%s were expected to stay unchanged (expected change: %s); %s %r differs, first established "
                          "divergence at bar %d" % (facet, ", ".join(exp.get("change") or []) or "none", "signal" if facet == "signals"
                                                     else "series", d["series"], d["first_index"]),
                "series": d["series"], "bar": d["first_index"], "at_bar": facts_at,
                "runs": {"reference": cw.get("run_id"), "result": res.get("run_id")},
                "other_divergences": [x for x in cand[1:]] + [x for x in divs if x["facet"] != facet],
                "same_bar_style_differences": same_bar,
                "command": CMD + "inspect --run-id %s --bar %d --compare-run-id %s" % (res.get("run_id"), d["first_index"], cw.get("run_id"))}
            return out
    if "objects" in unexpected:
        out["next_check"] = {"kind": "review-objects", "reason": "drawing objects differ although not expected: %s (final "
                             "state only: no bar can be assigned)" % "; ".join(q["facets"]["objects"]),
                             "runs": {"reference": cw.get("run_id"), "result": res.get("run_id")}}
        return out
    if "styles" in unexpected:
        out["next_check"] = {"kind": "review-styles", "reason": "styles differ although not expected: %s" % "; ".join(q["facets"]["styles"]),
                             "runs": {"reference": cw.get("run_id"), "result": res.get("run_id")}}
        return out
    if facts["declared_change_not_observed"]:
        out["next_check"] = {"kind": "check-expected-change", "reason": "the expected change of %s was not observed"
                             % ", ".join(facts["declared_change_not_observed"])}
        return out
    if out["missing"]:
        out["next_check"] = {"kind": "none-possible", "reason": "the comparison is incomplete: see missing"}
        return out
    changed = q.get("changed_facets") or []
    out["next_check"] = {"kind": "none",
                         "reason": "only the expected change was observed (%s); %s identical on the compared elements"
                                   % ("; ".join(sum((q["facets"][f] for f in changed), [])) or q.get("change"),
                                      ", ".join(f for f in ("values", "signals", "objects", "styles") if f not in changed)),
                         "scope": "no further check is justified on the compared elements; see not_covered"}
    return out


def next_check(root, wait=0):
    """The next useful check of the session, advisory, bound to the revision of its result."""
    root = Path(root)
    st = live.status(root, wait=wait)
    base = {"advisory": True, "engine_invocations": 0,
            "interpretation": "EXPECTED / UNEXPECTED / UNRESOLVED is Claude Code's judgement against the request and the "
                              "impact inventory; UNRESOLVED when the evidence does not decide. Not a regression verdict, an "
                              "accepted baseline, a TradingView validation or a calibration decision."}
    if not st.get("ok"):
        return dict(base, ok=False, missing=["no local test session: start one with %swork --slug <slug> --dataset <path>" % CMD])
    wd = live.work_dir(root, st["session"]["slug"])
    lt = _read(wd / "latest.json") or {}
    exps = _read(wd / live.EXPECT) or {}
    req = st["requested"]["revision_sha256"]
    out = dict(base, ok=True, work_source=st["session"]["work_source"], requested_revision=req, fresh=st["fresh"],
               computing=(st.get("computing") or {}).get("revision_sha256"), wait=st.get("wait"),
               last_good={k: (st.get("last_good") or {}).get(k) for k in ("run_id", "revision_sha256", "timestamp")})
    if not st.get("result"):
        out.update(applies_to_requested=False, missing=["no finished result yet for any revision"],
                   next_check={"kind": "wait", "reason": "the first computation is not finished",
                               "command": CMD + "status --wait 120"})
        return out
    rec = _for_result(st, lt, exps.get(st["result"]["revision_sha256"]), root=root)
    if st["fresh"]:
        out.update(applies_to_requested=True, **rec)
        return out
    out.update(applies_to_requested=False,
               missing=["the last finished result belongs to revision %s, not to the requested revision %s%s"
                        % ((st["result"]["revision_sha256"] or "?")[:12], req[:12],
                           " (being computed)" if out["computing"] == req else "")],
               next_check={"kind": "wait", "reason": "no result of the requested revision yet",
                           "command": CMD + "next --wait 120"},
               earlier_revision_recommendation=rec)
    return out
