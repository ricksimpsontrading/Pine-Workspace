# SPDX-License-Identifier: Apache-2.0
"""Validation state machine and promotion protocol (spec sections 51, 61.7).

Includes the corrective-pass regressions (audit 2026-09-05): unified
mechanical owner (no false `passed`), lock-serialized promotions, safe run
identifiers and physical confinement.
"""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tools.pws_workspace import core, validation
from tools.tests import helpers


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, run_id="run-a", status="passed", completed="2026-09-04T10:00:00Z",
                sha=None):
        return helpers.full_run_report(
            run_id, sha or core.sha256_file(self.source),
            status=status, completed_at=completed,
            started_at="2026-09-04T00:00:00Z")

    def test_init_idempotent(self):
        first = validation.init_validation_state(self.pdir)
        self.assertTrue(first["created"])
        second = validation.init_validation_state(self.pdir)
        self.assertFalse(second["created"])

    def test_promote_and_status(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir, self._report(), snapshot)
        self.assertTrue(res["promoted"], res)
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["persisted"], "passed")
        self.assertEqual(view["integrity"], "OK")
        self.assertEqual(view["effective"], "passed")

    def test_stale_after_source_change(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        validation.promote_run(self.pdir, self._report(), snapshot)
        self.source.write_text(self.source.read_text(encoding="utf-8") + "// v2\n",
                               encoding="utf-8")
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["effective"], "stale")
        self.assertEqual(view["persisted"], "passed")  # never persisted as stale

    def test_older_run_refused(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        validation.promote_run(self.pdir, self._report("run-new", completed="2026-09-04T12:00:00Z"),
                               snapshot)
        snapshot2 = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir,
                                     self._report("run-old", completed="2026-09-04T09:00:00Z"),
                                     snapshot2)
        self.assertFalse(res["promoted"])
        self.assertIn("older", res["conflict"])
        current = json.loads((self.pdir / "validation" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(current["last_run"]["run_id"], "run-new")

    def test_clock_tie_is_actionable_conflict(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        validation.promote_run(self.pdir, self._report("run-1", completed="2026-09-04T12:00:00Z"),
                               snapshot)
        snapshot2 = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir,
                                     self._report("run-2", completed="2026-09-04T12:00:00Z"),
                                     snapshot2)
        self.assertFalse(res["promoted"])
        self.assertIn("tie", res["conflict"])

    def test_concurrent_pointer_change_refused(self):
        validation.init_validation_state(self.pdir)
        stale_snapshot = b'{"schema_version": 1, "status": "unverified", "last_run": null}\n'
        # actual file differs from the snapshot taken "at run start"
        core.atomic_write_json(self.pdir / "validation" / "current.json", {
            "schema_version": 1, "status": "in-progress", "last_run": None})
        res = validation.promote_run(self.pdir, self._report("run-c"), stale_snapshot)
        self.assertFalse(res["promoted"])
        self.assertIn("changed since the run started", res["conflict"])

    def test_report_immutability(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        validation.promote_run(self.pdir, self._report("run-imm"), snapshot)
        snapshot2 = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir, self._report("run-imm",
                                     completed="2026-09-04T13:00:00Z"), snapshot2)
        self.assertFalse(res["promoted"])
        self.assertIn("immutable", res["conflict"])

    def test_missing_report_never_passed(self):
        validation.init_validation_state(self.pdir)
        core.atomic_write_json(self.pdir / "validation" / "current.json", {
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "ghost", "report": "runs/ghost.json",
                         "source_sha256": "0" * 64,
                         "completed_at": "2026-09-04T10:00:00Z"}})
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])

    def test_incomplete_report_rejected(self):
        validation.init_validation_state(self.pdir)
        snapshot = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir, {"run_id": "run-x"}, snapshot)
        self.assertFalse(res["promoted"])

    def test_source_fingerprint(self):
        fp = validation.source_fingerprint(self.root, self.source)
        self.assertEqual(len(fp["source_sha256"]), 64)


class TestUnifiedOwner(unittest.TestCase):
    """Audit F1: scan and validation-status share ONE mechanical owner —
    incoherent states are BROKEN everywhere, never a false `passed`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        (self.pdir / "validation").mkdir(exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_current(self, data):
        (self.pdir / "validation" / "current.json").write_text(
            json.dumps(data), encoding="utf-8")

    def _both_views(self):
        from tools.pws_workspace import scan
        view = validation.validation_status(self.pdir, self.source)
        s = scan.scan_workspace(self.root)
        p = next(x for x in s["products"] if x["slug"] == "my-indicator")
        return view, p

    def test_passed_without_run_is_broken_everywhere(self):
        self._write_current({"schema_version": 1, "status": "passed", "last_run": None})
        view, p = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])
        self.assertEqual(p["validation_integrity_status"], "BROKEN")
        self.assertIsNone(p["validation_effective_status"])
        self.assertIn("VALIDATION_STATUS_RUN_MISSING",
                      [f["code"] for f in view["findings"]])

    def test_unverified_with_run_is_broken(self):
        self._write_current({"schema_version": 1, "status": "unverified",
                             "last_run": {"run_id": "run-x", "report": "runs/run-x.json",
                                          "source_sha256": "0" * 64,
                                          "completed_at": "2026-09-05T10:00:00Z"}})
        view, _ = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")

    def test_passed_pointer_to_failed_report_is_broken(self):
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "runs").mkdir()
        (self.pdir / "validation" / "runs" / "run-f.json").write_text(json.dumps(
            helpers.full_run_report("run-f", sha, status="failed")), encoding="utf-8")
        self._write_current({"schema_version": 1, "status": "passed",
                             "last_run": {"run_id": "run-f", "report": "runs/run-f.json",
                                          "source_sha256": sha,
                                          "completed_at": "2026-09-05T10:00:00Z"}})
        view, p = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])
        self.assertIsNone(p["validation_effective_status"])
        self.assertIn("VALIDATION_STATUS_INCOHERENT",
                      [f["code"] for f in view["findings"]])

    def test_missing_evidence_broken_in_both_readers(self):
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "runs").mkdir()
        (self.pdir / "validation" / "runs" / "run-e.json").write_text(json.dumps(
            helpers.full_run_report("run-e", sha, evidence=[
                {"path": "evidence/run-e/absent.png", "sha256": "a" * 64,
                 "type": "screenshot"}])),
            encoding="utf-8")
        self._write_current({"schema_version": 1, "status": "passed",
                             "last_run": {"run_id": "run-e", "report": "runs/run-e.json",
                                          "source_sha256": sha,
                                          "completed_at": "2026-09-05T10:00:00Z"}})
        view, p = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])  # pine-release can never see passed
        self.assertEqual(p["validation_integrity_status"], "BROKEN")

    def test_invalid_schema_version_broken(self):
        self._write_current({"schema_version": "1", "status": "unverified",
                             "last_run": None})
        view, _ = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")

    def test_evidence_wrong_types_broken_not_crash(self):
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "runs").mkdir()
        (self.pdir / "validation" / "runs" / "run-t.json").write_text(json.dumps(
            helpers.full_run_report("run-t", sha, evidence=["not-an-object"])),
            encoding="utf-8")
        self._write_current({"schema_version": 1, "status": "passed",
                             "last_run": {"run_id": "run-t", "report": "runs/run-t.json",
                                          "source_sha256": sha,
                                          "completed_at": "2026-09-05T10:00:00Z"}})
        view, _ = self._both_views()
        self.assertEqual(view["integrity"], "BROKEN")


class TestValidationDirBoundary(unittest.TestCase):
    """Adversarial review 2026-09-05 (BLOCKING): a symlinked validation/
    directory must be refused on every read and write path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, pdir, run_id="run-s"):
        return helpers.full_run_report(
            run_id, core.sha256_file(pdir / "My Indicator.pine"))

    def test_cross_product_symlink_never_passed(self):
        import os
        pa = helpers.make_product(self.root, slug="prod-a", with_validation=False)
        validation.init_validation_state(pa)
        snap = (pa / "validation" / "current.json").read_bytes()
        self.assertTrue(validation.promote_run(pa, self._report(pa), snap)["promoted"])
        pb = helpers.make_product(self.root, slug="prod-b", with_validation=False)
        os.symlink(pa / "validation", pb / "validation")
        view = validation.validation_status(pb, pb / "My Indicator.pine")
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])
        self.assertIn("VALIDATION_DIR_SYMLINK",
                      [f["code"] for f in view["findings"]])
        from tools.pws_workspace import scan
        s = scan.scan_workspace(self.root)
        p = next(x for x in s["products"] if x["slug"] == "prod-b")
        self.assertEqual(p["validation_integrity_status"], "BROKEN")
        self.assertIsNone(p["validation_effective_status"])

    def test_external_symlink_write_refused(self):
        import os
        outside = Path(self.tmp.name) / "outside validation"
        outside.mkdir()
        pdir = helpers.make_product(self.root, slug="prod-x", with_validation=False)
        os.symlink(outside, pdir / "validation")
        init = validation.init_validation_state(pdir)
        self.assertFalse(init["created"])
        self.assertIn("symlink", init["reason"])
        res = validation.promote_run(pdir, self._report(pdir), None)
        self.assertFalse(res["promoted"])
        self.assertIn("symlink", res["conflict"])
        self.assertEqual(list(outside.iterdir()), [], "nothing written outside")

    def test_symlinked_current_json_refused(self):
        import os
        pdir = helpers.make_product(self.root, slug="prod-c", with_validation=False)
        (pdir / "validation").mkdir()
        target = Path(self.tmp.name) / "elsewhere.json"
        target.write_text(json.dumps({"schema_version": 1, "status": "unverified",
                                      "last_run": None}), encoding="utf-8")
        os.symlink(target, pdir / "validation" / "current.json")
        view = validation.validation_status(pdir, pdir / "My Indicator.pine")
        self.assertEqual(view["integrity"], "BROKEN")


class TestReportPointerForm(unittest.TestCase):
    """Adversarial review: the recognized report must be exactly
    runs/<run_id>.json — a self-referential or loose report is BROKEN."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        (self.pdir / "validation").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_self_referential_current_json_broken(self):
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "run_id": "run-self", "source_sha256": sha,
            "completed_at": "2026-09-05T10:00:00Z",
            "last_run": {"run_id": "run-self", "report": "current.json",
                         "source_sha256": sha,
                         "completed_at": "2026-09-05T10:00:00Z"}}), encoding="utf-8")
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIn("VALIDATION_REPORT_PATH_FORM",
                      [f["code"] for f in view["findings"]])

    def test_loose_report_path_broken(self):
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "loose.json").write_text(json.dumps({
            "run_id": "run-l", "status": "passed", "source_sha256": sha,
            "completed_at": "2026-09-05T10:00:00Z"}), encoding="utf-8")
        (self.pdir / "validation" / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-l", "report": "loose.json",
                         "source_sha256": sha,
                         "completed_at": "2026-09-05T10:00:00Z"}}), encoding="utf-8")
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")

    def test_evidence_outside_run_dir_broken(self):
        sha = core.sha256_file(self.source)
        vdir = self.pdir / "validation"
        (vdir / "runs").mkdir()
        (vdir / "note.txt").write_text("x", encoding="utf-8")
        (vdir / "runs" / "run-p.json").write_text(json.dumps(
            helpers.full_run_report("run-p", sha, evidence=[
                {"path": "note.txt", "type": "note",
                 "sha256": core.sha256_file(vdir / "note.txt")}])),
            encoding="utf-8")
        (vdir / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-p", "report": "runs/run-p.json",
                         "source_sha256": sha,
                         "completed_at": "2026-09-05T10:00:00Z"}}), encoding="utf-8")
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIn("VALIDATION_REPORT_INCOMPLETE",
                      [f["code"] for f in view["findings"]])
        self.assertIn("evidence path", view["detail"])


class TestPromotionBoundaries(unittest.TestCase):
    """Audit F3a: unsafe run ids never write outside validation/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        validation.init_validation_state(self.pdir)

    def tearDown(self):
        self.tmp.cleanup()

    def _promote(self, run_id):
        snap = (self.pdir / "validation" / "current.json").read_bytes()
        return validation.promote_run(self.pdir, helpers.full_run_report(
            run_id, core.sha256_file(self.source)), snap)

    def test_traversal_run_id_refused(self):
        res = self._promote("../../escaped")
        self.assertFalse(res["promoted"])
        self.assertIn("safe identifier", res["conflict"])
        self.assertFalse((self.pdir / "escaped.json").exists())
        self.assertFalse((self.root / "escaped.json").exists())

    def test_deep_traversal_refused(self):
        res = self._promote("../../../../escape2")
        self.assertFalse(res["promoted"])
        self.assertFalse((self.root / "escape2.json").exists())

    def test_absolute_and_weird_ids_refused(self):
        for bad in ("/abs", "a/b", "", None, 42, "." , ".."):
            res = self._promote(bad)
            self.assertFalse(res["promoted"], bad)

    def test_safe_id_accepted(self):
        res = self._promote(validation.new_run_id())
        self.assertTrue(res["promoted"], res)


class TestRunReportContract(unittest.TestCase):
    """3rd external audit, items 1, 2, 6, 7 — shared spec-51.4 contract."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        validation.init_validation_state(self.pdir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_incomplete_report_promotion_refused(self):
        """Item 1 (mutation path): a minimal report is never promoted."""
        snap = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(self.pdir, {
            "run_id": "run-min", "status": "passed",
            "source_sha256": core.sha256_file(self.source),
            "completed_at": "2026-09-05T10:00:00Z"}, snap)
        self.assertFalse(res["promoted"])
        self.assertIn("51.4", res["conflict"])
        self.assertFalse((self.pdir / "validation" / "runs").exists())

    def test_incomplete_report_on_disk_is_broken(self):
        """Item 1 (read path): an incomplete report already on disk is
        integrity BROKEN, never trusted as passed."""
        sha = core.sha256_file(self.source)
        (self.pdir / "validation" / "runs").mkdir()
        (self.pdir / "validation" / "runs" / "run-min.json").write_text(json.dumps({
            "run_id": "run-min", "status": "passed", "source_sha256": sha,
            "completed_at": "2026-09-05T10:00:00Z"}), encoding="utf-8")
        core.atomic_write_json(self.pdir / "validation" / "current.json", {
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-min", "report": "runs/run-min.json",
                         "source_sha256": sha,
                         "completed_at": "2026-09-05T10:00:00Z"}})
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])
        self.assertIn("VALIDATION_REPORT_INCOMPLETE",
                      [f["code"] for f in view["findings"]])

    def test_each_missing_required_key_refused(self):
        """Common contract, not example-matching: every required key absent
        individually causes refusal."""
        sha = core.sha256_file(self.source)
        for key in validation.RUN_REPORT_REQUIRED_KEYS:
            report = helpers.full_run_report("run-k", sha)
            del report[key]
            problems = validation.validate_run_report(report)
            self.assertTrue(problems, "missing %s must be a problem" % key)

    def test_deleted_source_never_effectively_passed(self):
        """Item 2: a promoted passed state with a deleted source yields an
        indeterminable effective status in BOTH readers."""
        snap = (self.pdir / "validation" / "current.json").read_bytes()
        res = validation.promote_run(
            self.pdir, helpers.full_run_report(
                "run-d", core.sha256_file(self.source)), snap)
        self.assertTrue(res["promoted"], res)
        self.source.unlink()
        view = validation.validation_status(self.pdir, self.source)
        self.assertIsNone(view["effective"])
        self.assertIn("VALIDATION_SOURCE_UNAVAILABLE",
                      [f["code"] for f in view["findings"]])
        view_none = validation.validation_status(self.pdir, None)
        self.assertIsNone(view_none["effective"])
        from tools.pws_workspace import scan
        s = scan.scan_workspace(self.root)
        p = next(x for x in s["products"] if x["slug"] == "my-indicator")
        self.assertNotEqual(p["validation_effective_status"], "passed")

    def test_current_json_list_is_conflict_not_crash(self):
        """Item 7: a list-shaped current.json yields an actionable conflict."""
        core.atomic_write_text(self.pdir / "validation" / "current.json", "[1, 2]\n")
        res = validation.promote_run(
            self.pdir, helpers.full_run_report(
                "run-l", core.sha256_file(self.source)), None)
        self.assertFalse(res["promoted"])
        self.assertIn("not a JSON object", res["conflict"])

    def test_corrupt_previous_run_shapes_refuse_not_crash(self):
        """Targeted review 2026-09-06 (BLOCKING): non-dict recognized report,
        non-dict last_run and unparseable previous completed_at must all
        refuse with an actionable conflict — never crash, never let an older
        run replace the recognized one."""
        sha = core.sha256_file(self.source)
        vdir = self.pdir / "validation"
        (vdir / "runs").mkdir(exist_ok=True)

        def set_current(last_run):
            core.atomic_write_json(vdir / "current.json", {
                "schema_version": 1, "status": "passed", "last_run": last_run})

        # (a) recognized report is a JSON list / string
        for shape in ("[1, 2]", '"abc"'):
            (vdir / "runs" / "run-prev.json").write_text(shape, encoding="utf-8")
            set_current({"run_id": "run-prev", "report": "runs/run-prev.json",
                         "source_sha256": sha,
                         "completed_at": "2026-09-05T12:00:00Z"})
            res = validation.promote_run(
                self.pdir, helpers.full_run_report("run-new-%d" % len(shape), sha),
                None)
            self.assertFalse(res["promoted"], shape)
            self.assertIn("not a JSON object", res["conflict"])
        # (b) last_run itself is a string -> order cannot be established
        set_current("runs/run-prev.json")
        res = validation.promote_run(
            self.pdir, helpers.full_run_report(
                "run-old", sha, completed_at="2026-09-04T08:00:00Z",
                started_at="2026-09-04T07:00:00Z"), None)
        self.assertFalse(res["promoted"])
        self.assertIn("run order cannot be established", res["conflict"])
        # (c) previous completed_at unparseable
        (vdir / "runs" / "run-prev.json").write_text(json.dumps(
            helpers.full_run_report("run-prev", sha, completed_at="garbage")),
            encoding="utf-8")
        set_current({"run_id": "run-prev", "report": "runs/run-prev.json",
                     "source_sha256": sha, "completed_at": "2026-09-05T12:00:00Z"})
        res = validation.promote_run(
            self.pdir, helpers.full_run_report(
                "run-old2", sha, completed_at="2026-09-04T08:00:00Z",
                started_at="2026-09-04T07:00:00Z"), None)
        self.assertFalse(res["promoted"])
        self.assertIn("parseable", res["conflict"])
        final = json.loads((vdir / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(final["last_run"]["run_id"], "run-prev",
                         "the recognized run must never be replaced by an older one")

    def test_promotion_refuses_dangling_evidence(self):
        """Targeted review 2026-09-06: the mutation path also verifies the
        physical proofs — a report referencing absent evidence is refused,
        not promoted into an instantly-BROKEN state."""
        res = validation.promote_run(self.pdir, helpers.full_run_report(
            "run-ev", core.sha256_file(self.source),
            evidence=[{"path": "evidence/run-ev/absent.png", "sha256": "a" * 64,
                       "type": "screenshot"}]), None)
        self.assertFalse(res["promoted"])
        self.assertIn("missing", res["conflict"])
        self.assertFalse((self.pdir / "validation" / "runs").exists())

    def test_vacuous_completed_reports_refused(self):
        """Targeted review 2026-09-06: whitespace conclusion and a completed
        run with zero applied controls violate the contract."""
        sha = core.sha256_file(self.source)
        blank = helpers.full_run_report("run-b", sha, conclusion="   ")
        self.assertTrue(any("conclusion" in p
                            for p in validation.validate_run_report(blank)))
        vacuous = helpers.full_run_report("run-v", sha, matrix=[], results={})
        self.assertTrue(any("applicable control" in p
                            for p in validation.validate_run_report(vacuous)))
        sparse_ok = helpers.full_run_report("run-i", sha, status="in-progress",
                                            matrix=[], results={})
        self.assertEqual(validation.validate_run_report(sparse_ok), [])

    def test_results_must_cover_applicable_controls(self):
        """4th external audit, item 1: results=[] (or uncovered controls) on a
        completed run is refused everywhere — a validation without recorded
        results is never trusted as passed."""
        sha = core.sha256_file(self.source)
        empty = helpers.full_run_report("run-e1", sha, results=[])
        problems = validation.validate_run_report(empty)
        self.assertTrue(any("results must be an object" in p for p in problems))
        res = validation.promote_run(self.pdir, empty, None)
        self.assertFalse(res["promoted"])
        # version-1 read path (historical reports): free-text outcomes
        uncovered = helpers.full_run_report_v1(
            "run-e2", sha,
            matrix=[{"test": "compilation", "applicable": True},
                    {"test": "realtime", "applicable": True},
                    {"test": "alerts", "applicable": False}],
            results={"compilation": "passed"})
        problems = validation.validate_run_report(uncovered)
        self.assertTrue(any("without a recorded result" in p and "realtime" in p
                            for p in problems))
        # a non-applicable control needs no result; a recorded manual
        # observation is an admissible outcome
        covered = helpers.full_run_report_v1(
            "run-e3", sha,
            matrix=[{"test": "compilation", "applicable": True},
                    {"test": "realtime", "applicable": True},
                    {"test": "alerts", "applicable": False}],
            results={"compilation": "passed",
                     "realtime": "observation the holder: signaux stables 30 min"})
        self.assertEqual(validation.validate_run_report(covered), [])

    def test_passed_incoherent_with_failed_result(self):
        sha = core.sha256_file(self.source)
        incoherent = helpers.full_run_report_v1(
            "run-f1", sha, results={"compilation": "failed"})
        problems = validation.validate_run_report(incoherent)
        self.assertTrue(any("incoherent" in p for p in problems))
        # a failure recorded OUTSIDE the matrix must not hide (wave-4 review)
        off_matrix = helpers.full_run_report_v1(
            "run-f2", sha,
            results={"compilation": "passed", "runtime": "failed"})
        problems = validation.validate_run_report(off_matrix)
        self.assertTrue(any("incoherent" in p and "runtime" in p
                            for p in problems))

    def test_evidence_traversal_segment_refused(self):
        """Wave-4 review: evidence must live in its OWN run namespace —
        'evidence/run-x/../run-y/…' is refused structurally."""
        sha = core.sha256_file(self.source)
        rep = helpers.full_run_report("run-x", sha, evidence=[
            {"path": "evidence/run-x/../run-y/proof.png", "sha256": "a" * 64,
             "type": "screenshot"}])
        problems = validation.validate_run_report(rep)
        self.assertTrue(any("traversal segment" in p for p in problems))
        res = validation.promote_run(self.pdir, rep, None)
        self.assertFalse(res["promoted"])

    def test_null_matrix_diagnosed_not_crash(self):
        """4th external audit, item 1: matrix=null must yield a diagnostic,
        never a TypeError."""
        sha = core.sha256_file(self.source)
        for override in ({"matrix": None}, {"results": None},
                         {"matrix": "x"}, {"results": 5},
                         {"matrix": [None]}, {"matrix": [{"test": "", "applicable": True}]},
                         {"results": {"compilation": None}},
                         {"results": {"": "passed"}}):
            rep = helpers.full_run_report("run-n", sha, **override)
            problems = validation.validate_run_report(rep)  # must not raise
            self.assertTrue(problems, override)
        on_disk = helpers.full_run_report("run-nd", sha, matrix=None)
        (self.pdir / "validation" / "runs").mkdir(exist_ok=True)
        (self.pdir / "validation" / "runs" / "run-nd.json").write_text(
            json.dumps(on_disk), encoding="utf-8")
        core.atomic_write_json(self.pdir / "validation" / "current.json", {
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-nd", "report": "runs/run-nd.json",
                         "source_sha256": sha,
                         "completed_at": on_disk["completed_at"]}})
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["integrity"], "BROKEN")
        self.assertIsNone(view["effective"])

    def test_symlinked_product_root_mutations_refused(self):
        """Item 6: init/promote through a symlinked product root never write
        outside."""
        import os
        outside = Path(self.tmp.name) / "outside product"
        outside.mkdir()
        link = self.root / "scripts" / "linked"
        os.symlink(outside, link)
        init = validation.init_validation_state(link)
        self.assertFalse(init["created"])
        self.assertIn("symlink", init["reason"])
        res = validation.promote_run(link, helpers.full_run_report(
            "run-s", "a" * 64), None)
        self.assertFalse(res["promoted"])
        self.assertIn("symlink", res["conflict"])
        self.assertEqual(list(outside.iterdir()), [], "nothing written outside")


class TestPromotionConcurrency(unittest.TestCase):
    """Audit F2a: the promotion transaction is serialized — an older run can
    never end up recognized after a newer promotion succeeded."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        validation.init_validation_state(self.pdir)
        self.sha = core.sha256_file(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, run_id, completed):
        return helpers.full_run_report(run_id, self.sha, completed_at=completed,
                                       started_at="2026-09-04T07:00:00Z")

    def test_init_serialized_with_promotion_lock(self):
        """Adversarial review: init must share the promotion lock — a
        concurrent first promotion is never silently reset to unverified."""
        fresh = helpers.make_product(self.root, slug="init-race",
                                     with_validation=False)
        (fresh / "validation").mkdir()
        results = {}

        def init():
            results["init"] = validation.init_validation_state(fresh)

        with core.file_lock(validation._lock_path(fresh)):
            t = threading.Thread(target=init)
            t.start()
            time.sleep(0.3)
            self.assertTrue(t.is_alive(), "init must wait for the shared lock")
            # promotion completes first (we hold its lock, write current.json)
            core.atomic_write_json(fresh / "validation" / "current.json", {
                "schema_version": 1, "status": "in-progress", "last_run": None})
        t.join(15)
        self.assertFalse(results["init"]["created"],
                         "init must not overwrite the state written first")
        persisted = json.loads((fresh / "validation" / "current.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "in-progress")

    def test_promotion_blocks_while_lock_held(self):
        lock_path = validation._lock_path(self.pdir)
        results = {}

        def promote():
            results["res"] = validation.promote_run(
                self.pdir, self._report("run-lock", "2026-09-05T12:00:00Z"), None)

        with core.file_lock(lock_path):
            t = threading.Thread(target=promote)
            t.start()
            time.sleep(0.3)
            self.assertTrue(t.is_alive(), "promotion must wait for the lock")
        t.join(15)
        self.assertTrue(results["res"]["promoted"], results)

    def test_interleaved_promotions_never_end_on_older_run(self):
        for i in range(10):
            pdir = helpers.make_product(self.root, slug="race-%d" % i,
                                        with_validation=False)
            validation.init_validation_state(pdir)
            sha = core.sha256_file(pdir / "My Indicator.pine")
            outcomes = {}

            def promote(tag, run_id, completed):
                outcomes[tag] = validation.promote_run(
                    pdir, helpers.full_run_report(run_id, sha, completed_at=completed,
                                                  started_at="2026-09-04T07:00:00Z"),
                    None)

            t_new = threading.Thread(target=promote,
                                     args=("new", "run-new", "2026-09-05T12:00:00Z"))
            t_old = threading.Thread(target=promote,
                                     args=("old", "run-old", "2026-09-04T08:00:00Z"))
            t_new.start(); t_old.start()
            t_new.join(15); t_old.join(15)
            final = json.loads((pdir / "validation" / "current.json")
                               .read_text(encoding="utf-8"))
            final_id = (final.get("last_run") or {}).get("run_id")
            self.assertTrue(outcomes["new"]["promoted"], outcomes)
            # invariant: after a successful newer promotion, the recognized
            # run is NEVER the older one (either it was refused, or it landed
            # first and was legitimately replaced)
            self.assertEqual(final_id, "run-new", outcomes)


class TestRunReportV2(unittest.TestCase):
    """Maintenance 2026-09 (spec sections 30.4, 30.5, 51.3-51.5): controlled
    verdicts, failed priority, coverage, unique identifiers, groups, minimal
    compilation, historical version-1 reports."""

    MATRIX = [{"id": "T1", "test": "compilation", "applicable": True},
              {"id": "T2", "test": "replay", "applicable": True},
              {"id": "T3", "test": "strategy report", "applicable": False}]
    STATUSES = ("passed", "partial", "failed", "in-progress")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pdir = helpers.make_product(self.root, with_validation=False)
        self.source = self.pdir / "My Indicator.pine"
        self.sha = core.sha256_file(self.source)
        validation.init_validation_state(self.pdir)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, status, results, run_id="run-v2", **extra):
        import copy
        return helpers.full_run_report(
            run_id, self.sha, status=status,
            matrix=copy.deepcopy(extra.pop("matrix", self.MATRIX)),
            results=results, **extra)

    def _admitted(self, results, **extra):
        return [s for s in self.STATUSES
                if validation.validate_run_report(
                    self._report(s, dict(results), **extra)) == []]

    def test_v2a_v2b_v2c_passed_refused_with_any_non_passed_verdict(self):
        for other in ("not-run", "indeterminate", "failed"):
            admitted = self._admitted({"T1": "passed", "T2": other})
            self.assertNotIn("passed", admitted, other)

    def test_v2d_coherent_partial_accepted(self):
        self.assertEqual(self._admitted({"T1": "passed", "T2": "not-run"}),
                         ["partial", "in-progress"])
        self.assertEqual(self._admitted({"T1": "passed", "T2": "indeterminate"}),
                         ["partial", "in-progress"])

    def test_all_passed_admits_passed(self):
        self.assertEqual(self._admitted({"T1": "passed", "T2": "passed"}),
                         ["passed", "in-progress"])
        # an explicit n-a on the non-applicable control is admitted
        self.assertEqual(
            self._admitted({"T1": "passed", "T2": "passed", "T3": "n-a"}),
            ["passed", "in-progress"])

    def test_v2e_verdict_outside_enumeration_or_free_text_refused(self):
        for bad in ("failed — compilation error", "not executed",
                    "non effectue", "ok", "", None, 1):
            rep = self._report("passed", {"T1": "passed", "T2": "passed"})
            rep["results"]["T2"] = helpers.v2_result("passed")
            rep["results"]["T2"]["verdict"] = bad
            self.assertTrue(validation.validate_run_report(rep), bad)
        free_text = self._report("passed", {"T1": "passed"})
        free_text["results"]["T2"] = "passed according to the holder"
        self.assertTrue(any("free text" in p for p in
                            validation.validate_run_report(free_text)))

    def test_na_reserved_to_non_applicable_controls(self):
        rep = self._report("passed", {"T1": "passed", "T2": "n-a"})
        self.assertTrue(any("not admitted" in p
                            for p in validation.validate_run_report(rep)))
        rep = self._report("passed", {"T1": "passed", "T2": "passed", "T3": "passed"})
        self.assertTrue(any("not admitted" in p
                            for p in validation.validate_run_report(rep)))

    def test_v2f_unreported_control_without_failure_only_in_progress(self):
        self.assertEqual(self._admitted({"T1": "passed"}), ["in-progress"])
        rep = self._report("passed", {"T1": "passed"})
        self.assertTrue(any("not reported" in p and "T2" in p
                            for p in validation.validate_run_report(rep)))

    def test_v2g_v2h_v2l_nothing_passed_only_in_progress(self):
        self.assertEqual(self._admitted({}), ["in-progress"])
        self.assertEqual(self._admitted({"T1": "not-run", "T2": "not-run"}),
                         ["in-progress"])
        self.assertEqual(
            self._admitted({"T1": "indeterminate", "T2": "indeterminate"}),
            ["in-progress"])

    def test_v2i_v2j_failed_is_never_hidden_by_missing_results(self):
        self.assertEqual(self._admitted({"T1": "failed"}), ["failed"])
        self.assertEqual(self._admitted({"T1": "failed", "T2": "not-run"}),
                         ["failed"])
        self.assertEqual(self._admitted({"T1": "passed", "T2": "failed"}),
                         ["failed"])
        res = validation.promote_run(
            self.pdir, self._report("failed", {"T1": "failed"}), None)
        self.assertTrue(res["promoted"], res)
        self.assertEqual(res["unreported_controls"], ["T2"])
        self.assertTrue(any("not reported" in n for n in res["notes"]))

    def test_v2k_unknown_or_duplicate_control_id_refused(self):
        rep = self._report("passed", {"T1": "passed", "T2": "passed",
                                      "T9": "passed"})
        self.assertTrue(any("absent from the matrix" in p
                            for p in validation.validate_run_report(rep)))
        dup = self._report("passed", {"T1": "passed"},
                           matrix=[{"id": "T1", "test": "a", "applicable": True},
                                   {"id": "T1", "test": "b", "applicable": True}])
        self.assertTrue(any("duplicate control id" in p
                            for p in validation.validate_run_report(dup)))
        no_id = self._report("in-progress", {},
                             matrix=[{"test": "a", "applicable": True}])
        self.assertEqual(validation.validate_run_report(no_id), [])
        del no_id["matrix"][0]["id"]
        self.assertTrue(any("non-empty 'id'" in p
                            for p in validation.validate_run_report(no_id)))

    def test_no_applicable_control_is_never_passed(self):
        matrix = [{"id": "T3", "test": "strategy report", "applicable": False}]
        self.assertEqual(self._admitted({}, matrix=matrix), ["in-progress"])
        self.assertEqual(self._admitted({"T3": "n-a"}, matrix=matrix),
                         ["in-progress"])
        self.assertEqual(self._admitted({}, matrix=[]), ["in-progress"])

    # ---- minimal compilation (spec 30.5) -------------------------------------

    CMATRIX = [{"id": "T1", "test": "compilation", "kind": "compilation",
                "applicable": True},
               {"id": "T2", "test": "replay", "applicable": True},
               {"id": "T3", "test": "strategy report", "applicable": False}]

    @staticmethod
    def _comp(errors=None, warnings=None, errors_reported=True,
              warnings_reported=True):
        return {"errors": {"reported": errors_reported, "items": errors or []},
                "warnings": {"reported": warnings_reported,
                             "items": warnings or []}}

    def _creport(self, status, results, comp=None, run_id="run-comp", **extra):
        extra.setdefault("matrix", self.CMATRIX)
        return self._report(status, results, run_id=run_id, scope="compilation",
                            compilation=self._comp() if comp is None else comp,
                            **extra)

    def _cadmitted(self, results, comp=None, **extra):
        return [s for s in self.STATUSES
                if validation.validate_run_report(
                    self._creport(s, dict(results), comp, **extra)) == []]

    def test_minimal_compilation_is_never_passed(self):
        """Spec 30.5: a successful minimal compilation is not a validation."""
        self.assertEqual(self._cadmitted({"T1": "passed", "T2": "not-run"}),
                         ["partial", "in-progress"])
        self.assertEqual(
            self._cadmitted({"T1": "failed", "T2": "not-run"},
                            self._comp(errors=["Error at 5412:9 type mismatch"])),
            ["failed"])
        # even with every listed control 'passed' the run is not a validation,
        # and a behavioural result is never invented
        self.assertEqual(self._cadmitted({"T1": "passed", "T2": "passed"}), [])
        bad = self._report("partial", {"T1": "passed", "T2": "not-run"},
                           scope="everything")
        self.assertTrue(any("scope" in p
                            for p in validation.validate_run_report(bad)))

    def test_compilation_lists_behavioural_controls_without_inventing(self):
        only = [{"id": "T1", "test": "compilation", "kind": "compilation",
                 "applicable": True}]
        rep = self._creport("in-progress", {"T1": "passed"}, matrix=only)
        self.assertTrue(any("none is listed" in p
                            for p in validation.validate_run_report(rep)))
        nokind = [{"id": "T1", "test": "compilation", "applicable": True},
                  {"id": "T2", "test": "replay", "applicable": True}]
        rep = self._creport("partial", {"T1": "passed", "T2": "not-run"},
                            matrix=nokind)
        self.assertTrue(any("exactly one applicable control of kind" in p
                            for p in validation.validate_run_report(rep)))
        rep = self._creport("partial", {"T1": "passed", "T2": "indeterminate"})
        self.assertTrue(any("must be 'not-run'" in p
                            for p in validation.validate_run_report(rep)))
        # a behavioural control left unreported is not an invented result
        self.assertEqual(self._cadmitted({"T1": "passed"}), ["in-progress"])

    def test_errors_and_warnings_are_recorded_separately(self):
        ok = {"T1": "passed", "T2": "not-run"}
        for comp in (None, {}, {"errors": {"reported": True, "items": []}},
                     {"errors": [], "warnings": []},
                     {"errors": {"reported": "yes", "items": []},
                      "warnings": {"reported": True, "items": []}},
                     {"errors": {"reported": True, "items": [""]},
                      "warnings": {"reported": True, "items": []}}):
            rep = self._creport("partial", dict(ok))
            if comp is None:
                del rep["compilation"]
            else:
                rep["compilation"] = comp
            self.assertTrue(validation.validate_run_report(rep), comp)
        # warnings observed, no error: valid, still never passed
        self.assertEqual(
            self._cadmitted(ok, self._comp(warnings=["Warning at 5331:5"])),
            ["partial", "in-progress"])

    def test_absence_of_observation_is_stated_never_guessed(self):
        ok = {"T1": "passed", "T2": "not-run"}
        # warnings not reported: admitted, and explicitly so
        self.assertEqual(
            self._cadmitted(ok, self._comp(warnings_reported=False)),
            ["partial", "in-progress"])
        # items under 'reported: false' are refused
        rep = self._creport("partial", dict(ok), self._comp(
            warnings=["Warning at 1:1"], warnings_reported=False))
        self.assertTrue(any("absence of observation" in p
                            for p in validation.validate_run_report(rep)))
        # 'passed' compilation requires that the absence of errors was observed
        rep = self._creport("partial", dict(ok), self._comp(errors_reported=False))
        self.assertTrue(any("must have been observed" in p
                            for p in validation.validate_run_report(rep)))
        # errors reported contradict a non-failed compilation control
        rep = self._creport("partial", dict(ok), self._comp(errors=["Error at 1:1"]))
        self.assertTrue(any("must be 'failed'" in p
                            for p in validation.validate_run_report(rep)))
        rep = self._creport("failed", {"T1": "failed", "T2": "not-run"})
        self.assertTrue(any("without any reported error" in p
                            for p in validation.validate_run_report(rep)))
        # the object is reserved to the compilation scope
        rep = self._report("passed", {"T1": "passed", "T2": "passed"},
                           compilation=self._comp())
        self.assertTrue(any("reserved" in p
                            for p in validation.validate_run_report(rep)))

    # ---- recording versus promotion (spec 30.5 / 51.4) -----------------------

    def _current(self):
        return json.loads((self.pdir / "validation" / "current.json")
                          .read_text(encoding="utf-8"))

    def _campaign(self, run_id="run-camp", sha=None, status="passed",
                  completed="2026-09-05T10:00:00Z"):
        results = {"T1": "passed", "T2": "passed"} if status == "passed" \
            else {"T1": "passed", "T2": "not-run"}
        rep = helpers.full_run_report(
            run_id, sha or self.sha, status=status, completed_at=completed,
            started_at="2026-09-05T09:00:00Z",
            matrix=[dict(m) for m in self.MATRIX], results=results)
        res = validation.promote_run(self.pdir, rep, None)
        self.assertTrue(res["promoted"], res)

    def _compile_run(self, run_id, status, completed, sha=None, errors=None):
        results = {"T1": "failed" if status == "failed" else "passed",
                   "T2": "not-run"}
        rep = self._creport(status, results, self._comp(errors=errors),
                            run_id=run_id, completed_at=completed,
                            started_at="2026-09-04T00:00:00Z")
        rep["source_sha256"] = sha or self.sha
        return rep

    def test_initial_promotion_without_recognized_run(self):
        res = validation.promote_run(
            self.pdir, self._compile_run("run-c0", "partial", "2026-09-06T10:00:00Z"),
            None)
        self.assertTrue(res["promoted"] and res["recorded"], res)
        self.assertEqual(self._current()["status"], "partial")

    def test_same_sha_non_failed_compilation_is_recorded_not_promoted(self):
        for prior in ("passed", "partial"):
            with self.subTest(prior=prior):
                pdir = helpers.make_product(self.root, slug="p-%s" % prior,
                                            with_validation=False)
                validation.init_validation_state(pdir)
                self.pdir, self.sha = pdir, core.sha256_file(pdir / "My Indicator.pine")
                self._campaign(status=prior)
                before = (pdir / "validation" / "current.json").read_bytes()
                res = validation.promote_run(
                    pdir, self._compile_run("run-c1", "partial",
                                            "2026-09-06T10:00:00Z"), None)
                self.assertFalse(res["promoted"])
                self.assertTrue(res["recorded"])
                self.assertIsNone(res["conflict"])
                self.assertTrue(any("WITHOUT promotion" in n for n in res["notes"]))
                self.assertEqual((pdir / "validation" / "current.json").read_bytes(),
                                 before)
                self.assertTrue((pdir / "validation" / "runs" / "run-c1.json").is_file())
                view = validation.validation_status(pdir, pdir / "My Indicator.pine")
                self.assertEqual((view["effective"], view["integrity"]), (prior, "OK"))

    def test_same_sha_failed_compilation_replaces_and_flags_contradiction(self):
        self._campaign()
        res = validation.promote_run(
            self.pdir, self._compile_run("run-c2", "failed", "2026-09-06T10:00:00Z",
                                         errors=["Error at 1:1"]), None)
        self.assertTrue(res["promoted"] and res["recorded"], res)
        self.assertTrue(any("CONTRADICTION" in n and "run-camp" in n
                            for n in res["notes"]))
        self.assertEqual(self._current()["status"], "failed")

    def test_failed_compilation_over_partial_carries_no_contradiction(self):
        self._campaign(status="partial")
        res = validation.promote_run(
            self.pdir, self._compile_run("run-c3", "failed", "2026-09-06T10:00:00Z",
                                         errors=["Error at 1:1"]), None)
        self.assertTrue(res["promoted"], res)
        self.assertFalse(any("CONTRADICTION" in n for n in res["notes"]))

    def test_other_sha_follows_the_normal_protocol_and_freshness(self):
        self._campaign()
        self.source.write_text(self.source.read_text(encoding="utf-8") + "// v2\n",
                               encoding="utf-8")
        new_sha = core.sha256_file(self.source)
        res = validation.promote_run(
            self.pdir, self._compile_run("run-c4", "partial", "2026-09-06T10:00:00Z",
                                         sha=new_sha), None)
        self.assertTrue(res["promoted"], res)
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual((view["persisted"], view["effective"]), ("partial", "partial"))
        # a compilation run on a SHA that is NOT the declared source is stale
        res = validation.promote_run(
            self.pdir, self._compile_run("run-c5", "partial", "2026-09-07T10:00:00Z",
                                         sha="c" * 64), None)
        self.assertTrue(res["promoted"], res)
        self.assertTrue(any("different from the source declared" in n
                            for n in res["notes"]))
        self.assertEqual(
            validation.validation_status(self.pdir, self.source)["effective"], "stale")

    def test_protections_are_never_bypassed_by_a_compilation_run(self):
        self._campaign(completed="2026-09-05T10:00:00Z")
        # older failed compilation: refused, kept, explicitly signalled
        res = validation.promote_run(
            self.pdir, self._compile_run("run-old", "failed", "2026-09-04T10:00:00Z",
                                         errors=["Error at 1:1"]), None)
        self.assertFalse(res["promoted"])
        self.assertTrue(res["recorded"])
        self.assertIn("older", res["conflict"])
        self.assertIn("FAILED run report is kept", res["conflict"])
        self.assertTrue((self.pdir / "validation" / "runs" / "run-old.json").is_file())
        self.assertEqual(self._current()["status"], "passed")
        # clock tie
        res = validation.promote_run(
            self.pdir, self._compile_run("run-tie", "failed", "2026-09-05T10:00:00Z",
                                         errors=["Error at 1:1"]), None)
        self.assertFalse(res["promoted"])
        self.assertIn("tie", res["conflict"])
        # concurrent witness
        res = validation.promote_run(
            self.pdir, self._compile_run("run-wit", "failed", "2026-09-06T10:00:00Z",
                                         errors=["Error at 1:1"]), b"stale witness")
        self.assertFalse(res["promoted"])
        self.assertIn("changed since the run started", res["conflict"])
        self.assertIn("NOT promoted", res["conflict"])
        # immutability: an existing run id is never rewritten, nothing recorded
        kept = (self.pdir / "validation" / "runs" / "run-old.json").read_bytes()
        res = validation.promote_run(
            self.pdir, self._compile_run("run-old", "partial", "2026-09-08T10:00:00Z"),
            None)
        self.assertFalse(res["promoted"] or res["recorded"])
        self.assertEqual((self.pdir / "validation" / "runs" / "run-old.json")
                         .read_bytes(), kept)
        # invalid report: neither recorded nor promoted
        bad = self._compile_run("run-bad", "passed", "2026-09-09T10:00:00Z")
        res = validation.promote_run(self.pdir, bad, None)
        self.assertFalse(res["promoted"] or res["recorded"])
        self.assertFalse((self.pdir / "validation" / "runs" / "run-bad.json").exists())
        self.assertEqual(self._current()["status"], "passed")

    # ---- groups (spec 30.4) ------------------------------------------------

    def _group(self, **over):
        grp = {"id": "G1", "controls": ["T1", "T2"],
               "presented_text": "Groupe affichage : T1 compilation, T2 replay.",
               "confirmation_text": "Tout est conforme.",
               "observed_by": "operator", "at": "2026-09-05T09:59:00Z"}
        grp.update(over)
        return grp

    def _grouped(self, group, status="passed", results=None):
        results = results if results is not None else {
            "T1": helpers.v2_result("passed", group="G1"),
            "T2": helpers.v2_result("passed", group="G1")}
        return self._report(status, results, groups=[group])

    def test_group_confirmation_accepted_when_list_was_presented(self):
        self.assertEqual(validation.validate_run_report(
            self._grouped(self._group())), [])

    def test_group_referencing_control_absent_from_matrix_refused(self):
        rep = self._grouped(self._group(controls=["T1", "T2", "T8"]))
        self.assertTrue(any("absent from the matrix" in p
                            for p in validation.validate_run_report(rep)))

    def test_group_without_presented_or_confirmation_text_refused(self):
        for key in ("presented_text", "confirmation_text"):
            for blank in ("", "   ", None):
                rep = self._grouped(self._group(**{key: blank}))
                self.assertTrue(any("presented before" in p
                                    for p in validation.validate_run_report(rep)),
                                (key, blank))

    def test_confirmation_never_extends_to_unlisted_control(self):
        rep = self._grouped(self._group(controls=["T1"]))
        self.assertTrue(any("never extends" in p
                            for p in validation.validate_run_report(rep)))
        unknown = self._grouped(self._group(), results={
            "T1": helpers.v2_result("passed", group="G9"),
            "T2": helpers.v2_result("passed", group="G1")})
        self.assertTrue(any("unknown group" in p
                            for p in validation.validate_run_report(unknown)))

    def test_applicable_control_outside_groups_without_verdict_refuses_passed(self):
        rep = self._grouped(self._group(controls=["T1"]), results={
            "T1": helpers.v2_result("passed", group="G1")})
        self.assertTrue(any("not reported" in p and "T2" in p
                            for p in validation.validate_run_report(rep)))

    # ---- declared source and historical reports (spec 51.3, 51.5) ----------

    def test_v3_promotion_on_another_sha_is_flagged_and_stale(self):
        rep = helpers.full_run_report("run-old-sha", "b" * 64)
        res = validation.promote_run(self.pdir, rep, None)
        self.assertTrue(res["promoted"], res)
        self.assertTrue(any("different from the source declared" in n
                            for n in res["notes"]))
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual(view["persisted"], "passed")
        self.assertEqual(view["effective"], "stale")
        self.assertTrue(any("does not validate the current source" in n
                            for n in view["notes"]))

    def test_v4_undeclared_pine_of_the_folder_is_never_the_reference(self):
        other = self.pdir / "Draft.pine"
        other.write_text(self.source.read_text(encoding="utf-8") + "// draft\n",
                         encoding="utf-8")
        rep = helpers.full_run_report("run-draft", core.sha256_file(other))
        res = validation.promote_run(self.pdir, rep, None)
        self.assertTrue(res["promoted"], res)
        self.assertTrue(any("different from the source declared" in n
                            for n in res["notes"]))
        self.assertEqual(
            validation.validation_status(self.pdir, self.source)["effective"],
            "stale")

    def test_unavailable_declared_source_is_not_called_different(self):
        (self.pdir / "SCRIPT.json").write_text("{not json", encoding="utf-8")
        res = validation.promote_run(
            self.pdir, helpers.full_run_report("run-nomanifest", self.sha), None)
        self.assertTrue(res["promoted"], res)
        self.assertTrue(any("could not be compared" in n for n in res["notes"]))
        self.assertFalse(any("different from" in n for n in res["notes"]))

    def test_promotion_on_the_declared_sha_carries_no_stale_note(self):
        res = validation.promote_run(
            self.pdir, helpers.full_run_report("run-ok", self.sha), None)
        self.assertTrue(res["promoted"], res)
        self.assertEqual(res["notes"], [])
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual((view["effective"], view["notes"]), ("passed", []))

    def test_v5_new_version_1_report_is_never_promoted(self):
        for rep in (helpers.full_run_report_v1("run-v1", self.sha),):
            res = validation.promote_run(self.pdir, rep, None)
            self.assertFalse(res["promoted"])
            self.assertIn("schema_version 1 is reserved", res["conflict"])
        unversioned = helpers.full_run_report_v1("run-v0", self.sha)
        del unversioned["schema_version"]
        res = validation.promote_run(self.pdir, unversioned, None)
        self.assertFalse(res["promoted"])
        self.assertFalse((self.pdir / "validation" / "runs").exists())

    def test_v6_existing_version_1_report_stays_inspected_and_admissible(self):
        vdir = self.pdir / "validation"
        (vdir / "runs").mkdir()
        rep = helpers.full_run_report_v1(
            "run-hist", self.sha,
            results={"compilation": "observation the holder: compile sans erreur"})
        (vdir / "runs" / "run-hist.json").write_text(json.dumps(rep), encoding="utf-8")
        before = (vdir / "runs" / "run-hist.json").read_bytes()
        core.atomic_write_json(vdir / "current.json", {
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-hist", "report": "runs/run-hist.json",
                         "source_sha256": self.sha,
                         "completed_at": rep["completed_at"]}})
        view = validation.validation_status(self.pdir, self.source)
        self.assertEqual((view["persisted"], view["integrity"], view["effective"]),
                         ("passed", "OK", "passed"))
        self.assertTrue(any("earlier schema version" in n for n in view["notes"]))
        self.assertEqual((vdir / "runs" / "run-hist.json").read_bytes(), before)

    def test_invalid_schema_version_refused(self):
        for bad in (3, 0, "2", True, None, 1.0, 2.0):
            rep = helpers.full_run_report("run-sv", self.sha)
            rep["schema_version"] = bad
            self.assertTrue(validation.validate_run_report(rep), bad)


class TestRecordedRunsOfTheWorkspace(unittest.TestCase):
    """v1: every run report recorded in the real workspace stays valid under
    the current validator and is never rewritten by it (read-only test)."""

    def test_recorded_reports_remain_valid(self):
        root = Path(__file__).resolve().parents[2]
        reports = sorted((root / "scripts").glob("*/validation/runs/*.json"))
        if not reports:
            self.skipTest("no recorded run report in this workspace")
        for path in reports:
            before = path.read_bytes()
            report = json.loads(before.decode("utf-8"))
            self.assertEqual(validation.validate_run_report(report), [], str(path))
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
