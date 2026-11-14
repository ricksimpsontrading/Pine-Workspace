# SPDX-License-Identifier: Apache-2.0
"""Migrations: pending detection from the real state, backup before change,
idempotence, preservation of Claude Code approvals, rollback (2026-11-06);
restoration validated as a whole before any write (second verification)."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.pws_workspace import config, core, migration, scan, tv_mode
from tools.tests import helpers


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.settings = self.root / core.LOCAL_SETTINGS_REL
        self.settings.parent.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _legacy_install(self):
        self.settings.write_text(json.dumps({
            "env": {core.TV_MODE_ENV_KEY: "chrome-experimental"},
            "permissions": {"allow": ["Bash(shasum -a 256)"]}}, indent=2), encoding="utf-8")
        helpers.make_product(self.root, slug="legacy-paid", distribution="paid-closed-source",
                             header=helpers.PAID_HEADER)
        helpers.configure(self.root, language="fr", holder="Legacy Holder",
                          aliases=("LegacyHolder",))

    def test_plan_lists_real_steps(self):
        """Contract changed on 2026-11-13 (F-14, owner's decision): pws.config.json
        holds the default written by init and the legacy key another mode — a
        conflict without provenance blocks m001 (and m003 waits) until the owner
        chooses; afterwards the steps run."""
        self._legacy_install()
        plan = migration.plan(self.root)
        ids = [s["id"] for s in plan["steps"]]
        self.assertEqual(ids, ["m001-tv-mode-to-config", "m005-manifests-v3",
                               "m003-remove-legacy-tv-key"])
        blocked = {s["id"]: s["blocked"] for s in plan["steps"]}
        self.assertEqual(blocked, {"m001-tv-mode-to-config": True, "m005-manifests-v3": False,
                                   "m003-remove-legacy-tv-key": True})
        self.assertTrue(tv_mode.set_mode(self.root, "chrome-experimental")["ok"])   # the owner chooses
        plan = migration.plan(self.root)
        self.assertEqual({s["id"]: (s["blocked"], s.get("waits_for")) for s in plan["steps"]},
                         {"m001-tv-mode-to-config": (False, None), "m005-manifests-v3": (False, None),
                          "m003-remove-legacy-tv-key": (True, "m001-tv-mode-to-config")})

    def test_apply_preserves_identity_language_approvals_and_products(self):
        self._legacy_install()
        # F-14 (2026-11-13): the conflict between init's default and the legacy
        # value is resolved by the owner's explicit choice before applying
        self.assertTrue(tv_mode.set_mode(self.root, "chrome-experimental")["ok"])
        before_settings = json.loads(self.settings.read_text(encoding="utf-8"))
        report = migration.apply(self.root, today="2026-11-06")
        self.assertEqual(report["errors"], [], report)
        self.assertEqual([a["id"] for a in report["applied"]],
                         ["m001-tv-mode-to-config", "m005-manifests-v3", "m003-remove-legacy-tv-key"])
        self.assertTrue(report["ambiguities"])  # COMMERCIAL draft reported, not guessed
        # TV mode moved, approvals intact, legacy key gone
        self.assertEqual(tv_mode.read_mode_detail(self.root)["source"], "config")
        self.assertEqual(tv_mode.read_mode(self.root)[0], "chrome-experimental")
        after_settings = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(after_settings["permissions"], before_settings["permissions"])
        self.assertNotIn("env", after_settings)
        # identity and language preserved
        self.assertEqual(config.language(self.root), "fr")
        self.assertEqual(config.identity(self.root)["copyright_holder"], "Legacy Holder")
        # manifest explicit v2, product still REGISTERED, source untouched
        m = json.loads((self.root / "scripts" / "legacy-paid" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual((m["schema_version"], m["profile"]), (3, "COMMERCIAL"))
        self.assertEqual(m["publication"], {"state": None, "privacy": None, "mode": None})
        self.assertEqual(m["migration"]["from_distribution"], "paid-closed-source")
        p = scan.scan_workspace(self.root)["products"][0]
        self.assertEqual(p["product_structure_status"], "REGISTERED")
        self.assertNotIn("MANIFEST_LEGACY_SCHEMA", [f["code"] for f in p["findings"]])
        # idempotent: nothing pending anymore
        self.assertEqual(migration.pending_steps(self.root), [])
        self.assertEqual(migration.apply(self.root)["applied"], [])

    def _cfg_without_mode(self):
        cfg = config.config_path(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data.pop("tv_validation_mode", None)
        data.pop(config.MODE_CHOICE_KEY, None)
        cfg.write_text(json.dumps(data), encoding="utf-8")

    def _set_legacy(self, value):
        self.settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: value},
                                             "permissions": {"allow": ["Bash(git status)"]}}), encoding="utf-8")

    def test_f14_conflict_without_provenance_blocks_and_changes_nothing(self):
        """F-14 (owner's decision of 2026-11-13)."""
        self._legacy_install()                       # config: manual (init), legacy: chrome-experimental
        cfg_before = config.config_path(self.root).read_bytes()
        settings_before = self.settings.read_bytes()
        plan = migration.plan(self.root)
        m001 = [s for s in plan["steps"] if s["id"] == "m001-tv-mode-to-config"][0]
        self.assertTrue(m001["blocked"])
        self.assertEqual(m001["values"]["config"]["value"], "manual")
        self.assertIn("origin not established", m001["values"]["config"]["origin"])
        self.assertEqual(m001["values"]["legacy"]["value"], "chrome-experimental")
        self.assertIn("settings.local.json", m001["values"]["legacy"]["origin"])
        self.assertEqual((config.config_path(self.root).read_bytes(), self.settings.read_bytes()),
                         (cfg_before, settings_before), "consulting the plan writes nothing")
        report = migration.apply(self.root, today="2026-11-13")
        self.assertNotIn("m001-tv-mode-to-config", [a["id"] for a in report["applied"]])
        self.assertNotIn("m003-remove-legacy-tv-key", [a["id"] for a in report["applied"]])
        self.assertEqual(tv_mode.read_mode(self.root)[0], "manual", "the mode in effect is kept")
        self.assertIn(core.TV_MODE_ENV_KEY, json.loads(self.settings.read_text(encoding="utf-8"))["env"],
                      "the legacy value is kept until the conflict is resolved")

    def test_f14_an_explicit_choice_resolves_the_conflict_once(self):
        for chosen in ("manual", "chrome-experimental"):
            with self.subTest(chosen=chosen):
                self.tmp.cleanup()
                self.setUp()
                self._legacy_install()
                self.assertTrue(tv_mode.set_mode(self.root, chosen)["ok"])
                report = migration.apply(self.root, today="2026-11-13")
                applied = [a["id"] for a in report["applied"]]
                self.assertIn("m001-tv-mode-to-config", applied)
                self.assertIn("m003-remove-legacy-tv-key", applied)
                self.assertEqual(tv_mode.read_mode(self.root)[0], chosen)
                self.assertNotIn("env", json.loads(self.settings.read_text(encoding="utf-8")))
                backup = Path(report["backup"]) / core.LOCAL_SETTINGS_REL
                self.assertEqual(json.loads(backup.read_text(encoding="utf-8"))["env"][core.TV_MODE_ENV_KEY],
                                 "chrome-experimental")
                ids = [s["id"] for s in migration.plan(self.root)["steps"]]
                self.assertNotIn("m001-tv-mode-to-config", ids, "never asked again")
                self.assertNotIn("m003-remove-legacy-tv-key", ids)

    def test_f14_without_a_usable_current_value_the_legacy_one_is_taken(self):
        self._legacy_install()
        self._cfg_without_mode()
        self.assertEqual(tv_mode.read_mode_detail(self.root)["source"], "legacy")
        report = migration.apply(self.root, today="2026-11-13")
        self.assertIn("m001-tv-mode-to-config", [a["id"] for a in report["applied"]])
        self.assertEqual(tv_mode.read_mode_detail(self.root), {"mode": "chrome-experimental", "source": "config",
                                                               "error": None})

    def test_f14_agreeing_values_migrate_without_question(self):
        self._legacy_install()
        self._set_legacy("manual")
        step = [s for s in migration.plan(self.root)["steps"] if s["id"] == "m001-tv-mode-to-config"][0]
        self.assertFalse(step["blocked"])
        report = migration.apply(self.root, today="2026-11-13")
        self.assertIn("m003-remove-legacy-tv-key", [a["id"] for a in report["applied"]])
        self.assertEqual(tv_mode.read_mode(self.root)[0], "manual")

    def test_f14_nothing_runnable_creates_no_backup(self):
        self._legacy_install()
        for m in list((self.root / "scripts").glob("*/SCRIPT.json")):
            m.unlink()                                # only m001 (blocked) and m003 (waiting) remain
        report = migration.apply(self.root, today="2026-11-13")
        self.assertEqual(report["applied"], [])
        self.assertFalse((self.root / migration.BACKUP_REL).exists() and
                         any((self.root / migration.BACKUP_REL).iterdir()))

    def test_a_late_rollback_preserves_the_later_modifications(self):
        """Audit F-09 (2026-11-13): the versions a rollback replaces or removes
        are copied beside the backup first; nothing is lost."""
        self._legacy_install()
        report = migration.apply(self.root, today="2026-11-13")
        self.assertEqual(report["errors"], [], report)
        self.assertTrue(config.set_value(self.root, "language", "en")["ok"])     # later change
        later = config.config_path(self.root).read_bytes()
        rb = migration.rollback(self.root, Path(report["backup"]).name)
        self.assertTrue(rb["ok"], rb)
        preserved = Path(rb["preserved"])
        self.assertTrue(preserved.is_dir())
        self.assertEqual((preserved / config.CONFIG_REL).read_bytes(), later)
        listed = json.loads((preserved / "PRESERVED.json").read_text(encoding="utf-8"))
        self.assertIn(str(config.CONFIG_REL), [f["path"] for f in listed["files"]])
        self.assertNotIn(preserved.name, migration.list_backups(self.root)
                         if hasattr(migration, "list_backups") else [])

    def test_rollback_restores_files_byte_for_byte(self):
        self._legacy_install()
        manifest_path = self.root / "scripts" / "legacy-paid" / "SCRIPT.json"
        before_manifest = manifest_path.read_bytes()
        before_settings = self.settings.read_bytes()
        before_config = config.config_path(self.root).read_bytes()
        report = migration.apply(self.root, today="2026-11-06")
        stamp = [b for b in migration.list_backups(self.root)][-1]
        self.assertIn(stamp, report["backup"])
        r = migration.rollback(self.root, stamp)
        self.assertTrue(r["ok"], r)
        self.assertEqual(manifest_path.read_bytes(), before_manifest)
        self.assertEqual(self.settings.read_bytes(), before_settings)
        self.assertEqual(config.config_path(self.root).read_bytes(), before_config)
        self.assertEqual(len(migration.pending_steps(self.root)), 3)

    def test_blocked_step_reported_not_applied(self):
        self.settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "banana"}}), encoding="utf-8")
        helpers.configure(self.root)
        plan = migration.plan(self.root)
        blocked = [s for s in plan["steps"] if s["blocked"]]
        self.assertTrue(blocked)
        report = migration.apply(self.root)
        self.assertTrue(report["skipped"])
        self.assertIn("env", json.loads(self.settings.read_text(encoding="utf-8")))

    def test_fresh_install_only_records_version(self):
        config.config_path(self.root).write_text(json.dumps({"schema_version": 1, "language": "en"}),
                                                 encoding="utf-8")
        ids = [s["id"] for s in migration.pending_steps(self.root)]
        self.assertEqual(ids, ["m004-record-workspace-version"])
        migration.apply(self.root)
        from tools.pws_workspace import version
        self.assertEqual(config.read_config(self.root)["data"]["workspace_version"], version.WORKSPACE_VERSION)

    def test_rollback_refuses_unsafe_manifest(self):
        bdir = self.root / migration.BACKUP_REL / "evil"
        bdir.mkdir(parents=True)
        core.atomic_write_json(bdir / "MANIFEST.json", {"files": [{"path": "../../x", "existed": False}]})
        self.assertFalse(migration.rollback(self.root, "evil")["ok"])
        self.assertFalse(migration.rollback(self.root, "../x")["ok"])
        core.atomic_write_json(bdir / "MANIFEST.json",
                               {"files": [{"path": str(self.root / "pws.config.json"), "existed": False}]})
        self.assertFalse(migration.rollback(self.root, "evil")["ok"])

    def test_rollback_refuses_whole_restoration_before_any_write(self):
        """Several files, the invalid entry AFTER valid ones (one of which would
        normally entail a removal): refused before any mutation; then the same
        backup, once valid, is restored and verified."""
        helpers.configure(self.root)
        self.settings.write_text('{"permissions": {"allow": ["Bash(ls:*)"]}}\n', encoding="utf-8")
        added = self.root / "scripts" / "added-later" / "SCRIPT.json"
        added.parent.mkdir(parents=True)
        added.write_text('{"added": true}\n', encoding="utf-8")
        cfg = config.config_path(self.root)
        bdir = self.root / migration.BACKUP_REL / "20261106T000000Z-synth"
        bdir.mkdir(parents=True)
        (bdir / "pws.config.json").write_text('{"schema_version": 1, "language": "en"}\n', encoding="utf-8")
        copy_settings = bdir / core.LOCAL_SETTINGS_REL
        copy_settings.parent.mkdir(parents=True)
        copy_settings.write_text('{"permissions": {}}\n', encoding="utf-8")
        entries = [
            {"path": "pws.config.json", "existed": True, "sha256": core.sha256_file(bdir / "pws.config.json")},
            {"path": "scripts/added-later/SCRIPT.json", "existed": False},              # would be removed
            {"path": str(core.LOCAL_SETTINGS_REL), "existed": True, "sha256": "0" * 64},   # invalid, last
        ]

        def write_manifest(files):
            core.atomic_write_json(bdir / "MANIFEST.json", {"stamp": bdir.name, "state": "applied", "files": files})

        before = (cfg.read_bytes(), added.read_bytes(), self.settings.read_bytes())

        def refused(rb, needle):
            self.assertFalse(rb["ok"])
            self.assertEqual(rb["stage"], "refused")
            self.assertEqual((rb["restored"], rb["removed"]), ([], []))
            self.assertTrue(any(needle in p for p in rb["problems"]), rb)
            self.assertIn("nothing changed", rb["error"])
            self.assertEqual((cfg.read_bytes(), added.read_bytes(), self.settings.read_bytes()), before)
            self.assertTrue(added.is_file())

        write_manifest(entries)                                   # (a) hash mismatch on the last entry
        refused(migration.rollback(self.root, bdir.name), "recorded hash")
        entries[2]["sha256"] = core.sha256_file(copy_settings)
        copy_settings.unlink()                                    # (b) copy missing
        write_manifest(entries)
        refused(migration.rollback(self.root, bdir.name), "backup copy missing")
        copy_settings.write_text('{"permissions": {}}\n', encoding="utf-8")
        write_manifest(entries + [{"path": "../escape", "existed": False}])   # (c) escaping entry
        refused(migration.rollback(self.root, bdir.name), "unsafe path")
        write_manifest(entries)                                   # (d) every entry valid
        rb = migration.rollback(self.root, bdir.name)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(rb["stage"], "verified")
        self.assertEqual(rb["restored"], ["pws.config.json", str(core.LOCAL_SETTINGS_REL)])
        self.assertEqual(rb["removed"], ["scripts/added-later/SCRIPT.json"])
        self.assertEqual(cfg.read_text(encoding="utf-8"), '{"schema_version": 1, "language": "en"}\n')
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"permissions": {}}\n')
        self.assertFalse(added.exists())

    def test_rollback_refuses_symlinked_destination(self):
        helpers.configure(self.root)
        cfg = config.config_path(self.root)
        outside = Path(self.tmp.name) / "outside config.json"
        shutil.move(str(cfg), str(outside))
        os.symlink(outside, cfg)
        before = outside.read_bytes()
        bdir = self.root / migration.BACKUP_REL / "20261106T000000Z-link"
        bdir.mkdir(parents=True)
        (bdir / "pws.config.json").write_text("{}\n", encoding="utf-8")
        core.atomic_write_json(bdir / "MANIFEST.json", {"files": [
            {"path": "pws.config.json", "existed": True, "sha256": core.sha256_file(bdir / "pws.config.json")}]})
        rb = migration.rollback(self.root, bdir.name)
        self.assertFalse(rb["ok"])
        self.assertEqual(rb["stage"], "refused")
        self.assertEqual(outside.read_bytes(), before)
        self.assertTrue(cfg.is_symlink())


    def test_schema2_manifest_migrates_to_schema3_idempotently(self):
        helpers.configure(self.root)
        m = helpers.v2_manifest_legacy("v2-prod", "My Indicator.pine", publication="tradingview-invite-only")
        helpers.make_product_v3(self.root, slug="v2-prod", profile="COMMERCIAL", manifest=m)
        ids = [s["id"] for s in migration.pending_steps(self.root)]
        self.assertIn("m005-manifests-v3", ids)
        report = migration.apply(self.root, today="2026-11-06")
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("state unknown" in a for a in report["ambiguities"]))
        new = json.loads((self.root / "scripts" / "v2-prod" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(new["schema_version"], 3)
        self.assertEqual(new["publication"], {"state": None, "privacy": None, "mode": "invite-only"})
        self.assertEqual(new["license"]["access"], "paid")
        self.assertNotIn("m005-manifests-v3", [s["id"] for s in migration.pending_steps(self.root)])

    def test_m006_rectifies_already_migrated_manifest_traceably_and_idempotently(self):
        helpers.configure(self.root)
        # manifest as written by the 2026-11-06 code: privacy deduced from a v1→v2→v3 chain
        m = helpers.v3_manifest("cma-like", "My Indicator.pine", profile="COMMERCIAL",
                                publication_overrides={"state": None, "privacy": "public", "mode": "invite-only"},
                                migration={"from_schema": 2, "from_publication": "tradingview-invite-only",
                                           "on": "2026-11-06",
                                           "previous": {"from_schema": 1, "from_distribution": "paid-closed-source"}})
        m["license"]["created_year"] = None
        helpers.make_product_v3(self.root, slug="cma-like", profile="COMMERCIAL", manifest=m)
        ids = [s["id"] for s in migration.pending_steps(self.root)]
        self.assertIn("m006-publication-derivations", ids)
        report = migration.apply(self.root, today="2026-11-06")
        self.assertEqual(report["errors"], [], report)
        new = json.loads((self.root / "scripts" / "cma-like" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(new["publication"], {"state": None, "privacy": None, "mode": None})
        self.assertIsNone(new["license"]["created_year"])  # never filled by a migration
        self.assertEqual(len(new["migration"]["rectifications"]), 2)
        self.assertNotIn("m006-publication-derivations", [s["id"] for s in migration.pending_steps(self.root)])
        # a holder-confirmed value survives
        from tools.pws_workspace import licensing
        c = licensing.confirm_publication(self.root, "cma-like", privacy="public", mode="invite-only")
        self.assertTrue(c["ok"], c)
        self.assertEqual(migration.pending_steps(self.root), [])
        cur = json.loads((self.root / "scripts" / "cma-like" / "SCRIPT.json").read_text(encoding="utf-8"))
        self.assertEqual(cur["publication"]["privacy"], "public")
        self.assertIn("publication.privacy", cur["migration"]["holder_confirmed"])

    def test_backups_unique_within_same_second_and_rollback_verified(self):
        helpers.configure(self.root)
        original = migration._stamp
        migration._stamp = lambda: "20261106T000000Z"
        try:
            cfg = config.config_path(self.root)
            cfg.write_text(json.dumps(dict(config.read_config(self.root)["data"], workspace_version="0.0.1")), encoding="utf-8")
            r1 = migration.apply(self.root)
            cfg.write_text(json.dumps(dict(config.read_config(self.root)["data"], workspace_version="0.0.2")), encoding="utf-8")
            r2 = migration.apply(self.root)
        finally:
            migration._stamp = original
        self.assertTrue(r1["applied"] and r2["applied"])
        self.assertNotEqual(r1["backup"], r2["backup"])
        self.assertEqual(len(migration.list_backups(self.root)), 2)
        first = json.loads((Path(r1["backup"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(first["state"], "applied")
        # audit F-10 (2026-11-13): the older backup is refused while the newer one is still applied
        refused = migration.rollback(self.root, Path(r1["backup"]).name)
        self.assertFalse(refused["ok"])
        self.assertIn("newer migration backup", refused["error"])
        rb = migration.rollback(self.root, Path(r2["backup"]).name)     # newest first
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(config.read_config(self.root)["data"]["workspace_version"], "0.0.2")
        rb = migration.rollback(self.root, Path(r1["backup"]).name)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(config.read_config(self.root)["data"]["workspace_version"], "0.0.1")
        # the journal is part of the backup (audit F-08): no entry survives the rollbacks
        self.assertEqual([m for m in config.read_config(self.root)["data"].get("migrations") or []], [])
        # tampered backup copy → rollback refused BEFORE any write: installed file intact
        bdir = Path(r2["backup"])
        (bdir / "pws.config.json").write_text("{}", encoding="utf-8")
        installed = config.config_path(self.root).read_bytes()
        rb2 = migration.rollback(self.root, bdir.name)
        self.assertFalse(rb2["ok"])
        self.assertEqual(rb2["stage"], "refused")
        self.assertEqual(config.config_path(self.root).read_bytes(), installed)


    # ---- corrections of 2026-11-13 (audit F-06, F-07, F-08, F-13) ----------------

    def test_unconvertible_manifest_blocks_m005_at_plan_time_and_nothing_is_written(self):
        helpers.configure(self.root)
        helpers.make_product(self.root, slug="aa-first")
        helpers.make_product(self.root, slug="mm-bad", distribution="no-such-distribution")
        before = {p.name: p.joinpath("SCRIPT.json").read_bytes() for p in (self.root / "scripts").iterdir()}
        step = [s for s in migration.plan(self.root)["steps"] if s["id"] == "m005-manifests-v3"][0]
        self.assertTrue(step["blocked"])
        self.assertIn("scripts/mm-bad/SCRIPT.json", step["detail"])
        r = migration.apply(self.root)
        self.assertNotIn("m005-manifests-v3", [a["id"] for a in r["applied"]])
        self.assertIn("m005-manifests-v3", [s["id"] for s in r["skipped"]])
        self.assertIn("m005-manifests-v3", r["remaining"])
        after = {p.name: p.joinpath("SCRIPT.json").read_bytes() for p in (self.root / "scripts").iterdir()}
        self.assertEqual(after, before)                                   # not even the convertible one

    def test_unreadable_configuration_is_an_error_never_an_empty_success(self):
        config.config_path(self.root).write_text("{not json", encoding="utf-8")
        self.assertIsNotNone(migration.plan(self.root)["config_error"])
        r = migration.apply(self.root)
        self.assertTrue(r["errors"])
        self.assertIn("unreadable", r["errors"][0]["error"])
        self.assertIsNone(r["backup"])

    def test_everything_blocked_creates_no_backup(self):
        self.settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "weird"}}), encoding="utf-8")
        helpers.configure(self.root)
        r = migration.apply(self.root)
        self.assertEqual(r["applied"], [])
        self.assertIsNone(r["backup"])
        self.assertEqual(migration.list_backups(self.root), [])
        self.assertTrue(r["skipped"])

    def test_dependent_step_is_applied_in_the_same_run_and_the_journal_is_in_the_backup(self):
        self.settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "chrome-experimental"}}), encoding="utf-8")
        helpers.configure(self.root)
        cfg = config.config_path(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data.pop("tv_validation_mode", None)
        cfg.write_text(json.dumps(data), encoding="utf-8")
        m003 = [s for s in migration.plan(self.root)["steps"] if s["id"] == "m003-remove-legacy-tv-key"][0]
        self.assertTrue(m003["blocked"])
        self.assertEqual(m003["waits_for"], "m001-tv-mode-to-config")
        r = migration.apply(self.root)
        ids = [a["id"] for a in r["applied"]]
        self.assertEqual(r["errors"], [])
        self.assertIn("m001-tv-mode-to-config", ids)
        self.assertIn("m003-remove-legacy-tv-key", ids)
        self.assertEqual(r["remaining"], [])
        manifest = json.loads((Path(r["backup"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertIn("pws.config.json", [f["path"] for f in manifest["files"]])
        self.assertEqual(manifest["state"], "applied")
        rb = migration.rollback(self.root, Path(r["backup"]).name)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8")).get("migrations") or [], [])

if __name__ == "__main__":
    unittest.main()
