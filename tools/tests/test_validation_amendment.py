# SPDX-License-Identifier: Apache-2.0
"""Run-report contract amendment of 2026-11-06: a not-run / n-a verdict may
carry a null author (no observation took place), never an invented one."""
import unittest

from tools.pws_workspace import validation
from tools.tests import helpers

SHA = "a" * 64


class TestNotRunAuthor(unittest.TestCase):
    def test_not_run_with_null_author_is_valid(self):
        report = helpers.full_run_report("run-1", SHA, status="partial")
        report["results"]["runtime"] = {"verdict": "not-run", "observed_by": None,
                                        "at": "2026-09-05T10:00:00Z",
                                        "observation": "blocked by the compilation failure"}
        self.assertEqual(validation.validate_run_report(report), [])

    def test_not_run_still_needs_observation_and_timestamp(self):
        report = helpers.full_run_report("run-1", SHA, status="partial")
        report["results"]["runtime"] = {"verdict": "not-run", "observed_by": None,
                                        "at": "2026-09-05T10:00:00Z", "observation": " "}
        self.assertTrue(validation.validate_run_report(report))
        report["results"]["runtime"] = {"verdict": "not-run", "observed_by": None,
                                        "at": None, "observation": "blocked"}
        self.assertTrue(validation.validate_run_report(report))

    def test_passed_and_failed_still_need_an_author(self):
        for verdict, status in (("passed", "passed"), ("failed", "failed")):
            report = helpers.full_run_report("run-1", SHA, status=status)
            report["results"]["compilation"]["observed_by"] = None
            problems = validation.validate_run_report(report)
            self.assertTrue(problems, verdict)
            self.assertIn("observed_by", problems[0])

    def test_n_a_with_null_author_is_valid(self):
        report = helpers.full_run_report("run-1", SHA, status="passed")
        report["matrix"].append({"id": "mtf", "test": "mtf", "applicable": False})
        report["results"]["mtf"] = {"verdict": "n-a", "observed_by": None,
                                    "at": "2026-09-05T10:00:00Z",
                                    "observation": "no MTF logic in this script"}
        self.assertEqual(validation.validate_run_report(report), [])


if __name__ == "__main__":
    unittest.main()
