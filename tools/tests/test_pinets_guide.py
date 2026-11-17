# SPDX-License-Identifier: Apache-2.0
"""Guided update of PineTS (2.2.0): `pinets guide` (state, search, prepare,
apply) over the existing lifecycle, and the guided recalibration. Isolated
workspaces only; the npm registry and GitHub answers are SIMULATED (never a
real query or installation): an archive is built from the engine of the
fixture, the "installation" rewrites the pin, the lockfile and the installed
version label exactly as npm would, the artifact being the archive's one.

The real-engine tests copy the adapter WITH its installed engine into a
temporary workspace and run the real runner (skipped when Node or the engine
is absent, as in a fresh distribution)."""
import base64
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, i18n, pinets_guide, recalibration, tooling
from tools.tests import helpers
from tools.tests.test_tooling import fake_engine

ROOT = core.workspace_root()
REAL_PE = ROOT / "tools" / "pine_exec"
HAS_ENGINE = (REAL_PE / "node_modules" / "pinets" / "package.json").is_file() and shutil.which("node") is not None


def sri(data):
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


def build_tgz(version, artifact, license_text=b"AGPL text\n", spdx="AGPL-3.0-only", extra=None, exports=True):
    pkg = {"name": "pinets", "version": version, "license": spdx, "type": "module",
           "module": "dist/pinets.min.es.js", "dependencies": {"acorn": "^8.14.0"}}
    if exports:
        pkg["exports"] = {".": {"node": {"import": "./dist/pinets.min.es.js"}, "default": "./dist/pinets.min.es.js"}}
    members = {"package/package.json": json.dumps(pkg).encode(), "package/LICENSE": license_text,
               "package/dist/pinets.min.es.js": artifact}
    members.update(extra or {})
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class FakeNpm:
    """Deterministic npm: `view` answers metadata, `pack` writes the archive,
    `install` rewrites the pin, lockfile and installed label, `ci` is a no-op."""

    def __init__(self, pe, version, tgz, integrity=None, view=None, latest=None):
        self.pe, self.version, self.tgz = pe, version, tgz
        self.integrity = integrity or sri(tgz)
        self.view = view
        self.latest = latest or version
        self.calls = []

    def run(self, cmd, cwd=None, timeout=None):
        self.calls.append(cmd[:2])
        if cmd[1] == "view" and cmd[2] == "pinets":                # check-update
            return 0, json.dumps({"version": self.latest, "dist-tags": {"latest": self.latest},
                                  "time": {self.latest: "2026-10-27T14:22:27.467Z"}}), ""
        if cmd[1] == "view":
            meta = self.view if self.view is not None else {
                "version": self.version, "license": "AGPL-3.0-only",
                "dist": {"integrity": self.integrity,
                         "tarball": "https://registry.npmjs.org/pinets/-/pinets-%s.tgz" % self.version},
                "repository": {"type": "git", "url": "git+https://github.com/Example/PineTS.git"}}
            return 0, json.dumps(meta), ""
        if cmd[1] == "pack":
            dest = Path(cmd[cmd.index("--pack-destination") + 1])
            (dest / ("pinets-%s.tgz" % self.version)).write_bytes(self.tgz)
            return 0, "[]", ""
        return 1, "", "unexpected npm call %s" % cmd

    def installer(self, fail_at=None, wrong_artifact=False):
        def run(cmd, cwd):
            self.calls.append(cmd[:2])
            if cmd[1] == fail_at:
                return 1, "", "simulated npm failure"
            if cmd[1] == "install":
                pkg = json.loads((cwd / "package.json").read_text(encoding="utf-8"))
                pkg["dependencies"]["pinets"] = self.version
                core.atomic_write_json(cwd / "package.json", pkg)
                lock = json.loads((cwd / "package-lock.json").read_text(encoding="utf-8"))
                lock["packages"]["node_modules/pinets"].update(version=self.version, integrity=self.integrity)
                core.atomic_write_json(cwd / "package-lock.json", lock)
                ipkg = cwd / "node_modules" / "pinets" / "package.json"
                data = json.loads(ipkg.read_text(encoding="utf-8"))
                data["version"] = self.version
                core.atomic_write_json(ipkg, data)
                lic = cwd / "node_modules" / "pinets" / "LICENSE"
                with tarfile.open(fileobj=io.BytesIO(self.tgz), mode="r:gz") as tf:
                    lic.write_bytes(tf.extractfile("package/LICENSE").read())
                    if not wrong_artifact:
                        (cwd / tooling.ARTIFACT_REL).write_bytes(tf.extractfile("package/dist/pinets.min.es.js").read())
                if wrong_artifact:
                    (cwd / tooling.ARTIFACT_REL).write_bytes(b"something else")
            return 0, "", ""
        return run


def no_github(url):
    return None, None, "URLError: <simulated: no network>"


def github_with(releases):
    return lambda url: (200, releases, None)


class TestPinetsGuideWithoutEngine(unittest.TestCase):
    """Fake engine (no Node needed): search, preparation and refusals."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, language="fr")
        self.pe = fake_engine(self.root)
        # the shipped calibration material (cases, datasets, references, contract): a planned recalibration
        # is bound to it (2.2.0 correction); the fake engine never executes it
        shutil.copytree(str(REAL_PE / "calibration"), str(self.pe / "calibration"), dirs_exist_ok=True)
        (self.pe / "PINETS_LICENSE").write_bytes(b"AGPL text\n")
        self.artifact = (self.pe / tooling.ARTIFACT_REL).read_bytes()
        self.tgz = build_tgz("0.10.1", self.artifact)
        self.npm = FakeNpm(self.pe, "0.10.1", self.tgz)
        self.dl = Path(self.tmp.name) / "download"

    def tearDown(self):
        self.tmp.cleanup()

    def engine_bytes(self):
        return {p.relative_to(self.pe).as_posix(): core.sha256_file(p) for p in self.pe.rglob("*") if p.is_file()}

    def test_state_and_search_in_both_languages(self):
        for lang in ("fr", "en"):
            st = pinets_guide.state(self.root, lang=lang)
            self.assertIn(i18n.t("ptg.installed.yes", lang, v="0.10.0"), st["summary"]["state"])
            self.assertIn(i18n.t("ptg.search.none", lang), st["summary"]["state"])
            self.assertIn(i18n.t("ptg.tv", lang), st["summary"]["limits"])
            # fake engine: fingerprint differs from the calibrated one → recorded statuses said not effective
            self.assertIn(i18n.t("ptg.calib.not_effective", lang), st["summary"]["state"])
        s = pinets_guide.search(self.root, lang="fr", runner=lambda cmd, timeout=60: (1, "", "ENOTFOUND registry"))
        self.assertEqual(s["result"]["result"], "error")
        self.assertIn("on ignore toujours", s["summary"]["text"])
        s = pinets_guide.search(self.root, lang="en", runner=FakeNpm(self.pe, "0.10.0", b"", latest="0.11.0-beta.1").run)
        self.assertEqual(s["result"]["result"], "prerelease")
        self.assertIn("not proposed by default", s["summary"]["text"])
        s = pinets_guide.search(self.root, lang="fr", runner=FakeNpm(self.pe, "0.10.0", b"", latest="0.10.0").run)
        self.assertEqual(s["result"]["result"], "up-to-date")
        s = pinets_guide.search(self.root, lang="fr", runner=self.npm.run)
        self.assertEqual(s["result"]["result"], "update-available")
        self.assertIn(i18n.t("ptg.next.prepare", "fr", latest="0.10.1"), s["summary"]["next"])

    def test_preparation_verifies_archive_licence_prerequisites_and_changes_without_installing(self):
        before = self.engine_bytes()
        releases = [{"tag_name": "v0.10.1", "draft": False, "prerelease": False, "body": "",
                     "published_at": "2026-10-01T00:00:00Z"},
                    {"tag_name": "v0.10.0", "draft": False, "prerelease": False, "body": "older"},
                    {"tag_name": "v0.11.0", "draft": False, "prerelease": False, "body": "newer than the target"}]
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=github_with(releases),
                                 dest=self.dl)
        self.assertTrue(p["applicable"], p["problems"])
        self.assertEqual(self.engine_bytes(), before)                       # nothing installed
        plan = p["plan"]
        self.assertEqual(plan["target"]["registry_integrity"], sri(self.tgz))
        self.assertEqual(plan["target"]["artifact_sha256"], hashlib.sha256(self.artifact).hexdigest())
        self.assertTrue(plan["license"]["text_identical"])
        self.assertEqual([r["tag"] for r in plan["changes"]["releases"]], ["v0.10.1"])
        sm = p["summary"]
        self.assertEqual(sm["confirm"]["question"], "Appliquer ce plan ?")
        self.assertTrue(any("v0.10.1" in n and "Aucune note" in n for n in sm["notes"]))
        self.assertIn(i18n.t("ptg.limit.version", "fr"), sm["limits"])
        self.assertTrue(any("compatibilité n'est PAS établie" in c for c in sm["change"]))
        # changes unavailable: said so, nothing inferred
        p2 = pinets_guide.prepare(self.root, "0.10.1", lang="en", runner=self.npm.run, http=no_github,
                                  dest=self.dl.parent / "dl2")
        self.assertTrue(any("unavailable" in n for n in p2["summary"]["notes"]))

    def test_refusals_before_anything_is_installed(self):
        before = self.engine_bytes()
        cases = [
            ("0.9.0", self.npm, "older than the pin"),
            ("0.10.0", self.npm, "equals the current pin"),
            ("latest", self.npm, "exact version"),
            ("0.10.1", FakeNpm(self.pe, "0.10.1", self.tgz, integrity="sha512-" + "A" * 86 + "=="), "integrity differs"),
            ("0.10.1", FakeNpm(self.pe, "0.10.1", build_tgz("0.10.1", self.artifact, spdx="MIT")), "licence"),
            ("0.10.1", FakeNpm(self.pe, "0.10.1", build_tgz("0.10.1", self.artifact, exports=False,
                                                           extra={"package/../evil": b"x"})), "unsafe"),
        ]
        for i, (target, npm, expected) in enumerate(cases):
            p = pinets_guide.prepare(self.root, target, lang="fr", runner=npm.run, http=no_github,
                                     dest=self.dl.parent / ("case%d" % i))
            self.assertFalse(p["applicable"], target)
            self.assertIn(expected, " ".join(p["problems"]), (target, p["problems"]))
        lic = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=cases[4][1].run, http=no_github,
                                   dest=self.dl.parent / "lic")
        self.assertTrue(lic["decision_required"])
        self.assertIn("Décision de votre part", lic["summary"]["headline"])
        no_search = pinets_guide.prepare(self.root, None, lang="fr", runner=self.npm.run, dest=self.dl)
        self.assertIn("no dated search", no_search["problems"][0])
        self.assertEqual(self.engine_bytes(), before)

    def test_apply_refuses_a_changed_engine_a_changed_archive_or_a_tampered_plan(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        self.assertTrue(p["applicable"])
        before = self.engine_bytes()
        r = pinets_guide.apply(self.root, p["plan_file"], yes=False, lang="fr")
        self.assertEqual(r["status"], "refused-before-mutation")
        tgz = Path(p["plan"]["target"]["archive"])
        tgz.write_bytes(self.tgz + b"x")
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("archive", r["error"])
        tgz.write_bytes(self.tgz)
        doc = json.loads(Path(p["plan_file"]).read_text(encoding="utf-8"))
        doc["recalibration"]["included"] = False
        Path(p["plan_file"]).write_text(json.dumps(doc), encoding="utf-8")
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="en", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("modified since it was written", r["error"])
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github,
                                 dest=self.dl.parent / "again")
        calib = self.pe / "calibration" / "capabilities.json"
        calib.write_text(calib.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        before = self.engine_bytes()
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("rien n'a été modifié", r["summary"]["headline"])
        self.assertEqual(self.engine_bytes(), before)

    def test_backup_impossible_installs_nothing(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        before = self.engine_bytes()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        rb = self.root / tooling.ROLLBACK_REL
        rb.parent.mkdir(parents=True, exist_ok=True)
        rb.symlink_to(outside, target_is_directory=True)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation", r)
        self.assertEqual(self.engine_bytes(), before)
        self.assertNotIn("install", [c[1] for c in self.npm.calls if len(c) > 1 and c[0] == "npm" and c[1] == "install"])

    def test_npm_failure_after_the_point_is_an_honest_install_failed_account(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr",
                               npm_runner=self.npm.installer(fail_at="ci"))
        self.assertEqual(r["status"], "install-failed")
        self.assertEqual(r["rollback_point"], "0.10.0")
        sm = r["summary"]
        self.assertIn("ÉCHEC", sm["headline"])
        self.assertTrue(any("pinets rollback 0.10.0 --yes" in line for line in sm["recovery"]))
        self.assertTrue(any("pin 0.10.1" in line for line in sm["changed"]))      # what really is on disk now
        self.assertNotIn("rien n'a été modifié", sm["text"])

    def test_engine_obtained_different_from_the_plan_is_a_verification_failure(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl,
                                 recalibrate=False)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="en",
                               npm_runner=self.npm.installer(wrong_artifact=True))
        self.assertEqual(r["status"], "verification-failed", r.get("error"))
        self.assertFalse(r["identity"]["artifact_sha256"])
        self.assertTrue(any("pinets rollback 0.10.0" in line for line in r["summary"]["recovery"]))

    def test_installation_without_recalibration_leaves_calibrations_stale(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl,
                                 recalibrate=False)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual((r["status"], r["ok"]), ("installed-verified", True), r.get("error"))
        caps = json.loads((self.pe / "calibration" / "capabilities.json").read_text(encoding="utf-8"))["capabilities"]
        self.assertEqual(caps["math-arith"]["calibration_status"], "STALE")
        self.assertEqual(caps["math-arith"]["capability_status"], "EXPERIMENTAL")
        self.assertIn(i18n.t("ptg.next.recal_later", "fr"), r["summary"]["next"])


class TestCorrectionsAfterVerification(TestPinetsGuideWithoutEngine):
    """Corrections after the independent verification of the 2.2.0 delivery:
    numeric comparisons, run report coherence, plan bound to the recalibration
    contract (checked again under the shared lock), licence text changes."""

    def test_comparisons_refuse_non_finite_invalid_and_missing_values(self):
        rel, exact = {"mode": "relative", "tolerance": 1e-10}, {"mode": "exact"}
        cp = recalibration.compare_points
        for bad in (float("nan"), float("inf"), float("-inf"), "100", True, [1]):
            self.assertEqual(cp([{"t": 1, "v": bad}], [{"t": 1, "v": 100.0}], rel)[0], "invalid", bad)
            self.assertEqual(cp([{"t": 1, "v": 100.0}], [{"t": 1, "v": bad}], rel)[0], "invalid", bad)
            self.assertEqual(cp([{"t": 1, "v": bad}], [{"t": 1, "v": 100.0}], exact)[0], "invalid", bad)
        self.assertEqual(cp([{"t": 1}], [{"t": 1, "v": 1.0}], rel)[0], "invalid")             # field absent
        self.assertEqual(cp([{"t": True, "v": 1.0}], [{"t": 1, "v": 1.0}], rel)[0], "invalid")  # bool timestamp
        self.assertEqual(cp([{"t": 2, "v": 1.0}], [{"t": 1, "v": 1.0}], rel)[0], "mismatch")
        self.assertEqual(cp([{"t": 1, "v": None}], [{"t": 1, "v": None}], rel)[0], "ok")       # na allowed both sides
        self.assertEqual(cp([{"t": 1, "v": None}], [{"t": 1, "v": 1.0}], rel)[0], "mismatch")
        for tol in (float("nan"), float("inf"), 0, -1e-9, "1e-9", None):
            self.assertEqual(cp([{"t": 1, "v": 1.0}], [{"t": 1, "v": 1.0}], {"mode": "relative", "tolerance": tol})[0],
                             "invalid", tol)
        self.assertEqual(cp([{"t": 1, "v": 100.0}], [{"t": 1, "v": 100.0 * (1 + 2e-9)}],
                            {"mode": "relative", "tolerance": 1e-9})[0], "mismatch")             # never relaxed
        self.assertEqual(cp(None, [], rel)[0], "invalid")
        self.assertEqual(recalibration.compare_series([{"t": 1, "v": float("nan")}], [{"t": 1, "v": 100}], rel)[0],
                         False)

    def test_run_reports_are_checked_against_the_runner_contract_and_this_execution(self):
        h = "a" * 64
        expect = {"pinets_version": "0.10.0", "normalization_schema": "pws-pinets-norm-v2",
                  "executor_fingerprint": h, "source_sha256": h, "dataset_sha256": h}
        good = {"schema": "pws-pinets-run-v1", "execution_status": "PINETS_EXECUTION_PASS", "pinets_version": "0.10.0",
                "normalization_schema": "pws-pinets-norm-v2", "executor_fingerprint": h, "source_sha256": h,
                "dataset_sha256": h, "unclassified_tokens": [], "capabilities_used": {}, "normalized": {"plots": {}}}
        chk = recalibration.check_run_report
        self.assertEqual(chk(good, 0, expect), ("pass", None))
        self.assertEqual(chk(dict(good, execution_status="PINETS_EXECUTION_FAIL"), 1, expect)[0], "fail")
        bad = [(good, 1), (dict(good, execution_status="PINETS_EXECUTION_FAIL"), 0), (good, 5), (good, None),
               (dict(good, pinets_version="999.0.0"), 0), (dict(good, normalization_schema="invented-schema"), 0),
               (dict(good, executor_fingerprint="b" * 64), 0), (dict(good, source_sha256="b" * 64), 0),
               (dict(good, dataset_sha256="b" * 64), 0), (dict(good, unclassified_tokens=["x"]), 0),
               (dict(good, normalized={}), 0), (dict(good, schema="other"), 0), (dict(good, pinets_version=None), 0),
               (dict(good, capabilities_used=[]), 0), (dict(good, executor_fingerprint="short"), 0)]
        for doc, rc in bad:
            self.assertEqual(chk(doc, rc, expect)[0], "unusable", (rc, {k: doc[k] for k in doc if doc[k] != good.get(k)}))
        missing = dict(good)
        del missing["normalization_schema"]
        self.assertEqual(chk(missing, 0, expect)[0], "unusable")
        self.assertEqual(chk(good, 0, dict(expect, pinets_version=None))[0], "unusable")     # unknown engine
        self.assertEqual(recalibration.expected_schema(ROOT), "pws-pinets-norm-v2")           # read from the adapter

    def test_a_contract_or_artifact_changed_after_the_plan_refuses_before_any_installation(self):
        for target in ("comparisons.json", "cases/calib-core.expected.json", "datasets/lcg-42-60.json",
                       "cases/calib-core.pine"):
            p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github,
                                     dest=self.dl.parent / ("dl-" + target.replace("/", "-")))
            self.assertTrue(p["applicable"], p["problems"])
            self.assertEqual(p["plan"]["recalibration"]["binding"]["cases"], ["calib-core"])
            f = self.pe / "calibration" / target
            original = f.read_bytes()
            f.write_bytes(original + b" ")
            before = self.engine_bytes()
            self.npm.calls.clear()
            r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
            self.assertEqual((r["status"], r["ok"]), ("refused-before-mutation", False), target)
            self.assertIn("recalibration contract", r["error"])
            self.assertEqual([c for c in self.npm.calls if c[:1] == ["npm"]], [], target)       # no npm call at all
            self.assertEqual(self.engine_bytes(), before, target)
            f.write_bytes(original)
        # removed artifact
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github,
                                 dest=self.dl.parent / "dl-removed")
        (self.pe / "calibration" / "comparisons.json").rename(self.pe / "calibration" / "comparisons.moved")
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation")
        (self.pe / "calibration" / "comparisons.moved").rename(self.pe / "calibration" / "comparisons.json")

    def test_the_plan_is_checked_again_under_the_shared_lock_before_the_first_change(self):
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        contract = self.pe / "calibration" / "comparisons.json"
        real_install = tooling.install

        def install_after_a_late_change(*args, **kwargs):     # the change lands after the first check
            contract.write_bytes(contract.read_bytes() + b" ")
            return real_install(*args, **kwargs)
        before = self.engine_bytes()
        self.npm.calls.clear()
        with mock.patch.object(pinets_guide.tooling, "install", install_after_a_late_change):
            r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation", r.get("error"))
        self.assertIn("refused before any change", r["error"])
        self.assertEqual([c for c in self.npm.calls if c[:1] == ["npm"]], [])
        after = self.engine_bytes()
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"calibration/comparisons.json"})          # only the test's own late change
        self.assertFalse((self.root / tooling.ROLLBACK_REL).exists())                     # not even a point

    def test_a_changed_licence_text_needs_an_explicit_decision_bound_to_that_text(self):
        other = build_tgz("0.10.1", self.artifact, license_text=b"AGPL text, with a new clause\n")
        npm = FakeNpm(self.pe, "0.10.1", other)
        before = self.engine_bytes()
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=npm.run, http=no_github, dest=self.dl)
        self.assertFalse(p["applicable"])
        self.assertIn("LICENSE text", p["decision_required"])
        self.assertIn("+AGPL text, with a new clause", p["license_text_diff"])
        new_sha = p["license_text_sha256"]
        self.assertIn("Décision de votre part", p["summary"]["headline"])
        wrong = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=npm.run, http=no_github,
                                     dest=self.dl.parent / "dl2", accept_license_text="0" * 64)
        self.assertFalse(wrong["applicable"])
        self.assertIn("does not cover this text", wrong["decision_required"])
        ok = pinets_guide.prepare(self.root, "0.10.1", lang="en", runner=npm.run, http=no_github,
                                  dest=self.dl.parent / "dl3", accept_license_text=new_sha)
        self.assertTrue(ok["applicable"], ok["problems"])
        dec = ok["plan"]["license"]["decision"]
        self.assertEqual((dec["version"], dec["spdx"], dec["text_sha256"]), ("0.10.1", "AGPL-3.0-only", new_sha))
        self.assertTrue(any("Licence decision recorded" in c for c in ok["summary"]["change"]))
        self.assertEqual((self.pe / "PINETS_LICENSE").read_bytes(), b"AGPL text\n")        # reference unchanged
        self.assertEqual(self.engine_bytes(), before)
        # a decision cannot be added to a plan afterwards (hash), nor a plan without it be applied
        doc = json.loads(Path(ok["plan_file"]).read_text(encoding="utf-8"))
        doc["license"]["decision"] = None
        Path(ok["plan_file"]).write_text(json.dumps(doc), encoding="utf-8")
        r = pinets_guide.apply(self.root, ok["plan_file"], yes=True, npm_runner=npm.installer())
        self.assertEqual(r["status"], "refused-before-mutation")
        # no recorded reference at all is never a validation
        (self.pe / "PINETS_LICENSE").unlink()
        p = pinets_guide.prepare(self.root, "0.10.1", lang="fr", runner=self.npm.run, http=no_github,
                                 dest=self.dl.parent / "dl4")
        self.assertFalse(p["applicable"])
        self.assertIn("no recorded copy", p["decision_required"])


@unittest.skipUnless(HAS_ENGINE, "PineTS engine or Node not installed here (fresh distribution)")
class TestPinetsGuideRealEngine(unittest.TestCase):
    """The adapter and its INSTALLED engine copied into a temporary workspace:
    the real runner executes the calibration case."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # real path: the doctor's fingerprint call does not resolve a symlinked parent (macOS /var → /private/var)
        self.root = helpers.make_workspace(os.path.realpath(self.tmp.name))
        helpers.configure(self.root, language="fr")
        self.pe = self.root / "tools" / "pine_exec"
        shutil.copytree(str(REAL_PE), str(self.pe), symlinks=True)
        self.artifact = (self.pe / tooling.ARTIFACT_REL).read_bytes()
        lic = (self.pe / "node_modules" / "pinets" / "LICENSE").read_bytes()
        # a version strictly newer than the pinned engine, whatever engine is installed here
        self.pin = tooling.engine_identity(self.root)["pinned_version"]
        major, minor, patch = (int(x) for x in self.pin.split("-")[0].split("."))
        self.target = "%d.%d.%d" % (major, minor, patch + 100)
        self.tgz = build_tgz(self.target, self.artifact, license_text=lic)
        self.npm = FakeNpm(self.pe, self.target, self.tgz)
        self.dl = Path(self.tmp.name) / "download"
        self.calib = self.pe / "calibration" / "capabilities.json"

    def tearDown(self):
        self.tmp.cleanup()

    def caps(self):
        return json.loads(self.calib.read_text(encoding="utf-8"))

    def test_successful_update_with_recalibration_marks_current_only_what_was_re_exercised(self):
        p = pinets_guide.prepare(self.root, self.target, lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        self.assertTrue(p["applicable"], p["problems"])
        self.assertEqual(p["plan"]["recalibration"]["cases"], ["calib-core"])
        expected_before = (self.pe / "calibration" / "cases" / "calib-core.expected.json").read_bytes()
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer())
        self.assertEqual((r["status"], r["ok"]), ("completed", True), json.dumps(r.get("recalibration"), indent=1)[:2000])
        rec = r["recalibration"]
        self.assertEqual(rec["cases"]["calib-core"]["verdict"], "concordant")
        data = self.caps()
        self.assertEqual(data["environment"]["pinets_version"], self.target)
        self.assertEqual(data["environment"]["executor_fingerprint"], rec["executor_fingerprint"])
        self.assertTrue(all(v["calibration_status"] == "CURRENT" for v in data["capabilities"].values()))
        self.assertTrue(all(v["capability_status"] == "EXPERIMENTAL" for v in data["capabilities"].values()))
        self.assertEqual(data["capabilities"]["ta-ema"]["known_divergences"][0][:20], "Convention de seed :")
        self.assertEqual((self.pe / "calibration" / "cases" / "calib-core.expected.json").read_bytes(),
                         expected_before)                                   # reference never rewritten
        results = Path(rec["results_dir"])
        persisted = json.loads((results / "COMPARISON.json").read_text(encoding="utf-8"))
        self.assertEqual((persisted["status"], persisted["calibration_written"], persisted["calibration_verified"]),
                         ("recalibrated", True, True))
        self.assertTrue((results / "calib-core.run.json").is_file())
        self.assertTrue((results / "capabilities.before.json").is_file())
        self.assertEqual(data["history"][-1]["event"], "guided recalibration")
        # the runner itself now derives the calibration as CURRENT for this engine
        st = {f["check"]: f["status"] for f in tooling.verify(self.root)}
        self.assertEqual((st["calibration-version"], st["fingerprint"]), ("OK", "OK"))
        self.assertIn("recalibré", r["summary"]["headline"])
        self.assertIn(i18n.t("ptg.done.gating", "fr"), r["summary"]["changed"])

    def test_divergent_recalibration_leaves_capabilities_stale_and_asks_for_a_decision(self):
        contract = self.pe / "calibration" / recalibration.CONTRACT_NAME
        doc = json.loads(contract.read_text(encoding="utf-8"))
        doc["cases"]["calib-core"]["series"]["EMA5"] = {"reference": "EMA5_first_value_seed", "mode": "exact"}
        contract.write_text(json.dumps(doc), encoding="utf-8")       # a comparison the engine is known to fail
        p = pinets_guide.prepare(self.root, self.target, lang="en", runner=self.npm.run, http=no_github, dest=self.dl)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="en", npm_runner=self.npm.installer())
        self.assertEqual((r["status"], r["ok"]), ("recalibration-divergent", False))
        self.assertEqual(r["recalibration"]["cases"]["calib-core"]["series"]["EMA5"]["ok"], False)
        self.assertTrue(all(v["calibration_status"] == "STALE" for v in self.caps()["capabilities"].values()))
        self.assertFalse(r["recalibration"]["calibration_written"])
        self.assertIn(i18n.t("ptg.next.decide", "en"), r["summary"]["next"])
        self.assertTrue(any("EMA5" in line for line in r["summary"]["result"]))

    def crafted(self, modify, rc=0):
        def run(pe, args, timeout=300):
            if args[0] != "runner.mjs":
                return recalibration._node_run(pe, args, timeout)
            rrc, o, e = recalibration._node_run(pe, args, timeout)
            out = Path(args[args.index("--out") + 1])
            doc = json.loads(out.read_text(encoding="utf-8"))
            modify(doc)
            out.write_text(json.dumps(doc), encoding="utf-8")
            return rc, o, e
        return run

    def test_a_report_without_identity_fields_never_gives_a_completed_update(self):
        p = pinets_guide.prepare(self.root, self.target, lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer(),
                               node_runner=self.crafted(lambda d: (d.pop("pinets_version"),
                                                                   d.pop("normalization_schema"))))
        self.assertEqual((r["status"], r["ok"]), ("recalibration-incomplete", False))
        rec = r["recalibration"]
        self.assertEqual((rec["status"], rec["calibration_written"], rec["current"]), ("incomplete", False, []))
        self.assertIn("pinets_version", rec["cases"]["calib-core"]["problem"])
        self.assertTrue(all(v["calibration_status"] == "STALE" for v in self.caps()["capabilities"].values()))
        persisted = json.loads((Path(rec["results_dir"]) / "COMPARISON.json").read_text(encoding="utf-8"))
        self.assertEqual((persisted["status"], persisted["calibration_written"]), ("incomplete", False))
        self.assertNotIn("recalibré", r["summary"]["headline"])

    def test_an_incoherent_report_never_promotes_a_capability(self):
        before = self.calib.read_bytes()

        def invent(d):
            d["pinets_version"], d["normalization_schema"] = "999.0.0", "invented-schema"
        for modify, rc, expected in ((invent, 1, "contradicts"), (lambda d: None, 1, "contradicts"),
                                     (lambda d: d.update(pinets_version="999.0.0"), 0, "999.0.0"),
                                     (lambda d: d.update(normalization_schema="invented-schema"), 0, "invented-schema"),
                                     (lambda d: d.update(executor_fingerprint="b" * 64), 0, "fingerprint"),
                                     (lambda d: d.update(dataset_sha256="b" * 64), 0, "dataset")):
            rec = recalibration.run(self.root, node_runner=self.crafted(modify, rc))
            self.assertEqual((rec["status"], rec["calibration_written"], rec["current"]), ("incomplete", False, []))
            self.assertIn(expected, rec["cases"]["calib-core"]["problem"])
            self.assertEqual(self.calib.read_bytes(), before)

    def test_a_failed_write_of_the_calibrations_is_never_a_success(self):
        p = pinets_guide.prepare(self.root, lang="fr", recalibrate_only=True)
        real = core.atomic_write_json

        def failing(path, data):
            if Path(path).name == "capabilities.json":
                raise OSError("simulated disk full")
            return real(path, data)
        with mock.patch.object(recalibration.core, "atomic_write_json", failing):
            r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr")
        self.assertEqual((r["status"], r["ok"]), ("recal-only-incomplete", False))
        rec = r["recalibration"]
        self.assertEqual(rec["cases"]["calib-core"]["verdict"], "concordant")
        self.assertFalse(rec["calibration_written"])
        self.assertTrue(any("could not be written" in pr for pr in rec["problems"]))
        persisted = json.loads((Path(rec["results_dir"]) / "COMPARISON.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "incomplete")

    def test_recalibration_only_is_refused_when_its_contract_changed_and_checks_the_engine_under_the_lock(self):
        p = pinets_guide.prepare(self.root, lang="fr", recalibrate_only=True)
        before = self.calib.read_bytes()
        contract = self.pe / "calibration" / recalibration.CONTRACT_NAME
        original = contract.read_bytes()
        contract.write_bytes(original + b" ")
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr")
        self.assertEqual((r["status"], r["ok"]), ("refused-before-mutation", False))
        self.assertEqual(self.calib.read_bytes(), before)
        contract.write_bytes(original)
        # an engine changed between its verification and the recalibration is never recalibrated
        report = {"verified_engine": {"pinned": "other"}, "plan": {}, "kind": "install"}
        out = pinets_guide._recalibrate_stage(self.root, json.loads(Path(p["plan_file"]).read_text()), report,
                                              "fr", None, installed=True)
        self.assertEqual((out["status"], out.get("ok")), ("recalibration-incomplete", None))
        self.assertEqual(self.calib.read_bytes(), before)

    def test_incomplete_recalibration_is_never_a_success(self):
        def broken_runner(pe, args, timeout=300):
            if args[0] == "runner.mjs":
                return 5, "", "simulated infrastructure error"
            return recalibration._node_run(pe, args, timeout)
        p = pinets_guide.prepare(self.root, self.target, lang="fr", runner=self.npm.run, http=no_github, dest=self.dl)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr", npm_runner=self.npm.installer(),
                               node_runner=broken_runner)
        self.assertEqual((r["status"], r["ok"]), ("recalibration-incomplete", False))
        self.assertTrue(any("calib-core" in line for line in r["summary"]["result"]))

    def test_recalibration_only_plan_of_the_current_engine(self):
        before = self.calib.read_bytes()
        p = pinets_guide.prepare(self.root, lang="fr", recalibrate_only=True)
        self.assertTrue(p["applicable"], p["problems"])
        self.assertEqual(self.calib.read_bytes(), before)
        r = pinets_guide.apply(self.root, p["plan_file"], yes=True, lang="fr")
        self.assertEqual((r["status"], r["ok"]), ("recalibrated", True), json.dumps(r.get("recalibration"))[:1500])
        self.assertEqual(self.caps()["environment"]["pinets_version"], self.pin)


if __name__ == "__main__":
    unittest.main()
