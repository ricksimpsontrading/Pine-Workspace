# SPDX-License-Identifier: Apache-2.0
"""Physical boundary and low-level primitives (spec sections 6.1, 61.11)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core
from tools.tests import helpers


class TestBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_path_contains_space(self):
        self.assertIn(" ", str(self.root))

    def test_is_within(self):
        inside = self.root / "scripts" / "x.txt"
        self.assertTrue(core.is_within(self.root, inside))
        self.assertFalse(core.is_within(self.root, self.root.parent / "elsewhere"))

    def test_symlink_escape_detected(self):
        target = Path(self.tmp.name) / "outside dir"
        target.mkdir()
        link = self.root / "scripts" / "escape"
        os.symlink(target, link)
        self.assertFalse(core.is_within(self.root, link))

    def test_enclosing_git_root_detected(self):
        parent = Path(self.tmp.name) / "parent repo"
        parent.mkdir()
        subprocess.run(["git", "init", "-q", str(parent)], check=True)
        child = parent / "pine workspace"
        child.mkdir()
        self.assertEqual(core.find_enclosing_git_root(child), parent.resolve())

    def test_no_enclosing_git_root(self):
        # tmp dirs are not under a git repo (unless the OS tmp is, which would
        # be a real environment fact worth surfacing)
        found = core.find_enclosing_git_root(self.root)
        self.assertIsNone(found, "unexpected enclosing repo: %s" % found)

    def test_sibling_project_ignored(self):
        """An arbitrarily named sibling is neither scanned nor required."""
        sibling = Path(self.tmp.name) / "sibling project"
        (sibling / "scripts").mkdir(parents=True)
        (sibling / "scripts" / "trap.pine").write_text("x", encoding="utf-8")
        from tools.pws_workspace import scan
        result = scan.scan_workspace(self.root)
        self.assertEqual(result["unregistered_pine"], [])
        self.assertEqual(result["products"], [])


class TestPrimitives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_write_and_read_json(self):
        p = self.root / "sub dir" / "file with space.json"
        core.atomic_write_json(p, {"a": 1})
        data, err = core.read_json(p)
        self.assertIsNone(err)
        self.assertEqual(data, {"a": 1})

    def test_read_json_missing_and_invalid(self):
        _, err = core.read_json(self.root / "nope.json")
        self.assertEqual(err, "missing")
        bad = self.root / "bad.json"
        bad.write_text("{", encoding="utf-8")
        _, err = core.read_json(bad)
        self.assertIn("invalid JSON", err)

    def test_sha256_stability(self):
        p = self.root / "x.bin"
        p.write_bytes(b"abc")
        self.assertEqual(
            core.sha256_file(p),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")



class TestSymlinkedRuntime20261113(unittest.TestCase):
    """Audit F-12: a lock file, a backup manifest or the local settings that
    are symbolic links are never followed."""

    def test_a_linked_lock_file_is_refused_and_nothing_is_created_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside" / "created-by-lock.txt"
            outside.parent.mkdir()
            lock = Path(tmp) / "ws" / "x.lock"
            lock.parent.mkdir()
            os.symlink(str(outside), str(lock))
            with self.assertRaises(OSError):
                with core.file_lock(lock, timeout=0.1):
                    pass
            self.assertFalse(outside.exists())

    def test_linked_backup_manifests_and_settings_are_refused(self):
        import json
        from tools.pws_workspace import migration, upgrade
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            outside = Path(tmp) / "outside.json"
            outside.write_text(json.dumps({"files": [], "state": "applied"}), encoding="utf-8")
            for module in (upgrade, migration):
                bdir = root / module.BACKUP_REL / "20261113T000000Z"
                bdir.mkdir(parents=True)
                os.symlink(str(outside), str(bdir / "MANIFEST.json"))
                r = module.rollback(root, "20261113T000000Z")
                self.assertFalse(r["ok"])
                self.assertIn("symbolic link", r["error"])
            settings = root / core.LOCAL_SETTINGS_REL
            settings.parent.mkdir(parents=True, exist_ok=True)
            target = Path(tmp) / "outside-settings.json"
            target.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
            os.symlink(str(target), str(settings))
            ok, detail = migration._apply_step(root, {"id": "m003-remove-legacy-tv-key"}, "2026-11-13")
            self.assertFalse(ok)
            self.assertTrue(settings.is_symlink())
            self.assertIn(core.TV_MODE_ENV_KEY, target.read_text(encoding="utf-8"))
            self.assertEqual(migration._legacy_key_present(root), (False, None))


if __name__ == "__main__":
    unittest.main()
