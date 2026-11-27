# SPDX-License-Identifier: Apache-2.0
"""Core upgrade of an installed workspace (point 5, 2026-11-06) and the
corrections after independent verification: physical confinement of every
path (symlinked folders/files, backup location), unique exclusively created
backups, concurrency, verified restore, rollback ordering with data
migrations even within the same second. Integration test on temporary
folders only (paths with spaces, HOME redirected); never the upstream
workspace."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tools.pws_workspace import config, core, distribution, migration, scan, upgrade
from tools.tests import helpers

ROOT = core.workspace_root()


def _build_packages(base):
    pkg1, pkg2 = base / "pkg v1", base / "pkg v2"
    r = distribution.build(ROOT, pkg1)
    assert r["ok"], r
    shutil.copytree(str(pkg1), str(pkg2))
    skill = pkg2 / ".claude" / "skills" / "pine-docs" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nNouvelle étape.\n", encoding="utf-8")
    (pkg2 / "docs" / "architecture" / "NEW_DOC.md").write_text("# New\n", encoding="utf-8")
    (pkg2 / ".claude" / "rules" / "research.md").unlink()
    (pkg2 / ".claude" / "rules" / "release.md").unlink()
    (pkg2 / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    distribution.write_marker(pkg2, "9.9.9")
    return pkg1, pkg2


def _install(pkg, target, home):
    env = dict(os.environ, HOME=str(home), PWS_INSTALL_SKIP_COMPONENTS="1")
    proc = subprocess.run([sys.executable, str(pkg / "install.py"), "--target", str(target),
                           "--language", "fr", "--copyright-holder", "Holder Test", "--yes"],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (target / upgrade.MARKER).is_file()


class TestUpgrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.pkg1, cls.pkg2 = _build_packages(Path(cls.shared.name))

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.install = base / "My Pine Workspace"
        self.home = base / "fake home"
        self.home.mkdir()
        _install(self.pkg1, self.install, self.home)
        helpers.make_product_v3(self.install, slug="user-prod", profile="FREE")
        (self.install / "docs" / "maintenance").mkdir(parents=True, exist_ok=True)
        (self.install / "docs" / "maintenance" / "note.md").write_text("preuve\n", encoding="utf-8")
        (self.install / ".claude" / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}}), encoding="utf-8")
        self.rule = self.install / ".claude" / "rules" / "research.md"
        self.rule.write_text(self.rule.read_text(encoding="utf-8") + "\n- note locale\n", encoding="utf-8")
        prov = self.install / "tools" / "pine_exec" / "PROVENANCE.json"
        data = json.loads(prov.read_text(encoding="utf-8"))
        data["local_note"] = "verified here"
        prov.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.skill = self.install / ".claude" / "skills" / "pine-docs" / "SKILL.md"

    def tearDown(self):
        self.tmp.cleanup()

    def _actions(self, p):
        return {e["path"]: e["action"] for e in p["entries"]}

    def _tree_hashes(self):
        return {str(p.relative_to(self.install)): core.sha256_file(p)
                for p in core.iter_paths_within(self.install) if ".claude/runtime" not in str(p)}

    # ---- plan and nominal apply / rollback -------------------------------

    def test_plan_classifies_every_case(self):
        p = upgrade.plan(self.install, self.pkg2)
        self.assertTrue(p["ok"], p)
        self.assertEqual(p["to_version"], "9.9.9")
        a = self._actions(p)
        self.assertEqual(a[".claude/skills/pine-docs/SKILL.md"], "update")
        self.assertEqual(a["docs/architecture/NEW_DOC.md"], "add")
        self.assertEqual(a[".claude/rules/release.md"], "remove")
        self.assertEqual(a[".claude/rules/research.md"], "conflict-rm")
        self.assertEqual(a["tools/pine_exec/PROVENANCE.json"], "keep-local")
        self.assertEqual(a["VERSION"], "update")
        self.assertNotIn("scripts/user-prod/SCRIPT.json", a)
        self.assertEqual(p["conflicts"], [".claude/rules/research.md"])

    def test_apply_refuses_conflicts_then_upgrades_preserving_user_data(self):
        r = upgrade.apply(self.install, self.pkg2)
        self.assertFalse(r["ok"])
        self.assertIn("research.md", r["error"])
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertTrue(r["ok"], r)
        self.assertTrue((self.install / "docs" / "architecture" / "NEW_DOC.md").is_file())
        self.assertFalse((self.install / ".claude" / "rules" / "release.md").exists())
        self.assertIn("Nouvelle étape", self.skill.read_text(encoding="utf-8"))
        prov = json.loads((self.install / "tools" / "pine_exec" / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["local_note"], "verified here")
        self.assertTrue((self.install / "tools" / "pine_exec" / "PROVENANCE.json.pws-new").is_file())
        self.assertEqual(config.language(self.install), "fr")
        self.assertTrue((self.install / "docs" / "maintenance" / "note.md").is_file())
        self.assertEqual(scan.scan_workspace(self.install)["products"][0]["product_structure_status"], "REGISTERED")
        manifest = json.loads((Path(r["backup"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "applied")
        self.assertIn("migrations_at_apply", manifest)
        stamp = Path(r["backup"]).name
        rb = upgrade.rollback(self.install, stamp)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual((rb["problems"], rb["stage"]), ([], "verified"))
        self.assertIn(".claude/skills/pine-docs/SKILL.md", rb["restored"])
        self.assertIn("docs/architecture/NEW_DOC.md", rb["removed"])
        self.assertTrue(self.rule.is_file())
        self.assertFalse((self.install / "docs" / "architecture" / "NEW_DOC.md").exists())
        self.assertNotIn("Nouvelle étape", self.skill.read_text(encoding="utf-8"))

    # ---- point 2: physical confinement -----------------------------------

    def test_symlinked_directory_escaping_installation_is_refused(self):
        outside = Path(self.tmp.name) / "outside skills"
        shutil.move(str(self.install / ".claude" / "skills"), str(outside))
        os.symlink(outside, self.install / ".claude" / "skills")
        target = outside / "pine-docs" / "SKILL.md"
        before = core.sha256_file(target)
        p = upgrade.plan(self.install, self.pkg2)
        self.assertFalse(p["ok"])
        self.assertIn(".claude/skills/pine-docs/SKILL.md", p["refused"])
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertFalse(r["ok"])
        self.assertEqual(core.sha256_file(target), before, "outside file must stay untouched")
        self.assertEqual(upgrade.list_backups(self.install), [])

    def test_symlinked_file_escaping_installation_is_refused(self):
        outside = Path(self.tmp.name) / "outside file.md"
        shutil.move(str(self.skill), str(outside))
        os.symlink(outside, self.skill)
        before = core.sha256_file(outside)
        p = upgrade.plan(self.install, self.pkg2)
        self.assertFalse(p["ok"])
        self.assertIn(".claude/skills/pine-docs/SKILL.md", p["refused"])
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertFalse(r["ok"])
        self.assertEqual(core.sha256_file(outside), before)

    def test_symlinked_package_file_is_refused(self):
        pkg = Path(self.tmp.name) / "pkg symlinked"
        shutil.copytree(str(self.pkg2), str(pkg))
        outside = Path(self.tmp.name) / "evil.md"
        outside.write_text("evil\n", encoding="utf-8")
        f = pkg / "docs" / "architecture" / "NEW_DOC.md"
        f.unlink()
        os.symlink(outside, f)
        p = upgrade.plan(self.install, pkg)
        self.assertFalse(p["ok"])
        self.assertIn("docs/architecture/NEW_DOC.md", p["refused"])

    def test_dangerous_backup_location_refused_before_mutation(self):
        outside = Path(self.tmp.name) / "outside runtime"
        outside.mkdir()
        runtime = self.install / ".claude" / "runtime"
        if runtime.exists():
            shutil.rmtree(str(runtime))
        os.symlink(outside, runtime)
        before = self._tree_hashes()
        p = upgrade.plan(self.install, self.pkg2)
        self.assertFalse(p["ok"])
        self.assertIn("backup location", p["error"])
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertFalse(r["ok"])
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(before, self._tree_hashes())

    def test_invalid_manifest_entry_refuses_whole_plan(self):
        pkg = Path(self.tmp.name) / "pkg bad manifest"
        shutil.copytree(str(self.pkg2), str(pkg))
        marker = json.loads((pkg / upgrade.MARKER).read_text(encoding="utf-8"))
        marker["files"]["../escape.md"] = "0" * 64
        (pkg / upgrade.MARKER).write_text(json.dumps(marker), encoding="utf-8")
        p = upgrade.plan(self.install, pkg)
        self.assertFalse(p["ok"])
        self.assertIn("invalid entries", p["error"])
        self.assertEqual(p["entries"], [])

    # ---- point 3: unique backups, concurrency, verified restore ----------

    def test_same_second_operations_get_distinct_backups_and_rollback_restores_initial(self):
        initial = core.sha256_file(self.skill)
        pkg3 = Path(self.tmp.name) / "pkg v3"
        shutil.copytree(str(self.pkg2), str(pkg3))
        s3 = pkg3 / ".claude" / "skills" / "pine-docs" / "SKILL.md"
        s3.write_text(s3.read_text(encoding="utf-8") + "\nEncore.\n", encoding="utf-8")
        (pkg3 / "VERSION").write_text("9.9.10\n", encoding="utf-8")
        distribution.write_marker(pkg3, "9.9.10")
        original = upgrade._stamp
        upgrade._stamp = lambda: "20261106T000000Z"
        try:
            r1 = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
            r2 = upgrade.apply(self.install, pkg3, overwrite_local=True)
        finally:
            upgrade._stamp = original
        self.assertTrue(r1["ok"] and r2["ok"], (r1, r2))
        self.assertNotEqual(r1["backup"], r2["backup"])
        m1 = json.loads((Path(r1["backup"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual([e["sha256"] for e in m1["files"] if e["path"] == ".claude/skills/pine-docs/SKILL.md"], [initial])
        rb2 = upgrade.rollback(self.install, Path(r2["backup"]).name)
        self.assertTrue(rb2["ok"], rb2)
        rb1 = upgrade.rollback(self.install, Path(r1["backup"]).name)
        self.assertTrue(rb1["ok"], rb1)
        self.assertEqual(core.sha256_file(self.skill), initial)

    def test_explicit_backup_name_collision_never_reuses_a_folder(self):
        broot = self.install / upgrade.BACKUP_REL
        broot.mkdir(parents=True, exist_ok=True)
        original = upgrade._stamp
        upgrade._stamp = lambda: "20261106T000000Z"
        try:
            existing = broot / "20261106T000000Z-aaaaaaaa"
            existing.mkdir()
            (existing / "MANIFEST.json").write_text(json.dumps({"files": [], "state": "applied"}), encoding="utf-8")
            r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        finally:
            upgrade._stamp = original
        self.assertTrue(r["ok"], r)
        self.assertNotEqual(Path(r["backup"]), existing)
        self.assertEqual(json.loads((existing / "MANIFEST.json").read_text(encoding="utf-8"))["files"], [])

    def test_concurrent_mutation_refused(self):
        lock_path = self.install / upgrade.MUTATION_LOCK_REL
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        held = threading.Event()
        release = threading.Event()

        def holder():
            with core.file_lock(lock_path, timeout=5):
                held.set()
                release.wait(5)
        t = threading.Thread(target=holder)
        t.start()
        held.wait(5)
        try:
            r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
            self.assertFalse(r["ok"])
            self.assertIn("in progress", r["error"])
            self.assertNotIn("Nouvelle étape", self.skill.read_text(encoding="utf-8"))
            m = migration.apply(self.install)
            self.assertTrue(m["errors"] and "in progress" in m["errors"][0]["error"])
        finally:
            release.set()
            t.join(5)

    def test_failure_mid_apply_restores_previous_state(self):
        before = self._tree_hashes()

        def failing_copy(src, dst):
            if Path(src).name == "NEW_DOC.md":
                raise OSError("disk full (simulated)")
            shutil.copy2(str(src), str(dst))

        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True, copy=failing_copy)
        self.assertFalse(r["ok"])
        self.assertIn("restored", r["error"])
        self.assertEqual(r["restore"]["stage"], "verified")
        self.assertEqual(before, self._tree_hashes())
        manifest = json.loads((Path(r["backup"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "failed-restored")

    # ---- restoration order (second verification): the whole restoration is
    # validated before any write; one invalid entry refuses it, nothing changes.
    # `_tree_hashes()` compares contents AND presence / absence of every file.

    def _upgraded_with_backup(self):
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertTrue(r["ok"], r)
        bdir = Path(r["backup"])
        manifest = json.loads((bdir / "MANIFEST.json").read_text(encoding="utf-8"))
        order = [(e["path"], e["existed"]) for e in manifest["files"]]
        # the backup lists restorations AND removals (added file, .pws-new copy)
        # before its last entry, the core manifest
        self.assertEqual(order[-1], (upgrade.MARKER, True))
        self.assertIn(("docs/architecture/NEW_DOC.md", False), order[:-1])
        self.assertIn((".claude/skills/pine-docs/SKILL.md", True), order[:-1])
        return bdir, manifest

    def _assert_refused_without_writes(self, rb, snapshot, needle):
        self.assertFalse(rb["ok"])
        self.assertEqual(rb["stage"], "refused")
        self.assertEqual((rb["restored"], rb["removed"]), ([], []))
        self.assertTrue(any(needle in p for p in rb["problems"]), rb)
        self.assertIn("nothing changed", rb["error"])
        self.assertEqual(self._tree_hashes(), snapshot)

    def test_rollback_with_tampered_copy_refuses_before_any_write(self):
        bdir, manifest = self._upgraded_with_backup()
        # the invalid entry is the LAST one: every valid entry precedes it
        (bdir / upgrade.MARKER).write_text("corrupted backup copy\n", encoding="utf-8")
        upgraded = self._tree_hashes()
        rb = upgrade.rollback(self.install, bdir.name)
        self._assert_refused_without_writes(rb, upgraded, "recorded hash")
        self.assertTrue((self.install / "docs" / "architecture" / "NEW_DOC.md").is_file())
        self.assertTrue((self.install / "tools" / "pine_exec" / "PROVENANCE.json.pws-new").is_file())
        self.assertFalse((self.install / ".claude" / "rules" / "release.md").exists())
        self.assertIn("Nouvelle étape", self.skill.read_text(encoding="utf-8"))
        self.assertEqual((self.install / "VERSION").read_text(encoding="utf-8"), "9.9.9\n")

    def test_rollback_with_missing_copy_refuses_before_any_write(self):
        bdir, manifest = self._upgraded_with_backup()
        # the retired rule was backed up near the end of the list (its restoration
        # would re-create it): remove that copy
        self.assertIn((".claude/rules/release.md", True), [(e["path"], e["existed"]) for e in manifest["files"]][2:])
        (bdir / ".claude" / "rules" / "release.md").unlink()
        upgraded = self._tree_hashes()
        rb = upgrade.rollback(self.install, bdir.name)
        self._assert_refused_without_writes(rb, upgraded, "backup copy missing")
        self.assertFalse((self.install / ".claude" / "rules" / "release.md").exists())
        self.assertTrue((self.install / "docs" / "architecture" / "NEW_DOC.md").is_file())

    def test_rollback_with_escaping_entry_or_symlinked_destination_refuses(self):
        bdir, manifest = self._upgraded_with_backup()
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        upgraded = self._tree_hashes()
        # (a) an entry escaping the installation, appended after the valid ones
        mpath = bdir / "MANIFEST.json"
        original = mpath.read_text(encoding="utf-8")
        manifest["files"].append({"path": "../outside.md", "existed": False})
        mpath.write_text(json.dumps(manifest), encoding="utf-8")
        rb = upgrade.rollback(self.install, bdir.name)
        self._assert_refused_without_writes(rb, upgraded, "unsafe path")
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
        mpath.write_text(original, encoding="utf-8")
        # (b) an installed destination replaced by a symlink to the outside
        version = self.install / "VERSION"
        version.unlink()
        os.symlink(outside, version)
        rb = upgrade.rollback(self.install, bdir.name)
        self.assertFalse(rb["ok"])
        self.assertEqual(rb["stage"], "refused")
        self.assertTrue(any("VERSION" in p and "unsafe path" in p for p in rb["problems"]), rb)
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
        self.assertTrue(version.is_symlink())
        self.assertEqual(self._tree_hashes(), {k: v for k, v in upgraded.items() if k != "VERSION"})

    def test_failure_mid_apply_with_unusable_backup_is_reported_without_further_writes(self):
        broot = self.install / upgrade.BACKUP_REL

        def failing_copy(src, dst):
            if Path(src).name == "NEW_DOC.md":
                # the backup becomes unusable right before the failure (simulated damage)
                for b in broot.iterdir():
                    (b / "VERSION").write_text("damaged copy\n", encoding="utf-8")
                raise OSError("disk full (simulated)")
            shutil.copy2(str(src), str(dst))

        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True, copy=failing_copy)
        self.assertFalse(r["ok"])
        self.assertEqual(r["restore"]["stage"], "refused")
        self.assertIn("REFUSED before any write", r["error"])
        bdir = Path(r["backup"])
        manifest = json.loads((bdir / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["state"], manifest["restore_stage"]), ("failed-restore-incomplete", "refused"))
        # honestly left as it was at the failure: files already applied stay, nothing else written
        self.assertEqual((self.install / "VERSION").read_text(encoding="utf-8"), "9.9.9\n")
        self.assertIn("Nouvelle étape", self.skill.read_text(encoding="utf-8"))
        self.assertFalse((self.install / "docs" / "architecture" / "NEW_DOC.md").exists())
        self.assertTrue((self.install / ".claude" / "rules" / "release.md").is_file())   # not reached yet
        at_failure = self._tree_hashes()
        # the recovery elements stay; a later explicit rollback refuses for the same
        # reason, still without writing
        rb = upgrade.rollback(self.install, bdir.name)
        self._assert_refused_without_writes(rb, at_failure, "recorded hash")

    def test_rollback_order_code_vs_data_within_the_same_second(self):
        original_up, original_mig = upgrade._stamp, migration._stamp
        upgrade._stamp = migration._stamp = lambda: "20261106T000000Z"
        try:
            r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
            self.assertTrue(r["ok"], r)
            # a data migration recorded right after (same second): m004 records the version
            config.config_path(self.install).write_text(
                json.dumps(dict(config.read_config(self.install)["data"], workspace_version="0.0.1")), encoding="utf-8")
            mig = migration.apply(self.install)
            self.assertTrue(mig["applied"], mig)
            rb = upgrade.rollback(self.install, Path(r["backup"]).name)
            self.assertFalse(rb["ok"])
            self.assertIn("migrate --rollback", rb["error"])
            self.assertTrue(migration.rollback(self.install, Path(mig["backup"]).name)["ok"])
            rb = upgrade.rollback(self.install, Path(r["backup"]).name)
            self.assertTrue(rb["ok"], rb)
        finally:
            upgrade._stamp, migration._stamp = original_up, original_mig

    def test_backup_without_migration_record_never_disables_the_check(self):
        """Audit F-05 (2026-11-13): a missing `migrations_at_apply` is not
        read as "no migration since"."""
        r = upgrade.apply(self.install, self.pkg2, overwrite_local=True)
        self.assertTrue(r["ok"], r)
        config.config_path(self.install).write_text(
            json.dumps(dict(config.read_config(self.install)["data"], workspace_version="0.0.1")), encoding="utf-8")
        self.assertTrue(migration.apply(self.install)["applied"])
        mpath = Path(r["backup"]) / "MANIFEST.json"
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        del manifest["migrations_at_apply"]
        mpath.write_text(json.dumps(manifest), encoding="utf-8")
        before = self._tree_hashes()
        rb = upgrade.rollback(self.install, Path(r["backup"]).name)
        self.assertFalse(rb["ok"])
        self.assertIn("cannot be excluded", rb["error"])
        self.assertEqual(self._tree_hashes(), before)

    # ---- point 7: explicit fixture without a core manifest ---------------

    def test_installation_without_manifest_and_bad_package_refused(self):
        no_manifest = Path(self.tmp.name) / "installation without manifest"
        shutil.copytree(str(self.install), str(no_manifest), symlinks=True)
        (no_manifest / upgrade.MARKER).unlink()
        p = upgrade.plan(no_manifest, self.pkg2)
        self.assertFalse(p["ok"])
        self.assertIn("no valid core manifest", p["error"])
        empty = Path(self.tmp.name) / "not a package"
        empty.mkdir()
        self.assertFalse(upgrade.plan(self.install, empty)["ok"])
        inside = self.install / "nested"
        inside.mkdir()
        self.assertFalse(upgrade.plan(self.install, inside)["ok"])


if __name__ == "__main__":
    unittest.main()
