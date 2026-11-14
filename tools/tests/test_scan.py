# SPDX-License-Identifier: Apache-2.0
"""Scanner axes and registration model (spec sections 39, 44, 61.11)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core, scan
from tools.tests import helpers


def product_by_slug(result, slug):
    return next(p for p in result["products"] if p["slug"] == slug)


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_scripts_dir_is_valid(self):
        empty = Path(tempfile.mkdtemp(prefix="pws empty ", dir=self.tmp.name))
        result = scan.scan_workspace(empty)
        self.assertFalse(result["scripts_dir_exists"])
        self.assertEqual(result["products"], [])

    def test_validate_manifest_is_the_scan_check_of_one_product(self):
        """Audit C-11 (2026-11-13): the guard and the licence writers reuse the
        scan's manifest checks through `validate_manifest` — same findings,
        same validated licence axes as the workspace scan."""
        pdir = helpers.make_product_v3(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"access": "premium"})
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        votes, source, profile, lic, pub, findings = scan.validate_manifest("paid", pdir, data)
        p = product_by_slug(scan.scan_workspace(self.root), "paid")
        manifest_codes = [f["code"] for f in p["findings"]
                          if not f["code"].startswith(("VALIDATION", "CONTEXT", "EVIDENCE"))]
        self.assertEqual([f["code"] for f in findings], manifest_codes)
        self.assertIn("BROKEN", votes)
        self.assertEqual((profile, lic, p["license"]), ("COMMERCIAL", None, None))
        self.assertEqual(str(source), p["source"])

    def test_c19_imported_licence_fields_exposed_only_when_recorded(self):
        """Audit C-19 (2026-11-13): the licence of an imported script is
        recorded (license.origin / license.status, compatible extension of
        schema 3); the validated licence carries those fields only when the
        manifest records them — an earlier manifest keeps its exact view; the
        scan and `validate_manifest` agree."""
        lic = {"id": "GPL-3.0-or-later", "grant": "license", "origin": "imported", "status": "confirmed",
               "source_visibility": "public", "access": "free"}
        pdir = helpers.make_product_v3(self.root, slug="imported", profile="FREE", license_overrides=lic)
        helpers.make_product_v3(self.root, slug="earlier", profile="COMMERCIAL")
        result = scan.scan_workspace(self.root)
        imported = product_by_slug(result, "imported")
        self.assertEqual(imported["product_structure_status"], "REGISTERED")
        self.assertEqual((imported["license"]["origin"], imported["license"]["status"]), ("imported", "confirmed"))
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        _votes, _src, _profile, validated, _pub, _f = scan.validate_manifest("imported", pdir, data)
        self.assertEqual(validated, imported["license"])
        earlier = product_by_slug(result, "earlier")
        self.assertNotIn("origin", earlier["license"])
        self.assertNotIn("status", earlier["license"])
        pending = dict(lic, id=None, status="to-analyse")
        helpers.make_product_v3(self.root, slug="pending", profile="FREE", license_overrides=pending)
        p = product_by_slug(scan.scan_workspace(self.root), "pending")
        self.assertEqual(p["product_structure_status"], "REGISTERED")               # never a mute BROKEN
        self.assertIn(("LICENSE_TO_ANALYSE", "WARNING"), [(f["code"], f["severity"]) for f in p["findings"]])

    def test_registered_product(self):
        helpers.make_product(self.root)
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "my-indicator")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(p["validation_status"], "unverified")
        self.assertEqual(p["validation_integrity_status"], "OK")
        self.assertEqual(p["validation_effective_status"], "unverified")
        self.assertEqual(result["unregistered_pine"], [])

    def test_orphan_pine_detected(self):
        pdir = self.root / "scripts" / "orphan-product"
        pdir.mkdir()
        (pdir / "Orphan Script.pine").write_text("//@version=6\n", encoding="utf-8")
        result = scan.scan_workspace(self.root)
        self.assertEqual(len(result["unregistered_pine"]), 1)
        self.assertIn("Orphan Script.pine", result["unregistered_pine"][0])

    def test_pine_directly_under_scripts(self):
        (self.root / "scripts" / "loose.pine").write_text("//@version=6\n", encoding="utf-8")
        result = scan.scan_workspace(self.root)
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("PINE_AT_SCRIPTS_ROOT", codes)
        self.assertIn("PINE_UNREGISTERED", codes)

    def test_manifest_incomplete(self):
        pdir = helpers.make_product(self.root, slug="incomplete-one")
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        del data["distribution"]
        (pdir / "SCRIPT.json").write_text(json.dumps(data), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "incomplete-one")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("MANIFEST_MISSING_FIELDS", [f["code"] for f in p["findings"]])

    def test_manifest_unknown_field_rejected(self):
        helpers.make_product(self.root, slug="extra-field",
                             manifest_extra={"version": "1.0.0"})
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "extra-field")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("MANIFEST_UNKNOWN_FIELDS", [f["code"] for f in p["findings"]])

    def test_slug_case_collision(self):
        """The collision logic must be exercised even on case-insensitive
        filesystems (adversarial review): simulate two distinct dirs whose
        names differ only by case via a patched directory listing."""
        from unittest import mock
        helpers.make_product(self.root, slug="my-tool")
        real_dir = self.root / "scripts" / "my-tool"
        fake_dir = self.root / "scripts" / "My-Tool"
        real_iterdir = Path.iterdir
        scripts_dir = self.root / "scripts"

        def fake_iterdir(path_self):
            entries = list(real_iterdir(path_self))
            if path_self == scripts_dir:
                entries.append(fake_dir)
            return iter(entries)

        # On a case-insensitive filesystem the alias path resolves to the SAME
        # real directory, so no other patching is needed; on a case-sensitive
        # one the alias does not exist and is filtered by is_dir().
        with mock.patch.object(Path, "iterdir", fake_iterdir):
            result = scan.scan_workspace(self.root)
        if fake_dir.is_dir():
            statuses = {p["slug"]: p["product_structure_status"]
                        for p in result["products"]}
            self.assertIn("AMBIGUOUS", statuses.values())
            codes = [f["code"] for f in result["findings"]]
            self.assertIn("SLUG_CASE_COLLISION", codes)
        else:  # case-sensitive filesystem: the alias cannot exist
            self.skipTest("case-sensitive filesystem — alias path unavailable")
        self.assertTrue(real_dir.is_dir())

    def test_source_absolute_rejected(self):
        pdir = helpers.make_product(self.root, slug="abs-source")
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        data["source"] = str(pdir / "My Indicator.pine")
        (pdir / "SCRIPT.json").write_text(json.dumps(data), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "abs-source")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("SOURCE_ABSOLUTE", [f["code"] for f in p["findings"]])

    def test_source_traversal_rejected(self):
        outside = self.root / "outside.pine"
        outside.write_text("//@version=6\n", encoding="utf-8")
        pdir = helpers.make_product(self.root, slug="traversal")
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        data["source"] = "../../outside.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(data), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "traversal")
        self.assertIn("SOURCE_ESCAPES_ROOT", [f["code"] for f in p["findings"]])

    def test_source_symlink_out_rejected(self):
        target = Path(self.tmp.name) / "real source.pine"
        target.write_text("//@version=6\n", encoding="utf-8")
        pdir = helpers.make_product(self.root, slug="symlinked")
        os.symlink(target, pdir / "Linked.pine")
        data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        data["source"] = "Linked.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(data), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "symlinked")
        self.assertIn("SOURCE_ESCAPES_ROOT", [f["code"] for f in p["findings"]])

    def test_library_paid_matrix_rejected(self):
        helpers.make_product(self.root, slug="paid-lib", kind="library",
                             distribution="paid-closed-source")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "paid-lib")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("KIND_DISTRIBUTION_MATRIX", [f["code"] for f in p["findings"]])

    def test_source_missing(self):
        pdir = helpers.make_product(self.root, slug="lost-source")
        (pdir / "My Indicator.pine").unlink()
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "lost-source")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("SOURCE_MISSING", [f["code"] for f in p["findings"]])

    def test_multiple_sources_ambiguous_without_manifest(self):
        pdir = self.root / "scripts" / "two-sources"
        pdir.mkdir()
        (pdir / "One.pine").write_text("//@version=6\n", encoding="utf-8")
        (pdir / "Two.pine").write_text("//@version=6\n", encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "two-sources")
        self.assertEqual(p["product_structure_status"], "AMBIGUOUS")

    def test_source_multi_claimed(self):
        p1 = helpers.make_product(self.root, slug="claimer-one")
        pdir2 = self.root / "scripts" / "claimer-two"
        pdir2.mkdir()
        manifest = {
            "schema_version": 1, "id": "claimer-two",
            "source": "../claimer-one/My Indicator.pine",
            "script_kind": "indicator", "distribution": "free-open-source",
        }
        (pdir2 / "SCRIPT.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p2 = product_by_slug(result, "claimer-two")
        # escapes its own product root: rejected before multi-claim can occur
        self.assertEqual(p2["product_structure_status"], "BROKEN")
        self.assertTrue(p1.exists())

    def test_placeholder_context_incomplete(self):
        pdir = helpers.make_product(self.root, slug="placeholder-doc")
        (pdir / "PRODUCT.md").write_text("TODO\n", encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "placeholder-doc")
        self.assertEqual(p["product_structure_status"], "INCOMPLETE")

    def test_validation_stale_derived(self):
        pdir = helpers.make_product(self.root, slug="stale-check")
        source = pdir / "My Indicator.pine"
        sha_a = core.sha256_file(source)
        run = helpers.full_run_report("run-x", sha_a,
                                      completed_at="2026-09-04T10:00:00Z",
                                      started_at="2026-09-04T09:00:00Z")
        (pdir / "validation" / "runs").mkdir()
        (pdir / "validation" / "runs" / "run-x.json").write_text(
            json.dumps(run), encoding="utf-8")
        (pdir / "validation" / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-x", "report": "runs/run-x.json",
                         "source_sha256": sha_a, "completed_at": "2026-09-04T10:00:00Z"},
        }), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "stale-check")
        self.assertEqual(p["validation_effective_status"], "passed")
        # modify the source -> derived stale, persisted file untouched
        source.write_text(source.read_text(encoding="utf-8") + "// edit\n", encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "stale-check")
        self.assertEqual(p["validation_effective_status"], "stale")
        persisted = json.loads((pdir / "validation" / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "passed")

    def test_validation_broken_integrity_never_passed(self):
        pdir = helpers.make_product(self.root, slug="broken-validation")
        (pdir / "validation" / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "ghost", "report": "runs/ghost.json",
                         "source_sha256": "0" * 64, "completed_at": "2026-09-04T10:00:00Z"},
        }), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "broken-validation")
        self.assertEqual(p["validation_integrity_status"], "BROKEN")
        self.assertIsNone(p["validation_effective_status"])

    def test_symlinked_product_root_not_scanned(self):
        """Audit F3b: a symlinked product root has no safe identity and its
        content is never read."""
        external = Path(self.tmp.name) / "external product"
        external.mkdir()
        (external / "SCRIPT.json").write_text(json.dumps({
            "schema_version": 1, "id": "evil", "source": "Evil.pine",
            "script_kind": "indicator", "distribution": "free-open-source"}),
            encoding="utf-8")
        (external / "Evil.pine").write_text("//@version=6\n", encoding="utf-8")
        os.symlink(external, self.root / "scripts" / "evil")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "evil")
        self.assertEqual(p["product_structure_status"], "AMBIGUOUS")
        self.assertIsNone(p["source"])
        self.assertIsNone(p["script_kind"])
        self.assertIn("PRODUCT_ROOT_SYMLINK", [f["code"] for f in p["findings"]])
        # the external .pine is neither registered nor listed as orphan
        self.assertEqual(result["unregistered_pine"], [])

    def test_symlinked_context_file_not_read(self):
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("# externe\n", encoding="utf-8")
        pdir = helpers.make_product(self.root, slug="ctx-link")
        (pdir / "PRODUCT.md").unlink()
        os.symlink(outside, pdir / "PRODUCT.md")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "ctx-link")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("CONTEXT_ESCAPES", [f["code"] for f in p["findings"]])

    def test_manifest_wrong_types_diagnosed_not_crash(self):
        """Audit F8: invalid JSON shapes yield BROKEN diagnostics, never a
        TypeError."""
        cases = [
            ("kind-list", {"script_kind": []}),
            ("dist-dict", {"distribution": {}}),
            ("schema-str", {"schema_version": "1"}),
            ("schema-bool", {"schema_version": True}),
            ("id-num", {"id": 42}),
            ("source-list", {"source": ["a.pine"]}),
        ]
        for slug, override in cases:
            pdir = helpers.make_product(self.root, slug=slug)
            data = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
            data.update(override)
            (pdir / "SCRIPT.json").write_text(json.dumps(data), encoding="utf-8")
        result = scan.scan_workspace(self.root)  # must not raise
        for slug, _ in cases:
            p = product_by_slug(result, slug)
            self.assertEqual(p["product_structure_status"], "BROKEN", slug)
            codes = [f["code"] for f in p["findings"]]
            self.assertTrue(any(c in ("MANIFEST_FIELD_TYPE", "MANIFEST_SCHEMA_VERSION")
                                for c in codes), (slug, codes))

    def test_library_paid_with_typed_fields_still_rejected(self):
        helpers.make_product(self.root, slug="paid-lib2", kind="library",
                             distribution="paid-closed-source")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "paid-lib2")
        self.assertIn("KIND_DISTRIBUTION_MATRIX", [f["code"] for f in p["findings"]])

    def test_evidence_hash_divergence_broken(self):
        pdir = helpers.make_product(self.root, slug="evidence-check")
        vdir = pdir / "validation"
        (vdir / "runs").mkdir()
        (vdir / "evidence" / "run-e").mkdir(parents=True)
        ev = vdir / "evidence" / "run-e" / "shot.txt"
        ev.write_text("proof", encoding="utf-8")
        source_sha = core.sha256_file(pdir / "My Indicator.pine")
        run = helpers.full_run_report(
            "run-e", source_sha, completed_at="2026-09-04T10:00:00Z",
            started_at="2026-09-04T09:00:00Z",
            evidence=[{"path": "evidence/run-e/shot.txt", "sha256": "f" * 64,
                       "type": "screenshot"}])
        (vdir / "runs" / "run-e.json").write_text(json.dumps(run), encoding="utf-8")
        (vdir / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "passed",
            "last_run": {"run_id": "run-e", "report": "runs/run-e.json",
                         "source_sha256": source_sha,
                         "completed_at": "2026-09-04T10:00:00Z"},
        }), encoding="utf-8")
        result = scan.scan_workspace(self.root)
        p = product_by_slug(result, "evidence-check")
        self.assertEqual(p["validation_integrity_status"], "BROKEN")
        self.assertIn("EVIDENCE_HASH_DIVERGES", [f["code"] for f in p["findings"]])


if __name__ == "__main__":
    unittest.main()
