# SPDX-License-Identifier: Apache-2.0
"""Core upgrade of an INSTALLED Pine Workspace from a distribution package.

Three distinct operations (ratified 2026-11-06):
  1. delivery of a new core version    → `upgrade --from <package> --plan | --apply`
  2. application of data migrations    → `migrate --plan | --apply` (separate step)
  3. rollback                          → `migrate --rollback` (data) then
                                          `upgrade --rollback <stamp>` (code)

Facts, never guesses: the installed core is identified by the core manifest
copied at installation (`PWS_DISTRIBUTION.json` at the workspace root:
files → SHA-256). An installation without it is the upstream workspace (the
one the distribution is built from) and is never upgraded by this tool.

Physical confinement (corrected 2026-11-06 after independent verification):
every path read or written — in the package, in the installation, in the
backups, the `.pws-new` copies and the manifests — is resolved PHYSICALLY
with the shared primitives (`core.is_within`, `core.runtime_tree_is_real`):
a symlinked directory or file on the chain, or a path escaping its root,
is REFUSED before any mutation and reported in the plan (never skipped
silently). A manifest carrying an invalid entry makes the whole plan
refused.

Backups and rollback (corrected the same day): every mutating operation
takes the shared mutation lock (`.claude/runtime/pws-mutation.lock`, also
taken by data migrations) so two concurrent operations are serialized or
refused; the backup folder is created EXCLUSIVELY with a unique name
(timestamp + random suffix, never reused even within the same second); the
backup is verified (hash of every copy) before the first mutation; the
manifest records the data migrations present at apply time so a code
rollback refuses while a later data migration is still applied, whatever
the clock says; a restore is declared successful only when every restored
file matches its recorded hash and every added file is gone.

Restoration order (corrected 2026-11-06 after the second verification, shared
module `restore.py`): a rollback — explicit or automatic after a failed
apply — first validates the WHOLE restoration under the lock (manifest,
confinement of every path, destinations, presence and hash of every copy)
and refuses it entirely, without a single write or removal, when one entry
is invalid; only then are the files copied and verified again.

Plan, per file of the new package:
  unchanged      installed == new
  update         installed == old manifest hash, new differs
  add            absent from the installation
  keep-local     installed differs from the old manifest AND the file is a
                 locally mutable core file (engine provenance, calibration,
                 pin/lockfile, Claude Code settings): kept; the new version is
                 written beside it as `<name>.pws-new` for review
  conflict       installed differs from the old manifest (local modification
                 of the core): refused unless --overwrite-local (backed up)
  refused        unsafe path (symlink, escape, protected prefix, package file
                 missing or hash mismatch) — the plan is not applicable
and per file of the old manifest absent from the new package:
  remove         installed == old hash → removed (backed up)
  conflict-rm    installed modified locally → kept unless --overwrite-local

Never touched: scripts/, docs/maintenance/, pws.config.json,
.claude/settings.local.json, .claude/runtime/, node_modules, and anything
not listed in either manifest.

Interruptions (corrected 2026-11-13, audit F-01): every file is written to a
temporary file then renamed (never a truncated core file); the backup manifest
is complete and marked `applying` BEFORE the first mutation; an interception
(Ctrl-C, SystemExit, any exception) restores the previous state through
`restore.py` and reports it. An abrupt stop (SIGKILL, power loss) cannot be
intercepted: the backup then stays `applying`, the plan and `update status`
report it as an interrupted upgrade, and `upgrade --rollback <stamp>` accepts
it (whole restoration validated before any write) — or the same package can be
applied again, explicitly. Rollbacks respect the order of the backups: an
older backup is refused while a newer one is still applied (audit F-10).
"""
import datetime
import os
import shutil
import tempfile
from pathlib import Path

from . import config, core, restore
from .restore import confined   # shared confinement rule (also used by migrate)

MARKER = "PWS_DISTRIBUTION.json"
BACKUP_REL = core.RUNTIME_REL / "upgrade-backup"
MUTATION_LOCK_REL = core.RUNTIME_REL / "pws-mutation.lock"
LOCALLY_MUTABLE = {
    "tools/pine_exec/PROVENANCE.json",
    "tools/pine_exec/calibration/capabilities.json",
    "tools/pine_exec/package.json",
    "tools/pine_exec/package-lock.json",
    ".claude/settings.json",
}
PROTECTED_PREFIXES = ("scripts/", "docs/maintenance/", ".claude/runtime/", ".claude/settings.local.json",
                      "pws.config.json", "tools/pine_exec/node_modules/", ".git/")


def _unsafe_key(key):
    """A manifest entry that is not a plain relative path, or that designates a
    protected zone in any spelling (`./scripts/…`, `docs//maintenance`,
    `Scripts/…` on a case-insensitive volume, `.git/…`) — audit F-04."""
    if not isinstance(key, str) or not key or "\\" in key or key.startswith("/"):
        return True
    if any(part in ("", ".", "..") for part in key.split("/")):
        return True
    low = key.casefold()
    return any(low == pref.rstrip("/").casefold() or low.startswith(pref.casefold()) for pref in PROTECTED_PREFIXES)


def _stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_marker(folder):
    """(marker, error). Any invalid entry (non-string, absolute, traversal,
    protected prefix) invalidates the WHOLE manifest — never skipped."""
    path = Path(folder) / MARKER
    if path.is_symlink():
        return None, "%s is a symlink" % MARKER
    data, err = core.read_json(path)
    if err or not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return None, err or "marker invalid"
    files, invalid = {}, []
    for k, v in data["files"].items():
        if not isinstance(v, str) or _unsafe_key(k):
            invalid.append(repr(k)[:80])
            continue
        files[k] = v
    if invalid:
        return None, "manifest carries invalid entries: %s" % ", ".join(invalid[:5])
    return {"version": data.get("workspace_version"), "files": files, "raw": data}, None


def installed_manifest(folder):
    """Public reader of a core manifest (installation or package): (manifest,
    error) — `manifest["raw"]` carries the whole marker. Used by the guided
    update path and the doctor; an installation without it is the upstream."""
    return _read_marker(folder)


def _roots_ok(root, package):
    root, package = Path(root), Path(package)
    if not root.is_dir():
        return "installation folder missing"
    if not package.is_dir():
        return "package folder missing"
    if root.is_symlink() or package.is_symlink():
        return "installation and package must be real folders (not symlinks)"
    if core.is_within(root, package) or core.is_within(package, root):
        return "the package must be a separate folder (not inside the installation, nor around it)"
    if not core.runtime_tree_is_real(root, BACKUP_REL.parts):
        return "backup location %s is a symlink or escapes the installation — refused" % BACKUP_REL
    return None


def plan(root, package):
    """Read-only comparison of the installation with the package."""
    root, package = Path(root), Path(package)
    out = {"ok": False, "package": str(package), "installation": str(root),
           "from_version": None, "to_version": None, "entries": [],
           "counts": {}, "conflicts": [], "refused": [], "error": None}
    err = _roots_ok(root, package)
    if err:
        out["error"] = err
        return out
    new, err = _read_marker(package)
    if new is None:
        out["error"] = "package has no valid %s: %s" % (MARKER, err)
        return out
    old, oerr = _read_marker(root)
    if old is None:
        out["error"] = ("no valid core manifest in the installation (%s): this workspace is the "
                        "upstream or was installed before manifests existed — not upgradable by "
                        "this tool" % (oerr,))
        return out
    out["from_version"], out["to_version"] = old["version"], new["version"]
    entries = []
    for rel, new_sha in sorted(new["files"].items()):
        src = confined(package, rel)
        dst = confined(root, rel)
        if src is None or not src.is_file():
            entries.append({"path": rel, "action": "refused",
                            "reason": "package file missing, symlinked or escaping the package"})
            continue
        if core.sha256_file(src) != new_sha:
            entries.append({"path": rel, "action": "refused", "reason": "package file hash mismatch"})
            continue
        if dst is None or confined(root, rel + ".pws-new") is None:
            entries.append({"path": rel, "action": "refused",
                            "reason": "installation path is a symlink or escapes the installation"})
            continue
        old_sha = old["files"].get(rel)
        if not dst.exists():
            entries.append({"path": rel, "action": "add"})
        elif not dst.is_file():
            entries.append({"path": rel, "action": "refused", "reason": "installation path is not a regular file"})
        else:
            cur = core.sha256_file(dst)
            if cur == new_sha:
                entries.append({"path": rel, "action": "unchanged"})
            elif old_sha == cur:
                entries.append({"path": rel, "action": "update"})
            elif rel in LOCALLY_MUTABLE:
                entries.append({"path": rel, "action": "keep-local", "local_sha256": cur, "new_sha256": new_sha,
                                "reason": "locally mutable core file; new version written as .pws-new"})
            else:
                entries.append({"path": rel, "action": "conflict",
                                "reason": "locally modified core file (differs from the installed manifest)"})
    for rel, old_sha in sorted(old["files"].items()):
        if rel in new["files"]:
            continue
        dst = confined(root, rel)
        if dst is None:
            entries.append({"path": rel, "action": "refused",
                            "reason": "retired file path is a symlink or escapes the installation"})
            continue
        if not dst.exists():
            continue
        if not dst.is_file():
            entries.append({"path": rel, "action": "refused", "reason": "retired path is not a regular file"})
        elif core.sha256_file(dst) == old_sha:
            entries.append({"path": rel, "action": "remove", "reason": "core file retired by the new version"})
        else:
            entries.append({"path": rel, "action": "conflict-rm",
                            "reason": "retired core file modified locally — kept unless --overwrite-local"})
    out["entries"] = entries
    counts = {}
    for e in entries:
        counts[e["action"]] = counts.get(e["action"], 0) + 1
    out["counts"] = counts
    out["conflicts"] = [e["path"] for e in entries if e["action"] in ("conflict", "conflict-rm")]
    out["refused"] = [e["path"] for e in entries if e["action"] == "refused"]
    out["interrupted"] = interrupted_backups(root)
    out["ok"] = not out["refused"]
    return out


def _backup_states(root):
    """[(stamp, state, order key)] of every readable upgrade backup, oldest first."""
    out = []
    for stamp in list_backups(root):
        manifest, err = core.read_json(Path(root) / BACKUP_REL / stamp / "MANIFEST.json")
        manifest = manifest if isinstance(manifest, dict) and not err else {}
        out.append((stamp, manifest.get("state"), core.backup_order_key(stamp, manifest)))
    return sorted(out, key=lambda x: x[2])


def interrupted_backups(root):
    """Backups left `applying` by an abrupt stop (SIGKILL, power loss): the
    installation may hold a mix of old and new core files. Recovery is
    explicit: `upgrade --rollback <stamp>`, or apply the same package again."""
    return [stamp for stamp, state, _key in _backup_states(root) if state == "applying"]


def _atomic_copy(src, dst):
    """Copy through a temporary file of the destination folder, then rename:
    an interruption never leaves a truncated file at `dst`."""
    dst = Path(dst)
    fd, tmp = tempfile.mkstemp(prefix=".pws-tmp-", dir=str(dst.parent))
    os.close(fd)
    try:
        shutil.copy2(str(src), tmp)
        os.replace(tmp, str(dst))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _new_backup_dir(root):
    """Exclusively created, unique backup folder (never reused, even within
    the same second)."""
    backup_root = Path(root) / BACKUP_REL
    backup_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="%s-" % _stamp(), dir=str(backup_root)))


def _backup(root, bdir, rels):
    """Copy every touched file into bdir and VERIFY each copy. Returns
    (manifest, problems)."""
    manifest = {"stamp": bdir.name, "files": [], "state": "backup", "created_at": core.precise_now()}
    problems = []
    for rel in rels:
        src = confined(root, rel)
        entry = {"path": rel}
        if src is None:
            problems.append("%s: unsafe path" % rel)
            continue
        entry["existed"] = src.is_file()
        if src.is_file():
            dst = confined(bdir, rel)
            if dst is None:
                problems.append("%s: unsafe backup path" % rel)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            entry["sha256"] = core.sha256_file(src)
            if core.sha256_file(dst) != entry["sha256"]:
                problems.append("%s: backup copy hash mismatch" % rel)
        manifest["files"].append(entry)
    return manifest, problems


def _migration_records(root):
    cfg = config.read_config(root)
    migs = cfg["data"].get("migrations")
    return [{"id": m.get("id"), "on": m.get("on"), "backup": m.get("backup")}
            for m in (migs if isinstance(migs, list) else []) if isinstance(m, dict)]


def _lock(root):
    return core.file_lock(Path(root) / MUTATION_LOCK_REL, timeout=0.5)


def apply(root, package, overwrite_local=False, copy=None):
    """Apply the plan. `copy(src, dst)` is injectable for failure tests."""
    root, package = Path(root), Path(package)
    p = plan(root, package)
    report = {"ok": False, "plan": p, "applied": [], "kept": [], "backup": None, "error": None}
    if not p["ok"]:
        report["error"] = p["error"] or "refused entries in the plan: %s" % ", ".join(p["refused"][:5])
        return report
    if p["conflicts"] and not overwrite_local:
        report["error"] = ("locally modified core files: %s — review them, then re-run with "
                           "--overwrite-local (they are backed up) or restore them first"
                           % ", ".join(p["conflicts"][:8]))
        return report
    copy = copy or _atomic_copy
    try:
        with _lock(root):
            return _apply_locked(root, package, p, copy, report)
    except TimeoutError:
        report["error"] = "another mutating operation (upgrade or migration) is in progress on this installation — retry later"
        return report


def _apply_locked(root, package, p, copy, report):
    # the plan was computed before the lock: recompute to refuse a state that
    # changed meanwhile (freshest state, as every other PWS writer)
    p2 = plan(root, package)
    if not p2["ok"] or [e["path"] for e in p2["entries"]] != [e["path"] for e in p["entries"]] \
            or [e["action"] for e in p2["entries"]] != [e["action"] for e in p["entries"]]:
        report["error"] = "installation changed while waiting for the lock — plan again"
        return report
    touched = []
    for e in p["entries"]:
        a = e["action"]
        if a in ("add", "update", "remove", "conflict", "conflict-rm"):
            touched.append(e["path"])
        if a == "keep-local":
            touched.append(e["path"] + ".pws-new")
    touched.append(MARKER)
    bdir = _new_backup_dir(root)
    report["backup"] = str(bdir)
    manifest, problems = _backup(root, bdir, touched)
    manifest["from_version"] = p["from_version"]
    manifest["to_version"] = p["to_version"]
    manifest["migrations_at_apply"] = _migration_records(root)
    if problems:
        manifest["state"] = "backup-failed"
        manifest["problems"] = problems
        core.atomic_write_json(bdir / "MANIFEST.json", manifest)
        report["error"] = "backup could not be verified — nothing changed: %s" % "; ".join(problems[:5])
        return report
    manifest["state"] = "applying"          # complete before the first mutation; detectable after SIGKILL
    core.atomic_write_json(bdir / "MANIFEST.json", manifest)
    try:
        for e in p["entries"]:
            a, rel = e["action"], e["path"]
            if a in ("add", "update", "conflict"):
                dst = confined(root, rel)
                src = confined(package, rel)
                if dst is None or src is None:
                    raise OSError("unsafe path at apply time: %s" % rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                copy(src, dst)
                report["applied"].append({"path": rel, "action": a})
            elif a in ("remove", "conflict-rm"):
                dst = confined(root, rel)
                if dst is None:
                    raise OSError("unsafe path at apply time: %s" % rel)
                dst.unlink()
                report["applied"].append({"path": rel, "action": a})
            elif a == "keep-local":
                dst = confined(root, rel + ".pws-new")
                src = confined(package, rel)
                if dst is None or src is None:
                    raise OSError("unsafe path at apply time: %s" % rel)
                copy(src, dst)
                report["kept"].append({"path": rel, "new_version": rel + ".pws-new",
                                       "local_sha256": e.get("local_sha256"), "new_sha256": e.get("new_sha256")})
        copy(confined(package, MARKER), root / MARKER)
        manifest["state"] = "applied"
        core.atomic_write_json(bdir / "MANIFEST.json", manifest)
        report["ok"] = True
    except BaseException as exc:  # noqa: BLE001 — Ctrl-C included: validate, restore, verify, then report
        # same two-stage mechanism as `rollback` (lock already held here); SIGKILL cannot
        # reach this handler: the manifest then stays `applying` (see interrupted_backups)
        if isinstance(exc, KeyboardInterrupt):
            exc = OSError("interrupted (Ctrl-C)")
        elif isinstance(exc, SystemExit):
            exc = OSError("interrupted (exit requested)")
        res = restore.restore(root, bdir, manifest)
        manifest["state"] = "failed-restored" if res["ok"] else "failed-restore-incomplete"
        manifest["failed"] = str(exc)
        manifest["restore_stage"] = res["stage"]
        manifest["restore_problems"] = res["problems"]
        core.atomic_write_json(bdir / "MANIFEST.json", manifest)
        if res["ok"]:
            detail = "previous state restored and verified from %s" % bdir
        elif res["stage"] == "refused":
            detail = ("automatic restoration REFUSED before any write (%s) — the installation is left "
                      "as it was at the failure; the backup is kept at %s: fix the reported problem, "
                      "then run `upgrade --rollback %s`"
                      % ("; ".join(res["problems"][:5]), bdir, bdir.name))
        else:
            detail = ("previous state NOT fully restored (%s) — the backup is kept at %s"
                      % ("; ".join(res["problems"][:5]), bdir))
        report["error"] = "apply failed (%s) — %s" % (exc, detail)
        report["restore"] = {"ok": res["ok"], "stage": res["stage"], "problems": res["problems"]}
        report["applied"] = []
    return report


def list_backups(root):
    bdir = Path(root) / BACKUP_REL
    if not bdir.is_dir() or not core.runtime_tree_is_real(root, BACKUP_REL.parts):
        return []
    return sorted(d.name for d in bdir.iterdir()
                  if d.is_dir() and not d.is_symlink() and (d / "MANIFEST.json").is_file())


def rollback(root, stamp, force=False):
    """Restore the files of one upgrade backup. Refuses while data migrations
    applied after the upgrade are still recorded (roll them back first);
    declares success only when every restored file is verified."""
    root = Path(root)
    if not core.is_safe_id(stamp):
        return {"ok": False, "error": "invalid backup stamp"}
    if not core.runtime_tree_is_real(root, BACKUP_REL.parts):
        return {"ok": False, "error": "backup location is a symlink or escapes the installation — refused"}
    bdir = confined(root, str(BACKUP_REL / stamp))
    if bdir is None or not bdir.is_dir():
        return {"ok": False, "error": "backup %s not found or unsafe" % stamp}
    if (bdir / "MANIFEST.json").is_symlink():
        return {"ok": False, "error": "backup %s: MANIFEST.json is a symbolic link — refused" % stamp}
    manifest, err = core.read_json(bdir / "MANIFEST.json")
    if err or not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return {"ok": False, "error": "backup %s: %s" % (stamp, err or "manifest invalid")}
    if manifest.get("state") not in ("applied", "applying", "failed-restore-incomplete"):
        return {"ok": False, "error": "backup %s was never applied (state %r) — nothing to roll back"
                % (stamp, manifest.get("state"))}
    mine = core.backup_order_key(stamp, manifest)
    newer = [s for s, state, key in _backup_states(root) if s != stamp and key > mine and state in ("applied", "applying")]
    if newer and not force:
        return {"ok": False, "error": "newer upgrade backup(s) still applied (%s) — roll them back first, newest "
                                      "first, or --force" % ", ".join(newer)}
    at_apply = manifest.get("migrations_at_apply")
    if not isinstance(at_apply, list):
        # audit F-05: a backup that does not record the migrations at apply
        # time cannot exclude a later data migration — never read as "none"
        if _migration_records(root) and not force:
            return {"ok": False, "error": "this backup does not record the data migrations present when it "
                                          "was applied: a later migration cannot be excluded — check "
                                          "`migrate --plan` and roll data migrations back first, or --force"}
    else:
        known = {(m.get("id"), m.get("on"), m.get("backup")) for m in at_apply if isinstance(m, dict)}
        later = [m for m in _migration_records(root)
                 if (m["id"], m["on"], m["backup"]) not in known]
        if later and not force:
            return {"ok": False, "error": "data migrations applied after this upgrade are still recorded "
                                          "(%s) — run `migrate --rollback <their stamp>` first, or --force"
                                          % ", ".join(str(m["id"]) for m in later)}
    try:
        with _lock(root):
            # whole restoration validated under the lock before any write;
            # one invalid entry → refused, nothing changed
            res = restore.restore(root, bdir, manifest)
            if res["ok"]:
                manifest["state"] = "rolled-back"
                manifest["rolled_back_at"] = _stamp()
                core.atomic_write_json(bdir / "MANIFEST.json", manifest)
    except TimeoutError:
        return {"ok": False, "error": "another mutating operation is in progress on this installation — retry later"}
    return restore.result(res, bdir)
