# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL development loop (tools/pws_workspace/live.py): browser frames built only after the
reader contract v1 checks (refusals keep the numeric result, no computation), grouping of close
saves into ONE computation of the last revision, last successful chart kept after a failure,
dataset labels. No engine call: runs are fixtures; `compute` is replaced where the follow-up is tested."""
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import live, local_test
from tools.tests.test_local_test_inspect import _artifacts

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures" / "visual" / "f4-objects"


def _frame(path):
    s = Path(path).read_text(encoding="utf-8")
    assert s.startswith("PWS_FRAME(") and s.rstrip().endswith(");")
    return json.loads(s[len("PWS_FRAME("):s.rstrip().rindex(");")])


class Frames(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws live "))
        self.run = self.tmp / "run A"; shutil.copytree(FIX, self.run)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_model_comes_from_the_checked_run(self):
        m, refusal = live.frame_model(ROOT, self.run)
        self.assertIsNone(refusal)
        rep = json.loads((self.run / "run.json").read_text())
        self.assertEqual((m["run_id"], m["source_sha256"], m["dataset_sha256"]),
                         (rep["run_id"], rep["source_sha256"], rep["dataset_sha256"]))
        self.assertEqual(len(m["times"]), len(m["bars"]))
        self.assertEqual(m["annex_version"], "v0.2-exp")
        self.assertIn("lines × 2", m["not_shown"])                 # drawings are listed, not drawn

    def _refused(self, mutate, code):
        mutate(self.run)
        before = (self.run / "run.json").read_bytes()
        with mock.patch.object(local_test.subprocess, "run") as engine, \
                mock.patch.object(live, "vela_state", return_value="ready"):
            m, refusal = live.frame_model(ROOT, self.run)
            out = live.open_view(ROOT, run_dir=self.run, lang="fr", browser=False)
            engine.assert_not_called()                              # no computation for a refusal
        self.assertIsNone(m); self.assertEqual(refusal["code"], code)
        self.assertEqual(out["engine_invocations"], 0)
        f = _frame(Path(out["page"]).parent / "frame.js")
        self.assertEqual((f["mode"], f["state"], f["chart"]), ("pinned", "refused", None))
        self.assertIn(code, f["message"]); self.assertIn("résultat numérique", f["message"])
        self.assertEqual((self.run / "run.json").read_bytes(), before)   # numeric result untouched
        shutil.rmtree(Path(out["page"]).parent, ignore_errors=True)

    def test_missing_annex_is_refused(self):
        self._refused(lambda d: (d / "graphics.json").unlink(), "MISSING")

    def test_altered_annex_is_refused(self):
        def alter(d):
            g = json.loads((d / "graphics.json").read_text()); g["declaration"]["title"] = "X"
            (d / "graphics.json").write_text(json.dumps(g))
        self._refused(alter, "ALTERED")

    def test_foreign_annex_is_refused(self):
        a, b = self.tmp / "a", self.tmp / "b"; a.mkdir(); b.mkdir()
        _artifacts(a, run_id="pexec-test-a"); _artifacts(b, run_id="pexec-test-b")
        self.run = a
        self._refused(lambda d: shutil.copyfile(b / "graphics.json", d / "graphics.json"), "OTHER_RUN")

    def test_browser_chart_absent_or_without_dependencies_is_explained(self):
        rep = (self.run / "run.json").read_bytes()
        for state, code, words in (("absent", "VELA_ABSENT", "vela-view"), ("no-deps", "VELA_NO_DEPS", "npm ci")):
            with mock.patch.object(live, "vela_state", return_value=state), \
                    mock.patch.object(local_test.subprocess, "run") as engine, \
                    mock.patch.object(live.subprocess, "run") as opener:
                for lang in ("fr", "en"):
                    out = live.open_view(ROOT, run_dir=self.run, lang=lang)
                    self.assertEqual((out["ok"], out["refusal_code"], out["engine_invocations"]), (False, code, 0))
                    self.assertIn(words, out["message"])
                    self.assertIn("numérique" if lang == "fr" else "numeric", out["message"])
                engine.assert_not_called(); opener.assert_not_called()        # no computation, no browser
            self.assertEqual((self.run / "run.json").read_bytes(), rep)

    def test_plan_offers_only_the_actions_of_this_installation(self):
        prod = {"source": str(self.run / "f4-objects.pine"), "script_kind": "indicator"}
        with mock.patch.object(local_test, "_product", return_value=prod):
            for state, browser in (("ready", True), ("no-deps", False), ("absent", False)):
                with mock.patch.object(live, "vela_state", return_value=state):
                    a = local_test.plan(ROOT, "x", "fr")["actions"]
                self.assertEqual((a["numeric"], a["follow"], a["chart"], a["chart_state"]),
                                 (True, True, browser, state))
                self.assertFalse([k for k in a if "iterm" in k or "terminal" in k])     # Vela is the only viewer

    def test_export_button_is_localized_and_uses_the_native_screenshot(self):
        js = (ROOT / live.PAGE_JS).read_text(encoding="utf-8")
        self.assertIn("state.chart.renderer.screenshot()", js)                # Vela's own raster, no computation
        self.assertIn("'pws-' + state.runId + '.png'", js)                    # run shown at the moment of the click
        self.assertIn("export_none", js)                                       # explanation when Vela gives no image
        for lang, label in (("fr", "Exporter en PNG"), ("en", "Export as PNG")):
            with mock.patch.object(live, "vela_state", return_value="ready"):
                out = live.open_view(ROOT, run_dir=self.run, lang=lang, browser=False)
            html = Path(out["page"]).read_text(encoding="utf-8")
            self.assertIn('<button id="export" type="button">', html)
            cfg = json.loads(html.split("window.PWS_VIEW = ", 1)[1].split(";</script>", 1)[0])
            self.assertEqual(cfg["texts"]["export"], label)
            self.assertIn("{name}", cfg["texts"]["export_done"])
            self.assertTrue(cfg["texts"]["export_none"])
            self.assertEqual(out["engine_invocations"], 0)
            shutil.rmtree(Path(out["page"]).parent, ignore_errors=True)

    def test_dataset_labels(self):
        d = {"type": "synthetic", "generator": "lcg-ohlcv-v1"}
        self.assertEqual(local_test.dataset_label(d, 500, "lcg-7-500", "fr"), "Données de démonstration — 500 bougies simulées")
        self.assertEqual(local_test.dataset_label(d, 500, "lcg-7-500", "en"), "Demo data — 500 simulated candles")
        self.assertEqual(local_test.dataset_label({"type": "imported"}, 8, "imported-sample", "fr"), "imported-sample (8)")


class WorkFollowUp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws work "))
        self.root = self.tmp / "root"; (self.root / live.WORK / "x").mkdir(parents=True)
        self.src = self.root / live.WORK / "x" / "S.pine"; self.src.write_text("v0\n")
        self.sess = {"slug": "x", "work_source": str(self.src), "dataset": "d", "language": "fr", "token": "t1"}
        (self.root / live.SESSION).write_text(json.dumps(self.sess))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_close_saves_give_one_computation_of_the_last_revision(self):
        calls = []

        def fake_compute(root, sess, reason):
            rev = live._sha(sess["work_source"]); calls.append((rev, Path(sess["work_source"]).read_text()))
            live._write_json(live.work_dir(root, "x") / "latest.json", {"revision_sha256": rev, "state": "ok"})
        live._write_json(live.work_dir(self.root, "x") / "latest.json", {"revision_sha256": live._sha(self.src), "state": "ok"})
        with mock.patch.object(live, "compute", side_effect=fake_compute):
            th = threading.Thread(target=live.watch, args=(self.root,), kwargs={"quiet": 0.5, "poll": 0.05})
            th.start(); time.sleep(0.3)
            for v in ("v1\n", "v2\n", "v3\n"):                      # three saves 0.1 s apart
                self.src.write_text(v); time.sleep(0.1)
            time.sleep(1.5)
            self.assertEqual([c[1] for c in calls], ["v3\n"])       # ONE computation, last revision
            self.src.write_text("v4\n"); time.sleep(1.5)
            self.assertEqual([c[1] for c in calls], ["v3\n", "v4\n"])
            (self.root / live.SESSION).write_text(json.dumps(dict(self.sess, token="t2")))   # session changes: follow-up ends
            th.join(timeout=5)
        self.assertFalse(th.is_alive())

    def test_failed_computation_keeps_the_last_good_chart_identified(self):
        good = self.tmp / "good"; shutil.copytree(FIX, good)
        live._write_json(live.work_dir(self.root, "x") / "latest.json", {
            "seq": 3, "state": "failed", "revision_sha256": "f" * 64, "run_id": "pexec-failed",
            "error": {"message": "Failed to transpile"},
            "last_good": {"run_id": "pexec-812929e2-69e1-4a97-9033-bc7924c79f50", "run_dir": str(good),
                          "revision_sha256": "a" * 64}})
        # the renderer and reader come from the real workspace (ROOT); session files and the page stay in tmp
        with mock.patch.object(live, "work_dir", lambda root, slug: self.root / live.WORK / slug), \
                mock.patch.object(live, "view_dir", lambda root, name: self.tmp / "views" / name):
            f = live.write_work_frame(ROOT, self.sess)
        self.assertEqual(f["state"], "failed")
        self.assertTrue(f["chart_is_last_good"])
        self.assertEqual(f["chart"]["run_id"], "pexec-812929e2-69e1-4a97-9033-bc7924c79f50")
        self.assertIn("Failed to transpile", f["message"])
        self.assertIn("dernier calcul réussi", f["message"]); self.assertIn("pexec-812929e2", f["message"])
        self.assertEqual(_frame(self.tmp / "views" / "work-x" / "frame.js")["seq"], 3)


if __name__ == "__main__":
    unittest.main()
