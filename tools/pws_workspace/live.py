# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL development loop of the local test (isolated study copy): work copy, automatic
follow-up, browser chart (Vela) and inspection by Claude Code.

ONE execution point: every computation is `local_test.run` (one runner process = one PineTS
call, report + graphics annex). The browser page never runs PineTS: it receives, through a
`frame.js` file, the series that run already computed, after the reader contract v1 checks of
the report, the annex and the dataset (`local_test.check`). The official connector
@luxalgo/vela-pinets is not installed: it executes PineTS itself in the browser (a second
computation), see docs/maintenance/2026-11-22-vela-pinets/RAPPORT.md. The page verifies, in the
browser, the content of the JavaScript it runs (page_integrity, LOADER_JS).

Session work target (`.claude/runtime/pine-local-test/session.json`): one script and one dataset.
`work` makes a work copy of a registered script (never the registered source), computes it once
and starts the follow-up process (`watch`), detached, single instance. `watch` polls the work
copy; saves close together are grouped (quiet period), then the LAST saved revision is computed
once. `latest.json` and the work page's `frame.js` follow each result; a failed computation keeps
the last successful chart, identified as such. Pages opened from the history are pinned to their
run: they never poll and never follow the work copy.

No server: the page is a local file; it re-reads its `frame.js` with a script element (works
offline in Safari and Chrome from file://).
"""
import datetime
import difflib
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from . import annex_reader, local_test

SESSION = local_test.RUNTIME / "session.json"
WORK = local_test.RUNTIME / "work"
VIEWS = Path(".claude") / "runtime" / "vela-view"
VELA_BUNDLE = Path("tools") / "vela_view" / "node_modules" / "@luxalgo" / "vela" / "dist" / "vela.global.min.js"
PAGE_JS = Path("tools") / "vela_view" / "page" / "pws-view.js"
QUIET_S = 0.8          # saves closer than this are one revision
POLL_S = 0.25

_T = {
    "page.title": {"fr": "Graphique du test local", "en": "Local test chart"},
    "page.work": {"fr": "Script de travail — actualisé automatiquement à chaque enregistrement",
                  "en": "Work script — refreshed automatically on every save"},
    "page.pinned": {"fr": "Test de l'historique — résultat figé de ce run", "en": "Test from the history — fixed result of this run"},
    "page.failed": {"fr": "Calcul en échec pour la révision {rev} : {msg}", "en": "Computation failed for revision {rev}: {msg}"},
    "page.last_good": {"fr": "Graphique affiché : dernier calcul réussi, run {run} (révision {rev}).",
                       "en": "Chart shown: last successful computation, run {run} (revision {rev})."},
    "page.no_good": {"fr": "Aucun calcul réussi à afficher.", "en": "No successful computation to show."},
    "page.refused": {"fr": "Aperçu refusé [{code}] : {msg}. Le résultat numérique du rapport reste valable.",
                     "en": "Preview refused [{code}]: {msg}. The numeric result of the report stays valid."},
    "page.running": {"fr": "Calcul en cours de la révision {rev}…", "en": "Computing revision {rev}…"},
    "page.final": {"fr": "Objets à l'état final : déplacer le curseur sur une ancienne bougie ne reconstitue pas "
                         "nécessairement ce qui était connu à cet instant.",
                   "en": "Objects in final state: moving the cursor to an old candle does not necessarily rebuild "
                         "what was known at that time."},
    "page.not_tv": {"fr": "Exécution locale PineTS : jamais une validation TradingView.",
                    "en": "Local PineTS execution: never a TradingView validation."},
    "page.bar": {"fr": "Barre", "en": "Bar"},
    "page.not_shown": {"fr": "Non affiché : {items}", "en": "Not shown: {items}"},
    "page.data": {"fr": "Données", "en": "Data"},
    "page.engine": {"fr": "Moteur", "en": "Engine"},
    "page.revision": {"fr": "Révision source", "en": "Source revision"},
    "page.updates": {"fr": "actualisations", "en": "updates"},
    "page.export": {"fr": "Exporter en PNG", "en": "Export as PNG"},
    "page.export_done": {"fr": "Image demandée au navigateur : {name} (dossier choisi par ses réglages de téléchargement).",
                         "en": "Image handed to the browser: {name} (folder chosen by its download settings)."},
    "page.export_none": {"fr": "Vela n'a fourni aucune image pour ce graphique (son moteur de rendu ne sait pas l'exporter) : "
                               "aucun fichier n'a été créé.",
                         "en": "Vela returned no image for this chart (its renderer cannot export it): no file was created."},
    "page.export_no_chart": {"fr": "Aucun graphique affiché : rien à exporter.", "en": "No chart shown: nothing to export."},
    "vela.absent": {"fr": "Graphique navigateur (Vela) non installé ici : ce paquet est une construction spéciale "
                          "sans le composant « vela-view ». Rien n'a été recalculé ; le résultat numérique du rapport reste "
                          "valable (local-test inspect, local-test status).",
                    "en": "Browser chart (Vela) not installed here: this package is a special build "
                          "without the \"vela-view\" component. Nothing was recomputed; the numeric result of the report stays "
                          "valid (local-test inspect, local-test status)."},
    "vela.no_deps": {"fr": "Graphique navigateur (Vela) présent mais pas encore préparé : "
                           "python3 -m tools.pws_workspace components prepare (npm ci --ignore-scripts depuis le lockfile). Rien n'a été recalculé ; le résultat "
                           "numérique du rapport reste valable.",
                     "en": "Browser chart (Vela) present but not prepared yet: "
                           "python3 -m tools.pws_workspace components prepare (npm ci --ignore-scripts from the lockfile). Nothing was recomputed; the numeric result "
                           "of the report stays valid."},
}


def vela_state(root):
    """'ready' (page script + Vela browser bundle), 'no-deps' (component shipped, npm ci not run) or
    'absent' (package built without the optional vela-view component)."""
    root = Path(root)
    if not (root / PAGE_JS).is_file():
        return "absent"
    return "ready" if (root / VELA_BUNDLE).is_file() else "no-deps"


def vela_absence(root, lang):
    """Refusal of a browser chart request in an installation without a usable Vela: the reason,
    no computation, the report untouched."""
    state = vela_state(root)
    return {"ok": False, "engine_invocations": 0, "vela": state, "refusal_code": "VELA_" + state.upper().replace("-", "_"),
            "message": _t("vela.absent" if state == "absent" else "vela.no_deps", lang)}


def _t(key, lang, **kw):
    e = _T[key]; s = e.get(lang) or e["en"]
    return s.format(**kw) if kw else s


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, data):
    path = Path(path); tmp = path.with_name(path.name + ".tmp-%s" % uuid.uuid4().hex[:6])
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)                                              # atomic: readers never see half a file


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _log(path, rec):
    rec = dict(rec, ts=_now())
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------------- session
def session(root):
    return _read_json(Path(root) / SESSION)


def work_dir(root, slug):
    return Path(root) / WORK / slug


def start_work(root, slug, dataset, lang, spawn=True):
    """Make (or keep) the session work copy of a registered script, compute it once, record the
    session work target and start the follow-up. The registered source is never modified."""
    root = Path(root)
    p = local_test._product(root, slug)
    ds = Path(dataset)
    if not ds.is_file():
        raise ValueError("dataset not found: %s" % ds)
    wd = work_dir(root, slug); wd.mkdir(parents=True, exist_ok=True)
    src = wd / Path(p["source"]).name
    created = not src.exists()
    if created:
        shutil.copyfile(p["source"], src)
    prev = session(root) or {}
    if prev.get("slug") and prev.get("slug") != slug:
        stop_watch(root)                                               # one work script per session
    sess = {"slug": slug, "work_source": str(src), "registered_source": str(p["source"]), "dataset": str(ds),
            "language": lang, "token": uuid.uuid4().hex, "started_at": _now()}
    _write_json(root / SESSION, sess)
    res = compute(root, sess, reason="start")
    out = {"ok": res.get("state") == "ok", "session": sess, "work_copy_created": created, "latest": res,
           "view": str(view_dir(root, "work-%s" % slug) / "index.html")}
    if spawn:
        out["watch"] = spawn_watch(root)
    return out


def compute(root, sess, reason):
    """ONE computation of the work copy's current saved revision; updates latest.json and the
    work page's frame. Returns the new latest record."""
    root = Path(root); slug = sess["slug"]; wd = work_dir(root, slug); lt = wd / "latest.json"
    prev = _read_json(lt) or {}
    rev = _sha(sess["work_source"])
    seq = int(prev.get("seq") or 0) + 1
    started = _now()
    # while computing, the record names ONLY the revision in computation: the previous run stays in
    # `result` (last finished computation) and `last_good`, never under the new revision
    running = {"seq": seq, "slug": slug, "state": "running", "revision_sha256": rev, "reason": reason,
               "updated_at": started, "run_id": None, "run_dir": None, "execution_status": None, "error": None,
               "computing": {"revision_sha256": rev, "seq": seq, "started_at": started},
               "result": prev.get("result") or _legacy_result(prev), "last_good": prev.get("last_good"),
               "qualification": None}
    _write_json(lt, running); write_work_frame(root, sess)
    _log(wd / "watch.log", {"event": "run-start", "revision_sha256": rev, "reason": reason, "seq": seq})
    try:
        # the annex is written when the reader is installed (charts); numeric-only otherwise
        r = local_test.run(root, slug, sess["dataset"], local_test.chart_component(root), sess.get("language", "en"),
                           source=sess["work_source"], origin="work")
    except Exception as exc:  # noqa: BLE001 — reported as a failed computation, never silently
        r = {"ok": False, "run_id": None, "run_dir": None, "error": {"message": "%s: %s" % (type(exc).__name__, exc)},
             "execution_status": None, "source_sha256": rev}
    computed = r.get("source_sha256") or rev
    finished = _now()
    stamp = (_read_json(Path(r["run_dir"]) / "run.json") or {}).get("timestamp") if r.get("run_dir") else None
    rec = {"seq": seq, "slug": slug, "revision_sha256": computed, "reason": reason, "updated_at": finished,
           "run_id": r.get("run_id"), "run_dir": r.get("run_dir"), "execution_status": r.get("execution_status"),
           "error": r.get("error"), "engine_invocations": 1, "last_good": prev.get("last_good"), "computing": None}
    good = {"run_id": r.get("run_id"), "run_dir": r.get("run_dir"), "revision_sha256": computed,
            "timestamp": stamp, "finished_at": finished}
    if r.get("ok") and not local_test.chart_component(root):
        rec["state"] = "ok"                                            # numeric-only installation: no chart to check
        rec["last_good"] = good
    elif r.get("ok"):
        c = local_test.check(root, r["run_dir"])
        if c["ok"]:
            rec["state"] = "ok"
            rec["last_good"] = good
        else:
            rec["state"] = "refused"; rec["refusal"] = {"code": c["code"], "detail": c["detail"]}
    else:
        rec["state"] = "failed"
    rec["result"] = {"seq": seq, "revision_sha256": computed, "state": rec["state"], "run_id": rec["run_id"],
                     "run_dir": rec["run_dir"], "execution_status": rec["execution_status"], "error": rec["error"],
                     "refusal": rec.get("refusal"), "timestamp": stamp, "finished_at": finished}
    # qualification of the change, on results ALREADY computed (no engine call): against the
    # previous successful result of this session, named as the comparison run
    ref = prev.get("last_good") or {}
    rec["qualification"] = None
    if r.get("ok") and ref.get("run_dir") and ref.get("run_id") != r.get("run_id"):
        try:
            from . import qualify
            rec["qualification"] = qualify.qualify(root, r["run_dir"], ref["run_dir"], slug=slug)
        except Exception as exc:  # noqa: BLE001 — a qualification failure never hides the result
            rec["qualification"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    _write_json(lt, rec)
    _log(wd / "watch.log", {"event": "run-end", "state": rec["state"], "run_id": rec["run_id"],
                            "revision_sha256": computed, "engine_invocations": 1, "seq": seq})
    write_work_frame(root, sess)
    return rec


# --------------------------------------------------------------------------------- follow-up
def _alive(pid):
    try:
        os.kill(int(pid), 0); return True
    except (OSError, ValueError, TypeError):
        return False


def spawn_watch(root):
    """Start the follow-up process, detached, once per session token (single instance)."""
    root = Path(root); sess = session(root)
    if not sess:
        return {"started": False, "reason": "no session work target"}
    wd = work_dir(root, sess["slug"]); pidf = wd / "watch.pid"
    info = _read_json(pidf) or {}
    if info.get("token") == sess["token"] and _alive(info.get("pid")):
        return {"started": False, "reason": "already running", "pid": info["pid"]}
    if info.get("pid") and _alive(info.get("pid")):
        stop_watch(root)
    out = open(wd / "watch.out", "a")
    proc = subprocess.Popen([sys.executable, "-m", "tools.pws_workspace", "local-test", "watch"], cwd=str(root),
                            stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
    _write_json(pidf, {"pid": proc.pid, "token": sess["token"], "started_at": _now()})
    return {"started": True, "pid": proc.pid}


def stop_watch(root):
    root = Path(root); sess = session(root) or {}
    for pidf in (Path(root) / WORK).glob("*/watch.pid"):
        info = _read_json(pidf) or {}
        if info.get("pid") and _alive(info["pid"]):
            try:
                os.kill(int(info["pid"]), signal.SIGTERM)
            except OSError:
                pass
        pidf.unlink(missing_ok=True)
    return {"stopped": True, "session": sess.get("slug")}


def watch(root, quiet=QUIET_S, poll=POLL_S, max_idle=6 * 3600):
    """Follow the session work copy: group close saves, compute the last saved revision once."""
    root = Path(root); sess = session(root)
    if not sess:
        return {"ok": False, "reason": "no session work target"}
    token, src = sess["token"], Path(sess["work_source"]); wd = work_dir(root, sess["slug"])
    _log(wd / "watch.log", {"event": "watch-start", "pid": os.getpid(), "token": token})
    stop = {"flag": False}
    import threading
    if threading.current_thread() is threading.main_thread():      # signals are installable in the main thread only
        signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    pending = None; since = 0.0; last_stat = None; last_activity = time.time()
    while not stop["flag"]:
        cur = session(root) or {}
        if cur.get("token") != token:                                 # another work target: this follow-up ends
            break
        if time.time() - last_activity > max_idle:
            break
        try:
            st = src.stat(); sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            time.sleep(poll); continue
        if sig != last_stat:
            last_stat = sig
            rev = _sha(src)
            if rev != pending:
                pending, since = rev, time.time()
                _log(wd / "watch.log", {"event": "save-seen", "revision_sha256": rev})
        done = (_read_json(wd / "latest.json") or {}).get("revision_sha256")
        if pending and pending != done and time.time() - since >= quiet:
            if _sha(src) != pending:                                   # saved again meanwhile: wait for quiet
                last_stat = None; continue
            compute(root, sess, reason="save")
            last_activity = time.time()
        time.sleep(poll)
    _log(wd / "watch.log", {"event": "watch-end", "pid": os.getpid()})
    return {"ok": True}


WAIT_CAP_S = 600       # bound of any wait for a result


def _legacy_result(lt):
    """`result` of a latest.json written before the freshness fields (finished records only)."""
    if not lt or lt.get("state") in (None, "running") or not lt.get("revision_sha256"):
        return None
    stamp = (_read_json(Path(lt["run_dir"]) / "run.json") or {}).get("timestamp") if lt.get("run_dir") else None
    return {"seq": lt.get("seq"), "revision_sha256": lt.get("revision_sha256"), "state": lt.get("state"),
            "run_id": lt.get("run_id"), "run_dir": lt.get("run_dir"), "execution_status": lt.get("execution_status"),
            "error": lt.get("error"), "refusal": lt.get("refusal"), "timestamp": stamp, "finished_at": lt.get("updated_at")}


def _saved_at(path):
    try:
        return datetime.datetime.fromtimestamp(Path(path).stat().st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _wait_summary(seen, result, fresh):
    """Readable account of the wait: initial and final revision of the saved file, and the revision
    the shown result belongs to."""
    r = result or {}
    head = ("revision changed during the wait: %s -> %s" % (seen[0][:12], seen[-1][:12]) if len(seen) > 1
            else "revision unchanged during the wait: %s" % seen[0][:12])
    if not r:
        return head + "; no finished result yet"
    return head + "; result shown: revision %s (run %s, %s)%s" % (
        (r.get("revision_sha256") or "?")[:12], r.get("run_id"), r.get("state"),
        "" if fresh else " — not the requested revision, nothing is presented as current")


def status(root, wait=0):
    """The session's state as Claude Code reads it, four things kept apart:
    `requested` (revision of the saved work file), `computing` (revision in computation, if any),
    `result` (last FINISHED computation, success or failure, with its revision and run_id) and
    `last_good` (last successful result, dated). `fresh` is true only when `result` belongs to the
    requested revision and nothing is computing. `wait` is bounded (WAIT_CAP_S); a save during the
    wait, or the timeout, is reported with the revisions and the real state."""
    root = Path(root); sess = session(root)
    if not sess:
        return {"ok": False, "reason": "no session work target"}
    wd = work_dir(root, sess["slug"]); t0 = time.time()
    wait = max(0.0, min(float(wait or 0), WAIT_CAP_S))
    first = _sha(sess["work_source"]); seen = [first]
    while True:
        lt = _read_json(wd / "latest.json") or {}
        cur = _sha(sess["work_source"])
        if cur != seen[-1]:
            seen.append(cur)
        result = lt.get("result") or _legacy_result(lt)
        computing = lt.get("computing") if lt.get("state") == "running" else None
        if lt.get("state") == "running" and not computing:            # record written before this version
            computing = {"revision_sha256": lt.get("revision_sha256"), "seq": lt.get("seq"), "started_at": lt.get("updated_at")}
        fresh = bool(result) and result.get("revision_sha256") == cur and not computing
        if fresh or time.time() - t0 >= wait:
            break
        time.sleep(0.2)
    info = _read_json(wd / "watch.pid") or {}
    alive = _alive(info.get("pid")) and info.get("token") == sess["token"]
    if result:
        result = dict(result, relation="requested-revision" if result.get("revision_sha256") == cur else "earlier-revision")
    outcome = ("fresh" if fresh else "superseded" if len(seen) > 1 else "timeout" if wait else "not-fresh")
    if not fresh and not computing and not alive:
        outcome += "; follow-up not running: the requested revision will not be computed"
    return {"ok": True, "session": sess, "latest": lt, "current_revision_sha256": cur, "settled": fresh,
            "requested": {"revision_sha256": cur, "saved_at": _saved_at(sess["work_source"])},
            "computing": computing, "result": result, "last_good": lt.get("last_good"), "fresh": fresh,
            "wait": {"requested_s": wait, "waited_s": round(time.time() - t0, 2), "outcome": outcome,
                     "revisions_seen": seen, "revision_changed": len(seen) > 1,
                     "initial_revision": seen[0], "final_revision": seen[-1],
                     "result_revision": (result or {}).get("revision_sha256"),
                     "summary": _wait_summary(seen, result, fresh)},
            "watch": {"pid": info.get("pid"), "alive": alive},
            "watch_log_tail": (wd / "watch.log").read_text(encoding="utf-8").splitlines()[-8:]
            if (wd / "watch.log").exists() else []}


EXPECT = "expectations.json"


def expect(root, change=(), unchanged=(), note="", from_impact=False):
    """Record what pine-develop's impact inventory expects for the CURRENT saved revision of the
    work copy, BEFORE its result is examined. Runtime only; never a verdict."""
    root = Path(root); sess = session(root)
    if not sess:
        raise ValueError("no session work target")
    facets = ("values", "signals", "objects", "styles")
    for f in list(change) + list(unchanged):
        if f not in facets:
            raise ValueError("unknown facet %s (one of %s)" % (f, ", ".join(facets)))
    wd = work_dir(root, sess["slug"]); rev = _sha(sess["work_source"])
    data = _read_json(wd / EXPECT) or {}
    lt = _read_json(wd / "latest.json") or {}
    res = lt.get("result") or {}
    data[rev] = {"revision_sha256": rev, "declared_at": _now(), "change": sorted(set(change)),
                 "unchanged": sorted(set(unchanged)), "note": note,
                 "result_already_finished": res.get("revision_sha256") == rev}
    if from_impact:
        imp = impact_of_change(root)
        if not imp.get("ok"):
            raise ValueError("impact unavailable: %s" % imp.get("reason"))
        if imp["requested_revision"] != rev:
            raise ValueError("the work file changed during the analysis: declare again")
        sx = imp["suggested_expectation"]
        data[rev].update(change=sorted(set(change) | set(sx["change"])), unchanged=sorted(set(unchanged) | set(sx["unchanged"])),
                         may_change=sx["may_change"], outputs=sx["outputs"], impact_reference=imp["reference"],
                         impact=[{k: r.get(k) for k in ("output", "status", "because", "facet")} for r in imp["analysis"]["outputs"]])
        data[rev]["explanation"] = ["%s: %s — %s" % (r.get("output") or "(untitled output)", r["status"],
                                    "; ".join(r["because"]) if isinstance(r.get("because"), list) else r.get("because"))
                                    for r in imp["analysis"]["outputs"]] + [
            "may-change means the output depends on the changed definition, not that it will differ on the tested bars"]
    _write_json(wd / EXPECT, data)
    return {"ok": True, "expectation": data[rev]}


def impact_of_change(root):
    """Static impact (tools/pws_workspace/impact.py) of the saved work file against the source of the
    comparison reference the follow-up uses (the last good result before this revision). Reads
    files only; never computes."""
    from . import impact
    root = Path(root); st = status(root)
    if not st.get("ok"):
        raise ValueError("no session work target")
    lt = st.get("latest") or {}; req = st["requested"]["revision_sha256"]
    res = st.get("result") or {}; q = lt.get("qualification") or {}
    if res.get("revision_sha256") == req and (q.get("compared_with") or {}).get("run_dir"):
        ref = q["compared_with"]
    else:
        lg = st.get("last_good") or {}
        ref = lg if lg.get("revision_sha256") != req else None
    if not ref or not ref.get("run_dir"):
        return {"ok": False, "requested_revision": req, "reason": "no reference revision to compare the source with"}
    lj = _read_json(Path(ref["run_dir"]) / "local-test.json") or {}
    snap = Path(ref["run_dir"]) / (lj.get("source_snapshot") or "")
    if not lj.get("source_snapshot") or not snap.is_file():
        return {"ok": False, "requested_revision": req, "reason": "the reference run %s has no source snapshot" % ref.get("run_id")}
    # the bytes actually analysed must be the revisions they are said to be
    ref_bytes = snap.read_bytes()
    ref_sha = hashlib.sha256(ref_bytes).hexdigest()
    recorded = (_read_json(Path(ref["run_dir"]) / "run.json") or {}).get("source_sha256")
    if ref_sha != ref.get("revision_sha256") or ref_sha != recorded:
        return {"ok": False, "requested_revision": req, "refused": "reference-mismatch",
                "reason": "the source snapshot of the reference run %s does not match its recorded revision: SHA-256 of "
                          "the bytes read %s, recorded %s (session) / %s (run report); no impact is computed from it"
                          % (ref.get("run_id"), ref_sha[:12], (ref.get("revision_sha256") or "?")[:12], (recorded or "?")[:12])}
    work_bytes = Path(st["session"]["work_source"]).read_bytes()
    work_sha = hashlib.sha256(work_bytes).hexdigest()
    if work_sha != req:
        return {"ok": False, "requested_revision": req, "refused": "work-file-changed",
                "reason": "the work file changed while it was read: SHA-256 of the bytes read %s, requested revision %s"
                          % (work_sha[:12], req[:12])}
    an = impact.analyse(ref_bytes.decode("utf-8"), work_bytes.decode("utf-8"))
    return {"ok": True, "requested_revision": req, "analysed": {"reference_sha256": ref_sha, "work_sha256": work_sha},
            "reference": {"run_id": ref.get("run_id"), "revision_sha256": ref.get("revision_sha256")},
            "analysis": an, "suggested_expectation": impact.expectation(an), "engine_invocations": 0}


def inspect_work(root, bar=None, wait=60, compare=None):
    """`inspect --work`: values or error presented as CURRENT only when they belong to the
    requested revision (the saved work file). Otherwise nothing is presented as current: the
    revisions, the state, the last finished result and the dated last good result are given."""
    root = Path(root)
    st = status(root, wait=wait)
    if not st.get("ok"):
        return st
    wd = work_dir(root, st["session"]["slug"])
    exp = (_read_json(wd / EXPECT) or {}).get(st["requested"]["revision_sha256"])
    fresh_block = {k: st[k] for k in ("requested", "computing", "result", "last_good", "fresh", "wait")}
    if st["fresh"] and (st["result"] or {}).get("run_dir"):
        out = inspect(root, st["result"]["run_dir"], bar=bar, compare=compare)
        q = (st.get("latest") or {}).get("qualification")
        if q and not q.get("error") and (q.get("compared_with") or {}).get("run_dir"):
            from . import qualify as _q
            comp = _q.comparability(q["compared_with"]["run_dir"], st["result"]["run_dir"], compare=q.get("compare_runs"),
                                    recorded=q.get("comparability"))
            if not comp["comparable"]:
                q = _q.withheld(q, comp)                     # nothing stated between runs that are not comparable
        if exp:
            exp = dict(exp, declared_before_result=exp["declared_at"] <= (st["result"].get("finished_at") or ""))
        from . import qualify
        out.update(fresh=True, freshness=fresh_block, qualification=q, expectation=exp,
                   expectation_facts=qualify.expectation_facts(exp, q))
        return out
    lg = st.get("last_good") or {}
    out = {"run_id": None, "fresh": False, "values": None, "error": None, "freshness": fresh_block,
           "expectation": exp,
           "note": "no result of the requested revision yet: nothing here is presented as current; "
                   "the last finished result and the last good result are named with their revision"}
    if lg.get("run_dir"):
        ins = inspect(root, lg["run_dir"], bar=bar)
        out["last_good_values"] = {"run_id": lg.get("run_id"), "revision_sha256": lg.get("revision_sha256"),
                                   "timestamp": lg.get("timestamp"), "bar": ins.get("bar"), "values": ins.get("values")}
    return out


# --------------------------------------------------------------------------------- frames
def frame_model(root, run_dir):
    """Chart content of ONE run for the page, built only after the reader contract v1 checks.
    Returns (model, None) or (None, refusal)."""
    c = local_test.check(root, run_dir)
    if not c["ok"]:
        return None, {"code": c["code"], "detail": c["detail"]}
    run_dir = Path(run_dir)
    m = annex_reader.load(str(run_dir / "dataset.json"),
                                             [(str(run_dir / "run.json"), str(run_dir / "graphics.json"))])
    rep = _read_json(run_dir / "run.json"); ds = _read_json(run_dir / "dataset.json")
    ind = m["inds"][0]
    ds_id = Path((_read_json(run_dir / "local-test.json") or {}).get("dataset_origin") or "dataset.json").stem
    series, levels, not_shown = [], [], []
    for key, s in ind["series"].items():
        color = (s["options"] or {}).get("color") or "#2962FF"
        width = int((s["options"] or {}).get("linewidth") or 1)
        if s["kind"] == "hline":
            vals = [p["v"] for p in s["points"] if isinstance(p.get("v"), (int, float)) and not isinstance(p.get("v"), bool)]
            if vals:
                levels.append({"key": key, "title": s.get("title") or key, "price": vals[0], "color": color})
            continue
        if s["kind"] in ("line", "style_line", "style_linebr", "style_stepline"):
            series.append({"key": key, "title": s.get("title") or key, "color": color, "width": width,
                           "kind": "step" if s["kind"] == "style_stepline" else "line",
                           "values": [p["v"] if isinstance(p.get("v"), (int, float)) and not isinstance(p.get("v"), bool)
                                      else None for p in s["points"]]})
        else:
            not_shown.append("%s (%s)" % (key, s["kind"]))
    counts = {k: v for k, v in ind["drawing_counts"].items() if v}
    not_shown += ["%s × %d" % (k, v) for k, v in counts.items()]
    sc = ds["descriptor"]["price_scale"]
    return {"run_id": rep["run_id"], "source_sha256": rep["source_sha256"], "dataset_sha256": rep["dataset_sha256"],
            "pinets_version": rep.get("pinets_version"), "executor_fingerprint": rep.get("executor_fingerprint"),
            "annex_version": ind["annex_version"], "title": ind["title"], "overlay": ind["overlay"],
            "times": m["times"], "bars": [[b["o"], b["h"], b["l"], b["c"], b.get("v")] for b in
                                         [{"o": x["o"] / sc, "h": x["h"] / sc, "l": x["l"] / sc, "c": x["c"] / sc,
                                           "v": x.get("v")} for x in ds["bars"]]],
            "series": series, "levels": levels, "not_shown": not_shown,
            "dataset_id": ds_id, "dataset_label": {lg: local_test.dataset_label(ds.get("descriptor"), len(ds["bars"]), ds_id, lg)
                                                   for lg in ("fr", "en")}}, None


def _texts(lang):
    keys = ("page.title", "page.work", "page.pinned", "page.final", "page.not_tv", "page.bar", "page.data",
            "page.engine", "page.revision", "page.updates")
    return {k.split(".", 1)[1]: _t(k, lang) for k in keys}


def page_texts(lang):
    """Texts the page needs before its first frame (the export button), in the configured language."""
    return {k.split(".", 1)[1]: _t(k, lang) for k in ("page.export", "page.export_done", "page.export_none",
                                                      "page.export_no_chart")}


def view_dir(root, name):
    return Path(root) / VIEWS / name


def _write_frame(d, frame):
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / ("frame.js.tmp-%s" % uuid.uuid4().hex[:6])
    tmp.write_text("PWS_FRAME(%s);\n" % json.dumps(frame, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, d / "frame.js")


def write_work_frame(root, sess):
    """frame.js of the work page from latest.json: the newest result, or — after a failure or a
    refusal — the last successful chart, identified as such, with the error."""
    root = Path(root); lang = sess.get("language", "en"); slug = sess["slug"]
    if vela_state(root) == "absent":
        return None                                                    # no page in this installation
    lt = _read_json(work_dir(root, slug) / "latest.json") or {}
    rev = (lt.get("revision_sha256") or "")[:12]
    frame = {"mode": "work", "slug": slug, "seq": lt.get("seq"), "state": lt.get("state"), "lang": lang,
             "texts": _texts(lang), "message": None, "chart": None, "chart_is_last_good": False}
    good = lt.get("last_good") or {}
    if lt.get("state") == "running":
        frame["message"] = _t("page.running", lang, rev=rev)
    elif lt.get("state") == "failed":
        msg = ((lt.get("error") or {}).get("message") or lt.get("execution_status") or "?")[:400]
        frame["message"] = _t("page.failed", lang, rev=rev, msg=msg)
    elif lt.get("state") == "refused":
        r = lt.get("refusal") or {}
        frame["message"] = _t("page.refused", lang, code=r.get("code"), msg=annex_reader.refusal_message(r.get("code"), lang))
    if good.get("run_dir"):
        model, refusal = frame_model(root, good["run_dir"])
        if model:
            frame["chart"] = model
            frame["chart_is_last_good"] = lt.get("state") != "ok" or good.get("run_id") != lt.get("run_id")
            if frame["chart_is_last_good"] and lt.get("state") in ("failed", "refused"):
                frame["message"] += " " + _t("page.last_good", lang, run=good["run_id"], rev=good["revision_sha256"][:12])
        else:
            frame["message"] = _t("page.refused", lang, code=refusal["code"],
                                  msg=annex_reader.refusal_message(refusal["code"], lang))
    elif lt.get("state") in ("failed", "refused"):
        frame["message"] += " " + _t("page.no_good", lang)
    _write_frame(view_dir(root, "work-%s" % slug), frame)
    return frame


# Integrity of what the page runs: each JavaScript file is wrapped in a function whose source the
# inline loader of index.html (generated here, the trust anchor) hashes in the browser BEFORE running
# it; a content that differs from the expected hash is never executed, whatever its name or URL.
WRAP = {"vela": ("window.__PWS_VELA = ", "function () {\n", "\nreturn typeof Vela !== 'undefined' ? Vela : undefined;\n}"),
        "page": ("window.__PWS_PAGE = ", "function () {\n", "\n}")}
BUNDLES = VIEWS / "_bundles"

LOADER_JS = r"""
(function(){
  var NET = window.__PWS_NET = [], LINKS = window.__PWS_LINKS = [];      // links only connect when clicked
  var LOADS = { img: 1, script: 1, link: 1, iframe: 1, source: 1, video: 1, audio: 1, object: 1, embed: 1 };
  function rec(kind, u){ try { var s = String(u); if (/^(https?|wss?):/i.test(s)) NET.push(kind + ' ' + s); } catch (e) {} }
  var F = window.fetch; if (F) window.fetch = function(u){ rec('fetch', u && u.url ? u.url : u); return F.apply(this, arguments); };
  var XO = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(m, u){ rec('xhr', u); return XO.apply(this, arguments); };
  if (window.WebSocket) { var WS = window.WebSocket; window.WebSocket = function(u, p){ rec('ws', u); return new WS(u, p); }; }
  if (window.EventSource) { var ES = window.EventSource; window.EventSource = function(u, c){ rec('sse', u); return new ES(u, c); }; }
  if (navigator.sendBeacon) { var SB = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = function(u, d){ rec('beacon', u); return SB(u, d); }; }
  var d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  if (d && d.set) Object.defineProperty(HTMLImageElement.prototype, 'src', { configurable: true, get: d.get,
      set: function(v){ rec('img', v); return d.set.call(this, v); } });
  try { new PerformanceObserver(function(l){ l.getEntries().forEach(function(e){ rec('resource', e.name); }); })
          .observe({ type: 'resource', buffered: true }); } catch (e) {}
  try { new MutationObserver(function(ms){ ms.forEach(function(m){ (m.addedNodes || []).forEach(function(n){
          var t = n.tagName ? n.tagName.toLowerCase() : '';
          if (LOADS[t]) ['src', 'href', 'data'].forEach(function(a){ var v = n.getAttribute(a); if (v) rec(t, v); });
          else if (t === 'a' && n.getAttribute('href')) LINKS.push(n.getAttribute('href')); }); }); })
          .observe(document.documentElement, { childList: true, subtree: true }); } catch (e) {}

  function sha256(str){
    var b = new TextEncoder().encode(str), K = [], H = [], i, j;
    function frac(x){ return ((x - Math.floor(x)) * 4294967296) | 0; }
    for (var n = 2, c = 0; c < 64; n++) { var pr = true; for (j = 2; j * j <= n; j++) if (n % j === 0) { pr = false; break; }
      if (pr) { if (c < 8) H[c] = frac(Math.pow(n, 1 / 2)); K[c++] = frac(Math.pow(n, 1 / 3)); } }
    var l = b.length, nb = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(nb); m.set(b); m[l] = 0x80;
    var bits = l * 8; for (i = 0; i < 8; i++) m[nb - 1 - i] = (bits / Math.pow(2, 8 * i)) & 255;
    var w = new Int32Array(64);
    for (var o = 0; o < nb; o += 64) {
      for (i = 0; i < 16; i++) w[i] = (m[o+4*i] << 24) | (m[o+4*i+1] << 16) | (m[o+4*i+2] << 8) | m[o+4*i+3];
      for (i = 16; i < 64; i++) { var x = w[i-15], y = w[i-2];
        var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3), s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
        w[i] = (w[i-16] + s0 + w[i-7] + s1) | 0; }
      var a = H[0], bb = H[1], cc = H[2], dd = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (i = 0; i < 64; i++) {
        var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7)), ch = (e & f) ^ (~e & g);
        var t1 = (h + S1 + ch + K[i] + w[i]) | 0, S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        var mj = (a & bb) ^ (a & cc) ^ (bb & cc), t2 = (S0 + mj) | 0;
        h = g; g = f; f = e; e = (dd + t1) | 0; dd = cc; cc = bb; bb = a; a = (t1 + t2) | 0; }
      H[0] = (H[0]+a)|0; H[1] = (H[1]+bb)|0; H[2] = (H[2]+cc)|0; H[3] = (H[3]+dd)|0; H[4] = (H[4]+e)|0; H[5] = (H[5]+f)|0; H[6] = (H[6]+g)|0; H[7] = (H[7]+h)|0; }
    return H.map(function(v){ return ('00000000' + (v >>> 0).toString(16)).slice(-8); }).join('');
  }
  var cfg = window.PWS_VIEW || {}, X = cfg.integrity || {}, R = window.__PWS_INTEGRITY = { vela_version: X.vela_version, ok: false };
  function stop(why){ R.reason = why; document.title = 'PWS | ' + (cfg.mode || '') + ' | INTEGRITY FAIL ' + why;
    var m = document.getElementById('msg'); if (m) { m.style.display = 'block'; m.textContent = (X.texts || {}).fail ? X.texts.fail.replace('{why}', why) : why; } }
  if (typeof window.__PWS_VELA !== 'function') return stop('vela not loaded');
  if (typeof window.__PWS_PAGE !== 'function') return stop('page script not loaded');
  R.vela_sha256 = sha256(window.__PWS_VELA.toString()); R.page_sha256 = sha256(window.__PWS_PAGE.toString());
  if (R.vela_sha256 !== X.vela_fn_sha256) return stop('vela content ' + R.vela_sha256.slice(0, 12) + ' != expected ' + String(X.vela_fn_sha256).slice(0, 12));
  if (R.page_sha256 !== X.page_fn_sha256) return stop('page script content ' + R.page_sha256.slice(0, 12) + ' != expected ' + String(X.page_fn_sha256).slice(0, 12));
  if (X.provenance_match === false) return stop('installed vela differs from its recorded provenance');
  R.ok = true; window.Vela = window.__PWS_VELA(); window.__PWS_PAGE();
})();
"""

_INTEGRITY_TEXTS = {
    "fail": {"fr": "Contrôle d'intégrité en échec ({why}) : le contenu chargé n'est pas celui vérifié par PWS, il n'est pas exécuté. "
                   "Aucun calcul n'a été lancé ; le résultat numérique du rapport reste valable.",
             "en": "Integrity check failed ({why}): the loaded content is not the one PWS verified, it is not run. "
                   "No computation was started; the numeric result of the report stays valid."},
}


def _wrapped(kind, text):
    """(file text, function source) of a wrapped JavaScript file."""
    head, fn_open, fn_close = WRAP[kind]
    fn = fn_open + text + fn_close
    return head + fn + ";\n", fn


def page_integrity(root, lang):
    """Write the wrapped Vela bundle and page script (content-addressed) and return what the inline
    loader must find: the hash of each function source, the installed Vela version and whether the
    installed bundle is the one of its recorded provenance (verified npm archive)."""
    root = Path(root)
    from . import vela_guide
    ident = vela_guide.identity(root)
    prov_sha = ((ident.get("provenance") or {}).get("bundle") or {}).get("sha256")
    out = {"vela_version": ident.get("installed"), "installed_bundle_sha256": ident.get("bundle_sha256"),
           "provenance_bundle_sha256": prov_sha,
           "provenance_match": None if not prov_sha else prov_sha == ident.get("bundle_sha256"),
           "texts": {k: v.get(lang) or v["en"] for k, v in _INTEGRITY_TEXTS.items()}, "files": {}}
    bdir = root / BUNDLES; bdir.mkdir(parents=True, exist_ok=True)
    for kind, src in (("vela", root / VELA_BUNDLE), ("page", root / PAGE_JS)):
        body, fn = _wrapped(kind, src.read_text(encoding="utf-8"))
        fsha = hashlib.sha256(fn.encode("utf-8")).hexdigest()
        f = bdir / ("%s-%s.js" % (kind, fsha[:16]))
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != hashlib.sha256(body.encode("utf-8")).hexdigest():
            tmp = f.with_name(f.name + ".tmp-" + uuid.uuid4().hex[:6]); tmp.write_text(body, encoding="utf-8"); os.replace(tmp, f)
        out[kind + "_fn_sha256"] = fsha
        out["files"][kind] = str(f)
    return out


def _page(root, d, cfg):
    """index.html of one view: local files only. The inline loader (generated here) verifies the
    wrapped Vela bundle and page script before running them, and records connection attempts."""
    integ = page_integrity(root, cfg["lang"])
    cfg = dict(cfg, integrity={k: v for k, v in integ.items() if k != "files"})
    token = uuid.uuid4().hex[:10]                                      # unique URL per opening: cold cache
    srcs = {k: "%s?v=%s&o=%s" % (Path(v).as_uri(), integ[k + "_fn_sha256"][:12], token) for k, v in integ["files"].items()}
    html = """<!doctype html>
<html lang="%(lang)s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PWS</title>
<style>
html,body{margin:0;height:100%%;background:#131722;color:#d1d4dc;font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#app{display:grid;grid-template-columns:1fr 300px;grid-template-rows:auto 1fr;height:100%%}
#bar{grid-column:1/3;padding:8px 12px;border-bottom:1px solid #2a2e39;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
#head{flex:1}#export{background:#2a2e39;color:#d1d4dc;border:1px solid #434651;border-radius:4px;padding:4px 10px;font:inherit;cursor:pointer}
#export:hover{background:#363a45}
#bar b{color:#fff}#msg{padding:6px 12px;background:#4a1f24;color:#ffb4b4;display:none;grid-column:1/3}
#chart{min-height:0;min-width:0}#side{border-left:1px solid #2a2e39;padding:10px 12px;overflow:auto}
#side h3{margin:10px 0 4px;font-size:12px;color:#9598a1;text-transform:uppercase;letter-spacing:.04em}
#side .v{font-variant-numeric:tabular-nums}#side .k{color:#9598a1}.dim{color:#787b86;font-size:12px}
</style></head><body>
<div id="app"><div id="bar"><span id="head"></span><button id="export" type="button"></button></div><div id="msg"></div><div id="chart"></div><div id="side"></div></div>
<script>window.PWS_VIEW = %(cfg)s;</script>
<script src="%(vela)s"></script>
<script src="%(page)s"></script>
<script>%(loader)s</script>
</body></html>
""" % {"lang": cfg["lang"], "cfg": json.dumps(cfg, ensure_ascii=False), "vela": srcs["vela"], "page": srcs["page"],
       "loader": LOADER_JS}
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    return d / "index.html"


def open_view(root, run_dir=None, work=False, bar=None, lang="en", browser=True, opener=None):
    """Open the chart in the default browser. `work`: the session work page (follows the work
    copy). `run_dir`: a page pinned to that run (from the history: never follows anything).
    Opening only reads results: it never runs PineTS. Without the browser chart in this installation,
    the request is refused with the reason; nothing is recomputed and the report is untouched."""
    root = Path(root)
    if vela_state(root) != "ready":
        return vela_absence(root, lang)
    if work:
        sess = session(root)
        if not sess:
            raise ValueError("no session work target: run `local-test work` first")
        d = view_dir(root, "work-%s" % sess["slug"]); write_work_frame(root, sess); lang = sess.get("language", lang)
        cfg = {"mode": "work", "lang": lang, "poll_ms": 500, "bar": bar, "texts": page_texts(lang)}
    else:
        run_dir = Path(run_dir)
        rep = _read_json(run_dir / "run.json") or {}
        d = view_dir(root, "run-%s" % (rep.get("run_id") or run_dir.name))
        model, refusal = frame_model(root, run_dir)
        frame = {"mode": "pinned", "seq": 1, "state": "ok" if model else "refused", "lang": lang, "texts": _texts(lang),
                 "chart": model, "chart_is_last_good": False, "run_dir": str(run_dir),
                 "message": None if model else _t("page.refused", lang, code=refusal["code"],
                                                 msg=annex_reader.refusal_message(refusal["code"], lang))}
        _write_frame(d, frame)
        cfg = {"mode": "pinned", "lang": lang, "poll_ms": 0, "bar": bar, "texts": page_texts(lang)}
    page = _page(root, d, cfg)
    out = {"ok": True, "page": str(page), "mode": cfg["mode"], "engine_invocations": 0}
    if browser:
        p = (opener or subprocess.run)(["open", str(page)], capture_output=True, text=True, timeout=30)
        out["opened"] = p.returncode == 0
        if p.returncode != 0:
            out["open_error"] = (p.stderr or "").strip()[:300]
    return out


# --------------------------------------------------------------------------------- observation in Vela
OBS_PREFIX = "PWS-OBS v1"
OBS_FIELDS = ("req", "status", "run", "series", "bar", "t", "pane", "cursor_pane", "value", "datawindow", "vela")


def parse_obs_title(title):
    """Fields of an observation title ('PWS-OBS v1 | k=v | … | end'), or None if it is not one."""
    if not title or not title.startswith(OBS_PREFIX):
        return None
    parts = [p.strip() for p in title.split(" | ")]
    out = {"_complete": parts[-1] == "end"}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    return out


def judge_observation(fields, req, run_id, series, bar, t):
    """'observed' only when the title answers THIS request about THIS run, series, bar and bar time,
    is complete, and carries a value from Vela's event; otherwise the reason it is not observed."""
    if fields is None:
        return "not observed: no observation title"
    if fields.get("req") != req:
        return "not observed: stale title (request %s, expected %s)" % (fields.get("req"), req)
    if not fields.get("_complete") or any(k not in fields for k in OBS_FIELDS):
        return "not observed: incomplete title (status %s)" % fields.get("status")
    if fields["status"] != "observed":
        return "not observed: page reports %s" % fields["status"]
    if (fields["run"], fields["series"], fields["bar"], fields["t"]) != (run_id, series, str(bar), str(t)):
        return "not observed: target mismatch (run %s series %s bar %s t %s)" % (
            fields["run"], fields["series"], fields["bar"], fields["t"])
    if not fields["pane"] or fields["cursor_pane"].split("/")[-1] != fields["pane"]:
        return "not observed: cursor not on the series pane (%s vs %s)" % (fields["cursor_pane"], fields["pane"])
    try:
        float(fields["value"])
    except ValueError:
        return "not observed: no numeric value in Vela's event (%s)" % fields["value"]
    if not fields["vela"].endswith("verified"):
        return "not observed: Vela content not verified (%s)" % fields["vela"]
    return "observed"


def _safari_title(url):
    """Title of the Safari tab showing `url` (AppleScript, read only); None if no such tab."""
    script = ('tell application "Safari"\nrepeat with w in windows\nrepeat with t in tabs of w\n'
              'if (URL of t) starts with "%s" then return name of t\nend repeat\nend repeat\nreturn ""\nend tell') % url
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    return p.stdout.strip() or None


def _safari_close(url):
    script = ('tell application "Safari"\nrepeat with w in windows\nrepeat with t in tabs of w\n'
              'if (URL of t) starts with "%s" then close t\nend repeat\nend repeat\nend tell') % url
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)


def observe(root, run_dir, bar, series, lang="en", timeout=30, keep_open=False, opener=None, reader=None, closer=None):
    """Ask Vela itself for the value of `series` at `bar` of ONE existing run: an observation page
    (pinned to the run, never computing) moves Vela's crosshair to the bar with simulated pointer
    events and writes what Vela's OWN crosshair event reports into the tab title, which is read
    back. Bounded (`timeout`); anything stale, incomplete or off-target is 'not observed'."""
    root = Path(root); run_dir = Path(run_dir)
    rep = _read_json(run_dir / "run.json") or {}
    out = {"ok": False, "status": None, "run_id": rep.get("run_id"), "series": series, "bar": bar,
           "engine_invocations": 0}
    if vela_state(root) != "ready":
        a = vela_absence(root, lang)
        out.update(status="not observed: browser chart unavailable here (%s)" % a.get("refusal_code"),
                   refusal_code=a.get("refusal_code"), message=a.get("message"))
        return out
    model, refusal = frame_model(root, run_dir)
    if not model:
        out["status"] = "not observed: preview refused [%s]" % refusal["code"]; return out
    keys = [s["key"] for s in model["series"]]
    if series not in keys:
        out["status"] = "not observed: series %s is not drawn by Vela here (drawn: %s)" % (series, ", ".join(keys)); return out
    n = len(model["times"])
    if not 0 <= bar < n:
        out["status"] = "not observed: bar %d outside 0..%d" % (bar, n - 1); return out
    t = model["times"][bar]; req = uuid.uuid4().hex[:10]
    d = view_dir(root, "obs-%s" % rep.get("run_id"))
    _write_frame(d, {"mode": "pinned", "seq": 1, "state": "ok", "lang": lang, "texts": _texts(lang), "chart": model,
                     "chart_is_last_good": False, "run_dir": str(run_dir), "message": None})
    cfg = {"mode": "pinned", "lang": lang, "poll_ms": 0, "bar": bar, "texts": page_texts(lang),
           "observe": {"req": req, "run_id": rep.get("run_id"), "series": series, "bar": bar, "t": t}}
    page = _page(root, d, cfg); url = page.as_uri()
    (opener or (lambda u: subprocess.run(["open", "-a", "Safari", u], capture_output=True, text=True, timeout=30)))(url)
    read = reader or _safari_title
    t0 = time.time(); title = None; verdict = "not observed: no observation title"; attempts = 0
    while time.time() - t0 < min(float(timeout), WAIT_CAP_S):
        attempts += 1
        title = read(url)
        fields = parse_obs_title(title)
        verdict = judge_observation(fields, req, rep.get("run_id"), series, bar, t)
        if verdict == "observed" or (fields and fields.get("req") == req and fields.get("_complete")):
            break
        time.sleep(0.5)
    fields = parse_obs_title(title) or {}
    if verdict.startswith("not observed") and time.time() - t0 >= min(float(timeout), WAIT_CAP_S):
        verdict += " (after %.1f s, %d reads)" % (time.time() - t0, attempts)
    report_v = (((rep.get("normalized") or {}).get("plots") or {}).get(series) or [None] * n)[bar]
    frame_v = next(s["values"][bar] for s in model["series"] if s["key"] == series)
    out.update(ok=verdict == "observed", status=verdict, request=req, bar_time=t, page=str(page), reads=attempts,
               title=title, vela_event_value=float(fields["value"]) if verdict == "observed" else None,
               pane=fields.get("pane"), cursor_pane=fields.get("cursor_pane"), datawindow=fields.get("datawindow"),
               vela=fields.get("vela"),
               report_value=(report_v or {}).get("v") if isinstance(report_v, dict) else report_v, frame_value=frame_v,
               sources={"vela_event_value": "Vela renderer.onCrosshairMove CrosshairEvent.values[<indicator>:<series>]",
                        "datawindow": "Vela renderer.dataWindowReadout(), formatted text",
                        "report_value": "run.json normalized.plots[series][bar].v",
                        "frame_value": "frame.js written by PWS from the checked annex"},
               limit="value held by Vela for its series at that bar, not the drawn pixels")
    if verdict == "observed":
        out["equal_to_report"] = out["vela_event_value"] == out["report_value"]
    if not keep_open:
        (closer or _safari_close)(url)
    return out


# --------------------------------------------------------------------------------- inspection
NOT_CAPTURED = ["script variables (values of `var`/local variables) — the PWS runner records plots only",
                "series that are computed but not plotted", "per-bar history of drawing objects (final state only)",
                "inputs as edited in a settings dialog (the source revision is the only input)"]


def _chart_values(run_dir, bar):
    """Value of every series of the (checked) graphics annex at `bar`, booleans of signal plots
    included — the normalized payload keeps numbers only."""
    g = _read_json(Path(run_dir) / "graphics.json") or {}
    vals, kinds, times = {}, {}, {}
    for s in g.get("series") or []:
        pts = s.get("points") or []
        p = pts[bar] if 0 <= bar < len(pts) else {}
        vals[s["key"]] = p.get("v"); kinds[s["key"]] = s.get("kind"); times[s["key"]] = p.get("t")
    return {"source": "graphics annex (reader contract v1 passed)", "values": vals, "kinds": kinds, "times": times}


def inspect(root, run_dir, bar=None, compare=None):
    """What Claude Code can read from one run: identity, status, error, warnings, alerts, the value
    of every plot at `bar` (default last), and — with `compare` (another run folder) — the value
    differences and the source diff between the two revisions. Reads files only."""
    run_dir = Path(run_dir); rep = _read_json(run_dir / "run.json") or {}; lt = _read_json(run_dir / "local-test.json") or {}
    plots = ((rep.get("normalized") or {}).get("plots") or {})
    ds = _read_json(run_dir / "dataset.json") or {}
    n = len(ds.get("bars") or [])
    bar = n - 1 if bar is None else int(bar)
    sc = (ds.get("descriptor") or {}).get("price_scale") or 1
    b = (ds.get("bars") or [])[bar] if 0 <= bar < n else None
    snap = run_dir / (lt.get("source_snapshot") or "")
    out = {"run_id": rep.get("run_id"), "run_dir": str(run_dir), "origin": lt.get("origin"),
           "execution_status": rep.get("execution_status"), "error": rep.get("error"),
           "source_revision_sha256": rep.get("source_sha256"), "source_snapshot": str(snap) if snap.is_file() else None,
           "dataset": {"id": Path(lt.get("dataset_origin") or "dataset").stem, "sha256": rep.get("dataset_sha256"),
                       "label": {lg: local_test.dataset_label(ds.get("descriptor"), n, Path(lt.get("dataset_origin") or "dataset").stem, lg)
                                 for lg in ("fr", "en")}, "bars": n},
           "engine": {"pinets_version": rep.get("pinets_version"), "executor_fingerprint": rep.get("executor_fingerprint"),
                      "normalization_schema": rep.get("normalization_schema")},
           "warnings": (rep.get("normalized") or {}).get("warnings"), "alerts": (rep.get("normalized") or {}).get("alerts"),
           "capabilities_used": rep.get("capabilities_used"), "unclassified_tokens": rep.get("unclassified_tokens"),
           "bar": bar, "time": b and b.get("t"),
           "ohlc": b and {"open": b["o"] / sc, "high": b["h"] / sc, "low": b["l"] / sc, "close": b["c"] / sc},
           "values": {k: (v[bar]["v"] if 0 <= bar < len(v) else None) for k, v in plots.items()},
           "annex": local_test.check(root, run_dir) if (run_dir / "graphics.json").exists() else None,
           "not_captured": NOT_CAPTURED}
    out["chart_values"] = _chart_values(run_dir, bar) if (out["annex"] or {}).get("ok") else None
    if compare:
        other = inspect(root, compare, bar=bar)
        out["compare"] = {"run_id": other["run_id"], "source_revision_sha256": other["source_revision_sha256"],
                          "same_dataset": other["dataset"]["sha256"] == out["dataset"]["sha256"],
                          "same_engine": other["engine"] == out["engine"],
                          "values": {k: {"this": out["values"].get(k), "other": other["values"].get(k)}
                                     for k in sorted(set(out["values"]) | set(other["values"]))}}
        if out["chart_values"] is not None and other["chart_values"] is not None:
            cv, co = out["chart_values"]["values"], other["chart_values"]["values"]
            out["compare"]["chart_values"] = {k: {"this": cv.get(k), "other": co.get(k)} for k in sorted(set(cv) | set(co))}
        # values above are each run's own; whether they may be compared at all is said here
        from . import qualify
        comp = qualify.comparability(compare, run_dir, run_ids={"reference": other["run_id"], "result": out["run_id"]})
        out["compare"]["comparable"] = {k: comp[k] for k in ("comparable", "reasons", "explanation")}
        if not comp["comparable"]:
            out["compare"]["note"] = ("each value (values, chart_values) is its own run's; the runs are not comparable, so "
                                      "no equality or difference between their values is established")
        if out["source_snapshot"] and other["source_snapshot"]:
            a = Path(other["source_snapshot"]).read_text(encoding="utf-8").splitlines()
            bb = Path(out["source_snapshot"]).read_text(encoding="utf-8").splitlines()
            out["compare"]["source_diff"] = list(difflib.unified_diff(a, bb, other["run_id"], out["run_id"], lineterm=""))
    return out
