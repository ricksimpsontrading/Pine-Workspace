# SPDX-License-Identifier: Apache-2.0
"""Deterministic menu: action → script order, applicability, pagination,
localization, single-script identity (2026-11-06)."""
import tempfile
import unittest

from tools.pws_workspace import i18n, menu, session
from tools.tests import helpers


def find(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n
        for screen in n.get("children") or []:
            r = find(screen, node_id)
            if r:
                return r
    return None


class TestMenu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_workspace_hides_work_and_quality(self):
        m = menu.build_menu(session.session_status(self.root))
        ids = [t["id"] for t in m["top"]]
        self.assertEqual(ids, ["new", "maintenance"])
        self.assertIn({"id": "work", "reason": i18n.t("menu.na.no_registered", "en")}, m["inapplicable"])
        self.assertEqual(m["language"], "en")

    def test_single_registered_script_direct_but_explicit(self):
        helpers.configure(self.root, language="fr")
        helpers.make_product_v2(self.root, slug="solo", profile="COMMERCIAL")
        m = menu.build_menu(session.session_status(self.root))
        self.assertEqual(m["language"], "fr")
        self.assertEqual(m["single_script"]["slug"], "solo")
        self.assertIn("solo (Indicateur, COMMERCIAL)", m["single_script_label"])
        work = find(m["top"], "work")
        self.assertIsNotNone(work)
        # action first (develop is the first option), script selection afterwards
        first_screen = work["children"][0]
        self.assertEqual(first_screen[0]["id"], "work.develop")
        self.assertTrue(first_screen[0]["needs_script"])
        self.assertEqual(find(m["top"], "work.docs")["route"], "pine-docs")
        self.assertEqual(find(m["top"], "work.audit")["route"], "pine-audit")

    def test_every_screen_has_at_most_four_options(self):
        helpers.make_product_v2(self.root, slug="a")

        def walk(nodes):
            for n in nodes:
                for screen in n.get("children") or []:
                    self.assertLessEqual(len(screen), menu.MAX_OPTIONS)
                    walk(screen)
        m = menu.build_menu(session.session_status(self.root))
        self.assertLessEqual(len(m["top"]), menu.MAX_OPTIONS)
        walk(m["top"])

    def test_pagination_adds_more_and_back(self):
        opts = [{"id": "o%d" % i, "label": "o%d" % i} for i in range(5)]
        screens = menu.paginate(opts, "en")
        self.assertEqual(len(screens), 2)
        self.assertEqual([o["id"] for o in screens[0]], ["o0", "o1", "more", "back"])
        self.assertEqual([o["id"] for o in screens[1]], ["o2", "o3", "o4", "back"])

    def test_not_ready_products_routed_to_onboarding_not_selected(self):
        helpers.make_product(self.root, slug="broken-one", with_context=False)
        m = menu.build_menu(session.session_status(self.root))
        self.assertEqual(m["scripts"], [])
        self.assertEqual(m["not_ready"][0]["slug"], "broken-one")
        self.assertEqual(m["not_ready"][0]["route"], "pine-onboard")
        self.assertNotIn("work", [t["id"] for t in m["top"]])

    def test_profiles_offered_with_library_rule(self):
        m = menu.build_menu(session.session_status(self.root))
        self.assertEqual([p["value"] for p in m["profiles"]],
                         ["FREE", "FREE_CLOSED", "PRIVATE", "COMMERCIAL"])
        self.assertEqual(m["free_closed_defaults"]["license"]["grant"], "free-use")
        self.assertEqual(m["free_closed_defaults"]["publication"]["mode"], "protected")
        self.assertEqual(m["profile_defaults"]["PRIVATE"]["publication"]["privacy"], None)
        self.assertIn("TradingView", m["library_rule"])

    def test_config_submenu_requires_explicit_tv_choice(self):
        m = menu.build_menu(session.session_status(self.root))
        tv = find(m["top"], "config.tvmode")
        self.assertTrue(tv["explicit_choice_required"])
        self.assertEqual(tv["current"], "manual")

    # ---- walkthrough corrections (2026-11-06) --------------------------------

    def _screens(self, nodes):
        for n in nodes:
            for screen in n.get("children") or []:
                yield n["id"], screen
                for sub in self._screens(screen):
                    yield sub

    def test_back_on_every_screen_below_the_first_level(self):
        helpers.configure(self.root, language="fr")
        helpers.make_product_v2(self.root, slug="a", profile="COMMERCIAL")
        m = menu.build_menu(session.session_status(self.root))
        screens = list(self._screens(m["top"]))
        self.assertGreaterEqual(len(screens), 10)
        for parent, screen in screens:
            ids = [o["id"] for o in screen]
            self.assertLessEqual(len(screen), menu.MAX_OPTIONS, (parent, ids))
            self.assertEqual(ids[-1], "back", (parent, ids))          # Back directly on every page
            self.assertEqual(ids.count("back"), 1, (parent, ids))
            if "more" in ids:                                          # a continued page keeps Back too
                self.assertEqual(ids[-2], "more", (parent, ids))
        self.assertNotIn("back", [t["id"] for t in m["top"]])        # the main menu needs none

    def test_every_option_has_a_short_plain_description(self):
        from tools.pws_workspace import config
        banned = ("pine-", "python3", "--", "sha256", "SHA", "fingerprint", "§")
        helpers.configure(self.root, language="fr")
        helpers.make_product_v2(self.root, slug="a", profile="COMMERCIAL")
        for lang in ("fr", "en"):
            self.assertTrue(config.set_value(self.root, "language", lang)["ok"])
            m = menu.build_menu(session.session_status(self.root))

            def check(node):
                if node["kind"] in ("action", "submenu", "setting"):
                    text = node["label"] + " " + (node.get("description") or "")
                    self.assertTrue(node.get("description"), node["id"])
                    self.assertLessEqual(len(node["description"]), 170, node["id"])
                    for word in banned:
                        self.assertNotIn(word, text, (lang, node["id"], text))
                for screen in node.get("children") or []:
                    for child in screen:
                        check(child)
            for top in m["top"]:
                check(top)
            self.assertEqual(find(m["top"], "new.import")["label"],
                             "Importer un script" if lang == "fr" else "Import a script")
            self.assertEqual(find(m["top"], "work.audit")["label"],
                             "Audit approfondi" if lang == "fr" else "Deep audit")

    def test_configuration_offers_every_setting_with_current_values(self):
        from tools.pws_workspace import config
        helpers.configure(self.root, language="fr", holder="Holder Test", aliases=("HolderAlias",))
        self.assertTrue(config.set_value(self.root, "identity.default_profile", "COMMERCIAL")["ok"])
        m = menu.build_menu(session.session_status(self.root))
        cfg = find(m["top"], "maintenance.config")
        self.assertEqual(cfg["kind"], "submenu")
        settings = [o["id"] for screen in cfg["children"] for o in screen if o["kind"] == "setting"]
        self.assertEqual(settings, ["config.language", "config.identity", "config.profile",
                                    "config.tvmode", "config.github", "config.cleanup"])
        self.assertEqual(len(cfg["children"]), 3)                     # six settings, Back on each page
        for screen in cfg["children"]:
            self.assertEqual(screen[-1]["id"], "back")
        lang_node = find(m["top"], "config.language")
        self.assertEqual((lang_node["current"], lang_node["current_label"]), ("fr", "Français"))
        self.assertEqual([c["label"] for c in lang_node["choices"]], ["English", "Français"])
        self.assertEqual([c["value"] for c in lang_node["choices"] if c["selected"]], ["fr"])
        self.assertEqual(lang_node["keep_label"], "Conserver « Français » (Retour)")
        ident = find(m["top"], "config.identity")
        self.assertEqual((ident["current"], ident["aliases"], ident["free_text"]),
                         ("Holder Test", ["HolderAlias"], True))
        self.assertIn("HolderAlias", ident["current_label"])
        prof = find(m["top"], "config.profile")
        self.assertEqual(prof["current"], "COMMERCIAL")
        self.assertEqual([c["value"] for c in prof["choices"]], ["FREE", "PRIVATE", "COMMERCIAL"])
        tv = find(m["top"], "config.tvmode")
        self.assertEqual((tv["current"], tv["explicit_choice_required"]), ("manual", True))
        self.assertEqual([c["value"] for c in tv["choices"]], ["manual", "chrome-experimental"])
        gh = find(m["top"], "config.github")
        self.assertEqual((gh["current"], gh["destinations"], gh["current_label"]), ([], [], "aucune"))
        cl = find(m["top"], "config.cleanup")
        self.assertEqual((cl["current"], cl["current_label"]), (True, "Activé"))
        self.assertEqual([c["value"] for c in cl["choices"]], [True, False])
        # English edition: language names stay names, never bare codes
        m_en = menu.build_menu(dict(session.session_status(self.root), language="en"))
        en_lang = find(m_en["top"], "config.language")
        self.assertEqual(en_lang["current_label"], "English")
        self.assertEqual(en_lang["keep_label"], "Keep “English” (Back)")
        self.assertEqual(find(m_en["top"], "config.cleanup")["current_label"], "Enabled")

    def test_script_choice_with_one_and_several_products(self):
        helpers.configure(self.root, language="fr")
        helpers.make_product_v2(self.root, slug="solo")
        m = menu.build_menu(session.session_status(self.root))
        self.assertEqual(m["single_script"]["slug"], "solo")
        self.assertEqual(m["continue_label"], "Continuer avec ce script")
        self.assertEqual([[o["id"] for o in s] for s in m["script_screens"]], [["script.solo", "back"]])
        for slug in ("b-two", "c-three", "d-four", "e-five"):
            helpers.make_product_v2(self.root, slug=slug)
        m = menu.build_menu(session.session_status(self.root))
        self.assertIsNone(m["single_script"])
        self.assertEqual(len(m["scripts"]), 5)
        screens = m["script_screens"]
        self.assertEqual(len(screens), 2)
        self.assertEqual([o["id"] for o in screens[0]][-2:], ["more", "back"])
        self.assertEqual(screens[0][-2]["label"], "Autres…")
        self.assertEqual(screens[1][-1]["id"], "back")
        self.assertEqual(sum(1 for s in screens for o in s if o["kind"] == "script"), 5)
        self.assertEqual({o["slug"] for s in screens for o in s if o["kind"] == "script"},
                         {"solo", "b-two", "c-three", "d-four", "e-five"})
        # the action is still chosen first; the script comes afterwards
        work = find(m["top"], "work")
        self.assertEqual(work["children"][0][0]["id"], "work.develop")
        self.assertTrue(find(m["top"], "work.develop")["needs_script"])
        self.assertTrue(find(m["top"], "quality.release")["needs_script"])


    def test_every_submenu_and_question_screen_has_a_short_header(self):
        """Audit B-06 (2026-11-13): headers never exceed the dialog limit."""
        from tools.pws_workspace import config
        helpers.configure(self.root, language="en")
        helpers.make_product_v2(self.root, slug="solo", profile="COMMERCIAL")
        for lang in ("en", "fr"):
            self.assertTrue(config.set_value(self.root, "language", lang)["ok"])
            m = menu.build_menu(session.session_status(self.root))
            subs = []

            def walk(nodes):
                for n in nodes:
                    if n.get("kind") == "submenu":
                        subs.append(n)
                    for screen in n.get("children") or []:
                        walk(screen)
            walk(m["top"])
            self.assertTrue(subs)
            for n in subs:
                self.assertTrue(n.get("header"), n["id"])
                self.assertLessEqual(len(n["header"]), menu.HEADER_MAX, (lang, n["id"], n["header"]))
            self.assertEqual(set(m["headers"]), set(menu.SCREEN_HEADERS))
            for key, value in m["headers"].items():
                self.assertTrue(0 < len(value) <= menu.HEADER_MAX, (lang, key, value))


if __name__ == "__main__":
    unittest.main()
