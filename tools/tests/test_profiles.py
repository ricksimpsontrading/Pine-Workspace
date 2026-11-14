# SPDX-License-Identifier: Apache-2.0
"""Licence profiles and SCRIPT.json schema v2: axes, coherence, legacy
derivation, explicit migration, header policies (2026-11-06)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import profiles, scan
from tools.tests import helpers


def product(root, slug):
    return [p for p in scan.scan_workspace(root)["products"] if p["slug"] == slug][0]


def codes(p):
    return [f["code"] for f in p["findings"]]


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_profiles_defaults_and_free_closed_variant(self):
        self.assertEqual(profiles.default_license("FREE")["id"], "CC-BY-NC-SA-4.0")
        self.assertEqual(profiles.default_license("PRIVATE")["grant"], "none")
        self.assertEqual(profiles.default_license("COMMERCIAL")["grant"], "eula")
        closed = profiles.default_license("FREE", closed_source=True)
        self.assertEqual((closed["id"], closed["grant"], closed["access"]),
                         ("PROPRIETARY", "free-use", "free"))
        self.assertEqual(profiles.profile_variant("FREE", closed), "FREE_CLOSED")
        self.assertEqual(profiles.profile_variant("FREE", profiles.default_license("FREE")), "FREE")

    def test_v2_free_registered(self):
        helpers.make_product_v2(self.root, profile="FREE")
        p = product(self.root, "my-indicator")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(p["profile"], "FREE")
        self.assertEqual(p["license"]["id"], "CC-BY-NC-SA-4.0")
        self.assertIsNone(p["distribution"])
        self.assertNotIn("MANIFEST_LEGACY_SCHEMA", codes(p))

    def test_v2_commercial_draft_eula_warns_not_blocks(self):
        helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        p = product(self.root, "paid-one")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertIn("EULA_DRAFT", codes(p))

    def test_v2_free_closed_source(self):
        helpers.make_product_v2(self.root, slug="free-closed", profile="FREE", closed_source=True)
        p = product(self.root, "free-closed")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(p["license"]["grant"], "free-use")

    def test_v2_coherence_broken_cc_closed(self):
        helpers.make_product_v2(self.root, slug="bad-cc", profile="FREE",
                                license_overrides={"source_visibility": "closed"})
        p = product(self.root, "bad-cc")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("LICENSE_VISIBILITY_MISMATCH", codes(p))

    def test_v2_library_must_be_open(self):
        helpers.make_product_v2(self.root, slug="lib-paid", kind="library", profile="COMMERCIAL",
                                body='library("LibPaid")\nexport f(float x) => x\n')
        p = product(self.root, "lib-paid")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("KIND_LIBRARY_OPEN_SOURCE", codes(p))

    def test_v2_unknown_axis_and_unknown_field(self):
        pdir = helpers.make_product_v2(self.root, slug="axis")
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["publication"]["mode"] = "youtube"
        m["extra"] = 1
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        p = product(self.root, "axis")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("MANIFEST_PUBLICATION_AXIS_INVALID", codes(p))
        self.assertIn("MANIFEST_UNKNOWN_FIELDS", codes(p))

    def test_v2_terms_ref_must_exist_inside_root(self):
        pdir = helpers.make_product_v2(self.root, slug="terms", profile="COMMERCIAL",
                                       license_overrides={"terms_ref": "release/EULA.md"})
        p = product(self.root, "terms")
        self.assertIn("LICENSE_TERMS_MISSING", codes(p))
        (pdir / "release").mkdir()
        (pdir / "release" / "EULA.md").write_text("# EULA\n", encoding="utf-8")
        p = product(self.root, "terms")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertNotIn("EULA_DRAFT", codes(p))
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["license"]["terms_ref"] = "../../outside.md"
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        self.assertIn("MANIFEST_LICENSE_FIELD_TYPE", codes(product(self.root, "terms")))

    def test_v1_legacy_derived_and_flagged(self):
        helpers.make_product(self.root, slug="legacy-paid", distribution="paid-closed-source",
                             header=helpers.PAID_HEADER)
        p = product(self.root, "legacy-paid")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(p["profile"], "COMMERCIAL")
        self.assertEqual(p["license"]["derived_from_v1"], "paid-closed-source")
        self.assertEqual(p["distribution"], "paid-closed-source")
        self.assertIn("MANIFEST_LEGACY_SCHEMA", codes(p))
        self.assertIsNone(p["publication"]["state"])
        self.assertIn("PUBLICATION_STATE_UNKNOWN", codes(p))

    def test_unknown_schema_version_broken(self):
        pdir = helpers.make_product(self.root, slug="v3")
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["schema_version"] = 4
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        p = product(self.root, "v3")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("MANIFEST_SCHEMA_VERSION", codes(p))

    def test_explicit_migration_keeps_meaning_and_reports_ambiguity(self):
        v1 = {"schema_version": 1, "id": "x", "source": "X.pine", "script_kind": "indicator",
              "distribution": "paid-closed-source"}
        new, notes, amb = profiles.migrate_manifest_v1_to_v2(v1, today="2026-11-06")
        self.assertEqual(new["profile"], "COMMERCIAL")
        self.assertEqual(new["license"]["access"], "paid")
        self.assertEqual(new["license"]["source_visibility"], "closed")
        self.assertEqual(new["migration"]["from_distribution"], "paid-closed-source")
        self.assertTrue(amb)
        self.assertEqual(new["schema_version"], 3)
        self.assertEqual(new["publication"], {"state": None, "privacy": None, "mode": None})
        free, _, amb2 = profiles.migrate_manifest_v1_to_v2(dict(v1, distribution="free-open-source"))
        self.assertEqual((free["profile"], free["license"]["id"]), ("FREE", "CC-BY-NC-SA-4.0"))
        self.assertEqual(free["publication"], {"state": None, "privacy": None, "mode": None})
        self.assertEqual(len(amb2), 1)  # the unknown publication (state, privacy, mode)
        none, _, amb3 = profiles.migrate_manifest_v1_to_v2(dict(v1, distribution="weird"))
        self.assertIsNone(none)
        self.assertTrue(amb3)

    def test_header_policy_from_identity_and_manifest_override(self):
        ident = {"configured": True, "copyright_holder": "Holder Test", "header_aliases": ["HA"]}
        pol = profiles.header_policy("FREE", profiles.default_license("FREE"), ident)
        self.assertTrue(pol["require_cc"])
        self.assertEqual(pol["holder_marks"], ["Holder Test", "HA"])
        lic = dict(profiles.default_license("COMMERCIAL"), copyright_holder="Other Co")
        pol = profiles.header_policy("COMMERCIAL", lic, ident)
        self.assertTrue(pol["require_proprietary_mark"])
        self.assertEqual(pol["holder_marks"], ["Other Co"])
        pol = profiles.header_policy("PRIVATE", profiles.default_license("PRIVATE"),
                                     {"configured": False})
        self.assertEqual(pol["holder_marks"], [])
        self.assertFalse(pol["identity_configured"])



class TestPublicationAxes(unittest.TestCase):
    """Schema 3: state / privacy / mode separated (2026-11-06 intervention)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_per_profile(self):
        self.assertEqual(profiles.default_publication("FREE"), {"state": "unpublished", "privacy": "public", "mode": "open"})
        self.assertEqual(profiles.default_publication("FREE", closed_source=True)["mode"], "protected")
        self.assertEqual(profiles.default_publication("PRIVATE"), {"state": "unpublished", "privacy": None, "mode": None})
        self.assertEqual(profiles.default_publication("COMMERCIAL")["mode"], "invite-only")

    def test_private_without_publication_is_registered(self):
        helpers.make_product_v3(self.root, slug="priv", profile="PRIVATE")
        p = product(self.root, "priv")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(p["publication"], {"state": "unpublished", "privacy": None, "mode": None})
        self.assertNotIn("PUBLICATION_STATE_UNKNOWN", codes(p))

    def test_private_publication_with_mode_defined(self):
        helpers.make_product_v3(self.root, slug="priv-pub", profile="PRIVATE",
                                publication_overrides={"state": "published", "privacy": "private", "mode": "protected"})
        p = product(self.root, "priv-pub")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertNotIn("PUBLICATION_INCOMPLETE", codes(p))

    def test_published_with_unknown_mode_warns(self):
        helpers.make_product_v3(self.root, slug="pub-unknown", profile="PRIVATE",
                                publication_overrides={"state": "published", "privacy": "private", "mode": None})
        p = product(self.root, "pub-unknown")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertIn("PUBLICATION_INCOMPLETE", codes(p))

    def test_commercial_requires_public_invite_only_for_sale(self):
        helpers.make_product_v3(self.root, slug="paid-priv", profile="COMMERCIAL",
                                publication_overrides={"privacy": "private"})
        p = product(self.root, "paid-priv")
        self.assertEqual(p["product_structure_status"], "REGISTERED")  # warning, not broken
        self.assertIn("ACCESS_PAID_PUBLICATION", codes(p))
        helpers.make_product_v3(self.root, slug="paid-ok", profile="COMMERCIAL")
        self.assertNotIn("ACCESS_PAID_PUBLICATION", codes(product(self.root, "paid-ok")))

    def test_open_mode_requires_public_source(self):
        helpers.make_product_v3(self.root, slug="free-closed-open", profile="FREE", closed_source=True,
                                publication_overrides={"mode": "open"})
        p = product(self.root, "free-closed-open")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("PUBLICATION_VISIBILITY_MISMATCH", codes(p))

    def test_library_private_open_allowed_paid_refused(self):
        helpers.make_product_v3(self.root, slug="lib-ok", kind="library", profile="FREE",
                                publication_overrides={"privacy": "private"},
                                body='library("LibOk")\nexport f(float x) => x\n')
        self.assertEqual(product(self.root, "lib-ok")["product_structure_status"], "REGISTERED")

    def test_terms_url_validation_and_warning(self):
        helpers.make_product_v3(self.root, slug="bad-url", profile="COMMERCIAL",
                                license_overrides={"terms_url": "http://example.invalid/eula"})
        self.assertIn("MANIFEST_LICENSE_FIELD_TYPE", codes(product(self.root, "bad-url")))
        helpers.make_product_v3(self.root, slug="url-no-terms", profile="COMMERCIAL",
                                license_overrides={"terms_url": "https://github.com/owner/repo/blob/main/EULA.md"})
        p = product(self.root, "url-no-terms")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertIn("TERMS_URL_WITHOUT_TERMS", codes(p))

    def test_c04_profile_and_axes_divergence_is_signalled(self):
        """Audit C-04 (2026-11-13): a profile whose licence axes describe another
        regime is signalled (warning, never blocking); the defaults are not."""
        for profile, closed in (("FREE", False), ("FREE", True), ("PRIVATE", False), ("COMMERCIAL", False)):
            slug = "default-%s-%s" % (profile.lower(), closed)
            helpers.make_product_v3(self.root, slug=slug, profile=profile, closed_source=closed)
            self.assertNotIn("PROFILE_AXES_DIVERGENCE", codes(product(self.root, slug)), slug)
        cases = (
            ("commercial-cc", "COMMERCIAL", profiles.default_license("FREE"), {"mode": "open"}, "grant 'cc'"),
            ("free-paid", "FREE", profiles.default_license("COMMERCIAL"), {"mode": "invite-only"}, "grant 'eula'"),
            ("free-none", "FREE", profiles.default_license("PRIVATE"), {"mode": "protected"}, "grant 'none'"),
            ("private-eula", "PRIVATE", profiles.default_license("COMMERCIAL"), {}, "access 'paid'"),
        )
        for slug, profile, lic, pub, words in cases:
            helpers.make_product_v3(self.root, slug=slug, profile=profile, license_overrides=dict(lic),
                                    publication_overrides=pub)
            p = product(self.root, slug)
            self.assertEqual(p["product_structure_status"], "REGISTERED", slug)
            finding = [f for f in p["findings"] if f["code"] == "PROFILE_AXES_DIVERGENCE"]
            self.assertEqual(len(finding), 1, slug)
            self.assertEqual(finding[0]["severity"], "WARNING")
            self.assertIn(words, finding[0]["detail"], slug)

    def test_c02_attached_draft_terms_stay_draft(self):
        """Audit C-02 (2026-11-13): attaching a document never settles the
        terms by itself — an attached draft keeps EULA_DRAFT / TERMS_DRAFT."""
        pdir = helpers.make_product_v3(self.root, slug="paid", profile="COMMERCIAL",
                                       license_overrides={"terms_ref": "release/EULA.md"})
        (pdir / "release").mkdir()
        for text in ("> **%s** — missing: X\n\n# EULA\n" % profiles.DRAFT_MARKER, "# EULA\nProvider: {{PROVIDER_LEGAL_NAME}}\n"):
            (pdir / "release" / "EULA.md").write_text(text, encoding="utf-8")
            p = product(self.root, "paid")
            self.assertEqual(p["product_structure_status"], "REGISTERED")
            self.assertIn("EULA_DRAFT", codes(p))
        (pdir / "release" / "EULA.md").write_text("# EULA\nalert: {{ticker}}\n", encoding="utf-8")
        self.assertNotIn("EULA_DRAFT", codes(product(self.root, "paid")))
        cdir = helpers.make_product_v3(self.root, slug="closed", profile="FREE", closed_source=True,
                                       license_overrides={"terms_ref": "release/FREE_USE_GRANT.md"})
        (cdir / "release").mkdir()
        (cdir / "release" / "FREE_USE_GRANT.md").write_text("> **%s**\n" % profiles.DRAFT_MARKER, encoding="utf-8")
        self.assertIn("TERMS_DRAFT", codes(product(self.root, "closed")))

    def test_c19_unrecordable_licence_is_explained_never_replaced(self):
        """Audit C-19 (2026-11-13). CONTRACT CHANGE (decision of the holder of
        2026-11-13 recording the licences of imported scripts): a licence of the
        closed list declared as a PROFILE licence (origin absent) stays BROKEN,
        and the detail now explains how it is recorded — as the existing licence
        of an imported script — instead of "schema 3 cannot record"; an unknown
        licence is still to analyse; nothing is ever replaced."""
        for lid, words in (("MPL-2.0", "MPL-2.0 is recorded only as the existing licence of an imported script"),
                           ("mit", "MIT is recorded only as the existing licence of an imported script"),
                           ("Example-Community-1.0", "licence not recognized")):
            slug = "lic-%s" % lid.lower().replace(".", "-")
            helpers.make_product_v3(self.root, slug=slug, profile="FREE",
                                    license_overrides={"id": lid, "grant": "none"})
            p = product(self.root, slug)
            self.assertEqual(p["product_structure_status"], "BROKEN")
            detail = [f["detail"] for f in p["findings"] if f["code"] == "MANIFEST_LICENSE_AXIS_INVALID"][0]
            self.assertIn(words, detail, lid)
            self.assertIn("never", detail, lid)
        self.assertIn("to analyse", detail)
        self.assertEqual(profiles.recognized_license(" apache-2.0 "), "Apache-2.0")
        self.assertIsNone(profiles.recognized_license("PROPRIETARY-ISH"))

    def test_v2_legacy_read_and_explicit_migration(self):
        m = helpers.v2_manifest_legacy("legacy-v2", "My Indicator.pine", publication="tradingview-private")
        helpers.make_product_v3(self.root, slug="legacy-v2", profile="COMMERCIAL", manifest=m)
        p = product(self.root, "legacy-v2")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertIn("MANIFEST_LEGACY_SCHEMA", codes(p))
        self.assertEqual(p["publication"]["privacy"], "private")
        self.assertIsNone(p["publication"]["mode"])
        self.assertIsNone(p["publication"]["state"])
        new, notes, amb = profiles.migrate_manifest_to_v3(m, today="2026-11-06")
        self.assertEqual(new["schema_version"], 3)
        self.assertEqual(new["publication"], {"state": None, "privacy": "private", "mode": None})
        self.assertNotIn("publication", new["license"])
        self.assertEqual(new["migration"]["from_publication"], "tradingview-private")
        self.assertTrue(any("unknown mode" in a for a in amb))
        # the three mode values: mode kept, privacy NEVER deduced
        for value, mode in (("tradingview-open", "open"), ("tradingview-protected", "protected"),
                            ("tradingview-invite-only", "invite-only")):
            legacy = helpers.v2_manifest_legacy("x", "X.pine", publication=value)
            legacy["license"]["created_year"] = 2021
            nv, _, ambv = profiles.migrate_manifest_to_v3(legacy)
            self.assertEqual(nv["publication"], {"state": None, "privacy": None, "mode": mode}, value)
            self.assertEqual(nv["license"]["created_year"], 2021)  # known year preserved
            self.assertTrue(any("privacy" in a for a in ambv), value)
            self.assertTrue(any("state unknown" in a for a in ambv), value)
        unp = helpers.v2_manifest_legacy("u", "X.pine", publication="unpublished")
        self.assertEqual(profiles.migrate_manifest_to_v3(unp)[0]["publication"],
                         {"state": "unpublished", "privacy": None, "mode": None})
        bad = helpers.v2_manifest_legacy("bad", "X.pine", publication="youtube")
        self.assertIsNone(profiles.migrate_manifest_to_v3(bad)[0])



CLOSED_LIST = ("MPL-2.0", "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
               "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
               "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
               "AGPL-3.0-only", "AGPL-3.0-or-later")
# the manifest of the real product of the workspace, shape only (fictitious slug):
# schema 3, profile licence PROPRIETARY / eula / closed / paid, migration block
CMA_SHAPED = {
    "id": "cma-shaped", "schema_version": 3, "script_kind": "indicator", "source": "My Indicator.pine",
    "profile": "COMMERCIAL",
    "license": {"access": "paid", "copyright_holder": None, "created_year": None, "grant": "eula",
                "id": "PROPRIETARY", "source_visibility": "closed", "terms_ref": None, "terms_url": None},
    "publication": {"mode": None, "privacy": None, "state": None},
    "migration": {"from_publication": "tradingview-invite-only", "from_schema": 2, "note": "fixture",
                  "on": "2026-11-06", "previous": {"from_distribution": "paid-closed-source", "from_schema": 1,
                                                   "note": "fixture", "on": "2026-11-06"},
                  "rectifications": [{"field": "publication.privacy", "from": "public", "on": "2026-11-06",
                                      "reason": "fixture", "step": "m006", "to": None}]},
}


def imported(lid, status="confirmed", **axes):
    lic = {"id": lid, "grant": profiles.imported_grant(lid) if lid else "license", "origin": "imported",
           "status": status, "source_visibility": "public", "access": "free"}
    lic.update(axes)
    return lic


class TestImportedLicences20261113(unittest.TestCase):
    """Audit C-19, decision of the holder of 2026-11-13: the licences of
    imported scripts are RECORDED (compatible extension of schema 3): closed
    list of exact SPDX identifiers, explicit « to analyse » state, conflicts as
    warnings, profiles never forcing the licence, earlier manifests unchanged."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make(self, slug, lic, profile="FREE", pub=None, header=None):
        helpers.make_product_v3(self.root, slug=slug, profile=profile, license_overrides=lic,
                                publication_overrides=pub, header=header or "// © 2021 Zeta Example\n"
                                                                            "// Version: 1.0.0\n//@version=6\n")
        return product(self.root, slug)

    def test_closed_list_exact_identifiers(self):
        self.assertEqual(profiles.IMPORTED_LICENSE_IDS, CLOSED_LIST)
        self.assertEqual(profiles.IMPORTABLE_LICENSE_IDS, ("CC-BY-NC-SA-4.0",) + CLOSED_LIST)
        for deprecated in ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0"):
            self.assertNotIn(deprecated, profiles.IMPORTABLE_LICENSE_IDS)
            self.assertEqual(profiles.deprecated_license(deprecated.lower()), deprecated)
        self.assertEqual(profiles.LICENSE_IDS, ("CC-BY-NC-SA-4.0", "PROPRIETARY"))   # the profiles are unchanged

    def test_each_licence_of_the_closed_list_is_recorded(self):
        for lid in profiles.IMPORTABLE_LICENSE_IDS:
            slug = "imp-%s" % lid.lower().replace(".", "-")
            p = self._make(slug, imported(lid))
            self.assertEqual(p["product_structure_status"], "REGISTERED", (lid, codes(p)))
            self.assertEqual((p["license"]["id"], p["license"]["origin"], p["license"]["status"]),
                             (lid, "imported", "confirmed"))
            self.assertEqual(p["license"]["grant"], "cc" if lid == "CC-BY-NC-SA-4.0" else "license")
            self.assertEqual([c for c in codes(p) if c not in ("PUBLICATION_STATE_UNKNOWN",)], [], lid)

    def test_profile_never_forces_the_licence_of_an_imported_script(self):
        for profile, pub, access in (("FREE", None, "free"),
                                     ("PRIVATE", {"state": "unpublished", "privacy": None, "mode": None}, "restricted"),
                                     ("COMMERCIAL", {"mode": "open"}, "free")):
            p = self._make("mpl-%s" % profile.lower(), imported("MPL-2.0", access=access), profile, pub)
            self.assertEqual(p["product_structure_status"], "REGISTERED", profile)
            self.assertNotIn("PROFILE_AXES_DIVERGENCE", codes(p), profile)
            self.assertNotIn("ACCESS_PAID_WITHOUT_EULA", codes(p), profile)
        # a FREE or PRIVATE profile with paid access still diverges (access axis)
        p = self._make("mit-free-paid", imported("MIT", access="paid"), "FREE", {"mode": "invite-only"})
        self.assertIn("PROFILE_AXES_DIVERGENCE", codes(p))
        self.assertNotIn("ACCESS_PAID_WITHOUT_EULA", codes(p))
        pol = profiles.header_policy("FREE", p["license"], {"configured": True, "copyright_holder": "Holder Test"})
        self.assertEqual((pol["origin"], pol["license_status"], pol["require_cc"], pol["require_proprietary_mark"]),
                         ("imported", "confirmed", False, False))

    def test_deprecated_ambiguous_and_unlisted_identifiers_are_never_recorded(self):
        for lid in ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "GPL-3.0+"):
            p = self._make("dep-%s" % lid.lower().replace(".", "-").replace("+", "plus"), imported(lid))
            self.assertEqual(p["product_structure_status"], "BROKEN", lid)
            detail = [f["detail"] for f in p["findings"] if f["code"] == "MANIFEST_LICENSE_AXIS_INVALID"][0]
            words = ("deprecated SPDX identifier (\"+\" form)" if lid.endswith("+")
                     else "deprecated and ambiguous SPDX identifier (neither \"only\" nor \"or later\")")
            for w in (words, "never recorded", "-or-later", "to-analyse"):
                self.assertIn(w, detail, lid)
        for lid, words in (("ISC", "licence not recognized"), ("CC-BY-SA-4.0", "licence not recognized"),
                           ("LicenseRef-Custom", "to analyse"), ("mpl-2.0", "exact identifier 'MPL-2.0'"),
                           ("PROPRIETARY", "PROPRIETARY is the licence of the PRIVATE")):
            p = self._make("bad-%s" % lid.lower().replace(".", "-"), imported(lid))
            self.assertEqual(p["product_structure_status"], "BROKEN", lid)
            detail = [f["detail"] for f in p["findings"] if f["code"] == "MANIFEST_LICENSE_AXIS_INVALID"][0]
            self.assertIn(words, detail, lid)

    def test_to_analyse_is_explicit_and_never_broken(self):
        p = self._make("custom", imported(None, status="to-analyse"))
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        finding = [f for f in p["findings"] if f["code"] == "LICENSE_TO_ANALYSE"][0]
        self.assertEqual(finding["severity"], "WARNING")
        for words in ("to analyse", "current work continues", "release preparation and export"):
            self.assertIn(words, finding["detail"])
        self.assertEqual(len(profiles.license_release_blockers(p["license"])), 1)
        self.assertEqual(profiles.license_release_blockers(imported("MPL-2.0")), [])
        self.assertEqual(profiles.license_release_blockers(profiles.default_license("COMMERCIAL")), [])
        # an identifier is never recorded with the « to analyse » state, nor missing when confirmed
        for lic in (imported("MPL-2.0", status="to-analyse"), imported(None)):
            p = self._make("bad-state-%s" % lic["status"], lic)
            self.assertEqual(p["product_structure_status"], "BROKEN", lic)

    def test_schema_rules_of_the_new_fields(self):
        cases = (
            ("status-without-origin", dict(profiles.default_license("PRIVATE"), status="confirmed"),
             "MANIFEST_LICENSE_AXIS_INVALID"),
            ("origin-without-status", {k: v for k, v in imported("MIT").items() if k != "status"},
             "MANIFEST_LICENSE_AXIS_INVALID"),
            ("origin-unknown", dict(imported("MIT"), origin="third-party"), "MANIFEST_LICENSE_AXIS_INVALID"),
            ("status-unknown", dict(imported("MIT"), status="maybe"), "MANIFEST_LICENSE_AXIS_INVALID"),
            ("grant-license-on-profile", dict(profiles.default_license("PRIVATE"), grant="license"),
             "LICENSE_GRANT_MISMATCH"),
            ("imported-grant-none", dict(imported("MPL-2.0"), grant="none"), "LICENSE_GRANT_MISMATCH"),
            ("imported-cc-grant-license", dict(imported("CC-BY-NC-SA-4.0"), grant="license"),
             "LICENSE_GRANT_MISMATCH"),
        )
        for slug, lic, code in cases:
            p = self._make(slug, lic, "PRIVATE", {"state": "unpublished", "privacy": None, "mode": None})
            self.assertEqual(p["product_structure_status"], "BROKEN", slug)
            self.assertIn(code, codes(p), slug)
            if slug in ("origin-without-status", "status-unknown"):     # one finding, on the status only
                self.assertEqual(len([f for f in p["findings"] if f["code"] == code]), 1, slug)
        # schema 2 never carries the new fields
        m = helpers.v2_manifest_legacy("legacy-imp", "My Indicator.pine")
        m["license"].update(origin="imported", status="confirmed")
        helpers.make_product_v3(self.root, slug="legacy-imp", profile="COMMERCIAL", manifest=m)
        p = product(self.root, "legacy-imp")
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertIn("MANIFEST_LICENSE_UNKNOWN_FIELDS", codes(p))

    def test_conflicts_are_warnings_to_analyse_never_a_block(self):
        p = self._make("gpl-paid", imported("GPL-3.0-only", source_visibility="closed", access="paid"),
                       "COMMERCIAL", {"privacy": "public", "mode": "invite-only"})
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        conflicts = [f for f in p["findings"] if f["code"] == "IMPORTED_LICENSE_CONFLICT"]
        self.assertEqual(len(conflicts), 3)
        self.assertEqual({f["severity"] for f in conflicts}, {"WARNING"})
        for words in ("closed source", "'invite-only'", "paid access"):
            self.assertTrue(any(words in f["detail"] for f in conflicts), words)
        self.assertTrue(all("never an automatic block nor a legal conclusion" in f["detail"] for f in conflicts))
        p = self._make("mpl-protected", imported("MPL-2.0"), "FREE", {"mode": "protected"})
        details = [f["detail"] for f in p["findings"] if f["code"] == "IMPORTED_LICENSE_CONFLICT"]
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].startswith("copyleft licence MPL-2.0 with a TradingView mode 'protected'"))
        p = self._make("mit-closed", imported("MIT", source_visibility="closed"), "PRIVATE",
                       {"state": "unpublished", "privacy": None, "mode": None})
        detail = [f["detail"] for f in p["findings"] if f["code"] == "IMPORTED_LICENSE_CONFLICT"][0]
        self.assertIn("its notice (copyright line and licence text) must be kept", detail)
        p = self._make("cc-paid", imported("CC-BY-NC-SA-4.0", access="paid"), "FREE", {"mode": "open"})
        self.assertTrue(any("NonCommercial" in f["detail"] for f in p["findings"]
                            if f["code"] == "IMPORTED_LICENSE_CONFLICT"))
        p = self._make("cc-closed", imported("CC-BY-NC-SA-4.0", source_visibility="closed"), "FREE",
                       {"mode": "protected"})
        self.assertIn("LICENSE_VISIBILITY_MISMATCH", codes(p))       # rule of the licence itself, unchanged

    # ---- independent counter-verification of 2026-11-13 (C-19: m1, m3) -------------------

    def test_m1_agpl_plus_is_a_deprecated_identifier_never_recorded(self):
        self.assertEqual(profiles.DEPRECATED_LICENSE_IDS,
                         ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0",
                          "GPL-2.0+", "GPL-3.0+", "LGPL-2.1+", "LGPL-3.0+", "AGPL-3.0+"))
        self.assertEqual(profiles.deprecated_license("AGPL-3.0+"), "AGPL-3.0+")
        self.assertEqual(profiles.license_family("AGPL-3.0+"), "AGPL")
        p = self._make("dep-agpl-plus", imported("AGPL-3.0+"))
        self.assertEqual(p["product_structure_status"], "BROKEN")
        detail = [f["detail"] for f in p["findings"] if f["code"] == "MANIFEST_LICENSE_AXIS_INVALID"][0]
        for w in ("deprecated SPDX identifier (\"+\" form)", "never recorded", "-or-later"):
            self.assertIn(w, detail)

    def test_m3_cc_with_a_closed_source_is_broken_never_also_a_conflict_to_analyse(self):
        """The mechanical rule of CC BY-NC-SA 4.0 (source public) stays BROKEN;
        the same closed source is never also « to analyse, never an automatic
        block ». The other conflicts of an imported CC licence stay warnings."""
        lic = imported("CC-BY-NC-SA-4.0", source_visibility="closed")
        p = self._make("cc-closed-protected", lic, "FREE", {"mode": "protected"})
        self.assertEqual(p["product_structure_status"], "BROKEN")
        self.assertEqual([f["severity"] for f in p["findings"] if f["code"] == "LICENSE_VISIBILITY_MISMATCH"],
                         ["BROKEN"])
        details = [f["detail"] for f in p["findings"] if f["code"] == "IMPORTED_LICENSE_CONFLICT"]
        self.assertFalse(any("closed source" in d for d in details), details)
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].startswith("copyleft licence CC-BY-NC-SA-4.0 with a TradingView mode 'protected'"))
        self.assertEqual(profiles.imported_license_conflicts(lic, {"mode": "open"}), [])
        self.assertEqual(len(profiles.imported_license_conflicts(dict(lic, access="paid"), {})), 1)   # NonCommercial
        # a copyleft licence without that mechanical rule keeps its closed-source conflict
        self.assertEqual(profiles.imported_license_conflicts(imported("GPL-3.0-only", source_visibility="closed"), {}),
                         ["copyleft licence GPL-3.0-only with a closed source (source_visibility 'closed')"])

    def test_earlier_manifests_valid_and_their_validated_view_unchanged(self):
        """No migration: every earlier manifest keeps its validity and its
        validated licence (the new fields appear only when recorded)."""
        before_keys = {"id", "grant", "source_visibility", "access", "copyright_holder", "created_year",
                       "terms_ref", "terms_url"}
        for profile, closed in (("FREE", False), ("FREE", True), ("PRIVATE", False), ("COMMERCIAL", False)):
            slug = "old-%s-%s" % (profile.lower(), closed)
            helpers.make_product_v3(self.root, slug=slug, profile=profile, closed_source=closed)
            p = product(self.root, slug)
            self.assertEqual(p["product_structure_status"], "REGISTERED", slug)
            self.assertEqual(set(p["license"]), before_keys, slug)
        m = json.loads(json.dumps(CMA_SHAPED))
        pdir = helpers.make_product_v3(self.root, slug="cma-shaped", profile="COMMERCIAL", manifest=m)
        raw = (pdir / "SCRIPT.json").read_bytes()
        p = product(self.root, "cma-shaped")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertEqual(sorted(set(codes(p))), ["EULA_DRAFT", "PUBLICATION_STATE_UNKNOWN"])
        self.assertEqual(p["license"], CMA_SHAPED["license"])
        self.assertEqual(profiles.license_release_blockers(p["license"]), [])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), raw)
        self.assertEqual(profiles.rectify_publication_derivations(m)[0]["license"], CMA_SHAPED["license"])


class TestImportedLegalDocuments20261114(unittest.TestCase):
    """Holder's request of 2026-11-14: `license.documents` lists the original
    legal documents of an imported script (compatible extension of schema 3:
    optional, imported licences only, every earlier manifest unchanged);
    names and places are a closed rule; a candidate is found by its name but
    never accepted because of it; an unavailable document is a warning (the
    export waits), never a block of current work. Fictitious products."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make(self, slug, lic, profile="FREE", files=()):
        pdir = helpers.make_product_v3(self.root, slug=slug, profile=profile, license_overrides=lic,
                                       header="// © 2021 Zeta Example\n// Version: 1.0.0\n//@version=6\n")
        for rel in files:
            (pdir / rel).parent.mkdir(parents=True, exist_ok=True)
            (pdir / rel).write_text("Fictitious legal text\n", encoding="utf-8")
        return pdir, product(self.root, slug)

    def test_names_and_places_of_a_legal_document(self):
        for rel in ("LICENSE", "LICENCE", "LICENSE.md", "LICENSE.txt", "LICENSE-MIT", "LICENSE.Apache-2.0",
                    "license.txt", "COPYING", "COPYING.LESSER", "NOTICE", "NOTICES", "NOTICE.fr.txt", "COPYRIGHT",
                    "AUTHORS", "PATENTS", "CREDITS.md", "ATTRIBUTION.md", "CONTRIBUTORS", "THIRD_PARTY_NOTICES.txt",
                    "THIRD-PARTY-LICENSES.md", "UNLICENSE", "LICENSES.md",
                    "release/LICENSE.md", "release/NOTICE.txt", "LICENSES/Apache-2.0.txt", "LICENSES/LicenseRef-x.txt"):
            self.assertIsNone(profiles.legal_document_path_problem(rel), rel)
        for rel, words in (("docs/LICENSE", "must lie at the product root"), ("release/legal/NOTICE", "must lie"),
                           ("../LICENSE", "plain relative POSIX path"), ("./LICENSE", "plain relative POSIX path"),
                           ("/LICENSE", "relative path"), ("~/LICENSE", "relative path"), ("C:/LICENSE", "relative path"),
                           ("LICENSE ", "relative path"), ("release\\LICENSE", "plain relative POSIX path"),
                           ("README.md", "not a legal-document name"), ("LICENSED.md", "not a legal-document name"),
                           ("NOTICEBOARD.md", "not a legal-document name"), ("LICENSE.pine", "is not a legal document"),
                           ("NOTICE.json", "is not a legal document"), ("LICENSES/.DS_Store", "hidden file"),
                           ("LICENSES/id_rsa", "text extension"), ("LICENSES/CLAUDE.md", "internal file"),
                           ("PRODUCT.md", "internal file"), ("LICENSE\u200b", "invisible or reordering"),
                           ("LICENSE\u202etxt.exe", "invisible or reordering"), ("LICENSE-" + "x" * 300, "too long"),
                           ("", "non-empty"), (None, "non-empty")):
            problem = profiles.legal_document_path_problem(rel)
            self.assertIsNotNone(problem, rel)
            self.assertIn(words, problem, rel)
        self.assertEqual([profiles.legal_document_target(r) for r in ("LICENSE", "release/NOTICE.md",
                                                                       "LICENSES/MIT.txt")],
                         ["LICENSE", "NOTICE.md", "LICENSES/MIT.txt"])

    def test_candidates_are_found_by_name_never_accepted_by_it(self):
        """Searched in the whole product (internal folders excepted); a candidate
        that cannot be declared where it is says why (cross-check of 2026-11-14:
        nothing is left out silently because of its place, kind or name)."""
        pdir, _ = self._make("cands", imported("Apache-2.0"),
                             files=("LICENSE", "NOTICE.txt", "AUTHORS", "release/COPYING", "release/old/NOTICE",
                                    "LICENSES/Apache-2.0.txt", "LICENSES/id_rsa", "LICENSES/old/MIT.txt",
                                    "docs/LICENSE", "legal/PATENTS", "research/third-party/LICENSE",
                                    "validation/LICENSE.txt", "tests/NOTICE", "README.md", "LICENSE.json"))
        os.symlink(str(pdir / "LICENSE"), str(pdir / "COPYRIGHT"))
        (pdir / "LICENSES" / ".DS_Store").write_bytes(b"x")
        found = {c["path"]: (c["kind"], c["declarable"]) for c in profiles.legal_document_candidates(pdir)}
        self.assertEqual(found, {"AUTHORS": ("file", True), "COPYRIGHT": ("symlink", False), "LICENSE": ("file", True),
                                 "NOTICE.txt": ("file", True), "release/COPYING": ("file", True),
                                 "release/old/NOTICE": ("file", False), "LICENSES/Apache-2.0.txt": ("file", True),
                                 "LICENSES/id_rsa": ("file", False), "LICENSES/old": ("folder", False),
                                 "docs/LICENSE": ("file", False), "legal/PATENTS": ("file", False)})
        reasons = {c["path"]: c["reason"] for c in profiles.legal_document_candidates(pdir)}
        self.assertIn("must lie at the product root", reasons["docs/LICENSE"])
        self.assertIn("symbolic link", reasons["COPYRIGHT"])
        # a folder named like a legal document, and a LICENSES/ that is a link, may hide documents
        lower, _ = self._make("lower", imported("MIT"), files=("licenses/MIT.txt",))
        self.assertEqual([(c["path"], c["kind"]) for c in profiles.legal_document_candidates(lower)],
                         [("licenses", "folder")])
        linked, _ = self._make("linked", imported("MIT"), files=("LICENSE",))
        outside = Path(self.tmp.name) / "third"
        outside.mkdir()
        os.symlink(str(outside), str(linked / "LICENSES"))
        self.assertIn({"path": "LICENSES", "kind": "symlink", "declarable": False,
                       "reason": "a symbolic link — never followed"}, profiles.legal_document_candidates(linked))

    def test_declaration_rules_and_compatibility(self):
        pdir, p = self._make("declared", dict(imported("Apache-2.0"), documents=["LICENSE", "release/NOTICE.md"]),
                             files=("LICENSE", "release/NOTICE.md"))
        self.assertEqual(p["product_structure_status"], "REGISTERED", codes(p))
        self.assertEqual(p["license"]["documents"], ["LICENSE", "release/NOTICE.md"])
        self.assertNotIn("LICENSE_DOCUMENT_UNAVAILABLE", codes(p))
        _, p = self._make("none", dict(imported("MPL-2.0"), documents=[]))
        self.assertEqual((p["product_structure_status"], p["license"]["documents"]), ("REGISTERED", []))
        _, p = self._make("undeclared", imported("MPL-2.0"))
        self.assertNotIn("documents", p["license"])                      # absent: not declared, view unchanged
        for slug, lic, code, words in (
                ("profile-docs", dict(profiles.default_license("FREE"), documents=["LICENSE"]),
                 "MANIFEST_LICENSE_AXIS_INVALID", "applies only to the existing licence of an imported script"),
                ("not-a-list", dict(imported("MIT"), documents="LICENSE"), "MANIFEST_LICENSE_FIELD_TYPE",
                 "must be a list of paths"),
                ("outside", dict(imported("MIT"), documents=["docs/LICENSE"]), "MANIFEST_LICENSE_FIELD_TYPE",
                 "must lie at the product root"),
                ("twice", dict(imported("MIT"), documents=["LICENSE", "LICENSE"]), "MANIFEST_LICENSE_FIELD_TYPE",
                 "declared twice"),
                ("case", dict(imported("MIT"), documents=["LICENSE", "license"]), "MANIFEST_LICENSE_FIELD_TYPE",
                 "only by case"),
                ("source", dict(imported("MIT"), documents=["My Indicator.pine"]), "MANIFEST_LICENSE_FIELD_TYPE",
                 "is not a legal document")):
            _, p = self._make(slug, lic)
            self.assertEqual(p["product_structure_status"], "BROKEN", slug)
            self.assertTrue(any(f["code"] == code and words in f["detail"] for f in p["findings"]), (slug, codes(p)))
        # schema 2 never carries the field
        m = helpers.v2_manifest_legacy("legacy-docs", "My Indicator.pine")
        m["license"]["documents"] = []
        helpers.make_product_v3(self.root, slug="legacy-docs", profile="COMMERCIAL", manifest=m)
        self.assertIn("MANIFEST_LICENSE_UNKNOWN_FIELDS", codes(product(self.root, "legacy-docs")))

    def test_an_unavailable_declared_document_is_a_warning_never_a_block(self):
        pdir, p = self._make("gone", dict(imported("Apache-2.0"), documents=["LICENSE", "NOTICE", "release/COPYING"]),
                             files=("LICENSE",))
        os.symlink(str(pdir / "LICENSE"), str(pdir / "NOTICE"))
        p = product(self.root, "gone")
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        details = [f["detail"] for f in p["findings"] if f["code"] == "LICENSE_DOCUMENT_UNAVAILABLE"]
        self.assertEqual({f["severity"] for f in p["findings"] if f["code"] == "LICENSE_DOCUMENT_UNAVAILABLE"},
                         {"WARNING"})
        self.assertEqual(len(details), 2)
        self.assertTrue(any(d.startswith("declared legal document NOTICE is a symbolic link") for d in details))
        self.assertTrue(any(d.startswith("declared legal document release/COPYING is missing") for d in details))
        self.assertTrue(all("current work continues" in d for d in details))

    def test_the_cma_shaped_manifest_stays_unchanged(self):
        m = json.loads(json.dumps(CMA_SHAPED))
        pdir = helpers.make_product_v3(self.root, slug="cma-shaped", profile="COMMERCIAL", manifest=m)
        raw = (pdir / "SCRIPT.json").read_bytes()
        p = product(self.root, "cma-shaped")
        self.assertEqual(p["license"], CMA_SHAPED["license"])
        self.assertEqual(sorted(set(codes(p))), ["EULA_DRAFT", "PUBLICATION_STATE_UNKNOWN"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), raw)


class TestPublicationRectification(unittest.TestCase):
    """m006: values deduced by the first schema-3 migration go back to null,
    traced; holder-confirmed values are never touched; idempotent."""

    def _v3(self, from_pub, privacy, mode, previous=None, confirmed=None):
        m = helpers.v3_manifest("x", "X.pine", profile="COMMERCIAL",
                                publication_overrides={"state": None, "privacy": privacy, "mode": mode})
        m["migration"] = {"from_schema": 2, "from_publication": from_pub, "on": "2026-11-06"}
        if previous:
            m["migration"]["previous"] = previous
        if confirmed:
            m["migration"]["holder_confirmed"] = confirmed
        return m

    def test_deduced_privacy_reset_mode_kept(self):
        m = self._v3("tradingview-invite-only", "public", "invite-only")
        new, changes = profiles.rectify_publication_derivations(m, today="2026-11-06")
        self.assertEqual(len(changes), 1)
        self.assertEqual(new["publication"], {"state": None, "privacy": None, "mode": "invite-only"})
        rect = new["migration"]["rectifications"]
        self.assertEqual((rect[0]["field"], rect[0]["from"], rect[0]["to"], rect[0]["step"]),
                         ("publication.privacy", "public", None, "m006"))
        again, changes2 = profiles.rectify_publication_derivations(new, today="2026-11-06")
        self.assertEqual(changes2, [])  # idempotent

    def test_v1_chain_resets_mode_too(self):
        m = self._v3("tradingview-invite-only", "public", "invite-only",
                     previous={"from_schema": 1, "from_distribution": "paid-closed-source"})
        new, changes = profiles.rectify_publication_derivations(m)
        self.assertEqual(len(changes), 2)
        self.assertEqual(new["publication"], {"state": None, "privacy": None, "mode": None})

    def test_confirmed_values_preserved(self):
        m = self._v3("tradingview-open", "public", "open", confirmed=["publication.privacy"])
        new, changes = profiles.rectify_publication_derivations(m)
        self.assertEqual(changes, [])
        self.assertEqual(new["publication"]["privacy"], "public")

    def test_private_and_unpublished_untouched(self):
        for from_pub, privacy, mode in (("tradingview-private", "private", None), ("unpublished", None, None)):
            m = self._v3(from_pub, privacy, mode)
            self.assertEqual(profiles.rectify_publication_derivations(m)[1], [])


if __name__ == "__main__":
    unittest.main()
