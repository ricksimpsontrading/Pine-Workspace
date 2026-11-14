# SPDX-License-Identifier: Apache-2.0
"""Guard 2026-11-06: policy-derived headers, Version inside the header only,
licence URL whitelist, work-log comments, path confinement, scripts-root
symlink (audit items 1, 2 and the profiles decision)."""
import json
import os
import tempfile
import unittest

from tools.pws_workspace import config, guard, profiles, scan, session
from tools.tests import helpers


def statuses(findings):
    return {f["check"]: f["status"] for f in findings}


class TestGuardPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        self.identity = config.identity(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _src(self, text, name="Case.pine"):
        p = self.root / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_version_in_body_does_not_satisfy_header_check(self):
        text = ("// © 2026 Holder Test\n// All Rights Reserved.\n//@version=6\n"
                'indicator("T")\n// Version: 9.9.9\nplot(close)\n')
        st = statuses(guard.check_source(self._src(text)))
        self.assertEqual(st["header-version"], "BLOCKING")
        detail = [f for f in guard.check_source(self._src(text)) if f["check"] == "header-version"][0]
        self.assertIn("outside the header", detail["detail"])

    def test_proprietary_policy_requires_mark_and_holder(self):
        pol = profiles.header_policy("COMMERCIAL", profiles.default_license("COMMERCIAL"), self.identity)
        ok = self._src(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(ok, pol, None, self.identity))
        self.assertEqual((st["header-structure"], st["header-copyright"]), ("OK", "OK"))
        wrong_holder = self._src("// © 2026 Somebody Else\n// All Rights Reserved.\n// Version: 1.0.0\n"
                                 "//@version=6\n" + helpers.MINIMAL_BODY, "wrong.pine")
        st = statuses(guard.check_source(wrong_holder, pol, None, self.identity))
        self.assertEqual(st["header-copyright"], "BLOCKING")
        alias = self._src("// © 2026 HolderAlias\n// All Rights Reserved.\n// Version: 1.0.0\n"
                          "//@version=6\n" + helpers.MINIMAL_BODY, "alias.pine")
        st = statuses(guard.check_source(alias, pol, None, self.identity))
        self.assertEqual(st["header-copyright"], "OK")
        no_mark = self._src("// © 2026 Holder Test\n// Version: 1.0.0\n//@version=6\n"
                            + helpers.MINIMAL_BODY, "nomark.pine")
        st = statuses(guard.check_source(no_mark, pol, None, self.identity))
        self.assertEqual(st["header-structure"], "BLOCKING")

    def test_cc_policy_and_unconfigured_identity_unverifiable(self):
        pol = profiles.header_policy("FREE", profiles.default_license("FREE"), {"configured": False})
        p = self._src(helpers.FREE_HEADER_HOLDER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, pol, None, {"configured": False}))
        self.assertEqual(st["header-structure"], "OK")
        self.assertEqual(st["header-copyright"], "UNVERIFIABLE")
        st = statuses(guard.check_source(p, "free-open-source", None, self.identity))
        self.assertEqual((st["header-structure"], st["header-copyright"]), ("OK", "OK"))

    def test_license_url_whitelist_in_comments_only(self):
        text = (helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY +
                "// Pivot helper derived from an MPL-2.0 notice: https://www.mozilla.org/MPL/2.0/\n")
        st = statuses(guard.check_source(self._src(text)))
        self.assertEqual(st["no-promo-urls"], "OK")
        text2 = (helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY +
                 'lbl = "https://www.mozilla.org/MPL/2.0/"\n')
        st = statuses(guard.check_source(self._src(text2, "s.pine")))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")
        text3 = helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + "// https://example.com/shop\n"
        st = statuses(guard.check_source(self._src(text3, "p.pine")))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")

    def test_worklog_comments_warning_never_blocking(self):
        text = (helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY +
                "// AUDIT: kept since lot 15c after the review\n"
                "// Claude: never change this threshold\n"
                "x = 1 // session filter (trading session, legitimate)\n")
        findings = guard.check_source(self._src(text))
        st = statuses(findings)
        self.assertEqual(st["no-worklog-comments"], "WARNING")
        w = [f for f in findings if f["check"] == "no-worklog-comments"][0]
        self.assertIn("2 comment line(s)", w["detail"])
        self.assertNotIn("BLOCKING", [f["status"] for f in findings if f["check"] == "no-worklog-comments"])
        clean = statuses(guard.check_source(self._src(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY, "c.pine")))
        self.assertEqual(clean["no-worklog-comments"], "OK")

    def test_guard_product_refuses_escaping_source(self):
        pdir = helpers.make_product_v2(self.root, slug="esc")
        outside = self.root.parent / "outside source.pine"
        outside.write_text(helpers.FREE_HEADER_HOLDER + helpers.MINIMAL_BODY, encoding="utf-8")
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["source"] = "../../../outside source.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        findings = guard.guard_product(pdir, self.identity)
        st = statuses(findings)
        self.assertEqual(st["source-exists"], "BLOCKING")
        self.assertNotIn("version-directive", st)  # never read
        m["source"] = str(outside)
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        st = statuses(guard.guard_product(pdir, self.identity))
        self.assertEqual(st["source-exists"], "BLOCKING")

    def test_guard_product_v2_end_to_end(self):
        pdir = helpers.make_product_v2(self.root, slug="v2ok", profile="COMMERCIAL")
        findings = guard.guard_product(pdir, self.identity)
        self.assertNotIn("BLOCKING", [f["status"] for f in findings])
        st = statuses(findings)
        self.assertEqual(st["header-copyright"], "OK")

    def test_symlinked_scripts_root_nothing_read(self):
        outside = self.root.parent / "outside scripts"
        (outside / "prod").mkdir(parents=True)
        (outside / "prod" / "X.pine").write_text(helpers.FREE_HEADER_HOLDER + helpers.MINIMAL_BODY,
                                                  encoding="utf-8")
        scripts = self.root / "scripts"
        scripts.rmdir()
        os.symlink(outside, scripts)
        s = scan.scan_workspace(self.root)
        self.assertTrue(s["scripts_dir_symlink"])
        self.assertEqual(s["products"], [])
        self.assertIn("SCRIPTS_ROOT_SYMLINK", [f["code"] for f in s["findings"]])
        self.assertEqual(session._registered_pine_hashes(self.root), {})

    def test_session_hashes_do_not_follow_directory_symlinks(self):
        helpers.make_product_v2(self.root, slug="real")
        outside = self.root.parent / "outside tree"
        outside.mkdir()
        (outside / "Hidden.pine").write_text("//@version=6\n", encoding="utf-8")
        os.symlink(outside, self.root / "scripts" / "real" / "linked")
        hashes = session._registered_pine_hashes(self.root)
        self.assertEqual(sorted(hashes), ["scripts/real/My Indicator.pine"])


    def test_declared_legal_reference_url(self):
        """Point 7 (2026-11-06): the product's declared terms_url is admitted in a
        comment; an undeclared URL on the same host stays forbidden; a URL in a
        user-facing string stays forbidden."""
        url = "https://github.com/owner/repo/blob/main/Published/x/EULA.md"
        lic = dict(profiles.default_license("COMMERCIAL"), terms_url=url)
        pol = profiles.header_policy("COMMERCIAL", lic, self.identity)
        header = ("// © 2026 Holder Test\n// All Rights Reserved.\n// Terms of use: %s\n"
                  "// Version: 1.0.0\n//@version=6\n" % url)
        st = statuses(guard.check_source(self._src(header + helpers.MINIMAL_BODY, "ok.pine"), pol, None, self.identity))
        self.assertEqual(st["no-promo-urls"], "OK")
        other = header.replace("Published/x/EULA.md", "Published/y/OTHER.md")
        st = statuses(guard.check_source(self._src(other + helpers.MINIMAL_BODY, "other.pine"), pol, None, self.identity))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")
        in_string = helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + 'tip = "%s"\n' % url
        st = statuses(guard.check_source(self._src(in_string, "str.pine"), pol, None, self.identity))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")
        # no declaration at all → the same URL is forbidden
        pol_none = profiles.header_policy("COMMERCIAL", profiles.default_license("COMMERCIAL"), self.identity)
        st = statuses(guard.check_source(self._src(header + helpers.MINIMAL_BODY, "undeclared.pine"), pol_none, None, self.identity))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")
        # end to end through the manifest
        pdir = helpers.make_product_v2(self.root, slug="legal-ref", profile="COMMERCIAL",
                                       header=header, license_overrides={"terms_url": url})
        st = statuses(guard.guard_product(pdir, self.identity))
        self.assertEqual(st["no-promo-urls"], "OK")


APACHE_NOTICE = ("// Portions Copyright 2021 Jane Doe\n"
                 "// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
                 "// you may not use this file except in compliance with the License.\n"
                 "// You may obtain a copy of the License at\n"
                 "//\n"
                 "//     http://www.apache.org/licenses/LICENSE-2.0\n"
                 "//\n")
MPL_EDITOR_HEADER = ("// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at "
                     "https://mozilla.org/MPL/2.0/\n// © Holder Test\n// Version: 1.0.0\n//@version=6\n")


class TestGuardCorrections20261113(unittest.TestCase):
    """Audit of 2026-11-12/13, constats C-10 to C-13, C-16 and C-19 (guard
    side), framed by decision D of the holder: third-party notices admitted
    by a targeted rule, promotional URLs still blocked, the declared licence
    checked exactly, an existing licence presented as the holder's decision."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        self.identity = config.identity(self.root)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, text, profile="COMMERCIAL", lic=None, policy=True):
        self.n += 1
        p = self.root / ("Case %d.pine" % self.n)
        p.write_text(text, encoding="utf-8")
        axes = profiles.default_license(profile)
        axes.update(lic or {})
        pol = profiles.header_policy(profile, axes, self.identity) if policy else None
        return {f["check"]: (f["status"], f["detail"], f.get("subjects"))
                for f in guard.check_source(p, pol, None, self.identity)}

    # ---- C-10: third-party licence notices -------------------------------------

    def test_c10_third_party_licence_notices_admitted_in_comments(self):
        notices = (
            APACHE_NOTICE,
            "// Helper released under CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/\n",
            "// along with this program.  If not, see <http://www.gnu.org/licenses/>.\n",
            "// You can obtain one at http://mozilla.org/MPL/2.0/.\n",
            "// SPDX: https://spdx.org/licenses/MIT.html\n",
            "// Copyright (c) 2021 Jane Doe, MIT License: https://github.com/janedoe/lib/blob/main/LICENSE\n",
            "// Portions adapted with permission from \"Example Lib\"\n"
            "// Copyright (c) 2021 Jane Doe — MIT License:\n"
            "//   https://gitlab.com/janedoe/example-lib/-/blob/main/LICENSE.md\n",
        )
        for profile, header in (("FREE", helpers.FREE_HEADER_HOLDER), ("COMMERCIAL", helpers.PROPRIETARY_HEADER)):
            for notice in notices:
                st = self._check(header + helpers.MINIMAL_BODY + notice, profile)
                self.assertEqual(st["no-promo-urls"][0], "OK", (profile, notice))

    def test_c10_promotional_or_misplaced_urls_stay_blocked(self):
        cc = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
        cases = (
            "// https://shop.example.invalid/buy\n",
            "// License: https://shop.example.invalid/LICENSE\n",                       # not a code host
            "// more tools: https://github.com/janedoe/tools/blob/main/LICENSE\n",       # not a licence notice
            "// https://creativecommons.org/licenses/../../choose/?promo=1\n",           # walks out, query
            "// https://www.gnu.org/licenses/gpl-3.0.html?ref=shop\n",
            'tip = "License: %s"\n' % cc,                                                # user-facing text
            'tip = "License: %s" // %s\n' % (cc, cc),                                    # string AND comment
            "// Portions adapted from https://www.tradingview.com/script/abcd1234/ by another author\n",
        )
        for extra in cases:
            st = self._check(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + extra)
            self.assertEqual(st["no-promo-urls"][0], "BLOCKING", extra)
            self.assertIn("never remove a licence notice", st["no-promo-urls"][1])

    # ---- C-11: the guard checks the manifest like the scan and the Stop hook -----

    def test_c11_guard_product_uses_the_validated_manifest_like_the_hook(self):
        pdir = helpers.make_product_v3(self.root, slug="broken-id", profile="COMMERCIAL",
                                       license_overrides={"id": "GPL-3.0", "access": "premium"})
        st = statuses(guard.guard_product(pdir, self.identity))
        self.assertEqual((st["manifest"], st["header-structure"]), ("BLOCKING", "UNVERIFIABLE"))
        shop = "http://shop.example.invalid/buy-now"
        pdir = helpers.make_product_v3(self.root, slug="shop-url", profile="COMMERCIAL",
                                       license_overrides={"terms_url": shop, "created_year": 2024})
        session.hook_session_start(self.root, {"session_id": "c11", "source": "startup"})
        (pdir / "My Indicator.pine").write_text(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY
                                                + "// Get the full suite: %s\n" % shop, encoding="utf-8")
        st = statuses(guard.guard_product(pdir, self.identity))
        self.assertEqual((st["manifest"], st["no-promo-urls"]), ("BLOCKING", "BLOCKING"))
        code, out = session.hook_stop(self.root, {"session_id": "c11"})
        decision = json.loads(out)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("[no-promo-urls] %s" % shop, decision["reason"])
        ok = helpers.make_product_v3(self.root, slug="fine", profile="COMMERCIAL")
        f = [x for x in guard.guard_product(ok, self.identity) if x["check"] == "manifest"][0]
        self.assertEqual(f["status"], "OK")
        self.assertIn("EULA_DRAFT", f["detail"])

    # ---- C-12: exact licence, contradictions, holder on the © line ---------------

    def test_c12_header_carries_exactly_the_declared_licence(self):
        cc = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
        free = helpers.FREE_HEADER_HOLDER
        st = self._check(free.replace(cc, "https://creativecommons.org/licenses/by-nd/4.0/") + helpers.MINIMAL_BODY, "FREE")
        self.assertEqual(st["header-structure"][0], "BLOCKING")
        st = self._check(free.replace("4.0", "3.0") + helpers.MINIMAL_BODY, "FREE")
        self.assertEqual(st["header-structure"][0], "BLOCKING")
        st = self._check(free.replace("// Version", "// All Rights Reserved.\n// Version") + helpers.MINIMAL_BODY, "FREE")
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))
        prop = helpers.PROPRIETARY_HEADER.replace("//\n", "// Licensed under CC BY-NC-SA 4.0: %s\n" % cc)
        st = self._check(prop + helpers.MINIMAL_BODY)
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))
        self.assertIn("never remove", st["header-consistency"][1])
        self.assertNotIn("header-consistency", self._check(free + helpers.MINIMAL_BODY, "FREE"))
        self.assertNotIn("header-consistency", self._check(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY))

    def test_c12_copyright_line_names_the_holder(self):
        third = ("// © 2019 Third Party Author\n// Maintained for Holder Test\n// All Rights Reserved.\n"
                 "// Version: 1.0.0\n//@version=6\n")
        st = self._check(third + helpers.MINIMAL_BODY, "PRIVATE")
        self.assertEqual(st["header-copyright"][0], "BLOCKING")
        self.assertIn("not on a © line", st["header-copyright"][1])
        both = ("// © 2024–2026 Holder Test\n// Portions © 2019 Third Party Author (used with permission)\n"
                "// All Rights Reserved.\n// Version: 1.0.0\n//@version=6\n")
        self.assertEqual(self._check(both + helpers.MINIMAL_BODY, "PRIVATE")["header-copyright"][0], "OK")

    # ---- C-13: BOM, parentheses, contacts without scheme ----------------------------

    def test_c13_bom_parentheses_and_contacts(self):
        st = self._check("\ufeff" + helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY)
        self.assertEqual((st["header-version"][0], st["header-structure"][0], st["header-copyright"][0]),
                         ("OK", "OK", "OK"))
        url = "https://example.invalid/terms_(v2)"
        st = self._check(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + "// Terms of use: %s.\n" % url,
                         lic={"terms_url": url})
        self.assertEqual(st["no-promo-urls"][0], "OK")
        for text in ('tip = "Visit www.shop.example.invalid"\n', 'tip = "mail sales@example.invalid"\n',
                     'tip = "More tools on shop.example.invalid"\n'):
            st = self._check(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + text)
            self.assertEqual((st["no-promo-urls"][0], st["no-promo-contacts"][0]), ("OK", "WARNING"), text)
        for text in ('tip = "Uses ta.dev and ta.ema; see strategy.entry"\n',
                     "// support for the author: jane@example.invalid (licence notice)\n"):
            self.assertNotIn("no-promo-contacts",
                             self._check(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY + text), text)

    # ---- C-16: header pasted before rendering -----------------------------------------

    def test_c16_unrendered_template_field_in_the_header(self):
        draft = helpers.FREE_HEADER_HOLDER.replace("© 2026", "© {{YEAR_RANGE}}")
        st = self._check(draft + helpers.MINIMAL_BODY, "FREE")
        self.assertEqual(st["header-copyright"][0], "BLOCKING")
        self.assertEqual(st["header-copyright"][2], ["{{YEAR_RANGE}}"])
        st = self._check(draft + helpers.MINIMAL_BODY, "FREE", policy=False)    # no manifest: still a fact
        self.assertEqual(st["header-copyright"][0], "BLOCKING")
        st = self._check("// International License (CC BY-NC-SA 4.0): {{CC_URL}}\n" + helpers.FREE_HEADER_HOLDER
                         + helpers.MINIMAL_BODY, "FREE")
        self.assertEqual(st["header-structure"][0], "BLOCKING")
        st = self._check(helpers.PROPRIETARY_HEADER.replace("//\n", "// alert text: {{ticker}} crossed\n")
                         + helpers.MINIMAL_BODY)
        self.assertEqual((st["header-structure"][0], st["header-copyright"][0]), ("OK", "OK"))

    # ---- C-19: an existing licence is a decision of the holder ------------------------

    def test_c19_existing_licence_header_is_presented_as_a_holder_decision(self):
        for profile in ("FREE", "PRIVATE"):
            st = self._check(MPL_EDITOR_HEADER + helpers.MINIMAL_BODY, profile)
            self.assertEqual(st["header-structure"][0], "BLOCKING", profile)
            detail = st["header-structure"][1]
            for words in ("MPL-2.0", "decision of the holder", "never remove or replace"):
                self.assertIn(words, detail, profile)
            self.assertEqual(st["no-promo-urls"][0], "OK")
        wrapped = ("// This Source Code Form is subject to the terms of the Mozilla Public\n"
                   "// License, v. 2.0. If a copy of the MPL was not distributed with this\n"
                   "// file, You can obtain one at https://mozilla.org/MPL/2.0/.\n")
        self.assertEqual(guard.header_licences(wrapped)[0], ["MPL-2.0"])
        unknown = "// Licensed under the Example Community License 1.0\n// © 2026 Holder Test\n// Version: 1.0.0\n//@version=6\n"
        st = self._check(unknown + helpers.MINIMAL_BODY, "PRIVATE")
        self.assertEqual(st["header-structure"][0], "BLOCKING")
        self.assertIn("not recognized: to analyse", st["header-structure"][1])


GPL3_OR_LATER = ("// Copyright (C) 2021 Zeta Example Author\n"
                 "// This program is free software: you can redistribute it and/or modify\n"
                 "// it under the terms of the GNU General Public License as published by\n"
                 "// the Free Software Foundation, either version 3 of the License, or\n"
                 "// (at your option) any later version.\n")
GPL3_ONLY = "// Copyright (C) 2021 Zeta Example Author\n// Licensed under the GNU General Public License, version 3.\n"
EXPAT = ("// Copyright (c) 2022 Zeta Example Author\n"
         "// Permission is hereby granted, free of charge, to any person obtaining a copy\n"
         "// of this software, subject to the following conditions:\n"
         "// The above copyright notice and this permission notice shall be included in\n"
         "// all copies or substantial portions of the Software.\n")
X11 = EXPAT + "// Except as contained in this notice, the name of the X Consortium shall not be used.\n"
MPL_THIRD = ("// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at "
             "https://mozilla.org/MPL/2.0/\n// © zeta_author_example\n")
VERSION_LINES = "// Version: 1.0.0\n//@version=6\n"


class TestImportedLicenceGuard20261113(unittest.TestCase):
    """Audit C-19, decision of the holder of 2026-11-13: the guard of an
    imported licence checks that its existing notice is present and coherent
    with license.id, never the CC header, "All Rights Reserved" nor the
    configured holder; a header detection is only a proposal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)                     # configured holder: Holder Test
        self.identity = config.identity(self.root)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, header, lid, status="confirmed", body=helpers.MINIMAL_BODY):
        self.n += 1
        p = self.root / ("Imported %d.pine" % self.n)
        p.write_text(header + VERSION_LINES + body, encoding="utf-8")
        lic = {"id": lid, "grant": profiles.imported_grant(lid) if lid else "license", "origin": "imported",
               "status": status, "source_visibility": "public", "access": "free"}
        pol = profiles.header_policy("FREE", lic, self.identity)
        return {f["check"]: (f["status"], f["detail"], f.get("subjects"))
                for f in guard.check_source(p, pol, None, self.identity)}

    def test_header_licence_proposal_is_exact_or_to_analyse(self):
        cases = (
            (MPL_THIRD, "recognized", "MPL-2.0"),
            ("// This Source Code Form is subject to the terms of the Mozilla Public\n// License, v. 2.0. If a "
             "copy of the MPL was not distributed with this\n// file, You can obtain one at "
             "https://mozilla.org/MPL/2.0/.\n", "recognized", "MPL-2.0"),
            (GPL3_OR_LATER, "recognized", "GPL-3.0-or-later"),
            (GPL3_ONLY, "recognized", "GPL-3.0-only"),
            (GPL3_OR_LATER.replace("version 3", "version 2"), "recognized", "GPL-2.0-or-later"),
            ("// GNU Lesser General Public License, version 2.1\n", "recognized", "LGPL-2.1-only"),
            ("// GNU Affero General Public License as published by the Free Software Foundation, either "
             "version 3 of the License, or (at your option) any later version.\n", "recognized", "AGPL-3.0-or-later"),
            ("// Released under the GNU General Public License.\n", "to-analyse", None),         # no version
            ("// Licensed under GPLv3 or later\n", "to-analyse", None),                         # no explicit clause
            ("// SPDX-License-Identifier: GPL-3.0\n", "to-analyse", None),                      # deprecated
            ("// SPDX-License-Identifier: GPL-3.0-or-later\n", "recognized", "GPL-3.0-or-later"),
            ("// SPDX-License-Identifier: MIT OR Apache-2.0\n", "to-analyse", None),            # expression
            ("// Released under the MIT License.\n", "to-analyse", None),                       # ambiguous term
            ("// SPDX-License-Identifier: MIT\n", "recognized", "MIT"),
            (EXPAT, "recognized", "MIT"),
            (X11, "to-analyse", None),
            ("// Licensed under the Apache License, Version 2.0\n", "recognized", "Apache-2.0"),
            ("// SPDX-License-Identifier: BSD-3-Clause\n", "recognized", "BSD-3-Clause"),
            ("// This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International "
             "(CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n// © ZetaAlgoExample\n",
             "recognized", "CC-BY-NC-SA-4.0"),
            ("// Licensed under CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\n", "to-analyse", None),
            ("// Licensed under the Example Community Trading Licence 1.0\n", "to-analyse", None),
            (MPL_THIRD + "// Portions: SPDX-License-Identifier: MIT\n", "to-analyse", None),   # several
            (MPL_THIRD + "// All Rights Reserved.\n", "to-analyse", None),                     # contradiction
            ("// © 2020 Zeta Example\n// All Rights Reserved.\n", "proprietary", "PROPRIETARY"),
            ("// Example trading helper\n", "none", None),
        )
        for header, state, proposal in cases:
            prop = guard.header_licence_proposal(header)
            self.assertEqual((prop["state"], prop["proposal"]), (state, proposal), header)
            if state == "to-analyse":
                self.assertTrue(prop["reasons"], header)
        self.assertIn("ambiguous (FSF: Expat or X11)",
                      guard.header_licence_proposal("// under the MIT License\n")["reasons"][0])

    def test_existing_notice_present_and_coherent(self):
        for header, lid in ((MPL_THIRD, "MPL-2.0"), (GPL3_OR_LATER, "GPL-3.0-or-later"), (GPL3_ONLY, "GPL-3.0-only"),
                            (EXPAT, "MIT"), ("// © 2021 Zeta\n// SPDX-License-Identifier: BSD-2-Clause\n",
                                             "BSD-2-Clause")):
            st = self._check(header, lid)
            self.assertEqual((st["header-structure"][0], st["header-copyright"][0]), ("OK", "OK"), lid)
            self.assertNotIn("header-consistency", st, lid)
            self.assertIn("configured holder is not required", st["header-copyright"][1])
        # the notice removed: BLOCKING, the object of the anomaly is the notice
        st = self._check("// © zeta_author_example\n", "MPL-2.0")
        self.assertEqual(st["header-structure"][:1] + (st["header-structure"][2],),
                         ("BLOCKING", ["MPL-2.0 notice"]))
        self.assertIn("never replace a licence notice", st["header-structure"][1])
        # « only » and « or later » are never assimilated; X11 is not MIT
        for header, lid, other in ((GPL3_OR_LATER, "GPL-3.0-only", "GPL-3.0-or-later"),
                                   (GPL3_ONLY, "GPL-3.0-or-later", "GPL-3.0-only"),
                                   (X11, "MIT", "X11"), (GPL3_ONLY, "GPL-2.0-only", "GPL-3.0-only")):
            st = self._check(header, lid)
            self.assertEqual(st["header-structure"][0], "BLOCKING", (lid, other))
            self.assertEqual(st["header-structure"][2], ["%s != %s" % (lid, other)])
            self.assertIn("never change the notice", st["header-structure"][1])
        # an ambiguous notice of the family, another licence mention: WARNING only
        st = self._check("// © 2021 Zeta\n// Released under the GNU General Public License.\n", "GPL-3.0-only")
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))
        st = self._check("// Licensed CC BY-NC-SA, © ZetaAlgoExample\n", "CC-BY-NC-SA-4.0")
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))
        self.assertIn("without an identifiable version", st["header-consistency"][1])
        st = self._check(MPL_THIRD + "// All Rights Reserved.\n", "MPL-2.0")
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))
        self.assertIn("never remove a licence notice", st["header-consistency"][1])

    def test_never_the_cc_header_the_proprietary_mark_nor_the_configured_holder(self):
        cc_third = ("// This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International "
                    "(CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n// © ZetaAlgoExample\n")
        st = self._check(cc_third, "CC-BY-NC-SA-4.0")
        self.assertEqual((st["header-structure"][0], st["header-copyright"][0]), ("OK", "OK"))
        # the same header under the FREE profile licence requires the configured holder
        p = self.root / "Profile.pine"
        p.write_text(cc_third + VERSION_LINES + helpers.MINIMAL_BODY, encoding="utf-8")
        pol = profiles.header_policy("FREE", profiles.default_license("FREE"), self.identity)
        st_profile = statuses(guard.check_source(p, pol, None, self.identity))
        self.assertEqual(st_profile["header-copyright"], "BLOCKING")
        # no copyright line at all: a warning, never a block (the original is unknown to the guard)
        st = self._check("// SPDX-License-Identifier: MIT\n", "MIT")
        self.assertEqual((st["header-structure"][0], st["header-copyright"][0]), ("OK", "WARNING"))
        self.assertIn("never invent an author", st["header-copyright"][1])

    def test_licence_to_analyse_unverifiable_never_a_violation(self):
        st = self._check("// Licensed under the Example Community Trading Licence 1.0\n// © 2024 Zeta\n",
                         None, status="to-analyse")
        self.assertEqual((st["header-structure"][0], st["header-copyright"][0]), ("UNVERIFIABLE", "OK"))
        for words in ("to analyse", "never remove or replace them", "licence statement not recognized"):
            self.assertIn(words, st["header-structure"][1])

    def test_licence_url_rule_of_decision_d_unchanged(self):
        st = self._check(MPL_THIRD, "MPL-2.0")
        self.assertEqual(st["no-promo-urls"][0], "OK")
        st = self._check(MPL_THIRD, "MPL-2.0", body=helpers.MINIMAL_BODY + "// more: https://shop.example.invalid\n")
        self.assertEqual(st["no-promo-urls"][0], "BLOCKING")
        st = self._check(MPL_THIRD, "MPL-2.0", body=helpers.MINIMAL_BODY + 'tip = "https://mozilla.org/MPL/2.0/"\n')
        self.assertEqual(st["no-promo-urls"][0], "BLOCKING")

    def test_end_to_end_and_the_stop_hook_protects_the_notice(self):
        lic = {"id": "MPL-2.0", "grant": "license", "origin": "imported", "status": "confirmed",
               "source_visibility": "public", "access": "free"}
        pdir = helpers.make_product_v3(self.root, slug="imported", profile="FREE", license_overrides=lic,
                                       header=MPL_THIRD + VERSION_LINES)
        findings = guard.guard_product(pdir, self.identity)
        self.assertNotIn("BLOCKING", [f["status"] for f in findings], findings)
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])   # French wording read below
        session.hook_session_start(self.root, {"session_id": "c19", "source": "startup"})
        source = pdir / "My Indicator.pine"
        source.write_text(source.read_text(encoding="utf-8").replace(MPL_THIRD.splitlines()[0] + "\n", ""),
                          encoding="utf-8")
        code, out = session.hook_stop(self.root, {"session_id": "c19"})
        decision = json.loads(out)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("[header-structure] MPL-2.0 notice", decision["reason"])
        self.assertIn("Ne jamais retirer ni modifier une notice de licence", decision["reason"])
        # a broken imported record: the copyright finding says the holder may not be required
        bad = dict(lic, id="GPL-3.0")
        pdir = helpers.make_product_v3(self.root, slug="broken-imported", profile="FREE", license_overrides=bad,
                                       header=GPL3_ONLY + VERSION_LINES)
        st = {f["check"]: (f["status"], f["detail"]) for f in guard.guard_product(pdir, self.identity)}
        self.assertEqual((st["manifest"][0], st["header-structure"][0]), ("BLOCKING", "UNVERIFIABLE"))
        self.assertIn("deprecated and ambiguous", st["manifest"][1])
        self.assertIn("never requires the configured holder", st["header-copyright"][1])

    # ---- independent counter-verification of 2026-11-13 (C-19: M2, m1, m2, m4) ----------

    def test_m2_several_versions_are_never_one_identifier(self):
        """A GNU notice stating several versions, or a choice between versions,
        is to analyse — never one -only or -or-later proposal; the guard warns
        for every recorded version: never silent, never a block as if the
        notice excluded it."""
        choices = (
            "// under the terms of the GNU General Public License as published by the Free Software Foundation;\n"
            "// either version 2 or version 3 of the License.\n",
            "// GNU General Public License version 2 or 3 as published by the Free Software Foundation.\n",
            "// under the terms of the GNU General Public License as published by the Free Software Foundation;\n"
            "// either version 2 of the License, or (at your option) version 3.\n",
            "// Licensed under the GNU GPL v2 or v3, at your option.\n",
            "// Licensed under GPLv2/GPLv3.\n",
            "// GNU General Public License, versions 2 and 3.\n",
            "// SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only\n",
        )
        for header in choices + ("// SPDX-License-Identifier: GPL-3.0-or-later\n" + choices[3],):
            prop = guard.header_licence_proposal(header)
            self.assertEqual((prop["state"], prop["proposal"]), ("to-analyse", None), header)
            self.assertTrue(prop["reasons"], header)
        for header in choices:
            for lid in ("GPL-2.0-only", "GPL-3.0-only", "GPL-2.0-or-later", "GPL-3.0-or-later"):
                st = self._check("// © 2021 Zeta Example\n" + header, lid)
                self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"),
                                 (header, lid))
                self.assertIn("does not establish %s exactly" % lid, st["header-consistency"][1])

    def test_m2_only_the_two_wordings_give_an_identifier(self):
        """Specification §45.4: "either version N of the License, or (at your
        option) any later version" → -or-later, "version N" alone → -only, any
        other wording → to analyse; a notice that agrees with other identifiers
        never lets an exact SPDX line win over it."""
        cases = (
            (GPL3_OR_LATER, "recognized", "GPL-3.0-or-later"),
            (GPL3_ONLY, "recognized", "GPL-3.0-only"),
            ("// GNU General Public License, version 2.\n", "recognized", "GPL-2.0-only"),
            ("// GNU General Public License version 3 or any later version.\n", "to-analyse", None),
            ("// GNU GPL, version 3 of the License, or (at your option) any later version.\n", "to-analyse", None),
            ("// GNU General Public License, either version 3 of the License.\n", "to-analyse", None),
            ("// GNU General Public License version 3, at your option.\n", "to-analyse", None),
            ("// SPDX-License-Identifier: GPL-2.0-only\n// Licensed under GPLv3 or later.\n", "to-analyse", None),
            ("// SPDX-License-Identifier: GPL-3.0-only\n// GNU GPL version 3 or any later version.\n",
             "to-analyse", None),
            ("// SPDX-License-Identifier: GPL-3.0-or-later\n// GNU GPL version 3 or any later version.\n",
             "recognized", "GPL-3.0-or-later"),
        )
        for header, state, proposal in cases:
            prop = guard.header_licence_proposal(header)
            self.assertEqual((prop["state"], prop["proposal"]), (state, proposal), header)

    def test_m1_agpl_plus_is_a_deprecated_identifier_of_the_agpl_family(self):
        self.assertEqual(profiles.deprecated_license("agpl-3.0+"), "AGPL-3.0+")
        prop = guard.header_licence_proposal("// SPDX-License-Identifier: AGPL-3.0+\n")
        self.assertEqual((prop["state"], prop["licences"][0]["family"]), ("to-analyse", "AGPL"))
        self.assertIn("deprecated SPDX identifier AGPL-3.0+ (\"+\" form)", prop["reasons"][0])
        for header, lid in (("// SPDX-License-Identifier: AGPL-3.0+\n// (c) 2022 Zeta Example\n", "AGPL-3.0-or-later"),
                            ("// SPDX-License-Identifier: GPL-3.0+\n// (c) 2022 Zeta Example\n", "GPL-3.0-or-later")):
            st = self._check(header, lid)
            self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"), lid)
        # an identifier outside the closed list keeps its family: another licence, never a missing notice
        for header, lid, subject in (("// SPDX-License-Identifier: GPL-1.0+\n", "GPL-3.0-or-later",
                                      "GPL-3.0-or-later != GPL-1.0+"),
                                     ("// SPDX-License-Identifier: X11\n", "MIT", "MIT != X11")):
            st = self._check(header + "// (c) 2022 Zeta Example\n", lid)
            self.assertEqual((st["header-structure"][0], st["header-structure"][2]), ("BLOCKING", [subject]))
        # each licence of an SPDX expression keeps its family: present, never a missing notice
        st = self._check("// SPDX-License-Identifier: MIT OR Apache-2.0\n// (c) 2022 Zeta Example\n", "MIT")
        self.assertEqual((st["header-structure"][0], st["header-consistency"][0]), ("OK", "WARNING"))

    def test_m2_deprecated_identifier_in_the_text_is_read_as_on_an_spdx_line(self):
        for token in ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "GPL-3.0+", "AGPL-3.0+"):
            for header in ("// Licensed under %s\n// © 2021 Zeta Example\n" % token, "// License: %s\n" % token,
                           "// SPDX-License-Identifier: %s\n" % token):
                prop = guard.header_licence_proposal(header)
                self.assertEqual((prop["state"], prop["proposal"]), ("to-analyse", None), header)
                self.assertIn("deprecated SPDX identifier %s" % token, prop["reasons"][0], header)
        # the same verdict of the guard for the text and the SPDX line, "-only" and "-or-later" alike
        for lid in ("GPL-3.0-only", "GPL-3.0-or-later"):
            verdicts = set()
            for header in ("// Licensed under GPL-3.0\n// © 2021 Zeta\n", "// SPDX-License-Identifier: GPL-3.0\n// © 2021 Zeta\n"):
                st = self._check(header, lid)
                verdicts.add((st["header-structure"][0], st.get("header-consistency", ("none",))[0]))
            self.assertEqual(verdicts, {("OK", "WARNING")}, lid)
        # unchanged: an exact identifier in the text, "GPLv3" and an explicit "version N" give -only
        for header in ("// License: GPL-3.0-only\n", "// License: GPLv3\n",
                       "// Licensed under GPL-3.0 (GNU General Public License, version 3)\n"):
            prop = guard.header_licence_proposal(header)
            self.assertEqual((prop["state"], prop["proposal"]), ("recognized", "GPL-3.0-only"), header)

    def test_m4_notice_right_after_the_version_directive_is_found(self):
        def run(text, lic):
            self.n += 1
            p = self.root / ("After %d.pine" % self.n)
            p.write_text(text, encoding="utf-8")
            return statuses(guard.check_source(p, profiles.header_policy("FREE", lic, self.identity), None,
                                               self.identity))
        imported = {"id": "MPL-2.0", "grant": "license", "origin": "imported", "status": "confirmed",
                    "source_visibility": "public", "access": "free"}
        st = run(VERSION_LINES + MPL_THIRD + "\n// Example helper\n" + helpers.MINIMAL_BODY, imported)
        self.assertEqual((st["header-version"], st["header-structure"], st["header-copyright"]), ("OK", "OK", "OK"))
        self.assertNotIn("header-consistency", st)
        cc_third = ("// This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International "
                    "(CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n// © ZetaAlgoExample\n")
        st = run(VERSION_LINES + cc_third + helpers.MINIMAL_BODY, dict(imported, id="CC-BY-NC-SA-4.0", grant="cc"))
        self.assertEqual((st["header-structure"], st["header-copyright"]), ("OK", "OK"))
        self.assertNotIn("cc-url-placement", st)                 # the licence header of an imported notice
        # after the first line of code, a comment is never the notice of the script
        st = run(VERSION_LINES + helpers.MINIMAL_BODY + MPL_THIRD, imported)
        self.assertEqual(st["header-structure"], "BLOCKING")
        # a profile licence keeps its header model: its CC header after the directive is still missing
        st = run(VERSION_LINES + cc_third.replace("ZetaAlgoExample", "2026 Holder Test") + helpers.MINIMAL_BODY,
                 profiles.default_license("FREE"))
        self.assertEqual((st["header-structure"], st["header-copyright"], st["cc-url-placement"]),
                         ("BLOCKING", "BLOCKING", "WARNING"))


if __name__ == "__main__":
    unittest.main()
