# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL next useful check (tools/pws_workspace/recommend.py): advisory recommendation bound to
the revision of its result, built from the session's qualification and the expectation declared by
pine-develop; zero engine call (no subprocess at all while recommending); the signal bar is the
first divergence established in the checked annexes (booleans of signal plots are dropped by the
normalized payload). Runs are fixtures; the qualification uses the runner's compare (no PineTS)."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import annex_reader, live, local_test, qualify, recommend
from tools.tests.test_adaptive_loop import make_run, rewrite_run

ROOT = Path(__file__).resolve().parents[2]
REAL_COMPARE = qualify.compare_runs
PHASE_C_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "next_check" / "phase-c-latest-final.json"
PHASE_C_EVIDENCE = ROOT / "docs" / "maintenance" / "2026-11-23-adaptive-validation" / "evidence" / "phase-c" / "latest-final.json"
PHASE_C_PREFIX = "~/Documents/Codex/pws-visual-engine-env/pws-isolated/.claude/runtime/worktrees/adaptive-validation/"


def signal_run(d, run_id, sig, color="#9C27B0", src="x\n"):
    """make_run + a boolean signal series 'Sig' (shape): booleans in the annex, null in the payload,
    as the real runner writes them."""
    d = make_run(d, run_id, color=color, src=src, shape=[0.0] * 30)
    rep = json.loads((d / "run.json").read_text()); g = json.loads((d / "graphics.json").read_text())
    rep["normalized"]["plots"]["Sig"] = [dict(p, v=None) for p in rep["normalized"]["plots"]["Sig"]]
    rep["normalized_payload_sha256"] = annex_reader.payload_sha256(rep["normalized"])
    for s in g["series"]:
        if s["key"] == "Sig":
            s["points"] = [dict(p, v=bool(sig[i])) for i, p in enumerate(s["points"])]
    g["normalized_payload_sha256"] = rep["normalized_payload_sha256"]
    text = json.dumps(g, indent=1) + "\n"; (d / "graphics.json").write_text(text)
    rep["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (d / "run.json").write_text(json.dumps(rep, indent=1))
    return d


class _Session(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws next "))
        self.root = self.tmp / "root"; (self.root / live.WORK / "x").mkdir(parents=True)
        self.src = self.root / live.WORK / "x" / "S.pine"
        self.sess = {"slug": "x", "work_source": str(self.src), "dataset": "d", "language": "fr", "token": "t1"}
        (self.root / live.SESSION).write_text(json.dumps(self.sess))
        self.plan = {}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_run(self, root, slug, dataset, graphics, lang, source=None, origin=None):
        text = Path(source).read_text(); rid = "pexec-%02d" % (len(list((self.tmp / "runs").glob("*"))) + 1 if (self.tmp / "runs").exists() else 1)
        sig, color = self.plan[text]
        d = signal_run(self.tmp / "runs" / rid, rid, sig, color=color, src=text)
        return {"ok": True, "run_id": rid, "run_dir": str(d), "execution_status": "PINETS_EXECUTION_PASS", "error": None,
                "source_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def compute(self, text, sig, color):
        self.plan[text] = (sig, color); self.src.write_text(text)
        with mock.patch.object(local_test, "run", side_effect=self.fake_run), \
                mock.patch.object(local_test, "chart_component", return_value=True), \
                mock.patch.object(live, "write_work_frame", return_value=None), \
                mock.patch.object(qualify, "compare_runs", lambda root, a, b, runner=None: REAL_COMPARE(ROOT, a, b)):
            return live.compute(self.root, self.sess, "save")

    def next(self):
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("no program may run while recommending")), \
                mock.patch.object(subprocess, "Popen", side_effect=AssertionError("no program may run while recommending")):
            return recommend.next_check(self.root)


class NextCheck(_Session):
    def test_colour_only_as_expected_needs_no_further_check(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        self.compute("v2\n", [0] * 30, "#FF9800")
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"], note="colour only")
        r = self.next()
        self.assertTrue(r["applies_to_requested"]); self.assertEqual(r["next_check"]["kind"], "none")
        self.assertIn("series RSI options color", r["next_check"]["reason"])
        self.assertEqual(r["engine_invocations"], 0); self.assertTrue(r["not_covered"])

    def test_signal_differs_although_only_styles_were_expected(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        sig = [0] * 30; sig[12] = 1
        self.compute("v2\n", sig, "#FF9800")
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"], note="aesthetic")
        r = self.next(); n = r["next_check"]
        self.assertEqual((n["kind"], n["series"], n["bar"]), ("read-bar", "Sig", 12))
        self.assertEqual((n["at_bar"]["reference"]["chart_value"], n["at_bar"]["result"]["chart_value"]), (False, True))
        self.assertEqual((n["at_bar"]["reference"]["report_value"], n["at_bar"]["result"]["report_value"]), (None, None))
        self.assertEqual(n["runs"], {"reference": "pexec-01", "result": "pexec-02"})
        self.assertIn("--bar 12 --compare-run-id pexec-01", n["command"])
        # Claude Code can re-read that bar: both runs, chart values including the booleans
        ins = live.inspect(self.root, self.tmp / "runs" / "pexec-02", bar=12, compare=self.tmp / "runs" / "pexec-01")
        self.assertEqual(ins["compare"]["chart_values"]["Sig"], {"this": True, "other": False})
        self.assertEqual(ins["values"]["Sig"], None)                    # the payload keeps numbers only

    def test_stale_result_keeps_its_recommendation_on_its_own_revision(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        self.compute("v2\n", [0] * 30, "#FF9800")
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"])
        old = live._sha(self.src)
        self.src.write_text("v3 saved, not computed\n")
        r = self.next()
        self.assertFalse(r["applies_to_requested"]); self.assertEqual(r["next_check"]["kind"], "wait")
        self.assertIn("not to the requested revision", r["missing"][0])
        self.assertEqual(r["earlier_revision_recommendation"]["for_revision"], old)
        self.assertEqual(r["earlier_revision_recommendation"]["next_check"]["kind"], "none")

    def test_first_result_has_no_comparable_reference(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        r = self.next()
        self.assertEqual(r["next_check"]["kind"], "none-possible"); self.assertIn("no comparable reference", r["missing"][0])

    def test_without_expectation_it_asks_for_it(self):
        self.compute("v1\n", [0] * 30, "#9C27B0"); self.compute("v2\n", [0] * 30, "#FF9800")
        r = self.next()
        self.assertEqual(r["next_check"]["kind"], "declare-expectation")
        self.assertIn("no expectation declared for revision %s" % live._sha(self.src)[:12], r["missing"][0])

    def test_undeterminable_bar_is_said(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        sig = [0] * 30; sig[12] = 1
        rec = self.compute("v2\n", sig, "#FF9800")
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"])
        lt = live._read_json(live.work_dir(self.root, "x") / "latest.json")
        lt["qualification"]["divergences"][0]["time_result"] += 1            # the bar no longer matches one dataset bar
        live._write_json(live.work_dir(self.root, "x") / "latest.json", lt)
        r = self.next()
        self.assertIn("bar impossible to determine", r["missing"][-1]); self.assertEqual(r["next_check"]["kind"], "review-signals")


class UnusableAnnex(_Session):
    """An annex missing or refused NOW: the recommendation says which run, its role and the exact
    reason, keeps the numeric facts of the reports apart, names signals only from a valid annex and
    never designates a bar — even though the earlier qualification (with a bar) is still stored."""
    def setUp(self):
        super().setUp()
        self.compute("v1\n", [0] * 30, "#9C27B0")
        sig = [0] * 30; sig[12] = 1
        self.compute("v2\n", sig, "#FF9800")
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"], note="aesthetic")
        lt = live._read_json(live.work_dir(self.root, "x") / "latest.json")
        self.assertEqual(lt["qualification"]["divergences"][0]["first_index"], 12)       # earlier observation present
        self.ref, self.cur = self.tmp / "runs" / "pexec-01", self.tmp / "runs" / "pexec-02"

    def check_unverifiable(self, r, role, run_id, code):
        n = r["next_check"]
        self.assertEqual(n["kind"], "unverifiable"); self.assertNotIn("bar", n); self.assertNotIn("at_bar", n)
        self.assertIn({"role": role, "run_id": run_id, "code": code}, [{k: u[k] for k in ("role", "run_id", "code")}
                                                                      for u in n["unavailable_annexes"]])
        self.assertEqual(n["numeric_facts"]["status"], "PINETS_REGRESSION_UNCHANGED")
        self.assertIsNone(r["facts"])                                      # nothing inferred from uncomparable facets
        self.assertNotIn("not observed", json.dumps(r))
        return n

    def test_result_annex_missing(self):
        (self.cur / "graphics.json").unlink()
        n = self.check_unverifiable(self.next(), "result", "pexec-02", "MISSING")
        self.assertEqual(n["not_comparable"]["signals"], ["Sig"]); self.assertEqual(n["names_from"], ["pexec-01"])
        self.assertEqual(n["summary"], "Cannot compare the signal Sig and the expected style change. The annex of the "
                         "result pexec-02 is missing [MISSING: graphics annex missing (graphics.json)]. The numeric "
                         "comparison of the two reports shows identical values.")

    def test_reference_annex_missing(self):
        (self.ref / "graphics.json").unlink()
        n = self.check_unverifiable(self.next(), "reference", "pexec-01", "MISSING")
        self.assertEqual(n["names_from"], ["pexec-02"]); self.assertIn("the reference pexec-01 is missing", n["summary"])

    def test_refused_annex_names_nothing(self):
        g = json.loads((self.cur / "graphics.json").read_text())
        g["series"].append({"key": "Ghost", "title": "Ghost", "callsite": "#9", "kind": "shape", "options": {}, "points": []})
        (self.cur / "graphics.json").write_text(json.dumps(g))          # no longer the annex recorded by the report
        n = self.check_unverifiable(self.next(), "result", "pexec-02", "ALTERED")
        self.assertEqual(n["not_comparable"]["signals"], ["Sig"]); self.assertNotIn("Ghost", json.dumps(n))
        self.assertIn("is refused [ALTERED", n["summary"])

    def test_both_annexes_unavailable(self):
        (self.cur / "graphics.json").unlink(); (self.ref / "graphics.json").unlink()
        n = self.check_unverifiable(self.next(), "result", "pexec-02", "MISSING")
        self.assertEqual(n["not_comparable"]["signals"], "unknown (no usable annex)"); self.assertEqual(n["names_from"], [])
        self.assertIn("the reference pexec-01 is missing", n["summary"]); self.assertIn("the result pexec-02 is missing", n["summary"])
        self.assertIn("no usable annex to name them", n["summary"])

    def test_both_valid_still_designate_the_bar(self):
        n = self.next()["next_check"]
        self.assertEqual((n["kind"], n["bar"]), ("read-bar", 12))


class FacetPathNotComparable(_Session):
    """D1 (expectation by facets, no per-output prediction): runs on different datasets never give a
    bar, a 'values/signals differ' review or an expected-change verdict between them."""
    def test_signal_on_other_dataset_is_not_read_at_a_bar(self):
        self.compute("v1\n", [0] * 30, "#9C27B0")
        sig = [0] * 30; sig[12] = 1
        self.compute("v2\n", sig, "#FF9800")
        rewrite_run(self.tmp / "runs" / "pexec-02", days=365)               # result on another dataset (still valid)
        lt = live._read_json(live.work_dir(self.root, "x") / "latest.json")
        lt["qualification"] = qualify.qualify(ROOT, self.tmp / "runs" / "pexec-02", self.tmp / "runs" / "pexec-01")
        live._write_json(live.work_dir(self.root, "x") / "latest.json", lt)
        live.expect(self.root, change=["styles"], unchanged=["values", "signals", "objects"], note="aesthetic")
        r = self.next(); n = r["next_check"]
        self.assertEqual((n["kind"], n["reasons"]), ("not-comparable", ["dataset_sha256"]))
        self.assertIn("the reference pexec-01 and the result pexec-02 are not comparable", n["reason"])
        self.assertNotIn("bar", n); self.assertIsNone(r["facts"]); self.assertNotIn("outputs_observed", r)
        self.assertEqual(n["per_run"]["result"]["series"]["Sig"], {"report_points": 30, "annex_points": 30})


class PhaseCEvidence(unittest.TestCase):
    def test_kept_phase_c_qualification_comment_only_needs_no_further_check(self):
        lt = json.loads(PHASE_C_FIXTURE.read_text())                    # self-contained: shipped with the tests
        st = {"result": lt["result"]}
        out = recommend._for_result(st, lt, {"change": [], "unchanged": ["values", "signals", "objects", "styles"]})
        self.assertEqual(out["next_check"]["kind"], "none")
        self.assertEqual(out["reference"]["run_id"], lt["qualification"]["compared_with"]["run_id"])


    @unittest.skipUnless(PHASE_C_EVIDENCE.is_file(), "private phase C evidence not shipped (development repository only)")
    def test_fixture_is_faithful_to_the_kept_evidence(self):
        raw = PHASE_C_EVIDENCE.read_text()
        self.assertEqual(PHASE_C_FIXTURE.read_text(), raw.replace(PHASE_C_PREFIX, "<phase-c-workspace>/"))

if __name__ == "__main__":
    unittest.main()
