# SPDX-License-Identifier: Apache-2.0
"""Guard parsers: parser uncertainty is NEVER a violation (spec sections 38-39)."""
import tempfile
import unittest
from pathlib import Path

from tools.pws_workspace import guard
from tools.tests import helpers


def statuses(findings):
    return {f["check"]: f["status"] for f in findings}


def write_source(root, text, name="Guard Case.pine"):
    p = root / name
    p.write_text(text, encoding="utf-8")
    return p


class TestShorttitle(unittest.TestCase):
    def test_real_shorttitle_blocking(self):
        self.assertEqual(guard.find_shorttitle('indicator("X", shorttitle="Y")'), [1])

    def test_short_title_variant(self):
        self.assertEqual(guard.find_shorttitle('indicator("X", short_title="Y")'), [1])

    def test_in_comment_ignored(self):
        self.assertEqual(guard.find_shorttitle("// never use shorttitle= here"), [])

    def test_in_string_ignored(self):
        self.assertEqual(guard.find_shorttitle('msg = "shorttitle= is forbidden"'), [])

    def test_after_code_comment_ignored(self):
        self.assertEqual(guard.find_shorttitle("x = 1  // shorttitle=foo"), [])

    def test_variable_named_shorttitle_not_flagged(self):
        """Audit F7a: a variable merely named shorttitle is legal Pine."""
        self.assertEqual(guard.find_shorttitle('shorttitle = "ma variable"'), [])
        self.assertEqual(guard.find_shorttitle("var string shorttitle = na"), [])

    def test_comparison_not_flagged(self):
        self.assertEqual(guard.find_shorttitle("cond = shorttitle == other"), [])

    def test_named_argument_multiline_flagged(self):
        src = 'indicator("X",\n     shorttitle="Y")'
        self.assertEqual(guard.find_shorttitle(src), [2])

    def test_named_argument_after_paren_flagged(self):
        self.assertEqual(guard.find_shorttitle('indicator(shorttitle="Y")'), [1])


class TestShorttitlePolicy(unittest.TestCase):
    """Adversarial review 2026-09-05: positional shorttitle detection and
    declaration-scoped named detection."""

    def _statuses(self, body):
        src = helpers.FREE_HEADER + body
        return {f["check"]: (f["status"], f["detail"])
                for f in guard.check_source(_write_tmp(self, src))}

    def test_positional_shorttitle_blocking(self):
        st = self._statuses('indicator("My Long Title", "SHRT")\nplot(close)\n')
        self.assertEqual(st["no-shorttitle"][0], "BLOCKING")
        self.assertIn("positional", st["no-shorttitle"][1])

    def test_positional_shorttitle_strategy_blocking(self):
        st = self._statuses('strategy("My Strategy", "S")\nplot(close)\n')
        self.assertEqual(st["no-shorttitle"][0], "BLOCKING")

    def test_second_named_argument_ok(self):
        st = self._statuses('indicator("Title", overlay=true)\nplot(close)\n')
        self.assertEqual(st["no-shorttitle"][0], "OK")

    def test_non_literal_second_positional_unverifiable(self):
        st = self._statuses('var t = "x"\nindicator("Title", t)\nplot(close)\n')
        self.assertEqual(st["no-shorttitle"][0], "UNVERIFIABLE")

    def test_named_in_declaration_blocking(self):
        st = self._statuses('indicator("Title",\n     shorttitle="S")\nplot(close)\n')
        self.assertEqual(st["no-shorttitle"][0], "BLOCKING")

    def test_named_outside_declaration_warning_only(self):
        st = self._statuses('indicator("Title")\n'
                            'f(shorttitle = 10) => shorttitle * 2\n'
                            'plot(f(close))\n')
        self.assertEqual(st["no-shorttitle"][0], "OK")
        self.assertEqual(st["shorttitle-outside-declaration"][0], "WARNING")

    def test_library_has_no_positional_shorttitle(self):
        st = self._statuses('library("MyLib", true)\n')
        self.assertEqual(st["no-shorttitle"][0], "OK")


def _write_tmp(case, text):
    import tempfile as _tf
    from pathlib import Path as _P
    d = getattr(case, "_tmpdir", None)
    if d is None:
        case._tmpdir = _tf.TemporaryDirectory()
        case.addCleanup(case._tmpdir.cleanup)
    p = _P(case._tmpdir.name) / "Case Source.pine"
    p.write_text(text, encoding="utf-8")
    return p


class TestGuardProductRobustness(unittest.TestCase):
    """Adversarial review: guard_product must diagnose, never crash."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_symlinked_product_root_refused_without_reading(self):
        """Targeted review 2026-09-06: guard never reads through a symlinked
        product root."""
        import os
        outside = self.root / "outside prod"
        outside.mkdir()
        (outside / "SCRIPT.json").write_text("{}", encoding="utf-8")
        link = self.root / "linked prod"
        os.symlink(outside, link)
        findings = guard.guard_product(link)
        self.assertEqual(findings[0]["check"], "product-root")
        self.assertEqual(findings[0]["status"], "BLOCKING")

    def test_non_object_manifest_blocking(self):
        pdir = self.root / "prod"
        pdir.mkdir()
        (pdir / "SCRIPT.json").write_text("[]", encoding="utf-8")
        findings = guard.guard_product(pdir)
        st = {f["check"]: f["status"] for f in findings}
        self.assertEqual(st["manifest"], "BLOCKING")

    def test_wrong_typed_fields_no_crash(self):
        pdir = self.root / "prod2"
        pdir.mkdir()
        (pdir / "SCRIPT.json").write_text(
            '{"source": [], "distribution": 42}', encoding="utf-8")
        findings = guard.guard_product(pdir)
        st = {f["check"]: f["status"] for f in findings}
        self.assertEqual(st["source-exists"], "BLOCKING")

    def test_version_echo_ignores_escaping_symlink(self):
        """The version-echo sweep never follows symlinks outside the product
        root."""
        import os
        outside = self.root / "outside NOTES.md"
        outside.write_text("version 1.0.0 mentioned here", encoding="utf-8")
        pdir = self.root / "prod3"
        pdir.mkdir()
        src = pdir / "S.pine"
        src.write_text(helpers.FREE_HEADER + helpers.MINIMAL_BODY, encoding="utf-8")
        os.symlink(outside, pdir / "NOTES.md")
        findings = guard.check_source(src, "free-open-source", pdir)
        st = {f["check"]: f["status"] for f in findings}
        self.assertEqual(st["version-only-in-source"], "OK")


class TestTitleExtraction(unittest.TestCase):
    def test_simple_title(self):
        st, title = guard.extract_title('//@version=6\nindicator("My Indicator")\n')
        self.assertEqual((st, title), ("EXTRACTED", "My Indicator"))

    def test_multiline_title(self):
        src = '//@version=6\nindicator(\n     title="Wrapped Title",\n     overlay=true)\n'
        st, title = guard.extract_title(src)
        self.assertEqual((st, title), ("EXTRACTED", "Wrapped Title"))

    def test_non_literal_title_not_blocking(self):
        src = '//@version=6\nvar t = "x"\nindicator(t)\n'
        st, _ = guard.extract_title(src)
        self.assertEqual(st, "NOT_EXTRACTABLE")

    def test_comment_inside_declaration_ignored(self):
        """Audit F7b: commented text can never masquerade as the title."""
        src = ('//@version=6\n'
               'indicator(\n'
               '     "Okay", // title="Echec"\n'
               '     overlay=true)\n')
        st, title = guard.extract_title(src)
        self.assertEqual((st, title), ("EXTRACTED", "Okay"))

    def test_comment_only_title_not_extracted_as_real(self):
        src = ('//@version=6\n'
               'indicator(\n'
               '     someVar, // title="Fake"\n'
               '     overlay=true)\n')
        st, _ = guard.extract_title(src)
        self.assertEqual(st, "NOT_EXTRACTABLE")


class TestCheckSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(tempfile.mkdtemp(prefix="guard root ", dir=self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_free_header_ok(self):
        p = write_source(self.root, helpers.FREE_HEADER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, "free-open-source"))
        self.assertEqual(st["header-structure"], "OK")
        self.assertEqual(st["version-directive"], "OK")
        self.assertEqual(st["header-version"], "OK")
        self.assertEqual(st["no-shorttitle"], "OK")
        self.assertEqual(st["title-ascii"], "OK")
        self.assertEqual(st["no-promo-urls"], "OK")

    def test_paid_header_ok(self):
        p = write_source(self.root, helpers.PAID_HEADER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, "paid-closed-source"))
        self.assertEqual(st["header-structure"], "OK")

    def test_free_header_missing_marks(self):
        p = write_source(self.root, "// Version: 1.0.0\n//@version=6\n" + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, "free-open-source"))
        self.assertEqual(st["header-structure"], "BLOCKING")

    def test_unknown_distribution_unverifiable(self):
        p = write_source(self.root, helpers.FREE_HEADER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, None))
        self.assertEqual(st["header-structure"], "UNVERIFIABLE")

    def test_missing_version_directive(self):
        p = write_source(self.root, "// Version: 1.0.0\n" + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p))
        self.assertEqual(st["version-directive"], "BLOCKING")

    def test_missing_header_version(self):
        p = write_source(self.root, "//@version=6\n" + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p))
        self.assertEqual(st["header-version"], "BLOCKING")

    def test_non_ascii_title_blocking(self):
        p = write_source(self.root, helpers.FREE_HEADER + 'indicator("Élan Décor")\n')
        st = statuses(guard.check_source(p))
        self.assertEqual(st["title-ascii"], "BLOCKING")

    def test_non_extractable_title_unverifiable_not_blocking(self):
        p = write_source(self.root, helpers.FREE_HEADER + 'var t = "x"\nindicator(t)\n')
        st = statuses(guard.check_source(p))
        self.assertEqual(st["title-ascii"], "UNVERIFIABLE")

    def test_cc_url_in_header_legitimate(self):
        p = write_source(self.root, helpers.FREE_HEADER + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p, "free-open-source"))
        self.assertEqual(st["no-promo-urls"], "OK")
        self.assertNotIn("cc-url-placement", st)

    def test_promo_url_blocking(self):
        p = write_source(self.root, helpers.FREE_HEADER +
                         "// visit https://holder-promo.example.com\n" + helpers.MINIMAL_BODY)
        st = statuses(guard.check_source(p))
        self.assertEqual(st["no-promo-urls"], "BLOCKING")

    def test_cc_url_outside_header_warning(self):
        """A licence URL is admitted in a COMMENT outside the header (warning
        on placement); inside a user-facing string it is forbidden (master
        §22.3) — policy ratified on 2026-11-06."""
        p = write_source(self.root, helpers.FREE_HEADER + helpers.MINIMAL_BODY +
                         '// see https://creativecommons.org/licenses/by-nc-sa/4.0/\n')
        st = statuses(guard.check_source(p))
        self.assertEqual(st["cc-url-placement"], "WARNING")
        self.assertEqual(st["no-promo-urls"], "OK")
        p2 = write_source(self.root, helpers.FREE_HEADER + helpers.MINIMAL_BODY +
                          'tip = "https://creativecommons.org/licenses/by-nc-sa/4.0/"\n',
                          name="string url.pine")
        st2 = statuses(guard.check_source(p2))
        self.assertEqual(st2["no-promo-urls"], "BLOCKING")

    def test_version_echo_in_docs_warning(self):
        pdir = self.root / "prod dir"
        pdir.mkdir()
        p = write_source(pdir, helpers.FREE_HEADER + helpers.MINIMAL_BODY)
        (pdir / "PRODUCT.md").write_text("Ce produit est en version 1.0.0.\n", encoding="utf-8")
        st = statuses(guard.check_source(p, "free-open-source", pdir))
        self.assertEqual(st["version-only-in-source"], "WARNING")

    def test_guard_product_end_to_end(self):
        tmp_ws = helpers.make_workspace(self.tmp.name)
        pdir = helpers.make_product(tmp_ws)
        findings = guard.guard_product(pdir)
        st = statuses(findings)
        self.assertEqual(st["manifest"], "OK")
        self.assertNotIn("BLOCKING", [f["status"] for f in findings])

    def test_url_pattern_keeps_balanced_parentheses_and_drops_wrapping(self):
        """Audit C-13 (2026-11-13): a URL keeps balanced parentheses; angle
        brackets, an unbalanced closing parenthesis and trailing punctuation
        are not part of it."""
        text = ("see https://example.invalid/terms_(v2). and <https://www.gnu.org/licenses/>. "
                "(https://example.invalid/x)")
        found = [guard._clean_url(u) for u in guard.URL_RE.findall(text)]
        self.assertEqual(found, ["https://example.invalid/terms_(v2)", "https://www.gnu.org/licenses/",
                                 "https://example.invalid/x"])

    def test_byte_order_mark_tolerated(self):
        """Audit C-13: a source saved with a UTF-8 byte order mark keeps its header."""
        p = write_source(self.root, "\ufeff" + helpers.PAID_HEADER + helpers.MINIMAL_BODY, name="bom.pine")
        st = statuses(guard.check_source(p, "paid-closed-source"))
        self.assertEqual((st["version-directive"], st["header-version"], st["header-structure"]),
                         ("OK", "OK", "OK"))


if __name__ == "__main__":
    unittest.main()
