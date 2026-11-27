# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL impact of a source change on the outputs (tools/pws_workspace/impact.py) and its use by
`local-test next` (D2): dependencies established from names in single-line definitions only;
constants stay identical; unfollowed constructs make the relation uncertain; a may-change output
identical on the tested bars is not an anomaly; an output predicted identical that differs is read
at its first divergence bar (D1); an unusable annex still makes everything unverifiable."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import annex_reader, impact, live, local_test, qualify, recommend
from tools.tests.test_adaptive_loop import make_run, rewrite_run
from tools.tests.test_next_check import REAL_COMPARE, ROOT

BASE = '''//@version=6
indicator("Demo")
r = ta.rsi(close, 14)
plot(r, "RSI", color=color.purple)
hline(70, "Upper", color=color.red)
hline(30, "Lower", color=color.green)
plotshape(r > 70, "Overbought", shape.triangledown, location.top, color=color.red)
'''


def status_of(an):
    return {r["output"]: r["status"] for r in an["outputs"]}


class Analysis(unittest.TestCase):
    def test_rsi_period_change(self):
        an = impact.analyse(BASE, BASE.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)"))
        self.assertEqual(status_of(an), {"RSI": "may-change", "Upper": "stays-identical", "Lower": "stays-identical",
                                         "Overbought": "may-change"})
        why = {r["output"]: r["because"] for r in an["outputs"]}
        self.assertEqual(why["Overbought"], ["Overbought <- r (line 3 changed: r = ta.rsi(close, 14) -> r = ta.rsi(close, 21))"])
        self.assertEqual(why["Upper"], "constant 70: depends on no definition")
        sx = impact.expectation(an)
        self.assertEqual((sx["unchanged"], sx["may_change"], sx["change"]), (["styles", "objects"], ["signals", "values"], []))

    def test_transitive_chain_and_unrelated_output(self):
        old = BASE.replace("r = ta.rsi(close, 14)", "src = close\nr = ta.rsi(src, 14)\nm = ta.sma(close, 5)") + 'plot(m, "MA")\n'
        an = impact.analyse(old, old.replace("src = close", "src = hl2"))
        st = status_of(an)
        self.assertEqual((st["RSI"], st["Overbought"], st["MA"]), ("may-change", "may-change", "stays-identical"))
        self.assertIn("RSI <- r <- src", next(r for r in an["outputs"] if r["output"] == "RSI")["because"][0])

    def test_same_name_or_value_is_not_a_dependency(self):
        old = BASE + 'rsi_copy = ta.rsi(close, 14)\nplot(rsi_copy, "RSI copy")\n'
        an = impact.analyse(old, old.replace("r = ta.rsi(close, 14)", "r = ta.rsi(close, 21)"))
        self.assertEqual(status_of(an)["RSI copy"], "stays-identical")    # same formula, separate definition

    def test_uncertain_constructs(self):
        old = BASE.replace("r = ta.rsi(close, 14)", "r = f(close)\nf(x) => ta.rsi(x, 14)")
        an = impact.analyse(old, old.replace("ta.rsi(x, 14)", "ta.rsi(x, 21)"))
        st = status_of(an)
        self.assertEqual((st["RSI"], st["Upper"]), ("uncertain", "stays-identical"))
        old2 = BASE + "if close > open\n    r := r + 1\n"
        an2 = impact.analyse(old2, old2.replace("r + 1", "r + 2"))
        self.assertEqual(status_of(an2)["RSI"], "uncertain")
        an3 = impact.analyse(BASE + "plot(r)\n", BASE.replace("14", "21") + "plot(r)\n")
        self.assertIn("no literal title", [r["because"] for r in an3["outputs"] if r["output"] is None][0])

    def test_state_qualifier_is_a_change(self):
        old = '//@version=6\nindicator("T")\nfloat r = close\nplot(r, "R")\nhline(50, "Mid")\n'
        an = impact.analyse(old, old.replace("float r = close", "var float r = close"))
        self.assertEqual(status_of(an), {"R": "may-change", "Mid": "stays-identical"})
        self.assertEqual(an["outputs"][0]["because"], ["R <- r (line 3 changed: float r = close -> var float r = close)"])

    def test_style_variable_is_reported_apart_from_the_value(self):
        old = '//@version=6\nindicator("T")\ntone = color.red\nx = close\nplot(x, "X", color=tone)\n'
        an = impact.analyse(old, old.replace("tone = color.red", "tone = color.blue"))
        x = an["outputs"][0]
        self.assertEqual(x["status"], "stays-identical")                     # the plotted value
        self.assertEqual(x["style"], {"status": "may-change", "because": ["X.color <- tone (line 3 changed: tone = color.red -> tone = color.blue)"]})
        self.assertNotIn("styles", impact.expectation(an)["unchanged"])
        unsure = old.replace("tone = color.red", "tone = pick()\npick() => color.red")
        x2 = impact.analyse(unsure, unsure.replace("color.red", "color.blue"))["outputs"][0]
        self.assertEqual(x2["style"]["status"], "uncertain")

    def test_colour_only_is_a_style_change(self):
        an = impact.analyse(BASE, BASE.replace("color.purple", "color.orange"))
        rsi = next(r for r in an["outputs"] if r["output"] == "RSI")
        self.assertEqual((rsi["status"], rsi["style_change"]), ("stays-identical", {"color": ("color.purple", "color.orange")}))
        self.assertNotIn("styles", impact.expectation(an)["unchanged"])


def patch_series(d, key, values):
    """Change one numeric series of a fixture run consistently (payload, annex, hashes)."""
    rep = json.loads((d / "run.json").read_text()); g = json.loads((d / "graphics.json").read_text())
    rep["normalized"]["plots"][key] = [dict(p, v=values[i]) for i, p in enumerate(rep["normalized"]["plots"][key])]
    rep["normalized_payload_sha256"] = annex_reader.payload_sha256(rep["normalized"])
    for s in g["series"]:
        if s["key"] == key:
            s["points"] = [dict(p, v=values[i]) for i, p in enumerate(s["points"])]
    g["normalized_payload_sha256"] = rep["normalized_payload_sha256"]
    text = json.dumps(g, indent=1) + "\n"; (d / "graphics.json").write_text(text)
    rep["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (d / "run.json").write_text(json.dumps(rep, indent=1))


def add_series(d, key, values, kind="hline", n_points=None):
    """Add one series to a fixture run (payload, annex, hashes); `n_points` truncates it."""
    rep = json.loads((d / "run.json").read_text()); g = json.loads((d / "graphics.json").read_text())
    t0 = rep["normalized"]["plots"]["RSI"][0]["t"]; n = n_points if n_points is not None else len(values)
    pts = [{"t": t0 + i * 3600000, "v": values[i]} for i in range(n)]
    rep["normalized"]["plots"][key] = pts
    rep["normalized_payload_sha256"] = annex_reader.payload_sha256(rep["normalized"])
    g["series"].append({"key": key, "title": key, "callsite": "#9", "kind": kind, "options": {"color": "#00FF00"}, "points": pts})
    g["normalized_payload_sha256"] = rep["normalized_payload_sha256"]
    text = json.dumps(g, indent=1) + "\n"; (d / "graphics.json").write_text(text)
    rep["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (d / "run.json").write_text(json.dumps(rep, indent=1))


class PerOutputNext(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws impact "))
        self.root = self.tmp / "root"; (self.root / live.WORK / "x").mkdir(parents=True)
        self.src = self.root / live.WORK / "x" / "S.pine"
        self.sess = {"slug": "x", "work_source": str(self.src), "dataset": "d", "language": "fr", "token": "t1"}
        (self.root / live.SESSION).write_text(json.dumps(self.sess))
        self.plan, self.n, self.rewrite = {}, 0, {}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_run(self, root, slug, dataset, graphics, lang, source=None, origin=None):
        text = Path(source).read_text(); self.n += 1; rid = "pexec-%02d" % self.n
        vals, upper, lower = self.plan[text]
        d = make_run(self.tmp / "runs" / rid, rid, vals=vals, src=text, shape=[0.0] * 30)
        if upper:
            patch_series(d, "Upper", upper)
        if lower is not None:
            add_series(d, "Lower", [30] * 30, n_points=lower)
        if self.rewrite.get(text):
            rewrite_run(d, **self.rewrite[text])
        return {"ok": True, "run_id": rid, "run_dir": str(d), "execution_status": "PINETS_EXECUTION_PASS", "error": None,
                "source_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def compute(self, text, vals=None, upper=None, lower=30):
        """`lower`: number of points of the 'Lower' series in this run (None: absent)."""
        self.plan[text] = (vals, upper, lower); self.src.write_text(text)
        with mock.patch.object(local_test, "run", side_effect=self.fake_run), \
                mock.patch.object(local_test, "chart_component", return_value=True), \
                mock.patch.object(live, "write_work_frame", return_value=None), \
                mock.patch.object(qualify, "compare_runs", lambda root, a, b, runner=None: REAL_COMPARE(ROOT, a, b)):
            return live.compute(self.root, self.sess, "save")

    def declare(self, text):
        self.src.write_text(text)
        return live.expect(self.root, from_impact=True, note="RSI 14 -> 21")["expectation"]

    def test_period_change_signal_identical_on_tested_bars(self):
        src = BASE.replace("plotshape(r > 70", "plotshape(r > 70").replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        e = self.declare(new)                                             # bound to the saved revision, before its result
        self.assertEqual((e["revision_sha256"], e["result_already_finished"]), (live._sha(self.src), False))
        self.assertEqual(e["outputs"]["Sig"]["status"], "may-change"); self.assertEqual(e["outputs"]["Upper"]["status"], "stays-identical")
        self.compute(new, vals=[40.0 + i for i in range(30)])
        r = recommend.next_check(self.root); n = r["next_check"]
        self.assertEqual(n["kind"], "none")
        obs = {o["output"]: o for o in r["outputs_observed"]}
        self.assertEqual(obs["RSI"]["observed"], "changed, first divergence at bar 0")
        self.assertEqual(obs["Sig"]["note"], "depends on the change but stays identical on these bars (not an anomaly)")
        self.assertEqual(obs["Upper"]["observed"], "identical on the 30 tested bars (measured in both results)")
        self.assertEqual(obs["Lower"]["observed"], "identical on the 30 tested bars (measured in both results)")

    def test_output_predicted_identical_that_differs_is_read_at_its_bar(self):
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        upper = [70] * 30; upper[17] = 71
        self.compute(new, vals=[40.0 + i for i in range(30)], upper=upper)
        n = recommend.next_check(self.root)["next_check"]
        self.assertEqual((n["kind"], n["series"], n["bar"]), ("read-bar", "Upper", 17))
        self.assertIn("was predicted to stay identical (constant 70: depends on no definition)", n["reason"])
        self.assertEqual((n["at_bar"]["reference"]["chart_value"], n["at_bar"]["result"]["chart_value"]), (70, 71))

    def _lower_case(self, ref_lower, cur_lower):
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src, lower=ref_lower)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        self.compute(new, vals=[40.0 + i for i in range(30)], lower=cur_lower)
        return recommend.next_check(self.root)

    def test_output_absent_from_both_results_is_not_called_identical(self):
        r = self._lower_case(None, None); n = r["next_check"]
        self.assertEqual((n["kind"], n["outputs"]), ("incomplete-proof", ["Lower"]))
        self.assertIn("Lower absent from both results: the reference pexec-01 and the result pexec-02 have no series 'Lower' (report and annex)", n["reason"])
        obs = {o["output"]: o for o in r["outputs_observed"]}
        self.assertTrue(obs["Lower"]["observed"].startswith("not comparable: absent from both results"))
        self.assertEqual(obs["Upper"]["observed"], "identical on the 30 tested bars (measured in both results)")   # facts kept
        self.assertEqual(obs["RSI"]["observed"], "changed, first divergence at bar 0")
        self.assertNotIn("no further check", json.dumps(n))

    def test_output_absent_from_one_result(self):
        n = self._lower_case(30, None)["next_check"]
        self.assertEqual(n["kind"], "incomplete-proof")
        self.assertIn("Lower absent from the result pexec-02 (no series 'Lower' in its report or annex), present in the other run", n["reason"])

    def test_output_partially_covered(self):
        # through the normal path the reader contract already refuses an annex that does not cover the dataset
        # (OTHER_DATASET); the proof rule itself is checked here on inventories
        ref = {"bars": 30, "report": {"Lower": 30}, "annex": {"Lower": [30]}}
        cur = {"bars": 30, "report": {"Lower": 20}, "annex": {"Lower": [20]}}
        lim = recommend._proof("Lower", "values", ref, cur, "pexec-01", "pexec-02")
        self.assertEqual(lim["limit"], "partially covered: result pexec-02 covers 20 of its 30 bars (report)")
        self.assertIsNone(recommend._proof("Lower", "values", ref, dict(cur, report={"Lower": 30}, annex={"Lower": [30]}),
                                           "pexec-01", "pexec-02"))
        sig = recommend._proof("Sig", "signals", {"bars": 30, "report": {"Sig": 30}, "annex": {}}, {"bars": 30, "report": {"Sig": 30}, "annex": {"Sig": [30]}}, "a", "b")
        self.assertEqual(sig["kind"], "absent")                         # a signal is proven by its annex only

    def test_ambiguous_output(self):
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        rec = self.compute(new, vals=[40.0 + i for i in range(30)])
        add_series(Path(rec["run_dir"]), "Upper", [70] * 30)                 # a second series named Upper
        lt = live._read_json(live.work_dir(self.root, "x") / "latest.json")
        n = recommend.next_check(self.root)["next_check"]
        self.assertEqual(n["kind"], "incomplete-proof")
        self.assertIn("Upper ambiguous: result pexec-02 has 2 series named 'Upper' in its annex", n["reason"])

    def test_signal_needs_its_annex(self):
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        rec = self.compute(new, vals=[40.0 + i for i in range(30)])
        g = json.loads((Path(rec["run_dir"]) / "graphics.json").read_text())
        g["series"] = [x for x in g["series"] if x["key"] != "Sig"]
        (Path(rec["run_dir"]) / "graphics.json").write_text(json.dumps(g))   # altered: refused, never a proof
        self.assertEqual(recommend.next_check(self.root)["next_check"]["kind"], "unverifiable")

    def test_reference_bytes_must_be_the_recorded_revision(self):
        src = BASE.replace('"Overbought"', '"Sig"')
        rec = self.compute(src)
        snap = Path(rec["run_dir"]) / "S.pine"
        snap.write_text(src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)"))   # same recorded SHA, other bytes
        self.src.write_text(src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)"))
        r = live.impact_of_change(self.root)
        self.assertEqual((r["ok"], r["refused"]), (False, "reference-mismatch"))
        self.assertIn("does not match its recorded revision", r["reason"])
        with self.assertRaises(ValueError):
            live.expect(self.root, from_impact=True)
        exps = live._read_json(live.work_dir(self.root, "x") / live.EXPECT) or {}
        self.assertNotIn(live._sha(self.src), exps)                            # nothing recorded from that reference

    # ------------------------------------------------------------------ runs that are not comparable
    def _not_comparable_case(self, **rewrite):
        """D2 fixture, Lower present in both runs, 30 bars each; the result run rewritten (dataset,
        configuration, executor), each run staying valid on its own."""
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        self.rewrite[new] = rewrite
        upper = [70] * 30; upper[17] = 71                                  # a "divergence" that must never be stated
        self.compute(new, vals=[40.0 + i for i in range(30)], upper=upper if rewrite.get("close_delta") else None)
        for rid in ("pexec-01", "pexec-02"):
            self.assertTrue(local_test.check(self.root, self.tmp / "runs" / rid)["ok"], rid)
        return recommend.next_check(self.root)

    def assert_nothing_between_the_runs(self, r, short):
        n = r["next_check"]
        self.assertEqual((n["kind"], n["runs"]), ("not-comparable", {"reference": "pexec-01", "result": "pexec-02"}))
        self.assertNotIn("bar", n); self.assertNotIn("at_bar", n); self.assertNotIn("command", n)
        self.assertEqual([o["output"] for o in r["outputs_observed"]], ["Lower", "RSI", "Sig", "Upper"])
        for o in r["outputs_observed"]:                                      # the limit applies to EVERY output
            self.assertEqual(o["observed"], "not comparable: the runs are not comparable (%s): reference pexec-01, "
                                            "result pexec-02" % short, o["output"])
            self.assertNotIn("note", o)
        self.assertEqual(sorted(u["output"] for u in r["outputs_not_comparable"]), ["Lower", "RSI", "Sig", "Upper"])
        self.assertIsNone(r["facts"]); self.assertEqual(r["missing"], [n["reason"]])
        self.assertEqual(r["qualification"]["change"], "not-comparable"); self.assertNotIn("facets", r["qualification"])
        dump = json.dumps(r)
        for claim in ("identical on", "first divergence at", "measured in both", "first established", "changed, "):
            self.assertNotIn(claim, dump)

    def test_other_dataset_global_verdict_and_every_output_row(self):
        r = self._not_comparable_case(days=365)
        n = r["next_check"]
        self.assertEqual(n["reasons"], ["dataset_sha256"])
        self.assertEqual(n["reason"], "the reference pexec-01 and the result pexec-02 are not comparable: the two runs used "
                                      "different datasets (same 30 bars and prices, every timestamp shifted by +365 days); no "
                                      "equality, difference or first divergence between them can be established, for any output")
        self.assert_nothing_between_the_runs(r, "different datasets")
        ref, cur = n["per_run"]["reference"], n["per_run"]["result"]          # facts verified separately for each run
        self.assertEqual((ref["dataset"]["bars"], ref["dataset"]["first_time"]), (30, "2020-01-01T00:00:00Z"))
        self.assertEqual((cur["dataset"]["bars"], cur["dataset"]["first_time"]), (30, "2020-12-31T00:00:00Z"))
        self.assertTrue(ref["dataset"]["matches_report"] and cur["dataset"]["matches_report"])
        self.assertEqual(r["outputs_observed"][0]["per_run"], {"reference": {"report_points": 30, "annex_points": 30},
                                                                "result": {"report_points": 30, "annex_points": 30}})

    def test_same_timestamps_other_prices_never_designate_a_bar(self):
        r = self._not_comparable_case(close_delta={5: 100})
        self.assertIn("same timestamps, prices differ from bar 5", r["next_check"]["reason"])
        self.assert_nothing_between_the_runs(r, "different datasets")

    def test_other_configuration_or_executor(self):
        r = self._not_comparable_case(configuration={"inputs": {"len": 21}})
        self.assertEqual(r["next_check"]["reasons"], ["configuration"])
        self.assertIn("the run configuration differs (inputs)", r["next_check"]["reason"])
        self.assert_nothing_between_the_runs(r, "different run configurations")

    def test_other_executor(self):
        r = self._not_comparable_case(fingerprint="c" * 64)
        self.assertEqual(r["next_check"]["reasons"], ["executor_fingerprint"])
        self.assertIn("(reference bbbbbbbbbbbb, result cccccccccccc)", r["next_check"]["reason"])
        self.assert_nothing_between_the_runs(r, "different executors")

    def test_stale_qualification_claiming_comparable_runs_is_not_trusted(self):
        self._not_comparable_case(days=365)
        f = live.work_dir(self.root, "x") / "latest.json"; lt = live._read_json(f)
        q = lt["qualification"]
        q.pop("comparability", None)                                         # as written by an earlier version
        q.update(compare_runs={"comparable": True, "status": "PINETS_REGRESSION_UNCHANGED", "changed": []}, change="unchanged",
                 annex="compared (reader contract v1 passed on both)", uncertain=[],
                 divergences=[], facets={"values": [], "signals": [], "objects": [], "styles": []})
        live._write_json(f, lt)
        r = recommend.next_check(self.root)
        self.assertEqual(r["next_check"]["reasons"], ["dataset_sha256"])
        self.assert_nothing_between_the_runs(r, "different datasets")

    def test_not_comparable_comes_first_and_keeps_the_annex_state(self):
        self._not_comparable_case(days=365)
        (self.tmp / "runs" / "pexec-02" / "graphics.json").unlink()
        r = recommend.next_check(self.root)
        self.assertEqual(r["next_check"]["kind"], "not-comparable")
        self.assertEqual(r["next_check"]["per_run"]["result"]["annex"]["code"], "MISSING")
        self.assertEqual(r["outputs_observed"][0]["per_run"]["result"]["annex_points"], "annex not usable (MISSING)")

    def test_wrong_shapes_never_crash_the_not_comparable_answer(self):
        """Run files of the wrong JSON shape or field types: an answer, never an exception."""
        self._not_comparable_case(days=365)
        d = self.tmp / "runs" / "pexec-02"
        rep = json.loads((d / "run.json").read_text())
        for name, mutate in (("graphics-list", lambda: (d / "graphics.json").write_text("[]")),
                             ("series-not-list", lambda: (d / "graphics.json").write_text(json.dumps({"series": {"a": 1}}))),
                             ("dataset-list", lambda: (d / "dataset.json").write_text("[1, 2]")),
                             ("report-list", lambda: (d / "run.json").write_text("[]")),
                             ("fingerprint-int", lambda: (d / "run.json").write_text(json.dumps(dict(rep, executor_fingerprint=7)))),
                             ("plots-list", lambda: (d / "run.json").write_text(json.dumps(dict(rep, normalized={"plots": [1]})))),
                             ("nan", lambda: (d / "run.json").write_text(json.dumps(rep).replace('"configuration": {}', '"configuration": {"x": NaN}')))):
            mutate()
            r = recommend.next_check(self.root)
            self.assertEqual(r["next_check"]["kind"], "not-comparable", name)
            self.assertIn("pexec-02", r["next_check"]["reason"], name)
        (d / "run.json").write_text("[]")
        r = recommend.next_check(self.root)
        self.assertIn("the report of the result pexec-02 is missing or unreadable (run.json)", r["next_check"]["reason"])
        self.assertEqual(r["next_check"]["what_would_compare"], "usable reports for both runs (run.json)")

    def test_no_capability_conclusion_between_runs_that_are_not_comparable(self):
        r = self._not_comparable_case(days=365)
        self.assertEqual(r["qualification"]["gating_note"], "the runs are not comparable: no conclusion between them, blocking or not")
        self.assertNotIn("conclusion is possible", json.dumps(r))

    def test_inspect_compare_says_whether_the_runs_are_comparable(self):
        self._not_comparable_case(days=365)
        ins = live.inspect(self.root, self.tmp / "runs" / "pexec-02", bar=5, compare=self.tmp / "runs" / "pexec-01")
        c = ins["compare"]
        self.assertFalse(c["same_dataset"]); self.assertFalse(c["comparable"]["comparable"])
        self.assertIn("not comparable", c["note"])
        self.assertIn("values", c); self.assertIn("chart_values", c)        # each run's own values stay readable
        same = live.inspect(self.root, self.tmp / "runs" / "pexec-01", bar=5, compare=self.tmp / "runs" / "pexec-01")
        self.assertTrue(same["compare"]["comparable"]["comparable"]); self.assertNotIn("note", same["compare"])

    def test_unusable_annex_still_unverifiable(self):
        src = BASE.replace('"Overbought"', '"Sig"')
        self.compute(src)
        new = src.replace("ta.rsi(close, 14)", "ta.rsi(close, 21)")
        self.declare(new)
        rec = self.compute(new, vals=[40.0 + i for i in range(30)])
        (Path(rec["run_dir"]) / "graphics.json").unlink()
        self.assertEqual(recommend.next_check(self.root)["next_check"]["kind"], "unverifiable")


if __name__ == "__main__":
    unittest.main()
