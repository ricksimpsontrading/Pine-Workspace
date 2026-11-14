# SPDX-License-Identifier: Apache-2.0
"""PWS configuration: defaults, validation, atomic RMW, init refusal,
separation from Claude Code settings (2026-11-06)."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import config, core, i18n
from tools.tests import helpers


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_without_file(self):
        cfg = config.read_config(self.root)
        self.assertFalse(cfg["present"])
        self.assertIsNone(cfg["error"])
        self.assertEqual(cfg["data"]["language"], "en")
        self.assertEqual(cfg["data"]["tv_validation_mode"], "manual")
        self.assertFalse(config.identity(self.root)["configured"])
        self.assertEqual(config.language(self.root), "en")

    def test_init_then_values(self):
        r = config.init_config(self.root, "fr", "Holder Test", ["HolderAlias"], "COMMERCIAL")
        self.assertTrue(r["ok"], r)
        ident = config.identity(self.root)
        self.assertEqual((ident["configured"], ident["copyright_holder"]), (True, "Holder Test"))
        self.assertEqual(ident["header_aliases"], ["HolderAlias"])
        self.assertEqual(config.language(self.root), "fr")
        data = json.loads(config.config_path(self.root).read_text(encoding="utf-8"))
        from tools.pws_workspace import version
        self.assertEqual(data["workspace_version"], version.WORKSPACE_VERSION)

    def test_init_refuses_overwrite_without_force(self):
        config.init_config(self.root, "fr", "Holder Test")
        r = config.init_config(self.root, "en", "Other")
        self.assertFalse(r["ok"])
        self.assertEqual(config.identity(self.root)["copyright_holder"], "Holder Test")
        r = config.init_config(self.root, "en", "Other", force=True)
        self.assertTrue(r["ok"])
        self.assertEqual(config.identity(self.root)["copyright_holder"], "Other")

    def test_unsupported_language_refused(self):
        r = config.init_config(self.root, "de")
        self.assertFalse(r["ok"])
        self.assertEqual(i18n.normalize_language("de"), "en")

    def test_set_value_and_validation(self):
        config.init_config(self.root, "en")
        self.assertTrue(config.set_value(self.root, "language", "fr")["ok"])
        self.assertEqual(config.language(self.root), "fr")
        self.assertFalse(config.set_value(self.root, "language", "xx")["ok"])
        self.assertFalse(config.set_value(self.root, "github.destinations", [])["ok"])
        self.assertTrue(config.set_value(self.root, "identity.copyright_holder", None)["ok"])
        self.assertFalse(config.identity(self.root)["configured"])

    def test_malformed_file_reported_defaults_apply(self):
        config.config_path(self.root).write_text("{broken", encoding="utf-8")
        cfg = config.read_config(self.root)
        self.assertTrue(cfg["present"])
        self.assertIsNotNone(cfg["error"])
        self.assertEqual(cfg["data"]["language"], "en")
        r = config.set_value(self.root, "language", "fr")
        self.assertFalse(r["ok"])

    def test_update_preserves_unknown_keys(self):
        config.config_path(self.root).write_text(json.dumps({
            "schema_version": 1, "language": "fr", "custom_note": "keep me"}), encoding="utf-8")
        self.assertTrue(config.set_value(self.root, "tv_validation_mode", "chrome-experimental")["ok"])
        data = json.loads(config.config_path(self.root).read_text(encoding="utf-8"))
        self.assertEqual(data["custom_note"], "keep me")
        self.assertEqual(data["language"], "fr")

    def test_symlinked_config_never_read_or_written(self):
        import os
        outside = self.root.parent / "outside config.json"
        outside.write_text(json.dumps({"schema_version": 1, "language": "fr"}), encoding="utf-8")
        os.symlink(outside, config.config_path(self.root))
        cfg = config.read_config(self.root)
        self.assertIsNotNone(cfg["error"])
        self.assertFalse(config.set_value(self.root, "language", "en")["ok"])
        self.assertEqual(json.loads(outside.read_text(encoding="utf-8"))["language"], "fr")

    def test_destination_validation(self):
        self.assertEqual(config.destination_problems(
            {"name": "pub", "repo": "owner/repo", "visibility": "public",
             "path_prefix": "Published", "branch": "main"}), [])
        self.assertTrue(config.destination_problems({"name": "x y", "repo": "bad",
                                                     "visibility": "open"}))
        self.assertTrue(config.destination_problems({"name": "ok", "repo": "o/r",
                                                     "visibility": "public",
                                                     "path_prefix": "../up"}))

    def test_hand_edited_destination_is_reported_by_the_validation(self):
        """Corrections of 2026-11-13: the export's own destination rules (plain
        branch, no .git prefix, URL that is not an option) are part of the
        configuration validation, so that doctor reports a hand edit."""
        base = {"name": "pub", "repo": "o/r", "visibility": "public", "path_prefix": "", "branch": "main"}
        self.assertEqual(config.destination_problems(base), [])
        for key, bad, needle in (("branch", "a..b", "plain branch name"),
                                 ("branch", "main.lock", "plain branch name"),
                                 ("path_prefix", "x/.git/y", ".git folder"),
                                 ("path_prefix", ".GIT", ".git folder"),
                                 ("url", "--upload-pack=touch x", "not an option"),
                                 ("url", "  ", "not an option")):
            problems = config.destination_problems(dict(base, **{key: bad}))
            self.assertTrue(any(needle in p for p in problems), (key, bad, problems))

    def test_destination_credentials_are_refused_and_never_displayed(self):
        """Review RS-02 (2026-11-13): no credentials in a destination URL; an
        existing one is masked by `config show` / `config set`."""
        base = {"name": "priv", "repo": "o/r", "visibility": "private", "path_prefix": "", "branch": "main"}
        for url in ("https://someone:FAKE-SECRET@github.com/o/r.git", "https://token@github.com/o/r.git",
                    "ssh://bob@github.com/o/r.git"):
            self.assertTrue(any("credentials" in p for p in config.destination_problems(dict(base, url=url))), url)
        for url in ("https://github.com/o/r.git", "git@github.com:o/r.git", "ssh://git@github.com/o/r.git"):
            self.assertEqual(config.destination_problems(dict(base, url=url)), [], url)
        view = config.redacted({"github": {"destinations": [dict(base, url="https://someone:FAKE-SECRET@github.com/o/r.git")]}})
        self.assertEqual(view["github"]["destinations"][0]["url"], "https://***@github.com/o/r.git")
        import subprocess
        import sys
        cfg = config.config_path(self.root)
        helpers.configure(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["github"]["destinations"] = [dict(base, url="https://someone:FAKE-SECRET@github.com/o/r.git")]
        cfg.write_text(json.dumps(data), encoding="utf-8")
        out = subprocess.run([sys.executable, "-m", "tools.pws_workspace", "--root", str(self.root), "config", "show"],
                             capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2])).stdout
        self.assertNotIn("FAKE-SECRET", out)

    def test_claude_code_settings_untouched(self):
        settings = self.root / core.LOCAL_SETTINGS_REL
        settings.parent.mkdir(parents=True)
        settings.write_text('{"permissions": {"allow": ["Bash(ls:*)"]}}', encoding="utf-8")
        before = settings.read_bytes()
        config.init_config(self.root, "fr", "Holder Test")
        config.set_value(self.root, "tv_validation_mode", "chrome-experimental")
        self.assertEqual(settings.read_bytes(), before)


    # ---- corrections of 2026-11-13 (audit A-07, A-08, A-11) ----------------------

    def test_forced_init_refused_leaves_the_existing_configuration_intact(self):
        self.assertTrue(config.init_config(self.root, "fr", "Holder Test", ["HolderAlias"])["ok"])
        before = config.config_path(self.root).read_bytes()
        r = config.init_config(self.root, "en", "Other", [""], force=True)      # invalid alias
        self.assertFalse(r["ok"])
        self.assertEqual(config.config_path(self.root).read_bytes(), before)
        with core.file_lock(str(config.config_path(self.root)) + ".lock"):
            pass
        r = config.init_config(self.root, "en", "Reset Holder", [], force=True)
        self.assertTrue(r["ok"], r)
        self.assertEqual(config.identity(self.root)["copyright_holder"], "Reset Holder")

    def test_mistyped_sections_never_break_readers_and_writers_refuse_cleanly(self):
        helpers.configure(self.root)
        path = config.config_path(self.root)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, bad in (("identity", "text"), ("github", "text"), ("maintenance", "text"), ("migrations", 5)):
            broken = dict(data, **{key: bad})
            path.write_text(json.dumps(broken), encoding="utf-8")
            cfg = config.read_config(self.root)
            self.assertTrue(cfg["problems"], key)                       # reported (doctor BLOCKING)
            self.assertIsInstance(cfg["data"]["identity"], dict)       # typed view for every reader
            self.assertIsInstance(cfg["data"]["identity"]["header_aliases"], list)
            self.assertIsInstance(cfg["data"]["github"]["destinations"], list)
            self.assertIsInstance(cfg["data"]["maintenance"]["startup_cleanup"], bool)
            self.assertIsInstance(cfg["data"]["migrations"], list)
            config.identity(self.root)                                  # never raises
            r = config.set_value(self.root, "identity.copyright_holder", "X")
            self.assertFalse(r["ok"])                                   # refused, never a crash
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[key], bad)   # nothing written

if __name__ == "__main__":
    unittest.main()
