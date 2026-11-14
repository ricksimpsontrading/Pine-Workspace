# SPDX-License-Identifier: Apache-2.0
"""Build the public distribution of Pine Workspace from the common core.

One implementation for both the personal installation and the
distribution: the distribution is GENERATED from the same files, through an
explicit allow-list — never a diverging copy. Excluded by construction:
products (`scripts/`), `docs/maintenance/` (reports, archives, evidence),
`.claude/runtime/`, personal configuration (`pws.config.json`,
`.claude/settings.local.json`), bootstrap/corrective evidence of the
personal installation, `node_modules`, lock files, macOS artefacts.

After the copy, the tree is scanned for personal data in three distinct
families: personal absolute paths of any account, explicit traces of the
account running the build (only in personal contexts — never the bare word,
so a common account name does not flag ordinary mentions of that word), and
the identity configured in the workspace. A hit is reported (the build is
marked `clean: False`) rather than silently shipped.

Target safety (corrected 2026-11-13, audit A-01): the target is CLASSIFIED
before anything is written or deleted. It must be a new or empty folder, or a
genuine previous PWS distribution build replaced only with --force. A marker
alone never authorizes a deletion: a genuine build holds exactly the files its
marker lists and no sign of an installation or of the development upstream
(pws.config.json, scripts/, .git, .claude/runtime, docs/maintenance, local
settings). The only unlisted files such a build may hold are the Python
bytecode files `*.pyc` of a `__pycache__/` folder under `tools/` (same rule as
the maintenance of the workspace); any other unlisted file (`*.lock`, a note
in `__pycache__/`, `.DS_Store`…) refuses the replacement, and one found at the
removal keeps the old tree, reported — never deleted silently (review
RS-06). The target may neither be nor contain the source workspace, nor be
inside it, nor be a symbolic link — folders compared by physical identity
(device, inode), so another case on a case-insensitive volume, a symbolic
link or a firmlink is still recognized (review RS-05). A replaced build is
swapped atomically: the new tree is built beside it, then renamed into place,
and the old tree is removed only after it has been re-checked.

Content: when the source is a Git repository with at least one commit, only
files tracked by Git are shipped (untracked or ignored files are reported,
never copied); a core file of FILE_MAP that Git does not track (the licence
texts included: `tools/pine_exec/LICENSE`, `docs/licensing/LICENSING.md`)
fails the build. Otherwise every file of the allow-listed folders is copied.
Shipped files get normalized permissions: 0644, or 0755 when the source file
is executable by its owner — never the local mode of the source (a 0600 file
is not shipped as 0600; review m9). A build is `ok` only when nothing
excluded leaked and the personal-data scan is clean (audit I-11).
"""
import datetime
import os
import re
import shutil
import stat
from pathlib import Path

from . import core, version

MARKER = "PWS_DISTRIBUTION.json"

# (source relative path, destination relative path) — files
FILE_MAP = (
    ("CLAUDE.md", "CLAUDE.md"),
    ("README.md", "README.md"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    (".gitignore", ".gitignore"),
    (".worktreeinclude", ".worktreeinclude"),
    ("install.py", "install.py"),
    ("INSTALL.md", "INSTALL.md"),
    ("docs/licensing/PWS_LICENSE_Apache-2.0.txt", "LICENSE"),
    ("docs/licensing/PWS_NOTICE.md", "NOTICE"),
    ("docs/licensing/THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
    (".claude/settings.json", ".claude/settings.json"),
    ("standards/PINE_SCRIPT_V6_STANDARD.md", "standards/PINE_SCRIPT_V6_STANDARD.md"),
    ("standards/INDEX.md", "standards/INDEX.md"),
    ("standards/TRACEABILITY.md", "standards/TRACEABILITY.md"),
    ("docs/architecture/BOOTSTRAP_SPEC.md", "docs/architecture/BOOTSTRAP_SPEC.md"),
    ("docs/architecture/ARCHITECTURE.md", "docs/architecture/ARCHITECTURE.md"),
    ("docs/architecture/FILE_CONTRACTS.md", "docs/architecture/FILE_CONTRACTS.md"),
    ("docs/architecture/OPERATIONS.md", "docs/architecture/OPERATIONS.md"),
    ("docs/architecture/MIGRATION.md", "docs/architecture/MIGRATION.md"),
    ("tools/__init__.py", "tools/__init__.py"),
    ("tools/pine_exec/runner.mjs", "tools/pine_exec/runner.mjs"),
    ("tools/pine_exec/normalize.mjs", "tools/pine_exec/normalize.mjs"),
    ("tools/pine_exec/datasets.mjs", "tools/pine_exec/datasets.mjs"),
    ("tools/pine_exec/fingerprint.mjs", "tools/pine_exec/fingerprint.mjs"),
    ("tools/pine_exec/package.json", "tools/pine_exec/package.json"),
    ("tools/pine_exec/package-lock.json", "tools/pine_exec/package-lock.json"),
    ("tools/pine_exec/LICENSE", "tools/pine_exec/LICENSE"),            # adapter: GNU AGPL v3 only
    ("tools/pine_exec/PINETS_LICENSE", "tools/pine_exec/PINETS_LICENSE"),
    ("tools/pine_exec/PROVENANCE.json", "tools/pine_exec/PROVENANCE.json"),
    # licensing map of the package, referred to by NOTICE: a core file (fails the build when Git does not
    # track it, review m7), copied once — the walk of docs/licensing below skips it
    ("docs/licensing/LICENSING.md", "docs/licensing/LICENSING.md"),
)
# directories copied recursively (no symlink followed)
DIR_MAP = (
    (".claude/rules", ".claude/rules"),
    (".claude/skills", ".claude/skills"),
    (".claude/agents", ".claude/agents"),
    ("docs/licensing", "docs/licensing"),
    ("tools/pws_workspace", "tools/pws_workspace"),
    ("tools/tests", "tools/tests"),
    ("tools/pine_exec/calibration", "tools/pine_exec/calibration"),
)
SKIP_NAMES = {"__pycache__", ".DS_Store", "node_modules"}
SKIP_SUFFIXES = (".pyc", ".lock")
NEVER_SHIP = ("scripts", "docs/maintenance", ".claude/runtime", ".claude/settings.local.json",
              "pws.config.json", "docs/architecture/BOOTSTRAP_REPORT.md",
              "docs/architecture/CORRECTIVE_REPORT_2026-09-05.md")

# files allowed to mention the project's own attribution
ATTRIBUTION_ALLOWED = {"NOTICE", "LICENSE", "THIRD_PARTY_NOTICES.md"}


# ---- personal-data scan: three distinct families (rule revised 2026-11-07) ----
# 1. personal absolute paths of ANY account: /Users/<x>/…, /home/<x>/…, X:\Users\<x>\…
# 2. explicit traces of THE system account running the build — only in personal
#    contexts: a complete path component, a home shorthand (~<account>), a
#    user@host form, an account environment assignment. The bare word is never
#    a hit on its own: a common account name (agent, admin, user…) must not turn
#    every ordinary mention of that word in code or documentation into a leak.
# 3. the identity deliberately configured in THIS workspace (copyright holder,
#    aliases, compact variants): distinctive by choice, searched anywhere.
PATH_PATTERNS = (
    ("personal-path", r"/Users/[A-Za-z0-9._-]+/"),
    ("personal-path", r"/home/[A-Za-z0-9._-]+/"),
    ("personal-path", r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
)
ACCOUNT_CONTEXTS = (
    r"[/\\]{a}(?=[/\\\s\"'`),;:]|$)",          # complete path component: …/<account>/ or …/<account>
    r"~{a}(?=[/\\\s\"'`),;:]|$)",                # home shorthand: ~<account>
    r"(?<![A-Za-z0-9._-]){a}@[A-Za-z0-9.-]+",        # user@host
    r"\b(?:USER|LOGNAME|USERNAME)\s*[=:]\s*[\"']?{a}\b",   # account environment assignment
)
MIN_ACCOUNT_LEN = 3


def system_account():
    """Name of the account running the build (never a personal literal here)."""
    return Path.home().name


def personal_patterns(root, account=None):
    """(family, regex) patterns that must not appear in a distribution, in the
    three families described above. `account` is the system account name to
    look for in personal contexts (default: the account running the build —
    injectable so tests simulate a deterministic environment instead of
    depending on the real user name); the configured identity comes from
    `pws.config.json` of `root`. This module never carries a personal literal."""
    from . import config
    pats = [(family, re.compile(rx)) for family, rx in PATH_PATTERNS]
    user = system_account() if account is None else account
    if isinstance(user, str) and len(user.strip()) >= MIN_ACCOUNT_LEN:
        a = re.escape(user.strip())
        pats += [("account-trace", re.compile(rx.format(a=a), re.I | re.M)) for rx in ACCOUNT_CONTEXTS]
    ident = config.identity(root)
    for mark in [ident.get("copyright_holder")] + list(ident.get("header_aliases") or []):
        if isinstance(mark, str) and len(mark.strip()) > 2:
            m = mark.strip()
            # case-insensitive (audit I-04): the holder's mark in capitals is the same mark
            pats.append(("configured-identity", re.compile(re.escape(m), re.I)))
            compact = re.sub(r"\s+", "", m)
            if compact != m:
                pats.append(("configured-identity", re.compile(re.escape(compact), re.I)))
    return pats


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SHIPPED_FILE_MODE = 0o644
SHIPPED_EXEC_MODE = 0o755


def shipped_mode(source_mode):
    """Permissions of a shipped file (review m9): 0755 when the source file is
    executable by its owner (the bit Git records), else 0644 — never the
    local mode itself (a 0600 file is shipped readable, a 0777 one is not
    shipped writable by all)."""
    return SHIPPED_EXEC_MODE if source_mode & stat.S_IXUSR else SHIPPED_FILE_MODE


def _ship(src, dst):
    """Copy one file into the distribution, with normalized permissions."""
    shutil.copy2(str(src), str(dst))
    os.chmod(str(dst), shipped_mode(os.stat(str(src)).st_mode))


def _copy_tree(src, dst, copied, root=None, tracked=None, untracked=None, skip=()):
    """Copy an allow-listed folder (no symbolic link followed). `skip` holds
    the destination paths already shipped by FILE_MAP at the same place:
    never copied twice (a file FILE_MAP ships under another name, such as
    docs/licensing/PWS_NOTICE.md → NOTICE, is still copied here)."""
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_NAMES
                             and not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES) or p.is_symlink():
                continue
            rel = p.relative_to(src)
            target = dst / rel
            if target in skip:
                continue
            if tracked is not None:
                rel_root = p.relative_to(root).as_posix()
                if rel_root not in tracked:
                    if untracked is not None:
                        untracked.append(rel_root)
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            _ship(p, target)
            copied.append(target)


# Signs that a folder holds an installation, the development upstream or their
# data: their presence forbids any deletion by `build-distribution`, whatever
# marker the folder also carries (audit A-01).
INSTALLATION_SIGNS = ("pws.config.json", "scripts", ".git", ".claude/runtime", ".claude/settings.local.json",
                      "docs/maintenance", "CLAUDE.local.md")


def _identity(path):
    """(device, inode) of an existing path (links followed), else None."""
    try:
        st = os.stat(str(path))
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def same_or_inside(path, folder):
    """True when `path` is `folder` or lies inside it, as the file system sees
    them (review RS-05): `path` is resolved physically (symbolic links and
    `..`), then it and every existing ancestor are compared to `folder` by
    identity (device, inode) — another case on a case-insensitive volume, a
    symbolic link or a firmlink of the same folder is still recognized."""
    fid = _identity(folder)
    if fid is None:
        return False
    probe = Path(os.path.realpath(str(path)))      # never abspath first: it would fold `link/..` lexically
    while True:
        if _identity(probe) == fid:
            return True
        if probe.parent == probe:
            return False
        probe = probe.parent


def target_relation_problem(root, target):
    """Refusal message when `target` is the source workspace `root`, lies
    inside it or contains it — compared by physical identity — else None.
    Shared by build-distribution and build-release."""
    if same_or_inside(target, root):
        return "target must be outside the source workspace"
    if _identity(target) is not None and same_or_inside(root, target):
        return "target contains the source workspace — refusing"
    return None


def _bytecode_cache_file(rel):
    """`tools/…/__pycache__/<name>.pyc`: the only file a previous build may hold
    without listing it (Python writes it when the build is run) — the rule of
    the maintenance of the workspace, nothing wider (review RS-06)."""
    parts = rel.split("/")
    return (len(parts) >= 3 and parts[0] == "tools" and parts[-2] == "__pycache__"
            and "__pycache__" not in parts[:-2] and parts[-1].endswith(".pyc") and len(parts[-1]) > len(".pyc"))


def _tree_files(target):
    """Relative files of `target` as a build lists them: every file except
    the marker at the top and the bytecode files of a `__pycache__/` under
    tools/ — a `*.lock`, `.DS_Store` or any other unlisted file is returned
    (review RS-06). Symbolic links are returned separately: a genuine build
    never contains one."""
    files, links = set(), []
    for dirpath, dirnames, filenames in os.walk(str(target), followlinks=False):
        for d in list(dirnames):
            if (Path(dirpath) / d).is_symlink():
                links.append((Path(dirpath) / d).relative_to(target).as_posix())
                dirnames.remove(d)
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(target).as_posix()
            if p.is_symlink():
                links.append(rel)
            elif rel != MARKER and not (_bytecode_cache_file(rel) and _is_regular(p)):
                files.add(rel)
    return files, links


def _is_regular(path):
    try:
        return stat.S_ISREG(os.lstat(str(path)).st_mode)
    except OSError:
        return False


def classify_target(root, target):
    """Classify a build target BEFORE any write or deletion. Returns
    (kind, message): kind is 'new', 'empty', 'previous-build' or 'refused'."""
    root, target = Path(root), Path(target)
    if target.is_symlink():
        return "refused", "target is a symbolic link — refusing (choose the real folder)"
    relation = target_relation_problem(root, target)
    if relation:
        return "refused", relation
    if not target.exists():
        return "new", None
    if not target.is_dir():
        return "refused", "target exists and is not a directory"
    entries = [e for e in target.iterdir() if e.name != ".DS_Store"]
    if not entries:
        return "empty", None
    if not (target / MARKER).is_file():
        return "refused", ("target is not empty and is not a PWS distribution build — refusing to overwrite "
                           "an existing project")
    signs = [s for s in INSTALLATION_SIGNS if (target / s).exists() or (target / s).is_symlink()]
    if signs:
        return "refused", ("target holds an installation or its data (%s): a distribution marker never "
                           "authorizes its replacement — choose another folder" % ", ".join(signs))
    marker, err = core.read_json(target / MARKER)
    if err or not isinstance(marker, dict) or not isinstance(marker.get("files"), dict):
        return "refused", "target carries an unreadable %s — refusing to replace it" % MARKER
    files, links = _tree_files(target)
    if links:
        return "refused", "target contains symbolic links (%s) — not a genuine build" % ", ".join(sorted(links)[:5])
    extra = sorted(files - set(marker["files"]))
    if extra:
        return "refused", ("target holds files that are not part of the previous build (%s%s) — refusing to "
                           "replace it: nothing is deleted; move or delete them yourself, or choose another "
                           "folder" % (", ".join(extra[:5]), ", …" if len(extra) > 5 else ""))
    return "previous-build", "previous PWS distribution build present — pass --force to replace it"


def check_target(target, root=None):
    """None when the target is usable as is (new or empty), else a message
    (kept for callers; `classify_target` is the full classification)."""
    kind, message = classify_target(root if root is not None else Path(target).parent / ".pws-no-root", target)
    return None if kind in ("new", "empty") else message


def _tracked_files(root):
    """Set of files tracked by Git (posix relative paths) when `root` is a Git
    repository with at least one commit, else None (walk the allow-list)."""
    import subprocess
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"],
                              capture_output=True, text=True, timeout=30)
        if head.returncode != 0:
            return None
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return {p.decode("utf-8", "surrogateescape") for p in out.stdout.split(b"\0") if p}


def _without_official_references(text):
    """The exact reference to the official repository of the core (its slug,
    therefore every URL that contains it) is public by definition and is
    removed before the scan — an exact identifier, never a bare word: the
    holder's identity outside that reference stays detected."""
    return text.replace(version.OFFICIAL_REPOSITORY, "<official-repository>")


def scan_personal(tree, patterns):
    """Files of the built tree carrying a personal path, an explicit trace of
    the building account or the configured identity (first match per file,
    with its family). The exact official-repository reference is exempt."""
    hits = []
    items = [(it if isinstance(it, tuple) else ("pattern", it)) for it in patterns]
    for p in core.iter_paths_within(tree):
        if (p.name in ATTRIBUTION_ALLOWED and p.parent == Path(tree)) \
                or p.name in ("PWS_NOTICE.md", "PWS_DISTRIBUTION.json"):
            continue
        if p.suffix in (".png", ".jpg", ".jpeg", ".webp", ".zip", ".gz"):
            continue
        try:
            text = _without_official_references(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        for family, rx in items:
            m = rx.search(text)
            if m:
                hits.append({"path": str(p.relative_to(tree)), "family": family,
                             "pattern": rx.pattern, "sample": m.group(0)})
                break
    return hits


def build(root, target, force=False, account=None):
    """Build the distribution into `target`. `account` overrides the system
    account name used by the personal-data scan (tests: simulated environment).
    The target is classified before anything is written or deleted; a genuine
    previous build is replaced only with `force`, by building beside it and
    swapping (the old tree is removed after a second check)."""
    root = Path(root)
    target = Path(target)
    kind, message = classify_target(root, target)
    if kind == "refused" or (kind == "previous-build" and not force):
        return {"ok": False, "clean": False, "error": message, "target": str(target), "target_kind": kind}
    missing = [src for src, _ in FILE_MAP if not (root / src).is_file()]
    missing += [src for src, _ in DIR_MAP if not (root / src).is_dir()]
    if missing:
        return {"ok": False, "clean": False, "error": "source files missing: %s" % ", ".join(missing),
                "target": str(target), "target_kind": kind}
    tracked = _tracked_files(root)
    untracked = []
    unshipped = [src for src, _ in FILE_MAP if tracked is not None and src not in tracked]
    if unshipped:
        return {"ok": False, "clean": False, "target": str(target), "target_kind": kind,
                "error": "core files not tracked by Git: %s — commit them first" % ", ".join(unshipped)}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work = target if kind != "previous-build" else target.parent / (".%s.pws-build-%s" % (target.name, stamp))
    work.mkdir(parents=True, exist_ok=True)
    copied = []
    for src, dst in FILE_MAP:
        d = work / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        _ship(root / src, d)
        copied.append(d)
    shipped = {work / dst for _, dst in FILE_MAP}          # LICENSING.md: FILE_MAP and DIR_MAP, copied once
    for src, dst in DIR_MAP:
        _copy_tree(root / src, work / dst, copied, root=root, tracked=tracked, untracked=untracked,
                   skip=shipped)
    (work / "VERSION").write_text(version.WORKSPACE_VERSION + "\n", encoding="utf-8")
    os.chmod(str(work / "VERSION"), SHIPPED_FILE_MODE)
    copied.append(work / "VERSION")
    # never-ship guard: none of the excluded paths may exist in the result
    leaked = [n for n in NEVER_SHIP if (work / n).exists()]
    hits = scan_personal(work, personal_patterns(root, account=account))
    git = core.git_state(root)
    marker = write_marker(work, version.WORKSPACE_VERSION, extra={
        "source_commit": git.get("commit"),
        "source_dirty": git.get("dirty"),
        "personal_pattern_hits": hits,
    })
    result = {"ok": not leaked and not hits, "clean": not hits and not leaked, "target": str(target),
              "target_kind": kind, "files": len(marker["files"]), "leaked": leaked,
              "personal_pattern_hits": hits, "untracked_not_shipped": sorted(untracked),
              "marker": str(target / MARKER)}
    if kind == "previous-build":
        # swap: the new tree is complete and verified; the old one is re-checked before removal
        old = target.parent / (".%s.pws-old-%s" % (target.name, stamp))
        again, again_msg = classify_target(root, target)
        if again != "previous-build":
            result.update(ok=False, error="target changed during the build (%s) — new build kept at %s, "
                                          "target untouched" % (again_msg, work), new_build=str(work))
            return result
        os.rename(str(target), str(old))
        os.rename(str(work), str(target))
        result["replaced_previous_build"] = True
        files, links = _tree_files(old)
        marker_old, _ = core.read_json(old / MARKER)
        listed = set(marker_old["files"]) if isinstance(marker_old, dict) \
            and isinstance(marker_old.get("files"), dict) else set()
        signs = [s for s in INSTALLATION_SIGNS if os.path.lexists(str(old / s))]
        if not links and listed and files <= listed and not signs:
            shutil.rmtree(str(old))
        else:
            # never deleted silently: kept beside the new build, with what made it unsafe to remove
            why = {"unlisted_files": sorted(files - listed)[:20], "symbolic_links": sorted(links)[:20],
                   "installation_signs": signs, "unreadable_marker": not listed}
            result["previous_build_kept"] = str(old)
            result["previous_build_kept_why"] = why
            result["note"] = ("previous build kept at %s (not removed: it holds files its marker does not list, a "
                              "link or a sign of an installation) — check it, then delete it yourself" % old)
    if not result["clean"] and not result.get("error"):
        result["error"] = ("distribution not clean: %d personal-data hit(s), %d excluded path(s) present — "
                           "nothing may be published from this tree" % (len(hits), len(leaked)))
    return result


def write_marker(target, workspace_version, extra=None):
    """(Re)write the core manifest of a package: every file of the tree except
    the marker itself, with its SHA-256. Also used to refresh a package after
    an edit (tests, release engineering)."""
    target = Path(target)
    files = sorted(str(p.relative_to(target)) for p in core.iter_paths_within(target)
                   if p.is_file() and p.name != MARKER and p.name not in SKIP_NAMES
                   and not p.name.endswith(SKIP_SUFFIXES))
    from . import migration   # local import: the marker declares the steps known by this core
    marker = {
        "workspace_version": workspace_version,
        "built_at": _now(),
        "files": {f: core.sha256_file(target / f) for f in files},
        "excluded_by_construction": list(NEVER_SHIP),
        "platform_support": {"macos": "supported first", "windows": "deferred",
                             "linux": "not verified"},
        # read by the guided update path BEFORE an upgrade: data-migration steps
        # this core knows (an installation announces those not yet recorded) and
        # the public repository whose releases are consulted — both derived
        "migrations": list(migration.STEP_IDS),
        "official_repository": version.OFFICIAL_REPOSITORY,
    }
    marker.update(extra or {})
    core.atomic_write_json(target / MARKER, marker)
    os.chmod(str(target / MARKER), SHIPPED_FILE_MODE)    # shipped like any core file (review m9)
    return marker
