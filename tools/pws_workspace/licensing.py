# SPDX-License-Identifier: Apache-2.0
"""Licence texts: render the English templates with the configured identity
and a product's licence/publication axes; report the EULA draft status;
confirm publication facts.

Templates live in `docs/licensing/templates/` (English texts; French and
English explanations in `docs/licensing/PROFILES.md`; reuse permission in
`docs/licensing/TEMPLATE_PERMISSION.md`).

Template format (deliberately small, not a general engine):
  {{NAME}}                 placeholder, filled from the context values;
  [[?NAME:text]]           optional block kept only when NAME has a value
                           (the body may contain {{NAME}} placeholders);
  [[!NAME:text]]           optional block kept only when NAME is EMPTY;
  <!-- pws-template … -->  provenance line of a Markdown template, stripped;
  //! pws-template …       provenance line of a header template, stripped.
Optional blocks never nest and never contain `]]`. After rendering, any
residual block syntax means the template is malformed: the render is an
ERROR, never a document declared final.

Nothing is invented: a required field without a value stays a visible
placeholder and keeps the document in DRAFT status — the rendered text then
carries an explicit draft banner (Markdown kinds). An unknown creation year
is NOT replaced by the current year: `{{YEAR_RANGE}}` stays unfilled and the
header is a draft until `license.created_year` is set (a new project may
receive the current year explicitly at creation; a migrated project keeps
its unknown year until confirmed). A draft never blocks development; it is
reported before any publication and never exported.

Guided path « Licence and terms of use » (2026-11-07, menu Quality /
publication → skill `pine-license`), independent of `pine-release`: it
never runs release checks, reviews, PineTS or TradingView. It reuses this
module and its data only — the manifest axes (`license confirm`), the
holder's fields in `release/eula-fields.json` (`license set-fields`) and the
templates (`license render` = preview, `license write` = generation).
`overview` is the read-only consolidated view the skill renders: profile
variant, documents applicable to the product with their draft state,
recorded facts versus facts still to confirm, fields grouped for the
dialogue (groups and labels localized from the catalogue). Consulting and
previewing never write; saving happens only on an explicit command after the
holder's grouped confirmation; a technically complete document is never
presented as a legally validated contract.

Bounds of the writers (corrections of 2026-11-13, audit C-01 to C-09):
  - the documents of a product follow its LICENCE AXES (licence id and
    grant, `documents_regime`), never the profile name; a profile whose axes
    describe another regime is signalled by the manifest checks;
  - `write` writes only a document of those axes, only directly under
    `release/` (`.md` documents, `.txt` headers), never through a symbolic
    link, and replaces an existing file only at the default destination of
    that document or at the attached terms document;
  - `confirm --terms-ref` attaches only the current and complete rendering
    of the product's terms document (a draft, a stale copy or any other file
    is refused); the terms status is derived from the attached document
    itself (current / draft / stale);
  - `confirm` checks the RESULTING manifest with the checks of the scan and
    refuses a value that would make it BROKEN; `clear` returns a confirmed
    value to « unknown »;
  - `confirm`, `set-fields` and `write` work under an exclusive lock held on
    the product directory itself (no lock file); `confirm` and `set-fields`
    re-read the freshest state, refuse a concurrent change made by a writer
    that does not take the lock, and check what they wrote;
  - only the holder's fields of `release/eula-fields.json` feed the
    rendering: identity, years and URLs always come from the manifest and the
    configuration (other keys stay in the file, ignored and reported).

Licence of an imported script (decision of the holder of 2026-11-13, audit
C-19 — profiles.py): regime IMPORTED, « existing licence kept ». No PWS terms
document applies (no header template, EULA, notice nor grant: `write` and
`confirm --terms-ref` refuse); `status` and `overview` show the recorded
licence, or the licence still to analyse, with the licence PROPOSAL read in
the source header (never a legal proof) and the conflicts to analyse.
`detect_source_licence` gives that proposal for a source not yet onboarded
(read-only). `confirm_publication(license_id=…)` records the exact identifier
of an imported licence confirmed by the holder (closed list only; a
deprecated or ambiguous identifier is refused) and `clear=("license_id",)`
returns it to « to analyse ».

Original legal documents of an imported script (holder's request of
2026-11-14 — profiles.py): `confirm_publication(license_documents=[…])`
records the files the holder declares as accompanying the existing licence
(each one checked: legal-document name and place, regular file inside the
product, never through a link, text that can be checked); `[]` records that
none accompanies the script; `clear=("license_documents",)` returns to « not
declared ». `legal_documents_review` gives, read-only, the declared
documents, the candidates found in the product and what keeps the export
waiting; the documents are never rewritten, translated nor replaced by a
PWS template.
"""
import datetime
import fcntl
import json
import os
import re
import stat
import threading
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from . import config, core, i18n, profiles, scan, version

TEMPLATES_REL = Path("docs/licensing/templates")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
OPTIONAL_BLOCK_RE = re.compile(r"\[\[([?!])([A-Z0-9_]+):(.*?)\]\]", re.S)
TEMPLATE_NOTE_RE = re.compile(r"^(?:<!--\s*pws-template[^\n]*?-->[ \t]*\n|//!\s*pws-template[^\n]*\n)", re.M)
DRAFT_MARKER = profiles.DRAFT_MARKER
KINDS = {
    "header-free": "HEADER_FREE_CC_BY_NC_SA.txt",
    "header-proprietary": "HEADER_PROPRIETARY.txt",
    "notice": "NOTICE_PROPRIETARY_SHORT.md",
    "grant": "FREE_USE_GRANT_CLOSED_SOURCE.md",
    "eula": "EULA_COMMERCIAL_TEMPLATE.md",
}
HEADER_KINDS = ("header-free", "header-proprietary")
EULA_REQUIRED_FIELDS = (
    "PROVIDER_LEGAL_NAME", "PROVIDER_CONTACT", "PRODUCT_NAME", "AUTHORIZED_ACCOUNT_RULE",
    "LICENSE_MODEL", "TERM_OR_PERIOD", "ACCESS_CHANNEL", "RENEWAL_TERMS",
    "EXPIRY_AND_TERMINATION", "SUPPORT_TERMS", "GOVERNING_LAW_REFERENCE",
)
EULA_OPTIONAL_FIELDS = ("REFUND_POLICY_REFERENCE", "PRICE_OR_PLAN_REFERENCE", "ADDITIONAL_TERMS")
# ---- guided path: field groups, documents per licence regime -------------
FIELD_GROUPS = (
    ("product", ("PRODUCT_NAME",)),
    ("provider", ("PROVIDER_LEGAL_NAME", "PROVIDER_CONTACT")),
    ("beneficiary", ("AUTHORIZED_ACCOUNT_RULE",)),
    ("commercial", ("LICENSE_MODEL", "TERM_OR_PERIOD", "ACCESS_CHANNEL", "PRICE_OR_PLAN_REFERENCE")),
    ("renewal", ("RENEWAL_TERMS", "EXPIRY_AND_TERMINATION")),
    ("support", ("SUPPORT_TERMS",)),
    ("refunds", ("REFUND_POLICY_REFERENCE",)),
    ("law", ("GOVERNING_LAW_REFERENCE",)),
    ("additional", ("ADDITIONAL_TERMS",)),
)
FIELD_NAMES = tuple(f for _, names in FIELD_GROUPS for f in names)
# Values filled from the manifest, the configuration and the source — never
# from the holder's fields file (audit C-07).
CONTEXT_KEYS = ("COPYRIGHT_HOLDER", "CREATED_YEAR", "CURRENT_YEAR", "YEAR_RANGE", "PRODUCT_NAME",
                "PRODUCT_SLUG", "PROFILE", "SCRIPT_KIND", "LICENSE_ID", "GRANT", "SOURCE_VISIBILITY",
                "ACCESS", "PUBLICATION_STATE", "PUBLICATION_PRIVACY", "PUBLICATION_MODE", "TERMS_URL",
                "CC_URL")
TEMPLATE_KEYS = frozenset(CONTEXT_KEYS) | frozenset(FIELD_NAMES)
TEMPLATE_SYNTAX = ("{{", "}}", "[[", "]]")
FIELDS_REL = "release/eula-fields.json"
RELEASE_DIR = "release"
# existing licence of an imported script: kept as it is, no PWS document
IMPORTED_REGIME = "IMPORTED"
# (kind, role, required) per licence regime — the documents the path serves
DOCUMENTS = {
    "FREE": (("header-free", "header", True),),
    "FREE_CLOSED": (("header-proprietary", "header", True), ("grant", "terms", True)),
    "PRIVATE": (("header-proprietary", "header", True), ("notice", "terms", True),
                ("grant", "permission", False)),
    "COMMERCIAL": (("header-proprietary", "header", True), ("eula", "terms", True)),
    IMPORTED_REGIME: (),
}
REGIME_BY_GRANT = {"free-use": "FREE_CLOSED", "none": "PRIVATE", "eula": "COMMERCIAL"}
# localized texts of the imported licence — the catalogue (i18n) wins as soon
# as it carries the key
_TEXTS = {
    "license.imported.regime": {"en": "Existing licence kept (imported script)",
                                "fr": "Licence existante conservée (script importé)"},
    "license.imported.kept": {"en": "Existing licence kept: {id}", "fr": "Licence existante conservée : {id}"},
    "license.imported.to_analyse": {"en": "Existing licence to analyse", "fr": "Licence existante à analyser"},
    "license.imported.profile": {"en": "Usage profile {profile} — {licence}",
                                 "fr": "Profil d'usage {profile} — {licence}"},
    "license.confirm.license_id": {"en": "Existing licence of the imported script (exact identifier, closed list)",
                                   "fr": "Licence existante du script importé (identifiant exact, liste fermée)"},
    "license.confirm.license_documents": {
        "en": "Original legal documents of the imported script (LICENSE, COPYING, NOTICE…)",
        "fr": "Documents juridiques d'origine du script importé (LICENSE, COPYING, NOTICE…)"},
}
DEFAULT_DEST = {"eula": "release/EULA.md", "grant": "release/FREE_USE_GRANT.md", "notice": "release/NOTICE.md",
                "header-free": "release/HEADER_FREE.txt", "header-proprietary": "release/HEADER_PROPRIETARY.txt"}
# manifest values a holder can return to « unknown » (`confirm_publication(clear=…)`)
CLEARABLE = {"state": "publication.state", "privacy": "publication.privacy", "mode": "publication.mode",
             "created_year": "license.created_year", "terms_ref": "license.terms_ref",
             "terms_url": "license.terms_url", "license_id": "license.id",
             "license_documents": "license.documents"}
LOCK_TIMEOUT = 10.0
# original legal documents of an imported script: far smaller than this; a larger file is not checked
LEGAL_DOCUMENT_MAX_BYTES = 1 << 20
SPDX_SCOPE_NOTE = ("the recorded SPDX identifier names the licence; it does not establish by itself which documents "
                   "and notices a redistribution requires — the holder declares the documents that accompany the "
                   "script from its original distribution")
LEGAL_NOTE = ("A document reported complete is technically complete (every required field filled, no "
              "template syntax left); it is not a legally reviewed or validated contract. Pine Workspace "
              "gives no legal advice and invents no identity, jurisdiction, URL, year or commercial term.")
PERMISSION_NOTE = ("Rendered from a Pine Workspace template under the Template Permission "
                   "(docs/licensing/TEMPLATE_PERMISSION.md): you may use, modify and distribute "
                   "this text in your product documents without PWS attribution; the common "
                   "template text stays PWS's, your additions and product-specific content are yours.")
HEADER_YEAR_RE = re.compile(r"©\s*(\d{4})")
HEADER_MODE_RES = (("invite-only", re.compile(r"invite[- ]only", re.I)),
                   ("protected", re.compile(r"\bprotected\b", re.I)),
                   ("open", re.compile(r"open[- ]source", re.I)))
_LOCAL = threading.local()


# ---- products, paths and lock --------------------------------------------------

def _product(root, slug):
    for p in scan.scan_workspace(root)["products"]:
        if p["slug"] == slug:
            return p
    return None


def _product_dir_problem(root, product):
    """Refusal reason when a product root is not a real folder of scripts/
    (a symbolic link is never read through nor written through)."""
    pdir = Path(product["path"])
    scripts = Path(root) / "scripts"
    if scripts.is_symlink() or pdir.is_symlink():
        return "product root %s is a symbolic link — nothing is read through it nor written" % pdir
    try:
        if pdir.resolve().parent != scripts.resolve():
            return "product root %s is not a folder of scripts/ — nothing written" % pdir
    except OSError as exc:
        return "product root %s cannot be resolved (%s)" % (pdir, exc)
    return None


def _get(root, slug):
    """(product, error): a scanned product whose root is a real folder."""
    product = _product(root, slug)
    if product is None:
        return None, "unknown product %r" % slug
    problem = _product_dir_problem(root, product)
    if problem:
        return None, problem
    return product, None


def _confined(pdir, rel):
    """(path, problem): `rel` must be a relative POSIX path inside the product
    root whose existing components are real folders or files — no symbolic
    link is followed and the product root is never left physically."""
    if not isinstance(rel, str) or not rel.strip() or "\x00" in rel or "\\" in rel:
        return None, "invalid relative path %r" % (rel,)
    pure = PurePosixPath(rel)
    if pure.is_absolute() or rel.startswith("~") or ".." in pure.parts or not pure.parts:
        return None, "path %r escapes the product root" % rel
    cur = Path(pdir)
    for part in pure.parts:
        cur = cur / part
        if cur.is_symlink():
            return None, "%s is a symbolic link — never followed" % cur.relative_to(pdir).as_posix()
    if not core.is_within(pdir, cur):
        return None, "path %r escapes the product root" % rel
    return cur, None


@contextmanager
def _product_lock(pdir, timeout=LOCK_TIMEOUT):
    """Exclusive lock of ONE product's licence writers (manifest, holder's
    fields, written documents), taken with flock on the product DIRECTORY
    itself: no lock file is created in the product. Re-entrant within one
    thread; other threads and processes wait up to `timeout` (TimeoutError)."""
    key = os.path.realpath(str(pdir))
    held = getattr(_LOCAL, "held", None)
    if held is None:
        held = _LOCAL.held = set()
    if key in held:
        yield
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(pdir), flags)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError("lock of %s not acquired" % pdir)
                time.sleep(0.02)
        held.add(key)
        try:
            yield
        finally:
            held.discard(key)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _lock_refusal(slug, exc):
    if isinstance(exc, TimeoutError):
        return ("another licence command is running on product %s (lock not acquired) — retry; "
                "nothing written" % slug)
    return "product %s: %s — nothing written" % (slug, exc)


# ---- licence regime of a product ------------------------------------------------

def documents_regime(lic):
    """Documents regime of a product, derived from its LICENCE AXES — licence
    id and grant — never from the profile name (audit C-04): FREE (CC BY-NC-SA
    header), FREE_CLOSED (free-use grant), PRIVATE (proprietary notice),
    COMMERCIAL (EULA), IMPORTED (existing licence of an imported script kept,
    no PWS document). None when the axes are invalid or contradictory."""
    if not isinstance(lic, dict):
        return None
    if profiles.is_imported(lic):
        return IMPORTED_REGIME
    if lic.get("id") == profiles.CC_LICENSE_ID:
        return "FREE" if lic.get("grant") == "cc" else None
    if lic.get("id") == "PROPRIETARY":
        return REGIME_BY_GRANT.get(lic.get("grant"))
    return None


def documents_for(lic):
    """(kind, role, required) documents of a product's licence axes."""
    return DOCUMENTS.get(documents_regime(lic), ())


def terms_kind(lic):
    """Kind of the product's terms document (role 'terms'), or None."""
    return next((kind for kind, role, _req in documents_for(lic) if role == "terms"), None)


def _axes_text(lic):
    if not isinstance(lic, dict):
        return "licence block invalid"
    if profiles.is_imported(lic):
        return "existing licence of an imported script: %s, status %s" % (lic.get("id"), lic.get("status"))
    return "licence %s, grant %s" % (lic.get("id"), lic.get("grant"))


def _text(key, lang, **kwargs):
    """Localized text of the imported-licence path (catalogue first)."""
    if i18n.has_key(key):
        return i18n.t(key, lang, **kwargs)
    entry = _TEXTS[key]
    text = entry.get(i18n.normalize_language(lang)) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def _source_header(product):
    """Where the existing notice of an imported script is read in the
    product's source (the header, then the initial comment block after the
    //@version line — guard._licence_notice_region), or None when unreadable."""
    try:
        from . import guard
        text = Path(product["source"]).read_text(encoding="utf-8") if product.get("source") else ""
        return "\n".join(guard._licence_notice_region(text)[0])
    except (OSError, UnicodeDecodeError):
        return None


def _single_byte_text_problem(data):
    """Why non-UTF-8 bytes cannot be checked as an ASCII-compatible
    single-byte text (ISO 8859, Windows code pages…), or None: such a text
    keeps code and words in ASCII, so the checks see them. A control byte
    other than tab, line breaks and form feed, or almost no ASCII space,
    reveals another encoding (EBCDIC, UTF-16/32…), in which code would stay
    invisible to the checks (cross-check of 2026-11-14)."""
    if any((b < 0x20 and b not in (0x09, 0x0A, 0x0B, 0x0C, 0x0D)) or b == 0x7F for b in data):
        return "control bytes"
    if len(data) >= 40 and data.count(b" ") * 20 < len(data):
        return "almost no ASCII space"
    return None


def read_legal_document(pdir, rel):
    """(state, bytes, text) of ONE declared original legal document of an
    imported script — read-only, never through a symbolic link (any
    component), a regular file only, never outside the product root.
    `state["problem"]` explains a refusal: declaration not accepted (name or
    place, profiles.legal_document_path_problem), absent, declared with
    another case than the file's own name, symbolic link, special file, hard
    link (the same file elsewhere), unreadable, empty, larger than
    LEGAL_DOCUMENT_MAX_BYTES, or content that cannot be checked (a NUL byte:
    binary content or UTF-16/32; another non-UTF-8 text that is not an
    ASCII-compatible single-byte text). The bytes are the original ones —
    exported as they are, never rewritten nor translated; `text` serves the
    checks only: UTF-8 (a BOM stays in the bytes) or, failing that, a
    single-byte reading (Latin-1)."""
    state = {"path": rel, "kind": None, "size": None, "sha256": None, "encoding": None, "problem": None}
    problem = profiles.legal_document_path_problem(rel)
    if problem:
        state["problem"] = "declaration not accepted: %s" % problem
        return state, None, None
    pdir = Path(pdir)
    try:
        path, problem = _confined(pdir, rel)
    except OSError as exc:
        state["problem"] = "unreadable path (%s)" % (exc.strerror or exc)
        return state, None, None
    if problem:
        state.update(kind="symlink" if "symbolic link" in problem else None, problem=problem)
        return state, None, None
    try:
        if len(rel.split("/")) == 2:      # the folder under its exact name too (case-insensitive file systems)
            folder = rel.split("/")[0]
            root_names = os.listdir(str(pdir))
            if folder not in root_names:
                other = next((n for n in root_names if n.casefold() == folder.casefold()), None)
                state.update(kind="absent", problem=("declared under %r while the folder is named %r: declare its "
                                                      "exact name" % (folder, other)) if other
                             else "absent: no folder %s/ in the product" % folder)
                return state, None, None
        names = os.listdir(str(path.parent))
    except OSError as exc:
        state.update(kind="absent", problem="absent (%s)" % (exc.strerror or exc))
        return state, None, None
    if path.name not in names:
        other = next((n for n in names if n.casefold() == path.name.casefold()), None)
        state.update(kind="absent", problem=("declared as %r while the file is named %r: declare its exact name"
                                              % (rel, other)) if other else "absent: no such file in the product")
        return state, None, None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        try:
            linked = stat.S_ISLNK(os.lstat(str(path)).st_mode)
        except OSError:
            linked = False
        if linked:
            state.update(kind="symlink", problem="a symbolic link — never followed")
        else:
            state["problem"] = "unreadable (%s)" % (exc.strerror or exc)
        return state, None, None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            state.update(kind="special", problem="not a regular file — never exported")
            return state, None, None
        state["kind"] = "file"
        if info.st_nlink > 1:
            state["problem"] = ("a hard link (the same file exists elsewhere, %d names) — never exported: copy the "
                                "original document into the product as an independent file" % info.st_nlink)
            return state, None, None
        if info.st_size > LEGAL_DOCUMENT_MAX_BYTES:
            state.update(size=info.st_size, problem="larger than %d bytes — not checked, not exported"
                         % LEGAL_DOCUMENT_MAX_BYTES)
            return state, None, None
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            total += len(chunk)
            if total > LEGAL_DOCUMENT_MAX_BYTES:
                state["problem"] = "larger than %d bytes — not checked, not exported" % LEGAL_DOCUMENT_MAX_BYTES
                return state, None, None
            chunks.append(chunk)
        data = b"".join(chunks)
    except OSError as exc:
        state["problem"] = "unreadable (%s)" % (exc.strerror or exc)
        return state, None, None
    finally:
        os.close(fd)
    state.update(size=len(data), sha256=core.sha256_bytes(data))
    if not data:
        state["problem"] = "empty file — not an original legal document"
        return state, None, None
    if b"\x00" in data:
        state["problem"] = ("contains NUL bytes (binary content, or a UTF-16/32 encoding): only a text in UTF-8 or "
                            "in a single-byte encoding can be checked before export")
        return state, None, None
    try:
        text = data.decode("utf-8")
        state["encoding"] = "UTF-8 with BOM" if text.startswith("﻿") else "UTF-8"
    except UnicodeDecodeError:
        why = _single_byte_text_problem(data)
        if why:
            state["problem"] = ("neither UTF-8 nor an ASCII-compatible single-byte text (%s): its content cannot be "
                                "checked before export — the export waits; the holder decides how this document "
                                "is provided" % why)
            return state, None, None
        text = data.decode("latin-1")
        state["encoding"] = "single-byte, not UTF-8 (read as Latin-1 for the checks, kept as it is)"
    return state, data, text


def legal_documents_review(product):
    """Read-only state of the original legal documents of an imported script:
    (review, payloads) — (None, {}) for a profile licence. `payloads` maps
    every declared document accepted so far to its (bytes, text).
    `review["blockers"]` lists what keeps an export waiting, each with its
    resolution: documents not declared; a candidate found in the product but
    not declared (an export never leaves a legal document out silently); a
    declared document refused (read_legal_document). Nothing is recorded,
    rewritten nor translated here."""
    lic = product.get("license")
    if not profiles.is_imported(lic):
        return None, {}
    slug = product["slug"]
    pdir = Path(product["path"])
    declared = lic.get("documents")
    candidates = profiles.legal_document_candidates(pdir)
    review = {"declared": declared, "candidates": candidates, "undeclared": [], "documents": [],
              "blockers": [], "note": SPDX_SCOPE_NOTE}
    declare = ("`license confirm --slug %s --license-document <path>` (repeatable; the declaration lists every "
               "document)" % slug)
    move = ("move the original documents, as regular files, to the product root, directly under release/ or "
            "directly under LICENSES/ (as LICENSES/<licence>.txt) and declare them, or move what is not a document "
            "of this licence out of the product yourself")

    def shown(c):
        return "%s (%s)" % (c["path"], c["kind"] if c["declarable"] else c["reason"])

    if declared is None:
        found = ", ".join(shown(c) for c in candidates) or "none found in the product"
        review["blockers"].append(
            "the original legal documents of the imported licence are not declared (license.documents; legal "
            "documents found: %s) — declare those that accompany the existing licence with %s, or record that none "
            "does with `license confirm --slug %s --no-license-documents`%s"
            % (found, declare, slug, "; for an entry that cannot be declared where it is: " + move
               if any(not c["declarable"] for c in candidates) else ""))
        review["undeclared"] = [c["path"] for c in candidates]
        return review, {}
    if not isinstance(declared, list) or not all(isinstance(d, str) for d in declared):
        review["blockers"].append("license.documents is invalid — repair SCRIPT.json (see `scan`)")
        return review, {}
    keys, folded = set(declared), {d.casefold() for d in declared}
    undeclared = [c for c in candidates if c["path"] not in keys]    # exact names (case-sensitive file systems)
    review["undeclared"] = [c["path"] for c in undeclared]
    declarable = [c for c in undeclared if c["declarable"]]
    others = [c for c in undeclared if not c["declarable"]]
    if declarable:
        variants = [c["path"] for c in declarable if c["path"].casefold() in folded]
        review["blockers"].append(
            "legal document(s) found in the product but not declared: %s — an export never leaves a legal document "
            "out silently: declare it too (%s), or move a file that is not a document of this licence out of the "
            "product yourself%s" % (", ".join(shown(c) for c in declarable), declare,
                                    "; %s differs from a declared document only by case: both cannot be exported — "
                                    "keep one of them in the product" % ", ".join(variants) if variants else ""))
    if others:
        review["blockers"].append(
            "legal document(s) or folder(s) found that cannot be declared as they are: %s — %s"
            % (", ".join(shown(c) for c in others), move))
    payloads = {}
    for rel in declared:
        state, data, text = read_legal_document(pdir, rel)
        review["documents"].append(state)
        if state["problem"]:
            review["blockers"].append("declared legal document %s: %s — restore the original file (a regular text "
                                      "file inside the product, never a link) or correct the declaration (%s)"
                                      % (rel, state["problem"], declare))
        else:
            payloads[rel] = (data, text)
    return review, payloads


def existing_licence(product, lang="en"):
    """The existing licence of an imported script, as the guided path shows it
    (None for a profile licence): recorded identifier or « to analyse », the
    licence PROPOSAL read in the source header (never a legal proof), whether
    the header notice establishes the recorded licence exactly
    (`header_matches_record`: false for a missing notice, another licence of
    the family, or a notice that establishes no single identifier — several
    versions, a deprecated identifier, an ambiguous wording), the conflicts to
    analyse and what keeps release preparation and export from treating it as
    settled."""
    lic = product.get("license")
    if not profiles.is_imported(lic):
        return None
    from . import guard
    lid, state = lic.get("id"), lic.get("status")
    header = _source_header(product)
    prop = guard.header_licence_proposal(header) if header is not None else None
    coherent = None
    if prop is not None and state == "confirmed" and lid in profiles.IMPORTABLE_LICENSE_IDS:
        family = profiles.license_family(lid)
        read = [e for e in prop["read"] if e["family"] == family]
        stated = {e["id"] or e["other"] for e in read if e["id"] or e["other"]}
        established = any(e["id"] == lid for e in prop["licences"] if e["family"] == family)
        coherent = bool(read) and stated <= {lid} and established
    kept = state == "confirmed" and lid in profiles.IMPORTABLE_LICENSE_IDS
    findings = [{"code": f["code"], "detail": f["detail"]} for f in product.get("findings") or []
                if f.get("code") in ("LICENSE_TO_ANALYSE", "IMPORTED_LICENSE_CONFLICT", "IMPORTED_LICENSE_TERMS",
                                     "LICENSE_DOCUMENT_UNAVAILABLE")]
    legal_documents, _payloads = legal_documents_review(product)
    return {"id": lid, "status": state, "state": "kept" if kept else "to-analyse",
            "legal_documents": legal_documents,
            "label": (_text("license.imported.kept", lang, id=lid) if kept
                      else _text("license.imported.to_analyse", lang)),
            "header": None if prop is None else {k: prop[k] for k in ("state", "proposal", "licences",
                                                                      "proprietary_mark", "reasons", "notes")},
            "header_text": None if prop is None else guard.describe_proposal(prop),
            "header_matches_record": coherent,
            "warnings": findings,
            "release_blockers": profiles.license_release_blockers(lic),
            "note": ("a header detection is a proposal for the holder, never a legal proof; the licence, its "
                     "texts and its attributions are kept as they are — nothing is relicensed")}


def detect_source_licence(root, source_rel):
    """Licence PROPOSAL read in the header of ONE .pine source under scripts/
    (onboarding: the manifest may not exist yet). Read-only; never through a
    symbolic link nor outside scripts/; never a legal proof — the holder
    confirms before anything is recorded. The notice is read in the header
    (`header_lines`) and in the initial comment block after the //@version
    line (`after_version_lines`), where an imported notice may stand."""
    from . import guard
    root = Path(root)
    scripts = root / "scripts"
    if not isinstance(source_rel, str) or not source_rel.strip():
        return {"ok": False, "error": "--source must be the path of a .pine file under scripts/"}
    rel = PurePosixPath(source_rel.strip())
    if rel.is_absolute() or ".." in rel.parts or len(rel.parts) < 2 or rel.parts[0] != "scripts" \
            or rel.suffix != ".pine":
        return {"ok": False, "error": "%r is not a relative path of a .pine file under scripts/" % source_rel}
    if scripts.is_symlink():
        return {"ok": False, "error": "scripts/ is a symbolic link — nothing read"}
    path, problem = _confined(scripts, PurePosixPath(*rel.parts[1:]).as_posix())
    if problem:
        return {"ok": False, "error": "%s — nothing read" % problem}
    if not path.is_file():
        return {"ok": False, "error": "%s does not exist" % rel.as_posix()}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": "%s unreadable (%s)" % (rel.as_posix(), exc)}
    header = guard._header_region(text)
    lines, _span = guard._licence_notice_region(text)     # header + initial comment block after //@version
    prop = guard.header_licence_proposal("\n".join(lines))
    out = {"ok": True, "source": rel.as_posix(), "header_lines": [ln for ln in header if ln.strip()],
           "after_version_lines": [ln for ln in lines[len(header):] if ln.strip()]}
    out.update({k: prop[k] for k in ("state", "proposal", "licences", "proprietary_mark", "reasons", "notes")})
    out["summary"] = guard.describe_proposal(prop)
    if prop["state"] == "recognized":
        out["record_if_confirmed"] = {"origin": "imported", "status": "confirmed", "id": prop["proposal"],
                                      "grant": profiles.imported_grant(prop["proposal"])}
    elif prop["state"] == "to-analyse":
        out["record_if_confirmed"] = {"origin": "imported", "status": "to-analyse", "id": None,
                                      "grant": "license"}
    else:
        out["record_if_confirmed"] = None
    # legal documents next to the source (product folder scripts/<slug>/): a list to review, never recorded here
    pdir = scripts / rel.parts[1] if len(rel.parts) >= 3 else None
    out["legal_document_candidates"] = (profiles.legal_document_candidates(pdir)
                                        if pdir is not None and not pdir.is_symlink() else [])
    out["note"] = ("PROPOSAL read in the header, to be confirmed by the holder — never a legal proof; nothing "
                   "is recorded nor written. A licence of the holder's own script may instead take a profile "
                   "(FREE, PRIVATE, COMMERCIAL); the existing licence of an imported script is kept with its "
                   "texts and attributions (docs/licensing/PROFILES.md). Its original legal documents (licence "
                   "text, NOTICE, attributions) stay as they are in the product — root, release/ or LICENSES/ — "
                   "and are declared by the holder once the product is onboarded (`license confirm "
                   "--license-document <path>`, or `--no-license-documents`); " + SPDX_SCOPE_NOTE + ".")
    return out


def _manifest_problems(product):
    """BROKEN findings of the manifest itself (source, context and evidence
    findings belong to other paths and never block the licence path)."""
    return [{"code": f["code"], "detail": f["detail"]} for f in product.get("findings") or []
            if f.get("severity") == "BROKEN"
            and not str(f.get("code", "")).startswith(("SOURCE_", "CONTEXT_", "VALIDATION", "EVIDENCE"))]


def _is_draft_text(text):
    return DRAFT_MARKER in text or bool(profiles.TEMPLATE_RESIDUE_RE.search(text))


def _first_difference(a, b):
    la, lb = a.splitlines(), b.splitlines()
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return i
    return min(len(la), len(lb)) + 1


# ---- holder's fields ------------------------------------------------------------

def _fields_file(product_dir):
    """The holder's fields of `release/eula-fields.json` (audit C-07): only
    the declared holder fields with a non-blank value free of template syntax
    feed the rendering; any other key stays in the file but is IGNORED and
    reported — identity, years and URLs always come from the manifest and the
    configuration. Never read through a symbolic link."""
    out = {"values": {}, "error": None, "ignored": []}
    path, problem = _confined(product_dir, FIELDS_REL)
    if problem:
        out["error"] = "%s not read: %s" % (FIELDS_REL, problem)
        return out
    data, err = core.read_json(path)
    if err == "missing":
        return out
    if err or not isinstance(data, dict):
        out["error"] = "%s %s" % (FIELDS_REL, err or "is not an object")
        return out
    for key, value in data.items():
        if key not in FIELD_NAMES:
            out["ignored"].append("%s (not a holder field)" % key)
        elif not isinstance(value, str) or not value.strip():
            continue
        elif any(tok in value for tok in TEMPLATE_SYNTAX):
            out["ignored"].append("%s (template syntax in the value)" % key)
        else:
            out["values"][key] = value
    return out


def _eula_fields(product_dir):
    fields = _fields_file(product_dir)
    return fields["values"], fields["error"]


# ---- rendering -----------------------------------------------------------------

def header_hints(product):
    """Facts OBSERVED in the source header, offered as references to confirm
    (never written to the manifest): copyright year, publication mode words."""
    hints = {"year": None, "mode": None}
    try:
        from . import guard
        text = Path(product["source"]).read_text(encoding="utf-8") if product.get("source") else ""
        header = "\n".join(guard._header_region(text))
    except (OSError, UnicodeDecodeError):
        return hints
    m = HEADER_YEAR_RE.search(header)
    if m:
        hints["year"] = int(m.group(1))
    for mode, rx in HEADER_MODE_RES:
        if rx.search(header):
            hints["mode"] = mode
            break
    return hints


def _source_header_licences(product):
    """Other licences recognized in the source header (MPL-2.0, MIT, …):
    reported for the holder, never written nor replaced."""
    try:
        from . import guard
        text = Path(product["source"]).read_text(encoding="utf-8") if product.get("source") else ""
        foreign, _statement = guard.header_licences("\n".join(guard._header_region(text)))
    except (OSError, UnicodeDecodeError):
        return []
    return foreign


def context(root, slug):
    """Placeholder values for a product (never invented: unknown → None)."""
    product, err = _get(root, slug)
    if err:
        return None, err
    return _context_for(root, product), None


def _context_for(root, product):
    ident = config.identity(root)
    lic = product.get("license") or {}
    pub = product.get("publication") or {}
    holder = lic.get("copyright_holder") or ident.get("copyright_holder")
    title = None
    try:
        from . import guard
        text = Path(product["source"]).read_text(encoding="utf-8") if product.get("source") else ""
        st, t = guard.extract_title(text)
        title = t if st == "EXTRACTED" else None
    except (OSError, UnicodeDecodeError):
        title = None
    year = lic.get("created_year")
    this_year = datetime.date.today().year
    if isinstance(year, int) and not isinstance(year, bool):
        year_range = "%d–%d" % (year, this_year) if year < this_year else str(year)
        created = str(year)
    else:
        year_range, created = None, None   # unknown stays unknown
    mode = pub.get("mode")
    mode_text = {"open": "open-source", "protected": "protected", "invite-only": "invite-only"}.get(mode)
    kind = product.get("script_kind")
    values = {
        "COPYRIGHT_HOLDER": holder,
        "CREATED_YEAR": created,
        "CURRENT_YEAR": str(this_year),
        "YEAR_RANGE": year_range,
        "PRODUCT_NAME": title,
        "PRODUCT_SLUG": product.get("slug"),
        "PROFILE": product.get("profile"),
        "SCRIPT_KIND": kind if kind in core.SCRIPT_KINDS else None,
        "LICENSE_ID": lic.get("id"),
        "GRANT": lic.get("grant"),
        "SOURCE_VISIBILITY": lic.get("source_visibility"),
        "ACCESS": lic.get("access"),
        "PUBLICATION_STATE": pub.get("state"),
        "PUBLICATION_PRIVACY": pub.get("privacy"),
        "PUBLICATION_MODE": mode_text,
        "TERMS_URL": lic.get("terms_url"),
        "CC_URL": profiles.CC_URL,
    }
    fields = _fields_file(product["path"])
    values.update(fields["values"])      # the holder's fields only (audit C-07)
    return {"product": product, "values": values, "fields": fields["values"],
            "eula_fields_error": fields["error"], "fields_ignored": fields["ignored"]}


def render_text(template, values, kind):
    """Pure rendering. Returns {text, missing, error}. `missing` lists the
    placeholders left unfilled; `error` is set when the template is malformed."""
    text = TEMPLATE_NOTE_RE.sub("", template)

    def optional(m):
        flag, key, body = m.group(1), m.group(2), m.group(3)
        present = bool(values.get(key))
        return body if (present if flag == "?" else not present) else ""

    text = OPTIONAL_BLOCK_RE.sub(optional, text)
    missing = []

    def sub(m):
        key = m.group(1)
        val = values.get(key)
        if val is None or val == "":
            missing.append(key)
            return "{{%s}}" % key
        return str(val)

    text = PLACEHOLDER_RE.sub(sub, text)
    if kind in HEADER_KINDS and values.get("TERMS_URL"):
        text = text.replace("// Version: X.Y.Z", "// Terms of use: %s\n// Version: X.Y.Z" % values["TERMS_URL"], 1)
    # a line emptied by optional blocks disappears; no triple blank lines
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # residual block syntax (anything left once the legitimate {{KEY}}
    # placeholders of a draft are set aside) means a malformed template
    error = None
    stripped = PLACEHOLDER_RE.sub("", text)
    for token in ("[[", "]]", "{{", "}}"):
        pos = stripped.find(token)
        if pos >= 0:
            error = "template malformed: residual block syntax %r (line %d of the rendered text)" % (
                token, stripped.count("\n", 0, pos) + 1)
            break
    return {"text": text, "missing": sorted(set(missing)), "error": error}


def render(root, slug, kind):
    """Pure rendering of one document (preview): never written. A kind that is
    not a document of the product's licence axes is still rendered for
    reference, flagged `applicable: false` (`write` refuses it)."""
    if kind not in KINDS:
        return {"ok": False, "error": "unknown kind %r (allowed: %s)" % (kind, ", ".join(KINDS))}
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    return _render_for(root, product, kind)


def _render_for(root, product, kind, ctx=None):
    ctx = ctx if ctx is not None else _context_for(root, product)
    tpath = Path(root) / TEMPLATES_REL / KINDS[kind]
    try:
        template = tpath.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": "template missing: %s (%s)" % (tpath, exc)}
    r = render_text(template, ctx["values"], kind)
    if r["error"]:
        return {"ok": False, "kind": kind, "error": r["error"], "draft": True,
                "missing_fields": r["missing"], "required_missing": r["missing"]}
    # optional fields never leave a placeholder; an unfilled year range means
    # the creation year is unknown: report the field the holder must set
    required_missing = sorted({("CREATED_YEAR" if k == "YEAR_RANGE" else k) for k in r["missing"]})
    draft = bool(required_missing)
    text = r["text"]
    if draft and kind not in HEADER_KINDS:
        banner = ("> **%s** — missing: %s. Fill `release/eula-fields.json` / the manifest "
                  "(created_year, identity), then render again; this banner disappears when the "
                  "document is complete.\n\n" % (DRAFT_MARKER, ", ".join(required_missing)))
        text = banner + text
    lic = ctx["product"].get("license")
    out = {"ok": True, "kind": kind, "text": text, "missing_fields": r["missing"],
           "draft": draft, "required_missing": required_missing,
           "eula_fields_error": ctx["eula_fields_error"], "permission": PERMISSION_NOTE,
           "applicable": kind in [k for k, _r, _q in documents_for(lic)]}
    if ctx["fields_ignored"]:
        out["fields_ignored"] = ctx["fields_ignored"]
    if not out["applicable"]:
        out["note"] = ("reference only: %r is not a document of this product (%s) — `license write` "
                       "refuses it" % (kind, _axes_text(lic)))
    return out


# ---- status ------------------------------------------------------------------

def _derivations(manifest):
    mig = manifest.get("migration") if isinstance(manifest, dict) else None
    if not isinstance(mig, dict):
        return {}
    return {k: mig.get(k) for k in ("from_schema", "from_distribution", "from_publication",
                                     "rectifications", "holder_confirmed") if k in mig}


def _terms_state(root, product, ctx):
    """State of the attached terms document (`terms_ref`), derived from the
    document itself (audit C-02): None (nothing attached), current, draft,
    stale, missing, unreadable, unverifiable or not-applicable."""
    lic = product.get("license") or {}
    ref = lic.get("terms_ref")
    kind = terms_kind(product.get("license"))
    out = {"ref": ref, "kind": kind, "state": None, "detail": None}
    if not ref:
        return out
    if kind is None:
        out.update(state="not-applicable",
                   detail="no terms document applies to these licence axes (%s)" % _axes_text(lic))
        return out
    path, problem = _confined(product["path"], ref)
    if problem:
        out.update(state="unreadable", detail=problem)
        return out
    if not path.is_file():
        out.update(state="missing", detail="%s does not exist" % ref)
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        out.update(state="unreadable", detail=str(exc))
        return out
    if _is_draft_text(text):
        out.update(state="draft", detail="draft banner or unfilled template field")
        return out
    r = _render_for(root, product, kind, ctx)
    if not r["ok"]:
        out.update(state="unverifiable", detail=r["error"])
    elif r["text"] == text and not r["draft"]:
        out["state"] = "current"
    elif r["text"] == text:
        out.update(state="draft", detail="missing: %s" % ", ".join(r["required_missing"]))
    else:
        out.update(state="stale", detail="differs from the current rendering of the %s document "
                                         "(first difference at line %d)" % (kind, _first_difference(text, r["text"])))
    return out


def status(root, slug):
    """Licence status of a product: profile, axes, publication recorded vs
    proposed, header hints, EULA draft/complete/n-a, declared legal reference,
    attached terms document and its state."""
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    return _status_for(root, product, _context_for(root, product))


def _imported_notes(out, existing, slug):
    """Notes of the existing licence of an imported script (status)."""
    notes = out["notes"]
    if existing["state"] == "kept":
        notes.append("existing licence kept: %s (imported script) — the licence itself defines the rights: no "
                     "PWS terms document applies (no header template, EULA, notice nor grant is generated); its "
                     "notices and attributions stay in the source as they are" % existing["id"])
        if existing["header_matches_record"] is False:
            notes.append("the source header does not establish the recorded licence %s (read in the header: %s) "
                         "— the holder corrects the record if needed, never the notice (see `guard`)"
                         % (existing["id"], existing["header_text"]))
    else:
        notes.append("existing licence TO ANALYSE (imported script, no identifier recorded): current work "
                     "continues; release preparation and export wait until the holder records the exact licence "
                     "(`license confirm --slug %s --license-id <SPDX identifier of the closed list>`) — read in "
                     "the header: %s" % (slug, existing["header_text"] or "source unreadable"))
    for w in existing["warnings"]:
        if w["code"] not in ("LICENSE_TO_ANALYSE", "LICENSE_DOCUMENT_UNAVAILABLE"):
            notes.append("%s: %s" % (w["code"], w["detail"]))
    docs = existing.get("legal_documents") or {}
    if isinstance(docs.get("declared"), list) and not docs.get("blockers"):
        notes.append("original legal documents declared: %s — exported verbatim with the script (%s)"
                     % (", ".join(docs["declared"]) or "none (no separate document accompanies the script)",
                        SPDX_SCOPE_NOTE))
    for blocker in docs.get("blockers") or []:
        notes.append("export waits: %s" % blocker)


def _status_for(root, product, ctx, lang="en"):
    slug = product["slug"]
    lic = product.get("license") or {}
    pub = product.get("publication") or {}
    imported = profiles.is_imported(product.get("license"))
    manifest, _ = core.read_json(Path(product["path"]) / "SCRIPT.json")
    closed = lic.get("id") == "PROPRIETARY" and product.get("profile") == "FREE"
    proposed = profiles.default_publication(product["profile"], closed_source=closed) \
        if product.get("profile") in profiles.PROFILES else None
    hints = header_hints(product)
    regime = documents_regime(product.get("license"))
    terms = _terms_state(root, product, ctx)
    problems = _manifest_problems(product)
    existing = existing_licence(product, lang)
    out = {"ok": True, "slug": slug, "profile": product.get("profile"),
           "profile_variant": profiles.profile_variant(product.get("profile"), lic),
           "documents_regime": regime,
           "license": {k: lic.get(k) for k in ("id", "grant", "source_visibility", "access",
                                               "copyright_holder", "created_year", "terms_ref",
                                               "terms_url")},
           "license_origin": profiles.license_origin(product.get("license")),
           "existing_licence": existing,
           "license_release_blockers": profiles.license_release_blockers(product.get("license")),
           "publication": {k: pub.get(k) for k in ("state", "privacy", "mode")},
           "publication_proposed_by_profile": proposed,
           "header_hints": hints,
           "derivations": _derivations(manifest),
           "copyright_holder_effective": ctx["values"].get("COPYRIGHT_HOLDER"),
           "identity_configured": ctx["values"].get("COPYRIGHT_HOLDER") is not None,
           "eula": "n/a", "eula_missing_fields": [], "terms_draft": None, "terms": terms,
           "manifest_status": product.get("product_structure_status"),
           "manifest_problems": problems, "notes": []}
    if imported:
        out["license"].update({k: lic.get(k) for k in profiles.LICENSE_IMPORT_KEYS})
    if problems:
        out["notes"].append("SCRIPT.json is BROKEN (%s) — repair it first: the licence information "
                            "shown may be incomplete and nothing is confirmed into a broken manifest"
                            % "; ".join("%s: %s" % (p["code"], p["detail"]) for p in problems[:3]))
    elif regime is None:
        out["notes"].append("licence axes invalid or contradictory (%s): no licence document applies"
                            % _axes_text(product.get("license")))
    if regime not in (None, IMPORTED_REGIME) and product.get("profile") in profiles.PROFILES \
            and regime != profiles.profile_variant(product["profile"], lic):
        out["notes"].append("the documents follow the licence axes (%s → %s), not the profile %s "
                            "(PROFILE_AXES_DIVERGENCE) — confirm which one is right (holder's decision)"
                            % (_axes_text(lic), regime, product["profile"]))
    if existing is not None:
        _imported_notes(out, existing, slug)
    else:
        foreign = _source_header_licences(product)
        if foreign:
            out["header_licences"] = foreign
            out["notes"].append("the source header mentions %s besides or instead of the declared licence "
                                "(%s): a third-party notice to keep, or a licence decision of the holder — "
                                "never removed nor replaced automatically" % (", ".join(foreign), lic.get("id")))
    if lic.get("derived_from_v1"):
        out["notes"].append("axes derived from legacy distribution %r — run migrate" % lic["derived_from_v1"])
    if pub.get("derived_from_v2"):
        out["notes"].append("publication derived from legacy value %r — run migrate" % pub["derived_from_v2"])
    unknown = [k for k in ("state", "privacy", "mode") if pub.get(k) is None]
    if unknown and pub.get("state") != "unpublished":
        out["notes"].append("publication %s unknown — confirm with `license confirm` (profile proposes %s)"
                            % (", ".join(unknown), proposed))
    if hints["mode"] and pub.get("mode") is None:
        out["notes"].append("header mentions a %r publication — reference to confirm, not recorded" % hints["mode"])
    if lic.get("created_year") is None and not imported:
        out["notes"].append("created_year unknown — headers stay drafts until it is set"
                            + (" (header shows © %d: reference to confirm, not recorded)" % hints["year"]
                               if hints["year"] else ""))
    if lic.get("grant") == "eula":
        # same values as the rendering: a field recorded by the holder, or a
        # value derived from the product itself (PRODUCT_NAME from the title)
        missing = [f for f in EULA_REQUIRED_FIELDS if not ctx["values"].get(f)]
        if ctx["values"].get("COPYRIGHT_HOLDER") is None:
            missing.insert(0, "COPYRIGHT_HOLDER")
        if lic.get("created_year") is None:
            missing.append("CREATED_YEAR")
        out["eula_missing_fields"] = missing
        # complete only when the ATTACHED document is the current, complete
        # rendering of the recorded information (audit C-02)
        out["eula"] = "complete" if not missing and terms["state"] == "current" else "draft"
        if not lic.get("terms_ref"):
            out["notes"].append("terms_ref not set: the rendered EULA is not yet attached to the product")
        if ctx["eula_fields_error"]:
            out["notes"].append(ctx["eula_fields_error"])
        if out["eula"] == "draft":
            out["notes"].append("EULA DRAFT — development continues; settle the fields before a "
                                "commercial publication (never invent legal identity, jurisdiction, "
                                "refund or commercial terms)")
    ref = lic.get("terms_ref")
    if ref:
        tpath, problem = _confined(product["path"], ref)
        try:
            ttext = tpath.read_text(encoding="utf-8") if tpath is not None else None
        except (OSError, UnicodeDecodeError):
            ttext = None
        out["terms_draft"] = (DRAFT_MARKER in ttext or bool(PLACEHOLDER_RE.search(ttext))
                              or "[[" in ttext or "]]" in ttext) if ttext is not None else None
        if out["terms_draft"]:
            out["notes"].append("attached terms (%s) are still a DRAFT — not exportable, not publishable" % ref)
        if terms["state"] == "stale":
            out["notes"].append("attached terms (%s) are no longer the current rendering of the recorded "
                                "information (%s) — write them again (`license write --slug %s --kind %s`); "
                                "not exportable as they are" % (ref, terms["detail"], slug, terms["kind"]))
        elif terms["state"] in ("missing", "unreadable", "unverifiable", "not-applicable"):
            out["notes"].append("attached terms (%s): %s — %s" % (ref, terms["state"], terms["detail"]))
    if ctx["fields_ignored"]:
        out["notes"].append("%s: ignored (never used for the rendering): %s"
                            % (FIELDS_REL, ", ".join(ctx["fields_ignored"])))
    if lic.get("terms_url") and not ref:
        out["notes"].append("terms_url declared but no terms document attached (terms_ref null)")
    if lic.get("access") == "paid" and lic.get("grant") != "eula":
        out["notes"].append("paid access without EULA grant — terms undefined")
    return out


# ---- writers -------------------------------------------------------------------

def _write_destination(product, kind, dest_rel):
    """(path, problem) of a `write` destination (audit C-01): a file directly
    under release/, with the extension of the document, never through a
    symbolic link; an existing file is replaced only at the default
    destination of this document or at the attached terms document."""
    default = DEFAULT_DEST[kind]
    path, problem = _confined(Path(product["path"]), dest_rel)
    if problem:
        return None, "destination %s" % problem
    pure = PurePosixPath(dest_rel)
    norm = pure.as_posix()
    if len(pure.parts) != 2 or pure.parts[0] != RELEASE_DIR:
        return None, "destination %r must be a file directly under release/ (default: %s)" % (dest_rel, default)
    suffix = PurePosixPath(default).suffix
    if pure.suffix != suffix:
        return None, "destination %r must end with %s, like %s" % (dest_rel, suffix, default)
    if path.exists() or path.is_symlink():
        if not path.is_file():
            return None, "destination %r exists and is not a regular file" % dest_rel
        lic = product.get("license")
        attached = (lic or {}).get("terms_ref")
        if norm != default and not (norm == attached and kind == terms_kind(lic)):
            return None, ("destination %r already exists and is neither the default destination of the "
                          "%s document (%s) nor its attached copy: an existing file is never overwritten"
                          % (dest_rel, kind, default))
    return path, None


def write_rendered(root, slug, kind, dest_rel):
    """Write a rendered document of the product (release/ by default). Only a
    document of the product's licence axes (audit C-08), only at a bounded
    destination (audit C-01). A draft is written WITH its banner; a malformed
    template is never written."""
    if kind not in KINDS:
        return {"ok": False, "error": "unknown kind %r (allowed: %s)" % (kind, ", ".join(KINDS))}
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    try:
        with _product_lock(Path(product["path"])):
            return _write_locked(root, slug, kind, dest_rel)
    except (TimeoutError, OSError) as exc:
        return {"ok": False, "error": _lock_refusal(slug, exc)}


def _write_locked(root, slug, kind, dest_rel):
    product, err = _get(root, slug)            # freshest manifest, under the lock
    if err:
        return {"ok": False, "error": err}
    lic = product.get("license")
    regime = documents_regime(lic)
    if regime is None:
        return {"ok": False, "error": "the licence axes of SCRIPT.json are invalid or contradictory (%s) — "
                                      "repair the manifest first (`license overview` lists the problems); "
                                      "nothing written" % _axes_text(lic)}
    if regime == IMPORTED_REGIME:
        return {"ok": False, "error": "the existing licence of this imported script is kept as it is (%s): no PWS "
                                      "document applies to it — nothing written" % _axes_text(lic)}
    allowed = [k for k, _r, _q in DOCUMENTS[regime]]
    if kind not in allowed:
        return {"ok": False, "error": "%r is not a document of this product (%s → %s): `license write` "
                                      "accepts %s; nothing written" % (kind, _axes_text(lic), regime,
                                                                       ", ".join(allowed))}
    dest, problem = _write_destination(product, kind, dest_rel)
    if problem:
        return {"ok": False, "error": problem + " — nothing written"}
    r = _render_for(root, product, kind)
    if not r["ok"]:
        return r
    dest.parent.mkdir(exist_ok=True)
    core.atomic_write_text(dest, r["text"])
    r["written"] = str(dest)
    return r


# ---- guided path « Licence and terms of use » --------------------------------

def default_dest(kind):
    """Default destination of a written document inside the product root."""
    return DEFAULT_DEST[kind]


def template_fields(root, kind):
    """(used, required) holder's field names of a template: `used` = every
    placeholder or optional block, `required` = placeholders standing outside
    optional blocks (a field used only in an optional block is optional).
    The dialogue asks nothing the template does not provide for."""
    tpath = Path(root) / TEMPLATES_REL / KINDS[kind]
    try:
        text = tpath.read_text(encoding="utf-8")
    except OSError:
        return set(), set()
    used = set(PLACEHOLDER_RE.findall(text)) | {m.group(2) for m in OPTIONAL_BLOCK_RE.finditer(text)}
    required = set(PLACEHOLDER_RE.findall(OPTIONAL_BLOCK_RE.sub("", text)))
    return used & set(FIELD_NAMES), required & set(FIELD_NAMES)


def overview(root, slug, lang="en"):
    """Read-only consolidated view for the guided path (writes nothing):
    profile variant, the documents of the licence axes (draft state, missing
    fields, written copy on disk and whether it is current), recorded facts,
    facts still to confirm (with the exact command), fields grouped for the
    dialogue (value recorded by the holder, or derived value shown as such),
    the state of the attached terms and the manifest problems, if any."""
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    ctx = _context_for(root, product)
    st = _status_for(root, product, ctx, lang)
    values = ctx["values"]
    variant = st["profile_variant"]
    regime = st["documents_regime"]
    lic, pub = st["license"], st["publication"]
    existing = st["existing_licence"]
    docs, used, required_fields = [], set(), set()
    for kind, role, required in DOCUMENTS.get(regime, ()):
        r = _render_for(root, product, kind, ctx)      # pure rendering, never written here
        dest_rel = DEFAULT_DEST[kind]
        dest, _problem = _confined(product["path"], dest_rel)
        on_disk = {"path": dest_rel, "exists": dest is not None and dest.is_file(),
                   "current": None, "draft": None}
        if on_disk["exists"]:
            try:
                disk = dest.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                disk = None
            if disk is not None:
                on_disk["current"] = (r.get("text") == disk) if r["ok"] else None
                on_disk["draft"] = DRAFT_MARKER in disk or bool(PLACEHOLDER_RE.search(disk))
        tf_used, tf_required = template_fields(root, kind)
        used |= tf_used
        if required:
            required_fields |= tf_required
        docs.append({"kind": kind, "role": role, "required": required,
                     "label": i18n.t("license.doc.%s" % kind, lang),
                     "role_label": i18n.t("license.role.%s" % role, lang),
                     "ok": r["ok"], "error": r.get("error"), "draft": r.get("draft"),
                     "required_missing": r.get("required_missing") or [],
                     "destination": dest_rel, "on_disk": on_disk,
                     "attached": lic.get("terms_ref") == dest_rel})
    recorded_fields, ferr = ctx["fields"], ctx["eula_fields_error"]
    groups = []
    for gid, names in FIELD_GROUPS:
        items = []
        for name in names:
            if name not in used:
                continue
            value = recorded_fields.get(name)
            derived = values.get(name) if value is None else None    # e.g. PRODUCT_NAME from the source title
            items.append({"name": name, "label": i18n.t("license.field.%s" % name, lang),
                          "required": name in required_fields, "value": value, "derived": derived,
                          "source": "fields" if value is not None else ("derived" if derived else None)})
        if items:
            groups.append({"id": gid, "label": i18n.t("license.group.%s" % gid, lang), "fields": items})
    missing = [f["name"] for g in groups for f in g["fields"]
               if f["required"] and not f["value"] and not f["derived"]]
    to_confirm = []
    if values.get("COPYRIGHT_HOLDER") is None and existing is None:   # an imported licence never needs it
        to_confirm.append({"key": "copyright_holder", "label": i18n.t("license.confirm.holder", lang),
                           "hint": None, "command": "config set identity.copyright_holder <name>"})
    if existing is not None and existing["state"] != "kept":
        to_confirm.append({"key": "license.id", "label": _text("license.confirm.license_id", lang),
                           "hint": (existing["header"] or {}).get("proposal"),
                           "command": "license confirm --slug %s --license-id <SPDX identifier>" % slug})
    if existing is not None and (existing.get("legal_documents") or {}).get("blockers"):
        to_confirm.append({"key": "license.documents", "label": _text("license.confirm.license_documents", lang),
                           "hint": [c["path"] for c in existing["legal_documents"]["candidates"]] or None,
                           "command": "license confirm --slug %s --license-document <path> (repeatable), or "
                                      "--no-license-documents" % slug})
    if lic.get("created_year") is None and existing is None:
        to_confirm.append({"key": "license.created_year", "label": i18n.t("license.confirm.created_year", lang),
                           "hint": st["header_hints"].get("year"),
                           "command": "license confirm --slug %s --created-year <year>" % slug})
    for key in ("state", "privacy", "mode"):
        if pub.get(key) is None:
            to_confirm.append({"key": "publication." + key,
                               "label": i18n.t("license.confirm.publication_%s" % key, lang),
                               "hint": (st["publication_proposed_by_profile"] or {}).get(key),
                               "command": "license confirm --slug %s --%s <value>" % (slug, key)})
    terms_doc = next((d for d in docs if d["role"] == "terms"), None)
    if terms_doc is not None and lic.get("terms_ref") is None:
        to_confirm.append({"key": "license.terms_ref", "label": i18n.t("license.confirm.terms_ref", lang),
                           "hint": terms_doc["destination"],
                           "command": "license confirm --slug %s --terms-ref %s" % (slug, terms_doc["destination"])})
    terms = st["terms"]
    draft = regime is None or bool(st["manifest_problems"]) \
        or any(d["draft"] or not d["ok"] for d in docs if d["required"]) \
        or (lic.get("grant") == "eula" and st["eula"] == "draft") \
        or (terms["ref"] is not None and terms["state"] != "current" and existing is None)
    holder_in_manifest = bool((product.get("license") or {}).get("copyright_holder"))
    if existing is not None:
        # an imported licence is kept as it is: « kept » or « to-analyse »,
        # never a draft of a PWS document (a broken manifest stays « draft »)
        status_value = "draft" if st["manifest_problems"] else existing["state"]
        profile_label = _text("license.imported.profile", lang, profile=st["profile"], licence=existing["label"])
        regime_label = _text("license.imported.regime", lang)
    else:
        status_value = "draft" if draft else "complete"
        profile_label = i18n.t("menu.profile.%s" % variant, lang)
        regime_label = i18n.t("menu.profile.%s" % regime, lang) if regime else None
    return {"ok": True, "slug": slug, "profile": st["profile"], "profile_variant": variant,
            "profile_label": profile_label,
            "documents_regime": regime,
            "documents_regime_label": regime_label,
            "license_origin": st["license_origin"],
            "license_state": existing["state"] if existing is not None else None,
            "existing_licence": existing,
            "license_release_blockers": st["license_release_blockers"],
            "recorded": {"copyright_holder": values.get("COPYRIGHT_HOLDER"),
                         "copyright_holder_source": ("manifest" if holder_in_manifest else
                                                     ("configuration" if values.get("COPYRIGHT_HOLDER") else None)),
                         "product_name": values.get("PRODUCT_NAME"), "created_year": lic.get("created_year"),
                         "license": lic, "publication": pub,
                         "terms_ref": lic.get("terms_ref"), "terms_url": lic.get("terms_url")},
            "documents": docs,
            "fields": {"storage": FIELDS_REL, "error": ferr, "ignored": ctx["fields_ignored"],
                       "groups": groups},
            "missing_fields": missing, "to_confirm": to_confirm,
            "status": status_value,
            "terms_attached": terms_doc is not None and lic.get("terms_ref") is not None,
            "terms_state": terms["state"],
            "manifest_status": st["manifest_status"], "manifest_problems": st["manifest_problems"],
            "notes": st["notes"], "legal_note": LEGAL_NOTE,
            "independent_of_release": True}


def set_fields(root, slug, updates, clear=(), dry_run=False):
    """Record holder-supplied field values in `release/eula-fields.json` of
    ONE product: existing values are kept unless explicitly changed or
    cleared, unknown keys already present are preserved, nothing is invented
    (an empty value is refused — use `clear`; template syntax is refused).
    `dry_run` returns the exact changes without writing (the recap shown
    before the grouped confirmation). The read-modify-write runs under the
    product lock (audit C-05). Never touches the manifest, the source or
    other products, never writes through a symbolic link."""
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    pdir = Path(product["path"])
    path, problem = _confined(pdir, FIELDS_REL)
    if problem:
        return {"ok": False, "error": "%s: %s — nothing written" % (FIELDS_REL, problem)}
    updates = {k: v for k, v in (updates or {}).items()}
    clear = list(clear or ())
    problems = []
    for k, v in updates.items():
        if k not in FIELD_NAMES:
            problems.append("%s: unknown field (allowed: %s)" % (k, ", ".join(FIELD_NAMES)))
        elif not isinstance(v, str) or not v.strip():
            problems.append("%s: empty value (use --clear to remove a value)" % k)
        elif any(tok in v for tok in TEMPLATE_SYNTAX):
            problems.append("%s: template syntax ({{ }}, [[ ]]) is not allowed in a value" % k)
    for k in clear:
        if k not in FIELD_NAMES:
            problems.append("%s: unknown field" % k)
        elif k in updates:
            problems.append("%s: both set and cleared" % k)
    if problems:
        return {"ok": False, "error": "; ".join(problems), "problems": problems}
    if dry_run:
        return _apply_fields(slug, path, updates, clear, dry_run=True)
    try:
        with _product_lock(pdir):
            out = _apply_fields(slug, path, updates, clear, dry_run=False)
    except (TimeoutError, OSError) as exc:
        return {"ok": False, "error": _lock_refusal(slug, exc)}
    if out.get("ok") and out.get("written"):
        out["status"] = status(root, slug)["eula"]
    return out


def _apply_fields(slug, path, updates, clear, dry_run):
    before = path.read_bytes() if path.exists() else None
    if before is None:
        data = {}
    else:
        try:
            data = json.loads(before.decode("utf-8"))
            problem = None if isinstance(data, dict) else "is not an object"
        except (ValueError, UnicodeDecodeError) as exc:
            problem = "invalid JSON: %s" % exc
        if problem:
            return {"ok": False, "error": "%s %s — repair it first; it is never overwritten blindly"
                                          % (FIELDS_REL, problem)}

    def current(k):
        v = data.get(k)
        return v.strip() if isinstance(v, str) and v.strip() else None

    changes, unchanged, merged = [], [], dict(data)
    for k, v in updates.items():
        if current(k) == v.strip():
            unchanged.append(k)
        else:
            changes.append({"field": k, "old": current(k), "new": v.strip()})
            merged[k] = v.strip()
    for k in clear:
        if current(k) is None:
            unchanged.append(k)
        else:
            changes.append({"field": k, "old": current(k), "new": None})
            merged[k] = ""
    out = {"ok": True, "slug": slug, "path": FIELDS_REL, "dry_run": dry_run,
           "changes": changes, "unchanged": unchanged, "written": None}
    if dry_run or not changes:
        return out
    now = path.read_bytes() if path.exists() else None
    if now != before:
        return {"ok": False, "error": "concurrent modification of %s detected — retry; nothing written" % FIELDS_REL}
    core.atomic_write_json(path, merged)
    written, err = core.read_json(path)
    if err or written != merged:
        return {"ok": False, "error": "post-write check of %s failed: %s" % (FIELDS_REL, err or "content differs")}
    out["written"] = str(path)
    return out


def _manifest_shape_problem(data):
    """Types the confirmation relies on (audit C-09): never a crash, never a
    blind rewrite of a section of an unexpected type."""
    if not isinstance(data.get("license"), dict):
        return "license must be an object"
    if not isinstance(data.get("publication"), dict):
        return "publication must be an object {state, privacy, mode}"
    mig = data.get("migration")
    if mig is None:
        return None
    if not isinstance(mig, dict):
        return "migration must be an object"
    confirmed = mig.get("holder_confirmed")
    if confirmed is not None and (not isinstance(confirmed, list)
                                  or not all(isinstance(c, str) for c in confirmed)):
        return "migration.holder_confirmed must be a list of strings"
    if mig.get("confirmations") is not None and not isinstance(mig.get("confirmations"), list):
        return "migration.confirmations must be a list"
    return None


def _broken_findings(slug, pdir, data):
    """BROKEN findings of a manifest dict under the checks of the scan (the
    source findings are not the licence path's concern)."""
    _v, _s, profile, lic, pub, found = scan.validate_manifest(slug, pdir, data)
    broken = [f for f in found if f["severity"] == "BROKEN" and not f["code"].startswith("SOURCE_")]
    return broken, profile, lic, pub


def _terms_ref_refusal(root, product, profile, lic, pub, rel):
    """Reason to refuse attaching `rel` as the product's terms (audit C-02,
    C-03): only the current and complete rendering of the terms document of
    the licence axes resulting from the confirmation can be attached."""
    kind = terms_kind(lic)
    if kind is None:
        return "no terms document applies to these licence axes (%s): nothing to attach" % _axes_text(lic)
    path, problem = _confined(product["path"], rel)
    if problem:
        return "terms_ref %s" % problem
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return "terms_ref %s unreadable (%s)" % (rel, exc)
    if _is_draft_text(text):
        return ("%s is still a DRAFT (draft banner or unfilled template field): complete the "
                "information, write it again (`license write --slug %s --kind %s`), then attach it"
                % (rel, product["slug"], kind))
    after = dict(product, profile=profile, license=lic, publication=pub)
    r = _render_for(root, after, kind)
    if not r["ok"]:
        return "the %s document cannot be rendered (%s): nothing attached" % (kind, r["error"])
    if r["draft"]:
        return ("the %s document is still a DRAFT (missing: %s): complete the information, write it "
                "again, then attach it" % (kind, ", ".join(r["required_missing"])))
    if text != r["text"]:
        return ("%s is not the current rendering of the %s document of this product (first difference "
                "at line %d): attach only a document written by `license write --slug %s --kind %s` "
                "and unchanged since" % (rel, kind, _first_difference(text, r["text"]), product["slug"], kind))
    return None


def confirm_publication(root, slug, state=None, privacy=None, mode=None, created_year=None,
                        terms_ref=None, terms_url=None, clear=(), license_id=None, license_documents=None):
    """Record publication facts (and optionally the creation year, the
    attached terms document and the declared terms URL) CONFIRMED by the
    holder in the manifest; confirmed keys are listed in
    `migration.holder_confirmed` so no rectification ever resets them.
    `clear` (names of CLEARABLE) returns confirmed values to « unknown »
    (null), removed from `holder_confirmed` and traced in `confirmations`.
    `license_id` records the EXACT identifier of the existing licence of an
    IMPORTED script confirmed by the holder (closed list only: a deprecated or
    ambiguous identifier, or any other licence, is refused — never on a
    profile licence); `clear=("license_id",)` returns it to « to analyse ».
    `license_documents` (a list; [] = none) records the original legal
    documents the holder declares for an IMPORTED script — the whole
    declaration, each document checked by read_legal_document, two documents
    never sharing an exported name; `clear=("license_documents",)` returns to
    « not declared ».

    The resulting manifest must pass the checks of the scan (a value that
    would make it BROKEN is refused, audit C-06); an attached terms document
    must be the current and complete rendering of the product's terms
    (audit C-02, C-03); the read-modify-write runs under the product lock
    with a freshest-state check (audit C-05)."""
    product, err = _get(root, slug)
    if err:
        return {"ok": False, "error": err}
    pdir = Path(product["path"])
    updates = {}
    for key, val, allowed in (("state", state, profiles.PUBLICATION_STATES),
                              ("privacy", privacy, profiles.PUBLICATION_PRIVACIES),
                              ("mode", mode, profiles.PUBLICATION_MODES)):
        if val is None:
            continue
        if val not in allowed:
            return {"ok": False, "error": "publication.%s must be one of %s" % (key, list(allowed))}
        updates["publication." + key] = val
    if created_year is not None:
        if not isinstance(created_year, int) or isinstance(created_year, bool) \
                or created_year < 2000 or created_year > datetime.date.today().year + 1:
            return {"ok": False, "error": "created_year must be a plausible year"}
        updates["license.created_year"] = created_year
    if terms_ref is not None:
        path, problem = _confined(pdir, terms_ref)
        if problem or not path.is_file():
            return {"ok": False, "error": "terms_ref must be an existing file inside the product root "
                                          "(render and write the document first)%s"
                                          % (": " + problem if problem else "")}
        if path.suffix != ".md":
            return {"ok": False, "error": "terms_ref must designate a Markdown terms document (.md) written "
                                          "by `license write`"}
        updates["license.terms_ref"] = PurePosixPath(terms_ref).as_posix()
    if terms_url is not None:
        if not profiles.HTTPS_URL_RE.match(terms_url):
            return {"ok": False, "error": "terms_url must be an https URL"}
        updates["license.terms_url"] = terms_url
    if license_id is not None:
        if license_id not in profiles.IMPORTABLE_LICENSE_IDS:
            deprecated = profiles.deprecated_license(license_id)
            known = profiles.importable_license(license_id)
            why = ("%s: never recorded — choose the exact \"-only\" or \"-or-later\" identifier from the notice"
                   % profiles.deprecated_reason(deprecated) if deprecated else
                   "use the exact identifier %r" % known if known else
                   "not in the closed list of recordable licences: the licence stays to analyse")
            return {"ok": False, "error": "license_id %r refused (%s; closed list: %s) — nothing written"
                                          % (license_id, why, ", ".join(profiles.IMPORTABLE_LICENSE_IDS))}
        updates["license.id"] = license_id
    if license_documents is not None:
        if isinstance(license_documents, str) or not isinstance(license_documents, (list, tuple)):
            return {"ok": False, "error": "license_documents must be a list of paths — nothing written"}
        docs, names = [], {}
        for rel in license_documents:
            doc, _data, _text = read_legal_document(pdir, rel)
            problem = doc["problem"]
            if problem is None and rel in docs:
                problem = "declared twice"
            if problem is None:
                target = profiles.legal_document_target(rel).casefold()
                if target in names:
                    problem = "%s and %s would be exported under the same name" % (names[target], rel)
                names[target] = rel
            if problem:
                return {"ok": False, "error": "legal document %r refused (%s) — nothing written" % (rel, problem)}
            docs.append(rel)
        updates["license.documents"] = docs
    clears = []
    for key in clear or ():
        dotted = CLEARABLE.get(key) or (key if key in CLEARABLE.values() else None)
        if dotted is None:
            return {"ok": False, "error": "%r cannot be cleared (allowed: %s)" % (key, ", ".join(CLEARABLE))}
        if dotted in updates:
            return {"ok": False, "error": "%s: both confirmed and cleared" % dotted}
        if dotted not in clears:
            clears.append(dotted)
    if not updates and not clears:
        return {"ok": False, "error": "nothing to confirm"}
    try:
        with _product_lock(pdir):
            return _confirm_locked(root, product, updates, clears)
    except (TimeoutError, OSError) as exc:
        return {"ok": False, "error": _lock_refusal(slug, exc)}


def _confirm_locked(root, product, updates, clears):
    slug = product["slug"]
    pdir = Path(product["path"])
    path = pdir / "SCRIPT.json"
    if path.is_symlink():
        return {"ok": False, "error": "SCRIPT.json is a symbolic link — nothing written"}
    try:
        before = path.read_bytes()
        data = json.loads(before.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": "SCRIPT.json unreadable (%s) — nothing written" % exc}
    if not isinstance(data, dict) or data.get("schema_version") != version.MANIFEST_SCHEMA_VERSION:
        return {"ok": False, "error": "manifest must be schema %d (run migrate first)" % version.MANIFEST_SCHEMA_VERSION}
    shape = _manifest_shape_problem(data)
    if shape:
        return {"ok": False, "error": "SCRIPT.json: %s — repair the manifest first (see `scan`); nothing written"
                                      % shape}
    if ("license.id" in updates or "license.id" in clears) and data["license"].get("origin") != "imported":
        return {"ok": False, "error": "license_id is recorded only for the existing licence of an imported script "
                                      "(license.origin 'imported'): a profile licence is never changed here — "
                                      "nothing written"}
    if ("license.documents" in updates or "license.documents" in clears) \
            and data["license"].get("origin") != "imported":
        return {"ok": False, "error": "license documents are recorded only for the existing licence of an imported "
                                      "script (license.origin 'imported'): the documents of a profile licence are "
                                      "the ones Pine Workspace renders — nothing written"}
    new = json.loads(json.dumps(data))
    for dotted, value in list(updates.items()) + [(k, None) for k in clears]:
        section, field = dotted.split(".")
        new[section][field] = value
    if "license.id" in updates:     # confirmed by the holder: the exact identifier and its grant
        new["license"]["status"] = "confirmed"
        new["license"]["grant"] = profiles.imported_grant(updates["license.id"])
    elif "license.id" in clears:    # back to « to analyse »: no identifier recorded
        new["license"]["status"] = "to-analyse"
        new["license"]["grant"] = "license"
    mig = dict(new.get("migration") or {})
    confirmed = [c for c in (mig.get("holder_confirmed") or []) if c not in clears]
    for k in updates:
        if k not in confirmed:
            confirmed.append(k)
    mig["holder_confirmed"] = confirmed
    values = dict(updates)
    values.update({k: None for k in clears})
    if "license.id" in updates or "license.id" in clears:
        values.update({"license.status": new["license"]["status"], "license.grant": new["license"]["grant"]})
    mig["confirmations"] = list(mig.get("confirmations") or []) + [
        {"on": datetime.date.today().isoformat(), "values": values}]
    new["migration"] = mig
    broken_after, profile, lic, pub = _broken_findings(slug, pdir, new)
    if broken_after:
        known = {(f["code"], f["detail"]) for f in _broken_findings(slug, pdir, data)[0]}
        parts = []
        introduced = [f for f in broken_after if (f["code"], f["detail"]) not in known]
        present = [f for f in broken_after if (f["code"], f["detail"]) in known]
        if introduced:
            parts.append("introduced by this confirmation: " + "; ".join(
                "%s: %s" % (f["code"], f["detail"]) for f in introduced))
        if present:
            parts.append("already present: " + "; ".join("%s: %s" % (f["code"], f["detail"]) for f in present))
        return {"ok": False, "error": "refused: the resulting manifest would be BROKEN (%s) — nothing written; "
                                      "confirm a coherent value or repair SCRIPT.json first" % " | ".join(parts)}
    if "license.terms_ref" in updates:
        refusal = _terms_ref_refusal(root, product, profile, lic, pub, updates["license.terms_ref"])
        if refusal:
            return {"ok": False, "error": refusal + " — nothing written"}
    if path.read_bytes() != before:
        return {"ok": False, "error": "concurrent modification of SCRIPT.json detected — retry; nothing written"}
    core.atomic_write_json(path, new)
    written, err = core.read_json(path)
    if err or written != new:
        return {"ok": False, "error": "post-write check of SCRIPT.json failed: %s" % (err or "content differs")}
    out = {"ok": True, "confirmed": updates, "path": str(path)}
    if clears:
        out["cleared"] = clears
    return out


def eula_fields_skeleton():
    """Skeleton of release/eula-fields.json with every field blank."""
    return json.dumps({k: "" for k in EULA_REQUIRED_FIELDS + EULA_OPTIONAL_FIELDS},
                      indent=2, ensure_ascii=False) + "\n"
