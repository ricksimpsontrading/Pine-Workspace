# SPDX-License-Identifier: Apache-2.0
"""Startup cleanup whitelist and archive import procedure (2026-11-06), with
the safety rules added after the audit of 2026-11-12 (findings E-01 to E-07)."""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, maintenance
from tools.tests import helpers

RUNS_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


class TestCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / "tools" / "pws_workspace" / "__pycache__").mkdir(parents=True)
        (self.root / "tools" / "pws_workspace" / "__pycache__" / "x.cpython-39.pyc").write_bytes(b"\x00" * 10)
        (self.root / ".DS_Store").write_bytes(b"\x00")
        (self.root / "docs" / "maintenance").mkdir(parents=True)
        (self.root / "docs" / "maintenance" / "evidence.png").write_bytes(b"png")
        (self.root / "docs" / "maintenance" / ".DS_Store").write_bytes(b"\x00")
        sdir = self.root / core.RUNTIME_REL / "session"
        sdir.mkdir(parents=True)
        core.atomic_write_json(sdir / "latest.json", {"session_id": "current"})
        core.atomic_write_json(sdir / "current.json", {"files": {}})
        old = sdir / "old-session.json"
        core.atomic_write_json(old, {"files": {}})
        ancient = time.time() - 30 * 86400
        os.utime(old, (ancient, ancient))
        core.atomic_write_json(sdir / "recent-other.json", {"files": {}})
        rb = self.root / core.RUNTIME_REL / "pinets-rollback" / "0.9.33"
        rb.mkdir(parents=True)
        (rb / ".DS_Store").write_bytes(b"\x00")
        (rb / "package.json").write_text("{}", encoding="utf-8")
        (self.root / "keep.lock").write_text("", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_plans_only_whitelisted_items(self):
        report = maintenance.cleanup(self.root, execute=False)
        cats = {p["category"] for p in report["planned"]}
        self.assertEqual(cats, {"pycache", "ds_store", "stale_session_snapshot"})
        paths = {p["path"] for p in report["planned"]}
        self.assertIn(".DS_Store", paths)
        self.assertIn("docs/maintenance/.DS_Store", paths)
        self.assertNotIn(".claude/runtime/pinets-rollback/0.9.33/.DS_Store", paths)
        self.assertNotIn("docs/maintenance/evidence.png", paths)
        self.assertNotIn("keep.lock", paths)
        self.assertNotIn(".claude/runtime/session/current.json", paths)
        self.assertNotIn(".claude/runtime/session/recent-other.json", paths)
        self.assertTrue((self.root / ".DS_Store").exists())  # dry run

    def test_execute_removes_and_logs(self):
        report = maintenance.cleanup(self.root, execute=True)
        self.assertFalse((self.root / ".DS_Store").exists())
        self.assertFalse((self.root / "tools" / "pws_workspace" / "__pycache__").exists())
        self.assertFalse((self.root / core.RUNTIME_REL / "session" / "old-session.json").exists())
        self.assertTrue((self.root / core.RUNTIME_REL / "session" / "current.json").exists())
        self.assertTrue((self.root / "docs" / "maintenance" / "evidence.png").exists())
        self.assertTrue((self.root / "keep.lock").exists())
        self.assertEqual(report["anomalies"], [])
        log = (self.root / maintenance.MAINTENANCE_REL / "cleanup-log.jsonl").read_text(encoding="utf-8")
        self.assertIn("pycache", log)
        again = maintenance.cleanup(self.root, execute=True)
        self.assertEqual(again["removed"], [])

    def test_disabled_by_configuration(self):
        helpers.configure(self.root)
        from tools.pws_workspace import config
        config.set_value(self.root, "maintenance.startup_cleanup", False)
        report = maintenance.startup_cleanup(self.root)
        self.assertFalse(report["enabled"])
        self.assertTrue((self.root / ".DS_Store").exists())

    def test_startup_summary_silent_when_nothing_to_do(self):
        maintenance.cleanup(self.root, execute=True)
        report = maintenance.startup_cleanup(self.root)
        self.assertEqual(report["summary_lines"], [])

    def test_symlinked_runtime_skipped(self):
        outside = self.root.parent / "outside rt"
        outside.mkdir()
        runtime = self.root / core.RUNTIME_REL
        import shutil
        shutil.rmtree(str(runtime))
        os.symlink(outside, runtime)
        report = maintenance.cleanup(self.root, execute=True)
        self.assertTrue(report["anomalies"])
        self.assertEqual(list(outside.iterdir()), [])


class TestArchives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.source = Path(self.tmp.name) / "external backups"
        self.source.mkdir()
        (self.source / "a.zip").write_bytes(b"zip-a")
        (self.source / "dup.zip").write_bytes(b"zip-a")
        (self.source / "sub").mkdir()
        (self.source / "sub" / "candidate-abc.pine").write_text("//@version=6\n", encoding="utf-8")
        (self.source / "MANIFEST.txt").write_text("manifest\n", encoding="utf-8")
        (self.source / ".DS_Store").write_bytes(b"\x00")
        (self.root / "docs" / "maintenance" / "2026-old").mkdir(parents=True)
        (self.root / "docs" / "maintenance" / "2026-old" / "same.txt").write_text("manifest\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_classifies_duplicates_and_existing(self):
        plan = maintenance.plan_import(self.root, self.source)
        by = {e["rel"]: e for e in plan["entries"]}
        self.assertEqual(by["a.zip"]["action"], "copy")
        self.assertEqual(by["dup.zip"]["action"], "duplicate_in_source")
        self.assertEqual(by["dup.zip"]["same_as"], "docs/maintenance/archives/a.zip")
        self.assertEqual(by["MANIFEST.txt"]["action"], "already_in_workspace")
        self.assertEqual(by["sub/candidate-abc.pine"]["classification"], "source-return-point")
        self.assertEqual(plan["counts"], {"copy": 2, "duplicate_in_source": 1, "already_in_workspace": 1})
        self.assertNotIn(".DS_Store", by)

    def test_import_verify_then_remove_source(self):
        plan = maintenance.plan_import(self.root, self.source)
        r = maintenance.execute_import(self.root, plan)
        self.assertTrue(r["ok"], r)
        target = self.root / "docs" / "maintenance" / "archives"
        self.assertTrue((target / "a.zip").is_file())
        self.assertTrue((target / "sub" / "candidate-abc.pine").is_file())
        self.assertFalse((target / "dup.zip").exists())
        manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["entries"]), 4)
        self.assertIn("dup.zip", (target / "INDEX.md").read_text(encoding="utf-8"))
        complete, problems = maintenance.verify_import(self.root, plan)
        self.assertTrue(complete, problems)
        self.assertTrue(self.source.exists())
        # importing (and even a complete verification) never deletes the source by
        # itself: the deletion needs the holder's explicit authorization (--yes)
        rr = maintenance.remove_source(self.root, plan)
        self.assertFalse(rr["ok"])
        self.assertTrue(rr["verified"])
        self.assertEqual(rr["would_remove"], str(self.source))
        self.assertTrue(self.source.exists())
        rr = maintenance.remove_source(self.root, plan, yes=True)
        self.assertTrue(rr["ok"], rr)
        self.assertFalse(self.source.exists())

    def test_remove_source_refused_when_incomplete(self):
        plan = maintenance.plan_import(self.root, self.source)
        maintenance.execute_import(self.root, plan)
        (self.root / "docs" / "maintenance" / "archives" / "a.zip").unlink()
        rr = maintenance.remove_source(self.root, plan, yes=True)
        self.assertFalse(rr["ok"])
        self.assertIn("incomplete", rr["error"])
        self.assertTrue(self.source.exists())

    def test_import_is_idempotent_and_refuses_conflicts(self):
        plan = maintenance.plan_import(self.root, self.source)
        maintenance.execute_import(self.root, plan)
        r = maintenance.execute_import(self.root, plan)
        self.assertTrue(r["ok"])
        (self.root / "docs" / "maintenance" / "archives" / "a.zip").write_bytes(b"changed")
        r = maintenance.execute_import(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertTrue(r["failures"])


class TestCleanupSafety(unittest.TestCase):
    """Only truly recreatable items go: never a user file stored in a cache
    folder, a file cited by a tracked document, the latest or current
    snapshot; an unreadable folder is an anomaly, never a failure (E-06, E-07)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        self.outside = Path(self.tmp.name) / "outside"
        self.outside.mkdir()
        (self.outside / "ext.pyc").write_bytes(b"e")
        self.cache = self.root / "tools" / "pkg" / "__pycache__"
        (self.cache / "sub").mkdir(parents=True)
        (self.cache / "m.cpython-39.pyc").write_bytes(b"\x00" * 10)
        (self.cache / "notes.txt").write_bytes(b"n" * 5000)
        (self.cache / "sub" / "data.json").write_bytes(b"d" * 7000)
        os.symlink(self.outside / "ext.pyc", self.cache / "link.pyc")
        (self.root / "tools" / "pkg" / "legacy.pyc").write_bytes(b"l")
        self.sdir = self.root / core.RUNTIME_REL / "session"
        self.sdir.mkdir(parents=True)
        core.atomic_write_json(self.sdir / "latest.json", {"session_id": "sess-latest"})
        self.old = time.time() - 30 * 86400

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self, sid, old=True, content=None):
        p = self.sdir / ("%s.json" % sid)
        core.atomic_write_json(p, content if content is not None
                               else {"session_id": sid, "files": {}, "guard": None})
        if old:
            os.utime(p, (self.old, self.old))
        return p

    def test_pycache_keeps_user_content_and_reports_exact_bytes(self):
        report = maintenance.cleanup(self.root, execute=True)
        self.assertEqual([r["path"] for r in report["removed"]],
                         ["tools/pkg/__pycache__/m.cpython-39.pyc"])
        self.assertEqual(report["bytes"], 10)
        self.assertEqual(report["anomalies"], [])
        for kept in (self.cache / "notes.txt", self.cache / "sub" / "data.json",
                     self.root / "tools" / "pkg" / "legacy.pyc", self.outside / "ext.pyc"):
            self.assertTrue(kept.is_file(), kept)
        self.assertTrue((self.cache / "link.pyc").is_symlink())

    def test_only_unused_snapshots_in_the_expected_format_go(self):
        stale = self.snapshot("sess-old")
        kept = [self.snapshot("sess-latest"), self.snapshot("sess-current"),
                self.snapshot("notes", content={"note": 1}), self.snapshot("empty", content={}),
                self.snapshot(".hidden", content={"files": {}}),
                self.snapshot("renamed", content={"session_id": "someone-else", "files": {}})]
        used = self.snapshot("sess-used")
        os.utime(used, None)  # created long ago, used now (the Stop hook refreshes it)
        kept.append(used)
        report = maintenance.cleanup(self.root, execute=True, current_session_id="sess-current")
        self.assertEqual([r["path"] for r in report["removed"]
                          if r["category"] == "stale_session_snapshot"],
                         [".claude/runtime/session/sess-old.json"])
        self.assertFalse(stale.exists())
        for p in kept:
            self.assertTrue(p.is_file(), p)

    def test_current_session_snapshot_kept_when_latest_names_another(self):
        a = self.snapshot("sess-A")
        report = maintenance.startup_cleanup(self.root, current_session_id="sess-A")
        self.assertNotIn(".claude/runtime/session/sess-A.json",
                         [r["path"] for r in report["removed"]])
        self.assertTrue(a.is_file())
        maintenance.cleanup(self.root, execute=True)  # another session starting later
        self.assertFalse(a.exists())

    def test_unreadable_latest_keeps_every_snapshot(self):
        stale = self.snapshot("sess-old")
        (self.sdir / "latest.json").write_text("{not json", encoding="utf-8")
        maintenance.cleanup(self.root, execute=True)
        self.assertTrue(stale.is_file())

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_file_cited_by_a_tracked_document_is_kept(self):
        stale = self.snapshot("sess-old")
        ds = self.root / "docs" / "maintenance" / ".DS_Store"
        ds.parent.mkdir(parents=True)
        ds.write_bytes(b"\x00")
        (self.root / ".DS_Store").write_bytes(b"\x00")
        (self.root / "docs" / "maintenance" / "report.md").write_text(
            "Evidence: `.claude/runtime/session/sess-old.json`, `docs/maintenance/.DS_Store`, "
            "`tools/pkg/__pycache__/m.cpython-39.pyc`; a generic mention: .DS_Store\n",
            encoding="utf-8")
        (self.root / "untracked.md").write_text("tools/pkg/__pycache__/other.cpython-39.pyc\n",
                                                encoding="utf-8")
        (self.cache / "other.cpython-39.pyc").write_bytes(b"o")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "docs/maintenance/report.md"], check=True)
        report = maintenance.cleanup(self.root, execute=True)
        self.assertEqual(sorted(report["kept_referenced"]),
                         [".claude/runtime/session/sess-old.json", "docs/maintenance/.DS_Store",
                          "tools/pkg/__pycache__/m.cpython-39.pyc"])
        self.assertTrue(stale.is_file())
        self.assertTrue(ds.is_file())
        self.assertTrue((self.cache / "m.cpython-39.pyc").is_file())
        self.assertFalse((self.root / ".DS_Store").exists())  # a bare name cites no file
        self.assertFalse((self.cache / "other.cpython-39.pyc").exists())  # untracked document

    def test_reference_check_unavailable_removes_nothing(self):
        (self.root / ".git").mkdir()  # a repository Git cannot read
        (self.root / ".DS_Store").write_bytes(b"\x00")
        report = maintenance.cleanup(self.root, execute=True)
        self.assertEqual(report["removed"], [])
        self.assertTrue(any("reference check unavailable" in a for a in report["anomalies"]))
        self.assertTrue((self.root / ".DS_Store").is_file())

    @unittest.skipIf(RUNS_AS_ROOT, "permissions are not enforced for root")
    def test_unreadable_folder_is_an_anomaly_not_a_failure(self):
        locked = self.root / "tools" / "pkg2" / "__pycache__"
        locked.mkdir(parents=True)
        (locked / "x.cpython-39.pyc").write_bytes(b"\x00")
        (self.root / ".DS_Store").write_bytes(b"\x00")
        os.chmod(locked, 0)
        try:
            plan = maintenance.cleanup(self.root, execute=False)
            report = maintenance.startup_cleanup(self.root)
        finally:
            os.chmod(locked, stat.S_IRWXU)
        self.assertEqual([a for a in plan["anomalies"] if "tools/pkg2/__pycache__" in a],
                         plan["anomalies"][:1])
        self.assertEqual(len(plan["anomalies"]), 1)  # reported once
        self.assertFalse((self.root / ".DS_Store").exists())  # the rest is still cleaned
        self.assertTrue(any("tools/pkg2/__pycache__" in line for line in report["summary_lines"]))
        self.assertTrue((locked / "x.cpython-39.pyc").is_file())

    def test_startup_cleanup_never_raises(self):
        with mock.patch.object(maintenance, "_candidates", side_effect=RuntimeError("boom")):
            report = maintenance.startup_cleanup(self.root)
        self.assertTrue(any("boom" in line for line in report["summary_lines"]))


class TestArchiveSafety(unittest.TestCase):
    """Path relations refused both ways, removal bound to the CURRENT content
    of the source, cumulative move index, reports instead of traces
    (E-01 to E-04)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = helpers.make_workspace(self.tmp.name)
        (self.root / "docs" / "maintenance").mkdir(parents=True)
        self.archives = self.root / "docs" / "maintenance" / "archives"
        self.source = self.base / "external backups"
        (self.source / "sub").mkdir(parents=True)
        (self.source / "a.zip").write_bytes(b"zip-a")
        (self.source / "sub" / "b.pine").write_text("//@version=6\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def imported(self, source=None):
        plan = maintenance.plan_import(self.root, source or self.source)
        self.assertTrue(plan.get("ok"), plan)
        r = maintenance.execute_import(self.root, plan)
        self.assertTrue(r["ok"], r)
        return plan

    def manifest(self):
        return json.loads((self.archives / "MANIFEST.json").read_text(encoding="utf-8"))

    @staticmethod
    def forged(plan, folder):
        """A well-formed plan pointed at another folder (fingerprints recomputed),
        so that only the path checks can refuse it."""
        forged = dict(plan, source=str(folder), source_real=str(Path(folder).resolve()),
                      source_identity=maintenance._dir_identity(folder))
        forged["plan_id"] = maintenance._plan_id(forged)
        return forged

    def test_source_containing_the_workspace_refused_at_every_step(self):
        (self.base / "lot.zip").write_bytes(b"lot")
        for spelling in (self.base, Path(str(self.base).swapcase())):
            plan = maintenance.plan_import(self.root, spelling)
            self.assertFalse(plan["ok"], spelling)
        self.assertIn("CONTAINS the workspace", maintenance.plan_import(self.root, self.base)["error"])
        forged = self.forged(self.imported(), self.base)
        for result in (maintenance.execute_import(self.root, forged),
                       maintenance.remove_source(self.root, forged, yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("CONTAINS the workspace", result["error"])
        self.assertTrue((self.archives / "a.zip").is_file())
        self.assertTrue((self.base / "lot.zip").is_file())

    def test_source_equal_to_or_inside_the_workspace_refused(self):
        for src in (self.root, self.root / "docs", self.archives):
            src.mkdir(parents=True, exist_ok=True)
            (src / "x.zip").write_bytes(b"x")
            plan = maintenance.plan_import(self.root, src)
            self.assertFalse(plan["ok"], src)
            self.assertIn("workspace", plan["error"])
        forged = self.forged(self.imported(), self.root / "docs")
        self.assertIn("inside the workspace",
                      maintenance.remove_source(self.root, forged, yes=True)["error"])
        self.assertTrue((self.root / "docs" / "x.zip").is_file())

    def test_other_installation_refused_both_ways(self):
        other = self.base / "zone" / "other install"
        (other / "tools" / "pws_workspace").mkdir(parents=True)
        (other / "docs").mkdir()
        (other / "docs" / "r.zip").write_bytes(b"r")
        for src, words in ((self.base / "zone", "contains a PWS installation"),
                           (other, "is a PWS installation"),
                           (other / "docs", "inside another PWS installation")):
            plan = maintenance.plan_import(self.root, src)
            self.assertFalse(plan["ok"], src)
            self.assertIn(words, plan["error"])

    def test_symlinked_source_refused(self):
        link = self.base / "shortcut"
        os.symlink(self.source, link)
        plan = maintenance.plan_import(self.root, link)
        self.assertFalse(plan["ok"])
        self.assertIn("symbolic link", plan["error"])
        forged = dict(self.imported(), source=str(link))
        forged["plan_id"] = maintenance._plan_id(forged)
        r = maintenance.remove_source(self.root, forged, yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("symbolic link", r["error"])
        self.assertTrue((self.source / "a.zip").is_file())

    def test_target_outside_the_archives_refused_and_refused_plan_never_imported(self):
        (self.root / "standards").mkdir()
        (self.root / "standards" / "INDEX.md").write_text("# derived index\n", encoding="utf-8")
        for target in ("../outside", "standards", "/tmp/elsewhere", "docs/maintenance"):
            plan = maintenance.plan_import(self.root, self.source, target)
            self.assertFalse(plan["ok"], target)
            r = maintenance.execute_import(self.root, plan)  # a report, never a KeyError
            self.assertFalse(r["ok"])
            self.assertIn("refused plan", r["error"])
        self.assertFalse(self.archives.exists())
        self.assertEqual((self.root / "standards" / "INDEX.md").read_text(encoding="utf-8"),
                         "# derived index\n")

    def test_removal_checks_the_current_content_of_the_source(self):
        plan = self.imported()
        self.assertTrue(maintenance.verify_import(self.root, plan)[0])
        (self.source / "new delivery.zip").write_bytes(b"never inventoried")
        r = maintenance.remove_source(self.root, plan, yes=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["changes"], {"new_not_archived": ["new delivery.zip"]})
        (self.source / "new delivery.zip").unlink()
        (self.source / "a.zip").write_bytes(b"zip-a, newer version")
        r = maintenance.remove_source(self.root, plan, yes=True)
        self.assertEqual(r["changes"], {"modified_since_plan": ["a.zip"]})
        self.assertTrue(self.source.is_dir())
        (self.source / "a.zip").write_bytes(b"zip-a")
        (self.source / "sub" / "b.pine").unlink()  # already archived: nothing left to lose
        r = maintenance.remove_source(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual((r["files"], r["already_absent"]), (1, ["sub/b.pine"]))
        r = maintenance.remove_source(self.root, plan, yes=True)
        self.assertTrue(r["ok"], r)
        self.assertFalse(self.source.exists())

    def test_stale_plan_on_a_recreated_folder_refused(self):
        plan = self.imported()
        self.assertTrue(maintenance.remove_source(self.root, plan, yes=True)["ok"])
        (self.base / "filler").mkdir()  # never hand the freed inode back to the new folder
        (self.source / "sub").mkdir(parents=True)  # recreated later, even with the same files
        (self.source / "a.zip").write_bytes(b"zip-a")
        (self.source / "sub" / "b.pine").write_text("//@version=6\n", encoding="utf-8")
        self.assertIn("stale plan", maintenance.execute_import(self.root, plan)["error"])
        r = maintenance.remove_source(self.root, plan, yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("stale plan", r["error"])
        self.assertTrue((self.source / "a.zip").is_file())

    def test_links_and_special_files_reported_without_blocking_plan_but_block_removal(self):
        outside = self.base / "elsewhere"
        outside.mkdir()
        (outside / "precious.zip").write_bytes(b"p")
        os.symlink(outside / "precious.zip", self.source / "file link.zip")
        os.symlink(outside, self.source / "folder link")
        os.mkfifo(str(self.source / "pipe"))
        plan = maintenance.plan_import(self.root, self.source)  # never blocks on the pipe
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(sorted((s["rel"], s["kind"]) for s in plan["skipped"]),
                         [("file link.zip", "symlink"), ("folder link", "symlink"),
                          ("pipe", "special")])
        self.assertEqual(len(plan["anomalies"]), 3)
        self.assertTrue(maintenance.execute_import(self.root, plan)["ok"])
        r = maintenance.remove_source(self.root, plan, yes=True)
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["changes"]["not_verifiable"]), 3)
        self.assertTrue((self.source / "a.zip").is_file())
        self.assertTrue((outside / "precious.zip").is_file())

    @unittest.skipIf(RUNS_AS_ROOT, "permissions are not enforced for root")
    def test_unreadable_file_is_an_anomaly_not_a_trace(self):
        locked = self.source / "locked.zip"
        locked.write_bytes(b"secret")
        os.chmod(locked, 0)
        try:
            plan = maintenance.plan_import(self.root, self.source)
        finally:
            os.chmod(locked, stat.S_IRUSR | stat.S_IWUSR)
        self.assertTrue(plan["ok"], plan)
        self.assertTrue(any(a.startswith("unreadable file skipped: locked.zip")
                            for a in plan["anomalies"]))

    def test_manifest_and_index_are_cumulative(self):
        first = self.imported()
        second_src = self.base / "second folder"
        second_src.mkdir()
        (second_src / "c.zip").write_bytes(b"zip-c")
        (second_src / "copy of a.zip").write_bytes(b"zip-a")  # archived by the first import
        second = self.imported(second_src)
        manifest = self.manifest()
        self.assertEqual([r["source_folder"] for r in manifest["imports"]],
                         [str(self.source), str(second_src)])
        self.assertEqual([e["rel"] for e in manifest["entries"]],
                         ["a.zip", "sub/b.pine", "c.zip", "copy of a.zip"])
        index = (self.archives / "INDEX.md").read_text(encoding="utf-8")
        for text in (str(self.source), str(second_src), "sub/b.pine", "copy of a.zip"):
            self.assertIn(text, index)
        self.assertTrue(maintenance.verify_import(self.root, first)[0])
        self.assertTrue(maintenance.verify_import(self.root, second)[0])
        at = manifest["imports"][0]["imported_at"]
        self.assertTrue(maintenance.execute_import(self.root, first)["ok"])  # same import again
        again = self.manifest()
        self.assertEqual([r["imported_at"] for r in again["imports"]][:1], [at])
        self.assertEqual(len(again["imports"]), 2)
        self.assertEqual(len(again["entries"]), 4)

    def test_single_import_manifest_of_earlier_versions_is_kept(self):
        self.archives.mkdir(parents=True)
        core.atomic_write_json(self.archives / "MANIFEST.json", {
            "imported_at": "2026-11-06T02:23:41Z", "source_folder": "/old/backups",
            "target": "docs/maintenance/archives", "note": "older", "anomalies": [],
            "failures": [], "entries": [{
                "rel": "old.zip", "action": "copy", "bytes": 3, "classification": "archive",
                "destination": "docs/maintenance/archives/old.zip", "sha256": "0" * 64,
                "mtime": "2026-09-22T02:20:39Z"}]})
        (self.archives / "INDEX.md").write_text(maintenance.INDEX_TITLE + "\n\nolder\n",
                                                encoding="utf-8")
        self.imported()
        manifest = self.manifest()
        self.assertEqual(manifest["format"], 2)
        self.assertEqual(manifest["imports"][0]["source_folder"], "/old/backups")
        self.assertEqual([e["rel"] for e in manifest["entries"]], ["old.zip", "a.zip", "sub/b.pine"])
        index = (self.archives / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("/old/backups", index)
        self.assertIn("`old.zip`", index)

    def test_foreign_or_orphan_index_never_overwritten(self):
        self.archives.mkdir(parents=True)
        (self.archives / "INDEX.md").write_text("# my own notes\n", encoding="utf-8")
        plan = maintenance.plan_import(self.root, self.source)
        r = maintenance.execute_import(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertIn("not a PWS move index", r["error"])
        self.assertEqual((self.archives / "INDEX.md").read_text(encoding="utf-8"), "# my own notes\n")
        self.assertFalse((self.archives / "a.zip").exists())
        (self.archives / "INDEX.md").write_text(maintenance.INDEX_TITLE + "\n", encoding="utf-8")
        r = maintenance.execute_import(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertIn("without MANIFEST.json", r["error"])

    def test_missing_or_empty_source_never_empties_the_index(self):
        self.imported()
        before = (self.archives / "MANIFEST.json").read_text(encoding="utf-8")
        missing = maintenance.plan_import(self.root, self.base / "typo")
        self.assertFalse(missing["ok"])
        self.assertIn("missing", missing["error"])
        only_ds = self.base / "only ds"
        only_ds.mkdir()
        (only_ds / ".DS_Store").write_bytes(b"\x00")
        empty = maintenance.plan_import(self.root, only_ds)
        self.assertFalse(empty["ok"])
        self.assertIn("nothing to import", empty["error"])
        for plan in (missing, empty):
            self.assertFalse(maintenance.execute_import(self.root, plan)["ok"])
            self.assertFalse(maintenance.verify_import(self.root, plan)[0])
            self.assertFalse(maintenance.remove_source(self.root, plan, yes=True)["ok"])
        self.assertEqual((self.archives / "MANIFEST.json").read_text(encoding="utf-8"), before)
        self.assertTrue((only_ds / ".DS_Store").is_file())

    def test_index_names_and_existing_destinations_need_a_sub_folder(self):
        (self.source / "MANIFEST.json").write_text('{"entries": ["older"]}', encoding="utf-8")
        plan = maintenance.plan_import(self.root, self.source)
        self.assertFalse(plan["ok"])
        self.assertIn("move index", plan["error"])
        sub = maintenance.plan_import(self.root, self.source, "docs/maintenance/archives/older set")
        self.assertTrue(sub["ok"], sub)
        self.assertTrue(maintenance.execute_import(self.root, sub)["ok"])
        self.assertIn("older", (self.archives / "older set" / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(self.manifest()["format"], 2)
        other = self.base / "other"
        other.mkdir()
        (other / "a.zip").write_bytes(b"different content, same name")
        clash = maintenance.plan_import(self.root, other, "docs/maintenance/archives/older set")
        self.assertFalse(clash["ok"])
        self.assertIn("already exists", clash["error"])

    def test_file_changed_between_plan_and_import_installs_nothing(self):
        plan = maintenance.plan_import(self.root, self.source)
        (self.source / "a.zip").write_bytes(b"changed after the plan")
        r = maintenance.execute_import(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertIn("changed since the plan", r["failures"][0])
        self.assertFalse((self.archives / "a.zip").exists())
        self.assertEqual(list(self.archives.rglob("*" + maintenance.PARTIAL_SUFFIX)), [])
        self.assertFalse(maintenance.remove_source(self.root, plan, yes=True)["ok"])

    def test_interrupted_import_never_leaves_a_truncated_archive(self):
        plan = maintenance.plan_import(self.root, self.source)
        with mock.patch("os.replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                maintenance.execute_import(self.root, plan)
        self.assertFalse((self.archives / "a.zip").exists())
        self.assertFalse(maintenance.verify_import(self.root, plan)[0])
        self.assertFalse(maintenance.remove_source(self.root, plan, yes=True)["ok"])
        self.assertTrue(maintenance.execute_import(self.root, plan)["ok"])  # resumed
        self.assertEqual(list(self.archives.rglob("*" + maintenance.PARTIAL_SUFFIX)), [])
        self.assertTrue(maintenance.verify_import(self.root, plan)[0])

    def test_older_or_altered_plans_refused_for_import_and_removal(self):
        plan = self.imported()
        older = {k: plan[k] for k in ("source", "target", "entries", "anomalies", "counts")}
        self.assertTrue(maintenance.verify_import(self.root, older)[0])  # reading stays possible
        for result in (maintenance.execute_import(self.root, older),
                       maintenance.remove_source(self.root, older, yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("older version", result["error"])
        altered = json.loads(json.dumps(plan))
        altered["entries"][0]["sha256"] = "f" * 64
        r = maintenance.remove_source(self.root, altered, yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("altered", r["error"])
        self.assertTrue(self.source.is_dir())

    def test_unexpected_errors_are_reports(self):
        plan = maintenance.plan_import(self.root, self.source)
        with mock.patch.object(maintenance, "_load_manifest",
                               side_effect=OSError(28, "No space left on device")):
            r = maintenance.execute_import(self.root, plan)
        self.assertFalse(r["ok"])
        self.assertIn("No space left on device", r["error"])
        with mock.patch.object(maintenance, "_scan_source", side_effect=ValueError("odd")):
            self.assertFalse(maintenance.plan_import(self.root, self.source)["ok"])
            self.assertFalse(maintenance.remove_source(self.root, plan, yes=True)["ok"])
        self.assertTrue(self.source.is_dir())



class TestArchivesPlanCommand20261113(unittest.TestCase):
    """Audit E-04 (2026-11-13): a refused archive plan exits 1 and is never
    written over an existing plan file."""

    def test_refused_plan_exits_1_and_keeps_the_existing_plan_file(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_workspace(tmp)
            plan_file = Path(tmp) / "approved-plan.json"
            plan_file.write_text('{"kept": true}', encoding="utf-8")
            for source in (str(Path(tmp) / "missing"), str(root)):
                r = subprocess.run([sys.executable, "-m", "tools.pws_workspace", "--root", str(root),
                                    "maintenance", "archives-plan", "--source", source,
                                    "--plan-file", str(plan_file)],
                                   capture_output=True, text=True,
                                   cwd=str(Path(__file__).resolve().parents[2]))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                out = json.loads(r.stdout)
                self.assertFalse(out["ok"])
                self.assertTrue(out["error"])
                self.assertFalse(out["plan_file_written"])
                self.assertEqual(plan_file.read_text(encoding="utf-8"), '{"kept": true}')


if __name__ == "__main__":
    unittest.main()
