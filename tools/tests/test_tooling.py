# SPDX-License-Identifier: Apache-2.0
"""PineTS lifecycle: identity beyond the version number, verify, install plan
and execution with an injected npm, calibrations STALE, rollback (2026-11-06).
No network and no real npm is ever used here."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, doctor, tooling
from tools.tests import helpers

LOCK_INTEGRITY = "sha512-abc"


def fake_engine(root, version="0.10.0", artifact=b"engine-0.10.0"):
    pe = root / "tools" / "pine_exec"
    (pe / "calibration" / "cases").mkdir(parents=True, exist_ok=True)
    (pe / "node_modules" / "pinets" / "dist").mkdir(parents=True, exist_ok=True)
    core.atomic_write_json(pe / "package.json", {"name": "pws-pine-exec", "private": True,
                                                 "dependencies": {"pinets": version}})
    core.atomic_write_json(pe / "package-lock.json", {"packages": {
        "node_modules/pinets": {"version": version, "integrity": LOCK_INTEGRITY}}})
    core.atomic_write_json(pe / "node_modules" / "pinets" / "package.json", {"version": version})
    (pe / "node_modules" / "pinets" / "dist" / "pinets.min.es.js").write_bytes(artifact)
    core.atomic_write_json(pe / "PROVENANCE.json", {
        "package": "pinets", "pinned_version": version,
        "provenance": {"registry_integrity": LOCK_INTEGRITY},
        "license": {"license_basis": "AGPL-3.0-only"}, "verified_at": "2026-09-29"})
    core.atomic_write_json(pe / "calibration" / "capabilities.json", {
        "environment": {"pinets_version": version, "executor_fingerprint": "f" * 64,
                        "normalization_schema": "pws-pinets-norm-v2"},
        "capabilities": {"math-arith": {"capability_status": "EXPERIMENTAL",
                                        "calibration_status": "CURRENT"},
                         "ta-ema": {"capability_status": "EXPERIMENTAL",
                                    "calibration_status": "MISSING"}}})
    (pe / "calibration" / "cases" / "calib-core.pine").write_text("//@version=6\n", encoding="utf-8")
    return pe


class TestTooling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _statuses(self, findings):
        return {f["check"]: f["status"] for f in findings}

    def test_status_reports_identity_and_rules(self):
        s = tooling.status(self.root)
        self.assertEqual(s["pinets"]["pinned"], "0.10.0")
        self.assertEqual(s["pinets"]["installed"], "0.10.0")
        self.assertEqual(s["pinets"]["installed_artifact_sha256"],
                         hashlib.sha256(b"engine-0.10.0").hexdigest())
        self.assertEqual(s["calibration"]["gating"], 0)
        self.assertIn("no silent update at startup", s["rules"])
        self.assertIn("pinets-cli", s["other_tools"])

    def test_verify_records_then_detects_artifact_drift(self):
        st = self._statuses(tooling.verify(self.root))
        self.assertEqual(st["installed-artifact"], "INFO")  # not recorded yet
        st = self._statuses(tooling.verify(self.root, record=True))
        self.assertEqual(st["installed-artifact"], "OK")
        prov = json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["installed_artifact"]["sha256"], hashlib.sha256(b"engine-0.10.0").hexdigest())
        # same declared version, different engine on disk → BLOCKING
        (self.pe / "node_modules" / "pinets" / "dist" / "pinets.min.es.js").write_bytes(b"tampered")
        st = self._statuses(tooling.verify(self.root))
        self.assertEqual(st["installed-artifact"], "BLOCKING")
        self.assertEqual(st["installed"], "OK")  # version number alone would have passed
        # verify never overwrites a recorded hash
        st = self._statuses(tooling.verify(self.root, record=True))
        self.assertEqual(st["installed-artifact"], "BLOCKING")

    def test_verify_lockfile_and_integrity_mismatch(self):
        lock = json.loads((self.pe / "package-lock.json").read_text(encoding="utf-8"))
        lock["packages"]["node_modules/pinets"]["integrity"] = "sha512-other"
        core.atomic_write_json(self.pe / "package-lock.json", lock)
        st = self._statuses(tooling.verify(self.root))
        self.assertEqual(st["registry-integrity"], "BLOCKING")

    def test_install_refused_without_yes_and_plan_problems(self):
        r = tooling.install(self.root, "0.10.0", yes=False)
        self.assertFalse(r["ok"])
        self.assertIn("equals the current pin", r["error"])
        r = tooling.install(self.root, "latest", yes=True)
        self.assertFalse(r["ok"])
        r = tooling.install(self.root, "0.10.1", yes=False)
        self.assertFalse(r["ok"])
        self.assertIn("--yes", r["error"])
        self.assertEqual(r["plan"]["current"], "0.10.0")

    def test_install_with_injected_npm_marks_calibrations_stale_and_rollback(self):
        calls = []

        def fake_npm(cmd, cwd):
            calls.append(cmd)
            if cmd[1] == "install":
                core.atomic_write_json(cwd / "package.json", {"dependencies": {"pinets": "0.10.1"}})
                core.atomic_write_json(cwd / "package-lock.json", {"packages": {
                    "node_modules/pinets": {"version": "0.10.1", "integrity": "sha512-new"}}})
            if cmd[1] == "ci":
                core.atomic_write_json(cwd / "node_modules" / "pinets" / "package.json", {"version": "0.10.1"})
                (cwd / "node_modules" / "pinets" / "dist" / "pinets.min.es.js").write_bytes(b"engine-0.10.1")
            return 0, "", ""

        r = tooling.install(self.root, "0.10.1", yes=True, npm_runner=fake_npm)
        self.assertTrue(r["ok"], r)
        self.assertEqual(calls[0][:3], ["npm", "install", "--save-exact"])
        self.assertIn("--ignore-scripts", calls[0])
        prov = json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["pinned_version"], "0.10.1")
        self.assertEqual(prov["provenance"]["previous_pin"]["pinned_version"], "0.10.0")
        self.assertEqual(prov["installed_artifact"]["sha256"], hashlib.sha256(b"engine-0.10.1").hexdigest())
        self.assertIsNone(prov["verified_at"])
        calib = json.loads((self.pe / "calibration" / "capabilities.json").read_text(encoding="utf-8"))
        self.assertEqual(calib["capabilities"]["math-arith"]["calibration_status"], "STALE")
        self.assertEqual(calib["capabilities"]["math-arith"]["capability_status"], "EXPERIMENTAL")
        self.assertEqual(calib["capabilities"]["ta-ema"]["calibration_status"], "MISSING")
        self.assertNotIn("effective_gating", calib["capabilities"]["math-arith"])
        points = tooling.list_rollback_points(self.root)
        self.assertEqual(points[0]["version"], "0.10.0")
        self.assertTrue(points[0]["has_node_modules"])
        # rollback to the previous engine, byte for byte
        rb = tooling.rollback(self.root, yes=False)
        self.assertFalse(rb["ok"])
        rb = tooling.rollback(self.root, yes=True)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(rb["artifact_check"], "match")
        ident = tooling.engine_identity(self.root)
        self.assertEqual(ident["pinned_version"], "0.10.0")
        self.assertEqual(ident["installed_artifact"]["sha256"], hashlib.sha256(b"engine-0.10.0").hexdigest())
        calib = json.loads((self.pe / "calibration" / "capabilities.json").read_text(encoding="utf-8"))
        self.assertEqual(calib["capabilities"]["math-arith"]["calibration_status"], "CURRENT")

    def test_install_aborts_when_npm_fails_and_rollback_point_exists(self):
        def failing_npm(cmd, cwd):
            return 1, "", "network down"
        r = tooling.install(self.root, "0.10.1", yes=True, npm_runner=failing_npm)
        self.assertFalse(r["ok"])
        self.assertTrue((self.root / tooling.ROLLBACK_REL / "0.10.0" / "package.json").is_file())
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")

    def test_recalibrate_plan_never_executes(self):
        plan = tooling.recalibrate_plan(self.root)
        self.assertEqual(plan["cases"], ["calib-core.pine"])
        self.assertIn("CURRENT ≠ GATING", plan["rules"])
        calib = json.loads((self.pe / "calibration" / "capabilities.json").read_text(encoding="utf-8"))
        self.assertEqual(calib["capabilities"]["math-arith"]["calibration_status"], "CURRENT")


    # ---- Tools menu wording (walkthrough corrections, 2026-11-06) ----------

    def test_status_separates_local_state_from_update_availability(self):
        s = tooling.status(self.root)
        self.assertEqual(s["pinets"]["installed"], "0.10.0")           # local state
        self.assertEqual((s["calibration"]["current"], s["calibration"]["capabilities"]), (1, 2))
        self.assertEqual(s["calibration"]["gating"], 0)                # CURRENT never implies GATING
        self.assertIsNone(s["update_check"]["checked_at"])             # nothing searched yet
        self.assertIsNone(s["update_check"]["update_available"])
        self.assertIn("UNKNOWN", s["update_check"]["note"])
        self.assertEqual((s["rollback_points"], s["rollback_points_usable"]), ([], []))

        def fake_run(cmd, cwd=None, timeout=120):
            self.assertEqual(cmd[:3], ["npm", "view", "pinets"])
            return 0, json.dumps({"version": "0.10.2", "dist-tags": {"latest": "0.10.2"},
                                  "time": {"0.10.2": "2026-10-01T00:00:00Z"}}), ""
        r = tooling.check_update(self.root, runner=fake_run)
        self.assertTrue(r["ok"])
        self.assertEqual((r["latest"], r["update_available"]), ("0.10.2", True))
        self.assertTrue((self.root / tooling.UPDATE_CHECK_REL).is_file())
        s = tooling.status(self.root)
        self.assertEqual(s["update_check"]["checked_at"], r["checked_at"])   # dated, reused result
        self.assertEqual((s["update_check"]["latest"], s["update_check"]["update_available"]), ("0.10.2", True))
        self.assertEqual(s["pinets"]["installed"], "0.10.0")           # nothing installed by a check

    def test_rollback_points_usable_only_when_complete_and_manual_layout_refused(self):
        self.assertTrue(tooling.save_rollback_point(self.root)["ok"])
        manual = self.root / tooling.ROLLBACK_REL / "0.9.33"          # hand-made layout (files under tracked/)
        (manual / "node_modules" / "pinets").mkdir(parents=True)
        (manual / "tracked").mkdir()
        core.atomic_write_json(manual / "tracked" / "package.json", {"dependencies": {"pinets": "0.9.33"}})
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertTrue(points["0.10.0"]["usable"])
        self.assertIsNone(points["0.10.0"]["reason"])
        self.assertFalse(points["0.9.33"]["usable"])
        self.assertIn("package.json", points["0.9.33"]["reason"])
        self.assertIn("manual procedure", points["0.9.33"]["reason"])
        self.assertEqual(tooling.status(self.root)["rollback_points_usable"], ["0.10.0"])
        rb = tooling.rollback(self.root, "0.9.33", yes=True)
        self.assertFalse(rb["ok"])
        self.assertIn("not usable", rb["error"])
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")
        self.assertFalse(tooling.rollback(self.root, "9.9.9", yes=True)["ok"])
        self.assertFalse(tooling.rollback(self.root, "0.10.0", yes=False)["ok"])   # still needs --yes


def tree_state(base):
    """Exact state of a tree: regular files with their hash, symlinks with
    their target (nothing followed)."""
    base = Path(base)
    out = {}
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).as_posix()
        if p.is_symlink():
            out[rel] = ("symlink", os.readlink(str(p)))
        elif p.is_file():
            out[rel] = ("file", hashlib.sha256(p.read_bytes()).hexdigest())
    return out


class TestRollbackPointsVerified(unittest.TestCase):
    """Rollback points (2026-11-07): a manifest absent, malformed, old or
    incomplete never makes a point usable; every recorded hash is verified on
    the saved content; one anomaly refuses the whole restoration without any
    change to the active engine; a valid restoration is verified after
    execution; an execution error is reported as incomplete with the recovery
    elements kept. Fixtures only — never the installed engine."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)
        # the real engine tree carries symlinks (node_modules/.bin): one is saved too
        (self.pe / "node_modules" / ".bin").mkdir()
        os.symlink("../pinets/package.json", str(self.pe / "node_modules" / ".bin" / "pinets-info"))
        self.rdir = self.root / tooling.ROLLBACK_REL

    def tearDown(self):
        self.tmp.cleanup()

    def _point(self, version="0.10.0"):
        r = tooling.save_rollback_point(self.root)
        self.assertTrue(r["ok"], r)
        return self.rdir / version

    def _manifest(self, pdir):
        return json.loads((pdir / tooling.ROLLBACK_MANIFEST).read_text(encoding="utf-8"))

    def _write_manifest(self, pdir, data):
        core.atomic_write_json(pdir / tooling.ROLLBACK_MANIFEST, data)

    def _newer_engine(self):
        """Simulate a later install: other files, another artifact, extra entries."""
        core.atomic_write_json(self.pe / "package.json", {"dependencies": {"pinets": "0.10.1"}})
        core.atomic_write_json(self.pe / "node_modules" / "pinets" / "package.json", {"version": "0.10.1"})
        (self.pe / "node_modules" / "pinets" / "dist" / "pinets.min.es.js").write_bytes(b"engine-0.10.1")
        (self.pe / "node_modules" / "pinets" / "dist" / "extra.js").write_bytes(b"extra")
        os.symlink("../pinets/dist/extra.js", str(self.pe / "node_modules" / ".bin" / "extra"))

    def _assert_refused_unchanged(self, before, rb, point_dirs):
        self.assertFalse(rb["ok"], rb)
        self.assertEqual(rb.get("stage"), "refused", rb)
        self.assertIn("nothing changed", rb["error"])
        self.assertEqual(tree_state(self.pe), before)                      # content AND presence identical
        self.assertEqual(sorted(p.name for p in self.rdir.iterdir()), sorted(point_dirs))   # no pre-rollback point
        self.assertEqual([p.name for p in self.pe.iterdir() if p.name.startswith((".restore-", "node_modules."))], [])

    def test_saved_point_records_every_hash_and_symlink(self):
        pdir = self._point()
        m = self._manifest(pdir)
        self.assertEqual(m["format"], tooling.ROLLBACK_FORMAT)
        self.assertEqual(sorted(m["engine_files"]), sorted(tooling.ENGINE_FILES))
        self.assertTrue(m["node_modules"])
        paths = {e["path"]: e for e in m["entries"]}
        self.assertEqual(paths["node_modules/.bin/pinets-info"], {"path": "node_modules/.bin/pinets-info",
                                                                 "symlink": "../pinets/package.json"})
        self.assertFalse((pdir / "node_modules" / ".bin" / "pinets-info").exists())   # recorded, never copied as a file
        self.assertEqual(paths[tooling.ARTIFACT_REL]["sha256"], hashlib.sha256(b"engine-0.10.0").hexdigest())
        self.assertEqual(m["installed_artifact_sha256"], paths[tooling.ARTIFACT_REL]["sha256"])
        for e in m["entries"]:
            if "sha256" in e:
                self.assertEqual(hashlib.sha256((pdir / e["path"]).read_bytes()).hexdigest(), e["sha256"], e["path"])
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertTrue(points["0.10.0"]["usable"])
        self.assertEqual(points["0.10.0"]["format"], 2)

    def test_manifest_absent_unrelated_or_old_format_never_usable_and_never_converted(self):
        pdir = self._point()
        before = tree_state(self.pe)
        cases = {
            "unrelated": {"unrelated": True},
            "format1": {"saved_at": "2026-09-29T00:00:00Z", "version": "0.10.0",
                        "files": list(tooling.ENGINE_FILES) + ["node_modules"],
                        "installed_artifact_sha256": hashlib.sha256(b"engine-0.10.0").hexdigest()},
            "no-hashes": {"format": 2, "version": "0.10.0", "engine_files": list(tooling.ENGINE_FILES),
                          "node_modules": True, "entries": [{"path": rel} for rel in tooling.ENGINE_FILES]},
        }
        for name, manifest in cases.items():
            self._write_manifest(pdir, manifest)
            written = (pdir / tooling.ROLLBACK_MANIFEST).read_bytes()
            points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
            self.assertFalse(points["0.10.0"]["usable"], name)
            self.assertTrue(points["0.10.0"]["reason"], name)
            if name == "format1":
                self.assertIn("format 1", points["0.10.0"]["reason"])
                self.assertIn("manual procedure", points["0.10.0"]["reason"])
            rb = tooling.rollback(self.root, "0.10.0", yes=True)
            self.assertFalse(rb["ok"], name)
            self.assertIn("not usable", rb["error"])
            self.assertEqual(tree_state(self.pe), before, name)
            # listing or refusing never rewrites the manifest (no retroactive "proof")
            self.assertEqual((pdir / tooling.ROLLBACK_MANIFEST).read_bytes(), written, name)
        (pdir / tooling.ROLLBACK_MANIFEST).unlink()
        self.assertFalse(tooling.list_rollback_points(self.root)[0]["usable"])
        self.assertEqual(tooling.status(self.root)["rollback_points_usable"], [])

    def test_invalid_hash_and_altered_content_refused_before_any_write(self):
        pdir = self._point()
        good = self._manifest(pdir)
        self._newer_engine()
        before = tree_state(self.pe)
        # (a) an invalid hash in the manifest
        bad = json.loads(json.dumps(good))
        next(e for e in bad["entries"] if e["path"] == "package.json")["sha256"] = "zz"
        self._write_manifest(pdir, bad)
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertFalse(points["0.10.0"]["usable"])
        self.assertIn("no valid recorded hash", points["0.10.0"]["reason"])
        self._assert_refused_unchanged(before, tooling.rollback(self.root, "0.10.0", yes=True), ["0.10.0"])
        # (b) altered content of the LAST node_modules entry (checked late): the whole restoration is refused
        self._write_manifest(pdir, good)
        last = [e for e in good["entries"] if "sha256" in e and e["path"].startswith("node_modules/")][-1]
        (pdir / last["path"]).write_bytes(b"tampered")
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertFalse(points["0.10.0"]["usable"])
        self.assertIn("does not match the recorded hash", points["0.10.0"]["reason"])
        self._assert_refused_unchanged(before, tooling.rollback(self.root, "0.10.0", yes=True), ["0.10.0"])
        # (c) the point is bypassed at the listing stage AND at the execution stage: alter after a usable listing
        (pdir / last["path"]).write_bytes(b"engine-0.10.0" if last["path"] == tooling.ARTIFACT_REL
                                          else json.dumps({"version": "0.10.0"}).encode())
        self.assertTrue({p["version"]: p for p in tooling.list_rollback_points(self.root)}["0.10.0"]["usable"])
        (pdir / "calibration" / "capabilities.json").write_bytes(b"{}")
        self._assert_refused_unchanged(before, tooling.rollback(self.root, "0.10.0", yes=True), ["0.10.0"])

    def test_missing_required_file_dangerous_path_and_unlisted_content_refused(self):
        pdir = self._point()
        good = self._manifest(pdir)
        self._newer_engine()
        before = tree_state(self.pe)

        def refused(detail):
            points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
            self.assertFalse(points["0.10.0"]["usable"], detail)
            self.assertIn(detail, " ".join(points["0.10.0"]["problems"]))
            self._assert_refused_unchanged(before, tooling.rollback(self.root, "0.10.0", yes=True), ["0.10.0"])

        # required engine file missing from the backup (structural: reported before any hash)
        (pdir / "calibration" / "capabilities.json").unlink()
        refused("missing at the top level")
        shutil.copy2(str(self.pe / "calibration" / "capabilities.json"),
                     str(pdir / "calibration" / "capabilities.json"))      # same bytes as recorded
        self.assertTrue({p["version"]: p for p in tooling.list_rollback_points(self.root)}["0.10.0"]["usable"])
        # dangerous paths: traversal, absolute, symlink target leaving node_modules
        for entry in ({"path": "../escape.json", "sha256": "a" * 64},
                      {"path": "/etc/hosts", "sha256": "a" * 64},
                      {"path": "node_modules/.bin/evil", "symlink": "../../../../etc/passwd"},
                      {"path": "calibration/other.json", "sha256": "a" * 64}):
            bad = json.loads(json.dumps(good))
            bad["entries"].append(entry)
            self._write_manifest(pdir, bad)
            refused("unsafe path" if entry["path"].startswith(("..", "/")) else
                    ("leaves node_modules" if "symlink" in entry else "unexpected entry"))
        self._write_manifest(pdir, good)
        # an unlisted file inside the saved node_modules tree
        (pdir / "node_modules" / "pinets" / "unlisted.js").write_bytes(b"x")
        refused("not recorded in the manifest")
        (pdir / "node_modules" / "pinets" / "unlisted.js").unlink()
        # a symlinked destination on the engine side
        shutil.rmtree(str(self.pe / "calibration"))
        (self.root / "elsewhere").mkdir()
        os.symlink(str(self.root / "elsewhere"), str(self.pe / "calibration"))
        before = tree_state(self.pe)
        refused("unsafe path")

    def test_valid_rollback_is_verified_after_execution(self):
        pdir = self._point()
        expected = tree_state(pdir)
        del expected[tooling.ROLLBACK_MANIFEST]
        expected["node_modules/.bin/pinets-info"] = ("symlink", "../pinets/package.json")
        self._newer_engine()
        newer = tree_state(self.pe)
        self.assertNotEqual(newer, expected)
        rb = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual((rb["stage"], rb["artifact_check"], rb["node_modules"]), ("verified", "match", "restored"))
        self.assertEqual(sorted(rb["restored"]), sorted(tooling.ENGINE_FILES))
        self.assertEqual(rb["leftovers"], [])
        after = tree_state(self.pe)
        self.assertEqual({k: v for k, v in after.items() if k.startswith(("node_modules/",) + tooling.ENGINE_FILES)},
                         expected)                                          # exact tree, extra entries gone
        self.assertNotIn("node_modules/pinets/dist/extra.js", after)
        self.assertNotIn("node_modules/.bin/extra", after)
        self.assertEqual([p.name for p in self.pe.iterdir() if p.name.startswith((".restore-", "node_modules."))], [])
        # the replaced engine was saved to a verified point first: the way back exists
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        back = [v for v in points if v.startswith("before-rollback-")]
        self.assertEqual(len(back), 1)
        self.assertTrue(points[back[0]]["usable"], points[back[0]]["reason"])
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")
        # the point itself is untouched by the restoration
        self.assertEqual({k: v for k, v in tree_state(pdir).items() if k != tooling.ROLLBACK_MANIFEST},
                         {k: v for k, v in expected.items() if k != "node_modules/.bin/pinets-info"})

    def test_execution_error_is_reported_incomplete_and_recovery_kept(self):
        from unittest import mock
        pdir = self._point()
        self._newer_engine()
        newer = tree_state(self.pe)
        real_rename = os.rename
        calls = []

        def failing_rename(src, dst):
            calls.append((src, dst))
            if len(calls) == 2:                      # staged tree → node_modules: fails after the first rename
                raise OSError("simulated I/O error")
            return real_rename(src, dst)

        with mock.patch("os.rename", side_effect=failing_rename):
            rb = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertFalse(rb["ok"], rb)
        self.assertEqual(rb["stage"], "incomplete")
        self.assertIn("NOT verified", rb["error"])
        self.assertTrue(any("simulated I/O error" in p for p in rb["problems"]))
        rec = rb["recovery"]
        self.assertTrue(Path(rec["point"]).is_dir())                                  # the point is kept
        self.assertTrue(Path(rec["before_rollback_point"]).is_dir())                  # pre-rollback engine kept
        self.assertTrue(Path(rec["staging"]).is_dir())                                # staged tree kept
        self.assertTrue(Path(rec["replaced_node_modules"]).is_dir())                  # replaced tree kept
        self.assertFalse((self.pe / "node_modules").exists())                         # honest: not in place
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertTrue(points["0.10.0"]["usable"])
        self.assertTrue(points[Path(rec["before_rollback_point"]).name]["usable"])
        # a new attempt (no fault) completes and verifies; recovery elements of the failed attempt stay
        rb2 = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertTrue(rb2["ok"], rb2)
        self.assertEqual(rb2["stage"], "verified")
        self.assertTrue(Path(rec["staging"]).is_dir() and Path(rec["replaced_node_modules"]).is_dir())
        self.assertEqual(tooling.engine_identity(self.root)["installed_artifact"]["sha256"],
                         hashlib.sha256(b"engine-0.10.0").hexdigest())
        # the replaced (newer) tree is intact for manual recovery
        self.assertEqual(tree_state(Path(rec["replaced_node_modules"])),
                         {k[len("node_modules/"):]: v for k, v in newer.items() if k.startswith("node_modules/")})

    def test_existing_old_format_point_is_kept_and_a_new_verified_point_saved_beside(self):
        old = self.rdir / "0.10.0"
        old.mkdir(parents=True)
        core.atomic_write_json(old / tooling.ROLLBACK_MANIFEST, {"version": "0.10.0", "files": ["package.json"]})
        (old / "package.json").write_bytes(b"{}")
        before = tree_state(old)
        r = tooling.save_rollback_point(self.root)
        self.assertTrue(r["ok"], r)
        self.assertNotEqual(Path(r["path"]).name, "0.10.0")
        self.assertIn("kept untouched", r["note"])
        self.assertEqual(tree_state(old), before)                                     # never converted
        points = {p["version"]: p for p in tooling.list_rollback_points(self.root)}
        self.assertFalse(points["0.10.0"]["usable"])
        self.assertTrue(points[Path(r["path"]).name]["usable"])
        # an install always starts from a usable point; an unsavable engine aborts before any change
        os.symlink("missing-target", str(self.pe / "node_modules" / "dangling"))
        r = tooling.save_rollback_point(self.root, label="with-dangling")
        self.assertTrue(r["ok"], r)      # a dangling symlink inside node_modules is recorded, not followed
        (self.pe / "node_modules" / "dangling").unlink()
        os.symlink("/etc/hosts", str(self.pe / "node_modules" / "escape"))
        r = tooling.save_rollback_point(self.root, label="with-escape")
        self.assertFalse(r["ok"], r)
        self.assertFalse((self.rdir / "with-escape").exists())
        rep = tooling.install(self.root, "0.10.1", yes=True, npm_runner=lambda cmd, cwd: (0, "", ""))
        self.assertFalse(rep["ok"])
        self.assertIn("aborting before any change", rep["error"])
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")


# ---- corrections before publication (audit 2026-11-12/13, domain G) ---------

def complete_npm(pe, calls=None):
    """Injected npm that really "installs" the requested version (fixtures)."""
    def run(cmd, cwd):
        if calls is not None:
            calls.append(" ".join(cmd))
        if cmd[1] == "install":
            target = cmd[-1].split("@", 1)[1]
            core.atomic_write_json(pe / "package.json", {"dependencies": {"pinets": target}})
            core.atomic_write_json(pe / "package-lock.json", {"packages": {
                "node_modules/pinets": {"version": target, "integrity": "sha512-new"}}})
            core.atomic_write_json(pe / "node_modules" / "pinets" / "package.json", {"version": target})
            (pe / tooling.ARTIFACT_REL).write_bytes(b"engine-" + target.encode())
        return 0, "", ""
    return run


def published(version):
    return {"version": version, "dist-tags": {"latest": version}, "time": {version: "2026-10-01T00:00:00Z"}}


def npm_answer(payload, rc=0):
    out = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda cmd, cwd=None, timeout=120: (rc, out, "" if rc == 0 else "npm ERR! simulated")


class TestUpdateCheck(unittest.TestCase):
    """`pinets check-update` (G-01, G-02, G-03): numeric comparison, a
    pre-release never proposed by default, any answer without a usable version
    is an error that records nothing, and the dated result is re-evaluated
    against the pin in force."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)                      # pin 0.10.0
        self.record = self.root / tooling.UPDATE_CHECK_REL

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_a_stable_strictly_newer_version_is_an_update(self):
        cases = (("0.10.1", "update-available", True), ("0.10.10", "update-available", True),
                 ("1.0.0", "update-available", True), ("0.10.0", "up-to-date", False),
                 ("0.9.40", "ahead", False), ("0.9.99", "ahead", False),
                 ("0.11.0-beta.1", "prerelease", False), ("0.10.0-rc.1", "ahead", False))
        for latest, result, available in cases:
            r = tooling.check_update(self.root, runner=npm_answer(published(latest)))
            self.assertTrue(r["ok"], (latest, r))
            self.assertEqual((r["result"], r["update_available"]), (result, available), latest)
            self.assertEqual(r["latest_is_prerelease"], "-" in latest, latest)
            self.assertEqual(r["recorded"], str(tooling.UPDATE_CHECK_REL))
            uc = tooling.read_update_check(self.root)                  # what tooling-status reuses
            self.assertEqual((uc["latest"], uc["result"], uc["update_available"]), (latest, result, available), latest)
        self.assertIn("never proposed by default", tooling.check_update(
            self.root, runner=npm_answer(published("0.11.0-beta.1")))["note"])

    def test_a_pinned_prerelease_follows_semver_precedence(self):
        core.atomic_write_json(self.pe / "package.json", {"dependencies": {"pinets": "0.11.0-beta.2"}})
        for latest, result in (("0.11.0", "update-available"), ("0.11.0-beta.10", "prerelease"),
                               ("0.11.0-beta.1", "ahead"), ("0.10.9", "ahead")):
            r = tooling.check_update(self.root, runner=npm_answer(published(latest)))
            self.assertEqual(r["result"], result, latest)
            self.assertEqual(r["update_available"], result == "update-available", latest)

    def test_answers_without_a_usable_version_are_errors_that_record_nothing(self):
        good = tooling.check_update(self.root, runner=npm_answer(published("0.10.1")))
        recorded = self.record.read_bytes()
        bad = (("npm ERR! code E404", 1), ("garbage <html>", 0), ('"0.10.1"', 0), ("null", 0), ("[1, 2]", 0),
               ({}, 0), ({"version": 10, "dist-tags": "x", "time": []}, 0), ({"version": "latest"}, 0),
               ({"version": "v0.10.1"}, 0), ({"version": None, "dist-tags": {"latest": "0.10.1"}}, 0))
        for payload, rc in bad:
            r = tooling.check_update(self.root, runner=npm_answer(payload, rc))
            self.assertFalse(r["ok"], payload)
            self.assertEqual((r["result"], r["update_available"], r["recorded"]), ("error", None, None), payload)
            self.assertIn("UNKNOWN", r["note"])
            self.assertEqual(self.record.read_bytes(), recorded, payload)     # the dated result is untouched
        uc = tooling.read_update_check(self.root)
        self.assertEqual((uc["checked_at"], uc["update_available"]), (good["checked_at"], True))
        self.record.unlink()
        self.assertFalse(tooling.check_update(self.root, runner=npm_answer({}))["ok"])
        self.assertFalse(self.record.exists())                                # never a dated "no update"
        self.assertEqual(tooling.status(self.root)["update_check"]["result"], "not-searched")

    def test_a_record_without_usable_version_reads_unknown(self):
        # what the earlier tool recorded for an `{}` answer
        core.atomic_write_json(self.record, {"ok": True, "pinned": "0.10.0", "latest": None,
                                             "update_available": False, "checked_at": "2026-11-13T04:40:09Z"})
        uc = tooling.read_update_check(self.root)
        self.assertEqual((uc["checked_at"], uc["result"], uc["update_available"]),
                         ("2026-11-13T04:40:09Z", "unknown", None))
        self.assertIn("UNKNOWN", uc["note"])

    def test_dated_result_is_re_evaluated_after_install_and_rollback(self):
        r = tooling.check_update(self.root, runner=npm_answer(published("0.10.1")))
        self.assertTrue(r["update_available"])
        self.assertTrue(tooling.install(self.root, "0.10.1", yes=True, npm_runner=complete_npm(self.pe))["ok"])
        uc = tooling.status(self.root)["update_check"]
        self.assertEqual((uc["checked_at"], uc["latest"]), (r["checked_at"], "0.10.1"))     # same dated search
        self.assertEqual((uc["result"], uc["update_available"], uc["pinned_at_check"], uc["pinned_now"]),
                         ("up-to-date", False, "0.10.0", "0.10.1"))
        self.assertIn("while the pin was 0.10.0", uc["note"])
        self.assertTrue(tooling.rollback(self.root, yes=True)["ok"])
        uc = tooling.read_update_check(self.root)
        self.assertEqual((uc["result"], uc["update_available"], uc["pinned_now"]), ("update-available", True, "0.10.0"))


class TestInstallPostconditionsAndDefaultRollback(unittest.TestCase):
    """`pinets install` declares success only for the engine actually on disk
    (G-04) and records the point really saved, which `pinets rollback` without
    a version restores (G-06)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)
        self.rdir = self.root / tooling.ROLLBACK_REL

    def tearDown(self):
        self.tmp.cleanup()

    def _bytes(self):
        return ((self.pe / "PROVENANCE.json").read_bytes(),
                (self.pe / "calibration" / "capabilities.json").read_bytes())

    def _unusable_same_version_point(self):
        manual = self.rdir / "0.10.0"
        manual.mkdir(parents=True)
        shutil.copy2(str(self.pe / "package.json"), str(manual / "package.json"))

    def _previous_pin(self):
        return json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))["provenance"]["previous_pin"]

    def test_npm_success_without_effect_is_a_failure_with_state_and_way_back(self):
        before, calls = self._bytes(), []
        r = tooling.install(self.root, "0.10.1", yes=True,
                            npm_runner=lambda cmd, cwd: (calls.append(cmd[1]), (0, "", ""))[1])
        self.assertEqual(calls, ["install", "ci"])
        self.assertFalse(r["ok"], r)
        self.assertIn("not pinets 0.10.1", r["error"])
        self.assertIn("`pinets rollback 0.10.0 --yes`", r["error"])
        self.assertEqual(r["rollback_point"], "0.10.0")
        self.assertEqual((r["state"]["pinned"], r["state"]["installed"]), ("0.10.0", "0.10.0"))
        self.assertEqual(self._bytes(), before)              # PROVENANCE and calibrations untouched
        st = {f["check"]: f["status"] for f in tooling.verify(self.root)}
        self.assertEqual((st["provenance-pin"], st["lockfile"]), ("OK", "OK"))

    def test_manifests_rewritten_without_the_engine_is_a_failure(self):
        before = self._bytes()

        def manifests_only(cmd, cwd):
            if cmd[1] == "install":
                core.atomic_write_json(cwd / "package.json", {"dependencies": {"pinets": "0.10.1"}})
                core.atomic_write_json(cwd / "package-lock.json", {"packages": {
                    "node_modules/pinets": {"version": "0.10.1", "integrity": "sha512-new"}}})
            return 0, "", ""
        r = tooling.install(self.root, "0.10.1", yes=True, npm_runner=manifests_only)
        self.assertFalse(r["ok"])
        self.assertIn("node_modules/pinets is version '0.10.0'", r["error"])
        self.assertEqual(self._bytes(), before)
        st = {f["check"]: f["status"] for f in tooling.verify(self.root)}
        self.assertEqual(st["installed"], "WARNING")         # the half-done state is visible
        back = tooling.rollback(self.root, r["rollback_point"], yes=True)
        self.assertTrue(back["ok"], back)
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")

    def test_verify_reports_a_provenance_that_does_not_describe_the_pin(self):
        prov = json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        prov["pinned_version"] = "0.10.1"
        core.atomic_write_json(self.pe / "PROVENANCE.json", prov)
        st = {f["check"]: f["status"] for f in tooling.verify(self.root)}
        dc = {r["check"]: r["severity"] for r in doctor._pinets_checks(self.root)}
        self.assertEqual((st["provenance-pin"], dc["pinets-provenance-pin"]), ("WARNING", "WARNING"))
        (self.pe / "PROVENANCE.json").unlink()
        st = {f["check"]: f["status"] for f in tooling.verify(self.root)}
        dc = {r["check"]: r["severity"] for r in doctor._pinets_checks(self.root)}
        self.assertEqual((st["provenance"], dc["pinets-provenance"]), ("WARNING", "WARNING"))

    def test_the_point_really_saved_is_recorded_and_restored_by_default(self):
        self._unusable_same_version_point()
        r = tooling.install(self.root, "0.10.1", yes=True, npm_runner=complete_npm(self.pe))
        self.assertTrue(r["ok"], r)
        point = r["rollback_point"]
        self.assertTrue(point.startswith("0.10.0-") and point != "0.10.0")
        prev = self._previous_pin()
        self.assertEqual((prev["rollback"], prev["rollback_point"]), ("%s/%s" % (tooling.ROLLBACK_REL, point), point))
        rb = tooling.rollback(self.root, yes=True)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual((rb["version"], rb["stage"]), (point, "verified"))
        self.assertEqual(tooling.engine_identity(self.root)["pinned_version"], "0.10.0")

    def test_earlier_provenance_falls_back_to_the_latest_usable_install_point(self):
        self._unusable_same_version_point()
        # a usable pre-rollback point carrying the same pin, more recent: never chosen by default
        r = tooling.save_rollback_point(self.root, label="before-rollback-20991231T000000Z-zz")
        self.assertTrue(r["ok"], r)
        manifest = Path(r["path"]) / tooling.ROLLBACK_MANIFEST
        m = json.loads(manifest.read_text(encoding="utf-8"))
        m["saved_at"] = "2099-12-31T00:00:00Z"
        core.atomic_write_json(manifest, m)
        r = tooling.install(self.root, "0.10.1", yes=True, npm_runner=complete_npm(self.pe))
        self.assertTrue(r["ok"], r)
        prov = json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        prov["provenance"]["previous_pin"]["rollback"] = "%s/0.10.0" % tooling.ROLLBACK_REL   # as written before
        del prov["provenance"]["previous_pin"]["rollback_point"]
        core.atomic_write_json(self.pe / "PROVENANCE.json", prov)
        rb = tooling.rollback(self.root, yes=True)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(rb["version"], r["rollback_point"])

    def test_previous_pin_without_usable_point_is_refused_with_its_reason(self):
        self._unusable_same_version_point()
        prov = json.loads((self.pe / "PROVENANCE.json").read_text(encoding="utf-8"))
        prov["provenance"]["previous_pin"] = {"pinned_version": "0.10.0",
                                              "rollback": "docs/maintenance/x/02-dossier.md, section 5"}
        core.atomic_write_json(self.pe / "PROVENANCE.json", prov)
        before = tree_state(self.pe)
        rb = tooling.rollback(self.root, yes=True)
        self.assertEqual((rb["ok"], rb["stage"], rb["version"]), (False, "refused", "0.10.0"))
        self.assertIn("not usable", rb["error"])
        self.assertEqual(tree_state(self.pe), before)


class TestRollbackTreeConfined(unittest.TestCase):
    """G-05: a rollback tree reached through a symbolic link (on itself or a
    parent) is neither listed, written nor restored — refused before any
    write, the npm runner is never called."""

    def test_symlinked_rollback_tree_or_parent_refused_before_any_write(self):
        for link_rel in (tooling.ROLLBACK_REL, core.RUNTIME_REL, Path(".claude")):
            with tempfile.TemporaryDirectory() as tmp:
                root = helpers.make_workspace(tmp)
                pe = fake_engine(root)
                outside = Path(tmp) / "outside"
                outside.mkdir()
                # a verified point exists, then its tree is replaced by a link to the outside copy
                self.assertTrue(tooling.save_rollback_point(root)["ok"])
                real = root / link_rel
                shutil.move(str(real), str(outside / "moved"))
                os.symlink(str(outside / "moved"), str(real))
                files_outside = sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*"))
                before, calls = tree_state(pe), []
                r = tooling.install(root, "0.10.1", yes=True, npm_runner=complete_npm(pe, calls))
                self.assertFalse(r["ok"], link_rel)
                self.assertIn("symbolic link", r["error"])
                self.assertEqual(calls, [], link_rel)
                self.assertFalse(tooling.save_rollback_point(root)["ok"], link_rel)
                s = tooling.status(root)
                self.assertEqual((s["rollback_points"], s["rollback_points_usable"]), ([], []), link_rel)
                self.assertIn("symbolic link", s["rollback_tree_refused"])
                rb = tooling.rollback(root, "0.10.0", yes=True)
                self.assertEqual((rb["ok"], rb["stage"]), (False, "refused"), link_rel)
                self.assertFalse(tooling.rollback(root, yes=True)["ok"], link_rel)
                self.assertEqual(tree_state(pe), before, link_rel)                  # engine untouched
                self.assertEqual(sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*")),
                                 files_outside, link_rel)                           # nothing written outside


class TestEngineIntegrityReading(unittest.TestCase):
    """G-07, G-08, G-10: `tooling-status` never calls CURRENT an absent engine
    or an artifact that is not the recorded one; `verify` and the doctor give
    the same fact the same severity; the recorded `verified_at` is never shown
    as a verification of this machine; every repair command printed is
    `npm ci --ignore-scripts`."""

    MAPPING = {"lockfile": "pinets-lockfile", "installed": "pinets-installed",
               "installed-artifact": "pinets-installed-artifact"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)
        self.art = self.pe / tooling.ARTIFACT_REL
        self.assertEqual({f["check"]: f["status"] for f in tooling.verify(self.root, record=True)}
                         ["installed-artifact"], "OK")

    def tearDown(self):
        self.tmp.cleanup()

    def _status(self):
        with mock.patch.object(tooling, "_current_fingerprint", return_value="f" * 64):   # calibrated one
            return tooling.status(self.root)

    def _states(self):
        """(label, mutate, restore) of the engine states compared below."""
        art = self.art.read_bytes()
        inst = self.pe / "node_modules" / "pinets" / "package.json"
        lock = (self.pe / "package-lock.json").read_bytes()
        return (
            ("match", lambda: None, lambda: None),
            ("differs", lambda: self.art.write_bytes(art + b"\n"), lambda: self.art.write_bytes(art)),
            ("missing", lambda: self.art.unlink(), lambda: self.art.write_bytes(art)),
            ("version", lambda: core.atomic_write_json(inst, {"version": "0.9.0"}),
             lambda: core.atomic_write_json(inst, {"version": "0.10.0"})),
            ("lockfile", lambda: core.atomic_write_json(self.pe / "package-lock.json", {"packages": {
                "node_modules/pinets": {"version": "0.10.1", "integrity": LOCK_INTEGRITY}}}),
             lambda: (self.pe / "package-lock.json").write_bytes(lock)),
            ("absent", lambda: shutil.move(str(self.pe / "node_modules"), str(self.root / "nm-away")),
             lambda: shutil.move(str(self.root / "nm-away"), str(self.pe / "node_modules"))),
        )

    def test_freshness_is_current_only_for_the_recorded_installed_engine(self):
        # (a lockfile change is seen through the executor fingerprint, which hashes
        # package.json and package-lock.json — mocked to the calibrated value here)
        expected = {"match": ("match", "CURRENT"), "differs": ("differs", "STALE"),
                    "missing": ("missing", "unknown"), "version": ("match", "STALE"),
                    "absent": ("not-installed", "unknown")}
        for label, mutate, restore_ in self._states():
            if label not in expected:
                continue
            mutate()
            s = self._status()
            self.assertEqual((s["pinets"]["artifact_check"], s["calibration"]["freshness"].split(" ")[0]),
                             expected[label], (label, s["calibration"]["freshness"]))
            restore_()
        self.assertIn("installed artifact matches the recorded hash", self._status()["calibration"]["freshness"])

    def test_verify_and_doctor_give_the_same_severity_to_the_same_fact(self):
        seen = set()
        for label, mutate, restore_ in self._states():
            mutate()
            v = {f["check"]: f["status"] for f in tooling.verify(self.root)}
            d = {r["check"]: r["severity"] for r in doctor._pinets_checks(self.root)}
            for vcheck, dcheck in self.MAPPING.items():
                self.assertEqual(v[vcheck], d[dcheck], (label, vcheck))
                seen.add((label, vcheck, v[vcheck]))
            restore_()
        self.assertIn(("differs", "installed-artifact", "BLOCKING"), seen)     # an integrity failure in both
        self.assertIn(("missing", "installed-artifact", "WARNING"), seen)
        self.assertIn(("absent", "installed-artifact", "INFO"), seen)

    def test_recorded_verification_date_is_not_presented_as_an_integrity_check(self):
        prov_before = (self.pe / "PROVENANCE.json").read_bytes()
        s = self._status()["pinets"]
        self.assertNotIn("verified_at", s)
        self.assertEqual(s["provenance_verified_at"], "2026-09-29")
        self.assertIn("NOT a verification performed on this machine", s["provenance_verified_at_note"])
        self.art.write_bytes(b"tampered")
        s = self._status()["pinets"]
        self.assertEqual((s["artifact_check"], s["provenance_verified_at"]), ("differs", "2026-09-29"))
        self.assertIn("DIFFERENT", s["artifact_check_note"])
        tooling.verify(self.root)
        self.assertEqual((self.pe / "PROVENANCE.json").read_bytes(), prov_before)   # verify writes nothing

    def test_every_repair_command_printed_is_npm_ci_with_ignore_scripts(self):
        bare = re.compile(r"npm ci(?! --ignore-scripts)")
        texts = [tooling.install(self.root, "0.10.0", yes=True)["error"]]
        for label, mutate, restore_ in self._states():
            mutate()
            texts += [f["detail"] for f in tooling.verify(self.root)]
            texts += [r["detail"] for r in doctor._pinets_checks(self.root)]
            texts.append(self._status()["pinets"]["artifact_check_note"])
            restore_()
        mentions = [t for t in texts if "npm ci" in t]
        self.assertGreaterEqual(len(mentions), 6)
        self.assertEqual([t for t in mentions if bare.search(t)], [])


class TestInterruptedRollback(unittest.TestCase):
    """G-11: an interruption during `pinets rollback` is reported (never a
    trace without a report), and what it leaves beside the engine is flagged
    by `verify`, the doctor and `tooling-status` — never removed automatically."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.pe = fake_engine(self.root)
        (self.pe / "node_modules" / ".bin").mkdir()
        os.symlink("../pinets/package.json", str(self.pe / "node_modules" / ".bin" / "pinets-info"))
        self.assertTrue(tooling.install(self.root, "0.10.1", yes=True, npm_runner=complete_npm(self.pe))["ok"])
        self.rdir = self.root / tooling.ROLLBACK_REL

    def tearDown(self):
        self.tmp.cleanup()

    def _leftover_names(self):
        return sorted(p.name for p in self.pe.iterdir() if p.name.startswith((".restore-", "node_modules.")))

    def test_interruption_during_the_renames_is_incomplete_and_flagged_everywhere(self):
        real_rename, calls = os.rename, []

        def interrupted(src, dst):
            calls.append(src)
            if len(calls) == 2:                  # after node_modules was moved aside
                raise KeyboardInterrupt("simulated")
            return real_rename(src, dst)
        with mock.patch("os.rename", side_effect=interrupted):
            rb = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertEqual((rb["ok"], rb["stage"], rb.get("interrupted")), (False, "incomplete", True))
        self.assertIn("NOT verified", rb["error"])
        back = Path(rb["recovery"]["before_rollback_point"]).name
        self.assertFalse((self.pe / "node_modules").exists())
        left = tooling.rollback_leftovers(self.root)
        self.assertEqual(sorted(x["kind"] for x in left), ["replaced-node_modules", "staging"])
        self.assertEqual({x["before_rollback_point"] for x in left}, {back})
        self.assertTrue(all(x["before_rollback_point_present"] for x in left))
        v = {f["check"]: f for f in tooling.verify(self.root)}
        self.assertEqual(v["rollback-leftovers"]["status"], "WARNING")
        self.assertIn(back, v["rollback-leftovers"]["detail"])
        self.assertIn("interrupted rollback", v["installed"]["detail"])
        d = {r["check"]: r for r in doctor._pinets_checks(self.root)}
        self.assertEqual(d["pinets-rollback-leftovers"]["severity"], "WARNING")
        self.assertIn("interrupted rollback", d["pinets-installed"]["detail"])
        s = tooling.status(self.root)
        self.assertEqual(len(s["rollback_leftovers"]), 2)
        self.assertIn(back, s["rollback_leftovers_note"])
        self.assertTrue(s["calibration"]["freshness"].startswith("unknown (engine not installed"))
        # recovery through the pre-rollback point; the leftovers stay until removed by hand
        rec = tooling.rollback(self.root, back, yes=True)
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(len(tooling.rollback_leftovers(self.root)), 2)
        self.assertEqual({f["check"]: f["status"] for f in tooling.verify(self.root)}["rollback-leftovers"], "WARNING")

    def test_interruption_while_staging_changes_nothing_and_leaves_nothing(self):
        before = tree_state(self.pe)
        with mock.patch("os.symlink", side_effect=KeyboardInterrupt("simulated")):   # staging only
            rb = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertEqual((rb["ok"], rb["stage"], rb.get("interrupted")), (False, "refused", True))
        self.assertIn("nothing changed", rb["error"])
        self.assertEqual(tree_state(self.pe), before)
        self.assertEqual(self._leftover_names(), [])
        self.assertEqual(tooling.rollback_leftovers(self.root), [])

    def test_interruption_while_saving_the_current_engine_leaves_no_partial_point(self):
        before, points = tree_state(self.pe), sorted(p.name for p in self.rdir.iterdir())
        real_copy, calls = shutil.copy2, []

        def interrupted(src, dst, **kw):
            calls.append(src)
            if len(calls) == 3:
                raise KeyboardInterrupt("simulated")
            return real_copy(src, dst, **kw)
        with mock.patch.object(tooling.shutil, "copy2", side_effect=interrupted):
            rb = tooling.rollback(self.root, "0.10.0", yes=True)
        self.assertEqual((rb["ok"], rb["stage"], rb.get("interrupted")), (False, "refused", True))
        self.assertEqual(tree_state(self.pe), before)
        self.assertEqual(sorted(p.name for p in self.rdir.iterdir()), points)     # no partial point
        self.assertEqual(self._leftover_names(), [])


if __name__ == "__main__":
    unittest.main()
