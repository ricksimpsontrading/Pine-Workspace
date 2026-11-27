# SPDX-License-Identifier: Apache-2.0
"""Maintenance: startup cleanup (whitelist) and archive import.

Startup cleanup — fast, deterministic, in-scope only. It removes, file by
file, items that are BOTH explicitly recreatable and unused:
  * `*.pyc` regular files directly inside a real `__pycache__/` folder under
    tools/ (the folder itself only once emptied; any other content of such a
    folder — a user file, a sub-folder, a link — is never touched);
  * `.DS_Store` regular files (macOS artefacts);
  * session snapshots in the format written by the SessionStart hook
    (`<safe id>.json` holding a `files` mapping) whose LAST MODIFICATION —
    i.e. their last use — is older than SNAPSHOT_RETENTION_DAYS; never the
    snapshot named by `latest.json` nor the current session's one, and none
    at all while `latest.json` is unreadable.
A candidate whose relative path is cited by a text file tracked by Git is
kept; when that check cannot run, nothing is removed. Never touches archives
content, evidence, sources, lock files, `node_modules`, PineTS rollback or
evaluation trees, nor anything under `.git`; links are never followed nor
removed. An unreadable folder is an anomaly, never a failure of the hook.
Serialized by an advisory lock so two sessions never clean concurrently; logs
to `.claude/runtime/maintenance/cleanup-log.jsonl`; reports only when it did
something or met an anomaly.

Archive import — procedure ratified on 2026-11-06 (six steps): inventory,
references, copy, hash verification and completeness, move index, deletion
of the external folder only after complete verification. Exact duplicates
(same SHA-256) keep ONE copy plus references; nothing else is dropped.
These local archives never replace a backup independent of the disk.

Safety rules enforced here at the plan, the import and the removal (an
explicit `--yes` never replaces any of them):
  * refused path relations, compared by physical identity (device, inode):
    source equal to, inside or containing the workspace; source inside or
    containing another PWS installation; source given as a symbolic link;
    target outside docs/maintenance/archives;
  * a plan is bound to its source folder (identity) and to its inventory
    (SHA-256 of the entries); an older plan format, an altered plan, a plan
    without entry or with a blocking anomaly is refused;
  * the removal re-inventories the CURRENT source and refuses any new,
    modified, linked, special or unreadable item and any recreated folder;
    it then deletes only the files it has just verified as archived (plus
    `.DS_Store`) and the emptied folders — never a recursive deletion;
  * MANIFEST.json and INDEX.md at the archives root are cumulative: every
    import stays listed and resolvable; a foreign or unreadable index is
    never overwritten.
"""
import datetime
import hashlib
import json
import os
import shutil
import stat
import time
import unicodedata
from pathlib import Path

from . import core

SNAPSHOT_RETENTION_DAYS = 7
MAINTENANCE_REL = core.RUNTIME_REL / "maintenance"
SESSION_REL = core.RUNTIME_REL / "session"
ARCHIVES_REL = Path("docs/maintenance/archives")
PROTECTED_DIR_NAMES = {".git", "node_modules"}
# trees never entered by the cleanup walk (reference material, rollbacks)
PROTECTED_RUNTIME_SUBTREES = {"pinets-rollback", "pinets-eval", "pine-local-test", "vela-view",
                              "migration-backup", "github-export", "maintenance"}
# files of the session folder that are never snapshots
SESSION_SIDE_FILES = {"latest.json", "stop-info.json", "imports.json"}
# file name the SessionStart hook gives to the snapshot of an unsafe session id
UNSAFE_SESSION_STEM = "unsafe-session-id"

PLAN_FORMAT = 2
MANIFEST_FORMAT = 2
ACTIONS = ("copy", "duplicate_in_source", "already_in_workspace")
INDEX_TITLE = "# Archives — index des déplacements / move index"
PARTIAL_SUFFIX = ".pws-partial"
MANIFEST_NOTE = ("Local archives grouped from external backup folders. They do NOT replace a "
                 "backup independent of this disk. Historical reports keep their original "
                 "paths: use this cumulative move index (one record per import) to resolve them.")
_OPEN_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_OPEN_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_HEX = frozenset("0123456789abcdef")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(base, path):
    try:
        return Path(path).relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _reason(exc):
    return getattr(exc, "strerror", None) or str(exc)


def _sha256_regular(path):
    """SHA-256 of a regular file, opened without following a link and without
    blocking on a named pipe (a FIFO swapped in after a listing)."""
    fd = os.open(str(path), os.O_RDONLY | _OPEN_NOFOLLOW | _OPEN_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file: %s" % path)
        h = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    finally:
        os.close(fd)


def _regular_sha(path):
    """SHA-256 of `path` when it is a regular file, else None (missing, link,
    special file, unreadable)."""
    try:
        if not stat.S_ISREG(os.lstat(str(path)).st_mode):
            return None
        return _sha256_regular(path)
    except OSError:
        return None


def _unlink_quietly(path):
    try:
        os.unlink(str(path))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Startup cleanup (whitelist)
# ---------------------------------------------------------------------------

def _walk(top, root, anomalies):
    """os.walk without following links; an unreadable folder is an anomaly."""
    def onerror(exc):
        anomalies.append("unreadable folder: %s (%s)"
                         % (_rel(root, getattr(exc, "filename", None) or top), _reason(exc)))
    return os.walk(str(top), followlinks=False, onerror=onerror)


def _regular_size(path, root, anomalies):
    """Size of a regular file (a link is never followed), else None."""
    try:
        st = os.lstat(str(path))
    except FileNotFoundError:
        return None
    except OSError as exc:
        anomalies.append("unreadable item: %s (%s)" % (_rel(root, path), _reason(exc)))
        return None
    return st.st_size if stat.S_ISREG(st.st_mode) else None


def _pycache_candidates(root, anomalies):
    """`*.pyc` regular files directly inside a real `__pycache__/` under tools/,
    then the folder itself (0 byte) when it holds nothing else."""
    out = []
    tools_dir = root / "tools"
    if not tools_dir.is_dir() or tools_dir.is_symlink():
        return out
    for dirpath, dirnames, _ in _walk(tools_dir, root, anomalies):
        dirnames[:] = sorted(d for d in dirnames if d not in PROTECTED_DIR_NAMES)
        if "__pycache__" not in dirnames:
            continue
        dirnames.remove("__pycache__")  # inspected here, never walked further
        cache = Path(dirpath) / "__pycache__"
        if cache.is_symlink() or not core.is_within(root, cache):
            continue
        try:
            names = sorted(os.listdir(str(cache)))
        except OSError as exc:
            anomalies.append("unreadable folder: %s (%s)" % (_rel(root, cache), _reason(exc)))
            continue
        files = []
        for name in names:
            if name.endswith(".pyc") and len(name) > len(".pyc"):
                size = _regular_size(cache / name, root, anomalies)
                if size is not None:
                    files.append((cache / name, "pycache", size))
        out.extend(files)
        if len(files) == len(names):  # nothing but bytecode: the emptied folder goes too
            out.append((cache, "pycache", 0))
    return out


def _ds_store_candidates(root, anomalies):
    out = []
    for dirpath, dirnames, filenames in _walk(root, root, anomalies):
        rel_parts = Path(dirpath).relative_to(root).parts
        dirnames[:] = sorted(d for d in dirnames if d not in PROTECTED_DIR_NAMES)
        if rel_parts[:2] == (".claude", "runtime"):
            dirnames[:] = [d for d in dirnames if d not in PROTECTED_RUNTIME_SUBTREES]
        if ".DS_Store" in filenames:
            p = Path(dirpath) / ".DS_Store"
            size = _regular_size(p, root, anomalies)
            if size is not None:
                out.append((p, "ds_store", size))
    return out


def _snapshot_stem(session_id):
    return session_id if core.is_safe_id(session_id) else UNSAFE_SESSION_STEM


def _is_snapshot(path, stem):
    """Format written by the SessionStart hook: a JSON object holding a `files`
    mapping and, when present, the `session_id` its file name derives from."""
    data, err = core.read_json(path)
    if err or not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return False
    sid = data.get("session_id", stem)
    if not isinstance(sid, str):
        return False
    return sid == stem or (stem == UNSAFE_SESSION_STEM and not core.is_safe_id(sid))


def _snapshot_candidates(root, anomalies, current_session_id=None):
    """Snapshots unused for SNAPSHOT_RETENTION_DAYS. The age is the LAST
    MODIFICATION of the file (the Stop hook refreshes it at every end of
    turn), never its creation. Kept: the snapshot named by latest.json, the
    current session's one, and all of them while latest.json is unreadable."""
    out = []
    sdir = root / SESSION_REL
    if not sdir.is_dir() or sdir.is_symlink():
        return out
    latest, lerr = core.read_json(sdir / "latest.json")
    if lerr or not isinstance(latest, dict) or not isinstance(latest.get("session_id"), str):
        return out
    keep = {_snapshot_stem(latest["session_id"])}
    if isinstance(current_session_id, str) and current_session_id:
        keep.add(_snapshot_stem(current_session_id))
    cutoff = time.time() - SNAPSHOT_RETENTION_DAYS * 86400
    try:
        names = sorted(os.listdir(str(sdir)))
    except OSError as exc:
        anomalies.append("unreadable folder: %s (%s)" % (_rel(root, sdir), _reason(exc)))
        return out
    for name in names:
        stem = name[:-len(".json")]
        if (not name.endswith(".json") or name in SESSION_SIDE_FILES
                or not core.is_safe_id(stem) or stem in keep):
            continue
        p = sdir / name
        try:
            st = os.lstat(str(p))
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_mtime >= cutoff:
            continue
        if _is_snapshot(p, stem):
            out.append((p, "stale_session_snapshot", st.st_size))
    return out


def _candidates(root, anomalies=None, current_session_id=None):
    """Whitelisted removable items: [(path, category, bytes)]."""
    root = Path(root)
    if anomalies is None:
        anomalies = []
    return (_pycache_candidates(root, anomalies) + _ds_store_candidates(root, anomalies)
            + _snapshot_candidates(root, anomalies, current_session_id))


def _tracked_references(root, rels):
    """Paths among `rels` cited by a text file tracked by Git. Returns (set,
    error); on error nothing may be removed. A bare file name (an item at the
    workspace root) is a generic mention, never the citation of one file.
    Case and Unicode composition are ignored: a wider match only keeps more."""
    variants = {}
    for rel in rels:
        if "/" not in rel:
            continue
        for form in (rel, unicodedata.normalize("NFC", rel), unicodedata.normalize("NFD", rel)):
            variants.setdefault(form, rel)
    if not variants:
        return set(), None
    args = ["grep", "--no-color", "-I", "-F", "-i", "-o", "-h"]
    for form in sorted(variants):
        args += ["-e", form]
    rc, out, err = core.git(root, *args)
    if rc == 1:
        return set(), None
    if rc != 0:
        # no repository at all (decided on the file system, never on a
        # localized message): nothing is tracked, nothing can be cited
        if not os.path.lexists(str(Path(root) / ".git")) and core.find_enclosing_git_root(root) is None:
            return set(), None
        return None, "reference check unavailable (git grep: %s)" % (
            ((err or "").splitlines() or [str(rc)])[0])
    found = {unicodedata.normalize("NFC", line).casefold() for line in out.splitlines() if line}
    referenced = set()
    for rel in set(variants.values()):
        key = unicodedata.normalize("NFC", rel).casefold()
        if any(key in f for f in found):
            referenced.add(rel)
    return referenced, None


def cleanup(root, execute, enabled=True, current_session_id=None):
    """Plan (execute=False) or run (execute=True) the whitelisted cleanup.
    `current_session_id`: the session that triggers it (its snapshot is kept)."""
    root = Path(root)
    report = {"enabled": enabled, "executed": execute, "removed": [], "planned": [],
              "kept_referenced": [], "bytes": 0, "anomalies": [], "summary_lines": [],
              "skipped_locked": False}
    if not enabled:
        return report
    if not core.runtime_tree_is_real(root, MAINTENANCE_REL.parts):
        report["anomalies"].append("runtime tree is a symlink or escapes the workspace — "
                                   "cleanup skipped (nothing written through it)")
        return report
    lock = root / MAINTENANCE_REL / "cleanup.lock"
    try:
        with core.file_lock(lock, timeout=0.2):
            try:
                _run_cleanup(root, execute, report, current_session_id)
            except (OSError, ValueError) as exc:
                report["anomalies"].append("cleanup interrupted: %s" % _reason(exc))
            report["anomalies"] = list(dict.fromkeys(report["anomalies"]))
            if execute and (report["removed"] or report["anomalies"]):
                _log(root, report)
    except TimeoutError:
        report["skipped_locked"] = True
    except OSError as exc:
        report["anomalies"].append("cleanup lock unavailable: %s" % _reason(exc))
    return report


def _run_cleanup(root, execute, report, current_session_id):
    anomalies = report["anomalies"]
    items = _candidates(root, anomalies, current_session_id)
    if not items:
        return
    referenced, err = _tracked_references(root, [_rel(root, p) for p, _, _ in items])
    if err:
        anomalies.append("%s — nothing removed" % err)
        return
    for path, category, size in items:
        rel = _rel(root, path)
        if rel in referenced:
            report["kept_referenced"].append(rel)
            continue
        report["planned"].append({"path": rel, "category": category, "bytes": size})
        if not execute:
            continue
        try:
            st = os.lstat(str(path))
            if category == "pycache" and stat.S_ISDIR(st.st_mode):
                try:
                    os.rmdir(str(path))  # succeeds only when nothing is left inside
                except OSError:
                    continue  # something stayed or appeared: the folder is kept
                done = 0
            elif stat.S_ISREG(st.st_mode):
                os.unlink(str(path))
                done = st.st_size
            else:
                continue  # replaced since the listing: no longer a candidate
        except FileNotFoundError:
            continue
        except OSError as exc:
            anomalies.append("%s: %s" % (rel, _reason(exc)))
            continue
        report["removed"].append({"path": rel, "category": category, "bytes": done})
        report["bytes"] += done


def _log(root, report):
    path = Path(root) / MAINTENANCE_REL / "cleanup-log.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": _now_iso(), "removed": report["removed"],
                                "anomalies": report["anomalies"]},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass


def startup_cleanup(root, current_session_id=None):
    """Hook entry: whitelist cleanup when enabled by the configuration;
    returns the report with localized summary lines (only when relevant).
    Never raises: the SessionStart hook must not fail because of it."""
    from . import config, i18n
    try:
        data = config.read_config(root).get("data")
        data = data if isinstance(data, dict) else {}
        maint = data.get("maintenance")
        enabled = bool((maint if isinstance(maint, dict) else {}).get("startup_cleanup", True))
        lang = i18n.normalize_language(data.get("language"))
    except Exception:  # unreadable configuration: no cleanup, default language
        enabled, lang = False, "en"
    try:
        report = cleanup(root, execute=True, enabled=enabled,
                         current_session_id=current_session_id)
    except Exception as exc:  # never a failure of the hook
        report = {"enabled": enabled, "executed": True, "removed": [], "planned": [],
                  "kept_referenced": [], "bytes": 0, "skipped_locked": False,
                  "summary_lines": [],
                  "anomalies": ["cleanup interrupted: %s: %s" % (type(exc).__name__, exc)]}
    lines = []
    if report.get("skipped_locked"):
        lines.append(i18n.t("cleanup.skipped_lock", lang))
    if report["removed"]:
        lines.append(i18n.t("cleanup.removed", lang, n=len(report["removed"]),
                            bytes=report["bytes"]))
    for a in report["anomalies"][:3]:
        lines.append(i18n.t("cleanup.anomaly", lang, detail=a))
    report["summary_lines"] = lines
    return report


# ---------------------------------------------------------------------------
# Archive import (external backups → docs/maintenance/archives)
# ---------------------------------------------------------------------------

def _dir_identity(path):
    st = os.stat(str(path))
    return [st.st_dev, st.st_ino]


def _is_installation(folder):
    """A PWS installation (or distribution) is recognised by its core package."""
    return os.path.lexists(os.path.join(str(folder), "tools", "pws_workspace"))


def _source_relation_problem(root, source):
    """Refusal reason for a source folder, or None. Checked at the plan, the
    import and the removal. Folders are compared by physical identity (device,
    inode): another spelling, case, firmlink or linked parent of the same
    folder is still recognised."""
    root = Path(root)
    src = Path(str(source))
    if not src.is_absolute():
        return "the source path must be absolute: %s" % source
    if src.is_symlink():
        return ("the source is a symbolic link — give the real folder, never a link "
                "(refused): %s" % source)
    if not src.exists():
        return "source folder missing: %s" % source
    if not src.is_dir():
        return "the source is not a folder: %s" % source
    try:
        src_id = _dir_identity(src)
        root_real = root.resolve()
        root_id = _dir_identity(root_real)
        src_real = src.resolve()
    except OSError as exc:
        return "source folder unreadable: %s (%s)" % (source, _reason(exc))
    if src_id == root_id:
        return "the source IS the workspace (refused): %s" % source
    for anc in src_real.parents:
        try:
            if _dir_identity(anc) == root_id:
                return "the source is inside the workspace (refused): %s" % source
        except OSError:
            pass
        if _is_installation(anc):
            return ("the source is inside another PWS installation %s (refused): %s"
                    % (anc, source))
    for anc in [root_real] + list(root_real.parents):
        try:
            if _dir_identity(anc) == src_id:
                return ("the source CONTAINS the workspace %s — deleting it would delete the "
                        "workspace (refused): %s" % (root_real, source))
        except OSError:
            continue
    if _is_installation(src_real):
        return "the source is a PWS installation (refused): %s" % source
    return None


def _check_target(root, target_rel):
    """(error, normalized target): the target must stay physically inside
    docs/maintenance/archives (the folder itself or one of its sub-folders)."""
    if not isinstance(target_rel, (str, Path)) or not str(target_rel).strip():
        return "invalid target: %r" % (target_rel,), None
    rel = Path(str(target_rel))
    n = len(ARCHIVES_REL.parts)
    if rel.is_absolute() or ".." in rel.parts or rel.parts[:n] != ARCHIVES_REL.parts:
        return ("target refused: archives are imported only into %s or one of its "
                "sub-folders (got %s)" % (ARCHIVES_REL.as_posix(), target_rel)), None
    root = Path(root)
    if not core.runtime_tree_is_real(root, rel.parts) or not core.is_within(root, root / rel):
        return ("target refused: %s crosses a symbolic link or escapes the workspace"
                % target_rel), None
    return None, rel.as_posix()


_SKIP_TEXT = {"symlink": "symlink skipped (never followed nor copied): %s",
              "special": "special file skipped (not a regular file): %s",
              "unreadable": "unreadable file skipped: %s",
              "unreadable-folder": "unreadable folder skipped: %s"}


def _skipped_text(item):
    text = _SKIP_TEXT.get(item.get("kind"), "skipped: %s") % item.get("rel")
    if item.get("detail"):
        text += " (%s)" % item["detail"]
    return text


def _scan_source(source, root_id=None):
    """Recursive physical inventory: regular files only (hashed), `.DS_Store`
    ignored, links / special / unreadable items listed as skipped, never
    followed nor opened. Stops before hashing when the source holds the
    workspace or a PWS installation."""
    source = Path(source)
    scan = {"entries": [], "stats": {}, "skipped": [], "ignored": [], "dirs": [],
            "installations": [], "contains_workspace": False}
    files = []

    def onerror(exc):
        scan["skipped"].append({"rel": _rel(source, getattr(exc, "filename", None) or source),
                                "kind": "unreadable-folder", "detail": _reason(exc)})

    for dirpath, dirnames, filenames in os.walk(str(source), followlinks=False, onerror=onerror):
        here = Path(dirpath)
        scan["dirs"].append(here)
        if root_id is not None:
            try:
                if _dir_identity(here) == root_id:
                    scan["contains_workspace"] = True
            except OSError:
                pass
        if "tools" in dirnames and _is_installation(here):
            scan["installations"].append(_rel(source, here))
        kept = []
        for name in sorted(dirnames):
            if (here / name).is_symlink():
                scan["skipped"].append({"rel": _rel(source, here / name), "kind": "symlink"})
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            p = here / name
            rel = _rel(source, p)
            try:
                st = os.lstat(str(p))
            except OSError as exc:
                scan["skipped"].append({"rel": rel, "kind": "unreadable", "detail": _reason(exc)})
                continue
            if stat.S_ISLNK(st.st_mode):
                scan["skipped"].append({"rel": rel, "kind": "symlink"})
            elif not stat.S_ISREG(st.st_mode):
                scan["skipped"].append({"rel": rel, "kind": "special"})
            elif name == ".DS_Store":
                scan["ignored"].append({"rel": rel, "kind": "ds_store"})
                scan["stats"][rel] = (st.st_size, st.st_mtime_ns)
            else:
                files.append((p, rel, st))
    if scan["contains_workspace"] or scan["installations"]:
        return scan
    for p, rel, st in files:
        try:
            digest = _sha256_regular(p)
        except OSError as exc:
            scan["skipped"].append({"rel": rel, "kind": "unreadable", "detail": _reason(exc)})
            continue
        scan["entries"].append({"rel": rel, "bytes": st.st_size, "mtime": _iso(st.st_mtime),
                                "sha256": digest})
        scan["stats"][rel] = (st.st_size, st.st_mtime_ns)
    return scan


def inventory(source_dir):
    """Flat inventory of a folder: ([{rel, bytes, mtime, sha256}], anomalies).
    No link is followed nor copied, a special file is never opened, `.DS_Store`
    is ignored; links, special and unreadable items are listed as anomalies."""
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        return [], ["source folder missing: %s" % source_dir]
    scan = _scan_source(source_dir)
    return scan["entries"], [_skipped_text(s) for s in scan["skipped"]]


def _existing_hashes(tree, exclude=()):
    """{sha256: rel} for regular files already present under `tree` (first in
    sorted order). Partial copies and the paths in `exclude` (the mutable
    move index) never serve as references."""
    out = {}
    tree = Path(tree)
    if not tree.is_dir() or tree.is_symlink():
        return out
    for dirpath, dirnames, filenames in os.walk(str(tree), followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            if name == ".DS_Store" or name.endswith(PARTIAL_SUFFIX):
                continue
            p = Path(dirpath) / name
            rel = p.relative_to(tree).as_posix()
            if rel in exclude:
                continue
            digest = _regular_sha(p)
            if digest:
                out.setdefault(digest, rel)
    return out


def classify(rel):
    """Mechanical classification of an archive entry by its form only (a
    name or a date never decides usefulness)."""
    low = rel.lower()
    if low.endswith(".pine"):
        return "source-return-point"
    if low.endswith((".zip", ".tar.gz", ".tgz")):
        return "archive"
    if "manifest" in low and low.endswith(".txt"):
        return "manifest"
    if low.endswith((".md", ".txt", ".json")):
        return "document"
    return "other"


def _inventory_digest(entries):
    rows = sorted([e["rel"], e["bytes"], e["sha256"]] for e in entries)
    return core.sha256_bytes(core.canonical_json(rows).encode("utf-8"))


def _plan_id(plan):
    basis = {"source": plan["source"], "source_real": plan["source_real"],
             "source_identity": plan["source_identity"], "created_at": plan["created_at"],
             "inventory_sha256": plan["inventory_sha256"], "target": plan["target"]}
    return core.sha256_bytes(core.canonical_json(basis).encode("utf-8"))[:16]


def plan_import(root, source_dir, target_rel="docs/maintenance/archives"):
    """Read-only plan: what gets copied, what is an exact duplicate (kept once
    with references), what already exists in the workspace. A refusal is a
    report carrying `ok: false` and `error`, never an exception."""
    try:
        return _plan_import(Path(root), source_dir, target_rel)
    except Exception as exc:  # a report, never a trace
        return {"ok": False, "error": "plan failed: %s: %s" % (type(exc).__name__, exc)}


def _plan_import(root, source_dir, target_rel):
    source = os.path.abspath(str(source_dir))  # absolute, links NOT resolved
    err, target = _check_target(root, target_rel)
    if err:
        return {"ok": False, "error": err, "source": source}
    problem = _source_relation_problem(root, source)
    if problem:
        return {"ok": False, "error": problem, "source": source}
    scan = _scan_source(source, root_id=_dir_identity(root))
    if scan["contains_workspace"]:
        return {"ok": False, "source": source,
                "error": "the source CONTAINS the workspace (refused): %s" % source}
    if scan["installations"]:
        return {"ok": False, "source": source,
                "error": "the source contains a PWS installation (%s) — refused: %s"
                         % (", ".join(scan["installations"][:3]), source)}
    archives_in_docs = ARCHIVES_REL.relative_to("docs/maintenance").as_posix()
    existing = _existing_hashes(root / "docs" / "maintenance",
                                exclude={archives_in_docs + "/MANIFEST.json",
                                         archives_in_docs + "/INDEX.md"})
    reserved = {(ARCHIVES_REL / "MANIFEST.json").as_posix().casefold(),
                (ARCHIVES_REL / "INDEX.md").as_posix().casefold()}
    plan = {"format": PLAN_FORMAT, "ok": True, "created_at": _now_iso(),
            "source": source, "source_real": str(Path(source).resolve()),
            "source_identity": _dir_identity(source), "target": target, "entries": [],
            "anomalies": [_skipped_text(s) for s in scan["skipped"]],
            "skipped": scan["skipped"], "ignored": scan["ignored"], "blocking": [],
            "total_bytes": 0, "copy_bytes": 0,
            "counts": {"copy": 0, "duplicate_in_source": 0, "already_in_workspace": 0}}
    seen, destinations = {}, {}
    hint = "import into a sub-folder (--target %s/<name>)" % ARCHIVES_REL.as_posix()
    for e in scan["entries"]:
        item = dict(e)
        item["classification"] = classify(e["rel"])
        plan["total_bytes"] += e["bytes"]
        if e["sha256"] in seen:
            item["action"] = "duplicate_in_source"
            item["same_as"] = seen[e["sha256"]]
            plan["counts"]["duplicate_in_source"] += 1
        elif e["sha256"] in existing:
            item["action"] = "already_in_workspace"
            item["same_as"] = "docs/maintenance/" + existing[e["sha256"]]
            plan["counts"]["already_in_workspace"] += 1
        else:
            dest = (Path(target) / e["rel"]).as_posix()
            item["action"] = "copy"
            item["destination"] = dest
            plan["counts"]["copy"] += 1
            plan["copy_bytes"] += e["bytes"]
            seen[e["sha256"]] = dest
            key = dest.casefold()
            if key in reserved:
                plan["blocking"].append("%s would overwrite the archives move index %s — %s"
                                        % (e["rel"], dest, hint))
            elif key in destinations:
                plan["blocking"].append("%s and %s share the destination %s"
                                        % (destinations[key], e["rel"], dest))
            elif os.path.lexists(str(root / dest)):
                plan["blocking"].append("%s: the destination %s already exists with a "
                                        "different content — %s" % (e["rel"], dest, hint))
            destinations[key] = e["rel"]
        plan["entries"].append(item)
    if not plan["entries"]:
        plan["blocking"].append("nothing to import: the source holds no regular file to archive")
    plan["inventory_sha256"] = _inventory_digest(plan["entries"])
    plan["plan_id"] = _plan_id(plan)
    if plan["blocking"]:
        plan["ok"] = False
        more = len(plan["blocking"]) - 3
        plan["error"] = "plan refused: " + "; ".join(plan["blocking"][:3]) + (
            " (+%d more)" % more if more > 0 else "")
    return plan


def _plan_error(root, plan, for_mutation):
    """Structural refusal reason for a plan read from disk, or None. Import and
    removal (`for_mutation`) accept only the current plan format, bound to
    its source folder and inventory; verification also reads older plans."""
    if not isinstance(plan, dict):
        return "invalid plan (not a JSON object)"
    if plan.get("error"):
        return "refused plan: %s" % plan["error"]
    if plan.get("blocking"):
        return "the plan carries blocking anomalies: %s" % "; ".join(map(str, plan["blocking"]))
    current = plan.get("format") == PLAN_FORMAT
    if for_mutation and not current:
        return ("plan written by an older version or of an unknown format (not bound to its "
                "source folder) — run archives-plan again")
    err, target = _check_target(root, plan.get("target"))
    if err:
        return err
    if not isinstance(plan.get("source"), str) or not plan["source"]:
        return "invalid plan: no source folder"
    entries = plan.get("entries")
    if not isinstance(entries, list) or not entries:
        return "the plan lists no entry — nothing to import or verify (check the source path)"
    copy_destinations = set()
    for e in entries:
        if not isinstance(e, dict):
            return "invalid plan entry: %r" % (e,)
        rel, sha, size, action = e.get("rel"), e.get("sha256"), e.get("bytes"), e.get("action")
        if (not isinstance(rel, str) or not rel or Path(rel).is_absolute()
                or ".." in Path(rel).parts or not isinstance(sha, str) or len(sha) != 64
                or not set(sha) <= _HEX or not isinstance(size, int) or size < 0
                or action not in ACTIONS):
            return "invalid plan entry: %s" % (rel,)
        if action == "copy":
            if e.get("destination") != (Path(target) / rel).as_posix():
                return "invalid plan entry: %s (destination outside the planned target)" % rel
            copy_destinations.add(e["destination"])
    for e in entries:
        ref = e.get("same_as")
        if e["action"] == "duplicate_in_source" and ref not in copy_destinations:
            return "invalid plan entry: %s (duplicate of no copied entry)" % e["rel"]
        if e["action"] == "already_in_workspace" and (
                not isinstance(ref, str) or not ref.startswith("docs/maintenance/")
                or ".." in Path(ref).parts):
            return "invalid plan entry: %s (reference outside docs/maintenance)" % e["rel"]
    if current:
        for key in ("source_real", "source_identity", "created_at", "inventory_sha256", "plan_id"):
            if key not in plan:
                return "invalid plan: %s missing" % key
        if _inventory_digest(entries) != plan["inventory_sha256"] or _plan_id(plan) != plan["plan_id"]:
            return ("the plan file was altered after archives-plan (fingerprint mismatch) — "
                    "run archives-plan again")
    return None


STALE_PLAN = ("the source folder is not the one inventoried by the plan (replaced, recreated "
              "or remounted since) — stale plan refused, nothing done; run archives-plan again")


def _source_matches_plan(source, plan):
    try:
        return (_dir_identity(source) == plan["source_identity"]
                and str(Path(source).resolve()) == plan["source_real"])
    except OSError:
        return False


def _with_archive_lock(root, action):
    """Serialize archive writers (import, removal) of one workspace."""
    if not core.runtime_tree_is_real(root, MAINTENANCE_REL.parts):
        return {"ok": False, "error": "runtime tree is a symlink or escapes the workspace — "
                                      "archive operation refused"}
    try:
        with core.file_lock(root / MAINTENANCE_REL / "archives.lock", timeout=0.5):
            return action()
    except TimeoutError:
        return {"ok": False, "error": "another archive operation holds the lock — nothing done"}


def execute_import(root, plan):
    """Copy planned entries (each verified by SHA-256 before it appears),
    then record the import in the cumulative MANIFEST.json and INDEX.md.
    Never deletes the source. A refusal is a report, never an exception."""
    try:
        return _execute_import(Path(root), plan)
    except Exception as exc:  # a report, never a trace
        return {"ok": False, "error": "import interrupted: %s: %s" % (type(exc).__name__, exc)}


def _execute_import(root, plan):
    err = _plan_error(root, plan, for_mutation=True)
    if err:
        return {"ok": False, "error": err}
    source = Path(plan["source"])
    problem = _source_relation_problem(root, source)
    if problem:
        return {"ok": False, "error": problem}
    if not _source_matches_plan(source, plan):
        return {"ok": False, "error": STALE_PLAN}
    return _with_archive_lock(root, lambda: _copy_and_index(root, plan, source))


def _copy_and_index(root, plan, source):
    manifest, merr = _load_manifest(root)
    if merr:
        return {"ok": False, "error": merr}
    target = root / plan["target"]
    target.mkdir(parents=True, exist_ok=True)
    if not core.runtime_tree_is_real(root, Path(plan["target"]).parts):
        return {"ok": False, "error": "target crosses a symbolic link — nothing copied"}
    copied, failures = [], []
    for item in plan["entries"]:
        if item["action"] != "copy":
            continue
        dst = root / item["destination"]
        if not core.is_within(target, dst):
            failures.append("%s: destination escapes the archive folder" % item["rel"])
            continue
        if os.path.lexists(str(dst)):
            if _regular_sha(dst) == item["sha256"]:
                copied.append(item["rel"])
            else:
                failures.append("%s: destination exists with different content" % item["rel"])
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not core.is_within(target, dst.parent):
                failures.append("%s: destination escapes the archive folder" % item["rel"])
                continue
            problem = _copy_verified(source / item["rel"], dst, item["sha256"])
        except OSError as exc:
            problem = "copy failed (%s)" % _reason(exc)
        if problem:
            failures.append("%s: %s" % (item["rel"], problem))
            continue
        copied.append(item["rel"])
    _record_import(manifest, plan, failures)
    folder = root / ARCHIVES_REL
    core.atomic_write_json(folder / "MANIFEST.json", manifest)
    _write_index(folder, manifest)
    return {"ok": not failures, "copied": len(copied), "failures": failures,
            "manifest": str(folder / "MANIFEST.json"), "import_id": plan["plan_id"]}


def _copy_verified(src, dst, expected_sha):
    """Copy one regular file through a partial file next to its destination;
    the destination appears only once the copied bytes match the planned
    SHA-256 (an interrupted copy never leaves a truncated archive in place).
    Returns None or the failure reason."""
    partial = dst.parent / ("." + dst.name + PARTIAL_SUFFIX)
    fd_in = os.open(str(src), os.O_RDONLY | _OPEN_NOFOLLOW | _OPEN_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd_in).st_mode):
            return "no longer a regular file in the source"
        h = hashlib.sha256()
        fd_out = os.open(str(partial), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _OPEN_NOFOLLOW,
                         0o644)
        try:
            with os.fdopen(fd_out, "wb") as out:
                with os.fdopen(fd_in, "rb", closefd=False) as inp:
                    for chunk in iter(lambda: inp.read(1 << 20), b""):
                        h.update(chunk)
                        out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            _unlink_quietly(partial)
            raise
    finally:
        os.close(fd_in)
    if h.hexdigest() != expected_sha:
        _unlink_quietly(partial)
        return "content changed since the plan — nothing installed; run archives-plan again"
    if _regular_sha(partial) != expected_sha:
        _unlink_quietly(partial)
        return "hash mismatch after copy — nothing installed"
    try:
        shutil.copystat(str(src), str(partial), follow_symlinks=False)
    except OSError:
        pass
    if os.path.lexists(str(dst)):
        _unlink_quietly(partial)
        return "destination appeared during the import — nothing replaced"
    os.replace(str(partial), str(dst))
    return None


def _empty_manifest():
    return {"format": MANIFEST_FORMAT, "note": MANIFEST_NOTE,
            "archives_root": ARCHIVES_REL.as_posix(), "imports": [], "entries": []}


def _index_is_ours(path):
    try:
        if not stat.S_ISREG(os.lstat(str(path)).st_mode):
            return False
        with open(str(path), encoding="utf-8") as f:
            return f.readline().rstrip("\n") == INDEX_TITLE
    except (OSError, UnicodeDecodeError):
        return False


def _load_manifest(root):
    """(cumulative manifest, error). A single-import manifest written before
    the cumulative format becomes the first import record; a foreign,
    unreadable or unknown index is never overwritten nor rebuilt from nothing."""
    folder = Path(root) / ARCHIVES_REL
    mpath, ipath = folder / "MANIFEST.json", folder / "INDEX.md"
    if os.path.lexists(str(ipath)) and not _index_is_ours(ipath):
        return None, ("%s exists and is not a PWS move index — refusing to overwrite it"
                      % (ARCHIVES_REL / "INDEX.md").as_posix())
    if not os.path.lexists(str(mpath)):
        if os.path.lexists(str(ipath)):
            return None, ("INDEX.md exists without MANIFEST.json — restore the manifest (Git "
                          "history) before any import; the move index is never rebuilt from nothing")
        return _empty_manifest(), None
    if mpath.is_symlink() or not mpath.is_file():
        return None, "MANIFEST.json is not a regular file — refusing to overwrite it"
    data, err = core.read_json(mpath)
    if err or not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return None, ("MANIFEST.json unreadable or invalid (%s) — refusing to overwrite the move "
                      "index" % (err or "unexpected content"))
    if data.get("format") == MANIFEST_FORMAT and isinstance(data.get("imports"), list):
        return data, None
    if "format" in data:
        return None, "MANIFEST.json has an unknown format (%r) — refusing to overwrite it" % (
            data.get("format"),)
    iid = "legacy-%s" % (data.get("imported_at") or "unknown")
    manifest = _empty_manifest()
    manifest["imports"].append({
        "import_id": iid, "imported_at": data.get("imported_at"),
        "source_folder": data.get("source_folder"),
        "target": data.get("target") or ARCHIVES_REL.as_posix(),
        "anomalies": data.get("anomalies") or [], "failures": data.get("failures") or [],
        "plan_format": 1})
    manifest["entries"] = [dict(e, import_id=iid) for e in data["entries"] if isinstance(e, dict)]
    return manifest, None


def _record_import(manifest, plan, failures):
    """Add (or refresh, for the same plan) one import record; the entries of
    every other import stay listed, in import order."""
    iid = plan["plan_id"]
    now = _now_iso()
    records = manifest["imports"]
    previous = next((r for r in records if isinstance(r, dict) and r.get("import_id") == iid), None)
    record = {"import_id": iid,
              "imported_at": previous.get("imported_at") or now if previous else now,
              "source_folder": plan["source"], "source_real": plan["source_real"],
              "target": plan["target"], "plan_created_at": plan["created_at"],
              "inventory_sha256": plan["inventory_sha256"], "counts": plan.get("counts"),
              "anomalies": plan.get("anomalies") or [], "failures": failures,
              "plan_format": PLAN_FORMAT}
    if previous:
        record["last_run_at"] = now
        records[records.index(previous)] = record
    else:
        records.append(record)
    by_import = {}
    for e in manifest["entries"]:
        by_import.setdefault(e.get("import_id"), []).append(e)
    by_import[iid] = [dict(e, import_id=iid) for e in plan["entries"]]
    order = [r.get("import_id") for r in records if isinstance(r, dict)]
    known = set(order)
    manifest["entries"] = ([e for i in order for e in by_import.get(i, [])]
                           + [e for i, es in by_import.items() if i not in known for e in es])


def _md(value):
    return str(value).replace("|", "\\|")


def _write_index(folder, manifest):
    lines = [INDEX_TITLE, "",
             "Ces archives locales ne remplacent pas une sauvegarde indépendante du disque. "
             "Les rapports historiques conservent leurs chemins d'origine : cet index "
             "cumulatif (une section par import) permet de les résoudre. / These local "
             "archives do not replace an off-disk backup; historical reports keep their "
             "original paths — resolve them with this cumulative index (one section per "
             "import).", ""]
    by_import = {}
    for e in manifest["entries"]:
        by_import.setdefault(e.get("import_id"), []).append(e)
    for rec in manifest["imports"]:
        iid = rec.get("import_id")
        lines += ["## Import %s" % (rec.get("imported_at") or "?"), "",
                  "Source d'origine / original source: `%s`" % rec.get("source_folder"),
                  "Importé le / imported at: %s" % rec.get("imported_at"),
                  "Identifiant / import id: `%s`" % iid, "",
                  "| Chemin d'origine / original path | Action | Destination ou référence "
                  "| SHA-256 | Octets | Classification |",
                  "|---|---|---|---|---|---|"]
        for e in by_import.get(iid, []):
            dest = e.get("destination") or e.get("same_as") or ""
            lines.append("| `%s` | %s | `%s` | `%s…` | %s | %s |" % (
                _md(e.get("rel")), e.get("action"), _md(dest), str(e.get("sha256", ""))[:16],
                e.get("bytes"), e.get("classification", "")))
        if rec.get("anomalies"):
            lines += ["", "### Anomalies", ""] + ["- %s" % a for a in rec["anomalies"]]
        if rec.get("failures"):
            lines += ["", "### Échecs / failures", ""] + ["- %s" % f for f in rec["failures"]]
        lines.append("")
    core.atomic_write_text(folder / "INDEX.md", "\n".join(lines).rstrip("\n") + "\n")


def verify_import(root, plan):
    """Every entry of the plan is either copied (hash verified) or referenced
    by an existing file with the same hash, and (current plan format) the
    cumulative move index records the import without failure. Returns
    (complete, problems); never raises."""
    try:
        return _verify_import(Path(root), plan)
    except Exception as exc:  # a report, never a trace
        return False, ["verification interrupted: %s: %s" % (type(exc).__name__, exc)]


def _verify_import(root, plan):
    err = _plan_error(root, plan, for_mutation=False)
    if err:
        return False, [err]
    problems = []
    archives = root / ARCHIVES_REL
    docs_maintenance = root / "docs" / "maintenance"
    for item in plan["entries"]:
        if item["action"] == "copy":
            dst = root / item["destination"]
            if not core.is_within(archives, dst) or _regular_sha(dst) != item["sha256"]:
                problems.append("%s: copy missing or hash differs" % item["rel"])
        elif item["action"] == "already_in_workspace":
            ref = root / item["same_as"]
            if not core.is_within(docs_maintenance, ref) or _regular_sha(ref) != item["sha256"]:
                problems.append("%s: workspace reference %s missing or changed"
                                % (item["rel"], item["same_as"]))
        else:
            if _regular_sha(root / item["same_as"]) != item["sha256"]:
                problems.append("%s: kept duplicate %s missing or changed"
                                % (item["rel"], item["same_as"]))
    if plan.get("format") == PLAN_FORMAT:
        manifest, merr = _load_manifest(root)
        record = None if merr else next(
            (r for r in manifest["imports"] if r.get("import_id") == plan["plan_id"]), None)
        if merr:
            problems.append("move index unreadable: %s" % merr)
        elif record is None:
            problems.append("the move index (MANIFEST.json) does not record this import — "
                            "run archives-import")
        elif record.get("failures"):
            problems.append("the move index records failures for this import: %s"
                            % "; ".join(map(str, record["failures"][:3])))
    return not problems, problems


def remove_source(root, plan, yes=False):
    """Delete the external source folder ONLY after a complete verification
    of its CURRENT content AND an explicit confirmation (`yes`) given by the
    holder for THIS folder (importing never authorizes the deletion by
    itself). Only the files verified at that moment are deleted, one by one,
    then the emptied folders; anything else is kept."""
    try:
        return _remove_source(Path(root), plan, yes)
    except Exception as exc:  # a report, never a trace
        return {"ok": False, "error": "removal interrupted: %s: %s — only files verified as "
                                      "archived may have been deleted; everything else is kept"
                                      % (type(exc).__name__, exc)}


def _remove_source(root, plan, yes):
    err = _plan_error(root, plan, for_mutation=True)
    if err:
        return {"ok": False, "error": "%s — source kept" % err}
    source = Path(plan["source"])
    problem = _source_relation_problem(root, source)
    if problem:
        return {"ok": False, "error": "%s — source kept" % problem}
    if not _source_matches_plan(source, plan):
        return {"ok": False, "error": STALE_PLAN}
    return _with_archive_lock(root, lambda: _verify_then_remove(root, plan, source, yes))


def _inventory_changes(entries, scan):
    """Blocking differences between the plan and the CURRENT source, plus the
    planned files already absent (archived, nothing left to lose)."""
    planned = {e["rel"]: e for e in entries}
    current = {e["rel"]: e for e in scan["entries"]}
    blocking = {}
    new = sorted(set(current) - set(planned))
    modified = sorted(r for r in set(planned) & set(current)
                      if (planned[r]["sha256"], planned[r]["bytes"])
                      != (current[r]["sha256"], current[r]["bytes"]))
    not_verifiable = [_skipped_text(s) for s in scan["skipped"]]
    for key, value in (("new_not_archived", new), ("modified_since_plan", modified),
                       ("not_verifiable", not_verifiable)):
        if value:
            blocking[key] = value
    return blocking, sorted(set(planned) - set(current))


def _verify_then_remove(root, plan, source, yes):
    scan = _scan_source(source, root_id=_dir_identity(root))
    if scan["contains_workspace"] or scan["installations"]:
        return {"ok": False, "error": "the source now contains the workspace or a PWS "
                                      "installation — source kept"}
    changes, absent = _inventory_changes(plan["entries"], scan)
    if changes:
        return {"ok": False, "changes": changes,
                "error": "the CURRENT content of the source is not the verified one — source "
                         "kept (handle the listed items, then plan and import again)"}
    complete, problems = _verify_import(root, plan)
    if not complete:
        return {"ok": False, "error": "verification incomplete — source kept",
                "problems": problems}
    n_files = len(scan["entries"])
    n_bytes = sum(e["bytes"] for e in scan["entries"])
    if not yes:
        return {"ok": False, "verified": True, "would_remove": str(source),
                "would_remove_resolved": str(source.resolve()), "files": n_files,
                "bytes": n_bytes, "already_absent": absent,
                "error": "refused without --yes — the current content of %s (%d files, %d "
                         "bytes) was re-inventoried and every file is archived and verified; "
                         "deleting this folder needs the holder's explicit authorization for "
                         "this folder" % (source, n_files, n_bytes)}
    return _delete_verified(source, scan)


def _delete_verified(source, scan):
    """Delete exactly the files of the verified inventory (and the ignored
    `.DS_Store`) when unchanged since, then the emptied folders, deepest
    first. Anything that appeared or changed meanwhile is kept."""
    removed, removed_bytes, kept = 0, 0, []
    for rel in sorted(scan["stats"]):
        p = source / rel
        try:
            st = os.lstat(str(p))
            if not stat.S_ISREG(st.st_mode) or (st.st_size, st.st_mtime_ns) != scan["stats"][rel]:
                kept.append(rel)
                continue
            os.unlink(str(p))
        except FileNotFoundError:
            continue
        except OSError as exc:
            kept.append("%s (%s)" % (rel, _reason(exc)))
            continue
        removed += 1
        removed_bytes += st.st_size
    for folder in sorted(scan["dirs"], key=lambda d: len(d.parts), reverse=True):
        try:
            os.rmdir(str(folder))
        except OSError:
            continue
    if os.path.lexists(str(source)):
        return {"ok": False, "files_removed": removed, "bytes_removed": removed_bytes,
                "kept": kept[:50],
                "error": "source partially removed: what appeared or changed during the "
                         "removal was kept (nothing unverified was deleted): %s" % source}
    return {"ok": True, "removed": str(source), "files_removed": removed,
            "bytes_removed": removed_bytes}
