# SPDX-License-Identifier: Apache-2.0
"""Idempotent migrations of an installation to the current workspace version.

Each step declares when it applies (from the real state, never from a
version number alone), what it changes, and is recorded in
`pws.config.json.migrations` once applied. `plan` is read-only; `apply`
backs up every file it is about to change under
`.claude/runtime/migration-backup/<stamp>/` (with a manifest) before
writing; `rollback <stamp>` restores those files byte for byte through the
shared two-stage mechanism of `restore.py` (corrected 2026-11-06 after the
second verification): the whole restoration is validated under the mutation
lock before any write — one invalid entry refuses it entirely, nothing
changed — then every copy is verified again after writing. `apply` never
restores automatically: it stops at the first failing step and keeps the
backup for an explicit `rollback`.

What a migration never does: overwrite a product's DECISIONS, validation
state, research, PRODUCT.md, the user's approvals or any Claude Code setting
other than the legacy TV-mode key it moves (spec section 55).

Reliability of the reports (corrected 2026-11-13, audit F-06, F-07, F-08,
F-10, F-13, H-05): an unreadable configuration is an error (never an empty
success); a step that cannot complete is BLOCKED at plan time (m005 with a
non-convertible manifest) instead of half-writing; the migration journal
(pws.config.json) is part of every backup, so a rollback also removes the
journal entries; no empty backup is created; a step that waits for another one
(`waits_for`) is applied in the same run once its prerequisite is applied; the
report lists what remains; a rollback respects the order of the backups and
marks the restored backup `rolled-back`. Steps are state-based (m004 recurs at
each new version): the journal records what was applied, it never decides
alone whether a step is due.
"""
import datetime
import json
import shutil
import tempfile
from pathlib import Path

from . import config, core, profiles, restore, version

BACKUP_REL = core.RUNTIME_REL / "migration-backup"
MUTATION_LOCK_REL = core.RUNTIME_REL / "pws-mutation.lock"   # shared with `upgrade`


def _manifests(root):
    """[(slug, path, data_or_None, error)] for every scripts/<slug>/SCRIPT.json."""
    out = []
    scripts = Path(root) / "scripts"
    if scripts.is_symlink() or not scripts.is_dir():
        return out
    for d in sorted(p for p in scripts.iterdir() if p.is_dir() and not p.is_symlink()):
        mp = d / "SCRIPT.json"
        if mp.is_symlink() or not mp.is_file():
            continue
        data, err = core.read_json(mp)
        out.append((d.name, mp, data, err))
    return out


def _legacy_key_present(root):
    if (Path(root) / core.LOCAL_SETTINGS_REL).is_symlink():
        return False, None   # audit F-12: content outside the workspace is never read
    data, err = core.read_json(Path(root) / core.LOCAL_SETTINGS_REL)
    if err or not isinstance(data, dict):
        return False, None
    env = data.get("env")
    if isinstance(env, dict) and core.TV_MODE_ENV_KEY in env:
        return True, env.get(core.TV_MODE_ENV_KEY)
    return False, None


def _recorded(cfg):
    migs = cfg["data"].get("migrations")
    return {m.get("id") for m in (migs if isinstance(migs, list) else []) if isinstance(m, dict)}


# ---- step definitions ------------------------------------------------------

def _step_tv_mode(root, cfg):
    present, value = _legacy_key_present(root)
    if not present or "m001-tv-mode-to-config" in _recorded(cfg):
        return None
    if value not in core.MODES:
        return {"id": "m001-tv-mode-to-config", "blocked": True,
                "detail": "legacy env.%s is %r (invalid) — fix it manually first"
                          % (core.TV_MODE_ENV_KEY, value), "changes": []}
    # F-14 (owner's decision of 2026-11-13): never a silent change of the mode
    # in effect, never a removal of the legacy value before the conflict is resolved
    raw = cfg["raw"] if isinstance(cfg["raw"], dict) else {}
    current = raw.get("tv_validation_mode")
    choice = raw.get(config.MODE_CHOICE_KEY)
    explicit = isinstance(choice, dict) and choice.get("by") == "owner"
    legacy_origin = ".claude/settings.local.json (env.%s)" % core.TV_MODE_ENV_KEY
    values = {"config": {"value": current, "origin": "pws.config.json" + (
                  " — explicit choice of the owner (%s, %s)" % (choice.get("command"), choice.get("at"))
                  if explicit else " — origin not established (it may be the default written by init)")},
              "legacy": {"value": value, "origin": legacy_origin}}
    if current not in core.MODES:
        return {"id": "m001-tv-mode-to-config", "blocked": False, "values": values,
                "detail": "pws.config.json has no usable mode (%s): the legacy mode %r from %s is copied "
                          "into pws.config.json" % ("absent" if current is None else "invalid %r" % current,
                                                    value, legacy_origin),
                "changes": [str(config.CONFIG_REL)], "value": value}
    if current == value:
        return {"id": "m001-tv-mode-to-config", "blocked": False, "values": values,
                "detail": "pws.config.json and %s agree on %r: nothing to choose, the legacy key is then "
                          "retired (m003)" % (legacy_origin, value),
                "changes": [str(config.CONFIG_REL)], "value": current}
    if explicit:
        return {"id": "m001-tv-mode-to-config", "blocked": False, "values": values,
                "detail": "the owner chose %r explicitly (%s, %s): it is kept; the legacy value %r is then "
                          "retired (m003, kept in the migration backup)"
                          % (current, choice.get("command"), choice.get("at"), value),
                "changes": [str(config.CONFIG_REL)], "value": current}
    return {"id": "m001-tv-mode-to-config", "blocked": True, "values": values,
            "detail": "conflict: pws.config.json holds %r (the mode in effect; origin not established, it "
                      "may be the default written by init) and %s holds the legacy %r. Nothing changes and "
                      "the legacy value is kept until the owner chooses: `tv-mode %s` keeps the mode in "
                      "effect, `tv-mode %s` adopts the legacy one" % (current, legacy_origin, value,
                                                                    current, value),
            "changes": []}


def _step_manifests(root, cfg):
    """Schema 1 and schema 2 manifests → current schema (3): licence axes
    kept, publication split into state/privacy/mode, unknown parts null."""
    legacy = []
    for slug, path, data, err in _manifests(root):
        if err or not isinstance(data, dict):
            continue
        if data.get("schema_version") in (version.MANIFEST_SCHEMA_LEGACY, version.MANIFEST_SCHEMA_V2):
            new, notes, ambiguities = profiles.migrate_manifest_to_v3(data)
            legacy.append({"slug": slug, "path": str(path.relative_to(root)),
                           "from_schema": data.get("schema_version"),
                           "convertible": new is not None, "notes": notes,
                           "ambiguities": ambiguities})
    if not legacy:
        return None
    unconvertible = [m["path"] for m in legacy if not m["convertible"]]
    if unconvertible:
        return {"id": "m005-manifests-v3", "blocked": True,
                "detail": "manifest(s) not convertible to schema 3: %s — fix them first; nothing is rewritten "
                          "until every legacy manifest converts" % ", ".join(unconvertible),
                "changes": [], "manifests": legacy}
    return {"id": "m005-manifests-v3", "blocked": False,
            "detail": "rewrite %d legacy SCRIPT.json (schema 1/2 → 3): licence axes kept, "
                      "publication split into state / privacy / mode with unknown parts "
                      "left null; ambiguities are reported, never guessed" % len(legacy),
            "changes": [m["path"] for m in legacy], "manifests": legacy}


def _step_remove_legacy_key(root, cfg):
    present, _ = _legacy_key_present(root)
    if not present:
        return None
    raw = cfg["raw"] or {}
    present, value = _legacy_key_present(root)
    if value not in core.MODES:
        return {"id": "m003-remove-legacy-tv-key", "blocked": True,
                "detail": "legacy env.%s is %r (invalid): nothing is removed until it is "
                          "fixed or confirmed manually" % (core.TV_MODE_ENV_KEY, value),
                "changes": []}
    if "m001-tv-mode-to-config" not in _recorded(cfg):
        # F-14: the legacy value is never removed before m001 has settled the mode
        return {"id": "m003-remove-legacy-tv-key", "blocked": True, "waits_for": "m001-tv-mode-to-config",
                "detail": "waits for m001 (the mode must be settled in pws.config.json first; applied in the "
                          "same run once m001 is applied, never while m001 is blocked)",
                "changes": [str(core.LOCAL_SETTINGS_REL)]}
    return {"id": "m003-remove-legacy-tv-key", "blocked": False,
            "detail": "remove env.%s from .claude/settings.local.json (every other key, "
                      "approvals included, is preserved)" % core.TV_MODE_ENV_KEY,
            "changes": [str(core.LOCAL_SETTINGS_REL)]}


def _step_workspace_version(root, cfg):
    if cfg["data"].get("workspace_version") == version.WORKSPACE_VERSION:
        return None
    return {"id": "m004-record-workspace-version", "blocked": False,
            "detail": "record workspace_version %s in pws.config.json (was %r)"
                      % (version.WORKSPACE_VERSION, cfg["data"].get("workspace_version")),
            "changes": [str(config.CONFIG_REL)]}


def _step_publication_rectification(root, cfg):
    """Manifests already migrated to schema 3 by the 2026-11-06 code whose
    publication privacy (and, for a v1→v2→v3 chain, mode) was DEDUCED from
    defaults instead of recorded: deduced values go back to null, traced in
    `migration.rectifications`; holder-confirmed values are preserved."""
    todo = []
    for slug, path, data, err in _manifests(root):
        if err or not isinstance(data, dict) or data.get("schema_version") != version.MANIFEST_SCHEMA_VERSION:
            continue
        new, changes = profiles.rectify_publication_derivations(data)
        if changes:
            todo.append({"slug": slug, "path": str(path.relative_to(root)), "changes": changes})
    if not todo:
        return None
    return {"id": "m006-publication-derivations", "blocked": False,
            "detail": "reset %d deduced publication value(s) to null (traced rectification; "
                      "holder-confirmed values kept)" % sum(len(t["changes"]) for t in todo),
            "changes": [t["path"] for t in todo], "manifests": todo}


STEPS = (_step_tv_mode, _step_manifests, _step_remove_legacy_key, _step_workspace_version,
         _step_publication_rectification)
# Identifiers of the steps known by THIS version of the core, in STEPS order.
# Recorded in the distribution marker and in RELEASE.json so that an
# installation can announce, BEFORE upgrading, which steps may apply (those
# not yet recorded there). `migrate --plan`, run by the new code after the
# upgrade, remains the only authority on what actually applies.
STEP_IDS = ("m001-tv-mode-to-config", "m005-manifests-v3", "m003-remove-legacy-tv-key",
            "m004-record-workspace-version", "m006-publication-derivations")


def pending_steps(root):
    cfg = config.read_config(root)
    if cfg["error"]:
        return []
    steps = []
    for fn in STEPS:
        step = fn(root, cfg)
        if step:
            steps.append(step)
    return steps


def plan(root):
    cfg = config.read_config(root)
    return {"config_present": cfg["present"], "config_error": cfg["error"],
            "workspace_version": version.WORKSPACE_VERSION,
            "installed_version": cfg["data"].get("workspace_version"),
            "steps": pending_steps(root)}


# ---- apply / rollback -----------------------------------------------------

def _stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup(root, rel_paths):
    """Exclusively created, unique backup folder (timestamp + random suffix:
    never reused, even within the same second); every copy verified."""
    backup_root = Path(root) / BACKUP_REL
    backup_root.mkdir(parents=True, exist_ok=True)
    bdir = Path(tempfile.mkdtemp(prefix="%s-" % _stamp(), dir=str(backup_root)))
    manifest = {"stamp": bdir.name, "files": [], "state": "backup", "created_at": core.precise_now()}
    for rel in rel_paths:
        src = Path(root) / rel
        entry = {"path": rel, "existed": src.is_file()}
        if src.is_file():
            dst = bdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            entry["sha256"] = core.sha256_file(src)
            if core.sha256_file(dst) != entry["sha256"]:
                raise OSError("backup copy of %s could not be verified" % rel)
        manifest["files"].append(entry)
    core.atomic_write_json(bdir / "MANIFEST.json", manifest)
    return bdir


def _record(root, step_id, stamp, note=None):
    def mutate(data):
        data.setdefault("migrations", []).append(
            {"id": step_id, "on": _stamp(), "backup": stamp, "note": note})
        return None
    return config.update_config(root, mutate)


def apply(root, today=None):
    """Apply every pending, non-blocked step in order, under the shared
    mutation lock (also taken by `upgrade`). Returns a report."""
    root = Path(root)
    report = {"applied": [], "skipped": [], "errors": [], "backup": None,
              "ambiguities": []}
    if not core.runtime_tree_is_real(root, BACKUP_REL.parts):
        report["errors"].append({"id": None, "error": "backup location %s is a symlink or escapes "
                                                      "the workspace — refused" % BACKUP_REL})
        return report
    try:
        with core.file_lock(root / MUTATION_LOCK_REL, timeout=0.5):
            return _apply_locked(root, today, report)
    except TimeoutError:
        report["errors"].append({"id": None, "error": "another mutating operation (upgrade or "
                                                      "migration) is in progress — retry later"})
        return report


def _apply_locked(root, today, report):
    cfg = config.read_config(root)
    if cfg["error"]:
        report["errors"].append({"id": None, "error": "pws.config.json unreadable — no migration evaluated, "
                                                      "nothing changed: %s" % cfg["error"]})
        return report
    steps = pending_steps(root)
    report["remaining"] = []
    if not steps:
        return report
    ids_runnable = {s["id"] for s in steps if not s["blocked"]}
    # a step waiting for another one counts only when that one can run (F-13/F-14:
    # no backup is created when nothing can be applied)
    runnable = [s for s in steps if not s["blocked"] or s.get("waits_for") in ids_runnable]
    if not runnable:                               # everything blocked: no backup, nothing changed
        report["skipped"] = [{"id": s["id"], "reason": s["detail"]} for s in steps]
        report["remaining"] = [s["id"] for s in steps]
        return report
    changes = []
    for s in runnable:
        changes.extend(s["changes"])
    changes.append(str(config.CONFIG_REL))         # the journal is written: always part of the backup
    seen, ordered = set(), []
    for c in changes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    try:
        bdir = _backup(root, ordered)
    except OSError as exc:
        report["errors"].append({"id": None, "error": "backup failed — nothing changed: %s" % exc})
        return report
    stamp = bdir.name
    report["backup"] = str(bdir)
    attempted = set()
    while True:
        # re-evaluated after each step: a step waiting for another one becomes due in the same run
        current = pending_steps(root)
        step = next((s for s in current if s["id"] not in attempted and not s["blocked"]), None)
        if step is None:
            break
        attempted.add(step["id"])
        if not set(step["changes"]) <= seen:
            report["errors"].append({"id": step["id"], "error": "step changes files that are not in the backup "
                                                                "(%s) — not applied" % ", ".join(step["changes"])})
            break
        try:
            ok, note = _apply_step(root, step, today)
        except Exception as exc:  # noqa: BLE001 — report, never half-apply silently
            ok, note = False, "unexpected error: %s" % exc
        if ok:
            rec = _record(root, step["id"], stamp, note)
            if not rec["ok"]:
                report["errors"].append({"id": step["id"], "error": rec["error"]})
            else:
                report["applied"].append({"id": step["id"], "note": note})
            if step["id"] == "m005-manifests-v3":
                for m in step.get("manifests", []):
                    for a in m["ambiguities"]:
                        report["ambiguities"].append("%s: %s" % (m["slug"], a))
            if step["id"] == "m006-publication-derivations":
                for m in step.get("manifests", []):
                    for c in m["changes"]:
                        report["ambiguities"].append("%s: %s" % (m["slug"], c))
        else:
            report["errors"].append({"id": step["id"], "error": note})
            break  # later steps may depend on this one: stop, backup stays
    after = pending_steps(root)
    report["skipped"] = [{"id": s["id"], "reason": s["detail"]} for s in after if s["blocked"]]
    report["remaining"] = [s["id"] for s in after]
    manifest, _ = core.read_json(bdir / "MANIFEST.json")
    if isinstance(manifest, dict):
        manifest["state"] = "applied" if report["applied"] else ("failed" if report["errors"] else "unused")
        manifest["applied_steps"] = [a["id"] for a in report["applied"]]
        core.atomic_write_json(bdir / "MANIFEST.json", manifest)
    return report


def _apply_step(root, step, today):
    sid = step["id"]
    if sid == "m001-tv-mode-to-config":
        value = step["value"]
        current = (config.read_config(root)["raw"] or {}).get("tv_validation_mode")
        if current == value:
            return True, "tv_validation_mode=%s kept (no write)" % value

        def mutate(data):
            data["tv_validation_mode"] = value
            return None
        r = config.update_config(root, mutate)
        return r["ok"], (r["error"] or "tv_validation_mode=%s" % value)
    if sid == "m005-manifests-v3":
        # every manifest is converted in memory first: nothing is written unless all convert
        converted = []
        for m in step["manifests"]:
            path = root / m["path"]
            data, err = core.read_json(path)
            if err or not isinstance(data, dict):
                return False, "%s: %s — nothing written" % (m["path"], err or "not an object")
            new, _, _ = profiles.migrate_manifest_to_v3(data, today=today)
            if new is None:
                return False, "%s: not convertible — nothing written" % m["path"]
            converted.append((path, new, m["slug"]))
        for path, new, _slug in converted:
            core.atomic_write_json(path, new)
        return True, "manifests migrated: %s" % ", ".join(slug for _p, _n, slug in converted)
    if sid == "m003-remove-legacy-tv-key":
        path = root / core.LOCAL_SETTINGS_REL
        if path.is_symlink():
            return False, "settings.local.json is a symbolic link — not modified"
        try:
            with core.file_lock(str(path) + ".lock"):
                before = path.read_bytes()
                data = json.loads(before.decode("utf-8"))
                if not isinstance(data, dict):
                    return False, "settings.local.json is not an object"
                env = data.get("env")
                if isinstance(env, dict):
                    env.pop(core.TV_MODE_ENV_KEY, None)
                    if not env:
                        data.pop("env", None)
                if path.read_bytes() != before:
                    return False, "concurrent modification of settings.local.json — retry"
                core.atomic_write_json(path, data)
        except (OSError, ValueError, TimeoutError) as exc:
            return False, "settings.local.json: %s" % exc
        return True, "legacy key removed"
    if sid == "m004-record-workspace-version":
        def mutate(data):
            data["workspace_version"] = version.WORKSPACE_VERSION
            return None
        r = config.update_config(root, mutate)
        return r["ok"], (r["error"] or "workspace_version=%s" % version.WORKSPACE_VERSION)
    if sid == "m006-publication-derivations":
        done = []
        for m in step["manifests"]:
            path = root / m["path"]
            data, err = core.read_json(path)
            if err or not isinstance(data, dict):
                return False, "%s: %s" % (m["path"], err or "not an object")
            new, changes = profiles.rectify_publication_derivations(data, today=today)
            if not changes:
                continue
            core.atomic_write_json(path, new)
            done.append("%s (%d value(s))" % (m["slug"], len(changes)))
        return True, "publication derivations rectified: %s" % ", ".join(done)
    return False, "unknown step %s" % sid


def list_backups(root):
    bdir = Path(root) / BACKUP_REL
    if not bdir.is_dir():
        return []
    return sorted(d.name for d in bdir.iterdir() if d.is_dir() and (d / "MANIFEST.json").is_file())


def rollback(root, stamp, force=False):
    """Restore the files of one backup byte for byte (files that did not
    exist before the migration are removed) under the shared mutation lock;
    success is declared only when every restored file matches its recorded
    hash. The backup itself is kept."""
    root = Path(root)
    if not core.is_safe_id(stamp):
        return {"ok": False, "error": "invalid backup stamp"}
    if not core.runtime_tree_is_real(root, BACKUP_REL.parts):
        return {"ok": False, "error": "backup location is a symlink or escapes the workspace — refused"}
    bdir = restore.confined(root, str(BACKUP_REL / stamp))
    if bdir is None or not bdir.is_dir():
        return {"ok": False, "error": "backup %s not found or unsafe" % stamp}
    if (bdir / "MANIFEST.json").is_symlink():
        return {"ok": False, "error": "backup %s: MANIFEST.json is a symbolic link — refused" % stamp}
    manifest, err = core.read_json(bdir / "MANIFEST.json")
    if err or not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return {"ok": False, "error": "backup %s: %s" % (stamp, err or "manifest invalid")}
    newer = []
    mine = core.backup_order_key(stamp, manifest)
    for other in list_backups(root):
        if other == stamp:
            continue
        m, e = core.read_json(Path(root) / BACKUP_REL / other / "MANIFEST.json")
        if not e and isinstance(m, dict) and m.get("state") == "applied" and core.backup_order_key(other, m) > mine:
            newer.append(other)
    if newer and not force:
        return {"ok": False, "error": "newer migration backup(s) still applied (%s) — roll them back first, "
                                      "newest first" % ", ".join(newer)}
    try:
        with core.file_lock(root / MUTATION_LOCK_REL, timeout=0.5):
            # whole restoration validated under the lock before any write;
            # one invalid entry → refused, nothing changed
            res = restore.restore(root, bdir, manifest)
            if res["ok"]:
                manifest["state"] = "rolled-back"
                core.atomic_write_json(bdir / "MANIFEST.json", manifest)
    except TimeoutError:
        return {"ok": False, "error": "another mutating operation is in progress — retry later"}
    return restore.result(res, bdir)
