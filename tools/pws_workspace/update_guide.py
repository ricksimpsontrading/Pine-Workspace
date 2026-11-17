# SPDX-License-Identifier: Apache-2.0
"""Guided update of Pine Workspace (2.2.0) — one continuous path over the
EXISTING chain of `update` (status, check, fetch / prepare, plan, apply),
itself orchestrating `upgrade` (code) and `migrate` (data). Nothing here
downloads, copies, backs up, migrates or restores by itself: this module
calls those functions in order and turns their results into short summaries
in the configured language (what will change, what is kept, the planned
checks, the result, the remaining action, the recovery).

Stages, each explicit, none at session start:

  state     installed version, kind of installation, last dated search.
  search    explicit query of the official releases (stable only unless
            pre-releases are asked); an error or an absence of release is
            never "up to date"; release notes classified available / absent /
            unusable and never replaced by an invented description.
  prepare   download of the release found (or verification of a local
            package), then the hash-bound plan, as ONE step; the summary is
            the confirmation request: component, versions, origin, changes,
            files kept (`.pws-new` to merge), migrations, backup, checks,
            limits. On the development upstream it stops before any download
            with an understandable explanation (the existing refusal).
  apply     the existing `update.apply` on the approved plan file, then the
            account of what REALLY happened (never "nothing changed" once the
            code is installed; a diagnostic that did not run or is unusable is
            never a success).

The summaries are presentation only: the technical result of each stage is
returned unchanged under `result`.
"""
from pathlib import Path

from . import config, i18n, update, version

NOTES_MAX = 20000          # the release search keeps at most 20 000 characters of notes


def _lang(root, lang=None):
    return i18n.normalize_language(lang or config.language(root))


def summary(lang, headline, **sections):
    """A short summary: `headline` plus the non-empty sections among state,
    change, changed, kept, checks, checks_done, limits, result, recovery,
    next, notes — and `text`, the same content as plain text in `lang`."""
    order = ("state", "change", "changed", "kept", "checks", "checks_done", "limits", "result", "recovery",
             "next", "notes")
    out = {"language": lang, "headline": headline}
    lines = [headline]
    for key in order:
        items = [s for s in (sections.get(key) or []) if s]
        if not items:
            continue
        out[key] = items
        lines.append("")
        lines.append(i18n.t("guide.sec." + key, lang) + " :" if lang == "fr" else i18n.t("guide.sec." + key, lang) + ":")
        lines.extend("- " + s for s in items)
    if sections.get("confirm"):
        out["confirm"] = sections["confirm"]
        lines.append("")
        lines.append(sections["confirm"]["question"])
    out["text"] = "\n".join(lines)
    return out


def confirm_block(lang):
    return {"question": i18n.t("guide.confirm.question", lang),
            "options": [{"value": "apply", "label": i18n.t("guide.confirm.apply", lang)},
                        {"value": "cancel", "label": i18n.t("guide.confirm.cancel", lang)}],
            "binding": i18n.t("guide.confirm.binding", lang)}


def notes_state(text, truncated_at=NOTES_MAX):
    """(`available` | `absent` | `unusable`, reason, truncated): published
    notes are used only when they are readable text; nothing is ever inferred
    from their absence."""
    if text is None or (isinstance(text, str) and not text.strip()):
        return "absent", None, False
    if not isinstance(text, str):
        return "unusable", "not text", False
    bad = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
    if bad or "�" in text:
        return "unusable", "control or undecodable characters", False
    words = [w for w in text.split() if any(ch.isalnum() for ch in w)]
    if len(words) < 3:
        return "unusable", "too short to describe a change", False
    return "available", None, len(text) >= truncated_at


def notes_lines(lang, text):
    state, why, truncated = notes_state(text)
    if state == "available":
        lines = [i18n.t("guide.notes.available", lang)]
        if truncated:
            lines.append(i18n.t("guide.notes.truncated", lang, n=NOTES_MAX))
        return state, lines
    if state == "absent":
        return state, [i18n.t("guide.notes.absent", lang)]
    return state, [i18n.t("guide.notes.unusable", lang, why=why)]


def _kind_text(lang, kind):
    if kind.get("kind") == "distribution":
        return i18n.t("pwsg.kind.distribution", lang, v=kind.get("manifest_version"))
    return i18n.t("pwsg.kind.development", lang)


def _result_text(lang, rec):
    res = rec.get("result") or "not-searched"
    latest = (rec.get("latest") or {}).get("version") if isinstance(rec.get("latest"), dict) else None
    key = "pwsg.result." + res
    if not i18n.has_key(key):
        key = "pwsg.result.error"
    return i18n.t(key, lang, latest=latest, v=version.WORKSPACE_VERSION, error=rec.get("error") or res)


# ---- stage 1: state ------------------------------------------------------------

def state(root, lang=None):
    root = Path(root)
    lang = _lang(root, lang)
    st = update.status(root)
    kind = st["installation"]
    lines = []
    rec = st["last_check"]
    if not rec.get("checked_at"):
        lines.append(i18n.t("pwsg.search.none", lang))
    else:
        lines.append(i18n.t("pwsg.search.dated", lang, at=rec["checked_at"], result=_result_text(lang, rec)))
        if rec.get("source") == "simulated":
            lines.append(i18n.t("guide.simulated", lang))
    if st["pending_migrations"]:
        lines.append(i18n.t("pwsg.pending", lang, ids=", ".join(st["pending_migrations"])))
    limits = [i18n.t("pwsg.dev.explain", lang)] if kind["kind"] == "development" else []
    nxt = [i18n.t("pwsg.next.search", lang)]
    if rec.get("result") == "update-available" and kind["kind"] == "distribution":
        nxt = [i18n.t("pwsg.next.prepare", lang, latest=rec["latest"]["version"])]
    return {"stage": "state", "component": "pine-workspace", "result": st,
            "summary": summary(lang, i18n.t("pwsg.headline.status", lang, v=version.WORKSPACE_VERSION,
                                            kind=_kind_text(lang, kind)),
                               state=lines, limits=limits, next=nxt)}


# ---- stage 2: search -----------------------------------------------------------

def search(root, lang=None, fetch=None, include_prereleases=False):
    root = Path(root)
    lang = _lang(root, lang)
    rec = update.check(root, fetch=fetch, include_prereleases=include_prereleases)
    kind = update.installation_kind(root)
    res = rec.get("result")
    result = [_result_text(lang, rec)]
    notes, notes_status = [], None
    if rec.get("source") == "simulated":
        result.append(i18n.t("guide.simulated", lang))
    if rec.get("prereleases_skipped"):
        result.append(i18n.t("pwsg.search.prereleases_skipped", lang, n=rec["prereleases_skipped"]))
    latest = rec.get("latest") if isinstance(rec.get("latest"), dict) else None
    if latest and res == "update-available":
        if latest.get("published_at") or latest.get("html_url"):
            result.append(i18n.t("pwsg.search.published", lang, date=latest.get("published_at") or "?",
                                 url=latest.get("html_url") or "?"))
        if latest.get("prerelease"):
            result.append(i18n.t("pwsg.search.prerelease_chosen", lang))
        notes_status, notes = notes_lines(lang, latest.get("notes"))
    result.append(i18n.t("pwsg.search.nothing_changed", lang))
    limits, nxt = [], []
    if kind["kind"] == "development":
        limits.append(i18n.t("pwsg.dev.explain", lang))
    if res == "update-available" and kind["kind"] == "distribution":
        nxt.append(i18n.t("pwsg.next.prepare", lang, latest=latest["version"]))
    elif res in ("error", "no-release"):
        nxt.append(i18n.t("pwsg.next.retry", lang))
    out = {"stage": "search", "component": "pine-workspace", "result": rec, "notes_state": notes_status,
           "notes_text": (latest or {}).get("notes") if notes_status == "available" else None,
           "summary": summary(lang, i18n.t("pwsg.search.headline", lang, repo=version.OFFICIAL_REPOSITORY),
                              result=result, notes=notes, limits=limits, next=nxt)}
    return out


# ---- stage 3: prepare and plan -------------------------------------------------

def prepare(root, lang=None, package=None, sha256=None, downloader=None, dest=None, plan_file=None):
    """Download (or verify a local package) then plan, as one step. Writes
    nothing in the installation except the plan record."""
    root = Path(root)
    lang = _lang(root, lang)
    kind = update.installation_kind(root)
    base = {"stage": "prepare", "component": "pine-workspace", "applicable": False, "plan_file": None,
            "plan_hash": None, "fetch": None, "plan": None}
    if kind["kind"] != "distribution":
        base["refused"] = "development-upstream"
        base["summary"] = summary(lang, i18n.t("pwsg.plan.refused", lang, why=i18n.t("pwsg.kind.development", lang)),
                                  limits=[i18n.t("pwsg.dev.explain", lang)])
        return base
    if package:
        got = update.prepare_local(root, package, expected_sha256=sha256, dest=dest)
    else:
        got = update.fetch_release(root, downloader=downloader, dest=dest)
    base["fetch"] = got
    if not got.get("ok"):
        why = "; ".join(got.get("problems") or ["package not verified"])
        base["summary"] = summary(lang, i18n.t("pwsg.plan.refused", lang, why=why))
        return base
    p = update.plan(root, got["package_dir"], plan_file=plan_file)
    base["plan"] = p
    base["plan_file"], base["plan_hash"] = p.get("plan_file"), p.get("plan_hash")
    base["applicable"] = bool(p.get("applicable") and p.get("plan_file"))
    base["summary"] = plan_summary(lang, p, got)
    return base


def plan_summary(lang, p, got=None):
    cur, target = p.get("current_version"), p.get("target_version") or "?"
    if not p.get("applicable") or not p.get("plan_file"):
        up = p.get("upgrade") or {}
        lines = []
        if up.get("conflicts"):
            lines.append(i18n.t("pwsg.plan.conflicts", lang, paths=", ".join(up["conflicts"][:8])))
        why = "; ".join(p.get("refusals") or ["plan not applicable"])
        return summary(lang, i18n.t("pwsg.plan.refused", lang, why=why), result=lines,
                       limits=[i18n.t("pwsg.dev.explain", lang)] if (p.get("installation") or {}).get("kind")
                       == "development" else [])
    up = p["upgrade"]
    origin = p.get("origin")
    tag = ((got or {}).get("release") or {}).get("tag") if origin == "github-release" else None
    change = [i18n.t("pwsg.plan.component", lang),
              i18n.t("pwsg.plan.origin.release", lang, repo=version.OFFICIAL_REPOSITORY, tag=tag or "v" + str(target))
              if origin == "github-release" else i18n.t("pwsg.plan.origin.local", lang)]
    if p.get("simulated"):
        change.append(i18n.t("guide.simulated", lang))
    change.append(i18n.t("pwsg.plan.files", lang, changed=len(up.get("changed") or []), retired=len(up.get("retired") or [])))
    mig = p.get("migrations_may_apply")
    change.append(i18n.t("pwsg.plan.migrations_undeclared", lang) if mig is None
                  else i18n.t("pwsg.plan.migrations", lang, ids=", ".join(mig) or i18n.t("guide.none", lang)))
    kept = [i18n.t("pwsg.plan.kept.user", lang)]
    pending = set(up.get("kept_local_pending") or [])
    for path in up.get("kept_local") or []:
        kept.append(i18n.t("pwsg.plan.kept.local" if path in pending else "pwsg.plan.kept.already", lang, path=path))
    checks = [i18n.t("pwsg.check.rebind", lang), i18n.t("pwsg.check.backup", lang),
              i18n.t("pwsg.check.manifest", lang), i18n.t("pwsg.check.migrate", lang),
              i18n.t("pwsg.check.doctor", lang)]
    limits = [i18n.t("pwsg.limit.atomic", lang), i18n.t("guide.no_auto_rollback", lang),
              i18n.t("pwsg.limit.restart", lang), i18n.t("guide.permissions", lang)]
    _, notes = notes_lines(lang, p.get("changes") if p.get("changes") and not str(p.get("changes")).startswith(
        "not available for this package") else None)
    return summary(lang, i18n.t("pwsg.plan.headline", lang, cur=cur, target=target), change=change, kept=kept,
                   checks=checks, limits=limits, notes=notes, confirm=confirm_block(lang))


# ---- stage 4: apply and account ------------------------------------------------

def apply(root, plan_file, yes=False, lang=None, runner=None, copy=None):
    root = Path(root)
    lang = _lang(root, lang)
    r = update.apply(root, plan_file, yes=yes, runner=runner, copy=copy)
    return {"stage": "apply", "component": "pine-workspace", "ok": bool(r.get("ok")), "status": r.get("status"),
            "result": r, "summary": report_summary(lang, r)}


def _diag_text(lang, report):
    d = (report.get("stages") or {}).get("doctor")
    verdict = (report.get("done") or {}).get("diagnostic") or "not-run"
    if verdict == "ok":
        n = len((d or {}).get("warnings") or [])
        return i18n.t("pwsg.diag.ok_warnings", lang, n=n) if n else i18n.t("pwsg.diag.ok", lang)
    if verdict == "blocking":
        return i18n.t("pwsg.diag.blocking", lang, checks=", ".join((d or {}).get("blocking") or []))
    if verdict == "unavailable":
        return i18n.t("pwsg.diag.unavailable", lang)
    return i18n.t("pwsg.diag.not-run", lang)


def _yn(lang, value):
    if value is True:
        return i18n.t("guide.yes", lang)
    if value is False:
        return i18n.t("guide.no", lang)
    return i18n.t("guide.unknown", lang)


def report_summary(lang, r):
    status = r.get("status") or "refused-before-mutation"
    plan = r.get("plan") or {}
    cur = plan.get("current_version") or version.WORKSPACE_VERSION
    target = plan.get("target_version") or "?"
    skey = "pwsg.status.failed-restore" if status.startswith("failed-restore-") else "pwsg.status." + status
    headline = i18n.t("pwsg.report.headline", lang, cur=cur, target=target, status=i18n.t(skey, lang))
    done = r.get("done") or {}
    changed, result, recovery, nxt = [], [], [], []
    if status == "refused-before-mutation":
        result.append(i18n.t("pwsg.done.reason", lang, why=r.get("error") or "?"))
        nxt.append(i18n.t("pwsg.next.replan", lang))
        return summary(lang, headline, result=result, next=nxt)
    changed.append(i18n.t("pwsg.done.code", lang, installed=_yn(lang, done.get("code_installed")),
                          verified=_yn(lang, done.get("code_verified"))))
    if done.get("migrations_evaluated") is False:
        changed.append(i18n.t("pwsg.done.not_evaluated", lang))
    elif done.get("code_installed"):
        none = i18n.t("guide.none", lang)
        changed.append(i18n.t("pwsg.done.migrations", lang, applied=", ".join(done.get("migrations_applied") or []) or none,
                              remaining=", ".join(done.get("migrations_remaining") or []) or none,
                              blocked=", ".join(done.get("migrations_blocked") or []) or none))
    if done.get("code_installed"):
        changed.append(i18n.t("pwsg.done.diagnostic", lang, verdict=_diag_text(lang, r)))
    for path in done.get("kept_local") or []:
        changed.append(i18n.t("pwsg.done.kept", lang, path=path))
    if status != "applied" and r.get("error"):
        result.append(i18n.t("pwsg.done.reason", lang, why=r["error"]))
    rec = r.get("recovery") or {}
    if rec.get("migration_backup"):
        recovery.append(i18n.t("pwsg.recovery.migration", lang, path=rec["migration_backup"],
                               stamp=Path(rec["migration_backup"]).name))
    if rec.get("upgrade_backup"):
        recovery.append(i18n.t("pwsg.recovery.upgrade", lang, path=rec["upgrade_backup"],
                               stamp=Path(rec["upgrade_backup"]).name))
    if recovery:
        recovery.append(i18n.t("pwsg.recovery.order", lang))
    if done.get("code_installed") or r.get("restart_required"):
        nxt.append(i18n.t("pwsg.next.restart", lang))
    if status != "applied" and r.get("next_action"):
        nxt.append(i18n.t("pwsg.next.technical", lang, action=r["next_action"]))
    return summary(lang, headline, changed=changed, result=result, recovery=recovery, next=nxt)
