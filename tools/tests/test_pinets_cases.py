# SPDX-License-Identifier: Apache-2.0
"""Tooling tests of the generic PineTS capability cases.

These tests check the MATERIAL of tools/tests/pinets_cases — manifest,
expected values, comparator, recorded observations. They must pass.

They deliberately assert NOTHING about what an engine does with a case: a
concordance, a divergence or an execution failure is a recorded result of a
capability probe (run_campaign.py), never a condition of this suite. In
particular no test requires a given syntax to fail: an upstream fix must be
recognizable as progress when a migration is studied.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.tests.pinets_cases import build_cases, cases_lib as lib, run_campaign

NODE = shutil.which("node")
PINETS = lib.PINE_EXEC / "node_modules" / "pinets" / "package.json"


def pts(values, t0=1000, step=10):
    return [{"t": t0 + i * step, "v": v} for i, v in enumerate(values)]


class TestCaseMaterial(unittest.TestCase):
    def setUp(self):
        self.manifest = lib.load_manifest()

    def test_manifest_files_exist_and_match_their_fingerprints(self):
        self.assertEqual(self.manifest["schema"], lib.MANIFEST_SCHEMA)
        ids = [c["id"] for c in self.manifest["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(ids)
        for case in self.manifest["cases"]:
            for key in ("source", "dataset", "expected", "config"):
                if key == "config" and key not in case:
                    continue
                path = lib.resolve(case[key])
                self.assertTrue(path.is_file(), case[key])
                self.assertEqual(lib.sha256_file(path), case[key + "_sha256"],
                                 case[key])

    def test_cases_are_generic_and_never_a_product(self):
        """No product name, path or constant; nothing under scripts/; no
        calibration artifact is created or modified by the cases."""
        for case in self.manifest["cases"]:
            self.assertTrue(case["source"].startswith("tools/tests/pinets_cases/sources/"))
            self.assertTrue(case["expected"].startswith("tools/tests/pinets_cases/expected/"))
            text = lib.resolve(case["source"]).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("//@version=6\n"), case["id"])
            for folder in ("scripts/",):
                self.assertNotIn(folder, case["source"] + case["dataset"])
        products = [p.name for p in (lib.REPO / "scripts").iterdir() if p.is_dir()] \
            if (lib.REPO / "scripts").is_dir() else []
        material = "".join(
            p.read_text(encoding="utf-8") for p in sorted(lib.HERE.rglob("*"))
            if p.is_file() and p.suffix in (".pine", ".py", ".md")
            or p.name == "cases.json").lower()
        for slug in products:
            self.assertNotIn(slug.lower(), material)

    def test_every_expected_series_states_its_provenance(self):
        for case in self.manifest["cases"]:
            doc = json.loads(lib.resolve(case["expected"]).read_text(encoding="utf-8"))
            self.assertEqual(doc["schema"], lib.EXPECTED_SCHEMA)
            self.assertEqual(doc["case"], case["id"])
            self.assertTrue(doc["series"], case["id"])
            for name, spec in doc["series"].items():
                where = "%s/%s" % (case["id"], name)
                self.assertIn(spec["status"], lib.SERIES_STATUSES, where)
                self.assertTrue(spec.get("provenance", "").strip(), where)
                self.assertTrue(("values" in spec) != ("variants" in spec), where)
                if spec["status"] == lib.EXPLORATION:
                    self.assertTrue(spec.get("missing_proof", "").strip(), where)
                    self.assertIn("variants", spec, where)
                else:
                    self.assertNotIn("missing_proof", spec, where)
            for item in doc["explorations"]:
                self.assertTrue(item["topic"].strip() and item["missing_proof"].strip())

    def test_expected_values_never_come_from_the_engine(self):
        """Static guard of the independence contract: the builder neither
        runs the runner nor imports the engine."""
        text = (lib.HERE / "build_cases.py").read_text(encoding="utf-8")
        for forbidden in ("runner.mjs", "run_campaign", "node_modules", "from 'pinets'",
                          'from "pinets"', "observations"):
            self.assertNotIn(forbidden, text)

    @unittest.skipUnless(NODE, "node is required by the canonical dataset serializer")
    def test_datasets_expected_and_manifest_are_reproducible(self):
        datasets = build_cases.build()
        generated = dict(datasets)
        generated.update(build_cases.build_expected_and_manifest(datasets))
        self.assertEqual(len(generated),
                         len(build_cases.DATASETS) + len(self.manifest["cases"]) + 1)
        for rel, text in sorted(generated.items()):
            self.assertEqual(lib.resolve(rel).read_text(encoding="utf-8"), text, rel)
        on_disk = sorted(str(p.relative_to(lib.REPO)) for folder in ("datasets", "expected")
                         for p in (lib.HERE / folder).iterdir() if p.is_file())
        self.assertEqual(on_disk, sorted(k for k in generated if not k.endswith("cases.json")),
                         "no orphan dataset or expected file")


class TestComparator(unittest.TestCase):
    def _expected(self, **series):
        return {"series": series}

    def test_exact_concordance(self):
        exp = self._expected(A={"status": lib.ESTABLISHED, "provenance": "x",
                                "values": pts([1.0, None, 3.0])})
        cmp_ = lib.compare_case(exp, {"plots": {"A": pts([1.0, None, 3.0])}})
        self.assertEqual(cmp_["series"]["A"]["outcome"], lib.CONCORDANT)
        self.assertEqual(lib.case_outcome(cmp_), lib.CASE_CONCORDANT)

    def test_tiny_float_gap_is_described_not_hidden(self):
        exp = self._expected(A={"status": lib.ESTABLISHED, "provenance": "x",
                                "values": pts([111.729833155, 2.0])})
        cmp_ = lib.compare_case(exp, {"plots": {"A": pts([111.729833156, 2.0])}})
        entry = cmp_["series"]["A"]
        self.assertEqual(entry["outcome"], lib.CLOSE)
        self.assertEqual(entry["detail"]["expected"]["differing_points"], 1)
        self.assertLessEqual(entry["detail"]["expected"]["largest_relative_gap"],
                             lib.RELATIVE_TOLERANCE)
        self.assertEqual(lib.case_outcome(cmp_), lib.CASE_CLOSE)

    def test_real_divergence_and_na_pattern_are_never_tolerated(self):
        exp = self._expected(A={"status": lib.ESTABLISHED, "provenance": "x",
                                "values": pts([1.0, 2.0])})
        for actual in ([1.0, 2.1], [1.0, None], [None, 2.0], [1.0, "2.0"], [1.0, True]):
            cmp_ = lib.compare_case(exp, {"plots": {"A": pts(actual)}})
            self.assertEqual(cmp_["series"]["A"]["outcome"], lib.DIVERGENT, actual)
            self.assertEqual(lib.case_outcome(cmp_), lib.CASE_DIVERGENT)
        for payload in ({"plots": {"A": pts([1.0])}},
                        {"plots": {"A": pts([1.0, 2.0], t0=5)}}):
            self.assertEqual(lib.compare_case(exp, payload)["series"]["A"]["outcome"],
                             lib.DIVERGENT)

    def test_missing_series_and_unclaimed_keys(self):
        exp = self._expected(A={"status": lib.ESTABLISHED, "provenance": "x",
                                "values": pts([1.0])})
        cmp_ = lib.compare_case(exp, {"plots": {"#1": pts([None])}})
        self.assertEqual(cmp_["series"]["A"]["outcome"], lib.MISSING)
        self.assertEqual(cmp_["unexpected_payload_keys"]["#1"]["all_null"], True)
        self.assertEqual(lib.case_outcome(cmp_), lib.CASE_DIVERGENT)
        for empty in (None, {}, {"plots": None}):
            self.assertEqual(lib.compare_case(exp, empty)["series"]["A"]["outcome"],
                             lib.MISSING)

    def test_documented_variants_name_the_one_observed(self):
        exp = self._expected(E={"status": lib.ESTABLISHED, "provenance": "x",
                                "variants": {"one": pts([1.0, 2.0]),
                                             "two": pts([None, 2.0])}})
        cmp_ = lib.compare_case(exp, {"plots": {"E": pts([None, 2.0])}})
        self.assertEqual(cmp_["series"]["E"]["outcome"], lib.CONCORDANT)
        self.assertEqual(cmp_["series"]["E"]["equals"], ["two"])

    def test_an_exploration_is_observed_and_never_judged(self):
        exp = self._expected(X={"status": lib.EXPLORATION, "provenance": "x",
                                "missing_proof": "y", "match": "title-and-suffixes",
                                "variants": {"candidate": pts([1.0])}})
        for actual in ([1.0], [9.0], [None]):
            cmp_ = lib.compare_case(exp, {"plots": {"X": pts(actual), "X#1": pts([1.0])}})
            self.assertEqual(cmp_["series"]["X"]["outcome"], lib.OBSERVED)
            self.assertEqual(sorted(cmp_["series"]["X"]["observed"]), ["X", "X#1"])
            self.assertEqual(lib.case_outcome(cmp_), lib.CASE_OBSERVED_ONLY)
        absent = lib.compare_case(exp, {"plots": {}})
        self.assertTrue(absent["series"]["X"]["observed_absent"])
        self.assertEqual(lib.case_outcome(absent), lib.CASE_OBSERVED_ONLY)


INITIAL_RECORD = "pinets-0.9.33.json"
INITIAL_RECORD_SHA256 = "e05b2158b38f0aec5086a3ddb84c5e815aa296013fc96850f456e44c5905a88b"


class TestRecordedObservations(unittest.TestCase):
    """A durable record describes ONE identified campaign on ITS perimeter.
    It is never required to cover fixtures added or changed afterwards."""

    def _records(self):
        files = sorted((lib.HERE / "observations").glob("*.json"))
        self.assertTrue(files)
        return [(p, lib.loads_strict(p.read_text(encoding="utf-8"))) for p in files]

    def test_the_initial_record_is_preserved(self):
        path = lib.HERE / "observations" / INITIAL_RECORD
        self.assertEqual(lib.sha256_file(path), INITIAL_RECORD_SHA256)

    def test_every_record_is_identified_and_internally_coherent(self):
        for path, doc in self._records():
            self.assertIn(doc["schema"], lib.OBSERVATION_SCHEMAS, path.name)
            self.assertEqual(len(doc["engine_identities"]), 1, path.name)
            identity = doc["engine_identities"][0]
            for key in ("pinets_version", "executor_fingerprint", "normalization_schema"):
                self.assertTrue(identity[key], key)
            self.assertIn(identity["pinets_version"], path.name)
            ids = [o["case"] for o in doc["observations"]]
            self.assertEqual(len(ids), len(set(ids)), path.name)
            self.assertEqual(sum(doc["counts"].values()), len(ids), path.name)
            for obs in doc["observations"]:
                self.assertIn(obs["outcome"], lib.CASE_OUTCOMES, obs["case"])
                for key in ("source_sha256", "dataset_sha256", "expected_sha256"):
                    self.assertTrue(lib.is_hex64(obs[key]), obs["case"])
                self.assertEqual(obs["pinets_version"], identity["pinets_version"])
                if obs["outcome"] == lib.CASE_EXECUTION_FAIL:
                    self.assertTrue(obs["error"], obs["case"])
                self.assertNotIn(obs["outcome"], lib.UNUSABLE_OUTCOMES,
                                 "an unusable campaign is never recorded")
            self.assertNotIn(str(lib.REPO), path.read_text(encoding="utf-8"),
                             "no machine path in a durable record")

    def test_a_campaign_record_states_its_own_perimeter(self):
        seen = 0
        for path, doc in self._records():
            if doc["schema"] != lib.OBSERVATION_SCHEMA_V2:
                continue
            seen += 1
            campaign = doc["campaign"]
            self.assertTrue(campaign["id"])
            self.assertRegex(campaign["observed_on"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertEqual(campaign["status"], lib.CAMPAIGN_COMPLETE, path.name)
            scope = {s["case"]: s for s in campaign["scope"]}
            self.assertEqual(sorted(scope), sorted(o["case"] for o in doc["observations"]))
            for obs in doc["observations"]:
                for key, value in scope[obs["case"]].items():
                    if key != "case":
                        self.assertEqual(obs[key], value, obs["case"])
            engine = campaign["engine"]
            self.assertEqual(engine["installed_pinets_version"],
                             doc["engine_identities"][0]["pinets_version"])
            self.assertTrue(lib.is_hex64(
                engine["files"]["node_modules/pinets/dist/pinets.min.es.js"]))
        return seen

    def test_a_record_is_not_required_to_cover_later_fixtures(self):
        """The initial record predates fixtures added later: it stays valid,
        and what it does not cover is simply outside its perimeter."""
        manifest = {c["id"]: c for c in lib.load_manifest()["cases"]}
        doc = lib.loads_strict((lib.HERE / "observations" / INITIAL_RECORD)
                               .read_text(encoding="utf-8"))
        observed = {o["case"]: o for o in doc["observations"]}
        later = sorted(set(manifest) - set(observed))
        self.assertTrue(later, "fixtures were added after the initial record")
        self.assertTrue(all(c.startswith(("P5-", "P6-")) for c in later), later)
        # the record says nothing about them, and nothing is asked of it
        self.assertEqual(sum(doc["counts"].values()), len(observed))
        from tools.tests.pinets_cases import compare_campaigns as cc
        current = {"engine_identities": doc["engine_identities"],
                   "observations": [dict(observed[c]) for c in observed] +
                   [{"case": c, "outcome": lib.CASE_CONCORDANT} for c in later]}
        result = cc.compare_records(doc, current)
        self.assertEqual({result["cases"][c]["classification"] for c in later},
                         {cc.ONLY_IN_B})
        self.assertEqual({result["cases"][c]["classification"] for c in observed},
                         {cc.UNCHANGED})


FAKE_RUNNER = r"""
// Test double of an executor: writes the report its MODE asks for.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { payloadSha256 } from './normalize.mjs';
const HERE = dirname(fileURLToPath(import.meta.url));
const mode = readFileSync(join(HERE, 'MODE'), 'utf8').trim();
const opts = {};
const rest = process.argv.slice(3);
for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = rest[i + 1];
const sha = p => createHash('sha256').update(readFileSync(p)).digest('hex');
const counter = join(HERE, 'COUNTER');
const n = existsSync(counter) ? Number(readFileSync(counter, 'utf8')) + 1 : 1;
writeFileSync(counter, String(n));
const expected = JSON.parse(readFileSync(join(HERE, 'EXPECTED'), 'utf8'));
const plots = {};
for (const [k, s] of Object.entries(expected.series)) {
  plots[k] = (s.values ?? Object.values(s.variants)[0]).map(p => ({ t: p.t, v: p.v }));
}
const first = Object.keys(plots)[0];
const normalized = { schema: 'pws-pinets-norm-v2', plots, alerts: [], warnings: [],
                     internal_keys_present: [] };
const requested = opts.config ? JSON.parse(readFileSync(opts.config, 'utf8')) : {};
const report = {
  schema: 'pws-pinets-run-v1', run_id: 'pexec-fake-' + n,
  source: opts.source, source_sha256: sha(opts.source),
  dataset: opts.dataset, dataset_sha256: sha(opts.dataset),
  configuration: requested, pinets_version: '9.9.9',
  executor_fingerprint: 'a'.repeat(64), normalization_schema: 'pws-pinets-norm-v2',
  capabilities_used: {}, unclassified_tokens: [],
  execution_status: 'PINETS_EXECUTION_PASS', error: null,
  normalized, normalized_payload_sha256: null,
};
let code = 0;
let text = null;
if (mode === 'no-report') process.exit(0);
if (mode === 'infrastructure') { console.error('disk on fire'); process.exit(5); }
if (mode === 'garbage') { writeFileSync(opts.out, '{not json'); process.exit(0); }
if (mode === 'engine-fail') {
  report.execution_status = 'PINETS_EXECUTION_FAIL';
  report.error = { message: 'Failed to transpile: fake' };
  report.normalized = null; code = 1;
}
if (mode === 'fail-without-message') {
  report.execution_status = 'PINETS_EXECUTION_FAIL';
  report.error = null; report.normalized = null; code = 1;
}
if (mode === 'wrong-source') report.source_sha256 = 'b'.repeat(64);
if (mode === 'config-ignored') report.configuration = {};
if (mode === 'config-invented') report.configuration = { inputs: { Length: 99 } };
if (mode === 'config-other-value') report.configuration = { inputs: { Length: 3, Multiplier: 0.75 } };
if (mode === 'config-partial') report.configuration = { inputs: { Length: 3 } };
if (mode === 'config-missing') delete report.configuration;
if (mode === 'config-null') report.configuration = null;
if (mode === 'config-string') report.configuration = '{}';
if (mode === 'config-list') report.configuration = [];
if (mode === 'config-drift' && n === 2) report.configuration = {};
if (mode === 'wrong-version') report.pinets_version = '0.0.1';
if (mode === 'unknown-status') report.execution_status = 'MAYBE';
if (mode === 'wrong-schema') report.schema = 'something-else';
if (mode === 'identity-drift' && n === 2) report.executor_fingerprint = 'c'.repeat(64);
if (mode === 'same-run-id') report.run_id = 'pexec-fake-constant';
if (mode === 'boolean') normalized.plots[first][0].v = true;
if (mode === 'string') normalized.plots[first][0].v = '3';
if (mode === 'not-deterministic' && n === 2) normalized.plots[first][0].v = 123456;
if (mode === 'flaky' && n === 2) {
  report.execution_status = 'PINETS_EXECUTION_FAIL';
  report.error = { message: 'sometimes' }; report.normalized = null; code = 1;
}
if (report.normalized) report.normalized_payload_sha256 = payloadSha256(report.normalized);
if (mode === 'tampered-payload') normalized.plots[first][0].v = 42;
text = JSON.stringify(report, null, 2);
if (mode === 'non-finite') text = text.replace('"v": 3', '"v": NaN');
writeFileSync(opts.out, text + '\n');
process.exit(code);
"""

CASE = "P1-untyped-counter"
WITH_CONFIG = "P6-inputs-overridden"


@unittest.skipUnless(NODE, "node is required")
class TestCampaignLauncher(unittest.TestCase):
    """Guarantees of the launcher about ITSELF, exercised with a test double
    of an executor. None of these tests is about what a real engine does."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.fake = self.base / "fake executor"
        (self.fake / "node_modules" / "pinets" / "dist").mkdir(parents=True)
        (self.fake / "runner.mjs").write_text(FAKE_RUNNER, encoding="utf-8")
        shutil.copy(str(lib.PINE_EXEC / "normalize.mjs"), str(self.fake / "normalize.mjs"))
        (self.fake / "node_modules" / "pinets" / "package.json").write_text(
            json.dumps({"name": "pinets", "version": "9.9.9"}), encoding="utf-8")
        (self.fake / "node_modules" / "pinets" / "dist" / "pinets.min.es.js") \
            .write_text("// fake engine\n", encoding="utf-8")
        case = next(c for c in lib.load_manifest()["cases"] if c["id"] == CASE)
        shutil.copy(str(lib.resolve(case["expected"])), str(self.fake / "EXPECTED"))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, mode, out_name="out", record=True, cases=CASE):
        (self.fake / "MODE").write_text(mode, encoding="utf-8")
        first = cases.split(",")[0]
        known = {c["id"]: c for c in lib.load_manifest()["cases"]}
        if first in known:
            shutil.copy(str(lib.resolve(known[first]["expected"])),
                        str(self.fake / "EXPECTED"))
        counter = self.fake / "COUNTER"
        if counter.exists():
            counter.unlink()
        out = self.base / out_name
        record_path = self.base / ("record-%s.json" % out_name)
        argv = ["--out-dir", str(out), "--campaign-id", "test-" + mode,
                "--observed-on", "2000-01-01", "--executor", str(self.fake),
                "--cases", cases]
        if record:
            argv += ["--observations", str(record_path)]
        import contextlib
        import io
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_campaign.main(argv)
        doc = None
        if (out / "campaign.json").is_file():
            doc = json.loads((out / "campaign.json").read_text(encoding="utf-8"))
        return code, doc, record_path, stderr.getvalue()

    def _assert_unusable(self, mode, outcome, needle, cases=CASE):
        code, doc, record, _ = self._run(mode, out_name="unusable-%s-%s" % (mode, cases),
                                         cases=cases)
        self.assertEqual(code, 1, mode)
        self.assertEqual(doc["campaign"]["status"], lib.CAMPAIGN_UNUSABLE, mode)
        self.assertTrue(doc["campaign"]["unusable_reasons"], mode)
        obs = doc["observations"][0]
        self.assertEqual(obs["outcome"], outcome, mode)
        problems = " | ".join(obs.get("harness_problems") or obs.get("payload_problems"))
        self.assertIn(needle, problems, mode)
        self.assertNotIn("error_reported_by", obs)
        self.assertFalse(record.exists(), "an unusable campaign is never recorded")

    def test_a_well_formed_campaign_is_complete_and_recorded(self):
        code, doc, record, _ = self._run("ok")
        self.assertEqual(code, 0)
        self.assertEqual(doc["campaign"]["status"], lib.CAMPAIGN_COMPLETE)
        obs = doc["observations"][0]
        self.assertEqual(obs["outcome"], lib.CASE_CONCORDANT)
        self.assertTrue(obs["deterministic"])
        self.assertEqual(obs["execution_status"], [lib.EXECUTION_PASS] * 2)
        self.assertEqual([s["case"] for s in doc["campaign"]["scope"]], [CASE])
        self.assertTrue(record.is_file())
        self.assertNotIn(str(self.base), record.read_text(encoding="utf-8"))

    def test_an_earlier_report_can_never_serve_a_new_attempt(self):
        code, _, _, _ = self._run("ok", out_name="first")
        self.assertEqual(code, 0)
        # same directory again: refused before anything runs
        code, _, _, err = self._run("no-report", out_name="first", record=False)
        self.assertEqual(code, 2)
        self.assertIn("not empty", err)
        # a stale report planted in a new directory is refused as well
        stale = self.base / "planted"
        stale.mkdir()
        shutil.copy(str(self.base / "first" / (CASE + ".run1.json")),
                    str(stale / (CASE + ".run1.json")))
        code, _, _, err = self._run("no-report", out_name="planted", record=False)
        self.assertEqual(code, 2)
        self.assertIn("not empty", err)
        # and an engine that writes nothing in a fresh directory is a
        # launcher failure, not a result
        self._assert_unusable("no-report", lib.CASE_HARNESS_FAILURE,
                              "no run report produced")

    def test_engine_reported_failure_is_a_result_of_a_complete_campaign(self):
        code, doc, record, _ = self._run("engine-fail", out_name="engine-fail")
        self.assertEqual(code, 0)
        self.assertEqual(doc["campaign"]["status"], lib.CAMPAIGN_COMPLETE)
        obs = doc["observations"][0]
        self.assertEqual(obs["outcome"], lib.CASE_EXECUTION_FAIL)
        self.assertEqual(obs["error_reported_by"], "engine")
        self.assertEqual(obs["error"], "Failed to transpile: fake")
        self.assertTrue(record.is_file())

    def test_launcher_failures_are_never_engine_results(self):
        for mode, needle in (("infrastructure", "launcher exit code 5"),
                             ("garbage", "unreadable or invalid"),
                             ("fail-without-message", "without an error message"),
                             ("unknown-status", "is not admitted"),
                             ("wrong-schema", "run report schema")):
            with self.subTest(mode=mode):
                self._assert_unusable(mode, lib.CASE_HARNESS_FAILURE, needle)

    def test_fingerprints_and_engine_identity_are_checked(self):
        for mode, needle in (("wrong-source", "another source fingerprint"),
                             ("wrong-version", "differs from the installed engine"),
                             ("identity-drift", "identity differs between the two runs"),
                             ("same-run-id", "same run_id"),
                             ("tampered-payload", "does not match the payload")):
            with self.subTest(mode=mode):
                self._assert_unusable(mode, lib.CASE_HARNESS_FAILURE, needle)

    def test_declared_configuration_must_equal_the_requested_one(self):
        """External verification: a report declaring {} while inputs were
        requested was accepted as concordant and deterministic."""
        code, doc, record, _ = self._run("ok", out_name="config-ok", cases=WITH_CONFIG)
        self.assertEqual(code, 0)
        self.assertEqual(doc["observations"][0]["outcome"], lib.CASE_CONCORDANT)
        self.assertTrue(doc["observations"][0]["deterministic"])
        self.assertTrue(record.is_file())
        for mode, needle in (("config-ignored", "different from the one requested"),
                             ("config-other-value", "different from the one requested"),
                             ("config-partial", "different from the one requested"),
                             ("config-drift", "run 2: run report declares a configuration"),
                             ("config-missing", "declares no configuration"),
                             ("config-null", "configuration is malformed"),
                             ("config-string", "configuration is malformed"),
                             ("config-list", "configuration is malformed")):
            with self.subTest(mode=mode):
                self._assert_unusable(mode, lib.CASE_HARNESS_FAILURE, needle,
                                      cases=WITH_CONFIG)

    def test_default_configuration_is_the_empty_object(self):
        """A case without a configuration file requests {}: a report that
        declares inputs nobody asked for is refused as well."""
        code, doc, _, _ = self._run("ok", out_name="default-ok")
        self.assertEqual(code, 0)
        for mode, needle in (("config-invented", "different from the one requested"),
                             ("config-missing", "declares no configuration"),
                             ("config-null", "configuration is malformed")):
            with self.subTest(mode=mode):
                self._assert_unusable(mode, lib.CASE_HARNESS_FAILURE, needle)

    def test_a_malformed_configuration_file_is_a_problem_of_the_attempt(self):
        from unittest import mock
        manifest = lib.load_manifest()
        bad = self.base / "bad config.json"
        bad.write_text("[1, 2]", encoding="utf-8")
        for case in manifest["cases"]:
            if case["id"] == WITH_CONFIG:
                case["config"] = str(bad)
                case["config_sha256"] = lib.sha256_file(bad)
        with mock.patch.object(lib, "load_manifest", return_value=manifest), \
                mock.patch.object(lib, "resolve", side_effect=lambda rel: (
                    Path(rel) if Path(rel).is_absolute() else lib.REPO / rel)):
            self._assert_unusable("ok", lib.CASE_HARNESS_FAILURE,
                                  "requested configuration unreadable",
                                  cases=WITH_CONFIG)

    def test_material_that_differs_from_the_manifest_stops_the_campaign(self):
        from unittest import mock
        manifest = lib.load_manifest()
        for case in manifest["cases"]:
            if case["id"] == CASE:
                case["source_sha256"] = "0" * 64
        with mock.patch.object(lib, "load_manifest", return_value=manifest):
            code, doc, record, err = self._run("ok", out_name="material")
        self.assertEqual(code, 2)
        self.assertIsNone(doc)
        self.assertIn("does not match the manifest", err)
        self.assertFalse(record.exists())
        code, _, _, err = self._run("ok", out_name="unknown", cases="No-such-case")
        self.assertEqual(code, 2)
        self.assertIn("unknown case", err)

    def test_booleans_and_non_finite_values_are_rejected(self):
        self._assert_unusable("boolean", lib.CASE_INVALID_PAYLOAD,
                              "boolean True in place of a number")
        self._assert_unusable("string", lib.CASE_INVALID_PAYLOAD,
                              "str in place of a number")
        self._assert_unusable("non-finite", lib.CASE_HARNESS_FAILURE,
                              "unreadable or invalid")

    def test_determinism_is_stated_only_on_two_valid_executions(self):
        code, doc, _, _ = self._run("not-deterministic", out_name="not-deterministic")
        self.assertEqual(code, 0)
        obs = doc["observations"][0]
        self.assertEqual(obs["outcome"], lib.CASE_NOT_DETERMINISTIC)
        self.assertFalse(obs["deterministic"])
        code, doc, _, _ = self._run("flaky", out_name="flaky")
        self.assertEqual(doc["observations"][0]["outcome"], lib.CASE_NOT_DETERMINISTIC)
        self.assertEqual(doc["observations"][0]["execution_status"],
                         [lib.EXECUTION_PASS, lib.EXECUTION_FAIL])

    def test_a_durable_record_is_never_overwritten(self):
        code, _, record, _ = self._run("ok", out_name="one")
        self.assertEqual(code, 0)
        before = record.read_bytes()
        target = self.base / "record-two.json"
        shutil.copy(str(record), str(target))
        code, _, _, err = self._run("engine-fail", out_name="two")
        self.assertEqual(code, 2)
        self.assertIn("never overwritten", err)
        self.assertEqual(target.read_bytes(), before)


class TestPayloadContract(unittest.TestCase):
    def test_valid_payload(self):
        self.assertEqual(lib.payload_problems(
            {"plots": {"A": pts([1, 2.5, None, 0, -3.0])}, "alerts": [], "warnings": []}), [])

    def test_rejected_values(self):
        for bad in (True, False, float("nan"), float("inf"), float("-inf"), "3", [1], {}):
            problems = lib.payload_problems({"plots": {"A": pts([1.0, bad])}})
            self.assertTrue(problems, repr(bad))
        for payload in (None, {}, {"plots": []}, {"plots": {"A": 3}},
                        {"plots": {"A": [{"t": 1}]}},
                        {"plots": {"A": [{"t": True, "v": 1}]}},
                        {"plots": {"A": [{"t": 1.5, "v": 1}]}},
                        {"plots": {}, "alerts": 3}):
            self.assertTrue(lib.payload_problems(payload), repr(payload))

    def test_strict_json_refuses_non_finite_tokens(self):
        for text in ('{"v": NaN}', '{"v": Infinity}', '{"v": -Infinity}'):
            with self.assertRaises(ValueError):
                lib.loads_strict(text)
        self.assertEqual(lib.loads_strict('{"v": 1.5}'), {"v": 1.5})

    def test_expected_documents_hold_only_finite_numbers_or_null(self):
        for case in lib.load_manifest()["cases"]:
            doc = lib.loads_strict(lib.resolve(case["expected"]).read_text(encoding="utf-8"))
            for name, spec in doc["series"].items():
                for label, values in (spec.get("variants") or
                                      {"values": spec.get("values")}).items():
                    self.assertEqual(lib.payload_problems({"plots": {name: values}}), [],
                                     "%s/%s/%s" % (case["id"], name, label))


class TestCampaignComparison(unittest.TestCase):
    def _obs(self, **over):
        base = {"case": "X", "source_sha256": "s", "dataset_sha256": "d",
                "expected_sha256": "e", "outcome": lib.CASE_CONCORDANT,
                "execution_status": [lib.EXECUTION_PASS, lib.EXECUTION_PASS],
                "normalized_payload_sha256": "p", "deterministic": True,
                "series": {"A": {"status": lib.ESTABLISHED, "outcome": lib.CONCORDANT,
                                 "equals": ["expected"]}}}
        base.update(over)
        return base

    def test_classification(self):
        from tools.tests.pinets_cases import compare_campaigns as cc
        a = self._obs()
        self.assertEqual(cc.compare_case(a, self._obs())["classification"], cc.UNCHANGED)
        # the initial record stored the status as a single string
        legacy = self._obs(execution_status=lib.EXECUTION_PASS)
        self.assertEqual(cc.compare_case(legacy, a)["classification"], cc.UNCHANGED)
        failed = self._obs(outcome=lib.CASE_EXECUTION_FAIL, error="boom", series=None,
                           execution_status=[lib.EXECUTION_FAIL] * 2,
                           normalized_payload_sha256=None, deterministic=None)
        self.assertEqual(cc.compare_case(failed, a)["classification"], cc.PROGRESS)
        self.assertEqual(cc.compare_case(a, failed)["classification"], cc.REGRESSION)
        other_error = dict(failed, error="another message")
        self.assertEqual(cc.compare_case(failed, other_error)["classification"], cc.CHANGED)
        moved = self._obs(normalized_payload_sha256="q")
        self.assertEqual(cc.compare_case(a, moved)["classification"], cc.CHANGED)
        changed_fixture = self._obs(expected_sha256="other")
        self.assertEqual(cc.compare_case(a, changed_fixture)["classification"],
                         cc.NOT_COMPARABLE)
        unusable = self._obs(outcome=lib.CASE_HARNESS_FAILURE)
        self.assertEqual(cc.compare_case(a, unusable)["classification"], cc.CHANGED)

    def test_perimeters_need_not_be_equal(self):
        from tools.tests.pinets_cases import compare_campaigns as cc
        a = {"engine_identities": [1], "observations": [self._obs(), self._obs(case="Y")]}
        b = {"engine_identities": [1], "observations": [self._obs(), self._obs(case="Z")]}
        result = cc.compare_records(a, b)
        self.assertTrue(result["same_engine"])
        self.assertEqual({k: v["classification"] for k, v in result["cases"].items()},
                         {"X": cc.UNCHANGED, "Y": cc.ONLY_IN_A, "Z": cc.ONLY_IN_B})


@unittest.skipUnless(NODE and PINETS.is_file(), "PineTS dependency not installed")
class TestCampaignOnTheActiveExecutor(unittest.TestCase):
    def test_the_launcher_classifies_a_case_whatever_the_engine_does(self):
        before = {p: lib.sha256_file(p) for folder in ("sources", "expected", "datasets")
                  for p in (lib.HERE / folder).iterdir()}
        with tempfile.TemporaryDirectory() as tmp:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                code = run_campaign.main([
                    "--out-dir", str(Path(tmp) / "out dir"), "--campaign-id", "smoke",
                    "--observed-on", "2000-01-01",
                    "--cases", "P1-typed-counter,P1-untyped-counter"])
            doc = json.loads((Path(tmp) / "out dir" / "campaign.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(doc["campaign"]["status"], lib.CAMPAIGN_COMPLETE)
        self.assertEqual(len(doc["observations"]), 2)
        for obs in doc["observations"]:
            self.assertIn(obs["outcome"], lib.CASE_OUTCOMES)
            self.assertNotIn(obs["outcome"], lib.UNUSABLE_OUTCOMES)
        self.assertEqual({p: lib.sha256_file(p) for p in before}, before,
                         "a probe never rewrites a case")


if __name__ == "__main__":
    unittest.main()
