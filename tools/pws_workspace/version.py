# SPDX-License-Identifier: Apache-2.0
"""Workspace version, release identity and schema levels — the single source
for migrations, the distribution marker, the release metadata and the
guided update path.

WORKSPACE_VERSION identifies the layout and contracts of the Pine Workspace
core (tooling, manifests, configuration). It is NOT a product version: Pine
scripts carry their own `// Version:` header. Convention ratified on
2026-11-08 — MAJOR.MINOR.PATCH: MAJOR for a compatibility break, MINOR for a
compatible evolution, PATCH for a compatible correction. `migrate` applies
the steps an installation has not recorded yet, whatever the number says. A
published version is never replaced silently: a corrected delivery gets a
NEW number. 2.1.0 is the first public release (holder's decision of
2026-11-08).

Everything else is DERIVED from this module, never a second independent
value: the `VERSION` file and `workspace_version` of a built distribution,
the release tag (`v` + version), the archive name, `RELEASE.json`, and the
consistency check of `build-release` against the top entry of CHANGELOG.md.
"""
import re

WORKSPACE_VERSION = "2.1.0"
CONFIG_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 3
MANIFEST_SCHEMA_LEGACY = 1
MANIFEST_SCHEMA_V2 = 2   # read-compatible: publication as a single string

# Public home of the core. The guided update path reads its RELEASES there
# (read-only, unauthenticated). Product exports use the configured
# destinations of pws.config.json, never this constant.
OFFICIAL_REPOSITORY = "ricksimpsontrading/Pine-Workspace"
PACKAGE_BASENAME = "pine-workspace"    # archive pine-workspace-<version>.zip, top folder pine-workspace-<version>/
TAG_PREFIX = "v"

_VERSION_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                         r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def parse_version(text):
    """(major, minor, patch, prerelease_or_None) from "2.1.0", "v2.1.0" or
    "2.2.0-rc.1"; None when the text is not a MAJOR.MINOR.PATCH version.
    Versions are never compared as plain strings (2.10.0 > 2.9.0)."""
    if not isinstance(text, str):
        return None
    m = _VERSION_RE.match(text.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def is_prerelease(text):
    """True for a pre-release number (suffix after a hyphen: rc, beta…)."""
    parsed = parse_version(text)
    return bool(parsed and parsed[3])


def normalized(text):
    """Canonical "MAJOR.MINOR.PATCH[-pre]" text of a parsable version, else None."""
    parsed = parse_version(text)
    if parsed is None:
        return None
    base = "%d.%d.%d" % parsed[:3]
    return base + ("-" + parsed[3] if parsed[3] else "")


def prerelease_key(pre):
    """Sort key of a pre-release suffix by SemVer precedence (audit H-08):
    dot-separated identifiers, numeric ones compared numerically and ranked
    below alphanumeric ones; a longer list wins when the prefix is equal
    (rc.2 > rc.1 > beta.11 > beta.2 > alpha)."""
    key = []
    for ident in str(pre or "").split("."):
        key.append((0, int(ident), "") if ident.isdigit() else (1, 0, ident))
    return tuple(key)


def compare(a, b):
    """-1, 0 or 1 comparing two versions numerically (a pre-release ranks
    below the release of the same number; pre-releases follow SemVer
    precedence); None when one is unparsable."""
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return None
    ka = pa[:3] + ((0, prerelease_key(pa[3])) if pa[3] else (1, ()))
    kb = pb[:3] + ((0, prerelease_key(pb[3])) if pb[3] else (1, ()))
    return (ka > kb) - (ka < kb)


def release_tag(ver=None):
    return TAG_PREFIX + (ver or WORKSPACE_VERSION)


def package_name(ver=None):
    return "%s-%s" % (PACKAGE_BASENAME, ver or WORKSPACE_VERSION)
