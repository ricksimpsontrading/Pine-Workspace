# SPDX-License-Identifier: Apache-2.0
"""Release engineering of the core (maintainer side): build the publication
artefacts of ONE version from the existing distribution mechanism — and
nothing else. Publishing (tag, GitHub release, upload) is a separate,
explicit act of the holder, described in OPERATIONS.md.

`build-release --target <folder>` produces, for version.WORKSPACE_VERSION:
  <target>/pine-workspace-<version>/            the distribution (distribution.build)
  <target>/pine-workspace-<version>.zip         the archive, one top folder
  <target>/pine-workspace-<version>.zip.sha256  shasum-compatible line
  <target>/RELEASE.json                         metadata read by the update path
  <target>/RELEASE_NOTES.md                     the CHANGELOG entry of the version
and verifies them after writing: safe archive entries (the update path's own
inspection), inner core manifest present in the archive, metadata consistent
with the version. The archive's SHA-256 is an INTEGRITY check, not a proof
of authenticity: no signing chain exists and none is claimed. Archive
entries carry normalized permissions — 0644, or 0755 for a file executable
by its owner — never the local mode of the built tree (review m9).

Target: neither the source workspace, nor inside it, nor containing it —
compared by physical identity, whatever the case of the path on a
case-insensitive volume (review RS-05, same rule as build-distribution).

Consistency, one source: the number comes from version.py; the top entry of
CHANGELOG.md must carry the same number (refused otherwise); tag, archive
name, VERSION file, marker and RELEASE.json are derived. A published version
is never rebuilt under the same number: a corrected delivery takes a new one
(the holder checks that the tag does not exist before publishing).
"""
import datetime
import os
import stat
import zipfile
from pathlib import Path

from . import core, distribution, i18n, migration, update, version

SCHEMA = 1



def _update_path(lang):
    """Menu path of the guided update, in the given language (audit I-10:
    English texts name the English labels, the French ones as a second form)."""
    return "/pws → %s → %s → %s" % (i18n.t("menu.maintenance", lang), i18n.t("menu.maintenance.tools", lang),
                                     i18n.t("menu.tools.update", lang))

def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def changelog_top_version(root):
    """Version of the first `## [x.y.z]` entry of CHANGELOG.md, or None."""
    path = Path(root) / "CHANGELOG.md"
    if path.is_symlink() or not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        if line.startswith("## "):
            head = line[3:].strip()
            if head.startswith("["):
                head = head[1:].split("]")[0]
            else:
                head = head.split()[0] if head.split() else ""
            return version.normalized(head)
    return None


def check_consistency(root):
    """Version sources agree: version.py (the source), CHANGELOG top entry."""
    problems = []
    ver = version.WORKSPACE_VERSION
    if version.parse_version(ver) is None or version.is_prerelease(ver):
        problems.append("WORKSPACE_VERSION %r is not a stable MAJOR.MINOR.PATCH number" % ver)
    top = changelog_top_version(root)
    if top is None:
        problems.append("CHANGELOG.md missing or without a `## [x.y.z]` entry")
    elif top != version.normalized(ver):
        problems.append("CHANGELOG.md top entry is %s, version.py says %s" % (top, ver))
    return {"ok": not problems, "version": ver, "changelog_version": top, "tag": version.release_tag(ver),
            "package": version.package_name(ver), "problems": problems}


def write_artefacts(dist_dir, target, ver, changelog_text="", git=None, force=False):
    """Archive + SHA-256 + RELEASE.json + RELEASE_NOTES.md for a built
    distribution `dist_dir` of version `ver`, verified after writing. Shared
    by `build_release` and by the tests (fixture releases of other numbers)."""
    dist_dir, target = Path(dist_dir), Path(target)
    report = {"ok": False, "problems": [], "target": str(target)}
    name = version.package_name(ver)
    zip_path = target / (name + ".zip")
    target.mkdir(parents=True, exist_ok=True)
    if zip_path.exists() and not force:
        report["problems"].append("%s already exists — a published version is never rebuilt silently; pass "
                                  "--force only for an UNPUBLISHED build" % zip_path.name)
        return report
    marker, merr = core.read_json(dist_dir / distribution.MARKER)
    if merr or not isinstance(marker, dict) or not isinstance(marker.get("files"), dict):
        report["problems"].append("distribution has no readable %s: %s" % (distribution.MARKER, merr))
        return report
    if version.normalized(marker.get("workspace_version")) != version.normalized(ver):
        report["problems"].append("distribution marker says %r, artefacts requested for %s"
                                  % (marker.get("workspace_version"), ver))
        return report
    files = sorted(p for p in core.iter_paths_within(dist_dir) if p.is_file())
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info = zipfile.ZipInfo.from_file(str(p), (Path(name) / p.relative_to(dist_dir)).as_posix())
            # normalized permissions (review m9): a file kept 0600 locally is never archived as 0600
            info.external_attr = (stat.S_IFREG | distribution.shipped_mode(os.stat(str(p)).st_mode)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(str(p), "rb") as src:
                z.writestr(info, src.read())
    sha = core.sha256_file(zip_path)
    (target / (name + ".zip.sha256")).write_text("%s  %s\n" % (sha, zip_path.name), encoding="utf-8")
    git = git or {}
    meta = {
        "schema": SCHEMA, "name": version.PACKAGE_BASENAME, "version": ver, "tag": version.release_tag(ver),
        "zip": zip_path.name, "zip_sha256": sha, "zip_bytes": zip_path.stat().st_size, "zip_top_folder": name,
        "core_files": len(marker["files"]), "manifest_sha256": core.sha256_file(dist_dir / distribution.MARKER),
        "workspace_version": ver, "config_schema": version.CONFIG_SCHEMA_VERSION,
        "manifest_schema": version.MANIFEST_SCHEMA_VERSION,
        "migrations": list(marker.get("migrations") or migration.STEP_IDS),
        "official_repository": version.OFFICIAL_REPOSITORY,
        "source_commit": git.get("commit"), "source_dirty": git.get("dirty"), "built_at": _now(),
        "requirements": {"python": "3.9 or later, standard library only",
                         "git": "optional (degraded mode without it)",
                         "node_npm": "optional, local PineTS tests only (engine not shipped)",
                         "platforms": marker.get("platform_support")},
        "install": "python3 install.py  (from the extracted package folder; never over an existing installation)",
        "update": "%s (menus in French: %s), or: update prepare --package <zip> ; update plan --package-dir … ; "
                  "update apply --plan-file … --yes" % (_update_path("en"), _update_path("fr")),
        "integrity": "SHA-256 of the archive (zip_sha256; also the .sha256 asset) — integrity only, no cryptographic signature",
        "notes": update.RELEASE_NOTES,
    }
    core.atomic_write_json(target / update.RELEASE_JSON, meta)
    section = update.changelog_section(changelog_text, ver) or ""
    notes = ("# Pine Workspace %s\n\n%s\n\n## Assets\n\n| Asset | Role |\n|---|---|\n"
             "| `%s` | the distribution (one top folder `%s/`) |\n| `%s.sha256` | SHA-256 of the archive |\n"
             "| `RELEASE.json` | metadata read by the guided update path |\n| `RELEASE_NOTES.md` | these notes |\n\n"
             "SHA-256 of `%s`: `%s` — an integrity check, not a proof of authenticity (no signature).\n\n"
             "## Install or update\n\n- New installation: extract the archive, then `python3 install.py` from the "
             "extracted folder (see `INSTALL.md`).\n- Existing installation: `%s` (menus in French: `%s`), or the "
             "`update` commands (plan before apply, never over an existing installation).\n"
             % (version.release_tag(ver), section, zip_path.name, name, zip_path.name, zip_path.name, sha,
                _update_path("en"), _update_path("fr")))
    (target / update.RELEASE_NOTES).write_text(notes, encoding="utf-8")
    # verification after writing: archive inspection, inner manifest, metadata
    ok, problems, top, _infos = update.inspect_archive(zip_path)
    if not ok or top != name:
        report["problems"].append("archive verification failed: %s" % "; ".join(problems or ["top folder %r" % top]))
    with zipfile.ZipFile(str(zip_path)) as z:
        names = set(z.namelist())
    missing = [rel for rel in marker["files"] if "%s/%s" % (name, rel) not in names]
    if missing or "%s/%s" % (name, distribution.MARKER) not in names:
        report["problems"].append("archive misses core files: %s" % ", ".join(missing[:5]))
    report.update({"version": ver, "tag": meta["tag"], "zip": str(zip_path), "zip_sha256": sha,
                   "zip_bytes": meta["zip_bytes"], "core_files": meta["core_files"],
                   "release_json": str(target / update.RELEASE_JSON), "notes": str(target / update.RELEASE_NOTES),
                   "source_commit": meta["source_commit"], "source_dirty": meta["source_dirty"]})
    report["ok"] = not report["problems"]
    return report


def build_release(root, target, force=False, allow_dirty=False):
    """Build and verify the artefacts of the CURRENT version into `target`.
    Publication artefacts come from a COMMITTED, CLEAN tree (audit I-03): the
    archive then holds exactly the content of `source_commit`. `allow_dirty`
    exists for tests of the artefact structure only (never exposed by the CLI)."""
    root, target = Path(root), Path(target)
    report = {"ok": False, "target": str(target), "problems": [], "consistency": check_consistency(root)}
    if not report["consistency"]["ok"]:
        report["problems"] = list(report["consistency"]["problems"])
        return report
    relation = distribution.target_relation_problem(root, target)     # physical identity (review RS-05)
    if relation:
        report["problems"].append(relation)
        return report
    git = core.git_state(root)
    if not allow_dirty and (not git.get("commit") or git.get("dirty")):
        report["problems"].append("publication artefacts are built only from a committed, clean tree (commit %s, "
                                  "dirty %s) — commit or set aside the changes first"
                                  % (git.get("commit"), git.get("dirty")))
        return report
    ver = version.WORKSPACE_VERSION
    name = version.package_name(ver)
    if (target / (name + ".zip")).exists() and not force:
        report["problems"].append("%s.zip already exists — a published version is never rebuilt silently; pass "
                                  "--force only for an UNPUBLISHED build" % name)
        return report
    built = distribution.build(root, target / name, force=force)
    report["distribution"] = built
    if not built["ok"] or not built["clean"]:
        report["problems"].append("distribution not clean: %s" % (built.get("error") or built.get("personal_pattern_hits")))
        return report
    art = write_artefacts(target / name, target, ver,
                          changelog_text=(root / "CHANGELOG.md").read_text(encoding="utf-8"),
                          git=git, force=force)
    report.update({k: v for k, v in art.items() if k != "target"})
    report["ok"] = art["ok"]
    return report
