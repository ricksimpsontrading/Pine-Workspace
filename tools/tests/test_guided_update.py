# SPDX-License-Identifier: Apache-2.0
"""Guided update of Pine Workspace (2.2.0): the continuous path `update guide`
(state, search, prepare = fetch + plan, apply) over the existing chain, with
localized summaries in French and English. Isolated installations and
SIMULATED release answers only (never a real query): absence of update,
available version, failed search, pre-release, absent or unusable notes,
cancellation, altered package, local state changed after the plan, backup
impossible, success with data kept, customized permission file kept,
blocked migration, blocking or unusable diagnostic, failure after a partial
change, development upstream refusal."""
import json
import os
import shutil
import unittest
from pathlib import Path

from tools.pws_workspace import config, core, i18n, update, update_guide, upgrade
from tools.tests.test_update import (V1, V2, InstalledFixture, api_release, doctor_seam, local_downloader,
                                     network_error, seam, simulated, tree)


class TestNotesReading(unittest.TestCase):
    def test_notes_are_available_absent_or_unusable_and_never_invented(self):
        self.assertEqual(update_guide.notes_state("## Changed\n- the update path is guided")[0], "available")
        self.assertEqual(update_guide.notes_state("")[0], "absent")
        self.assertEqual(update_guide.notes_state(None)[0], "absent")
        self.assertEqual(update_guide.notes_state("   \n")[0], "absent")
        self.assertEqual(update_guide.notes_state("ok")[0], "unusable")
        self.assertEqual(update_guide.notes_state("bad \x00 binary \x01 content here")[0], "unusable")
        self.assertEqual(update_guide.notes_state(["not", "text"])[0], "unusable")
        self.assertTrue(update_guide.notes_state("word " * 5000)[2])          # truncated at the search cap
        for lang in ("fr", "en"):
            state, lines = update_guide.notes_lines(lang, "")
            self.assertEqual(state, "absent")
            self.assertEqual(lines, [i18n.t("guide.notes.absent", lang)])

    def test_every_guide_text_exists_in_both_languages(self):
        from tools.pws_workspace.guide_text import CATALOGUE
        for key, entry in CATALOGUE.items():
            self.assertEqual(sorted(entry), ["en", "fr"], key)
            self.assertTrue(entry["en"].strip() and entry["fr"].strip(), key)
            self.assertEqual(sorted(set(_fields(entry["en"]))), sorted(set(_fields(entry["fr"]))), key)


def _fields(text):
    import string
    return [f for _, f, _, _ in string.Formatter().parse(text) if f]


class TestGuidedSearch(InstalledFixture):
    def test_state_then_search_in_both_languages_and_honest_unknowns(self):
        for lang in ("fr", "en"):
            st = update_guide.state(self.install, lang=lang)
            self.assertIn(i18n.t("pwsg.search.none", lang), st["summary"]["state"])
            self.assertIn(i18n.t("pwsg.kind.distribution", lang, v=V1), st["summary"]["headline"])
        before = tree(self.install)
        # failed search: never "up to date", nothing downloaded or changed
        s = update_guide.search(self.install, lang="fr", fetch=network_error)
        self.assertEqual(s["result"]["result"], "error")
        self.assertIn("on ignore toujours", s["summary"]["text"])
        self.assertIn(i18n.t("pwsg.next.retry", "fr"), s["summary"]["next"])
        self.assertNotIn("à jour", s["summary"]["result"][0].replace("ignore toujours si une version plus récente", ""))
        # no stable release (only a pre-release): unknown, pre-release skipped
        s = update_guide.search(self.install, lang="en", fetch=simulated([api_release("v" + V2 + "-rc.1", self.assets,
                                                                                       prerelease=True)]))
        self.assertEqual(s["result"]["result"], "no-release")
        self.assertIn(i18n.t("pwsg.search.prereleases_skipped", "en", n=1), s["summary"]["result"])
        # ... proposed only on request, and then said to be a pre-release
        s = update_guide.search(self.install, lang="fr", include_prereleases=True,
                                fetch=simulated([api_release("v" + V2 + "-rc.1", self.assets, prerelease=True,
                                                             body="Release candidate with the guided path")]))
        self.assertEqual(s["result"]["result"], "update-available")
        self.assertIn(i18n.t("pwsg.search.prerelease_chosen", "fr"), s["summary"]["result"])
        # up to date
        s = update_guide.search(self.install, lang="fr", fetch=simulated([api_release("v" + V1, self.assets)]))
        self.assertEqual(s["result"]["result"], "up-to-date")
        self.assertEqual(s["summary"]["next"] if "next" in s["summary"] else [], [])
        # available, with notes / without notes / unusable notes
        s = update_guide.search(self.install, lang="fr", fetch=simulated([api_release(
            "v" + V2, self.assets, body="## Changed\n- guided update of PineTS and Pine Workspace")]))
        self.assertEqual((s["result"]["result"], s["notes_state"]), ("update-available", "available"))
        self.assertIn("guided update of PineTS", s["notes_text"])
        self.assertIn(i18n.t("pwsg.next.prepare", "fr", latest=V2), s["summary"]["next"])
        self.assertIn(i18n.t("guide.simulated", "fr"), s["summary"]["result"])
        s = update_guide.search(self.install, lang="en", fetch=simulated([api_release("v" + V2, self.assets, body="")]))
        self.assertEqual(s["notes_state"], "absent")
        self.assertIsNone(s["notes_text"])
        self.assertIn(i18n.t("guide.notes.absent", "en"), s["summary"]["notes"])
        s = update_guide.search(self.install, lang="fr", fetch=simulated([api_release("v" + V2, self.assets,
                                                                                       body="\x00\x01\x02")]))
        self.assertEqual(s["notes_state"], "unusable")
        self.assertEqual(tree(self.install), before)                       # only the dated search record


class TestGuidedApply(InstalledFixture):
    def search_available(self):
        s = update_guide.search(self.install, lang="fr", fetch=simulated([api_release("v" + V2, self.assets,
                                                                                       body="Fixture notes of the release")]))
        self.assertEqual(s["result"]["result"], "update-available")

    def prepared(self, lang="fr", dest=None):
        self.search_available()
        p = update_guide.prepare(self.install, lang=lang, downloader=local_downloader(self.assets),
                                 dest=dest or self.dl)
        self.assertTrue(p["applicable"], json.dumps(p.get("plan") or p.get("fetch"), indent=1)[:2000])
        return p

    def test_plan_summary_is_the_confirmation_request_and_cancelling_changes_nothing(self):
        before = tree(self.install)
        p = self.prepared("fr")
        sm = p["summary"]
        self.assertEqual(sm["confirm"]["question"], "Appliquer ce plan ?")
        self.assertEqual([o["value"] for o in sm["confirm"]["options"]], ["apply", "cancel"])
        self.assertIn(i18n.t("pwsg.plan.kept.user", "fr"), sm["kept"])
        self.assertIn(i18n.t("pwsg.limit.atomic", "fr"), sm["limits"])
        self.assertIn(i18n.t("guide.permissions", "fr"), sm["limits"])
        self.assertTrue(any("Release officielle" in line for line in sm["change"]))
        self.assertTrue(any("m004-record-workspace-version" in line for line in sm["change"]))
        self.assertIn(i18n.t("guide.notes.available", "fr"), sm["notes"])
        # cancelling = not calling apply: the installation is unchanged (only the plan record exists)
        self.assertEqual(tree(self.install), before)
        self.assertTrue(core.is_within(self.install / ".claude" / "runtime", Path(p["plan_file"])))
        en = update_guide.plan_summary("en", p["plan"], p["fetch"])
        self.assertEqual(en["confirm"]["question"], "Apply this plan?")

    def test_successful_guided_update_keeps_data_and_a_customized_permission_file(self):
        settings = self.install / ".claude" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        data["permissions"]["ask"].append("Bash(echo local-customization)")
        settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        local_sha = core.sha256_file(settings)
        p = self.prepared("fr")
        self.assertIn(i18n.t("pwsg.plan.kept.local", "fr", path=".claude/settings.json"), p["summary"]["kept"])
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr")
        self.assertEqual((r["status"], r["ok"]), ("applied", True), json.dumps(r["result"], indent=1)[:2500])
        self.assertEqual(core.sha256_file(settings), local_sha)                     # kept as is
        self.assertTrue((self.install / ".claude" / "settings.json.pws-new").is_file())
        self.assertEqual(config.read_config(self.install)["data"]["workspace_version"], V2)
        self.assertTrue((self.install / "scripts" / "user-prod").is_dir())
        self.assertEqual((self.install / "docs" / "maintenance" / "note.md").read_text(encoding="utf-8"), "preuve\n")
        sm = r["summary"]
        self.assertIn("appliquée et vérifiée", sm["headline"])
        self.assertIn(i18n.t("pwsg.done.kept", "fr", path=".claude/settings.json"), sm["changed"])
        self.assertIn(i18n.t("pwsg.next.restart", "fr"), sm["next"])
        self.assertTrue(any("upgrade --rollback" in line for line in sm["recovery"]))

    def test_altered_package_or_changed_installation_refuses_before_any_change(self):
        p = self.prepared()
        before = tree(self.install)
        target = Path(p["fetch"]["package_dir"]) / "docs" / "architecture" / "NEW_DOC.md"
        target.write_text("# altered after the plan\n", encoding="utf-8")
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr")
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("rien n'a été modifié", r["summary"]["headline"])
        self.assertEqual(tree(self.install), before)
        target.write_text("# New\n", encoding="utf-8")                             # package restored
        (self.install / "docs" / "architecture" / "OPERATIONS.md").write_text("local edit\n", encoding="utf-8")
        before = tree(self.install)
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="en")
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("plan changed", r["result"]["error"])
        self.assertEqual(tree(self.install), before)
        r = update_guide.apply(self.install, p["plan_file"], yes=False, lang="en")   # no confirmation
        self.assertEqual(r["status"], "refused-before-mutation")

    def test_provenance_of_the_prepared_package_is_bound_to_the_plan(self):
        p = self.prepared()
        prepared_file = Path(p["fetch"]["download_dir"]) / update.PREPARED
        info = json.loads(prepared_file.read_text(encoding="utf-8"))
        info["provenance"] = "something else"
        prepared_file.write_text(json.dumps(info), encoding="utf-8")
        before = tree(self.install)
        r = update_guide.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertEqual(tree(self.install), before)

    def test_backup_impossible_refuses_before_any_change(self):
        p = self.prepared()
        before = tree(self.install)
        blocker = self.install / upgrade.BACKUP_REL
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_text("not a folder\n", encoding="utf-8")           # the backup folder cannot be created
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr")
        self.assertEqual(r["status"], "refused-before-mutation", json.dumps(r["result"], indent=1)[:1500])
        self.assertIn("backup", r["result"]["error"])
        self.assertEqual(tree(self.install), before)

    def test_blocked_migration_is_reported_with_the_code_installed(self):
        (self.install / ".claude" / "settings.local.json").write_text(
            json.dumps({"env": {core.TV_MODE_ENV_KEY: "weird"}}), encoding="utf-8")
        p = self.prepared()
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr")
        self.assertEqual(r["status"], "stopped-blocked-migrations")
        sm = r["summary"]
        self.assertIn("BLOQUÉE", sm["headline"])
        self.assertIn(i18n.t("pwsg.done.code", "fr", installed="oui", verified="oui"), sm["changed"])
        self.assertTrue(any("m001-tv-mode-to-config" in line for line in sm["changed"]))
        self.assertNotIn("rien n'a été modifié", sm["text"])

    def test_blocking_or_unusable_diagnostic_is_never_a_success(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        os.symlink(str(outside), str(self.install / "scripts" / "escape"))
        p = self.prepared()
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="en")
        self.assertEqual(r["status"], "diagnostic-blocking")
        self.assertIn("BLOCKING", r["summary"]["headline"])
        self.assertTrue(any("no-outgoing-symlinks" in line for line in r["summary"]["changed"]))

    def test_unusable_diagnostic_is_reported_as_such(self):
        p = self.prepared()
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr",
                               runner=doctor_seam((1, "", "simulated failure of the doctor process")))
        self.assertEqual(r["status"], "diagnostic-unavailable")
        self.assertIn(i18n.t("pwsg.done.diagnostic", "fr", verdict=i18n.t("pwsg.diag.unavailable", "fr")),
                      r["summary"]["changed"])

    def test_failure_after_a_partial_change_states_what_really_changed(self):
        p = self.prepared()
        before = tree(self.install)

        def failing_copy(src, dst):
            if Path(dst).name == "NEW_DOC.md":
                raise OSError("simulated disk failure")
            shutil.copy2(str(src), str(dst))
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr", copy=failing_copy)
        self.assertEqual(r["status"], "failed-restored")
        self.assertIn("restauré et vérifié", r["summary"]["headline"])
        self.assertEqual(tree(self.install), before)
        self.assertTrue(any("upgrade --rollback" in line for line in r["summary"]["recovery"]))
        # failure AFTER the code installation: unusable migration answer → incomplete, code installed
        p = self.prepared(dest=self.dl.parent / "download 2")
        r = update_guide.apply(self.install, p["plan_file"], yes=True, lang="fr",
                               runner=seam(**{"migrate_--apply": (0, "garbage", "")}))
        self.assertEqual(r["status"], "incomplete", json.dumps(r["result"], indent=1)[:2000])
        sm = r["summary"]
        self.assertIn(i18n.t("pwsg.done.code", "fr", installed="oui", verified="oui"), sm["changed"])
        self.assertIn(i18n.t("pwsg.next.restart", "fr"), sm["next"])
        self.assertNotIn("rien n'a été modifié", sm["text"])

    def test_report_of_an_unrestored_failure_never_claims_nothing_changed(self):
        report = {"status": "failed-restore-perform", "ok": False, "error": "disk full",
                  "plan": {"current_version": V1, "target_version": V2},
                  "done": {"code_installed": None, "code_verified": False, "migrations_applied": [],
                           "migrations_remaining": [], "migrations_blocked": [], "diagnostic": "not-run",
                           "kept_local": []},
                  "recovery": {"upgrade_backup": "/x/.claude/runtime/upgrade-backup/20261117T000000Z-abc"},
                  "next_action": "fix, then `upgrade --rollback 20261117T000000Z-abc`", "restart_required": False}
        for lang in ("fr", "en"):
            sm = update_guide.report_summary(lang, report)
            self.assertIn(i18n.t("pwsg.status.failed-restore", lang), sm["headline"])
            self.assertIn(i18n.t("pwsg.done.code", lang, installed=i18n.t("guide.unknown", lang),
                                 verified=i18n.t("guide.no", lang)), sm["changed"])
            self.assertTrue(any("20261117T000000Z-abc" in line for line in sm["recovery"]))
            self.assertNotIn(i18n.t("pwsg.status.refused-before-mutation", lang), sm["text"])


class TestDevelopmentUpstream(unittest.TestCase):
    def test_the_upstream_gets_an_understandable_refusal_before_any_download(self):
        from tools.tests import helpers
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            helpers.configure(root, language="fr")

            def no_download(url, dest):
                raise AssertionError("nothing may be downloaded on the development upstream")
            r = update_guide.prepare(root, downloader=no_download)
            self.assertEqual((r["applicable"], r.get("refused")), (False, "development-upstream"))
            self.assertIn(i18n.t("pwsg.dev.explain", "fr"), r["summary"]["limits"])
            st = update_guide.state(root, lang="en")
            self.assertIn(i18n.t("pwsg.dev.explain", "en"), st["summary"]["limits"])


if __name__ == "__main__":
    unittest.main()
