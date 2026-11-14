# SPDX-License-Identifier: Apache-2.0
"""Session snapshot lifecycle, SessionStart summary, Stop hook behavior
(spec sections 40-41, 61.5)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import config, core, i18n, session
from tools.tests import helpers


class TestSessionStart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _snap(self, session_id):
        return self.root / session.SESSION_DIR_REL / ("%s.json" % session_id)

    def test_baseline_created_once_never_overwritten(self):
        helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        snap1 = self._snap("s1").read_text(encoding="utf-8")
        # a .pine changes mid-session; a re-trigger must NOT rewrite the baseline
        src = self.root / "scripts" / "my-indicator" / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// edit\n", encoding="utf-8")
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        self.assertEqual(self._snap("s1").read_text(encoding="utf-8"), snap1)

    def test_resume_carries_previous_baseline(self):
        helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        baseline = json.loads(self._snap("s1").read_text(encoding="utf-8"))["files"]
        src = self.root / "scripts" / "my-indicator" / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// edit\n", encoding="utf-8")
        session.hook_session_start(self.root, {"session_id": "s2", "source": "resume"})
        carried = json.loads(self._snap("s2").read_text(encoding="utf-8"))
        self.assertEqual(carried["files"], baseline)
        self.assertEqual(carried["carried_from"], "s1")

    def test_clear_starts_fresh_baseline(self):
        helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        src = self.root / "scripts" / "my-indicator" / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// edit\n", encoding="utf-8")
        session.hook_session_start(self.root, {"session_id": "s3", "source": "clear"})
        fresh = json.loads(self._snap("s3").read_text(encoding="utf-8"))
        self.assertNotIn("carried_from", fresh)

    def test_symlinked_runtime_never_written_through(self):
        """Targeted review 2026-09-06: a symlinked .claude/runtime must not
        route hook writes outside the workspace — the hook degrades to
        snapshot-less operation and still reports."""
        import os
        outside = Path(self.tmp.name) / "outside runtime"
        outside.mkdir()
        runtime = self.root / core.RUNTIME_REL
        runtime.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(outside, runtime)
        text, status = session.hook_session_start(
            self.root, {"session_id": "sym1", "source": "startup"})
        self.assertIn("PWS", text)
        self.assertEqual(list(outside.iterdir()), [], "nothing written outside")
        code, out = session.hook_stop(self.root, {"session_id": "sym1"})
        self.assertEqual((code, out), (0, ""))

    def test_subagent_does_not_touch_baseline(self):
        text, _ = session.hook_session_start(
            self.root, {"session_id": "sub1", "source": "startup", "agent_type": "reviewer"})
        self.assertFalse(self._snap("sub1").exists())
        self.assertIn("PWS", text)

    def test_summary_contains_orphans_and_budget(self):
        pdir = self.root / "scripts" / "orphan-prod"
        pdir.mkdir()
        (pdir / "Orphan.pine").write_text("//@version=6\n", encoding="utf-8")
        text, status = session.hook_session_start(
            self.root, {"session_id": "s9", "source": "startup"})
        self.assertIn("UNREGISTERED", text)
        self.assertIn("Orphan.pine", text)
        self.assertLessEqual(len(text), session.STDOUT_BUDGET)
        self.assertEqual(status["counts"]["unregistered_pine"], 1)

    def test_summary_states_the_configured_language_explicitly(self):
        """The configured language is transmitted at session start as an
        explicit line (2026-11-14), right after the title, in that language;
        an explicit change is reflected by the next summary. No config file:
        the default (English) is stated."""
        from tools.pws_workspace import config, i18n
        fr_line = i18n.t("summary.language", "fr")
        en_line = i18n.t("summary.language", "en")
        self.assertTrue(fr_line.startswith("Langue configurée : fr"), fr_line)
        self.assertTrue(en_line.startswith("Configured language: en"), en_line)
        text, _ = session.hook_session_start(self.root, {"session_id": "lang0", "source": "startup"})
        self.assertEqual(text.split("\n")[:2], ["PWS", en_line])          # no config: default English
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])
        text, status = session.hook_session_start(self.root, {"session_id": "lang1", "source": "startup"})
        self.assertEqual(status["language"], "fr")
        self.assertEqual(text.split("\n")[:2], ["PWS", fr_line])
        self.assertNotIn(en_line, text)
        self.assertTrue(config.set_value(self.root, "language", "en")["ok"])
        text, status = session.hook_session_start(self.root, {"session_id": "lang1", "source": "compact"})
        self.assertEqual(status["language"], "en")
        self.assertEqual(text.split("\n")[:2], ["PWS", en_line])
        self.assertNotIn(fr_line, text)

    def test_session_status_structure_for_menu(self):
        helpers.make_product(self.root)
        status = session.session_status(self.root)
        for key in ("git", "tv_mode", "standard", "products", "counts",
                    "unregistered_pine", "stale_validations"):
            self.assertIn(key, status)
        self.assertEqual(status["tv_mode"], "manual")
        self.assertEqual(status["counts"]["registered"], 1)


class TestStopHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_stop_hook_active_short_circuit(self):
        code, out = session.hook_stop(self.root, {"session_id": "s1",
                                                  "stop_hook_active": True})
        self.assertEqual((code, out), (0, ""))

    def test_no_baseline_never_blocks(self):
        code, out = session.hook_stop(self.root, {"session_id": "unknown"})
        self.assertEqual((code, out), (0, ""))

    def test_clean_session_no_block(self):
        helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        code, out = session.hook_stop(self.root, {"session_id": "s1"})
        self.assertEqual((code, out), (0, ""))

    def test_blocking_violation_blocks(self):
        pdir = helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") +
                       "// visit https://promo.example.com now\n", encoding="utf-8")
        code, out = session.hook_stop(self.root, {"session_id": "s1"})
        self.assertEqual(code, 0)
        decision = json.loads(out)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("no-promo-urls", decision["reason"])

    def test_unregistered_modified_blocks_with_onboard_action(self):
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        pdir = self.root / "scripts" / "newprod"
        pdir.mkdir()
        (pdir / "New.pine").write_text("//@version=6\n", encoding="utf-8")
        code, out = session.hook_stop(self.root, {"session_id": "s1"})
        decision = json.loads(out)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("pine-onboard", decision["reason"])

    def test_compliant_change_no_block(self):
        pdir = helpers.make_product(self.root)
        session.hook_session_start(self.root, {"session_id": "s1", "source": "startup"})
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "plot(open, title=\"O\")\n",
                       encoding="utf-8")
        code, out = session.hook_stop(self.root, {"session_id": "s1"})
        self.assertEqual((code, out), (0, ""))


class TestStopAttribution(unittest.TestCase):
    """Maintenance 2026-09 (spec section 41.2): attribution finding by
    finding — introduced / pre-existing / made visible by the context /
    indeterminate. Only introduced findings block."""

    NO_VERSION_HEADER = (
        "// This work is licensed under the Attribution-NonCommercial-ShareAlike 4.0 "
        "International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n"
        "// © LegacyHolder\n"
        "//@version=6\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
        # these attribution tests read the French wording of the Stop hook
        # (the language of the messages is tested in TestStopLanguage20261114)
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def _start(self, sid="s1"):
        session.hook_session_start(self.root, {"session_id": sid, "source": "startup"})

    def _stop(self, sid="s1"):
        code, out = session.hook_stop(self.root, {"session_id": sid})
        self.assertEqual(code, 0)
        info_path = session._stop_info_path(self.root, sid)  # one file per session
        info = []
        if info_path.exists():
            info = json.loads(info_path.read_text(encoding="utf-8"))["info"]
        return (json.loads(out) if out else None), info

    def _git(self, *args):
        rc, out, err = core.git(self.root, *args)
        self.assertEqual(rc, 0, err)

    def _init_git(self):
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "test")
        self._git("config", "commit.gpgsign", "false")

    def test_t1_orphan_moved_and_onboarded_unchanged_never_blocks(self):
        """PWS-02: an imported source without a Version line, moved under a
        product root and onboarded WITHOUT modification."""
        orphan = self.root / "scripts" / "Imported v3.pine"
        orphan.write_text(self.NO_VERSION_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        self._start()
        pdir = helpers.make_product(self.root, slug="imported")
        target = pdir / "My Indicator.pine"
        target.unlink()
        orphan.rename(target)
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("header-version" in i and "rendu visible" in i for i in info), info)

    def test_t2_preexisting_anomaly_unrelated_edit_never_blocks(self):
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER)
        self._start()
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "plot(open, title=\"O\")\n",
                       encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("header-version" in i and "préexistant" in i for i in info), info)

    def test_t3_introduced_anomaly_blocks(self):
        pdir = helpers.make_product(self.root)
        self._start()
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8").replace("// Version: 1.0.0\n", ""),
                       encoding="utf-8")
        decision, _ = self._stop()
        self.assertEqual(decision["decision"], "block")
        self.assertIn("header-version", decision["reason"])

    def test_t4_new_noncompliant_file_blocks(self):
        self._start()
        helpers.make_product(self.root, slug="fresh", header=self.NO_VERSION_HEADER)
        decision, _ = self._stop()
        self.assertEqual(decision["decision"], "block")
        self.assertIn("header-version", decision["reason"])
        self.assertIn("nouveau fichier", decision["reason"])

    def test_t5_manifest_change_on_unchanged_content_blocks(self):
        """A known fingerprint exempts from no check: the check was evaluable
        at start and the finding did not exist."""
        pdir = helpers.make_product(self.root)
        self._start()
        manifest = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        manifest["distribution"] = "paid-closed-source"
        (pdir / "SCRIPT.json").write_text(json.dumps(manifest), encoding="utf-8")
        decision, _ = self._stop()
        self.assertEqual(decision["decision"], "block")
        self.assertIn("header-structure", decision["reason"])

    def test_t6_git_rename_with_modification_attributes_per_finding(self):
        """Moved AND modified, correspondence reported by Git: the
        pre-existing anomaly informs, the new one blocks."""
        self._init_git()
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER,
                                    body=helpers.MINIMAL_BODY + "// filler line\n" * 40)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "baseline")
        self._start()
        old = pdir / "My Indicator.pine"
        new = pdir / "Renamed Indicator.pine"
        self._git("mv", str(old.relative_to(self.root)), str(new.relative_to(self.root)))
        new.write_text(new.read_text(encoding="utf-8") +
                       "// see https://promo.example.com\n", encoding="utf-8")
        self._git("add", "-A")
        manifest = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        manifest["source"] = "Renamed Indicator.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(manifest), encoding="utf-8")
        decision, info = self._stop()
        self.assertEqual(decision["decision"], "block")
        introduced = decision["reason"].split("Signalé sans blocage")[0]
        self.assertIn("no-promo-urls", introduced)
        self.assertNotIn("header-version", introduced)
        self.assertTrue(any("header-version" in i and "préexistant" in i for i in info), info)

    def test_t6b_same_product_same_name_is_not_a_provenance(self):
        """Untracked move with modification: a shared product or file name
        never establishes provenance — indeterminate, no block."""
        pdir = helpers.make_product(self.root)
        self._start()
        old = pdir / "My Indicator.pine"
        sub = pdir / "src"
        sub.mkdir()
        new = sub / "My Indicator.pine"
        new.write_text(old.read_text(encoding="utf-8").replace("// Version: 1.0.0\n", ""),
                       encoding="utf-8")
        old.unlink()
        manifest = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        manifest["source"] = "src/My Indicator.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(manifest), encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("indéterminée" in i for i in info), info)

    def test_t7_no_correspondence_is_indeterminate(self):
        pdir = helpers.make_product(self.root)
        self._start()
        (pdir / "My Indicator.pine").unlink()
        other = helpers.make_product(self.root, slug="other",
                                     header=self.NO_VERSION_HEADER)
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("indéterminée" in i and "header-version" in i
                            for i in info), info)
        self.assertTrue(other.is_dir())

    def test_t8_two_findings_same_check_only_the_new_one_blocks(self):
        pdir = helpers.make_product(
            self.root, body=helpers.MINIMAL_BODY + "// https://old.example.com\n")
        self._start()
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://new.example.com\n",
                       encoding="utf-8")
        decision, info = self._stop()
        self.assertEqual(decision["decision"], "block")
        introduced = decision["reason"].split("Signalé sans blocage")[0]
        self.assertIn("https://new.example.com", introduced)
        self.assertNotIn("https://old.example.com", introduced)
        self.assertTrue(any("https://old.example.com" in i and "préexistant" in i
                            for i in info), info)

    def test_t10_old_snapshot_without_findings_never_blocks_retroactively(self):
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER)
        self._start()
        snap = self.root / session.SESSION_DIR_REL / "s1.json"
        data = json.loads(snap.read_text(encoding="utf-8"))
        del data["guard"]  # snapshot written by the previous tooling
        snap.write_text(json.dumps(data), encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("rendu visible" in i for i in info), info)
        self.assertTrue(pdir.is_dir())

    def test_t11_line_shift_does_not_create_a_new_finding(self):
        pdir = helpers.make_product(
            self.root, body=helpers.MINIMAL_BODY + "// https://old.example.com\n")
        self._start()
        src = pdir / "My Indicator.pine"
        text = src.read_text(encoding="utf-8")
        src.write_text(text.replace('indicator("Test Indicator")',
                                    'indicator("Test Indicator")\n// a\n// b\n// c'),
                       encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("préexistant" in i for i in info), info)

    def test_t12_same_url_added_again_is_one_introduced_finding(self):
        pdir = helpers.make_product(
            self.root, body=helpers.MINIMAL_BODY + "// https://dup.example.com\n")
        self._start()
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://dup.example.com\n",
                       encoding="utf-8")
        decision, _ = self._stop()
        self.assertEqual(decision["decision"], "block")
        introduced = decision["reason"].split("Signalé sans blocage")[0]
        self.assertEqual(introduced.count("https://dup.example.com"), 1)

    def test_info_is_handed_to_next_session_start_once(self):
        helpers.make_product(self.root, header=self.NO_VERSION_HEADER)
        self._start()
        self._stop()
        text, status = session.hook_session_start(
            self.root, {"session_id": "s2", "source": "startup"})
        self.assertIn(i18n.t("summary.list.stop", "fr"), text)          # French summary: "HOOK STOP — …"
        self.assertTrue(status["stop_info"])
        text2, _ = session.hook_session_start(
            self.root, {"session_id": "s3", "source": "startup"})
        self.assertNotIn(i18n.t("summary.list.stop", "fr"), text2)


    def test_ambiguous_git_rename_stays_indeterminate(self):
        """Closing review I2: two files derived from the vanished baseline
        file — Git reports one as renamed, the other as added. Git merely
        picked a candidate: nothing is attributed, nothing blocks."""
        self._init_git()
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER,
                                    body=helpers.MINIMAL_BODY + "// filler line\n" * 40)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "baseline")
        self._start()
        old = pdir / "My Indicator.pine"
        text = old.read_text(encoding="utf-8")
        (pdir / "X.pine").write_text(text + "// https://promo.example.com\n",
                                     encoding="utf-8")
        (pdir / "Y.pine").write_text(text + "// other line\n", encoding="utf-8")
        old.unlink()
        self._git("add", "-A")
        manifest = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        manifest["source"] = "X.pine"
        (pdir / "SCRIPT.json").write_text(json.dumps(manifest), encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("X.pine" in i and "indéterminée" in i for i in info), info)

    def test_unevaluable_check_on_modified_content_is_not_called_a_context_effect(self):
        """Closing review I3: the label states facts only."""
        orphan_dir = self.root / "scripts" / "later"
        orphan_dir.mkdir()
        src = orphan_dir / "My Indicator.pine"
        src.write_text(helpers.FREE_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        self._start()
        src.write_text(src.read_text(encoding="utf-8") + "// https://promo.example.com\n",
                       encoding="utf-8")
        (orphan_dir / "SCRIPT.json").write_text(json.dumps({
            "schema_version": 1, "id": "later", "source": "My Indicator.pine",
            "script_kind": "indicator", "distribution": "free-open-source"}),
            encoding="utf-8")
        for name in ("PRODUCT.md", "ARCHITECTURE.md", "CLAUDE.md"):
            (orphan_dir / name).write_text("# contexte de test\n", encoding="utf-8")
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("no-promo-urls" in i and "introduction n'est pas exclue" in i
                            for i in info), info)

    def test_corrupt_snapshot_never_crashes_never_blocks_retroactively(self):
        """Closing review I1: malformed guard records degrade to 'guard
        state unknown at start'."""
        helpers.make_product(self.root, header=self.NO_VERSION_HEADER)
        rel = "scripts/my-indicator/My Indicator.pine"
        for bad in ("a string", 5, None, [], {"evaluable": "yes"},
                    {"evaluable": True, "blocking": 5},
                    {"evaluable": True, "blocking": [[["x"], "", 1]]},
                    {"evaluable": True, "blocking": [["c", "s", "many"]]},
                    {"evaluable": True, "blocking": [],
                     "unevaluable_checks": None},
                    {"evaluable": True, "blocking": [],
                     "unevaluable_checks": [["x"]]}):
            sid = "corrupt"
            snap = self.root / session.SESSION_DIR_REL / ("%s.json" % sid)
            if snap.exists():
                snap.unlink()
            self._start(sid)
            data = json.loads(snap.read_text(encoding="utf-8"))
            data["guard"][rel] = bad
            snap.write_text(json.dumps(data), encoding="utf-8")
            decision, _ = self._stop(sid)
            self.assertIsNone(decision, bad)
        for shape in ("[1, 2]", '"text"', '{"files": 3}',
                      '{"files": {"scripts/gone.pine": 1}, "guard": 7}'):
            snap.write_text(shape, encoding="utf-8")
            self.assertEqual(session.hook_stop(self.root, {"session_id": sid}),
                             (0, ""), shape)

    def test_non_object_stdin_never_crashes(self):
        for bad in (["x"], "text", 3, None):
            self.assertEqual(session.hook_stop(self.root, bad), (0, ""))
            text, _ = session.hook_session_start(self.root, bad)
            self.assertIn("PWS", text)

    def test_unsafe_session_id_never_escapes_the_session_directory(self):
        session.hook_session_start(
            self.root, {"session_id": "../../../escaped", "source": "startup"})
        self.assertFalse((self.root / "escaped.json").exists())
        self.assertFalse((self.root.parent / "escaped.json").exists())
        inside = sorted(p.name for p in (self.root / session.SESSION_DIR_REL).iterdir())
        self.assertIn("unsafe-session-id.json", inside)


    # ---- M12 (closing review of the 2026-09-27 maintenance): durable tests
    # for three cases that had only been exercised once, by hand. They test
    # the ratified behaviour as it is; none of them implies a tooling change.

    def _fake_git_status(self, porcelain_z):
        """Patch the `git status` call of _git_renames with a fixed porcelain
        -z stream. Every other git call stays real."""
        import subprocess
        from unittest import mock
        real = subprocess.run

        def fake(cmd, **kwargs):
            if isinstance(cmd, list) and "status" in cmd:
                return mock.Mock(returncode=0, stdout=porcelain_z.encode("utf-8"))
            return real(cmd, **kwargs)

        return mock.patch("subprocess.run", side_effect=fake)

    def test_m12_c_git_copy_entry_is_never_parsed_as_a_rename(self):
        """T-M12-C, parsing: a `C` (copy) entry is not a rename, and a rename
        sharing its origin or its destination with a copy is ambiguous."""
        self._init_git()
        stream = ("C  scripts/p/Copy.pine\0scripts/p/Origin.pine\0"
                  "R  scripts/p/Renamed.pine\0scripts/p/Origin.pine\0"
                  "R  scripts/r/Target.pine\0scripts/r/Source.pine\0"
                  "C  scripts/r2/Target 2.pine\0scripts/r2/Source 2.pine\0"
                  "R  scripts/r2/Target 2.pine\0scripts/r2/Other.pine\0"
                  " M scripts/m/Modified.pine\0"
                  "?? scripts/u/Untracked.pine\0")
        with self._fake_git_status(stream):
            renames = session._git_renames(self.root)
        self.assertEqual(renames, {"scripts/r/Target.pine": "scripts/r/Source.pine"})

    def test_m12_c_git_copy_is_never_a_provenance_for_the_hook(self):
        """T-M12-C, attribution: Git reports the new file as a COPY of a
        baseline file. The copy inherits nothing: every finding of the new
        file is introduced, including the one its origin already had."""
        self._init_git()
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER)
        self._start()
        origin = pdir / "My Indicator.pine"
        other = helpers.make_product(self.root, slug="copied",
                                     header=self.NO_VERSION_HEADER)
        copy = other / "My Indicator.pine"
        copy.write_text(origin.read_text(encoding="utf-8") +
                        "// https://promo.example.com\n", encoding="utf-8")
        stream = ("C  scripts/copied/My Indicator.pine\0"
                  "scripts/my-indicator/My Indicator.pine\0")
        with self._fake_git_status(stream):
            decision, info = self._stop()
        self.assertEqual(decision["decision"], "block")
        introduced = decision["reason"].split("Signalé sans blocage")[0]
        self.assertIn("scripts/copied/My Indicator.pine: [header-version]", introduced)
        self.assertIn("scripts/copied/My Indicator.pine: [no-promo-urls]", introduced)
        self.assertIn("nouveau fichier", introduced)
        self.assertFalse(any("copied" in i and "préexistant" in i for i in info), info)
        # the untouched origin keeps its own pre-existing finding, unblocked
        self.assertTrue(any("scripts/my-indicator/" in i and "préexistant" in i
                            for i in info), info)

    def test_m12_u_real_git_rename_with_accents_and_spaces(self):
        """T-M12-U: a real Git rename to a path with accented characters and
        spaces, then a forbidden URL added. The UTF-8 path of the NUL
        separated stream is decoded; the old finding informs, the new one
        blocks. A single accented name is used: nothing here depends on the
        Unicode normalization of the file system."""
        self._init_git()
        pdir = helpers.make_product(self.root, header=self.NO_VERSION_HEADER,
                                    body=helpers.MINIMAL_BODY + "// filler line\n" * 40)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "baseline")
        self._start()
        old_rel = "scripts/my-indicator/My Indicator.pine"
        new_name = "Indicateur été à séance.pine"
        self._git("mv", old_rel, "scripts/my-indicator/" + new_name)
        listed = [n for n in os.listdir(str(pdir)) if n.endswith(".pine")]
        self.assertEqual(len(listed), 1)
        new = pdir / listed[0]  # the name as the file system stores it
        new.write_text(new.read_text(encoding="utf-8") +
                       "// https://promo.example.com\n", encoding="utf-8")
        self._git("add", "-A")
        manifest = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        manifest["source"] = listed[0]
        (pdir / "SCRIPT.json").write_text(json.dumps(manifest, ensure_ascii=False),
                                          encoding="utf-8")
        renames = session._git_renames(self.root)
        self.assertEqual(list(renames.values()), [old_rel])
        (target,) = renames
        self.assertTrue(target.startswith("scripts/my-indicator/Indicateur "))
        self.assertTrue(target.endswith(" séance.pine") or
                        target.endswith(" séance.pine"), repr(target))
        self.assertNotIn("\\", target)
        self.assertNotIn('"', target)
        decision, info = self._stop()
        self.assertEqual(decision["decision"], "block")
        introduced = decision["reason"].split("Signalé sans blocage")[0]
        self.assertIn("no-promo-urls", introduced)
        self.assertNotIn("header-version", introduced)
        self.assertTrue(any("header-version" in i and "préexistant" in i
                            and "Indicateur " in i for i in info), info)

    def _twin_baseline(self, second_registered):
        """Two baseline sources with the SAME bytes, then a new path carrying
        those bytes. Neither baseline file disappears: no single origin."""
        first = helpers.make_product(self.root, slug="alpha",
                                     header=self.NO_VERSION_HEADER)
        data = (first / "My Indicator.pine").read_bytes()
        if second_registered:
            second = helpers.make_product(self.root, slug="beta",
                                          header=self.NO_VERSION_HEADER)
            self.assertEqual((second / "My Indicator.pine").read_bytes(), data)
        else:
            orphan = self.root / "scripts" / "unregistered twin"
            orphan.mkdir()
            (orphan / "My Indicator.pine").write_bytes(data)
        self._start()
        snapshot = json.loads((self.root / session.SESSION_DIR_REL / "s1.json")
                              .read_text(encoding="utf-8"))
        twins = [k for k, v in snapshot["files"].items()
                 if v == core.sha256_file(first / "My Indicator.pine")]
        self.assertEqual(len(twins), 2)
        states = [snapshot["guard"][k] for k in twins]
        third = helpers.make_product(self.root, slug="gamma",
                                     header=self.NO_VERSION_HEADER)
        self.assertEqual((third / "My Indicator.pine").read_bytes(), data)
        return states

    def test_m12_b_identical_baseline_files_with_identical_guard_states(self):
        """T-M12-B, variant 1: the guard states of the candidates agree, so
        the attribution does not depend on which one is picked."""
        states = self._twin_baseline(second_registered=True)
        self.assertEqual(states[0], states[1])
        decision, info = self._stop()
        self.assertIsNone(decision)
        gamma = [i for i in info if "scripts/gamma/" in i]
        self.assertEqual(len(gamma), 1, info)
        self.assertIn("header-version", gamma[0])
        self.assertIn("préexistant", gamma[0])

    def test_m12_b_identical_baseline_files_with_different_guard_states(self):
        """T-M12-B, variant 2: one candidate was evaluable at start, the
        other was not. No arbitrary choice: the attribution is indeterminate
        and nothing blocks."""
        states = self._twin_baseline(second_registered=False)
        self.assertNotEqual(states[0], states[1])
        self.assertEqual(sorted(s["evaluable"] for s in states), [False, True])
        decision, info = self._stop()
        self.assertIsNone(decision)
        gamma = [i for i in info if "scripts/gamma/" in i]
        self.assertEqual(len(gamma), 1, info)
        self.assertIn("indéterminée", gamma[0])
        self.assertNotIn("préexistant", gamma[0])

    def test_m12_b_order_of_the_candidates_does_not_matter(self):
        """T-M12-B: same outcome whatever the lexical order of the twins."""
        first = helpers.make_product(self.root, slug="zeta",
                                     header=self.NO_VERSION_HEADER)
        orphan = self.root / "scripts" / "alpha orphan"
        orphan.mkdir()
        (orphan / "My Indicator.pine").write_bytes(
            (first / "My Indicator.pine").read_bytes())
        self._start()
        helpers.make_product(self.root, slug="gamma", header=self.NO_VERSION_HEADER)
        decision, info = self._stop()
        self.assertIsNone(decision)
        self.assertTrue(any("scripts/gamma/" in i and "indéterminée" in i
                            for i in info), info)


class TestImportRecord(unittest.TestCase):
    """Complementary pass 2026-09-27 (spec sections 41.2 / 52.5): explicit,
    declarative, non-renewable import record. Product-agnostic: nothing here
    depends on a product name, path or documentary structure."""

    NO_VERSION = helpers.FREE_HEADER.replace("// Version: 1.0.0\n", "")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
        # these attribution tests read the French wording of the Stop hook
        # (the language of the messages is tested in TestStopLanguage20261114)
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def _start(self, sid="s1", source="startup"):
        session.hook_session_start(self.root, {"session_id": sid, "source": source})

    def _stop(self, sid="s1"):
        code, out = session.hook_stop(self.root, {"session_id": sid})
        self.assertEqual(code, 0)
        path = session._stop_info_path(self.root, sid)  # one file per session
        info = json.loads(path.read_text(encoding="utf-8"))["info"] if path.exists() else []
        return (json.loads(out)["reason"] if out else None), info

    def _drop(self, name="Imported v3.pine", header=None, body=helpers.MINIMAL_BODY):
        f = self.root / "scripts" / name
        f.write_text((self.NO_VERSION if header is None else header) + body,
                     encoding="utf-8")
        return f

    def _onboard(self, orphan, slug="imported", distribution="free-open-source"):
        pdir = helpers.make_product(self.root, slug=slug, distribution=distribution)
        target = pdir / "My Indicator.pine"
        target.unlink()
        orphan.rename(target)
        return target

    def test_scenario_a_import_never_declared_blocks_with_onboarding_action(self):
        self._start()
        self._drop()
        reason, _ = self._stop()
        self.assertIn("pine-onboard", reason)

    def test_scenario_a_declared_unchanged_import_informs_without_blocking(self):
        self._start()
        orphan = self._drop()
        res = session.register_import(self.root, orphan)
        self.assertTrue(res["registered"], res)
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertTrue(any("import déclaré" in i for i in info), info)

    def test_scenario_b_without_record_still_blocks_as_new_file(self):
        self._start()
        self._onboard(self._drop())
        reason, _ = self._stop()
        self.assertIn("nouveau fichier", reason)

    def test_scenario_b_declared_import_onboarded_unchanged_never_blocks(self):
        self._start()
        orphan = self._drop()
        sha = core.sha256_file(orphan)
        self.assertTrue(session.register_import(self.root, orphan)["registered"])
        target = self._onboard(orphan)
        self.assertEqual(core.sha256_file(target), sha)
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertTrue(any("header-version" in i and "préexistant à l'import" in i
                            for i in info), info)

    def test_scenario_c_file_present_at_start_needs_no_record(self):
        orphan = self._drop()
        self._start()
        res = session.register_import(self.root, orphan)
        self.assertFalse(res["registered"])
        self.assertIn("present at session start", res["reason"])
        self._onboard(orphan)
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertTrue(any("rendu visible" in i for i in info), info)

    def test_modification_after_import_blocks_only_what_was_introduced(self):
        self._start()
        orphan = self._drop()
        session.register_import(self.root, orphan)
        target = self._onboard(orphan)
        session.register_import(self.root, target)  # relocation, same content
        target.write_text(target.read_text(encoding="utf-8") +
                          "// https://promo.example.com\n", encoding="utf-8")
        reason, info = self._stop()
        introduced = reason.split("Signalé sans blocage")[0]
        self.assertIn("no-promo-urls", introduced)
        self.assertNotIn("header-version", introduced)
        self.assertTrue(any("header-version" in i and "préexistant à l'import" in i
                            for i in info), info)

    def test_relocation_is_followed_by_the_hook_without_explicit_call(self):
        self._start()
        orphan = self._drop()
        session.register_import(self.root, orphan)
        target = self._onboard(orphan)
        self.assertIsNone(self._stop()[0])  # the hook follows the unchanged move
        target.write_text(target.read_text(encoding="utf-8") +
                          "// https://promo.example.com\n", encoding="utf-8")
        reason, _ = self._stop()
        self.assertIn("no-promo-urls", reason.split("Signalé sans blocage")[0])

    def test_record_is_never_renewed_after_modification(self):
        self._start()
        orphan = self._drop(header=helpers.FREE_HEADER)
        self.assertTrue(session.register_import(self.root, orphan)["registered"])
        before = (self.root / session.SESSION_DIR_REL / "imports.json").read_bytes()
        orphan.write_text(orphan.read_text(encoding="utf-8") +
                          "// https://promo.example.com\n", encoding="utf-8")
        res = session.register_import(self.root, orphan)
        self.assertFalse(res["registered"])
        self.assertTrue(res.get("refused"))
        self.assertIn("never renewed", res["reason"])
        self.assertEqual(
            (self.root / session.SESSION_DIR_REL / "imports.json").read_bytes(), before)
        self._onboard(orphan)
        reason, _ = self._stop()
        self.assertIn("no-promo-urls", reason)

    def test_moved_and_modified_without_relocation_is_never_laundered(self):
        """Moved AND modified before any relocation: the record cannot be
        paired, a new registration records the MODIFIED state only as a
        distinct import — the anomaly present in it is not attributed to the
        original import."""
        self._start()
        orphan = self._drop(header=helpers.FREE_HEADER)
        session.register_import(self.root, orphan)
        text = orphan.read_text(encoding="utf-8")
        target = self._onboard(orphan)
        target.write_text(text + "// https://promo.example.com\n", encoding="utf-8")
        reason, _ = self._stop()
        self.assertIn("no-promo-urls", reason)

    def test_reregistration_after_move_and_modification_never_launders(self):
        """External verification of r2: compliant import, moved to its
        product root, modified (forbidden URL) BEFORE the move was attached,
        then registered again on the new path. The command must not create a
        fresh reference; the following Stop must still block."""
        self._start()
        orphan = self._drop(header=helpers.FREE_HEADER)
        first = session.register_import(self.root, orphan)
        self.assertTrue(first["registered"], first)
        imports = self.root / session.SESSION_DIR_REL / "imports.json"
        recorded = imports.read_bytes()
        target = self._onboard(orphan)
        target.write_text(target.read_text(encoding="utf-8") +
                          "// https://promo.example.com\n", encoding="utf-8")
        reason, _ = self._stop()
        self.assertIn("no-promo-urls", reason)
        again = session.register_import(self.root, target)
        self.assertFalse(again["registered"], again)
        self.assertFalse(again["relocated"])
        self.assertTrue(again.get("refused"))
        self.assertEqual(again["lost_records"], ["scripts/Imported v3.pine"])
        self.assertIn("no new record is created", again["reason"])
        self.assertEqual(imports.read_bytes(), recorded,
                         "the initial record is kept untouched")
        reason, info = self._stop()
        self.assertIsNotNone(reason)
        introduced = reason.split("Signalé sans blocage")[0]
        self.assertIn("no-promo-urls", introduced)
        self.assertFalse(any("préexistant à l'import" in i for i in info), info)
        # a third attempt changes nothing either
        self.assertTrue(session.register_import(self.root, target).get("refused"))
        self.assertIn("no-promo-urls", self._stop()[0])
        # CLI: a refusal is a non-zero exit
        from tools.pws_workspace import __main__ as cli
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["--root", str(self.root), "import-register", str(target)])
        self.assertEqual(code, 1)

    def test_lost_record_refuses_an_unrelated_candidate_too(self):
        """Same name or same product proves nothing, and neither does their
        absence: while a record has lost its file, a candidate that does not
        carry its content gets no fresh record, whatever its name."""
        self._start()
        orphan = self._drop(header=helpers.FREE_HEADER)
        session.register_import(self.root, orphan)
        orphan.unlink()
        other = self._drop(name="Another Script.pine", header=helpers.FREE_HEADER,
                           body=helpers.MINIMAL_BODY + "plot(open, title=\"O\")\n")
        res = session.register_import(self.root, other)
        self.assertTrue(res.get("refused"))
        self.assertFalse(res["registered"])

    def test_ordinary_import_and_unchanged_move_still_work(self):
        self._start()
        a = self._drop(name="A.pine")
        b = self._drop(name="B.pine", body=helpers.MINIMAL_BODY + "// b\n")
        self.assertTrue(session.register_import(self.root, a)["registered"])
        self.assertTrue(session.register_import(self.root, b)["registered"])
        target = self._onboard(a, slug="prod-a")
        moved = session.register_import(self.root, target)
        self.assertTrue(moved["registered"] and moved["relocated"], moved)
        # with every record attached again, a further import is accepted
        c = self._drop(name="C.pine", body=helpers.MINIMAL_BODY + "// c\n")
        self.assertTrue(session.register_import(self.root, c)["registered"])
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertTrue(any("prod-a" in i and "préexistant à l'import" in i
                            for i in info), info)

    def test_equal_fingerprint_does_not_exempt_a_copy(self):
        self._start()
        orphan = self._drop()
        session.register_import(self.root, orphan)
        copy_dir = helpers.make_product(self.root, slug="copy")
        (copy_dir / "My Indicator.pine").write_bytes(orphan.read_bytes())
        reason, _ = self._stop()
        self.assertIn("scripts/copy/My Indicator.pine", reason)
        self.assertIn("nouveau fichier", reason)
        self.assertNotIn("Imported v3.pine: [", reason.split("Signale")[0])

    def test_lost_record_with_two_identical_candidates_is_indeterminate(self):
        self._start()
        orphan = self._drop()
        session.register_import(self.root, orphan)
        data = orphan.read_bytes()
        orphan.unlink()
        for slug in ("first", "second"):
            pdir = helpers.make_product(self.root, slug=slug)
            (pdir / "My Indicator.pine").write_bytes(data)
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertEqual(sum(1 for i in info if "indéterminée" in i), 2, info)

    def test_guard_runs_in_the_current_context_on_an_imported_file(self):
        """A check not evaluable at import (distribution unknown) becomes
        visible with the manifest: reported, never silently exempted."""
        self._start()
        orphan = self._drop(header=helpers.FREE_HEADER)
        session.register_import(self.root, orphan)
        self._onboard(orphan, distribution="paid-closed-source")
        reason, info = self._stop()
        self.assertIsNone(reason)
        self.assertTrue(any("header-structure" in i and "non évaluable à l'import" in i
                            for i in info), info)

    def test_registration_boundaries(self):
        self._start()
        outside = Path(self.tmp.name) / "Outside.pine"
        outside.write_text(helpers.FREE_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        self.assertFalse(session.register_import(self.root, outside)["registered"])
        (self.root / "scripts" / "note.txt").write_text("x", encoding="utf-8")
        self.assertFalse(session.register_import(
            self.root, self.root / "scripts" / "note.txt")["registered"])
        self.assertFalse(session.register_import(
            self.root, self.root / "scripts" / "Absent.pine")["registered"])
        orphan = self._drop()
        self.assertTrue(session.register_import(self.root, orphan)["registered"])
        again = session.register_import(self.root, orphan)
        self.assertFalse(again["registered"])
        self.assertIn("unchanged", again["reason"])

    def test_records_survive_resume_and_other_sessions_and_are_pruned_when_unused(self):
        """Audit D-05 (2026-11-13): the start of another session no longer
        erases the records of a session still open; a record is pruned once
        no present session can use it."""
        self._start()
        orphan = self._drop()
        session.register_import(self.root, orphan)
        imports = self.root / session.SESSION_DIR_REL / "imports.json"
        self._start("s2", source="resume")
        self.assertTrue(imports.exists())
        self._onboard(orphan)
        self.assertIsNone(self._stop("s2")[0])
        self._start("s3", source="startup")      # another session meanwhile
        self.assertIn("scripts/Imported v3.pine",
                      json.loads(imports.read_text(encoding="utf-8"))["imports"])
        self.assertIsNone(self._stop("s2")[0], "s2 still sees its import")
        for sid in ("s1", "s2"):                  # sessions gone (startup cleanup)
            session._snapshot_paths(self.root, sid)[1].unlink()
        self._start("s4", source="startup")
        self.assertEqual(json.loads(imports.read_text(encoding="utf-8"))["imports"], {})

    def test_corrupt_import_file_never_crashes(self):
        self._start()
        self._onboard(self._drop())
        imports = self.root / session.SESSION_DIR_REL / "imports.json"
        for shape in ("[1]", '{"imports": 3}', '{"imports": {"a": 1}}',
                      '{"imports": {"a": {"path": "b", "sha256": 1, "guard": {}}}}'):
            imports.write_text(shape, encoding="utf-8")
            code, out = session.hook_stop(self.root, {"session_id": "s1"})
            self.assertEqual(code, 0)
            self.assertIn("nouveau fichier", out, shape)



class TestSessionIsolation20261113(unittest.TestCase):
    """Audit 2026-11-12/13: D-05 (two sessions on one workspace), D-07 (hook
    failure traced), E-06 (snapshot of an active session kept), C-10 (block
    message never invites removing a licence mention)."""
    NO_VERSION = helpers.FREE_HEADER.replace("// Version: 1.0.0\n", "")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
        # these attribution tests read the French wording of the Stop hook
        # (the language of the messages is tested in TestStopLanguage20261114)
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def _start(self, sid, source="startup"):
        return session.hook_session_start(self.root, {"session_id": sid, "source": source})

    def _stop(self, sid):
        code, out = session.hook_stop(self.root, {"session_id": sid})
        self.assertEqual(code, 0)
        path = session._stop_info_path(self.root, sid)
        info = json.loads(path.read_text(encoding="utf-8"))["info"] if path.exists() else []
        return (json.loads(out)["reason"] if out else None), info

    def _snap(self, sid):
        return session._snapshot_paths(self.root, sid)[1]

    def test_c1_an_import_survives_the_start_of_another_session(self):
        self._start("A")
        orphan = self.root / "scripts" / "Imported v3.pine"
        orphan.write_text(self.NO_VERSION + helpers.MINIMAL_BODY, encoding="utf-8")
        self.assertTrue(session.register_import(self.root, orphan)["registered"])
        self._start("B")                                   # another terminal
        pdir = helpers.make_product(self.root, slug="imported")
        target = pdir / "My Indicator.pine"
        target.write_bytes(orphan.read_bytes())
        orphan.unlink()                                    # onboarding moves it
        reason, info = self._stop("A")
        self.assertIsNone(reason, "an import is never taken for a creation")
        self.assertTrue(any("header-version" in i and "à l'import" in i for i in info), info)

    def test_c2_the_stop_of_another_session_never_erases_pending_information(self):
        pdir = helpers.make_product(self.root, header=self.NO_VERSION)
        self._start("A")
        self._start("B")
        _, info_a = self._stop("A")
        self.assertTrue(any("header-version" in i and "préexistant" in i for i in info_a))
        src = pdir / "My Indicator.pine"
        src.write_text(helpers.FREE_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        _, info_b = self._stop("B")                        # nothing to report for B
        self.assertEqual(info_b, [])
        self.assertTrue(session._stop_info_path(self.root, "A").exists())
        _, status = self._start("C")
        self.assertTrue(any(i.startswith("[session A] ") and "header-version" in i
                            for i in status["stop_info"]), status["stop_info"])
        _, status = self._start("D")
        self.assertEqual(status["stop_info"], [], "shown once")

    def test_c3_a_resume_after_another_active_session_carries_nothing(self):
        pdir = helpers.make_product(self.root)
        self._start("A")
        self._start("B")
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://promo.example.com\n",
                       encoding="utf-8")
        self.assertIn("no-promo-urls", self._stop("A")[0] or "")
        b_started = session._stamp_epoch(json.loads(
            self._snap("B").read_text(encoding="utf-8"))["created_at"])
        os.utime(str(self._snap("A")), (b_started + 5, b_started + 5))  # A active after B
        self._start("A-resumed", source="resume")         # new identifier, pointer = B
        snap = json.loads(self._snap("A-resumed").read_text(encoding="utf-8"))
        self.assertNotIn("carried_from", snap)
        self.assertEqual(snap["lineage"], {"established": False, "pointer": "B"})
        reason, info = self._stop("A-resumed")
        self.assertIsNone(reason)
        self.assertTrue(any("no-promo-urls" in i and "lignée de session non établie" in i
                            for i in info), info)

    def test_c3_a_resume_without_concurrent_activity_still_carries(self):
        pdir = helpers.make_product(self.root)
        self._start("A")
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://promo.example.com\n",
                       encoding="utf-8")
        self._start("A2", source="resume")
        snap = json.loads(self._snap("A2").read_text(encoding="utf-8"))
        self.assertEqual(snap.get("carried_from"), "A")
        self.assertIn("no-promo-urls", self._stop("A2")[0] or "")

    def test_c3_a_forked_session_never_infers_its_parent(self):
        pdir = helpers.make_product(self.root)
        self._start("A")
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://promo.example.com\n",
                       encoding="utf-8")
        self._start("F", source="fork")
        snap = json.loads(self._snap("F").read_text(encoding="utf-8"))
        self.assertNotIn("carried_from", snap)
        self.assertEqual(snap["lineage"], {"established": False, "pointer": "A"})
        reason, info = self._stop("F")
        self.assertIsNone(reason)
        self.assertTrue(any("lignée de session non établie" in i for i in info), info)

    def test_d07_a_hook_failure_is_traced_and_announced_once(self):
        helpers.make_product(self.root)
        self._start("A")
        original = session._hook_stop
        session._hook_stop = lambda root, data: 1 / 0
        try:
            self.assertEqual(session.hook_stop(self.root, {"session_id": "A"}), (0, ""))
        finally:
            session._hook_stop = original
        trace = json.loads((self.root / session.SESSION_DIR_REL / session.HOOK_ERRORS)
                           .read_text(encoding="utf-8"))["errors"]
        self.assertEqual(len(trace), 1)
        self.assertIn("ZeroDivisionError", trace[0]["error"])
        text, status = self._start("B")
        self.assertTrue(status["hook_errors"])
        self.assertIn("hook-errors.json", text)
        _, status = self._start("C")
        self.assertEqual(status["hook_errors"], [], "announced once, trace kept")

    def test_e06_the_stop_refreshes_the_snapshot_and_the_start_keeps_it(self):
        helpers.make_product(self.root)
        self._start("A")
        old = self._snap("A").stat().st_mtime - 30 * 86400
        os.utime(str(self._snap("A")), (old, old))
        self._stop("A")
        self.assertGreater(self._snap("A").stat().st_mtime, old + 29 * 86400)
        os.utime(str(self._snap("A")), (old, old))
        self._start("B")                                   # latest = B, A idle 30 days
        self.assertFalse(self._snap("A").exists(), "an idle snapshot is still cleaned")
        self._start("C")
        old = self._snap("C").stat().st_mtime - 30 * 86400
        os.utime(str(self._snap("C")), (old, old))
        self._start("D")
        self._start("C", source="resume")                  # same identifier comes back
        self.assertTrue(self._snap("C").exists(), "the current session is never cleaned")

    def test_c10_a_block_on_a_possible_licence_mention_says_never_remove_it(self):
        pdir = helpers.make_product(self.root)
        self._start("A")
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://example.org/LICENSE\n",
                       encoding="utf-8")
        reason, _ = self._stop("A")
        self.assertIn("no-promo-urls", reason)
        self.assertIn("Ne jamais retirer ni modifier une notice de licence", reason)
        src.write_text(self.NO_VERSION + helpers.MINIMAL_BODY, encoding="utf-8")
        reason, _ = self._stop("A")
        self.assertIn("header-version", reason)
        self.assertNotIn("notice de licence", reason)


class TestStopLanguage20261114(unittest.TestCase):
    """2026-11-14: every text of the Stop path — blocking reason, non-blocking
    information, categories, warning on legal mentions, information handed
    to the next summary — follows the language in force when it is shown;
    the verdict never depends on the language; paths, check identifiers and
    guard details are reproduced exactly; information recorded by an earlier
    version is shown as recorded, never reinterpreted. These tests check the
    text the tooling transmits, not its rendering in Claude Code."""

    NO_VERSION = helpers.FREE_HEADER.replace("// Version: 1.0.0\n", "")
    ITEM_RE = __import__("re").compile(r"^- (\S+?): (\[[\w-]+\] )?", __import__("re").M)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _workspace(self, name, lang):
        holder = Path(self.tmp.name) / name
        holder.mkdir()
        root = helpers.make_workspace(str(holder))
        (root / core.LOCAL_SETTINGS_REL).parent.mkdir(parents=True, exist_ok=True)
        (root / core.LOCAL_SETTINGS_REL).write_text(json.dumps(
            {"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
        if lang is not None:
            self.assertTrue(config.set_value(root, "language", lang)["ok"])
        return root

    def _stop(self, root, sid):
        code, out = session.hook_stop(root, {"session_id": sid})
        self.assertEqual(code, 0)
        return json.loads(out) if out else None

    def _unregistered_event(self, root):
        """A script created during the session outside any product."""
        session.hook_session_start(root, {"session_id": "s1", "source": "startup"})
        new = root / "scripts" / "fresh" / "Fresh.pine"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("//@version=6\nindicator('Fresh')\nplot(close)\n", encoding="utf-8")
        return self._stop(root, "s1")

    def _licence_event(self, root):
        """A pre-existing finding (no Version line) and an introduced licence URL."""
        pdir = helpers.make_product(root, header=self.NO_VERSION)
        session.hook_session_start(root, {"session_id": "s1", "source": "startup"})
        src = pdir / "My Indicator.pine"
        src.write_text(src.read_text(encoding="utf-8") + "// https://example.org/LICENSE\n",
                       encoding="utf-8")
        return self._stop(root, "s1")

    def _shape(self, decision):
        """Language-independent shape of a decision: verdict, keys, items."""
        reason = decision["reason"]
        return (decision["decision"], sorted(decision),
                [(m.group(1), m.group(2)) for m in self.ITEM_RE.finditer(reason)])

    def test_unregistered_script_blocks_in_the_configured_language_with_the_same_verdict(self):
        en = self._unregistered_event(self._workspace("en", "en"))
        fr = self._unregistered_event(self._workspace("fr", "fr"))
        self.assertTrue(en["reason"].startswith(i18n.t("stop.reason.introduced", "en")), en["reason"])
        self.assertIn("scripts/fresh/Fresh.pine: modified during the session but UNREGISTERED — run pine-onboard",
                      en["reason"])
        self.assertIsNone(__import__("re").search(r"[éèêàùç]|pendant|exécuter", en["reason"]), en["reason"])
        self.assertTrue(fr["reason"].startswith(i18n.t("stop.reason.introduced", "fr")), fr["reason"])
        self.assertIn("scripts/fresh/Fresh.pine: modifié pendant la session mais UNREGISTERED — exécuter pine-onboard",
                      fr["reason"])
        self.assertEqual(self._shape(en), self._shape(fr))          # same verdict, same protocol, same items
        self.assertEqual(self._shape(en)[:2], ("block", ["decision", "reason"]))

    def test_non_blocking_information_and_legal_warning_in_both_languages(self):
        decisions = {}
        for lang, preexisting in (("en", "pre-existing"), ("fr", "préexistant")):
            root = self._workspace("ws-" + lang, lang)
            d = self._licence_event(root)
            decisions[lang] = d
            reason = d["reason"]
            self.assertIn(i18n.t("stop.reason.legal", lang), reason)
            self.assertIn(i18n.t("stop.reason.info", lang), reason)
            introduced, informed = reason.split(i18n.t("stop.reason.info", lang))
            self.assertIn("[no-promo-urls] https://example.org/LICENSE", introduced)  # detail reproduced exactly
            self.assertIn("[header-version]", informed)
            self.assertIn(preexisting, informed)
            record = json.loads(session._stop_info_path(root, "s1").read_text(encoding="utf-8"))
            self.assertEqual((record["format"], record["language"]), (session.STOP_INFO_FORMAT, lang))
            self.assertEqual([i["k"] for i in record["items"]], ["note"])
            self.assertEqual(record["items"][0]["label"], {"k": "preexisting"})
            self.assertEqual(record["info"], [session._render_stop_item(record["items"][0], lang)])
        self.assertEqual(self._shape(decisions["en"]), self._shape(decisions["fr"]))
        self.assertNotIn("Ne jamais", decisions["en"]["reason"])
        self.assertNotIn("Never remove", decisions["fr"]["reason"])

    def test_recorded_information_is_worded_in_the_language_in_force_when_shown(self):
        for recorded, shown, word, other in (("fr", "en", "pre-existing", "préexistant"),
                                             ("en", "fr", "préexistant", "pre-existing")):
            root = self._workspace("switch-" + recorded, recorded)
            self._licence_event(root)
            self.assertTrue(config.set_value(root, "language", shown)["ok"])   # explicit change after the record
            text, status = session.hook_session_start(root, {"session_id": "s2", "source": "startup"})
            self.assertEqual(len(status["stop_info"]), 1, status["stop_info"])
            line = status["stop_info"][0]
            self.assertTrue(line.startswith("[session s1] "), line)
            self.assertIn(word, line)
            self.assertNotIn(other, line)
            self.assertIn(i18n.t("summary.list.stop", shown), text)
            text2, status2 = session.hook_session_start(root, {"session_id": "s3", "source": "startup"})
            self.assertEqual(status2["stop_info"], [])                         # still shown once

    def test_information_of_earlier_versions_is_shown_as_recorded(self):
        root = self._workspace("legacy", "en")
        sdir = root / session.SESSION_DIR_REL
        (sdir / session.STOP_INFO_DIR).mkdir(parents=True, exist_ok=True)
        old_single = "scripts/x/X.pine: [header-version] no '// Version: X.Y.Z' line in header — preexistant"
        old_session = ("scripts/y/Y.pine: UNREGISTERED — executer pine-onboard — deplace sans modification, "
                       "deja non enregistre")
        (sdir / "stop-info.json").write_text(json.dumps({"info": [old_single]}), encoding="utf-8")
        (sdir / session.STOP_INFO_DIR / "oldsession.json").write_text(
            json.dumps({"session_id": "oldsession", "info": [old_session]}), encoding="utf-8")
        (sdir / session.STOP_INFO_DIR / "future01.json").write_text(json.dumps(
            {"session_id": "future01", "format": 3, "items": [{"k": "unknown-kind", "rel": "scripts/z/Z.pine"}],
             "info": ["recorded line of an unknown kind"]}), encoding="utf-8")
        text, status = session.hook_session_start(root, {"session_id": "now", "source": "startup"})
        marker = i18n.t("stop.recorded", "en")
        self.assertIn(marker + old_single, status["stop_info"])
        self.assertIn("[session oldsessi] " + marker + old_session, status["stop_info"])
        self.assertIn("[session future01] " + marker + "recorded line of an unknown kind", status["stop_info"])
        self.assertEqual(len(status["stop_info"]), 3, status["stop_info"])
        _, again = session.hook_session_start(root, {"session_id": "later", "source": "startup"})
        self.assertEqual(again["stop_info"], [])
        # the same records shown in French keep their words, only the marker follows the language
        root_fr = self._workspace("legacy-fr", "fr")
        sdir = root_fr / session.SESSION_DIR_REL
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "stop-info.json").write_text(json.dumps({"info": [old_single]}), encoding="utf-8")
        _, status = session.hook_session_start(root_fr, {"session_id": "now", "source": "startup"})
        self.assertEqual(status["stop_info"], [i18n.t("stop.recorded", "fr") + old_single])

    def test_fallback_without_configuration_or_with_an_unknown_language_is_english(self):
        absent = self._workspace("absent", None)
        self.assertFalse((absent / "pws.config.json").exists())
        d = self._unregistered_event(absent)
        self.assertTrue(d["reason"].startswith(i18n.t("stop.reason.introduced", i18n.DEFAULT_LANGUAGE)))
        self.assertEqual(i18n.DEFAULT_LANGUAGE, "en")
        unknown = self._workspace("unknown", "fr")
        cfg = json.loads((unknown / "pws.config.json").read_text(encoding="utf-8"))
        cfg["language"] = "de"
        (unknown / "pws.config.json").write_text(json.dumps(cfg), encoding="utf-8")
        d = self._unregistered_event(unknown)
        self.assertTrue(d["reason"].startswith(i18n.t("stop.reason.introduced", "en")), d["reason"])

    def test_every_stop_text_exists_in_both_languages(self):
        keys = [k for k in i18n._CATALOGUE if k.startswith("stop.")]
        self.assertGreaterEqual(len(keys), 20)
        for k in keys:
            self.assertEqual(sorted(i18n._CATALOGUE[k]), ["en", "fr"], k)
        for item in ({"k": "unregistered", "rel": "a.pine", "cat": c}
                     for c in ("moved-unchanged", "imported-unchanged", "indeterminate")):
            for lang in ("en", "fr"):
                self.assertIsNotNone(session._render_stop_item(item, lang), item)
        self.assertIsNone(session._render_stop_item({"k": "unregistered", "rel": "a.pine", "cat": "?"}, "en"))
        self.assertIsNone(session._render_stop_item({"k": "note", "rel": "a.pine", "check": "c", "text": "t",
                                                     "label": {"k": "visible"}}, "en"))   # no moment: not worded


if __name__ == "__main__":
    unittest.main()
