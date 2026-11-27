# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL adaptive validation loop (isolated study copy): what Claude Code reads is tied to the
requested revision (status / inspect --work, bounded wait, failure then new save, history by run_id
unchanged), change qualification on results already computed (compareRuns, useful annex content,
comment-only source), expectation facts, and the Vela observation title (stale / incomplete /
off-target answers are 'not observed'). No PineTS call: runs are fixtures; `node runner.mjs
compare` (no engine import) is the only Node program started."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import annex_reader, live, local_test, qualify

ROOT = Path(__file__).resolve().parents[2]
T0 = 1577836800000


def make_run(d, run_id, vals=None, color="#9C27B0", drawings=None, src="//@version=6\nplot(x)\n", n=30, alerts=None,
             title="RSI", shape=None):
    """A consistent run folder (report, annex, dataset, source snapshot, local-test.json)."""
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    vals = vals or [50.0 + i * 0.5 for i in range(n)]
    ds = {"schema": "pws-dataset-v1", "descriptor": {"price_scale": 100},
          "bars": [{"t": T0 + i * 3600000, "o": 10000 + i, "h": 10050 + i, "l": 9950 + i, "c": 10010 + i, "v": 1} for i in range(n)]}
    (d / "dataset.json").write_text(json.dumps(ds))
    dsha = hashlib.sha256((d / "dataset.json").read_bytes()).hexdigest()
    plots = {"RSI": [{"t": T0 + i * 3600000, "v": vals[i]} for i in range(n)],
             "Upper": [{"t": T0 + i * 3600000, "v": 70} for i in range(n)]}
    series = [{"key": "RSI", "title": title, "callsite": "#0", "kind": "line", "options": {"color": color},
               "points": [{"t": T0 + i * 3600000, "v": vals[i]} for i in range(n)]},
              {"key": "Upper", "title": "Upper", "callsite": "#1", "kind": "hline", "options": {"color": "#F23645"},
               "points": [{"t": T0 + i * 3600000, "v": 70} for i in range(n)]}]
    if shape is not None:
        plots["Sig"] = [{"t": T0 + i * 3600000, "v": shape[i]} for i in range(n)]
        series.append({"key": "Sig", "title": "Sig", "callsite": "#2", "kind": "shape", "options": {"color": "#00FF00"},
                       "points": [{"t": T0 + i * 3600000, "v": shape[i]} for i in range(n)]})
    normalized = {"schema": "pws-pinets-norm-v2", "alerts": alerts or [], "warnings": [], "internal_keys_present": [],
                  "plots": plots}
    ident = {"run_id": run_id, "source_sha256": hashlib.sha256(src.encode()).hexdigest(), "dataset_sha256": dsha,
             "pinets_version": "0.13.1", "executor_fingerprint": "b" * 64, "normalization_schema": "pws-pinets-norm-v2",
             "normalized_payload_sha256": annex_reader.payload_sha256(normalized)}
    annex = dict(ident, schema=local_test.GRAPHICS_SCHEMA, declaration={"title": "T", "overlay": False}, series=series,
                 drawings=drawings or {}, drawings_scope="final-state", limits=[])
    text = json.dumps(annex, indent=1) + "\n"
    (d / "graphics.json").write_text(text)
    rep = dict(ident, schema="pws-pinets-run-v1", execution_status="PINETS_EXECUTION_PASS", normalized=normalized,
               timestamp="2026-11-23T20:00:00Z", configuration={},
               dataset_descriptor={"type": "synthetic", "price_scale": 100},
               capabilities_used={"ta-rsi": {"capability_status": "EXPERIMENTAL", "calibration_status": "MISSING"},
                                  "plot-plot": {"capability_status": "EXPERIMENTAL", "calibration_status": "CURRENT"}},
               unclassified_tokens=[], graphics_annex={"schema": local_test.GRAPHICS_SCHEMA,
                                                       "sha256": hashlib.sha256(text.encode()).hexdigest(),
                                                       "status": "GRAPHICS_WRITTEN", "error": None})
    (d / "run.json").write_text(json.dumps(rep, indent=1))
    (d / "S.pine").write_text(src)
    (d / "local-test.json").write_text(json.dumps({"source_snapshot": "S.pine", "origin": "work", "dataset_origin": "d.json"}))
    return d



DAY = 86400000


def rewrite_run(d, days=0, close_delta=None, configuration=None, fingerprint=None):
    """Rewrite ONE fixture run so that it stays valid on its own (reader contract v1): shift every
    timestamp (dataset, report series, annex series) by `days`, change the close of some bars
    ({index: delta in price-scale units}), set the report configuration or the executor fingerprint
    (report and annex identity). Every hash is re-derived."""
    d = Path(d); off = days * DAY
    ds = json.loads((d / "dataset.json").read_text())
    for i, b in enumerate(ds["bars"]):
        b["t"] += off
        if close_delta and i in close_delta:
            b["c"] += close_delta[i]; b["h"] = max(b["h"], b["c"]); b["l"] = min(b["l"], b["c"])
    (d / "dataset.json").write_text(json.dumps(ds))
    dsha = hashlib.sha256((d / "dataset.json").read_bytes()).hexdigest()
    rep = json.loads((d / "run.json").read_text()); g = json.loads((d / "graphics.json").read_text())
    for pts in rep["normalized"]["plots"].values():
        for p in pts:
            p["t"] += off
    for s_ in g["series"]:
        for p in s_["points"]:
            p["t"] += off
    rep["dataset_sha256"] = g["dataset_sha256"] = dsha
    if configuration is not None:
        rep["configuration"] = configuration
    if fingerprint is not None:
        rep["executor_fingerprint"] = g["executor_fingerprint"] = fingerprint
    rep["normalized_payload_sha256"] = g["normalized_payload_sha256"] = annex_reader.payload_sha256(rep["normalized"])
    text = json.dumps(g, indent=1) + "\n"; (d / "graphics.json").write_text(text)
    rep["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (d / "run.json").write_text(json.dumps(rep, indent=1))
    return d

class SourceClassification(unittest.TestCase):
    def test_comment_only_keeps_strings_directives_and_indentation(self):
        base = '//@version=6\nindicator("A // not a comment")\nif x\n    plot(1) // one\n'
        self.assertEqual(qualify.source_change(base, base.replace("// one", "// two")), "comment-only")
        self.assertEqual(qualify.source_change(base, base + "// trailing note\n\n"), "comment-only")
        self.assertEqual(qualify.source_change(base, base.replace("A // not", "A // NOT")), "code")        # string
        self.assertEqual(qualify.source_change(base, base.replace("//@version=6", "//@version=5")), "code")  # directive
        self.assertEqual(qualify.source_change(base, base.replace("    plot", "  plot")), "code")         # indentation
        self.assertEqual(qualify.source_change(base, base), "identical")


class AnnexAndCompare(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws qualify "))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def q(self, a, b):
        return qualify.qualify(ROOT, b, a)

    def test_recomputation_alone_is_unchanged_even_if_the_annex_sha_differs(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = make_run(self.tmp / "b", "pexec-b")
        self.assertNotEqual((a / "graphics.json").read_bytes(), (b / "graphics.json").read_bytes())
        q = self.q(a, b)
        self.assertEqual((q["change"], q["compare_runs"]["status"]), ("unchanged", "PINETS_REGRESSION_UNCHANGED"))
        self.assertEqual(q["compared_with"]["run_id"], "pexec-a")

    def test_style_only_is_presentation_only(self):
        q = self.q(make_run(self.tmp / "a", "pexec-a"), make_run(self.tmp / "b", "pexec-b", color="#FF0000"))
        self.assertEqual(q["change"], "presentation-only")
        self.assertEqual(q["facets"]["styles"], ["series RSI options color"])

    def test_values_and_styles_together_are_both_named(self):
        q = self.q(make_run(self.tmp / "a", "pexec-a"),
                   make_run(self.tmp / "b", "pexec-b", vals=[40.0 + i for i in range(30)], color="#FF0000"))
        self.assertEqual(q["change"], "values+styles")
        self.assertTrue(q["facets"]["values"][0].startswith("series RSI first index 0"))

    def test_signals_and_objects(self):
        a = make_run(self.tmp / "a", "pexec-a", shape=[None] * 30,
                     drawings={"labels": [{"x": 1, "y": 2.0, "text": "A", "color": "#fff"}]})
        b = make_run(self.tmp / "b", "pexec-b", shape=[None] * 29 + [1.0],
                     drawings={"labels": [{"x": 1, "y": 3.0, "text": "A", "color": "#000"}]})
        q = self.q(a, b)
        self.assertEqual(q["changed_facets"], ["signals", "objects", "styles"])
        self.assertIn("labels content of 1 object(s)", q["facets"]["objects"])
        self.assertIn("labels style of 1 object(s)", q["facets"]["styles"])

    def test_shape_attributes_of_a_changed_signal_are_not_a_style_change(self):
        a = make_run(self.tmp / "a", "pexec-a", shape=[None] * 30)
        b = make_run(self.tmp / "b", "pexec-b", shape=[None] * 29 + [1.0])
        g = json.loads((b / "graphics.json").read_text())
        for s in g["series"]:
            if s["key"] == "Sig":
                s["points"][29]["o"] = {"shape": "shape_triangle_down", "location": "Top"}
        text = json.dumps(g, indent=1) + "\n"; (b / "graphics.json").write_text(text)
        rep = json.loads((b / "run.json").read_text()); rep["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
        (b / "run.json").write_text(json.dumps(rep, indent=1))
        q = self.q(a, b)
        self.assertEqual(q["changed_facets"], ["signals"]); self.assertEqual(q["facets"]["styles"], [])

    def test_comment_only_source(self):
        q = self.q(make_run(self.tmp / "a", "pexec-a", src="plot(x) // a\n"), make_run(self.tmp / "b", "pexec-b", src="plot(x) // b\n"))
        self.assertEqual((q["source"], q["change"]), ("comment-only", "comment-only"))

    def test_not_comparable_is_inconclusive_and_explained(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = make_run(self.tmp / "b", "pexec-b", n=31)
        q = self.q(a, b)
        self.assertEqual(q["compare_runs"]["status"], "PINETS_INCONCLUSIVE")
        self.assertIn("the two runs used different datasets", q["uncertain"][0])
        # nothing is compared between runs that are not comparable
        self.assertEqual((q["change"], q["changed_facets"], q["divergences"]), ("not-comparable", [], []))
        self.assertEqual(q["facets"], {"values": [], "signals": [], "objects": [], "styles": []})
        self.assertEqual(q["comparability"]["reasons"], ["dataset_sha256"])
        self.assertIn("the reference pexec-a and the result pexec-b are not comparable", q["comparability"]["explanation"])
        self.assertIn("30 bars in the reference, 31 in the result", q["comparability"]["explanation"])
        self.assertEqual(q["annex"], "not compared: the runs are not comparable")
        self.assertIsNone(qualify.expectation_facts({"change": ["styles"], "unchanged": ["values"]}, q))

    def test_shifted_dataset_gives_no_cross_run_facet(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = rewrite_run(make_run(self.tmp / "b", "pexec-b", vals=[40.0 + i for i in range(30)]), days=365)
        self.assertTrue(local_test.check(ROOT, a)["ok"] and local_test.check(ROOT, b)["ok"])      # each valid on its own
        q = self.q(a, b)
        self.assertEqual((q["change"], q["divergences"], q["changed_facets"]), ("not-comparable", [], []))
        self.assertIn("same 30 bars and prices, every timestamp shifted by +365 days", q["comparability"]["explanation"])

    def test_configuration_the_port_cannot_write_is_not_a_false_refusal(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = make_run(self.tmp / "b", "pexec-b")
        ra, rb = (json.loads((x / "run.json").read_text()) for x in (a, b))
        ra["configuration"] = {"k": "\ud800"}; rb["configuration"] = {"k": "\ud800"}     # lone surrogate, identical
        for r_ in (ra, rb):
            r_["normalized_payload_sha256"] = annex_reader.payload_sha256(r_["normalized"])
        self.assertNotIn("configuration", qualify.report_reasons(ra, rb))
        rb["configuration"] = {"k": "\ud801"}
        self.assertIn("configuration", qualify.report_reasons(ra, rb))

    def test_recorded_refusal_without_reason_stays_a_refusal(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = make_run(self.tmp / "b", "pexec-b")
        self.assertTrue(qualify.comparability(a, b)["comparable"])
        self.assertTrue(qualify.comparability(a, b, compare={"status": "PINETS_INCONCLUSIVE", "reasons": ["compare-unavailable"]})["comparable"])
        c = qualify.comparability(a, b, recorded={"comparable": False, "reasons": []})
        self.assertEqual((c["comparable"], c["reasons"]), (False, ["recorded-refusal"]))
        (b / "run.json").unlink()
        c = qualify.comparability(a, b, run_ids={"reference": "pexec-a", "result": "pexec-b"})
        self.assertIn("the report of the result pexec-b is missing or unreadable (run.json)", c["explanation"])

    def test_python_mirror_agrees_with_the_runner_compare(self):
        """qualify.report_reasons gives the same reasons as the runner's compareRuns (node, no PineTS)."""
        base = make_run(self.tmp / "base", "pexec-base")
        variants = {
            "same": make_run(self.tmp / "same", "pexec-same"),
            "dataset": rewrite_run(make_run(self.tmp / "ds", "pexec-ds"), days=365),
            "prices": rewrite_run(make_run(self.tmp / "px", "pexec-px"), close_delta={5: 100}),
            "configuration": rewrite_run(make_run(self.tmp / "cf", "pexec-cf"), configuration={"inputs": {"len": 21}}),
            "configuration-number-form": rewrite_run(make_run(self.tmp / "cn", "pexec-cn"), configuration={}),
            "executor": rewrite_run(make_run(self.tmp / "ex", "pexec-ex"), fingerprint="c" * 64),
        }
        bad_ts = make_run(self.tmp / "ts", "pexec-ts"); r = json.loads((bad_ts / "run.json").read_text())
        r["timestamp"] = "2026-11-23 20:00:00"; (bad_ts / "run.json").write_text(json.dumps(r)); variants["malformed-timestamp"] = bad_ts
        failed = make_run(self.tmp / "fl", "pexec-fl"); r = json.loads((failed / "run.json").read_text())
        r["execution_status"] = "PINETS_EXECUTION_FAIL"; (failed / "run.json").write_text(json.dumps(r)); variants["fail"] = failed
        for name, v in variants.items():
            runner = qualify.compare_runs(ROOT, base, v)
            mirror = qualify.report_reasons(json.loads((base / "run.json").read_text()), json.loads((v / "run.json").read_text()))
            self.assertEqual(mirror, runner.get("reasons") or [], name)

    def test_altered_annex_is_not_compared(self):
        a = make_run(self.tmp / "a", "pexec-a"); b = make_run(self.tmp / "b", "pexec-b", color="#FF0000")
        (b / "graphics.json").write_text((b / "graphics.json").read_text().replace("#FF0000", "#00FF00"))
        q = self.q(a, b)
        self.assertIn("refused", q["annex"]); self.assertEqual(q["change"], "uncertain")

    def test_gating_is_derived_and_never_claimed(self):
        q = self.q(make_run(self.tmp / "a", "pexec-a"), make_run(self.tmp / "b", "pexec-b"))
        self.assertFalse(q["all_effectively_gating"])
        self.assertIn("no blocking conclusion", q["gating_note"])
        self.assertIn("neither a confirmed regression nor an accepted baseline nor a TradingView validation", q["authority"])

    def test_expectation_facts(self):
        f = qualify.expectation_facts({"change": ["values"], "unchanged": ["styles"]},
                                      {"changed_facets": ["values", "styles"], "uncertain": []})
        self.assertEqual((f["declared_change_observed"], f["declared_unchanged_but_changed"]), (["values"], ["styles"]))


class Freshness(unittest.TestCase):
    """latest.json as `compute` writes it, read by status / inspect_work (runs are fixtures)."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws fresh "))
        self.root = self.tmp / "root"; (self.root / live.WORK / "x").mkdir(parents=True)
        self.src = self.root / live.WORK / "x" / "S.pine"; self.src.write_text("v1\n")
        self.sess = {"slug": "x", "work_source": str(self.src), "dataset": "d", "language": "fr", "token": "t1"}
        (self.root / live.SESSION).write_text(json.dumps(self.sess))
        self.runs = {}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_run(self, root, slug, dataset, graphics, lang, source=None, origin=None):
        text = Path(source).read_text(); rid = "pexec-%02d" % (len(self.runs) + 1)
        d = make_run(self.tmp / "runs" / rid, rid, src=text, vals=None if "ok" in text or "v" in text else None)
        if "BROKEN" in text:
            rep = json.loads((d / "run.json").read_text()); rep.update(execution_status="PINETS_EXECUTION_FAIL",
                                                                         normalized=None, error={"message": "Failed to transpile"})
            (d / "run.json").write_text(json.dumps(rep))
            self.runs[rid] = d
            return {"ok": False, "run_id": rid, "run_dir": str(d), "execution_status": "PINETS_EXECUTION_FAIL",
                    "error": {"message": "Failed to transpile"}, "source_sha256": hashlib.sha256(text.encode()).hexdigest()}
        self.runs[rid] = d
        return {"ok": True, "run_id": rid, "run_dir": str(d), "execution_status": "PINETS_EXECUTION_PASS",
                "error": None, "source_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def patched(self):
        return [mock.patch.object(local_test, "run", side_effect=self.fake_run),
                mock.patch.object(local_test, "chart_component", return_value=False),
                mock.patch.object(live, "write_work_frame", return_value=None),
                mock.patch.object(qualify, "compare_runs", return_value={"comparable": True, "status": "PINETS_REGRESSION_UNCHANGED", "changed": []})]

    def test_running_failure_new_save_and_history(self):
        ps = self.patched()
        for p in ps: p.start()
        try:
            live.compute(self.root, self.sess, "start")                      # A ok
            st = live.status(self.root)
            self.assertTrue(st["fresh"]); self.assertEqual(st["result"]["run_id"], "pexec-01")
            self.assertTrue(st["last_good"]["timestamp"])
            # a new save while A is the last result: nothing of A is presented as current
            self.src.write_text("v2\n")
            st = live.status(self.root)
            self.assertFalse(st["fresh"]); self.assertEqual(st["result"]["relation"], "earlier-revision")
            ins = live.inspect_work(self.root, bar=5, wait=0)
            self.assertEqual((ins["run_id"], ins["values"], ins["fresh"]), (None, None, False))
            self.assertEqual(ins["last_good_values"]["run_id"], "pexec-01")
            # the running record names only the revision in computation
            real = live._write_json; seen = {}
            def spy(path, data):
                if Path(path).name == "latest.json" and data.get("state") == "running":
                    seen.update(data)
                real(path, data)
            with mock.patch.object(live, "_write_json", side_effect=spy):
                live.compute(self.root, self.sess, "save")                   # B ok
            self.assertEqual((seen["run_id"], seen["run_dir"]), (None, None))
            self.assertEqual(seen["computing"]["revision_sha256"], live._sha(self.src))
            self.assertEqual(seen["result"]["run_id"], "pexec-01")
            # failure, then a new save while the failure is the last result
            self.src.write_text("BROKEN\n"); live.compute(self.root, self.sess, "save")   # C failed
            ins = live.inspect_work(self.root, bar=5, wait=0)
            self.assertTrue(ins["fresh"]); self.assertEqual(ins["execution_status"], "PINETS_EXECUTION_FAIL")
            self.assertEqual(ins["freshness"]["last_good"]["run_id"], "pexec-02")
            self.src.write_text("v4\n")
            ins = live.inspect_work(self.root, bar=5, wait=0)
            self.assertFalse(ins["fresh"]); self.assertIsNone(ins["error"])          # C's error is not presented as current
            self.assertEqual(ins["freshness"]["result"]["state"], "failed")
            self.assertEqual(ins["freshness"]["result"]["relation"], "earlier-revision")
            self.assertEqual(ins["last_good_values"]["run_id"], "pexec-02")
            # history by run_id keeps its meaning and its keys
            old = live.inspect(self.root, self.runs["pexec-01"], bar=5)
            self.assertEqual(old["run_id"], "pexec-01")
            self.assertNotIn("freshness", old); self.assertNotIn("qualification", old)
        finally:
            for p in ps: p.stop()

    def test_bounded_wait_reports_a_save_during_the_wait(self):
        ps = self.patched()
        for p in ps: p.start()
        try:
            live.compute(self.root, self.sess, "start")
            self.src.write_text("v1b\n")                                      # saved, not computed: not fresh
            def saver():
                time.sleep(0.3); self.src.write_text("v2\n"); time.sleep(0.3); self.src.write_text("v3\n")
            th = threading.Thread(target=saver); th.start()
            st = live.status(self.root, wait=1.2); th.join()
            self.assertFalse(st["fresh"])
            self.assertEqual(st["wait"]["outcome"].split(";")[0], "superseded")
            # a non-atomic write can be read half-way: transient revisions may appear between the two saves
            seen = st["wait"]["revisions_seen"]
            self.assertGreaterEqual(len(seen), 3)
            self.assertEqual((seen[0], seen[-1]), (hashlib.sha256(b"v1b\n").hexdigest(), hashlib.sha256(b"v3\n").hexdigest()))
            self.assertIn(hashlib.sha256(b"v2\n").hexdigest(), seen)
            w = st["wait"]
            self.assertTrue(w["revision_changed"])
            self.assertEqual((w["initial_revision"], w["final_revision"]), (w["revisions_seen"][0], w["revisions_seen"][-1]))
            self.assertEqual(w["result_revision"], st["result"]["revision_sha256"])
            self.assertIn("revision changed during the wait: %s -> %s" % (w["initial_revision"][:12], w["final_revision"][:12]), w["summary"])
            self.assertIn("not the requested revision", w["summary"])
            self.assertLess(st["wait"]["waited_s"], 3)
            live.compute(self.root, self.sess, "save")                     # fresh again: returns at once
            self.assertEqual(live.status(self.root, wait=10_000)["wait"]["requested_s"], live.WAIT_CAP_S)
        finally:
            for p in ps: p.stop()

    def test_wait_without_change_and_change_then_fresh(self):
        ps = self.patched()
        for p in ps: p.start()
        try:
            live.compute(self.root, self.sess, "start")
            st = live.status(self.root, wait=5)                              # already fresh: no change seen
            self.assertEqual((st["fresh"], st["wait"]["outcome"], st["wait"]["revision_changed"]), (True, "fresh", False))
            self.assertIn("revision unchanged during the wait", st["wait"]["summary"])
            self.src.write_text("v1b\n")
            st = live.status(self.root, wait=0.4)                            # saved, not computed, no change during the wait
            self.assertEqual((st["fresh"], st["wait"]["outcome"].split(";")[0], st["wait"]["revision_changed"]), (False, "timeout", False))
            self.src.write_text("v1c\n")                                     # B saved; C saved during the wait, then computed
            def later():
                time.sleep(0.3); self.src.write_text("v1d\n"); time.sleep(0.3); live.compute(self.root, self.sess, "save")
            th = threading.Thread(target=later); th.start()
            st = live.status(self.root, wait=5); th.join()
            w = st["wait"]
            self.assertEqual((st["fresh"], w["outcome"], w["revision_changed"]), (True, "fresh", True))
            self.assertEqual((w["initial_revision"], w["final_revision"], w["result_revision"]),
                             (hashlib.sha256(b"v1c\n").hexdigest(), live._sha(self.src), live._sha(self.src)))
            self.assertIn("result shown: revision %s" % live._sha(self.src)[:12], w["summary"])
        finally:
            for p in ps: p.stop()

    def test_legacy_latest_is_still_readable(self):
        d = make_run(self.tmp / "runs" / "old", "pexec-old", src="v1\n")
        live._write_json(live.work_dir(self.root, "x") / "latest.json", {
            "seq": 1, "state": "ok", "revision_sha256": live._sha(self.src), "run_id": "pexec-old", "run_dir": str(d)})
        st = live.status(self.root)
        self.assertTrue(st["fresh"]); self.assertEqual(st["result"]["timestamp"], "2026-11-23T20:00:00Z")

    def test_expectation_is_bound_to_the_saved_revision(self):
        r = live.expect(self.root, change=["values"], unchanged=["styles"], note="RSI length 14 -> 10")
        self.assertEqual(r["expectation"]["revision_sha256"], live._sha(self.src))
        with self.assertRaises(ValueError):
            live.expect(self.root, change=["colours"])


class Observation(unittest.TestCase):
    REQ, RUN, T = "abc123", "pexec-f7", 1579618800000

    def title(self, **over):
        f = dict(req=self.REQ, status="observed", run=self.RUN, series="RSI", bar="495", t=str(self.T), pane="pane-pws-work",
                 cursor_pane="study/pane-pws-work", value="50.2847753904", datawindow="50,28", vela="0.10.15 25ed1ef43c25 verified")
        f.update(over)
        return "PWS-OBS v1 | " + " | ".join("%s=%s" % kv for kv in f.items()) + " | end"

    def judge(self, title):
        return live.judge_observation(live.parse_obs_title(title), self.REQ, self.RUN, "RSI", 495, self.T)

    def test_observed_and_refusals(self):
        self.assertEqual(self.judge(self.title()), "observed")
        self.assertIn("stale title", self.judge(self.title(req="old999")))
        self.assertIn("incomplete", self.judge(self.title()[:-len(" | end")]))
        self.assertIn("incomplete", self.judge("PWS-OBS v1 | req=%s | status=pending" % self.REQ))
        self.assertIn("target mismatch", self.judge(self.title(t="1579615200000")))
        self.assertIn("target mismatch", self.judge(self.title(run="pexec-other")))
        self.assertIn("page reports not-reached", self.judge(self.title(status="not-reached")))
        self.assertIn("cursor not on the series pane", self.judge(self.title(cursor_pane="price/price")))
        self.assertIn("not verified", self.judge(self.title(vela="0.10.15 25ed1ef43c25 UNVERIFIED")))
        self.assertIn("no observation title", self.judge("PWS | pinned | ok"))

    def test_without_vela_nothing_is_opened_and_the_numeric_result_stays(self):
        tmp = Path(tempfile.mkdtemp(prefix="pws obs "))
        try:
            d = make_run(tmp / "r", "pexec-x")
            opened = []
            with mock.patch.object(live, "vela_state", return_value="no-deps"):
                r = live.observe(ROOT, d, 5, "RSI", opener=opened.append, reader=lambda u: None, closer=lambda u: None)
            self.assertFalse(r["ok"]); self.assertIn("browser chart unavailable", r["status"]); self.assertEqual(opened, [])
            self.assertEqual(live.inspect(ROOT, d, bar=5)["values"]["RSI"], 52.5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unknown_series_or_bar_is_refused_before_opening(self):
        tmp = Path(tempfile.mkdtemp(prefix="pws obs "))
        try:
            d = make_run(tmp / "r", "pexec-x"); opened = []
            if live.vela_state(ROOT) != "ready":
                self.skipTest("Vela not installed here")
            with mock.patch.object(live, "view_dir", lambda root, name: tmp / "views" / name):
                r = live.observe(ROOT, d, 5, "Upper", opener=opened.append, reader=lambda u: None, closer=lambda u: None)
                self.assertIn("not drawn by Vela", r["status"])
                r = live.observe(ROOT, d, 99, "RSI", opener=opened.append, reader=lambda u: None, closer=lambda u: None)
                self.assertIn("outside", r["status"])
            self.assertEqual(opened, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_stale_page_title_times_out_as_not_observed(self):
        tmp = Path(tempfile.mkdtemp(prefix="pws obs "))
        try:
            if live.vela_state(ROOT) != "ready":
                self.skipTest("Vela not installed here")
            d = make_run(tmp / "r", "pexec-x"); opened = []
            stale = self.title(req="old999", run="pexec-x", t=str(T0 + 5 * 3600000), bar="5")
            with mock.patch.object(live, "view_dir", lambda root, name: tmp / "views" / name):
                r = live.observe(ROOT, d, 5, "RSI", timeout=1.2, opener=opened.append, reader=lambda u: stale,
                                 closer=lambda u: None)
            self.assertFalse(r["ok"]); self.assertIn("stale title", r["status"]); self.assertEqual(len(opened), 1)
            self.assertIsNone(r["vela_event_value"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_page_contains_the_observation_and_never_overwrites_its_answer(self):
        js = (ROOT / "tools" / "vela_view" / "page" / "pws-view.js").read_text()
        self.assertIn("onCrosshairMove(function (e) { last = e; })", js)
        self.assertIn("'pws-work:' + key", js)
        self.assertIn("tries < 40", js)
        self.assertIn("document.title = OB ? (obsState.title", js)


if __name__ == "__main__":
    unittest.main()
