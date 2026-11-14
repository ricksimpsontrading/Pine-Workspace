# SPDX-License-Identifier: Apache-2.0
"""GitHub export workflow — connection status, destinations, export plan,
staging, diff and publication (each step explicit, nothing implicit).

Connection: PWS never stores a token. Authentication relies on the
workstation's own mechanisms (`gh auth` keychain or the git credential
helper); `status` reports whether they are usable, with any token-looking
line filtered out of the displayed output. The git credential helper is
shown by its name only, never with its arguments; an inline helper (`!…`)
or a value carrying a password or a token is never shown (review RS-03).

Content policy (ratified 2026-11-06): an export is built from an ALLOWED
list — never the workspace, never secrets, personal configuration, runtime,
archives, internal tracking, validation evidence; a source whose
`source_visibility` is `closed` never goes to a PUBLIC destination (a
PRIVATE destination may receive it when explicitly configured). A private
folder inside a public repository is NOT assumed possible. The existing
repository is a destination to configure, never restructured automatically.
Details (hardened after the audit of 2026-11-12):
  - only regular files are read and exported: a symbolic link (to a file or
    a folder, inside or outside the product) and any special file are listed
    as excluded with their reason, never followed;
  - allowed documents are matched on their FULL path from the product root
    (`release/README.md`, `docs/<…TUTORIAL…>.md`, `release/<…tutorial…>.md`):
    a deeper folder such as `research/docs/` never matches;
  - a document is exported only when it is UTF-8 text without the draft
    banner, without an unfilled licence-template field (`{{KEY}}` for the
    keys of the licence templates) and without a template block
    (`[[?KEY:…]]`, `[[!KEY:…]]`); TradingView alert placeholders such as
    `{{ticker}}` are ordinary text. The declared source is excluded while it
    still carries such a field (e.g. `© {{YEAR_RANGE}}` in its header);
  - `terms_ref` is exported as the product's terms only when it designates a
    recognized terms document (`release/EULA.md`, `release/FREE_USE_GRANT.md`,
    `release/NOTICE.md`, or a file identical to the current rendering of one
    of those kinds); a recognized terms document that is no longer current
    (the rendering of the recorded fields differs from the file) is reported
    and excluded;
  - towards a PUBLIC destination, a closed-source product exports no Pine
    code: a document that is a copy of its source, reproduces a code line of
    it, or carries a `//@version=` annotation, a declaration statement or a
    ```pine block is excluded; any product's document reproducing three code
    lines (or the whole text) of another closed source is excluded too;
  - the declared source of a product whose source is PUBLIC is judged like a
    document against the OTHER closed sources (review RS-04): when it is a
    copy of one of them or reproduces three of its code lines, it never goes
    to a public destination (excluded, with a warning) and, towards a private
    destination, it is closed content (I-06 check below);
  - two exported files never share a target name (compared without case,
    as on the holder's file system): the plan is refused;
  - an imported script (licence `origin` imported) travels with its original
    legal documents (holder's request of 2026-11-14): the documents the
    holder declared in `license.documents` (LICENSE, COPYING, NOTICE,
    AUTHORS, PATENTS… at the product root, directly under release/ or
    LICENSES/) are exported as they are — same name (`LICENSES/<name>`
    kept), same bytes, encoding and language — never replaced by a PWS
    template nor compared with one. They are never followed through a link,
    never a special file nor a hard link, never larger than 1 MiB, must be
    checkable text (UTF-8, or an ASCII-compatible single-byte text), must not
    carry PWS draft or template syntax, and towards a public destination
    never the Pine code of a closed source. A file with a legal-document name
    is never exported because of its name alone, and never left out silently
    wherever it lies in the product (internal folders excepted): while the
    documents are not declared, a candidate is not declared or cannot be
    declared where it is, or a declared document is missing, altered or
    refused, the plan is refused with the resolution
    (licensing.legal_documents_review). The recorded SPDX identifier alone
    never establishes the documents a redistribution requires.

Binding and revalidation: PLAN.json records the effective destination
(name, repo, visibility, branch, path_prefix, clone URL), the licence axes
and the SHA-256 of every staged file. `export-diff` and `publish` re-read
the configuration and the manifest, recompute the plan in memory and refuse
when the destination, the source visibility or the included files differ
from the plan, or when a staged file was altered: `export-plan` must run
again. The local clone must be a real folder whose `origin` is the
configured clone URL, checked out on the configured branch, without
unpublished local work (uncommitted or untracked change, local commit,
stash); otherwise the operation is refused with the path and the action.
Removing or replacing a destination invalidates its plans (PLAN.json is
renamed PLAN.invalidated.json) and sets a clean clone aside under
`clones/.stale/`; a clone holding unpublished work (or whose state git
cannot establish) is never moved nor deleted: it is marked
(`clones/<name>.STALE.json`), reported, and refused until the holder
handles it. `fetch` sets aside a clean clone of another repository before
cloning. Nothing is ever deleted by these checks, and `--yes` replaces none
of them. `export-diff` writes nothing.

Publication (`publish --yes`) copies the verified staged files into the
verified clone, commits and pushes the configured branch to `origin` —
`git push` stays under the user's permission prompt.

Two distinct checks precede a send, neither replaced by the `private`
declaration, an earlier result or `--yes`:
  1. IDENTITY of the repository the holder authorized — EVERY send, public
     content included (holder's request of 2026-11-14; same mechanism as
     I-06, `_origin_remote`, no second one): the remote rule below. A
     public content may go to a destination declared public or to a private
     repository the holder chose explicitly; GitHub is not queried for it.
  2. PRIVACY required by closed content (I-06, holder's decision of
     2026-11-13): the real visibility below, only when the send carries
     closed content.
`publish` makes both before anything is written into the clone and reads
the remote again right before `git push`: when it changed after the local
commit, nothing is pushed and the result describes the state left on disk
(`state_left`: clone, branch, commit, files, unpublished work, next steps).
Cross-check of 2026-11-14 — what is sent is exactly the plan, and only
there: the identity check also refuses an empty URL entry and any setting
that makes git connect elsewhere than the URL shows or without verifying it
(`core.sshCommand`, `core.gitProxy`, `remote.origin.vcs`,
`http.curloptResolve`, `http.sslVerify` false, the variables `GIT_SSH`,
`GIT_SSH_COMMAND`, `GIT_PROXY_COMMAND`, `GIT_SSL_NO_VERIFY`); a target whose
name differs only by case from an entry of the repository, or that needs a
folder where the repository holds a file, is refused; a file whose bytes git
would change when committing (end-of-line conversion or a filter of
.gitattributes or of the git configuration) is refused before any write; no
hook runs when the clone commits and pushes; the local commit is checked
(one new commit, only the planned paths, each with the exact bytes) before
the push.

Real repository before a closed source is sent (I-06, holder's decision of
2026-11-13). A send carries closed content when one of its files is the
product's closed source, a public source reproducing another product's
closed source, or a document carrying Pine code of a closed source (same
judgement as towards a public destination), the manifests being re-read at
that moment. Such a send is preceded by a check that nothing replaces —
neither the `private` declaration, nor an earlier result, nor `--yes`:
  - remote (made for every send since 2026-11-14, see above): `origin`
    must have exactly one fetch URL and one push URL as git
    really uses them (`git remote get-url [--push] --all origin`: pushurl,
    insteadOf and pushInsteadOf applied), both — like the destination's own
    URL — written EXACTLY in one of the accepted forms of a github.com
    repository URL designating the configured repository:
    `https://github.com/<owner>/<repo>[.git][/]`,
    `git@github.com:<owner>/<repo>[.git]` or
    `ssh://git@github.com/<owner>/<repo>[.git]` (review RS-01: no
    credentials nor any other user part, no port, query, fragment or
    percent-encoding, scheme and host in lower case — a user part holding
    « # » or « ? » made git contact another host than the one read). Several
    URLs, any other form, another host, another repository or a remote git
    cannot read is refused, and the refusal names the host git would really
    contact (read as git reads it: for https, RFC 3986 — the authority ends
    at the first « / », « ? » or « # »);
  - GitHub: `gh repo view https://github.com/<repo> --json
    nameWithOwner,visibility,isPrivate,url`, with the current gh
    authentication (`gh api` is never used), must report the configured
    repository itself (a renamed or transferred repository is refused) as
    PRIVATE with isPrivate true. PUBLIC, INTERNAL, gh absent or not
    authenticated, a repository not found or not visible, an error, an
    invalid or incoherent answer: refused;
  - `export-plan` (offline) announces the checks (`destination_check`, and
    `visibility_check` for closed content); `export-diff` makes them and
    presents the effective repository, the observed visibility and the UTC
    time, with ok=false when publish would refuse; `publish --yes` makes
    them again — never reusing a stored result — as the last step before
    writing into the clone (a refusal writes and pushes nothing), and reads
    the remote again right before `git push`.
Limit: the visibility can change between the check and the push. The check
is made immediately before the push (only local writes and the commit come
in between), with no atomic guarantee from GitHub.
Displayed outputs never show credentials of a URL (`user:token@` masked).
Only a user part made of RFC 3986 userinfo characters inside the authority
is masked: a part git does not read as credentials (a host followed by « # »
or « ? », a « [ », « ] » or « \\ ») is shown as is, so the real host is
never hidden behind `***@`.
"""
import datetime
import fnmatch
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from . import config, core, licensing, profiles, scan

EXPORT_REL = core.RUNTIME_REL / "github-export"
CLONES_DIRNAME = "clones"
STALE_DIRNAME = ".stale"
PLAN_FORMAT = 2
TOKEN_LINE_RE = re.compile(r"token|ghp_|gho_|ghu_|ghs_|ghr_", re.I)
ALLOWED_DOC_PATTERNS = ("release/CHANGELOG.md", "release/RELEASE_NOTES.md", "release/README.md",
                        "release/EULA.md", "release/LICENSE.md", "release/LICENSE.txt",
                        "README.md", "LICENSE", "LICENSE.md", "LICENSE.txt")
# matched component by component from the product root (never from the right)
TUTORIAL_GLOBS = ("docs/*TUTORIAL*.md", "docs/*Tutorial*.md", "docs/*tutorial*.md",
                  "release/*TUTORIAL*.md", "release/*tutorial*.md")
INTERNAL_REASONS = {
    "SCRIPT.json": "internal manifest",
    "CLAUDE.md": "internal instructions",
    "ARCHITECTURE.md": "internal map",
    "DECISIONS.md": "internal decisions",
    "PRODUCT.md": "internal product context",
    "research": "internal research",
    "validation": "validation evidence",
    "tests": "internal tests",
    "docs": "internal tracking (only tutorials are exported)",
    ".pws-validation.lock": "lock file",
}
NEVER_EXPORTED = ["workspace tree", "pws.config.json", ".claude/", "docs/maintenance/", "archives",
                  "validation evidence", "secrets", "symbolic links"]
# recognized terms documents: default destination of each rendered terms kind
TERMS_DOC_KINDS = {licensing.DEFAULT_DEST[k]: k for k in ("eula", "grant", "notice")}
# licence-template keys filled from the manifest and the identity (licensing.context);
# the holder's fields come from licensing.FIELD_NAMES, the templates add theirs
TEMPLATE_CONTEXT_KEYS = ("COPYRIGHT_HOLDER", "CREATED_YEAR", "CURRENT_YEAR", "YEAR_RANGE",
                         "PRODUCT_NAME", "PRODUCT_SLUG", "PROFILE", "LICENSE_ID", "GRANT",
                         "SOURCE_VISIBILITY", "ACCESS", "PUBLICATION_STATE", "PUBLICATION_PRIVACY",
                         "PUBLICATION_MODE", "TERMS_URL", "CC_URL", "SCRIPT_KIND")
TEMPLATE_BLOCK_RE = re.compile(r"\[\[[?!][A-Z0-9_]+:")
PINE_MARKERS = (
    ("a //@version= annotation", re.compile(r"^[ \t>]*//[ \t]*@version[ \t]*=", re.M)),
    ("a declaration statement", re.compile(r"^[ \t>]*(?:indicator|strategy|library)[ \t]*\(", re.M)),
    ("a pine code block", re.compile(r"^[ \t>]*(?:`{3,}|~{3,})[ \t]*pine(?:script)?\b", re.M | re.I)),
)
MIN_CODE_LINE = 16          # shorter lines (or comments) are not a fingerprint of a source
OTHER_SOURCE_MIN_LINES = 3  # lines of ANOTHER product's closed source that make a document a copy
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
DEST_KEYS = ("name", "repo", "visibility", "branch", "path_prefix", "url", "clone_url")
DRAFT_MARKER = licensing.DRAFT_MARKER
# real repository check before a closed source is sent (I-06)
GITHUB_HOST = "github.com"
GH_VIEW_FIELDS = "nameWithOwner,visibility,isPrivate,url"
GH_TIMEOUT = 30
GH_VISIBILITIES = ("PUBLIC", "PRIVATE", "INTERNAL")
GH_ENV_DROPPED = ("GH_DEBUG", "DEBUG", "GH_FORCE_TTY", "CLICOLOR_FORCE", "GH_PAGER", "PAGER")
GH_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")    # `_` for managed-user accounts
GH_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# I-06, strict reading (review RS-01, 2026-11-13): the ONLY URL forms accepted as designating a github.com
# repository when closed content is sent — matched on the whole string, nothing a parser could read as
# another host: no user part except `git@` for ssh, no port, query, fragment or percent-encoding
_GH_REPO_PART = r"(?P<repo>[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9._-]+?)"
GH_STRICT_URL_RES = (
    re.compile(r"https://github\.com/%s(?:\.git)?/?" % _GH_REPO_PART),
    re.compile(r"git@github\.com:%s(?:\.git)?" % _GH_REPO_PART),
    re.compile(r"ssh://git@github\.com/%s(?:\.git)?" % _GH_REPO_PART),
)
GH_ACCEPTED_URL_FORMS = ("https://github.com/<owner>/<repo>[.git][/]", "git@github.com:<owner>/<repo>[.git]",
                         "ssh://git@github.com/<owner>/<repo>[.git]")
# credentials of a URL, masked for display: a user part made of RFC 3986 userinfo characters (« @ » kept so
# that a password holding one is masked up to the last « @ »), hence inside the authority — never across
# « / », « ? » or « # », and never a part holding « [ », « ] », « \ » or a quote: such a part is shown as is,
# so the real host stays visible (review RS-01)
URL_USERINFO_RE = re.compile(r"(?P<scheme>\b[A-Za-z][A-Za-z0-9+.-]*://)(?P<user>[A-Za-z0-9._~%!$&()*+,;=:@-]+)@")
URL_SCHEME_PREFIX_RE = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://")
URL_QUERY_RE = re.compile(r"(?P<head>\b[A-Za-z][A-Za-z0-9+.-]*://[^\s?#'\"<>]*)\?[^\s#'\"<>]+")
SCP_USERINFO_RE = re.compile(r"(?<![\w.+%~-])(?P<user>[\w.+%~-]+)@(?P<host>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+):(?!//)")
VISIBILITY_CHECK_LIMIT = ("the repository visibility can change between this check and the push: the check is made "
                          "immediately before the push (only local writes and the commit come in between), with no "
                          "atomic guarantee from GitHub")
# identity of the authorized repository, for every send (holder's request of 2026-11-14)
DESTINATION_CHECK_NOTE = ("not verified at this stage (export-plan works offline): before anything is written into the "
                          "clone, export-diff and publish check that the destination's URL and the clone's single "
                          "fetch URL and single push URL, as git really uses them (remote.origin.pushurl, insteadOf "
                          "and pushInsteadOf applied), designate this GitHub repository; publish reads the remote "
                          "again right before git push. Identity of the authorized repository only: the privacy that "
                          "closed content requires is a separate check (visibility_check)")
DESTINATION_CHECK_LIMIT = ("the clone's git configuration and the environment are read again right before git push; "
                           "a change made in the instant between that reading and the push itself is not detected. "
                           "The check is offline: it does not see a repository renamed or transferred on GitHub "
                           "(GitHub redirects git operations), nor the SSH client configuration (~/.ssh/config) — "
                           "the authenticity of github.com rests on SSH host-key or TLS certificate verification — "
                           "nor a compromised environment (git or its helper programs replaced)")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd, cwd=None, timeout=120):
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _filter_secret_lines(text):
    return "\n".join(l for l in text.splitlines() if not TOKEN_LINE_RE.search(l))


def _redact_text(text):
    """Mask the credentials of every URL in a text (`https://user:token@…`,
    `token@host:path`, a query string); the conventional ssh user `git`
    stays visible. Only a user part inside the authority, made of userinfo
    characters, is masked: `https://h#@github.com/…` or `https://h?@…` keeps
    its real host `h` visible (review RS-01)."""
    if not isinstance(text, str):
        return text
    text = URL_USERINFO_RE.sub(lambda m: m.group("scheme") + ("git" if m.group("user") == "git" else "***") + "@",
                               text)
    text = URL_QUERY_RE.sub(lambda m: m.group("head") + "?***", text)
    return SCP_USERINFO_RE.sub(lambda m: ("git" if m.group("user") == "git" else "***") + "@" + m.group("host")
                               + ":", text)


def _redact(obj):
    """Copy of a result for display: every string passes through _redact_text."""
    if isinstance(obj, str):
        return _redact_text(obj)
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


INLINE_HELPER_SHOWN = "inline helper (masked)"
SECRET_HELPER_SHOWN = "helper masked (its value carries a password or a token)"
SECRET_VALUE_RE = re.compile(r"password\s*=|passwd\s*=|secret\s*=|" + TOKEN_LINE_RE.pattern, re.I)


def _credential_helper_shown(value):
    """What `status` shows of git's `credential.helper` (review RS-03): the
    helper's name only — its first word, a path reduced to its file name,
    never its arguments. An inline helper (`!…`: a shell command, which may
    carry a password or a token) and a value carrying `password=` or a token
    are never shown, even in part: only a masked mention."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("!"):
        return INLINE_HELPER_SHOWN
    if SECRET_VALUE_RE.search(value):
        return SECRET_HELPER_SHOWN
    name = value.split()[0].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name or None


def status(root):
    """Connection facts without ever printing a secret: the gh output without
    its token lines, the git credential helper by its name only."""
    gh = shutil.which("gh")
    out = {"gh_installed": bool(gh), "gh_auth": None, "gh_auth_output": None,
           "git_credential_helper": None, "destinations": destinations(root),
           "note": "no token is stored by PWS; authentication relies on gh or the git credential helper"}
    if gh:
        rc, o, e = _run([gh, "auth", "status", "--hostname", "github.com"], timeout=30)
        out["gh_auth"] = "logged-in" if rc == 0 else "not-logged-in"
        out["gh_auth_output"] = _filter_secret_lines((o + "\n" + e).strip())[:600]
    rc, o, _ = _run(["git", "config", "--get", "credential.helper"])
    out["git_credential_helper"] = _credential_helper_shown(o) if rc == 0 else None
    return _redact(out)


# ---- destinations ------------------------------------------------------------

def _configured_destinations(root):
    cfg = config.read_config(root)
    dests = (cfg["data"].get("github") or {}).get("destinations") or []
    return [d for d in dests if isinstance(d, dict)]


def destinations(root):
    """The configured destinations as displayed (credentials of a URL masked)."""
    return _redact(_configured_destinations(root))


def _use_problems(dest):
    """Checks this module needs on top of config.destination_problems: a plain
    branch name (it becomes a refspec) and no `.git` folder in the prefix."""
    out = []
    branch = dest.get("branch") or "main"
    if not isinstance(branch, str) or not BRANCH_RE.match(branch) or ".." in branch \
            or "//" in branch or branch.endswith(("/", ".lock")):
        out.append("branch must be a plain branch name (letters, digits, . _ - /)")
    prefix = dest.get("path_prefix") or ""
    if isinstance(prefix, str) and any(p.lower() == ".git" for p in Path(prefix).parts):
        out.append("path_prefix must not designate the .git folder")
    url = dest.get("url")
    if url is not None and (not isinstance(url, str) or not url.strip() or url.strip().startswith("-")):
        out.append("url must be a non-empty string that is not an option")
    return out


def destination_add(root, name, repo, visibility, path_prefix="", branch="main", url=None):
    dest = {"name": name, "repo": repo, "visibility": visibility,
            "path_prefix": path_prefix, "branch": branch}
    if url:
        dest["url"] = url
    problems = list(dict.fromkeys(config.destination_problems(dest) + _use_problems(dest)))
    if problems:
        return {"ok": False, "error": "; ".join(problems)}

    def mutate(data):
        lst = data.setdefault("github", {}).setdefault("destinations", [])
        if any(isinstance(d, dict) and d.get("name") == name for d in lst):
            return "destination %r already exists — remove it first" % name
        lst.append(dest)
        return None

    r = config.update_config(root, mutate)
    if r.get("ok"):
        # leftovers of an earlier destination of the same name (plan, clone) are
        # invalidated when they do not match the new one — never deleted
        r.update(_invalidate_destination_state(root, name, _effective_destination(dest),
                                               "destination %r replaced" % name))
        r["destination"] = _effective_destination(dest)
    return _redact(r)


def destination_remove(root, name):
    def mutate(data):
        lst = data.setdefault("github", {}).setdefault("destinations", [])
        before = len(lst)
        lst[:] = [d for d in lst if not (isinstance(d, dict) and d.get("name") == name)]
        if len(lst) == before:
            return "destination %r not found" % name
        return None

    r = config.update_config(root, mutate)
    if r.get("ok"):
        r.update(_invalidate_destination_state(root, name, None, "destination %r removed" % name))
    return _redact(r)


def _destination(root, name):
    for d in _configured_destinations(root):
        if d.get("name") == name:
            return d
    return None


def _configured_destination(root, name):
    """(destination, error): the CURRENT configuration entry, validated."""
    if not core.is_safe_id(name):
        return None, "invalid destination name %r" % (name,)
    dest = _destination(root, name)
    if dest is None:
        return None, "unknown destination %r" % name
    problems = list(dict.fromkeys(config.destination_problems(dest) + _use_problems(dest)))
    if problems:
        return None, "destination %r is invalid in pws.config.json: %s" % (name, "; ".join(problems))
    return dest, None


def _clone_url(dest):
    return dest.get("url") or "https://github.com/%s.git" % dest["repo"]


def _effective_destination(dest):
    """What the export really targets — shown in every output and bound to the plan."""
    return {"name": dest.get("name"), "repo": dest.get("repo"), "visibility": dest.get("visibility"),
            "branch": dest.get("branch") or "main", "path_prefix": dest.get("path_prefix") or "",
            "url": dest.get("url") or None, "clone_url": _clone_url(dest)}


# ---- product files -------------------------------------------------------------

def _product(root, slug):
    for p in scan.scan_workspace(root)["products"]:
        if p["slug"] == slug:
            return p
    return None


def _ascii_slug_name(slug):
    return re.sub(r"[^A-Za-z0-9._-]", "-", slug)


def _walk_product(pdir):
    """Every entry under the product root as (rel, path, kind): kind `file`
    (regular), `symlink` (link to a file or a folder — listed, never
    followed) or `special` (not a regular file)."""
    pdir = Path(pdir)
    for dirpath, dirnames, filenames in os.walk(str(pdir), followlinks=False):
        base = Path(dirpath)
        for d in sorted(dirnames):
            if (base / d).is_symlink():
                dirnames.remove(d)
                yield (base / d).relative_to(pdir).as_posix(), base / d, "symlink"
        dirnames.sort()
        for name in sorted(filenames):
            p = base / name
            if p.is_symlink():
                kind = "symlink"
            else:
                try:
                    kind = "file" if stat.S_ISREG(os.lstat(str(p)).st_mode) else "special"
                except OSError:
                    kind = "special"
            yield p.relative_to(pdir).as_posix(), p, kind


def _read_regular(path):
    """(bytes, error): content of a REGULAR file opened without following a
    final symbolic link and without blocking on a special file."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        return None, "unreadable (%s)" % (exc.strerror or exc)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None, "not a regular file"
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), None
    except OSError as exc:
        return None, "unreadable (%s)" % (exc.strerror or exc)
    finally:
        os.close(fd)


def _is_tutorial(rel):
    parts = rel.split("/")
    for glob in TUTORIAL_GLOBS:
        gparts = glob.split("/")
        if len(parts) == len(gparts) and all(fnmatch.fnmatchcase(p, g) for p, g in zip(parts, gparts)):
            return True
    return False


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def _template_keys(root=None):
    """Keys of the licence templates: context keys, holder's fields, and the
    placeholders of the templates of `root` when they are present."""
    keys = set(TEMPLATE_CONTEXT_KEYS) | set(licensing.FIELD_NAMES)
    if root is not None:
        tdir = Path(root) / licensing.TEMPLATES_REL
        try:
            names = sorted(os.listdir(str(tdir)))
        except OSError:
            names = []
        for name in names:
            data, err = _read_regular(tdir / name)
            if err:
                continue
            text = data.decode("utf-8", "replace")
            keys |= set(licensing.PLACEHOLDER_RE.findall(text))
            keys |= {m.group(2) for m in licensing.OPTIONAL_BLOCK_RE.finditer(text)}
    return frozenset(keys)


def _template_residue(text, keys):
    """First unfilled licence-template field or template block, else None.
    Only the template keys count: `{{ticker}}` is a TradingView alert
    placeholder, not a residue."""
    for m in licensing.PLACEHOLDER_RE.finditer(text):
        if m.group(1) in keys:
            return "unfilled licence-template field {{%s}} at line %d" % (m.group(1), _line_of(text, m.start()))
    m = TEMPLATE_BLOCK_RE.search(text)
    if m:
        return "licence-template block %s at line %d" % (m.group(0), _line_of(text, m.start()))
    return None


def _draft_text_reason(text, keys=None):
    if DRAFT_MARKER in text:
        return "draft document (draft banner present) — settle it before export"
    residue = _template_residue(text, keys if keys is not None else _template_keys())
    if residue and residue.startswith("unfilled"):
        return "draft document: %s — settle it before export" % residue
    if residue:
        return "document carries a residual %s — render it again before export" % residue
    return None


def _draft_reason(path, keys=None):
    """A legal/product document still carrying the draft banner, an unfilled
    licence-template field or a template block is never exported (it would
    publish an unfinished text). A document that cannot be read as UTF-8
    text cannot be checked: it is never exported either."""
    data, err = _read_regular(path)
    if err:
        return "document %s — cannot be checked, not exported" % err
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "document is not UTF-8 text — cannot be checked, not exported"
    return _draft_text_reason(text, keys)


def _code_lines(text):
    """Fingerprint of a Pine source: whitespace-normalized code lines (not
    comments) of at least MIN_CODE_LINE characters."""
    out = set()
    for line in text.splitlines():
        norm = " ".join(line.split())
        if len(norm) >= MIN_CODE_LINE and not norm.startswith("//"):
            out.add(norm)
    return out


def _closed_sources(root, products, own_slug):
    """[(slug, bytes, code lines)] of the OTHER closed-source products."""
    out = []
    for p in products:
        lic = p.get("license") or {}
        if p["slug"] == own_slug or lic.get("source_visibility") == "public" or not p.get("source"):
            continue
        src = Path(p["source"])
        if not core.is_within(p["path"], src):
            continue
        try:
            data = src.read_bytes()
        except OSError:
            continue
        out.append((p["slug"], data, _code_lines(data.decode("utf-8", "replace"))))
    return out


def _pine_code_reason(text, data, own, others):
    """Why a document must not reach a PUBLIC destination, or None. `own` is
    (bytes, lines) of the product's closed source (None for a public
    source); `others` lists the other closed sources of the workspace."""
    flat = " ".join(text.split())
    if own is not None:
        own_bytes, own_lines = own
        if own_bytes is not None and data == own_bytes:
            return "copy of the closed source"
        for label, rx in PINE_MARKERS:
            m = rx.search(text)
            if m:
                return "carries Pine code (%s, line %d)" % (label, _line_of(text, m.start()))
        hits = [l for l in own_lines if l in flat]
        if hits:
            return "reproduces %d code line(s) of the closed source" % len(hits)
    for slug, other_bytes, other_lines in others:
        hits = [l for l in other_lines if l in flat]
        if data == other_bytes or len(hits) >= OTHER_SOURCE_MIN_LINES:
            return "reproduces the closed source of product %r (%d code line(s))" % (slug, len(hits))
    return None


def _first_difference(a, b):
    la, lb = a.splitlines(), b.splitlines()
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            return i + 1
    return min(len(la), len(lb)) + 1


def _legal_text_reason(text, keys):
    """Why an ORIGINAL legal document cannot be exported as it is, or None:
    it carries the draft banner or licence-template syntax of Pine Workspace
    (an original document never does — the file is a PWS rendering or holds
    a residue to check). It is never compared with a PWS template."""
    if DRAFT_MARKER in text:
        return "it carries the draft banner of Pine Workspace (%r)" % DRAFT_MARKER
    residue = _template_residue(text, keys)
    if residue:
        return "it carries a Pine Workspace %s" % residue
    return None


# ---- plan --------------------------------------------------------------------

def _compute_plan(root, slug, dest):
    """Pure computation of the export set (reads only). Returns (plan,
    payload) where payload maps each target to the exact bytes checked."""
    root = Path(root)
    eff = _effective_destination(dest)
    products = scan.scan_workspace(root)["products"]
    product = next((p for p in products if p["slug"] == slug), None)
    if product is None:
        return {"ok": False, "error": "unknown product %r" % slug, "destination": eff}, {}
    if product["product_structure_status"] != "REGISTERED":
        return {"ok": False, "error": "product %s is %s — only a REGISTERED product is exported"
                % (slug, product["product_structure_status"]), "destination": eff}, {}
    lic = product.get("license") or {}
    # C-19 (2026-11-13): an imported licence still « to analyse » is not settled — nothing is exported
    blockers = profiles.license_release_blockers(lic)
    if blockers:
        return {"ok": False, "error": "product %s: %s — not exported" % (slug, "; ".join(blockers)),
                "destination": eff}, {}
    visibility = lic.get("source_visibility")
    public_dest = eff["visibility"] != "private"
    closed_to_public = visibility != "public" and public_dest
    pdir = Path(product["path"])
    prefix = eff["path_prefix"]
    target_dir = (Path(prefix) / _ascii_slug_name(slug)) if prefix else Path(_ascii_slug_name(slug))
    keys = _template_keys(root)
    terms = lic.get("terms_ref")
    included, excluded, warnings, payload = [], [], [], {}
    renders = {}

    def render(kind):
        if kind not in renders:
            renders[kind] = licensing.render(root, slug, kind)
        return renders[kind]

    def include(rel, to, role, reason, data):
        included.append({"from": rel, "to": to, "role": role, "reason": reason,
                         "sha256": core.sha256_bytes(data)})
        payload[to] = data

    source = Path(product["source"]) if product.get("source") else None
    source_rel = source.relative_to(pdir).as_posix() if source is not None else None
    own = None
    if source is not None and closed_to_public:
        try:   # fingerprint only (never exported); scan keeps the source inside the product
            sdata = source.read_bytes()
        except OSError:
            sdata = None
        own = (sdata, _code_lines(sdata.decode("utf-8", "replace")) if sdata is not None else set())
    elif source is None and closed_to_public:
        own = (None, set())
    # the other closed sources: documents towards a public destination, and a PUBLIC declared source towards
    # any destination (review RS-04: a public source copying a closed one is closed content)
    others = _closed_sources(root, products, slug) if (public_dest or visibility == "public") else []

    # original legal documents of an imported script (2026-11-14): judged here, never by the allow-list below
    legal, legal_payloads = licensing.legal_documents_review(product)
    legal_paths, legal_blockers = set(), []
    if legal is not None:
        # exact names: two files differing only by case are two documents (case-sensitive file systems)
        legal_paths = {c["path"] for c in legal["candidates"]}
        if isinstance(legal["declared"], list):
            legal_paths |= {d for d in legal["declared"] if isinstance(d, str)}
        legal_blockers = list(legal["blockers"])
        states = {d["path"]: d for d in legal["documents"]}
        kinds = {c["path"]: c for c in legal["candidates"]}
        for rel in legal.get("undeclared") or []:
            c = kinds.get(rel) or {"declarable": True, "reason": None}
            excluded.append({"path": rel, "reason": ("legal document not declared in license.documents — the export "
                                                     "waits until it is declared (or moved out of the product by "
                                                     "the holder)" if c["declarable"] else
                                                     "legal document or folder that cannot be declared as it is (%s) "
                                                     "— the export waits until the holder moves it" % c["reason"])})
        for state in legal["documents"]:
            if state["problem"]:
                excluded.append({"path": state["path"], "reason": "declared legal document refused: %s — the "
                                                                  "export waits" % state["problem"]})
        for rel, (data, text) in sorted(legal_payloads.items()):
            why = _legal_text_reason(text, keys)
            if why is None and public_dest:
                leak = _pine_code_reason(text, data, own, others)
                why = "%s — never exported to a public destination" % leak if leak else None
            if why:
                states[rel]["problem"] = why
                legal_blockers.append("declared legal document %s refused: %s — restore the original document or "
                                      "correct the declaration (`license confirm --slug %s --license-document "
                                      "<path>`)" % (rel, why, slug))
                excluded.append({"path": rel, "reason": "declared legal document refused: %s — the export waits"
                                                        % why})
                continue
            include(rel, (target_dir / profiles.legal_document_target(rel)).as_posix(), "legal",
                    "original legal document of the imported licence (license.documents), exported verbatim "
                    "(%s)" % states[rel]["encoding"], data)

    for rel, p, kind in _walk_product(pdir):
        if rel in legal_paths:
            continue        # an original legal document of the imported licence: judged above
        if kind == "symlink":
            what = "declared source is a symbolic link" if rel == source_rel else "symbolic link"
            excluded.append({"path": rel, "reason": "%s — never followed nor exported (export the real "
                                                    "file instead)" % what})
            continue
        if kind == "special":
            excluded.append({"path": rel, "reason": "not a regular file — never exported"})
            continue
        if rel == source_rel:
            if closed_to_public:
                excluded.append({"path": rel, "reason": "proprietary source (source_visibility=closed) "
                                                        "never exported to a public destination"})
                continue
            data, err = _read_regular(p)
            text = None
            if not err:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    err = "not UTF-8 text"
            if err:
                excluded.append({"path": rel, "reason": "declared source %s — not exported" % err})
                continue
            residue = _template_residue(text, keys)
            if residue:
                excluded.append({"path": rel, "reason": "declared source still carries a template residue: %s "
                                                        "— set the missing fact (e.g. license.created_year), "
                                                        "render the header again and paste it before export"
                                                        % residue})
                warnings.append("source %s excluded: %s" % (rel, residue))
                continue
            # review RS-04: a public source judged like a document against the OTHER closed sources
            copied = _pine_code_reason(text, data, None, others) if visibility == "public" else None
            if copied and public_dest:
                excluded.append({"path": rel, "reason": "declared source %s — a public source reproducing a closed "
                                                        "source is never exported to a public destination "
                                                        "(remove the copied code, or use a private destination: "
                                                        "its real repository is then checked as for a closed "
                                                        "source)" % copied})
                warnings.append("source %s excluded: it %s" % (rel, copied))
                continue
            if copied:
                warnings.append("source %s %s: it is closed content, sent only after the check of the real "
                                "GitHub repository (I-06)" % (rel, copied))
            include(rel, (target_dir / ("%s.pine" % _ascii_slug_name(slug))).as_posix(), "source",
                    "source (%s visibility, %s destination)" % (visibility, eff["visibility"]), data)
            continue
        if p.suffix == ".pine":
            excluded.append({"path": rel, "reason": "secondary .pine (only the declared source may be exported)"})
            continue
        allowed = rel in ALLOWED_DOC_PATTERNS or _is_tutorial(rel)
        is_terms = bool(terms) and rel == terms
        if not allowed and not is_terms:
            top = rel.split("/")[0]
            excluded.append({"path": rel, "reason": INTERNAL_REASONS.get(rel) or INTERNAL_REASONS.get(top)
                             or "not in the allowed list"})
            continue
        data, err = _read_regular(p)
        text = None
        if not err:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                err = "is not UTF-8 text"
        if err:
            excluded.append({"path": rel, "reason": "document %s — cannot be checked, not exported" % err})
            continue
        terms_kind = TERMS_DOC_KINDS.get(rel)
        if is_terms and terms_kind is None and rel.endswith(".md"):
            terms_kind = next((k for k in ("eula", "grant", "notice")
                               if render(k).get("ok") and render(k).get("text") == text), None)
        if is_terms and terms_kind is None:
            note = ("terms_ref %r is not a recognized terms document (%s, or a document written by "
                    "`license write`)" % (rel, ", ".join(sorted(TERMS_DOC_KINDS))))
            if not allowed:
                excluded.append({"path": rel, "reason": note + " — not exported"})
                warnings.append(note + " — not exported")
                continue
            warnings.append(note + " — exported only as an ordinary product document")
            is_terms = False
        draft = _draft_text_reason(text, keys)
        if draft:
            excluded.append({"path": rel, "reason": draft})
            continue
        if terms_kind is not None:
            r = render(terms_kind)
            if not r.get("ok"):
                excluded.append({"path": rel, "reason": "terms document whose currency cannot be established "
                                                        "(%s) — not exported" % r.get("error")})
                continue
            if r.get("text") != text:
                why = ("terms document no longer current: it differs from the current rendering of the "
                       "recorded fields and identity (first difference at line %d) — review the fields, "
                       "write it again (`license write --slug %s --kind %s`), then run export-plan again"
                       % (_first_difference(text, r.get("text") or ""), slug, terms_kind))
                excluded.append({"path": rel, "reason": why})
                warnings.append("%s excluded: %s" % (rel, why))
                continue
        if public_dest:
            leak = _pine_code_reason(text, data, own, others)
            if leak:
                excluded.append({"path": rel, "reason": "%s — never exported to a public destination "
                                                        "(remove the code from the document, or use a "
                                                        "private destination)" % leak})
                continue
        include(rel, (target_dir / Path(rel).name).as_posix(), "terms" if is_terms else "document",
                "licence terms referenced by the manifest" if is_terms else "allowed product document", data)

    included.sort(key=lambda i: i["from"])
    excluded.sort(key=lambda e: e["path"])
    seen, collisions = {}, []
    for item in included:
        key = item["to"].casefold()
        if key in seen:
            collisions.append({"to": item["to"], "from": [seen[key]["from"], item["from"]]})
        else:
            seen[key] = item
    plan = {"ok": True, "slug": slug, "destination": eff, "profile": product.get("profile"),
            "license": {k: lic.get(k) for k in ("id", "grant", "source_visibility", "publication",
                                                "access", "terms_ref", "origin", "status", "documents")},
            "target_dir": target_dir.as_posix(), "included": included, "excluded": excluded,
            "warnings": warnings, "staging": None, "never_exported": list(NEVER_EXPORTED)}
    if collisions:
        plan.update({"ok": False, "collisions": collisions,
                     "error": "plan refused: several files would be exported under the same target name "
                              "(%s) — rename or remove one of them, then run export-plan again"
                              % "; ".join("%s ← %s" % (c["to"], " + ".join(c["from"])) for c in collisions)})
    if legal is not None:
        plan["legal_documents"] = {"declared": legal["declared"], "candidates": legal["candidates"],
                                   "undeclared": legal["undeclared"], "documents": legal["documents"],
                                   "blockers": legal_blockers, "note": legal["note"]}
        if legal_blockers:
            refusal = ("export refused: the original legal documents of the imported licence are not settled — "
                       "%s; nothing is exported before, never an incomplete set" % " | ".join(legal_blockers))
            plan.update(ok=False, error=refusal if plan["ok"] else "%s; also %s" % (plan["error"], refusal))
    return plan, payload


def _staging_dir(root, slug, dest_name):
    return Path(root) / EXPORT_REL / ("%s--%s" % (_ascii_slug_name(slug), dest_name))


def _runtime_ok(root, *parts):
    return core.runtime_tree_is_real(root, tuple(EXPORT_REL.parts) + tuple(parts))


def _invalidate_plan_at(root, staging, reason):
    """PLAN.json → PLAN.invalidated.json (+ INVALIDATED.json): an invalidated
    plan can no longer be compared nor published. Nothing is deleted."""
    plan_path = Path(staging) / "PLAN.json"
    if not _runtime_ok(root, Path(staging).name) or plan_path.is_symlink() or not plan_path.is_file():
        return None
    try:
        os.replace(str(plan_path), str(Path(staging) / "PLAN.invalidated.json"))
        core.atomic_write_json(Path(staging) / "INVALIDATED.json",
                               {"at": _now(), "reason": reason, "plan": "PLAN.invalidated.json",
                                "action": "run `github export-plan` again"})
    except OSError as exc:
        return {"staging": str(staging), "reason": reason, "error": str(exc)}
    return {"staging": str(staging), "reason": reason}


def export_plan(root, slug, dest_name):
    """Compute the allowed export set for a product and a destination; write
    the staging folder + PLAN.json. Read-only on the product, offline: when
    the plan carries closed content, it announces the check of the real
    GitHub repository made by export-diff and publish (never stored)."""
    plan = _export_plan(root, slug, dest_name)
    if plan.get("ok") and plan.get("staging"):
        eff = plan["destination"]
        plan["destination_check"] = {
            "required": True, "performed": False, "ok": None, "checked_at": None,
            "configured": {"name": eff.get("name"), "repo": eff.get("repo"), "visibility": eff.get("visibility"),
                           "url": eff.get("clone_url")},
            "remote": None, "error": None, "note": DESTINATION_CHECK_NOTE, "limit": DESTINATION_CHECK_LIMIT}
        files, err = _staged_payload(Path(plan["staging"]), plan["included"])
        content, cerr = _closed_content(root, slug, files) if files is not None else (None, err)
        if cerr or content["files"]:
            eff = plan["destination"]
            plan["visibility_check"] = {
                "required": True, "performed": False, "ok": None, "checked_at": None,
                "closed_content": content["files"] if content else [],
                "configured": {"name": eff.get("name"), "repo": eff.get("repo"),
                               "visibility": eff.get("visibility")},
                "remote": None, "observed": None, "error": cerr,
                "note": "not verified at this stage (export-plan works offline): export-diff observes the real "
                        "GitHub repository and publish checks it again immediately before the push; only a "
                        "repository GitHub reports PRIVATE, designated by the clone's single push URL, receives "
                        "this closed content",
                "limit": VISIBILITY_CHECK_LIMIT}
    return _redact(plan)


def _export_plan(root, slug, dest_name):
    root = Path(root)
    dest, err = _configured_destination(root, dest_name)
    plan, payload = (_compute_plan(root, slug, dest) if dest is not None
                     else ({"ok": False, "error": err}, {}))
    staging = _staging_dir(root, slug, dest_name) if core.is_safe_id(dest_name) else None
    if not plan.get("ok"):
        if staging is not None:
            previous = _invalidate_plan_at(root, staging, "export-plan refused: %s" % plan.get("error"))
            if previous:
                plan["invalidated_previous_plan"] = previous
        return plan
    if not _runtime_ok(root, staging.name, "files") or (staging.exists() and not staging.is_dir()):
        return {"ok": False, "error": "the export folder %s is not a real folder of the workspace (symbolic "
                                      "link or file) — nothing written" % staging,
                "destination": plan["destination"]}
    # the previous plan stops being usable BEFORE its staged files are replaced
    _invalidate_plan_at(root, staging, "superseded by a new export-plan")
    files_dir = staging / "files"
    try:
        if files_dir.exists():
            shutil.rmtree(str(files_dir))
        files_dir.mkdir(parents=True)
        for item in plan["included"]:
            dst = files_dir / item["to"]
            if not core.is_within(files_dir, dst):
                return {"ok": False, "error": "target %r escapes the staging folder" % item["to"]}
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(str(dst), "wb") as f:
                f.write(payload[item["to"]])
        plan.update({"plan_format": PLAN_FORMAT, "created_at": _now(), "staging": str(staging),
                     "clone": _inspect_clone(root, dest_name, plan["destination"])})
        core.atomic_write_json(staging / "PLAN.json", plan)
        for marker in ("INVALIDATED.json", "PLAN.invalidated.json"):
            if (staging / marker).is_file() and not (staging / marker).is_symlink():
                (staging / marker).unlink()
    except OSError as exc:
        return {"ok": False, "error": "staging not written (%s) — no usable plan; run export-plan again" % exc,
                "destination": plan["destination"]}
    return plan


def _revalidate(root, slug, dest_name):
    """Bind the stored plan to the CURRENT configuration and manifest.
    Returns (context, None) or (None, refusal)."""
    root = Path(root)
    if not core.is_safe_id(dest_name):
        return None, {"ok": False, "error": "invalid destination name %r" % (dest_name,)}
    staging = _staging_dir(root, slug, dest_name)
    again = "run `github export-plan --slug %s --destination %s` again and review the new plan" % (slug, dest_name)
    if not _runtime_ok(root, staging.name, "files"):
        return None, {"ok": False, "error": "the export folder %s contains a symbolic link — refused" % staging}
    plan, err = core.read_json(staging / "PLAN.json")
    if err or not isinstance(plan, dict):
        return None, {"ok": False, "error": "no export plan — run `github export-plan --slug %s "
                                            "--destination %s` first" % (slug, dest_name)}
    if plan.get("plan_format") != PLAN_FORMAT or not isinstance(plan.get("destination"), dict) \
            or not isinstance(plan.get("included"), list) \
            or not all(isinstance(i, dict) and isinstance(i.get("to"), str) for i in plan["included"]):
        return None, {"ok": False, "error": "export plan prepared by an earlier version (not bound to its "
                                            "destination) or unreadable — " + again}
    if plan.get("slug") != slug or plan["destination"].get("name") != dest_name:
        return None, {"ok": False, "error": "the plan in %s belongs to %r → %r — %s"
                      % (staging, plan.get("slug"), plan["destination"].get("name"), again)}
    dest, derr = _configured_destination(root, dest_name)
    if derr:
        return None, {"ok": False, "error": "%s — the plan prepared for it is stale; %s" % (derr, again),
                      "plan_destination": plan["destination"]}
    eff = _effective_destination(dest)
    diffs = ["%s: plan %r, now %r" % (k, plan["destination"].get(k), eff.get(k))
             for k in DEST_KEYS if plan["destination"].get(k) != eff.get(k)]
    if diffs:
        return None, {"ok": False, "error": "destination %r changed since the plan (%s) — %s"
                      % (dest_name, "; ".join(diffs), again),
                      "destination": eff, "plan_destination": plan["destination"]}
    fresh, _ = _compute_plan(root, slug, dest)
    if not fresh.get("ok"):
        return None, {"ok": False, "error": "the plan is stale: export-plan would now refuse (%s)"
                      % fresh.get("error"), "destination": eff}
    planned = (plan.get("license") or {}).get("source_visibility")
    current = fresh["license"].get("source_visibility")
    if planned != current:
        return None, {"ok": False, "error": "source visibility changed since the plan (plan %r, now %r) — %s"
                      % (planned, current, again), "destination": eff}
    # the ratified rule, evaluated again on the current manifest and configuration
    if current != "public" and eff["visibility"] != "private" \
            and any(i.get("role") == "source" for i in plan["included"]):
        return None, {"ok": False, "error": "refused: the plan carries a closed source "
                                            "(source_visibility=%s) for a public destination" % current,
                      "destination": eff}
    old = {i.get("to"): (i.get("from"), i.get("sha256"), i.get("role")) for i in plan["included"]
           if isinstance(i, dict)}
    new = {i["to"]: (i["from"], i["sha256"], i["role"]) for i in fresh["included"]}
    if old != new:
        changed = sorted(set(old) ^ set(new)) + sorted(t for t in set(old) & set(new) if old[t] != new[t])
        return None, {"ok": False, "error": "the product changed since the plan (%s) — %s"
                      % (", ".join(str(t) for t in changed[:8]), again), "destination": eff}
    files_dir = staging / "files"
    for item in plan["included"]:
        target = files_dir / item["to"]
        data, rerr = (_read_regular(target) if core.is_within(files_dir, target)
                      else (None, "outside the staging folder"))
        if rerr or core.sha256_bytes(data) != item.get("sha256"):
            return None, {"ok": False, "error": "staged file %s altered or missing since the plan (%s) — %s"
                          % (item["to"], rerr or "SHA-256 differs", again), "destination": eff}
    return {"plan": plan, "dest": dest, "eff": eff, "staging": staging}, None


# ---- local clone ---------------------------------------------------------------

def _clone_dir(root, dest_name):
    return Path(root) / EXPORT_REL / CLONES_DIRNAME / dest_name


def _norm_url(url):
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if "://" in url or re.match(r"^[^/]+:", url):          # URL or scp-like host:path
        return url.rstrip("/")
    return os.path.normpath(os.path.realpath(os.path.expanduser(url)))


def _same_url(a, b):
    return _norm_url(a) is not None and _norm_url(a) == _norm_url(b)


def _unpublished_work(cdir, branch):
    """Local work the remote does not hold — uncommitted or untracked
    changes, commits absent from origin/<branch>, stashes — or `known`
    False when git cannot establish it."""
    unknown = {"known": False, "changes": [], "change_count": None, "local_commits": None, "stashes": None}
    if not branch:
        return unknown
    rc1, changes, _ = _run(["git", "-C", str(cdir), "status", "--porcelain", "--untracked-files=all"], timeout=60)
    rc2, ahead, _ = _run(["git", "-C", str(cdir), "rev-list", "--count",
                          "refs/remotes/origin/%s..HEAD" % branch], timeout=60)
    rc3, stashes, _ = _run(["git", "-C", str(cdir), "stash", "list"], timeout=60)
    if rc1 or rc2 or rc3 or not ahead.isdigit():
        return unknown
    lines = [l for l in changes.splitlines() if l.strip()]
    return {"known": True, "changes": lines[:20], "change_count": len(lines), "local_commits": int(ahead),
            "stashes": len([l for l in stashes.splitlines() if l.strip()])}


def _holds_unpublished(work):
    return (not work or not work.get("known") or bool(work.get("change_count"))
            or bool(work.get("local_commits")) or bool(work.get("stashes")))


def _inspect_clone(root, dest_name, eff):
    """Facts about clones/<name> against the effective destination (read-only)."""
    cdir = _clone_dir(root, dest_name)
    info = {"path": str(cdir), "exists": False, "origin": None, "branch": None,
            "expected_origin": eff.get("clone_url"), "expected_branch": eff.get("branch"),
            "matches_destination": None, "unpublished_work": None, "problem": None}
    if not _runtime_ok(root, CLONES_DIRNAME, dest_name):
        info["exists"] = cdir.exists() or cdir.is_symlink()
        info["problem"] = "the clone path is (or passes through) a symbolic link"
        return info
    if not cdir.exists():
        return info
    info["exists"] = True
    if not cdir.is_dir() or not (cdir / ".git").is_dir() or (cdir / ".git").is_symlink():
        info["problem"] = "the folder is not a git clone"
        return info
    rc, origin, _ = _run(["git", "-C", str(cdir), "remote", "get-url", "origin"], timeout=30)
    info["origin"] = origin if rc == 0 and origin else None
    rc, branch, _ = _run(["git", "-C", str(cdir), "symbolic-ref", "--quiet", "--short", "HEAD"], timeout=30)
    info["branch"] = branch if rc == 0 and branch else None
    info["matches_destination"] = bool(_same_url(info["origin"], eff.get("clone_url"))
                                       and info["branch"] == eff.get("branch"))
    info["unpublished_work"] = _unpublished_work(cdir, info["branch"] or eff.get("branch"))
    return info


def _describe_work(work):
    if not work or not work.get("known"):
        return "state not established by git"
    return "%s uncommitted or untracked change(s), %s local commit(s) absent from origin, %s stash(es)" % (
        work.get("change_count"), work.get("local_commits"), work.get("stashes"))


def _clone_refusal(info, dest_name):
    """Why the clone cannot serve a comparison or a publication, or None."""
    path = info["path"]
    if info["problem"]:
        return ("local clone %s: %s — run `github fetch --destination %s` (a clone holding no unpublished "
                "work is set aside, never deleted; otherwise inspect and move the folder yourself)"
                % (path, info["problem"], dest_name))
    if not info["exists"]:
        return "destination not fetched — run `github fetch --destination %s`" % dest_name
    if not info["matches_destination"]:
        return ("stale local clone %s: origin %r on branch %r, while destination %r is %r on branch %r — "
                "run `github fetch --destination %s` (it sets a clean stale clone aside; a clone holding "
                "unpublished work is never moved)" % (path, info["origin"], info["branch"], dest_name,
                                                     info["expected_origin"], info["expected_branch"],
                                                     dest_name))
    if _holds_unpublished(info["unpublished_work"]):
        return ("local clone %s holds unpublished local work (%s) — inspect it (`git -C <clone> status`, "
                "`git -C <clone> log origin/%s..HEAD`), publish or discard that work yourself, then run "
                "`github fetch --destination %s`; nothing was changed"
                % (path, _describe_work(info["unpublished_work"]), info["expected_branch"], dest_name))
    return None


def _set_aside_or_mark(root, dest_name, info, reason):
    """A stale clone is never deleted: without unpublished work it moves to
    clones/.stale/<name>--<time>; with unpublished work (or an unknown
    state) it stays in place, marked by clones/<name>.STALE.json."""
    cdir = _clone_dir(root, dest_name)
    clones = cdir.parent
    record = {"at": _now(), "reason": reason, "origin": info.get("origin"), "branch": info.get("branch"),
              "unpublished_work": info.get("unpublished_work"), "problem": info.get("problem")}
    if not _runtime_ok(root, CLONES_DIRNAME):
        return {"error": "the clones folder is (or passes through) a symbolic link — nothing moved"}
    movable = info.get("problem") is None and not _holds_unpublished(info.get("unpublished_work"))
    try:
        if movable:
            stale = clones / STALE_DIRNAME
            stale.mkdir(exist_ok=True)
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            target = stale / ("%s--%s" % (dest_name, stamp))
            os.rename(str(cdir), str(target))
            action = "kept for reference only — delete it yourself when it is no longer needed"
            core.atomic_write_json(Path(str(target) + ".json"), dict(record, moved_from=str(cdir), action=action))
            old_marker = clones / ("%s.STALE.json" % dest_name)
            if old_marker.is_file() and not old_marker.is_symlink():
                old_marker.unlink()
            return {"set_aside": {"path": str(target), "reason": reason, "action": action}}
        marker = clones / ("%s.STALE.json" % dest_name)
        action = ("inspect it (`git -C <clone> status`, `git -C <clone> log`), publish or discard its "
                  "unpublished work yourself, then move or delete the folder; until then fetch, "
                  "export-diff and publish refuse it")
        core.atomic_write_json(marker, dict(record, path=str(cdir), action=action))
        return {"marked": {"path": str(cdir), "marker": str(marker), "reason": reason,
                           "unpublished_work": info.get("unpublished_work"), "problem": info.get("problem"),
                           "action": action}}
    except OSError as exc:
        return {"error": "stale clone %s left in place: %s" % (cdir, exc)}


def _invalidate_destination_state(root, name, keep, reason):
    """Invalidate the plans and the clone of destination `name` that do not
    match `keep` (the new effective destination; None = all of them)."""
    out = {"invalidated_plans": [], "clone_set_aside": None, "clone_marked": None}
    if not core.is_safe_id(name):
        return out
    if not _runtime_ok(root):
        out["clone_problem"] = ("%s is (or passes through) a symbolic link — plans and clone not inspected; "
                                "every export command refuses it" % (Path(root) / EXPORT_REL))
        return out
    base = Path(root) / EXPORT_REL
    if base.is_dir():
        for staging in sorted(base.iterdir()):
            if staging.name == CLONES_DIRNAME or staging.is_symlink() or not staging.is_dir():
                continue
            plan, _ = core.read_json(staging / "PLAN.json")
            pdest = plan.get("destination") if isinstance(plan, dict) else None
            pname = pdest.get("name") if isinstance(pdest, dict) else None
            if pname != name and not (pname is None and staging.name.endswith("--" + name)):
                continue
            if keep is not None and isinstance(plan, dict) and plan.get("plan_format") == PLAN_FORMAT \
                    and pdest == keep:
                continue
            inv = _invalidate_plan_at(root, staging, reason)
            if inv:
                out["invalidated_plans"].append(inv)
    cdir = _clone_dir(root, name)
    if cdir.exists() or cdir.is_symlink():
        info = _inspect_clone(root, name, keep or {"clone_url": None, "branch": None})
        if keep is None or not info.get("matches_destination"):
            r = _set_aside_or_mark(root, name, info, reason)
            out["clone_set_aside"] = r.get("set_aside")
            out["clone_marked"] = r.get("marked")
            if r.get("error"):
                out["clone_problem"] = r["error"]
    return out


def fetch(root, dest_name):
    """Clone (or update) the destination locally — explicit network step.
    A clone of another repository or branch is set aside first (never
    deleted); a clone holding unpublished local work is refused."""
    return _redact(_fetch(root, dest_name))


def _fetch(root, dest_name):
    root = Path(root)
    dest, err = _configured_destination(root, dest_name)
    if err:
        return {"ok": False, "error": err}
    eff = _effective_destination(dest)
    cdir = _clone_dir(root, dest_name)
    out = {"destination": eff, "path": str(cdir)}
    if not _runtime_ok(root, CLONES_DIRNAME):
        return dict(out, ok=False, action="none",
                    error="the clones folder is (or passes through) a symbolic link — nothing fetched")
    marker = cdir.parent / ("%s.STALE.json" % dest_name)
    set_aside = None
    if cdir.exists() or cdir.is_symlink():
        info = _inspect_clone(root, dest_name, eff)
        if info["problem"] is None and info["matches_destination"]:
            if _holds_unpublished(info["unpublished_work"]):
                return dict(out, ok=False, action="none", clone=info,
                            error="local clone %s holds unpublished local work (%s) — nothing was pulled, "
                                  "moved or deleted; inspect it (`git -C <clone> status`, `git -C <clone> log "
                                  "origin/%s..HEAD`), publish or discard that work yourself, then run fetch "
                                  "again" % (cdir, _describe_work(info["unpublished_work"]), eff["branch"]))
            rc, o, e = _run(["git", "-C", str(cdir), "pull", "--ff-only", "origin", eff["branch"]], timeout=300)
            if rc == 0 and marker.is_file() and not marker.is_symlink():
                marker.unlink()
            return dict(out, ok=rc == 0, action="pull", detail=(e or o)[-400:],
                        clone=_inspect_clone(root, dest_name, eff))
        if info["problem"]:
            reason = "clone unusable for destination %r: %s" % (dest_name, info["problem"])
        else:
            reason = ("clone does not match destination %r (origin %r on branch %r; expected %r on branch %r)"
                      % (dest_name, info["origin"], info["branch"], eff["clone_url"], eff["branch"]))
        r = _set_aside_or_mark(root, dest_name, info, reason)
        if not r.get("set_aside"):
            why = r.get("error") or ("it holds unpublished local work (%s)"
                                     % _describe_work(info["unpublished_work"])
                                     if info["problem"] is None else "it cannot be inspected safely")
            return dict(out, ok=False, action="none", clone=info, clone_marked=r.get("marked"),
                        error="%s; %s — nothing was moved, deleted or fetched; %s"
                              % (reason, why, (r.get("marked") or {}).get("action") or "inspect it"))
        set_aside = r["set_aside"]
    cdir.parent.mkdir(parents=True, exist_ok=True)
    rc, o, e = _run(["git", "clone", "--branch", eff["branch"], "--single-branch", "--",
                     eff["clone_url"], str(cdir)], timeout=600)
    res = dict(out, ok=rc == 0, action="clone", detail=(e or o)[-400:])
    if set_aside:
        res["stale_clone_set_aside"] = set_aside
    if rc == 0:
        res["clone"] = _inspect_clone(root, dest_name, eff)
        if not res["clone"]["matches_destination"]:
            res.update(ok=False, error="clone created but its origin or branch does not match the destination")
        elif marker.is_file() and not marker.is_symlink():
            marker.unlink()
    return res


# ---- real GitHub repository before a closed source is sent (I-06) ----------------

def _lines(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


def _split_repo(text):
    """'owner/name' when `text` is exactly a GitHub repository identifier, else None."""
    if not isinstance(text, str) or text.count("/") != 1:
        return None
    owner, name = text.split("/")
    if not GH_OWNER_RE.fullmatch(owner) or not GH_NAME_RE.fullmatch(name) or name in (".", ".."):
        return None
    return text


def _github_repo_of_url(url):
    """'owner/name' when `url` is written EXACTLY in one of the accepted forms
    of a github.com repository URL (GH_ACCEPTED_URL_FORMS), else None.
    Everything else is refused, whatever it may designate (review RS-01 —
    `https://h#@github.com/o/r` was read as github.com while git contacts
    `h`): a user part (credentials, or any user but `git@` for ssh), a port
    (even the default one), a query, a fragment, a percent-encoding, a
    scheme or host not in lower case, surrounding spaces, a deeper path,
    another host, a local path, file://, git://, http://."""
    if not isinstance(url, str):
        return None
    for rx in GH_STRICT_URL_RES:
        m = rx.fullmatch(url)
        if m:
            return _split_repo(m.group("repo"))
    return None


def _git_host(url):
    """Host git really contacts for `url`, read as git reads it — named in a
    refusal so that a crafted URL never hides its real target (review
    RS-01). For a URL with a scheme other than ssh (https through curl, RFC
    3986), the authority ends at the first « / », « ? » or « # » and its
    user part ends at its FIRST « @ » (git's credential_from_url); for
    ssh:// the host part ends at the first « / » and ssh splits the user at
    the LAST « @ »; for the scp-like form `[user@]host:path` the host part
    ends at the first « : » (local path when a « / » comes first). The port
    is dropped. None when no host can be read (local path)."""
    if not isinstance(url, str) or not url:
        return None
    m = URL_SCHEME_PREFIX_RE.match(url)
    if m:
        rest = url[m.end():]
        if m.group("scheme").lower() in ("ssh", "git+ssh", "ssh+git"):
            hostport = rest.split("/", 1)[0].rpartition("@")[2]
        else:
            authority = re.split(r"[/?#]", rest, 1)[0]
            hostport = authority.partition("@")[2] if "@" in authority else authority
    else:
        colon, slash = url.find(":"), url.find("/")
        if colon <= 0 or 0 <= slash < colon or (colon == 1 and url[0].isalpha()):   # local path, drive letter
            return None
        hostport = url[:colon].rpartition("@")[2]
    if hostport.startswith("["):
        end = hostport.find("]")
        host = hostport[:end + 1] if end > 0 else hostport
    else:
        host = hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
    return host or None


def _shown_url(url):
    """A URL as a refusal displays it: credentials masked (_redact_text) and,
    when git would contact a host, that host named explicitly."""
    host = _git_host(url)
    return "%s (host for git: %s)" % (_redact_text(url), host) if host else _redact_text(url)


def _same_repo(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.casefold() == b.casefold()


def _gh_run(args):
    """The real `gh` (read-only use: `gh repo view`), never interactive and
    without debug output; (returncode, stdout, stderr)."""
    gh = shutil.which("gh")
    if not gh:
        return 127, "", "gh is not installed"
    env = {k: v for k, v in os.environ.items() if k not in GH_ENV_DROPPED}
    env.update({"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1", "CLICOLOR": "0"})
    try:
        proc = subprocess.run([gh] + list(args), capture_output=True, text=True, timeout=GH_TIMEOUT,
                              env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, "", "gh did not answer within %d s" % GH_TIMEOUT
    except OSError as exc:
        return 127, "", "gh could not be run (%s)" % (exc.strerror or exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _observe_repository(repo, gh_runner=None):
    """(observation, problem): what GitHub reports NOW about `repo` through
    `gh repo view` with the current gh authentication — never cached, never
    `gh api`. A problem when the answer cannot be obtained, is not valid, or
    is incoherent."""
    args = ["repo", "view", "https://%s/%s" % (GITHUB_HOST, repo), "--json", GH_VIEW_FIELDS]
    try:
        rc, out, err = (gh_runner or _gh_run)(args)
    except Exception as exc:          # an executor that fails establishes nothing
        rc, out, err = 127, "", "gh could not be run (%s)" % exc.__class__.__name__
    obs = {"checked_at": _now(), "command": "gh " + " ".join(args), "repository": None, "visibility": None,
           "is_private": None, "url": None}
    err = err if isinstance(err, str) else ""
    out = out if isinstance(out, str) else ""
    if rc != 0:
        low = err.lower()
        if rc == 127:
            why = "gh (GitHub CLI) is not available"
        elif rc == 124:
            why = "gh did not answer in time"
        elif rc == 4 or "gh auth login" in low:
            why = "gh is not authenticated for github.com (authenticate yourself: `! gh auth login`)"
        elif "could not resolve to a repository" in low or "not found" in low:
            why = "repository not found, or not visible with the current gh authentication"
        else:
            why = "gh failed (exit code %s)" % rc
        detail = _redact_text(_filter_secret_lines(err))[:300]
        return obs, why + (" — %s" % detail if detail else "")
    obs["response_excerpt"] = _redact_text(_filter_secret_lines(out))[:300]
    try:
        data = json.loads(out)
    except ValueError:
        return obs, "invalid answer: not JSON"
    if not isinstance(data, dict):
        return obs, "invalid answer: not a JSON object"
    nwo, vis, priv, url = (data.get(k) for k in ("nameWithOwner", "visibility", "isPrivate", "url"))
    if _split_repo(nwo) is None:
        return obs, "invalid answer: nameWithOwner missing or not 'owner/name'"
    if not isinstance(vis, str) or vis.upper() not in GH_VISIBILITIES:
        return obs, "invalid answer: visibility missing or unknown (%s)" % _redact_text(json.dumps(vis))[:60]
    if not isinstance(priv, bool):
        return obs, "invalid answer: isPrivate missing or not a boolean"
    vis = vis.upper()
    if priv != (vis != "PUBLIC"):
        return obs, "incoherent answer: visibility %s with isPrivate=%s" % (vis, json.dumps(priv))
    if not _same_repo(_github_repo_of_url(url), nwo):
        return obs, "incoherent answer: url does not designate %s on %s" % (nwo, GITHUB_HOST)
    obs.pop("response_excerpt")       # kept only to diagnose an answer that is refused
    obs.update(repository=nwo, visibility=vis, is_private=priv, url=_redact_text(url))
    return obs, None


def _config_values(cdir, key):
    """(returncode, values) of a multi-valued git key of the clone, read with
    NUL separators so that an EMPTY value is kept (cross-check of
    2026-11-14: an empty push URL is still a push target for git)."""
    try:
        proc = subprocess.run(["git", "-C", str(cdir), "config", "--null", "--get-all", key], capture_output=True,
                              timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 127, []
    raw = proc.stdout.decode("utf-8", "surrogateescape")
    return proc.returncode, (raw.split("\0")[:-1] if raw else [])


# settings that make git connect elsewhere than the URL shows, or without verifying it (cross-check of
# 2026-11-14): the push transport is replaced, handed to a helper, pinned to another address or unverified
TRANSPORT_ENV = (("GIT_SSH", "replaces the ssh program"), ("GIT_SSH_COMMAND", "replaces the ssh command"),
                 ("GIT_PROXY_COMMAND", "replaces the connection"), ("GIT_SSL_NO_VERIFY", "disables TLS verification"))
TRANSPORT_CONFIG = ((r"^core\.sshcommand$", "replaces the ssh command"),
                    (r"^core\.gitproxy$", "replaces the connection"),
                    (r"^remote\.origin\.vcs$", "hands the push to a remote helper"),
                    (r"^http\..*curloptresolve$", "pins a host name to another address"))


def _transport_overrides(cdir):
    """What would make the push connect elsewhere than its URL, or without
    verifying it: the environment variables and the git settings of
    TRANSPORT_ENV / TRANSPORT_CONFIG (every scope git reads for the clone)
    and a TLS verification (`http.sslVerify`) turned off. A proxy with TLS
    verification is not one of them (the TLS session stays with github.com)."""
    out = []
    for var, why in TRANSPORT_ENV:
        if os.environ.get(var):
            out.append("the environment variable %s is set (it %s)" % (var, why))
    git = ["git", "-C", str(cdir), "config"]
    for rx, why in TRANSPORT_CONFIG:
        rc, o, _ = _run(git + ["--get-regexp", rx], timeout=30)
        if rc == 0:
            for key in sorted({line.split(None, 1)[0] for line in _lines(o)}):
                out.append("%s is set (it %s)" % (key, why))
        elif rc != 1:
            out.append("the git configuration of the clone cannot be read")
    rc, o, _ = _run(git + ["--type=bool", "--get-regexp", r"^http\..*sslverify$"], timeout=30)
    if rc == 0:
        for line in _lines(o):
            key, _sep, value = line.partition(" ")
            if value.strip() != "true":
                out.append("%s is %s (TLS verification disabled)" % (key, value.strip() or "false"))
    elif rc != 1:
        out.append("http.sslVerify cannot be read as a boolean")
    return list(dict.fromkeys(out))


def _origin_remote(cdir, eff, repo_of_url):
    """(facts, problem, push URLs): the URLs `git push origin` really uses —
    `git remote get-url [--push] --all` applies pushurl, insteadOf and
    pushInsteadOf — and the repository they designate. A problem unless
    there is exactly one fetch URL and one push URL (an empty entry counts),
    both written in an accepted form (_github_repo_of_url, strict) and
    designating the configured repository on github.com, like the
    destination's own URL, and unless nothing makes git connect elsewhere
    than these URLs or without verifying them (_transport_overrides); a
    refused URL is shown with the host git would really contact. The single
    remote check of this module: identity of the authorized repository for
    every send (2026-11-14), and the first condition of I-06."""
    git = ["git", "-C", str(cdir)]
    rc1, fetch_out, _ = _run(git + ["remote", "get-url", "--all", "origin"], timeout=30)
    rc2, push_out, _ = _run(git + ["remote", "get-url", "--push", "--all", "origin"], timeout=30)
    rc3, raw_urls = _config_values(cdir, "remote.origin.url")
    rc4, raw_push = _config_values(cdir, "remote.origin.pushurl")
    raw_push = raw_push if rc4 == 0 else []
    fetch_urls, push_urls = _lines(fetch_out), _lines(push_out)
    clean_urls, clean_push = [u.strip() for u in raw_urls if u.strip()], [u.strip() for u in raw_push if u.strip()]
    facts = {"fetch_urls": [_redact_text(u) for u in fetch_urls],
             "push_urls": [_redact_text(u) for u in push_urls],
             "pushurl_configured": bool(raw_push),
             "rewritten": fetch_urls != clean_urls or push_urls != (clean_push or clean_urls),
             "transport_overrides": None, "repository": None}
    repo = eff.get("repo")
    fix_clone = ("inspect the remote of the clone %s and remove yourself what sends the push elsewhere "
                 "(remote.origin.pushurl, several or empty URLs, an insteadOf / pushInsteadOf rewriting — possibly in "
                 "your global git configuration), or move the clone away and run fetch again" % cdir)
    if rc1 or rc2 or rc3 or rc4 not in (0, 1):
        return facts, "the URLs of the clone's origin cannot be read by git — %s" % fix_clone, None
    empty = [key for key, values in (("remote.origin.url", raw_urls), ("remote.origin.pushurl", raw_push))
             if any(not v.strip() for v in values)]
    if empty:
        return facts, ("origin has an empty URL entry (%s): git would try to use it too — %s"
                       % (", ".join(empty), fix_clone)), None
    if len(fetch_urls) != 1:
        return facts, "origin has %d fetch URLs, exactly one is accepted — %s" % (len(fetch_urls), fix_clone), None
    if len(push_urls) != 1:
        return facts, ("origin has %d push URLs (git would push to each of them), exactly one is accepted — %s"
                       % (len(push_urls), fix_clone)), None
    how = []
    if facts["pushurl_configured"]:
        how.append("remote.origin.pushurl is set")
    if facts["rewritten"]:
        how.append("an insteadOf / pushInsteadOf rewriting applies")
    how = " (%s)" % ", ".join(how) if how else ""
    forms = ("accepted forms only: %s — no credentials, port, query or fragment"
             % ", ".join(GH_ACCEPTED_URL_FORMS))
    if not _same_repo(repo_of_url(eff.get("clone_url")), repo):
        return facts, ("the destination's URL %s is not an https or ssh URL of the github.com repository %s (%s): "
                       "nothing is sent to a repository whose identity cannot be established as the one configured "
                       "for the destination (and a closed source only to a GitHub repository whose real visibility "
                       "is checked) — configure the destination with it (destination-remove, then destination-add "
                       "--repo %s without --url, or with its github.com URL), then run export-plan and fetch again"
                       % (_shown_url(eff.get("clone_url")), repo, forms, repo)), None
    push_repo, fetch_repo = repo_of_url(push_urls[0]), repo_of_url(fetch_urls[0])
    if push_repo is None:
        return facts, ("the push URL %s is not an https or ssh URL of a github.com repository (%s)%s — %s"
                       % (_shown_url(push_urls[0]), forms, how, fix_clone)), None
    if fetch_repo is None:
        return facts, ("the fetch URL %s is not an https or ssh URL of a github.com repository (%s)%s — %s"
                       % (_shown_url(fetch_urls[0]), forms, how, fix_clone)), None
    if not _same_repo(push_repo, fetch_repo):
        return facts, ("git would push to %s while the clone fetches from %s%s — %s"
                       % (push_repo, fetch_repo, how, fix_clone)), None
    if not _same_repo(push_repo, repo):
        return facts, ("git would push to %s while the destination %r is configured for %s%s — %s"
                       % (push_repo, eff.get("name"), repo, how, fix_clone)), None
    transport = _transport_overrides(cdir)
    facts["transport_overrides"] = transport
    if transport:
        return facts, ("git would not connect to %s as its URL shows, or would not verify it: %s — PWS sends only "
                       "through git's own transport to the URL it checked: remove that setting from the clone (`git "
                       "-C <clone> config --unset <key>`), from your git configuration or from the environment of "
                       "this command, then run export-diff again" % (repo, "; ".join(transport))), None
    facts["repository"] = push_repo
    return facts, None, push_urls


def _staged_payload(staging, included):
    """([(target, role, bytes)], error): the staged files of a plan."""
    files_dir = Path(staging) / "files"
    out = []
    for item in included:
        target = files_dir / item["to"]
        data, err = (_read_regular(target) if core.is_within(files_dir, target)
                     else (None, "outside the staging folder"))
        if err:
            return None, "staged file %s cannot be read (%s)" % (item["to"], err)
        out.append((item["to"], item.get("role"), data))
    return out, None


def _closed_content(root, slug, files):
    """(content, error): which of `files` [(target, role, bytes)] carry closed
    source code, judged on the manifests as they are NOW (re-read): the
    product's source when its source_visibility is not `public`; its PUBLIC
    source when it is a copy of another product's closed source or
    reproduces three of its code lines (review RS-04); a document the
    public-destination policy would exclude (copy or code line of the
    product's closed source, Pine code of a closed-source product, three code
    lines of another product's closed source)."""
    if files is None:
        return None, "the files to send cannot be read"
    products = scan.scan_workspace(root)["products"]
    product = next((p for p in products if p["slug"] == slug), None)
    if product is None or product["product_structure_status"] != "REGISTERED":
        return None, "product %r cannot be read again as a REGISTERED product" % slug
    visibility = (product.get("license") or {}).get("source_visibility")
    own = None
    if visibility != "public":
        sdata = None
        if product.get("source"):
            try:
                sdata = Path(product["source"]).read_bytes()
            except OSError:
                sdata = None
        own = (sdata, _code_lines(sdata.decode("utf-8", "replace")) if sdata is not None else set())
    others = _closed_sources(root, products, slug)
    hits = []
    for target, role, data in files:
        if role == "source" and visibility != "public":
            reason = "the product's source (source_visibility=%s)" % visibility
        elif role == "source":
            copied = _pine_code_reason(data.decode("utf-8", "replace"), data, None, others)
            reason = "the product's public source %s" % copied if copied else None
        else:
            reason = _pine_code_reason(data.decode("utf-8", "replace"), data, own, others)
        if reason:
            hits.append({"path": target, "reason": reason})
    return {"source_visibility": visibility, "files": hits}, None


def _destination_check(cdir, eff, repo_of_url=None):
    """(check, push URLs): IDENTITY of the repository the holder authorized,
    for every send (holder's request of 2026-11-14) — the single remote check
    of this module (_origin_remote), read now from the clone's git
    configuration (offline). check["ok"] is True only when the destination's
    own URL and the clone's single fetch URL and single push URL designate
    the configured repository; the push URLs are returned only then."""
    facts, problem, push_urls = _origin_remote(cdir, eff, repo_of_url or _github_repo_of_url)
    check = {"required": True, "performed": True, "ok": problem is None, "checked_at": _now(),
             "configured": {"name": eff.get("name"), "repo": eff.get("repo"), "visibility": eff.get("visibility"),
                            "url": eff.get("clone_url")},
             "remote": facts, "error": problem, "limit": DESTINATION_CHECK_LIMIT}
    return check, (push_urls if problem is None else None)


def _send_refusal(destination, visibility):
    """Why a send is refused, from its two checks, or None."""
    if visibility is not None and not visibility["ok"]:
        return visibility["error"]
    if not destination["ok"]:
        return destination["error"]
    return None


def _send_checks(root, slug, ctx, cdir, files, gh_runner=None, repo_of_url=None):
    """(destination check, visibility check, push URLs) of a send. The
    destination check (identity of the authorized repository) is made for
    EVERY send; the visibility check (I-06, privacy) only when the send
    carries closed content — None otherwise: it is ok only when the manifest
    re-read now, the declared destination, the remote git really pushes to
    and the answer of GitHub all agree on a PRIVATE repository. The push URLs
    are returned only when every check passed; nothing stored is reused."""
    eff = ctx["eff"]
    destination, push_urls = _destination_check(cdir, eff, repo_of_url)
    content, err = _closed_content(root, slug, files)
    if not err and not content["files"]:
        return destination, None, push_urls
    check = {"required": True, "performed": False, "ok": False, "checked_at": None,
             "closed_content": content["files"] if content else [],
             "configured": {"name": eff.get("name"), "repo": eff.get("repo"), "visibility": eff.get("visibility")},
             "remote": None, "observed": None, "error": None, "limit": VISIBILITY_CHECK_LIMIT}
    if err:
        check["error"] = "%s — nothing is sent" % err
        return destination, check, None
    planned = (ctx["plan"].get("license") or {}).get("source_visibility")
    if planned != content["source_visibility"]:
        check["error"] = ("source visibility changed since the plan (plan %r, now %r) — run export-plan again"
                          % (planned, content["source_visibility"]))
        return destination, check, None
    if eff.get("visibility") != "private":
        check["error"] = "closed content is only sent to a destination declared private"
        return destination, check, None
    check["remote"] = destination["remote"]
    if not destination["ok"]:
        check["error"] = "%s (the real visibility was not queried)" % destination["error"]
        return destination, check, None
    obs, problem = _observe_repository(eff["repo"], gh_runner)
    check["performed"] = True
    check["checked_at"] = obs.pop("checked_at")
    check["observed"] = obs
    if problem:
        check["error"] = ("the real visibility of %s on GitHub could not be established: %s — a closed source "
                          "is never sent without this check" % (eff["repo"], problem))
    elif not _same_repo(obs["repository"], eff["repo"]):
        check["error"] = ("GitHub resolves %s to %s (renamed or transferred repository) — update the destination "
                          "yourself (destination-remove, then destination-add --repo %s), then run export-plan, "
                          "fetch and export-diff again" % (eff["repo"], obs["repository"], obs["repository"]))
    elif obs["visibility"] != "PRIVATE":
        check["error"] = ("GitHub reports %s as %s (checked %s): a closed source is only sent to a repository "
                          "whose real visibility is PRIVATE — change the repository on GitHub yourself (holder's "
                          "act, outside this workflow) or choose another destination, then run export-diff again"
                          % (obs["repository"], obs["visibility"], check["checked_at"]))
    else:
        check["ok"] = True
        return destination, check, push_urls
    return destination, check, None


# ---- comparison and publication -----------------------------------------------

def _clone_target_problem(cdir, rel):
    """Why `rel` cannot be written into the clone as planned, or None: invalid
    or escaping path, `.git`, a symbolic link on the way, a FILE of the
    repository where a folder is needed, an entry of the repository whose
    name differs only by case from a component of `rel` (on a case-insensitive
    file system git would update that entry instead, under its old name —
    cross-check of 2026-11-14), or a target that is not a regular file."""
    parts = Path(rel).parts
    if not parts or Path(rel).is_absolute() or ".." in parts:
        return "invalid target path"
    if any(p.lower() == ".git" for p in parts):
        return "inside the .git folder"
    probe = Path(cdir)
    for i, part in enumerate(parts):
        try:
            names = os.listdir(str(probe))
        except OSError:
            names = []
        variant = next((n for n in names if n != part and n.casefold() == part.casefold()), None)
        if variant is not None:
            return ("the destination repository holds %s, whose name differs from %s only by case — rename or remove "
                    "it in the repository yourself, or keep the original name"
                    % ("/".join(list(parts[:i]) + [variant]), "/".join(parts[:i + 1])))
        probe = probe / part
        if probe.is_symlink():
            return "symbolic link in the destination repository"
        if not probe.exists():
            break
        if i < len(parts) - 1 and not probe.is_dir():
            return ("a file of the destination repository stands where a folder is needed (%s)"
                    % "/".join(parts[:i + 1]))
    target = Path(cdir) / rel
    if not core.is_within(cdir, target):
        return "escapes the clone"
    if target.exists() and not target.is_file():
        return "not a regular file in the destination repository"
    return None


def _git_blob(cdir, data, path=None):
    """Object id git gives `data` in the clone: the exact bytes (`--no-filters`)
    or, with `path`, the bytes git would store for that path (end-of-line
    conversion and filters of .gitattributes and of the git configuration
    applied, as `git add` does). None when git cannot hash it."""
    args = ["git", "-C", str(cdir), "hash-object", "--stdin"] + (["--path", path] if path else ["--no-filters"])
    try:
        proc = subprocess.run(args, input=data, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.decode("ascii", "replace").strip()
    return out if proc.returncode == 0 and out else None


def _altered_by_git(cdir, files):
    """[(path, why)] of the files [(path, role, bytes)] whose bytes git would
    change when committing them into the clone — the exact bytes of the plan
    (an original legal document verbatim, among others) could not be sent."""
    out = []
    for rel, _role, data in files:
        exact, stored = _git_blob(cdir, data), _git_blob(cdir, data, rel)
        if exact is None or stored is None:
            out.append((rel, "git cannot hash it in the clone"))
        elif exact != stored:
            out.append((rel, "git would change its bytes when committing it (end-of-line conversion or a filter set "
                             "by the repository's .gitattributes or by your git configuration, e.g. core.autocrlf)"))
    return out


def _altered_text(altered):
    return ("the exact bytes of the plan cannot be committed: %s — change these settings yourself (for example a "
            "`-text` attribute for these files in the repository's .gitattributes, or core.autocrlf=false), then run "
            "export-diff again" % "; ".join("%s: %s" % item for item in altered))


def _commit_problem(cdir, before, files):
    """Why the new commit of the clone is not exactly the plan, or None: one
    new commit on top of `before`, changing only the planned paths, each to
    the exact bytes of the plan."""
    git = ["git", "-C", str(cdir)]
    rc, parent, _ = _run(git + ["rev-parse", "HEAD^"])
    if rc != 0 or parent != before:
        return "HEAD is not one new commit on top of the checked state"
    try:
        proc = subprocess.run(git + ["diff", "--name-only", "-z", "--no-renames", before, "HEAD"],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "the commit cannot be read"
    if proc.returncode != 0:
        return "the commit cannot be read"
    changed = {n for n in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if n}
    extra = sorted(changed - {rel for rel, _role, _data in files})
    if extra:
        return "it also changes %s, outside the plan" % ", ".join(extra[:5])
    for rel, _role, data in files:
        rc, stored, _ = _run(git + ["rev-parse", "HEAD:%s" % rel])
        if rc != 0 or stored != _git_blob(cdir, data):
            return "%s is not committed under this name with the exact bytes of the plan" % rel
    return None


def _changes(cdir, included):
    changes = []
    for item in included:
        problem = _clone_target_problem(cdir, item["to"])
        if problem:
            changes.append({"path": item["to"], "change": "REFUSED (%s)" % problem})
            continue
        target = Path(cdir) / item["to"]
        if not target.exists():
            changes.append({"path": item["to"], "change": "added"})
            continue
        data, err = _read_regular(target)
        if err:
            changes.append({"path": item["to"], "change": "REFUSED (%s in the destination repository)" % err})
        elif core.sha256_bytes(data) != item["sha256"]:
            changes.append({"path": item["to"], "change": "modified"})
        else:
            changes.append({"path": item["to"], "change": "unchanged"})
    return changes


def _diff(root, slug, dest_name):
    """(result, context, clone info): full revalidation, then comparison."""
    ctx, refusal = _revalidate(root, slug, dest_name)
    if refusal:
        return refusal, None, None
    eff, plan = ctx["eff"], ctx["plan"]
    info = _inspect_clone(root, dest_name, eff)
    problem = _clone_refusal(info, dest_name)
    if problem:
        return ({"ok": False, "error": problem, "destination": eff, "clone": info,
                 "staging": str(ctx["staging"]), "included": plan["included"]}, None, None)
    cdir = Path(info["path"])
    warnings = list(plan.get("warnings") or [])
    target_dir = cdir / plan["target_dir"]
    if eff["visibility"] != "private" and plan["license"].get("source_visibility") != "public" \
            and core.is_within(cdir, target_dir) and target_dir.is_dir():
        already = sorted(p.relative_to(cdir).as_posix() for p in target_dir.glob("*.pine"))
        if already:
            warnings.append("the repository already holds %s although this product's source is closed and the "
                            "destination public — check the repository content and its real visibility "
                            "(holder's act, outside this workflow)" % ", ".join(already))
    result = {"ok": True, "slug": slug, "destination": eff, "clone": info,
              "changes": _changes(cdir, plan["included"]), "excluded": plan["excluded"],
              "warnings": warnings, "staging": str(ctx["staging"]), "plan_created_at": plan.get("created_at")}
    return result, ctx, info


def _would_push(diff):
    changes = diff.get("changes") or []
    return (not any(c["change"].startswith("REFUSED") for c in changes)
            and any(c["change"] in ("added", "modified") for c in changes))


def export_diff(root, slug, dest_name, gh_runner=None, repo_of_url=None):
    """Compare the staged files with the local clone (no write): plan,
    configuration, manifest, staging and clone are revalidated first. When
    something would be pushed, the identity of the destination is checked
    (every send, offline) and, when the send would carry closed content, the
    real GitHub repository is observed (I-06, network read through gh); both
    are presented, with ok=false when publish would refuse. `gh_runner(args)`
    and `repo_of_url(url)` replace the real gh and the github.com URL reading
    (tests only)."""
    diff, ctx, info = _diff(root, slug, dest_name)
    if diff.get("ok") and _would_push(diff):
        files, err = _staged_payload(ctx["staging"], ctx["plan"]["included"])
        if err:
            diff.update(ok=False, error="%s — run export-plan again" % err)
        else:
            destination, check, _ = _send_checks(root, slug, ctx, Path(info["path"]), files, gh_runner,
                                                 repo_of_url)
            diff["destination_check"] = destination
            if check is not None:
                diff["visibility_check"] = check
            altered = _altered_by_git(Path(info["path"]), files)
            diff["content_check"] = {"ok": not altered, "altered": [{"path": p, "reason": w} for p, w in altered]}
            refusal = _send_refusal(destination, check) or (_altered_text(altered) if altered else None)
            if refusal:
                diff.update(ok=False, error="publish would refuse this plan: %s" % refusal)
    return _redact(diff)


STATE_LEFT_STEPS = {
    "destination changed after the local commit": (
        "inspect the remote yourself (`git -C <clone> remote -v`, `git -C <clone> config --get-regexp "
        "'^(remote|url|core)\\.'`, your global git configuration and the environment) and remove what changed the "
        "destination (remote.origin.pushurl, a second URL, an insteadOf / pushInsteadOf rewriting, a transport "
        "setting); "),
    "the local commit differs from the plan": "inspect the commit yourself (`git -C <clone> show --stat HEAD`); ",
}


def _state_left(dest_name, ctx, cdir, eff, stage, commit, paths, recheck=None):
    """What a publication stopped after a local write leaves on disk: the
    stage reached, whether something was pushed (False; None when git push
    itself reported an error), the clone, its branch, the commit (if any),
    the files written, the unpublished local work as git reports it now, the
    staged plan (kept) and the next steps, all actions of the holder."""
    branch = eff["branch"]
    work = _unpublished_work(cdir, branch)
    pushed = None if stage == "git push failed" else False
    lead = ("git push reported an error: check the repository and the clone yourself before anything else; "
            if pushed is None else "nothing was pushed; ")
    return {"stage": stage, "pushed": pushed, "clone": str(cdir), "branch": branch, "commit": commit,
            "files_written": list(paths), "committed": commit is not None, "unpublished_work": work,
            "remote_now": (recheck or {}).get("remote"), "staging": str(ctx["staging"]),
            "plan": "kept unchanged (PLAN.json and the staged files)",
            "next": ("%sfetch, export-diff and publish refuse this clone while it holds unpublished local work. %s"
                     "then inspect the work (`git -C <clone> status`, `git -C <clone> log origin/%s..HEAD`), discard "
                     "it yourself and run `github fetch --destination %s`, then `github export-diff` and `github "
                     "publish` again" % (lead, STATE_LEFT_STEPS.get(stage, ""), branch, dest_name))}


def publish(root, slug, dest_name, message, yes=False, gh_runner=None, repo_of_url=None):
    """Copy the staged files into the clone, commit and push. Every check of
    export-diff runs first; an explicit --yes is required on top of them and
    replaces none; `git push` remains subject to the permission prompt. Every
    send is preceded by the check of the destination's identity and a send
    carrying closed content by the check of the real GitHub repository
    (I-06), both made again here as the last step before anything is written
    — an earlier result is never reused; the remote is read again right
    before `git push` and, when it changed after the local commit, nothing
    is pushed and `state_left` describes what stays on disk."""
    return _redact(_publish(root, slug, dest_name, message, yes, gh_runner, repo_of_url))


def _publish(root, slug, dest_name, message, yes, gh_runner, repo_of_url):
    diff, ctx, info = _diff(root, slug, dest_name)
    if not diff.get("ok"):
        return diff
    eff = diff["destination"]
    base = {"destination": eff, "clone": info, "diff": diff}
    if any(c["change"].startswith("REFUSED") for c in diff["changes"]):
        return dict(base, ok=False, error="refused path in the plan")
    if not any(c["change"] in ("added", "modified") for c in diff["changes"]):
        return dict(base, ok=True, published=False, note="nothing to publish (all unchanged)")
    if not yes:
        return dict(base, ok=False, error="refused without --yes — the holder authorizes this precise plan "
                                          "(destination, files, message) first")
    if not isinstance(message, str) or not message.strip():
        return dict(base, ok=False, error="a commit message is required")
    cdir = Path(info["path"])
    files_dir = ctx["staging"] / "files"
    verified = []
    for item in ctx["plan"]["included"]:      # every check first: nothing is written on a refusal
        data, err = _read_regular(files_dir / item["to"])
        if err or core.sha256_bytes(data) != item["sha256"]:
            return dict(base, ok=False, error="staged file %s changed during publication — nothing written; "
                                              "run export-plan again" % item["to"])
        problem = _clone_target_problem(cdir, item["to"])
        if problem:
            return dict(base, ok=False, error="target %s refused (%s) — nothing written" % (item["to"], problem))
        verified.append((item["to"], item.get("role"), data))
    # last checks before anything is written into the clone, committed and pushed: identity of the destination
    # (every send, 2026-11-14) and, for closed content, the real visibility (I-06)
    destination, check, push_urls = _send_checks(root, slug, ctx, cdir, verified, gh_runner, repo_of_url)
    base["destination_check"] = destination
    if check is not None:
        base["visibility_check"] = check
    refusal = _send_refusal(destination, check)
    if refusal or push_urls is None:
        return dict(base, ok=False, published=False,
                    error="refused before any write or push: %s" % (refusal or "the push URL is not established"))
    # the exact bytes of the plan, or nothing: git must not change them when committing (cross-check 2026-11-14)
    altered = _altered_by_git(cdir, verified)
    base["content_check"] = {"ok": not altered, "altered": [{"path": p, "reason": w} for p, w in altered]}
    if altered:
        return dict(base, ok=False, published=False,
                    error="refused before any write or push: %s" % _altered_text(altered))
    git = ["git", "-C", str(cdir)]
    rc, before, _ = _run(git + ["rev-parse", "HEAD"])
    if rc != 0 or not before:
        return dict(base, ok=False, published=False,
                    error="refused before any write or push: the commit of the clone cannot be read")
    paths = []
    try:
        for rel, _role, data in verified:
            dst = cdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(str(dst), "wb") as f:
                f.write(data)
            paths.append(rel)
    except OSError as exc:
        return dict(base, ok=False, published=False, paths=paths,
                    state_left=_state_left(dest_name, ctx, cdir, eff, "writing into the clone failed", None, paths),
                    error="writing %s into the clone %s failed (%s) — nothing committed nor pushed; the state of the "
                          "clone as git reports it is in state_left" % (rel, cdir, exc.strerror or exc))
    rc, out, err = _run(git + ["add", "--"] + paths)
    if rc != 0:
        return dict(base, ok=False, published=False, paths=paths,
                    state_left=_state_left(dest_name, ctx, cdir, eff, "git add failed", None, paths),
                    error="git add failed: %s — nothing committed nor pushed; the state of the clone %s as git "
                          "reports it is in state_left" % (err, cdir))
    # no hook runs in the publication clone: nothing outside the plan is committed (cross-check of 2026-11-14)
    rc, out, err = _run(git + ["-c", "core.hooksPath=/dev/null", "commit", "--no-verify", "-m", message])
    if rc != 0:
        return dict(base, ok=False, published=False, paths=paths,
                    state_left=_state_left(dest_name, ctx, cdir, eff, "git commit failed", None, paths),
                    error="git commit failed: %s — nothing pushed; the state of the clone %s as git reports it is in "
                          "state_left" % (err or out, cdir))
    _, commit, _ = _run(git + ["rev-parse", "HEAD"])
    commit = commit or None
    # the commit is exactly the plan: one new commit, only the planned paths, each with the exact bytes
    problem = _commit_problem(cdir, before, verified)
    if problem:
        return dict(base, ok=False, published=False, paths=paths, commit=commit,
                    state_left=_state_left(dest_name, ctx, cdir, eff, "the local commit differs from the plan",
                                           commit, paths),
                    clone=_inspect_clone(root, dest_name, eff),
                    error="the local commit %s differs from the plan (%s) — nothing pushed; it stays in the local "
                          "clone %s as unpublished local work (details in state_left); discard it yourself, then run "
                          "fetch" % (commit, problem, cdir))
    # the destination checked a moment ago is still the one the push will use: read again right before the push
    again, push_again = _destination_check(cdir, eff, repo_of_url)
    if not again["ok"] or push_again != push_urls:
        why = again["error"] or ("the push URL changed since the check (checked: %s; now: %s)"
                                 % (", ".join(push_urls), ", ".join(push_again or [])))
        return dict(base, ok=False, published=False, paths=paths, commit=commit, destination_recheck=again,
                    state_left=_state_left(dest_name, ctx, cdir, eff, "destination changed after the local commit",
                                           commit, paths, again),
                    clone=_inspect_clone(root, dest_name, eff),
                    error="the destination of the clone changed after the check (%s) — nothing pushed; commit %s "
                          "stays in the local clone %s as unpublished local work (details in state_left); remove "
                          "what changed the destination, discard that commit yourself, then run fetch"
                          % (why, commit, cdir))
    branch = eff["branch"]
    rc, out, err = _run(git + ["-c", "core.hooksPath=/dev/null", "push", "--no-verify", "origin",
                               "refs/heads/%s:refs/heads/%s" % (branch, branch)], timeout=600)
    res = dict(base, ok=rc == 0, published=rc == 0, paths=paths, commit=commit or None,
               detail=(err or out)[-400:])
    res["clone"] = _inspect_clone(root, dest_name, eff)
    if rc != 0:
        res["state_left"] = _state_left(dest_name, ctx, cdir, eff, "git push failed", commit, paths)
        work = res["state_left"]["unpublished_work"]
        if work.get("known") and work.get("local_commits") == 0:
            res["error"] = ("git push reported an error although, according to the clone, origin/%s now holds "
                            "commit %s — inspect the clone %s and the repository yourself before anything else"
                            % (branch, commit, cdir))
        else:
            res["error"] = ("git push failed — commit %s stays in the local clone %s as unpublished local work (git "
                            "reports %s); inspect it, push or discard it yourself, then run fetch"
                            % (commit, cdir, _describe_work(work)))
    return res
