# SPDX-License-Identifier: Apache-2.0
"""Installer (install.py): a REAL new installation of a package built from
this core, into a folder whose path contains spaces, with a fictitious
identity and the installer's record file isolated in a temporary HOME.
Non-regression (2026-11-07): every file of the core manifest, install.py
included, is installed with the hash recorded by the package; a distribution
can be rebuilt from the installation; `upgrade --plan` against the very same
package announces nothing to add, update or remove."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core, distribution, upgrade

ROOT = core.workspace_root()
# built at run time: this shipped file must not carry the fictitious identity literally
# (the personal-data scan of a distribution built FROM the test installation looks for it)
HOLDER = " ".join(("Example", "Holder", "Test"))


def tree(base):
    return {p.relative_to(base).as_posix(): core.sha256_file(p) for p in Path(base).rglob("*")
            if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}


class TestInstaller(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        base = Path(cls.shared.name)
        cls.package = base / "downloaded package"
        r = distribution.build(ROOT, cls.package)
        assert r["ok"], r
        cls.home = base / "isolated home"
        cls.home.mkdir()
        cls.target = base / "My Pine Workspace"
        cls.env = dict(os.environ, HOME=str(cls.home), PYTHONDONTWRITEBYTECODE="1", PWS_INSTALL_SKIP_COMPONENTS="1")
        cls.first = cls._install(cls.target, "en")

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    @classmethod
    def _install(cls, target, language):
        return subprocess.run([sys.executable, "install.py", "--target", str(target), "--language", language,
                               "--copyright-holder", HOLDER, "--yes"], cwd=str(cls.package),
                              env=cls.env, capture_output=True, text=True, timeout=300)

    def test_installation_matches_the_core_manifest_including_the_installer(self):
        self.assertEqual(self.first.returncode, 0, self.first.stdout + self.first.stderr)
        marker = json.loads((self.package / distribution.MARKER).read_text(encoding="utf-8"))
        self.assertIn("install.py", marker["files"])
        installed = self.target / "install.py"
        self.assertTrue(installed.is_file(), "install.py must be installed like every core file")
        self.assertEqual(core.sha256_file(installed), core.sha256_file(self.package / "install.py"))
        mismatched = [rel for rel, h in marker["files"].items()
                      if not (self.target / rel).is_file() or core.sha256_file(self.target / rel) != h]
        self.assertEqual(mismatched, [])
        # the installed core manifest is the package's one (used later by `upgrade`)
        self.assertEqual(core.sha256_file(self.target / distribution.MARKER),
                         core.sha256_file(self.package / distribution.MARKER))
        # first configuration: fictitious identity, chosen language, defaults
        cfg = json.loads((self.target / "pws.config.json").read_text(encoding="utf-8"))
        self.assertEqual((cfg["language"], cfg["identity"]["copyright_holder"], cfg["tv_validation_mode"]),
                         ("en", HOLDER, "manual"))
        # the record file lands in the isolated home only
        record = self.home / ".config" / "pine-workspace" / "install.json"
        self.assertTrue(record.is_file())
        self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["path"], str(self.target))
        for never in ("scripts", "docs/maintenance", ".claude/runtime", "tools/pine_exec/node_modules"):
            self.assertFalse((self.target / never).exists(), never)

    def test_distribution_rebuilds_from_the_installation_and_upgrade_plan_is_empty(self):
        self.assertEqual(self.first.returncode, 0)
        rebuilt = Path(self.shared.name) / "rebuilt from install"
        r = distribution.build(self.target, rebuilt, account="agent")
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["clean"], r["personal_pattern_hits"])
        marker = json.loads((self.package / distribution.MARKER).read_text(encoding="utf-8"))
        rebuilt_marker = json.loads((rebuilt / distribution.MARKER).read_text(encoding="utf-8"))
        self.assertEqual(rebuilt_marker["files"], marker["files"])          # same core, byte for byte
        plan = upgrade.plan(self.target, self.package)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["counts"], {"unchanged": len(marker["files"])}, plan["counts"])
        self.assertEqual([e for e in plan["entries"] if e["action"] != "unchanged"], [])

    def test_second_run_detects_the_installation_and_writes_nothing(self):
        before = tree(self.target)
        again = self._install(self.target, "fr")
        self.assertEqual(again.returncode, 1, again.stdout)
        out = again.stdout + again.stderr                 # message in the language asked for this run
        self.assertTrue("Nothing was overwritten" in out or "Rien n'a été écrasé" in out, out)
        self.assertEqual(tree(self.target), before)
        self.assertEqual(json.loads((self.target / "pws.config.json").read_text(encoding="utf-8"))["language"], "en")


    def _own_env(self, **more):
        home = Path(tempfile.mkdtemp(prefix="home ", dir=self.shared.name))    # never the shared record file
        return dict(self.env, HOME=str(home), **more)

    def _run_from(self, package, target, *extra, env=None):
        return subprocess.run([sys.executable, str(package / "install.py"), "--target", str(target)] + list(extra),
                              cwd=str(self.shared.name), env=env or self._own_env(), capture_output=True, text=True,
                              timeout=300)

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_only_the_manifest_is_installed_never_a_history_a_remote_or_a_configuration(self):
        # audit A-02 (2026-11-13): a clone of the public repository brings .git and a remote
        base = Path(self.shared.name)
        clone = base / "cloned package"
        shutil.copytree(str(self.package), str(clone))
        git = ["git", "-C", str(clone), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "public"],
                     ["remote", "add", "origin", "https://example.invalid/official/repository.git"]):
            subprocess.run(git + args, check=True, capture_output=True)
        (clone / "notes.txt").write_text("beside the package\n", encoding="utf-8")
        target = base / "from a clone"
        r = self._run_from(clone, target, "--language", "en", "--copyright-holder", HOLDER, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((target / "notes.txt").exists())
        remotes = subprocess.run(["git", "-C", str(target), "remote"], capture_output=True, text=True).stdout
        self.assertEqual(remotes.strip(), "")
        history = subprocess.run(["git", "-C", str(target), "log", "--oneline"], capture_output=True, text=True)
        self.assertNotEqual(history.returncode, 0)               # a fresh repository: no inherited commit
        # run from an installation, or with a configuration beside the package: refused, nothing written
        for package in (self.target, ):
            r = self._run_from(package, base / "never", "--language", "en", "--yes")
            self.assertEqual(r.returncode, 1)
            self.assertIn("installation, not a downloaded package", r.stdout)
            self.assertFalse((base / "never").exists())

    def test_an_altered_or_foreign_package_installs_nothing(self):
        # audit A-06: every core file is checked against the manifest before anything is written
        base = Path(self.shared.name)
        altered = base / "altered package"
        shutil.copytree(str(self.package), str(altered))
        (altered / "docs" / "architecture" / "OPERATIONS.md").write_text("truncated", encoding="utf-8")
        r = self._run_from(altered, base / "altered target", "--language", "en", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("incomplete or altered", r.stdout)
        self.assertFalse((base / "altered target").exists())
        lone = base / "downloads"
        lone.mkdir()
        shutil.copy2(str(self.package / "install.py"), str(lone / "install.py"))
        r = self._run_from(lone, base / "lone target", "--language", "en", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("PWS_DISTRIBUTION.json missing", r.stdout)
        self.assertFalse((base / "lone target").exists())

    def test_every_step_is_checked_and_git_failure_is_the_degraded_mode(self):
        # audit A-04: a holder starting with a dash, a failing git (macOS stub without developer tools)
        base = Path(self.shared.name)
        stub = base / "stub bin"
        stub.mkdir(exist_ok=True)
        (stub / "git").write_text("#!/bin/sh\necho 'xcode-select: no developer tools' >&2\nexit 1\n", encoding="utf-8")
        (stub / "git").chmod(0o755)
        env = self._own_env(PATH=str(stub) + os.pathsep + self.env.get("PATH", ""))
        target = base / "dash holder"
        r = self._run_from(self.package, target, "--language", "fr", "--copyright-holder=-AdaExample", "--yes", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cfg = json.loads((target / "pws.config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["identity"]["copyright_holder"], "-AdaExample")
        self.assertFalse((target / ".git").exists())
        self.assertIn("mode dégradé", r.stdout)
        self.assertNotIn("Dépôt Git initialisé", r.stdout)
        self.assertEqual([p.name for p in base.iterdir() if ".pws-install-" in p.name], [])
        # no terminal and no --yes: nothing installed
        r = subprocess.run([sys.executable, str(self.package / "install.py"), "--target", str(base / "no yes")],
                           cwd=str(base), env=self._own_env(), capture_output=True, text=True, input="", timeout=120)
        self.assertEqual(r.returncode, 1)
        self.assertFalse((base / "no yes").exists())

if __name__ == "__main__":
    unittest.main()
