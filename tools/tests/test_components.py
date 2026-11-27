# SPDX-License-Identifier: Apache-2.0
"""Preparation of the local test components at installation (tools/pws_workspace/components.py): Node/npm
missing, a Vela failure that leaves the numeric test usable, resumption that redoes nothing already
ready and never touches scripts, Vela provenance only from a provenance-record plan, demonstration data
checked by SHA-256. npm and the Vela guide are replaced by fakes; no network."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import components, live


class FakeGuide:
    PKG = "@luxalgo/vela"

    def __init__(self, root, kind="record-provenance"):
        self.root, self.kind, self.applied = Path(root), kind, 0

    def identity(self, root):
        nm = Path(root) / "tools/vela_view/node_modules/@luxalgo/vela"
        installed = json.loads((nm / "package.json").read_text())["version"] if (nm / "package.json").is_file() else None
        prov = json.loads((Path(root) / "tools/vela_view/PROVENANCE.json").read_text()) if (Path(root) / "tools/vela_view/PROVENANCE.json").is_file() else None
        ui = Path(root) / "tools/vela_view/node_modules/@luxalgo/vela-ui/package.json"
        return {"installed": installed, "installed_ui": json.loads(ui.read_text())["version"] if ui.is_file() else None,
                "connector_installed": False,
                "bundle_sha256": "b" * 64 if installed else None, "provenance": prov}

    def prepare(self, root, target=None, lang=None):
        f = Path(tempfile.mkdtemp()) / "plan.json"; f.write_text(json.dumps({"kind": self.kind, "target": {"version": target}}))
        return {"plan_file": str(f), "problems": []}

    def apply(self, root, plan_file, yes=False, lang=None):
        self.applied += 1
        (Path(root) / "tools/vela_view/PROVENANCE.json").write_text(json.dumps({"pinned_version": "0.10.15", "bundle": {"sha256": "b" * 64}}))
        return {"status": "provenance-recorded"}


class Components(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pws comp "))
        for rel, pkg in (("tools/pine_exec", {"dependencies": {"pinets": "0.13.1"}}), ("tools/vela_view", {"dependencies": {"@luxalgo/vela": "0.10.15"}})):
            (self.root / rel).mkdir(parents=True); (self.root / rel / "package.json").write_text(json.dumps(pkg))
        (self.root / "tools/pine_exec/package-lock.json").write_text(json.dumps({"packages": {"": {}}}))
        (self.root / "tools/vela_view/package-lock.json").write_text(json.dumps({"packages": {"": {},
            "node_modules/@luxalgo/vela": {"version": "0.10.15"}, "node_modules/@luxalgo/vela-ui": {"version": "0.4.4"}}}))
        (self.root / "tools/vela_view/page").mkdir(); (self.root / "tools/vela_view/page/pws-view.js").write_text("//")
        (self.root / "scripts/mine").mkdir(parents=True); (self.root / "scripts/mine/My.pine").write_text("//@version=6\n")
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def runner(self, fail_vela=False):
        def run(cmd, cwd, timeout=900):
            self.calls.append((Path(cwd).name, cmd[1]))
            if cmd[1] == "ci" and Path(cwd).name == "vela_view":
                if fail_vela:
                    return 1, "", "npm ERR! network"
                nm = Path(cwd) / "node_modules/@luxalgo/vela"; (nm / "dist").mkdir(parents=True, exist_ok=True)
                (nm / "package.json").write_text(json.dumps({"version": "0.10.15"})); (nm / "dist/vela.global.min.js").write_text("v")
                ui = Path(cwd) / "node_modules/@luxalgo/vela-ui"; ui.mkdir(parents=True, exist_ok=True)
                (ui / "package.json").write_text(json.dumps({"version": "0.4.4"}))
            if cmd[1] == "datasets.mjs":
                Path(cmd[-1]).write_text("demo")
            return 0, "", ""
        return run

    def pinets_ready(self, state):
        return mock.patch.object(components, "_pinets_ready", side_effect=lambda root: (state["ready"], [], "f" * 64))

    def test_node_missing_says_what_is_missing_and_how_to_resume(self):
        with mock.patch.object(components.shutil, "which", return_value=None):
            r = components.prepare(self.root, lang="fr")
        self.assertFalse(r["ok"]); self.assertFalse(r["numeric_test_usable"])
        self.assertIn("node, npm", r["problem"]); self.assertIn(components.RESUME, r["summary"])
        self.assertTrue((self.root / components.STATE).is_file())
        self.assertEqual((self.root / "scripts/mine/My.pine").read_text(), "//@version=6\n")

    def test_vela_failure_keeps_numeric_test_and_resume_completes(self):
        state = {"ready": False}
        def ci_pinets(cmd, cwd, timeout=900):
            if Path(cwd).name == "pine_exec":
                state["ready"] = True
            return self.runner(fail_vela=True)(cmd, cwd, timeout)
        guide = FakeGuide(self.root)
        with self.pinets_ready(state), mock.patch.object(components, "DEMO_SHA256", components.hashlib.sha256(b"demo").hexdigest()), \
                mock.patch.object(components.shutil, "which", side_effect=lambda b: "/usr/bin/" + b):
            r = components.prepare(self.root, lang="fr", runner=ci_pinets, guide=guide)
            self.assertFalse(r["ok"]); self.assertTrue(r["numeric_test_usable"]); self.assertFalse(r["chart_usable"])
            self.assertIn("Le test local numérique est utilisable", r["summary"]); self.assertIn(components.RESUME, r["summary"])
            self.assertIn("npm ci failed in tools/vela_view", r["components"][2]["problem"])
            # resume: what is ready is not redone; Vela is prepared; provenance recorded once
            self.calls.clear()
            with mock.patch.object(live, "vela_state", side_effect=lambda root: "ready" if (Path(root) / "tools/vela_view/node_modules/@luxalgo/vela/dist/vela.global.min.js").is_file() else "no-deps"):
                r2 = components.prepare(self.root, lang="fr", runner=self.runner(), guide=guide)
                self.assertTrue(r2["ok"], r2["summary"]); self.assertEqual(self.calls, [("vela_view", "ci")])
                self.assertEqual(guide.applied, 1)
                self.calls.clear()
                r3 = components.prepare(self.root, lang="fr", runner=self.runner(), guide=guide)
                self.assertTrue(r3["ok"]); self.assertEqual(self.calls, []); self.assertEqual(guide.applied, 1)
        self.assertEqual((self.root / "scripts/mine/My.pine").read_text(), "//@version=6\n")

    def test_vela_provenance_never_from_an_update_plan(self):
        state = {"ready": True}
        guide = FakeGuide(self.root, kind="update")
        with self.pinets_ready(state), mock.patch.object(components, "DEMO_SHA256", components.hashlib.sha256(b"demo").hexdigest()), \
                mock.patch.object(components.shutil, "which", side_effect=lambda b: "/usr/bin/" + b), \
                mock.patch.object(live, "vela_state", return_value="ready"):
            r = components.prepare(self.root, lang="en", runner=self.runner(), guide=guide)
        v = r["components"][2]
        self.assertFalse(v["ok"]); self.assertIn("not a provenance record (update)", v["problem"]); self.assertEqual(guide.applied, 0)

    def _ready_vela_with_ui(self, ui_version):
        nm = self.root / "tools/vela_view/node_modules/@luxalgo"
        (nm / "vela/dist").mkdir(parents=True); (nm / "vela/package.json").write_text(json.dumps({"version": "0.10.15"}))
        (nm / "vela/dist/vela.global.min.js").write_text("v")
        (nm / "vela-ui").mkdir(); (nm / "vela-ui/package.json").write_text(json.dumps({"version": ui_version}))
        (self.root / "tools/vela_view/PROVENANCE.json").write_text(json.dumps({"pinned_version": "0.10.15", "bundle": {"sha256": "b" * 64}}))

    def test_vela_ui_differing_from_the_lockfile_is_repaired_then_left_alone(self):
        self._ready_vela_with_ui("0.4.3")                               # Vela 0.10.15 + valid provenance, vela-ui 0.4.3
        guide = FakeGuide(self.root)
        with mock.patch.object(components.shutil, "which", side_effect=lambda b: "/usr/bin/" + b), \
                mock.patch.object(live, "vela_state", return_value="ready"):
            v = components.prepare_vela(self.root, runner=self.runner(), guide=guide)
            self.assertTrue(v["ok"], v); self.assertEqual(v["vela_ui"], "0.4.4")
            self.assertEqual(v["actions"][0], {"lock_mismatches": [{"package": "@luxalgo/vela-ui", "locked": "0.4.4", "installed": "0.4.3"}]})
            self.assertEqual(self.calls, [("vela_view", "ci")]); self.assertEqual(guide.applied, 0)
            self.calls.clear()
            v2 = components.prepare_vela(self.root, runner=self.runner(), guide=guide)
            self.assertTrue(v2["ok"]); self.assertEqual(self.calls, []); self.assertEqual(v2["actions"], [])

    def test_failed_vela_ui_repair_names_vela_and_keeps_the_numeric_test(self):
        self._ready_vela_with_ui("0.4.3")
        with self.pinets_ready({"ready": True}), mock.patch.object(components, "DEMO_SHA256", components.hashlib.sha256(b"demo").hexdigest()), \
                mock.patch.object(components.shutil, "which", side_effect=lambda b: "/usr/bin/" + b), \
                mock.patch.object(live, "vela_state", return_value="ready"):
            r = components.prepare(self.root, lang="fr", runner=self.runner(fail_vela=True), guide=FakeGuide(self.root))
        v = r["components"][2]
        self.assertFalse(v["ok"]); self.assertIn("@luxalgo/vela-ui 0.4.3 (locked 0.4.4)", v["problem"])
        self.assertTrue(r["numeric_test_usable"]); self.assertIn("Vela 0.10.15 (graphique dans le navigateur) : pas prêt", r["summary"])

    def test_demo_data_checked_by_sha(self):
        with mock.patch.object(components.shutil, "which", side_effect=lambda b: "/usr/bin/" + b):
            d = components.prepare_demo(self.root, runner=self.runner())
        self.assertFalse(d["ok"]); self.assertIn("differ from the reference", d["problem"])
        self.assertFalse((self.root / components.DEMO).exists())


if __name__ == "__main__":
    unittest.main()
