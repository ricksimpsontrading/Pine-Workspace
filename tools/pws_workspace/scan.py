# SPDX-License-Identifier: Apache-2.0
"""Workspace scanner — the single implementation of product/source facts.

Output contract (spec section 44.1), per product root:
  product_structure_status: REGISTERED | INCOMPLETE | BROKEN | AMBIGUOUS
  (synthesis order: AMBIGUOUS > BROKEN > INCOMPLETE > REGISTERED)
plus, per .pine file: source_registration_status REGISTERED | UNREGISTERED,
plus the validation axes DELEGATED to validation.inspect_validation (single
mechanical owner — no divergent readers), plus the profile/licence axes
DELEGATED to profiles (schema 3 — with `license.origin` / `license.status`
only when the manifest records the existing licence of an imported script,
audit C-19 —; schemas 1 and 2 read-compatible, reported as derived). A
licence to analyse is a WARNING (LICENSE_TO_ANALYSE), never a mute BROKEN.

A parallel structured findings list always accompanies the synthetic value.
Types are validated before any semantic use: an invalid JSON shape yields an
actionable BROKEN diagnostic, never a crash. Physical boundaries: a symlinked
`scripts/` root, symlinked product roots, escaping manifests/contexts/sources
are refused without ever reading outside the workspace (spec section 6.1.5);
directory symlinks are never followed.
"""
from pathlib import Path

from . import core, profiles, validation, version

REQUIRED_MANIFEST_KEYS = {"schema_version", "id", "source", "script_kind", "distribution"}
MANIFEST_FIELD_TYPES = {
    "schema_version": int,
    "id": str,
    "source": str,
    "script_kind": str,
    "distribution": str,
}
CONTEXT_FILES = ("PRODUCT.md", "ARCHITECTURE.md", "CLAUDE.md")
# Known placeholder markers (mechanical, prudent — spec sections 2.4 / 44.2).
PLACEHOLDER_MARKERS = ("{{", "TODO", "TBD", "PLACEHOLDER", "LOREM IPSUM")


def _finding(findings, code, severity, path, detail):
    findings.append({
        "code": code,
        "severity": severity,
        "path": str(path),
        "detail": detail,
    })


def _escapes(container, path):
    """True if path is a symlink chain or reference leaving container."""
    return Path(path).is_symlink() and not core.is_within(container, path)


def _is_placeholder_or_empty(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "unreadable"
    if not text.strip():
        return "empty"
    upper = text.upper()
    for marker in PLACEHOLDER_MARKERS:
        if marker in upper:
            return "placeholder marker %r" % marker
    return None


def _pine_files_within(base):
    return sorted(p for p in core.iter_paths_within(base) if p.suffix == ".pine")


def _validate_manifest_v1(slug, product_dir, data, findings):
    """Validate SCRIPT.json v1 (legacy, read-compatible). Returns
    (status_votes, source_path_or_None, profile, license) — profile and
    licence are DERIVED from the legacy distribution and flagged as such.

    Types are checked BEFORE any semantic use (audit F8): a wrong-typed field
    produces a BROKEN diagnostic and skips the semantic checks that assume
    the type — never a TypeError.
    """
    votes = []
    keys = set(data.keys())
    unknown = sorted(keys - REQUIRED_MANIFEST_KEYS)
    missing = sorted(REQUIRED_MANIFEST_KEYS - keys)
    if unknown:
        _finding(findings, "MANIFEST_UNKNOWN_FIELDS", "BROKEN", product_dir,
                 "unknown fields rejected by schema v1: %s" % ", ".join(unknown))
        votes.append("BROKEN")
    if missing:
        _finding(findings, "MANIFEST_MISSING_FIELDS", "BROKEN", product_dir,
                 "missing required fields: %s" % ", ".join(missing))
        votes.append("BROKEN")
        return votes, None, None, None, None

    typed_ok = {}
    for field, expected in MANIFEST_FIELD_TYPES.items():
        value = data.get(field)
        ok = isinstance(value, expected) and not isinstance(value, bool)
        typed_ok[field] = ok
        if not ok:
            _finding(findings, "MANIFEST_FIELD_TYPE", "BROKEN", product_dir,
                     "%s must be %s, got %s (%r)" % (
                         field, expected.__name__, type(value).__name__, value))
            votes.append("BROKEN")

    if typed_ok["id"] and data["id"] != slug:
        _finding(findings, "MANIFEST_ID_SLUG_MISMATCH", "BROKEN", product_dir,
                 "id %r must equal product slug %r" % (data["id"], slug))
        votes.append("BROKEN")
    kind = data.get("script_kind") if typed_ok["script_kind"] else None
    dist = data.get("distribution") if typed_ok["distribution"] else None
    if typed_ok["script_kind"] and kind not in core.SCRIPT_KINDS:
        _finding(findings, "MANIFEST_KIND_INVALID", "BROKEN", product_dir,
                 "script_kind %r not in %s" % (kind, list(core.SCRIPT_KINDS)))
        votes.append("BROKEN")
    if typed_ok["distribution"] and dist not in core.DISTRIBUTIONS:
        _finding(findings, "MANIFEST_DISTRIBUTION_INVALID", "BROKEN", product_dir,
                 "distribution %r not in %s" % (dist, list(core.DISTRIBUTIONS)))
        votes.append("BROKEN")
    if isinstance(kind, str) and isinstance(dist, str) \
            and (kind, dist) in core.INVALID_KIND_DISTRIBUTION:
        _finding(findings, "KIND_DISTRIBUTION_MATRIX", "BROKEN", product_dir,
                 "library + paid-closed-source is invalid under the current TradingView rule")
        votes.append("BROKEN")

    source_path = None
    if typed_ok["source"]:
        source = data["source"]
        if not source:
            _finding(findings, "SOURCE_FIELD_INVALID", "BROKEN", product_dir,
                     "source must be a non-empty string")
            votes.append("BROKEN")
        elif Path(source).is_absolute():
            _finding(findings, "SOURCE_ABSOLUTE", "BROKEN", product_dir,
                     "absolute source path rejected")
            votes.append("BROKEN")
        else:
            candidate = product_dir / source
            if not core.is_within(product_dir, candidate):
                _finding(findings, "SOURCE_ESCAPES_ROOT", "BROKEN", product_dir,
                         "source resolves outside the product root (traversal or symlink)")
                votes.append("BROKEN")
            elif not candidate.is_file():
                _finding(findings, "SOURCE_MISSING", "BROKEN", product_dir,
                         "declared source %r not found" % source)
                votes.append("BROKEN")
            elif not source.endswith(".pine"):
                _finding(findings, "SOURCE_NOT_PINE", "BROKEN", product_dir,
                         "declared source %r is not a .pine file" % source)
                votes.append("BROKEN")
            else:
                source_path = candidate
    profile, lic, pub = (profiles.derive_from_legacy(dist) if isinstance(dist, str)
                         else (None, None, None))
    if profile is not None:
        _finding(findings, "MANIFEST_LEGACY_SCHEMA", "WARNING", product_dir,
                 "schema v1 manifest: profile %s, licence and publication axes DERIVED "
                 "from distribution %r (publication state unknown) — run `python3 -m "
                 "tools.pws_workspace migrate --plan` to write the explicit v3 form"
                 % (profile, dist))
        if isinstance(kind, str) and kind in core.SCRIPT_KINDS:
            for code, sev, detail in profiles.coherence_problems(kind, profile, lic, pub):
                _finding(findings, code, sev, product_dir, detail)
                if sev == "BROKEN":
                    votes.append("BROKEN")
    return votes, source_path, profile, lic, pub


def _validate_manifest(slug, product_dir, data, findings):
    """Dispatch on schema_version. Returns (votes, source_path, profile,
    license, publication)."""
    if not isinstance(data, dict):
        _finding(findings, "MANIFEST_NOT_OBJECT", "BROKEN", product_dir,
                 "SCRIPT.json is not a JSON object")
        return ["BROKEN"], None, None, None, None
    sv = data.get("schema_version")
    if isinstance(sv, bool) or not isinstance(sv, int):
        _finding(findings, "MANIFEST_FIELD_TYPE", "BROKEN", product_dir,
                 "schema_version must be int, got %s (%r)" % (type(sv).__name__, sv))
        return ["BROKEN"], None, None, None, None
    if sv == version.MANIFEST_SCHEMA_VERSION:
        return profiles.validate_manifest_v3(slug, product_dir, data, findings, _finding)
    if sv == version.MANIFEST_SCHEMA_V2:
        return profiles.validate_manifest_v2(slug, product_dir, data, findings, _finding)
    if sv == version.MANIFEST_SCHEMA_LEGACY:
        return _validate_manifest_v1(slug, product_dir, data, findings)
    _finding(findings, "MANIFEST_SCHEMA_VERSION", "BROKEN", product_dir,
             "schema_version must be %d (or legacy %d / %d), got %r"
             % (version.MANIFEST_SCHEMA_VERSION, version.MANIFEST_SCHEMA_LEGACY,
                version.MANIFEST_SCHEMA_V2, sv))
    return ["BROKEN"], None, None, None, None


def validate_manifest(slug, product_dir, data):
    """Checks of ONE product's manifest, exactly as the workspace scan applies
    them (single implementation shared with the guard and the licence
    writers). Returns (votes, source_path, profile, license, publication,
    findings); the licence and publication are the VALIDATED values (None
    when their block is invalid)."""
    findings = []
    votes, source_path, profile, lic, pub = _validate_manifest(slug, Path(product_dir), data, findings)
    return votes, source_path, profile, lic, pub, findings


def _validation_axes(product_dir, source_path, findings):
    """Delegate to the single owner (validation.inspect_validation) and map
    its findings into the product findings list."""
    view = validation.inspect_validation(product_dir, source_path)
    findings.extend(view["findings"])
    return {
        "validation_status": view["persisted"],
        "validation_integrity_status": view["integrity"],
        "validation_effective_status": view["effective"],
        "validation_run_id": view["run_id"],
    }


def _empty_product(slug, product_dir, status, p_findings):
    return {
        "slug": slug, "path": str(product_dir),
        "product_structure_status": status,
        "source": None, "script_kind": None, "distribution": None,
        "schema_version": None, "profile": None, "license": None, "publication": None,
        "findings": p_findings,
        "validation_status": None, "validation_integrity_status": None,
        "validation_effective_status": None, "validation_run_id": None,
    }


def scan_workspace(root):
    """Scan scripts/** and return the full mechanical state."""
    root = Path(root)
    scripts_dir = root / "scripts"
    result = {
        "scripts_dir_exists": False,
        "scripts_dir_symlink": False,
        "products": [],
        "unregistered_pine": [],
        "findings": [],
    }
    findings = result["findings"]
    # Physical boundary of the scripts root itself: a symlinked scripts/ would
    # route every read (and the Stop hook's hashes) outside the workspace.
    if scripts_dir.is_symlink():
        result["scripts_dir_symlink"] = True
        _finding(findings, "SCRIPTS_ROOT_SYMLINK", "BROKEN", scripts_dir,
                 "scripts/ is a symlink%s — nothing under it is read; make it a real "
                 "directory inside the workspace" % (
                     "" if core.is_within(root, scripts_dir) else " escaping the workspace"))
        return result
    result["scripts_dir_exists"] = scripts_dir.is_dir()
    if not result["scripts_dir_exists"]:
        return result  # no products: valid state, not an error

    claimed_sources = {}
    slug_lower_seen = {}
    product_dirs = sorted([d for d in scripts_dir.iterdir() if d.is_dir()])

    for product_dir in product_dirs:
        slug = product_dir.name
        p_findings = []
        votes = []

        # Physical boundary: a symlinked product root has no safe identity
        # and its content is NEVER read (spec sections 2.10 / 6.1.5).
        if product_dir.is_symlink():
            _finding(p_findings, "PRODUCT_ROOT_SYMLINK", "AMBIGUOUS", product_dir,
                     "product root is a symlink%s — identity not establishable, "
                     "content not scanned" % (
                         "" if core.is_within(root, product_dir)
                         else " escaping the workspace"))
            result["products"].append(_empty_product(slug, product_dir, "AMBIGUOUS", p_findings))
            findings.extend(p_findings)
            continue

        low = slug.lower()
        if low in slug_lower_seen:
            _finding(p_findings, "SLUG_CASE_COLLISION", "AMBIGUOUS", product_dir,
                     "slug collides case-insensitively with %r" % slug_lower_seen[low])
            votes.append("AMBIGUOUS")
        else:
            slug_lower_seen[low] = slug

        manifest_path = product_dir / "SCRIPT.json"
        manifest = None
        source_path = None
        profile, lic, pub = None, None, None
        if _escapes(product_dir, manifest_path):
            _finding(p_findings, "MANIFEST_ESCAPES", "BROKEN", manifest_path,
                     "SCRIPT.json is a symlink escaping the product root — not read")
            votes.append("BROKEN")
        else:
            manifest, err = core.read_json(manifest_path)
            if err == "missing":
                _finding(p_findings, "MANIFEST_MISSING", "INCOMPLETE", product_dir,
                         "SCRIPT.json missing")
                votes.append("INCOMPLETE")
            elif err:
                _finding(p_findings, "MANIFEST_UNREADABLE", "BROKEN", manifest_path, err)
                votes.append("BROKEN")
            else:
                mvotes, source_path, profile, lic, pub = _validate_manifest(
                    slug, product_dir, manifest, p_findings)
                votes.extend(mvotes)
                if source_path is not None:
                    key = str(source_path.resolve())
                    if key in claimed_sources:
                        _finding(p_findings, "SOURCE_MULTI_CLAIMED", "AMBIGUOUS",
                                 source_path,
                                 "source also claimed by %r" % claimed_sources[key])
                        votes.append("AMBIGUOUS")
                    else:
                        claimed_sources[key] = slug

        # Ambiguity: several .pine files but no manifest designating the main one.
        pine_files = _pine_files_within(product_dir)
        if manifest is None and len(pine_files) > 1:
            _finding(p_findings, "MAIN_SOURCE_AMBIGUOUS", "AMBIGUOUS", product_dir,
                     "%d .pine files and no manifest to designate the main source"
                     % len(pine_files))
            votes.append("AMBIGUOUS")

        for name in CONTEXT_FILES:
            path = product_dir / name
            if _escapes(product_dir, path):
                _finding(p_findings, "CONTEXT_ESCAPES", "BROKEN", path,
                         "%s is a symlink escaping the product root — not read" % name)
                votes.append("BROKEN")
                continue
            if not path.is_file():
                _finding(p_findings, "CONTEXT_MISSING", "INCOMPLETE", path,
                         "%s missing" % name)
                votes.append("INCOMPLETE")
            else:
                problem = _is_placeholder_or_empty(path)
                if problem:
                    _finding(p_findings, "CONTEXT_PLACEHOLDER", "INCOMPLETE", path, problem)
                    votes.append("INCOMPLETE")

        axes = _validation_axes(product_dir, source_path, p_findings)
        for f in p_findings:
            if f["code"] == "VALIDATION_STATE_MISSING":
                votes.append("INCOMPLETE")
            elif f["severity"] == "BROKEN" and f["code"].startswith(("VALIDATION", "EVIDENCE")):
                votes.append("BROKEN")

        for order in ("AMBIGUOUS", "BROKEN", "INCOMPLETE"):
            if order in votes:
                status = order
                break
        else:
            status = "REGISTERED"

        is_manifest = isinstance(manifest, dict)
        product = {
            "slug": slug,
            "path": str(product_dir),
            "product_structure_status": status,
            "source": str(source_path) if source_path else None,
            "script_kind": manifest.get("script_kind") if is_manifest else None,
            "distribution": (manifest.get("distribution")
                             if is_manifest and manifest.get("schema_version") == 1 else None),
            "schema_version": manifest.get("schema_version") if is_manifest else None,
            "profile": profile,
            "license": lic,
            "publication": pub,
            "findings": p_findings,
        }
        product.update(axes)
        result["products"].append(product)
        findings.extend(p_findings)

    # Source registration axis: every .pine under scripts/** must be claimed.
    # Directory symlinks are never followed; escaping paths never listed.
    registered = {str(Path(p["source"]).resolve()) for p in result["products"]
                  if p["source"]}
    for pine in _pine_files_within(scripts_dir):
        if str(pine.resolve()) not in registered:
            result["unregistered_pine"].append(str(pine))
            _finding(findings, "PINE_UNREGISTERED", "WARNING", pine,
                     "orphan .pine: not the canonical source of any valid SCRIPT.json")
    for pine in sorted(scripts_dir.glob("*.pine")):
        _finding(findings, "PINE_AT_SCRIPTS_ROOT", "WARNING", pine,
                 ".pine directly under scripts/ — not onboardable in place; "
                 "do not move silently")

    return result
