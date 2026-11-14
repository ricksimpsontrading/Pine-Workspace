# SPDX-License-Identifier: Apache-2.0
"""Standard INDEX generation and freshness (spec sections 12, 61.3)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import core, standard
from tools.tests import helpers

MINI_MASTER = """# HOLDER EXAMPLE TRADING
# MASTER TEST

## 0. MISSION

Contenu.

## 1. STATUTS

### 1.1 OBLIGATOIRE

Contenu.

```text
## fake heading inside a fence — must be ignored
```

## 2. CLASSES
"""


class TestStandard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        master = self.root / core.STANDARD_REL
        master.parent.mkdir(parents=True, exist_ok=True)
        master.write_text(MINI_MASTER, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_headings_parsed_fences_ignored(self):
        headings = standard.parse_headings(MINI_MASTER)
        titles = [t for _, t, _ in headings]
        self.assertIn("0. MISSION", titles)
        self.assertIn("1.1 OBLIGATOIRE", titles)
        self.assertNotIn("fake heading inside a fence — must be ignored", titles)

    def test_index_generation_and_current(self):
        res = standard.generate_index(self.root, today="2026-09-04")
        self.assertGreater(res["headings"], 3)
        status = standard.standard_status(self.root)
        self.assertEqual(status["index"], "CURRENT")

    def test_index_stale_after_master_edit(self):
        standard.generate_index(self.root, today="2026-09-04")
        master = self.root / core.STANDARD_REL
        master.write_text(MINI_MASTER + "\n## 3. NOUVEAU\n", encoding="utf-8")
        status = standard.standard_status(self.root)
        self.assertEqual(status["index"], "STALE")

    def test_traceability_freshness(self):
        status = standard.standard_status(self.root)
        self.assertEqual(status["traceability"], "MISSING")
        sha = core.sha256_file(self.root / core.STANDARD_REL)
        (self.root / core.TRACEABILITY_REL).write_text(
            "# T\nSHA-256 %s\n" % sha, encoding="utf-8")
        status = standard.standard_status(self.root)
        self.assertEqual(status["traceability"], "CURRENT")

    def test_missing_master_reported(self):
        (self.root / core.STANDARD_REL).unlink()
        status = standard.standard_status(self.root)
        self.assertFalse(status["master_present"])


if __name__ == "__main__":
    unittest.main()
