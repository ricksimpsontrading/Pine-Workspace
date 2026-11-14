# SPDX-License-Identifier: Apache-2.0
"""Guided update of Pine Workspace (2026-11-08): version sources, explicit
release search with deterministic SIMULATED answers (never a real query),
archive safety, fetch/prepare verification, plan bound by a hash, apply
orchestrating `upgrade` then `migrate` run by the new code, refusals without
mutation, failure recovery through the existing guarantees, development
upstream refusal, release artefacts, menu entries in both languages.

Fixtures only: isolated installations with fictitious identities, a package
of THIS core (v1) and a package declared 9.9.9 (v2) whose own version.py says
9.9.9 — the real project version is never changed."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.pws_workspace import (config, core, distribution, doctor, i18n, menu, migration, release, session, update,
                                 upgrade, version)
from tools.tests import helpers
from tools.tests.test_upgrade import _install

ROOT = core.workspace_root()
REPO = version.OFFICIAL_REPOSITORY
V1 = version.WORKSPACE_VERSION
V2 = "9.9.9"
ZIP2 = version.package_name(V2) + ".zip"
ASSET_NAMES = (ZIP2, ZIP2 + ".sha256", update.RELEASE_JSON, update.RELEASE_NOTES)


def tree(base):
    """Hashes of an installation, without its ephemeral runtime and bytecode."""
    base = Path(base)
    return {p.relative_to(base).as_posix(): core.sha256_file(p) for p in base.rglob("*")
            if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
            and not p.relative_to(base).as_posix().startswith(".claude/runtime/")}


def build_fixtures(base):
    """pkg v1 (this core), pkg v2 declared 9.9.9 (its version.py says 9.9.9, a
    skill changed, a document added, a rule retired, a CHANGELOG entry) and the
    release artefacts of v2 written with the production artefact writer."""
    pkg1, pkg2 = base / "pkg v1", base / "pkg v2"
    r = distribution.build(ROOT, pkg1)
    assert r["ok"] and r["clean"], r
    shutil.copytree(str(pkg1), str(pkg2))
    vp = pkg2 / "tools" / "pws_workspace" / "version.py"
    text = vp.read_text(encoding="utf-8")
    assert 'WORKSPACE_VERSION = "%s"' % V1 in text
    vp.write_text(text.replace('WORKSPACE_VERSION = "%s"' % V1, 'WORKSPACE_VERSION = "%s"' % V2), encoding="utf-8")
    skill = pkg2 / ".claude" / "skills" / "pine-docs" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nNouvelle étape.\n", encoding="utf-8")
    (pkg2 / "docs" / "architecture" / "NEW_DOC.md").write_text("# New\n", encoding="utf-8")
    (pkg2 / ".claude" / "rules" / "research.md").unlink()
    (pkg2 / "VERSION").write_text(V2 + "\n", encoding="utf-8")
    changelog = pkg2 / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [%s] — Fixture release (2026-11-08)\n\n- fixture change for the tests\n\n"
                         "### Limits\n\n- fixture limit\n\n" % V2 + changelog.read_text(encoding="utf-8").split("\n", 2)[2],
                         encoding="utf-8")
    distribution.write_marker(pkg2, V2)
    assets = base / "assets v2"
    art = release.write_artefacts(pkg2, assets, V2, changelog_text=changelog.read_text(encoding="utf-8"),
                                  git={"commit": "fixture", "dirty": False})
    assert art["ok"], art
    return pkg1, pkg2, assets


def api_release(tag, assets_dir=None, prerelease=False, draft=False, body="", repo=REPO):
    """One entry of the GitHub releases API, as the deterministic simulation serves it."""
    ver = version.normalized(tag) or tag
    names = (version.package_name(ver) + ".zip", version.package_name(ver) + ".zip.sha256",
             update.RELEASE_JSON, update.RELEASE_NOTES) if assets_dir else ()
    return {"tag_name": tag, "name": tag, "draft": draft, "prerelease": prerelease,
            "published_at": "2026-11-08T00:00:00Z", "html_url": "https://github.com/%s/releases/tag/%s" % (repo, tag),
            "body": body,
            "assets": [{"name": n, "browser_download_url": update.DOWNLOAD_PREFIX % (repo, tag) + n,
                        "size": (assets_dir / n).stat().st_size if (assets_dir / n).exists() else 0} for n in names]}


def simulated(entries):
    return lambda url: (200, entries, None)


def network_error(url):
    return None, None, "URLError: <simulated: no network>"


def local_downloader(assets_dir):
    def download(url, dest):
        shutil.copy2(str(assets_dir / url.rsplit("/", 1)[1]), str(dest))
    return download


class TestVersionSources(unittest.TestCase):
    def test_semver_parsing_comparison_and_prereleases(self):
        self.assertEqual(version.parse_version("v2.1.0"), (2, 1, 0, None))
        self.assertEqual(version.parse_version("2.2.0-rc.1")[3], "rc.1")
        for bad in ("2.1", "v2", "2.1.0.1", "latest", "", None, "2.01.0"):
            self.assertIsNone(version.parse_version(bad), bad)
        self.assertEqual(version.compare("2.10.0", "2.9.0"), 1)          # numeric, not lexical
        self.assertEqual(version.compare("v2.1.0", "2.1.0"), 0)
        self.assertEqual(version.compare("2.1.0-rc.1", "2.1.0"), -1)      # pre-release ranks below
        self.assertIsNone(version.compare("x", "2.1.0"))
        self.assertTrue(version.is_prerelease("3.0.0-beta"))
        self.assertFalse(version.is_prerelease(V1))
        self.assertEqual(version.release_tag(), "v" + V1)
        self.assertEqual(version.package_name("9.9.9"), "pine-workspace-9.9.9")

    def test_version_sources_agree_and_steps_are_declared(self):
        self.assertEqual(release.changelog_top_version(ROOT), V1)
        self.assertTrue(release.check_consistency(ROOT)["ok"], release.check_consistency(ROOT))
        source = (ROOT / "tools" / "pws_workspace" / "migration.py").read_text(encoding="utf-8")
        ids_in_code = set(re.findall(r'"id": "(m\d{3}-[a-z0-9-]+)"', source))
        self.assertEqual(ids_in_code, set(migration.STEP_IDS))
        results = {r["check"]: r for r in __import__("tools.pws_workspace.doctor", fromlist=["run_doctor"]).run_doctor(ROOT)}
        self.assertEqual(results["version-sources"]["severity"], "OK", results["version-sources"])


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, language="fr")

    def tearDown(self):
        self.tmp.cleanup()

    def test_before_any_search_the_state_is_not_searched(self):
        st = update.status(self.root)
        self.assertEqual(st["last_check"]["result"], "not-searched")
        self.assertIsNone(st["last_check"]["checked_at"])
        self.assertEqual(st["installation"]["kind"], "development")
        self.assertEqual(st["official_repository"], REPO)

    def test_update_available_up_to_date_no_release_and_error_never_mean_up_to_date_by_default(self):
        rec = update.check(self.root, fetch=simulated([api_release("v9.9.9"), api_release("v" + V1)]))
        self.assertEqual((rec["result"], rec["latest"]["version"], rec["source"]), ("update-available", "9.9.9", "simulated"))
        self.assertTrue(rec["checked_at"])
        self.assertEqual(update.read_check(self.root)["result"], "update-available")   # dated record kept
        self.assertEqual(update.check(self.root, fetch=simulated([api_release("v" + V1)]))["result"], "up-to-date")
        self.assertEqual(update.check(self.root, fetch=simulated([]))["result"], "no-release")
        err = update.check(self.root, fetch=network_error)
        self.assertEqual(err["result"], "error")
        self.assertIn("simulated: no network", err["error"])
        self.assertEqual(update.read_check(self.root)["result"], "error")              # an error is recorded as such
        self.assertEqual(update.check(self.root, fetch=lambda u: (404, None, "HTTP 404"))["result"], "error")
        self.assertEqual(update.check(self.root, fetch=simulated([api_release("v1.0.0")]))["result"], "ahead")

    def test_prereleases_and_drafts_are_skipped_and_versions_compare_numerically(self):
        rec = update.check(self.root, fetch=simulated([api_release("v10.0.0-rc.1", prerelease=True),
                                                        api_release("v12.0.0", draft=True)]))
        self.assertEqual((rec["result"], rec["prereleases_skipped"], rec["drafts_skipped"]), ("no-release", 1, 1))
        rec = update.check(self.root, fetch=simulated([api_release("v10.0.0-rc.1", prerelease=True)]),
                           include_prereleases=True)
        self.assertEqual((rec["result"], rec["latest"]["prerelease"]), ("update-available", True))
        rec = update.check(self.root, fetch=simulated([api_release("v2.9.0"), api_release("v2.10.0"),
                                                        api_release("not-a-version")]))
        self.assertEqual(rec["latest"]["version"], "2.10.0")
        self.assertEqual(rec["unparsable_tags"], ["not-a-version"])


class TestArchiveSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_zip(self, entries, name="bad.zip"):
        path = self.base / name
        with zipfile.ZipFile(str(path), "w") as z:
            for entry, data in entries:
                if isinstance(entry, zipfile.ZipInfo):
                    z.writestr(entry, data)
                else:
                    z.writestr(entry, data)
        return path

    def test_dangerous_archives_are_refused_before_any_extraction(self):
        link = zipfile.ZipInfo("pkg/link")
        link.external_attr = (0o120777 << 16)
        cases = {
            "traversal": [("pkg/PWS_DISTRIBUTION.json", "{}"), ("pkg/../evil.txt", "x")],
            "absolute": [("/abs/file", "x")],
            "symlink": [("pkg/PWS_DISTRIBUTION.json", "{}"), (link, "/etc/passwd")],
            "two tops": [("a/x", "x"), ("b/y", "y")],
            "backslash": [("pkg\\x", "x")],
        }
        for label, entries in cases.items():
            path = self.make_zip(entries, name=label.replace(" ", "-") + ".zip")
            ok, problems, _top, _infos = update.inspect_archive(path)
            self.assertFalse(ok, label)
            self.assertTrue(problems, label)
            dest = self.base / ("out " + label)
            pkg, problems = update.unpack_package(path, dest)
            self.assertIsNone(pkg, label)
            self.assertFalse(dest.exists(), "%s: nothing may be extracted" % label)

    def test_archive_without_a_valid_manifest_is_refused(self):
        path = self.make_zip([("pkg/README.md", "x"), ("pkg/PWS_DISTRIBUTION.json", "not json")])
        pkg, problems = update.unpack_package(path, self.base / "out")
        self.assertIsNone(pkg)
        self.assertTrue(any("PWS_DISTRIBUTION.json" in p for p in problems), problems)


class InstalledFixture(unittest.TestCase):
    """A real installation built from package v1 (fresh per test), the fixture
    package 9.9.9 and its release artefacts — shared by the flow and verdict
    tests below; carries no test of its own."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.pkg1, cls.pkg2, cls.assets = build_fixtures(Path(cls.shared.name))

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.install = base / "My Pine Workspace"
        self.home = base / "isolated home"
        self.home.mkdir()
        _install(self.pkg1, self.install, self.home)             # fictitious identity, French
        helpers.make_product_v3(self.install, slug="user-prod", profile="FREE")
        (self.install / "docs" / "maintenance").mkdir(parents=True)
        (self.install / "docs" / "maintenance" / "note.md").write_text("preuve\n", encoding="utf-8")
        (self.install / ".claude" / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}}), encoding="utf-8")
        self.dl = base / "download"

    def tearDown(self):
        self.tmp.cleanup()

    def prepared_plan(self, body=""):
        rec = update.check(self.install, fetch=simulated([api_release("v" + V2, self.assets, body=body)]))
        self.assertEqual(rec["result"], "update-available", rec)
        fetched = update.fetch_release(self.install, downloader=local_downloader(self.assets), dest=self.dl)
        self.assertTrue(fetched["ok"], fetched["problems"])
        self.assertTrue(fetched["simulated"])
        self.assertFalse(core.is_within(self.install, Path(fetched["download_dir"])))
        return update.plan(self.install, fetched["package_dir"])


class TestInstalledFlow(InstalledFixture):
    """Consultation, plan, apply, conflicts, local packages, provenance, upstream."""

    def test_status_of_a_distribution_installation(self):
        st = update.status(self.install)
        self.assertEqual((st["installation"]["kind"], st["installation"]["manifest_version"]), ("distribution", V1))
        self.assertEqual(st["last_check"]["result"], "not-searched")
        self.assertEqual(st["backups"], {"upgrade": [], "migration": []})

    def test_consultation_and_cancellation_never_mutate_the_installation(self):
        before = tree(self.install)
        p = self.prepared_plan(body="")
        self.assertTrue(p["applicable"], p["refusals"])
        self.assertEqual(tree(self.install), before)                 # check, fetch and plan wrote nothing
        self.assertTrue(Path(p["plan_file"]).is_file())              # only the plan record, under the runtime
        self.assertTrue(core.is_within(self.install / ".claude" / "runtime", Path(p["plan_file"])))
        self.assertEqual((p["current_version"], p["target_version"], p["origin"], p["direction"]),
                         (V1, V2, "github-release", "upgrade"))
        self.assertIn("authenticity not proven", p["provenance"])
        self.assertIn("fixture change for the tests", p["changes"])   # notes asset of the release
        self.assertIn("m004-record-workspace-version", p["migrations_may_apply"])
        self.assertEqual(p["upgrade"]["conflicts"], [])
        self.assertIn(".claude/rules/research.md", p["upgrade"]["retired"])
        self.assertIn("docs/architecture/NEW_DOC.md", p["upgrade"]["changed"])
        self.assertEqual(p["rollback"][0]["command"], "python3 -m tools.pws_workspace migrate --rollback <stamp>")
        self.assertTrue(p["restart_required"])

    def test_apply_requires_the_confirmation_and_an_unchanged_plan(self):
        p = self.prepared_plan()
        before = tree(self.install)
        r = update.apply(self.install, p["plan_file"], yes=False)
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertEqual(tree(self.install), before)
        # the installation changes after the approval: the hash no longer matches
        (self.install / "docs" / "architecture" / "OPERATIONS.md").write_text("local edit\n", encoding="utf-8")
        r = update.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertIn("plan changed", r["error"])

    def test_successful_update_preserves_user_data_and_runs_the_planned_migrations(self):
        p = self.prepared_plan()
        self.assertTrue(p["applicable"], p["refusals"])
        r = update.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual(r["status"], "applied", json.dumps(r, indent=1)[:3000])
        self.assertTrue(r["ok"] and r["restart_required"])
        self.assertTrue(r["stages"]["upgrade"]["ok"])
        self.assertIn("m004-record-workspace-version", r["stages"]["migrate"]["applied"])
        self.assertEqual(r["stages"]["migrate"]["unplanned"], [])
        self.assertEqual(r["stages"]["migrate"]["blocked"], [])
        self.assertTrue(r["stages"]["verify"]["ok"], r["stages"]["verify"])
        self.assertEqual((r["stages"]["doctor"]["verdict"], r["stages"]["doctor"]["rc"], r["stages"]["doctor"]["blocking"]),
                         ("ok", 0, []))
        self.assertIn("counts", r["stages"]["doctor"])
        self.assertEqual(r["done"], {"code_installed": True, "code_verified": True,
                                     "migrations_applied": ["m004-record-workspace-version"], "migrations_remaining": [],
                                     "migrations_blocked": [], "diagnostic": "ok", "kept_local": []})
        self.assertEqual(r["next_action"], update.RESTART_NOTE)
        self.assertEqual(upgrade.installed_manifest(self.install)[0]["version"], V2)
        cfg = config.read_config(self.install)["data"]
        self.assertEqual((cfg["workspace_version"], cfg["language"]), (V2, "fr"))      # migrated by the NEW code
        self.assertEqual(config.identity(self.install)["copyright_holder"], "Holder Test")
        self.assertTrue((self.install / "scripts" / "user-prod" / "SCRIPT.json").is_file())
        self.assertEqual((self.install / "docs" / "maintenance" / "note.md").read_text(encoding="utf-8"), "preuve\n")
        self.assertEqual(json.loads((self.install / ".claude" / "settings.local.json").read_text(encoding="utf-8")),
                         {"permissions": {"allow": ["Bash(ls:*)"]}})
        self.assertTrue((self.install / "docs" / "architecture" / "NEW_DOC.md").is_file())
        self.assertFalse((self.install / ".claude" / "rules" / "research.md").exists())
        self.assertIn("Nouvelle étape.", (self.install / ".claude" / "skills" / "pine-docs" / "SKILL.md").read_text(encoding="utf-8"))
        info = update.rollback_info(self.install)
        self.assertEqual(len(info["upgrade_backups"]), 1)
        self.assertEqual((info["upgrade_backups"][0]["state"], info["upgrade_backups"][0]["to_version"]), ("applied", V2))
        self.assertEqual(len(info["migration_backups"]), 1)
        self.assertTrue(info["restores_nothing"])
        again = update.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual(again["status"], "refused-before-mutation")     # the approved plan is spent

    def test_local_conflict_is_shown_and_never_overwritten(self):
        skill = self.install / ".claude" / "skills" / "pine-docs" / "SKILL.md"
        local = skill.read_text(encoding="utf-8") + "\n- personnalisation locale\n"
        skill.write_text(local, encoding="utf-8")
        p = self.prepared_plan()
        self.assertFalse(p["applicable"])
        self.assertEqual(p["upgrade"]["conflicts"], [".claude/skills/pine-docs/SKILL.md"])
        self.assertTrue(any("locally modified" in x for x in p["refusals"]), p["refusals"])
        self.assertIsNone(p["plan_file"])                                 # nothing to approve: no plan file
        # a hand-made plan file for the same package cannot force it through
        forged = Path(self.tmp.name) / "forged.json"
        forged.write_text(json.dumps(dict(p, plan_hash=p["plan_hash"])), encoding="utf-8")
        before = tree(self.install)
        r = update.apply(self.install, forged, yes=True)
        self.assertEqual(r["status"], "refused-before-mutation")
        self.assertEqual(tree(self.install), before)
        self.assertEqual(skill.read_text(encoding="utf-8"), local)

    def test_unplanned_migration_stops_after_the_code_upgrade(self):
        pkg3 = Path(self.tmp.name) / "pkg v3"
        shutil.copytree(str(self.pkg2), str(pkg3))
        marker_path = pkg3 / distribution.MARKER
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["migrations"] = [m for m in marker["migrations"] if m != "m004-record-workspace-version"]
        marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
        prep = update.prepare_local(self.install, pkg3)
        self.assertTrue(prep["ok"], prep["problems"])
        p = update.plan(self.install, prep["package_dir"])
        self.assertTrue(p["applicable"], p["refusals"])
        self.assertNotIn("m004-record-workspace-version", p["migrations_may_apply"])
        r = update.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual(r["status"], "stopped-unplanned-migrations", json.dumps(r, indent=1)[:2000])
        self.assertEqual(r["stages"]["migrate"]["unplanned"], ["m004-record-workspace-version"])
        self.assertFalse(r["stages"]["migrate"]["applied"])
        self.assertEqual(upgrade.installed_manifest(self.install)[0]["version"], V2)   # code upgraded…
        self.assertEqual(config.read_config(self.install)["data"]["workspace_version"], V1)   # …data untouched
        self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())
        self.assertIn("code installed", r["error"])
        self.assertIn("outside the approved plan", r["error"])
        self.assertIn("upgrade --rollback", r["next_action"])
        self.assertEqual(r["done"], {"code_installed": True, "code_verified": True, "migrations_applied": [],
                                     "migrations_remaining": ["m004-record-workspace-version"],
                                     "migrations_blocked": [], "diagnostic": "ok", "kept_local": []})

    def test_failure_during_apply_restores_the_previous_state(self):
        p = self.prepared_plan()
        before = tree(self.install)

        def failing_copy(src, dst):
            if Path(dst).name == "NEW_DOC.md":
                raise OSError("simulated disk failure")
            shutil.copy2(str(src), str(dst))
        r = update.apply(self.install, p["plan_file"], yes=True, copy=failing_copy)
        self.assertEqual(r["status"], "failed-restored", json.dumps(r, indent=1)[:2000])
        self.assertEqual(r["stages"]["upgrade"]["restore"]["stage"], "verified")
        self.assertEqual(tree(self.install), before)
        self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())
        self.assertFalse(r["restart_required"])

    def test_local_package_offline_integrity_only(self):
        zip_path = self.assets / ZIP2
        bad = update.prepare_local(self.install, zip_path, expected_sha256="0" * 64, dest=self.dl / "bad")
        self.assertFalse(bad["ok"])
        self.assertTrue(any("differs from the expected" in x for x in bad["problems"]), bad["problems"])
        good = update.prepare_local(self.install, zip_path, expected_sha256=core.sha256_file(zip_path), dest=self.dl / "good")
        self.assertTrue(good["ok"], good["problems"])
        self.assertIn("origin not verified online", good["provenance"])
        p = update.plan(self.install, good["package_dir"])
        self.assertTrue(p["applicable"], p["refusals"])
        self.assertEqual(p["origin"], "local-package")
        self.assertIn("not verified online", p["provenance"])
        self.assertIn("fixture change for the tests", p["changes"])    # from the package CHANGELOG

    def test_fetch_refuses_wrong_provenance_altered_or_inconsistent_packages(self):
        # assets served from another repository
        rec = update.check(self.install, fetch=simulated([api_release("v" + V2, self.assets, repo="someone/else")]))
        f = update.fetch_release(self.install, downloader=local_downloader(self.assets), dest=self.dl / "p")
        self.assertFalse(f["ok"])
        self.assertTrue(any("official repository" in x for x in f["problems"]), f["problems"])
        # missing RELEASE.json asset
        entry = api_release("v" + V2, self.assets)
        entry["assets"] = [a for a in entry["assets"] if a["name"] != update.RELEASE_JSON]
        update.check(self.install, fetch=simulated([entry]))
        f = update.fetch_release(self.install, downloader=local_downloader(self.assets), dest=self.dl / "m")
        self.assertTrue(any("no asset RELEASE.json" in x for x in f["problems"]), f["problems"])
        # altered archive: the published hash no longer matches
        tampered = Path(self.tmp.name) / "tampered"
        shutil.copytree(str(self.assets), str(tampered))
        with open(str(tampered / ZIP2), "ab") as fh:
            fh.write(b"\0")
        update.check(self.install, fetch=simulated([api_release("v" + V2, tampered)]))
        f = update.fetch_release(self.install, downloader=local_downloader(tampered), dest=self.dl / "t")
        self.assertFalse(f["ok"])
        self.assertTrue(any("SHA-256" in x and "differs" in x for x in f["problems"]), f["problems"])
        self.assertIsNone(f["package_dir"])                               # nothing extracted
        # inconsistent metadata: RELEASE.json announces another version
        inconsistent = Path(self.tmp.name) / "inconsistent"
        shutil.copytree(str(self.assets), str(inconsistent))
        meta = json.loads((inconsistent / update.RELEASE_JSON).read_text(encoding="utf-8"))
        meta["version"] = "8.8.8"
        (inconsistent / update.RELEASE_JSON).write_text(json.dumps(meta), encoding="utf-8")
        update.check(self.install, fetch=simulated([api_release("v" + V2, inconsistent)]))
        f = update.fetch_release(self.install, downloader=local_downloader(inconsistent), dest=self.dl / "i")
        self.assertTrue(any("does not match the release" in x for x in f["problems"]), f["problems"])
        self.assertEqual(update.status(self.install)["installation"]["manifest_version"], V1)   # untouched

    def test_development_upstream_consults_but_never_applies(self):
        dev = helpers.make_workspace(self.tmp.name)
        helpers.configure(dev, language="en")
        self.assertEqual(update.status(dev)["installation"]["kind"], "development")
        rec = update.check(dev, fetch=simulated([api_release("v" + V2, self.assets)]))
        self.assertEqual(rec["result"], "update-available")               # consultation works
        p = update.plan(dev, self.pkg2)
        self.assertFalse(p["ok"] or p["applicable"])
        self.assertTrue(any("development upstream" in x for x in p["refusals"]), p["refusals"])
        self.assertIsNone(p["plan_file"])
        forged = Path(self.tmp.name) / "dev-plan.json"
        forged.write_text(json.dumps({"plan_hash": "x", "package_dir": str(self.pkg2)}), encoding="utf-8")
        r = update.apply(dev, forged, yes=True)
        self.assertEqual(r["status"], "refused-before-mutation")

    def test_cli_round_trip_from_the_installation(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def cli(*args):
            return subprocess.run([sys.executable, "-m", "tools.pws_workspace"] + list(args), cwd=str(self.install),
                                  capture_output=True, text=True, timeout=600, env=env)
        st = json.loads(cli("update", "status").stdout)
        self.assertEqual(st["installation"]["kind"], "distribution")
        prep = json.loads(cli("update", "prepare", "--package", str(self.assets / ZIP2), "--dest", str(self.dl)).stdout)
        self.assertTrue(prep["ok"], prep)
        plan = json.loads(cli("update", "plan", "--package-dir", prep["package_dir"]).stdout)
        self.assertTrue(plan["applicable"], plan["refusals"])
        refused = cli("update", "apply", "--plan-file", plan["plan_file"])      # no --yes
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(json.loads(refused.stdout)["status"], "refused-before-mutation")
        applied = cli("update", "apply", "--plan-file", plan["plan_file"], "--yes")
        self.assertEqual(applied.returncode, 0, applied.stdout[-1500:] + applied.stderr[-500:])
        self.assertEqual(json.loads(applied.stdout)["status"], "applied")
        info = json.loads(cli("update", "rollback-info").stdout)
        self.assertEqual(len(info["upgrade_backups"]), 1)


def doctor_seam(result):
    """Runner that answers the doctor call with a fixed (rc, stdout, stderr)
    and lets every other call reach the real new code."""
    def runner(root, args):
        if args and args[0] == "doctor":
            return result
        return update._run_new_code(root, args)
    return runner


def defective_doctor_package(target, pkg2):
    """Package 9.9.9 whose OWN doctor violates its contract: its entries carry
    no `check` identifier while its exit code stays 0 (no BLOCKING) — the new
    version's diagnostic looks fine to a reader that does not validate it."""
    shutil.copytree(str(pkg2), str(target))
    doc = target / "tools" / "pws_workspace" / "doctor.py"
    doc.write_text(doc.read_text(encoding="utf-8") + "\n\n_run_doctor_real = run_doctor\n\n\n"
                   "def run_doctor(root):  # fixture: identifiers dropped, exit code stays 0\n"
                   "    return [{\"severity\": \"OK\", \"detail\": \"fixture: identifier dropped\"}]\n",
                   encoding="utf-8")
    distribution.write_marker(target, V2)
    return target


class TestVerdicts(InstalledFixture):
    """Final verdicts of `apply` (corrected 2026-11-08; diagnostic content
    validated 2026-11-12): never `applied` unless every stage succeeded; each
    report states what was actually done."""

    def on_disk(self):
        return (upgrade.installed_manifest(self.install)[0]["version"],
                config.read_config(self.install)["data"]["workspace_version"])

    def apply_prepared(self, runner=None):
        p = self.prepared_plan()
        self.assertTrue(p["applicable"], p["refusals"])
        return update.apply(self.install, p["plan_file"], yes=True, runner=runner)

    def test_blocked_migration_stops_the_data_phase_before_any_migration(self):
        # a REAL blocked step: invalid legacy TradingView key → m001 and m003 blocked, m004 pending
        (self.install / ".claude" / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}, "env": {core.TV_MODE_ENV_KEY: "weird"}}),
            encoding="utf-8")
        r = self.apply_prepared()
        self.assertEqual(r["status"], "stopped-blocked-migrations", json.dumps(r, indent=1)[:2500])
        self.assertFalse(r["ok"])
        self.assertEqual(sorted(b["id"] for b in r["stages"]["migrate"]["blocked"]),
                         ["m001-tv-mode-to-config", "m003-remove-legacy-tv-key"])
        self.assertEqual(r["stages"]["migrate"]["applied"], [])             # not even the other steps
        self.assertEqual(r["stages"]["doctor"]["verdict"], "ok")             # diagnostic otherwise normal
        self.assertEqual(self.on_disk(), (V2, V1))                           # code installed, data untouched
        self.assertEqual(r["done"], {"code_installed": True, "code_verified": True, "migrations_applied": [],
                                     "migrations_remaining": ["m004-record-workspace-version"],
                                     "migrations_blocked": ["m001-tv-mode-to-config", "m003-remove-legacy-tv-key"],
                                     "diagnostic": "ok", "kept_local": []})
        self.assertIn("code installed", r["error"])
        self.assertIn("BLOCKED", r["error"])
        self.assertIn("migrate --plan", r["next_action"])
        self.assertIn("upgrade --rollback", r["next_action"])
        self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())
        self.assertNotIn("migration_backup", r["recovery"])
        self.assertTrue(r["restart_required"])

    def test_doctor_blocking_after_every_other_step_succeeded(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        os.symlink(str(outside), str(self.install / "scripts" / "escape"))    # a REAL BLOCKING check
        r = self.apply_prepared()
        self.assertEqual(r["status"], "diagnostic-blocking", json.dumps(r, indent=1)[:2500])
        self.assertFalse(r["ok"])
        self.assertEqual(r["stages"]["doctor"]["verdict"], "blocking")
        self.assertEqual(r["stages"]["doctor"]["rc"], 1)
        self.assertIn("no-outgoing-symlinks", r["stages"]["doctor"]["blocking"])
        self.assertEqual(r["stages"]["migrate"]["applied"], ["m004-record-workspace-version"])
        self.assertTrue(r["stages"]["verify"]["ok"])
        self.assertEqual(self.on_disk(), (V2, V2))                           # update in place, verdict honest
        self.assertEqual(r["done"]["diagnostic"], "blocking")
        self.assertIn("BLOCKING", r["error"])
        self.assertIn("doctor", r["next_action"])
        self.assertIn("migration_backup", r["recovery"])

    def test_doctor_execution_failure_is_not_a_successful_diagnostic(self):
        r = self.apply_prepared(runner=doctor_seam((1, "", "simulated failure of the doctor process")))
        self.assertEqual(r["status"], "diagnostic-unavailable", json.dumps(r, indent=1)[:2500])
        self.assertFalse(r["ok"])
        self.assertEqual(r["stages"]["doctor"]["verdict"], "unavailable")
        self.assertIn("simulated failure", r["stages"]["doctor"]["error"])
        self.assertEqual(self.on_disk(), (V2, V2))
        self.assertEqual(r["done"]["diagnostic"], "unavailable")
        self.assertEqual(r["done"]["migrations_applied"], ["m004-record-workspace-version"])
        self.assertIn("doctor", r["next_action"])

    def test_invalid_or_inconsistent_doctor_result_is_not_trusted(self):
        r = self.apply_prepared(runner=doctor_seam((0, "not a json document", "")))
        self.assertEqual((r["status"], r["ok"], r["stages"]["doctor"]["verdict"]),
                         ("diagnostic-unavailable", False, "unavailable"))
        # exit code 0 with a BLOCKING entry contradicts the doctor's contract
        v = update.doctor_verdict(0, json.dumps([{"check": "x", "severity": "BLOCKING", "detail": "d"}]), "")
        self.assertEqual(v["verdict"], "unavailable")
        self.assertIn("inconsistent", v["error"])
        v = update.doctor_verdict(1, json.dumps([{"check": "x", "severity": "OK", "detail": ""}]), "")
        self.assertEqual(v["verdict"], "unavailable")
        self.assertEqual(update.doctor_verdict(None, "", "")["verdict"], "unavailable")

    def test_warnings_only_diagnostic_allows_success_per_the_doctor_contract(self):
        warnings_only = json.dumps([{"check": "a", "severity": "OK", "detail": ""},
                                    {"check": "b", "severity": "WARNING", "detail": "w"},
                                    {"check": "c", "severity": "INFO", "detail": "i"}])
        r = self.apply_prepared(runner=doctor_seam((0, warnings_only, "")))
        self.assertEqual((r["status"], r["ok"]), ("applied", True), json.dumps(r, indent=1)[:1500])
        self.assertEqual((r["stages"]["doctor"]["verdict"], r["stages"]["doctor"]["warnings"]), ("ok", ["b"]))
        self.assertEqual(r["done"]["diagnostic"], "ok")
        self.assertEqual(self.on_disk(), (V2, V2))

    def test_cli_exit_code_follows_the_verdict(self):
        (self.install / ".claude" / "settings.local.json").write_text(
            json.dumps({"env": {core.TV_MODE_ENV_KEY: "weird"}}), encoding="utf-8")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def cli(*args):
            return subprocess.run([sys.executable, "-m", "tools.pws_workspace"] + list(args), cwd=str(self.install),
                                  capture_output=True, text=True, timeout=600, env=env)
        prep = json.loads(cli("update", "prepare", "--package", str(self.assets / ZIP2), "--dest", str(self.dl)).stdout)
        plan = json.loads(cli("update", "plan", "--package-dir", prep["package_dir"]).stdout)
        applied = cli("update", "apply", "--plan-file", plan["plan_file"], "--yes")
        self.assertEqual(applied.returncode, 1, applied.stdout[-800:])
        data = json.loads(applied.stdout)
        self.assertEqual((data["status"], data["ok"]), ("stopped-blocked-migrations", False))
        self.assertEqual(data["done"]["code_installed"], True)
        self.assertEqual(self.on_disk(), (V2, V1))

    def test_doctor_content_is_validated_before_any_verdict(self):
        # (2026-11-12) `[{}]` and an unknown severity were a successful diagnostic; a list severity raised
        def entry(check="x", severity="OK", detail=""):
            return {"check": check, "severity": severity, "detail": detail}
        unusable = {
            "empty object": (0, "[{}]", "entry 0 has no 'check' field"),
            "unknown severity": (0, '[{"check":"x","severity":"INVALID"}]', "unknown severity 'INVALID'"),
            "severity of a wrong type": (0, '[{"check":"x","severity":[]}]', "'severity' is not a string (list)"),
            "severity missing": (0, json.dumps([{"check": "x", "detail": ""}]), "no 'severity' field"),
            "severity lowercase": (0, json.dumps([entry(severity="ok")]), "unknown severity 'ok'"),
            "severity null": (0, json.dumps([entry(severity=None)]), "'severity' is not a string (NoneType)"),
            "severity bool": (0, json.dumps([entry(severity=True)]), "'severity' is not a string (bool)"),
            "check missing": (0, json.dumps([{"severity": "OK", "detail": ""}]), "no 'check' field"),
            "check blank": (0, json.dumps([entry(check="  ")]), "unusable check identifier"),
            "check multi-line": (0, json.dumps([entry(check="a\nb")]), "unusable check identifier"),
            "check null": (0, json.dumps([entry(check=None)]), "'check' is not a string (NoneType)"),
            "check object": (0, json.dumps([entry(check={})]), "'check' is not a string (dict)"),
            "detail missing": (0, json.dumps([{"check": "x", "severity": "OK"}]), "no 'detail' field"),
            "detail of a wrong type": (0, json.dumps([entry(detail=5)]), "'detail' is not a string (int)"),
            "valid entries then an invalid one": (0, json.dumps([entry("a"), entry("b", "WARNING", "w"),
                                                                entry("c", "INVALID")]),
                                                  "entry 2 (check 'c') has an unknown severity"),
            "BLOCKING then an invalid one": (1, json.dumps([entry("a", "BLOCKING", "d"), {}]),
                                             "entry 1 has no 'check' field"),
            "entry not an object": (0, "[1]", "entry 0 is not an object (int)"),
            "empty list, exit code 0": (0, "[]", "reported no check at all"),
            "empty list, exit code 1": (1, "[]", "reported no check at all"),
            "not a list": (0, "{}", "did not produce a usable result"),
            "stdout None": (0, None, "did not produce a usable result"),
            "exit code bool": (True, json.dumps([entry("a")]), "did not produce a usable result"),
            "exit code string": ("0", json.dumps([entry("a")]), "did not produce a usable result"),
            "exit code 2": (2, json.dumps([entry("a")]), "inconsistent"),
        }
        for label, (rc, out, fragment) in unusable.items():
            v = update.doctor_verdict(rc, out, "")              # never raises, whatever the JSON types
            self.assertEqual((v["verdict"], v["ok"]), ("unavailable", False), label)
            self.assertIn(fragment, v["error"], label)
            self.assertNotIn("blocking", v.get("verdict"))      # an invalid entry never yields a partial verdict
        # conformant results keep their verdicts: warnings alone never block, BLOCKING blocks, extra keys are harmless
        v = update.doctor_verdict(0, json.dumps([entry("a"), entry("b", "WARNING", "w"), entry("c", "INFO", "i")]), "")
        self.assertEqual((v["verdict"], v["ok"], v["warnings"], v["counts"]),
                         ("ok", True, ["b"], {"OK": 1, "WARNING": 1, "INFO": 1}))
        v = update.doctor_verdict(1, json.dumps([entry("a"), entry("b", "BLOCKING", "d")]), "")
        self.assertEqual((v["verdict"], v["ok"], v["blocking"]), ("blocking", False, ["b"]))
        self.assertEqual(update.doctor_verdict(0, json.dumps([dict(entry("a"), extra=1)]), "")["verdict"], "ok")
        # the real doctor's output always conforms (it reports at least `tooling-tests`)
        real = doctor.run_doctor(self.install)
        self.assertIn("tooling-tests", [r["check"] for r in real])
        rc = 1 if any(r["severity"] == "BLOCKING" for r in real) else 0
        self.assertIn(update.doctor_verdict(rc, json.dumps(real), "")["verdict"], ("ok", "blocking"))

    def test_unusable_doctor_content_in_apply_is_never_a_success(self):
        # (2026-11-12) the doctor answering `[{}]` with exit code 0 ended in `applied` / ok true
        r = self.apply_prepared(runner=doctor_seam((0, "[{}]", "")))
        self.assertEqual((r["status"], r["ok"]), ("diagnostic-unavailable", False), json.dumps(r, indent=1)[:2500])
        self.assertEqual(r["stages"]["doctor"]["verdict"], "unavailable")
        self.assertIn("entry 0 has no 'check' field", r["stages"]["doctor"]["error"])
        self.assertIn("violates the doctor contract", r["error"])
        self.assertEqual(r["done"], {"code_installed": True, "code_verified": True,
                                     "migrations_applied": ["m004-record-workspace-version"],
                                     "migrations_remaining": [], "migrations_blocked": [],
                                     "diagnostic": "unavailable", "kept_local": []})
        self.assertEqual(self.on_disk(), (V2, V2))                           # update in place, reported, not a success
        self.assertIn("doctor", r["next_action"])
        self.assertIn("upgrade --rollback", r["next_action"])
        self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())
        self.assertIn("migration_backup", r["recovery"])
        self.assertTrue(r["restart_required"])

    def test_cli_exit_code_when_the_new_versions_doctor_violates_its_contract(self):
        # END-TO-END through the CLI: the installed NEW doctor answers without identifiers and exits 0
        pkg3 = defective_doctor_package(Path(self.tmp.name) / "pkg v3 defective doctor", self.pkg2)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def cli(*args):
            return subprocess.run([sys.executable, "-m", "tools.pws_workspace"] + list(args), cwd=str(self.install),
                                  capture_output=True, text=True, timeout=600, env=env)
        prep = json.loads(cli("update", "prepare", "--package", str(pkg3)).stdout)
        self.assertTrue(prep["ok"], prep["problems"])
        plan = json.loads(cli("update", "plan", "--package-dir", prep["package_dir"]).stdout)
        self.assertTrue(plan["applicable"], plan["refusals"])
        applied = cli("update", "apply", "--plan-file", plan["plan_file"], "--yes")
        self.assertEqual(applied.returncode, 1, applied.stdout[-800:])
        data = json.loads(applied.stdout)
        self.assertEqual((data["status"], data["ok"], data["stages"]["doctor"]["verdict"]),
                         ("diagnostic-unavailable", False, "unavailable"))
        self.assertEqual(data["stages"]["doctor"]["rc"], 0)
        self.assertIn("entry 0 has no 'check' field", data["stages"]["doctor"]["error"])
        self.assertEqual(data["done"]["migrations_applied"], ["m004-record-workspace-version"])
        self.assertEqual(data["done"]["diagnostic"], "unavailable")
        self.assertEqual(self.on_disk(), (V2, V2))
        installed = cli("doctor", "--json")                 # the installed doctor really exits 0 with that content
        self.assertEqual(installed.returncode, 0)
        self.assertEqual(json.loads(installed.stdout), [{"severity": "OK", "detail": "fixture: identifier dropped"}])



def next_version_package(target, pkg2, ver="9.9.10"):
    """A package one version after the 9.9.9 fixture (its own version.py says so)."""
    shutil.copytree(str(pkg2), str(target))
    vp = target / "tools" / "pws_workspace" / "version.py"
    text = vp.read_text(encoding="utf-8")
    vp.write_text(text.replace('WORKSPACE_VERSION = "%s"' % V2, 'WORKSPACE_VERSION = "%s"' % ver), encoding="utf-8")
    (target / "VERSION").write_text(ver + "\n", encoding="utf-8")
    distribution.write_marker(target, ver)
    return target


def seam(**answers):
    """Runner answering selected subcommands with fixed (rc, stdout, stderr)
    (key: first two arguments joined by '_', e.g. migrate_--apply) or with a
    callable; every other call reaches the real new code."""
    def runner(root, args):
        key = "_".join(args[:2])
        if key in answers:
            a = answers[key]
            return a(root, args) if callable(a) else a
        return update._run_new_code(root, args)
    return runner


class TestCorrections20261113(InstalledFixture):
    """Mission of correction (2026-11-13): H-04, H-05, H-01, H-02, H-03, F-01."""

    def apply_prepared(self, runner=None):
        p = self.prepared_plan()
        self.assertTrue(p["applicable"], p["refusals"])
        self.prepared_dir = Path(p["package_dir"])
        return update.apply(self.install, p["plan_file"], yes=True, runner=runner)

    def test_kept_local_file_is_verified_separately_and_the_update_succeeds(self):
        rel = "tools/pine_exec/PROVENANCE.json"            # rewritten by `pinets verify --record` or an install
        local = self.install / rel
        local.write_text(local.read_text(encoding="utf-8").rstrip() + "\n\n", encoding="utf-8")
        before = core.sha256_file(local)
        r = self.apply_prepared()
        self.assertEqual((r["status"], r["ok"]), ("applied", True), json.dumps(r, indent=1)[:2500])
        self.assertEqual(r["done"]["kept_local"], [rel])
        self.assertEqual(core.sha256_file(local), before)                      # local data preserved
        pkg_sha = upgrade.installed_manifest(self.pkg2)[0]["files"][rel]
        self.assertEqual(core.sha256_file(self.install / (rel + ".pws-new")), pkg_sha)   # new version intact
        self.assertEqual(r["stages"]["verify"]["kept"], [{"path": rel, "local_preserved": True,
                                                          "new_version": rel + ".pws-new", "new_version_intact": True}])
        self.assertIn(rel + ".pws-new", r["next_action"])
        again = update.plan(self.install, self.prepared_dir)
        self.assertFalse(again["applicable"])                                  # no loop on the same package
        self.assertIn("nothing to apply", " ".join(again["refusals"]))
        # a damaged new version is never reported as a success
        (self.install / (rel + ".pws-new")).write_text("damaged", encoding="utf-8")
        verify = update._verify_installed(self.install, self.prepared_dir, {rel: {"local_sha256": before}})
        self.assertFalse(verify["ok"])
        self.assertIn(rel, verify["mismatched"])

    def test_successive_updates_apply_the_recurrent_migration_each_time(self):
        r = self.apply_prepared()
        self.assertEqual(r["status"], "applied", json.dumps(r, indent=1)[:1500])
        pkg3 = next_version_package(Path(self.tmp.name) / "pkg v3", self.pkg2)
        for ver, pkg in (("9.9.10", pkg3), ):
            prep = update.prepare_local(self.install, pkg)
            self.assertTrue(prep["ok"], prep["problems"])
            p = update.plan(self.install, prep["package_dir"])
            self.assertTrue(p["applicable"], p["refusals"])
            self.assertIn("m004-record-workspace-version", p["migrations_may_apply"])
            r = update.apply(self.install, p["plan_file"], yes=True)
            self.assertEqual((r["status"], r["ok"]), ("applied", True), json.dumps(r, indent=1)[:2500])
            self.assertEqual(r["done"]["migrations_applied"], ["m004-record-workspace-version"])
            self.assertEqual(config.read_config(self.install)["data"]["workspace_version"], ver)

    def test_unusable_or_inconsistent_migrate_answers_are_never_a_success(self):
        cases = {
            "apply object without lists": {"migrate_--apply": (0, json.dumps({"applied": "m004"}), "")},
            "apply list": {"migrate_--apply": (0, "[]", "")},
            "apply rc inconsistent": {"migrate_--apply": (0, json.dumps({"applied": [], "errors": ["x"]}), "")},
            "apply silent no-op": {"migrate_--apply": (0, json.dumps({"applied": [], "errors": [], "backup": None}), "")},
            "plan config error": {"migrate_--plan": (0, json.dumps({"config_error": "unreadable", "steps": []}), "")},
            "plan entry not an object": {"migrate_--plan": (0, json.dumps({"config_error": None, "steps": [1]}), "")},
            "plan blocked not a boolean": {"migrate_--plan": (0, json.dumps({"config_error": None, "steps": [
                {"id": "m004-record-workspace-version", "blocked": "no", "detail": ""}]}), "")},
        }
        for label, answers in cases.items():
            with self.subTest(label):
                self.tearDown()
                self.setUp()
                r = self.apply_prepared(runner=seam(**answers))
                self.assertFalse(r["ok"], label)
                self.assertEqual(r["status"], "incomplete", (label, r.get("error")))
                self.assertTrue(r["done"]["code_installed"])
                self.assertIn("upgrade --rollback", r["next_action"])
                self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())

    def test_an_internal_error_after_the_code_installation_still_returns_an_account(self):
        def boom(root, args):
            raise RuntimeError("simulated internal error")
        r = self.apply_prepared(runner=seam(**{"doctor_--json": boom}))
        self.assertEqual((r["status"], r["ok"]), ("incomplete", False))
        self.assertIn("internal error after the code installation", r["error"])
        self.assertTrue(r["done"]["code_installed"])
        self.assertIn("migrate --plan", r["next_action"])
        self.assertTrue(Path(r["recovery"]["upgrade_backup"]).is_dir())

    def test_interruptions_of_the_code_upgrade_restore_or_stay_resumable(self):
        before = tree(self.install)
        calls = {"n": 0}

        def interrupted_copy(src, dst):
            calls["n"] += 1
            if calls["n"] == 5:
                raise KeyboardInterrupt()
            shutil.copy2(str(src), str(dst))
        r = upgrade.apply(self.install, self.pkg2, copy=interrupted_copy)
        self.assertFalse(r["ok"])
        self.assertIn("interrupted", r["error"])
        self.assertEqual(r["restore"]["stage"], "verified")
        self.assertEqual(tree(self.install), before)
        # an abrupt stop leaves the backup `applying`: reported, and rollback accepts it
        r = upgrade.apply(self.install, self.pkg2)
        self.assertTrue(r["ok"], r["error"])
        manifest_path = Path(r["backup"]) / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["state"] = "applying"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(upgrade.interrupted_backups(self.install), [Path(r["backup"]).name])
        self.assertIn(Path(r["backup"]).name, upgrade.plan(self.install, self.pkg2)["interrupted"])
        rb = upgrade.rollback(self.install, Path(r["backup"]).name)
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(tree(self.install), before)



class TestUpdateReadings20261113(unittest.TestCase):
    """H-08, H-09, H-12 (2026-11-13): readings that must never mislead."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ws"
        (self.root / ".claude" / "runtime").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_prereleases_follow_semver_precedence(self):
        self.assertEqual(version.compare("2.1.0-rc.2", "2.1.0-rc.1"), 1)
        self.assertEqual(version.compare("2.1.0-beta.11", "2.1.0-beta.2"), 1)
        self.assertEqual(version.compare("2.1.0", "2.1.0-rc.9"), 1)
        rels = [api_release("v9.9.9-rc.1"), api_release("v9.9.9-rc.2"), api_release("v9.9.9-beta.11")]
        rec = update.check(self.root, fetch=simulated(rels), include_prereleases=True)
        self.assertEqual(rec["latest"]["version"], "9.9.9-rc.2")

    def test_malformed_release_fields_and_truncated_answers_are_errors_not_traces(self):
        rel = api_release("v9.9.9")
        rel["assets"] = 5
        rec = update.check(self.root, fetch=simulated([rel]))
        self.assertEqual(rec["result"], "update-available")
        self.assertEqual(rec["latest"]["assets"], [])
        import http.client
        import urllib.request
        original = urllib.request.urlopen

        def truncated(*args, **kwargs):
            raise http.client.IncompleteRead(b"partial")
        urllib.request.urlopen = truncated
        try:
            status_code, data, err = update._http_get_json("https://example.invalid/x")
        finally:
            urllib.request.urlopen = original
        self.assertIsNone(data)
        self.assertIn("IncompleteRead", err)

    def test_an_expected_sha256_is_never_ignored_for_a_folder(self):
        folder = Path(self.tmp.name) / "package folder"
        folder.mkdir()
        r = update.prepare_local(self.root, folder, expected_sha256="0" * 64)
        self.assertFalse(r["ok"])
        self.assertIn("applies to an archive", " ".join(r["problems"]))


class TestPlanAndStatus20261113(InstalledFixture):
    """H-06, H-07 (2026-11-13)."""

    def test_the_approved_list_is_the_hash_bound_one_and_status_follows_the_installed_version(self):
        p = self.prepared_plan()
        self.assertTrue(p["applicable"], p["refusals"])
        data = json.loads(Path(p["plan_file"]).read_text(encoding="utf-8"))
        data["migrations_may_apply"] = []                    # altered outside the hash
        Path(p["plan_file"]).write_text(json.dumps(data), encoding="utf-8")
        r = update.apply(self.install, p["plan_file"], yes=True)
        self.assertEqual((r["status"], r["ok"]), ("applied", True), json.dumps(r, indent=1)[:2000])
        rc, out, _err = update._run_new_code(self.install, ["update", "status"])   # the INSTALLED code (9.9.9)
        st = json.loads(out)
        self.assertEqual(st["last_check"]["result"], "up-to-date")
        self.assertEqual(st["last_check"]["installed"], V2)
        self.assertEqual(st["interrupted_upgrades"], [])

    def test_an_explicit_plan_file_never_overwrites_an_existing_file(self):
        """H-13 (2026-11-13): `update plan --plan-file` on the configuration."""
        rec = update.check(self.install, fetch=simulated([api_release("v" + V2, self.assets)]))
        self.assertEqual(rec["result"], "update-available", rec)
        fetched = update.fetch_release(self.install, downloader=local_downloader(self.assets), dest=self.dl)
        cfg = config.config_path(self.install)
        before = cfg.read_bytes()
        p = update.plan(self.install, fetched["package_dir"], plan_file=str(cfg))
        self.assertFalse(p["applicable"])
        self.assertTrue(any("already exists" in r for r in p["refusals"]), p["refusals"])
        self.assertEqual(cfg.read_bytes(), before)
        fresh = Path(self.dl) / "new-plan.json"
        p = update.plan(self.install, fetched["package_dir"], plan_file=str(fresh))
        self.assertTrue(p["applicable"], p["refusals"])
        self.assertTrue(fresh.is_file())


class TestReleaseBuild(unittest.TestCase):
    def test_build_release_produces_verified_artefacts_and_never_rebuilds_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "release out"
            # structure test on the working tree: allow_dirty (the CLI never exposes it; publication
            # artefacts require a committed clean tree, tested below)
            r = release.build_release(ROOT, target, allow_dirty=True)
            self.assertTrue(r["ok"], r)
            self.assertEqual((r["version"], r["tag"]), (V1, "v" + V1))
            zip_path = Path(r["zip"])
            self.assertEqual(zip_path.name, version.package_name(V1) + ".zip")
            self.assertEqual((target / (zip_path.name + ".sha256")).read_text(encoding="utf-8").split()[0], r["zip_sha256"])
            meta = json.loads((target / update.RELEASE_JSON).read_text(encoding="utf-8"))
            self.assertEqual((meta["version"], meta["tag"], meta["zip"], meta["zip_sha256"], meta["migrations"]),
                             (V1, "v" + V1, zip_path.name, core.sha256_file(zip_path), list(migration.STEP_IDS)))
            self.assertEqual(meta["official_repository"], REPO)
            self.assertIn("no cryptographic signature", meta["integrity"])
            notes = (target / update.RELEASE_NOTES).read_text(encoding="utf-8")
            self.assertIn("First public release", notes)
            self.assertIn(r["zip_sha256"], notes)
            ok, problems, top, _ = update.inspect_archive(zip_path)
            self.assertTrue(ok and top == version.package_name(V1), problems)
            again = release.build_release(ROOT, target, allow_dirty=True)
            self.assertFalse(again["ok"])
            self.assertTrue(any("never rebuilt silently" in p for p in again["problems"]), again["problems"])
            prep = update.prepare_local(ROOT, zip_path, expected_sha256=r["zip_sha256"], dest=Path(tmp) / "prep")
            self.assertTrue(prep["ok"], prep["problems"])
            inner, _ = upgrade.installed_manifest(prep["package_dir"])
            self.assertEqual(inner["version"], V1)
            self.assertNotIn("scripts", [p.name for p in Path(prep["package_dir"]).iterdir()])


    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_publication_artefacts_require_a_committed_clean_tree_and_never_ship_untracked_files(self):
        # audit I-03 (2026-11-13): an archive holds exactly the content of its source commit
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source tree"
            self.assertTrue(distribution.build(ROOT, src)["ok"])
            git = ["git", "-C", str(src), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
                subprocess.run(git + args, check=True, capture_output=True)
            (src / ".claude" / "rules" / "CLAUDE.local.md").write_text("ignored personal note\n", encoding="utf-8")
            r = release.build_release(src, Path(tmp) / "out clean")
            self.assertTrue(r["ok"], r["problems"])
            self.assertEqual(r["source_dirty"], False)
            self.assertIn(".claude/rules/CLAUDE.local.md", r["distribution"]["untracked_not_shipped"])
            with zipfile.ZipFile(r["zip"]) as z:
                self.assertFalse(any(n.endswith("CLAUDE.local.md") for n in z.namelist()))
            (src / "README.md").write_text((src / "README.md").read_text(encoding="utf-8") + "\nedit\n",
                                           encoding="utf-8")
            refused = release.build_release(src, Path(tmp) / "out dirty")
            self.assertFalse(refused["ok"])
            self.assertIn("committed, clean tree", " ".join(refused["problems"]))
            self.assertFalse((Path(tmp) / "out dirty").exists())

    def test_release_target_inside_or_around_the_source_is_refused_whatever_its_case(self):
        """Review RS-05 (2026-11-13): build-release compares the target with the
        source by physical identity, like build-distribution — nothing is
        written inside the source spelled with another case."""
        with tempfile.TemporaryDirectory() as tmp:
            around = Path(tmp) / "Around"
            src = around / "Source WS"
            src.mkdir(parents=True)
            shutil.copy2(str(ROOT / "CHANGELOG.md"), str(src / "CHANGELOG.md"))   # version consistency passes

            def tree():
                return sorted(p.relative_to(around).as_posix() for p in around.rglob("*"))
            before = tree()
            cases = [(src / "release-out", "target must be outside the source workspace"),
                     (around, "target contains the source workspace — refusing")]
            if (Path(tmp) / "around" / "source ws").exists():        # case-insensitive volume
                cases += [(Path(tmp) / "around" / "SOURCE WS" / "release-out",
                           "target must be outside the source workspace"),
                          (Path(tmp) / "AROUND", "target contains the source workspace — refusing")]
            for target, expected in cases:
                with self.subTest(target=str(target)):
                    r = release.build_release(src, target, allow_dirty=True)
                    self.assertFalse(r["ok"])
                    self.assertEqual(r["problems"], [expected])
                    self.assertEqual(tree(), before)

    def test_archive_entries_carry_normalized_permissions(self):
        """Review m9 (2026-11-13): 0644, or 0755 for a file executable by its
        owner — a file kept 0600 locally is never archived as 0600."""
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            self.assertTrue(distribution.build(ROOT, dist)["ok"])
            os.chmod(str(dist / "tools" / "pine_exec" / "PROVENANCE.json"), 0o600)
            os.chmod(str(dist / "install.py"), 0o700)
            os.chmod(str(dist / "README.md"), 0o666)
            distribution.write_marker(dist, V1)
            os.chmod(str(dist / distribution.MARKER), 0o600)
            art = release.write_artefacts(dist, Path(tmp) / "assets", V1, git={"commit": "fixture", "dirty": False})
            self.assertTrue(art["ok"], art["problems"])
            top = version.package_name(V1)
            with zipfile.ZipFile(art["zip"]) as z:
                modes = {i.filename[len(top) + 1:]: (i.external_attr >> 16) for i in z.infolist()}
            self.assertEqual({rel: m & 0o777 for rel, m in modes.items()
                              if rel in ("tools/pine_exec/PROVENANCE.json", "install.py", "README.md",
                                         distribution.MARKER)},
                             {"tools/pine_exec/PROVENANCE.json": 0o644, "install.py": 0o755, "README.md": 0o644,
                              distribution.MARKER: 0o644})
            self.assertEqual({m & 0o777 for m in modes.values()} - {0o644, 0o755}, set())
            self.assertEqual({m & 0o170000 for m in modes.values()}, {0o100000})     # regular files only
            prep = update.prepare_local(ROOT, Path(art["zip"]), expected_sha256=art["zip_sha256"],
                                        dest=Path(tmp) / "prep")
            self.assertTrue(prep["ok"], prep["problems"])
            unpacked = Path(prep["package_dir"])
            self.assertEqual((unpacked / "tools" / "pine_exec" / "PROVENANCE.json").stat().st_mode & 0o777, 0o644)
            self.assertEqual((unpacked / "install.py").stat().st_mode & 0o777, 0o755)

class TestScanExemption(unittest.TestCase):
    def test_exact_official_repository_reference_is_exempt_but_identity_elsewhere_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            helpers.configure(root, language="en", holder="Holder Test", aliases=("HolderAlias",))
            built = Path(tmp) / "built tree"
            built.mkdir()
            (built / "a.md").write_text("Releases: https://github.com/%s/releases and api.github.com/repos/%s/releases\n"
                                        % (REPO, REPO), encoding="utf-8")
            (built / "b.md").write_text("Contact HolderAlias for details\n", encoding="utf-8")
            (built / "c.md").write_text("owner only: %s\n" % REPO.split("/")[0], encoding="utf-8")
            hits = distribution.scan_personal(built, distribution.personal_patterns(root, account="agent"))
            self.assertEqual([h["path"] for h in hits], ["b.md"])        # the exact reference is exempt, nothing else
            self.assertIn("<official-repository>", distribution._without_official_references("x %s y" % REPO))
            # the bare owner name is not an exemption: it stays subject to the identity patterns of the root
            self.assertEqual(distribution._without_official_references(REPO.split("/")[0]), REPO.split("/")[0])


class TestMenuEntries(unittest.TestCase):
    def test_tools_submenu_offers_pinets_and_the_workspace_update_in_both_languages(self):
        for lang, pinets, upd in (("fr", "PineTS", "Mettre à jour Pine-Workspace"), ("en", "PineTS", "Update Pine-Workspace")):
            with tempfile.TemporaryDirectory() as tmp:
                root = helpers.make_workspace(tmp)
                helpers.configure(root, language=lang)
                m = menu.build_menu(session.session_status(root))
                maint = [t for t in m["top"] if t["id"] == "maintenance"][0]
                tools = None
                for screen in maint["children"]:
                    for node in screen:
                        if node["id"] == "maintenance.tools":
                            tools = node
                self.assertIsNotNone(tools)
                self.assertEqual(tools["kind"], "submenu")
                screen = tools["children"][0]
                self.assertEqual([(n["id"], n["label"], n.get("route")) for n in screen],
                                 [("tools.pinets", pinets, "pine-tools"), ("tools.update", upd, "pws-update"),
                                  ("back", i18n.t("back", lang), None)])
                for node in screen[:2]:
                    self.assertTrue(node["description"] and len(node["description"]) < 200)
                ids = [n["id"] for s in maint["children"] for n in s]
                for expected in ("maintenance.doctor", "maintenance.status", "maintenance.config",
                                 "maintenance.tools", "maintenance.archives"):
                    self.assertIn(expected, ids)
        self.assertTrue((ROOT / ".claude" / "skills" / "pws-update" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
