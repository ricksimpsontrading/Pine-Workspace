# SPDX-License-Identifier: Apache-2.0
"""Guided path « Licence and terms of use » (2026-11-07): menu entry after the
action, then the script; documents and fields adapted to the profile variant;
consulting and previewing write nothing; cancelling writes nothing; saving is
limited to the chosen product, keeps existing fields and manages drafts;
nothing of the publication workflow is triggered. Fictitious products only."""
import hashlib
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core, licensing, menu, session
from tools.tests import helpers


def tree(base):
    base = Path(base)
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def find(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n
        for screen in n.get("children") or []:
            r = find(screen, node_id)
            if r:
                return r
    return None


class TestLicensePath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, language="fr")
        shutil.copytree(str(core.workspace_root() / licensing.TEMPLATES_REL), str(self.root / licensing.TEMPLATES_REL))

    def tearDown(self):
        self.tmp.cleanup()

    # ---- menu entry ---------------------------------------------------------

    def test_menu_entry_after_action_then_script_and_independent_route(self):
        m = menu.build_menu(session.session_status(self.root))
        self.assertIsNone(find(m["top"], "quality.license"))            # no product: no quality branch
        helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        m = menu.build_menu(session.session_status(self.root))
        node = find(m["top"], "quality.license")
        self.assertEqual((node["label"], node["route"], node["needs_script"], node["kind"]),
                         ("Licence et conditions d'utilisation", "pine-license", True, "action"))
        self.assertNotEqual(node["route"], find(m["top"], "quality.release")["route"])
        ids = [o["id"] for s in find(m["top"], "quality")["children"] for o in s if o["kind"] == "action"]
        self.assertEqual(ids, ["quality.local", "quality.tv", "quality.license", "quality.release", "quality.github"])
        for screen in find(m["top"], "quality")["children"]:
            self.assertEqual(screen[-1]["id"], "back")
        self.assertEqual(len(m["script_screens"]), 1)                   # the script is chosen afterwards
        self.assertEqual({o["slug"] for o in m["script_screens"][0] if o["kind"] == "script"}, {"paid-one", "free-one"})
        m_en = menu.build_menu(dict(session.session_status(self.root), language="en"))
        self.assertEqual(find(m_en["top"], "quality.license")["label"], "Licence and terms of use")

    # ---- documents and fields per profile -----------------------------------

    def test_documents_and_fields_follow_the_profile_variant(self):
        helpers.make_product_v2(self.root, slug="free-pub", profile="FREE", license_overrides={"created_year": 2024})
        helpers.make_product_v2(self.root, slug="free-closed", profile="FREE", closed_source=True,
                                license_overrides={"created_year": 2024})
        helpers.make_product_v2(self.root, slug="private-one", profile="PRIVATE", license_overrides={"created_year": 2024})
        helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL", license_overrides={"created_year": 2024})
        o = licensing.overview(self.root, "free-pub", "fr")
        self.assertEqual([d["kind"] for d in o["documents"]], ["header-free"])
        self.assertEqual((o["status"], o["fields"]["groups"], o["missing_fields"]), ("complete", [], []))
        self.assertEqual(o["profile_label"], "FREE — source public, CC BY-NC-SA 4.0")
        o = licensing.overview(self.root, "free-closed", "fr")
        self.assertEqual([d["kind"] for d in o["documents"]], ["header-proprietary", "grant"])
        self.assertEqual([g["id"] for g in o["fields"]["groups"]], ["product", "provider", "additional"])
        self.assertEqual([f["name"] for g in o["fields"]["groups"] for f in g["fields"]],
                         ["PRODUCT_NAME", "PROVIDER_CONTACT", "ADDITIONAL_TERMS"])   # only what the template provides for
        required = [f for g in o["fields"]["groups"] for f in g["fields"] if f["required"]]
        self.assertEqual([f["name"] for f in required], ["PRODUCT_NAME"])                      # no EULA field imposed
        self.assertEqual((required[0]["value"], required[0]["derived"]), (None, "Test Indicator"))
        self.assertEqual(o["status"], "complete")
        self.assertEqual([c["key"] for c in o["to_confirm"]], ["license.terms_ref"])
        o = licensing.overview(self.root, "private-one", "fr")
        self.assertEqual([(d["kind"], d["required"]) for d in o["documents"]],
                         [("header-proprietary", True), ("notice", True), ("grant", False)])
        self.assertEqual(o["documents"][1]["label"], "Notice propriétaire")
        self.assertEqual(o["documents"][2]["role_label"], "autorisation particulière facultative")
        self.assertEqual(o["status"], "complete")
        o = licensing.overview(self.root, "paid-one", "fr")
        self.assertEqual([d["kind"] for d in o["documents"]], ["header-proprietary", "eula"])
        self.assertEqual([g["id"] for g in o["fields"]["groups"]],
                         [g for g, _ in licensing.FIELD_GROUPS])
        names = [f["name"] for g in o["fields"]["groups"] for f in g["fields"]]
        self.assertEqual(sorted(names), sorted(licensing.FIELD_NAMES))
        product = next(f for g in o["fields"]["groups"] for f in g["fields"] if f["name"] == "PRODUCT_NAME")
        self.assertEqual((product["value"], product["derived"], product["source"]), (None, "Test Indicator", "derived"))
        self.assertEqual(sorted(o["missing_fields"]),
                         sorted(set(licensing.EULA_REQUIRED_FIELDS) - {"PRODUCT_NAME"}))
        self.assertEqual(o["status"], "draft")
        self.assertTrue(o["documents"][1]["draft"])
        self.assertIn("not a legally reviewed", o["legal_note"])
        self.assertTrue(o["independent_of_release"])
        # the holder of the rights (configuration) is distinct from the provider's legal identity (field)
        self.assertEqual((o["recorded"]["copyright_holder"], o["recorded"]["copyright_holder_source"]),
                         ("Holder Test", "configuration"))
        provider = next(f for g in o["fields"]["groups"] for f in g["fields"] if f["name"] == "PROVIDER_LEGAL_NAME")
        self.assertIsNone(provider["value"])
        self.assertIn("titulaire", provider["label"])
        # unknown year and publication facts are listed to confirm, never invented
        helpers.make_product_v2(self.root, slug="noyear", profile="COMMERCIAL",
                                publication_overrides={"state": None, "privacy": None, "mode": None})
        o = licensing.overview(self.root, "noyear", "en")
        self.assertEqual([c["key"] for c in o["to_confirm"]],
                         ["license.created_year", "publication.state", "publication.privacy",
                          "publication.mode", "license.terms_ref"])
        self.assertTrue(all("<" in c["command"] or c["command"].endswith(".md") for c in o["to_confirm"]))
        self.assertEqual(o["recorded"]["created_year"], None)

    # ---- consulting / previewing / cancelling write nothing --------------------

    def test_consultation_preview_and_cancel_write_nothing(self):
        pdir = helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        (pdir / "release").mkdir()
        (pdir / "release" / "eula-fields.json").write_text(json.dumps({"PROVIDER_CONTACT": "contact@example.invalid"}),
                                                           encoding="utf-8")
        before = tree(self.root)
        for lang in ("fr", "en"):
            self.assertTrue(licensing.overview(self.root, "paid-one", lang)["ok"])
        for kind in licensing.KINDS:
            self.assertTrue(licensing.render(self.root, "paid-one", kind)["ok"], kind)
        r = licensing.set_fields(self.root, "paid-one", {"PROVIDER_LEGAL_NAME": "Example Ltd"},
                                 clear=["PROVIDER_CONTACT"], dry_run=True)
        self.assertTrue(r["ok"] and r["dry_run"])
        self.assertEqual(r["changes"], [{"field": "PROVIDER_LEGAL_NAME", "old": None, "new": "Example Ltd"},
                                        {"field": "PROVIDER_CONTACT", "old": "contact@example.invalid", "new": None}])
        self.assertIsNone(r["written"])
        self.assertEqual(tree(self.root), before)                          # Back / Cancel: nothing written
        o = licensing.overview(self.root, "paid-one", "fr")
        self.assertIsNone(next(f for g in o["fields"]["groups"] for f in g["fields"]
                               if f["name"] == "PROVIDER_LEGAL_NAME")["value"])

    # ---- saving: one product, existing fields kept, drafts ---------------------

    def test_saving_is_limited_to_the_chosen_product_and_keeps_existing_fields(self):
        a = helpers.make_product_v2(self.root, slug="paid-a", profile="COMMERCIAL", license_overrides={"created_year": 2024})
        b = helpers.make_product_v2(self.root, slug="paid-b", profile="COMMERCIAL", license_overrides={"created_year": 2024})
        (a / "release").mkdir()
        (a / "release" / "eula-fields.json").write_text(json.dumps(
            {"PROVIDER_CONTACT": "contact@example.invalid", "LEGACY_NOTE": "kept as is"}), encoding="utf-8")
        before_b, before_a = tree(b), tree(a)
        # refusals write nothing: unknown field, empty value, set+clear
        for upd, clr in (({"NOT_A_FIELD": "x"}, []), ({"SUPPORT_TERMS": "  "}, []),
                         ({"SUPPORT_TERMS": "email"}, ["SUPPORT_TERMS"])):
            r = licensing.set_fields(self.root, "paid-a", upd, clear=clr)
            self.assertFalse(r["ok"], r)
        self.assertEqual(tree(a), before_a)
        r = licensing.set_fields(self.root, "paid-a", {"PROVIDER_LEGAL_NAME": "Example Ltd ",
                                                       "SUPPORT_TERMS": "email, business days"})
        self.assertTrue(r["ok"], r)
        self.assertEqual([c["field"] for c in r["changes"]], ["PROVIDER_LEGAL_NAME", "SUPPORT_TERMS"])
        self.assertEqual(r["status"], "draft")
        data = json.loads((a / "release" / "eula-fields.json").read_text(encoding="utf-8"))
        self.assertEqual(data["PROVIDER_LEGAL_NAME"], "Example Ltd")        # trimmed, never invented
        self.assertEqual(data["PROVIDER_CONTACT"], "contact@example.invalid")   # existing value kept
        self.assertEqual(data["LEGACY_NOTE"], "kept as is")                    # unknown key preserved
        self.assertEqual(tree(b), before_b)                                    # other product untouched
        changed = {k for k in set(tree(a)) | set(before_a) if tree(a).get(k) != before_a.get(k)}
        self.assertEqual(changed, {"release/eula-fields.json"})               # manifest and source untouched
        # same value again: no change, nothing written
        r = licensing.set_fields(self.root, "paid-a", {"PROVIDER_LEGAL_NAME": "Example Ltd"})
        self.assertEqual((r["changes"], r["unchanged"], r["written"]), ([], ["PROVIDER_LEGAL_NAME"], None))
        # clearing is explicit
        r = licensing.set_fields(self.root, "paid-a", {}, clear=["PROVIDER_CONTACT"])
        self.assertEqual(r["changes"], [{"field": "PROVIDER_CONTACT", "old": "contact@example.invalid", "new": None}])
        self.assertIsNone(next(f for g in licensing.overview(self.root, "paid-a")["fields"]["groups"]
                               for f in g["fields"] if f["name"] == "PROVIDER_CONTACT")["value"])
        # draft until every required field is recorded, then write and attach on explicit choice
        o = licensing.overview(self.root, "paid-a", "fr")
        self.assertEqual(o["status"], "draft")
        self.assertIn("PROVIDER_CONTACT", o["missing_fields"])
        rest = {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS if k != "PRODUCT_NAME"}
        self.assertTrue(licensing.set_fields(self.root, "paid-a", rest)["ok"])
        o = licensing.overview(self.root, "paid-a", "fr")
        self.assertEqual(o["missing_fields"], [])
        self.assertFalse(o["documents"][1]["draft"])
        self.assertEqual((o["status"], o["terms_attached"]), ("draft", False))   # complete text, not attached yet
        self.assertFalse(o["documents"][1]["on_disk"]["exists"])
        w = licensing.write_rendered(self.root, "paid-a", "eula", licensing.default_dest("eula"))
        self.assertTrue(w["ok"] and not w["draft"], w)
        self.assertNotIn(licensing.DRAFT_MARKER, (a / "release" / "EULA.md").read_text(encoding="utf-8"))
        o = licensing.overview(self.root, "paid-a", "fr")
        self.assertEqual(o["documents"][1]["on_disk"], {"path": "release/EULA.md", "exists": True,
                                                        "current": True, "draft": False})
        c = licensing.confirm_publication(self.root, "paid-a", terms_ref="release/EULA.md")
        self.assertTrue(c["ok"], c)
        m = json.loads((a / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(m["license"]["terms_ref"], "release/EULA.md")
        self.assertIn("license.terms_ref", m["migration"]["holder_confirmed"])
        o = licensing.overview(self.root, "paid-a", "fr")
        self.assertEqual((o["status"], o["terms_attached"], o["documents"][1]["attached"]), ("complete", True, True))
        self.assertEqual(o["to_confirm"], [])
        self.assertIn("not a legally reviewed", o["legal_note"])             # complete ≠ legally validated
        # a field changed afterwards makes the written copy stale, reported as such
        self.assertTrue(licensing.set_fields(self.root, "paid-a", {"SUPPORT_TERMS": "chat"})["ok"])
        self.assertFalse(licensing.overview(self.root, "paid-a")["documents"][1]["on_disk"]["current"])
        self.assertEqual(tree(b), before_b)

    def test_confirm_terms_refuses_escapes_missing_files_and_non_https(self):
        helpers.make_product_v2(self.root, slug="p", profile="COMMERCIAL")
        for bad in ("../../etc/passwd", "/etc/passwd", "release/EULA.md"):
            self.assertFalse(licensing.confirm_publication(self.root, "p", terms_ref=bad)["ok"], bad)
        self.assertFalse(licensing.confirm_publication(self.root, "p", terms_url="http://example.invalid/x")["ok"])
        self.assertTrue(licensing.confirm_publication(self.root, "p", terms_url="https://example.invalid/terms")["ok"])
        m = json.loads((self.root / "scripts" / "p" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual((m["license"]["terms_url"], m["license"]["terms_ref"]), ("https://example.invalid/terms", None))

    # ---- existing licence of an imported script (audit C-19, 2026-11-13) --------

    def test_imported_licence_kept_consulting_writes_nothing(self):
        """The guided path shows the existing licence of an imported script as
        kept (no document, no EULA field), or to analyse with the command that
        records the holder's confirmation; consulting writes nothing."""
        header = ("// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at "
                  "https://mozilla.org/MPL/2.0/\n// © zeta_author_example\n// Version: 1.0.0\n//@version=6\n")
        lic = {"id": "MPL-2.0", "grant": "license", "origin": "imported", "status": "confirmed",
               "source_visibility": "public", "access": "free"}
        helpers.make_product_v3(self.root, slug="imported-mpl", profile="FREE", header=header, license_overrides=lic)
        helpers.make_product_v3(self.root, slug="imported-pending", profile="PRIVATE", header=header,
                                license_overrides=dict(lic, id=None, status="to-analyse"),
                                publication_overrides={"state": "unpublished", "privacy": None, "mode": None})
        m = menu.build_menu(session.session_status(self.root))
        self.assertEqual({o["slug"] for o in m["script_screens"][0] if o["kind"] == "script"},
                         {"imported-mpl", "imported-pending"})               # both REGISTERED, both listed
        before = tree(self.root)
        o = licensing.overview(self.root, "imported-mpl", "fr")
        self.assertEqual((o["status"], o["documents"], o["fields"]["groups"], o["missing_fields"]),
                         ("kept", [], [], []))
        self.assertEqual(o["existing_licence"]["label"], "Licence existante conservée : MPL-2.0")
        o = licensing.overview(self.root, "imported-pending", "fr")
        self.assertEqual(o["status"], "to-analyse")
        self.assertEqual(o["to_confirm"][0]["key"], "license.id")
        self.assertEqual(o["to_confirm"][0]["hint"], "MPL-2.0")
        self.assertEqual(o["to_confirm"][0]["label"], "Licence existante du script importé (identifiant exact, liste fermée)")
        self.assertTrue(o["independent_of_release"])
        self.assertEqual(tree(self.root), before)

    # ---- the publication workflow is never triggered ---------------------------

    def test_path_never_triggers_release_review_pinets_or_tradingview(self):
        pdir = helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL", license_overrides={"created_year": 2024})
        before = tree(self.root)
        licensing.overview(self.root, "paid-one", "fr")
        licensing.render(self.root, "paid-one", "eula")
        licensing.set_fields(self.root, "paid-one", {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS
                                                     if k != "PRODUCT_NAME"})
        licensing.write_rendered(self.root, "paid-one", "eula", licensing.default_dest("eula"))
        licensing.confirm_publication(self.root, "paid-one", terms_ref="release/EULA.md")
        after = tree(self.root)
        touched = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(touched, {"scripts/paid-one/release/eula-fields.json", "scripts/paid-one/release/EULA.md",
                                   "scripts/paid-one/SCRIPT.json"})
        self.assertEqual(after["scripts/paid-one/validation/current.json"], before["scripts/paid-one/validation/current.json"])
        for never in ("release/CHANGELOG.md", "release/RELEASE_NOTES.md", "validation/runs"):
            self.assertFalse((pdir / never).exists(), never)
        self.assertFalse((self.root / ".claude" / "runtime" / "pine-local-test").exists())
        source = inspect.getsource(licensing)
        for forbidden in ("tooling", "validation.", "subprocess", "github."):
            self.assertNotIn(forbidden, source, forbidden)


if __name__ == "__main__":
    unittest.main()
