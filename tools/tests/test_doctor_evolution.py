# SPDX-License-Identifier: Apache-2.0
"""Doctor after the 2026-11-06 evolution: configuration checks, degraded
Git, engine artifact identity, legacy TV key (audit items 3 and 5)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from tools.pws_workspace import core, doctor
from tools.tests import helpers
from tools.tests.test_tooling import fake_engine


def by_check(results):
    out = {}
    for r in results:
        out.setdefault(r["check"], []).append(r)
    return out


class TestDoctorEvolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / "standards").mkdir()
        (self.root / "standards" / "PINE_SCRIPT_V6_STANDARD.md").write_text("# M\n\n## 0. X\n", encoding="utf-8")
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text(json.dumps({
            "worktree": {"baseRef": "head"},
            "hooks": {"SessionStart": [], "Stop": []}}), encoding="utf-8")
        (self.root / "tools" / "tests").mkdir(parents=True)
        (self.root / "tools" / "tests" / "test_x.py").write_text("", encoding="utf-8")
        import subprocess
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_config_is_info_not_blocking(self):
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pws-config"][0]["severity"], "INFO")
        self.assertEqual(r["tv-mode-valid"][0]["severity"], "OK")
        self.assertIn("default", r["tv-mode-valid"][0]["detail"])
        self.assertNotIn("BLOCKING", [x["severity"] for x in r["tv-mode-valid"]])

    def test_configured_identity_ok_and_legacy_key_info(self):
        helpers.configure(self.root)
        settings = self.root / core.LOCAL_SETTINGS_REL
        settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "manual"}}), encoding="utf-8")
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pws-config"][0]["severity"], "OK")
        self.assertEqual(r["identity-configured"][0]["severity"], "OK")
        # configuration wins over the legacy key: no legacy INFO once the config holds the mode
        self.assertNotIn("tv-mode-legacy-key", r)
        settings.write_text(json.dumps({"env": {core.TV_MODE_ENV_KEY: "banana"}}), encoding="utf-8")
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["tv-mode-valid"][0]["severity"], "OK")  # config is authoritative

    def test_invalid_config_blocking(self):
        (self.root / "pws.config.json").write_text(json.dumps({"schema_version": 1, "language": "xx"}),
                                                   encoding="utf-8")
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pws-config"][0]["severity"], "BLOCKING")

    def test_git_absent_is_degraded_warning_not_crash(self):
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent-bin"}):
            state = core.git_state(self.root)
            self.assertFalse(state["available"])
            self.assertIn("degraded", state["error"])
            r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["git-available"][0]["severity"], "WARNING")
        self.assertIn("install Git", r["git-available"][0]["detail"])

    def test_not_a_repo_is_warning(self):
        import shutil
        shutil.rmtree(str(self.root / ".git"))
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["git-repo"][0]["severity"], "WARNING")
        self.assertIn("git init", r["git-repo"][0]["detail"])

    def test_engine_artifact_identity(self):
        pe = fake_engine(self.root)
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pinets-installed-artifact"][0]["severity"], "INFO")
        prov = json.loads((pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        prov["installed_artifact"] = {"path": "node_modules/pinets/dist/pinets.min.es.js",
                                      "sha256": core.sha256_bytes(b"engine-0.10.0")}
        core.atomic_write_json(pe / "PROVENANCE.json", prov)
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pinets-installed-artifact"][0]["severity"], "OK")
        (pe / "node_modules" / "pinets" / "dist" / "pinets.min.es.js").write_bytes(b"other")
        r = by_check(doctor.run_doctor(self.root))
        # audit G-07 (2026-11-13): an installed artifact that differs from the recorded one is
        # BLOCKING, as in `pinets verify` (a missing artifact stays a WARNING in both)
        self.assertEqual(r["pinets-installed-artifact"][0]["severity"], "BLOCKING")
        prov["pinned_version"] = "0.9.33"
        core.atomic_write_json(pe / "PROVENANCE.json", prov)
        r = by_check(doctor.run_doctor(self.root))
        self.assertEqual(r["pinets-provenance-pin"][0]["severity"], "WARNING")


if __name__ == "__main__":
    unittest.main()
