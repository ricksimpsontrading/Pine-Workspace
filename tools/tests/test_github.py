# SPDX-License-Identifier: Apache-2.0
"""GitHub export: content policy by profile and destination, staging,
diff against a local clone, publication to a LOCAL bare repository (no
network), explicit --yes (2026-11-06). Corrections of 2026-11-13 (audit of
2026-11-12: I-02, C-15, C-14, C-03, C-16, C-17, I-05): plan and clone bound
to the current destination and source visibility, symbolic links and
indirect copies of a closed source, anchored allow-list, recognized and
current terms documents, template residues versus TradingView alert
placeholders, target-name collisions. Fictitious products and identities.

I-06 (holder's decision of 2026-11-13): a send carrying a closed source is
preceded by the check of the real GitHub repository and of the remote git
really pushes to. GitHub is simulated (FakeGitHub: injected `gh` executor,
local bare repositories standing for GitHub repositories); the real `gh` is
replaced for the whole module and must never run.

Review of 2026-11-13: strict reading of the remote URLs and real host shown
(RS-01), credential helper shown by its name only (RS-03), public source
copying a closed source (RS-04). Crafted hosts are `.invalid` (RFC 2606) and
git cannot open a network transport in these tests."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, github, licensing, profiles
from tools.tests import helpers

REAL_GH_RUN = github._gh_run
REAL_GH_CALLS = []
GH_VIEW = ["repo", "view", "https://github.com/owner/vault", "--json", "nameWithOwner,visibility,isPrivate,url"]


def _real_gh_blocked(args):
    """Stands for the real gh during these tests: records the call (the tests
    check none happened) and establishes nothing."""
    REAL_GH_CALLS.append(list(args))
    return 127, "", "the real gh is blocked during the tests"


def setUpModule():
    github._gh_run = _real_gh_blocked


def tearDownModule():
    github._gh_run = REAL_GH_RUN


def git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)


class FakeGitHub:
    """Simulated GitHub for the I-06 check: the answers of `gh repo view`
    (injected executor) and the github.com identity of LOCAL bare
    repositories, which stand for GitHub repositories (no network)."""

    def __init__(self):
        self.answers, self.identities, self.calls = {}, {}, []

    def repo(self, name, visibility="PRIVATE", is_private=None, name_with_owner=None, url=None):
        nwo = name_with_owner or name
        self.answer(name, 0, json.dumps({
            "nameWithOwner": nwo, "visibility": visibility,
            "isPrivate": (visibility != "PUBLIC") if is_private is None else is_private,
            "url": url or "https://github.com/%s" % nwo}))

    def answer(self, name, rc, out="", err=""):
        self.answers[name.casefold()] = (rc, out, err)

    def serve(self, bare, name):
        self.identities[os.path.realpath(str(bare))] = name

    def gh(self, args):
        self.calls.append(list(args))
        repo = args[2].split("https://github.com/", 1)[-1] if len(args) > 2 else ""
        return self.answers.get(repo.casefold(), (1, "", "GraphQL: Could not resolve to a Repository with the "
                                                          "name '%s'. (repository)" % repo))

    def repo_of_url(self, url):
        if isinstance(url, str) and os.path.isabs(url) and os.path.realpath(url) in self.identities:
            return self.identities[os.path.realpath(url)]
        return github._github_repo_of_url(url)

    @property
    def kw(self):
        return {"gh_runner": self.gh, "repo_of_url": self.repo_of_url}


def make_bare_with_main(tmp, name="remote repo"):
    bare = Path(tmp) / ("%s.git" % name)
    git("init", "--bare", "--initial-branch=main", str(bare))
    seed = Path(tmp) / ("seed %s" % name)
    git("clone", str(bare), str(seed))
    git("config", "user.email", "t@example.invalid", cwd=seed)
    git("config", "user.name", "tests", cwd=seed)
    (seed / "README.md").write_text("# remote\n", encoding="utf-8")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "seed", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    return bare


def listing(bare):
    return [x for x in git("ls-tree", "-r", "--name-only", "main", cwd=bare).stdout.split("\n") if x]


def set_license(pdir, **changes):
    """Edit the manifest directly (as a hand edit would): the export must
    judge the file it finds, whatever path wrote it."""
    m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
    m["license"].update(changes)
    (pdir / "SCRIPT.json").write_text(json.dumps(m, indent=2), encoding="utf-8")


def reasons(plan):
    return {e["path"]: e["reason"] for e in plan["excluded"]}


def froms(plan):
    return sorted(i["from"] for i in plan["included"])


class TestGithubPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        github.destination_add(self.root, "pub", "owner/public-scripts", "public", "Published")
        github.destination_add(self.root, "priv", "owner/private-vault", "private", "")

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_imported_licence_to_analyse_is_never_exported(self):
        """C-19 (2026-11-13): an imported script whose existing licence is still
        « to analyse » is not exported; once the exact licence is recorded it is."""
        mpl = ("// This source code is subject to the terms of the Mozilla Public License 2.0 at "
               "https://mozilla.org/MPL/2.0/\n// © Original Author\n//@version=6\n")
        helpers.make_product_v3(self.root, slug="imported-one", profile="FREE", header=mpl,
                                license_overrides={"id": None, "grant": "license", "origin": "imported",
                                                   "status": "to-analyse"})
        plan = github.export_plan(self.root, "imported-one", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("not exported", plan["error"])
        manifest = self.root / "scripts" / "imported-one" / "SCRIPT.json"
        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["license"].update({"id": "MPL-2.0", "status": "confirmed"})
        manifest.write_text(json.dumps(data), encoding="utf-8")
        # contract change of 2026-11-14 (holder's request): the export of an imported script also waits for the
        # declaration of its original legal documents — here none accompanies it (MPL notice in the header)
        plan = github.export_plan(self.root, "imported-one", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("are not declared", plan["error"])
        self.assertTrue(licensing.confirm_publication(self.root, "imported-one", license_documents=[])["ok"])
        plan = github.export_plan(self.root, "imported-one", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual((plan["license"]["origin"], plan["license"]["status"]), ("imported", "confirmed"))
        self.assertEqual(plan["legal_documents"]["declared"], [])

    def test_free_public_includes_source_and_tutorial_only(self):
        pdir = helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        (pdir / "docs").mkdir()
        (pdir / "docs" / "TUTORIAL.md").write_text("# Tutorial\n", encoding="utf-8")
        (pdir / "docs" / "STANDARD_COMPLIANCE.md").write_text("suivi\n", encoding="utf-8")
        (pdir / "DECISIONS.md").write_text("# D\n", encoding="utf-8")
        plan = github.export_plan(self.root, "free-one", "pub")
        self.assertTrue(plan["ok"], plan)
        tos = sorted(i["to"] for i in plan["included"])
        self.assertEqual(tos, ["Published/free-one/TUTORIAL.md", "Published/free-one/free-one.pine"])
        excluded = {e["path"]: e["reason"] for e in plan["excluded"]}
        self.assertIn("SCRIPT.json", excluded)
        self.assertIn("CLAUDE.md", excluded)
        self.assertIn("DECISIONS.md", excluded)
        self.assertIn("docs/STANDARD_COMPLIANCE.md", excluded)
        self.assertIn("validation/current.json", excluded)
        staged = Path(plan["staging"]) / "files" / "Published" / "free-one" / "free-one.pine"
        self.assertTrue(staged.is_file())
        self.assertTrue((Path(plan["staging"]) / "PLAN.json").is_file())

    def test_closed_source_never_to_public_destination(self):
        helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        plan = github.export_plan(self.root, "paid-one", "pub")
        self.assertTrue(plan["ok"])
        self.assertEqual([i for i in plan["included"] if i["to"].endswith(".pine")], [])
        reasons = [e["reason"] for e in plan["excluded"] if e["path"] == "My Indicator.pine"]
        self.assertTrue(reasons and "never exported to a public destination" in reasons[0])
        plan_priv = github.export_plan(self.root, "paid-one", "priv")
        self.assertEqual([i["to"] for i in plan_priv["included"]], ["paid-one/paid-one.pine"])

    def test_draft_legal_documents_never_exported(self):
        pdir = helpers.make_product_v2(self.root, slug="free-draft", profile="FREE")
        (pdir / "release").mkdir()
        (pdir / "release" / "EULA.md").write_text("# EULA\n\nProvider: {{PROVIDER_LEGAL_NAME}}\n", encoding="utf-8")
        (pdir / "release" / "CHANGELOG.md").write_text("# Changelog\n- 1.0.0\n", encoding="utf-8")
        plan = github.export_plan(self.root, "free-draft", "pub")
        tos = sorted(i["to"] for i in plan["included"])
        self.assertIn("Published/free-draft/CHANGELOG.md", tos)
        self.assertNotIn("Published/free-draft/EULA.md", tos)
        reasons = {e["path"]: e["reason"] for e in plan["excluded"]}
        self.assertIn("draft", reasons["release/EULA.md"])

    def test_not_registered_or_unknown_refused(self):
        helpers.make_product(self.root, slug="half", with_context=False)
        self.assertFalse(github.export_plan(self.root, "half", "pub")["ok"])
        self.assertFalse(github.export_plan(self.root, "nope", "pub")["ok"])
        self.assertFalse(github.export_plan(self.root, "half", "nowhere")["ok"])

    def test_destinations_validation_and_removal(self):
        r = github.destination_add(self.root, "bad name", "x", "public")
        self.assertFalse(r["ok"])
        self.assertFalse(github.destination_add(self.root, "pub", "o/r", "public")["ok"])
        self.assertTrue(github.destination_remove(self.root, "priv")["ok"])
        self.assertEqual([d["name"] for d in github.destinations(self.root)], ["pub"])

    def test_status_never_prints_token_lines(self):
        self.assertEqual(github._filter_secret_lines("Logged in\nToken: gho_abc\n- Token scopes: x"),
                         "Logged in")

    def test_status_shows_the_credential_helper_by_its_name_only(self):
        """Review RS-03 (2026-11-13): an inline helper or a value carrying a
        password or a token is never shown, even in part; a named helper is
        shown without its arguments (fictitious values only)."""
        cases = (
            ("!f() { echo username=x; echo password=ghp_FAKE0000; }; f", "INLINE_HELPER_SHOWN"),
            ("!/opt/fake/bin/gh auth git-credential", "INLINE_HELPER_SHOWN"),
            ("cache --timeout=900 --password=FAKE-SECRET-0000", "SECRET_HELPER_SHOWN"),
            ("store --file /opt/fake/creds/fictitious-store", "store"),
            ("/opt/fake/bin/git-credential-fake --token-file=/x", "SECRET_HELPER_SHOWN"),
            ("/opt/fake/bin/git-credential-fake --verbose", "git-credential-fake"),
            ("osxkeychain", "osxkeychain"),
        )
        for value, shown in cases:
            with self.subTest(value=value):
                def fake_run(cmd, cwd=None, timeout=120):
                    self.assertEqual(cmd, ["git", "config", "--get", "credential.helper"])
                    return 0, value, ""
                with mock.patch.object(github.shutil, "which", return_value=None), \
                        mock.patch.object(github, "_run", fake_run):
                    out = github.status(self.root)
                dumped = json.dumps(out)
                for secret in ("ghp_FAKE0000", "FAKE-SECRET-0000", "password=", "--file", "fictitious-store",
                               "/opt/fake", "--verbose"):
                    self.assertNotIn(secret, dumped)
                self.assertEqual(out["git_credential_helper"],
                                 getattr(github, shown) if shown.endswith("_SHOWN") else shown)
        with mock.patch.object(github.shutil, "which", return_value=None), \
                mock.patch.object(github, "_run", lambda cmd, cwd=None, timeout=120: (1, "", "")):
            self.assertIsNone(github.status(self.root)["git_credential_helper"])


class TestGithubPublishLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        self.bare = make_bare_with_main(self.tmp.name)
        github.destination_add(self.root, "local", "owner/local", "public", "Published",
                               "main", url=str(self.bare))
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        # contract change of 2026-11-14 (holder's request): every send checks the identity of the destination —
        # the local bare repository stands for the GitHub repository owner/local (simulated identity)
        self.gh = FakeGitHub()
        self.gh.serve(self.bare, "owner/local")

    def tearDown(self):
        self.tmp.cleanup()
        self.assertEqual(REAL_GH_CALLS, [])

    def test_fetch_diff_publish_requires_yes(self):
        plan = github.export_plan(self.root, "free-one", "local")
        self.assertTrue(plan["ok"])
        d = github.export_diff(self.root, "free-one", "local", **self.gh.kw)
        self.assertFalse(d["ok"])  # not fetched yet
        f = github.fetch(self.root, "local")
        self.assertTrue(f["ok"], f)
        clone = Path(f["path"])
        git("config", "user.email", "t@example.invalid", cwd=clone)
        git("config", "user.name", "tests", cwd=clone)
        d = github.export_diff(self.root, "free-one", "local", **self.gh.kw)
        self.assertTrue(d["ok"])
        self.assertEqual([c["change"] for c in d["changes"]], ["added"])
        r = github.publish(self.root, "free-one", "local", "export", yes=False, **self.gh.kw)
        self.assertFalse(r["ok"])
        listing = git("ls-tree", "-r", "--name-only", "main", cwd=self.bare).stdout
        self.assertNotIn("free-one.pine", listing)
        r = github.publish(self.root, "free-one", "local", "export free-one", yes=True, **self.gh.kw)
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["destination_check"]["ok"], r["destination_check"]["remote"]["repository"]),
                         (True, "owner/local"))
        listing = git("ls-tree", "-r", "--name-only", "main", cwd=self.bare).stdout
        self.assertIn("Published/free-one/free-one.pine", listing)
        self.assertNotIn("SCRIPT.json", listing)
        d = github.export_diff(self.root, "free-one", "local", **self.gh.kw)
        self.assertEqual([c["change"] for c in d["changes"]], ["unchanged"])
        r = github.publish(self.root, "free-one", "local", "again", yes=True, **self.gh.kw)
        self.assertFalse(r["published"])
        self.assertEqual(self.gh.calls, [])           # public content: GitHub never queried


class TestGithubContentPolicy(unittest.TestCase):
    """Allow-list hardening (audit 2026-11-12: C-14, C-15, C-03, C-16, C-17, I-05)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        shutil.copytree(str(core.workspace_root() / licensing.TEMPLATES_REL),
                        str(self.root / licensing.TEMPLATES_REL))
        github.destination_add(self.root, "pub", "owner/public-scripts", "public", "Published")
        github.destination_add(self.root, "priv", "owner/private-vault", "private", "")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, pdir, rel, text):
        p = pdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_tutorial_patterns_anchored_at_the_product_root(self):
        """C-14: research/docs/…, validation/release/…, docs/x/release/… never match."""
        pdir = helpers.make_product_v2(self.root, slug="nested", profile="FREE")
        internal = ("research/docs/competitor-tutorial-notes.md", "validation/release/tutorial-check.md",
                    "docs/tracking/release/TUTORIAL_REVIEW.md", "docs/sub/USER_TUTORIAL.md")
        for rel in ("docs/USER_TUTORIAL.md", "release/tutorial.md") + internal:
            self.write(pdir, rel, "# Notes\n")
        plan = github.export_plan(self.root, "nested", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(froms(plan), ["My Indicator.pine", "docs/USER_TUTORIAL.md", "release/tutorial.md"])
        for rel in internal:
            self.assertIn(rel, reasons(plan))
        self.assertEqual(reasons(plan)["research/docs/competitor-tutorial-notes.md"], "internal research")
        self.assertEqual(reasons(plan)["validation/release/tutorial-check.md"], "validation evidence")

    def test_symbolic_links_never_followed_nor_exported(self):
        """C-15: an internal link with an allowed name (file or folder) never
        carries the closed source to a destination — public or private."""
        pdir = helpers.make_product_v2(self.root, slug="linked", profile="COMMERCIAL")
        (pdir / "release").mkdir()
        os.symlink("../My Indicator.pine", str(pdir / "release" / "README.md"))
        self.write(pdir, "real-docs/USER_TUTORIAL.md", "# Tutorial\n")
        os.symlink("real-docs", str(pdir / "docs"))
        for dest in ("pub", "priv"):
            plan = github.export_plan(self.root, "linked", dest)
            self.assertTrue(plan["ok"], plan)
            self.assertNotIn("release/README.md", froms(plan))
            self.assertIn("symbolic link", reasons(plan)["release/README.md"])
            self.assertIn("symbolic link", reasons(plan)["docs"])
            staged = Path(plan["staging"]) / "files"
            self.assertFalse(any(f.is_symlink() for f in staged.rglob("*")))
            self.assertEqual(sorted(f.name for f in staged.rglob("*") if f.is_file()),
                             [] if dest == "pub" else ["linked.pine"])
        # a declared source that is itself a link is never followed either
        pfree = helpers.make_product_v2(self.root, slug="free-linked", profile="FREE",
                                        source_name="Main.pine")
        os.replace(str(pfree / "Main.pine"), str(pfree / "real.pine"))
        os.symlink("real.pine", str(pfree / "Main.pine"))
        plan = github.export_plan(self.root, "free-linked", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual([i for i in plan["included"] if i["to"].endswith(".pine")], [])
        self.assertIn("declared source is a symbolic link", reasons(plan)["Main.pine"])

    def test_copies_and_pine_code_of_a_closed_source_never_go_public(self):
        """Indirect paths: hard link, copy under an allowed name, a line of the
        source, Pine markers. A private destination may receive them."""
        pdir = helpers.make_product_v2(self.root, slug="leaky", profile="COMMERCIAL")
        source = pdir / "My Indicator.pine"
        with open(str(source), "a", encoding="utf-8") as f:
            f.write("secretLevel = ta.sma(close, 21) * 1.0618\n")
        (pdir / "release").mkdir()
        os.link(str(source), str(pdir / "release" / "README.md"))
        (pdir / "README.md").write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
        self.write(pdir, "docs/A_TUTORIAL.md", "# Tutorial\n\nThe level is `secretLevel = ta.sma(close,  21) * 1.0618`.\n")
        self.write(pdir, "docs/B_TUTORIAL.md", "# Tutorial\n\n```pine\nx = 1\n```\n")
        self.write(pdir, "docs/C_TUTORIAL.md", "# Tutorial\n\n    //@version=6\n")
        self.write(pdir, "docs/D_TUTORIAL.md", "# Tutorial\n\nindicator(\"My clone\")\n")
        self.write(pdir, "release/CHANGELOG.md", "# Changelog\n- 1.0.0: migrated to `//@version=6`, "
                                                 "new indicator() title.\n")
        plan = github.export_plan(self.root, "leaky", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(froms(plan), ["release/CHANGELOG.md"])
        r = reasons(plan)
        self.assertIn("copy of the closed source", r["release/README.md"])
        self.assertIn("never exported to a public destination", r["README.md"])
        self.assertIn("reproduces 1 code line(s) of the closed source", r["docs/A_TUTORIAL.md"])
        self.assertIn("pine code block", r["docs/B_TUTORIAL.md"])
        self.assertIn("//@version= annotation", r["docs/C_TUTORIAL.md"])
        self.assertIn("declaration statement", r["docs/D_TUTORIAL.md"])
        # the private destination may receive the source and these documents
        (pdir / "README.md").unlink()                      # (target-name collision otherwise)
        plan = github.export_plan(self.root, "leaky", "priv")
        self.assertTrue(plan["ok"], plan)
        self.assertIn("My Indicator.pine", froms(plan))
        self.assertIn("release/README.md", froms(plan))
        self.assertIn("docs/B_TUTORIAL.md", froms(plan))

    def test_public_product_document_reproducing_another_closed_source(self):
        pclosed = helpers.make_product_v2(self.root, slug="vault", profile="PRIVATE",
                                          body='indicator("Vault Indicator")\nalphaLine = ta.ema(close, 34)\n'
                                               'betaLine = ta.wma(close, 55)\nplot(alphaLine - betaLine)\n')
        pfree = helpers.make_product_v2(self.root, slug="free-doc", profile="FREE")
        body = (pclosed / "My Indicator.pine").read_text(encoding="utf-8").split("//@version=6\n", 1)[1]
        self.write(pfree, "docs/TUTORIAL.md", "# Tutorial\n\nSee:\n\n" + body.replace("indicator", "// indicator"))
        self.write(pfree, "release/CHANGELOG.md", "# Changelog\nalphaLine = ta.ema(close, 34)\n")
        plan = github.export_plan(self.root, "free-doc", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertIn("closed source of product 'vault'", reasons(plan)["docs/TUTORIAL.md"])
        self.assertIn("release/CHANGELOG.md", froms(plan))      # one shared line is not a copy
        self.assertIn("docs/TUTORIAL.md", froms(github.export_plan(self.root, "free-doc", "priv")))

    def test_public_source_reproducing_another_closed_source(self):
        """Review RS-04 (2026-11-13): the declared source of a PUBLIC-source
        product that copies another product's closed source (same bytes, or
        three of its code lines under its own header) never goes to a public
        destination; towards a private one it is closed content (I-06 check
        announced). Two shared lines are not a copy."""
        body = ('indicator("Vault Indicator")\nalphaLine = ta.ema(close, 34)\nbetaLine = ta.wma(close, 55)\n'
                'plot(alphaLine - betaLine, title="Spread")\n')
        pclosed = helpers.make_product_v2(self.root, slug="vault", profile="COMMERCIAL", body=body)
        closed_bytes = (pclosed / "My Indicator.pine").read_bytes()
        pcopy = helpers.make_product_v2(self.root, slug="free-copy", profile="FREE")
        (pcopy / "My Indicator.pine").write_bytes(closed_bytes)
        helpers.make_product_v2(self.root, slug="free-derived", profile="FREE",
                                body='indicator("Derived")\n' + body.split("\n", 1)[1])
        helpers.make_product_v2(self.root, slug="free-own", profile="FREE",
                                body='indicator("Own")\nalphaLine = ta.ema(close, 34)\nbetaLine = ta.wma(close, 55)\n'
                                     'plot(close - alphaLine, title="Own spread")\n')
        for slug, lines in (("free-copy", 4), ("free-derived", 3)):
            with self.subTest(slug=slug):
                plan = github.export_plan(self.root, slug, "pub")
                self.assertTrue(plan["ok"], plan)
                self.assertEqual([i for i in plan["included"] if i["role"] == "source"], [])
                why = reasons(plan)["My Indicator.pine"]
                self.assertIn("reproduces the closed source of product 'vault' (%d code line(s))" % lines, why)
                self.assertIn("never exported to a public destination", why)
                self.assertTrue(any("My Indicator.pine excluded" in w for w in plan["warnings"]), plan["warnings"])
                self.assertNotIn("visibility_check", plan)
                staged = Path(plan["staging"]) / "files"
                self.assertEqual([f for f in staged.rglob("*.pine")], [])
                priv = github.export_plan(self.root, slug, "priv")
                self.assertEqual([i["from"] for i in priv["included"] if i["role"] == "source"], ["My Indicator.pine"])
                self.assertEqual([c["path"] for c in priv["visibility_check"]["closed_content"]],
                                 ["%s/%s.pine" % (slug, slug)])
                self.assertIn("the product's public source reproduces the closed source of product 'vault'",
                              priv["visibility_check"]["closed_content"][0]["reason"])
        plan = github.export_plan(self.root, "free-own", "pub")       # two shared code lines: not a copy
        self.assertEqual([i["from"] for i in plan["included"] if i["role"] == "source"], ["My Indicator.pine"])
        self.assertNotIn("visibility_check", github.export_plan(self.root, "free-own", "priv"))

    def test_terms_ref_must_designate_a_recognized_terms_document(self):
        """C-03 (export side): SCRIPT.json or DECISIONS.md never leave as « terms »."""
        pdir = helpers.make_product_v2(self.root, slug="terms-any", profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        self.write(pdir, "DECISIONS.md", "# Decisions\nD-001 internal.\n")
        self.write(pdir, "README.md", "# Readme\n")
        for target in ("SCRIPT.json", "DECISIONS.md"):
            set_license(pdir, terms_ref=target)
            for dest in ("pub", "priv"):
                plan = github.export_plan(self.root, "terms-any", dest)
                self.assertTrue(plan["ok"], plan)
                self.assertNotIn(target, froms(plan))
                self.assertIn("not a recognized terms document", reasons(plan)[target])
                self.assertTrue(any("not a recognized terms document" in w for w in plan["warnings"]))
        set_license(pdir, terms_ref="README.md")
        plan = github.export_plan(self.root, "terms-any", "pub")
        item = [i for i in plan["included"] if i["from"] == "README.md"][0]
        self.assertEqual((item["role"], item["reason"]), ("document", "allowed product document"))
        self.assertTrue(any("ordinary product document" in w for w in plan["warnings"]))

    def _eula_product(self, slug):
        pdir = helpers.make_product_v2(self.root, slug=slug, profile="COMMERCIAL",
                                       license_overrides={"created_year": 2024})
        fields = {k: "value for %s" % k for k in licensing.EULA_REQUIRED_FIELDS}
        self.write(pdir, "release/eula-fields.json", json.dumps(fields))
        w = licensing.write_rendered(self.root, slug, "eula", "release/EULA.md")
        self.assertTrue(w["ok"] and not w["draft"], w)
        return pdir, fields

    def test_terms_document_no_longer_current_is_reported_and_excluded(self):
        """C-17: a field changed after the EULA was written."""
        pdir, fields = self._eula_product("stale-eula")
        set_license(pdir, terms_ref="release/EULA.md")
        plan = github.export_plan(self.root, "stale-eula", "pub")
        item = [i for i in plan["included"] if i["from"] == "release/EULA.md"][0]
        self.assertEqual((item["role"], item["reason"]), ("terms", "licence terms referenced by the manifest"))
        fields["GOVERNING_LAW_REFERENCE"] = "NEW governing law reference"
        (pdir / "release" / "eula-fields.json").write_text(json.dumps(fields), encoding="utf-8")
        plan = github.export_plan(self.root, "stale-eula", "pub")
        self.assertNotIn("release/EULA.md", froms(plan))
        self.assertIn("no longer current", reasons(plan)["release/EULA.md"])
        self.assertIn("license write --slug stale-eula --kind eula", reasons(plan)["release/EULA.md"])
        self.assertTrue(any("release/EULA.md excluded" in w for w in plan["warnings"]))
        # the same rule holds for an EULA exported as an ordinary allowed document
        set_license(pdir, terms_ref=None)
        self.assertIn("no longer current", reasons(github.export_plan(self.root, "stale-eula", "priv"))
                      ["release/EULA.md"])
        # written again: current, exported again
        licensing.write_rendered(self.root, "stale-eula", "eula", "release/EULA.md")
        self.assertIn("release/EULA.md", froms(github.export_plan(self.root, "stale-eula", "pub")))

    def test_terms_written_elsewhere_recognized_by_its_current_rendering(self):
        pdir, _ = self._eula_product("custom-dest")
        os.replace(str(pdir / "release" / "EULA.md"), str(pdir / "release" / "TERMS.md"))
        set_license(pdir, terms_ref="release/TERMS.md")
        plan = github.export_plan(self.root, "custom-dest", "pub")
        item = [i for i in plan["included"] if i["from"] == "release/TERMS.md"][0]
        self.assertEqual(item["role"], "terms")

    def test_alert_placeholders_are_not_template_residues(self):
        """C-16: {{ticker}} and [[1, 2]] are ordinary text; template keys and
        [[?…: blocks are residues."""
        pdir = helpers.make_product_v2(self.root, slug="alerts", profile="FREE")
        self.write(pdir, "docs/TUTORIAL.md", "# Tutorial\nUse {{ticker}}, {{close}}, {{interval}}, "
                                             "{{strategy.order.action}}; body {\"s\": \"{{ticker}}\"}.\n")
        self.write(pdir, "release/RELEASE_NOTES.md", "# Notes\n`levels = [[1, 2], [3, 4]]` }} ]]\n")
        self.write(pdir, "release/README.md", "# Readme\nProvider: {{PROVIDER_LEGAL_NAME}}\n")
        self.write(pdir, "release/CHANGELOG.md", "# Changelog\n[[?ADDITIONAL_TERMS:extra]]\n")
        plan = github.export_plan(self.root, "alerts", "pub")
        self.assertIn("docs/TUTORIAL.md", froms(plan))
        self.assertIn("release/RELEASE_NOTES.md", froms(plan))
        self.assertIn("draft", reasons(plan)["release/README.md"])
        self.assertIn("{{PROVIDER_LEGAL_NAME}}", reasons(plan)["release/README.md"])
        self.assertIn("residual licence-template block", reasons(plan)["release/CHANGELOG.md"])
        self.assertIn("draft", github._draft_reason(pdir / "release" / "README.md"))
        self.assertIsNone(github._draft_reason(pdir / "docs" / "TUTORIAL.md"))

    def test_source_with_an_unrendered_header_field_is_excluded(self):
        """C-16: « © {{YEAR_RANGE}} » pasted before the creation year was known."""
        header = ("// This work is licensed under the Attribution-NonCommercial-ShareAlike 4.0 "
                  "International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n"
                  "// © {{YEAR_RANGE}} Holder Test\n// Version: 1.0.0\n//@version=6\n")
        helpers.make_product_v2(self.root, slug="draft-header", profile="FREE", header=header,
                                body='indicator("T")\nalertcondition(close > open, "Up", "{{ticker}} up")\n')
        for dest in ("pub", "priv"):
            plan = github.export_plan(self.root, "draft-header", dest)
            self.assertTrue(plan["ok"], plan)
            self.assertEqual([i for i in plan["included"] if i["to"].endswith(".pine")], [])
            self.assertIn("{{YEAR_RANGE}}", reasons(plan)["My Indicator.pine"])
        helpers.make_product_v2(self.root, slug="alert-source", profile="FREE",
                                body='indicator("T")\nalertcondition(close > open, "Up", "{{ticker}} up")\n')
        plan = github.export_plan(self.root, "alert-source", "pub")
        self.assertIn("My Indicator.pine", froms(plan))

    def test_target_name_collision_refuses_the_plan(self):
        """I-05: README.md and release/README.md (or names differing by case)."""
        pdir = helpers.make_product_v2(self.root, slug="collide", profile="FREE")
        ok = github.export_plan(self.root, "collide", "pub")
        self.assertTrue(ok["ok"])
        staging = Path(ok["staging"])
        self.write(pdir, "README.md", "# Root readme\n")
        self.write(pdir, "release/README.md", "# Release readme\n")
        self.write(pdir, "docs/USER_TUTORIAL.md", "# A\n")
        self.write(pdir, "release/user_tutorial.md", "# B\n")
        plan = github.export_plan(self.root, "collide", "pub")
        self.assertFalse(plan["ok"])
        self.assertIn("same target name", plan["error"])
        self.assertEqual(sorted(c["to"].lower() for c in plan["collisions"]),
                         ["published/collide/readme.md", "published/collide/user_tutorial.md"])
        # the previous plan of this product and destination can no longer be used
        self.assertFalse((staging / "PLAN.json").exists())
        self.assertTrue((staging / "PLAN.invalidated.json").is_file())
        self.assertTrue(plan["invalidated_previous_plan"])
        self.assertIn("no export plan", github.export_diff(self.root, "collide", "pub")["error"])

    def test_unreadable_or_special_documents_are_not_exported(self):
        pdir = helpers.make_product_v2(self.root, slug="odd", profile="FREE")
        (pdir / "README.md").write_bytes(b"\xff\xfe# not utf-8\n")
        if hasattr(os, "mkfifo"):
            (pdir / "release").mkdir()
            os.mkfifo(str(pdir / "release" / "CHANGELOG.md"))
        plan = github.export_plan(self.root, "odd", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertIn("not UTF-8", reasons(plan)["README.md"])
        if hasattr(os, "mkfifo"):
            self.assertIn("not a regular file", reasons(plan)["release/CHANGELOG.md"])
        self.assertEqual(froms(plan), ["My Indicator.pine"])

    def test_destination_fields_used_as_paths_and_refspecs_are_checked(self):
        self.assertFalse(github.destination_add(self.root, "g", "o/r", "public", ".git/hooks")["ok"])
        self.assertFalse(github.destination_add(self.root, "b", "o/r", "public", "", "main:other")["ok"])
        self.assertFalse(github.destination_add(self.root, "u", "o/r", "public", "", "main", url="--upload-pack=x")["ok"])
        self.assertTrue(github.destination_add(self.root, "ok", "o/r", "public", "Published/v2", "release/v2")["ok"])


class TestGithubBinding(unittest.TestCase):
    """I-02: plan and clone bound to the current destination and source
    visibility; stale states invalidated, never deleted (local bare
    repositories, no network)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        self.paid = helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        self.env_backup = {k: os.environ.get(k) for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                                                          "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}
        os.environ.update({"GIT_AUTHOR_NAME": "tests", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                           "GIT_COMMITTER_NAME": "tests", "GIT_COMMITTER_EMAIL": "t@example.invalid"})
        # I-06: a closed source reaches a "private" destination only once GitHub reports it PRIVATE
        self.gh = FakeGitHub()

    def tearDown(self):
        for k, v in self.env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()
        self.assertEqual(REAL_GH_CALLS, [])

    def github_private(self, bare, repo):
        """Simulated GitHub: `bare` is the private repository `repo`."""
        self.gh.serve(bare, repo)
        self.gh.repo(repo, "PRIVATE")
        return self.gh.kw

    def bare(self, name):
        return make_bare_with_main(self.tmp.name, name)

    def add(self, name, visibility, bare, repo=None):
        r = github.destination_add(self.root, name, repo or "owner/%s" % bare.stem.replace(" ", "-"),
                                   visibility, "", "main", url=str(bare))
        self.assertTrue(r["ok"], r)
        return r

    def pine_files(self, bare):
        return [x for x in listing(bare) if x.endswith(".pine")]

    def test_destination_redeclared_public_under_the_same_name(self):
        """Audit r04 S1 / 06 H4: a plan prepared for a private destination is
        never published once the name designates a public one."""
        repo = self.bare("vault")
        self.add("s1", "private", repo)
        plan = github.export_plan(self.root, "paid-one", "s1")
        self.assertEqual([i["to"] for i in plan["included"]], ["paid-one/paid-one.pine"])
        r = github.destination_remove(self.root, "s1")
        self.assertEqual(len(r["invalidated_plans"]), 1)
        self.add("s1", "public", repo)
        self.assertTrue(github.fetch(self.root, "s1")["ok"])
        for result in (github.export_diff(self.root, "paid-one", "s1"),
                       github.publish(self.root, "paid-one", "s1", "export", yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("no export plan", result["error"])
        self.assertEqual(self.pine_files(repo), [])

    def test_plan_refused_when_the_configuration_was_edited_by_hand(self):
        repo = self.bare("vault")
        self.add("s1", "private", repo)
        github.export_plan(self.root, "paid-one", "s1")
        self.assertTrue(github.fetch(self.root, "s1")["ok"])
        cfg_path = self.root / "pws.config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["github"]["destinations"][0]["visibility"] = "public"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        for result in (github.export_diff(self.root, "paid-one", "s1"),
                       github.publish(self.root, "paid-one", "s1", "export", yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("changed since the plan", result["error"])
            self.assertIn("visibility: plan 'private', now 'public'", result["error"])
            self.assertIn("export-plan", result["error"])
            self.assertEqual(result["destination"]["visibility"], "public")
        self.assertEqual(self.pine_files(repo), [])
        # a new plan applies the rule to the current destination
        plan = github.export_plan(self.root, "paid-one", "s1")
        self.assertEqual([i for i in plan["included"] if i["to"].endswith(".pine")], [])

    def test_stale_clone_of_a_previous_destination_is_set_aside_never_used(self):
        """Audit r04 S2 / 06 H5: the clone of the former public destination is
        never the target of the new private one; it is set aside, not deleted."""
        old_public, new_private = self.bare("old public"), self.bare("new private")
        self.add("d", "public", old_public)
        self.assertEqual(github.fetch(self.root, "d")["action"], "clone")
        r = github.destination_remove(self.root, "d")
        moved = Path(r["clone_set_aside"]["path"])
        self.assertTrue((moved / ".git").is_dir())
        self.assertTrue(Path(str(moved) + ".json").is_file())
        self.add("d", "private", new_private)
        plan = github.export_plan(self.root, "paid-one", "d")
        self.assertEqual([i["to"] for i in plan["included"]], ["paid-one/paid-one.pine"])
        f = github.fetch(self.root, "d")
        self.assertEqual((f["ok"], f["action"]), (True, "clone"))
        self.assertTrue(f["clone"]["matches_destination"])
        r = github.publish(self.root, "paid-one", "d", "export", yes=True,
                           **self.github_private(new_private, "owner/new-private"))
        self.assertTrue(r["published"], r)
        self.assertEqual(r["visibility_check"]["observed"]["visibility"], "PRIVATE")
        self.assertEqual(self.pine_files(new_private), ["paid-one/paid-one.pine"])
        self.assertEqual(self.pine_files(old_public), [])

    def test_hand_edited_destination_stale_clone_refused_then_set_aside_by_fetch(self):
        old_public, new_private = self.bare("old public"), self.bare("new private")
        self.add("hand", "public", old_public)
        self.assertTrue(github.fetch(self.root, "hand")["ok"])
        cfg_path = self.root / "pws.config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["github"]["destinations"][0].update({"visibility": "private", "url": str(new_private),
                                                 "repo": "owner/new-private"})
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        plan = github.export_plan(self.root, "paid-one", "hand")
        self.assertFalse(plan["clone"]["matches_destination"])
        for result in (github.export_diff(self.root, "paid-one", "hand"),
                       github.publish(self.root, "paid-one", "hand", "export", yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("stale local clone", result["error"])
            self.assertIn("github fetch --destination hand", result["error"])
        self.assertEqual(self.pine_files(old_public), [])
        f = github.fetch(self.root, "hand")
        self.assertTrue(f["ok"], f)
        self.assertTrue(Path(f["stale_clone_set_aside"]["path"]).is_dir())
        self.assertTrue(github.publish(self.root, "paid-one", "hand", "export", yes=True,
                                       **self.github_private(new_private, "owner/new-private"))["published"])
        self.assertEqual(self.pine_files(new_private), ["paid-one/paid-one.pine"])
        self.assertEqual(self.pine_files(old_public), [])

    def test_replacement_after_a_hand_removal_invalidates_the_leftovers(self):
        """destination-add on a name whose plan and clone belong to a former
        destination (entry removed by hand): both are invalidated, nothing deleted."""
        old_public, new_private = self.bare("old public"), self.bare("new private")
        self.add("r", "public", old_public)
        old_plan = github.export_plan(self.root, "paid-one", "r")
        self.assertTrue(github.fetch(self.root, "r")["ok"])
        cfg_path = self.root / "pws.config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["github"]["destinations"] = []
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        r = self.add("r", "private", new_private)
        self.assertEqual([Path(p["staging"]).name for p in r["invalidated_plans"]], ["paid-one--r"])
        self.assertTrue((Path(old_plan["staging"]) / "PLAN.invalidated.json").is_file())
        self.assertTrue((Path(r["clone_set_aside"]["path"]) / ".git").is_dir())
        self.assertEqual(r["destination"]["visibility"], "private")
        github.export_plan(self.root, "paid-one", "r")
        self.assertEqual(github.fetch(self.root, "r")["action"], "clone")
        self.assertTrue(github.publish(self.root, "paid-one", "r", "export", yes=True,
                                       **self.github_private(new_private, "owner/new-private"))["published"])
        self.assertEqual((self.pine_files(new_private), self.pine_files(old_public)),
                         (["paid-one/paid-one.pine"], []))

    def test_source_visibility_changed_after_the_plan(self):
        """The case the audit left unverified: public source planned, then the
        manifest makes it closed — nothing reaches the public destination."""
        repo = self.bare("public")
        pdir = helpers.make_product_v2(self.root, slug="free-then-closed", profile="FREE")
        self.add("p", "public", repo)
        plan = github.export_plan(self.root, "free-then-closed", "p")
        self.assertIn("free-then-closed/free-then-closed.pine", [i["to"] for i in plan["included"]])
        self.assertTrue(github.fetch(self.root, "p")["ok"])
        m = json.loads((pdir / "SCRIPT.json").read_text(encoding="utf-8"))
        m["license"].update({"id": "PROPRIETARY", "grant": "free-use", "source_visibility": "closed"})
        m["publication"]["mode"] = "protected"
        (pdir / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        (pdir / "My Indicator.pine").write_text(helpers.PROPRIETARY_HEADER + helpers.MINIMAL_BODY,
                                                encoding="utf-8")
        for result in (github.export_diff(self.root, "free-then-closed", "p"),
                       github.publish(self.root, "free-then-closed", "p", "export", yes=True)):
            self.assertFalse(result["ok"])
            self.assertIn("source visibility changed since the plan", result["error"])
        self.assertEqual(self.pine_files(repo), [])

    def test_staged_file_altered_after_the_plan(self):
        repo = self.bare("public")
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        self.add("p", "public", repo)
        plan = github.export_plan(self.root, "free-one", "p")
        self.assertTrue(github.fetch(self.root, "p")["ok"])
        staged = Path(plan["staging"]) / "files" / "free-one" / "free-one.pine"
        staged.write_text("// altered\n" + staged.read_text(encoding="utf-8"), encoding="utf-8")
        r = github.publish(self.root, "free-one", "p", "export", yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("altered or missing since the plan", r["error"])
        self.assertEqual(self.pine_files(repo), [])

    def test_plan_of_an_earlier_version_is_refused(self):
        repo = self.bare("vault")
        self.add("s1", "private", repo)
        plan = github.export_plan(self.root, "paid-one", "s1")
        legacy = {k: v for k, v in plan.items() if k not in ("plan_format",)}
        core.atomic_write_json(Path(plan["staging"]) / "PLAN.json", legacy)
        self.assertTrue(github.fetch(self.root, "s1")["ok"])
        r = github.publish(self.root, "paid-one", "s1", "export", yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("earlier version", r["error"])

    def test_unpublished_local_work_is_refused_and_never_moved(self):
        repo = self.bare("public")
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        self.add("p", "public", repo)
        github.export_plan(self.root, "free-one", "p")
        clone = Path(github.fetch(self.root, "p")["path"])
        (clone / "LOCAL-NOTE.md").write_text("local work\n", encoding="utf-8")
        git("add", "LOCAL-NOTE.md", cwd=clone)
        git("commit", "-m", "local work not pushed", cwd=clone)
        for result in (github.export_diff(self.root, "free-one", "p"),
                       github.publish(self.root, "free-one", "p", "export", yes=True),
                       github.fetch(self.root, "p")):
            self.assertFalse(result["ok"])
            self.assertIn("unpublished local work", result["error"])
            self.assertIn(str(clone), result["error"])
        self.assertNotIn("LOCAL-NOTE.md", listing(repo))
        r = github.destination_remove(self.root, "p")
        self.assertIsNone(r["clone_set_aside"])
        self.assertEqual(r["clone_marked"]["path"], str(clone))
        self.assertTrue((clone.parent / "p.STALE.json").is_file())
        self.assertEqual(git("log", "-1", "--format=%s", cwd=clone).stdout.strip(), "local work not pushed")
        # re-added identically: still refused until the holder handles the work
        self.add("p", "public", repo)
        self.assertFalse(github.fetch(self.root, "p")["ok"])
        self.assertTrue(clone.is_dir())

    def test_failed_push_leaves_a_local_commit_that_blocks_the_next_publication(self):
        repo = self.bare("public")
        hook = repo / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        self.add("p", "public", repo)
        github.export_plan(self.root, "free-one", "p")
        self.assertTrue(github.fetch(self.root, "p")["ok"])
        # contract change of 2026-11-14: every send checks the identity of the destination (simulated here)
        self.gh.serve(repo, "owner/public")
        r = github.publish(self.root, "free-one", "p", "export", yes=True, **self.gh.kw)
        self.assertFalse(r["ok"])
        self.assertFalse(r["published"])
        self.assertIn("unpublished local work", r["error"])
        self.assertEqual(self.pine_files(repo), [])
        hook.unlink()
        r = github.publish(self.root, "free-one", "p", "export", yes=True, **self.gh.kw)
        self.assertFalse(r["ok"])
        self.assertIn("1 local commit(s)", r["error"])

    def test_symbolic_link_in_the_destination_repository_is_refused(self):
        repo = self.bare("public")
        seed = Path(self.tmp.name) / "seed public"
        os.symlink("../outside", str(seed / "free-one"))
        git("add", "free-one", cwd=seed)
        git("commit", "-m", "link", cwd=seed)
        git("push", "origin", "HEAD:main", cwd=seed)
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        self.add("p", "public", repo)
        github.export_plan(self.root, "free-one", "p")
        self.assertTrue(github.fetch(self.root, "p")["ok"])
        d = github.export_diff(self.root, "free-one", "p")
        self.assertTrue(d["changes"][0]["change"].startswith("REFUSED (symbolic link"))
        self.assertFalse(github.publish(self.root, "free-one", "p", "export", yes=True)["ok"])
        self.assertFalse((Path(self.tmp.name) / "outside").exists())

    def test_outputs_present_the_effective_destination(self):
        repo = self.bare("public")
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        self.add("p", "public", repo)
        plan = github.export_plan(self.root, "free-one", "p")
        self.assertTrue(github.fetch(self.root, "p")["ok"])
        d = github.export_diff(self.root, "free-one", "p")
        r = github.publish(self.root, "free-one", "p", "export", yes=False)
        for out in (plan, d, r):
            dest = out["destination"]
            self.assertEqual((dest["name"], dest["repo"], dest["visibility"], dest["branch"], dest["path_prefix"]),
                             ("p", "owner/public", "public", "main", ""))
            self.assertEqual(dest["clone_url"], str(repo))
        for out in (d, r):
            self.assertEqual(out["clone"]["origin"], str(repo))
            self.assertTrue(out["clone"]["matches_destination"])
        self.assertIn("refused without --yes", r["error"])


class TestGithubRealVisibility(unittest.TestCase):
    """I-06 (holder's decision of 2026-11-13): before a send carrying a closed
    source, GitHub is asked for the real repository and its visibility, and
    the remote git really pushes to must designate it. GitHub is simulated;
    git runs with an empty global configuration and cannot open a network
    transport (GIT_ALLOW_PROTOCOL=file)."""

    ENV = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
           "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_ALLOW_PROTOCOL")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        empty = Path(self.tmp.name) / "empty.gitconfig"
        empty.write_text("", encoding="utf-8")
        self.env_backup = {k: os.environ.get(k) for k in self.ENV}
        os.environ.update({"GIT_AUTHOR_NAME": "tests", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                           "GIT_COMMITTER_NAME": "tests", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                           "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_ALLOW_PROTOCOL": "file"})
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        helpers.make_product_v2(self.root, slug="paid-one", profile="COMMERCIAL")
        self.vault = make_bare_with_main(self.tmp.name, "vault")
        # another repository with the same history: a push there would succeed
        self.other = Path(self.tmp.name) / "public mirror.git"
        git("clone", "--bare", "--", str(self.vault), str(self.other))
        self.gh = FakeGitHub()
        self.gh.serve(self.vault, "owner/vault")
        self.gh.serve(self.other, "owner/public-mirror")
        r = github.destination_add(self.root, "s1", "owner/vault", "private", "", "main", url=str(self.vault))
        self.assertTrue(r["ok"], r)

    def tearDown(self):
        for k, v in self.env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()
        self.assertEqual(REAL_GH_CALLS, [])

    def pine(self, bare):
        return [x for x in listing(bare) if x.endswith(".pine")]

    def prepare(self, slug="paid-one", dest="s1"):
        plan = github.export_plan(self.root, slug, dest)
        self.assertTrue(plan["ok"], plan)
        f = github.fetch(self.root, dest)
        self.assertTrue(f["ok"], f)
        return plan, Path(f["path"])

    def publish(self, slug="paid-one", dest="s1", **kw):
        return github.publish(self.root, slug, dest, "export", yes=True, **(kw or self.gh.kw))

    def assert_nothing_sent(self, clone):
        """Neither repository received anything, nothing was written into the clone."""
        self.assertEqual((self.pine(self.vault), self.pine(self.other)), ([], []))
        self.assertEqual(git("status", "--porcelain", cwd=clone).stdout.strip(), "")
        self.assertEqual(git("rev-list", "--count", "refs/remotes/origin/main..HEAD", cwd=clone).stdout.strip(), "0")

    def test_private_repository_receives_the_closed_source_after_the_check(self):
        self.gh.repo("owner/vault", "PRIVATE")
        plan, clone = self.prepare()
        ann = plan["visibility_check"]           # export-plan works offline: it announces only
        self.assertEqual((ann["required"], ann["performed"], ann["observed"]), (True, False, None))
        self.assertEqual(ann["closed_content"], [{"path": "paid-one/paid-one.pine",
                                                  "reason": "the product's source (source_visibility=closed)"}])
        self.assertNotIn("visibility_check", (Path(plan["staging"]) / "PLAN.json").read_text(encoding="utf-8"))
        self.assertEqual(self.gh.calls, [])
        d = github.export_diff(self.root, "paid-one", "s1", **self.gh.kw)
        self.assertTrue(d["ok"], d)
        self.assertEqual(d["visibility_check"]["observed"]["visibility"], "PRIVATE")
        r = self.publish()
        self.assertTrue(r["published"], r)
        check = r["visibility_check"]
        self.assertTrue(check["ok"] and check["performed"])
        self.assertEqual((check["observed"]["repository"], check["observed"]["visibility"],
                          check["observed"]["is_private"], check["observed"]["url"]),
                         ("owner/vault", "PRIVATE", True, "https://github.com/owner/vault"))
        self.assertRegex(check["checked_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual((check["remote"]["repository"], check["remote"]["pushurl_configured"],
                          check["remote"]["rewritten"]), ("owner/vault", False, False))
        self.assertIn("no atomic guarantee", check["limit"])
        # observed by export-diff, then observed AGAIN by publish: never reused
        self.assertEqual(self.gh.calls, [GH_VIEW, GH_VIEW])
        self.assertEqual((self.pine(self.vault), self.pine(self.other)), (["paid-one/paid-one.pine"], []))

    def test_public_or_internal_repository_refused_nothing_written(self):
        for visibility in ("PUBLIC", "INTERNAL"):
            with self.subTest(visibility=visibility):
                self.gh.repo("owner/vault", visibility)
                _, clone = self.prepare()
                d = github.export_diff(self.root, "paid-one", "s1", **self.gh.kw)
                self.assertFalse(d["ok"])
                self.assertIn("publish would refuse", d["error"])
                self.assertEqual(d["visibility_check"]["observed"]["visibility"], visibility)
                self.assertEqual([c["change"] for c in d["changes"]], ["added"])
                r = self.publish()
                self.assertEqual((r["ok"], r["published"]), (False, False))
                self.assertIn("refused before any write or push", r["error"])
                self.assertIn("GitHub reports owner/vault as %s" % visibility, r["error"])
                self.assert_nothing_sent(clone)

    def test_visibility_that_cannot_be_established_is_refused(self):
        """Repository inaccessible, gh absent, not authenticated, timeout, other
        error, failing executor: refused; a token line of gh is never shown."""
        _, clone = self.prepare()
        cases = (
            ((1, "", "GraphQL: Could not resolve to a Repository with the name 'owner/vault'. (repository)"),
             "repository not found, or not visible with the current gh authentication"),
            ((127, "", "gh is not installed"), "gh (GitHub CLI) is not available"),
            ((4, "", "To get started with GitHub CLI, please run:  gh auth login\nAlternatively, populate the "
                     "GH_TOKEN environment variable with a GitHub API authentication token.\n"
                     "  - Token: gho_FAKE0000000000"), "gh is not authenticated for github.com"),
            ((124, "", "gh did not answer within 30 s"), "gh did not answer in time"),
            ((1, "", "error connecting to api.github.com"), "gh failed (exit code 1) — error connecting"),
        )
        for answer, expected in cases:
            with self.subTest(expected=expected):
                self.gh.answer("owner/vault", *answer)
                r = self.publish()
                self.assertFalse(r["ok"])
                self.assertIn("could not be established", r["error"])
                self.assertIn(expected, r["error"])
                self.assertNotIn("gho_FAKE", json.dumps(r))
                self.assertNotIn("GH_TOKEN", json.dumps(r))
                self.assertTrue(r["visibility_check"]["performed"])
                self.assertIsNone(r["visibility_check"]["observed"]["visibility"])
                self.assert_nothing_sent(clone)

        def failing(args):
            raise OSError("no executor")
        r = self.publish(gh_runner=failing, repo_of_url=self.gh.repo_of_url)
        self.assertIn("gh (GitHub CLI) is not available", r["error"])
        self.assert_nothing_sent(clone)

    def test_invalid_or_incoherent_answers_are_refused(self):
        _, clone = self.prepare()
        valid = {"nameWithOwner": "owner/vault", "visibility": "PRIVATE", "isPrivate": True,
                 "url": "https://github.com/owner/vault"}
        cases = (
            ("<html>sign in</html>", "invalid answer: not JSON"),
            (json.dumps([valid]), "invalid answer: not a JSON object"),
            (json.dumps(dict(valid, nameWithOwner=None)), "nameWithOwner missing"),
            (json.dumps(dict(valid, nameWithOwner="vault")), "nameWithOwner missing"),
            (json.dumps({k: v for k, v in valid.items() if k != "visibility"}), "visibility missing or unknown"),
            (json.dumps(dict(valid, visibility="SECRET")), "visibility missing or unknown"),
            (json.dumps(dict(valid, isPrivate="true")), "isPrivate missing or not a boolean"),
            (json.dumps(dict(valid, isPrivate=False)), "incoherent answer: visibility PRIVATE with isPrivate=false"),
            (json.dumps(dict(valid, visibility="PUBLIC")), "incoherent answer: visibility PUBLIC with isPrivate=true"),
            (json.dumps(dict(valid, url="https://ghe.example.com/owner/vault")), "url does not designate"),
            (json.dumps(dict(valid, url="https://github.com/owner/other")), "url does not designate"),
        )
        for out, expected in cases:
            with self.subTest(expected=expected, out=out[:40]):
                self.gh.answer("owner/vault", 0, out)
                r = self.publish()
                self.assertFalse(r["ok"])
                self.assertIn("could not be established", r["error"])
                self.assertIn(expected, r["error"])
                self.assert_nothing_sent(clone)
        self.assertEqual(len(self.gh.calls), len(cases))

    def test_renamed_or_transferred_repository_is_refused(self):
        _, clone = self.prepare()
        self.gh.repo("owner/vault", "PRIVATE", name_with_owner="new-owner/vault-2026")
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertIn("GitHub resolves owner/vault to new-owner/vault-2026 (renamed or transferred", r["error"])
        self.assertEqual(r["visibility_check"]["observed"]["repository"], "new-owner/vault-2026")
        self.assert_nothing_sent(clone)
        # the same repository written with another case is the same repository
        self.gh.repo("owner/vault", "PRIVATE", name_with_owner="Owner/Vault")
        self.assertTrue(self.publish()["published"])

    def test_visibility_changed_between_the_plan_and_the_push(self):
        self.gh.repo("owner/vault", "PRIVATE")
        _, clone = self.prepare()
        d = github.export_diff(self.root, "paid-one", "s1", **self.gh.kw)
        self.assertEqual((d["ok"], d["visibility_check"]["observed"]["visibility"]), (True, "PRIVATE"))
        self.gh.repo("owner/vault", "PUBLIC")            # made public after the reviewed comparison
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertEqual(r["visibility_check"]["observed"]["visibility"], "PUBLIC")
        self.assertIn("GitHub reports owner/vault as PUBLIC", r["error"])
        self.assertEqual(len(self.gh.calls), 2)
        self.assert_nothing_sent(clone)
        self.gh.repo("owner/vault", "PRIVATE")           # private again: the same plan, a new check
        r = self.publish()
        self.assertTrue(r["published"], r)
        self.assertEqual(len(self.gh.calls), 3)

    def test_remote_inconsistencies_are_refused_before_any_query(self):
        """origin of another repository, pushurl elsewhere, several push or fetch
        URLs, pushInsteadOf rewriting: refused, GitHub not even queried."""
        self.gh.repo("owner/vault", "PRIVATE")
        self.gh.repo("owner/public-mirror", "PRIVATE")   # even a private other repository is refused
        _, clone = self.prepare()
        cfg = clone / ".git" / "config"
        original = cfg.read_text(encoding="utf-8")
        cases = (
            ("pushurl", lambda: git("config", "remote.origin.pushurl", str(self.other), cwd=clone),
             "git would push to owner/public-mirror while the clone fetches from owner/vault "
             "(remote.origin.pushurl is set)"),
            ("two push URLs", lambda: (git("config", "--add", "remote.origin.pushurl", str(self.vault), cwd=clone),
                                       git("config", "--add", "remote.origin.pushurl", str(self.other), cwd=clone)),
             "origin has 2 push URLs"),
            ("two fetch URLs", lambda: git("config", "--add", "remote.origin.url", str(self.other), cwd=clone),
             "origin has 2 fetch URLs"),
            ("rewriting", lambda: git("config", "url.%s.pushInsteadOf" % self.other, str(self.vault), cwd=clone),
             "git would push to owner/public-mirror while the clone fetches from owner/vault "
             "(an insteadOf / pushInsteadOf rewriting applies)"),
            ("origin", lambda: git("remote", "set-url", "origin", str(self.other), cwd=clone),
             "stale local clone"),
        )
        for name, change, expected in cases:
            with self.subTest(case=name):
                change()
                for r in (github.export_diff(self.root, "paid-one", "s1", **self.gh.kw), self.publish()):
                    self.assertFalse(r["ok"])
                    self.assertIn(expected, r["error"])
                    if name != "origin":                 # (origin: refused earlier, as a stale clone)
                        self.assertIn("the real visibility was not queried", r["error"])
                self.assertEqual(self.gh.calls, [])
                self.assert_nothing_sent(clone)
                cfg.write_text(original, encoding="utf-8")
        self.assertTrue(self.publish()["published"])         # the clone restored: the check passes

    def test_closed_source_to_a_repository_outside_github_is_refused(self):
        """Default behaviour (nothing injected): a destination declared private
        whose URL is not a github.com repository cannot have its real
        visibility checked — the closed source is not sent (the real gh,
        blocked here, is not even run)."""
        _, clone = self.prepare()
        r = github.publish(self.root, "paid-one", "s1", "export", yes=True)
        self.assertEqual((r["ok"], r.get("published")), (False, False))
        self.assertIn("is not an https or ssh URL of the github.com repository owner/vault", r["error"])
        self.assertIn("refused before any write or push", r["error"])
        self.assert_nothing_sent(clone)

    def test_destination_url_of_another_repository_is_refused(self):
        self.gh.repo("owner/vault", "PRIVATE")
        r = github.destination_add(self.root, "s2", "owner/vault", "private", "", "main", url=str(self.other))
        self.assertTrue(r["ok"], r)
        _, clone = self.prepare(dest="s2")
        r = self.publish(dest="s2")
        self.assertFalse(r["ok"])
        self.assertIn("the destination's URL %s is not an https or ssh URL of the github.com repository "
                      "owner/vault" % self.other, r["error"])
        self.assertEqual(self.gh.calls, [])
        self.assert_nothing_sent(clone)

    def test_github_url_origin_queries_gh_repo_view_with_the_real_reading(self):
        """origin is the github.com URL of the destination (clone prepared from a
        local bare): the real URL reading accepts it and gh is asked with
        `gh repo view https://github.com/owner/vault --json …` (never gh api)."""
        github.destination_add(self.root, "gh", "owner/vault", "private", "", "main")
        github.export_plan(self.root, "paid-one", "gh")
        clone = self.root / github.EXPORT_REL / github.CLONES_DIRNAME / "gh"
        clone.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "--branch", "main", "--single-branch", "--", str(self.vault), str(clone))
        git("remote", "set-url", "origin", "https://github.com/owner/vault.git", cwd=clone)
        self.gh.repo("owner/vault", "PUBLIC")
        r = github.publish(self.root, "paid-one", "gh", "export", yes=True, gh_runner=self.gh.gh)
        self.assertFalse(r["ok"])
        self.assertIn("GitHub reports owner/vault as PUBLIC", r["error"])
        self.assertEqual(r["visibility_check"]["remote"]["push_urls"], ["https://github.com/owner/vault.git"])
        self.assertEqual(self.gh.calls, [GH_VIEW])
        self.assertNotIn("api", self.gh.calls[0])
        self.assert_nothing_sent(clone)
        # a rewriting toward the SAME repository (https → ssh) is read as such by the remote check
        git("config", "url.git@github.com:.insteadOf", "https://github.com/", cwd=clone)
        facts, problem, push = github._origin_remote(clone, github._effective_destination(
            github._destination(self.root, "gh")), github._github_repo_of_url)
        self.assertIsNone(problem)
        self.assertEqual((facts["repository"], facts["rewritten"], push),
                         ("owner/vault", True, ["git@github.com:owner/vault.git"]))

    def test_manifest_read_again_when_sending(self):
        """A FREE product's tutorial reproduces another product's code, public
        when planned; that product's manifest makes it closed before the send:
        the send now carries closed content and is checked."""
        body = ('indicator("Vault Indicator")\nalphaLine = ta.ema(close, 34)\nbetaLine = ta.wma(close, 55)\n'
                'plot(alphaLine - betaLine)\n')
        other = helpers.make_product_v2(self.root, slug="other-one", profile="FREE", body=body)
        free = helpers.make_product_v2(self.root, slug="free-doc", profile="FREE")
        (free / "docs").mkdir()
        (free / "docs" / "TUTORIAL.md").write_text("# Tutorial\n\n" + body.replace("indicator", "// indicator"),
                                                   encoding="utf-8")
        plan, clone = self.prepare(slug="free-doc")
        self.assertNotIn("visibility_check", plan)        # nothing closed when planned
        m = json.loads((other / "SCRIPT.json").read_text(encoding="utf-8"))
        m["license"].update({"id": "PROPRIETARY", "grant": "free-use", "source_visibility": "closed"})
        m["publication"]["mode"] = "protected"
        (other / "SCRIPT.json").write_text(json.dumps(m), encoding="utf-8")
        (other / "My Indicator.pine").write_text(helpers.PROPRIETARY_HEADER + body, encoding="utf-8")
        self.gh.repo("owner/vault", "PUBLIC")
        r = self.publish(slug="free-doc")
        self.assertFalse(r["ok"], r)
        self.assertEqual([c["path"] for c in r["visibility_check"]["closed_content"]], ["free-doc/TUTORIAL.md"])
        self.assertIn("closed source of product 'other-one'", r["visibility_check"]["closed_content"][0]["reason"])
        self.assert_nothing_sent(clone)
        self.gh.repo("owner/vault", "PRIVATE")
        self.assertTrue(self.publish(slug="free-doc")["published"])

    def test_public_content_needs_no_github_check(self):
        """No closed content (a public source to a public destination, or the
        documents of a closed product to a public destination): no query of
        GitHub — the identity of the destination is still checked (contract
        change of 2026-11-14: every send; the local bare repository stands
        for owner/public-scripts)."""
        pub = make_bare_with_main(self.tmp.name, "public scripts")
        self.gh.serve(pub, "owner/public-scripts")
        self.assertTrue(github.destination_add(self.root, "pub", "owner/public-scripts", "public", "", "main",
                                               url=str(pub))["ok"])
        helpers.make_product_v2(self.root, slug="free-one", profile="FREE")
        paid = self.root / "scripts" / "paid-one"
        (paid / "release").mkdir()
        (paid / "release" / "CHANGELOG.md").write_text("# Changelog\n- 1.0.0\n", encoding="utf-8")
        for slug, sent in (("free-one", "free-one/free-one.pine"), ("paid-one", "paid-one/CHANGELOG.md")):
            with self.subTest(slug=slug):
                plan, _ = self.prepare(slug=slug, dest="pub")
                self.assertNotIn("visibility_check", plan)
                self.assertEqual((plan["destination_check"]["required"], plan["destination_check"]["performed"]),
                                 (True, False))
                d = github.export_diff(self.root, slug, "pub", **self.gh.kw)
                self.assertTrue(d["ok"], d)
                self.assertNotIn("visibility_check", d)
                self.assertEqual((d["destination_check"]["ok"], d["destination_check"]["remote"]["repository"]),
                                 (True, "owner/public-scripts"))
                r = github.publish(self.root, slug, "pub", "export", yes=True, **self.gh.kw)
                self.assertTrue(r["published"], r)
                self.assertNotIn("visibility_check", r)
                self.assertTrue(r["destination_check"]["ok"])
                self.assertIn(sent, listing(pub))
        self.assertEqual(self.gh.calls, [])
        self.assertEqual([x for x in listing(pub) if x.endswith(".pine")], ["free-one/free-one.pine"])

    def test_credentials_of_a_url_are_never_displayed(self):
        self.gh.repo("owner/vault", "PRIVATE")
        _, clone = self.prepare()
        git("config", "remote.origin.pushurl",
            "https://someone:FAKE-SECRET-0000@github.com/owner/public-mirror.git", cwd=clone)
        for r in (github.export_diff(self.root, "paid-one", "s1", **self.gh.kw), self.publish()):
            self.assertFalse(r["ok"])
            dumped = json.dumps(r)
            self.assertNotIn("FAKE-SECRET-0000", dumped)
            self.assertIn("https://***@github.com/owner/public-mirror.git", dumped)
        self.assertEqual(self.gh.calls, [])
        self.assert_nothing_sent(clone)
        # review RS-02 (2026-11-13, config.destination_problems — contract change): a URL embedding
        # credentials is refused at writing; the refusal does not show them
        r = github.destination_add(self.root, "cred", "owner/vault", "private", "", "main",
                                   url="https://someone:FAKE-SECRET-0000@github.com/owner/vault.git")
        self.assertFalse(r["ok"])
        self.assertIn("credentials", r["error"])
        self.assertNotIn("FAKE-SECRET-0000", json.dumps(r))
        # written by hand into pws.config.json: still never displayed, and refused by every operation
        cfg_path = self.root / "pws.config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["github"]["destinations"].append({"name": "cred", "repo": "owner/vault", "visibility": "private",
                                              "path_prefix": "", "branch": "main",
                                              "url": "https://someone:FAKE-SECRET-0000@github.com/owner/vault.git"})
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        plan = github.export_plan(self.root, "paid-one", "cred")
        self.assertFalse(plan["ok"])
        for shown in (plan, github.destinations(self.root)):
            self.assertNotIn("FAKE-SECRET-0000", json.dumps(shown))
        self.assertIn("https://***@github.com/owner/vault.git", json.dumps(github.destinations(self.root)))

    def test_crafted_push_url_reaching_another_host_is_refused(self):
        """Review RS-01 (2026-11-13): a push URL whose user part holds « # » or
        « ? » is read by git as ANOTHER host (attacker.invalid), whatever
        follows the « @ ». It is refused before any query to GitHub and before
        anything is written, whether it comes from remote.origin.pushurl or
        from a global pushInsteadOf rewriting; the refusal shows the real
        host, never `***@github.com`. (GIT_ALLOW_PROTOCOL=file: git could not
        open an https transport anyway.)"""
        self.gh.repo("owner/vault", "PRIVATE")
        _, clone = self.prepare()
        cfg = clone / ".git" / "config"
        original = cfg.read_text(encoding="utf-8")
        for crafted, host in (("https://attacker.invalid#@github.com/owner/vault.git", "attacker.invalid"),
                              ("https://attacker.invalid?@github.com/owner/vault.git", "attacker.invalid"),
                              ("https://[::1]#@github.com/owner/vault.git", "[::1]")):
            with self.subTest(crafted=crafted):
                git("config", "remote.origin.pushurl", crafted, cwd=clone)
                for r in (github.export_diff(self.root, "paid-one", "s1", **self.gh.kw), self.publish()):
                    self.assertFalse(r["ok"])
                    self.assertIn("the push URL", r["error"])
                    self.assertIn("host for git: %s" % host, r["error"])
                    self.assertIn("the real visibility was not queried", r["error"])
                    self.assertNotIn("***@github.com", json.dumps(r))
                    self.assertIsNone(r["visibility_check"]["remote"]["repository"])
                self.assertEqual(self.gh.calls, [])
                self.assert_nothing_sent(clone)
                cfg.write_text(original, encoding="utf-8")
        # the same through a rewriting of the account's global configuration (case S4 of N-01)
        github.destination_add(self.root, "gh", "owner/vault", "private", "", "main")
        github.export_plan(self.root, "paid-one", "gh")
        gclone = self.root / github.EXPORT_REL / github.CLONES_DIRNAME / "gh"
        git("clone", "--branch", "main", "--single-branch", "--", str(self.vault), str(gclone))
        git("remote", "set-url", "origin", "https://github.com/owner/vault.git", cwd=gclone)
        with open(os.environ["GIT_CONFIG_GLOBAL"], "a", encoding="utf-8") as fh:
            fh.write('[url "https://attacker.invalid#@github.com/"]\n\tpushInsteadOf = https://github.com/\n')
        r = github.publish(self.root, "paid-one", "gh", "export", yes=True, gh_runner=self.gh.gh)
        self.assertEqual((r["ok"], r.get("published")), (False, False))
        self.assertIn("host for git: attacker.invalid", r["error"])
        self.assertIn("an insteadOf / pushInsteadOf rewriting applies", r["error"])
        self.assertEqual(r["visibility_check"]["remote"]["push_urls"],
                         ["https://attacker.invalid#@github.com/owner/vault.git"])
        self.assertEqual(self.gh.calls, [])
        self.assert_nothing_sent(gclone)

    def test_crafted_destination_url_shows_its_real_host_and_is_refused(self):
        """RS-01, case D of the review: the destination's own URL holds « ?@ »:
        listed with its real host, and a closed source is never sent to it."""
        crafted = "https://attacker.invalid?@github.com/owner/vault.git"
        self.assertTrue(github.destination_add(self.root, "d", "owner/vault", "private", "", "main",
                                               url=crafted)["ok"])
        shown = json.dumps(github.destinations(self.root))
        self.assertIn("https://attacker.invalid?", shown)
        self.assertNotIn("***@github.com", shown)
        github.export_plan(self.root, "paid-one", "d")
        clone = self.root / github.EXPORT_REL / github.CLONES_DIRNAME / "d"
        git("clone", "--branch", "main", "--single-branch", "--", str(self.vault), str(clone))
        git("remote", "set-url", "origin", crafted, cwd=clone)      # as a fetch would have left it
        self.gh.repo("owner/vault", "PRIVATE")
        r = github.publish(self.root, "paid-one", "d", "export", yes=True, gh_runner=self.gh.gh)
        self.assertEqual((r["ok"], r.get("published")), (False, False))
        self.assertIn("the destination's URL https://attacker.invalid?*** (host for git: attacker.invalid) is not "
                      "an https or ssh URL of the github.com repository owner/vault", r["error"])
        self.assertEqual(self.gh.calls, [])
        self.assert_nothing_sent(clone)

    def test_public_source_copying_a_closed_source_is_closed_content(self):
        """Review RS-04 (2026-11-13): a FREE product whose declared source is a
        copy of another product's closed source is checked like a closed
        source towards a private destination, and never reaches a public one."""
        free = helpers.make_product_v2(self.root, slug="free-copy", profile="FREE")
        (free / "My Indicator.pine").write_bytes((self.root / "scripts" / "paid-one" / "My Indicator.pine").read_bytes())
        self.gh.repo("owner/vault", "PUBLIC")
        plan, clone = self.prepare(slug="free-copy")
        self.assertIn("visibility_check", plan, "the copy of a closed source must announce the I-06 check")
        self.assertEqual([c["path"] for c in plan["visibility_check"]["closed_content"]],
                         ["free-copy/free-copy.pine"])
        r = self.publish(slug="free-copy")
        self.assertFalse(r["ok"])
        self.assertIn("GitHub reports owner/vault as PUBLIC", r["error"])
        self.assertIn("the product's public source reproduces the closed source of product 'paid-one'",
                      r["visibility_check"]["closed_content"][0]["reason"])
        self.assert_nothing_sent(clone)
        self.gh.repo("owner/vault", "PRIVATE")
        r = self.publish(slug="free-copy")
        self.assertTrue(r["published"], r)
        self.assertEqual(len(self.gh.calls), 2)
        self.assertEqual(self.pine(self.vault), ["free-copy/free-copy.pine"])
        # towards a public destination: never sent (the plan excludes it, nothing to publish)
        pub = make_bare_with_main(self.tmp.name, "public scripts")
        self.assertTrue(github.destination_add(self.root, "pub", "owner/public-scripts", "public", "", "main",
                                               url=str(pub))["ok"])
        plan, _ = self.prepare(slug="free-copy", dest="pub")
        self.assertIn("reproduces the closed source of product 'paid-one'", reasons(plan)["My Indicator.pine"])
        r = github.publish(self.root, "free-copy", "pub", "export", yes=True, **self.gh.kw)
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["published"])
        self.assertEqual([x for x in listing(pub) if x.endswith(".pine")], [])
        self.assertEqual(len(self.gh.calls), 2)


# ---- holder's request of 2026-11-14 -------------------------------------------------------------------------------
# Original legal documents of an imported script; identity of the destination for every send. Fictitious products,
# authors and texts; local bare repositories stand for GitHub repositories; GitHub simulated; no network.

APACHE_HEADER = (
    "// Copyright 2025 Fictitious Author\n"
    "//\n"
    "// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
    "// you may not use this file except in compliance with the License.\n"
    "// You may obtain a copy of the License at\n"
    "//\n"
    "//     http://www.apache.org/licenses/LICENSE-2.0\n"
    "//\n"
    "// Unless required by applicable law or agreed to in writing, software\n"
    "// distributed under the License is distributed on an \"AS IS\" BASIS,\n"
    "// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
    "// See the License for the specific language governing permissions and\n"
    "// limitations under the License.\n"
    "//@version=6\n")
GPL3_HEADER = ("// Copyright (C) 2024 Fictitious Author\n"
               "//\n"
               "// This program is free software: you can redistribute it and/or modify it under the terms of the\n"
               "// GNU General Public License as published by the Free Software Foundation, version 3 of the License.\n"
               "//@version=6\n")
MIT_HEADER = "// Copyright (c) 2023 Fictitious Author\n// SPDX-License-Identifier: MIT\n//@version=6\n"
APACHE_LICENSE = (b"                                 Apache License\n                           Version 2.0, January "
                  b"2004\n                        http://www.apache.org/licenses/\n\n   TERMS AND CONDITIONS FOR USE, "
                  b"REPRODUCTION, AND DISTRIBUTION\n   (fictitious excerpt for the tests)\n")
APACHE_NOTICE = (b"Fictitious Indicator\nCopyright 2025 Fictitious Author\n\n"
                 b"This product includes software developed by Fictitious Labs.\n")
GPL_COPYING = (b"                    GNU GENERAL PUBLIC LICENSE\n                       Version 3, 29 June 2007\n\n"
               b"   (fictitious excerpt for the tests)\n")
MIT_LICENSE = (b"MIT License\n\nCopyright (c) 2023 Fictitious Author\n\nPermission is hereby granted, free of charge, "
               b"to any person obtaining a copy (fictitious excerpt for the tests).\n")
FRENCH_NOTICE_LATIN1 = ("Avis de droit d'auteur - Indicateur fictif\n© 2024 Auteur Fictif. Licence Apache, version 2.0 : "
                        "voir le fichier LICENSE.\nTexte d'origine conservé tel quel, sans traduction.\n").encode("latin-1")
GERMAN_LICENSE_BOM_CRLF = ("﻿Lizenzhinweis für den fiktiven Indikator\r\nDieses Werk steht unter der Apache-Lizenz, "
                           "Version 2.0.\r\nÜbersetzungen werden nicht bereitgestellt.\r\n").encode("utf-8")


class _IsolatedGit:
    """git with an empty global configuration and no network transport
    (GIT_ALLOW_PROTOCOL=file); the real gh is blocked for the whole module."""
    ENV = TestGithubRealVisibility.ENV

    def isolate_git(self, tmp):
        self.global_config = Path(tmp) / "empty.gitconfig"
        self.global_config.write_text("", encoding="utf-8")
        self.env_backup = {k: os.environ.get(k) for k in self.ENV}
        os.environ.update({"GIT_AUTHOR_NAME": "tests", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                           "GIT_COMMITTER_NAME": "tests", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                           "GIT_CONFIG_GLOBAL": str(self.global_config), "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_ALLOW_PROTOCOL": "file"})

    def restore_git(self):
        for k, v in self.env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def sent_bytes(bare, path):
    """The bytes the repository really holds on main (what was sent)."""
    return subprocess.run(["git", "show", "main:%s" % path], cwd=str(bare), capture_output=True).stdout


class TestGithubImportedLegalDocuments(_IsolatedGit, unittest.TestCase):
    """An imported script travels with its original legal documents (LICENSE,
    COPYING, NOTICE…): declared by the holder, exported verbatim (name,
    bytes, encoding, language), never because of their name alone, never
    left out silently; confinement, links, special files, content control,
    closed code and collisions keep their protections."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.isolate_git(self.tmp.name)
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        self.gh = FakeGitHub()
        self.pub = make_bare_with_main(self.tmp.name, "public scripts")
        self.gh.serve(self.pub, "owner/public-scripts")
        self.assertTrue(github.destination_add(self.root, "pub", "owner/public-scripts", "public", "", "main",
                                               url=str(self.pub))["ok"])

    def tearDown(self):
        self.restore_git()
        self.tmp.cleanup()
        self.assertEqual(REAL_GH_CALLS, [])

    def imported(self, slug, files, lid="Apache-2.0", header=APACHE_HEADER, profile="FREE"):
        """An imported script whose existing licence `lid` the holder confirmed, with its files."""
        pdir = helpers.make_product_v3(self.root, slug=slug, profile=profile, header=header,
                                       license_overrides={"id": None, "grant": "license", "origin": "imported",
                                                          "status": "to-analyse"})
        for rel, data in files.items():
            (pdir / rel).parent.mkdir(parents=True, exist_ok=True)
            (pdir / rel).write_bytes(data)
        r = licensing.confirm_publication(self.root, slug, license_id=lid)
        self.assertTrue(r["ok"], r)
        return pdir

    def declare(self, slug, *documents):
        r = licensing.confirm_publication(self.root, slug, license_documents=list(documents))
        self.assertTrue(r["ok"], r)

    def staged(self, plan):
        """The files REALLY prepared for the send (staging folder), not the announced list."""
        files = Path(plan["staging"]) / "files"
        return {p.relative_to(files).as_posix(): p.read_bytes() for p in sorted(files.rglob("*")) if p.is_file()}

    def test_reported_case_waits_for_the_declaration_and_never_leaves_a_document_out(self):
        """The case reported on 2026-11-14 (before the correction: plan ok, COPYING
        and NOTICE excluded as « not in the allowed list », no warning)."""
        files = {"LICENSE": APACHE_LICENSE, "COPYING": b"Fictitious Indicator: copying conditions in LICENSE.\n",
                 "NOTICE": APACHE_NOTICE}
        self.imported("apache-one", files)
        plan = github.export_plan(self.root, "apache-one", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("are not declared", plan["error"])
        self.assertIn("never an incomplete set", plan["error"])
        self.assertIsNone(plan["staging"])
        self.assertFalse((github._staging_dir(self.root, "apache-one", "pub") / "PLAN.json").exists())
        self.assertEqual([c["path"] for c in plan["legal_documents"]["candidates"]], ["COPYING", "LICENSE", "NOTICE"])
        silent = [e["path"] for e in plan["excluded"] if e["reason"] == "not in the allowed list"]
        self.assertEqual([p for p in silent if p in files], [])
        for name in files:                                # shown in the preview with the reason the export waits
            self.assertIn("not declared in license.documents", reasons(plan)[name])
        # a partial declaration still waits: never an incomplete set
        self.declare("apache-one", "LICENSE")
        plan = github.export_plan(self.root, "apache-one", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("found in the product but not declared: COPYING (file), NOTICE (file)", plan["error"])
        self.assertEqual(plan["legal_documents"]["undeclared"], ["COPYING", "NOTICE"])
        self.declare("apache-one", "LICENSE", "COPYING", "NOTICE")
        plan = github.export_plan(self.root, "apache-one", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(sorted((i["from"], i["role"]) for i in plan["included"]),
                         [("COPYING", "legal"), ("LICENSE", "legal"), ("My Indicator.pine", "source"),
                          ("NOTICE", "legal")])
        staged = self.staged(plan)
        self.assertEqual(set(staged), {"apache-one/COPYING", "apache-one/LICENSE", "apache-one/NOTICE",
                                       "apache-one/apache-one.pine"})
        for name, data in files.items():
            self.assertEqual(staged["apache-one/%s" % name], data)

    def test_apache_licence_and_notice_sent_with_the_source(self):
        files = {"LICENSE": APACHE_LICENSE, "NOTICE": APACHE_NOTICE}
        self.imported("apache-two", files)
        self.declare("apache-two", "LICENSE", "NOTICE")
        plan = github.export_plan(self.root, "apache-two", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertTrue(all("exported verbatim" in i["reason"] for i in plan["included"] if i["role"] == "legal"))
        self.assertIn("does not establish by itself", plan["legal_documents"]["note"])
        self.assertTrue(github.fetch(self.root, "pub")["ok"])
        r = github.publish(self.root, "apache-two", "pub", "export apache-two", yes=True, **self.gh.kw)
        self.assertTrue(r["published"], r)
        self.assertEqual(sorted(listing(self.pub)), ["README.md", "apache-two/LICENSE", "apache-two/NOTICE",
                                                     "apache-two/apache-two.pine"])
        for name, data in files.items():
            self.assertEqual(sent_bytes(self.pub, "apache-two/%s" % name), data)
        self.assertEqual(self.gh.calls, [])

    def test_licence_text_in_copying(self):
        self.imported("gpl-one", {"COPYING": GPL_COPYING}, lid="GPL-3.0-only", header=GPL3_HEADER)
        plan = github.export_plan(self.root, "gpl-one", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertEqual(plan["legal_documents"]["candidates"],
                         [{"path": "COPYING", "kind": "file", "declarable": True, "reason": None}])
        self.declare("gpl-one", "COPYING")
        plan = github.export_plan(self.root, "gpl-one", "pub")
        self.assertTrue(plan["ok"], plan)
        staged = self.staged(plan)
        self.assertEqual(staged["gpl-one/COPYING"], GPL_COPYING)
        self.assertEqual(sorted(staged), ["gpl-one/COPYING", "gpl-one/gpl-one.pine"])   # nothing renamed nor added

    def test_documents_in_another_language_and_encoding_are_kept_as_they_are(self):
        files = {"NOTICE.fr.txt": FRENCH_NOTICE_LATIN1, "release/LICENSE.de.txt": GERMAN_LICENSE_BOM_CRLF,
                 "LICENSES/Apache-2.0.txt": APACHE_LICENSE}
        with self.assertRaises(UnicodeDecodeError):
            FRENCH_NOTICE_LATIN1.decode("utf-8")                       # really a single-byte encoding
        self.imported("multi", files)
        self.declare("multi", "NOTICE.fr.txt", "release/LICENSE.de.txt", "LICENSES/Apache-2.0.txt")
        plan = github.export_plan(self.root, "multi", "pub")
        self.assertTrue(plan["ok"], plan)
        staged = self.staged(plan)
        self.assertEqual(staged["multi/NOTICE.fr.txt"], FRENCH_NOTICE_LATIN1)          # encoding and language kept
        self.assertEqual(staged["multi/LICENSE.de.txt"], GERMAN_LICENSE_BOM_CRLF)      # BOM and CRLF kept
        self.assertEqual(staged["multi/LICENSES/Apache-2.0.txt"], APACHE_LICENSE)      # REUSE layout kept
        encodings = {d["path"]: d["encoding"] for d in plan["legal_documents"]["documents"]}
        self.assertTrue(encodings["NOTICE.fr.txt"].startswith("single-byte"))
        self.assertEqual(encodings["release/LICENSE.de.txt"], "UTF-8 with BOM")

    def test_dangerous_or_out_of_scope_legal_documents_are_refused(self):
        pdir = self.imported("risky", {"LICENSE": APACHE_LICENSE, "docs/LICENSE": APACHE_LICENSE,
                                       "licenses/MIT.txt": MIT_LICENSE,
                                       # closed Pine code written in EBCDIC: no NUL byte, invisible to a Latin-1 reading
                                       "LICENSE-EBCDIC.txt": helpers.MINIMAL_BODY.encode("cp500")})
        os.symlink(str(self.root / "pws.config.json"), str(pdir / "NOTICE"))
        os.link(str(self.root / "pws.config.json"), str(pdir / "COPYRIGHT.txt"))      # hard link to the configuration
        os.mkfifo(str(pdir / "COPYING"))
        (pdir / "COPYRIGHT").write_bytes(b"\x00\x01 binary")
        (pdir / "LICENSE.txt").write_bytes(b"")
        before = (pdir / "SCRIPT.json").read_bytes()
        cases = (("docs/LICENSE", "must lie at the product root"), ("../LICENSE", "plain relative POSIX path"),
                 ("/etc/hosts", "relative path inside the product root"), ("SCRIPT.json", "is not a legal document"),
                 ("My Indicator.pine", "is not a legal document"), (".env", "a hidden file is not a legal document"),
                 ("PRODUCT.md", "internal file of Pine Workspace"), ("README.md", "is not a legal-document name"),
                 ("NOTICE", "symbolic link"), ("COPYRIGHT.txt", "a hard link"),
                 ("COPYING", "not a regular file"), ("COPYRIGHT", "NUL bytes"), ("LICENSE.txt", "empty file"),
                 ("LICENSE-EBCDIC.txt", "neither UTF-8 nor an ASCII-compatible single-byte text"),
                 ("LICENSE-" + "x" * 300, "name too long"), ("LICENSE‮txt.exe", "invisible or reordering"),
                 ("LICENSE.md", "absent"), ("license", "declare its exact name"),
                 ("LICENSES/MIT.txt", "while the folder is named 'licenses': declare its exact name"))
        for rel, words in cases:
            with self.subTest(rel=rel):
                r = licensing.confirm_publication(self.root, "risky", license_documents=["LICENSE", rel])
                self.assertFalse(r["ok"], r)
                self.assertIn(words, r["error"])
                self.assertIn("nothing written", r["error"])
        self.assertEqual((pdir / "SCRIPT.json").read_bytes(), before)
        # declared by hand: the export judges the files it finds, follows no link, stages nothing
        set_license(pdir, documents=["LICENSE", "NOTICE", "COPYING", "COPYRIGHT", "LICENSE.txt", "COPYRIGHT.txt",
                                     "LICENSE-EBCDIC.txt"])
        plan = github.export_plan(self.root, "risky", "pub")
        self.assertFalse(plan["ok"], plan)
        for rel, words in (("NOTICE", "symbolic link"), ("COPYING", "not a regular file"),
                           ("COPYRIGHT", "NUL bytes"), ("LICENSE.txt", "empty file"), ("COPYRIGHT.txt", "a hard link"),
                           ("LICENSE-EBCDIC.txt", "neither UTF-8 nor an ASCII-compatible")):
            self.assertIn(words, reasons(plan)[rel])
        self.assertNotIn('"github"', json.dumps(plan))               # the configuration's content is never read
        self.assertIsNone(plan["staging"])
        self.assertFalse((github._staging_dir(self.root, "risky", "pub") / "files").exists())
        # a declaration outside the accepted places makes the manifest BROKEN: never exported
        set_license(pdir, documents=["docs/LICENSE"])
        plan = github.export_plan(self.root, "risky", "pub")
        self.assertFalse(plan["ok"])
        self.assertIn("only a REGISTERED product is exported", plan["error"])

    def test_pws_template_text_and_closed_code_are_refused(self):
        self.imported("drafty", {"LICENSE": APACHE_LICENSE,
                                 "NOTICE": b"Notice\n" + github.DRAFT_MARKER.encode("utf-8") + b"\n",
                                 "COPYRIGHT": b"Copyright {{COPYRIGHT_HOLDER}}\n"})
        self.declare("drafty", "LICENSE", "NOTICE", "COPYRIGHT")
        plan = github.export_plan(self.root, "drafty", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("draft banner of Pine Workspace", reasons(plan)["NOTICE"])
        self.assertIn("unfilled licence-template field {{COPYRIGHT_HOLDER}}", reasons(plan)["COPYRIGHT"])
        # an imported permissive licence with a closed source: the Pine code of the source never reaches a public
        # destination, not even inside a legal document
        self.imported("closed-mit", {"LICENSE": MIT_LICENSE, "NOTICE": b"Bundled code:\nindicator(\"Test Indicator\")\n"},
                      lid="MIT", header=MIT_HEADER, profile="PRIVATE")
        self.declare("closed-mit", "LICENSE", "NOTICE")
        plan = github.export_plan(self.root, "closed-mit", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("never exported to a public destination", reasons(plan)["NOTICE"])
        self.assertIn("never exported to a public destination", reasons(plan)["My Indicator.pine"])
        # towards a private destination: sent only once GitHub reports the repository PRIVATE (I-06)
        vault = make_bare_with_main(self.tmp.name, "vault")
        self.gh.serve(vault, "owner/vault")
        self.assertTrue(github.destination_add(self.root, "vault", "owner/vault", "private", "", "main",
                                               url=str(vault))["ok"])
        plan = github.export_plan(self.root, "closed-mit", "vault")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(sorted(c["path"] for c in plan["visibility_check"]["closed_content"]),
                         ["closed-mit/NOTICE", "closed-mit/closed-mit.pine"])
        self.assertTrue(github.fetch(self.root, "vault")["ok"])
        self.gh.repo("owner/vault", "PUBLIC")
        r = github.publish(self.root, "closed-mit", "vault", "export", yes=True, **self.gh.kw)
        self.assertEqual((r["ok"], r["published"]), (False, False))
        self.assertIn("GitHub reports owner/vault as PUBLIC", r["error"])
        self.assertEqual(listing(vault), ["README.md"])
        self.gh.repo("owner/vault", "PRIVATE")
        r = github.publish(self.root, "closed-mit", "vault", "export", yes=True, **self.gh.kw)
        self.assertTrue(r["published"], r)
        self.assertEqual(sent_bytes(vault, "closed-mit/LICENSE"), MIT_LICENSE)

    def test_declared_document_missing_or_modified_after_the_plan(self):
        pdir = self.imported("watched", {"LICENSE": APACHE_LICENSE, "NOTICE": APACHE_NOTICE})
        self.declare("watched", "LICENSE", "NOTICE")
        self.assertTrue(github.export_plan(self.root, "watched", "pub")["ok"])
        self.assertTrue(github.fetch(self.root, "pub")["ok"])
        (pdir / "NOTICE").write_bytes(APACHE_NOTICE + b"Line added after the plan.\n")
        for r in (github.export_diff(self.root, "watched", "pub", **self.gh.kw),
                  github.publish(self.root, "watched", "pub", "export", yes=True, **self.gh.kw)):
            self.assertFalse(r["ok"])
            self.assertIn("the product changed since the plan (watched/NOTICE)", r["error"])
        (pdir / "NOTICE").write_bytes(APACHE_NOTICE)
        self.assertTrue(github.export_plan(self.root, "watched", "pub")["ok"])
        (pdir / "NOTICE").unlink()
        for r in (github.export_diff(self.root, "watched", "pub", **self.gh.kw),
                  github.publish(self.root, "watched", "pub", "export", yes=True, **self.gh.kw)):
            self.assertFalse(r["ok"])
            self.assertIn("export-plan would now refuse", r["error"])
            self.assertIn("declared legal document NOTICE: absent", r["error"])
        product = github._product(self.root, "watched")
        self.assertEqual(product["product_structure_status"], "REGISTERED")          # current work continues
        self.assertIn(("LICENSE_DOCUMENT_UNAVAILABLE", "WARNING"),
                      [(f["code"], f["severity"]) for f in product["findings"]])
        # the staged copy altered after the plan: the file sent is the one checked
        (pdir / "NOTICE").write_bytes(APACHE_NOTICE)
        plan = github.export_plan(self.root, "watched", "pub")
        (Path(plan["staging"]) / "files" / "watched" / "NOTICE").write_bytes(b"altered copy\n")
        r = github.publish(self.root, "watched", "pub", "export", yes=True, **self.gh.kw)
        self.assertFalse(r["ok"])
        self.assertIn("staged file watched/NOTICE altered or missing since the plan", r["error"])
        self.assertEqual(listing(self.pub), ["README.md"])

    def test_target_name_collisions_are_refused(self):
        pdir = self.imported("twins", {"LICENSE.md": APACHE_LICENSE, "release/LICENSE.md": APACHE_LICENSE + b"(2)\n",
                                       "NOTICE": APACHE_NOTICE, "release/notice": APACHE_NOTICE})
        for docs in (["LICENSE.md", "release/LICENSE.md"], ["NOTICE", "release/notice"]):
            with self.subTest(docs=docs):
                r = licensing.confirm_publication(self.root, "twins", license_documents=docs)
                self.assertFalse(r["ok"], r)
                self.assertIn("would be exported under the same name", r["error"])
        set_license(pdir, documents=["LICENSE.md", "release/LICENSE.md", "NOTICE", "release/notice"])
        plan = github.export_plan(self.root, "twins", "pub")
        self.assertFalse(plan["ok"])
        self.assertIn("several files would be exported under the same target name", plan["error"])
        self.assertEqual(sorted(c["to"] for c in plan["collisions"]), ["twins/LICENSE.md", "twins/notice"])

    # ---- independent cross-check of 2026-11-14 (A-1 to A-8) -----------------------------------------------------

    def seed(self, changes, message):
        """Commit files into the destination repository through its seed clone (as another contributor would)."""
        seed = Path(self.tmp.name) / "seed public scripts"
        for rel, text in changes.items():
            (seed / rel).parent.mkdir(parents=True, exist_ok=True)
            (seed / rel).write_text(text, encoding="utf-8")
        git("add", "-A", cwd=seed)
        git("commit", "-m", message, cwd=seed)
        git("push", "origin", "HEAD:main", cwd=seed)

    def test_line_endings_and_git_filters_never_alter_the_sent_bytes(self):
        """A-1: git would normalize the CRLF of an original document (`* text=auto`
        in the destination, core.autocrlf): refused before any write — the
        exact bytes or nothing; exempted by the holder, the bytes are sent."""
        crlf = b"Fictitious Indicator\r\nCopyright 2025 Fictitious Author\r\n"
        self.seed({".gitattributes": "* text=auto\n"}, "attributes")
        self.imported("crlf-one", {"LICENSE": APACHE_LICENSE, "NOTICE": crlf})
        self.declare("crlf-one", "LICENSE", "NOTICE")
        self.assertTrue(github.export_plan(self.root, "crlf-one", "pub")["ok"])
        f = github.fetch(self.root, "pub")
        clone = Path(f["path"])
        d = github.export_diff(self.root, "crlf-one", "pub", **self.gh.kw)
        self.assertFalse(d["ok"])
        self.assertEqual([a["path"] for a in d["content_check"]["altered"]], ["crlf-one/NOTICE"])
        self.assertIn("the exact bytes of the plan cannot be committed", d["error"])
        r = github.publish(self.root, "crlf-one", "pub", "export", yes=True, **self.gh.kw)
        self.assertEqual((r["ok"], r["published"]), (False, False))
        self.assertIn("refused before any write or push", r["error"])
        self.assertEqual(git("status", "--porcelain", cwd=clone).stdout.strip(), "")
        self.assertNotIn("crlf-one/NOTICE", listing(self.pub))
        # the holder exempts these files from any conversion: the original bytes are sent
        self.seed({".gitattributes": "* text=auto\ncrlf-one/** -text\n"}, "exempt the export")
        self.assertTrue(github.fetch(self.root, "pub")["ok"])
        r = github.publish(self.root, "crlf-one", "pub", "export", yes=True, **self.gh.kw)
        self.assertTrue(r["published"], r)
        self.assertEqual(sent_bytes(self.pub, "crlf-one/NOTICE"), crlf)
        # core.autocrlf of the git configuration is seen too
        self.imported("crlf-two", {"NOTICE": crlf})
        self.declare("crlf-two", "NOTICE")
        self.assertTrue(github.export_plan(self.root, "crlf-two", "pub")["ok"])
        git("config", "core.autocrlf", "input", cwd=clone)
        r = github.publish(self.root, "crlf-two", "pub", "export", yes=True, **self.gh.kw)
        self.assertFalse(r["ok"])
        self.assertEqual([a["path"] for a in r["content_check"]["altered"]], ["crlf-two/NOTICE"])
        self.assertNotIn("crlf-two/NOTICE", listing(self.pub))

    def test_a_name_differing_only_by_case_is_another_document(self):
        """A-2: on a case-sensitive file system, `License` beside a declared
        `LICENSE` is another document — never taken for it, never dropped
        silently (simulated: this machine's file system may keep one name only)."""
        self.imported("cased", {"LICENSE": APACHE_LICENSE})
        self.declare("cased", "LICENSE")
        real = profiles.legal_document_candidates

        def with_variant(product_dir):
            return real(product_dir) + [{"path": "License", "kind": "file", "declarable": True, "reason": None}]
        with mock.patch.object(profiles, "legal_document_candidates", with_variant):
            plan = github.export_plan(self.root, "cased", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("found in the product but not declared: License (file)", plan["error"])
        self.assertIn("differs from a declared document only by case", plan["error"])

    def test_case_variant_in_the_destination_repository_is_refused(self):
        """A-3: the repository already tracks `case-one/license`; git would update
        that entry under its old name on a case-insensitive file system — the
        target is refused, nothing written."""
        self.seed({"case-one/license": "older text\n"}, "older licence file")
        self.imported("case-one", {"LICENSE": APACHE_LICENSE})
        self.declare("case-one", "LICENSE")
        self.assertTrue(github.export_plan(self.root, "case-one", "pub")["ok"])
        clone = Path(github.fetch(self.root, "pub")["path"])
        d = github.export_diff(self.root, "case-one", "pub", **self.gh.kw)
        change = next(c for c in d["changes"] if c["path"] == "case-one/LICENSE")["change"]
        self.assertIn("REFUSED (the destination repository holds case-one/license, whose name differs from "
                      "case-one/LICENSE only by case", change)
        r = github.publish(self.root, "case-one", "pub", "export", yes=True, **self.gh.kw)
        self.assertFalse(r["ok"])
        self.assertEqual(git("status", "--porcelain", cwd=clone).stdout.strip(), "")
        self.assertEqual(sent_bytes(self.pub, "case-one/license"), b"older text\n")

    def test_links_folders_and_other_legal_names_wait_for_the_holder(self):
        """A-4 / A-5: a LICENSES/ that is a link, an attribution file (AUTHORS)
        and a document out of place (legal/PATENTS) are never left out
        silently: the export waits, each with its resolution."""
        pdir = self.imported("others", {"LICENSE": APACHE_LICENSE, "AUTHORS": b"Fictitious Author\n",
                                        "legal/PATENTS": b"Fictitious patent grant\n"})
        outside = Path(self.tmp.name) / "third"
        outside.mkdir()
        (outside / "MIT.txt").write_bytes(MIT_LICENSE)
        os.symlink(str(outside), str(pdir / "LICENSES"))
        self.declare("others", "LICENSE")
        plan = github.export_plan(self.root, "others", "pub")
        self.assertFalse(plan["ok"], plan)
        self.assertIn("found in the product but not declared: AUTHORS (file)", plan["error"])
        self.assertIn("LICENSES (a symbolic link — never followed)", plan["error"])
        self.assertIn("legal/PATENTS (must lie at the product root", plan["error"])
        self.assertIn("move the original documents", plan["error"])
        # the holder replaces the link and moves the out-of-place document, then declares everything
        os.unlink(str(pdir / "LICENSES"))
        (pdir / "LICENSES").mkdir()
        (pdir / "LICENSES" / "MIT.txt").write_bytes(MIT_LICENSE)
        shutil.move(str(pdir / "legal" / "PATENTS"), str(pdir / "PATENTS"))
        self.declare("others", "LICENSE", "AUTHORS", "PATENTS", "LICENSES/MIT.txt")
        plan = github.export_plan(self.root, "others", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(sorted(self.staged(plan)), ["others/AUTHORS", "others/LICENSE", "others/LICENSES/MIT.txt",
                                                     "others/PATENTS", "others/others.pine"])

    def test_a_profile_licence_keeps_its_rules(self):
        """The holder's own products are not concerned: their legal documents are
        the ones PWS renders; a declaration is refused and makes a hand-edited
        manifest BROKEN."""
        pdir = helpers.make_product_v3(self.root, slug="own-free", profile="FREE")
        (pdir / "COPYING").write_bytes(b"own text\n")
        plan = github.export_plan(self.root, "own-free", "pub")
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(reasons(plan)["COPYING"], "not in the allowed list")
        self.assertNotIn("legal_documents", plan)
        r = licensing.confirm_publication(self.root, "own-free", license_documents=["COPYING"])
        self.assertFalse(r["ok"])
        self.assertIn("recorded only for the existing licence of an imported script", r["error"])
        set_license(pdir, documents=["COPYING"])
        self.assertFalse(github.export_plan(self.root, "own-free", "pub")["ok"])


class TestGithubDestinationIdentity(_IsolatedGit, unittest.TestCase):
    """Identity of the destination for EVERY send (holder's request of
    2026-11-14): the destination's URL and the clone's single fetch and push
    URLs — pushurl and rewritings applied — designate the repository the
    holder authorized, checked before anything is written into the clone and
    again right before the push. GitHub is queried only for the privacy of
    closed content. One mechanism (_origin_remote), as for I-06."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.isolate_git(self.tmp.name)
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root)
        helpers.make_product_v3(self.root, slug="free-one", profile="FREE")
        self.authorized = make_bare_with_main(self.tmp.name, "authorized")
        # another repository with the same history: a push there would succeed
        self.other = Path(self.tmp.name) / "other.git"
        git("clone", "--bare", "--", str(self.authorized), str(self.other))
        self.gh = FakeGitHub()
        self.gh.serve(self.authorized, "owner/public-scripts")
        self.gh.serve(self.other, "owner/other-repo")
        self.assertTrue(github.destination_add(self.root, "pub", "owner/public-scripts", "public", "", "main",
                                               url=str(self.authorized))["ok"])

    def tearDown(self):
        self.restore_git()
        self.tmp.cleanup()
        self.assertEqual(REAL_GH_CALLS, [])

    def prepare(self, slug="free-one", dest="pub"):
        plan = github.export_plan(self.root, slug, dest)
        self.assertTrue(plan["ok"], plan)
        f = github.fetch(self.root, dest)
        self.assertTrue(f["ok"], f)
        return plan, Path(f["path"])

    def publish(self, slug="free-one", dest="pub", **kw):
        return github.publish(self.root, slug, dest, "export", yes=True, **(kw or self.gh.kw))

    def pine(self, bare):
        return [x for x in listing(bare) if x.endswith(".pine")]

    def assert_nothing_sent(self, clone):
        self.assertEqual((self.pine(self.authorized), self.pine(self.other)), ([], []))
        self.assertEqual(git("status", "--porcelain", cwd=clone).stdout.strip(), "")
        self.assertEqual(git("rev-list", "--count", "refs/remotes/origin/main..HEAD", cwd=clone).stdout.strip(), "0")

    def test_public_send_to_the_authorized_repository(self):
        plan, clone = self.prepare()
        self.assertEqual((plan["destination_check"]["required"], plan["destination_check"]["performed"]), (True, False))
        self.assertNotIn("visibility_check", plan)
        d = github.export_diff(self.root, "free-one", "pub", **self.gh.kw)
        self.assertTrue(d["ok"], d)
        self.assertEqual((d["destination_check"]["ok"], d["destination_check"]["remote"]["repository"]),
                         (True, "owner/public-scripts"))
        r = self.publish()
        self.assertTrue(r["published"], r)
        self.assertTrue(r["destination_check"]["ok"])
        self.assertNotIn("visibility_check", r)
        self.assertEqual((self.pine(self.authorized), self.pine(self.other)), (["free-one/free-one.pine"], []))
        self.assertEqual(self.gh.calls, [])

    def test_public_send_to_an_explicitly_private_destination(self):
        vault = make_bare_with_main(self.tmp.name, "private vault")
        self.gh.serve(vault, "owner/private-vault")
        self.assertTrue(github.destination_add(self.root, "vault", "owner/private-vault", "private", "", "main",
                                               url=str(vault))["ok"])
        plan, _ = self.prepare(dest="vault")
        self.assertNotIn("visibility_check", plan)          # public content: no privacy required
        r = self.publish(dest="vault")
        self.assertTrue(r["published"], r)
        self.assertEqual((r["destination_check"]["ok"], r["destination_check"]["remote"]["repository"]),
                         (True, "owner/private-vault"))
        self.assertEqual(self.pine(vault), ["free-one/free-one.pine"])
        self.assertEqual(self.gh.calls, [])

    def test_pushurl_designating_another_repository_is_refused(self):
        _, clone = self.prepare()
        git("config", "remote.origin.pushurl", str(self.other), cwd=clone)
        for r in (github.export_diff(self.root, "free-one", "pub", **self.gh.kw), self.publish()):
            self.assertFalse(r["ok"])
            self.assertIn("git would push to owner/other-repo while the clone fetches from owner/public-scripts "
                          "(remote.origin.pushurl is set)", r["error"])
            self.assertFalse(r["destination_check"]["ok"])
            self.assertNotIn("visibility_check", r)
        self.assertIn("refused before any write or push", r["error"])
        self.assert_nothing_sent(clone)
        self.assertEqual(self.gh.calls, [])

    def test_rewritings_and_multiple_urls_are_refused(self):
        _, clone = self.prepare()
        cfg = clone / ".git" / "config"
        original = cfg.read_text(encoding="utf-8")

        def global_rewriting():
            with open(str(self.global_config), "a", encoding="utf-8") as fh:
                fh.write('[url "%s"]\n\tpushInsteadOf = %s\n' % (self.other, self.authorized))
        cases = (
            ("pushInsteadOf", lambda: git("config", "url.%s.pushInsteadOf" % self.other, str(self.authorized),
                                          cwd=clone),
             "git would push to owner/other-repo while the clone fetches from owner/public-scripts (an insteadOf / "
             "pushInsteadOf rewriting applies)"),
            ("global pushInsteadOf", global_rewriting, "git would push to owner/other-repo while the clone fetches"),
            ("insteadOf", lambda: git("config", "url.%s.insteadOf" % self.other, str(self.authorized), cwd=clone),
             "stale local clone"),
            ("two push URLs", lambda: (git("config", "--add", "remote.origin.pushurl", str(self.authorized), cwd=clone),
                                       git("config", "--add", "remote.origin.pushurl", str(self.other), cwd=clone)),
             "origin has 2 push URLs"),
            ("two fetch URLs", lambda: git("config", "--add", "remote.origin.url", str(self.other), cwd=clone),
             "origin has 2 fetch URLs"),
        )
        for name, change, expected in cases:
            with self.subTest(case=name):
                change()
                for r in (github.export_diff(self.root, "free-one", "pub", **self.gh.kw), self.publish()):
                    self.assertFalse(r["ok"])
                    self.assertIn(expected, r["error"])
                self.assert_nothing_sent(clone)
                cfg.write_text(original, encoding="utf-8")
                self.global_config.write_text("", encoding="utf-8")
        self.assertTrue(self.publish()["published"])            # restored: the check passes
        self.assertEqual(self.gh.calls, [])

    def test_destination_changed_between_preparation_and_send(self):
        _, clone = self.prepare()
        self.assertTrue(github.export_diff(self.root, "free-one", "pub", **self.gh.kw)["ok"])
        # redirected after the reviewed comparison: refused before any write
        git("config", "remote.origin.pushurl", str(self.other), cwd=clone)
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertIn("refused before any write or push", r["error"])
        self.assert_nothing_sent(clone)
        git("config", "--unset", "remote.origin.pushurl", cwd=clone)
        # the destination edited by hand after the plan: the plan is bound to the destination
        cfg_path = self.root / "pws.config.json"
        saved = cfg_path.read_text(encoding="utf-8")
        cfg = json.loads(saved)
        cfg["github"]["destinations"][0]["url"] = str(self.other)
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertIn("changed since the plan", r["error"])
        self.assert_nothing_sent(clone)
        cfg_path.write_text(saved, encoding="utf-8")
        # changed AFTER the local commit (injected right after `git commit` — hooks never run in the publication
        # clone): nothing pushed, state described
        real_run = github._run

        def redirect_after_commit(cmd, cwd=None, timeout=120):
            result = real_run(cmd, cwd=cwd, timeout=timeout)
            if "commit" in cmd and "--no-verify" in cmd:
                real_run(["git", "-C", str(clone), "config", "remote.origin.pushurl", str(self.other)])
            return result
        with mock.patch.object(github, "_run", redirect_after_commit):
            r = self.publish()
        self.assertEqual((r["ok"], r["published"]), (False, False))
        self.assertIn("the destination of the clone changed after the check", r["error"])
        self.assertIn("nothing pushed", r["error"])
        self.assertIn("git would push to owner/other-repo", r["destination_recheck"]["error"])
        state = r["state_left"]
        head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
        self.assertEqual((state["stage"], state["pushed"], state["committed"], state["branch"], state["commit"]),
                         ("destination changed after the local commit", False, True, "main", head))
        self.assertEqual(state["files_written"], ["free-one/free-one.pine"])
        self.assertEqual(state["unpublished_work"]["local_commits"], 1)
        self.assertEqual(state["clone"], str(clone))
        self.assertIn("discard it yourself", state["next"])
        self.assertEqual((self.pine(self.authorized), self.pine(self.other)), ([], []))   # nothing pushed anywhere
        git("config", "--unset", "remote.origin.pushurl", cwd=clone)
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertIn("unpublished local work", r["error"])
        self.assertEqual(self.gh.calls, [])

    def test_trap_urls_are_refused_with_their_real_host(self):
        _, clone = self.prepare()
        cfg = clone / ".git" / "config"
        original = cfg.read_text(encoding="utf-8")
        for crafted in ("https://attacker.invalid#@github.com/owner/public-scripts.git",
                        "https://attacker.invalid?@github.com/owner/public-scripts.git"):
            with self.subTest(crafted=crafted):
                git("config", "remote.origin.pushurl", crafted, cwd=clone)
                for r in (github.export_diff(self.root, "free-one", "pub", **self.gh.kw), self.publish()):
                    self.assertFalse(r["ok"])
                    self.assertIn("the push URL", r["error"])
                    self.assertIn("host for git: attacker.invalid", r["error"])
                    self.assertNotIn("***@github.com", json.dumps(r))
                self.assert_nothing_sent(clone)
                cfg.write_text(original, encoding="utf-8")
        # the destination's own URL crafted (as a fetch would have left the clone): never a send
        crafted = "https://attacker.invalid?@github.com/owner/public-scripts.git"
        self.assertTrue(github.destination_add(self.root, "d", "owner/public-scripts", "public", "", "main",
                                               url=crafted)["ok"])
        self.assertTrue(github.export_plan(self.root, "free-one", "d")["ok"])
        dclone = self.root / github.EXPORT_REL / github.CLONES_DIRNAME / "d"
        git("clone", "--branch", "main", "--single-branch", "--", str(self.authorized), str(dclone))
        git("remote", "set-url", "origin", crafted, cwd=dclone)
        r = github.publish(self.root, "free-one", "d", "export", yes=True, gh_runner=self.gh.gh)
        self.assertEqual((r["ok"], r.get("published")), (False, False))
        self.assertIn("the destination's URL https://attacker.invalid?*** (host for git: attacker.invalid) is not "
                      "an https or ssh URL of the github.com repository owner/public-scripts", r["error"])
        self.assert_nothing_sent(dclone)
        self.assertEqual(self.gh.calls, [])

    def test_destination_of_another_or_of_an_unknown_repository_is_refused(self):
        self.assertTrue(github.destination_add(self.root, "mixed", "owner/public-scripts", "public", "", "main",
                                               url=str(self.other))["ok"])
        _, clone = self.prepare(dest="mixed")
        r = self.publish(dest="mixed")
        self.assertFalse(r["ok"])
        self.assertIn("the destination's URL %s is not an https or ssh URL of the github.com repository "
                      "owner/public-scripts" % self.other, r["error"])
        self.assert_nothing_sent(clone)
        # nothing injected (the real reading): a local repository designates no GitHub repository
        _, clone = self.prepare()
        r = github.publish(self.root, "free-one", "pub", "export", yes=True)
        self.assertFalse(r["ok"])
        self.assertIn("is not an https or ssh URL of the github.com repository owner/public-scripts", r["error"])
        self.assertIn("refused before any write or push", r["error"])
        self.assert_nothing_sent(clone)
        self.assertEqual(self.gh.calls, [])

    # ---- independent cross-check of 2026-11-14 (B-1 to B-4) -----------------------------------------------------

    def test_transport_overrides_are_refused(self):
        """B-1: settings that make git connect elsewhere than the URL shows (or
        without verifying it) — in the clone, in the global configuration or in
        the environment — are refused like a pushurl, before any write."""
        _, clone = self.prepare()
        cfg = clone / ".git" / "config"
        original = cfg.read_text(encoding="utf-8")

        def global_ssh():
            with open(str(self.global_config), "a", encoding="utf-8") as fh:
                fh.write("[core]\n\tsshCommand = ssh -F /dev/null\n")
        cases = (
            ("core.sshCommand", lambda: git("config", "core.sshCommand", "ssh -F /dev/null", cwd=clone),
             "core.sshcommand is set"),
            ("global core.sshCommand", global_ssh, "core.sshcommand is set"),
            ("http.sslVerify", lambda: git("config", "http.sslVerify", "false", cwd=clone), "TLS verification disabled"),
            ("http.curloptResolve", lambda: git("config", "http.curloptResolve", "github.com:443:192.0.2.1", cwd=clone),
             "http.curloptresolve is set"),
            ("remote.origin.vcs", lambda: git("config", "remote.origin.vcs", "fictitious", cwd=clone),
             "remote.origin.vcs is set"),
        )
        for name, change, expected in cases:
            with self.subTest(case=name):
                change()
                for r in (github.export_diff(self.root, "free-one", "pub", **self.gh.kw), self.publish()):
                    self.assertFalse(r["ok"])
                    self.assertIn(expected, r["error"])
                    self.assertIn("git would not connect to owner/public-scripts as its URL shows", r["error"])
                self.assert_nothing_sent(clone)
                cfg.write_text(original, encoding="utf-8")
                self.global_config.write_text("", encoding="utf-8")
        for var in ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_PROXY_COMMAND", "GIT_SSL_NO_VERIFY"):
            with self.subTest(variable=var), mock.patch.dict(os.environ, {var: "1"}):
                r = self.publish()
                self.assertFalse(r["ok"])
                self.assertIn("the environment variable %s is set" % var, r["error"])
                self.assert_nothing_sent(clone)
        self.assertTrue(self.publish()["published"])
        self.assertEqual(self.gh.calls, [])

    def test_hooks_never_run_in_the_publication_clone(self):
        """B-2: hooks (here from a global core.hooksPath) never run when the
        clone commits and pushes: no amended commit, no push elsewhere."""
        self.prepare()
        hooks = Path(self.tmp.name) / "global-hooks"
        hooks.mkdir()
        marker = Path(self.tmp.name) / "a hook ran"
        (hooks / "post-commit").write_text(
            "#!/bin/sh\necho ran > '%s'\necho extra > unplanned.txt\ngit add unplanned.txt\n"
            "git commit --amend --no-edit -q\n" % marker, encoding="utf-8")
        (hooks / "pre-push").write_text("#!/bin/sh\necho ran > '%s'\ngit push -q '%s' HEAD:refs/heads/main\n"
                                        % (marker, self.other), encoding="utf-8")
        for hook in hooks.iterdir():
            hook.chmod(0o755)
        with open(str(self.global_config), "a", encoding="utf-8") as fh:
            fh.write("[core]\n\thooksPath = %s\n" % hooks)
        r = self.publish()
        self.assertTrue(r["published"], r)
        self.assertFalse(marker.exists())
        self.assertEqual(sorted(listing(self.authorized)), ["README.md", "free-one/free-one.pine"])
        self.assertEqual(self.pine(self.other), [])

    def test_a_commit_that_differs_from_the_plan_is_never_pushed(self):
        """The local commit is checked before the push: one new commit, only the
        planned paths, each with the exact bytes (here a change slipped in
        right after `git commit`)."""
        _, clone = self.prepare()
        real_run = github._run

        def amend_after_commit(cmd, cwd=None, timeout=120):
            result = real_run(cmd, cwd=cwd, timeout=timeout)
            if "commit" in cmd and "--no-verify" in cmd:
                (clone / "unplanned.txt").write_text("not in the plan\n", encoding="utf-8")
                real_run(["git", "-C", str(clone), "add", "unplanned.txt"])
                real_run(["git", "-C", str(clone), "commit", "--amend", "--no-edit", "-q"])
            return result
        with mock.patch.object(github, "_run", amend_after_commit):
            r = self.publish()
        self.assertEqual((r["ok"], r["published"]), (False, False))
        self.assertIn("differs from the plan (it also changes unplanned.txt, outside the plan)", r["error"])
        self.assertEqual(r["state_left"]["stage"], "the local commit differs from the plan")
        self.assertEqual((self.pine(self.authorized), self.pine(self.other)), ([], []))

    def test_empty_push_url_entry_and_file_where_a_folder_is_needed_are_refused(self):
        """B-3: an empty pushurl entry is still a push target for git; B-4: a file
        of the repository where the export needs a folder. Both refused before
        any write."""
        _, clone = self.prepare()
        git("config", "--add", "remote.origin.pushurl", str(self.authorized), cwd=clone)
        git("config", "--add", "remote.origin.pushurl", "", cwd=clone)
        for r in (github.export_diff(self.root, "free-one", "pub", **self.gh.kw), self.publish()):
            self.assertFalse(r["ok"])
            self.assertIn("origin has an empty URL entry (remote.origin.pushurl)", r["error"])
        self.assert_nothing_sent(clone)
        git("config", "--unset-all", "remote.origin.pushurl", cwd=clone)
        seed = Path(self.tmp.name) / "seed authorized"
        (seed / "free-one").write_text("a file where the export needs a folder\n", encoding="utf-8")
        git("add", "free-one", cwd=seed)
        git("commit", "-m", "file", cwd=seed)
        git("push", "origin", "HEAD:main", cwd=seed)
        self.assertTrue(github.fetch(self.root, "pub")["ok"])
        d = github.export_diff(self.root, "free-one", "pub", **self.gh.kw)
        self.assertEqual([c["change"] for c in d["changes"]],
                         ["REFUSED (a file of the destination repository stands where a folder is needed (free-one))"])
        r = self.publish()
        self.assertFalse(r["ok"])
        self.assertIn("refused path in the plan", r["error"])
        self.assertEqual(git("status", "--porcelain", cwd=clone).stdout.strip(), "")

    def test_closed_content_keeps_the_real_privacy_check(self):
        helpers.make_product_v3(self.root, slug="paid-one", profile="COMMERCIAL")
        vault = make_bare_with_main(self.tmp.name, "vault")
        self.gh.serve(vault, "owner/vault")
        self.assertTrue(github.destination_add(self.root, "vault", "owner/vault", "private", "", "main",
                                               url=str(vault))["ok"])
        plan, clone = self.prepare(slug="paid-one", dest="vault")
        self.assertIn("destination_check", plan)
        self.assertIn("visibility_check", plan)
        self.gh.repo("owner/vault", "PUBLIC")
        r = self.publish(slug="paid-one", dest="vault")
        self.assertFalse(r["ok"])
        self.assertTrue(r["destination_check"]["ok"])                 # the right repository…
        self.assertFalse(r["visibility_check"]["ok"])                 # …but not private: refused
        self.assertIn("GitHub reports owner/vault as PUBLIC", r["error"])
        self.assertEqual(self.pine(vault), [])
        self.gh.repo("owner/vault", "PRIVATE")
        r = self.publish(slug="paid-one", dest="vault")
        self.assertTrue(r["published"], r)
        self.assertEqual(self.pine(vault), ["paid-one/paid-one.pine"])
        self.assertEqual(self.gh.calls, [GH_VIEW, GH_VIEW])
        # towards the public destination the closed source is never planned, whatever the identity check says
        plan = github.export_plan(self.root, "paid-one", "pub")
        self.assertIn("never exported to a public destination", reasons(plan)["My Indicator.pine"])


class TestGithubUrlReading(unittest.TestCase):
    """Reading of remote URLs, masking of credentials and the real gh executor (never run)."""

    def test_github_repository_urls(self):
        """Strict reading (review RS-01, 2026-11-13 — contract change: a user
        part, an explicit port, the scp form without `git@` and an upper-case
        scheme or host, accepted before, are now refused for a closed send)."""
        accepted = ("https://github.com/owner/vault.git", "https://github.com/owner/vault",
                    "https://github.com/owner/vault/", "https://github.com/owner/vault.git/",
                    "git@github.com:owner/vault.git", "git@github.com:owner/vault",
                    "ssh://git@github.com/owner/vault.git", "ssh://git@github.com/owner/vault")
        for url in accepted:
            self.assertEqual(github._github_repo_of_url(url), "owner/vault", url)
        self.assertEqual(github._github_repo_of_url("https://github.com/Owner/Vault.git"), "Owner/Vault")
        refused = ("https://ghe.example.com/owner/vault.git", "git://github.com/owner/vault.git",
                   "http://github.com/owner/vault.git", "file:///srv/owner/vault.git", "/srv/vault.git", "origin",
                   "https://github.com/owner/vault/tree/main", "https://github.com/owner/vault.git?ref=x",
                   "https://github.com:8443/owner/vault.git", "ssh://git@ssh.github.com:443/owner/vault.git",
                   "https://www.github.com/owner/vault.git", "https://github.com/owner", "",
                   "https://github.com/own%65r/vault.git", None,
                   # accepted before the strict reading (RS-01)
                   "github.com:owner/vault", "ssh://git@github.com:22/owner/vault.git",
                   "https://someone:secret@github.com/owner/vault.git", "HTTPS://GitHub.com/owner/vault.git",
                   "https://GitHub.com/owner/vault.git", "https://github.com:443/owner/vault.git",
                   # user parts git does not read as credentials: another host for git (RS-01)
                   "https://attacker.invalid#@github.com/owner/vault.git",
                   "https://attacker.invalid?@github.com/owner/vault.git",
                   "https://[::1]#@github.com/owner/vault.git", "https://attacker.invalid\\@github.com/owner/vault.git",
                   "https://a[b]@github.com/owner/vault.git", "https://git@github.com/owner/vault.git",
                   "ssh://attacker.invalid#@github.com/owner/vault.git", "attacker.invalid#@github.com:owner/vault.git",
                   "ssh://zz@github.com/owner/vault.git", "zz@github.com:owner/vault.git",
                   # fragment, surrounding spaces, trailing newline, trailing slash of the ssh forms
                   "https://github.com/owner/vault.git#main", " https://github.com/owner/vault.git",
                   "https://github.com/owner/vault.git\n", "git@github.com:owner/vault/",
                   "ssh://git@github.com/owner/vault/", "https://github.com/-owner/vault.git")
        for url in refused:
            self.assertIsNone(github._github_repo_of_url(url), url)

    def test_the_host_git_really_contacts_is_read_as_git_reads_it(self):
        """RS-01: https (curl, RFC 3986) — the authority ends at the first « / »,
        « ? » or « # »; ssh and the scp form pass the user part with the
        host to ssh, which splits them at the last « @ » (observed with git
        2.42 / curl 8.7 through a loopback capture proxy: CONNECT
        attacker.invalid for `#@` and `?@`, github.com for `\\@`, `[b]@` and
        `%23@`)."""
        cases = (
            ("https://attacker.invalid#@github.com/owner/vault.git", "attacker.invalid"),
            ("https://attacker.invalid?@github.com/owner/vault.git", "attacker.invalid"),
            ("https://[::1]#@github.com/owner/vault.git", "[::1]"),
            ("https://attacker.invalid\\@github.com/owner/vault.git", "github.com"),
            ("https://a[b]@github.com/o/r.git", "github.com"),
            ("https://attacker.invalid%23@github.com/o/r.git", "github.com"),
            ("https://zz@attacker.invalid@github.com/o/r.git", "attacker.invalid@github.com"),
            ("https://github.com:443/owner/vault.git", "github.com"),
            ("https://someone:secret@github.com/owner/vault.git", "github.com"),
            ("ssh://attacker.invalid#@github.com/owner/vault.git", "github.com"),
            ("ssh://git@github.com:22/owner/vault.git", "github.com"),
            ("attacker.invalid#@github.com:owner/vault.git", "github.com"),
            ("git@github.com:owner/vault.git", "github.com"),
            ("/srv/vault.git", None), ("origin", None), ("file:///srv/vault.git", None),
        )
        for url, host in cases:
            self.assertEqual(github._git_host(url), host, url)

    def test_credentials_masked_in_displayed_text(self):
        self.assertEqual(github._redact_text("fatal: 'https://user:tok@github.com/o/r.git/' x"),
                         "fatal: 'https://***@github.com/o/r.git/' x")
        self.assertEqual(github._redact_text("https://user:p@ss@github.com/o/r"), "https://***@github.com/o/r")
        self.assertEqual(github._redact_text("ghp_x@github.com:o/r.git"), "***@github.com:o/r.git")
        self.assertEqual(github._redact_text("https://github.com/o/r?token=abc"), "https://github.com/o/r?***")
        for kept in ("git@github.com:o/r.git", "ssh://git@github.com/o/r.git", "/tmp/pws test/clones/s1"):
            self.assertEqual(github._redact_text(kept), kept)
        # RS-01: a part git does not read as credentials is never masked — the real host stays visible
        for crafted in ("https://attacker.invalid#@github.com/owner/vault.git",
                        "https://[::1]#@github.com/owner/vault.git",
                        "https://attacker.invalid\\@github.com/owner/vault.git"):
            self.assertEqual(github._redact_text(crafted), crafted)
        self.assertEqual(github._redact_text("https://attacker.invalid?@github.com/owner/vault.git"),
                         "https://attacker.invalid?***")
        self.assertEqual(github._redact_text("https://x@attacker.invalid#@github.com/o/r"),
                         "https://***@attacker.invalid#@github.com/o/r")

    def test_real_executor_runs_gh_repo_view_non_interactively(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(cmd=cmd, env=kw.get("env"), stdin=kw.get("stdin"), timeout=kw.get("timeout"))
            return subprocess.CompletedProcess(cmd, 0, stdout='{"x": 1}\n', stderr="")
        with mock.patch.object(github.shutil, "which", return_value="/opt/fake/gh"), \
                mock.patch.object(github.subprocess, "run", fake_run), \
                mock.patch.dict(os.environ, {"GH_DEBUG": "api", "GH_FORCE_TTY": "1"}):
            self.assertEqual(REAL_GH_RUN(GH_VIEW), (0, '{"x": 1}', ""))
        self.assertEqual(seen["cmd"], ["/opt/fake/gh"] + GH_VIEW)
        self.assertNotIn("GH_DEBUG", seen["env"])
        self.assertNotIn("GH_FORCE_TTY", seen["env"])
        self.assertEqual((seen["env"]["GH_PROMPT_DISABLED"], seen["stdin"], seen["timeout"]),
                         ("1", subprocess.DEVNULL, github.GH_TIMEOUT))
        with mock.patch.object(github.shutil, "which", return_value=None):
            self.assertEqual(REAL_GH_RUN(GH_VIEW)[0], 127)


if __name__ == "__main__":
    unittest.main()
