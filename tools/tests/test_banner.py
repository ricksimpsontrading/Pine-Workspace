# SPDX-License-Identifier: Apache-2.0
"""Banners (2026-11-07 / 08; menu text "PWS" since 2026-11-14). Two distinct
usages: the FIXED "PWS" banner of the /pws menu (same text whether `menu --json` is captured or written to
a terminal of any width), and the adaptive PINE-WORKSPACE banner of the
`banner` subcommand (three printable-ASCII constants, a choice driven by
the real width of each variant plus an explicit margin, plain text for an
unknown or invalid width, nothing below the name's own width, width read at
each display). Structured outputs are never prefixed; menu content and Back
are untouched."""
import io
import json
import os
import select
import struct
import subprocess
import sys
import tempfile
import unittest

from tools.pws_workspace import banner, core, menu, session
from tools.tests import helpers

try:
    import fcntl
    import pty
    import termios
    HAVE_PTY = hasattr(os, "openpty")
except ImportError:            # pragma: no cover — platform without pseudo-terminals
    HAVE_PTY = False

ROOT = core.workspace_root()
NAME_WIDTH = len("PINE-WORKSPACE")
PRINTABLE = set(range(32, 127)) | {10}


def set_columns(fd, columns):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))


def clean_env(**extra):
    """Environment of a human terminal: no Claude Code marker, no bytecode."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


def run_in_pty(argv, columns, env):
    """Run argv with stdout attached to a REAL pseudo-terminal of `columns`
    columns. The master is read concurrently (a pty buffer is small) and the
    pty's CRLF is normalised. Returns (text, returncode, stderr)."""
    master, slave = pty.openpty()
    set_columns(slave, columns)
    p = subprocess.Popen(argv, cwd=str(ROOT), stdout=slave, stderr=subprocess.PIPE, env=env)
    os.close(slave)
    out = b""
    try:
        while True:
            ready, _, _ = select.select([master], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            elif p.poll() is not None:
                break
        _, err = p.communicate(timeout=300)
    finally:
        os.close(master)
    return out.decode("utf-8").replace("\r\n", "\n"), p.returncode, err.decode("utf-8", "replace")


def check_block(testcase, text, label):
    """Printable ASCII and newlines only, no tab, no trailing space, no empty
    line: one single block."""
    testcase.assertTrue(text and not text.startswith("\n") and not text.endswith("\n"), label)
    testcase.assertNotIn("\t", text, label)
    for ch in text:
        testcase.assertIn(ord(ch), PRINTABLE, (label, repr(ch)))
    for line in text.split("\n"):
        testcase.assertEqual(line, line.rstrip(), (label, "trailing space"))
        testcase.assertTrue(line.strip(), (label, "empty line"))


class TestMenuBanner(unittest.TestCase):
    """The fixed banner of /pws."""

    def test_fixed_pws_banner_depicts_pws_in_one_printable_block(self):
        check_block(self, banner.MENU, "menu")
        self.assertEqual(banner.MENU_NAME, "PWS")
        lines = banner.MENU.split("\n")
        self.assertEqual(len(lines), 5)
        self.assertEqual(banner.width_of(banner.MENU), 23)
        self.assertEqual(max(len(l) for l in lines), 23)
        # the exact FIGlet "Standard" art of "PWS" (holder's decision of 2026-11-14)
        self.assertEqual(lines, [
            " ______        ______",
            "|  _ \\ \\      / / ___|",
            "| |_) \\ \\ /\\ / /\\___ \\",
            "|  __/ \\ V  V /  ___) |",
            "|_|     \\_/\\_/  |____/",
        ])
        # the product keeps its official name: only the banner text changed
        self.assertEqual(banner.NAME, "PINE-WORKSPACE")

    def test_menu_banner_is_structured_fixed_data(self):
        b = banner.menu_banner("en")
        self.assertEqual(b, {"name": "PWS", "usage": "menu", "fixed": True, "text": banner.MENU,
                             "width": 23, "height": 5, "language": "en",
                             "question": banner.MENU + "\n\nWhat would you like to do?"})
        self.assertEqual(banner.menu_banner("en"), b)                # no state, no width involved
        self.assertEqual(banner.menu_banner(), b)                    # default language: English
        self.assertEqual(banner.menu_banner("xx")["language"], "en")

    def test_menu_question_keeps_the_exact_lines_a_blank_line_and_the_localized_question(self):
        expected_question = {"fr": "Que souhaitez-vous faire ?", "en": "What would you like to do?"}
        for lang, sentence in expected_question.items():
            q = banner.menu_banner(lang)["question"]
            lines = q.split("\n")
            self.assertEqual(lines[:5], banner.MENU.split("\n"), lang)      # the five exact lines, spaces kept
            self.assertEqual(lines[0][0], " ", "leading space of the first line kept")
            self.assertEqual(lines[5], "", "one empty line")
            self.assertEqual(lines[6], sentence, lang)
            self.assertEqual(len(lines), 7, lang)
            self.assertNotIn("\t", q)
            self.assertFalse(q.startswith("\n") or q.endswith("\n") or q.endswith(" "))
            self.assertEqual(q, banner.MENU + "\n\n" + sentence)
        self.assertNotEqual(banner.menu_banner("fr")["question"], banner.menu_banner("en")["question"])

    def test_fixed_banner_is_distinct_from_the_adaptive_terminal_variants(self):
        self.assertNotIn(banner.MENU, [t for _, t in banner.VARIANTS])
        for width in list(range(1, 200)) + [None, 0, -1, "80"]:
            self.assertNotEqual(banner.select(width)[1], banner.MENU, repr(width))
        d = banner.describe(200, "terminal")
        self.assertEqual((d["usage"], d["fixed"], d["name"]), ("terminal", False, "PINE-WORKSPACE"))
        self.assertNotEqual(d["text"], banner.MENU)


class TestVariants(unittest.TestCase):
    """The adaptive banner of the `banner` subcommand."""

    def test_three_variants_printable_ascii_only_name_kept_whole(self):
        self.assertEqual([n for n, _ in banner.VARIANTS], ["large", "compact", "minimal"])
        self.assertEqual(banner.NAME, "PINE-WORKSPACE")
        self.assertEqual(banner.MINIMAL, banner.NAME)
        for name, text in banner.VARIANTS:
            check_block(self, text, name)
        # one block per variant: the hyphenated name is never split over two blocks
        self.assertEqual(len(banner.LARGE.split("\n")), 5)
        self.assertEqual(len(banner.COMPACT.split("\n")), 4)

    def test_widths_are_the_longest_line_and_strictly_decreasing(self):
        self.assertEqual(banner.width_of("ab\nabcd\na"), 4)
        widths = [banner.width_of(t) for _, t in banner.VARIANTS]
        self.assertEqual(widths[-1], NAME_WIDTH)
        self.assertTrue(widths[0] > widths[1] > widths[2], widths)
        self.assertEqual(banner.describe(None)["variant_widths"],
                         {"large": widths[0], "compact": widths[1], "minimal": widths[2]})


class TestChoice(unittest.TestCase):
    def test_thresholds_follow_the_real_width_of_each_artistic_variant(self):
        large = banner.width_of(banner.LARGE) + banner.MARGIN
        compact = banner.width_of(banner.COMPACT) + banner.MARGIN
        self.assertGreater(large, compact)
        self.assertGreater(compact, NAME_WIDTH)
        self.assertEqual(banner.describe(None)["fits_from"],
                         {"large": large, "compact": compact, "minimal": NAME_WIDTH})
        # large: just below, exactly, just above
        self.assertEqual(banner.select(large - 1), ("compact", banner.COMPACT))
        self.assertEqual(banner.select(large), ("large", banner.LARGE))
        self.assertEqual(banner.select(large + 1), ("large", banner.LARGE))
        # compact
        self.assertEqual(banner.select(compact - 1), ("minimal", banner.MINIMAL))
        self.assertEqual(banner.select(compact), ("compact", banner.COMPACT))
        self.assertEqual(banner.select(compact + 1), ("compact", banner.COMPACT))
        # minimal: needs only its own 14 columns (no margin for plain text)
        self.assertEqual(banner.select(NAME_WIDTH - 1), (None, None))
        self.assertEqual(banner.select(NAME_WIDTH), ("minimal", banner.MINIMAL))
        self.assertEqual(banner.select(NAME_WIDTH + 1), ("minimal", banner.MINIMAL))

    def test_unknown_or_invalid_width_gives_the_plain_text(self):
        for width in (None, 0, -1, -80, "80", "", 80.0, float("nan"), True, False, [], {}, object()):
            self.assertEqual(banner.select(width), ("minimal", banner.MINIMAL), repr(width))
            d = banner.describe(width, "unknown")
            self.assertEqual((d["variant"], d["text"], d["available_width"]),
                             ("minimal", banner.MINIMAL, None), repr(width))

    def test_known_width_below_the_name_omits_the_banner(self):
        for width in range(1, NAME_WIDTH):
            self.assertEqual(banner.select(width), (None, None), width)
            self.assertIsNone(banner.render(width))
        d = banner.describe(10, "terminal")
        self.assertEqual((d["variant"], d["text"], d["width"], d["available_width"], d["width_source"]),
                         (None, None, 0, 10, "terminal"))

    def test_two_successive_displays_follow_the_width_of_the_moment(self):
        shown = [banner.describe(w, "terminal")["variant"] for w in (200, 70, 20, 200, 13)]
        self.assertEqual(shown, ["large", "compact", "minimal", "large", None])
        self.assertEqual(banner.render(200), banner.LARGE)       # no state kept between calls
        self.assertEqual(banner.render(70), banner.COMPACT)

    def test_every_chosen_artistic_variant_respects_width_and_margin_and_is_the_widest_fit(self):
        artistic = dict(banner.ARTISTIC)
        for width in range(1, 200):
            variant, text = banner.select(width)
            if variant in artistic:
                self.assertLessEqual(banner.width_of(text) + banner.MARGIN, width, width)
                for line in text.split("\n"):
                    self.assertLessEqual(len(line), width - banner.MARGIN, width)
                wider = [n for n, t in banner.ARTISTIC if banner.width_of(t) > banner.width_of(text)]
                for n in wider:          # no wider variant would have fitted
                    self.assertGreater(banner.width_of(artistic[n]) + banner.MARGIN, width, (width, n))
            elif variant == "minimal":
                self.assertGreaterEqual(width, NAME_WIDTH)
                for n, t in banner.ARTISTIC:
                    self.assertGreater(banner.width_of(t) + banner.MARGIN, width, (width, n))
            else:
                self.assertEqual((variant, text), (None, None))
                self.assertLess(width, NAME_WIDTH)


class TestWidthDetection(unittest.TestCase):
    def test_captured_output_is_a_fallback(self):
        self.assertEqual(banner.detect_width(io.StringIO(), {}), (None, "captured"))
        self.assertEqual(banner.current(io.StringIO(), {})["variant"], "minimal")

    def test_unreadable_size_is_a_fallback(self):
        class TtyWithoutSize:
            def isatty(self):
                return True

            def fileno(self):
                raise OSError("no fd")
        self.assertEqual(banner.detect_width(TtyWithoutSize(), {}), (None, "unavailable"))

    @unittest.skipUnless(HAVE_PTY, "pseudo-terminals unavailable on this platform")
    def test_real_terminal_width_read_at_each_call_and_tool_pty_never_trusted(self):
        master, slave = pty.openpty()
        try:
            set_columns(slave, 120)
            with os.fdopen(os.dup(slave), "w") as stream:
                self.assertEqual(banner.detect_width(stream, {}), (120, "terminal"))
                self.assertEqual(banner.current(stream, {})["variant"], "large")
                set_columns(slave, 60)                       # resized: seen at the next display
                self.assertEqual(banner.detect_width(stream, {}), (60, "terminal"))
                self.assertEqual(banner.current(stream, {})["variant"], "minimal")
                set_columns(slave, 70)
                self.assertEqual(banner.current(stream, {})["variant"], "compact")
                # a tool pseudo-terminal (Claude Code marker) is not the visible interface
                self.assertEqual(banner.detect_width(stream, {"CLAUDECODE": "1"}), (None, "tool-pty"))
                self.assertEqual(banner.current(stream, {"CLAUDECODE": "1"})["variant"], "minimal")
        finally:
            os.close(master)
            os.close(slave)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_workspace(self.tmp.name)
        helpers.configure(self.root, language="fr")
        helpers.make_product_v3(self.root, slug="solo")

    def tearDown(self):
        self.tmp.cleanup()

    def argv(self, *args):
        return [sys.executable, "-m", "tools.pws_workspace", "--root", str(self.root), *args]

    def cli(self, *args, stdin=None, env=None):
        return subprocess.run(self.argv(*args), cwd=str(ROOT), input=stdin, capture_output=True, text=True,
                              timeout=300, env=env or dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_menu_json_carries_the_fixed_banner_as_data_and_the_tree_is_unchanged(self):
        r = self.cli("menu", "--json")                              # captured, as in Claude Code
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("{"), r.stdout[:40])    # never prefixed
        data = json.loads(r.stdout)
        b = data.pop("banner")
        self.assertEqual(b, banner.menu_banner("fr"))               # the fixed PWS art, even captured
        self.assertEqual((b["name"], b["fixed"], b["usage"], b["width"], b["height"], b["language"]),
                         ("PWS", True, "menu", 23, 5, "fr"))
        self.assertEqual(b["text"], banner.MENU)
        # the ready-to-send main-menu question: exact lines, blank line, French question
        self.assertEqual(b["question"], banner.MENU + "\n\nQue souhaitez-vous faire ?")
        self.assertEqual(b["question"].split("\n")[:5], banner.MENU.split("\n"))
        expected = json.loads(json.dumps(menu.build_menu(session.session_status(self.root))))
        self.assertEqual(data, expected)                            # same actions, order, ids, routes, labels
        self.assertEqual(data["language"], "fr")

        def walk(nodes):
            for n in nodes:
                for screen in n.get("children") or []:
                    self.assertEqual(screen[-1]["id"], "back")
                    self.assertEqual(screen[-1]["label"], "Retour")
                    walk(screen)
        walk(data["top"])
        self.assertEqual([t["id"] for t in data["top"]], ["work", "new", "quality", "maintenance"])

    @unittest.skipUnless(HAVE_PTY, "pseudo-terminals unavailable on this platform")
    def test_pws_receives_the_same_fixed_banner_captured_or_in_a_terminal_of_any_width(self):
        captured = json.loads(self.cli("menu", "--json").stdout)["banner"]
        for columns, env in ((120, clean_env()), (30, clean_env()), (120, clean_env(CLAUDECODE="1"))):
            out, rc, err = run_in_pty(self.argv("menu", "--json"), columns, env)
            self.assertEqual(rc, 0, err)
            self.assertTrue(out.startswith("{"), out[:40])
            self.assertEqual(json.loads(out)["banner"], captured, columns)
        self.assertEqual(captured["text"], banner.MENU)
        self.assertEqual(captured["question"], banner.MENU + "\n\nQue souhaitez-vous faire ?")

    def test_menu_question_follows_the_configured_language(self):
        from tools.pws_workspace import config
        r = config.set_value(self.root, "language", "en")
        self.assertTrue(r["ok"], r)
        data = json.loads(self.cli("menu", "--json").stdout)
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["banner"]["question"], banner.MENU + "\n\nWhat would you like to do?")
        self.assertEqual(data["title"], "PWS menu")

    def test_structured_outputs_and_hooks_are_never_prefixed_with_a_banner(self):
        art_lines = set(banner.MENU.split("\n")) | set(banner.LARGE.split("\n")) | set(banner.COMPACT.split("\n"))
        for args in (("session-status", "--json"), ("scan", "--json"), ("doctor", "--json"),
                     ("version",), ("banner", "--json"), ("menu", "--json")):
            r = self.cli(*args)
            self.assertIn(r.stdout.lstrip()[:1], ("{", "["), args)
            json.loads(r.stdout)                                     # whole output is one JSON document
            self.assertFalse(art_lines & set(r.stdout.split("\n")), args)
        hook = self.cli("hook-session-start", stdin=json.dumps({"session_id": "t-banner", "source": "startup"}))
        self.assertEqual(hook.returncode, 0, hook.stderr)
        self.assertTrue(hook.stdout.startswith("PWS\n"), hook.stdout[:60])
        self.assertFalse(art_lines & set(hook.stdout.split("\n")))
        self.assertNotIn("PINE-WORKSPACE", hook.stdout)
        self.assertNotIn("Pine-WS", hook.stdout)
        self.assertNotIn(banner.MENU, hook.stdout)                  # its first line "PWS" is plain text, not the art

    def test_banner_command_captured_prints_the_plain_text(self):
        r = self.cli("banner")
        self.assertEqual((r.returncode, r.stdout), (0, "PINE-WORKSPACE\n"))

    @unittest.skipUnless(HAVE_PTY, "pseudo-terminals unavailable on this platform")
    def test_banner_command_in_a_real_terminal_follows_its_width_at_each_display(self):
        large = banner.width_of(banner.LARGE) + banner.MARGIN
        compact = banner.width_of(banner.COMPACT) + banner.MARGIN
        cases = ((large, clean_env(), banner.LARGE + "\n"),
                 (compact, clean_env(), banner.COMPACT + "\n"),               # resized: next display
                 (compact - 1, clean_env(), banner.MINIMAL + "\n"),
                 (NAME_WIDTH - 1, clean_env(), ""),                           # omitted, nothing printed
                 (large, clean_env(CLAUDECODE="1"), banner.MINIMAL + "\n"))   # tool pty: fallback
        for columns, env, expected in cases:
            out, rc, err = run_in_pty(self.argv("banner"), columns, env)
            self.assertEqual((rc, out), (0, expected), (columns, err))


if __name__ == "__main__":
    unittest.main()
