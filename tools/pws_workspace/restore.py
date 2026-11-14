# SPDX-License-Identifier: Apache-2.0
"""Verified restoration of a backup into an installation — ONE mechanism
shared by `upgrade --rollback`, the automatic restoration after a failed
`upgrade --apply`, and `migrate --rollback`.

Order of operations (corrected 2026-11-06 after the second independent
verification: a backup copy used to be written over the installed file
BEFORE its hash was verified, so a refused restoration had already damaged
the installation, and the entries preceding the invalid one had already been
restored or removed):

  1. check   — under the caller's mutation lock, the WHOLE restoration is
               validated before any write or removal in the installation:
               manifest structure, every path and its physical confinement
               (installation side and backup side), every destination, the
               presence and the SHA-256 of every needed copy, duplicates.
               One invalid entry refuses the whole restoration: nothing has
               been replaced, created or removed.
  2. perform — only after that global validation: files are copied and each
               copy is verified again after writing; added files are removed
               and their absence verified. Success is declared only when the
               restored state matches the manifest. An error met during this
               stage (despite a successful validation) is reported as an
               incomplete restoration with the list of discrepancies; the
               backup is never modified or removed here, so the recovery
               elements stay available for a new attempt.

  Between the two (audit F-09, 2026-11-13), the current version of every
  file the restoration replaces with a different content or removes is
  copied, verified, to `<backup>.replaced-<date>/` beside the backup
  (`PRESERVED.json` lists them): a late rollback never loses a modification
  made after the backup. If that copy cannot be made, nothing is written.

The caller owns the lock, the backup folder lookup and the policy checks
(backup state, ordering with data migrations); this module owns the
confinement rule and the two-stage restoration only.
"""
import re
import shutil
from pathlib import Path

from . import core

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def confined(base, rel):
    """Physical path base/rel, or None when rel is absolute, traverses, has a
    symlink on its chain or resolves outside base. Shared confinement rule
    for packages, installations and backups."""
    base = Path(base)
    if not isinstance(rel, str) or not rel:
        return None
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or any(part in ("", ".") for part in p.parts):
        return None
    probe = base
    for part in p.parts:
        probe = probe / part
        if probe.is_symlink():
            return None
        if probe.exists() and not core.is_within(base, probe):
            return None
    return probe


def check(root, bdir, manifest):
    """Validate the whole restoration WITHOUT touching the installation.
    Returns (actions, problems); the restoration may proceed only when
    `problems` is empty."""
    root, bdir = Path(root), Path(bdir)
    actions, problems, seen = [], [], set()
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list):
        return [], ["backup manifest invalid (no file list)"]
    for entry in files:
        if not isinstance(entry, dict):
            problems.append("%r: invalid manifest entry" % (entry,))
            continue
        rel = entry.get("path")
        target = confined(root, rel) if isinstance(rel, str) else None
        if target is None:
            problems.append("%r: unsafe path" % (rel,))
            continue
        if rel in seen:
            problems.append("%s: duplicate entry" % rel)
            continue
        seen.add(rel)
        probe, bad_parent = root, None
        for part in Path(rel).parts[:-1]:   # destination chain: real directories or absent
            probe = probe / part
            if probe.exists() and not probe.is_dir():
                bad_parent = part
                break
        if bad_parent is not None:
            problems.append("%s: destination parent %r is not a directory" % (rel, bad_parent))
            continue
        if not isinstance(entry.get("existed"), bool):     # audit F-05: never read as "added, remove it"
            problems.append("%s: manifest entry without a boolean `existed`" % rel)
            continue
        action = {"path": rel, "target": target, "existed": entry["existed"]}
        if action["existed"]:
            src = confined(bdir, rel)
            if src is None or not src.is_file():
                problems.append("%s: backup copy missing" % rel)
                continue
            recorded = entry.get("sha256")
            if not isinstance(recorded, str) or not SHA256_RE.match(recorded):
                problems.append("%s: no recorded hash for the backup copy" % rel)
                continue
            if core.sha256_file(src) != recorded:
                problems.append("%s: backup copy does not match the recorded hash" % rel)
                continue
            if target.exists() and not target.is_file():
                problems.append("%s: destination is not a regular file" % rel)
                continue
            action["src"], action["sha256"] = src, recorded
        elif target.is_dir():
            problems.append("%s: added path is a directory, not a file" % rel)
            continue
        actions.append(action)
    return actions, problems


def perform(actions):
    """Execute validated actions and verify each one after the fact.
    Returns (restored, removed, problems)."""
    restored, removed, problems = [], [], []
    for a in actions:
        rel, target = a["path"], a["target"]
        try:
            if a["existed"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(a["src"]), str(target))
                if core.sha256_file(target) != a["sha256"]:
                    problems.append("%s: restored file does not match the recorded hash" % rel)
                else:
                    restored.append(rel)
            else:
                if target.exists() or target.is_symlink():
                    target.unlink()
                    removed.append(rel)
                if target.exists() or target.is_symlink():
                    problems.append("%s: added file still present" % rel)
        except OSError as exc:
            problems.append("%s: %s" % (rel, exc))
    return restored, removed, problems


def preserve(bdir, actions):
    """Copy the current version of every file that the restoration replaces
    with a different content or removes. Returns (folder or None, problems);
    a problem means nothing may be written."""
    bdir = Path(bdir)
    todo = []
    for a in actions:
        target = a["target"]
        if target.is_symlink() or not target.is_file():
            continue
        if a["existed"] and core.sha256_file(target) == a["sha256"]:
            continue                     # identical content: nothing would be lost
        todo.append(a)
    if not todo:
        return None, []
    stamp = core.precise_now().replace(":", "").replace("-", "")
    dest = bdir.parent / ("%s.replaced-%s" % (bdir.name, stamp))
    entries = []
    try:
        dest.mkdir(exist_ok=False)
        for a in todo:
            out = dest / a["path"]
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(a["target"]), str(out))
            sha = core.sha256_file(out)
            if sha != core.sha256_file(a["target"]):
                return None, ["%s: the copy of its current version does not verify" % a["path"]]
            entries.append({"path": a["path"], "sha256": sha,
                            "action": "replaced" if a["existed"] else "removed"})
        core.atomic_write_json(dest / "PRESERVED.json", {
            "from_backup": bdir.name, "created_at": core.precise_now(), "files": entries,
            "note": "versions replaced or removed by a rollback — restore by hand if needed"})
    except OSError as exc:
        return None, ["current versions could not be preserved (%s) — nothing was written" % exc]
    return dest, []


def restore(root, bdir, manifest):
    """Two-stage restoration (the caller holds the mutation lock).

    Result: `ok`, `stage` ('refused' — nothing was written; 'incomplete' —
    validated, then an error during execution, discrepancies listed;
    'verified' — restored state matches the manifest), `problems`,
    `restored`, `removed`, `checked`, `preserved` (folder holding the
    versions replaced or removed, or None)."""
    actions, problems = check(root, bdir, manifest)
    if not problems:
        preserved, problems = preserve(bdir, actions)
    if problems:
        return {"ok": False, "stage": "refused", "problems": problems,
                "restored": [], "removed": [], "checked": len(actions), "preserved": None}
    restored, removed, problems = perform(actions)
    return {"ok": not problems, "stage": "verified" if not problems else "incomplete",
            "problems": problems, "restored": restored, "removed": removed, "checked": len(actions),
            "preserved": str(preserved) if preserved else None}


def result(res, bdir):
    """Uniform rollback result (CLI / report shape) built from `restore`'s
    outcome; the error text states whether anything was written."""
    out = {"ok": res["ok"], "stage": res["stage"], "restored": res["restored"],
           "removed": res["removed"], "backup": str(bdir), "problems": res["problems"],
           "preserved": res.get("preserved")}
    if res["stage"] == "refused":
        out["error"] = "rollback refused before any write — nothing changed: %s" % "; ".join(res["problems"][:5])
    elif res["problems"]:
        out["error"] = "rollback incomplete — state NOT verified: %s" % "; ".join(res["problems"][:5])
    return out
