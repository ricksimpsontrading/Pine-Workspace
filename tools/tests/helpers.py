# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the tooling tests.

Temporary roots deliberately contain a SPACE in their name (spec section 6.1:
discovery and tests must cover workspace roots and source names with spaces).
"""
import json
import tempfile
from pathlib import Path

FREE_HEADER = (
    "// This work is licensed under the Attribution-NonCommercial-ShareAlike 4.0 "
    "International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n"
    "// © LegacyHolder\n"
    "// Version: 1.0.0\n"
    "//@version=6\n"
)
PAID_HEADER = (
    "// © 2020–2026 Legacy Holder\n"
    "// All Rights Reserved. Proprietary and Confidential.\n"
    "//\n"
    "// Version: 2.1.0\n"
    "//@version=6\n"
)
MINIMAL_BODY = 'indicator("Test Indicator")\nplot(close, title="C")\n'


def make_workspace(tmpdir_holder):
    """Create a minimal workspace root whose path contains a space."""
    base = Path(tempfile.mkdtemp(prefix="pws test ", dir=tmpdir_holder))
    (base / "scripts").mkdir()
    return base


VERDICTS = ("passed", "failed", "not-run", "indeterminate", "n-a")


def v2_result(verdict, observation="observation consignee par la suite de tests",
              observed_by="operator", at="2026-09-05T09:58:00Z", group=None):
    """One structured version-2 result entry."""
    entry = {"verdict": verdict, "observation": observation,
             "observed_by": observed_by, "at": at}
    if group is not None:
        entry["group"] = group
    return entry


def full_run_report(run_id, source_sha256, status="passed",
                    completed_at="2026-09-05T10:00:00Z",
                    started_at="2026-09-05T09:55:00Z",
                    source="My Indicator.pine", **overrides):
    """Complete VERSION-2 run report satisfying the shared spec-51.4 contract
    (validation.validate_run_report), coherent with `status`. Tests override
    single fields to build the exact incoherences they target. Convenience:
    a matrix entry without `id` takes its `test` as id, and a result given as
    a bare verdict string becomes a structured entry."""
    matrix = [{"id": "compilation", "test": "compilation", "applicable": True}]
    if status == "partial":
        matrix.append({"id": "runtime", "test": "runtime", "applicable": True})
        results = {"compilation": v2_result("passed"),
                   "runtime": v2_result("not-run")}
    elif status == "in-progress":
        results = {}
    else:
        results = {"compilation": v2_result(status)}
    report = {
        "schema_version": 2,
        "run_id": run_id,
        "status": status,
        "source": source,
        "source_sha256": source_sha256,
        "started_at": started_at,
        "completed_at": completed_at,
        "git_commit": None,
        "working_tree": None,
        "requested_mode": "manual",
        "effective_mode": "manual",
        "fallback_reason": None,
        "matrix": matrix,
        "results": results,
        "anomalies": [],
        "evidence": [],
        "conclusion": "rapport genere par la suite de tests",
    }
    report.update(overrides)
    if isinstance(report["matrix"], list):
        for entry in report["matrix"]:
            if isinstance(entry, dict) and "id" not in entry \
                    and isinstance(entry.get("test"), str):
                entry["id"] = entry["test"]
    if isinstance(report["results"], dict):
        for key, value in list(report["results"].items()):
            if isinstance(value, str) and value in VERDICTS:
                report["results"][key] = v2_result(value)
    return report


def full_run_report_v1(run_id, source_sha256, status="passed",
                       completed_at="2026-09-05T10:00:00Z",
                       started_at="2026-09-05T09:55:00Z",
                       source="My Indicator.pine", **overrides):
    """HISTORICAL version-1 report (free-text results): read compatibility
    only — it can be inspected on disk, never promoted."""
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "source": source,
        "source_sha256": source_sha256,
        "started_at": started_at,
        "completed_at": completed_at,
        "git_commit": None,
        "working_tree": None,
        "requested_mode": "manual",
        "effective_mode": "manual",
        "fallback_reason": None,
        "matrix": [{"test": "compilation", "applicable": True}],
        "results": {"compilation": status},
        "anomalies": [],
        "evidence": [],
        "conclusion": "rapport genere par la suite de tests",
    }
    report.update(overrides)
    return report


PROPRIETARY_HEADER = (
    "// © 2020–2026 Holder Test\n"
    "// All Rights Reserved.\n"
    "//\n"
    "// Version: 2.1.0\n"
    "//@version=6\n"
)
FREE_HEADER_HOLDER = (
    "// This work is licensed under the Attribution-NonCommercial-ShareAlike 4.0 "
    "International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/\n"
    "// © 2026 Holder Test\n"
    "// Version: 1.0.0\n"
    "//@version=6\n"
)


def v3_manifest(slug, source_name, kind="indicator", profile="FREE", license_overrides=None,
                closed_source=False, publication_overrides=None, **extra):
    """Schema-3 manifest with the profile defaults (overridable axis by axis)."""
    from tools.pws_workspace import profiles
    lic = profiles.default_license(profile, closed_source=closed_source)
    lic.update({"copyright_holder": None, "created_year": None, "terms_ref": None, "terms_url": None})
    if license_overrides:
        lic.update(license_overrides)
    pub = profiles.default_publication(profile, closed_source=closed_source)
    if publication_overrides:
        pub.update(publication_overrides)
    manifest = {"schema_version": 3, "id": slug, "source": source_name,
                "script_kind": kind, "profile": profile, "license": lic, "publication": pub}
    manifest.update(extra)
    return manifest


def v2_manifest_legacy(slug, source_name, kind="indicator", profile="COMMERCIAL",
                       publication="tradingview-invite-only"):
    """HISTORICAL schema-2 manifest (publication as a string inside license)."""
    from tools.pws_workspace import profiles
    lic = profiles.default_license(profile)
    lic.update({"publication": publication, "copyright_holder": None, "created_year": None,
                "terms_ref": None})
    return {"schema_version": 2, "id": slug, "source": source_name, "script_kind": kind,
            "profile": profile, "license": lic}


def make_product_v3(root, slug="my-indicator", source_name="My Indicator.pine",
                    kind="indicator", profile="FREE", header=None, body=MINIMAL_BODY,
                    license_overrides=None, closed_source=False, publication_overrides=None,
                    with_context=True, with_validation=True, manifest=None):
    """Product with a schema-3 manifest (2026-11-06 profiles, publication axes)."""
    if header is None:
        header = FREE_HEADER_HOLDER if (profile == "FREE" and not closed_source) else PROPRIETARY_HEADER
    pdir = root / "scripts" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / source_name).write_text(header + body, encoding="utf-8")
    if manifest is None:
        manifest = v3_manifest(slug, source_name, kind, profile, license_overrides, closed_source,
                               publication_overrides)
    (pdir / "SCRIPT.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if with_context:
        (pdir / "PRODUCT.md").write_text(
            "# Produit\nIndicateur de test: moyenne mobile sur close.\n", encoding="utf-8")
        (pdir / "ARCHITECTURE.md").write_text(
            "# Architecture\nUn plot unique derive de close.\n", encoding="utf-8")
        (pdir / "CLAUDE.md").write_text(
            "# Contexte\nProduit de test minimal.\n", encoding="utf-8")
    if with_validation:
        vdir = pdir / "validation"
        vdir.mkdir(exist_ok=True)
        (vdir / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "unverified", "last_run": None,
        }, indent=2), encoding="utf-8")
    return pdir


# compatibility aliases for the tests written for the 2026-11-06 lot
v2_manifest = v3_manifest
make_product_v2 = make_product_v3


def configure(root, language="fr", holder="Holder Test", aliases=("HolderAlias",)):
    """Write a personal configuration with a configured identity."""
    from tools.pws_workspace import config
    r = config.init_config(root, language, holder, list(aliases))
    assert r["ok"], r
    return r


def make_product(root, slug="my-indicator", source_name="My Indicator.pine",
                 kind="indicator", distribution="free-open-source",
                 header=FREE_HEADER, body=MINIMAL_BODY, manifest_extra=None,
                 with_context=True, with_validation=True):
    pdir = root / "scripts" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / source_name).write_text(header + body, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "id": slug,
        "source": source_name,
        "script_kind": kind,
        "distribution": distribution,
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (pdir / "SCRIPT.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if with_context:
        (pdir / "PRODUCT.md").write_text(
            "# Produit\nIndicateur de test: moyenne mobile sur close.\n", encoding="utf-8")
        (pdir / "ARCHITECTURE.md").write_text(
            "# Architecture\nUn plot unique derive de close.\n", encoding="utf-8")
        (pdir / "CLAUDE.md").write_text(
            "# Contexte\nProduit de test minimal.\n", encoding="utf-8")
    if with_validation:
        vdir = pdir / "validation"
        vdir.mkdir(exist_ok=True)
        (vdir / "current.json").write_text(json.dumps({
            "schema_version": 1, "status": "unverified", "last_run": None,
        }, indent=2), encoding="utf-8")
    return pdir
