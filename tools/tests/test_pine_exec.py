# SPDX-License-Identifier: Apache-2.0
"""Durable tests of the PineTS thin adapter (spec sections 39, 61.10).

These tests execute Node. When Node or node_modules is unavailable they SKIP
with an explicit reason — the absence of Node is a declared limitation, never
a defect of any Pine source (spec section 6.1).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core
from tools.tests import ref_indicators

WORKSPACE = core.workspace_root()
PINE_EXEC = WORKSPACE / "tools" / "pine_exec"
NODE = shutil.which("node")
NODE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "TZ": "UTC",
            "LANG": "C", "LC_ALL": "C"}


def node_ready():
    return NODE is not None and (PINE_EXEC / "node_modules" / "pinets").is_dir()


def run_node(args, cwd=PINE_EXEC):
    return subprocess.run([NODE] + args, cwd=str(cwd), capture_output=True,
                          text=True, env=NODE_ENV, timeout=120)


@unittest.skipUnless(node_ready(),
                     "Node.js or tools/pine_exec/node_modules unavailable — "
                     "declared limitation (run npm ci --ignore-scripts), never a Pine source defect")
class TestPineExec(unittest.TestCase):
    def test_dataset_generation_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "a space" / "d1.json"
            out2 = Path(tmp) / "d2.json"
            out1.parent.mkdir()
            for out in (out1, out2):
                proc = run_node(["datasets.mjs", "gen", "--seed", "42", "--bars", "60",
                                 "--base-cents", "10000", "--vol-cents", "150",
                                 "--out", str(out)])
                self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            self.assertEqual(core.sha256_file(out1),
                             "ff3a5ae872cc81b130d73636d21210fcee026f5883c9969473d8aef9661d9b36")

    def test_python_mirror_reproduces_dataset(self):
        data = json.loads((PINE_EXEC / "calibration" / "datasets" / "lcg-42-60.json")
                          .read_text(encoding="utf-8"))
        p = data["descriptor"]["params"]
        mine = ref_indicators.generate_bars(p["seed"], p["bars"], p["base_cents"],
                                            p["vol_cents"], p["t0_ms"], p["tf_ms"])
        self.assertEqual(mine, data["bars"])

    def test_calibration_case_against_independent_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(out)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            run = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(run["execution_status"], "PINETS_EXECUTION_PASS")
        self.assertEqual(run["unclassified_tokens"], [])
        for cap in ("ta-sma", "ta-ema", "series-history", "math-arith", "plot-plot"):
            self.assertIn(cap, run["capabilities_used"])
            entry = run["capabilities_used"][cap]
            # contract-based (audit F6e): statuses must be valid and coherent
            # with the manifest — a legitimate future GATING promotion is
            # allowed, an invented status is not.
            self.assertIn(entry["capability_status"],
                          ("GATING", "EXPERIMENTAL", "UNSUPPORTED"))
            self.assertEqual(entry["calibration_status"], "CURRENT",
                             "calibration must be CURRENT when the manifest "
                             "matches the live environment")
        self.assertTrue(run["calibration_environment_match"])
        expected = ref_indicators.expected_payload_for_core_case(
            PINE_EXEC / "calibration" / "datasets" / "lcg-42-60.json")
        plots = run["normalized"]["plots"]
        # exact concordance: SMA5 / PREV / MID
        for name in ("SMA5", "PREV", "MID"):
            self.assertEqual(plots[name], expected[name], "%s diverges" % name)
        # ta-ema: SMA-seed convention within documented float tolerance
        got = plots["EMA5"]
        ref = expected["EMA5_sma_seed"]
        self.assertEqual(len(got), len(ref))
        for g, e in zip(got, ref):
            if g["v"] is None or e["v"] is None:
                self.assertEqual(g["v"], e["v"])
            else:
                self.assertLessEqual(abs(g["v"] - e["v"]) / max(abs(e["v"]), 1e-9), 1e-9)

    def test_run_identity_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            run = json.loads(out.read_text(encoding="utf-8"))
        calib = json.loads((PINE_EXEC / "calibration" / "capabilities.json")
                           .read_text(encoding="utf-8"))
        for field in ("run_id", "timestamp", "source_sha256", "dataset_sha256",
                      "dataset_descriptor", "configuration", "pinets_version",
                      "executor_fingerprint", "normalization_schema",
                      "capabilities_used", "normalized_payload_sha256"):
            self.assertIn(field, run)
            self.assertIsNotNone(run[field], field)
        # the version actually pinned (not a constant: a guided PineTS update must leave this test valid)
        pinned = json.loads((PINE_EXEC / "package.json").read_text(encoding="utf-8"))["dependencies"]["pinets"]
        self.assertEqual(run["pinets_version"], pinned)
        self.assertEqual(run["normalization_schema"], "pws-pinets-norm-v2")
        self.assertEqual(run["executor_fingerprint"],
                         calib["environment"]["executor_fingerprint"],
                         "environment drifted since calibration — recalibrate "
                         "(calibrations for the old identity are STALE)")

    def test_calibration_manifest_integrity(self):
        calib = json.loads((PINE_EXEC / "calibration" / "capabilities.json")
                           .read_text(encoding="utf-8"))
        for name, art in calib["case_artifacts"].items():
            path = PINE_EXEC / "calibration" / art["path"]
            self.assertTrue(path.is_file(), name)
            self.assertEqual(core.sha256_file(path), art["sha256"],
                             "%s hash diverges — calibration STALE" % name)
        for cap, entry in calib["capabilities"].items():
            self.assertIn(entry["capability_status"],
                          ("GATING", "EXPERIMENTAL", "UNSUPPORTED"))
            self.assertIn(entry["calibration_status"],
                          ("CURRENT", "STALE", "MISSING"))
            self.assertNotIn("effective_gating", entry)
            # coherence, not prohibition (audit F6e): a GATING capability is
            # legitimate ONLY with a CURRENT independent calibration backed by
            # real cases — zero GATING remains a perfectly valid state.
            if entry["capability_status"] == "GATING":
                self.assertEqual(entry["calibration_status"], "CURRENT",
                                 "%s: GATING requires CURRENT calibration" % cap)
                self.assertTrue(entry.get("cases"),
                                "%s: GATING requires real calibration cases" % cap)

    def test_explicit_matrix_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp) / "matrix out"
            manifest = Path(tmp) / "matrix.json"
            manifest.write_text(json.dumps({
                "source": str(PINE_EXEC / "calibration" / "cases" / "calib-core.pine"),
                "datasets": [str(PINE_EXEC / "calibration" / "datasets" / "lcg-42-60.json")],
                "configs": [{"periods": 20}, {}],
            }), encoding="utf-8")
            proc = run_node(["runner.mjs", "matrix", "--manifest", str(manifest),
                             "--out-dir", str(tmpd)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads((tmpd / "matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(len(result["cells"]), 2)
            run_ids = {c["run_id"] for c in result["cells"]}
            self.assertEqual(len(run_ids), 2,
                             "each elementary run keeps its own identity")
            for cell in result["cells"]:
                self.assertTrue(Path(cell["report"]).is_file())
                self.assertEqual(cell["execution_status"], "PINETS_EXECUTION_PASS")

    def test_execution_fail_is_separate_axis(self):
        """A source that PineTS cannot run -> PINETS_EXECUTION_FAIL, and the
        runner still produces a fully identified report (never a TV status)."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad case.pine"
            bad.write_text("//@version=6\nindicator(\"Bad\")\n"
                           "x = totally.unknown_namespace_call(close)\nplot(x)\n",
                           encoding="utf-8")
            out = Path(tmp) / "run.json"
            proc = run_node(["runner.mjs", "run", "--source", str(bad),
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(out)])
            run = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(run["execution_status"], "PINETS_EXECUTION_FAIL")
        self.assertIsNotNone(run["error"])
        self.assertIn("totally.unknown_namespace_call", run["unclassified_tokens"])
        for key in ("TV_VALIDATED", "tv_status", "validation"):
            self.assertNotIn(key, run)

    def test_imported_snapshot_consumable_with_provenance(self):
        """spec section 61.10.21: an imported OHLCV snapshot with explicit
        provenance and a stable hash is consumable without any network
        provider."""
        ds_path = PINE_EXEC / "calibration" / "datasets" / "imported-sample.json"
        data = json.loads(ds_path.read_text(encoding="utf-8"))
        self.assertEqual(data["descriptor"]["type"], "imported")
        self.assertIn("provenance", data["descriptor"])
        sha_before = core.sha256_file(ds_path)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", str(ds_path), "--out", str(out)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            run = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(run["execution_status"], "PINETS_EXECUTION_PASS")
            self.assertEqual(run["dataset_sha256"], sha_before)
            self.assertEqual(run["dataset_descriptor"]["type"], "imported")

    def test_reproducible_normalized_output(self):
        """spec section 61.10.8: same source + dataset + config -> identical
        normalized payload hash across runs."""
        hashes = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "run.json"
                run_node(["runner.mjs", "run",
                          "--source", "calibration/cases/calib-core.pine",
                          "--dataset", "calibration/datasets/lcg-42-60.json",
                          "--out", str(out)])
                hashes.append(json.loads(out.read_text(encoding="utf-8"))
                              ["normalized_payload_sha256"])
        self.assertEqual(hashes[0], hashes[1])

    def test_regression_qualification_pass_plus_changed(self):
        """Audit F6f / spec sections 24.4.9 and 61.10.18: a REAL regression
        qualification — same dataset and configuration, modified source —
        yields PINETS_EXECUTION_PASS on both sides plus a CHANGED comparison
        that is not an execution failure."""
        with tempfile.TemporaryDirectory() as tmp:
            src_a = Path(tmp) / "variant a.pine"
            src_b = Path(tmp) / "variant b.pine"
            src_a.write_text('//@version=6\nindicator("V")\nplot(close, title="S")\n',
                             encoding="utf-8")
            src_b.write_text('//@version=6\nindicator("V")\nplot(open, title="S")\n',
                             encoding="utf-8")
            runs = {}
            for tag, src in (("a", src_a), ("b", src_b), ("a2", src_a)):
                out = Path(tmp) / ("run-%s.json" % tag)
                proc = run_node(["runner.mjs", "run", "--source", str(src),
                                 "--dataset", "calibration/datasets/lcg-42-60.json",
                                 "--out", str(out)])
                self.assertEqual(proc.returncode, 0, proc.stderr)
                runs[tag] = out
                self.assertEqual(json.loads(out.read_text(encoding="utf-8"))
                                 ["execution_status"], "PINETS_EXECUTION_PASS")
            # modified source, same dataset/config -> CHANGED (and still PASS)
            proc = run_node(["runner.mjs", "compare", "--a", str(runs["a"]),
                             "--b", str(runs["b"])])
            verdict = json.loads(proc.stdout)
            self.assertTrue(verdict["comparable"])
            self.assertEqual(verdict["status"], "PINETS_REGRESSION_CHANGED")
            self.assertEqual([c["plot"] for c in verdict["changed"]], ["S"])
            self.assertIn("EXPECTED / UNEXPECTED / UNRESOLVED", verdict["note"])
            # identical source -> UNCHANGED
            proc = run_node(["runner.mjs", "compare", "--a", str(runs["a"]),
                             "--b", str(runs["a2"])])
            verdict = json.loads(proc.stdout)
            self.assertEqual(verdict["status"], "PINETS_REGRESSION_UNCHANGED")

    def test_non_plot_divergence_stays_actionable(self):
        """Targeted review 2026-09-06: an alerts/warnings-only difference must
        name its diverging section, never yield CHANGED with an empty diff."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            base = json.loads(out.read_text(encoding="utf-8"))
            variant = json.loads(out.read_text(encoding="utf-8"))
            variant["normalized"]["warnings"] = ["injected divergence"]
            # keep the report self-consistent: recompute the payload sha via
            # a real node call
            script = ("import(%r).then(m => {const p=%s;"
                      "console.log(m.payloadSha256(p));})"
                      % ((PINE_EXEC / "normalize.mjs").as_uri(),
                         json.dumps(variant["normalized"])))
            proc = subprocess.run([NODE, "--input-type=module", "-e", script],
                                  cwd=str(PINE_EXEC), capture_output=True,
                                  text=True, env=NODE_ENV, timeout=60)
            variant["normalized_payload_sha256"] = proc.stdout.strip()
            vfile = Path(tmp) / "variant.json"
            vfile.write_text(json.dumps(variant), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(out),
                             "--b", str(vfile)])
            verdict = json.loads(proc.stdout)
        self.assertEqual(verdict["status"], "PINETS_REGRESSION_CHANGED")
        self.assertIn({"section": "warnings"}, verdict["changed"])

    def test_incomparable_runs_are_inconclusive(self):
        """Different datasets are NOT a regression comparison: the verdict is
        PINETS_INCONCLUSIVE, never CHANGED."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = {}
            for tag, ds in (("x", "calibration/datasets/lcg-42-60.json"),
                            ("y", "calibration/datasets/imported-sample.json")):
                out = Path(tmp) / ("run-%s.json" % tag)
                run_node(["runner.mjs", "run",
                          "--source", "calibration/cases/calib-core.pine",
                          "--dataset", ds, "--out", str(out)])
                runs[tag] = out
            proc = run_node(["runner.mjs", "compare", "--a", str(runs["x"]),
                             "--b", str(runs["y"])])
            verdict = json.loads(proc.stdout)
            self.assertFalse(verdict["comparable"])
            self.assertEqual(verdict["status"], "PINETS_INCONCLUSIVE")
            self.assertIn("dataset_sha256", verdict["reasons"])

    def test_validation_destination_refused(self):
        """Audit F6c/F6d: pointing --out INSIDE a validation/ directory must
        be REFUSED (exit 4, nothing written) — this test exercises the
        refusal itself, not a neighboring write."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_validation = Path(tmp) / "scripts" / "prod" / "validation"
            fake_validation.mkdir(parents=True)
            out = fake_validation / "pinets-run.json"
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(out)])
            self.assertEqual(proc.returncode, 4, proc.stderr)
            self.assertIn("validation/", proc.stderr)
            self.assertEqual(list(fake_validation.iterdir()), [])
            # matrix destinations are refused the same way
            manifest = Path(tmp) / "matrix.json"
            manifest.write_text(json.dumps({
                "source": str(PINE_EXEC / "calibration" / "cases" / "calib-core.pine"),
                "datasets": [str(PINE_EXEC / "calibration" / "datasets" / "lcg-42-60.json")],
            }), encoding="utf-8")
            proc = run_node(["runner.mjs", "matrix", "--manifest", str(manifest),
                             "--out-dir", str(fake_validation / "out")])
            self.assertEqual(proc.returncode, 4)
            self.assertEqual(list(fake_validation.iterdir()), [])
            # a legitimate destination still works
            ok_out = Path(tmp) / "run.json"
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(ok_out)])
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(ok_out.is_file())

    def test_validation_destination_refusal_bypasses_closed(self):
        """Adversarial review 2026-09-05: the refusal must hold under APFS
        case-insensitivity (VALIDATION/) and through directory symlinks."""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            upper = Path(tmp) / "VALIDATION"
            upper.mkdir()
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(upper / "run.json")])
            self.assertEqual(proc.returncode, 4, proc.stderr)
            self.assertEqual(list(upper.iterdir()), [])
            real_validation = Path(tmp) / "scripts" / "p" / "validation"
            real_validation.mkdir(parents=True)
            link = Path(tmp) / "innocent"
            os.symlink(real_validation, link)
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--out", str(link / "run.json")])
            self.assertEqual(proc.returncode, 4, proc.stderr)
            self.assertEqual(list(real_validation.iterdir()), [])

    def test_compare_refuses_malformed_reports(self):
        """A malformed report must never yield a false UNCHANGED."""
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.json"
            b = Path(tmp) / "b.json"
            # materially different plots, no payload shas, wrong schema
            a.write_text(json.dumps({"schema": "pws-pinets-run-v1",
                                     "execution_status": "PINETS_EXECUTION_PASS",
                                     "normalized": {"plots": {"S": [{"t": 1, "v": 1}]}}}),
                         encoding="utf-8")
            b.write_text(json.dumps({"schema": "pws-pinets-run-v1",
                                     "execution_status": "PINETS_EXECUTION_PASS",
                                     "normalized": {"plots": {"S": [{"t": 1, "v": 2}]}}}),
                         encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(a), "--b", str(b)])
            verdict = json.loads(proc.stdout)
            self.assertFalse(verdict["comparable"])
            self.assertEqual(verdict["status"], "PINETS_INCONCLUSIVE")
            self.assertTrue(any("malformed_report" in r for r in verdict["reasons"]))

    def test_compare_refuses_identityless_reports(self):
        """3rd external audit, item 4: two reports with EQUAL self-declared
        hashes but no identities and no payload must be INCONCLUSIVE, never
        UNCHANGED."""
        with tempfile.TemporaryDirectory() as tmp:
            fake = {"schema": "pws-pinets-run-v1",
                    "execution_status": "PINETS_EXECUTION_PASS",
                    "normalized_payload_sha256": "a" * 64}
            a = Path(tmp) / "a.json"
            b = Path(tmp) / "b.json"
            a.write_text(json.dumps(fake), encoding="utf-8")
            b.write_text(json.dumps(fake), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(a), "--b", str(b)])
            verdict = json.loads(proc.stdout)
        self.assertFalse(verdict["comparable"])
        self.assertEqual(verdict["status"], "PINETS_INCONCLUSIVE")
        self.assertTrue(any("dataset_sha256" in r for r in verdict["reasons"]))
        self.assertTrue(any("normalized" in r for r in verdict["reasons"]))

    def test_compare_refuses_stripped_real_report(self):
        """4th external audit, item 3: a REAL report stripped of its
        configuration and source_sha256, compared with itself, must be
        INCONCLUSIVE — absence is never defaulted away."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            data = json.loads(out.read_text(encoding="utf-8"))
            del data["configuration"]
            del data["source_sha256"]
            stripped = Path(tmp) / "stripped.json"
            stripped.write_text(json.dumps(data), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(stripped),
                             "--b", str(stripped)])
            verdict = json.loads(proc.stdout)
        self.assertFalse(verdict["comparable"])
        self.assertEqual(verdict["status"], "PINETS_INCONCLUSIVE")
        self.assertTrue(any("configuration" in r for r in verdict["reasons"]))
        self.assertTrue(any("source_sha256" in r for r in verdict["reasons"]))

    def test_compare_refuses_malformed_timestamp(self):
        """Wave-4 review: the run identity includes an RFC 3339 timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            data = json.loads(out.read_text(encoding="utf-8"))
            data["timestamp"] = "not-a-timestamp"
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(data), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(bad),
                             "--b", str(out)])
            verdict = json.loads(proc.stdout)
        self.assertFalse(verdict["comparable"])
        self.assertTrue(any("timestamp" in r for r in verdict["reasons"]))

    def test_changed_never_has_empty_diff(self):
        """Wave-4 review: a payload divergence outside the enumerated
        sections still names {'section': 'payload'}."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            variant = json.loads(out.read_text(encoding="utf-8"))
            variant["normalized"]["crafted_future_key"] = "divergence"
            script = ("import(%r).then(m => {const p=%s;"
                      "console.log(m.payloadSha256(p));})"
                      % ((PINE_EXEC / "normalize.mjs").as_uri(),
                         json.dumps(variant["normalized"])))
            proc = subprocess.run([NODE, "--input-type=module", "-e", script],
                                  cwd=str(PINE_EXEC), capture_output=True,
                                  text=True, env=NODE_ENV, timeout=60)
            variant["normalized_payload_sha256"] = proc.stdout.strip()
            vfile = Path(tmp) / "variant.json"
            vfile.write_text(json.dumps(variant), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(out),
                             "--b", str(vfile)])
            verdict = json.loads(proc.stdout)
        self.assertEqual(verdict["status"], "PINETS_REGRESSION_CHANGED")
        self.assertEqual(verdict["changed"], [{"section": "payload"}])

    def test_compare_allows_differing_source_shas(self):
        """source_sha256 must be present and valid on both sides, but MAY
        differ — that is precisely how two source versions are compared."""
        with tempfile.TemporaryDirectory() as tmp:
            src_a = Path(tmp) / "a.pine"
            src_b = Path(tmp) / "b.pine"
            src_a.write_text('//@version=6\nindicator("V")\nplot(close, title="S")\n',
                             encoding="utf-8")
            src_b.write_text('//@version=6\nindicator("V")\nplot(open, title="S")\n',
                             encoding="utf-8")
            outs = {}
            for tag, src in (("a", src_a), ("b", src_b)):
                outs[tag] = Path(tmp) / ("run-%s.json" % tag)
                run_node(["runner.mjs", "run", "--source", str(src),
                          "--dataset", "calibration/datasets/lcg-42-60.json",
                          "--out", str(outs[tag])])
            proc = run_node(["runner.mjs", "compare", "--a", str(outs["a"]),
                             "--b", str(outs["b"])])
            verdict = json.loads(proc.stdout)
        self.assertTrue(verdict["comparable"])
        self.assertEqual(verdict["status"], "PINETS_REGRESSION_CHANGED")

    def test_compare_refuses_self_declared_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            run_node(["runner.mjs", "run",
                      "--source", "calibration/cases/calib-core.pine",
                      "--dataset", "calibration/datasets/lcg-42-60.json",
                      "--out", str(out)])
            data = json.loads(out.read_text(encoding="utf-8"))
            data["normalized_payload_sha256"] = "f" * 64  # lies about its payload
            tampered = Path(tmp) / "tampered.json"
            tampered.write_text(json.dumps(data), encoding="utf-8")
            proc = run_node(["runner.mjs", "compare", "--a", str(out), "--b", str(tampered)])
            verdict = json.loads(proc.stdout)
            self.assertFalse(verdict["comparable"])
            self.assertTrue(any("payload_sha_mismatch" in r for r in verdict["reasons"]))

    def test_infrastructure_error_distinct_exit_code(self):
        """A missing dataset is an input error (exit 5), never conflated with
        PINETS_EXECUTION_FAIL (exit 1)."""
        proc = run_node(["runner.mjs", "run",
                         "--source", "calibration/cases/calib-core.pine",
                         "--dataset", "no such dataset.json"])
        self.assertEqual(proc.returncode, 5, proc.stderr)
        self.assertIn("not a Pine source result", proc.stderr)

    def test_hostile_ambient_environment_neutralized(self):
        """The runner enforces TZ/LANG/LC_ALL itself: a hostile ambient
        environment must not change the normalized payload."""
        with tempfile.TemporaryDirectory() as tmp:
            hostile_env = dict(NODE_ENV)
            hostile_env.update({"TZ": "America/New_York", "LANG": "tr_TR.UTF-8",
                                "LC_ALL": "tr_TR.UTF-8"})
            shas = []
            for env in (NODE_ENV, hostile_env):
                out = Path(tmp) / ("run-%d.json" % len(shas))
                proc = subprocess.run(
                    [NODE, "runner.mjs", "run",
                     "--source", "calibration/cases/calib-core.pine",
                     "--dataset", "calibration/datasets/lcg-42-60.json",
                     "--out", str(out)],
                    cwd=str(PINE_EXEC), capture_output=True, text=True,
                    env=env, timeout=120)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                shas.append(json.loads(out.read_text(encoding="utf-8"))
                            ["normalized_payload_sha256"])
            self.assertEqual(shas[0], shas[1])


@unittest.skipUnless(node_ready(),
                     "Node.js or tools/pine_exec/node_modules unavailable — "
                     "declared limitation (run npm ci --ignore-scripts), never a Pine source defect")
class TestClassifierV2(unittest.TestCase):
    """Audit F5: closed-world lexical classifier — an empty unclassified list
    now means every token was recognized, and unknown constructs are
    reported instead of silently dropped."""

    def _classify(self, source):
        script = ("import(%r).then(m => {"
                  "console.log(JSON.stringify(m.classifyCapabilities(%s)));})"
                  % ((PINE_EXEC / "runner.mjs").as_uri(), json.dumps(source)))
        proc = subprocess.run([NODE, "--input-type=module", "-e", script],
                              cwd=str(PINE_EXEC), capture_output=True, text=True,
                              env=NODE_ENV, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_audit_snippet_fully_classified(self):
        r = self._classify('//@version=6\nindicator("Test")\n'
                           'plot(barstate.islast ? close : open)\n')
        self.assertIn("barstate-islast", r["used"])
        self.assertIn("control-ternary", r["used"])
        self.assertIn("series-builtin", r["used"])
        self.assertEqual(r["unclassified"], [])

    def test_unknown_member_chain_unclassified(self):
        r = self._classify('//@version=6\nindicator("T")\n'
                           'x = unknownns.mystery(close)\nplot(x)\n')
        self.assertIn("unknownns.mystery", r["unclassified"])

    def test_unknown_identifier_unclassified(self):
        r = self._classify('//@version=6\nindicator("T")\n'
                           'plot(mystery_builtin(close))\n')
        self.assertIn("mystery_builtin", r["unclassified"])

    def test_named_arguments_and_locals_are_neutral(self):
        r = self._classify('//@version=6\nindicator("T")\n'
                           'myLen = 5\nsmoothed = ta.sma(close, myLen)\n'
                           'plot(smoothed, title="S", color=color.new(#26A69A, 0))\n')
        self.assertEqual(r["unclassified"], [])
        self.assertIn("ta-sma", r["used"])
        self.assertIn("color-new", r["used"])

    def test_locals_pollution_from_wrapped_named_args(self):
        """Adversarial review: a named-argument label on a continuation line
        of a wrapped call must not become a local hiding unknown calls."""
        base = '//@version=6\nindicator("T")\ny = foo(close)\nplot(y)\n'
        wrapped = ('//@version=6\nindicator("T")\n'
                   'plot(close,\n     foo="X")\ny = foo(close)\nplot(y)\n')
        r1 = self._classify(base)
        r2 = self._classify(wrapped)
        self.assertIn("foo", r1["unclassified"])
        self.assertIn("foo", r2["unclassified"],
                      "wrapped named arg must not shadow the unknown call")

    def test_deep_member_chain_keeps_tail(self):
        r = self._classify('//@version=6\nstrategy("T")\n'
                           'strategy.risk.allow_entry_in(strategy.direction.long)\n'
                           'plot(close)\n')
        self.assertIn("strategy-risk-allow_entry_in", r["used"])
        self.assertIn("strategy-direction-long", r["used"])

    def test_local_shadowing_namespace_name(self):
        r = self._classify('//@version=6\nindicator("T")\nsize = 5\n'
                           'plot(close * size)\n')
        self.assertNotIn("size", r["used"])
        self.assertEqual(r["unclassified"], [])

    def test_calib_core_capability_set_stable(self):
        source = (PINE_EXEC / "calibration" / "cases" / "calib-core.pine") \
            .read_text(encoding="utf-8")
        r = self._classify(source)
        for cap in ("declaration-indicator", "ta-sma", "ta-ema", "series-history",
                    "series-builtin", "math-arith", "plot-plot"):
            self.assertIn(cap, r["used"])
        self.assertEqual(r["unclassified"], [])


@unittest.skipUnless(node_ready(),
                     "Node.js or tools/pine_exec/node_modules unavailable — "
                     "declared limitation (run npm ci --ignore-scripts), never a Pine source defect")
class TestDerivedFreshness(unittest.TestCase):
    """Audit F4: calibration freshness is derived per run from the CURRENT
    triplet and the calibration artifacts — a drifted environment (e.g. the
    external audit's Linux/Node 24) degrades CURRENT to STALE while
    capability_status is preserved."""

    def _run_with_calibration(self, calib_dir):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            proc = run_node(["runner.mjs", "run",
                             "--source", "calibration/cases/calib-core.pine",
                             "--dataset", "calibration/datasets/lcg-42-60.json",
                             "--calibration", str(calib_dir), "--out", str(out)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(out.read_text(encoding="utf-8"))

    def _copy_calibration(self, tmp):
        import shutil as sh
        dst = Path(tempfile.mkdtemp(prefix="calib copy ", dir=tmp)) / "calibration"
        sh.copytree(PINE_EXEC / "calibration", dst)
        return dst

    def test_environment_drift_derives_stale_and_preserves_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["environment"]["executor_fingerprint"] = "0" * 64
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertFalse(run["calibration_environment_match"])
        for cap, entry in run["capabilities_used"].items():
            self.assertEqual(entry["calibration_status"], "STALE", cap)
            self.assertEqual(entry["capability_status"], "EXPERIMENTAL",
                             "capability_status must be preserved on drift")

    def test_artifact_divergence_derives_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            case = dst / "cases" / "calib-core.pine"
            case.write_text(case.read_text(encoding="utf-8") + "// altered\n",
                            encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertTrue(run["calibration_artifact_failures"])
        for cap, entry in run["capabilities_used"].items():
            self.assertEqual(entry["calibration_status"], "STALE", cap)

    def test_matching_environment_keeps_current(self):
        run = self._run_with_calibration(PINE_EXEC / "calibration")
        self.assertTrue(run["calibration_environment_match"])
        self.assertEqual(run["calibration_artifact_failures"], [])
        for cap, entry in run["capabilities_used"].items():
            self.assertEqual(entry["calibration_status"], "CURRENT", cap)

    def test_no_case_artifacts_means_no_current(self):
        """Adversarial review: CURRENT with zero evidence is refused — a
        manifest whose case_artifacts map was removed derives STALE."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest.pop("case_artifacts", None)
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        for cap, entry in run["capabilities_used"].items():
            self.assertEqual(entry["calibration_status"], "STALE", cap)

    def test_ghost_evidence_derives_stale(self):
        """A capability whose evidence_artifacts reference no verified
        artifact cannot be CURRENT — staleness stays scoped to it."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["capabilities"]["ta-sma"]["evidence_artifacts"] = \
                ["ghost-artifact-never-hashed"]
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertEqual(run["capabilities_used"]["ta-sma"]["calibration_status"],
                         "STALE")
        # untouched capabilities keep their evidence
        self.assertEqual(run["capabilities_used"]["math-arith"]["calibration_status"],
                         "CURRENT")

    def test_pine_file_alone_is_not_calibration_evidence(self):
        """3rd audit item 5a: a capability whose evidence is ONLY the case
        source (no expected/reference with reference_provenance) cannot be
        CURRENT."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["case_artifacts"] = {
                "calib-core.pine": manifest["case_artifacts"]["calib-core.pine"]}
            for cap in manifest["capabilities"].values():
                cap["evidence_artifacts"] = ["calib-core.pine"]
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        for cap, entry in run["capabilities_used"].items():
            self.assertEqual(entry["calibration_status"], "STALE", cap)

    def test_staleness_scoped_to_concerned_capabilities(self):
        """3rd audit item 5b: a failing artifact only stales the capabilities
        that list it — never unconcerned ones."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            (dst / "unrelated.bin").write_text("x", encoding="utf-8")
            manifest["case_artifacts"]["unrelated-artifact"] = {
                "path": "unrelated.bin", "sha256": "0" * 64}  # hash diverges
            manifest["capabilities"]["ta-ema"]["evidence_artifacts"] = \
                manifest["capabilities"]["ta-ema"]["evidence_artifacts"] + \
                ["unrelated-artifact"]
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertEqual(run["capabilities_used"]["ta-ema"]["calibration_status"],
                         "STALE", "concerned capability must go stale")
        self.assertEqual(run["capabilities_used"]["ta-sma"]["calibration_status"],
                         "CURRENT", "unconcerned capability must stay CURRENT")
        self.assertIn("unrelated-artifact", run["calibration_artifact_failures"])

    def test_escaping_artifact_path_is_failure(self):
        """Targeted review 2026-09-06: a traversal or symlinked artifact path
        escaping calibration/ is an artifact FAILURE, never evidence — same
        rule as the doctor."""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            outside = Path(tmp) / "outside-reference.json"
            outside.write_text("{}", encoding="utf-8")
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["case_artifacts"]["escaping"] = {
                "path": "../outside-reference.json",
                "sha256": core.sha256_file(outside),
                "reference_provenance": "fake"}
            manifest["capabilities"]["ta-sma"]["evidence_artifacts"] = ["escaping"]
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
            self.assertIn("escaping", run["calibration_artifact_failures"])
            self.assertEqual(run["capabilities_used"]["ta-sma"]["calibration_status"],
                             "STALE")
            # symlink variant
            dst2 = self._copy_calibration(tmp)
            os.symlink(outside, dst2 / "linked-reference.json")
            manifest2 = json.loads((dst2 / "capabilities.json").read_text(encoding="utf-8"))
            manifest2["case_artifacts"]["linked"] = {
                "path": "linked-reference.json",
                "sha256": core.sha256_file(outside),
                "reference_provenance": "fake"}
            manifest2["capabilities"]["ta-sma"]["evidence_artifacts"] = ["linked"]
            (dst2 / "capabilities.json").write_text(json.dumps(manifest2),
                                                    encoding="utf-8")
            run2 = self._run_with_calibration(dst2)
            self.assertIn("linked", run2["calibration_artifact_failures"])
            self.assertEqual(run2["capabilities_used"]["ta-sma"]["calibration_status"],
                             "STALE")

    def test_missing_evidence_list_derives_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["capabilities"]["ta-sma"].pop("evidence_artifacts", None)
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertEqual(run["capabilities_used"]["ta-sma"]["calibration_status"],
                         "STALE")

    def test_run_records_calibration_manifest_identity(self):
        run = self._run_with_calibration(PINE_EXEC / "calibration")
        self.assertEqual(run["calibration_manifest_sha256"],
                         core.sha256_file(PINE_EXEC / "calibration" / "capabilities.json"))

    def test_missing_stays_missing_on_drift(self):
        """A never-calibrated capability is MISSING, not STALE — drift does
        not invent a calibration history."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._copy_calibration(tmp)
            manifest = json.loads((dst / "capabilities.json").read_text(encoding="utf-8"))
            manifest["environment"]["executor_fingerprint"] = "0" * 64
            manifest["capabilities"]["ta-sma"]["calibration_status"] = "MISSING"
            (dst / "capabilities.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
            run = self._run_with_calibration(dst)
        self.assertEqual(run["capabilities_used"]["ta-sma"]["calibration_status"],
                         "MISSING")


if __name__ == "__main__":
    unittest.main()
