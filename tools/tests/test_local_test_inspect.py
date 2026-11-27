# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL "inspect the result" path (isolated study copy): localized plan screen
(chart option OFF by default), "Open the chart" (browser, Vela) and the reader contract v1
refusals (tools/pws_workspace/annex_reader.py). No engine call: the run artifacts are built
here, consistent by construction."""
import copy
import hashlib
import json
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from tools.pws_workspace import annex_reader as render      # the reader: part of the core, no display
from tools.pws_workspace import live, local_test

ROOT = Path(__file__).resolve().parents[2]


def _artifacts(dirpath, run_id="pexec-test-0001", n=30):
    """Write run.json, graphics.json and dataset.json of one fake execution into dirpath."""
    t0 = 1577836800000
    ds = {"schema": "pws-dataset-v1", "descriptor": {"price_scale": 100},
          "bars": [{"t": t0 + i * 3600000, "o": 10000 + i, "h": 10050 + i, "l": 9950 + i, "c": 10010 + i, "v": 1}
                   for i in range(n)]}
    (dirpath / "dataset.json").write_text(json.dumps(ds), encoding="utf-8")
    dsha = hashlib.sha256((dirpath / "dataset.json").read_bytes()).hexdigest()
    vals = [50.0 + i * 0.5 for i in range(n)]
    normalized = {"schema": "pws-pinets-norm-v2", "alerts": [], "warnings": [], "internal_keys_present": [],
                  "plots": {"RSI": [{"t": t0 + i * 3600000, "v": vals[i]} for i in range(n)],
                            "Upper": [{"t": t0 + i * 3600000, "v": 70} for i in range(n)]}}
    ident = {"run_id": run_id, "source_sha256": "a" * 64, "dataset_sha256": dsha, "pinets_version": "0.10.0",
             "executor_fingerprint": "b" * 64, "normalization_schema": "pws-pinets-norm-v2",
             "normalized_payload_sha256": render.payload_sha256(normalized)}
    annex = dict(ident, schema=local_test.GRAPHICS_SCHEMA, declaration={"title": "T", "overlay": False},
                 series=[{"key": "RSI", "title": "RSI", "callsite": "#0", "kind": "line", "options": {"color": "#9C27B0"},
                          "points": [{"t": t0 + i * 3600000, "v": vals[i]} for i in range(n)]},
                         {"key": "Upper", "title": "Upper", "callsite": "#1", "kind": "hline", "options": {"color": "#F23645"},
                          "points": [{"t": t0 + i * 3600000, "v": 70} for i in range(n)]}],
                 drawings={}, drawings_scope="final-state", limits=[])
    text = json.dumps(annex, indent=1) + "\n"
    (dirpath / "graphics.json").write_text(text, encoding="utf-8")
    report = dict(ident, schema="pws-pinets-run-v1", execution_status="PINETS_EXECUTION_PASS", normalized=normalized,
                  source=str(dirpath / "T.pine"), graphics_annex={"schema": local_test.GRAPHICS_SCHEMA,
                  "sha256": hashlib.sha256(text.encode()).hexdigest(), "status": "GRAPHICS_WRITTEN", "error": None})
    (dirpath / "run.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


class InspectPath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws inspect "))           # path with a space
        self.run = self.tmp / "run A"; self.run.mkdir(); _artifacts(self.run)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_texts_localized_and_complete(self):
        for key, entry in local_test._T.items():
            self.assertTrue(entry.get("fr") and entry.get("en"), key)
        self.assertEqual(local_test._t("lt.graphics", "fr"), "Préparer le graphique")
        self.assertEqual(local_test._t("lt.open", "fr"), "Ouvrir le graphique")
        self.assertEqual(local_test._t("lt.open", "en"), "Open the chart")
        self.assertNotIn("iTerm", json.dumps(local_test._T, ensure_ascii=False))
        self.assertIn("Objets à l'état final", local_test._t("lt.final", "fr"))
        self.assertEqual(local_test._t("lt.graphics", "en"), "Prepare the chart")

    def test_without_chart_component_only_the_numeric_test_is_offered(self):
        with mock.patch.object(local_test, "chart_component", return_value=False), \
                mock.patch.object(local_test, "_product", return_value={"source": str(Path(__file__)),
                                                                         "script_kind": "indicator"}):
            for lang in ("fr", "en"):
                pl = local_test.plan(ROOT, "x", lang)
                self.assertEqual([o["value"] for o in pl["graphics_screen"]["options"]], ["numeric", "back"])
                self.assertFalse(pl["chart_component"])
                self.assertIn(local_test._t("lt.no_chart", lang), pl["notes"])
                self.assertNotIn("--graphics", pl["run_command"])
            with mock.patch.object(local_test.subprocess, "run") as engine:
                with self.assertRaises(ValueError):
                    local_test.run(ROOT, "x", __file__, True, "fr")
                engine.assert_not_called()                       # refused before any engine call

    def test_preflight_accepts_consistent_run(self):
        self.assertEqual(local_test.preflight(ROOT, self.run), (True, None))
        with mock.patch.object(live, "vela_state", return_value="ready"):
            out = local_test.reopen(ROOT, self.run, "fr")
        self.assertTrue(out["ok"]); self.assertEqual(out["engine_invocations"], 0)
        self.assertEqual(out["open"]["label"], "Ouvrir le graphique")         # the browser chart, Vela
        self.assertEqual(shlex.split(out["open"]["command"]),
                         ["python3", "-m", "tools.pws_workspace", "local-test", "view", "--run-id", "pexec-test-0001"])
        for state in ("absent", "no-deps"):                                    # no Vela: the reason, no command
            with mock.patch.object(live, "vela_state", return_value=state):
                out = local_test.reopen(ROOT, self.run, "fr")
            self.assertNotIn("open", out); self.assertIn("Vela", out["open_refused"])

    def _refused(self, mutate):
        d = self.tmp / "copy"; shutil.copytree(self.run, d); mutate(d)
        before = (d / "run.json").read_bytes() if (d / "run.json").exists() else None
        ok, reason = local_test.preflight(ROOT, d)
        out = local_test.reopen(ROOT, d, "fr")
        after = (d / "run.json").read_bytes() if (d / "run.json").exists() else None
        self.assertFalse(ok); self.assertFalse(out["ok"]); self.assertNotIn("open", out)
        self.assertEqual(before, after, "the report is never modified by a refusal")
        return reason

    def test_refuse_missing_annex(self):
        reason = self._refused(lambda d: (d / "graphics.json").unlink())
        self.assertIn("missing annex", reason); self.assertIn("[MISSING]", reason)

    def test_refuse_altered_annex(self):
        def alter(d):
            g = json.loads((d / "graphics.json").read_text()); g["series"][0]["points"][3]["v"] += 1
            (d / "graphics.json").write_text(json.dumps(g, indent=1) + "\n")
        reason = self._refused(alter)
        self.assertIn("SHA-256 differs", reason); self.assertIn("[ALTERED]", reason)

    def test_refuse_annex_of_another_run(self):
        other = self.tmp / "run B"; other.mkdir(); _artifacts(other, run_id="pexec-test-0002")
        reason = self._refused(lambda d: shutil.copyfile(other / "graphics.json", d / "graphics.json"))
        self.assertIn("another execution", reason); self.assertIn("[OTHER_RUN]", reason)

    def test_refuse_changed_dataset(self):
        def change(d):
            ds = json.loads((d / "dataset.json").read_text()); ds["bars"][0]["c"] += 1
            (d / "dataset.json").write_text(json.dumps(ds))
        reason = self._refused(change)
        self.assertIn("another dataset", reason); self.assertIn("[OTHER_DATASET]", reason)




# ---------------------------------------------------------------------------------------------
# Reader contract v1 (tools/pws_workspace/READER_CONTRACT.md): version of origin, stable refusal
# codes, inputs preserved, no engine call. Same fixtures as above.
import os
import subprocess
import sys


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _rebind(d, annex_fn=None, report_fn=None):
    """Edit the annex and/or report of run folder `d`, then re-bind them exactly as the runner
    does (payload hash, identity copy, annex SHA-256 recorded in the report)."""
    r = json.loads((d / "run.json").read_text()); g = json.loads((d / "graphics.json").read_text())
    if report_fn: report_fn(r)
    if annex_fn: annex_fn(g)
    r["normalized_payload_sha256"] = g["normalized_payload_sha256"] = render.payload_sha256(r["normalized"])
    text = json.dumps(g, indent=1) + "\n"
    (d / "graphics.json").write_text(text, encoding="utf-8")
    r["graphics_annex"]["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (d / "run.json").write_text(json.dumps(r, indent=1), encoding="utf-8")


class ReaderContractV1(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pws reader "))
        self.run = self.tmp / "run A"; self.run.mkdir(); _artifacts(self.run)
        shim = self.tmp / "shim"; shim.mkdir(); self.calls = self.tmp / "node-calls.log"
        (shim / "node").write_text('#!/bin/sh\necho "$*" >> "%s"\nexit 99\n' % self.calls)
        os.chmod(shim / "node", 0o755)
        self.env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ.get("PATH", ""))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _node_calls(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def _load(self, d):
        return render.load(str(d / "dataset.json"), [(str(d / "run.json"), str(d / "graphics.json"))])

    def test_codes_are_stable_and_localized(self):
        self.assertEqual(render.REFUSAL_CODES, ("MISSING", "MALFORMED", "REPORT_INVALID", "UNKNOWN_SCHEMA", "LEGACY",
                                                "SCHEMA_MISMATCH", "ALTERED", "OTHER_RUN", "OTHER_DATASET"))
        for code in render.REFUSAL_CODES:
            self.assertTrue(render.refusal_message(code, "fr") and render.refusal_message(code, "en"), code)
            self.assertNotEqual(render.refusal_message(code, "fr"), render.refusal_message(code, "en"), code)

    def test_unknown_schema_declared_by_both_with_matching_sha_is_refused(self):
        d = self.tmp / "copy unknown"; shutil.copytree(self.run, d)
        unknown = "pws-pinets-graphics-v9-unknown"

        def set_schema(x):
            x["schema"] = unknown
        _rebind(d, annex_fn=set_schema, report_fn=lambda r: r["graphics_annex"].update(schema=unknown))
        rep = json.loads((d / "run.json").read_text())
        self.assertEqual(rep["graphics_annex"]["schema"], unknown)                       # same schema declared
        self.assertEqual(_sha(d / "graphics.json"), rep["graphics_annex"]["sha256"])       # SHA-256 matches
        before = {f: _sha(d / f) for f in ("run.json", "graphics.json", "dataset.json")}
        with self.assertRaises(render.Refused) as cm:
            self._load(d)
        self.assertEqual(cm.exception.refusal_code, "UNKNOWN_SCHEMA")
        c = local_test.check(ROOT, d)
        self.assertEqual((c["ok"], c["code"]), (False, "UNKNOWN_SCHEMA"))
        for lang in ("fr", "en"):
            out = local_test.reopen(ROOT, d, lang)
            self.assertEqual(out["refusal_code"], "UNKNOWN_SCHEMA"); self.assertNotIn("open", out)
            self.assertIn(render.refusal_message("UNKNOWN_SCHEMA", lang), out["open_refused"])
            self.assertEqual(out["execution_status"], "PINETS_EXECUTION_PASS"); self.assertEqual(out["engine_invocations"], 0)
        # CLI `local-test open` ("Open the chart" of an earlier test): exit 4 and nothing opened when Vela is
        # installed here; exit 7 (VELA_ABSENT / VELA_NO_DEPS) otherwise — never a computation
        cli = subprocess.run([sys.executable, "-m", "tools.pws_workspace", "local-test", "open", "--run-dir", str(d),
                              "--no-browser"], cwd=str(ROOT), env=self.env, capture_output=True, text=True, timeout=120)
        out = json.loads(cli.stdout)
        if live.vela_state(ROOT) == "ready":
            self.assertEqual(cli.returncode, 4, cli.stdout + cli.stderr)
            self.assertEqual(out["refusal_code"], "UNKNOWN_SCHEMA"); self.assertNotIn("page", out)
        else:
            self.assertEqual(cli.returncode, 7, cli.stdout + cli.stderr)
            self.assertTrue(out["refusal_code"].startswith("VELA_"))
        # zero PineTS call; numeric result kept: files untouched, status PASS, payload still bound
        self.assertEqual(self._node_calls(), [])
        self.assertEqual(before, {f: _sha(d / f) for f in before})
        rep = json.loads((d / "run.json").read_text())
        self.assertEqual(rep["execution_status"], "PINETS_EXECUTION_PASS")
        self.assertEqual(render.payload_sha256(rep["normalized"]), rep["normalized_payload_sha256"])

    def test_schema_mismatch_between_report_and_annex(self):
        d = self.tmp / "copy mismatch"; shutil.copytree(self.run, d)
        _rebind(d, report_fn=lambda r: r["graphics_annex"].update(schema="pws-pinets-graphics-v1"))
        with self.assertRaises(render.Refused) as cm:
            self._load(d)
        self.assertEqual(cm.exception.refusal_code, "SCHEMA_MISMATCH")

    def test_legacy_annex_refused(self):
        d = self.tmp / "copy legacy"; shutil.copytree(self.run, d)
        _rebind(d, annex_fn=lambda g: g.update(schema="pws-pinets-graphics-v0.1-exp"))
        with self.assertRaises(render.Refused) as cm:
            self._load(d)
        self.assertEqual(cm.exception.refusal_code, "LEGACY")

    def test_valid_v02_is_read_under_its_version_with_family_counts(self):
        m = self._load(self.run)
        ind = m["inds"][0]
        self.assertEqual((ind["annex_schema"], ind["annex_version"]), ("pws-pinets-graphics-v0.2-exp", "v0.2-exp"))
        self.assertEqual(set(ind["drawing_counts"]), set(render.DRAWING_FAMILIES))
        c = local_test.check(ROOT, self.run)
        self.assertEqual((c["ok"], c["annex_version"]), (True, "v0.2-exp"))
        out = local_test.reopen(ROOT, self.run, "fr")
        self.assertEqual(out["open"]["annex_version"], "v0.2-exp")
        self.assertIn("v0.2-exp", out["open"]["version_note"])
        self.assertIn("ne reconstitue pas nécessairement ce qui était connu à cet instant", out["open"]["final_state"])

    def test_corrections_boolean_values_raw_kind_limits_and_12_significant_digits(self):
        d = self.tmp / "copy corrections"; shutil.copytree(self.run, d)
        t = [p["t"] for p in json.loads((d / "graphics.json").read_text())["series"][0]["points"]]

        def annex(g):
            g["declaration"] = {}                                                  # title / overlay absent
            g["limits"] = ["drawings: final state", "callsite: order of calls"]
            g["drawings"] = {"labels": [{"x": 1}, {"x": 2}], "tables": [{}]}
            g["series"].append({"key": "Flag", "title": "Flag", "callsite": None, "kind": "shape", "options": {},
                                "points": [{"t": x, "v": True} for x in t]})          # boolean values
            g["series"].append({"key": "Hist", "title": "Hist", "callsite": "#2", "kind": "style_histogram",
                                "options": {"style": "style_histogram"},              # raw engine style
                                "points": [{"t": x, "v": 1.23456789012345} for x in t]})

        def report(r):
            r["normalized"]["plots"]["Flag"] = [{"t": x, "v": None} for x in t]   # roundValue(non-number) = null
            r["normalized"]["plots"]["Hist"] = [{"t": x, "v": 1.23456789012} for x in t]   # 12 significant digits
        _rebind(d, annex, report)
        ind = self._load(d)["inds"][0]
        self.assertEqual(ind["drawing_counts"]["labels"], 2); self.assertEqual(ind["drawing_counts"]["tables"], 1)
        self.assertEqual(ind["drawing_counts"]["lines"], 0)
        self.assertFalse(ind["overlay"])
        # a difference within the 12 significant digits is a refusal
        def off(r):
            r["normalized"]["plots"]["Hist"][0]["v"] = 1.23456789013
        _rebind(d, report_fn=off)
        with self.assertRaises(render.Refused) as cm:
            self._load(d)
        self.assertEqual(cm.exception.refusal_code, "MALFORMED")

    def test_unknown_drawing_family_or_bad_limits_is_malformed(self):
        for name, fn in (("family", lambda g: g.update(drawings={"arrows": []})),
                         ("limits", lambda g: g.update(limits="final state"))):
            d = self.tmp / ("copy " + name); shutil.copytree(self.run, d); _rebind(d, annex_fn=fn)
            with self.assertRaises(render.Refused) as cm:
                self._load(d)
            self.assertEqual(cm.exception.refusal_code, "MALFORMED", name)


if __name__ == "__main__":
    unittest.main()
