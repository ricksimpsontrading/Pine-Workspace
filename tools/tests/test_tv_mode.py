# SPDX-License-Identifier: Apache-2.0
"""TV mode controller: pws.config.json-backed, legacy fallback, default,
atomic RMW with conflict refusal and key preservation (spec sections 19.3,
28, 61.8 — updated 2026-11-06)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import config, core, tv_mode
from tools.tests import helpers


class TestTvMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.settings = self.root / core.LOCAL_SETTINGS_REL
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.cfg = config.config_path(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_settings(self, data):
        self.settings.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def test_default_manual_without_any_file(self):
        d = tv_mode.read_mode_detail(self.root)
        self.assertEqual((d["mode"], d["source"], d["error"]), ("manual", "default", None))

    def test_round_trip_preserves_other_config_keys(self):
        config.init_config(self.root, "fr", "Holder Test")
        r1 = tv_mode.set_mode(self.root, "chrome-experimental")
        self.assertTrue(r1["ok"], r1)
        r2 = tv_mode.set_mode(self.root, "manual")
        self.assertTrue(r2["ok"], r2)
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["tv_validation_mode"], "manual")
        self.assertEqual(data["language"], "fr")
        self.assertEqual(data["identity"]["copyright_holder"], "Holder Test")

    def test_settings_local_json_never_touched_by_set_mode(self):
        self._write_settings({"permissions": {"allow": ["Bash(ls:*)"]}})
        before = self.settings.read_bytes()
        self.assertTrue(tv_mode.set_mode(self.root, "chrome-experimental")["ok"])
        self.assertEqual(self.settings.read_bytes(), before)

    def test_invalid_mode_refused(self):
        tv_mode.set_mode(self.root, "manual")
        r = tv_mode.set_mode(self.root, "automatic")
        self.assertFalse(r["ok"])
        self.assertEqual(tv_mode.read_mode(self.root), ("manual", None))

    def test_missing_config_created(self):
        r = tv_mode.set_mode(self.root, "manual")
        self.assertTrue(r["ok"])
        self.assertTrue(self.cfg.is_file())
        d = tv_mode.read_mode_detail(self.root)
        self.assertEqual((d["mode"], d["source"]), ("manual", "config"))

    def test_invalid_persisted_mode_reported(self):
        self.cfg.write_text(json.dumps({"schema_version": 1, "tv_validation_mode": "banana"}),
                            encoding="utf-8")
        mode, err = tv_mode.read_mode(self.root)
        self.assertIsNone(mode)
        self.assertIn("invalid", err)

    def test_read_mode_survives_malformed_config(self):
        """The read path diagnoses, never crashes, on a malformed config."""
        for payload in ("[]", '"manual"', "{broken"):
            self.cfg.write_text(payload, encoding="utf-8")
            mode, err = tv_mode.read_mode(self.root)
            self.assertIsNone(mode, payload)
            self.assertIsNotNone(err, payload)

    def test_legacy_settings_key_read_only_when_config_has_no_mode(self):
        self._write_settings({"env": {core.TV_MODE_ENV_KEY: "chrome-experimental"}})
        d = tv_mode.read_mode_detail(self.root)
        self.assertEqual((d["mode"], d["source"]), ("chrome-experimental", "legacy"))
        # once the configuration carries the mode, the legacy key is ignored
        tv_mode.set_mode(self.root, "manual")
        d = tv_mode.read_mode_detail(self.root)
        self.assertEqual((d["mode"], d["source"]), ("manual", "config"))

    def test_legacy_invalid_value_reported_not_used(self):
        self._write_settings({"env": {core.TV_MODE_ENV_KEY: "banana"}})
        mode, err = tv_mode.read_mode(self.root)
        self.assertIsNone(mode)
        self.assertIn("legacy", err)

    def test_file_authoritative_over_stale_env(self):
        """The process env var is never a read path."""
        tv_mode.set_mode(self.root, "chrome-experimental")
        with mock.patch.dict(os.environ, {core.TV_MODE_ENV_KEY: "manual"}):
            mode, _ = tv_mode.read_mode(self.root)
        self.assertEqual(mode, "chrome-experimental")

    def test_concurrent_modification_refused(self):
        tv_mode.set_mode(self.root, "manual")
        original = self.cfg.read_bytes()
        modified = original.replace(b'"manual"', b'"manual" ')
        real_read_bytes = Path.read_bytes
        calls = {"n": 0}

        def fake_read_bytes(path_self):
            if path_self == self.cfg:
                calls["n"] += 1
                return original if calls["n"] == 1 else modified
            return real_read_bytes(path_self)

        with mock.patch.object(Path, "read_bytes", fake_read_bytes):
            r = tv_mode.set_mode(self.root, "chrome-experimental")
        self.assertFalse(r["ok"])
        self.assertIn("concurrent", r["error"])
        self.assertEqual(json.loads(self.cfg.read_text(encoding="utf-8"))["tv_validation_mode"],
                         "manual")

    def test_unreadable_config_refused(self):
        self.cfg.write_text("{broken", encoding="utf-8")
        r = tv_mode.set_mode(self.root, "manual")
        self.assertFalse(r["ok"])
        self.assertIn("refusing", r["error"])



class TestLegacyModeKept20261113(unittest.TestCase):
    """Audit D-10: an unrelated configuration write never switches the mode in
    effect of an installation still carrying the legacy key."""

    def test_unrelated_write_keeps_the_legacy_mode_and_an_explicit_choice_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            settings = root / core.LOCAL_SETTINGS_REL
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "chrome-experimental"}}),
                                encoding="utf-8")
            cfg = config.config_path(root)
            if cfg.exists():
                data = json.loads(cfg.read_text(encoding="utf-8"))
                data.pop("tv_validation_mode", None)
                cfg.write_text(json.dumps(data), encoding="utf-8")
            before = tv_mode.read_mode_detail(root)
            self.assertEqual(before["mode"], "chrome-experimental")
            self.assertTrue(config.set_value(root, "language", "fr")["ok"])
            self.assertNotIn("tv_validation_mode", json.loads(cfg.read_text(encoding="utf-8")))
            self.assertEqual(tv_mode.read_mode_detail(root)["mode"], "chrome-experimental")
            self.assertTrue(tv_mode.set_mode(root, "manual")["ok"])   # the owner's explicit choice
            self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["tv_validation_mode"], "manual")
            self.assertEqual(tv_mode.read_mode_detail(root)["mode"], "manual")



class TestLegacyLinkNeverRead20261113(unittest.TestCase):
    """Review RS-07: a symlinked settings.local.json is never read for the
    legacy mode (as for the migrations); an explicit choice resolves it."""

    def test_linked_legacy_settings_are_reported_and_an_explicit_choice_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            outside = Path(tmp) / "outside-settings.json"
            outside.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "chrome-experimental"}}), encoding="utf-8")
            settings = root / core.LOCAL_SETTINGS_REL
            settings.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(outside), str(settings))
            cfg = config.config_path(root)
            if cfg.exists():
                data = json.loads(cfg.read_text(encoding="utf-8"))
                data.pop("tv_validation_mode", None)
                cfg.write_text(json.dumps(data), encoding="utf-8")
            d = tv_mode.read_mode_detail(root)
            self.assertIsNone(d["mode"])
            self.assertIn("symbolic link", d["error"])
            self.assertTrue(tv_mode.set_mode(root, "manual")["ok"])
            self.assertEqual(tv_mode.read_mode_detail(root), {"mode": "manual", "source": "config", "error": None})
            self.assertIn("chrome-experimental", outside.read_text(encoding="utf-8"), "never written either")


if __name__ == "__main__":
    unittest.main()
