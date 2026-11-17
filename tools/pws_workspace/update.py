# SPDX-License-Identifier: Apache-2.0
"""Guided update of an INSTALLED Pine Workspace from the official releases or
from a local package — orchestration ONLY. `upgrade` (code) and `migrate`
(data) remain the sole mutation authorities: nothing here copies, restores or
backs up a file by itself.

Ratified by the holder on 2026-11-08. Steps, each explicit, none at session
start, nothing automatic:

  status        installed version and kind of installation, last search
                (dated, or "not searched"), backups available — read-only.
  check         explicit network query of the releases of
                version.OFFICIAL_REPOSITORY (GitHub REST, unauthenticated,
                standard library). Stable releases only — drafts and
                pre-releases are skipped unless asked; versions are compared
                numerically (MAJOR.MINOR.PATCH), never as strings; the dated
                result is recorded for later display. An error or an absence
                of release is reported as such and NEVER as "up to date".
  fetch         download of the release found by the last search into a
                temporary folder OUTSIDE the installation: asset URLs must
                belong to the official repository and tag (provenance of the
                download), RELEASE.json is read first (version == tag), the
                archive's SHA-256 is compared with the published value, the
                extraction is checked before any write (no absolute path, no
                `..`, no symlink, one top folder, confined), then the inner
                core manifest is verified file by file.
  prepare       the same verification for a LOCAL archive or folder, offline:
                integrity only — the origin is then "local package" and is
                never claimed verified online.
  plan          read-only summary before any change: current and target
                version, origin of the package, main changes (release notes
                or the package CHANGELOG), the `upgrade` plan (conflicts,
                files kept locally, retired files), the data migrations that
                MAY apply (declared by the package, not yet recorded here),
                backups and rollback order, restart of Claude Code required.
                The plan is written to a file with a hash: the holder's
                approval binds that exact plan.
  apply         refuses when the plan changed since approval, when the
                installation is the development upstream, or when conflicts
                exist (never --overwrite-local on its own). Then
                `upgrade.apply`, then `migrate --plan` run by the NEW code in a
                separate process: a BLOCKED step stops the data phase before
                any migration is applied; the migrations are applied only if
                they all belong to the approved list — otherwise the run STOPS
                after the code upgrade and reports the step(s). Then the
                installed files and version are verified against the new
                manifest and `doctor --json` is run and interpreted by its real
                contract (a non-empty list of checks, each with a usable
                `check` identifier, a severity among OK/INFO/WARNING/BLOCKING
                and a string `detail`, validated BEFORE any verdict; exit code
                1 iff a BLOCKING check; warnings alone never block; a failed
                run, an unusable or non-conforming output, an empty list or an
                exit code inconsistent with the result is never a successful
                diagnostic).
                The status is explicit and is a success ONLY when every stage
                succeeded: refused-before-mutation, failed-restored,
                failed-restore-<stage>, incomplete, stopped-blocked-migrations,
                stopped-unplanned-migrations, diagnostic-blocking,
                diagnostic-unavailable, applied. Every report states what was
                actually done (`done`: code installed and verified, migrations
                applied / remaining / blocked, diagnostic), the backups
                (`recovery`) and the useful next step (`next_action`); once the
                code is installed the report never pretends nothing changed.
                "Code upgrade then data migrations" is NOT atomic as a whole
                and is never presented as such; no automatic rollback of the
                whole path exists.
  rollback-info the documented order (data first, then code), the backups
                that exist with their state, the exact existing commands and
                their limits — this command restores nothing.

The development upstream — the workspace distributions are built FROM — is
recognised by the absence of the core manifest `PWS_DISTRIBUTION.json`,
never by a path: it may consult releases, but no plan and no apply are
accepted there. The SHA-256 published with a release is an integrity check;
it does not prove authenticity (no signing chain exists).
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from . import config, core, migration, upgrade, version

UPDATE_REL = core.RUNTIME_REL / "pws-update"
CHECK_REL = UPDATE_REL / "last-check.json"
PLANS_REL = UPDATE_REL / "plans"
API_RELEASES = "https://api.github.com/repos/%s/releases?per_page=30"
DOWNLOAD_PREFIX = "https://github.com/%s/releases/download/%s/"
USER_AGENT = "pine-workspace-update/%s" % version.WORKSPACE_VERSION
TIMEOUT = 20
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024     # extracted size cap (a package weighs a few megabytes)
RELEASE_JSON = "RELEASE.json"
RELEASE_NOTES = "RELEASE_NOTES.md"
PREPARED = "PREPARED.json"                # written next to a verified package by fetch/prepare
MARKER = upgrade.MARKER
RESTART_NOTE = ("after a successful update, quit and relaunch Claude Code so that the new "
                "instructions (CLAUDE.md, skills, rules) are loaded")
NOT_ATOMIC_NOTE = ("the code upgrade and the data migrations are two operations: they are not "
                   "atomic as a whole (the run stops between them on an unplanned migration)")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- installation facts (read-only) -----------------------------------------

def installation_kind(root):
    """`distribution` (core manifest present and valid) or `development`
    (the upstream: no core manifest) — decided by the marker, never by a path."""
    manifest, err = upgrade.installed_manifest(root)
    if manifest is None:
        return {"kind": "development", "manifest_version": None, "built_at": None, "source_commit": None,
                "reason": ("no valid core manifest (%s): this workspace is the development upstream from "
                           "which distributions are built — it is updated through its own repository and "
                           "a public distribution is never applied onto it" % (err or MARKER))}
    raw = manifest["raw"]
    return {"kind": "distribution", "manifest_version": manifest["version"], "built_at": raw.get("built_at"),
            "source_commit": raw.get("source_commit"), "core_files": len(manifest["files"]), "reason": None}


def read_check(root):
    """The last explicit search, dated — or the honest absence of a search."""
    path = Path(root) / CHECK_REL
    if core.runtime_tree_is_real(root, CHECK_REL.parts) and path.is_file():
        data, err = core.read_json(path)
        if not err and isinstance(data, dict) and data.get("checked_at"):
            latest = data.get("latest") if isinstance(data.get("latest"), dict) else None
            if latest and data.get("result") in ("update-available", "up-to-date", "ahead") \
                    and data.get("installed") != version.WORKSPACE_VERSION:
                # audit H-07: the result is re-read against the version installed NOW
                cmp = version.compare(latest.get("version"), version.WORKSPACE_VERSION)
                if cmp is not None:
                    data = dict(data, result={1: "update-available", 0: "up-to-date", -1: "ahead"}[cmp],
                                searched_with=data.get("installed"), installed=version.WORKSPACE_VERSION,
                                note="result re-read against the installed version %s (search dated %s)"
                                     % (version.WORKSPACE_VERSION, data.get("checked_at")))
            return data
    return {"checked_at": None, "result": "not-searched", "latest": None, "source": None,
            "repository": version.OFFICIAL_REPOSITORY, "installed": version.WORKSPACE_VERSION,
            "note": "no search performed yet: whether a newer version exists is unknown"}


def status(root):
    root = Path(root)
    cfg = config.read_config(root)
    return {
        "installed_version": version.WORKSPACE_VERSION,
        "config_version": cfg["data"].get("workspace_version"),
        "installation": installation_kind(root),
        "official_repository": version.OFFICIAL_REPOSITORY,
        "last_check": read_check(root),
        "pending_migrations": [s["id"] for s in migration.pending_steps(root)],
        "backups": {"upgrade": upgrade.list_backups(root), "migration": migration.list_backups(root)},
        "interrupted_upgrades": upgrade.interrupted_backups(root),
        "notes": {"restart": RESTART_NOTE, "atomicity": NOT_ATOMIC_NOTE},
    }


# ---- explicit search of the official releases --------------------------------

def _http_get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, "HTTP %s" % exc.code
    except Exception as exc:  # noqa: BLE001 — truncated body, protocol error…: an error result, never a trace (H-09)
        return None, None, "%s: %s" % (type(exc).__name__, exc)


def _release_summary(rel):
    assets = []
    raw_assets = rel.get("assets") if isinstance(rel.get("assets"), list) else []
    for a in raw_assets:
        if isinstance(a, dict) and isinstance(a.get("name"), str):
            assets.append({"name": a["name"], "url": a.get("browser_download_url"), "size": a.get("size")})
    body = rel.get("body") if isinstance(rel.get("body"), str) else ""
    return {"tag": rel.get("tag_name"), "version": version.normalized(rel.get("tag_name")),
            "name": rel.get("name"), "published_at": rel.get("published_at"), "html_url": rel.get("html_url"),
            "prerelease": bool(rel.get("prerelease")) or version.is_prerelease(rel.get("tag_name")),
            "assets": assets, "notes": body[:20000]}


def check(root, fetch=None, include_prereleases=False):
    """Explicit query of the releases. `fetch(url) -> (status, json, error)`
    is injectable: a test's deterministic answer is recorded as `simulated`,
    the real query as `github`. Never installs anything."""
    root = Path(root)
    simulated = fetch is not None
    fetch = fetch or _http_get_json
    url = API_RELEASES % version.OFFICIAL_REPOSITORY
    status_code, data, err = fetch(url)
    rec = {"checked_at": _now(), "source": "simulated" if simulated else "github",
           "repository": version.OFFICIAL_REPOSITORY, "url": url,
           "installed": version.WORKSPACE_VERSION, "include_prereleases": bool(include_prereleases),
           "result": None, "latest": None, "error": None,
           "prereleases_skipped": 0, "drafts_skipped": 0, "unparsable_tags": []}
    if err or not isinstance(data, list):
        rec["result"] = "error"
        rec["error"] = err or "unexpected response (not a list of releases)"
        if status_code == 404:
            rec["error"] += " — repository or releases not found (nothing published yet?)"
        rec["note"] = "the search failed: whether a newer version exists is still unknown"
    else:
        candidates = []
        for rel in data:
            if not isinstance(rel, dict):
                continue
            if rel.get("draft"):
                rec["drafts_skipped"] += 1
                continue
            parsed = version.parse_version(rel.get("tag_name"))
            if parsed is None:
                rec["unparsable_tags"].append(str(rel.get("tag_name"))[:40])
                continue
            if (parsed[3] or rel.get("prerelease")) and not include_prereleases:
                rec["prereleases_skipped"] += 1
                continue
            candidates.append((parsed[:3] + ((0, version.prerelease_key(parsed[3])) if parsed[3] else (1, ())), rel))
        if not candidates:
            rec["result"] = "no-release"
            rec["note"] = "no stable release found: whether a newer version exists is unknown (not 'up to date')"
        else:
            candidates.sort(key=lambda item: item[0])
            latest = _release_summary(candidates[-1][1])
            rec["latest"] = latest
            cmp = version.compare(latest["version"], version.WORKSPACE_VERSION)
            rec["result"] = {1: "update-available", 0: "up-to-date", -1: "ahead"}[cmp]
            if cmp < 0:
                rec["note"] = "the installed version is newer than the latest published release"
    if core.runtime_tree_is_real(root, CHECK_REL.parts):
        (root / UPDATE_REL).mkdir(parents=True, exist_ok=True)
        core.atomic_write_json(root / CHECK_REL, rec)
        rec["recorded"] = str(CHECK_REL)
    else:
        rec["recorded"] = None
    return rec


# ---- archives: inspection before any write, confined extraction ---------------

def inspect_archive(zip_path):
    """(ok, problems, top_folder, infos): every entry must be a regular file
    or folder under ONE top folder, with no absolute path, drive, backslash
    or `..`, no symlink or special file, and a total size under the cap."""
    problems, tops, infos, total = [], set(), [], 0
    try:
        with zipfile.ZipFile(str(zip_path)) as z:
            for info in z.infolist():
                name = info.filename
                if not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name.split("/")[0]:
                    problems.append("unsafe entry name: %r" % name[:80])
                    continue
                parts = PurePosixPath(name).parts
                if ".." in parts or any(p in ("", ".") for p in parts):
                    problems.append("entry escapes its folder: %r" % name[:80])
                    continue
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    problems.append("symbolic link refused: %r" % name[:80])
                    continue
                if mode and mode not in (0o100000, 0o040000):
                    problems.append("special file refused: %r" % name[:80])
                    continue
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    problems.append("archive exceeds the extraction cap (%d bytes)" % MAX_ARCHIVE_BYTES)
                    break
                tops.add(parts[0])
                infos.append(info)
    except (zipfile.BadZipFile, OSError) as exc:
        return False, ["not a readable archive: %s" % exc], None, []
    if len(tops) != 1:
        problems.append("archive must contain exactly one top folder (found %d)" % len(tops))
    if not infos and not problems:
        problems.append("archive is empty")
    return not problems, problems, (next(iter(tops)) if len(tops) == 1 else None), infos


def verify_package_dir(package_dir):
    """Core manifest present and every listed file matching its hash. Returns
    (manifest, problems)."""
    manifest, err = upgrade.installed_manifest(package_dir)
    if manifest is None:
        return None, ["package has no valid %s: %s" % (MARKER, err)]
    problems = []
    for rel, sha in sorted(manifest["files"].items()):
        p = Path(package_dir) / rel
        if p.is_symlink() or not p.is_file():
            problems.append("%s: missing or not a regular file" % rel)
        elif core.sha256_file(p) != sha:
            problems.append("%s: hash mismatch" % rel)
    return manifest, problems


def unpack_package(zip_path, dest):
    """Extract a verified archive into `dest` (created, must not exist):
    nothing is written when the inspection fails; every target path is
    confined; no symlink is ever created. Returns (package_dir, problems)."""
    dest = Path(dest)
    ok, problems, top, infos = inspect_archive(zip_path)
    if not ok:
        return None, problems
    if dest.exists():
        return None, ["extraction folder already exists: %s" % dest]
    dest.mkdir(parents=True)
    try:
        with zipfile.ZipFile(str(zip_path)) as z:
            for info in infos:
                target = dest / info.filename
                if not core.is_within(dest, target):
                    raise OSError("entry escapes the extraction folder: %s" % info.filename)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(str(target), "wb") as out:
                    shutil.copyfileobj(src, out)
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(str(target), mode & 0o755)
    except (OSError, zipfile.BadZipFile) as exc:
        shutil.rmtree(str(dest), ignore_errors=True)
        return None, ["extraction failed, folder removed: %s" % exc]
    package = dest / top
    manifest, mproblems = verify_package_dir(package)
    if mproblems:
        return None, mproblems
    return package, []


# ---- fetch from the official release / prepare a local package ----------------

def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(str(dest), "wb") as out:
        total = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise OSError("download exceeds the size cap")
            out.write(chunk)


def _write_prepared(folder, info):
    core.atomic_write_json(Path(folder) / PREPARED, info)


def fetch_release(root, tag=None, downloader=None, check_record=None, dest=None):
    """Download the release found by the last search into a temporary folder
    outside the installation and verify it. `downloader(url, dest_path)` is
    injectable (tests: deterministic local copies, reported as such)."""
    root = Path(root)
    rec = check_record or read_check(root)
    out = {"ok": False, "origin": "github-release", "simulated": downloader is not None,
           "download_dir": None, "package_dir": None, "release": None, "problems": []}
    latest = rec.get("latest") if isinstance(rec, dict) else None
    if rec.get("result") not in ("update-available", "up-to-date", "ahead") or not latest:
        out["problems"].append("no dated search with a release to fetch — run `update check` first")
        return out
    if tag and tag != latest.get("tag"):
        out["problems"].append("only the release of the last search can be fetched here (%s)" % latest.get("tag"))
        return out
    tag = latest["tag"]
    ver = version.normalized(tag)
    zip_name = version.package_name(ver) + ".zip"
    prefix = DOWNLOAD_PREFIX % (version.OFFICIAL_REPOSITORY, tag)
    assets = {a["name"]: a for a in latest.get("assets") or [] if isinstance(a, dict)}
    for required in (RELEASE_JSON, zip_name):
        if required not in assets:
            out["problems"].append("the release has no asset %s" % required)
    for name, a in assets.items():
        if name in (RELEASE_JSON, zip_name, zip_name + ".sha256", RELEASE_NOTES) \
                and not (isinstance(a.get("url"), str) and a["url"].startswith(prefix)):
            out["problems"].append("asset %s is not served from the official repository and tag" % name)
    if out["problems"]:
        return out
    ddir = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="pine-workspace-update-"))
    if core.is_within(root, ddir):
        out["problems"].append("the download folder must be outside the installation")
        return out
    ddir.mkdir(parents=True, exist_ok=True)
    out["download_dir"] = str(ddir)
    dl = downloader or _download
    try:
        dl(assets[RELEASE_JSON]["url"], ddir / RELEASE_JSON)
        meta, err = core.read_json(ddir / RELEASE_JSON)
        if err or not isinstance(meta, dict):
            out["problems"].append("RELEASE.json unreadable: %s" % err)
            return out
        out["release"] = meta
        if version.normalized(meta.get("version")) != ver or meta.get("tag") != tag or meta.get("zip") != zip_name:
            out["problems"].append("RELEASE.json (version %r, tag %r, zip %r) does not match the release %s"
                                   % (meta.get("version"), meta.get("tag"), meta.get("zip"), tag))
            return out
        dl(assets[zip_name]["url"], ddir / zip_name)
        sha = core.sha256_file(ddir / zip_name)
        if sha != meta.get("zip_sha256"):
            out["problems"].append("archive SHA-256 %s differs from the published value %s — refused"
                                   % (sha[:16], str(meta.get("zip_sha256"))[:16]))
            return out
        if isinstance(meta.get("zip_bytes"), int) and (ddir / zip_name).stat().st_size != meta["zip_bytes"]:
            out["problems"].append("archive size differs from the published value — refused")
            return out
        if zip_name + ".sha256" in assets:
            dl(assets[zip_name + ".sha256"]["url"], ddir / (zip_name + ".sha256"))
            published = (ddir / (zip_name + ".sha256")).read_text(encoding="utf-8", errors="replace").split()
            if not published or published[0].lower() != sha:
                out["problems"].append("the .sha256 asset does not match the archive — refused")
                return out
        notes_path = None
        if RELEASE_NOTES in assets:
            dl(assets[RELEASE_NOTES]["url"], ddir / RELEASE_NOTES)
            notes_path = str(ddir / RELEASE_NOTES)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        out["problems"].append("download failed: %s" % exc)
        return out
    package, problems = unpack_package(ddir / zip_name, ddir / "package")
    if problems:
        out["problems"] = problems
        return out
    manifest, _ = upgrade.installed_manifest(package)
    if version.normalized(manifest["version"]) != ver:
        out["problems"].append("the package manifest says version %r, the release is %s" % (manifest["version"], tag))
        return out
    out.update({"ok": True, "package_dir": str(package), "zip": str(ddir / zip_name), "zip_sha256": sha,
                "provenance": ("assets of %s, tag %s (URLs checked); SHA-256 equal to the published value: "
                               "integrity verified, authenticity not proven (no signature)"
                               % (version.OFFICIAL_REPOSITORY, tag)),
                "notes_path": notes_path, "notes": latest.get("notes") or ""})
    _write_prepared(ddir, {"origin": "github-release", "simulated": out["simulated"], "tag": tag,
                           "provenance": out["provenance"], "release": meta, "notes_path": notes_path,
                           "notes": out["notes"], "package_dir": out["package_dir"], "prepared_at": _now()})
    return out


def prepare_local(root, source, expected_sha256=None, dest=None):
    """Verify a LOCAL archive (.zip) or an already extracted package folder,
    offline: integrity only. The origin stays `local-package`."""
    root = Path(root)
    src = Path(source).expanduser()
    out = {"ok": False, "origin": "local-package", "source": str(src), "package_dir": None,
           "download_dir": None, "problems": [], "sha256": None}
    if src.is_symlink() or not src.exists():
        out["problems"].append("local package missing or symlinked: %s" % src)
        return out
    if src.is_file():
        sha = core.sha256_file(src)
        out["sha256"] = sha
        if expected_sha256 and sha != expected_sha256.strip().lower():
            out["problems"].append("archive SHA-256 %s differs from the expected %s — refused"
                                   % (sha[:16], expected_sha256.strip()[:16]))
            return out
        ddir = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="pine-workspace-update-"))
        if core.is_within(root, ddir):
            out["problems"].append("the extraction folder must be outside the installation")
            return out
        ddir.mkdir(parents=True, exist_ok=True)
        out["download_dir"] = str(ddir)
        package, problems = unpack_package(src, ddir / "package")
        if problems:
            out["problems"] = problems
            return out
        holder = ddir
    elif src.is_dir():
        if expected_sha256:
            out["problems"].append("an expected SHA-256 applies to an archive (.zip), not to a folder: give the "
                                   "archive, or omit --sha256 (a folder is checked against its own manifest)")
            return out
        manifest, problems = verify_package_dir(src)
        if problems:
            out["problems"] = problems
            return out
        package, holder = src, None
    else:
        out["problems"].append("local package is neither an archive nor a folder")
        return out
    out.update({"ok": True, "package_dir": str(package),
                "provenance": ("local package: integrity verified offline (%smanifest and every file hash)"
                               " — origin not verified online"
                               % ("archive hash%s, " % (" as expected" if expected_sha256 else "") if src.is_file() else ""))})
    if holder is not None:
        _write_prepared(holder, {"origin": "local-package", "simulated": False, "provenance": out["provenance"],
                                 "package_dir": out["package_dir"], "sha256": sha, "prepared_at": _now()})
    return out


# ---- plan: read-only summary bound to a hash -------------------------------------

def changelog_section(text, ver):
    """The CHANGELOG entry of one version (heading `## [<version>] …` to the
    next `## `), or None."""
    if not isinstance(text, str):
        return None
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and ("[%s]" % ver in line or line[3:].strip().startswith(ver)):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def _prepared_info(package_dir):
    """The PREPARED.json written by fetch/prepare next to the extraction
    folder (package_dir = <holder>/package/<top>), when it names this package."""
    package_dir = Path(package_dir)
    for holder in (package_dir.parent, package_dir.parent.parent):
        p = holder / PREPARED
        if p.is_file():
            data, err = core.read_json(p)
            if not err and isinstance(data, dict) and data.get("package_dir") == str(package_dir):
                return data
    return None


def _plan_hash(root, pkg_manifest, up, may_apply, origin=None, provenance=None, archive_sha256=None):
    """Binds the approval to the installation (state of each core entry), the
    package (every file hash) and, since 2.2.0, to its origin, its recorded
    provenance and the archive verified by fetch/prepare."""
    return core.sha256_bytes(core.canonical_json({
        "installation": str(root), "from": up["from_version"], "to": up["to_version"],
        "package_files": pkg_manifest["files"],
        "entries": [(e["path"], e["action"]) for e in up["entries"]],
        "migrations_may_apply": may_apply, "origin": origin, "provenance": provenance,
        "archive_sha256": archive_sha256}).encode("utf-8"))


def _prepared_archive_sha(prepared):
    if not isinstance(prepared, dict):
        return None
    release = prepared.get("release") if isinstance(prepared.get("release"), dict) else {}
    sha = release.get("zip_sha256") or prepared.get("sha256")
    return sha if isinstance(sha, str) else None


def plan(root, package_dir, origin=None, write=True, plan_file=None):
    """Read-only summary of what an update would do, bound to a hash and
    written to a plan file (the approval covers that exact plan)."""
    root, pkg = Path(root), Path(package_dir)
    kind = installation_kind(root)
    out = {"ok": False, "applicable": False, "installation": kind, "package_dir": str(pkg),
           "current_version": version.WORKSPACE_VERSION, "target_version": None,
           "origin": origin, "provenance": None, "changes": None, "upgrade": None,
           "migrations_may_apply": None, "backups": None, "rollback": None,
           "restart_required": True, "notes": {"restart": RESTART_NOTE, "atomicity": NOT_ATOMIC_NOTE},
           "plan_file": None, "plan_hash": None, "refusals": []}
    if kind["kind"] != "distribution":
        out["refusals"].append("development upstream: " + kind["reason"])
        return out
    prepared = _prepared_info(pkg)
    if prepared:
        out["origin"] = out["origin"] or prepared.get("origin")
        out["provenance"] = prepared.get("provenance")
        out["simulated"] = bool(prepared.get("simulated"))
    out["origin"] = out["origin"] or "local-package"
    if not out["provenance"]:
        out["provenance"] = ("local package folder: manifest and every file hash verified offline — "
                             "origin not verified online")
    pkg_manifest, problems = verify_package_dir(pkg)
    if problems:
        out["refusals"].append("package not verified: %s" % "; ".join(problems[:5]))
        return out
    up = upgrade.plan(root, pkg)
    out["upgrade"] = {k: up.get(k) for k in ("ok", "error", "from_version", "to_version", "counts", "conflicts",
                                             "refused", "interrupted")}
    out["upgrade"]["kept_local"] = [e["path"] for e in up["entries"] if e["action"] == "keep-local"]
    out["upgrade"]["retired"] = [e["path"] for e in up["entries"] if e["action"] in ("remove", "conflict-rm")]
    out["upgrade"]["changed"] = [e["path"] for e in up["entries"] if e["action"] in ("add", "update")]
    if up["error"]:
        out["refusals"].append(up["error"])
        return out
    if up["refused"]:
        out["refusals"].append("refused entries in the upgrade plan: %s" % ", ".join(up["refused"][:5]))
    target = up["to_version"]
    out["target_version"] = target
    cmp = version.compare(target, version.WORKSPACE_VERSION)
    if cmp is None:
        out["refusals"].append("target version %r is not a MAJOR.MINOR.PATCH number" % target)
    elif cmp < 0:
        out["refusals"].append("the package version %s is LOWER than the installed %s — a downgrade is not an "
                               "update: use the rollback procedure" % (target, version.WORKSPACE_VERSION))
    out["direction"] = {None: "unknown", 1: "upgrade", 0: "same-version", -1: "downgrade"}[cmp]
    # changes: release notes of the fetch, else the CHANGELOG shipped in the package
    notes = (prepared or {}).get("notes") or ""
    notes_path = (prepared or {}).get("notes_path")
    if notes_path and Path(notes_path).is_file():
        notes = Path(notes_path).read_text(encoding="utf-8", errors="replace")
    if not notes.strip() and (pkg / "CHANGELOG.md").is_file():
        notes = changelog_section(pkg.joinpath("CHANGELOG.md").read_text(encoding="utf-8", errors="replace"),
                                  version.normalized(target) or str(target)) or ""
    out["changes"] = notes.strip() or "not available for this package (no release notes, no CHANGELOG entry)"
    # data migrations that MAY apply: every step declared by the package (corrected 2026-11-13, audit H-05).
    # Steps are state-based (m004 recurs at each version): the journal never removes a step from the
    # approval; `migrate --plan`, run by the new code, decides which ones are actually due.
    declared = pkg_manifest["raw"].get("migrations")
    out["migrations_recorded"] = sorted(i for i in migration._recorded(config.read_config(root)) if isinstance(i, str))
    if isinstance(declared, list):
        out["migrations_may_apply"] = [m for m in declared if isinstance(m, str)]
    else:
        out["migrations_may_apply"] = None   # package without declaration: any step will stop the run
    out["backups"] = {"upgrade": upgrade.list_backups(root), "migration": migration.list_backups(root),
                      "new_backup_before_apply": str(upgrade.BACKUP_REL) + "/<stamp>/"}
    out["rollback"] = rollback_info(root)["order"]
    out["archive_sha256"] = _prepared_archive_sha(prepared)
    out["plan_hash"] = _plan_hash(root, pkg_manifest, up, out["migrations_may_apply"], out["origin"],
                                  out["provenance"], out["archive_sha256"])
    out["ok"] = not out["refusals"]
    # a kept local file whose new version already sits beside it (.pws-new, verified) needs nothing more
    pending_kept = [e["path"] for e in up["entries"] if e["action"] == "keep-local"
                    and not _new_version_present(root, e["path"], e.get("new_sha256"))]
    out["upgrade"]["kept_local_pending"] = pending_kept
    out["applicable"] = out["ok"] and not up["conflicts"] and cmp is not None and cmp >= 0 \
        and bool(out["upgrade"]["changed"] or out["upgrade"]["retired"] or pending_kept)
    if out["ok"] and not out["applicable"]:
        if up["conflicts"]:
            out["refusals"].append("locally modified core files: %s — review them (restore, or keep a copy) before "
                                   "updating; the guided path never overwrites them" % ", ".join(up["conflicts"][:8]))
        else:
            out["refusals"].append("nothing to apply: the installation already matches this package")
    if write and out["applicable"]:      # only an approvable plan is written
        if plan_file:
            path = Path(plan_file)
            # audit H-13: an explicit plan file never replaces an existing
            # file (a user file, the configuration) nor goes through a link
            if os.path.lexists(str(path)):
                out["refusals"].append("plan file %s already exists: choose a new file name (nothing was "
                                       "overwritten)" % path)
                out["ok"] = out["applicable"] = False
                return out
        else:
            if not core.runtime_tree_is_real(root, PLANS_REL.parts):
                out["refusals"].append("plan folder %s is a symlink or escapes the installation" % PLANS_REL)
                out["ok"] = out["applicable"] = False
                return out
            (root / PLANS_REL).mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=_now().replace(":", "") + "-", suffix=".json", dir=str(root / PLANS_REL))
            os.close(fd)
            path = Path(name)
        core.atomic_write_json(path, {k: v for k, v in out.items() if k != "plan_file"})
        out["plan_file"] = str(path)
    return out


# ---- apply: upgrade, then migrations by the new code, then verification ----------

def _run_new_code(root, args):
    """Run the tooling INSTALLED in `root` (the new code after an upgrade) in a
    separate process; returns (rc, stdout, stderr)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run([sys.executable, "-m", "tools.pws_workspace"] + list(args), cwd=str(root),
                              capture_output=True, text=True, timeout=900, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _json_or_none(text):
    """Parsed JSON, or None when `text` is not a string or not JSON — never raises."""
    try:
        return json.loads(text)
    except (TypeError, ValueError, RecursionError):
        return None


def _new_version_present(root, rel, new_sha):
    """The new version of a kept local file sits beside it as <rel>.pws-new
    with the package hash."""
    p = Path(root) / (rel + ".pws-new")
    return bool(new_sha) and not p.is_symlink() and p.is_file() and core.sha256_file(p) == new_sha


def _verify_installed(root, package_dir, kept=None):
    """Installed files against the new manifest, with the files KEPT locally
    (audit H-04) verified separately: the local file is the one present
    before the update (preserved, hash unchanged) and the new version proposed
    by the package sits beside it intact (`<path>.pws-new`, package hash)."""
    manifest, problems = verify_package_dir(package_dir)
    if manifest is None:
        return {"ok": False, "problems": problems, "mismatched": [], "kept": []}
    kept = kept or {}
    mismatched, kept_report = [], []
    for rel, sha in manifest["files"].items():
        p = Path(root) / rel
        if rel in kept:
            info = kept[rel] or {}
            local_ok = not p.is_symlink() and p.is_file() and bool(info.get("local_sha256")) \
                and core.sha256_file(p) == info.get("local_sha256")
            new_ok = _new_version_present(root, rel, sha)
            kept_report.append({"path": rel, "local_preserved": local_ok, "new_version": rel + ".pws-new",
                                "new_version_intact": new_ok})
            if not (local_ok and new_ok):
                mismatched.append(rel)
            continue
        if p.is_symlink() or not p.is_file() or core.sha256_file(p) != sha:
            mismatched.append(rel)
    installed, _ = upgrade.installed_manifest(root)
    same_marker = installed is not None and installed["files"] == manifest["files"]
    return {"ok": not mismatched and same_marker, "mismatched": mismatched, "kept": kept_report,
            "installed_version": installed["version"] if installed else None,
            "expected_version": manifest["version"], "marker_identical": same_marker}


def _int_rc(rc):
    return isinstance(rc, int) and not isinstance(rc, bool)


def migrate_plan_check(rc, out):
    """(steps, problem): strict reading of `migrate --plan` (audit H-02). The
    whole plan is unusable when the exit code is not 0, the configuration is
    unreadable or one step is malformed — never filtered, never defaulted."""
    doc = _json_or_none(out)
    if not _int_rc(rc):
        return None, "migrate --plan exit code %r" % (rc,)
    if not isinstance(doc, dict):
        return None, "migrate --plan did not return a JSON object (rc %s): %s" % (rc, str(out or "no output").strip()[:200])
    if doc.get("config_error") is not None:
        return None, "configuration unreadable: %s" % str(doc.get("config_error"))[:200]
    if rc != 0:
        return None, "migrate --plan exit code %s" % rc
    steps = doc.get("steps")
    if not isinstance(steps, list):
        return None, "`steps` is not a list"
    seen = set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            return None, "step %d is not an object" % i
        sid = s.get("id")
        if not isinstance(sid, str) or not sid.strip() or not sid.isprintable():
            return None, "step %d has no usable id" % i
        if sid in seen:
            return None, "step %s listed twice" % sid
        seen.add(sid)
        if not isinstance(s.get("blocked"), bool):
            return None, "step %s: `blocked` is not a boolean" % sid
        if not isinstance(s.get("detail"), str):
            return None, "step %s: `detail` is not a string" % sid
        waits = s.get("waits_for")
        if waits is not None and not isinstance(waits, str):
            return None, "step %s: `waits_for` is not a string" % sid
    return steps, None


def migrate_apply_check(rc, out):
    """(report, problem): strict reading of `migrate --apply` (audit H-01):
    an object whose `applied` lists objects with a usable `id`, whose
    `errors` is a list, whose exit code is 1 exactly when errors exist."""
    doc = _json_or_none(out)
    if not _int_rc(rc):
        return None, "migrate --apply exit code %r" % (rc,)
    if not isinstance(doc, dict):
        return None, "migrate --apply did not return a JSON object (rc %s): %s" % (rc, str(out or "no output").strip()[:200])
    applied, errors = doc.get("applied"), doc.get("errors")
    if not isinstance(applied, list):
        return None, "`applied` is not a list"
    for i, a in enumerate(applied):
        if not isinstance(a, dict) or not isinstance(a.get("id"), str) or not a["id"].strip():
            return None, "applied entry %d has no usable id" % i
    if not isinstance(errors, list):
        return None, "`errors` is not a list"
    backup = doc.get("backup")
    if backup is not None and not isinstance(backup, str):
        return None, "`backup` is not a path"
    if rc != (1 if errors else 0):
        return None, "exit code %s inconsistent with %d error(s)" % (rc, len(errors))
    return doc, None


def _done(code_installed=False, code_verified=None, applied=None, remaining=None, blocked=None,
          diagnostic="not-run"):
    """What was actually accomplished — reported with every verdict so that the
    account always matches the operations performed."""
    return {"code_installed": code_installed, "code_verified": code_verified,
            "migrations_applied": list(applied or []), "migrations_remaining": list(remaining or []),
            "migrations_blocked": list(blocked or []), "diagnostic": diagnostic, "kept_local": []}


DOCTOR_SEVERITIES = ("OK", "INFO", "WARNING", "BLOCKING")   # the doctor's contract, nothing else
DOCTOR_FIELDS = ("check", "severity", "detail")               # every entry of `doctor --json` carries the three


def _doctor_entry_problem(index, entry):
    """Why entry `index` of a `doctor --json` result violates the contract
    (None when it conforms): an object whose `check` is a usable identifier
    (non-blank, printable, single-line string), whose `severity` is one of
    DOCTOR_SEVERITIES and whose `detail` is a string. Checked field by field,
    presence then type then value, so the first violation is named; nothing
    is defaulted, nothing is skipped. Never raises on wrongly typed values."""
    if not isinstance(entry, dict):
        return "entry %d is not an object (%s)" % (index, type(entry).__name__)
    for field in DOCTOR_FIELDS:
        if field not in entry:
            return "entry %d has no '%s' field" % (index, field)
        value = entry[field]
        if not isinstance(value, str):
            return "entry %d: '%s' is not a string (%s)" % (index, field, type(value).__name__)
        if field == "check" and (not value.strip() or not value.isprintable()):
            return "entry %d has an unusable check identifier (%r)" % (index, value[:40])
        if field == "severity" and value not in DOCTOR_SEVERITIES:
            return "entry %d (check %r) has an unknown severity %r" % (index, entry["check"][:60], value[:40])
    return None


def doctor_verdict(rc, out, err=""):
    """Interpret a `doctor --json` run by its real contract: a JSON list of at
    least one check on stdout (the doctor always reports `tooling-tests`),
    each `{"check": <identifier>, "severity": OK|INFO|WARNING|BLOCKING,
    "detail": <string>}`, exit code 1 iff a BLOCKING check is present, else 0.
    The content is validated entry by entry BEFORE any count, message or
    verdict; one invalid entry makes the whole diagnostic unusable.
    Verdicts: `ok` (warnings alone never block), `blocking`, `unavailable`
    (not executed, unusable or non-conforming output, empty list, or exit
    code inconsistent with the result — never presented as a successful
    diagnostic)."""
    def unavailable(message, **more):
        return dict({"ok": False, "verdict": "unavailable", "rc": rc, "error": message}, **more)

    doc = _json_or_none(out)
    if rc is None or isinstance(rc, bool) or not isinstance(rc, int) or not isinstance(doc, list):
        return unavailable("doctor --json did not produce a usable result (rc %s): %s"
                           % (rc, str(err or out or "no output").strip()[:300]))
    if not doc:
        return unavailable("doctor --json reported no check at all (rc %s) — the doctor always reports at "
                           "least one: not trusted" % rc)
    for index, entry in enumerate(doc):
        problem = _doctor_entry_problem(index, entry)
        if problem:
            return unavailable("doctor --json result violates the doctor contract (rc %s): %s" % (rc, problem),
                               entries=len(doc))
    counts = {}
    for r in doc:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    blocking = [r["check"] for r in doc if r["severity"] == "BLOCKING"]
    warnings = [r["check"] for r in doc if r["severity"] == "WARNING"]
    expected_rc = 1 if blocking else 0
    if rc != expected_rc:
        return {"ok": False, "verdict": "unavailable", "rc": rc, "counts": counts, "blocking": blocking,
                "warnings": warnings,
                "error": "doctor exit code %s is inconsistent with its result (%d BLOCKING): not trusted"
                         % (rc, len(blocking))}
    if blocking:
        return {"ok": False, "verdict": "blocking", "rc": rc, "counts": counts, "blocking": blocking,
                "warnings": warnings}
    return {"ok": True, "verdict": "ok", "rc": rc, "counts": counts, "blocking": [], "warnings": warnings}


def apply(root, plan_file, yes=False, runner=None, copy=None):
    """Apply an approved plan. The report's `status` is explicit and never a
    success unless every stage succeeded: `refused-before-mutation`,
    `failed-restored`, `failed-restore-<stage>`, `incomplete`,
    `stopped-blocked-migrations`, `stopped-unplanned-migrations`,
    `diagnostic-blocking`, `diagnostic-unavailable`, `applied`. `done` states
    what was accomplished (code installed and verified, migrations applied,
    remaining, blocked, diagnostic), `recovery` the backups, `next_action` the
    useful next step; `restart_required` is true whenever the code changed."""
    root = Path(root)
    report = {"ok": False, "status": None, "plan_file": str(plan_file), "stages": {}, "recovery": {},
              "done": _done(), "next_action": None, "restart_required": False,
              "notes": {"restart": RESTART_NOTE, "atomicity": NOT_ATOMIC_NOTE}}

    def refused(message):
        report["status"] = "refused-before-mutation"
        report["error"] = message
        report["next_action"] = "nothing changed — fix the cause, then plan again"
        return report

    approved, err = core.read_json(plan_file)
    if err or not isinstance(approved, dict) or not approved.get("plan_hash"):
        return refused("plan file unreadable or without hash: %s" % (err or plan_file))
    if not yes:
        return refused("explicit confirmation required (--yes) after reviewing the plan")
    pkg = Path(approved.get("package_dir") or "")
    current = plan(root, pkg, origin=approved.get("origin"), write=False)
    report["plan"] = {k: current.get(k) for k in ("current_version", "target_version", "origin", "upgrade",
                                                  "migrations_may_apply", "refusals", "plan_hash")}
    if current.get("plan_hash") != approved["plan_hash"]:
        return refused("the plan changed since it was approved (installation or package differ) — plan again")
    if not current["applicable"]:
        return refused("; ".join(current["refusals"]) or "plan not applicable")
    target = current["target_version"]
    # stage 1: code, by the upgrade authority (never --overwrite-local here)
    up = upgrade.apply(root, pkg, overwrite_local=False, copy=copy)
    stage = {"ok": up["ok"], "error": up.get("error"), "backup": up.get("backup"),
             "applied": len(up.get("applied") or []), "kept_local": up.get("kept")}
    if up.get("restore") is not None:
        stage["restore"] = up["restore"]
    report["stages"]["upgrade"] = stage
    if not up["ok"]:
        if up.get("restore") is None:
            return refused(up.get("error") or "upgrade refused")
        report["recovery"] = {"upgrade_backup": up.get("backup"), "restore_stage": up["restore"].get("stage")}
        if up["restore"].get("ok"):
            report["status"] = "failed-restored"
            report["done"] = _done(code_installed=False, code_verified=False)
            report["next_action"] = ("the previous state was restored and verified (backup kept) — fix the cause "
                                     "of the failure, then plan again")
        else:
            report["status"] = "failed-restore-" + str(up["restore"].get("stage"))
            report["recovery"]["restore_problems"] = up["restore"].get("problems")
            report["done"] = _done(code_installed=None, code_verified=False)   # partially written, not restored
            report["next_action"] = ("the installation is left as it was at the failure — fix the reported "
                                     "problem, then `upgrade --rollback %s`" % Path(up.get("backup") or "").name)
        report["error"] = up.get("error")
        return report
    report["restart_required"] = True
    report["recovery"] = {"upgrade_backup": up.get("backup")}
    stamp = Path(up["backup"]).name
    rollback_hint = ("rollback stays available: `migrate --rollback <stamp>` for an applied data migration, "
                     "then `upgrade --rollback %s` for the code" % stamp)
    run = runner or _run_new_code
    kept = {k.get("path"): k for k in (up.get("kept") or []) if isinstance(k, dict)}
    try:
        return _after_code_installed(root, pkg, approved, target, report, run, rollback_hint, kept)
    except Exception as exc:  # noqa: BLE001 — the code is installed: an account is always returned (audit H-03)
        report["status"] = "incomplete"
        report["error"] = ("code installed (version %s); internal error after the code installation (%s: %s) — "
                           "the data migrations and the diagnostic may not have run"
                           % (target, type(exc).__name__, str(exc)[:300]))
        report["done"] = _done(code_installed=True, code_verified=None, diagnostic="not-run")
        report["done"]["migrations_evaluated"] = False
        report["next_action"] = ("run `python3 -m tools.pws_workspace migrate --plan`, then `migrate --apply` if "
                                 "steps are due, then `doctor`; %s" % rollback_hint)
        return report


def _after_code_installed(root, pkg, approved, target, report, run, rollback_hint, kept):
    """Stages 2 and 3 of `apply`, once the new code is installed: data
    migrations decided, applied and re-checked by the NEW code (every response
    validated strictly), then verification of the installed files (kept local
    files verified separately) and the diagnostic."""
    planned = report["plan"].get("migrations_may_apply")   # recomputed and hash-bound (audit H-06)
    rc, out, errtxt = run(root, ["migrate", "--plan"])
    steps, problem = migrate_plan_check(rc, out)
    if problem:
        report["stages"]["migrate"] = {"applied": [], "pending": None, "blocked": [], "unplanned": [],
                                       "evaluated": False, "errors": [{"error": "migrate --plan unusable (%s) %s"
                                                                       % (problem, (errtxt or "").strip()[:200])}]}
        verify = _verify_installed(root, pkg, kept)
        report["stages"]["verify"] = verify
        report["done"] = _done(code_installed=True, code_verified=verify["ok"], diagnostic="not-run")
        report["done"]["migrations_evaluated"] = False
        report["done"]["kept_local"] = [k["path"] for k in verify.get("kept") or []]
        report["status"] = "incomplete"
        report["error"] = ("code installed (version %s, %s); data migrations NOT evaluated: %s"
                           % (target, "verified" if verify["ok"] else "verification found mismatches", problem))
        report["next_action"] = ("run `python3 -m tools.pws_workspace migrate --plan` yourself, then `migrate "
                                 "--apply` explicitly; %s" % rollback_hint)
        return report
    ids = {s["id"] for s in steps}
    # a step waiting for a prerequisite that is itself due is applied in the same run (not a block)
    waiting = {s["id"] for s in steps if s["blocked"] and s.get("waits_for") in ids}
    blocked = [{"id": s["id"], "detail": s["detail"]} for s in steps if s["blocked"] and s["id"] not in waiting]
    pending = [s["id"] for s in steps if not s["blocked"] or s["id"] in waiting]
    unplanned = [s for s in pending if not isinstance(planned, list) or s not in planned]
    mstage = {"pending": pending, "blocked": blocked, "planned": planned, "unplanned": unplanned,
              "applied": [], "errors": [], "backup": None, "evaluated": True}
    report["stages"]["migrate"] = mstage
    stopped = None
    remaining = list(pending)
    if blocked:
        stopped = "stopped-blocked-migrations"        # nothing applied to the data, not even the other steps
    elif unplanned:
        stopped = "stopped-unplanned-migrations"
    elif pending:
        rc, out, errtxt = run(root, ["migrate", "--apply"])
        mres, problem = migrate_apply_check(rc, out)
        if problem:
            mstage["errors"].append({"error": "migrate --apply response unusable (%s) %s"
                                              % (problem, (errtxt or "").strip()[:200])})
            mstage["apply_response_usable"] = False
        else:
            mstage["applied"] = [a["id"] for a in mres["applied"]]
            mstage["errors"] = [e if isinstance(e, dict) else {"error": str(e)} for e in mres["errors"]]
            mstage["backup"] = mres.get("backup")
            if mstage["backup"]:
                report["recovery"]["migration_backup"] = mstage["backup"]
        # verification by the new code: no due migration may remain unexplained (audit H-01)
        rc2, out2, _err2 = run(root, ["migrate", "--plan"])
        after, problem2 = migrate_plan_check(rc2, out2)
        if problem2:
            mstage["errors"].append({"error": "post-apply `migrate --plan` unusable (%s)" % problem2})
            remaining = [p for p in pending if p not in mstage["applied"]]
            mstage["remaining_known"] = False
        else:
            remaining = [s["id"] for s in after if not s["blocked"] or s.get("waits_for")]
            newly_blocked = [s["id"] for s in after if s["blocked"] and not s.get("waits_for")]
            if remaining:
                mstage["errors"].append({"error": "migration(s) still due after `migrate --apply`: %s"
                                                  % ", ".join(remaining)})
            if newly_blocked:
                mstage["errors"].append({"error": "migration(s) blocked after `migrate --apply`: %s"
                                                  % ", ".join(newly_blocked)})
        mstage["remaining"] = remaining
    # stage 3: verification of the installed files and version, then the doctor (read-only, always run)
    verify = _verify_installed(root, pkg, kept)
    report["stages"]["verify"] = verify
    rc, out, errtxt = run(root, ["doctor", "--json"])
    dstage = doctor_verdict(rc, out, errtxt)
    report["stages"]["doctor"] = dstage
    report["done"] = _done(code_installed=True, code_verified=verify["ok"], applied=mstage["applied"],
                           remaining=remaining, blocked=[b["id"] for b in blocked], diagnostic=dstage["verdict"])
    report["done"]["kept_local"] = [k["path"] for k in verify.get("kept") or []]
    code_text = "code installed (version %s, %s)" % (target, "verified" if verify["ok"]
                                                     else "verification found mismatches: %s"
                                                     % ", ".join(verify.get("mismatched") or [])[:200])
    diag_text = {"ok": "diagnostic ok", "blocking": "diagnostic BLOCKING on %s" % ", ".join(dstage.get("blocking") or []),
                 "unavailable": "diagnostic unavailable (%s)" % dstage.get("error")}[dstage["verdict"]]
    if stopped == "stopped-blocked-migrations":
        report["status"] = stopped
        report["error"] = ("%s; data migration(s) BLOCKED: %s — no data migration applied, the others wait (%s); %s"
                           % (code_text, "; ".join("%s (%s)" % (b["id"], b["detail"]) for b in blocked),
                              ", ".join(pending) or "none", diag_text))
        report["next_action"] = ("resolve the blocking cause, then `migrate --plan` and `migrate --apply` "
                                 "explicitly; %s" % rollback_hint)
    elif stopped == "stopped-unplanned-migrations":
        report["status"] = stopped
        report["error"] = ("%s; data migration(s) outside the approved plan: %s — no data migration applied; %s"
                           % (code_text, ", ".join(unplanned), diag_text))
        report["next_action"] = ("review `migrate --plan`, then `migrate --apply` explicitly; %s" % rollback_hint)
    elif mstage["errors"]:
        report["status"] = "incomplete"
        report["error"] = ("%s; data migrations not completed (%s) — applied: %s; remaining: %s; %s"
                           % (code_text, "; ".join(str(e.get("error") or e) for e in mstage["errors"])[:300],
                              ", ".join(mstage["applied"]) or "none", ", ".join(remaining) or "none", diag_text))
        report["next_action"] = ("the migration backup is kept (`migrate --rollback <stamp>`) — fix the cause, "
                                 "then `migrate --plan` and `migrate --apply`; %s" % rollback_hint)
    elif not verify["ok"]:
        report["status"] = "incomplete"
        report["error"] = "%s; migrations applied: %s; %s" % (code_text, ", ".join(mstage["applied"]) or "none", diag_text)
        report["next_action"] = ("the installed files do not all match the new manifest (or a kept local file was "
                                 "not preserved, or its new version is damaged) — plan again, or %s" % rollback_hint)
    elif dstage["verdict"] == "blocking":
        report["status"] = "diagnostic-blocking"
        report["error"] = "%s; migrations applied: %s; %s" % (code_text, ", ".join(mstage["applied"]) or "none", diag_text)
        report["next_action"] = ("resolve the BLOCKING checks reported by `python3 -m tools.pws_workspace doctor` "
                                 "(the update itself is in place); %s" % rollback_hint)
    elif dstage["verdict"] == "unavailable":
        report["status"] = "diagnostic-unavailable"
        report["error"] = "%s; migrations applied: %s; %s" % (code_text, ", ".join(mstage["applied"]) or "none", diag_text)
        report["next_action"] = ("run `python3 -m tools.pws_workspace doctor` yourself and read its result before "
                                 "trusting this update; %s" % rollback_hint)
    else:
        report["status"] = "applied"
        report["ok"] = True
        report["next_action"] = RESTART_NOTE
        if report["done"]["kept_local"]:
            report["next_action"] += ("; your local versions were kept, the new ones sit beside them for review: %s"
                                      % ", ".join(k + ".pws-new" for k in report["done"]["kept_local"]))
    return report

# ---- rollback: information only -----------------------------------------------

def _backup_entries(root, rel, read_state=True):
    entries = []
    for stamp in sorted(set((upgrade.list_backups(root) if rel == upgrade.BACKUP_REL else migration.list_backups(root)))):
        data, err = core.read_json(Path(root) / rel / stamp / "MANIFEST.json")
        e = {"stamp": stamp}
        if not err and isinstance(data, dict):
            e.update({"state": data.get("state"), "from_version": data.get("from_version"),
                      "to_version": data.get("to_version"), "files": len(data.get("files") or [])})
        entries.append(e)
    return entries


def rollback_info(root):
    """What exists and in which order it is rolled back — nothing is restored."""
    root = Path(root)
    return {
        "order": [
            {"step": 1, "what": "data migrations (configuration, manifests) — most recent first",
             "command": "python3 -m tools.pws_workspace migrate --rollback <stamp>"},
            {"step": 2, "what": "core files (code) — refused while a later data migration is still recorded",
             "command": "python3 -m tools.pws_workspace upgrade --rollback <stamp>"},
        ],
        "upgrade_backups": _backup_entries(root, upgrade.BACKUP_REL),
        "migration_backups": _backup_entries(root, migration.BACKUP_REL),
        "limits": [
            "a restoration is validated as a whole under the shared lock before any write; one invalid entry "
            "refuses it entirely (nothing changed); success is declared only when every restored file is verified",
            "backups live in .claude/runtime (ephemeral space): protect them like the rest of the runtime",
            "code rollback does not undo PineTS engine changes or product edits made meanwhile",
            NOT_ATOMIC_NOTE, RESTART_NOTE,
        ],
        "restores_nothing": True,
    }
