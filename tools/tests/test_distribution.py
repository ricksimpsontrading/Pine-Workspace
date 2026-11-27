# SPDX-License-Identifier: Apache-2.0
"""Public distribution build: allow-list, never-ship exclusions, target
safety, personal-pattern scan (2026-11-06). Integration test on the real
workspace core (read-only on the source, writes into a temp target).
Review of 2026-11-13: target compared by physical identity (RS-05), only
the bytecode of tools/**/__pycache__ ignored in a previous build (RS-06),
LICENSING.md a core file (m7), normalized permissions (m9)."""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, distribution

ROOT = core.workspace_root()


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / "pws public build"

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_is_clean_and_excludes_personal_content(self):
        # deterministic simulated environment: the building account is named
        # `agent`, a common word of the shipped instructions (never the real user)
        r = distribution.build(ROOT, self.target, account="agent")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["leaked"], [])
        self.assertEqual(r["personal_pattern_hits"], [], r["personal_pattern_hits"])
        for never in ("scripts", "docs/maintenance", ".claude/runtime", "pws.config.json",
                      ".claude/settings.local.json", "docs/architecture/BOOTSTRAP_REPORT.md"):
            self.assertFalse((self.target / never).exists(), never)
        for must in ("CLAUDE.md", "README.md", "INSTALL.md", "install.py", "LICENSE", "NOTICE",
                     "THIRD_PARTY_NOTICES.md", "VERSION", "standards/PINE_SCRIPT_V6_STANDARD.md",
                     "tools/pws_workspace/__main__.py", "tools/tests/helpers.py",
                     ".claude/skills/pws/SKILL.md", "docs/licensing/PROFILES.md",
                     "tools/pine_exec/package-lock.json", "tools/pine_exec/PINETS_LICENSE"):
            self.assertTrue((self.target / must).is_file(), must)
        self.assertFalse((self.target / "tools" / "pine_exec" / "node_modules").exists())
        marker = json.loads((self.target / distribution.MARKER).read_text(encoding="utf-8"))
        from tools.pws_workspace import version
        self.assertEqual(marker["workspace_version"], version.WORKSPACE_VERSION)
        self.assertIn("LICENSE", marker["files"])
        self.assertEqual(marker["platform_support"]["windows"], "deferred")

    def test_runner_imports_ship_and_vela_is_the_only_optional_viewer(self):
        # every local module runner.mjs imports is shipped: without one no local test runs at all
        import re
        runner = (ROOT / "tools" / "pine_exec" / "runner.mjs").read_text(encoding="utf-8")
        local = sorted(set(re.findall(r"from '\./([A-Za-z0-9_.-]+\.mjs)'", runner)))
        self.assertIn("graphics.mjs", local)
        r = distribution.build(ROOT, self.target, account="agent")
        self.assertTrue(r["ok"], r)
        for mod in local:
            self.assertTrue((self.target / "tools" / "pine_exec" / mod).is_file(), mod)
        self.assertEqual(r["optional_components"], [])
        self.assertTrue((self.target / "tools" / "pws_workspace" / "annex_reader.py").is_file())   # reader: core
        self.assertFalse((self.target / "tools" / "vela_view").exists())
        # the terminal viewers are withdrawn: no component, never shipped
        self.assertEqual(sorted(distribution.OPTIONAL_DIRS), ["vela-view"])
        self.assertIn("tools/visual", distribution.NEVER_SHIP)
        refused = distribution.build(ROOT, Path(self.tmp.name) / "viewer", optional=("visual-viewer",))
        self.assertFalse(refused["ok"])
        with_vela = Path(self.tmp.name) / "with vela"
        r3 = distribution.build(ROOT, with_vela, account="agent", optional=("vela-view",))
        self.assertTrue(r3["ok"], r3)
        self.assertEqual(r3["optional_components"], ["vela-view"])
        for f in ("tools/vela_view/package.json", "tools/vela_view/package-lock.json", "tools/vela_view/page/pws-view.js",
                  "tools/pws_workspace/annex_reader.py", "tools/pws_workspace/READER_CONTRACT.md"):
            self.assertTrue((with_vela / f).is_file(), f)
        for absent in ("tools/vela_view/node_modules", "tools/visual"):
            self.assertFalse((with_vela / absent).exists(), absent)
        marker = json.loads((with_vela / distribution.MARKER).read_text(encoding="utf-8"))
        self.assertFalse([k for k in marker["files"] if k.startswith("tools/visual/") or k.endswith(".jsonl")])
        bad = distribution.build(ROOT, Path(self.tmp.name) / "unknown", optional=("nope",))
        self.assertFalse(bad["ok"])
        self.assertFalse((Path(self.tmp.name) / "unknown").exists())

    def test_target_safety(self):
        other = Path(self.tmp.name) / "existing project"
        other.mkdir()
        (other / "main.py").write_text("print(1)\n", encoding="utf-8")
        r = distribution.build(ROOT, other)
        self.assertFalse(r["ok"])
        self.assertTrue((other / "main.py").is_file())
        r = distribution.build(ROOT, self.target)
        self.assertTrue(r["ok"])
        r2 = distribution.build(ROOT, self.target)
        self.assertFalse(r2["ok"])  # previous build present, --force required
        self.assertIn("--force", r2["error"])
        r3 = distribution.build(ROOT, self.target, force=True)
        self.assertTrue(r3["ok"])
        inside = ROOT / "docs" / "maintenance" / "should not happen"
        self.assertFalse(distribution.build(ROOT, inside)["ok"])

    def test_personal_patterns_derive_from_configuration(self):
        pats = distribution.personal_patterns(ROOT, account="agent")
        self.assertTrue(any(f == "personal-path" and p.pattern.startswith("/Users/") for f, p in pats))
        sample = Path(self.tmp.name) / "t"
        sample.mkdir()
        home_path = "/" + "Users" + "/" + "someone" + "/project"   # built, never a literal in a shipped file
        (sample / "a.md").write_text("see %s\n" % home_path, encoding="utf-8")
        (sample / "b.md").write_text("nothing personal\n", encoding="utf-8")
        hits = distribution.scan_personal(sample, pats)
        self.assertEqual([(h["path"], h["family"]) for h in hits], [("a.md", "personal-path")])

    # ---- rule revised 2026-11-07 after an independent run under an account named `agent` ----

    def _scan(self, pats, text):
        sample = Path(self.tmp.name) / ("s%d" % len(list(Path(self.tmp.name).iterdir())))
        sample.mkdir()
        (sample / "x.md").write_text(text, encoding="utf-8")
        return [h["family"] for h in distribution.scan_personal(sample, pats)]

    def test_common_account_name_never_flags_ordinary_mentions(self):
        from tools.tests import helpers
        root = helpers.make_workspace(self.tmp.name)
        helpers.configure(root, holder="Holder Test", aliases=("HolderAlias",))
        pats = distribution.personal_patterns(root, account="agent")
        for ordinary in ("the agent `pws-pine-cartographer` is read-only", "Agent tool", "an AGENT reads",
                         "`.claude/agents/pws-pine-reviewer.md`", "user-agent header", "subagent / agents"):
            self.assertEqual(self._scan(pats, ordinary + "\n"), [], ordinary)
        # a simulated environment (Path.home patched for this test only) gives the same patterns
        from unittest import mock
        with mock.patch.object(Path, "home", return_value=Path("/" + "home") / "agent"):
            derived = distribution.personal_patterns(root)
        self.assertEqual([(f, p.pattern) for f, p in derived], [(f, p.pattern) for f, p in pats])

    def test_personal_paths_account_traces_and_configured_identity_stay_detected(self):
        from tools.tests import helpers
        root = helpers.make_workspace(self.tmp.name)
        helpers.configure(root, holder="Holder Test", aliases=("HolderAlias",))
        pats = distribution.personal_patterns(root, account="agent")
        # personal texts are BUILT at run time: this shipped file must not carry them literally
        users, home, a = "/" + "Users", "/" + "home", "ag" + "ent"
        for personal in (users + "/%s/project" % a, home + "/%s/.claude/" % a, users + "/someone/x",
                         home + "/other/x/", "C:" + "\\Users\\%s\\x" % a):
            self.assertEqual(self._scan(pats, "see %s\n" % personal), ["personal-path"], personal)
        for trace in ("/Volumes/backup/%s/notes" % a, "backup:/srv/%s" % a, "~%s/.claude" % a, "~%s" % a,
                      "%s@workstation.local" % a, "USER=%s" % a, "LOGNAME: %s" % a):
            self.assertEqual(self._scan(pats, "trace %s end\n" % trace), ["account-trace"], trace)
        for identity in ("© 2026 Holder Test", "HolderAlias wrote this", "by holdertest"):
            self.assertEqual(self._scan(pats, identity + "\n"), ["configured-identity"], identity)
        # a distinctive account name follows the same contexts (no dependence on the real user)
        pats = distribution.personal_patterns(root, account="zq-distinct-user")
        self.assertEqual(self._scan(pats, "copied from /Volumes/zq-distinct-user/notes\n"), ["account-trace"])
        self.assertEqual(self._scan(pats, "mail zq-distinct-user@example.invalid\n"), ["account-trace"])
        self.assertEqual(self._scan(pats, "the word zq-distinct-user alone\n"), [])
        # short or empty account names add no account pattern at all
        self.assertEqual([f for f, _ in distribution.personal_patterns(root, account="me")].count("account-trace"), 0)
        self.assertEqual([f for f, _ in distribution.personal_patterns(root, account="")].count("account-trace"), 0)

    def test_build_from_a_common_account_name_is_clean_and_a_real_trace_is_not(self):
        r = distribution.build(ROOT, self.target, account="agent")
        self.assertTrue(r["clean"], r["personal_pattern_hits"])
        # the scan still catches an explicit trace of that account planted in the built tree
        home, a = "/" + "home", "ag" + "ent"
        (self.target / "docs" / "note.md").write_text("built under %s/%s/pws\n" % (home, a), encoding="utf-8")
        hits = distribution.scan_personal(self.target, distribution.personal_patterns(ROOT, account="agent"))
        self.assertEqual([(h["path"], h["family"]) for h in hits], [("docs/note.md", "personal-path")])
        (self.target / "docs" / "note.md").write_text("checked by ~%s on that host\n" % a, encoding="utf-8")
        hits = distribution.scan_personal(self.target, distribution.personal_patterns(ROOT, account="agent"))
        self.assertEqual([(h["path"], h["family"]) for h in hits], [("docs/note.md", "account-trace")])


    def test_force_never_deletes_an_installation_the_source_or_unlisted_files(self):
        # audit A-01 (2026-11-13): the target is classified before any deletion
        def tree(base):
            return sorted(p.relative_to(base).as_posix() for p in Path(base).rglob("*") if p.is_file())
        install = Path(self.tmp.name) / "an installation"
        self.assertTrue(distribution.build(ROOT, install)["ok"])
        (install / "pws.config.json").write_text("{}\n", encoding="utf-8")
        (install / "scripts" / "mine").mkdir(parents=True)
        (install / "scripts" / "mine" / "Mine.pine").write_text("//@version=6\n", encoding="utf-8")
        before = tree(install)
        for target in (install, install / "."):
            r = distribution.build(install, target, force=True)
            self.assertFalse(r["ok"], r)
            self.assertEqual(tree(install), before)            # nothing deleted, nothing written
        r = distribution.build(ROOT, install, force=True)       # an installation is never a "previous build"
        self.assertFalse(r["ok"])
        self.assertIn("installation", r["error"])
        self.assertEqual(tree(install), before)
        parent = Path(self.tmp.name) / "around"
        (parent / "inner").mkdir(parents=True)
        self.assertIn("contains the source", distribution.build(parent / "inner", parent, force=True)["error"])
        # a genuine previous build holding an unlisted file is not replaced
        build = Path(self.tmp.name) / "previous build"
        self.assertTrue(distribution.build(ROOT, build)["ok"])
        (build / "notes.txt").write_text("user notes\n", encoding="utf-8")
        r = distribution.build(ROOT, build, force=True)
        self.assertFalse(r["ok"])
        self.assertIn("not part of the previous build", r["error"])
        self.assertTrue((build / "notes.txt").is_file())
        (build / "notes.txt").unlink()
        r = distribution.build(ROOT, build, force=True)         # genuine build: swapped, nothing left beside it
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["replaced_previous_build"])
        self.assertEqual([p.name for p in build.parent.iterdir() if ".pws-" in p.name], [])
        link = Path(self.tmp.name) / "link to build"
        os.symlink(str(build), str(link))
        self.assertIn("symbolic link", distribution.build(ROOT, link, force=True)["error"])

    # ---- review of 2026-11-13: RS-05, RS-06, m7, m9 ----

    def test_target_inside_or_around_the_source_is_refused_whatever_its_spelling(self):
        """RS-05: folders compared by physical identity — inside the source
        written with another case (case-insensitive volume), through a
        symbolic link or a `..`, or a parent of the source written with
        another case: refused before anything is written."""
        around = Path(self.tmp.name) / "Around"
        src = around / "Source WS"
        (src / "sub").mkdir(parents=True)
        (src / "keep.txt").write_text("source content\n", encoding="utf-8")
        link = Path(self.tmp.name) / "link to source sub"
        os.symlink(str(src / "sub"), str(link))

        def tree():
            return sorted(p.relative_to(around).as_posix() for p in around.rglob("*"))
        before = tree()
        inside = [src / "dist-out", link / "dist-out", link / ".." / "dist-out"]
        containing = [around]
        if (Path(self.tmp.name) / "around" / "source ws").exists():      # case-insensitive volume
            inside.append(Path(self.tmp.name) / "around" / "SOURCE WS" / "dist-out")
            inside.append(Path(self.tmp.name) / "AROUND" / "source ws")
            containing.append(Path(self.tmp.name) / "AROUND")
        for target, expected in ([(t, "target must be outside the source workspace") for t in inside]
                                 + [(t, "target contains the source workspace — refusing") for t in containing]):
            with self.subTest(target=str(target)):
                self.assertEqual(distribution.classify_target(src, target), ("refused", expected))
                r = distribution.build(src, target, force=True)
                self.assertEqual((r["ok"], r["error"]), (False, expected))
                self.assertEqual(tree(), before)
                self.assertEqual(distribution.target_relation_problem(src, target), expected)
        self.assertIsNone(distribution.target_relation_problem(src, Path(self.tmp.name) / "elsewhere"))

    def test_force_ignores_only_the_bytecode_of_a_pycache_under_tools(self):
        """RS-06: a previous build holding any other unlisted file — `*.lock`,
        a note in `__pycache__/`, bytecode outside tools/, `.DS_Store` — is
        never replaced (the file stays); the bytecode Python writes under
        tools/ is the only exemption."""
        build = Path(self.tmp.name) / "previous build"
        self.assertTrue(distribution.build(ROOT, build)["ok"])
        for rel in ("notes.lock", "tools/__pycache__/my-notes.md", "docs/__pycache__/x.cpython-39.pyc",
                    ".DS_Store", "tools/pws_workspace/__pycache__/sub/x.cpython-39.pyc", "tools/notes.pyc"):
            with self.subTest(rel=rel):
                p = build / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("user content\n", encoding="utf-8")
                kind, message = distribution.classify_target(ROOT, build)
                self.assertEqual(kind, "refused")
                r = distribution.build(ROOT, build, force=True)
                self.assertFalse(r["ok"], r)
                self.assertIn("not part of the previous build (%s)" % rel, r["error"])
                self.assertIn("nothing is deleted", r["error"])
                self.assertEqual(p.read_text(encoding="utf-8"), "user content\n")
                p.unlink()
        pyc = build / "tools" / "pws_workspace" / "__pycache__" / "core.cpython-39.pyc"
        pyc.parent.mkdir(parents=True, exist_ok=True)
        pyc.write_bytes(b"\x00fictitious bytecode")
        r = distribution.build(ROOT, build, force=True)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["replaced_previous_build"])
        self.assertNotIn("previous_build_kept", r)
        self.assertFalse(pyc.exists())
        self.assertEqual([p.name for p in build.parent.iterdir() if ".pws-" in p.name], [])

    def test_unlisted_file_found_at_the_removal_keeps_the_old_build(self):
        """RS-06, second net: a file the marker does not list, found when the
        old tree is about to be removed (it appeared after the
        classification), keeps that tree beside the new build, reported."""
        build = Path(self.tmp.name) / "previous build"
        self.assertTrue(distribution.build(ROOT, build)["ok"])
        (build / "notes.lock").write_text("user note\n", encoding="utf-8")
        with mock.patch.object(distribution, "classify_target",
                               side_effect=lambda root, target: ("previous-build", "simulated: file added later")):
            r = distribution.build(ROOT, build, force=True)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["replaced_previous_build"])
        self.assertIn("previous_build_kept", r, "the old tree holding an unlisted file must never be deleted")
        kept = Path(r["previous_build_kept"])
        self.assertEqual((kept / "notes.lock").read_text(encoding="utf-8"), "user note\n")
        self.assertEqual(r["previous_build_kept_why"]["unlisted_files"], ["notes.lock"])
        self.assertIn("delete it yourself", r["note"])
        self.assertTrue((build / distribution.MARKER).is_file())
        self.assertFalse((build / "notes.lock").exists())

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_licensing_map_is_a_core_file_shipped_once(self):
        """m7: docs/licensing/LICENSING.md not tracked by Git fails the build,
        like tools/pine_exec/LICENSE; tracked, it is shipped once."""
        src = Path(self.tmp.name) / "source tree"
        self.assertTrue(distribution.build(ROOT, src)["ok"])
        git = ["git", "-C", str(src), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"],
                     ["rm", "-q", "--cached", "docs/licensing/LICENSING.md"], ["commit", "-q", "-m", "untracked"]):
            subprocess.run(git + args, check=True, capture_output=True)
        out = Path(self.tmp.name) / "out untracked"
        r = distribution.build(src, out)
        self.assertFalse(r["ok"], r)
        self.assertIn("core files not tracked by Git: docs/licensing/LICENSING.md", r["error"])
        self.assertFalse(out.exists())
        for args in (["add", "docs/licensing/LICENSING.md"], ["commit", "-q", "-m", "tracked"]):
            subprocess.run(git + args, check=True, capture_output=True)
        with mock.patch.object(distribution, "_ship", wraps=distribution._ship) as ship:
            r = distribution.build(src, Path(self.tmp.name) / "out tracked")
        self.assertTrue(r["ok"], r)
        copies = [c for c in ship.call_args_list
                  if Path(c[0][1]).as_posix().endswith("/docs/licensing/LICENSING.md")]
        self.assertEqual(len(copies), 1)
        built = Path(self.tmp.name) / "out tracked"
        self.assertEqual((built / "docs" / "licensing" / "LICENSING.md").read_bytes(),
                         (src / "docs" / "licensing" / "LICENSING.md").read_bytes())
        # a file FILE_MAP ships under another name stays in docs/licensing/ too (a build is a valid source)
        for rel in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "docs/licensing/PWS_LICENSE_Apache-2.0.txt",
                    "docs/licensing/PWS_NOTICE.md", "docs/licensing/THIRD_PARTY_NOTICES.md"):
            self.assertTrue((built / rel).is_file(), rel)
        self.assertEqual(sorted(json.loads((built / distribution.MARKER).read_text(encoding="utf-8"))["files"]),
                         sorted(json.loads((src / distribution.MARKER).read_text(encoding="utf-8"))["files"]))

    def test_shipped_files_get_normalized_permissions(self):
        """m9: 0644, or 0755 for a file executable by its owner — never the
        local mode (a 0600 PROVENANCE.json is not shipped as 0600)."""
        src = Path(self.tmp.name) / "source tree"
        self.assertTrue(distribution.build(ROOT, src)["ok"])
        os.chmod(str(src / "tools" / "pine_exec" / "PROVENANCE.json"), 0o600)
        os.chmod(str(src / "install.py"), 0o700)
        os.chmod(str(src / "docs" / "licensing" / "PROFILES.md"), 0o666)
        out = Path(self.tmp.name) / "out"
        r = distribution.build(src, out)
        self.assertTrue(r["ok"], r)
        modes = {p.relative_to(out).as_posix(): stat.S_IMODE(p.stat().st_mode) for p in out.rglob("*") if p.is_file()}
        self.assertEqual((modes["tools/pine_exec/PROVENANCE.json"], modes["install.py"],
                          modes["docs/licensing/PROFILES.md"], modes[distribution.MARKER], modes["VERSION"]),
                         (0o644, 0o755, 0o644, 0o644, 0o644))
        self.assertEqual(set(modes.values()) - {0o644, 0o755}, set())


if __name__ == "__main__":
    unittest.main()
