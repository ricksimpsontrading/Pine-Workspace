# SPDX-License-Identifier: Apache-2.0
"""Licence profiles and `SCRIPT.json` schema 3 — single owner of the
profile/licence semantics shared by scan, guard, menu, templates and
migration.

Three usage profiles are DEFAULT CONFIGURATIONS (never quality levels); the
axes stay separate and individually overridable in the manifest:

  profile                   FREE | PRIVATE | COMMERCIAL
  license.id / grant        CC-BY-NC-SA-4.0 / cc  |  PROPRIETARY / none, free-use, eula
                            | existing licence of an imported script / license (see below)
  license.source_visibility public | closed        (is the source code published / delivered?)
  license.access            free | paid | restricted
  license.terms_ref         relative path to the rendered terms inside the product root, or null
  license.terms_url         declared legal reference URL of the product (https), or null
  license.origin            profile (default when absent) | imported
  license.status            imported licence only: confirmed | to-analyse
  license.documents         imported licence only: original legal documents declared by
                            the holder (list of paths; [] = none; absent = not declared)
  publication.state         unpublished | published | null (unknown — to confirm)
  publication.privacy       public | private | null  (TradingView publication privacy)
  publication.mode          open | protected | invite-only | null (TradingView script mode)

Four notions stay distinct: the usage profile, the licence (`license.id`,
exact), the visibility of the source, and the TradingView publication
(state, privacy, mode).

TradingView publication has TWO independent dimensions (writing/publishing):
the PRIVACY of the publication (public listing or private) and the MODE of
the script (open: source visible; protected: source hidden; invite-only:
source hidden and access granted per user). A private publication can be
open, protected or invite-only. Schema 2 conflated them in one string; the
2026-11-06 intervention separates them (schema 3).

Derived values (documented, never persisted): `profile_variant` FREE_CLOSED
= FREE profile under a proprietary free-use grant; a `published` state with
unknown privacy or mode is reported as incomplete. Nothing else is derived:
coherence rules check the axes against each other instead. A profile whose
licence axes describe another regime (FREE under an EULA or without grant,
PRIVATE or FREE with paid access, COMMERCIAL without EULA) is signalled
(PROFILE_AXES_DIVERGENCE, warning): the licence documents and the header
checks follow the licence axes. An attached terms document that is still a
draft keeps the terms in draft status (EULA_DRAFT / TERMS_DRAFT).

Licences of imported scripts (decision of the holder of 2026-11-13, audit
C-19; compatible extension of schema 3, `schema_version` unchanged, every
earlier manifest valid and unchanged). The profiles stay the configurations
proposed for new projects (licences CC-BY-NC-SA-4.0 and PROPRIETARY, origin
`profile`, the default when `license.origin` is absent); they never force
the licence of an imported script. An existing script keeps its licence,
its texts and its attributions: `license.origin` = `imported` with
  - `license.status` = `confirmed` and the EXACT SPDX identifier confirmed by
    the holder, from a closed list (IMPORTABLE_LICENSE_IDS: CC-BY-NC-SA-4.0,
    grant `cc`, and IMPORTED_LICENSE_IDS, grant `license` = rights defined by
    the licence itself); "only" and "or later" are never assimilated and the
    deprecated ambiguous identifiers (GPL-3.0…) are never recorded;
  - or `license.status` = `to-analyse` and `license.id` = null: a licence
    that is custom, ambiguous, unrecognized or outside the closed list. The
    state is explicit (LICENSE_TO_ANALYSE warning, never a mute BROKEN): it
    never stops current work, and it keeps release preparation and export
    from treating the licence as settled (`license_release_blockers`).
A header detection is a PROPOSAL for the holder (guard.header_licence_proposal),
never a legal proof; nothing is recorded without the holder's confirmation.

Original legal documents of an imported script (holder's request of
2026-11-14; same compatible extension, `schema_version` unchanged, every
earlier manifest valid and unchanged): `license.documents` lists the files
that accompany the existing licence (licence text, NOTICE, attributions),
declared by the holder — they travel with the script, verbatim, when it is
exported. A declared document lies at the product root or directly under
`release/` with a legal-document name (LICENSE / LICENCE, COPYING,
COPYRIGHT, NOTICE, PATENTS, AUTHORS, CREDITS, ATTRIBUTION, CONTRIBUTORS,
THIRD_PARTY_NOTICES and their variants: `LICENSE.md`, `LICENSE-MIT`,
`COPYING.LESSER`, `NOTICE.txt`…), or directly under `LICENSES/` (REUSE
layout: `LICENSES/MIT.txt`). A file with such a name anywhere in the product
(internal folders excepted), every entry of `LICENSES/`, a folder with such a
name, or a `release/` / `LICENSES/` that is a link, is a CANDIDATE
(legal_document_candidates): never exported because of its name alone,
never left out silently either — the export of an imported script waits
until every candidate is declared (or, when it cannot be declared where it
is, moved by the holder) and every declared document is present and
accepted. `[]` records that no separate legal document accompanies the
script. The recorded SPDX identifier names the licence; it does not
establish by itself which documents and notices a redistribution requires.
Possible conflicts (copyleft licence with a closed source, a protected or
invite-only mode, paid access; permissive licence whose notice must be
kept) are warnings to analyse (IMPORTED_LICENSE_CONFLICT), never an
automatic block presented as a legal conclusion. One mechanical rule stays
above them: a CC BY-NC-SA 4.0 licence, imported or not, publishes its source
(LICENSE_VISIBILITY_MISMATCH, BROKEN) — a closed source under it is never
also reported as a conflict to analyse.

Legacy schemas are read-compatible and migrated EXPLICITLY (never guessed):
  v1  `distribution` free-open-source → FREE defaults, paid-closed-source →
      COMMERCIAL defaults; publication state unknown (null).
  v2  `license.publication` string → publication object: the known part is
      kept (privacy public for the three public modes, privacy private for
      tradingview-private with an UNKNOWN mode), the state is unknown unless
      the value was `unpublished`.
"""
import datetime
import os
import re
import stat
import unicodedata
from pathlib import Path

from . import core, version

PROFILES = ("FREE", "PRIVATE", "COMMERCIAL")
LICENSE_IDS = ("CC-BY-NC-SA-4.0", "PROPRIETARY")      # licences of the profiles (origin `profile`)
GRANTS = ("cc", "none", "free-use", "eula", "license")
LICENSE_ORIGINS = ("profile", "imported")
IMPORTED_STATUSES = ("confirmed", "to-analyse")
SOURCE_VISIBILITIES = ("public", "closed")
ACCESS_MODES = ("free", "paid", "restricted")
PUBLICATION_STATES = ("unpublished", "published")
PUBLICATION_PRIVACIES = ("public", "private")
PUBLICATION_MODES = ("open", "protected", "invite-only")

CC_LICENSE_ID = "CC-BY-NC-SA-4.0"
CC_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CC_MARK = "CC BY-NC-SA"
PROPRIETARY_MARK = "All Rights Reserved"
HTTPS_URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+(?:/[^\s'\"<>]*)?$")
# Banner of a rendered document that is still incomplete (licensing.render);
# shared here so that the manifest checks recognize an attached draft.
DRAFT_MARKER = "DRAFT — not for publication"
# Residual template syntax in a document: an unfilled {{KEY}} or an optional block.
TEMPLATE_RESIDUE_RE = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}|\[\[[?!][A-Z0-9_]+:")
# Existing licences an IMPORTED script can record (decision of the holder of
# 2026-11-13, audit C-19): a closed list of exact SPDX identifiers whose rights
# are defined by the licence itself (grant `license`). "MIT" is the SPDX
# identifier of the Expat text; "only" and "or later" are distinct identifiers.
IMPORTED_LICENSE_IDS = (
    "MPL-2.0", "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later",
)
# Every licence an imported script can record: CC BY-NC-SA 4.0 too (a third-party
# script under it keeps grant `cc`), plus the closed list above. Anything else —
# custom, ambiguous, unrecognized licence, another Creative Commons variant — is
# recorded as `to-analyse` (license.id null), never replaced automatically.
IMPORTABLE_LICENSE_IDS = (CC_LICENSE_ID,) + IMPORTED_LICENSE_IDS
# Deprecated SPDX identifiers of the GNU licences: never recorded (they state
# neither "only" nor "or later", or use the deprecated "+" form) — the five
# identifiers and their five "+" forms, AGPL-3.0+ included (audit C-19, m1).
DEPRECATED_LICENSE_IDS = (
    "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0",
    "GPL-2.0+", "GPL-3.0+", "LGPL-2.1+", "LGPL-3.0+", "AGPL-3.0+",
)
PERMISSIVE_LICENSE_IDS = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause")
# copyleft: the source of the covered files must stay available to recipients
# (MPL-2.0 per file; CC BY-NC-SA 4.0: share-alike and non-commercial)
COPYLEFT_LICENSE_IDS = tuple(i for i in IMPORTABLE_LICENSE_IDS if i not in PERMISSIVE_LICENSE_IDS)
# Licence grants each profile describes (the profile is a starting
# configuration; the axes stay adjustable, a divergence is signalled).
PROFILE_GRANTS = {"FREE": ("cc", "free-use"), "PRIVATE": ("none",), "COMMERCIAL": ("eula",)}

LICENSE_DEFAULTS = {
    "FREE": {"id": "CC-BY-NC-SA-4.0", "grant": "cc", "source_visibility": "public", "access": "free"},
    "PRIVATE": {"id": "PROPRIETARY", "grant": "none", "source_visibility": "closed", "access": "restricted"},
    "COMMERCIAL": {"id": "PROPRIETARY", "grant": "eula", "source_visibility": "closed", "access": "paid"},
}
FREE_CLOSED_LICENSE = {"id": "PROPRIETARY", "grant": "free-use", "source_visibility": "closed", "access": "free"}
PUBLICATION_DEFAULTS = {
    "FREE": {"state": "unpublished", "privacy": "public", "mode": "open"},
    "FREE_CLOSED": {"state": "unpublished", "privacy": "public", "mode": "protected"},
    "PRIVATE": {"state": "unpublished", "privacy": None, "mode": None},
    "COMMERCIAL": {"state": "unpublished", "privacy": "public", "mode": "invite-only"},
}

LEGACY_DISTRIBUTION_TO_PROFILE = {"free-open-source": "FREE", "paid-closed-source": "COMMERCIAL"}
# schema-2 publication string → (state, privacy, mode); None = unknown, kept
# unknown. The three mode values never recorded the privacy of the
# publication: it is NOT deduced (corrected 2026-11-06 after independent
# verification); `tradingview-private` recorded the privacy, not the mode.
LEGACY_PUBLICATION_V2 = {
    "tradingview-open": (None, None, "open"),
    "tradingview-protected": (None, None, "protected"),
    "tradingview-invite-only": (None, None, "invite-only"),
    "tradingview-private": (None, "private", None),
    "unpublished": ("unpublished", None, None),
}
UNKNOWN_PUBLICATION = {"state": None, "privacy": None, "mode": None}

V3_REQUIRED_KEYS = {"schema_version", "id", "source", "script_kind", "profile", "license", "publication"}
V3_OPTIONAL_KEYS = {"migration"}
LICENSE_REQUIRED_KEYS = {"id", "grant", "source_visibility", "access"}
LICENSE_OPTIONAL_KEYS = {"copyright_holder", "created_year", "terms_ref", "terms_url"}
# compatible extension of schema 3 (2026-11-13, audit C-19; `documents` 2026-11-14):
# optional, and kept in the validated licence only when the manifest records
# them, so that the validated view of every earlier manifest stays exactly what it was
LICENSE_IMPORT_KEYS = ("origin", "status", "documents")
PUBLICATION_KEYS = {"state", "privacy", "mode"}
# original legal documents of an imported script (license.documents, 2026-11-14):
# where they may lie, which names are legal-document names, what is never one
LEGAL_DOCUMENT_FOLDERS = ("release", "LICENSES")      # besides the product root
REUSE_LICENSES_FOLDER = "LICENSES"                     # REUSE layout: licence texts named after their identifier
# licence texts, notices and attributions (cross-check of 2026-11-14: AUTHORS, PATENTS, third-party notices…)
LEGAL_DOCUMENT_NAME_RE = re.compile(
    r"^(?:LICEN[CS]ES?|COPYING|COPYRIGHTS?|NOTICES?|PATENTS?|AUTHORS?|CREDITS?|ATTRIBUTIONS?|CONTRIBUTORS?|"
    r"UNLICENSE|THIRD[-_ ]?PARTY[-_ ]?(?:NOTICES?|LICEN[CS]ES?))(?![A-Za-z])", re.I)
REUSE_FILE_SUFFIXES = (".txt", ".md", ".markdown", ".rst", ".html", ".htm")
NOT_LEGAL_DOCUMENT_SUFFIXES = (".pine", ".json", ".lock")
PWS_INTERNAL_NAMES = ("script.json", "claude.md", "architecture.md", "decisions.md", "product.md")
INTERNAL_FOLDERS = ("research", "validation", "tests")   # internal, never exported: not searched for candidates
FILE_NAME_FORBIDDEN_RE = re.compile(r"[\x00-\x1f\x7f\\/]")
FILE_NAME_MAX_BYTES = 255
LEGAL_PATH_MAX_BYTES = 1024
# invisible or reordering characters (format, control, private use, separators): a name must show what it is
HIDDEN_CHAR_CATEGORIES = ("Cc", "Cf", "Co", "Cs", "Zl", "Zp")


def default_license(profile, closed_source=False):
    """Default licence axes for a profile (FREE + closed_source → free-use)."""
    if profile == "FREE" and closed_source:
        return dict(FREE_CLOSED_LICENSE)
    return dict(LICENSE_DEFAULTS[profile])


def default_publication(profile, closed_source=False):
    key = "FREE_CLOSED" if (profile == "FREE" and closed_source) else profile
    return dict(PUBLICATION_DEFAULTS[key])


def profile_variant(profile, lic):
    """Display variant: FREE_CLOSED for a FREE profile under a proprietary
    free-use grant, else the profile itself (derived, never persisted)."""
    if profile == "FREE" and isinstance(lic, dict) and lic.get("id") == "PROPRIETARY":
        return "FREE_CLOSED"
    return profile


# ---- licence of an imported script (2026-11-13, audit C-19) ---------------------

def license_origin(lic):
    """`imported` for the existing licence of an imported script, `profile`
    otherwise (absent or null origin = a licence configured by a profile)."""
    return "imported" if isinstance(lic, dict) and lic.get("origin") == "imported" else "profile"


def is_imported(lic):
    return license_origin(lic) == "imported"


def imported_status(lic):
    """`confirmed` / `to-analyse` for an imported licence, None otherwise."""
    return lic.get("status") if is_imported(lic) else None


def importable_license(value):
    """Canonical identifier of a licence an imported script can record
    (case-insensitive exact SPDX identifier of the closed list), else None."""
    if not isinstance(value, str):
        return None
    wanted = value.strip().lower()
    return next((lid for lid in IMPORTABLE_LICENSE_IDS if lid.lower() == wanted), None)


def deprecated_license(value):
    """Canonical deprecated GNU identifier (never recorded), else None."""
    if not isinstance(value, str):
        return None
    wanted = value.strip().lower()
    return next((lid for lid in DEPRECATED_LICENSE_IDS if lid.lower() == wanted), None)


def deprecated_reason(lid):
    """Why a deprecated GNU identifier is never recorded."""
    if lid.endswith("+"):
        return "%s is a deprecated SPDX identifier (\"+\" form)" % lid
    return "%s is a deprecated and ambiguous SPDX identifier (neither \"only\" nor \"or later\")" % lid


# name kept for the callers of the 2026-11-13 corrections
recognized_license = importable_license


def license_family(lid):
    """Family of a licence identifier, used to match a header notice: MPL,
    MIT, Apache, BSD, GPL, LGPL, AGPL, CC-BY-NC-SA, PROPRIETARY; None when
    unknown."""
    if not isinstance(lid, str):
        return None
    if lid == CC_LICENSE_ID:
        return "CC-BY-NC-SA"
    if lid == "PROPRIETARY":
        return "PROPRIETARY"
    for prefix in ("AGPL", "LGPL", "GPL", "MPL", "MIT", "Apache", "BSD"):
        if lid.startswith(prefix):
            return prefix
    return None


def imported_grant(lid):
    """Grant of an imported licence: `cc` for CC BY-NC-SA 4.0 (rule of that
    licence), `license` (rights defined by the licence itself) otherwise."""
    return "cc" if lid == CC_LICENSE_ID else "license"


def _license_id_problem(value, origin, status):
    """Detail of a `license.id` that the licence block cannot record, or None."""
    imported = origin == "imported"
    if imported and status == "to-analyse":
        if value is None:
            return None
        return ("license.id %r with license.status 'to-analyse': an imported licence to analyse records "
                "no identifier (license.id null) — record the exact identifier with license.status "
                "'confirmed' once the holder has confirmed it" % (value,))
    if imported and status == "confirmed" and value in IMPORTABLE_LICENSE_IDS:
        return None
    if not imported and value in LICENSE_IDS:
        return None
    if imported and status not in IMPORTED_STATUSES:
        return None     # reported once, on license.status
    allowed = list(IMPORTABLE_LICENSE_IDS) if imported else list(LICENSE_IDS)
    detail = "license.id %r not in %s" % (value, allowed)
    deprecated = deprecated_license(value)
    known = importable_license(value)
    if imported and value is None:
        return ("license.id null with license.status 'confirmed': record the exact identifier the holder "
                "confirmed (closed list: %s), or license.status 'to-analyse'" % ", ".join(IMPORTABLE_LICENSE_IDS))
    if deprecated:
        return detail + (" — %s: never recorded; read the notice (\"version N\" alone: -only; \"or (at your "
                         "option) any later version\": -or-later) and record the exact identifier confirmed by "
                         "the holder with license.origin 'imported', or license.status 'to-analyse' with "
                         "license.id null — never relicensed automatically (docs/licensing/PROFILES.md)"
                         % deprecated_reason(deprecated))
    if imported and value == "PROPRIETARY":
        return detail + (" — PROPRIETARY is the licence of the PRIVATE, COMMERCIAL and FREE-with-closed-"
                         "source profiles (license.origin 'profile'); the existing licence of an imported "
                         "script is one of the closed list, or 'to-analyse' (holder's decision)")
    if known and not imported:
        return detail + (" — %s is recorded only as the existing licence of an imported script: "
                         "license.origin 'imported', license.status 'confirmed', license.id %r, "
                         "license.grant %r, after the holder's confirmation — keep the existing licence and "
                         "its notices, never relicense automatically (docs/licensing/PROFILES.md)"
                         % (known, known, imported_grant(known)))
    if known:
        return detail + " — record the exact identifier %r (holder's confirmation)" % known
    return detail + (" — licence not recognized (not in the closed list of recordable licences): to "
                     "analyse — record license.origin 'imported', license.status 'to-analyse', "
                     "license.id null; never replaced automatically (holder's decision, "
                     "docs/licensing/PROFILES.md)")


def _full_license(lic):
    out = {"copyright_holder": None, "created_year": None, "terms_ref": None, "terms_url": None}
    out.update(lic)
    return out


def derive_from_legacy(distribution):
    """(profile, license, publication) derived from a v1 distribution, or
    (None, None, None). Schema 1 recorded only the distribution: the licence
    axes are its documented meaning; the publication (state, privacy, mode)
    is entirely UNKNOWN — profile defaults are proposals for new projects,
    never historical facts of a migrated one."""
    profile = LEGACY_DISTRIBUTION_TO_PROFILE.get(distribution)
    if profile is None:
        return None, None, None
    lic = _full_license(default_license(profile))
    lic["derived_from_v1"] = distribution
    return profile, lic, dict(UNKNOWN_PUBLICATION)


def publication_from_v2(value):
    """Schema-2 publication string → publication object (known parts only)."""
    if value not in LEGACY_PUBLICATION_V2:
        return None
    state, privacy, mode = LEGACY_PUBLICATION_V2[value]
    return {"state": state, "privacy": privacy, "mode": mode, "derived_from_v2": value}


def imported_license_conflicts(lic, pub):
    """Possible conflicts between an imported licence and the other axes —
    facts to analyse by the holder, never a legal conclusion: a copyleft
    licence with a closed source, a source-hiding TradingView mode or paid
    access; a permissive licence whose notice must travel with the work.
    A closed source under CC BY-NC-SA 4.0 is not one of them: the mechanical
    rule of that licence makes the manifest BROKEN (coherence_problems,
    LICENSE_VISIBILITY_MISMATCH), never also a point to analyse (audit C-19, m3)."""
    if not is_imported(lic) or lic.get("id") not in IMPORTABLE_LICENSE_IDS:
        return []
    lid = lic["id"]
    pub = pub if isinstance(pub, dict) else {}
    hiding = []
    if lic.get("source_visibility") == "closed" and lid != CC_LICENSE_ID:
        hiding.append("closed source (source_visibility 'closed')")
    if pub.get("mode") in ("protected", "invite-only"):
        hiding.append("TradingView mode %r (source hidden)" % pub["mode"])
    paid = lic.get("access") == "paid"
    out = []
    if lid in COPYLEFT_LICENSE_IDS:
        for what in hiding:
            out.append("copyleft licence %s with a %s" % (lid, what))
        if paid:
            out.append("paid access under the copyleft licence %s%s"
                       % (lid, " (its NonCommercial clause)" if lid == CC_LICENSE_ID else ""))
    elif hiding or paid:
        ways = hiding + (["paid access"] if paid else [])
        out.append("permissive licence %s with %s: allowed in principle, but its notice (copyright line and "
                   "licence text) must be kept with every copy of the work" % (lid, ", ".join(ways)))
    return out


def license_release_blockers(lic):
    """What keeps release preparation and export from treating the licence of
    a product as settled — a DEFINITIVE condition of those steps only, never
    a block of current work. [] when nothing does. An imported licence to
    analyse is the case: its identifier is not recorded."""
    if not isinstance(lic, dict):
        return ["licence block invalid — repair SCRIPT.json (see `scan`)"]
    if is_imported(lic) and (lic.get("status") != "confirmed" or lic.get("id") not in IMPORTABLE_LICENSE_IDS):
        return ["existing licence of the imported script to analyse (license.status %r, license.id %r): "
                "release preparation and export wait for the holder to record the exact licence (closed "
                "list, docs/licensing/PROFILES.md) — the notices stay in the source as they are"
                % (lic.get("status"), lic.get("id"))]
    return []


def legal_document_path_problem(rel):
    """Why `rel` cannot designate an original legal document of an imported
    script (`license.documents`), or None. Accepted: a relative POSIX path at
    the product root or directly under release/ whose name is a legal-document
    name (LEGAL_DOCUMENT_NAME_RE), or directly under LICENSES/ (REUSE layout:
    a text named after its licence, REUSE_FILE_SUFFIXES); never a hidden file,
    a Pine source, a JSON or a lock file, an internal file of Pine Workspace, a
    name too long or holding an invisible or reordering character."""
    if not isinstance(rel, str) or not rel:
        return "must be a non-empty relative path"
    if rel != rel.strip() or rel.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", rel):
        return "must be a relative path inside the product root"
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts) or any(FILE_NAME_FORBIDDEN_RE.search(p) for p in parts):
        return ("must be a plain relative POSIX path (no empty, '.' or '..' component, no backslash nor "
                "control character)")
    if any(unicodedata.category(ch) in HIDDEN_CHAR_CATEGORIES for ch in rel):
        return "the name holds an invisible or reordering character: a declared name must show what it is"
    if len(rel.encode("utf-8")) > LEGAL_PATH_MAX_BYTES \
            or any(len(p.encode("utf-8")) > FILE_NAME_MAX_BYTES for p in parts):
        return "name too long"
    if len(parts) == 1:
        folder, name = "", parts[0]
    elif len(parts) == 2 and parts[0] in LEGAL_DOCUMENT_FOLDERS:
        folder, name = parts
    else:
        return "must lie at the product root, directly under release/ or directly under LICENSES/"
    if name.startswith("."):
        return "a hidden file is not a legal document"
    if name.lower().endswith(NOT_LEGAL_DOCUMENT_SUFFIXES):
        return "a %s file is not a legal document" % name.rsplit(".", 1)[-1]
    if name.lower() in PWS_INTERNAL_NAMES:
        return "%s is an internal file of Pine Workspace, not a legal document" % name
    if folder == REUSE_LICENSES_FOLDER:
        if not name.lower().endswith(REUSE_FILE_SUFFIXES):
            return ("under LICENSES/, a licence text is named after its licence with a text extension (%s), "
                    "e.g. LICENSES/MIT.txt" % ", ".join(REUSE_FILE_SUFFIXES))
    elif not LEGAL_DOCUMENT_NAME_RE.match(name):
        return ("%r is not a legal-document name (LICENSE, LICENCE, COPYING, COPYRIGHT, NOTICE, PATENTS, AUTHORS, "
                "CREDITS, ATTRIBUTION, CONTRIBUTORS, THIRD_PARTY_NOTICES and their variants such as LICENSE.md, "
                "LICENSE-MIT, COPYING.LESSER or NOTICE.txt; under LICENSES/, a licence text such as MIT.txt)"
                % name)
    return None


def legal_document_target(rel):
    """Path of a declared legal document inside the exported product folder:
    its own name for the product root and release/ (like the other release
    documents), `LICENSES/<name>` kept as it is (REUSE layout)."""
    parts = rel.split("/")
    return rel if len(parts) == 2 and parts[0] == REUSE_LICENSES_FOLDER else parts[-1]


CANDIDATE_KIND_REASONS = {"symlink": "a symbolic link — never followed", "folder": "a folder — only files are declared",
                          "special": "not a regular file"}


def legal_document_candidates(product_dir):
    """[{path, kind, declarable, reason}] of the entries of the product that
    may be original legal documents — searched in the whole product (hidden
    entries and the internal folders research/, validation/ and tests/
    excepted), without following any symbolic link (cross-check of
    2026-11-14: a document is never left out silently because of its place
    or its kind). A candidate is: a file, link or special file whose name is
    a legal-document name, wherever it lies; every entry directly under
    LICENSES/; a folder whose name is a legal-document name (its content is
    not searched further); release/ or LICENSES/ when it is a symbolic link
    or a special file. Kind `file`, `symlink`, `folder` or `special`;
    `declarable` only for a regular file accepted by
    legal_document_path_problem, `reason` saying otherwise why it cannot be
    declared as it is. Pine sources, JSON and lock files are not documents.
    Read-only."""
    pdir = Path(product_dir)
    out = []

    def add(rel, kind):
        reason = CANDIDATE_KIND_REASONS.get(kind) or legal_document_path_problem(rel)
        out.append({"path": rel, "kind": kind, "declarable": reason is None, "reason": reason})

    def walk(base, rel_base):
        try:
            entries = sorted(os.scandir(str(base)), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            name = entry.name
            rel = "%s/%s" % (rel_base, name) if rel_base else name
            if name.startswith(".") or (not rel_base and name in INTERNAL_FOLDERS):
                continue
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError:
                continue
            kind = ("symlink" if stat.S_ISLNK(mode) else "folder" if stat.S_ISDIR(mode)
                    else "file" if stat.S_ISREG(mode) else "special")
            in_reuse = rel_base == REUSE_LICENSES_FOLDER
            legal_name = bool(LEGAL_DOCUMENT_NAME_RE.match(name))
            if not rel_base and name in LEGAL_DOCUMENT_FOLDERS and kind != "file":
                if kind == "folder":
                    walk(entry.path, rel)          # release/ and LICENSES/ under their exact names
                else:
                    add(rel, kind)                 # a link or a special file may hide documents
                continue
            if kind == "folder":
                if in_reuse or legal_name:
                    add(rel, kind)                 # documents inside it are never exported
                else:
                    walk(entry.path, rel)
                continue
            if in_reuse or (legal_name and not name.lower().endswith(NOT_LEGAL_DOCUMENT_SUFFIXES)):
                add(rel, kind)

    walk(pdir, "")
    return out


def declared_documents_problems(product_dir, lic):
    """A declared original legal document (`license.documents`) that is
    missing, a symbolic link, inside a folder that is a symbolic link, or not
    a regular file (LICENSE_DOCUMENT_UNAVAILABLE, warning): current work
    continues; the export of the product waits until the holder restores it
    or corrects the declaration. Never reads a document's content."""
    docs = lic.get("documents") if isinstance(lic, dict) and is_imported(lic) else None
    if not isinstance(docs, list):
        return []
    out = []
    for rel in docs:
        if not isinstance(rel, str) or legal_document_path_problem(rel):
            continue
        path = Path(product_dir) / rel
        why = None
        try:
            if len(rel.split("/")) == 2 and stat.S_ISLNK(os.lstat(str(Path(product_dir) / rel.split("/")[0])).st_mode):
                why = "lies in a folder that is a symbolic link (never followed)"
            else:
                mode = os.lstat(str(path)).st_mode
                why = ("is a symbolic link (never followed)" if stat.S_ISLNK(mode)
                       else None if stat.S_ISREG(mode) else "is not a regular file")
        except OSError:
            why = "is missing"
        if why:
            out.append(("LICENSE_DOCUMENT_UNAVAILABLE", "WARNING",
                        "declared legal document %s %s: current work continues; the export of this product waits "
                        "until the holder restores the original file (a regular file, never a link) or corrects the "
                        "declaration (`license confirm --license-document`)" % (rel, why)))
    return out


def coherence_problems(script_kind, profile, lic, pub):
    """Semantic coherence of the axes. Returns [(code, severity, detail)].
    BROKEN = contradiction; WARNING = legitimate but to be signalled."""
    problems = []
    imported = is_imported(lic)
    if lic["id"] == CC_LICENSE_ID:
        if lic["grant"] != "cc":
            problems.append(("LICENSE_GRANT_MISMATCH", "BROKEN",
                             "CC BY-NC-SA 4.0 implies grant 'cc', got %r" % lic["grant"]))
        if lic["source_visibility"] != "public":
            problems.append(("LICENSE_VISIBILITY_MISMATCH", "BROKEN",
                             "a CC BY-NC-SA 4.0 script publishes its source "
                             "(source_visibility must be 'public')"))
    else:
        if lic["grant"] == "cc":
            problems.append(("LICENSE_GRANT_MISMATCH", "BROKEN",
                             "grant 'cc' requires license CC-BY-NC-SA-4.0"))
        if imported and lic["grant"] != "license":
            problems.append(("LICENSE_GRANT_MISMATCH", "BROKEN",
                             "the existing licence of an imported script defines the rights itself: "
                             "grant must be 'license', got %r" % lic["grant"]))
    if lic["grant"] == "license" and not imported:
        problems.append(("LICENSE_GRANT_MISMATCH", "BROKEN",
                         "grant 'license' (rights defined by the licence itself) applies only to the "
                         "existing licence of an imported script (license.origin 'imported')"))
    if imported and lic.get("status") == "to-analyse":
        problems.append(("LICENSE_TO_ANALYSE", "WARNING",
                         "existing licence of the imported script to analyse (license.status 'to-analyse', "
                         "no identifier recorded): its notices and attributions stay in the source as they "
                         "are; current work continues — release preparation and export wait for the holder "
                         "to record the exact licence (closed list) or to decide otherwise "
                         "(docs/licensing/PROFILES.md)"))
    for conflict in imported_license_conflicts(lic, pub):
        problems.append(("IMPORTED_LICENSE_CONFLICT", "WARNING",
                         "%s — to analyse (holder's decision): never an automatic block nor a legal "
                         "conclusion; never remove a notice or an attribution" % conflict))
    mode, privacy, state = pub.get("mode"), pub.get("privacy"), pub.get("state")
    if mode == "open" and lic["source_visibility"] != "public":
        problems.append(("PUBLICATION_VISIBILITY_MISMATCH", "BROKEN",
                         "publication mode 'open' shows the source on TradingView: "
                         "source_visibility must be 'public'"))
    if script_kind == "library":
        if lic["source_visibility"] != "public" or mode not in (None, "open"):
            problems.append(("KIND_LIBRARY_OPEN_SOURCE", "BROKEN",
                             "a TradingView library is always open-source: "
                             "source_visibility 'public' and publication mode 'open' "
                             "(public or private publication)"))
        if lic["access"] == "paid":
            problems.append(("KIND_LIBRARY_PAID", "BROKEN",
                             "a library cannot be paid under the current TradingView rule"))
    if lic["access"] == "paid":
        # an imported licence defines the rights itself: paid access is a
        # conflict to analyse (above), never a call to change the licence
        if lic["grant"] != "eula" and not imported:
            problems.append(("ACCESS_PAID_WITHOUT_EULA", "WARNING",
                             "paid access without an EULA grant — the usage terms are "
                             "undefined; set grant 'eula' and terms_ref before any "
                             "commercial publication"))
        if privacy is not None and privacy != "public" or mode is not None and mode != "invite-only":
            problems.append(("ACCESS_PAID_PUBLICATION", "WARNING",
                             "paid access on TradingView goes through a PUBLIC invite-only "
                             "script (master §34.4): privacy %r / mode %r must be confirmed "
                             "against the current rules before any commercial publication"
                             % (privacy, mode)))
    if lic["grant"] == "eula" and not lic.get("terms_ref"):
        problems.append(("EULA_DRAFT", "WARNING",
                         "EULA grant without terms_ref: the EULA is a DRAFT — this "
                         "never blocks development but must be settled before a "
                         "commercial publication"))
    if lic.get("terms_url") and not lic.get("terms_ref") and not imported:
        problems.append(("TERMS_URL_WITHOUT_TERMS", "WARNING",
                         "terms_url declared while no terms document is attached "
                         "(terms_ref null): the reference points to terms not yet "
                         "prepared — settle before publication"))
    if imported and lic.get("terms_ref"):
        problems.append(("IMPORTED_LICENSE_TERMS", "WARNING",
                         "terms_ref %r declared for an imported licence: no PWS terms document applies (the "
                         "existing licence defines the rights itself) — the attached file is not used as "
                         "the product's terms" % lic["terms_ref"]))
    if lic["grant"] == "free-use" and lic["access"] != "free":
        problems.append(("GRANT_FREE_USE_ACCESS", "WARNING",
                         "a free-use grant normally goes with access 'free'"))
    if state == "published" and (privacy is None or mode is None):
        problems.append(("PUBLICATION_INCOMPLETE", "WARNING",
                         "state 'published' with unknown privacy or mode — record the "
                         "real TradingView settings"))
    if state is None:
        unknown = [k for k, v in (("state", state), ("privacy", privacy), ("mode", mode)) if v is None]
        problems.append(("PUBLICATION_STATE_UNKNOWN", "WARNING",
                         "publication %s unknown (migrated manifest) — confirm with "
                         "`license confirm`; nothing was inferred" % ", ".join(unknown)))
    divergent = []
    # the profile never forces the licence of an imported script: only the
    # access axis is compared for it
    if profile in PROFILE_GRANTS and lic["grant"] not in PROFILE_GRANTS[profile] and not imported:
        divergent.append("grant %r" % lic["grant"])
    if profile in ("FREE", "PRIVATE") and lic["access"] == "paid":
        divergent.append("access 'paid'")
    if divergent:
        problems.append(("PROFILE_AXES_DIVERGENCE", "WARNING",
                         "profile %s and the licence axes describe different regimes (%s): the "
                         "licence documents and the header checks follow the licence axes, never "
                         "the profile name — confirm which one is right (holder's decision)"
                         % (profile, ", ".join(divergent))))
    return problems


def attached_terms_problems(product_dir, lic):
    """An attached terms document (`terms_ref`) that is still a draft — draft
    banner or residual template syntax — keeps the terms in DRAFT status: the
    attachment never settles them by itself (audit C-02). Reads one file of
    the product, never through a symbolic link."""
    terms = lic.get("terms_ref") if isinstance(lic, dict) else None
    if not isinstance(terms, str) or not terms:
        return []
    path = Path(product_dir) / terms
    if path.is_symlink() or not core.is_within(product_dir, path) or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if DRAFT_MARKER not in text and not TEMPLATE_RESIDUE_RE.search(text):
        return []
    code = "EULA_DRAFT" if lic.get("grant") == "eula" else "TERMS_DRAFT"
    return [(code, "WARNING",
             "the attached terms document %s is still a DRAFT (draft banner or unfilled template "
             "field): complete the information and write it again (`license write`) before any "
             "publication — this never blocks development" % terms)]


DERIVED_V2_MODES = ("tradingview-open", "tradingview-protected", "tradingview-invite-only")


def rectify_publication_derivations(manifest, today=None):
    """Rectify a schema-3 manifest migrated by the 2026-11-06 code, which
    deduced publication values instead of recording them:
      - from a schema-2 mode string: privacy 'public' was deduced → null;
      - from a v1 → v2 → v3 chain (migration.previous.from_schema == 1): the
        mode itself came from profile defaults → null as well.
    Values listed in `migration.holder_confirmed` are never touched. Returns
    (new_manifest, changes); changes == [] means nothing to do. Each change
    is traced in `migration.rectifications`."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != version.MANIFEST_SCHEMA_VERSION:
        return manifest, []
    mig = manifest.get("migration")
    pub = manifest.get("publication")
    if not isinstance(mig, dict) or not isinstance(pub, dict):
        return manifest, []
    confirmed = set(c for c in (mig.get("holder_confirmed") or []) if isinstance(c, str))
    already = {r.get("field") for r in (mig.get("rectifications") or []) if isinstance(r, dict)}
    today = today or datetime.date.today().isoformat()
    changes = []
    new = dict(manifest)
    new_pub = dict(pub)
    new_mig = dict(mig)
    rect = list(new_mig.get("rectifications") or [])

    def reset(field, reason):
        if new_pub.get(field) is None or "publication.%s" % field in confirmed                 or "publication.%s" % field in already:
            return
        rect.append({"on": today, "step": "m006", "field": "publication.%s" % field,
                     "from": new_pub.get(field), "to": None, "reason": reason})
        changes.append("publication.%s %r → null (%s)" % (field, new_pub.get(field), reason))
        new_pub[field] = None

    from_pub = mig.get("from_publication")
    chain_v1 = mig.get("from_schema") == 1 or (
        isinstance(mig.get("previous"), dict) and mig["previous"].get("from_schema") == 1)
    if mig.get("from_schema") == 2 and from_pub in DERIVED_V2_MODES:
        reset("privacy", "schema 2 never recorded the publication privacy; 'public' had been deduced")
        if chain_v1:
            reset("mode", "the schema-2 value itself came from profile defaults (v1 chain), not from a record")
    elif mig.get("from_schema") == 1:
        reset("privacy", "schema 1 never recorded the publication; profile defaults had been applied")
        reset("mode", "schema 1 never recorded the publication; profile defaults had been applied")
    if not changes:
        return manifest, []
    new_mig["rectifications"] = rect
    new["publication"] = new_pub
    new["migration"] = new_mig
    return new, changes


def _add_broken(findings, add_finding, product_dir, votes, code, detail):
    add_finding(findings, code, "BROKEN", product_dir, detail)
    votes.append("BROKEN")


def _validate_license_block(lic_raw, product_dir, findings, add_finding, votes, imports=True):
    """Validate the `license` object. Returns the normalized dict or None.
    `imports`: the licence-of-an-imported-script fields of schema 3 (origin,
    status) are admitted — never in a schema-2 manifest."""
    if not isinstance(lic_raw, dict):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_TYPE",
                    "license must be an object")
        return None
    lkeys = set(lic_raw.keys())
    known_keys = LICENSE_REQUIRED_KEYS | LICENSE_OPTIONAL_KEYS | (set(LICENSE_IMPORT_KEYS) if imports else set())
    lunknown = sorted(lkeys - known_keys)
    lmissing = sorted(LICENSE_REQUIRED_KEYS - lkeys)
    ok = True
    if lunknown:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_UNKNOWN_FIELDS",
                    "unknown license fields: %s" % ", ".join(lunknown))
        ok = False
    if lmissing:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_MISSING_FIELDS",
                    "missing license fields: %s" % ", ".join(lmissing))
        return None
    origin = lic_raw.get("origin") if imports else None
    status = lic_raw.get("status") if imports else None
    if origin is not None and origin not in LICENSE_ORIGINS:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                    "license.origin %r not in %s (absent = profile)" % (origin, list(LICENSE_ORIGINS)))
        ok = False
    if status is not None and status not in IMPORTED_STATUSES:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                    "license.status %r not in %s" % (status, list(IMPORTED_STATUSES)))
        ok = False
    elif origin == "imported" and status is None:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                    "license.status is required for the existing licence of an imported script: "
                    "'confirmed' (exact identifier recorded after the holder's confirmation) or "
                    "'to-analyse' (license.id null)")
        ok = False
    elif origin != "imported" and status is not None:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                    "license.status applies only to the existing licence of an imported script "
                    "(license.origin 'imported')")
        ok = False
    id_problem = _license_id_problem(lic_raw.get("id"), origin, status)
    if id_problem:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID", id_problem)
        ok = False
    documents = lic_raw.get("documents") if imports else None
    if documents is not None:          # absent or null: not declared
        if origin != "imported":
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                        "license.documents applies only to the existing licence of an imported script "
                        "(license.origin 'imported')")
            ok = False
        elif not isinstance(documents, list) or not all(isinstance(d, str) for d in documents):
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                        "license.documents must be a list of paths inside the product root ([] = no separate "
                        "legal document; absent or null = not declared)")
            ok = False
        else:
            seen, folded = set(), set()
            for rel in documents:
                problem = legal_document_path_problem(rel)
                if problem is None and rel in seen:
                    problem = "declared twice"
                elif problem is None and rel.casefold() in folded:
                    problem = "differs from another declared document only by case: both cannot be exported"
                seen.add(rel)
                folded.add(rel.casefold())
                if problem:
                    _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                                "license.documents entry %r: %s" % (rel, problem))
                    ok = False
    for field, allowed in (("grant", GRANTS), ("source_visibility", SOURCE_VISIBILITIES),
                           ("access", ACCESS_MODES)):
        value = lic_raw.get(field)
        if value not in allowed:
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                        "license.%s %r not in %s" % (field, value, list(allowed)))
            ok = False
    holder = lic_raw.get("copyright_holder")
    if holder is not None and (not isinstance(holder, str) or not holder.strip()):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                    "license.copyright_holder must be null or a non-blank string")
        ok = False
    year = lic_raw.get("created_year")
    this_year = datetime.date.today().year
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)
                             or year < 2000 or year > this_year + 1):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                    "license.created_year must be null or a plausible year (int)")
        ok = False
    terms = lic_raw.get("terms_ref")
    if terms is not None:
        if not isinstance(terms, str) or not terms or Path(terms).is_absolute() \
                or ".." in Path(terms).parts:
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                        "license.terms_ref must be null or a relative path inside the product root")
            ok = False
        elif not core.is_within(product_dir, Path(product_dir) / terms) \
                or not (Path(product_dir) / terms).is_file():
            _add_broken(findings, add_finding, product_dir, votes, "LICENSE_TERMS_MISSING",
                        "license.terms_ref %r does not exist inside the product root" % terms)
    url = lic_raw.get("terms_url")
    if url is not None and (not isinstance(url, str) or not HTTPS_URL_RE.match(url.strip())):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_FIELD_TYPE",
                    "license.terms_url must be null or an https URL")
        ok = False
    if not ok:
        return None
    lic = {k: lic_raw.get(k) for k in LICENSE_REQUIRED_KEYS | LICENSE_OPTIONAL_KEYS}
    for key in LICENSE_IMPORT_KEYS:
        if imports and key in lic_raw:
            lic[key] = lic_raw[key]
    if isinstance(lic.get("terms_url"), str):
        lic["terms_url"] = lic["terms_url"].strip()
    return lic


def _validate_publication_block(pub_raw, product_dir, findings, add_finding, votes):
    if not isinstance(pub_raw, dict):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_PUBLICATION_TYPE",
                    "publication must be an object {state, privacy, mode}")
        return None
    keys = set(pub_raw.keys())
    if keys != PUBLICATION_KEYS:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_PUBLICATION_FIELDS",
                    "publication must carry exactly %s (got %s)"
                    % (sorted(PUBLICATION_KEYS), sorted(keys)))
        return None
    ok = True
    for field, allowed in (("state", PUBLICATION_STATES), ("privacy", PUBLICATION_PRIVACIES),
                           ("mode", PUBLICATION_MODES)):
        v = pub_raw.get(field)
        if v is not None and v not in allowed:
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_PUBLICATION_AXIS_INVALID",
                        "publication.%s %r not in %s (or null = unknown)" % (field, v, list(allowed)))
            ok = False
    if pub_raw.get("state") == "unpublished" and (pub_raw.get("privacy") or pub_raw.get("mode")):
        # legitimate: the intended settings of a future publication
        pass
    return dict(pub_raw) if ok else None


def _validate_source(data, product_dir, findings, add_finding, votes):
    source = data["source"]
    if not source:
        _add_broken(findings, add_finding, product_dir, votes, "SOURCE_FIELD_INVALID",
                    "source must be a non-empty string")
        return None
    if Path(source).is_absolute():
        _add_broken(findings, add_finding, product_dir, votes, "SOURCE_ABSOLUTE",
                    "absolute source path rejected")
        return None
    candidate = Path(product_dir) / source
    if not core.is_within(product_dir, candidate):
        _add_broken(findings, add_finding, product_dir, votes, "SOURCE_ESCAPES_ROOT",
                    "source resolves outside the product root (traversal or symlink)")
        return None
    if not candidate.is_file():
        _add_broken(findings, add_finding, product_dir, votes, "SOURCE_MISSING",
                    "declared source %r not found" % source)
        return None
    if not source.endswith(".pine"):
        _add_broken(findings, add_finding, product_dir, votes, "SOURCE_NOT_PINE",
                    "declared source %r is not a .pine file" % source)
        return None
    return candidate


def validate_manifest_v3(slug, product_dir, data, findings, add_finding):
    """Validate a schema-3 manifest. Returns (votes, source_path, profile,
    license, publication). Types are checked before any semantic use."""
    votes = []
    keys = set(data.keys())
    unknown = sorted(keys - V3_REQUIRED_KEYS - V3_OPTIONAL_KEYS)
    missing = sorted(V3_REQUIRED_KEYS - keys)
    if unknown:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_UNKNOWN_FIELDS",
                    "unknown fields rejected by schema v3: %s" % ", ".join(unknown))
    if missing:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_MISSING_FIELDS",
                    "missing required fields: %s" % ", ".join(missing))
        return votes, None, None, None, None
    typed = True
    for field in ("id", "source", "script_kind", "profile"):
        if not isinstance(data.get(field), str):
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_FIELD_TYPE",
                        "%s must be str, got %s" % (field, type(data.get(field)).__name__))
            typed = False
    if not typed:
        return votes, None, None, None, None
    if data["id"] != slug:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_ID_SLUG_MISMATCH",
                    "id %r must equal product slug %r" % (data["id"], slug))
    kind = data["script_kind"]
    if kind not in core.SCRIPT_KINDS:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_KIND_INVALID",
                    "script_kind %r not in %s" % (kind, list(core.SCRIPT_KINDS)))
    profile = data["profile"]
    if profile not in PROFILES:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_PROFILE_INVALID",
                    "profile %r not in %s" % (profile, list(PROFILES)))
        profile = None
    lic = _validate_license_block(data["license"], product_dir, findings, add_finding, votes)
    pub = _validate_publication_block(data["publication"], product_dir, findings, add_finding, votes)
    if lic is not None and pub is not None and profile is not None and kind in core.SCRIPT_KINDS:
        for code, sev, detail in coherence_problems(kind, profile, lic, pub):
            add_finding(findings, code, sev, product_dir, detail)
            if sev == "BROKEN":
                votes.append("BROKEN")
    if lic is not None:
        for code, sev, detail in attached_terms_problems(product_dir, lic):
            add_finding(findings, code, sev, product_dir, detail)
        for code, sev, detail in declared_documents_problems(product_dir, lic):
            add_finding(findings, code, sev, product_dir, detail)
    mig = data.get("migration")
    if mig is not None and not isinstance(mig, dict):
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_FIELD_TYPE",
                    "migration must be an object when present")
    source_path = _validate_source(data, product_dir, findings, add_finding, votes)
    return votes, source_path, profile, lic, pub


def validate_manifest_v2(slug, product_dir, data, findings, add_finding):
    """Read-compatibility for schema 2 (publication as a string). The
    publication object is DERIVED (known parts kept, unknown kept unknown)
    and the manifest is flagged for explicit migration."""
    votes = []
    keys = set(data.keys())
    required = (V3_REQUIRED_KEYS - {"publication"})
    unknown = sorted(keys - required - V3_OPTIONAL_KEYS)
    missing = sorted(required - keys)
    if unknown:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_UNKNOWN_FIELDS",
                    "unknown fields rejected by schema v2: %s" % ", ".join(unknown))
    if missing:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_MISSING_FIELDS",
                    "missing required fields: %s" % ", ".join(missing))
        return votes, None, None, None, None
    typed = True
    for field in ("id", "source", "script_kind", "profile"):
        if not isinstance(data.get(field), str):
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_FIELD_TYPE",
                        "%s must be str, got %s" % (field, type(data.get(field)).__name__))
            typed = False
    if not typed:
        return votes, None, None, None, None
    if data["id"] != slug:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_ID_SLUG_MISMATCH",
                    "id %r must equal product slug %r" % (data["id"], slug))
    kind = data["script_kind"]
    if kind not in core.SCRIPT_KINDS:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_KIND_INVALID",
                    "script_kind %r not in %s" % (kind, list(core.SCRIPT_KINDS)))
    profile = data["profile"]
    if profile not in PROFILES:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_PROFILE_INVALID",
                    "profile %r not in %s" % (profile, list(PROFILES)))
        profile = None
    lic_raw = data["license"]
    pub = None
    lic = None
    if isinstance(lic_raw, dict):
        lic_raw = dict(lic_raw)
        pub_value = lic_raw.pop("publication", None)
        pub = publication_from_v2(pub_value)
        if pub is None:
            _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_AXIS_INVALID",
                        "license.publication %r not in %s" % (pub_value, sorted(LEGACY_PUBLICATION_V2)))
        lic = _validate_license_block(lic_raw, product_dir, findings, add_finding, votes, imports=False)
    else:
        _add_broken(findings, add_finding, product_dir, votes, "MANIFEST_LICENSE_TYPE",
                    "license must be an object")
    if lic is not None and pub is not None and profile is not None and kind in core.SCRIPT_KINDS:
        for code, sev, detail in coherence_problems(kind, profile, lic, pub):
            add_finding(findings, code, sev, product_dir, detail)
            if sev == "BROKEN":
                votes.append("BROKEN")
    if lic is not None:
        for code, sev, detail in attached_terms_problems(product_dir, lic):
            add_finding(findings, code, sev, product_dir, detail)
    add_finding(findings, "MANIFEST_LEGACY_SCHEMA", "WARNING", product_dir,
                "schema v2 manifest: publication axes DERIVED from the legacy string "
                "%r (state unknown unless 'unpublished') — run `python3 -m "
                "tools.pws_workspace migrate --plan` to write the explicit v3 form"
                % (data["license"].get("publication") if isinstance(data["license"], dict) else None))
    source_path = _validate_source(data, product_dir, findings, add_finding, votes)
    return votes, source_path, profile, lic, pub


def header_policy(profile, lic, identity):
    """What the guard must find in a source header, derived from the licence
    axes and the configured identity. `identity` comes from config.identity().
    `allowed_urls` = the product's declared legal reference (terms_url).
    An imported licence (`origin` imported) never requires the CC header nor
    the "All Rights Reserved" mark nor a copyright line naming the configured
    holder: the guard checks that its existing notice is still present and
    coherent with `license_id` (null while the licence is to analyse)."""
    policy = {"license_id": None, "grant": None, "require_cc": False,
              "require_proprietary_mark": False, "holder_marks": [],
              "identity_configured": bool(identity and identity.get("configured")),
              "profile": profile, "allowed_urls": [], "origin": "profile", "license_status": None,
              "license_valid": isinstance(lic, dict)}
    if isinstance(lic, dict):
        imported = is_imported(lic)
        policy["license_id"] = lic.get("id")
        policy["grant"] = lic.get("grant")
        policy["origin"] = license_origin(lic)
        policy["license_status"] = imported_status(lic)
        policy["require_cc"] = lic.get("id") == CC_LICENSE_ID and not imported
        policy["require_proprietary_mark"] = lic.get("id") == "PROPRIETARY" and not imported
        holder = lic.get("copyright_holder")
        if isinstance(holder, str) and holder.strip():
            policy["holder_marks"] = [holder.strip()]
            policy["identity_configured"] = True
        url = lic.get("terms_url")
        if isinstance(url, str) and url.strip():
            policy["allowed_urls"] = [url.strip()]
    if not policy["holder_marks"] and identity and identity.get("configured"):
        policy["holder_marks"] = [identity["copyright_holder"]] + list(identity.get("header_aliases") or [])
    return policy


def policy_from_legacy_distribution(distribution, identity):
    profile, lic, _ = derive_from_legacy(distribution)
    if profile is None:
        return None
    return header_policy(profile, lic, identity)


def migrate_manifest_to_v3(data, today=None):
    """Explicit migration of a v1 or v2 manifest dict to schema 3. Returns
    (new_manifest, notes, ambiguities). Never guesses: unknown publication
    facts stay null and are listed as ambiguities for the holder to confirm."""
    today = today or datetime.date.today().isoformat()
    sv = data.get("schema_version")
    notes, ambiguities = [], []
    if sv == version.MANIFEST_SCHEMA_LEGACY:
        dist = data.get("distribution")
        profile, lic, pub = derive_from_legacy(dist)
        if profile is None:
            return None, [], ["distribution %r has no v3 equivalent" % (dist,)]
        lic = {k: v for k, v in lic.items() if k != "derived_from_v1"}
        migration = {"from_schema": 1, "from_distribution": dist, "on": today,
                     "note": ("licence axes = documented meaning of the legacy distribution; "
                              "publication entirely unknown (schema 1 never recorded it) — "
                              "confirm state, privacy and mode; nothing was inferred")}
        notes.append("%s → profile %s, licence %s, publication unknown" % (dist, profile, lic))
        ambiguities.append("publication state, privacy and mode unknown (schema 1 never recorded them) — confirm")
        if profile == "COMMERCIAL":
            ambiguities.append("COMMERCIAL: EULA terms_ref not set (draft) and created_year "
                               "unknown — to confirm")
    elif sv == 2:
        lic_src = dict(data.get("license") or {})
        pub_value = lic_src.pop("publication", None)
        pub = publication_from_v2(pub_value)
        if pub is None:
            return None, [], ["publication %r has no v3 equivalent" % (pub_value,)]
        pub.pop("derived_from_v2", None)
        profile = data.get("profile")
        lic = _full_license(lic_src)
        prev = data.get("migration") if isinstance(data.get("migration"), dict) else None
        migration = {"from_schema": 2, "from_publication": pub_value, "on": today,
                     "note": ("publication string split into state/privacy/mode: known parts kept, "
                              "unknown parts null; confirm the real TradingView settings")}
        if prev:
            migration["previous"] = prev
        notes.append("%r → publication %s" % (pub_value, pub))
        if pub["state"] is None:
            ambiguities.append("publication state unknown (schema 2 conflated it with the mode) — confirm")
        if pub["privacy"] is None and pub["mode"] is not None:
            ambiguities.append("publication privacy (public / private) was never recorded — confirm")
        if pub["mode"] is None and pub["privacy"] == "private":
            ambiguities.append("private publication with unknown mode (open / protected / "
                               "invite-only) — confirm")
    else:
        return None, [], ["schema_version %r is not a migration source" % (sv,)]
    new = {
        "schema_version": version.MANIFEST_SCHEMA_VERSION,
        "id": data.get("id"),
        "source": data.get("source"),
        "script_kind": data.get("script_kind"),
        "profile": profile,
        "license": lic,
        "publication": pub,
        "migration": migration,
    }
    return new, notes, ambiguities


# Backward-compatible name used by earlier callers/tests of the 2026-11-06 lot.
migrate_manifest_v1_to_v2 = migrate_manifest_to_v3
