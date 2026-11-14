# SPDX-License-Identifier: Apache-2.0
"""Shared mechanical primitives: paths, boundary, hashing, JSON, atomic IO, git.

Single source of low-level facts. Other modules must reuse these helpers and
never re-derive them. All path handling goes through pathlib (paths may
contain spaces); no shell string concatenation.
"""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

MODES = ("manual", "chrome-experimental")
VALIDATION_STATUSES = ("unverified", "in-progress", "passed", "failed", "partial")
SCRIPT_KINDS = ("indicator", "strategy", "library")
DISTRIBUTIONS = ("free-open-source", "paid-closed-source")
# script_kind x distribution matrix (spec section 45.4): library + paid is invalid.
INVALID_KIND_DISTRIBUTION = {("library", "paid-closed-source")}

STANDARD_REL = Path("standards/PINE_SCRIPT_V6_STANDARD.md")
INDEX_REL = Path("standards/INDEX.md")
TRACEABILITY_REL = Path("standards/TRACEABILITY.md")
LOCAL_SETTINGS_REL = Path(".claude/settings.local.json")
RUNTIME_REL = Path(".claude/runtime")
TV_MODE_ENV_KEY = "PWS_TV_VALIDATION_MODE"


def workspace_root():
    """Physical workspace root: the directory containing tools/pws_workspace."""
    return Path(__file__).resolve().parents[2]


def is_within(root, path):
    """True if path's physical resolution stays inside root's physical tree."""
    try:
        real_root = Path(root).resolve()
        real_path = Path(path).resolve()
    except OSError:
        return False
    return real_path == real_root or real_root in real_path.parents


def find_enclosing_git_root(root):
    """Return the path of a git root strictly ABOVE root, or None.

    Spec section 6.1: an enclosing parent repository must stop the tooling
    before mutation and be reported to the holder.
    """
    parent = Path(root).resolve().parent
    while True:
        if (parent / ".git").exists():
            return parent
        if parent == parent.parent:
            return None
        parent = parent.parent


# Safe identifier for filesystem-embedded ids (run_id, slugs used in paths):
# no separators, no traversal, bounded length.
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def is_safe_id(value):
    return isinstance(value, str) and bool(SAFE_ID_RE.match(value)) and ".." not in value


@contextmanager
def file_lock(lock_path, timeout=10.0):
    """Exclusive advisory lock (flock) serializing PWS writers of one target.

    Coordinates ONLY processes that take this lock (all PWS tooling writers).
    An external writer that does not take it (e.g. Claude Code rewriting
    settings.local.json for approvals) is NOT coordinated — callers must
    combine this with freshest-state re-reads, conflict refusal and post-write
    verification, and the residual window is documented in FILE_CONTRACTS.md.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # never through a symbolic link (audit F-12): a linked lock file would
    # create or touch a file outside the workspace — refused (OSError)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError("lock timeout on %s" % lock_path)
                time.sleep(0.02)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def runtime_tree_is_real(root, rel_parts):
    """True when every existing component of root/rel_parts is a real
    directory physically inside root (no symlink anywhere on the chain). A
    symlinked `.claude/`, `runtime/` or deeper folder would route ephemeral
    writes (snapshots, locks, logs) outside the workspace (spec 6.1.5)."""
    root = Path(root)
    probe = root
    for part in rel_parts:
        probe = probe / part
        if probe.is_symlink() or (probe.exists() and not is_within(root, probe)):
            return False
    return True


def iter_paths_within(base):
    """Yield files under base WITHOUT following directory symlinks and
    without ever leaving base's physical tree (spec section 6.1.5)."""
    base = Path(base)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            if is_within(base, p):
                yield p


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj):
    """Canonical JSON text used for hashing and atomic writes."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path):
    """Return (data, error). error is a short diagnostic string or None."""
    p = Path(path)
    if not p.is_file():
        return None, "missing"
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "unreadable: %s" % exc
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, "invalid JSON: %s" % exc


def atomic_write_text(path, text):
    """Write text atomically: temp file in the same directory + os.replace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, str(p))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, obj, indent=2):
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=indent) + "\n"
    atomic_write_text(path, text)


def git(root, *args):
    """Run a git command inside root. Returns (returncode, stdout, stderr).

    Git absent from PATH is a DEGRADED but handled state (never an uncaught
    exception): the call returns a non-zero code with a readable stderr."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root)] + list(args),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return 127, "", "git not available: %s" % exc
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_state(root):
    """Mechanical git facts for root (never mutates). `error` explains a
    degraded state (git missing, not a repository) in plain words."""
    state = {
        "available": False,
        "is_repo": False,
        "branch": None,
        "commit": None,
        "unborn": None,
        "dirty": None,
        "remotes": [],
        "error": None,
    }
    rc, out, err = git(root, "--version")
    if rc != 0:
        state["error"] = ("git is not installed or not on PATH — degraded mode: no local "
                          "history, no worktrees; install Git to restore them (%s)" % err)
        return state
    state["available"] = True
    rc, out, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if rc != 0 or out != "true":
        state["error"] = ("not a git repository — degraded mode: no local history; "
                          "run `git init` inside the workspace root to restore it")
        return state
    state["is_repo"] = True
    rc, out, _ = git(root, "symbolic-ref", "--short", "HEAD")
    state["branch"] = out if rc == 0 else None
    rc, out, _ = git(root, "rev-parse", "--verify", "HEAD")
    if rc == 0:
        state["commit"] = out
        state["unborn"] = False
    else:
        state["commit"] = None
        state["unborn"] = True
    rc, out, _ = git(root, "status", "--porcelain")
    state["dirty"] = bool(out) if rc == 0 else None
    rc, out, _ = git(root, "remote")
    state["remotes"] = [r for r in out.splitlines() if r] if rc == 0 else []
    return state


def list_user_skill_names():
    """Names of personal skills in ~/.claude/skills — existence listing ONLY.

    Narrow, documented exception to the physical-boundary rule (recorded in
    FILE_CONTRACTS.md): the doctor must diagnose skill-name collisions
    (spec section 32.2) and personal skills shadow project skills. This reads
    directory names only — never file contents, never follows further.
    """
    d = Path.home() / ".claude" / "skills"
    if not d.is_dir():
        return []
    names = []
    for child in sorted(d.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            names.append(child.name)
    return names


def precise_now():
    """UTC time with microseconds: orders backups created within the same second."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def backup_order_key(stamp, manifest):
    """Creation order of a backup: its recorded `created_at` (microseconds), or,
    for backups written before 2026-11-13, the second encoded in its stamp
    (`YYYYMMDDTHHMMSSZ-…`)."""
    created = manifest.get("created_at") if isinstance(manifest, dict) else None
    if isinstance(created, str) and created:
        return created
    s = str(stamp)[:16]
    if len(s) == 16 and s[8] == "T":
        return "%s-%s-%sT%s:%s:%s.000000Z" % (s[0:4], s[4:6], s[6:8], s[9:11], s[11:13], s[13:15])
    return ""
