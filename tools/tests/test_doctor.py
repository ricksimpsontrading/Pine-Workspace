# SPDX-License-Identifier: Apache-2.0
"""Doctor aggregation, severity mapping, actionable BLOCKINGs (spec section 32)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core, doctor
from tools.tests import helpers


def by_check(results):
    out = {}
    for r in results:
        out.setdefault(r["check"], []).append(r)
    return out


def make_minimal_root(tmpname):
    """Minimal healthy root for doctor tests (no git repo by default)."""
    root = helpers.make_workspace(tmpname)
    master = root / core.STANDARD_REL
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text("# M\n## 0. MISSION\n", encoding="utf-8")
    (root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
        {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
    (root / ".claude" / "settings.json").write_text(json.dumps({
        "hooks": {"SessionStart": [], "Stop": []},
        "worktree": {"baseRef": "head"},
    }), encoding="utf-8")
    (root / "tools" / "tests").mkdir(parents=True)
    (root / "tools" / "tests" / "test_x.py").write_text("# t\n", encoding="utf-8")
    return root


class TestDoctor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_minimal_root(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_absent_scripts_dir_tolerated(self):
        import shutil
        shutil.rmtree(self.root / "scripts")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["products"][0]["severity"], "OK")
        self.assertIn("zero products", results["products"][0]["detail"])

    def test_enclosing_repo_blocking_and_actionable(self):
        parent = Path(self.tmp.name) / "parent repo"
        parent.mkdir()
        subprocess.run(["git", "init", "-q", str(parent)], check=True)
        nested = parent / "pine workspace"
        nested.mkdir()
        results = by_check(doctor.run_doctor(nested))
        finding = results["no-enclosing-repo"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("ask the holder", finding["detail"])

    def test_tv_mode_invalid_blocking(self):
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "banana"}}), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["tv-mode-valid"][0]["severity"], "BLOCKING")

    def test_pinets_floating_range_blocking(self):
        pe = self.root / "tools" / "pine_exec"
        pe.mkdir(parents=True)
        (pe / "package.json").write_text(json.dumps(
            {"dependencies": {"pinets": "^0.9.33"}}), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["pinets-pinned"][0]["severity"], "BLOCKING")

    def test_persisted_effective_gating_blocking(self):
        pe = self.root / "tools" / "pine_exec"
        (pe / "calibration").mkdir(parents=True)
        (pe / "package.json").write_text(json.dumps(
            {"dependencies": {"pinets": "0.9.33"}}), encoding="utf-8")
        (pe / "package-lock.json").write_text(json.dumps(
            {"packages": {"node_modules/pinets": {"version": "0.9.33"}}}), encoding="utf-8")
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "capabilities": {"ta-sma": {
                "capability_status": "EXPERIMENTAL",
                "calibration_status": "CURRENT",
                "effective_gating": False,
            }},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["no-persisted-effective-gating"][0]["severity"], "BLOCKING")

    def test_gating_without_current_calibration_flagged(self):
        pe = self.root / "tools" / "pine_exec"
        (pe / "calibration").mkdir(parents=True)
        (pe / "package.json").write_text(json.dumps(
            {"dependencies": {"pinets": "0.9.33"}}), encoding="utf-8")
        (pe / "package-lock.json").write_text(json.dumps(
            {"packages": {"node_modules/pinets": {"version": "0.9.33"}}}), encoding="utf-8")
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "capabilities": {"ta-sma": {
                "capability_status": "GATING",
                "calibration_status": "STALE",
            }},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["gating-calibration-current"][0]["severity"], "WARNING")

    def test_project_mcp_blocking(self):
        (self.root / ".mcp.json").write_text("{}", encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["no-project-mcp"][0]["severity"], "BLOCKING")

    def test_gitkeep_warning(self):
        (self.root / "scripts" / ".gitkeep").write_text("", encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["no-gitkeep"][0]["severity"], "WARNING")

    def _pine_exec_base(self):
        pe = self.root / "tools" / "pine_exec"
        (pe / "calibration").mkdir(parents=True, exist_ok=True)
        (pe / "package.json").write_text(json.dumps(
            {"dependencies": {"pinets": "0.9.33"}}), encoding="utf-8")
        (pe / "package-lock.json").write_text(json.dumps(
            {"packages": {"node_modules/pinets": {"version": "0.9.33"}}}), encoding="utf-8")
        return pe

    def test_calibration_artifact_divergence_warns(self):
        """Audit F6b: case/expected/reference hashes feed operational
        freshness."""
        pe = self._pine_exec_base()
        case = pe / "calibration" / "case.pine"
        case.write_text("//@version=6\n", encoding="utf-8")
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "case_artifacts": {"case.pine": {"path": "case.pine", "sha256": "0" * 64}},
            "capabilities": {},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["calibration-artifact-integrity"][0]
        self.assertEqual(finding["severity"], "WARNING")
        self.assertIn("STALE", finding["detail"])

    def test_calibration_artifact_integrity_ok(self):
        pe = self._pine_exec_base()
        case = pe / "calibration" / "case.pine"
        case.write_text("//@version=6\n", encoding="utf-8")
        from tools.pws_workspace import core as c
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "case_artifacts": {"case.pine": {"path": "case.pine",
                                             "sha256": c.sha256_file(case)}},
            "capabilities": {},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["calibration-artifact-integrity"][0]["severity"], "OK")

    def test_malformed_capability_entry_no_crash(self):
        """Audit F8 (robustness): non-object capability entries are diagnosed,
        never a crash."""
        pe = self._pine_exec_base()
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "capabilities": {"ta-sma": "CURRENT", "ok-cap": {
                "capability_status": "EXPERIMENTAL", "calibration_status": "MISSING"}},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["pinets-calibration"][0]
        self.assertEqual(finding["severity"], "WARNING")
        self.assertIn("ta-sma", finding["detail"])

    def test_pine_source_stamped_as_reference_flagged(self):
        """Targeted review 2026-09-06: a .pine case source must never count
        as an independent reference."""
        pe = self._pine_exec_base()
        case = pe / "calibration" / "case.pine"
        case.write_text("//@version=6\n", encoding="utf-8")
        from tools.pws_workspace import core as c
        (pe / "calibration" / "capabilities.json").write_text(json.dumps({
            "environment": {"pinets_version": "0.9.33"},
            "case_artifacts": {"case.pine": {
                "path": "case.pine", "sha256": c.sha256_file(case),
                "reference_provenance": "indument estampille"}},
            "capabilities": {"ta-x": {
                "capability_status": "EXPERIMENTAL",
                "calibration_status": "CURRENT",
                "evidence_artifacts": ["case.pine"]}},
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["calibration-reference-provenance"][0]
        self.assertEqual(finding["severity"], "WARNING")
        self.assertIn(".pine", finding["detail"])

    def test_baseline_absent_is_valid(self):
        results = by_check(doctor.run_doctor(self.root))
        finding = results["behavioral-baselines"][0]
        self.assertEqual(finding["severity"], "OK")
        self.assertIn("never created automatically", finding["detail"])

    def test_baseline_valid_ok(self):
        """Audit F6a: durable baselines are controlled by the doctor
        (temporary fixture — no product baseline is ever created for real)."""
        bdir = self.root / "scripts" / "prod-x" / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        (bdir / "base-1.json").write_text(json.dumps({
            "source_sha256": "a" * 64, "dataset_sha256": "b" * 64,
            "dataset_descriptor": {"type": "synthetic"},
            "normalized_payload_sha256": "c" * 64,
            "pinets_version": "0.9.33", "executor_fingerprint": "d" * 64,
            "normalization_schema": "pws-pinets-norm-v1", "configuration": {},
            "capabilities_used": {}, "acceptance_basis": "RICK_EXPLICIT_ACCEPTANCE",
            "accepted_at": "2026-09-05T10:00:00Z",
            "acceptance_evidence_ref": None,
            "acceptance_rationale": "decision explicite de the holder pour ce contexte precis",
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["baseline:prod-x/base-1.json"][0]["severity"], "OK")

    def test_baseline_malformed_blocking(self):
        bdir = self.root / "scripts" / "prod-y" / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        (bdir / "bad.json").write_text(json.dumps({
            "source_sha256": "zz", "acceptance_basis": "AUTO_PROMOTED",
        }), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-y/bad.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("missing field", finding["detail"])

    def test_baseline_null_identity_fields_blocking(self):
        """3rd external audit, item 3: essential fields set to null are a
        contract violation, not an accepted baseline."""
        bdir = self.root / "scripts" / "prod-n" / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        (bdir / "nulls.json").write_text(json.dumps({
            "source_sha256": "a" * 64, "dataset_sha256": "b" * 64,
            "dataset_descriptor": None, "normalized_payload_sha256": "c" * 64,
            "pinets_version": None, "executor_fingerprint": "d" * 64,
            "normalization_schema": None, "configuration": None,
            "capabilities_used": None,
            "acceptance_basis": "TRADINGVIEW_VALIDATED_SOURCE",
            "accepted_at": None,
            "acceptance_evidence_ref": "validation/evidence/ghost/absent.png",
            "acceptance_rationale": None}), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-n/nulls.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        for marker in ("dataset_descriptor", "pinets_version", "accepted_at"):
            self.assertIn(marker, finding["detail"])

    def test_baseline_dangling_evidence_ref_blocking(self):
        """3rd external audit, item 3: a TRADINGVIEW_VALIDATED_SOURCE baseline
        whose evidence reference does not exist is a broken proof."""
        bdir = self.root / "scripts" / "prod-e" / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        (bdir / "dangling.json").write_text(json.dumps({
            "source_sha256": "a" * 64, "dataset_sha256": "b" * 64,
            "dataset_descriptor": {"type": "synthetic"},
            "normalized_payload_sha256": "c" * 64,
            "pinets_version": "0.9.33", "executor_fingerprint": "d" * 64,
            "normalization_schema": "pws-pinets-norm-v2", "configuration": {},
            "capabilities_used": {},
            "acceptance_basis": "TRADINGVIEW_VALIDATED_SOURCE",
            "accepted_at": "2026-09-05T10:00:00Z",
            "acceptance_evidence_ref": "validation/evidence/ghost/absent.png",
            "acceptance_rationale": None}), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-e/dangling.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("does not exist", finding["detail"])

    def _tv_baseline_product(self, slug, accepted_sha, run_sha=None,
                             run_status="passed", ref="validation/runs/run-1.json"):
        """Product with a real TradingView run report + verified evidence and
        a TV-basis baseline referencing it."""
        from tools.pws_workspace import core as c
        from tools.tests import helpers as h
        product = self.root / "scripts" / slug
        bdir = product / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        evdir = product / "validation" / "evidence" / "run-1"
        evdir.mkdir(parents=True)
        (evdir / "proof.png").write_bytes(b"real proof bytes")
        run_report = h.full_run_report(
            "run-1", run_sha or accepted_sha, status=run_status,
            results={"compilation": run_status},
            evidence=[{"path": "evidence/run-1/proof.png", "type": "screenshot",
                       "sha256": c.sha256_file(evdir / "proof.png")}])
        runs = product / "validation" / "runs"
        runs.mkdir(parents=True)
        (runs / "run-1.json").write_text(json.dumps(run_report), encoding="utf-8")
        (product / "PRODUCT.md").write_text("# produit reel\n", encoding="utf-8")
        (bdir / "base.json").write_text(json.dumps({
            "source_sha256": accepted_sha, "dataset_sha256": "b" * 64,
            "dataset_descriptor": {"type": "synthetic"},
            "normalized_payload_sha256": "c" * 64,
            "pinets_version": "0.9.33", "executor_fingerprint": "d" * 64,
            "normalization_schema": "pws-pinets-norm-v2", "configuration": {},
            "capabilities_used": {},
            "acceptance_basis": "TRADINGVIEW_VALIDATED_SOURCE",
            "accepted_at": "2026-09-05T10:00:00Z",
            "acceptance_evidence_ref": ref,
            "acceptance_rationale": None}), encoding="utf-8")
        return product

    def test_baseline_tv_basis_with_matching_run_ok(self):
        """A historical passed run of the SAME accepted sha, with verified
        evidence, is a valid acceptance proof (the product's current source
        is irrelevant)."""
        self._tv_baseline_product("prod-ok", "a" * 64)
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["baseline:prod-ok/base.json"][0]["severity"], "OK")

    def test_baseline_arbitrary_file_as_evidence_blocking(self):
        """4th external audit, item 2: PRODUCT.md existing is not a proof."""
        self._tv_baseline_product("prod-weak", "a" * 64, ref="PRODUCT.md")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-weak/base.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("validation/runs/", finding["detail"])

    def test_baseline_ref_traversal_inside_lexical_prefix_blocking(self):
        """A ref like validation/runs/../evidence/x.json passes the lexical
        prefix but must be refused by resolved containment."""
        product = self._tv_baseline_product("prod-trav", "a" * 64)
        sneaky = product / "validation" / "evidence" / "sneaky.json"
        sneaky.write_text("{}", encoding="utf-8")
        base = product / "tests" / "behavioral" / "baselines" / "base.json"
        data = json.loads(base.read_text(encoding="utf-8"))
        data["acceptance_evidence_ref"] = "validation/runs/../evidence/sneaky.json"
        base.write_text(json.dumps(data), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-trav/base.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")

    def test_baseline_sha_mismatch_blocking(self):
        """The referenced run must validate the SAME source_sha256 the
        baseline accepts."""
        self._tv_baseline_product("prod-mismatch", "a" * 64, run_sha="e" * 64)
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-mismatch/base.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("does not match the baseline", finding["detail"])

    def test_baseline_non_passed_run_blocking(self):
        self._tv_baseline_product("prod-failedrun", "a" * 64, run_status="failed")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-failedrun/base.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("passed", finding["detail"])

    def test_baseline_tampered_run_evidence_blocking(self):
        product = self._tv_baseline_product("prod-tamper", "a" * 64)
        (product / "validation" / "evidence" / "run-1" / "proof.png").write_bytes(
            b"tampered")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-tamper/base.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("hash diverges", finding["detail"])

    def test_baseline_tv_basis_requires_evidence(self):
        bdir = self.root / "scripts" / "prod-z" / "tests" / "behavioral" / "baselines"
        bdir.mkdir(parents=True)
        base = {
            "source_sha256": "a" * 64, "dataset_sha256": "b" * 64,
            "dataset_descriptor": {}, "normalized_payload_sha256": "c" * 64,
            "pinets_version": "0.9.33", "executor_fingerprint": "d" * 64,
            "normalization_schema": "pws-pinets-norm-v1", "configuration": {},
            "capabilities_used": {},
            "acceptance_basis": "TRADINGVIEW_VALIDATED_SOURCE",
            "accepted_at": "2026-09-05T10:00:00Z",
            "acceptance_evidence_ref": None, "acceptance_rationale": None,
        }
        (bdir / "no-evidence.json").write_text(json.dumps(base), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["baseline:prod-z/no-evidence.json"][0]
        self.assertEqual(finding["severity"], "BLOCKING")
        self.assertIn("acceptance_evidence_ref", finding["detail"])

    def test_malformed_shapes_never_crash_the_doctor(self):
        """Adversarial review 2026-09-05: valid-JSON wrong-shape inputs must
        yield actionable diagnostics, never AttributeError/TypeError — the
        doctor is the detection net for the settings external writer."""
        cases = [
            (".claude/settings.json", "[]"),
            (".claude/settings.local.json", "[]"),
            (".claude/settings.local.json", '{"env": "manual"}'),
            ("tools/pine_exec/package.json", "[]"),
            ("tools/pine_exec/package.json", '{"dependencies": {"pinets": 5}}'),
            ("tools/pine_exec/package.json", '{"dependencies": []}'),
        ]
        for rel, payload in cases:
            root = make_minimal_root(self.tmp.name)
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
            results = doctor.run_doctor(root)  # must not raise
            self.assertTrue(results, (rel, payload))

    def test_malformed_lockfile_and_provenance_no_crash(self):
        pe = self._pine_exec_base()
        (pe / "package-lock.json").write_text("[]", encoding="utf-8")
        (pe / "PROVENANCE.json").write_text("[]", encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        self.assertEqual(results["pinets-lockfile"][0]["severity"], "BLOCKING")
        self.assertEqual(results["pinets-provenance"][0]["severity"], "WARNING")

    def test_missing_node_is_limitation_not_blocking(self):
        """pine_exec configured but node_modules absent -> INFO, never a
        defect of any Pine source (spec section 6.1)."""
        pe = self.root / "tools" / "pine_exec"
        pe.mkdir(parents=True)
        (pe / "package.json").write_text(json.dumps(
            {"dependencies": {"pinets": "0.9.33"}}), encoding="utf-8")
        (pe / "package-lock.json").write_text(json.dumps(
            {"packages": {"node_modules/pinets": {"version": "0.9.33"}}}), encoding="utf-8")
        results = by_check(doctor.run_doctor(self.root))
        finding = results["pinets-installed"][0]
        self.assertEqual(finding["severity"], "INFO")
        self.assertIn("npm ci", finding["detail"])


if __name__ == "__main__":
    unittest.main()
