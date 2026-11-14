# SPDX-License-Identifier: Apache-2.0
"""Master-standard derivatives: INDEX generation and freshness status.

INDEX.md is derived from the REAL headings of the master (never invented).
Freshness rule (spec section 12.4): recorded SHA != current SHA => STALE.
TRACEABILITY.md freshness uses the same SHA rule but its regeneration is a
semantic analysis — this module only reports its staleness, never rewrites it.
"""
import datetime
import re
from pathlib import Path

from . import core

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
SHA_LINE_RE = re.compile(r"SHA-256[^0-9a-f]*([0-9a-f]{64})")

# Routing: main operational consumers per top-level master section number.
# Derived static map — regenerated with INDEX; not a second authority.
CONSUMERS = {
    0: "all workflows", 1: "pine-develop, pine-review", 2: "pine-develop, pine-audit",
    3: "pine-research", 4: "CLAUDE.md, config (language), all skills",
    5: "pine-new, pine-onboard, scan, profiles, licensing",
    6: "guard, licensing, pine-new, pine-release", 7: "pine-research", 8: "pine-research",
    9: "pine-develop, pine-audit, pine-onboard, pws-pine-cartographer", 10: "pine-develop",
    11: "pine-develop", 12: "pine-develop, guard", 13: "pine-develop, pine-review",
    14: "pine-review", 15: "pine-develop", 16: "pine-develop, pine-review",
    17: "pine-review", 18: "pine-new", 19: "pine-new, pine-review",
    20: "pine-develop, pine-review", 21: "pine-develop", 22: "pine-review, pine-release",
    23: "pine-develop, pine-review", 24: "pine-develop, pine-review, guard (no-worklog-comments)",
    25: "pine-develop, pine-review", 26: "pine-develop, pine-review",
    27: "pine-develop, tv-validate", 28: "pine-develop, pine-research",
    29: "pine-new, pine-review", 30: "pine-new, pine-review",
    31: "pine-release, guard", 32: "pine-release, pine-github", 33: "pine-docs, pine-release",
    34: "pine-release, tv-validate", 35: "pine-release, tv-validate",
    36: "pine-review, pine-audit", 37: "pine-review, guard", 38: "pine-develop",
    39: "pine-new", 40: "tv-validate", 41: "pine-release, pine-github",
    42: "pine-develop, pine-release",
}

TOP_NUM_RE = re.compile(r"^(\d+)\.")


def parse_headings(text):
    """Return [(level, title, line_number)] from real markdown headings."""
    in_fence = False
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2), i))
    return out


def _keywords(title):
    words = re.findall(r"[A-Za-zÀ-ÿ0-9_.`/-]{4,}", title)
    stop = {"with", "without", "from", "into", "their", "that", "this", "when", "what", "only",
            "each", "every", "than", "then", "over", "under", "about", "after", "before",
            # French words, kept for a master written in French
            "pour", "avec", "sans", "dans", "les", "des", "leur", "tout", "tous", "toute"}
    return ", ".join(w.strip("`").lower() for w in words if w.lower() not in stop)[:120]


def generate_index(root, today=None):
    """Generate standards/INDEX.md from the master's real headings."""
    root = Path(root)
    master = root / core.STANDARD_REL
    text = master.read_text(encoding="utf-8")
    sha = core.sha256_file(master)
    total_lines = text.count("\n") + 1
    headings = parse_headings(text)
    today = today or datetime.date.today().isoformat()

    lines = [
        "# INDEX — PINE SCRIPT V6 STANDARD",
        "",
        "Status: derived, non-normative (spec §12). Generated automatically from the real headings of the master.",
        "Never edit by hand: regenerate with `python3 -m tools.pws_workspace standard-index`.",
        "",
        "Master: `standards/PINE_SCRIPT_V6_STANDARD.md`",
        "SHA-256: %s" % sha,
        "Generated on: %s" % today,
        "",
        "Freshness rule: if the SHA of the master differs from the one above, this index is STALE",
        "and must no longer be used as a reliable representation (`standard-status` checks it).",
        "",
        "| Level | Section | Lines | Routing keywords | Main consumers |",
        "|---|---|---|---|---|",
    ]
    for idx, (level, title, line_no) in enumerate(headings):
        end = headings[idx + 1][2] - 1 if idx + 1 < len(headings) else total_lines
        consumers = ""
        m = TOP_NUM_RE.match(title)
        if level == 2 and m:
            consumers = CONSUMERS.get(int(m.group(1)), "")
        lines.append("| %d | %s | %d–%d | %s | %s |" % (
            level, title.replace("|", "\\|"), line_no, end, _keywords(title), consumers))
    lines.append("")
    core.atomic_write_text(root / core.INDEX_REL, "\n".join(lines) + "\n")
    return {"sha256": sha, "headings": len(headings), "path": str(root / core.INDEX_REL)}


def _recorded_sha(path):
    data, err = None, None
    p = Path(path)
    if not p.is_file():
        return None, "missing"
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "unreadable: %s" % exc
    m = SHA_LINE_RE.search(text)
    if not m:
        return None, "no recorded SHA-256"
    return m.group(1), None


def standard_status(root):
    """Freshness of the master, INDEX and TRACEABILITY."""
    root = Path(root)
    master = root / core.STANDARD_REL
    out = {"master_present": master.is_file(), "master_sha256": None,
           "index": "MISSING", "traceability": "MISSING"}
    if not out["master_present"]:
        return out
    sha = core.sha256_file(master)
    out["master_sha256"] = sha
    for key, rel in (("index", core.INDEX_REL), ("traceability", core.TRACEABILITY_REL)):
        recorded, err = _recorded_sha(root / rel)
        if err == "missing":
            out[key] = "MISSING"
        elif err:
            out[key] = "UNREADABLE"
        else:
            out[key] = "CURRENT" if recorded == sha else "STALE"
    return out
