# SPDX-License-Identifier: Apache-2.0
"""Licence templates: rendering from configuration + manifest, draft status
when legal/commercial fields are missing, nothing invented (2026-11-06)."""
import hashlib
import json
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import licensing, profiles, scan
from tools.tests import helpers

REAL_TEMPLATES = licensing.TEMPLATES_REL


def _tree(base):
    base = Path(base)
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*")) if p.is_file() and not p.is_symlink()}


def _codes(root, slug):
    p = [x for x in scan.scan_workspace(root)["products"] if x["slug"] == slug][0]
    return p["product_structure_status"], [f["code"] for f in p["findings"]]


class TestLicensing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        # use the real templates of the workspace
        import shutil
        from tools.pws_workspace import core
        src = core.workspace_root() / REAL_TEMPLATES
        shutil.copytree(str(src), str(self.root / REAL_TEMPLATES))

    def tearDown(self):
        self.tmp.cleanup()

    def test_free_header_rendered_with_holder(self):
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE",
                                license_overrides={"created_year": 2024})
        r = licensing.render(self.root, "free-one", "header-free")
        self.assertTrue(r["ok"], r)
        self.assertIn("© 2024–", r["text"])
        self.assertNotIn("[[", r["text"])
        self.assertNotIn("]]", r["text"])
        self.assertNotIn("}}", r["text"])
        self.assertIn("Holder Test", r["text"])
        self.assertIn("CC BY-NC-SA 4.0", r["text"])
        self.assertIn("Creative Commons does not recommend its licenses for software", r["text"])
        self.assertFalse(r["draft"])

    def test_eula_is_draft_until_fields_supplied_and_never_invents(self):
        pdir = helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        st = licensing.status(self.root, "paid-one")
        self.assertEqual(st["eula"], "draft")
        self.assertIn("GOVERNING_LAW_REFERENCE", st["eula_missing_fields"])
        r = licensing.render(self.root, "paid-one", "eula")
        self.assertTrue(r["draft"])
        self.assertIn("{{PROVIDER_LEGAL_NAME}}", r["text"])  # visible placeholder, not invented
        self.assertIn(licensing.DRAFT_MARKER, r["text"])      # explicit draft banner
        self.assertNotIn("pws-template", r["text"])            # provenance line stripped
        w = licensing.write_rendered(self.root, "paid-one", "eula", "release/EULA.md")
        self.assertIn(licensing.DRAFT_MARKER, (pdir / "release" / "EULA.md").read_text(encoding="utf-8"))
        self.assertIn('contains no universal "no refund" clause', r["text"])
        self.assertIn("Mandatory rights of the customer", r["text"])
        fields = {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS}
        (pdir / "release" / "eula-fields.json").write_text(json.dumps(fields), encoding="utf-8")
        r = licensing.render(self.root, "paid-one", "eula")
        self.assertFalse(r["draft"], r["required_missing"])
        self.assertNotIn(licensing.DRAFT_MARKER, r["text"])
        w = licensing.write_rendered(self.root, "paid-one", "eula", "release/EULA.md")
        self.assertTrue(w["ok"])
        self.assertIn("Template Permission", w["permission"])
        # still "draft" status until the manifest references the written terms
        self.assertEqual(licensing.status(self.root, "paid-one")["eula"], "draft")
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["license"]["terms_ref"] = "release/EULA.md"
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        self.assertEqual(licensing.status(self.root, "paid-one")["eula"], "complete")

    def test_free_use_grant_for_closed_free(self):
        helpers.make_product_v2(self.root, slug="free-closed", profile="FREE", closed_source=True,
                                license_overrides={"created_year": 2025})
        st = licensing.status(self.root, "free-closed")
        self.assertEqual(st["profile_variant"], "FREE_CLOSED")
        self.assertEqual(st["eula"], "n/a")
        r = licensing.render(self.root, "free-closed", "grant")
        self.assertIn("source code is not delivered", r["text"].lower())
        self.assertIn("protected script", r["text"])
        self.assertFalse(r["draft"])  # ADDITIONAL_TERMS / PROVIDER_CONTACT optional here
        self.assertIn("Nothing in this grant forbids that use", r["text"])

    def test_unknown_product_or_kind(self):
        self.assertFalse(licensing.render(self.root, "nope", "notice")["ok"])
        helpers.make_product_v2(self.root, slug="x")
        self.assertFalse(licensing.render(self.root, "x", "poster")["ok"])
        self.assertFalse(licensing.write_rendered(self.root, "x", "notice", "../../escape.md")["ok"])

    def test_skeleton_has_every_required_field_blank(self):
        data = json.loads(licensing.eula_fields_skeleton())
        for k in licensing.EULA_REQUIRED_FIELDS:
            self.assertEqual(data[k], "")


    def test_header_carries_declared_terms_url_only_when_set(self):
        helpers.make_product_v2(self.root, slug="with-url", profile="COMMERCIAL",
                                license_overrides={"terms_url": "https://github.com/o/r/blob/main/EULA.md",
                                                   "created_year": 2020})
        r = licensing.render(self.root, "with-url", "header-proprietary")
        self.assertIn("// Terms of use: https://github.com/o/r/blob/main/EULA.md\n// Version: X.Y.Z", r["text"])
        self.assertNotIn("pws-template", r["text"])
        self.assertFalse(r["draft"])
        helpers.make_product_v2(self.root, slug="no-url", profile="COMMERCIAL")
        r2 = licensing.render(self.root, "no-url", "header-proprietary")
        self.assertNotIn("Terms of use", r2["text"])
        st = licensing.status(self.root, "with-url")
        self.assertEqual(st["publication"]["mode"], "invite-only")
        self.assertTrue(any("terms_url declared" in n for n in st["notes"]))



class TestOptionalBlocksAndYears(unittest.TestCase):
    """Corrections after independent verification (2026-11-06): optional
    blocks with nested placeholders, malformed templates, unknown creation
    year never replaced by the current year."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        import shutil
        from tools.pws_workspace import core
        shutil.copytree(str(core.workspace_root() / REAL_TEMPLATES), str(self.root / REAL_TEMPLATES))
        self.pdir = helpers.make_product_v2(self.root, slug="eula-prod", profile="COMMERCIAL",
                                            license_overrides={"created_year": 2024})
        (self.pdir / "release").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _fields(self, **optional):
        fields = {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS}
        fields.update(optional)
        (self.pdir / "release" / "eula-fields.json").write_text(json.dumps(fields), encoding="utf-8")

    def _assert_clean(self, text):
        for token in ("[[", "]]", "{{", "}}", "pws-template"):
            self.assertNotIn(token, text, token)

    def test_all_optional_absent(self):
        self._fields()
        r = licensing.render(self.root, "eula-prod", "eula")
        self.assertTrue(r["ok"] and not r["draft"], r)
        self._assert_clean(r["text"])
        self.assertIn("Refund policy reference: none stated by the Provider in this Agreement. In the absence", r["text"])
        self.assertNotIn("Price or plan reference", r["text"])
        self.assertNotIn("## 14. Additional terms", r["text"])
        # audit C-18 (contract change, 2026-11-13): the numbering stays continuous
        # when the optional block is omitted — section 14 is the last one
        self.assertIn("## 14. Entire agreement and changes", r["text"])
        self.assertNotIn("## 15.", r["text"])
        self.assertNotIn(licensing.DRAFT_MARKER, r["text"])

    def test_each_optional_present_separately(self):
        self._fields(PRICE_OR_PLAN_REFERENCE="Plan Pro")
        r = licensing.render(self.root, "eula-prod", "eula")
        self._assert_clean(r["text"])
        self.assertIn("- Price or plan reference: Plan Pro.", r["text"])
        self._fields(REFUND_POLICY_REFERENCE="see the order page")
        r = licensing.render(self.root, "eula-prod", "eula")
        self._assert_clean(r["text"])
        self.assertIn("Refund policy reference: see the order page. In the absence", r["text"])
        self.assertNotIn("none stated", r["text"])
        self._fields(ADDITIONAL_TERMS="Beta features may change.")
        r = licensing.render(self.root, "eula-prod", "eula")
        self._assert_clean(r["text"])
        self.assertIn("## 14. Additional terms\n\nBeta features may change.\n\n## 15.", r["text"])

    def test_all_optional_present(self):
        self._fields(PRICE_OR_PLAN_REFERENCE="Plan Pro", REFUND_POLICY_REFERENCE="order page",
                     ADDITIONAL_TERMS="Beta features may change.")
        r = licensing.render(self.root, "eula-prod", "eula")
        self.assertFalse(r["draft"])
        self._assert_clean(r["text"])
        for s in ("Plan Pro", "order page", "Beta features may change."):
            self.assertIn(s, r["text"])

    def test_required_missing_is_draft_with_banner_and_write_status_export_agree(self):
        r = licensing.render(self.root, "eula-prod", "eula")
        self.assertTrue(r["draft"])
        self.assertIn(licensing.DRAFT_MARKER, r["text"])
        self.assertIn("PROVIDER_LEGAL_NAME", r["required_missing"])
        w = licensing.write_rendered(self.root, "eula-prod", "eula", "release/EULA.md")
        self.assertTrue(w["draft"])
        from tools.pws_workspace import github
        self.assertIn("draft", github._draft_reason(self.pdir / "release" / "EULA.md"))
        m = json.loads((self.pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["license"]["terms_ref"] = "release/EULA.md"
        (self.pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        st = licensing.status(self.root, "eula-prod")
        self.assertTrue(st["terms_draft"])
        self.assertEqual(st["eula"], "draft")

    def test_malformed_template_is_an_error_never_a_final_document(self):
        bad = self.root / REAL_TEMPLATES / "EULA_COMMERCIAL_TEMPLATE.md"
        bad.write_text("# EULA\n\n[[?ADDITIONAL_TERMS:unclosed {{ADDITIONAL_TERMS}}\n", encoding="utf-8")
        self._fields()
        r = licensing.render(self.root, "eula-prod", "eula")
        self.assertFalse(r["ok"])
        self.assertIn("malformed", r["error"])
        w = licensing.write_rendered(self.root, "eula-prod", "eula", "release/EULA.md")
        self.assertFalse(w["ok"])
        self.assertFalse((self.pdir / "release" / "EULA.md").exists())

    def test_grant_optional_contact(self):
        helpers.make_product_v2(self.root, slug="free-closed", profile="FREE", closed_source=True,
                                license_overrides={"created_year": 2025})
        r = licensing.render(self.root, "free-closed", "grant")
        self.assertFalse(r["draft"], r)
        self._assert_clean(r["text"])
        self.assertNotIn("## 6. Contact", r["text"])
        fdir = self.root / "scripts" / "free-closed" / "release"
        fdir.mkdir()
        (fdir / "eula-fields.json").write_text(json.dumps({"PROVIDER_CONTACT": "support@example.invalid"}), encoding="utf-8")
        r = licensing.render(self.root, "free-closed", "grant")
        self._assert_clean(r["text"])
        self.assertIn("## 6. Contact\n\nQuestions about this grant: support@example.invalid", r["text"])

    def test_unknown_created_year_never_becomes_current_year(self):
        helpers.make_product_v2(self.root, slug="noyear", profile="COMMERCIAL")
        r = licensing.render(self.root, "noyear", "header-proprietary")
        self.assertTrue(r["ok"])
        self.assertTrue(r["draft"])
        self.assertIn("CREATED_YEAR", r["required_missing"] + r["missing_fields"])
        self.assertIn("{{YEAR_RANGE}}", r["text"])
        self.assertNotIn("© 2026", r["text"])
        st = licensing.status(self.root, "noyear")
        self.assertIn("CREATED_YEAR", st["eula_missing_fields"])
        self.assertTrue(any("created_year unknown" in n for n in st["notes"]))

    def test_known_years(self):
        import datetime
        this_year = datetime.date.today().year
        helpers.make_product_v2(self.root, slug="old", profile="COMMERCIAL", license_overrides={"created_year": 2020})
        r = licensing.render(self.root, "old", "header-proprietary")
        self.assertIn("© 2020–%d Holder Test" % this_year, r["text"])
        self.assertFalse(r["draft"])
        helpers.make_product_v2(self.root, slug="new", profile="COMMERCIAL", license_overrides={"created_year": this_year})
        r = licensing.render(self.root, "new", "header-proprietary")
        self.assertIn("© %d Holder Test" % this_year, r["text"])
        self.assertNotIn("–", r["text"].splitlines()[0])
        # rendering never writes the manifest
        m = json.loads((self.root / "scripts" / "old" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(m["license"]["created_year"], 2020)

    def test_header_hints_reported_not_recorded(self):
        header = ("// © 2020–2026 Holder Test\n// All Rights Reserved.\n// distributed as an invite-only script\n"
                  "// Version: 1.0.0\n//@version=6\n")
        helpers.make_product_v2(self.root, slug="hinted", profile="COMMERCIAL", header=header,
                                publication_overrides={"state": None, "privacy": None, "mode": None})
        st = licensing.status(self.root, "hinted")
        self.assertEqual(st["header_hints"], {"year": 2020, "mode": "invite-only"})
        self.assertEqual(st["publication"], {"state": None, "privacy": None, "mode": None})
        self.assertEqual(st["publication_proposed_by_profile"]["mode"], "invite-only")
        m = json.loads((self.root / "scripts" / "hinted" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertIsNone(m["license"]["created_year"])
        c = licensing.confirm_publication(self.root, "hinted", state="published", created_year=2020)
        self.assertTrue(c["ok"], c)
        m = json.loads((self.root / "scripts" / "hinted" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual((m["publication"]["state"], m["license"]["created_year"]), ("published", 2020))
        self.assertIn("license.created_year", m["migration"]["holder_confirmed"])
        self.assertFalse(licensing.confirm_publication(self.root, "hinted", mode="youtube")["ok"])


class TestCorrections20261113(unittest.TestCase):
    """Audit of 2026-11-12/13, constats C-01 to C-09 and C-18: bounded
    destinations and kinds, attached terms, documents derived from the licence
    axes, concurrent writers, resulting-manifest checks, holder's fields only,
    unexpected types, EULA numbering and type of script. Fictitious products."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        import shutil
        from tools.pws_workspace import core
        shutil.copytree(str(core.workspace_root() / REAL_TEMPLATES), str(self.root / REAL_TEMPLATES))

    def tearDown(self):
        self.tmp.cleanup()

    def _fill(self, slug, **extra):
        fields = {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS if k != "PRODUCT_NAME"}
        fields.update(extra)
        r = licensing.set_fields(self.root, slug, fields)
        self.assertTrue(r["ok"], r)

    def _manifest(self, slug):
        return json.loads((self.root / "scripts" / slug / "SCRIPT.json").read_text(encoding="utf-8"))

    def _set_manifest(self, slug, m):
        (self.root / "scripts" / slug / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")

    # ---- C-01 / C-09: where `license write` may write --------------------------

    def test_c01_write_destination_bounded_to_release_documents(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        (pdir / "release").mkdir()
        (pdir / "release" / "CHANGELOG.md").write_text("# Changelog\n- 1.0.0\n", encoding="utf-8")
        before = _tree(pdir)
        for dest in ("My Indicator.pine", "SCRIPT.json", "validation/current.json", "PRODUCT.md",
                     "release/eula-fields.json", "release/CHANGELOG.md", "release/EULA.txt", "release",
                     "release/sub/EULA.md", "../other/EULA.md", "/tmp/pws-test-escape.md", "release\\EULA.md"):
            r = licensing.write_rendered(self.root, "paid", "eula", dest)
            self.assertFalse(r["ok"], dest)
            self.assertIn("nothing written", r["error"], dest)
        self.assertEqual(_tree(pdir), before)                       # source, manifest, evidence untouched
        self.assertTrue(licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")["ok"])
        self.assertTrue(licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")["ok"])  # default replaced
        self.assertTrue(licensing.write_rendered(self.root, "paid", "eula", "release/EULA-copy.md")["ok"])
        r = licensing.write_rendered(self.root, "paid", "eula", "release/EULA-copy.md")
        self.assertFalse(r["ok"])                                    # existing, neither default nor attached
        self.assertIn("never overwritten", r["error"])
        self.assertEqual(_tree(pdir)["release/CHANGELOG.md"], before["release/CHANGELOG.md"])

    def test_c01_symlinked_release_never_followed_and_directory_destination(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        outside = Path(self.tmp.name) / "outside release"
        outside.mkdir()
        (outside / "eula-fields.json").write_text(json.dumps({"PROVIDER_CONTACT": "outside@example.invalid"}),
                                                   encoding="utf-8")
        os.symlink(outside, pdir / "release")
        o = licensing.overview(self.root, "paid")
        contact = next(f for g in o["fields"]["groups"] for f in g["fields"] if f["name"] == "PROVIDER_CONTACT")
        self.assertIsNone(contact["value"])                          # never read through the link
        self.assertIn("symbolic link", o["fields"]["error"])
        self.assertFalse(licensing.set_fields(self.root, "paid", {"SUPPORT_TERMS": "email"})["ok"])
        self.assertFalse(licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")["ok"])
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["eula-fields.json"])
        self.assertEqual(json.loads((outside / "eula-fields.json").read_text(encoding="utf-8")),
                         {"PROVIDER_CONTACT": "outside@example.invalid"})
        os.unlink(str(pdir / "release"))
        (pdir / "release" / "EULA.md").mkdir(parents=True)
        r = licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")     # C-09 (R3): no exception
        self.assertFalse(r["ok"])
        self.assertIn("not a regular file", r["error"])

    # ---- C-08: only the documents of the licence axes ---------------------------

    def test_c08_write_only_documents_of_the_licence_axes(self):
        pdir = helpers.make_product_v2(self.root, slug="free", profile="FREE",
                                       license_overrides={"created_year": 2024})
        for kind in ("eula", "header-proprietary", "grant", "notice"):
            r = licensing.write_rendered(self.root, "free", kind, licensing.default_dest(kind))
            self.assertFalse(r["ok"], kind)
            self.assertIn("not a document of this product", r["error"])
        self.assertFalse((pdir / "release").exists())
        self.assertTrue(licensing.write_rendered(self.root, "free", "header-free",
                                                 licensing.default_dest("header-free"))["ok"])
        r = licensing.render(self.root, "free", "eula")             # the preview stays available, flagged
        self.assertTrue(r["ok"])
        self.assertFalse(r["applicable"])
        self.assertIn("refuses", r["note"])
        self.assertTrue(licensing.render(self.root, "free", "header-free")["applicable"])

    # ---- C-02 / C-03: attached terms ---------------------------------------------

    def test_c02_draft_never_attached_and_status_follows_the_attached_document(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        self.assertTrue(licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")["draft"])
        before = (pdir / "SCRIPT.json").read_bytes()
        r = licensing.confirm_publication(self.root, "paid", terms_ref="release/EULA.md")
        self.assertFalse(r["ok"])
        self.assertIn("DRAFT", r["error"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        # attached by hand anyway, fields completed WITHOUT writing the document again
        m = self._manifest("paid")
        m["license"]["terms_ref"] = "release/EULA.md"
        self._set_manifest("paid", m)
        self._fill("paid")
        st = licensing.status(self.root, "paid")
        self.assertEqual(st["eula_missing_fields"], [])
        self.assertEqual((st["eula"], st["terms"]["state"]), ("draft", "draft"))
        self.assertEqual(licensing.overview(self.root, "paid")["status"], "draft")
        self.assertIn("EULA_DRAFT", _codes(self.root, "paid")[1])
        # written again: current and complete
        self.assertFalse(licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")["draft"])
        st = licensing.status(self.root, "paid")
        self.assertEqual((st["eula"], st["terms"]["state"]), ("complete", "current"))
        self.assertNotIn("EULA_DRAFT", _codes(self.root, "paid")[1])
        # a field changed afterwards: the attached copy is stale, the status draft again
        self._fill("paid", GOVERNING_LAW_REFERENCE="another reference")
        st = licensing.status(self.root, "paid")
        self.assertEqual((st["eula"], st["terms"]["state"]), ("draft", "stale"))
        self.assertTrue(any("no longer the current rendering" in n for n in st["notes"]))
        self.assertEqual(licensing.overview(self.root, "paid")["status"], "draft")

    def test_c03_terms_ref_only_the_current_rendering_of_the_terms_document(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        self._fill("paid")
        (pdir / "DECISIONS.md").write_text("# Decisions\n- internal note\n", encoding="utf-8")
        for ref in ("SCRIPT.json", "DECISIONS.md", "PRODUCT.md", "validation/current.json", "../paid/SCRIPT.json"):
            self.assertFalse(licensing.confirm_publication(self.root, "paid", terms_ref=ref)["ok"], ref)
        self.assertIsNone(self._manifest("paid")["license"]["terms_ref"])
        # a stale copy at the default destination is refused as well
        licensing.write_rendered(self.root, "paid", "eula", "release/EULA.md")
        self._fill("paid", SUPPORT_TERMS="chat only")
        r = licensing.confirm_publication(self.root, "paid", terms_ref="release/EULA.md")
        self.assertFalse(r["ok"])
        self.assertIn("not the current rendering", r["error"])
        # the current rendering is accepted, under its default name or another one
        self.assertTrue(licensing.write_rendered(self.root, "paid", "eula", "release/EULA-2026.md")["ok"])
        self.assertTrue(licensing.confirm_publication(self.root, "paid", terms_ref="release/EULA-2026.md")["ok"])
        self.assertEqual(licensing.status(self.root, "paid")["eula"], "complete")
        # the rendering is checked against the manifest RESULTING from the confirmation
        self.assertFalse(licensing.confirm_publication(self.root, "paid", created_year=2025,
                                                       terms_ref="release/EULA-2026.md")["ok"])
        self.assertEqual(self._manifest("paid")["license"]["created_year"], 2024)
        # no terms document applies to a CC BY-NC-SA product
        fdir = helpers.make_product_v2(self.root, slug="free", profile="FREE",
                                       license_overrides={"created_year": 2024})
        (fdir / "release").mkdir()
        (fdir / "release" / "TERMS.md").write_text("# Terms\n", encoding="utf-8")
        r = licensing.confirm_publication(self.root, "free", terms_ref="release/TERMS.md")
        self.assertFalse(r["ok"])
        self.assertIn("no terms document applies", r["error"])

    # ---- C-04: documents follow the licence axes ----------------------------------

    def test_c04_documents_follow_the_licence_axes_not_the_profile_name(self):
        helpers.make_product_v3(self.root, slug="free-paid", profile="FREE",
                                license_overrides=dict(profiles.default_license("COMMERCIAL"), created_year=2024),
                                publication_overrides={"mode": "invite-only"})
        o = licensing.overview(self.root, "free-paid")
        self.assertEqual([d["kind"] for d in o["documents"]], ["header-proprietary", "eula"])
        self.assertEqual((o["documents_regime"], o["profile_variant"], o["status"]),
                         ("COMMERCIAL", "FREE_CLOSED", "draft"))
        self.assertTrue(any("PROFILE_AXES_DIVERGENCE" in n for n in o["notes"]))
        self.assertFalse(licensing.write_rendered(self.root, "free-paid", "grant",
                                                  licensing.default_dest("grant"))["ok"])
        helpers.make_product_v3(self.root, slug="commercial-cc", profile="COMMERCIAL",
                                header=helpers.FREE_HEADER_HOLDER,
                                license_overrides=dict(profiles.default_license("FREE"), created_year=2024))
        o = licensing.overview(self.root, "commercial-cc")
        self.assertEqual([d["kind"] for d in o["documents"]], ["header-free"])
        self.assertEqual((o["documents_regime"], o["status"]), ("FREE", "complete"))

    # ---- C-05: concurrent writers -------------------------------------------------

    def _race(self, calls):
        """Run the calls in parallel threads while every manifest/fields write
        is slowed down: without the product lock, the read-modify-writes
        interleave and all but one update are lost."""
        from tools.pws_workspace import core
        real = core.atomic_write_json

        def slow(path, obj, indent=2):
            time.sleep(0.3)
            return real(path, obj, indent=indent)

        results = []
        with mock.patch.object(core, "atomic_write_json", slow):
            threads = [threading.Thread(target=lambda c=c: results.append(c())) for c in calls]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
        return results

    def test_c05_concurrent_confirmations_are_never_lost(self):
        helpers.make_product_v2(self.root, slug="race", profile="COMMERCIAL",
                                publication_overrides={"state": None, "privacy": None, "mode": None})
        calls = [lambda kw=kw: licensing.confirm_publication(self.root, "race", **kw)
                 for kw in ({"state": "published"}, {"privacy": "public"}, {"mode": "invite-only"},
                            {"created_year": 2020})]
        results = self._race(calls)
        self.assertEqual([r["ok"] for r in results], [True] * 4, results)
        m = self._manifest("race")
        self.assertEqual((m["publication"]["state"], m["publication"]["privacy"], m["publication"]["mode"],
                          m["license"]["created_year"]), ("published", "public", "invite-only", 2020))
        self.assertEqual(sorted(m["migration"]["holder_confirmed"]),
                         ["license.created_year", "publication.mode", "publication.privacy", "publication.state"])
        self.assertEqual(len(m["migration"]["confirmations"]), 4)

    def test_c05_concurrent_field_updates_are_never_lost(self):
        pdir = helpers.make_product_v2(self.root, slug="race", profile="COMMERCIAL")
        names = ("PROVIDER_LEGAL_NAME", "PROVIDER_CONTACT", "SUPPORT_TERMS", "LICENSE_MODEL")
        calls = [lambda n=n: licensing.set_fields(self.root, "race", {n: "value %s" % n}) for n in names]
        results = self._race(calls)
        self.assertEqual([r["ok"] for r in results], [True] * 4, results)
        data = json.loads((pdir / "release" / "eula-fields.json").read_text(encoding="utf-8"))
        self.assertEqual({n: data.get(n) for n in names}, {n: "value %s" % n for n in names})

    # ---- C-06: the resulting manifest must stay valid; back to unknown --------------

    def test_c06_confirm_refuses_a_value_that_breaks_the_manifest(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL")
        before = (pdir / "SCRIPT.json").read_bytes()
        r = licensing.confirm_publication(self.root, "paid", mode="open")
        self.assertFalse(r["ok"])
        self.assertIn("PUBLICATION_VISIBILITY_MISMATCH", r["error"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        helpers.make_product_v2(self.root, slug="lib", profile="FREE", kind="library",
                                body='library("ExampleLib")\nexport f(float x) => x\n')
        r = licensing.confirm_publication(self.root, "lib", mode="protected")
        self.assertFalse(r["ok"])
        self.assertIn("KIND_LIBRARY_OPEN_SOURCE", r["error"])
        self.assertEqual(_codes(self.root, "lib")[0], "REGISTERED")
        # a confirmation that REPAIRS a broken manifest is accepted
        helpers.make_product_v2(self.root, slug="fix", profile="COMMERCIAL", publication_overrides={"mode": "open"})
        self.assertEqual(_codes(self.root, "fix")[0], "BROKEN")
        self.assertTrue(licensing.confirm_publication(self.root, "fix", mode="invite-only")["ok"])
        self.assertEqual(_codes(self.root, "fix")[0], "REGISTERED")

    def test_c06_a_confirmed_value_returns_to_unknown(self):
        helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL")
        self.assertTrue(licensing.confirm_publication(self.root, "paid", state="published", privacy="public")["ok"])
        r = licensing.confirm_publication(self.root, "paid", clear=["state", "publication.privacy"])
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cleared"], ["publication.state", "publication.privacy"])
        m = self._manifest("paid")
        self.assertEqual((m["publication"]["state"], m["publication"]["privacy"]), (None, None))
        self.assertNotIn("publication.state", m["migration"]["holder_confirmed"])
        self.assertEqual(m["migration"]["confirmations"][-1]["values"],
                         {"publication.state": None, "publication.privacy": None})
        self.assertFalse(licensing.confirm_publication(self.root, "paid", clear=["profile"])["ok"])
        self.assertFalse(licensing.confirm_publication(self.root, "paid", mode="invite-only", clear=["mode"])["ok"])

    # ---- C-07: only the holder's fields feed the rendering ---------------------------

    def test_c07_only_holder_fields_feed_the_rendering(self):
        pdir = helpers.make_product_v2(self.root, slug="paid", profile="COMMERCIAL")   # created_year unknown
        (pdir / "release").mkdir()
        (pdir / "release" / "eula-fields.json").write_text(json.dumps({
            "YEAR_RANGE": "2011–2026", "COPYRIGHT_HOLDER": "Mallory Example Corp",
            "TERMS_URL": "https://shop.example.invalid/buy-now", "CC_URL": "https://example.invalid/not-cc",
            "SUPPORT_TERMS": "e-mail support"}), encoding="utf-8")
        r = licensing.render(self.root, "paid", "header-proprietary")
        self.assertTrue(r["draft"])
        self.assertIn("CREATED_YEAR", r["required_missing"])
        for forbidden in ("Mallory", "2011", "shop.example.invalid"):
            self.assertNotIn(forbidden, r["text"])
        self.assertEqual(len(r["fields_ignored"]), 4)
        r = licensing.render(self.root, "paid", "header-free")
        self.assertIn(profiles.CC_URL, r["text"])
        self.assertNotIn("not-cc", r["text"])
        o = licensing.overview(self.root, "paid")
        self.assertEqual((o["recorded"]["copyright_holder"], o["recorded"]["copyright_holder_source"]),
                         ("Holder Test", "configuration"))
        self.assertEqual(next(f["value"] for g in o["fields"]["groups"] for f in g["fields"]
                              if f["name"] == "SUPPORT_TERMS"), "e-mail support")
        self.assertTrue(any("ignored" in n for n in licensing.status(self.root, "paid")["notes"]))
        # set-fields keeps unknown keys in the file but refuses template syntax in a value
        r = licensing.set_fields(self.root, "paid", {"SUPPORT_TERMS": "see {{SUPPORT_PAGE}}"})
        self.assertFalse(r["ok"])
        data = json.loads((pdir / "release" / "eula-fields.json").read_text(encoding="utf-8"))
        self.assertEqual((data["COPYRIGHT_HOLDER"], data["SUPPORT_TERMS"]), ("Mallory Example Corp", "e-mail support"))
        data["PROVIDER_CONTACT"] = "tickets [[priority]]"            # hand-written value with block syntax
        (pdir / "release" / "eula-fields.json").write_text(json.dumps(data), encoding="utf-8")
        r = licensing.render(self.root, "paid", "eula")
        self.assertTrue(r["ok"], r)                                  # ignored, never a malformed render
        self.assertIn("PROVIDER_CONTACT", r["required_missing"])

    # ---- C-09: unexpected types, broken manifest ---------------------------------------

    def test_c09_unexpected_types_never_raise_and_nothing_is_written(self):
        cases = {"license-string": ("license", "PROPRIETARY"),
                 "publication-list": ("publication", ["published"]),
                 "confirmations-string": ("migration", {"confirmations": "none yet",
                                                        "holder_confirmed": "publication.state"})}
        for slug, (key, value) in cases.items():
            m = helpers.v3_manifest(slug, "My Indicator.pine", profile="COMMERCIAL")
            m[key] = value
            pdir = helpers.make_product_v3(self.root, slug=slug, profile="COMMERCIAL", manifest=m)
            before = (pdir / "SCRIPT.json").read_bytes()
            for call in (lambda: licensing.overview(self.root, slug), lambda: licensing.status(self.root, slug),
                         lambda: licensing.render(self.root, slug, "eula")):
                self.assertIsInstance(call(), dict)
            r = licensing.confirm_publication(self.root, slug, state="published")
            self.assertFalse(r["ok"], slug)
            self.assertIn("nothing written", r["error"])
            self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before, slug)

    def test_c09_broken_manifest_is_announced_and_never_confirmed_into(self):
        pdir = helpers.make_product_v2(self.root, slug="broken", profile="COMMERCIAL",
                                       license_overrides={"access": "premium", "created_year": 2024})
        o = licensing.overview(self.root, "broken")
        self.assertEqual((o["manifest_status"], o["documents"], o["status"]), ("BROKEN", [], "draft"))
        self.assertEqual(o["manifest_problems"][0]["code"], "MANIFEST_LICENSE_AXIS_INVALID")
        self.assertTrue(any("BROKEN" in n for n in o["notes"]))
        before = (pdir / "SCRIPT.json").read_bytes()
        r = licensing.confirm_publication(self.root, "broken", state="published")
        self.assertFalse(r["ok"])
        self.assertIn("already present", r["error"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        self.assertFalse(licensing.write_rendered(self.root, "broken", "eula", "release/EULA.md")["ok"])

    # ---- C-18: EULA numbering and type of script -----------------------------------

    def test_c18_eula_numbering_is_continuous_and_names_the_type_of_script(self):
        helpers.make_product_v2(self.root, slug="strat", profile="COMMERCIAL", kind="strategy",
                                body='strategy("Example Strategy")\nplot(close)\n',
                                license_overrides={"created_year": 2024})
        self._fill("strat")
        for extra, last in (({}, 14), ({"ADDITIONAL_TERMS": "Beta features may change."}, 15)):
            if extra:
                self._fill("strat", **extra)
            r = licensing.render(self.root, "strat", "eula")
            self.assertFalse(r["draft"], r["required_missing"])
            nums = [int(n) for n in re.findall(r"^## (\d+)\.", r["text"], re.M)]
            self.assertEqual(nums, list(range(1, last + 1)))
            self.assertIn("## %d. Entire agreement and changes" % last, r["text"])
            self.assertIn("a Pine Script strategy", r["text"])
            self.assertNotIn("a Pine Script indicator", r["text"])



MPL_HEADER = ("// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at "
              "https://mozilla.org/MPL/2.0/\n// © zeta_author_example\n// Version: 1.0.0\n//@version=6\n")
CUSTOM_HEADER = ("// Licensed under the Example Community Trading Licence 1.0\n// © 2024 Zeta Example\n"
                 "// Version: 1.0.0\n//@version=6\n")
DUAL_HEADER = ("// © 2021 Zeta Example\n// Licensed under the GNU GPL v2 or v3, at your option.\n"
               "// Version: 1.0.0\n//@version=6\n")


def _imported(lid, status="confirmed", **axes):
    lic = {"id": lid, "grant": profiles.imported_grant(lid) if lid else "license", "origin": "imported",
           "status": status, "source_visibility": "public", "access": "free"}
    lic.update(axes)
    return lic


class TestImportedLicencePath20261113(unittest.TestCase):
    """Audit C-19, decision of the holder of 2026-11-13: the licence path
    keeps the existing licence of an imported script (« existing licence
    kept »), imposes no PWS terms document, shows the header proposal as a
    proposal, and records an exact identifier only on the holder's
    confirmation. Fictitious products and identities."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, holder="Bruno Exemple Indicators")
        import shutil
        from tools.pws_workspace import core
        shutil.copytree(str(core.workspace_root() / REAL_TEMPLATES), str(self.root / REAL_TEMPLATES))

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self, slug):
        return json.loads((self.root / "scripts" / slug / "SCRIPT.json").read_text(encoding="utf-8"))

    def test_existing_licence_kept_in_status_and_overview(self):
        helpers.make_product_v3(self.root, slug="mpl", profile="FREE", header=MPL_HEADER,
                                license_overrides=_imported("MPL-2.0"))
        o = licensing.overview(self.root, "mpl", "fr")
        self.assertEqual((o["status"], o["documents_regime"], o["documents"], o["license_origin"],
                          o["license_state"]), ("kept", "IMPORTED", [], "imported", "kept"))
        self.assertEqual(o["documents_regime_label"], "Licence existante conservée (script importé)")
        self.assertEqual(o["profile_label"], "Profil d'usage FREE — Licence existante conservée : MPL-2.0")
        existing = o["existing_licence"]
        self.assertEqual((existing["id"], existing["header"]["proposal"], existing["header_matches_record"]),
                         ("MPL-2.0", "MPL-2.0", True))
        self.assertIn("never a legal proof", existing["note"])
        self.assertEqual(o["license_release_blockers"], [])
        keys = [c["key"] for c in o["to_confirm"]]
        self.assertNotIn("license.created_year", keys)                  # no PWS header to render
        self.assertNotIn("license.terms_ref", keys)                     # no PWS terms document
        st = licensing.status(self.root, "mpl")
        self.assertEqual((st["eula"], st["license"]["origin"], st["license"]["status"]), ("n/a", "imported", "confirmed"))
        self.assertTrue(any(n.startswith("existing licence kept: MPL-2.0") for n in st["notes"]))
        self.assertFalse(any("PROFILE_AXES_DIVERGENCE" in n or "created_year unknown" in n for n in st["notes"]))
        self.assertEqual(licensing.overview(self.root, "mpl", "en")["existing_licence"]["label"],
                         "Existing licence kept: MPL-2.0")
        # the header no longer establishes the recorded licence: reported, the record is the holder's
        helpers.make_product_v3(self.root, slug="mismatch", profile="FREE", header=CUSTOM_HEADER,
                                license_overrides=_imported("MPL-2.0"))
        st = licensing.status(self.root, "mismatch")
        self.assertFalse(st["existing_licence"]["header_matches_record"])
        self.assertTrue(any("does not establish the recorded licence MPL-2.0" in n for n in st["notes"]))

    def test_licence_to_analyse_blocks_release_and_export_only(self):
        helpers.make_product_v3(self.root, slug="custom", profile="FREE", header=CUSTOM_HEADER,
                                license_overrides=_imported(None, status="to-analyse"))
        o = licensing.overview(self.root, "custom", "fr")
        self.assertEqual((o["status"], o["license_state"], o["manifest_status"]), ("to-analyse", "to-analyse", "REGISTERED"))
        self.assertEqual(o["existing_licence"]["label"], "Licence existante à analyser")
        self.assertEqual(len(o["license_release_blockers"]), 1)
        entry = next(c for c in o["to_confirm"] if c["key"] == "license.id")
        self.assertIn("--license-id", entry["command"])
        self.assertIsNone(entry["hint"])                                 # custom licence: no proposal
        st = licensing.status(self.root, "custom")
        self.assertTrue(any("TO ANALYSE" in n and "current work continues" in n for n in st["notes"]))
        helpers.make_product_v3(self.root, slug="mpl-pending", profile="FREE", header=MPL_HEADER,
                                license_overrides=_imported(None, status="to-analyse"))
        entry = next(c for c in licensing.overview(self.root, "mpl-pending")["to_confirm"] if c["key"] == "license.id")
        self.assertEqual(entry["hint"], "MPL-2.0")                       # the proposal, never recorded by itself
        self.assertIsNone(self._manifest("mpl-pending")["license"]["id"])

    def test_no_pws_terms_document_is_imposed(self):
        pdir = helpers.make_product_v3(self.root, slug="mpl", profile="FREE", header=MPL_HEADER,
                                       license_overrides=_imported("MPL-2.0"))
        before = _tree(pdir)
        for kind in licensing.KINDS:
            r = licensing.write_rendered(self.root, "mpl", kind, licensing.default_dest(kind))
            self.assertFalse(r["ok"], kind)
            self.assertIn("no PWS document applies", r["error"])
            self.assertFalse(licensing.render(self.root, "mpl", kind)["applicable"], kind)
        self.assertEqual(_tree(pdir), before)
        (pdir / "release").mkdir()
        (pdir / "release" / "NOTICE.md").write_text("# Notice\n", encoding="utf-8")
        r = licensing.confirm_publication(self.root, "mpl", terms_ref="release/NOTICE.md")
        self.assertFalse(r["ok"])
        self.assertIn("no terms document applies", r["error"])
        self.assertTrue(licensing.confirm_publication(self.root, "mpl", state="published", privacy="public",
                                                      mode="open")["ok"])

    def test_confirm_license_id_only_exact_and_only_for_an_imported_licence(self):
        pdir = helpers.make_product_v3(self.root, slug="pending", profile="FREE", header=MPL_HEADER,
                                       license_overrides=_imported(None, status="to-analyse"))
        before = (pdir / "SCRIPT.json").read_bytes()
        for lid, words in (("GPL-3.0", "deprecated and ambiguous"), ("mpl-2.0", "exact identifier 'MPL-2.0'"),
                           ("ISC", "not in the closed list"), ("PROPRIETARY", "not in the closed list")):
            r = licensing.confirm_publication(self.root, "pending", license_id=lid)
            self.assertFalse(r["ok"], lid)
            self.assertIn(words, r["error"], lid)
            self.assertIn("nothing written", r["error"], lid)
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        r = licensing.confirm_publication(self.root, "pending", license_id="MPL-2.0")
        self.assertTrue(r["ok"], r)
        m = self._manifest("pending")
        self.assertEqual({k: m["license"][k] for k in ("id", "status", "grant", "origin")},
                         {"id": "MPL-2.0", "status": "confirmed", "grant": "license", "origin": "imported"})
        self.assertIn("license.id", m["migration"]["holder_confirmed"])
        self.assertEqual(m["migration"]["confirmations"][-1]["values"],
                         {"license.id": "MPL-2.0", "license.status": "confirmed", "license.grant": "license"})
        self.assertEqual(_codes(self.root, "pending")[0], "REGISTERED")
        r = licensing.confirm_publication(self.root, "pending", clear=["license_id"])
        self.assertTrue(r["ok"], r)
        m = self._manifest("pending")
        self.assertEqual((m["license"]["id"], m["license"]["status"], m["license"]["grant"]),
                         (None, "to-analyse", "license"))
        self.assertNotIn("license.id", m["migration"]["holder_confirmed"])
        self.assertTrue(licensing.confirm_publication(self.root, "pending", license_id="CC-BY-NC-SA-4.0")["ok"])
        self.assertEqual(self._manifest("pending")["license"]["grant"], "cc")
        # a profile licence is never changed by this path
        cdir = helpers.make_product_v3(self.root, slug="paid", profile="COMMERCIAL")
        before = (cdir / "SCRIPT.json").read_bytes()
        for kwargs in ({"license_id": "MIT"}, {"clear": ["license_id"]}):
            r = licensing.confirm_publication(self.root, "paid", **kwargs)
            self.assertFalse(r["ok"], kwargs)
            self.assertIn("a profile licence is never changed here", r["error"])
        self.assertEqual((cdir / "SCRIPT.json").read_bytes(), before)

    def test_detect_source_licence_is_a_read_only_proposal(self):
        pdir = self.root / "scripts" / "to-onboard"
        pdir.mkdir()
        (pdir / "Imported Script.pine").write_text(MPL_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        (pdir / "Custom.pine").write_text(CUSTOM_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        before = _tree(self.root)
        r = licensing.detect_source_licence(self.root, "scripts/to-onboard/Imported Script.pine")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["state"], r["proposal"]), ("recognized", "MPL-2.0"))
        self.assertEqual(r["record_if_confirmed"], {"origin": "imported", "status": "confirmed", "id": "MPL-2.0",
                                                    "grant": "license"})
        self.assertIn("never a legal proof", r["note"])
        self.assertEqual(r["header_lines"][0][:40], MPL_HEADER[:40])
        r = licensing.detect_source_licence(self.root, "scripts/to-onboard/Custom.pine")
        self.assertEqual((r["state"], r["record_if_confirmed"]["status"], r["record_if_confirmed"]["id"]),
                         ("to-analyse", "to-analyse", None))
        outside = Path(self.tmp.name) / "outside.pine"
        outside.write_text(MPL_HEADER, encoding="utf-8")
        os.symlink(outside, pdir / "Linked.pine")
        for bad in ("../outside.pine", str(outside), "scripts/../outside.pine", "scripts/to-onboard/PRODUCT.md",
                    "scripts/to-onboard/Linked.pine", "scripts/to-onboard/Missing.pine", "elsewhere/x.pine"):
            self.assertFalse(licensing.detect_source_licence(self.root, bad)["ok"], bad)
        os.unlink(str(pdir / "Linked.pine"))
        self.assertEqual(_tree(self.root), before)                       # nothing written

    # ---- independent counter-verification of 2026-11-13 (C-19: M2, m1, m4) ---------------

    def test_detect_reads_the_notice_after_the_directive_and_never_proposes_one_version(self):
        pdir = self.root / "scripts" / "to-onboard"
        pdir.mkdir()
        notice = MPL_HEADER.split("// Version:")[0]                     # the MPL notice and its © line
        (pdir / "After.pine").write_text("// Version: 1.0.0\n//@version=6\n" + notice + helpers.MINIMAL_BODY,
                                         encoding="utf-8")
        (pdir / "Dual.pine").write_text(DUAL_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        before = _tree(self.root)
        r = licensing.detect_source_licence(self.root, "scripts/to-onboard/After.pine")
        self.assertEqual((r["state"], r["proposal"]), ("recognized", "MPL-2.0"))
        self.assertEqual(r["header_lines"], ["// Version: 1.0.0"])
        self.assertEqual(r["after_version_lines"], notice.splitlines())
        r = licensing.detect_source_licence(self.root, "scripts/to-onboard/Dual.pine")
        self.assertEqual((r["state"], r["proposal"], r["record_if_confirmed"]["status"], r["record_if_confirmed"]["id"]),
                         ("to-analyse", None, "to-analyse", None))
        self.assertIn("several versions stated (2.0, 3.0)", r["reasons"][0])
        self.assertEqual(r["after_version_lines"], [])
        self.assertEqual(_tree(self.root), before)                       # nothing written

    def test_header_matches_record_only_when_the_header_establishes_it(self):
        """`header_matches_record` is true only when the header establishes the
        recorded identifier exactly: false for a notice that states several
        versions or no version — never a silent acceptance of either version."""
        for lid, header in (("GPL-2.0-only", DUAL_HEADER), ("GPL-3.0-only", DUAL_HEADER),
                            ("GPL-3.0-only", "// © 2021 Zeta Example\n// Released under the GNU General Public "
                                             "License.\n// Version: 1.0.0\n//@version=6\n")):
            slug = "rec-%s-%d" % (lid.lower().replace(".", "-"), len(header))
            helpers.make_product_v3(self.root, slug=slug, profile="FREE", header=header,
                                    license_overrides=_imported(lid))
            st = licensing.status(self.root, slug)
            self.assertFalse(st["existing_licence"]["header_matches_record"], (lid, header))
            self.assertTrue(any("does not establish the recorded licence %s" % lid in n for n in st["notes"]), lid)
        notice = MPL_HEADER.split("// Version:")[0]
        helpers.make_product_v3(self.root, slug="after", profile="FREE", header="// Version: 1.0.0\n//@version=6\n"
                                + notice, license_overrides=_imported("MPL-2.0"))
        existing = licensing.overview(self.root, "after", "en")["existing_licence"]
        self.assertEqual((existing["state"], existing["header"]["proposal"], existing["header_matches_record"]),
                         ("kept", "MPL-2.0", True))

    def test_agpl_plus_is_refused_as_a_deprecated_identifier(self):
        pdir = helpers.make_product_v3(self.root, slug="pending", profile="FREE", header=DUAL_HEADER,
                                       license_overrides=_imported(None, status="to-analyse"))
        before = (pdir / "SCRIPT.json").read_bytes()
        r = licensing.confirm_publication(self.root, "pending", license_id="AGPL-3.0+")
        self.assertFalse(r["ok"])
        for words in ("deprecated SPDX identifier (\"+\" form)", "nothing written"):
            self.assertIn(words, r["error"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)

    def test_the_cma_shaped_profile_manifest_is_unchanged(self):
        from tools.tests.test_profiles import CMA_SHAPED
        m = json.loads(json.dumps(CMA_SHAPED))
        pdir = helpers.make_product_v3(self.root, slug="cma-shaped", profile="COMMERCIAL", manifest=m)
        raw = (pdir / "SCRIPT.json").read_bytes()
        o = licensing.overview(self.root, "cma-shaped", "fr")
        self.assertEqual((o["status"], o["documents_regime"], [d["kind"] for d in o["documents"]]),
                         ("draft", "COMMERCIAL", ["header-proprietary", "eula"]))
        self.assertEqual((o["license_origin"], o["license_state"], o["existing_licence"]), ("profile", None, None))
        self.assertEqual(o["profile_label"], "COMMERCIAL — propriétaire, EULA configurable")
        self.assertEqual([c["key"] for c in o["to_confirm"]],
                         ["license.created_year", "publication.state", "publication.privacy", "publication.mode",
                          "license.terms_ref"])
        st = licensing.status(self.root, "cma-shaped")
        self.assertEqual(set(st["license"]), {"id", "grant", "source_visibility", "access", "copyright_holder",
                                              "created_year", "terms_ref", "terms_url"})
        self.assertEqual(st["license_release_blockers"], [])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), raw)


class TestImportedLegalDocumentsPath20261114(unittest.TestCase):
    """Holder's request of 2026-11-14: the original legal documents of an
    imported script are declared by the holder (`license confirm
    --license-document`, `--no-license-documents`, `--clear
    license_documents`), shown with what keeps the export waiting, proposed
    (never recorded) at detection; never rewritten nor translated.
    Fictitious products and identities."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, holder="Bruno Exemple Indicators")

    def tearDown(self):
        self.tmp.cleanup()

    def _manifest(self, slug):
        return json.loads((self.root / "scripts" / slug / "SCRIPT.json").read_text(encoding="utf-8"))

    def test_declare_clear_and_record_none(self):
        pdir = helpers.make_product_v3(self.root, slug="mpl", profile="FREE", header=MPL_HEADER,
                                       license_overrides=_imported("MPL-2.0"))
        (pdir / "LICENSE").write_bytes(b"Mozilla Public License Version 2.0 (fictitious excerpt)\n")
        (pdir / "release").mkdir()
        (pdir / "release" / "NOTICE.txt").write_bytes("Avis d'origine, conservé tel quel.\n".encode("latin-1"))
        tree = _tree(pdir)
        r = licensing.confirm_publication(self.root, "mpl", license_documents=["LICENSE", "release/NOTICE.txt"])
        self.assertTrue(r["ok"], r)
        m = self._manifest("mpl")
        self.assertEqual(m["license"]["documents"], ["LICENSE", "release/NOTICE.txt"])
        self.assertIn("license.documents", m["migration"]["holder_confirmed"])
        self.assertEqual(m["migration"]["confirmations"][-1]["values"],
                         {"license.documents": ["LICENSE", "release/NOTICE.txt"]})
        self.assertEqual(_codes(self.root, "mpl")[0], "REGISTERED")
        self.assertEqual({k: v for k, v in _tree(pdir).items() if k != "SCRIPT.json"},
                         {k: v for k, v in tree.items() if k != "SCRIPT.json"})       # the documents untouched
        docs = licensing.status(self.root, "mpl")["existing_licence"]["legal_documents"]
        self.assertEqual((docs["declared"], docs["undeclared"], docs["blockers"]),
                         (["LICENSE", "release/NOTICE.txt"], [], []))
        self.assertEqual([d["encoding"].split(",")[0] for d in docs["documents"]], ["UTF-8", "single-byte"])
        self.assertIn("does not establish by itself", docs["note"])
        st = licensing.status(self.root, "mpl")
        self.assertTrue(any(n.startswith("original legal documents declared: LICENSE, release/NOTICE.txt")
                            for n in st["notes"]))
        self.assertTrue(licensing.confirm_publication(self.root, "mpl", clear=["license_documents"])["ok"])
        m = self._manifest("mpl")
        self.assertIsNone(m["license"]["documents"])
        self.assertNotIn("license.documents", m["migration"]["holder_confirmed"])
        o = licensing.overview(self.root, "mpl", "fr")
        entry = next(c for c in o["to_confirm"] if c["key"] == "license.documents")
        self.assertEqual(entry["label"], "Documents juridiques d'origine du script importé (LICENSE, COPYING, NOTICE…)")
        self.assertEqual(entry["hint"], ["LICENSE", "release/NOTICE.txt"])
        self.assertIn("--no-license-documents", entry["command"])
        self.assertTrue(any(n.startswith("export waits: the original legal documents") for n in
                            licensing.status(self.root, "mpl")["notes"]))
        self.assertTrue(licensing.confirm_publication(self.root, "mpl", license_documents=[])["ok"])
        self.assertEqual(self._manifest("mpl")["license"]["documents"], [])
        st = licensing.status(self.root, "mpl")       # files with a legal name still present: never left out silently
        self.assertTrue(any("found in the product but not declared: LICENSE (file), release/NOTICE.txt (file)" in n
                            for n in st["notes"]))

    def test_refused_declarations_write_nothing(self):
        pdir = helpers.make_product_v3(self.root, slug="mpl", profile="FREE", header=MPL_HEADER,
                                       license_overrides=_imported("MPL-2.0"))
        (pdir / "LICENSE").write_bytes(b"text\n")
        before = (pdir / "SCRIPT.json").read_bytes()
        for docs, words in ((["LICENSE", "LICENSE"], "declared twice"), ("LICENSE", "must be a list of paths"),
                            (["PRODUCT.md"], "internal file of Pine Workspace"),
                            (["README.md"], "not a legal-document name"), (["NOTICE"], "absent")):
            r = licensing.confirm_publication(self.root, "mpl", license_documents=docs)
            self.assertFalse(r["ok"], docs)
            self.assertIn(words, r["error"], docs)
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        cdir = helpers.make_product_v3(self.root, slug="paid", profile="COMMERCIAL")
        (cdir / "LICENSE").write_bytes(b"text\n")
        before = (cdir / "SCRIPT.json").read_bytes()
        for kwargs in ({"license_documents": ["LICENSE"]}, {"license_documents": []},
                       {"clear": ["license_documents"]}):
            r = licensing.confirm_publication(self.root, "paid", **kwargs)
            self.assertFalse(r["ok"], kwargs)
            self.assertIn("recorded only for the existing licence of an imported script", r["error"])
        self.assertEqual((cdir / "SCRIPT.json").read_bytes(), before)

    def test_detect_lists_the_legal_documents_next_to_the_source_without_recording(self):
        pdir = self.root / "scripts" / "to-onboard"
        pdir.mkdir()
        (pdir / "Imported Script.pine").write_text(MPL_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        (pdir / "LICENSE").write_bytes(b"text\n")
        (pdir / "NOTICE").write_bytes(b"text\n")
        before = _tree(self.root)
        r = licensing.detect_source_licence(self.root, "scripts/to-onboard/Imported Script.pine")
        self.assertEqual(r["legal_document_candidates"],
                         [{"path": "LICENSE", "kind": "file", "declarable": True, "reason": None},
                          {"path": "NOTICE", "kind": "file", "declarable": True, "reason": None}])
        self.assertNotIn("documents", r["record_if_confirmed"])
        self.assertIn("--license-document", r["note"])
        self.assertEqual(_tree(self.root), before)


class TestLicenseCommandLine20261113(unittest.TestCase):
    """Command wiring of the 2026-11-13 corrections: `license confirm --clear`
    returns a confirmed value to unknown (C-06); `license status` exits 1 when
    it fails (audit E11)."""

    def _cli(self, root, *args):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, "-m", "tools.pws_workspace", "--root", str(root), "license"] + list(args),
                           capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2]))
        return r.returncode, json.loads(r.stdout)

    def test_confirm_clear_and_status_exit_code(self):
        from tools.tests import helpers
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            helpers.configure(root, holder="Ada Example Trading")
            pdir = helpers.make_product_v3(root, slug="demo", profile="COMMERCIAL")
            rc, out = self._cli(root, "confirm", "--slug", "demo", "--created-year", "2024")
            self.assertEqual(rc, 0, out)
            self.assertEqual(json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))["license"]["created_year"], 2024)
            rc, out = self._cli(root, "confirm", "--slug", "demo", "--clear", "created_year")
            self.assertEqual(rc, 0, out)
            self.assertIsNone(json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))["license"]["created_year"])
            rc, out = self._cli(root, "status", "--slug", "missing-product")
            self.assertEqual(rc, 1, out)
            self.assertFalse(out["ok"])

    def test_confirm_license_documents_options(self):
        """2026-11-14: --license-document (repeatable), --no-license-documents,
        --clear license_documents; the two first exclude each other."""
        from tools.tests import helpers
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            helpers.configure(root, holder="Bruno Exemple Indicators")
            pdir = helpers.make_product_v3(root, slug="imp", profile="FREE", header=MPL_HEADER,
                                           license_overrides=_imported("MPL-2.0"))
            (pdir / "LICENSE").write_bytes(b"text\n")
            (pdir / "NOTICE").write_bytes(b"text\n")
            manifest = pdir / "SCRIPT.json"
            rc, out = self._cli(root, "confirm", "--slug", "imp", "--license-document", "LICENSE",
                                "--license-document", "NOTICE")
            self.assertEqual(rc, 0, out)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["license"]["documents"],
                             ["LICENSE", "NOTICE"])
            rc, out = self._cli(root, "confirm", "--slug", "imp", "--license-document", "LICENSE",
                                "--no-license-documents")
            self.assertEqual((rc, out["ok"]), (1, False))
            self.assertIn("exclude each other", out["error"])
            rc, out = self._cli(root, "confirm", "--slug", "imp", "--no-license-documents")
            self.assertEqual(rc, 0, out)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["license"]["documents"], [])
            rc, out = self._cli(root, "confirm", "--slug", "imp", "--clear", "license_documents")
            self.assertEqual(rc, 0, out)
            self.assertIsNone(json.loads(manifest.read_text(encoding="utf-8"))["license"]["documents"])


if __name__ == "__main__":
    unittest.main()
