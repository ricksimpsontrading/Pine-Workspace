# SPDX-License-Identifier: Apache-2.0
"""Guided update of Vela (tools/pws_workspace/vela_guide.py): plan contents (changelog of the archive,
API check, bundle scan), refusals before any change, provenance recording, offline switch with a fake
npm, verified rollback points (two kept), restoration, page integrity and the menu entry. No network."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.pws_workspace import core, live, menu, pinets_guide, vela_guide as V

DTS_OK = """
declare class Vela { constructor(container: HTMLElement | string, options?: VelaOptions);
  registerEngine(language: string, engine: ScriptingEngine): this;
  addIndicator(source: string, options?: AddIndicatorOptions): IndicatorHandle;
  setMarket(next: MarketSwitch): Promise<void>; inspect(): SceneInspection; get renderer(): RendererControl; }
declare class RendererControl { screenshot(): string | null; onCrosshairMove(cb: (e: CrosshairEvent) => void): Unsubscribe; }
interface IndicatorHandle { updateCode(source: string): Promise<CodeUpdateResult>;
  on<K extends keyof IndicatorEventMap>(event: K, handler: (p: IndicatorEventMap[K]) => void): () => void; }
interface ScriptingEngine { prepare(source: string, instanceId: string): Promise<PreparedScript>;
  execute(req: ExecutionRequest, handlers: ExecutionHandlers): ExecutionSession; }
interface ExecutionHandlers { onModel(model: IndicatorModel): void; }
interface IndicatorModel { series: SeriesSpec[]; priceLines: PriceLine[]; }
interface MarketConfig { data?: OHLCV[]; }
"""


def _tree(root, version, bundle=b"var Vela=(function(exports){return exports;})({});", lic="Apache-2.0"):
    vv = Path(root) / "tools" / "vela_view"
    (vv / "page").mkdir(parents=True, exist_ok=True); (vv / "page" / "pws-view.js").write_text("// page\n")
    pkgdir = vv / "node_modules" / "@luxalgo" / "vela"
    shutil.rmtree(vv / "node_modules", ignore_errors=True)
    (pkgdir / "dist").mkdir(parents=True)
    (pkgdir / "package.json").write_text(json.dumps({"name": V.PKG, "version": version, "license": lic}))
    (pkgdir / "dist" / "vela.global.min.js").write_bytes(bundle)
    (pkgdir / "dist" / "index.d.ts").write_text(DTS_OK)
    integ = "sha512-" + hashlib.sha256(version.encode()).hexdigest()
    (vv / "package.json").write_text(json.dumps({"name": "pws-vela-view", "dependencies": {V.PKG: version}}))
    (vv / "package-lock.json").write_text(json.dumps({"packages": {"": {}, "node_modules/" + V.PKG: {
        "version": version, "integrity": integ, "license": lic}}}))
    return vv


class Pieces(unittest.TestCase):
    def test_changelog_sections_between_versions(self):
        text = "# Log\n## [0.11.0]\nnew\n## [0.10.14]\nfix b\n## [0.10.13]\nfix a\n"
        self.assertEqual([s["version"] for s in V.changelog_sections(text, "0.10.13", "0.11.0")], ["0.11.0", "0.10.14"])
        self.assertEqual(V.changelog_sections(text, "0.11.0", "0.11.0"), [])

    def test_api_check_ok_missing_and_ambiguous(self):
        d = Path(tempfile.mkdtemp())
        try:
            (d / "index.d.ts").write_text(DTS_OK)
            self.assertTrue(all(a["status"] == "ok" for a in V.api_check(d)))
            (d / "index.d.ts").write_text(DTS_OK.replace("screenshot(): string | null;", "screenshot(opts: X): Blob;")
                                          .replace("onModel(model: IndicatorModel): void;", ""))
            st = {a["api"]: a["status"] for a in V.api_check(d)}
            self.assertEqual((st["screenshot"], st["onModel"]), ("ambiguous", "missing"))
        finally:
            shutil.rmtree(d)

    def test_bundle_scan(self):
        s = V.bundle_scan(b"var Vela=(function(){fetch('https://api.example.com');new Worker('w.js')})()")
        self.assertTrue(s["starts_with_var_vela"])
        self.assertEqual((s["loaders"]["new Worker"], s["network_hosts"]), (1, ["https://api.example.com"]))


class Guide(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pws vela "))
        self.vv = _tree(self.root, "0.10.13", bundle=b"var Vela=1;// 0.10.13")
        self.work = Path(tempfile.mkdtemp(prefix="pws-vela-plan-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True); shutil.rmtree(self.work, ignore_errors=True)

    def _plan(self, **over):
        ident = V.identity(self.root)
        cand = self.work / "candidate"; _tree(cand.parent / "c", "0.10.14", bundle=b"var Vela=2;// 0.10.14")
        shutil.copytree(cand.parent / "c" / "tools" / "vela_view", cand, dirs_exist_ok=True)
        cident = V.identity(self.root, cand)
        plan = {"format": 1, "component": "vela", "kind": "update", "work_dir": str(self.work), "cache": str(self.work / "cache"),
                "current": {"version": "0.10.13", "package_sha256": ident["package_sha256"], "lock_sha256": ident["lock_sha256"],
                            "bundle_sha256": ident["bundle_sha256"]},
                "baseline_provenance": {"package": V.PKG, "pinned_version": "0.10.13", "bundle": {"sha256": ident["bundle_sha256"]}},
                "engine_guard": V._engine_guard(self.root),
                "target": {"version": "0.10.14", "registry_integrity": cident["lock_integrity"],
                           "bundle_sha256": cident["bundle_sha256"], "license": "Apache-2.0"},
                "candidate": {"dir": str(cand), "package_sha256": cident["package_sha256"], "lock_sha256": cident["lock_sha256"],
                              "lock_entries": cident["lock_entries"]},
                "license_changes": [], "license_accepted": [], "api": [], "probe_required": False, "blocked": False}
        plan.update(over)
        plan["plan_hash"] = pinets_guide._plan_hash(plan)
        f = self.work / ("plan-%d.json" % len(list(self.work.glob("plan-*.json")))); core.atomic_write_json(f, plan)
        return f, cand

    def _fake_npm(self, cand):
        def run(cmd, cwd=None, env=None, timeout=None):
            assert cmd[:3] == ["npm", "ci", "--offline"] and "--ignore-scripts" in cmd, cmd
            shutil.copytree(cand / "node_modules", Path(cwd) / "node_modules")
            return 0, "", ""
        return run

    def test_refusals_change_nothing(self):
        before = V.identity(self.root)
        cases = [("plan_hash", {}), ("blocked", {"blocked": True}), ("probe", {"probe_required": True}),
                 ("licence", {"license_changes": [{"package": "x", "version": "1", "from": "MIT", "to": "GPL-3.0"}]})]
        for name, over in cases:
            f, cand = self._plan(**over)
            if name == "plan_hash":
                p = json.loads(f.read_text()); p["target"]["version"] = "9.9.9"; f.write_text(json.dumps(p))
            r = V.apply(self.root, f, yes=True, lang="fr", npm_runner=self._fake_npm(cand))
            self.assertFalse(r["ok"], name); self.assertEqual(r["status"], "refused-before-mutation", name)
        f, cand = self._plan()
        self.assertFalse(V.apply(self.root, f, yes=False, lang="fr")["ok"])                  # no "Apply"
        self.assertEqual(V.identity(self.root), before)
        self.assertEqual(V.list_points(self.root), [])

    def test_update_offline_then_rollback_keeps_two_points(self):
        f, cand = self._plan()
        r = V.apply(self.root, f, yes=True, lang="fr", npm_runner=self._fake_npm(cand))
        self.assertTrue(r["ok"], r["problems"]); self.assertEqual(r["status"], "completed")
        ident = V.identity(self.root)
        self.assertEqual((ident["installed"], ident["bundle_sha256"]), ("0.10.14", hashlib.sha256(b"var Vela=2;// 0.10.14").hexdigest()))
        self.assertEqual(ident["provenance"]["previous"]["version"], "0.10.13")
        self.assertTrue(r["engine_guard_unchanged"])
        self.assertIn("aucune recalibration", r["summary"]["text"].lower())
        pts = V.list_points(self.root); self.assertEqual([(p["version"], p["usable"]) for p in pts], [("0.10.13", True)])
        rb = V.rollback(self.root, yes=True, lang="fr")
        self.assertTrue(rb["ok"], rb["problems"])
        ident = V.identity(self.root)
        self.assertEqual((ident["installed"], ident["bundle_sha256"]), ("0.10.13", hashlib.sha256(b"var Vela=1;// 0.10.13").hexdigest()))
        self.assertEqual(sorted(p["version"] for p in V.list_points(self.root)), ["0.10.13", "0.10.14"])
        for _ in range(2):                                                    # more points: only two are kept
            self.assertTrue(V._save_point(self.root, "extra")["ok"]); V._prune(self.root)
        self.assertEqual(len([p for p in V.list_points(self.root) if p["usable"]]), 2)

    def test_altered_point_is_never_restored(self):
        f, cand = self._plan()
        self.assertTrue(V.apply(self.root, f, yes=True, lang="fr", npm_runner=self._fake_npm(cand))["ok"])
        p = V.list_points(self.root)[0]
        (self.root / V.ROLLBACK_REL / p["name"] / V.BUNDLE_REL).write_bytes(b"tampered")
        r = V.rollback(self.root, yes=True, lang="fr")
        self.assertFalse(r["ok"]); self.assertEqual(V.identity(self.root)["installed"], "0.10.14")

    def test_record_provenance_plan(self):
        ident = V.identity(self.root)
        plan = {"format": 1, "component": "vela", "kind": "record-provenance", "work_dir": str(self.work), "cache": "",
                "current": {"version": "0.10.13", "package_sha256": ident["package_sha256"], "lock_sha256": ident["lock_sha256"],
                            "bundle_sha256": ident["bundle_sha256"]},
                "baseline_provenance": {"package": V.PKG, "pinned_version": "0.10.13",
                                        "bundle": {"path": V.BUNDLE_REL, "sha256": ident["bundle_sha256"]}},
                "engine_guard": V._engine_guard(self.root), "target": {"version": "0.10.13"}}
        plan["plan_hash"] = pinets_guide._plan_hash(plan)
        f = self.work / "rec.json"; core.atomic_write_json(f, plan)
        r = V.apply(self.root, f, yes=True, lang="en")
        self.assertTrue(r["ok"]); self.assertEqual(r["status"], "provenance-recorded")
        self.assertEqual(V.identity(self.root)["provenance"]["bundle"]["sha256"], ident["bundle_sha256"])


class PageIntegrity(unittest.TestCase):
    def test_expected_hashes_are_those_of_the_wrapped_function_sources(self):
        root = Path(__file__).resolve().parents[2]
        if live.vela_state(root) != "ready":
            self.skipTest("Vela not installed here")
        out = live.page_integrity(root, "fr")
        for kind in ("vela", "page"):
            text = Path(out["files"][kind]).read_text(encoding="utf-8")
            head = live.WRAP[kind][0]
            fn = text[len(head):text.rindex(";\n")]
            self.assertEqual(hashlib.sha256(fn.encode("utf-8")).hexdigest(), out[kind + "_fn_sha256"], kind)
        self.assertIn("INTEGRITY FAIL", live.LOADER_JS)
        self.assertIn("window.__PWS_VELA.toString()", live.LOADER_JS)

    def test_menu_offers_vela_only_where_installed(self):
        base = {"language": "fr", "products": []}
        def ids(st):
            out = []

            def walk(nodes):
                for n in nodes:
                    out.append(n.get("id"))
                    for scr in n.get("children") or []:
                        walk(scr)
            walk(menu.build_menu(st)["top"])
            return out
        self.assertIn("tools.vela", ids(dict(base, vela_state="ready")))
        self.assertNotIn("tools.vela", ids(dict(base, vela_state="absent")))


if __name__ == "__main__":
    unittest.main()
