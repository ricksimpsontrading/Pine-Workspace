# SPDX-License-Identifier: Apache-2.0
"""Session state: session-status aggregate, SessionStart/Stop hooks.

This module only AGGREGATES facts from scan/standard/validation/tv_mode —
it never re-derives them (single-implementation contract, FILE_CONTRACTS.md).

Snapshot lifecycle (spec section 40.6): one baseline per session_id, created
once, never silently overwritten. On resume/compact/clear the previous
logical baseline is carried over through the latest.json pointer so the Stop
hook keeps comparing against what existed when the logical session began.
Subagent sessions (agent_id present) never touch the main baseline.
Several Claude Code sessions may share one workspace (corrections of
2026-11-13, audit D-05): a session resumed or compacted under a NEW
identifier carries the baseline named by latest.json only when no other
session has been active since that session began; otherwise its lineage is
not established, it takes a fresh baseline and the findings present at the
resume are reported as such, never as plainly pre-existing. A forked session
(source "fork") always takes a fresh baseline with an unestablished lineage:
Claude Code gives a hook no field naming the session it comes from. The Stop hook
refreshes the modification time of its snapshot at every end of turn (its
last use, read by the startup cleanup).

Stop hook (spec section 41): respects stop_hook_active, blocks ONLY on
mechanical BLOCKING guard findings INTRODUCED during the session, attributed
finding by finding against the guard record kept in the baseline (introduced
/ pre-existing / made visible by the context / indeterminate). A file is
attached to the baseline by path, else by identical content, else by a
rename reported by Git (technical correspondence, unambiguous only); a
shared name or product is never a provenance. Degrades to silence when no
baseline exists. Non-blocking information goes to the next SessionStart
summary (exit-0 stdout of a Stop hook is not injected into context —
documented limitation).

Import record (spec sections 41.2 / 52.5): onboarding DECLARES a source
imported during the session before touching it. The record keeps the path,
the SHA-256 and the guard state at import time. It is declarative — it
distinguishes an import from a creation, it never proves where the file
came from. A record is never renewed: once the content has changed, the
import cannot be registered again. A record attaches to ONE file only; an
equal fingerprint alone exempts no other file from any check. Records are
dated: one serves the sessions that began before it was registered, and the
start of another session never erases it; a record no present session can
use any more is pruned.

Stop information and failures: each session writes only its own
information file (stop-info/<session>.json); the next session start shows
every pending one once, labelled with its session when it is another one.
An internal failure of the Stop hook never blocks nor crashes the session,
but it is recorded (hook-errors.json) and announced at the next start.
"""
import datetime
import json
import os
import sys
import traceback
from pathlib import Path

from . import config, core, guard, i18n, profiles, scan, standard, tv_mode, version

SESSION_DIR_REL = core.RUNTIME_REL / "session"
MAX_LIST = 10
STDOUT_BUDGET = 6000  # hard cap well under the 10k SessionStart context cap
STOP_INFO_DIR = "stop-info"
HOOK_ERRORS = "hook-errors.json"
MAX_HOOK_ERRORS = 20
# files of the session folder that are never snapshots
SIDE_FILES = {"latest.json", "stop-info.json", "imports.json", HOOK_ERRORS}
# checks whose finding may concern a licence notice, an attribution or a
# legal reference: the block message never invites removing such a mention
LICENCE_SENSITIVE_CHECKS = {"no-promo-urls", "header-copyright", "header-structure"}


def _compact_license(lic):
    if not isinstance(lic, dict):
        return None
    return {k: lic.get(k) for k in ("id", "grant", "source_visibility", "access",
                                     "terms_ref", "terms_url", "derived_from_v1", "origin", "status")
            if k in lic}


def session_status(root):
    """Structured mechanical state for the /pws menu and diagnostics."""
    root = Path(root)
    s = scan.scan_workspace(root)
    std = standard.standard_status(root)
    mode_detail = tv_mode.read_mode_detail(root)
    git = core.git_state(root)
    cfg = config.read_config(root)
    lang = i18n.normalize_language(cfg["data"].get("language"))
    products = s["products"]
    stale = [p["slug"] for p in products if p.get("validation_effective_status") == "stale"]
    broken_validation = [p["slug"] for p in products
                         if p.get("validation_integrity_status") == "BROKEN"]
    from . import migration  # local import: migration aggregates this module's peers
    pending = migration.pending_steps(root)
    ident = config.identity(root)
    maint = cfg["data"].get("maintenance")
    maint = maint if isinstance(maint, dict) else {}
    gh = cfg["data"].get("github")
    gh_dests = (gh.get("destinations") if isinstance(gh, dict) else None) or []
    return {
        "language": lang,
        "workspace_version": version.WORKSPACE_VERSION,
        "config": {
            "present": cfg["present"],
            "error": cfg["error"],
            "problems": cfg["problems"],
            "workspace_version": cfg["data"].get("workspace_version"),
            "identity_configured": ident["configured"],
            "copyright_holder": ident["copyright_holder"],
            "header_aliases": ident["header_aliases"],
            "default_profile": ident["default_profile"],
            "startup_cleanup": bool(maint.get("startup_cleanup", True)),
            "github_destinations": [{"name": d.get("name"), "repo": d.get("repo"),
                                     "visibility": d.get("visibility")}
                                    for d in gh_dests if isinstance(d, dict)],
            "pending_migrations": [m["id"] for m in pending],
        },
        "git": git,
        "tv_mode": mode_detail["mode"],
        "tv_mode_source": mode_detail["source"],
        "tv_mode_error": mode_detail["error"],
        "standard": std,
        "products": [{
            "slug": p["slug"],
            "product_structure_status": p["product_structure_status"],
            "script_kind": p.get("script_kind"),
            "distribution": p.get("distribution"),
            "schema_version": p.get("schema_version"),
            "profile": p.get("profile"),
            "profile_variant": (profiles.profile_variant(p.get("profile"), p.get("license"))
                                if p.get("profile") else None),
            "license": _compact_license(p.get("license")),
            "publication": p.get("publication"),
            "validation_status": p.get("validation_status"),
            "validation_integrity_status": p.get("validation_integrity_status"),
            "validation_effective_status": p.get("validation_effective_status"),
        } for p in products],
        "counts": {
            "products": len(products),
            "registered": sum(1 for p in products if p["product_structure_status"] == "REGISTERED"),
            "incomplete": sum(1 for p in products if p["product_structure_status"] == "INCOMPLETE"),
            "broken": sum(1 for p in products if p["product_structure_status"] == "BROKEN"),
            "ambiguous": sum(1 for p in products if p["product_structure_status"] == "AMBIGUOUS"),
            "unregistered_pine": len(s["unregistered_pine"]),
        },
        "unregistered_pine": s["unregistered_pine"],
        "stale_validations": stale,
        "broken_validations": broken_validation,
        "findings": s["findings"],
    }


def _snapshot_paths(root, session_id):
    """Paths of the session snapshot. An identifier that is not a safe file
    name never reaches the filesystem: it maps to a fixed inert name."""
    d = Path(root) / SESSION_DIR_REL
    if not core.is_safe_id(session_id):
        session_id = "unsafe-session-id"
    return d, d / ("%s.json" % session_id), d / "latest.json"


def _stem(session_id):
    return session_id if core.is_safe_id(session_id) else "unsafe-session-id"


def _stamp_epoch(stamp):
    """Epoch seconds of a core.precise_now() stamp, None when absent or
    malformed (snapshots and records written before 2026-11-13)."""
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return None


def _snapshots(root):
    """Every session snapshot present: [(session_id, path, data)], in the
    format written by hook_session_start (a mapping holding a `files`
    mapping, stored under the name its session_id maps to)."""
    sdir = Path(root) / SESSION_DIR_REL
    out = []
    if sdir.is_symlink() or not sdir.is_dir():
        return out
    try:
        names = sorted(os.listdir(str(sdir)))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json") or name in SIDE_FILES:
            continue
        path = sdir / name
        if path.is_symlink() or not path.is_file():
            continue
        data, err = core.read_json(path)
        if err or not isinstance(data, dict) or not isinstance(data.get("files"), dict):
            continue
        sid = data.get("session_id")
        if not isinstance(sid, str) or _snapshot_paths(root, sid)[1] != path:
            continue
        out.append((sid, path, data))
    return out


def _predecessor(root, session_id):
    """Baseline to carry for a session resumed or compacted under a NEW
    identifier. Returns (snapshot or None, pointer id when the lineage is
    not established). latest.json names the last session STARTED; when
    another session has been active since that one began, the pointer may
    name a session other than the resumed one: nothing is carried."""
    sdir = Path(root) / SESSION_DIR_REL
    latest, lerr = core.read_json(sdir / "latest.json")
    if lerr or not isinstance(latest, dict) or not isinstance(latest.get("session_id"), str):
        return None, None
    prev_id = latest["session_id"]
    prev_path = _snapshot_paths(root, prev_id)[1]
    prev, perr = core.read_json(prev_path)
    if perr or not isinstance(prev, dict) or not isinstance(prev.get("files"), dict):
        return None, None
    began = _stamp_epoch(prev.get("created_at"))
    if began is None:
        try:
            began = prev_path.stat().st_mtime  # snapshot without a start date
        except OSError:
            return None, prev_id
    for sid, path, _ in _snapshots(root):
        if sid in (prev_id, session_id):
            continue
        try:
            if path.stat().st_mtime > began:
                return None, prev_id
        except OSError:
            continue
    return prev, None


def _touch(path):
    """Record the last use of a snapshot (read by the startup cleanup)."""
    try:
        if not path.is_symlink() and path.is_file():
            os.utime(str(path), None)
    except OSError:
        pass


def _runtime_writable(root):
    """The ephemeral runtime tree must be a REAL in-workspace tree: a
    symlinked .claude/, runtime/ or session/ would route hook writes outside
    the workspace (targeted review 2026-09-06, spec 6.1.5). When violated the
    hooks silently degrade to snapshot-less operation (the Stop hook already
    never blocks without a baseline)."""
    return core.runtime_tree_is_real(root, SESSION_DIR_REL.parts)


def _registered_pine_hashes(root):
    """SHA-256 of every .pine under scripts/ — same physical walk as the
    scanner (no directory symlink followed, nothing outside the workspace;
    a symlinked scripts/ root yields nothing, as for the scanner)."""
    files = {}
    root = Path(root)
    scripts_dir = root / "scripts"
    if scripts_dir.is_symlink() or not scripts_dir.is_dir():
        return files
    for pine in sorted(p for p in core.iter_paths_within(scripts_dir) if p.suffix == ".pine"):
        if pine.is_symlink():
            continue
        try:
            files[str(pine.relative_to(root))] = core.sha256_file(pine)
        except OSError:
            continue
    return files


def _product_policy(product, identity):
    """Header policy of a scanned product (explicit v2 axes or derived v1)."""
    if not product or not product.get("profile"):
        return None
    return profiles.header_policy(product["profile"], product.get("license"), identity)


def hook_session_start(root, stdin_data):
    """SessionStart hook body. Returns the text to print on stdout."""
    root = Path(root)
    if not isinstance(stdin_data, dict):
        stdin_data = {}
    session_id = stdin_data.get("session_id") or "unknown-session"
    source = stdin_data.get("source") or "startup"
    is_subagent = bool(stdin_data.get("agent_id") or stdin_data.get("agent_type"))

    if not is_subagent and _runtime_writable(root):
        sdir, snap_path, latest_path = _snapshot_paths(root, session_id)
        sdir.mkdir(parents=True, exist_ok=True)
        if not snap_path.exists():
            carried, unproven = None, None
            if source in ("resume", "compact"):
                carried, unproven = _predecessor(root, session_id)
            elif source == "fork":
                # a session forked from another one (Claude Code: --fork-session,
                # /fork, /branch): no hook input field names the parent session
                # (hooks reference, read 2026-11-13) — its lineage is never inferred
                latest, _ = core.read_json(latest_path)
                unproven = (latest.get("session_id") if isinstance(latest, dict)
                            and isinstance(latest.get("session_id"), str) else "unknown")
            if carried is not None:
                # same logical session continues (spec 40.6)
                snapshot = dict(carried)
                snapshot["session_id"] = session_id
                snapshot["carried_from"] = carried.get("session_id")
            else:
                files = _registered_pine_hashes(root)
                snapshot = {
                    "session_id": session_id,
                    "created_at": core.precise_now(),  # dates the import records it serves
                    "source": source,
                    "files": files,
                    "guard": _baseline_guard(root, files),
                }
                if unproven:
                    snapshot["lineage"] = {"established": False, "pointer": unproven}
            core.atomic_write_json(snap_path, snapshot)
            core.atomic_write_json(latest_path, {"session_id": session_id})
            _prune_imports(root)
        else:
            # baseline exists for this session_id — never overwrite (spec 40.6)
            _touch(snap_path)

    cleanup_lines = []
    if not is_subagent:
        # Fast deterministic startup maintenance (whitelisted recreatable
        # temporaries only); reported only when it acted or hit an anomaly.
        from . import maintenance  # local import: keeps the hook path light
        cleanup_lines = maintenance.startup_cleanup(
            root, current_session_id=session_id).get("summary_lines", [])

    status = session_status(root)
    status["stop_info"] = _read_stop_info(root, consume=not is_subagent,
                                          session_id=session_id,
                                          lang=status.get("language"))
    status["hook_errors"] = _hook_errors(root, mark_reported=not is_subagent)
    status["cleanup_info"] = cleanup_lines
    return _format_summary(status), status


def _format_summary(status):
    lang = status.get("language") or i18n.DEFAULT_LANGUAGE
    lines = ["PWS", i18n.t("summary.language", lang)]
    g = status["git"]
    if g["is_repo"]:
        git_line = i18n.t("summary.git.local", lang,
                          branch=g["branch"] or "?",
                          state=i18n.t("summary.dirty" if g["dirty"] else "summary.clean", lang),
                          unborn=i18n.t("summary.unborn", lang) if g["unborn"] else "")
        if g["remotes"]:
            git_line += i18n.t("summary.remotes", lang, remotes=",".join(g["remotes"]))
    elif g.get("available"):
        git_line = i18n.t("summary.git.none", lang)
    else:
        git_line = i18n.t("summary.git.unavailable", lang)
    lines.append(git_line)
    if status["tv_mode"]:
        source = status.get("tv_mode_source")
        suffix = ""
        if source == "default":
            suffix = i18n.t("summary.tvmode.default", lang)
        elif source == "legacy":
            suffix = i18n.t("summary.tvmode.legacy", lang)
        lines.append(i18n.t("summary.tvmode", lang, mode=status["tv_mode"], source=suffix))
    else:
        lines.append(i18n.t("summary.tvmode.invalid", lang, error=status["tv_mode_error"]))
    c = status["counts"]
    lines.append(i18n.t("summary.products", lang, registered=c["registered"],
                        incomplete=c["incomplete"], broken=c["broken"],
                        ambiguous=c["ambiguous"]))
    lines.append(i18n.t("summary.unregistered", lang, n=c["unregistered_pine"]))
    lines.append(i18n.t("summary.stale", lang, n=len(status["stale_validations"])))
    lines.append(i18n.t("summary.standard", lang, index=status["standard"]["index"],
                        traceability=status["standard"]["traceability"]))
    cfg = status.get("config") or {}
    if not cfg.get("present"):
        lines.append(i18n.t("summary.config.missing", lang))
    if cfg.get("pending_migrations"):
        lines.append(i18n.t("summary.config.migrate", lang, n=len(cfg["pending_migrations"])))

    def _capped(title, items):
        if not items:
            return
        lines.append("")
        lines.append(title)
        for item in items[:MAX_LIST]:
            lines.append("  %s" % item)
        if len(items) > MAX_LIST:
            lines.append(i18n.t("summary.more", lang, n=len(items) - MAX_LIST))

    _capped(i18n.t("summary.list.unregistered", lang), status["unregistered_pine"])
    _capped(i18n.t("summary.list.stale", lang), status["stale_validations"])
    _capped(i18n.t("summary.list.broken", lang), status["broken_validations"])
    _capped(i18n.t("summary.list.stop", lang), status.get("stop_info") or [])
    _capped(i18n.t("summary.list.hookerrors", lang), status.get("hook_errors") or [])
    _capped(i18n.t("summary.list.cleanup", lang), status.get("cleanup_info") or [])
    text = "\n".join(lines)
    return text[:STDOUT_BUDGET]


def _git_renames(root):
    """Renames reported by `git status` under scripts/: {new_path: old_path}.

    This is a TECHNICAL CORRESPONDENCE computed by Git (content similarity
    between HEAD and the index) — it does not by itself prove the real
    history of a file. A target or an origin involved in more than one
    rename/copy entry is ambiguous and dropped. Read-only: nothing is staged,
    no index is written."""
    proc_rc, out, _ = core.git(root, "rev-parse", "--is-inside-work-tree")
    if proc_rc != 0 or out != "true":
        return {}
    import subprocess
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "-z",
             "--untracked-files=all", "--", "scripts"],
            capture_output=True)
    except OSError:
        return {}
    if proc.returncode != 0:
        return {}
    fields = proc.stdout.decode("utf-8", "replace").split("\0")
    pairs = []
    ambiguous_new, ambiguous_old = set(), set()
    i = 0
    while i < len(fields):
        entry = fields[i]
        if len(entry) < 4:
            i += 1
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            old = fields[i + 1] if i + 1 < len(fields) else ""
            i += 2
            if "C" in xy:  # a copy is never a provenance for a move
                ambiguous_new.add(path)
                ambiguous_old.add(old)
            else:
                pairs.append((path, old))
            continue
        i += 1
    renames = {}
    for new, old in pairs:
        if [n for n, _ in pairs].count(new) > 1 or [o for _, o in pairs].count(old) > 1:
            continue
        if new in ambiguous_new or old in ambiguous_old:
            continue
        renames[new] = old
    return renames


def _attach(rel, sha, baseline_files, current, renames):
    """Attach a changed current file to the baseline.

    Returns (category, baseline_path_or_None). Categories ('unchanged' is
    decided by the caller): 'modified',
    'moved-unchanged', 'moved-modified', 'new', 'indeterminate'. A shared
    file name or product is never a provenance; any ambiguous correspondence
    stays indeterminate (spec section 41.2)."""
    if rel in baseline_files:
        return "modified", rel
    same_content = sorted(b for b, bsha in baseline_files.items() if bsha == sha)
    if same_content:
        gone = [b for b in same_content if b not in current]
        candidates = gone or same_content
        return "moved-unchanged", candidates if len(candidates) > 1 else candidates[0]
    # Files with no correspondence by path or by content, on both sides. A
    # rename reported by Git is accepted only when it is the ONLY possible
    # pairing: one such current file, one such vanished baseline file.
    # Otherwise Git merely picked one candidate among several.
    baseline_shas = set(baseline_files.values())
    unmatched_new = [c for c, csha in current.items()
                     if c not in baseline_files and csha not in baseline_shas]
    current_shas = set(current.values())
    unmatched_gone = [b for b, bsha in baseline_files.items()
                      if b not in current and bsha not in current_shas]
    old = renames.get(rel)
    if old is not None and unmatched_new == [rel] and unmatched_gone == [old]:
        return "moved-modified", old
    if old is not None:
        return "indeterminate", None
    unaccounted = []
    moved_sources = set()
    for other, osha in current.items():
        if other in baseline_files:
            continue
        for b, bsha in baseline_files.items():
            if bsha == osha and b not in current:
                moved_sources.add(b)
    for b in baseline_files:
        if b not in current and b not in moved_sources:
            unaccounted.append(b)
    if unaccounted:
        return "indeterminate", None
    return "new", None


def _stop_info_path(root, session_id):
    """Information file of ONE session: no session ever overwrites or
    deletes the information of another one."""
    return Path(root) / SESSION_DIR_REL / STOP_INFO_DIR / ("%s.json" % _stem(session_id))


def _imports_path(root):
    return Path(root) / SESSION_DIR_REL / "imports.json"


def _imports_lock(root):
    return Path(root) / SESSION_DIR_REL / "imports.lock"


def _import_applies(record, started):
    """An import record serves a session that began before it was
    registered. Without dates (written before 2026-11-13): a snapshot
    without a start date keeps every record, as before; a dated session
    ignores an undated record (the start of a session used to erase it)."""
    if started is None:
        return True
    at = _stamp_epoch(record.get("registered_at"))
    return at is not None and at >= started


def _prune_imports(root):
    """Drop the records no present session can use any more. Never raises."""
    try:
        with core.file_lock(_imports_lock(root), timeout=1.0):
            imports = _load_imports(root)
            if not imports:
                return
            starts = [_stamp_epoch(data.get("created_at")) for _, _, data in _snapshots(root)]
            undated_session = any(s is None for s in starts)
            dated = [s for s in starts if s is not None]
            oldest = min(dated) if dated else None
            keep = {}
            for key, rec in imports.items():
                at = _stamp_epoch(rec.get("registered_at"))
                if undated_session or (at is not None and (oldest is None or at >= oldest)):
                    keep[key] = rec
            if len(keep) != len(imports):
                _save_imports(root, keep)
    except (OSError, TimeoutError):
        pass


def _load_imports(root):
    """Import records of the logical session: {original_path: record}.
    Malformed entries are dropped — a dropped record only means the file is
    treated as if it had never been declared."""
    data, err = core.read_json(_imports_path(root))
    if err or not isinstance(data, dict) or not isinstance(data.get("imports"), dict):
        return {}
    out = {}
    for key, rec in data["imports"].items():
        if not isinstance(key, str) or not isinstance(rec, dict):
            continue
        if not isinstance(rec.get("path"), str) \
                or not isinstance(rec.get("sha256"), str) \
                or _sane_record(rec.get("guard")) is None:
            continue
        out[key] = {"path": rec["path"], "sha256": rec["sha256"],
                    "guard": rec["guard"]}
        if isinstance(rec.get("registered_at"), str):
            out[key]["registered_at"] = rec["registered_at"]
    return out


def _save_imports(root, imports):
    path = _imports_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    core.atomic_write_json(path, {"imports": imports})


def register_import(root, source_path):
    """Declare a .pine imported during the session, BEFORE any modification.

    Returns {registered, relocated, path, sha256, reason}. Idempotent on an
    unchanged file. Refuses to renew a record whose content has changed.
    Moving the unchanged file (onboarding) relocates its record."""
    root = Path(root)
    out = {"registered": False, "relocated": False, "path": None,
           "sha256": None, "reason": None}
    if not _runtime_writable(root):
        out["reason"] = "runtime directory not writable inside the workspace"
        return out
    p = Path(source_path)
    if not p.is_absolute():
        p = root / p
    scripts_dir = root / "scripts"
    if p.is_symlink() or not p.is_file() or p.suffix != ".pine" \
            or not core.is_within(scripts_dir, p):
        out["reason"] = "not a regular .pine file under scripts/"
        return out
    rel = str(p.resolve().relative_to(root.resolve()))
    sha = core.sha256_file(p)
    out["path"], out["sha256"] = rel, sha
    try:
        with core.file_lock(_imports_lock(root), timeout=5.0):
            return _register_import_locked(root, p, rel, sha, out)
    except TimeoutError:
        out["reason"] = "import records busy (another session is writing them): retry"
        return out


def _register_import_locked(root, p, rel, sha, out):
    # The caller's session is not known here: the record is needed unless
    # EVERY present session baseline already holds this file.
    snaps = _snapshots(root)
    if snaps and all(rel in data["files"] for _, _, data in snaps):
        out["reason"] = ("present at session start: the session baseline "
                         "already covers this file, no import record needed")
        return out
    imports = _load_imports(root)
    for key, rec in imports.items():
        if rec["path"] == rel:
            if rec["sha256"] == sha:
                out["reason"] = "already registered, content unchanged"
                return out
            out["reason"] = ("already registered and the content has changed "
                             "since the import: an import record is never "
                             "renewed")
            out["refused"] = True
            return out
        if key == rel:
            out["reason"] = ("this path already served for an import, now "
                             "followed at %s: a second record is refused"
                             % rec["path"])
            out["refused"] = True
            return out
    moved = [key for key, rec in imports.items()
             if rec["sha256"] == sha and not (root / rec["path"]).is_file()]
    if len(moved) == 1:
        imports[moved[0]]["path"] = rel
        _save_imports(root, imports)
        out["registered"] = out["relocated"] = True
        out["reason"] = "record of %s relocated (content unchanged)" % moved[0]
        return out
    if len(moved) > 1:
        out["reason"] = ("several import records share this content and have "
                         "lost their file: ambiguous, nothing relocated")
        out["refused"] = True
        return out
    # An import record has lost its file and this candidate does not carry
    # its content: it may be that very import, moved AND modified. Creating
    # a fresh record here would take the modified state as the reference and
    # hide what was changed. The initial record is kept untouched. Nothing is
    # inferred from a file name or a product.
    lost = sorted(key for key, rec in imports.items()
                  if not (root / rec["path"]).is_file())
    if lost:
        out["reason"] = ("import record(s) without their file: %s — this file "
                         "cannot be attached to them without ambiguity (its "
                         "content differs from what was recorded); no new "
                         "record is created, the initial record is kept. If "
                         "this file is that import, it was modified after the "
                         "import: its findings are checked as they are"
                         % ", ".join(lost[:5]))
        out["refused"] = True
        out["lost_records"] = lost
        return out
    # guard state at import time: no manifest yet, so the distribution-bound
    # checks are recorded as not evaluable
    findings = guard.check_source(p, None, None)
    imports[rel] = {
        "path": rel,
        "sha256": sha,
        "registered_at": core.precise_now(),
        "guard": {
            "evaluable": True,
            "unevaluable_checks": guard.unverifiable_checks(findings),
            "blocking": [[c, s, n] for (c, s), n in
                         sorted(guard.blocking_identities(findings).items())],
        },
    }
    _save_imports(root, imports)
    out["registered"] = True
    out["reason"] = "import recorded"
    return out


def _attach_imports(root, imports, baseline, current, applicable=None):
    """Attach each import record (of `applicable` keys, all by default) to AT
    MOST one current file.

    Returns (attached, ambiguous): attached = {current_path: (category,
    guard_record)} with category 'imported-unchanged' or 'imported-modified';
    ambiguous = current paths whose content equals a lost import record that
    cannot be paired without a choice."""
    attached, ambiguous = {}, set()
    lost = []
    relocations = {}
    for key, rec in imports.items():
        if applicable is not None and key not in applicable:
            continue
        path = rec["path"]
        if path in current and path not in baseline:
            attached[path] = ("imported-unchanged" if current[path] == rec["sha256"]
                              else "imported-modified", rec["guard"])
        elif path not in current:
            lost.append(key)
    relocated = False
    for key in lost:
        rec = imports[key]
        same = [k for k in lost if imports[k]["sha256"] == rec["sha256"]]
        candidates = [c for c, csha in current.items()
                      if csha == rec["sha256"] and c not in baseline
                      and c not in attached]
        if len(same) == 1 and len(candidates) == 1:
            attached[candidates[0]] = ("imported-unchanged", rec["guard"])
            rec["path"] = candidates[0]
            relocations[key] = (rec["sha256"], candidates[0])
            relocated = True
        else:
            ambiguous.update(candidates)
    if relocated and _runtime_writable(root):
        # re-read under the lock: a record written meanwhile by another
        # session is never lost by this update
        try:
            with core.file_lock(_imports_lock(root), timeout=1.0):
                fresh = _load_imports(root)
                for key, (sha, path) in relocations.items():
                    if key in fresh and fresh[key]["sha256"] == sha:
                        fresh[key]["path"] = path
                _save_imports(root, fresh)
        except (OSError, TimeoutError):
            pass
    return attached, ambiguous


def _sane_record(record):
    """Normalize one baseline guard record. Anything malformed yields None
    (treated as 'guard state unknown at start': never a retroactive block,
    never a crash)."""
    if not isinstance(record, dict) or not isinstance(record.get("evaluable"), bool):
        return None
    blocking = record.get("blocking", [])
    unevaluable = record.get("unevaluable_checks", [])
    if not isinstance(blocking, list) or not isinstance(unevaluable, list):
        return None
    counts = {}
    for item in blocking:
        if not (isinstance(item, list) and len(item) == 3
                and isinstance(item[0], str) and isinstance(item[1], str)
                and isinstance(item[2], int) and not isinstance(item[2], bool)):
            return None
        counts[(item[0], item[1])] = item[2]
    if not all(isinstance(c, str) for c in unevaluable):
        return None
    return {"evaluable": record["evaluable"], "blocking": counts,
            "unevaluable_checks": set(unevaluable)}


def hook_stop(root, stdin_data):
    """Stop hook body — never raises: any unexpected failure degrades to the
    silent, non-blocking outcome. Returns (exit_code, stdout_text)."""
    try:
        return _hook_stop(root, stdin_data)
    except Exception as exc:  # noqa: BLE001 — a hook must never crash the session
        _record_hook_error(root, "stop", exc)
        return 0, ""


def _record_hook_error(root, hook, exc):
    """Trace an internal failure of a hook (announced at the next start).
    Never raises."""
    try:
        if not _runtime_writable(root):
            return
        path = Path(root) / SESSION_DIR_REL / HOOK_ERRORS
        data, err = core.read_json(path)
        if err or not isinstance(data, dict) or not isinstance(data.get("errors"), list):
            data = {"errors": []}
        frames = traceback.extract_tb(exc.__traceback__)
        where = ("%s:%s (%s)" % (Path(frames[-1].filename).name, frames[-1].lineno,
                                 frames[-1].name)) if frames else ""
        data["errors"] = (data["errors"] + [{
            "at": core.precise_now(), "hook": hook,
            "error": "%s: %s" % (type(exc).__name__, str(exc)[:300]),
            "where": where, "reported": False}])[-MAX_HOOK_ERRORS:]
        path.parent.mkdir(parents=True, exist_ok=True)
        core.atomic_write_json(path, data)
    except Exception:  # noqa: BLE001
        pass


def _hook_errors(root, mark_reported):
    """Hook failures not yet announced: one line each; marked as announced
    (the trace itself is kept, last MAX_HOOK_ERRORS entries)."""
    path = Path(root) / SESSION_DIR_REL / HOOK_ERRORS
    data, err = core.read_json(path)
    if err or not isinstance(data, dict) or not isinstance(data.get("errors"), list):
        return []
    lines = []
    for e in data["errors"]:
        if isinstance(e, dict) and e.get("reported") is False:
            lines.append("%s — %s — %s %s" % (e.get("at"), e.get("hook"), e.get("error"),
                                             e.get("where") or ""))
            if mark_reported:
                e["reported"] = True
    if lines and mark_reported and _runtime_writable(root):
        try:
            core.atomic_write_json(path, data)
        except OSError:
            pass
    return lines


def _hook_stop(root, stdin_data):
    """Stop hook body. Returns (exit_code, stdout_text).

    Attribution is made finding by finding (spec section 41.2). Blocks
    (decision JSON) ONLY on mechanical BLOCKING guard findings INTRODUCED
    during this session. Pre-existing findings, findings made visible by the
    context and findings of indeterminate attribution are reported without
    blocking, with their category, and handed to the next SessionStart
    summary. Never blocks twice in a row (stop_hook_active) and never blocks
    without a baseline.
    """
    if not isinstance(stdin_data, dict):
        return 0, ""
    if stdin_data.get("stop_hook_active"):
        return 0, ""
    session_id = stdin_data.get("session_id") or ""
    root = Path(root)
    _, snap_path, _ = _snapshot_paths(root, session_id)
    snapshot, err = core.read_json(snap_path)
    if err or not isinstance(snapshot, dict):
        return 0, ""  # no baseline: inform-only degradation, never block
    if _runtime_writable(root):
        _touch(snap_path)  # last use of this baseline (startup cleanup)
    lineage = snapshot.get("lineage")
    unproven = isinstance(lineage, dict) and lineage.get("established") is False

    baseline = snapshot.get("files", {})
    if not isinstance(baseline, dict):
        return 0, ""
    records = snapshot.get("guard")
    if not isinstance(records, dict):
        records = None  # snapshot written before finding attribution existed
    current = _registered_pine_hashes(root)
    # The guard always runs with the CURRENT context on every present .pine:
    # a known fingerprint exempts from no check (a manifest change can make
    # an unchanged source non-compliant).
    registered_sources = _registered_sources(root)
    identity = config.identity(root)
    renames = _git_renames(root)
    all_imports = _load_imports(root)
    started = _stamp_epoch(snapshot.get("created_at"))
    imported, import_ambiguous = _attach_imports(
        root, all_imports, baseline, current,
        {k for k, rec in all_imports.items() if _import_applies(rec, started)})
    # a declared import is accounted for: it must not make another file's
    # correspondence look ambiguous
    others = {k: v for k, v in current.items() if k not in imported}
    # Structured items (2026-11-14): the words are chosen when the items are
    # shown, in the language in force at that moment (_render_stop_item); the
    # attribution logic below is unchanged.
    introduced, info = [], []
    sensitive = False

    def note(rel, label, check, detail):
        info.append({"k": "note", "rel": rel, "check": check, "text": detail, "label": label})

    for rel in sorted(current):
        if baseline.get(rel) == current[rel]:
            category, attached = "unchanged", rel
            if rel not in registered_sources:
                continue  # untouched and still unregistered: nothing new
        elif rel in imported:
            category, attached = imported[rel][0], None
        elif rel in import_ambiguous:
            category, attached = "indeterminate", None
        else:
            category, attached = _attach(rel, current[rel], baseline, others,
                                         renames)
        record = None
        at_import = rel in imported and category != "unchanged"
        moment = "import" if at_import else "start"
        if at_import:
            record = imported[rel][1]
        elif isinstance(attached, list):
            # several baseline files share this exact content: usable only
            # when their guard records agree, otherwise nothing is attributed
            raw = [(records or {}).get(a) for a in attached]
            recs = [_sane_record(r) for r in raw]
            if records is not None and all(r == recs[0] for r in recs):
                record = raw[0]
                attached = attached[0]
            else:
                category, attached = "indeterminate", None
        elif attached is not None and records is not None:
            record = records.get(attached)
        record = _sane_record(record)
        evaluable = bool(record and record.get("evaluable"))
        content_changed = category in ("modified", "moved-modified",
                                       "imported-modified")

        product = registered_sources.get(rel)
        if product is None:
            if category in ("modified", "moved-modified", "new",
                            "imported-modified"):
                introduced.append({"k": "unregistered_modified", "rel": rel})
            else:
                info.append({"k": "unregistered", "rel": rel, "cat": category})
            continue

        findings = guard.check_source(root / rel, _product_policy(product, identity),
                                      Path(product["path"]), identity)
        counts = guard.blocking_identities(findings)
        details = {}
        for f in findings:
            if f["status"] == "BLOCKING":
                details[f["check"]] = f["detail"]
        if category == "indeterminate":
            for (check, subject), n in sorted(counts.items()):
                note(rel, {"k": "indeterminate"}, check, _subject_text(subject, details[check]))
            if not counts:
                info.append({"k": "indeterminate_clean", "rel": rel})
            continue
        if category == "new":
            for (check, subject), n in sorted(counts.items()):
                introduced.append({"k": "new_file", "rel": rel, "check": check,
                                   "text": _subject_text(subject, details[check])})
                if check in LICENCE_SENSITIVE_CHECKS:
                    sensitive = True
            continue
        base_counts = {}
        unevaluable = set()
        if evaluable:
            base_counts = record["blocking"]
            unevaluable = record["unevaluable_checks"]
        for (check, subject), n in sorted(counts.items()):
            text = _subject_text(subject, details[check])
            if not evaluable or check in unevaluable:
                # "changed" is stated as a fact, not as a cause: the content
                # changed too, so an introduction cannot be excluded
                note(rel, {"k": "visible", "moment": moment, "changed": content_changed},
                     check, text)
                continue
            before = base_counts.get((check, subject), 0)
            if before:
                if at_import:
                    label = {"k": "preexisting", "moment": moment}
                elif unproven:
                    label = {"k": "resumed"}
                else:
                    label = {"k": "preexisting"}
                note(rel, label, check, text)
            if n > before:
                introduced.append({"k": "introduced", "rel": rel, "check": check, "text": text})
                if check in LICENCE_SENSITIVE_CHECKS:
                    sensitive = True

    lang = _configured_language(root)   # the language in force now, at Stop
    _write_stop_info(root, session_id, info, lang)
    if introduced:
        reason = (i18n.t("stop.reason.introduced", lang) + "\n- "
                  + "\n- ".join(_render_stop_item(i, lang) or str(i) for i in introduced[:12]))
        if sensitive:
            reason += "\n\n" + i18n.t("stop.reason.legal", lang)
        if info:
            reason += ("\n\n" + i18n.t("stop.reason.info", lang) + "\n- "
                       + "\n- ".join(_render_stop_item(i, lang) or str(i) for i in info[:8]))
        return 0, json.dumps({"decision": "block", "reason": reason})
    return 0, ""


def _configured_language(root):
    """Language in force now (`language` of pws.config.json); a missing or
    unreadable configuration or an unknown value gives the catalogue default,
    as everywhere else (config.read_config, i18n.normalize_language)."""
    try:
        return i18n.normalize_language(config.read_config(root)["data"].get("language"))
    except Exception:  # noqa: BLE001 — a hook never fails on its presentation
        return i18n.DEFAULT_LANGUAGE


def _render_stop_label(label, lang):
    """Words of the category of a non-blocking finding, in `lang`; None when
    `label` is not a known structure."""
    if not isinstance(label, dict):
        return None
    kind, moment = label.get("k"), label.get("moment")
    if moment not in (None, "start", "import"):
        return None
    at = i18n.t("stop.moment." + moment, lang) if moment else None
    if kind == "indeterminate":
        return i18n.t("stop.label.indeterminate", lang)
    if kind == "resumed":
        return i18n.t("stop.label.resumed", lang)
    if kind == "preexisting":
        return (i18n.t("stop.label.preexisting_at", lang, moment=at) if at
                else i18n.t("stop.label.preexisting", lang))
    if kind == "visible" and at:
        text = i18n.t("stop.label.visible", lang, moment=at)
        if label.get("changed") is True:
            text += i18n.t("stop.label.visible.changed", lang)
        return text
    return None


def _render_stop_item(item, lang):
    """One line of Stop information or of a blocking reason, in `lang`. Paths,
    check identifiers and guard details are reproduced exactly. None when the
    item is not a known structure (its recorded text is then shown as is)."""
    if not isinstance(item, dict) or not isinstance(item.get("rel"), str):
        return None
    kind, rel = item.get("k"), item["rel"]
    if kind == "unregistered_modified":
        return i18n.t("stop.item.unregistered_modified", lang, rel=rel)
    if kind == "unregistered":
        key = "stop.category.%s" % item.get("cat")
        if not i18n.has_key(key):
            return None
        return i18n.t("stop.item.unregistered", lang, rel=rel, category=i18n.t(key, lang))
    if kind == "indeterminate_clean":
        return i18n.t("stop.item.indeterminate_clean", lang, rel=rel)
    check, text = item.get("check"), item.get("text")
    if not isinstance(check, str) or not isinstance(text, str):
        return None
    if kind == "introduced":
        return i18n.t("stop.item.introduced", lang, rel=rel, check=check, text=text)
    if kind == "new_file":
        return i18n.t("stop.item.new_file", lang, rel=rel, check=check, text=text)
    if kind == "note":
        label = _render_stop_label(item.get("label"), lang)
        if label is None:
            return None
        return i18n.t("stop.item.note", lang, rel=rel, check=check, text=text, label=label)
    return None


def _subject_text(subject, detail):
    """Human text of one anomaly: its object when it has one, else the
    guard detail (which may carry line numbers — display only)."""
    return subject if subject else detail


def _registered_sources(root):
    root = Path(root)
    s = scan.scan_workspace(root)
    registered = {}
    for p in s["products"]:
        if p.get("source"):
            try:
                registered[str(Path(p["source"]).resolve()
                               .relative_to(root.resolve()))] = p
            except ValueError:
                continue
    return registered


def _baseline_guard(root, files):
    """Guard record of every .pine at baseline time: whether the guard could
    be applied (registered source), the checks it could not evaluate, and the
    counted identities of its BLOCKING findings."""
    root = Path(root)
    registered = _registered_sources(root)
    identity = config.identity(root)
    records = {}
    for rel in files:
        product = registered.get(rel)
        if product is None:
            records[rel] = {"evaluable": False, "unevaluable_checks": [],
                            "blocking": []}
            continue
        findings = guard.check_source(root / rel, _product_policy(product, identity),
                                      Path(product["path"]), identity)
        records[rel] = {
            "evaluable": True,
            "unevaluable_checks": guard.unverifiable_checks(findings),
            "blocking": [[c, s, n] for (c, s), n in
                         sorted(guard.blocking_identities(findings).items())],
        }
    return records


def _info_tree_real(root):
    return core.runtime_tree_is_real(root, SESSION_DIR_REL.parts + (STOP_INFO_DIR,))


STOP_INFO_FORMAT = 2   # 2026-11-14: structured items, worded when shown


def _write_stop_info(root, session_id, info, lang=None):
    """Persist the non-blocking Stop information of THIS session for the
    next SessionStart summary (exit-0 stdout of a Stop hook is not injected
    into context). Never touches the file of another session. Format 2:
    `items` (structured, worded in the language in force when they are shown)
    and `info` (the same lines worded at write time, in `language` — kept so
    that a reader of the format 1 still finds them)."""
    if not _runtime_writable(root) or not _info_tree_real(root):
        return
    path = _stop_info_path(root, session_id)
    lang = i18n.normalize_language(lang)
    try:
        if info:
            items = info[:50]
            path.parent.mkdir(parents=True, exist_ok=True)
            core.atomic_write_json(path, {
                "session_id": session_id, "format": STOP_INFO_FORMAT, "language": lang,
                "items": items, "info": [_render_stop_item(i, lang) or str(i) for i in items]})
        elif path.exists():
            path.unlink()
    except OSError:
        pass


def _read_stop_info(root, consume, session_id=None, lang=None):
    """Pending Stop information of every session, oldest first, each shown
    once; a line of another session is labelled with its identifier. The
    file written before 2026-11-13 (stop-info.json) is read the same way.
    Structured items are worded in `lang`, the language in force at display;
    a line recorded as text only (earlier versions) or an item of unknown
    structure is shown as it was recorded, marked as such, never
    reinterpreted."""
    sdir = Path(root) / SESSION_DIR_REL
    sources = [(sdir / "stop-info.json", None)]
    if _info_tree_real(root) and (sdir / STOP_INFO_DIR).is_dir():
        try:
            names = sorted(os.listdir(str(sdir / STOP_INFO_DIR)))
        except OSError:
            names = []
        sources += [(sdir / STOP_INFO_DIR / n, n[:-len(".json")]) for n in names
                    if n.endswith(".json")]

    def last_use(item):
        try:
            return item[0].stat().st_mtime
        except OSError:
            return 0.0
    own = _stem(session_id) if session_id else None
    out = []
    for path, stem in sorted(sources, key=last_use):
        if path.is_symlink() or not path.is_file():
            continue
        data, err = core.read_json(path)
        if err or not isinstance(data, dict):
            continue
        items, recorded = data.get("items"), data.get("info")
        if not isinstance(items, list) and not isinstance(recorded, list):
            continue
        label = "" if stem is None or stem == own else "[session %s] " % stem[:8]
        if isinstance(items, list):
            for i, item in enumerate(items):
                line = _render_stop_item(item, lang)
                if line is None:
                    if not (isinstance(recorded, list) and i < len(recorded)):
                        continue
                    line = i18n.t("stop.recorded", lang) + str(recorded[i])
                out.append(label + line)
        else:
            out.extend(label + i18n.t("stop.recorded", lang) + str(x) for x in recorded)
        if consume and _runtime_writable(root):
            try:
                path.unlink()
            except OSError:
                pass
    return out
