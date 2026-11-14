# SPDX-License-Identifier: Apache-2.0
"""PWS personal configuration — `pws.config.json` at the workspace root.

Separated from Claude Code's own settings (`.claude/settings*.json`): PWS
owns identity, language, the persisted TradingView mode, GitHub destinations
and maintenance preferences; Claude Code keeps permissions and approvals.
The file is personal (gitignored, copied into worktrees via
`.worktreeinclude`) and never part of a distribution.

Reading never fails: a missing file yields the documented defaults (English,
manual TradingView mode, identity not configured) plus `present: False`;
a malformed file yields the defaults plus an actionable `error`.

Writing is a read-modify-write transaction under the shared PWS writers'
lock (`pws.config.json.lock`), with freshest-state re-read, refusal of a
concurrent modification, atomic replace and post-write verification — the
same contract as every other PWS writer (FILE_CONTRACTS.md).
"""
import copy
import json
import re
from pathlib import Path

from . import core, i18n, version

CONFIG_REL = Path("pws.config.json")
PROFILES_FOR_DEFAULT = ("FREE", "PRIVATE", "COMMERCIAL")

DEFAULTS = {
    "schema_version": version.CONFIG_SCHEMA_VERSION,
    "workspace_version": None,       # None until `init` or `migrate` records it
    "language": i18n.DEFAULT_LANGUAGE,
    "identity": {
        "copyright_holder": None,     # e.g. "Legacy Holder"
        "header_aliases": [],         # extra © marks accepted in existing headers
        "default_profile": "FREE",
    },
    "tv_validation_mode": "manual",
    "github": {"destinations": []},
    "maintenance": {"startup_cleanup": True},
    "migrations": [],
}


def config_path(root):
    return Path(root) / CONFIG_REL


def _lock_path(root):
    return str(config_path(root)) + ".lock"


def _merge_defaults(raw):
    data = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return data
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            merged = dict(data[key])
            merged.update(value)
            data[key] = merged
        else:
            data[key] = value
    return data


def validate(data):
    """Actionable problems of a (merged) configuration. Empty = valid."""
    problems = []
    sv = data.get("schema_version")
    if not isinstance(sv, int) or isinstance(sv, bool) or sv != version.CONFIG_SCHEMA_VERSION:
        problems.append("schema_version must be %d, got %r" % (version.CONFIG_SCHEMA_VERSION, sv))
    if data.get("language") not in i18n.LANGUAGES:
        problems.append("language must be one of %s, got %r" % (list(i18n.LANGUAGES), data.get("language")))
    if data.get("tv_validation_mode") not in core.MODES:
        problems.append("tv_validation_mode must be one of %s, got %r"
                        % (list(core.MODES), data.get("tv_validation_mode")))
    choice = data.get(MODE_CHOICE_KEY)
    if choice is not None and not (isinstance(choice, dict) and choice.get("by") == "owner"
                                   and isinstance(choice.get("at"), str)):
        problems.append("%s must be null or an object {by: owner, at: <date>}" % MODE_CHOICE_KEY)
    ident = data.get("identity")
    if not isinstance(ident, dict):
        problems.append("identity must be an object")
    else:
        holder = ident.get("copyright_holder")
        if holder is not None and (not isinstance(holder, str) or not holder.strip()):
            problems.append("identity.copyright_holder must be null or a non-blank string")
        aliases = ident.get("header_aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
            problems.append("identity.header_aliases must be a list of non-blank strings")
        if ident.get("default_profile") not in PROFILES_FOR_DEFAULT:
            problems.append("identity.default_profile must be one of %s" % list(PROFILES_FOR_DEFAULT))
    gh = data.get("github")
    if not isinstance(gh, dict) or not isinstance(gh.get("destinations"), list):
        problems.append("github.destinations must be a list")
    else:
        names = set()
        for i, dest in enumerate(gh["destinations"]):
            dp = destination_problems(dest)
            if dp:
                problems.append("github.destinations[%d]: %s" % (i, "; ".join(dp)))
                continue
            if dest["name"] in names:
                problems.append("github.destinations: duplicate name %r" % dest["name"])
            names.add(dest["name"])
    maint = data.get("maintenance")
    if not isinstance(maint, dict) or not isinstance(maint.get("startup_cleanup"), bool):
        problems.append("maintenance.startup_cleanup must be a boolean")
    if not isinstance(data.get("migrations"), list):
        problems.append("migrations must be a list")
    wv = data.get("workspace_version")
    if wv is not None and not isinstance(wv, str):
        problems.append("workspace_version must be null or a string")
    return problems


DESTINATION_VISIBILITIES = ("public", "private")
# provenance of the TradingView mode when the owner set it explicitly (F-14)
MODE_CHOICE_KEY = "tv_validation_mode_choice"
# a destination branch becomes a refspec: a plain branch name only
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def destination_problems(dest):
    """Validate one GitHub destination entry."""
    problems = []
    if not isinstance(dest, dict):
        return ["destination must be an object"]
    name = dest.get("name")
    if not core.is_safe_id(name):
        problems.append("name must be a safe identifier")
    repo = dest.get("repo")
    if not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/")):
        problems.append("repo must be 'owner/name'")
    if dest.get("visibility") not in DESTINATION_VISIBILITIES:
        problems.append("visibility must be 'public' or 'private'")
    prefix = dest.get("path_prefix", "")
    if not isinstance(prefix, str) or prefix.startswith("/") or ".." in Path(prefix).parts:
        problems.append("path_prefix must be a relative path without traversal")
    elif any(p.lower() == ".git" for p in Path(prefix).parts):
        problems.append("path_prefix must not designate the .git folder")
    branch = dest.get("branch", "main")
    if not isinstance(branch, str) or not branch or branch.startswith("-"):
        problems.append("branch must be a non-empty string")
    elif not BRANCH_RE.match(branch) or ".." in branch or "//" in branch \
            or branch.endswith(("/", ".lock")):
        problems.append("branch must be a plain branch name (letters, digits, . _ - /)")
    url = dest.get("url")
    if url is not None and (not isinstance(url, str) or not url.strip() or url.strip().startswith("-")):
        problems.append("url must be a non-empty string that is not an option")
    elif isinstance(url, str) and url_has_credentials(url):
        # review RS-02 (2026-11-13): credentials never live in the configuration
        problems.append("url must not embed credentials (use the gh or git credential helper)")
    return problems


_SCHEME_AUTHORITY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://([^/?#]*)")


def url_has_credentials(url):
    """True when a URL carries credentials in its authority (RFC 3986 parsing:
    the authority stops at the first « / », « ? » or « # »). An ssh URL may
    only name the « git » user; the scp-like form « git@host:path » is kept."""
    m = _SCHEME_AUTHORITY_RE.match(url.strip())
    if not m:
        return False
    scheme, authority = m.group(1).lower(), m.group(2)
    if "@" not in authority:
        return False
    user = authority.rsplit("@", 1)[0]
    return not (scheme == "ssh" and user == "git")


def redacted(data):
    """Copy of a configuration view whose GitHub destination URLs never show
    credentials (config show / config set output)."""
    out = copy.deepcopy(data)
    gh = out.get("github") if isinstance(out, dict) else None
    for dest in (gh.get("destinations") if isinstance(gh, dict) and isinstance(gh.get("destinations"), list) else []):
        if isinstance(dest, dict) and isinstance(dest.get("url"), str) and url_has_credentials(dest["url"]):
            url = dest["url"].strip()
            m = _SCHEME_AUTHORITY_RE.match(url)
            host = m.group(2).rsplit("@", 1)[1]
            dest["url"] = "%s://***@%s%s" % (m.group(1), host, url[m.end():])
    return out


def read_config(root):
    """Return {present, error, problems, data(merged with defaults), raw}."""
    path = config_path(root)
    out = {"present": False, "error": None, "problems": [], "data": None,
           "raw": None, "path": str(path)}
    if path.is_symlink() or (path.exists() and not core.is_within(root, path)):
        out["error"] = "pws.config.json is a symlink or escapes the workspace — not read"
        out["data"] = _merge_defaults(None)
        return out
    raw, err = core.read_json(path)
    if err == "missing":
        out["data"] = _merge_defaults(None)
        return out
    out["present"] = True
    if err:
        out["error"] = err
        out["data"] = _merge_defaults(None)
        return out
    if not isinstance(raw, dict):
        out["error"] = "pws.config.json is not a JSON object"
        out["data"] = _merge_defaults(None)
        return out
    out["raw"] = raw
    merged = _merge_defaults(raw)
    out["problems"] = validate(merged)
    # audit A-08: readers receive a TYPED view — a section of the wrong type is replaced by its
    # default in `data` (the problem stays reported, the doctor shows it BLOCKING, writers refuse)
    out["data"] = _typed_view(merged)
    return out


def _typed_view(data):
    """Copy of `data` whose sections have the documented types (defaults where not)."""
    view = dict(data)
    ident = view.get("identity") if isinstance(view.get("identity"), dict) else {}
    holder = ident.get("copyright_holder")
    aliases = ident.get("header_aliases")
    view["identity"] = {
        "copyright_holder": holder if isinstance(holder, str) else None,
        "header_aliases": [a for a in aliases if isinstance(a, str)] if isinstance(aliases, list) else [],
        "default_profile": ident.get("default_profile") if ident.get("default_profile") in PROFILES_FOR_DEFAULT
        else DEFAULTS["identity"]["default_profile"]}
    for key in ("copyright_holder", "header_aliases", "default_profile"):
        ident.pop(key, None)
    view["identity"].update({k: v for k, v in ident.items()})      # unknown keys kept as they are
    github = view.get("github") if isinstance(view.get("github"), dict) else {}
    dests = github.get("destinations")
    view["github"] = dict(github, destinations=[d for d in dests if isinstance(d, dict)
                                                and all(isinstance(d.get(k), str) for k in ("name", "repo"))]
                          if isinstance(dests, list) else [])
    maint = view.get("maintenance") if isinstance(view.get("maintenance"), dict) else {}
    view["maintenance"] = dict(maint, startup_cleanup=maint.get("startup_cleanup")
                               if isinstance(maint.get("startup_cleanup"), bool) else True)
    view["migrations"] = view["migrations"] if isinstance(view.get("migrations"), list) else []
    if not isinstance(view.get("language"), str):
        view["language"] = DEFAULTS["language"]
    if not isinstance(view.get("tv_validation_mode"), str):
        view["tv_validation_mode"] = DEFAULTS["tv_validation_mode"]
    return view


def language(root):
    """Configured user language (defaults apply when unconfigured)."""
    cfg = read_config(root)
    return i18n.normalize_language(cfg["data"].get("language"))


def identity(root):
    """Identity facts for header checks and templates."""
    cfg = read_config(root)
    ident = cfg["data"].get("identity") or {}
    holder = ident.get("copyright_holder")
    holder = holder.strip() if isinstance(holder, str) and holder.strip() else None
    aliases = [a.strip() for a in (ident.get("header_aliases") or [])
               if isinstance(a, str) and a.strip()]
    return {"configured": holder is not None, "copyright_holder": holder,
            "header_aliases": aliases,
            "default_profile": ident.get("default_profile") or "FREE"}


def update_config(root, mutate):
    """RMW transaction: `mutate(data)` edits the merged dict in place (or
    returns an error string to refuse). Returns {ok, error, data}."""
    path = config_path(root)
    if path.is_symlink():
        return {"ok": False, "error": "pws.config.json is a symlink — refusing"}
    try:
        with core.file_lock(_lock_path(root)):
            before = path.read_bytes() if path.exists() else None
            if before is not None:
                try:
                    raw = json.loads(before.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    return {"ok": False,
                            "error": "pws.config.json unreadable, refusing blind overwrite: %s" % exc}
                if not isinstance(raw, dict):
                    return {"ok": False, "error": "pws.config.json is not an object, refusing"}
            else:
                raw = None
            data = _merge_defaults(raw)
            # audit D-10: a write that does not concern the TradingView mode never
            # materializes its default — while the key is absent, a legacy value
            # of .claude/settings.local.json stays the mode in effect
            mode_absent = not (isinstance(raw, dict) and "tv_validation_mode" in raw)
            if mode_absent:
                data.pop("tv_validation_mode", None)
            try:
                refusal = mutate(data)
            except (TypeError, AttributeError, KeyError) as exc:
                return {"ok": False, "error": "pws.config.json has a section of an unexpected type (%s: %s) — "
                                              "fix it first (see `doctor`); nothing was written"
                                              % (type(exc).__name__, exc)}
            if refusal:
                return {"ok": False, "error": refusal}
            check = dict(data)
            check.setdefault("tv_validation_mode", DEFAULTS["tv_validation_mode"])
            problems = validate(check)
            if problems:
                return {"ok": False, "error": "refused, resulting configuration invalid: "
                                              + "; ".join(problems)}
            now = path.read_bytes() if path.exists() else None
            if now != before:
                return {"ok": False,
                        "error": "concurrent modification of pws.config.json detected — retry"}
            core.atomic_write_json(path, data)
            written, err = core.read_json(path)
    except TimeoutError as exc:
        return {"ok": False, "error": "config lock not acquired: %s" % exc}
    if err or not isinstance(written, dict):
        return {"ok": False, "error": "post-write validation failed: %s" % (err or "not an object")}
    return {"ok": True, "error": None, "data": written}


def init_config(root, language_code, copyright_holder=None, header_aliases=None,
                default_profile="FREE", force=False):
    """First configuration. Refuses to overwrite an existing file unless
    force=True (an existing personal configuration is never silently reset)."""
    path = config_path(root)
    if path.exists() and not force:
        return {"ok": False, "error": "pws.config.json already exists — use `config set` "
                                      "to change a value, or --force to reset it"}
    lang = i18n.normalize_language(language_code)
    if isinstance(language_code, str) and language_code.strip().lower()[:2] not in i18n.LANGUAGES:
        return {"ok": False, "error": "unsupported language %r (supported: %s)"
                % (language_code, ", ".join(i18n.LANGUAGES))}

    new = copy.deepcopy(DEFAULTS)
    new["language"] = lang
    new["workspace_version"] = version.WORKSPACE_VERSION
    new["identity"]["copyright_holder"] = (copyright_holder.strip() if isinstance(copyright_holder, str)
                                           and copyright_holder.strip() else None)
    new["identity"]["header_aliases"] = list(header_aliases or [])
    new["identity"]["default_profile"] = default_profile
    problems = validate(new)
    if problems:     # audit A-07: refused BEFORE anything is touched — the existing file stays as it is
        return {"ok": False, "error": "refused, resulting configuration invalid: " + "; ".join(problems)}
    if path.is_symlink():
        return {"ok": False, "error": "pws.config.json is a symlink — refusing"}
    try:
        with core.file_lock(_lock_path(root)):
            if path.exists() and not force:      # audit A-11: existence tested under the lock
                return {"ok": False, "error": "pws.config.json already exists — use `config set` "
                                              "to change a value, or --force to reset it"}
            core.atomic_write_json(path, new)    # replaced atomically: never deleted first
            written, err = core.read_json(path)
    except (TimeoutError, OSError) as exc:
        return {"ok": False, "error": "configuration not written (%s): the existing file, if any, is unchanged" % exc}
    if err or not isinstance(written, dict):
        return {"ok": False, "error": "post-write validation failed: %s" % (err or "not an object")}
    return {"ok": True, "error": None, "data": written}


def mode_choice_record(command):
    """Provenance of a TradingView mode set by an explicit command of the owner
    (F-14, 2026-11-13): it distinguishes a choice from a default written by
    `init`, so that a conflict with a legacy value can be resolved once."""
    return {"by": "owner", "at": core.precise_now(), "command": command}


def set_value(root, dotted_key, value):
    """Set one scalar/list value by dotted key (e.g. `identity.copyright_holder`)."""
    parts = dotted_key.split(".")
    allowed = {
        ("language",), ("tv_validation_mode",), ("identity", "copyright_holder"),
        ("identity", "header_aliases"), ("identity", "default_profile"),
        ("maintenance", "startup_cleanup"),
    }
    if tuple(parts) not in allowed:
        return {"ok": False, "error": "key %r is not settable this way (allowed: %s)"
                % (dotted_key, ", ".join(".".join(a) for a in sorted(allowed)))}

    def mutate(data):
        target = data
        for p in parts[:-1]:
            target = target.setdefault(p, {})
        target[parts[-1]] = value
        if tuple(parts) == ("tv_validation_mode",):
            data[MODE_CHOICE_KEY] = mode_choice_record("config set")
        return None

    return update_config(root, mutate)
