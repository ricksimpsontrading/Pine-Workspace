# SPDX-License-Identifier: Apache-2.0
"""Deterministic Pine source guard — mechanical checks only (spec section 38).

Finding classes:
  BLOCKING     mechanical violation, reliable, must be fixed;
  WARNING      mechanical signal worth attention, never blocks;
  UNVERIFIABLE parser could not establish the fact — honest diagnostic,
               NEVER a violation (spec section 39: parser uncertainty is
               not proof of violation);
  OK           check passed.

Header policy (master section 6, 2026-11-06 profiles): the marks expected in
the licence header are DERIVED from the product's VALIDATED licence axes (the
same manifest checks as the scan and the Stop hook) and the configured
identity (`pws.config.json`), never hard-coded:
  - every source: `//@version=6`, `// Version: X.Y.Z` INSIDE the header
    region (a Version line further down the body never satisfies it); a
    UTF-8 byte order mark is tolerated;
  - CC BY-NC-SA 4.0 licence: exactly the "CC BY-NC-SA 4.0" mark and the
    licence URL https://creativecommons.org/licenses/by-nc-sa/4.0/;
  - proprietary licence: the "All Rights Reserved" mark;
  - copyright line: a `©` line naming the copyright holder (or one of the
    configured aliases) when an identity is configured — UNVERIFIABLE
    otherwise; a third-party © line is an attribution and stays;
  - an unrendered template field (`© {{YEAR_RANGE}}`) is BLOCKING.
Licence notices (decision D of 2026-11-13): a header that lacks the declared
licence but carries ANOTHER recognized licence (MPL-2.0 — the default header of
the Pine Editor —, MIT, Apache-2.0, GPL…) or an unrecognized licence statement
is reported as a licence decision of the holder, to analyse — never as a
notice to remove or replace. A header that carries the declared marks AND
another licence mention gets a WARNING (third-party notice to keep, or
contradiction to analyse).
Licence of an imported script (`license.origin` imported, 2026-11-13, audit
C-19): never the CC header nor "All Rights Reserved" nor a copyright line
naming the configured holder (the original authors stay cited). The existing
notice must still be present and coherent with `license.id`: a missing notice,
or a notice stating another exact licence of the same family (GPL-3.0-or-later
against GPL-3.0-only…), is BLOCKING — the record is corrected with the holder,
the notice is never changed to satisfy the guard; a notice that does not
establish the recorded identifier exactly (several versions or a choice
between versions, a deprecated identifier, a "later" wording without the
explicit clause…) or another licence mention is a WARNING — never silent,
never a block. That notice is read in the header and in the initial comment
block that follows the //@version line, up to the first line of code (where
its authors may have put it). A licence still to analyse leaves the header
model UNVERIFIABLE (nothing to compare with). `header_licence_proposal`
reads a header and PROPOSES an exact identifier — never a legal proof.
URL policy: licence URLs are admitted in COMMENT lines only — licence bodies
(Creative Commons licences and public-domain tools, MPL, Apache, GNU, OSI,
SPDX; https or http) and the LICENSE / COPYING / NOTICE file of a source
repository on a known code host when the comment is a licence notice — plus
the product's declared `terms_url` (exact). Any other URL anywhere, and any
URL in code or user-facing text, is BLOCKING (master sections 6, 22.3); a web
address without scheme or an e-mail address in user-facing text is a WARNING.

shorttitle policy (master section 6.3, hardened by the 2026-09-05 reviews):
the forbidden construct is the declaration parameter — named (`shorttitle=`
inside the indicator/strategy/library argument list) or POSITIONAL (second
positional argument of indicator/strategy). A named `shorttitle=` outside the
declaration (user-function default or call) is only a WARNING; a variable
merely named shorttitle is not flagged at all; a non-literal second
positional argument is UNVERIFIABLE.

Work-log comments (master section 24.5): lot history, audit/review
narratives, conversation references and instructions to the assistant do
not belong in a source — reported as ONE WARNING with a count, never
blocking (an existing product is cleaned in its own task).

No semantic judgement: signal quality, repaint, UX, architecture are out of
scope (spec section 37.3).

Finding identity (spec section 41.2): every BLOCKING finding carries
`subjects`, one entry per anomaly — the OBJECT of the anomaly (missing mark,
offending value or URL), never its position. The human `detail` keeps the
line numbers; the identity never does, so shifting lines cannot turn an
existing anomaly into a new one, and two anomalies of the same check stay
distinct (occurrences are counted).
"""
import re
from pathlib import Path

from . import core, profiles

SHORTTITLE_RE = re.compile(r"\bshort_?title\s*=(?!=)")
DECL_RE = re.compile(r"^\s*(indicator|strategy|library)\s*\(", re.M)
VERSION_DIRECTIVE_RE = re.compile(r"^//@version=6\s*$", re.M)
HEADER_VERSION_RE = re.compile(r"^//\s*Version:\s*(\d+\.\d+\.\d+)\s*$", re.M)
# A URL keeps balanced parentheses (`…/terms_(v2)`); angle brackets, quotes and
# unbalanced parentheses end it; trailing sentence punctuation is not part of it.
URL_RE = re.compile(r"https?://(?:[^\s'\"()<>\[\]{}]|\([^\s'\"()<>\[\]{}]*\))+")
URL_TRAILING_PUNCTUATION = ".,;:!?"
CC_URL_PREFIX = "https://creativecommons.org/licenses/"
CC_LICENSES_URL_RE = re.compile(r"^https?://(?:www\.)?creativecommons\.org/licenses/", re.I)
# Licence URLs admitted in comment lines (third-party notices, licence header):
# the licence bodies themselves, https or http (decision D of 2026-11-13)...
LICENCE_BODY_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:"
    r"creativecommons\.org/(?:licenses|publicdomain)/"
    r"|mozilla\.org/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?MPL/"
    r"|apache\.org/licenses/"
    r"|gnu\.org/(?:licenses|copyleft)/"
    r"|opensource\.org/licenses?/"
    r"|spdx\.org/licenses/"
    r")[^?\s]*$", re.I)
# ... and the licence file of a source repository on a known code host, only
# in a comment that is a licence notice (never a domain-wide allowance).
REPO_LICENCE_FILE_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|codeberg\.org|"
    r"raw\.githubusercontent\.com|gist\.github\.com|sourceforge\.net)/"
    r"[^?#\s]*/(?:LICEN[CS]E|COPYING|UNLICENSE|NOTICE)(?:[._-][A-Za-z0-9._-]*)?$", re.I)
NOTICE_WORDS_RE = re.compile(
    r"licen[cs]|copyright|©|\(c\)|spdx|public[ -]?domain|copyleft|\bcc0\b|\bmpl\b|\bgpl\b|"
    r"permission is hereby granted|all rights reserved", re.I)
# Header licence marks (exact for the declared licence) and other licences.
CC_MARK_RE = re.compile(r"\bCC[ \u00a0]+BY-NC-SA[ \u00a0]+4\.0\b")
CC_EXACT_URL_RE = re.compile(r"https://creativecommons\.org/licenses/by-nc-sa/4\.0(?:/|\b)")
CC_FAMILY_RE = re.compile(r"\bCC[ \u00a0]+BY-NC-SA\b|creativecommons\.org/licenses/by-nc-sa/", re.I)
PROPRIETARY_MARK_RE = re.compile(r"all rights reserved", re.I)
FOREIGN_LICENCES = (
    ("MPL-2.0", re.compile(r"Mozilla Public License|mozilla\.org/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?MPL"
                           r"|\bMPL[- ]?2\.0\b", re.I)),
    ("Apache-2.0", re.compile(r"Apache License|apache\.org/licenses/|\bApache-2\.0\b", re.I)),
    ("AGPL", re.compile(r"GNU Affero General Public License|\bAGPL", re.I)),
    ("LGPL", re.compile(r"GNU (?:Lesser|Library) General Public License|\bLGPL", re.I)),
    ("GPL", re.compile(r"GNU General Public License|\bGPL-?[23]|\bGPLv[23]", re.I)),
    ("MIT", re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge"
                       r"|SPDX-License-Identifier:\s*MIT\b", re.I)),
    ("BSD", re.compile(r"\bBSD[- ]?[234]-Clause\b|Redistribution and use in source and binary forms", re.I)),
    ("CC0-1.0", re.compile(r"\bCC0\b|creativecommons\.org/publicdomain/", re.I)),
    ("Unlicense", re.compile(r"\bUnlicense\b|unlicense\.org", re.I)),
    ("ISC", re.compile(r"\bISC License\b", re.I)),
    ("another Creative Commons licence", re.compile(
        r"creativecommons\.org/licenses/(?!by-nc-sa/4\.0)|\bCC[ \u00a0]+BY(?:-(?:SA|ND|NC|NC-ND))?[ \u00a0]+\d",
        re.I)),
)
LICENCE_STATEMENT_RE = re.compile(r"\blicen[cs]ed under\b|\breleased under\b|\bdistributed under the\b"
                                  r"|\bsubject to the terms of the\b|SPDX-License-Identifier", re.I)
# ---- licence proposal of a header (imported scripts, 2026-11-13, audit C-19) ----
SPDX_LINE_RE = re.compile(r"SPDX-License-Identifier:\s*([^\n]*?)\s*(?:\*/)?\s*$", re.I | re.M)
SPDX_SINGLE_ID_RE = re.compile(r"^[A-Za-z0-9.+-]+$")
MPL_RE = re.compile(r"Mozilla Public Licen[cs]e|mozilla\.org/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?MPL|\bMPL\b", re.I)
MPL_VERSION_RES = (re.compile(r"Mozilla Public Licen[cs]e,?\s*(?:v(?:ersion)?\.?\s*)?(\d+(?:\.\d+)?)", re.I),
                   re.compile(r"mozilla\.org/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?MPL/(\d+(?:\.\d+)?)", re.I),
                   re.compile(r"\bMPL[- ]?v?(\d+(?:\.\d+)?)\b", re.I))
MPL_NO_COPYLEFT_EXCEPTION_RE = re.compile(r"Incompatible With Secondary Licen[cs]es", re.I)
APACHE_RE = re.compile(r"Apache Licen[cs]e|apache\.org/licenses/|\bApache-\d", re.I)
APACHE_VERSION_RES = (re.compile(r"Apache Licen[cs]e,?\s*(?:Version|v\.?)?\s*(\d+(?:\.\d+)?)", re.I),
                      re.compile(r"apache\.org/licenses/LICENSE-(\d+(?:\.\d+)?)", re.I),
                      re.compile(r"\bApache-(\d+(?:\.\d+)?)\b", re.I))
GNU_FAMILIES = (
    ("AGPL", re.compile(r"GNU Affero General Public Licen[cs]e|\bAGPL", re.I), ("3.0",)),
    ("LGPL", re.compile(r"GNU (?:Lesser|Library) General Public Licen[cs]e|\bLGPL", re.I), ("2.1", "3.0")),
    ("GPL", re.compile(r"GNU General Public Licen[cs]e|\bGNU GPL\b|\bGPL\b|\bGPL-?v?\d", re.I), ("2.0", "3.0")),
)
GNU_LIBRARY_RE = re.compile(r"GNU Library General Public Licen[cs]e", re.I)
GNU_VERSION_RES = (
    re.compile(r"\bversion\s+(\d+(?:\.\d+)?)\s+of\s+the\s+(?:GNU\s+)?(?:Affero\s+|Lesser\s+|Library\s+)?"
               r"(?:General\s+Public\s+)?Licen[cs]e", re.I),
    re.compile(r"General\s+Public\s+Licen[cs]e,?\s*(?:as\s+published\s+by\s+the\s+Free\s+Software\s+"
               r"Foundation,?\s*)?(?:v(?:ersion)?\.?\s*)(\d+(?:\.\d+)?)", re.I),
    re.compile(r"\b(?:A|L)?GPL[- ]?(?:v(?:ersion)?\.?\s*)?(\d+(?:\.\d+)?)", re.I),     # GPLv3, GPL-3.0, GPL version 3
)
# A choice between GNU versions — a version followed by another one: "version 2
# or 3", "version 2 or version 3 of the License", "v2 or v3", "GPLv2/GPLv3",
# "version 2 of the License, or (at your option) version 3". It states neither
# one "-only" nor one "-or-later" licence (audit C-19, M2). A bare second number
# is one digit (and an optional decimal): never a year.
GNU_VERSION_CHOICE_RE = re.compile(
    r"(?:\bversions?\s+|\b(?:A|L)?GPL[- ]?v?|\bv\.?\s*)(\d+(?:\.\d+)?)"
    r"(?:\s+of\s+the\s+(?:GNU\s+)?(?:Affero\s+|Lesser\s+|Library\s+)?(?:General\s+Public\s+)?Licen[cs]e)?"
    r"((?:\s*(?:,\s*(?:or|and(?:/or)?)\b|,|/|&|\bor\b|\band/or\b|\band\b)\s*(?:\(\s*at\s+your\s+option\s*\)\s*)?"
    r"(?:(?:the\s+)?(?:GNU\s+)?(?:(?:A|L)?GPL[- ]?v?\s*|versions?\s+|v\.?\s*)\d+(?:\.\d+)?"
    r"|\d(?:\.\d)?(?!\d|\.\d)))+)", re.I)
# The only "-or-later" wording (specification §45.4): "either version N of the
# License, or (at your option) any later version" — case, spacing, comment
# wrapping, the optional comma and the licence named in full are free.
GNU_OR_LATER_CLAUSE_RE = re.compile(
    r"\beither\s+version\s+(\d+(?:\.\d+)?)\s+of\s+the\s+(?:GNU\s+)?(?:Affero\s+|Lesser\s+|Library\s+)?"
    r"(?:General\s+Public\s+)?Licen[cs]e\s*,?\s*or\s+\(\s*at\s+your\s+option\s*\)\s+any\s+later\s+version\b",
    re.I)
# words of a choice outside that clause: "either … or …", "at your option"
GNU_CHOICE_WORDS_RE = re.compile(r"\beither\b|\bat\s+your\s+option\b", re.I)
GNU_LATER_WORDING_RE = re.compile(r"\blater\b|(?:GPL|version)[- ]?v?\d+(?:\.\d+)?\+", re.I)
GNU_EXCEPTION_RE = re.compile(r"\bexception\b", re.I)
# a deprecated GNU SPDX identifier written in the text of a notice ("Licensed
# under GPL-3.0"): read as on an SPDX line, never as "version N" alone (m2);
# a path segment of a URL (…/licenses/gpl-3.0) is not an identifier
GNU_SPDX_TOKEN_RE = re.compile(r"(?<![\w.+/-])((?:A|L)?GPL-\d+\.\d+\+?)(?![\w+/]|[.-]\w)", re.I)
EXPAT_GRANT_RE = re.compile(r"Permission is hereby granted,?\s+free of charge,?\s+to any person obtaining a copy", re.I)
EXPAT_NOTICE_RE = re.compile(r"above copyright notice and this permission notice shall be included", re.I)
X11_CLAUSE_RE = re.compile(r"Except as contained in this notice,?\s+the name of", re.I)
MIT_NAME_RE = re.compile(r"\bMIT[- ](?:Licen[cs]e|licen[cs]ed)\b|\bunder\s+(?:the\s+)?MIT\b|\(MIT\)", re.I)
BSD_TEXT_RE = re.compile(r"Redistribution and use in source and binary forms,?\s+with or without modification,?"
                         r"\s+are permitted", re.I)
BSD_SOURCE_COND_RE = re.compile(r"Redistributions of source code must retain the above copyright notice", re.I)
BSD_BINARY_COND_RE = re.compile(r"Redistributions in binary form must reproduce the above copyright notice", re.I)
BSD_NAME_COND_RE = re.compile(r"Neither the name of.{0,240}?(?:may|shall) be used to endorse or promote", re.I | re.S)
BSD_ADVERTISING_RE = re.compile(r"All advertising materials mentioning features or use of this software", re.I)
BSD2_NAME_RE = re.compile(r"\bBSD[- ]2[- ]Clause\b|\bSimplified BSD\b", re.I)
BSD3_NAME_RE = re.compile(r"\bBSD[- ]3[- ]Clause\b|\b(?:New|Modified|Revised) BSD\b", re.I)
BSD_ANY_RE = re.compile(r"\bBSD[- ](?:style[- ])?licen[cs]e|\bunder\s+(?:a\s+|the\s+)?BSD\b", re.I)
CC_URL_REF_RE = re.compile(r"creativecommons\.org/licenses/([a-z]+(?:-[a-z]+)*)/(\d+\.\d+)", re.I)
CC_MARK_REF_RE = re.compile(r"\bCC[ \u00a0]+(BY(?:-(?:NC|SA|ND))*)[ \u00a0]+(\d+\.\d+)\b", re.I)
CC_TEXT_REF_RE = re.compile(r"\bAttribution((?:-(?:NonCommercial|ShareAlike|NoDerivatives|NoDerivs))*)\s+(\d+\.\d+)",
                            re.I)
CC_ANY_RE = re.compile(r"Creative\s+Commons|creativecommons\.org|\bCC[ \u00a0]+BY\b|\bCC0\b", re.I)
CC_PUBLIC_DOMAIN_RE = re.compile(r"\bCC0\b|creativecommons\.org/publicdomain/", re.I)
OTHER_NAMED_LICENCES = (
    ("ISC", re.compile(r"\bISC Licen[cs]e\b", re.I)),
    ("Unlicense", re.compile(r"\bUnlicense\b|unlicense\.org", re.I)),
    ("BSL-1.0", re.compile(r"Boost Software Licen[cs]e", re.I)),
    ("Zlib", re.compile(r"\bzlib Licen[cs]e\b", re.I)),
    ("EPL", re.compile(r"Eclipse Public Licen[cs]e", re.I)),
    ("EUPL", re.compile(r"European Union Public Licen[cs]e", re.I)),
    ("Artistic", re.compile(r"Artistic Licen[cs]e", re.I)),
    ("WTFPL", re.compile(r"\bWTFPL\b|Do What The F", re.I)),
    ("public domain", re.compile(r"\bpublic[ -]domain\b", re.I)),
)
# a copyright line of the original authors (imported licences): ©, (c) + year,
# or "Copyright" + year / at the start of a comment line (never the wording
# "copyright notice" or "copyright holders" of a licence text)
COPYRIGHT_LINE_RE = re.compile(r"©|\(c\)\s*\d{4}|\bcopyright\s*(?:\(c\)|©)?\s*\d{4}"
                               r"|^\s*//+\s*copyright\b(?!\s+(?:notice|holders?)\b)", re.I)
# Web addresses without scheme and e-mail addresses in user-facing text.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
WWW_RE = re.compile(r"\bwww\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:/[^\s'\"]*)?", re.I)
BARE_DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+(?:com|net|org|io|co|shop|store|app|info|biz|xyz|gg|me"
                            r"|ai|ly|link|site|online|invalid)\b(?:/[^\s'\"]*)?", re.I)
STRING_LITERAL_RE = re.compile(r"^(['\"])(?:\\.|(?!\1).)*\1$", re.S)
NAMED_ARG_RE = re.compile(r"^[A-Za-z_]\w*\s*=(?!=)")
WORKLOG_PATTERNS = (
    (re.compile(r"\blots?\s+\d+[a-z]?\b", re.I), "lot history"),
    (re.compile(r"\b(since|until|as of|from|after|before|in)\s+lot\b", re.I), "lot history"),
    (re.compile(r"\bAUDIT\s*:", re.I), "audit narrative"),
    (re.compile(r"\bREVIEW\s*:", re.I), "review narrative"),
    (re.compile(r"\bpending review\b", re.I), "review narrative"),
    (re.compile(r"\bconversation\b", re.I), "conversation reference"),
    (re.compile(r"\bClaude\b"), "instruction to the assistant"),
    (re.compile(r"\bmigrated from v\d", re.I), "version history"),
)


def strip_comments_and_strings(line):
    """Remove string literals and the trailing // comment from one line."""
    out = []
    i, n = 0, len(line)
    in_str = None
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ("'", '"'):
            in_str = c
            out.append("\x00")
            i += 1
            continue
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        out.append(c)
        i += 1
    return "".join(out)


def comment_text(line):
    """The // comment part of one line (strings respected), or None."""
    i, n = 0, len(line)
    in_str = None
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ("'", '"'):
            in_str = c
            i += 1
            continue
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            return line[i + 2:]
        i += 1
    return None


def find_shorttitle(source_text):
    """Line numbers where shorttitle/short_title appears as a NAMED CALL
    ARGUMENT (preceded, across whitespace and line breaks, by '(' or ',').

    A variable merely named `shorttitle` (assignment or comparison) is legal
    Pine and is NOT flagged. Comments and strings are stripped first."""
    stripped = "\n".join(strip_comments_and_strings(line)
                         for line in source_text.splitlines())
    hits = []
    for m in SHORTTITLE_RE.finditer(stripped):
        before = stripped[:m.start()].rstrip()
        if before.endswith(("(", ",")):
            hits.append(stripped.count("\n", 0, m.start()) + 1)
    return hits


def _declaration_args(source_text):
    """Locate the main declaration call and return
    (kind, args_text, start_line, end_line) with comments skipped and strings
    preserved, or (None, None, None, None). args_text is None when the
    argument list is unbalanced (honest give-up)."""
    m = DECL_RE.search(source_text)
    if not m:
        return None, None, None, None
    kind = m.group(1)
    i = source_text.index("(", m.start())
    start_line = source_text.count("\n", 0, i) + 1
    depth, j, in_str = 0, i, None
    chars = []
    n = len(source_text)
    while j < n:
        c = source_text[j]
        if in_str:
            chars.append(c)
            if c == "\\" and j + 1 < n:
                chars.append(source_text[j + 1])
                j += 2
                continue
            if c == in_str:
                in_str = None
            j += 1
            continue
        if c in ("'", '"'):
            in_str = c
            chars.append(c)
            j += 1
            continue
        if c == "/" and j + 1 < n and source_text[j + 1] == "/":
            # comment inside the argument list: skip to end of line so
            # commented text can never masquerade as an argument
            while j < n and source_text[j] != "\n":
                j += 1
            continue
        if c == "(":
            depth += 1
            if depth > 1:
                chars.append(c)
            j += 1
            continue
        if c == ")":
            depth -= 1
            if depth == 0:
                end_line = source_text.count("\n", 0, j) + 1
                return kind, "".join(chars), start_line, end_line
            chars.append(c)
            j += 1
            continue
        chars.append(c)
        j += 1
    return kind, None, start_line, None


def _split_top_level_args(args_text):
    """Split an argument list on top-level commas (strings and nesting
    respected)."""
    parts, cur = [], []
    depth, in_str, i = 0, None, 0
    n = len(args_text)
    while i < n:
        c = args_text[i]
        if in_str:
            cur.append(c)
            if c == "\\" and i + 1 < n:
                cur.append(args_text[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ("'", '"'):
            in_str = c
            cur.append(c)
        elif c in "([":
            depth += 1
            cur.append(c)
        elif c in ")]":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_title(source_text):
    """(status, title): EXTRACTED | NOT_EXTRACTABLE | NO_DECL."""
    kind, args, _, _ = _declaration_args(source_text)
    if kind is None:
        return "NO_DECL", None
    if args is None:
        return "NOT_EXTRACTABLE", None
    tm = re.search(r"\btitle\s*=\s*(['\"])((?:\\.|(?!\1).)*)\1", args, re.S)
    if tm:
        return "EXTRACTED", tm.group(2)
    fm = re.match(r"^(['\"])((?:\\.|(?!\1).)*)\1", args.strip(), re.S)
    if fm:
        return "EXTRACTED", fm.group(2)
    return "NOT_EXTRACTABLE", None


def _strip_bom(text):
    """A UTF-8 byte order mark at the start of a source is tolerated."""
    return text[1:] if text.startswith("\ufeff") else text


def _string_literals(code):
    """Contents of the string literals of one line of code (comment removed)."""
    out, i, n = [], 0, len(code)
    while i < n:
        quote = code[i]
        if quote not in ("'", '"'):
            i += 1
            continue
        j, buf = i + 1, []
        while j < n:
            if code[j] == "\\" and j + 1 < n:
                buf.append(code[j:j + 2])
                j += 2
                continue
            if code[j] == quote:
                break
            buf.append(code[j])
            j += 1
        out.append("".join(buf))
        i = j + 1
    return out


def _comment_blocks(lines):
    """For each line index, the text of the contiguous block of full-line
    comments it belongs to, or None when the line is not a full-line comment."""
    full = [line.lstrip().startswith("//") for line in lines]
    blocks = [None] * len(lines)
    i = 0
    while i < len(lines):
        if not full[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(lines) and full[j + 1]:
            j += 1
        text = "\n".join(lines[i:j + 1])
        for k in range(i, j + 1):
            blocks[k] = text
        i = j + 1
    return blocks


def _clean_url(url):
    return url.rstrip(URL_TRAILING_PUNCTUATION)


def _licence_url_kind(url):
    """'body' (licence text of a licence body), 'repo' (licence file of a
    source repository on a known code host) or None. A path that walks out
    of the licence folder (`..`, `.`, encoded dots) or a query string is never
    a licence reference."""
    low = url.lower()
    if "/../" in low or "/./" in low or low.endswith(("/..", "/.")) or "%2e" in low:
        return None
    if LICENCE_BODY_URL_RE.match(url):
        return "body"
    if REPO_LICENCE_FILE_URL_RE.match(url):
        return "repo"
    return None


def _contacts_in(text):
    """Web addresses without scheme and e-mail addresses in one text."""
    hits, rest = [], URL_RE.sub(" ", text)
    for rx in (EMAIL_RE, WWW_RE, BARE_DOMAIN_RE):
        hits.extend(m.group(0) for m in rx.finditer(rest))
        rest = rx.sub(" ", rest)
    return hits


def _flatten_comments(text):
    """One line of prose from consecutive comment lines (a notice wrapped over
    several `//` lines stays recognizable: "Mozilla Public // License")."""
    return re.sub(r"\s*\n\s*//[!/]?[ \t]*", " ", text)


def header_licences(header_text):
    """(other recognized licences, unrecognized licence statement present) of
    a header region — the declared CC BY-NC-SA 4.0 / proprietary marks are
    not "other" licences."""
    flat = _flatten_comments(header_text)
    foreign = [name for name, rx in FOREIGN_LICENCES if rx.search(flat)]
    return foreign, bool(LICENCE_STATEMENT_RE.search(flat))


# ---- licence proposal of a header (imported scripts, audit C-19) ---------------

def _licence_entry(family, lid=None, other=None, reason=None, compatible=None):
    """One licence read in a header: `id` = exact identifier of the closed list
    (profiles.IMPORTABLE_LICENSE_IDS) when the notice establishes it; `other` =
    an identifier it establishes OUTSIDE the closed list; `reason` = why no
    identifier of the closed list can be proposed. `compatible`, on an entry
    that establishes no identifier: the identifiers of the closed list it
    still agrees with — an exact identifier read elsewhere in the header and
    outside that set is a contradiction (empty: a choice between versions
    agrees with no single identifier); absent: no constraint ("GNU General
    Public License" without a version, the bare words "MIT License")."""
    entry = {"family": family, "id": lid, "other": other, "reason": reason}
    if compatible is not None:
        entry["compatible"] = tuple(compatible)
    return entry


def _version_key(v):
    return v if "." in v else v + ".0"


def _versions(flat, regexes):
    found = set()
    for rx in regexes:
        for m in rx.finditer(flat):
            found.add(_version_key(m.group(1)))
    return found


def _identifier_family(expr):
    """Family of an SPDX identifier outside the closed list (GPL-1.0+, MIT-0,
    X11, CC-BY-SA-4.0…): the guard then compares it with the recorded licence
    of that family instead of declaring the notice missing (audit C-19, m1);
    the identifier itself when no family is known."""
    low = expr.lower()
    if low == "x11" or low.startswith("x11-"):
        return "MIT"
    if low.startswith("cc-by-nc-sa"):
        return "CC-BY-NC-SA"
    if low.startswith("cc"):
        return "CC"
    for prefix in ("AGPL", "LGPL", "GPL", "MPL", "MIT", "Apache", "BSD"):
        if low.startswith(prefix.lower()):
            return prefix
    return expr


def _deprecated_entry(dep, where=""):
    """A deprecated GNU SPDX identifier (GPL-3.0, AGPL-3.0+…), on an SPDX line
    or in the text of a notice: to analyse, never recorded; it still agrees
    with the exact identifiers of its version."""
    base = dep.rstrip("+")
    if dep.endswith("+"):
        return _licence_entry(profiles.license_family(dep), compatible=(base + "-or-later",), reason=(
            "deprecated SPDX identifier %s (\"+\" form)%s: never recorded — the exact \"-or-later\" identifier is "
            "recorded only after the holder's confirmation" % (dep, where)))
    return _licence_entry(profiles.license_family(dep), compatible=(base + "-only", base + "-or-later"), reason=(
        "deprecated SPDX identifier %s%s: it does not state the exact licence (\"only\" or \"or later\") — never "
        "recorded" % (dep, where)))


def _spdx_expression_entries(expr):
    """One entry per licence family of an SPDX expression ("GPL-2.0-only OR
    GPL-3.0-only", "MIT OR Apache-2.0", "… WITH an-exception"): a choice or a
    combination, never one identifier — the notice of each family is present
    (never "missing"), it establishes no identifier of the closed list."""
    reason = "SPDX expression %r (several licences or an exception)" % expr
    families, after_with = [], False
    for token in re.sub(r"[()]", " ", expr).split():
        if token.upper() in ("OR", "AND", "WITH"):
            after_with = token.upper() == "WITH"
            continue
        if after_with or not SPDX_SINGLE_ID_RE.match(token):
            after_with = False
            continue
        canonical = profiles.importable_license(token) or profiles.deprecated_license(token)
        family = profiles.license_family(canonical) if canonical else _identifier_family(token)
        if family not in families:
            families.append(family)
    if not families:
        return [_licence_entry("SPDX expression", reason=reason)]
    return [_licence_entry(family, reason=reason, compatible=()) for family in families]


def _spdx_entries(header_text):
    out = []
    for m in SPDX_LINE_RE.finditer(header_text):
        expr = m.group(1).strip()
        if not SPDX_SINGLE_ID_RE.match(expr):
            out.extend(_spdx_expression_entries(expr))
            continue
        known = profiles.importable_license(expr)
        deprecated = profiles.deprecated_license(expr)
        if known:
            out.append(_licence_entry(profiles.license_family(known), known))
        elif deprecated:
            out.append(_deprecated_entry(deprecated))
        else:
            out.append(_licence_entry(_identifier_family(expr), other=expr,
                                      reason="SPDX identifier %s is not in the closed list of recordable "
                                             "licences" % expr))
    return out


def _gnu_entry(flat, family, allowed, several):
    """What a GNU notice of one family establishes (specification §45.4):
    "either version N of the License, or (at your option) any later version"
    gives -or-later, "version N" alone gives -only, any other wording is to
    analyse — several versions or a choice between versions (never one
    identifier, audit C-19 M2), a "later" wording without that clause, a
    deprecated SPDX identifier written in the text, read as on an SPDX line
    (m2)."""
    if several:
        return _licence_entry(family, reason="several GNU licences in the header")
    if family == "LGPL" and GNU_LIBRARY_RE.search(flat):
        return _licence_entry(family, other="LGPL-2.0", reason="GNU Library General Public License (LGPL "
                                                              "2.0) is not in the closed list")
    if GNU_EXCEPTION_RE.search(flat):
        return _licence_entry(family, reason="a licence exception is stated (not in the closed list)")
    versions = _versions(flat, GNU_VERSION_RES)
    choices = list(GNU_VERSION_CHOICE_RE.finditer(flat))
    for m in choices:
        versions.add(_version_key(m.group(1)))
        versions.update(_version_key(v) for v in re.findall(r"\d+(?:\.\d+)?", m.group(2)))
    if not versions:
        return _licence_entry(family, reason="no version stated (\"any version ever published\" may apply)")
    if len(versions) > 1 or choices:
        return _licence_entry(family, compatible=(), reason=(
            "several versions stated (%s): a choice between versions — never one \"-only\" or \"-or-later\" "
            "identifier" % ", ".join(sorted(versions))))
    v = versions.pop()
    if v not in allowed:
        return _licence_entry(family, other="%s-%s" % (family, v), reason="%s version %s is not in the "
                                                                         "closed list" % (family, v))
    only, or_later = "%s-%s-only" % (family, v), "%s-%s-or-later" % (family, v)
    rest = GNU_OR_LATER_CLAUSE_RE.sub(" ", flat)
    if rest != flat:
        if GNU_CHOICE_WORDS_RE.search(rest) or GNU_LATER_WORDING_RE.search(rest):
            return _licence_entry(family, compatible=(or_later,), reason=(
                "the clause \"either version %s of the License, or (at your option) any later version\" and "
                "another choice or \"later\" wording: only / or later not established" % v))
        return _licence_entry(family, or_later)
    if GNU_CHOICE_WORDS_RE.search(rest):
        return _licence_entry(family, compatible=(), reason=(
            "a choice wording (\"either\", \"at your option\") without the clause \"either version N of the "
            "License, or (at your option) any later version\": only / or later not established"))
    deprecated = [d for d in (profiles.deprecated_license(t) for t in GNU_SPDX_TOKEN_RE.findall(rest))
                  if d and profiles.license_family(d) == family]
    if deprecated and not _versions(GNU_SPDX_TOKEN_RE.sub(" ", rest), GNU_VERSION_RES):
        plus = [d for d in deprecated if d.endswith("+")]
        return _deprecated_entry((plus or deprecated)[0], " in the text of the notice")
    if GNU_LATER_WORDING_RE.search(rest):
        return _licence_entry(family, compatible=(or_later,), reason=(
            "a \"later\" wording without the clause \"either version N of the License, or (at your option) any "
            "later version\": only / or later not established"))
    return _licence_entry(family, only)


def _cc_entries(flat):
    refs = set()
    for rx in (CC_URL_REF_RE, CC_MARK_REF_RE):
        for m in rx.finditer(flat):
            refs.add((m.group(1).lower(), m.group(2)))
    names = {"noncommercial": "nc", "sharealike": "sa", "noderivatives": "nd", "noderivs": "nd"}
    for m in CC_TEXT_REF_RE.finditer(flat):
        parts = [p for p in m.group(1).lower().split("-") if p]
        refs.add(("-".join(["by"] + [names[p] for p in parts]), m.group(2)))
    out = []
    if CC_PUBLIC_DOMAIN_RE.search(flat):
        out.append(_licence_entry("CC", other="CC0-1.0", reason="CC0 public-domain dedication: not in the closed "
                                                                "list"))
    for elements, v in sorted(refs):
        if (elements, v) == ("by-nc-sa", "4.0"):
            out.append(_licence_entry("CC-BY-NC-SA", profiles.CC_LICENSE_ID))
        else:
            ident = "CC-%s-%s" % (elements.upper(), v)
            out.append(_licence_entry("CC-BY-NC-SA" if elements == "by-nc-sa" else "CC", other=ident,
                                      reason="Creative Commons variant other than CC BY-NC-SA 4.0 (%s)" % ident))
    if not any(e == "by-nc-sa" for e, _v in refs) and (CC_FAMILY_RE.search(flat) or
                                                       re.search(r"Attribution-NonCommercial-ShareAlike", flat, re.I)):
        out.append(_licence_entry("CC-BY-NC-SA", reason="CC BY-NC-SA without an identifiable version"))
    if not out and CC_ANY_RE.search(flat):
        out.append(_licence_entry("CC", reason="Creative Commons mentioned without an identifiable licence and "
                                               "version"))
    return out


def _text_entries(flat):
    out = []
    if MPL_RE.search(flat):
        versions = _versions(flat, MPL_VERSION_RES)
        if versions == {"2.0"} and MPL_NO_COPYLEFT_EXCEPTION_RE.search(flat):
            out.append(_licence_entry("MPL", other="MPL-2.0-no-copyleft-exception", reason=(
                "MPL 2.0 with the \"Incompatible With Secondary Licenses\" notice: not in the closed list")))
        elif versions == {"2.0"}:
            out.append(_licence_entry("MPL", "MPL-2.0"))
        elif len(versions) == 1:
            v = next(iter(versions))
            out.append(_licence_entry("MPL", other="MPL-%s" % v, reason="Mozilla Public License %s: only 2.0 is "
                                                                       "in the closed list" % v))
        else:
            out.append(_licence_entry("MPL", reason="Mozilla Public License without one identifiable version"))
    if APACHE_RE.search(flat):
        versions = _versions(flat, APACHE_VERSION_RES)
        if versions == {"2.0"}:
            out.append(_licence_entry("Apache", "Apache-2.0"))
        elif len(versions) == 1:
            v = next(iter(versions))
            out.append(_licence_entry("Apache", other="Apache-%s" % v, reason="Apache License %s: only 2.0 is in "
                                                                             "the closed list" % v))
        else:
            out.append(_licence_entry("Apache", reason="Apache License without one identifiable version"))
    gnu = [(family, allowed) for family, rx, allowed in GNU_FAMILIES if rx.search(flat)]
    for family, allowed in gnu:
        out.append(_gnu_entry(flat, family, allowed, len(gnu) > 1))
    if X11_CLAUSE_RE.search(flat):
        out.append(_licence_entry("MIT", other="X11", reason="X11 licence (the Expat text plus a clause on the "
                                                             "X Consortium's name): not the text designated by "
                                                             "the identifier MIT"))
    elif EXPAT_GRANT_RE.search(flat) and EXPAT_NOTICE_RE.search(flat):
        out.append(_licence_entry("MIT", "MIT"))
    elif EXPAT_GRANT_RE.search(flat):
        out.append(_licence_entry("MIT", reason="permission text without its notice condition (MIT-0 variant or "
                                                "truncated text)"))
    elif MIT_NAME_RE.search(flat):
        out.append(_licence_entry("MIT", reason="the term \"MIT License\" is ambiguous (FSF: Expat or X11) — the "
                                                "Expat text or \"SPDX-License-Identifier: MIT\" is needed to "
                                                "propose MIT"))
    bsd_names = {lid for lid, rx in (("BSD-2-Clause", BSD2_NAME_RE), ("BSD-3-Clause", BSD3_NAME_RE))
                 if rx.search(flat)}
    if BSD_TEXT_RE.search(flat):
        if BSD_ADVERTISING_RE.search(flat):
            out.append(_licence_entry("BSD", other="BSD-4-Clause", reason="BSD text with the advertising clause "
                                                                          "(4-clause): not in the closed list"))
        elif not (BSD_SOURCE_COND_RE.search(flat) and BSD_BINARY_COND_RE.search(flat)):
            out.append(_licence_entry("BSD", reason="BSD text incomplete (its two redistribution conditions "
                                                    "are not both present)"))
        elif re.search(r"\bpatent", flat, re.I):
            out.append(_licence_entry("BSD", reason="BSD text with a patent clause (a variant outside the closed "
                                                    "list)"))
        else:
            text_id = "BSD-3-Clause" if BSD_NAME_COND_RE.search(flat) else "BSD-2-Clause"
            if bsd_names and bsd_names != {text_id}:
                out.append(_licence_entry("BSD", reason="BSD name and BSD text disagree"))
            else:
                out.append(_licence_entry("BSD", text_id))
    elif len(bsd_names) == 1:
        out.append(_licence_entry("BSD", bsd_names.pop()))
    elif bsd_names:
        out.append(_licence_entry("BSD", reason="two BSD variants named"))
    elif BSD_ANY_RE.search(flat):
        out.append(_licence_entry("BSD", reason="\"BSD licence\" does not say which variant"))
    out.extend(_cc_entries(flat))
    for name, rx in OTHER_NAMED_LICENCES:
        if rx.search(flat):
            out.append(_licence_entry(name, other=name, reason="%s is not in the closed list of recordable "
                                                               "licences" % name))
    return out


def _merge_licence_entries(entries):
    """One entry per family: the exact identifier when the notices of that
    family agree (an ambiguous notice never overrides an exact one), a
    contradiction when they establish different licences — or when a notice
    agrees only with other identifiers (`compatible`: several versions or a
    choice between versions, a "later" wording, a deprecated identifier of
    another version): never one identifier proposed over it (audit C-19, M2)."""
    by_family, order = {}, []
    for e in entries:
        if e["family"] not in by_family:
            by_family[e["family"]] = []
            order.append(e["family"])
        by_family[e["family"]].append(e)
    merged = []
    for family in order:
        group = by_family[family]
        exact = sorted({e["id"] for e in group if e["id"]} | {e["other"] for e in group if e["other"]})
        clash = [e for e in group if exact and "compatible" in e and exact[0] not in e["compatible"]]
        if len(exact) > 1:
            merged.append(_licence_entry(family, reason="contradictory notices (%s)" % ", ".join(exact)))
        elif clash:
            merged.append(_licence_entry(family, reason="contradictory notices (%s; %s)" % (
                exact[0], "; ".join(e["reason"] for e in clash))))
        elif exact:
            merged.append(next(e for e in group if exact[0] in (e["id"], e["other"])))
        else:
            reasons = []
            for e in group:
                if e["reason"] and e["reason"] not in reasons:
                    reasons.append(e["reason"])
            merged.append(_licence_entry(family, reason="; ".join(reasons) or None))
    return merged


def header_licence_proposal(header_text):
    """Licence PROPOSAL of a header region (onboarding, licence status, guard
    of an imported licence): never a legal proof — the holder confirms.

    Returns {state, proposal, licences, proprietary_mark, reasons, notes}:
      state  `recognized` — one licence of the closed list, exactly
                            (proposal = its SPDX identifier);
             `to-analyse` — custom, ambiguous, deprecated, unrecognized
                            licence, another Creative Commons variant,
                            several or contradictory licences (proposal None);
             `proprietary` — "All Rights Reserved" only (proposal PROPRIETARY:
                            a profile licence when the holder owns the rights);
             `none`       — no licence notice in the header.
    "Version N" alone gives -only, "either version N of the License, or (at
    your option) any later version" gives -or-later, anything else is to
    analyse: several versions or a choice between versions ("version 2 or 3",
    "v2 or v3", an SPDX expression), never one -only or -or-later identifier;
    a "later" wording without that clause; a deprecated SPDX identifier, on an
    SPDX line or in the text of the notice. "MIT" needs the Expat text or its
    SPDX identifier (the term "MIT License" is ambiguous)."""
    spdx = _spdx_entries(header_text)
    flat = _flatten_comments(SPDX_LINE_RE.sub(" ", header_text))
    read = spdx + _text_entries(flat)
    licences = _merge_licence_entries(read)
    proprietary = bool(PROPRIETARY_MARK_RE.search(flat))
    if not licences and LICENCE_STATEMENT_RE.search(flat):
        licences = [_licence_entry("unknown", reason="licence statement not recognized")]
    out = {"state": None, "proposal": None, "licences": licences, "read": read,
           "proprietary_mark": proprietary, "reasons": [], "notes": []}
    if not licences:
        if proprietary:
            out.update(state="proprietary", proposal="PROPRIETARY")
            out["notes"].append("\"All Rights Reserved\" only: a proprietary licence — recorded through a profile "
                                "(PRIVATE, COMMERCIAL, FREE with closed source) when the holder owns the rights; a "
                                "third-party proprietary script is to analyse")
        else:
            out["state"] = "none"
            out["reasons"].append("no licence notice in the header: the holder's own script takes a profile "
                                  "licence; a third-party script without a licence is to analyse (no permission is "
                                  "presumed)")
        return out
    if len(licences) > 1:
        out["state"] = "to-analyse"
        out["reasons"].append("several licences in the header (%s): dual licence, or a third-party portion notice "
                              "— which one applies to the script is a decision of the holder"
                              % ", ".join(_entry_text(e) for e in licences))
        return out
    entry = licences[0]
    if not entry["id"]:
        out["state"] = "to-analyse"
        out["reasons"].append(entry["reason"] or "licence not identified")
        return out
    if proprietary and entry["family"] not in ("MIT", "BSD"):
        out["state"] = "to-analyse"
        out["reasons"].append("\"All Rights Reserved\" and %s in the same header: a contradiction or a "
                              "third-party notice — to analyse" % entry["id"])
        return out
    out.update(state="recognized", proposal=entry["id"])
    if proprietary:
        out["notes"].append("\"All rights reserved\" also appears: customary on the copyright line of %s notices "
                            "— kept" % entry["id"])
    return out


def _entry_text(e):
    return e["id"] or e["other"] or ("%s (%s)" % (e["family"], e["reason"]) if e["reason"] else e["family"])


def describe_proposal(prop):
    """One line describing a licence proposal, for findings and notes."""
    if prop["state"] == "recognized":
        return "%s (proposal: recognized)" % prop["proposal"]
    if prop["state"] == "proprietary":
        return "All Rights Reserved only (proprietary)"
    if prop["state"] == "none":
        return "no licence notice"
    return "to analyse: %s" % "; ".join(prop["reasons"])


def _header_region(source_text):
    """Comment lines before //@version=6 (the license/version header block)."""
    header = []
    for line in _strip_bom(source_text).splitlines():
        if line.startswith("//@version"):
            break
        if line.startswith("//") or not line.strip():
            header.append(line)
        else:
            break
    return header


def _licence_notice_region(source_text):
    """(lines, span) where the EXISTING notice of an imported script is read:
    the header region, then the initial comment block that follows the
    //@version line (blank lines included) up to the first line of code — a
    notice its authors placed right after the directive stays there and is
    still found (audit C-19, m4). `span` = number of source lines covered.
    The header model of a profile licence keeps _header_region."""
    lines = _strip_bom(source_text).splitlines()
    region, i = [], 0
    while i < len(lines) and not lines[i].startswith("//@version"):
        if lines[i].strip() and not lines[i].startswith("//"):
            return region, i                    # code before any directive: the header only
        region.append(lines[i])
        i += 1
    if i == len(lines):
        return region, i
    j = i + 1
    while j < len(lines) and (lines[j].startswith("//") or not lines[j].strip()):
        region.append(lines[j])
        j += 1
    return region, j


def _check_shorttitle(text, add):
    """Named + positional shorttitle policy (see module docstring)."""
    kind, args, start_line, end_line = _declaration_args(text)
    named_hits = find_shorttitle(text)
    in_decl, outside = [], []
    for ln in named_hits:
        if start_line is not None and end_line is not None \
                and start_line <= ln <= end_line:
            in_decl.append(ln)
        else:
            outside.append(ln)

    if in_decl:
        add("no-shorttitle", "BLOCKING",
            "shorttitle/short_title argument in the declaration at line(s) %s"
            % ", ".join(map(str, in_decl)),
            subjects=["named-in-declaration"] * len(in_decl))
    elif kind in ("indicator", "strategy") and args is not None:
        parts = _split_top_level_args(args)
        second = parts[1] if len(parts) > 1 else None
        if second and not NAMED_ARG_RE.match(second):
            if STRING_LITERAL_RE.match(second):
                add("no-shorttitle", "BLOCKING",
                    "positional shorttitle (second argument of %s): %s"
                    % (kind, second),
                    subjects=["positional:%s" % second])
            else:
                add("no-shorttitle", "UNVERIFIABLE",
                    "second positional argument of %s is not a literal (%r) — "
                    "it would be the shorttitle; verify manually, NOT a violation"
                    % (kind, second[:40]))
        else:
            add("no-shorttitle", "OK")
    elif kind is not None and args is None:
        add("no-shorttitle", "UNVERIFIABLE",
            "declaration argument list not parseable — verify manually")
    else:
        add("no-shorttitle", "OK")

    if outside:
        add("shorttitle-outside-declaration", "WARNING",
            "named shorttitle= outside the declaration at line(s) %s — legal "
            "but worth renaming" % ", ".join(map(str, outside)))


def resolve_policy(policy, identity=None):
    """Normalize the header policy argument: None, a legacy distribution
    string, or a dict produced by profiles.header_policy."""
    if policy is None:
        return None
    if isinstance(policy, str):
        return profiles.policy_from_legacy_distribution(policy, identity)
    if isinstance(policy, dict):
        if not policy.get("holder_marks") and identity and identity.get("configured"):
            policy = dict(policy)
            policy["holder_marks"] = [identity["copyright_holder"]] + list(
                identity.get("header_aliases") or [])
            policy["identity_configured"] = True
        return policy
    return None


def _check_worklog_comments(text, add):
    hits = []
    kinds = set()
    for ln, line in enumerate(text.splitlines(), 1):
        comment = comment_text(line)
        if comment is None:
            continue
        for rx, kind in WORKLOG_PATTERNS:
            if rx.search(comment):
                hits.append(ln)
                kinds.add(kind)
                break
    if hits:
        add("no-worklog-comments", "WARNING",
            "%d comment line(s) carry work-log content (%s) — first at line(s) %s; "
            "move history, audit/review narratives and assistant instructions "
            "to the tracking artefacts (master §24.5)"
            % (len(hits), ", ".join(sorted(kinds)), ", ".join(map(str, hits[:3]))))
    else:
        add("no-worklog-comments", "OK")


def _check_header_licence(header_lines, pol, add, notice_lines=None):
    """header-structure, header-copyright and header-consistency of one
    header region under a resolved policy (None = licence model unknown).
    `notice_lines`: where the existing notice of an imported licence is read
    (_licence_notice_region; the header region when None)."""
    header = "\n".join(header_lines)
    notice_lines = header_lines if notice_lines is None else notice_lines
    copyright_idx = {i for i, line in enumerate(header_lines) if "©" in line or "(c)" in line.lower()}
    residues = [(i, m.group(0)) for i, line in enumerate(header_lines)
                for m in profiles.TEMPLATE_RESIDUE_RE.finditer(line)]
    on_copyright = sorted({tok for i, tok in residues if i in copyright_idx})
    elsewhere = sorted({tok for i, tok in residues if i not in copyright_idx})
    lid = (pol or {}).get("license_id")

    imported = (pol or {}).get("origin") == "imported"

    # ---- header-structure: the declared licence, exactly ----------------------
    if elsewhere:
        add("header-structure", "BLOCKING",
            "the header carries unrendered template syntax (%s) — render the header again "
            "(`license render`) and paste it" % ", ".join(elsewhere), subjects=elsewhere)
    elif pol is None:
        add("header-structure", "UNVERIFIABLE",
            "licence profile unknown — header model not checkable")
    elif imported:
        _check_imported_licence("\n".join(notice_lines), pol, add)
    elif lid not in (profiles.CC_LICENSE_ID, "PROPRIETARY"):
        add("header-structure", "UNVERIFIABLE",
            "licence axes of the manifest unknown or invalid (%r) — header model not checkable; "
            "repair SCRIPT.json first (see `scan`)" % (lid,))
    else:
        foreign, statement = header_licences(header)
        flat = _flatten_comments(header)
        cc_family = bool(CC_FAMILY_RE.search(flat))
        proprietary = bool(PROPRIETARY_MARK_RE.search(flat))
        missing = []
        if lid == profiles.CC_LICENSE_ID:
            declared_family = cc_family
            if not CC_MARK_RE.search(flat):
                missing.append(profiles.CC_MARK)
            if not CC_EXACT_URL_RE.search(header):
                missing.append("Creative Commons URL")
            other = foreign + (["proprietary 'All Rights Reserved'"] if proprietary else [])
        else:
            declared_family = proprietary
            if not proprietary:
                missing.append(profiles.PROPRIETARY_MARK)
            other = (["CC BY-NC-SA"] if cc_family else []) + foreign
        if missing:
            detail = "%s header missing: %s" % (lid, ", ".join(missing))
            if declared_family and lid == profiles.CC_LICENSE_ID:
                detail += " (the header must name CC BY-NC-SA 4.0 and %s exactly)" % profiles.CC_URL
            elif other:
                detail += (" — the header carries another licence (%s): licence decision of the "
                           "holder, to analyse; never remove or replace an existing licence notice "
                           "to satisfy the guard (the existing licence of an imported script is "
                           "recorded as such after the holder's confirmation: license.origin "
                           "'imported' — docs/licensing/PROFILES.md)" % ", ".join(other))
            elif statement:
                detail += (" — the header carries a licence statement that is not recognized: to "
                           "analyse (holder's decision); never remove it to satisfy the guard")
            add("header-structure", "BLOCKING", detail, subjects=missing)
        else:
            add("header-structure", "OK", lid)
            if other:
                add("header-consistency", "WARNING",
                    "the %s header also carries %s: a third-party notice to keep, or a "
                    "contradiction to analyse (holder's decision) — never remove a licence "
                    "notice or an attribution to satisfy a check" % (lid, ", ".join(other)))

    # ---- header-copyright: a © line naming the holder -------------------------
    marks = (pol or {}).get("holder_marks") or []
    if on_copyright:
        add("header-copyright", "BLOCKING",
            "the copyright line carries an unrendered template field (%s): set the missing fact "
            "(`license confirm --created-year`, identity with `config set`), render the header "
            "again (`license render`) and paste it" % ", ".join(on_copyright), subjects=on_copyright)
    elif pol is None:
        add("header-copyright", "UNVERIFIABLE",
            "licence profile unknown — copyright line not checkable")
    elif imported:
        # the original authors stay cited: the configured holder is never required
        if any(COPYRIGHT_LINE_RE.search(line) for line in notice_lines):
            add("header-copyright", "OK",
                "imported licence: the copyright lines of the original authors are kept; the configured "
                "holder is not required")
        else:
            add("header-copyright", "WARNING",
                "no copyright line in the header of an imported script: its licence keeps the notices of "
                "the original authors — compare with the imported source; never invent an author (not "
                "blocking: the guard cannot know the original)")
    elif not marks:
        add("header-copyright", "UNVERIFIABLE",
            "copyright holder not configured (pws.config.json identity) — "
            "copyright line not checkable")
    elif not copyright_idx:
        add("header-copyright", "BLOCKING",
            "no copyright line (©) in the header%s" % _invalid_axes_hint(pol), subjects=["©"])
    elif not any(m in header_lines[i] for i in copyright_idx for m in marks):
        detail = "no copyright line (©) names the configured holder (%s)" % " / ".join(marks)
        if any(m in header for m in marks):
            detail += (" — the holder is named elsewhere in the header, not on a © line; a "
                       "third-party © line is an attribution and stays")
        add("header-copyright", "BLOCKING", detail + _invalid_axes_hint(pol), subjects=[marks[0]])
    else:
        add("header-copyright", "OK")


def _invalid_axes_hint(pol):
    """Hint of a copyright finding while the licence axes are invalid: the
    holder requirement may not apply (an imported licence never requires the
    configured holder) — the manifest is repaired first."""
    if (pol or {}).get("license_valid", True):
        return ""
    return (" — the licence axes of SCRIPT.json are invalid: repair them first (`scan`); the existing licence "
            "of an imported script never requires the configured holder, and an attribution is never removed")


def _check_imported_licence(header, pol, add):
    """header-structure / header-consistency of the existing licence of an
    imported script: its notice is still present and coherent with
    `license.id`; never the CC header nor "All Rights Reserved"."""
    lid = pol.get("license_id")
    prop = header_licence_proposal(header)
    seen = ", ".join(_entry_text(e) for e in prop["licences"]) or describe_proposal(prop)
    if pol.get("license_status") != "confirmed" or lid not in profiles.IMPORTABLE_LICENSE_IDS:
        add("header-structure", "UNVERIFIABLE",
            "existing licence of the imported script to analyse (license.status %r, no identifier "
            "recorded): the header notices stay as they are (read in the header: %s) — checked once the "
            "holder records the licence; never remove or replace them" % (pol.get("license_status"), seen))
        return
    family = profiles.license_family(lid)
    mine = [e for e in prop["licences"] if e["family"] == family]
    others = [e for e in prop["licences"] if e["family"] != family]
    read = [e for e in prop["read"] if e["family"] == family]     # every notice of the family, unmerged
    if not mine:
        detail = ("the notice of the recorded licence %s is missing from the header: the existing notice of an "
                  "imported script stays in the source — restore it from the imported source; never replace "
                  "a licence notice nor remove an attribution to satisfy the guard" % lid)
        if others:
            detail += (" (the header carries %s: if that is the licence, the holder corrects the record, "
                       "never the notice)" % ", ".join(_entry_text(e) for e in others))
        add("header-structure", "BLOCKING", detail, subjects=["%s notice" % lid])
        return
    stated = sorted({e["id"] or e["other"] for e in read if (e["id"] or e["other"]) and
                     (e["id"] or e["other"]) != lid})
    if stated:
        add("header-structure", "BLOCKING",
            "the header notice states %s while license.id records %s: incoherent — the record is corrected "
            "after the holder's confirmation (\"only\" and \"or later\" are never assimilated); never change "
            "the notice to satisfy the guard" % (", ".join(stated), lid),
            subjects=["%s != %s" % (lid, s) for s in stated])
        return
    add("header-structure", "OK", "%s (imported licence: existing notice kept)" % lid)
    notes = ["the %s notice does not establish %s exactly (%s)" % (family, lid, e["reason"])
             for e in mine if not e["id"] and e["reason"]]
    if others:
        notes.append("the header also carries %s" % ", ".join(_entry_text(e) for e in others))
    if prop["proprietary_mark"] and family not in ("MIT", "BSD"):
        notes.append("the header also says \"All Rights Reserved\"")
    if notes:
        add("header-consistency", "WARNING",
            "imported licence %s: %s — a third-party notice to keep, or a contradiction to analyse "
            "(holder's decision); never remove a licence notice or an attribution to satisfy a check"
            % (lid, "; ".join(notes)))


def check_source(source_path, policy=None, product_dir=None, identity=None):
    """Run all mechanical checks on one Pine source. Returns findings list.

    `policy`: None (header model not checkable), a legacy distribution
    string, or a dict from profiles.header_policy. `identity`: the result of
    config.identity() — supplies the copyright-holder marks."""
    findings = []

    def add(check, status, detail="", subjects=None):
        finding = {"check": check, "status": status, "detail": detail,
                   "path": str(source_path)}
        if status == "BLOCKING":
            finding["subjects"] = list(subjects) if subjects else [""]
        findings.append(finding)

    p = Path(source_path)
    if not p.is_file():
        add("source-exists", "BLOCKING", "source file missing")
        return findings
    try:
        text = _strip_bom(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        add("source-readable", "BLOCKING", "unreadable: %s" % exc)
        return findings
    add("source-exists", "OK")

    # //@version=6 (master section 12 / 13.1)
    if VERSION_DIRECTIVE_RE.search(text):
        add("version-directive", "OK")
    else:
        add("version-directive", "BLOCKING", "//@version=6 directive missing")

    _check_shorttitle(text, add)

    # Product version in the HEADER region only (master section 6, audit
    # 2026-11-06 item 2): a Version line in the body never satisfies it.
    header_lines = _header_region(text)
    header = "\n".join(header_lines)
    vm = HEADER_VERSION_RE.search(header)
    version = vm.group(1) if vm else None
    if version:
        add("header-version", "OK", "Version: %s" % version)
    else:
        body_hit = HEADER_VERSION_RE.search(text)
        if body_hit:
            ln = text.count("\n", 0, body_hit.start()) + 1
            add("header-version", "BLOCKING",
                "no '// Version: X.Y.Z' line in the header — a Version line exists "
                "at line %d, outside the header region" % ln)
        else:
            add("header-version", "BLOCKING", "no '// Version: X.Y.Z' line in header")

    # Header structure by licence policy (master sections 6.1 / 6.2); the
    # existing notice of an imported licence is also read in the initial
    # comment block after the directive (audit C-19, m4)
    pol = resolve_policy(policy, identity)
    notice_lines, notice_span = header_lines, len(header_lines)
    if (pol or {}).get("origin") == "imported":
        notice_lines, notice_span = _licence_notice_region(text)
    _check_header_licence(header_lines, pol, add, notice_lines)

    # title ASCII when safely extractable (master section 6.4)
    status, title = extract_title(text)
    if status == "EXTRACTED":
        if all(ord(c) < 128 for c in title):
            add("title-ascii", "OK", title)
        else:
            add("title-ascii", "BLOCKING", "title contains non-ASCII characters: %r" % title,
                subjects=[title])
    elif status == "NO_DECL":
        add("title-ascii", "UNVERIFIABLE", "no indicator/strategy/library declaration found")
    else:
        add("title-ascii", "UNVERIFIABLE",
            "title not extractable as a literal — verify manually, NOT a violation")

    # URL policy (master sections 6.1 / 6.2 / 22.3): licence URLs are admitted
    # in comment lines only (CC in the header, third-party notices anywhere in
    # comments — targeted rule of decision D, see the module docstring); any
    # other URL, and any URL in code or user-facing text, is forbidden. The
    # code part and the comment part of a line are examined separately: the
    # same URL in a string and in a trailing comment is never admitted.
    bad_urls = []
    cc_outside_header = []
    contacts = []
    header_line_count = notice_span      # the licence header: the notice region of an imported licence
    declared = set((pol or {}).get("allowed_urls") or [])
    lines = text.splitlines()
    blocks = _comment_blocks(lines)
    for idx, line in enumerate(lines):
        ln = idx + 1
        comment = comment_text(line)
        code = line if comment is None else line[:len(line) - len(comment) - 2]
        for m in URL_RE.finditer(code):
            bad_urls.append((ln, _clean_url(m.group(0))))
        for literal in _string_literals(code):
            contacts.extend((ln, hit) for hit in _contacts_in(literal))
        if comment is None:
            continue
        for m in URL_RE.finditer(comment):
            raw = m.group(0)
            u = _clean_url(raw)
            if u in declared or raw in declared:
                # the product's DECLARED legal reference (license.terms_url):
                # an exact match in a comment, never a domain-wide allowance
                continue
            kind = _licence_url_kind(u)
            if kind == "body":
                if CC_LICENSES_URL_RE.match(u) and ln > header_line_count:
                    cc_outside_header.append((ln, u))
                continue
            if kind == "repo":
                context = blocks[idx] if blocks[idx] is not None else comment
                if NOTICE_WORDS_RE.search(context.replace(raw, " ")):
                    continue
            bad_urls.append((ln, u))
    if bad_urls:
        add("no-promo-urls", "BLOCKING",
            "forbidden URL(s): %s — admitted only: a licence URL in a comment (licence body, "
            "public-domain tool, SPDX, or the licence file of a source repository in a licence "
            "notice) and the declared terms_url; never remove a licence notice or an attribution "
            "to satisfy the guard" % "; ".join("l.%d %s" % x for x in bad_urls),
            subjects=[u for _, u in bad_urls])
    else:
        add("no-promo-urls", "OK")
    if cc_outside_header:
        add("cc-url-placement", "WARNING",
            "CC URL outside the licence header at line(s) %s (master §22.3)" %
            ", ".join(str(ln) for ln, _ in cc_outside_header))
    if contacts:
        add("no-promo-contacts", "WARNING",
            "user-facing text carries a web address without scheme or an e-mail address (%s): "
            "links and contacts are forbidden in user-facing text (master §22.3) — check it "
            "(heuristic, never blocking)" % "; ".join("l.%d %s" % x for x in contacts[:5]))

    _check_worklog_comments(text, add)

    # Product version echoed in controllable user-facing files (spec section
    # 56). Physically confined sweep: no symlink following, no reads outside
    # the product root.
    if version and product_dir is not None:
        echoes = []
        for md in sorted(core.iter_paths_within(product_dir)):
            if md.suffix != ".md":
                continue
            try:
                if version in md.read_text(encoding="utf-8"):
                    echoes.append(str(md.relative_to(product_dir)))
            except (OSError, UnicodeDecodeError, ValueError):
                continue
        if echoes:
            add("version-only-in-source", "WARNING",
                "product version %s appears in: %s" % (version, ", ".join(echoes)))
        else:
            add("version-only-in-source", "OK")

    return findings


def blocking_identities(findings):
    """Position-independent identities of the BLOCKING findings, counted:
    {(check, subject): occurrences}. A finding without `subjects` counts as
    one anomaly with an empty subject."""
    counts = {}
    for f in findings:
        if f.get("status") != "BLOCKING":
            continue
        for subject in (f.get("subjects") or [""]):
            key = (f["check"], subject)
            counts[key] = counts.get(key, 0) + 1
    return counts


def unverifiable_checks(findings):
    """Checks the guard could NOT evaluate in the given context."""
    return sorted({f["check"] for f in findings if f.get("status") == "UNVERIFIABLE"})


def policy_for_manifest(manifest, identity=None):
    """Header policy derived from a RAW manifest dict (v2 explicit axes, v1
    legacy distribution). None when the manifest carries no usable model.
    `guard_product` no longer uses it: it derives the policy from the
    validated manifest (audit C-11), exactly as the Stop hook does."""
    if not isinstance(manifest, dict):
        return None
    sv = manifest.get("schema_version")
    if sv in (2, 3) and isinstance(manifest.get("license"), dict) \
            and manifest.get("profile") in profiles.PROFILES:
        return profiles.header_policy(manifest["profile"], manifest["license"], identity)
    dist = manifest.get("distribution")
    if isinstance(dist, str):
        return profiles.policy_from_legacy_distribution(dist, identity)
    return None


def guard_product(product_dir, identity=None):
    """Guard a product root: manifest coherence + source checks. Types are
    validated before use (audit F8) — never a crash on a malformed manifest;
    a source path escaping the product root is refused, never read.

    The manifest goes through the SAME checks as the scan and the Stop hook
    (scan.validate_manifest, audit C-11): a BROKEN manifest is BLOCKING here,
    never "OK", and the header policy comes from the validated licence axes
    (an invalid licence block leaves the header model not checkable, and an
    invalid terms_url is never admitted as the declared legal reference)."""
    product_dir = Path(product_dir)
    findings = []
    if product_dir.is_symlink():
        findings.append({"check": "product-root", "status": "BLOCKING",
                         "detail": "product root is a symlink — identity not "
                                   "establishable, nothing read (spec 6.1.5)",
                         "path": str(product_dir)})
        return findings
    manifest, err = core.read_json(product_dir / "SCRIPT.json")
    if err:
        findings.append({"check": "manifest", "status": "BLOCKING",
                         "detail": "SCRIPT.json %s" % err, "path": str(product_dir)})
        return findings
    if not isinstance(manifest, dict):
        findings.append({"check": "manifest", "status": "BLOCKING",
                         "detail": "SCRIPT.json is not a JSON object (got %s)"
                                   % type(manifest).__name__,
                         "path": str(product_dir)})
        return findings
    from . import scan   # local import: the scan owns the manifest checks
    _votes, _src, profile, lic, _pub, checked = scan.validate_manifest(product_dir.name, product_dir, manifest)
    # source problems are reported by the source checks below, never twice
    broken = [f for f in checked if f["severity"] == "BROKEN" and not f["code"].startswith("SOURCE_")]
    warned = sorted({f["code"] for f in checked if f["severity"] == "WARNING"})
    if broken:
        findings.append({"check": "manifest", "status": "BLOCKING",
                         "detail": "SCRIPT.json is BROKEN (same checks as `scan`): %s"
                                   % "; ".join("%s: %s" % (f["code"], f["detail"]) for f in broken),
                         "path": str(product_dir), "subjects": sorted({f["code"] for f in broken})})
    else:
        findings.append({"check": "manifest", "status": "OK",
                         "detail": ("scan warnings: %s" % ", ".join(warned)) if warned else "",
                         "path": str(product_dir)})
    source = manifest.get("source")
    policy = profiles.header_policy(profile, lic, identity) if profile else None
    if isinstance(source, str) and source and not Path(source).is_absolute():
        candidate = product_dir / source
        if not core.is_within(product_dir, candidate):
            findings.append({"check": "source-exists", "status": "BLOCKING",
                             "detail": "declared source resolves outside the product "
                                       "root (traversal or symlink) — not read",
                             "path": str(product_dir), "subjects": [source]})
            return findings
        findings.extend(check_source(candidate, policy, product_dir, identity))
    else:
        findings.append({"check": "source-exists", "status": "BLOCKING",
                         "detail": "manifest has no usable relative source",
                         "path": str(product_dir), "subjects": [""]})
    return findings
