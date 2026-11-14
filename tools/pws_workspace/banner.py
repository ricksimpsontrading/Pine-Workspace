# SPDX-License-Identifier: Apache-2.0
"""Banners — two DISTINCT usages: the fixed "PWS" banner of the /pws
menu, and the adaptive PINE-WORKSPACE banner of the `banner` subcommand.

Presentation only (2026-11-07 / 08): a banner changes nothing in the menu
tree — not its actions, their order, their identifiers, the navigation,
the confirmations nor the routing. It is shown ONCE at the opening of
/pws and whenever the MAIN menu is shown again; never in front of a
submenu, a question, a result, a JSON document or a hook protocol. A
structured output that carries a banner (`menu --json`, `banner --json`)
does so as a plain data field; no output is ever prefixed with ASCII art.
Every constant is printable ASCII and newlines only (no tab, no character
of ambiguous width, no trailing space), one single block.
The adaptive constants (LARGE, COMPACT) and the former "Pine-WS" menu
banner were rendered ONCE while preparing this module (pyfiglet 1.0.4,
MIT, reading the official font files of the FIGlet distribution,
BSD-3-Clause; the fonts were not modified). The "PWS" menu constant was
composed on 2026-11-14 without running any tool: the P, W and S glyphs of
the "Standard" font, as rendered by pyfiglet in the former "Pine-WS"
constant and in LARGE, joined by that font's horizontal smushing rules
(standard.flf layout 24463: equal character, underscore, hierarchy,
opposite pair) — the same rules reproduce the former "Pine-WS" constant
byte for byte, and its W-S junction is unchanged. Nothing of that
toolchain ships with Pine Workspace and nothing is downloaded, imported or
computed at run time beyond these constants — see
docs/licensing/THIRD_PARTY_NOTICES.md.

1. /pws menu — `menu --json`, data field `banner` = `menu_banner(lang)`
   (holder's decision of 2026-11-08, replacing for /pws ONLY the former
   plain-text fallback; text "PWS" since the holder's decision of
   2026-11-14, replacing "Pine-WS"): ONE fixed constant, MENU, depicting
   exactly "PWS" in the FIGlet font "Standard" (Glenn Chappell & Ian Chai,
   1993) — 23 columns, 5 lines. The same text whether the output is
   captured or not: no width adaptation, no resizing, no animation. The
   skill `pws` passes `banner.question` VERBATIM as the text of the
   main-menu AskUserQuestion: the five banner lines, one empty line, the
   localized question. It never emits the banner as free text before the
   call: free text emitted between a tool result and a tool call is
   treated by Claude Code as progress narration and may be rewritten by
   its presentation layer (observed by the holder on 2026-11-08, the
   banner replaced by an English "summary"). Its width is fixed, so no
   fit in every window is promised, and how the dialog renders leading
   spaces is only established by the holder's observation. "PWS" is
   only the text of this banner: the workspace keeps its official name
   (Pine Workspace) everywhere else (documentation, paths, commands,
   identifiers, metadata).

2. `banner` subcommand (a terminal) — adaptive PINE-WORKSPACE variants:
     large    FIGlet font "Standard", 81 columns
     compact  FIGlet font "Small" (Glenn Chappell, 1993, based on Standard), 64 columns
     minimal  the name itself, plain text, 14 columns
   Choice: the width of a variant is its longest line; the widest artistic
   variant whose width plus MARGIN fits the available width is chosen; the
   plain-text variant only needs its own 14 columns; below 14 known
   columns the banner is omitted (None). An unknown or invalid width (None,
   not an integer, less than 1) yields the plain text.
   Width detection: standard library only, at EACH display — the real size
   of the terminal attached to the output stream (`os.get_terminal_size`),
   read anew every time, so a resize is honoured at the next display
   without any refresh, thread or signal handler. A captured output (pipe,
   file), a size that cannot be read, or a tool pseudo-terminal of Claude
   Code (environment marker CLAUDECODE: its width is the tool's, never the
   visible interface's) is a FALLBACK: width unknown, plain text.
"""
import os
import sys

from . import i18n

# ---- 1. fixed banner of the /pws menu -----------------------------------------
MENU_NAME = "PWS"

# MENU (FIGlet 'standard', "PWS"), 23 columns x 5 lines — never adapted:
#    ______        ______
#   |  _ \ \      / / ___|
#   | |_) \ \ /\ / /\___ \
#   |  __/ \ V  V /  ___) |
#   |_|     \_/\_/  |____/
MENU = "\n".join((
    ' ______        ______',
    '|  _ \\ \\      / / ___|',
    '| |_) \\ \\ /\\ / /\\___ \\',
    '|  __/ \\ V  V /  ___) |',
    '|_|     \\_/\\_/  |____/',
))

# ---- 2. adaptive banner of the `banner` subcommand ----------------------------
NAME = "PINE-WORKSPACE"
MARGIN = 2                            # columns kept free beside an artistic variant
TOOL_PTY_MARKERS = ("CLAUDECODE",)    # environment: a tool pseudo-terminal, not the visible interface

# LARGE (FIGlet 'standard'), 81 columns x 5 lines:
#    ____ ___ _   _ _____   __        _____  ____  _  ______  ____   _    ____ _____
#   |  _ \_ _| \ | | ____|  \ \      / / _ \|  _ \| |/ / ___||  _ \ / \  / ___| ____|
#   | |_) | ||  \| |  _| ____\ \ /\ / / | | | |_) | ' /\___ \| |_) / _ \| |   |  _|
#   |  __/| || |\  | |__|_____\ V  V /| |_| |  _ <| . \ ___) |  __/ ___ \ |___| |___
#   |_|  |___|_| \_|_____|     \_/\_/  \___/|_| \_\_|\_\____/|_| /_/   \_\____|_____|
LARGE = "\n".join((
    ' ____ ___ _   _ _____   __        _____  ____  _  ______  ____   _    ____ _____',
    '|  _ \\_ _| \\ | | ____|  \\ \\      / / _ \\|  _ \\| |/ / ___||  _ \\ / \\  / ___| ____|',
    "| |_) | ||  \\| |  _| ____\\ \\ /\\ / / | | | |_) | ' /\\___ \\| |_) / _ \\| |   |  _|",
    '|  __/| || |\\  | |__|_____\\ V  V /| |_| |  _ <| . \\ ___) |  __/ ___ \\ |___| |___',
    '|_|  |___|_| \\_|_____|     \\_/\\_/  \\___/|_| \\_\\_|\\_\\____/|_| /_/   \\_\\____|_____|',
))

# COMPACT (FIGlet 'small'), 64 columns x 4 lines:
#    ___ ___ _  _ ___  __      _____  ___ _  _____ ___  _   ___ ___
#   | _ \_ _| \| | __|_\ \    / / _ \| _ \ |/ / __| _ \/_\ / __| __|
#   |  _/| || .` | _|___\ \/\/ / (_) |   / ' <\__ \  _/ _ \ (__| _|
#   |_| |___|_|\_|___|   \_/\_/ \___/|_|_\_|\_\___/_|/_/ \_\___|___|
COMPACT = "\n".join((
    ' ___ ___ _  _ ___  __      _____  ___ _  _____ ___  _   ___ ___',
    '| _ \\_ _| \\| | __|_\\ \\    / / _ \\| _ \\ |/ / __| _ \\/_\\ / __| __|',
    "|  _/| || .` | _|___\\ \\/\\/ / (_) |   / ' <\\__ \\  _/ _ \\ (__| _|",
    '|_| |___|_|\\_|___|   \\_/\\_/ \\___/|_|_\\_|\\_\\___/_|/_/ \\_\\___|___|',
))

MINIMAL = NAME

# widest first: the choice walks this order and takes the first that fits
VARIANTS = (("large", LARGE), ("compact", COMPACT), ("minimal", MINIMAL))
ARTISTIC = VARIANTS[:-1]


def width_of(text):
    """Width of a banner: its longest line (no tab, no ambiguous width)."""
    return max(len(line) for line in text.split("\n"))


def menu_banner(lang=None):
    """Structured form of the FIXED /pws banner (data, never a prefix): the
    same text whatever the output stream or its width. `question` is the
    complete text of the main-menu question, passed verbatim by the skill
    to AskUserQuestion: the five banner lines, one empty line, then the
    question in the configured language. Not a variant of the adaptive
    banner — `select()` never returns it."""
    lang = i18n.normalize_language(lang)
    return {
        "name": MENU_NAME,
        "usage": "menu",
        "fixed": True,
        "text": MENU,
        "width": width_of(MENU),
        "height": len(MENU.split("\n")),
        "language": lang,
        "question": MENU + "\n\n" + i18n.t("menu.question", lang),
    }


def _known_width(width):
    """The width as a positive int, or None when unknown or invalid."""
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        return None
    return width


def select(width):
    """(variant name, text) for an available width; ("minimal", NAME) when
    the width is unknown or invalid; (None, None) when the known width is
    narrower than the name itself (banner omitted)."""
    known = _known_width(width)
    if known is None:
        return "minimal", MINIMAL
    if known < width_of(MINIMAL):
        return None, None
    for name, text in ARTISTIC:
        if width_of(text) + MARGIN <= known:
            return name, text
    return "minimal", MINIMAL


def render(width):
    """Text of the banner for an available width, or None when omitted."""
    return select(width)[1]


def detect_width(stream=None, environ=None):
    """(columns, source) of the terminal attached to `stream` (stdout by
    default), read at call time. `source` is "terminal" with a real width,
    else one of the fallbacks "captured" (not a terminal), "tool-pty"
    (pseudo-terminal of a tool, environment marker present) or
    "unavailable" (size not readable) — and the width is None."""
    stream = sys.stdout if stream is None else stream
    environ = os.environ if environ is None else environ
    try:
        is_tty = bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        is_tty = False
    if not is_tty:
        return None, "captured"
    if any(environ.get(marker) for marker in TOOL_PTY_MARKERS):
        return None, "tool-pty"
    try:
        columns = os.get_terminal_size(stream.fileno()).columns
    except (AttributeError, ValueError, OSError):
        return None, "unavailable"
    if columns < 1:
        return None, "unavailable"
    return columns, "terminal"


def describe(width=None, source="unknown"):
    """Structured form of the ADAPTIVE banner (data, never a prefix): the
    chosen variant and text, the widths, and how the available width was
    obtained. Terminal usage (`banner` subcommand), never the /pws menu."""
    variant, text = select(width)
    return {
        "name": NAME,
        "usage": "terminal",
        "fixed": False,
        "variant": variant,                       # large | compact | minimal | None (omitted)
        "text": text,                             # None when omitted
        "width": width_of(text) if text else 0,
        "available_width": _known_width(width),   # None when unknown
        "width_source": source,                   # terminal | captured | tool-pty | unavailable | given | unknown
        "margin": MARGIN,
        "variant_widths": {name: width_of(t) for name, t in VARIANTS},
        "fits_from": {name: width_of(t) + (MARGIN if (name, t) in ARTISTIC else 0)
                      for name, t in VARIANTS},
    }


def current(stream=None, environ=None):
    """The banner fitted to the terminal attached to `stream` right now."""
    return describe(*detect_width(stream, environ))
