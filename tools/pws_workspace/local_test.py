# SPDX-License-Identifier: Apache-2.0
"""Local PineTS test of ONE registered script, with an optional graphics annex
(EXPERIMENTAL "inspect the result" path, isolated study copy).

One path for both entries: `/pine-local-test` and `/pws → Quality / publication →
Local test (PineTS) → script` route to the skill `pine-local-test` (texts in the configured
language):

  plan  the chosen script, the local datasets and what THIS installation can do (`actions`).
        Read-only.
  run   ONE runner invocation (`runner.mjs run`) — hence one PineTS execution — on snapshots
        of the source and of the dataset copied into a folder of its own
        (.claude/runtime/pine-local-test/<slug>/<UTC>-<id>/). With the graphics annex (only
        offered when the browser chart component is installed) the same execution also writes
        `graphics.json` (schema v0.2-exp, SHA-256 recorded in the report).
  check the reader contract v1 (annex_reader): report, annex and dataset belong together.

"Open the chart" is the browser chart (Vela, tools/vela_view, see live.py), for the current
test as for an earlier one; it only reads the run's files and never runs PineTS.

PINETS_EXECUTION_PASS is never a TradingView validation.
"""
import datetime
import hashlib
import json
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path

from . import annex_reader, scan

RUNTIME = Path(".claude") / "runtime" / "pine-local-test"
GRAPHICS_SCHEMA = "pws-pinets-graphics-v0.2-exp"

_T = {
    "lt.question": {"fr": "Préparer le graphique de ce test ?", "en": "Prepare the chart of this test?"},
    "lt.numeric": {"fr": "Test numérique seul (par défaut)", "en": "Numeric test only (default)"},
    "lt.numeric.desc": {"fr": "Le test habituel : rapport numérique, sans annexe graphique.",
                        "en": "The usual test: numeric report, no graphics annex."},
    "lt.graphics": {"fr": "Préparer le graphique", "en": "Prepare the chart"},
    "lt.graphics.desc": {"fr": "Le même calcul écrit aussi l'annexe graphique ; un seul appel à PineTS.",
                         "en": "The same computation also writes the graphics annex; one single PineTS call."},
    "lt.back": {"fr": "Retour", "en": "Back"},
    "lt.dataset.question": {"fr": "Jeu de données local ?", "en": "Local dataset?"},
    "lt.open": {"fr": "Ouvrir le graphique", "en": "Open the chart"},
    "lt.open.desc": {"fr": "Ouvre ce test dans le navigateur (Vela) ; la page relit ses fichiers sans rappeler PineTS.",
                     "en": "Opens this test in the browser (Vela); the page re-reads its files without calling PineTS again."},
    "lt.final": {"fr": "Objets à l'état final : déplacer le curseur sur une ancienne bougie ne reconstitue pas "
                       "nécessairement ce qui était connu à cet instant.",
                 "en": "Objects in final state: moving the cursor to an old candle does not necessarily rebuild "
                       "what was known at that time."},
    "lt.scope": {"fr": "Graphique du navigateur : chandeliers, courbes, niveaux et panneaux ; les autres éléments "
                       "sont listés comme non affichés.",
                 "en": "Browser chart: candles, curves, levels and panes; other elements are listed as not shown."},
    "lt.no_chart": {"fr": "Graphique du navigateur (Vela) absent de cette installation : seul le test numérique est proposé.",
                    "en": "Browser chart (Vela) not installed here: only the numeric test is offered."},
    "lt.not_tv": {"fr": "Exécution locale PineTS : jamais une validation TradingView.",
                  "en": "Local PineTS execution: never a TradingView validation."},
    "lt.no_open.numeric": {"fr": "Test numérique seul : aucun graphique préparé.",
                           "en": "Numeric test only: no chart prepared."},
    "lt.no_open.fail": {"fr": "Calcul en échec : aucun graphique proposé.",
                        "en": "Computation failed: no chart offered."},
    "lt.no_open.annex": {"fr": "Graphique non proposé ({code}) : {reason}. Le résultat numérique reste celui du rapport.",
                         "en": "Chart not offered ({code}): {reason}. The numeric result stays the one of the report."},
    "lt.version": {"fr": "Annexe lue sous sa version d'origine : {version}.",
                   "en": "Annex read under its version of origin: {version}."},
}


_T.update({
    "lt.reason.not_found": {"fr": "aucun test enregistré avec ce run_id", "en": "no recorded test with this run_id"},
})


def _t(key, lang, **kw):
    e = _T[key]; s = e.get(lang) or e["en"]
    return s.format(**kw) if kw else s


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _product(root, slug):
    for p in scan.scan_workspace(root).get("products", []):
        if p.get("slug") == slug:
            if p.get("product_structure_status") != "REGISTERED":
                raise ValueError("script %s is %s, not REGISTERED" % (slug, p.get("product_structure_status")))
            return p
    raise ValueError("unknown script: %s" % slug)


DEMO_LABEL = {"fr": "Données de démonstration — {n} bougies simulées", "en": "Demo data — {n} simulated candles"}


def dataset_label(descriptor, n, stem, lang):
    """Readable label of a local dataset; the technical identifier stays in the details. Only the
    synthetic generator of PWS gets the demonstration label (its bars are simulated, not a market)."""
    d = descriptor if isinstance(descriptor, dict) else {}
    if d.get("type") == "synthetic" and d.get("generator") == "lcg-ohlcv-v1":
        return (DEMO_LABEL.get(lang) or DEMO_LABEL["en"]).format(n=n)
    return "%s (%d)" % (stem, n)


def _datasets(root, lang="en"):
    """Local datasets (pws-dataset-v1): runtime datasets, then the calibration datasets."""
    out = []
    for d in (root / RUNTIME / "datasets", root / "tools" / "pine_exec" / "calibration" / "datasets"):
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(j, dict) and j.get("schema") == "pws-dataset-v1":
                n = len(j.get("bars") or [])
                out.append({"path": str(f), "label": dataset_label(j.get("descriptor"), n, f.stem, lang),
                            "id": f.stem, "details": "%s · %d · %s" % (f.stem, n, _sha256(f)[:12]),
                            "bars": n, "sha256": _sha256(f)})
    return out


def reader(root=None):
    """The reader contract v1 (tools/pws_workspace/annex_reader.py): stdlib only, no display."""
    return annex_reader


def check(root, run_dir):
    """Reader contract v1: do run.json, graphics.json and dataset.json of one run folder belong
    together? Returns {ok, code, detail, annex_schema, annex_version}. Only reads; never runs PineTS."""
    run_dir = Path(run_dir)
    files = {k: run_dir / n for k, n in (("run", "run.json"), ("annex", "graphics.json"), ("dataset", "dataset.json"))}
    for k, f in files.items():
        if not f.is_file():
            return {"ok": False, "code": "MISSING", "detail": "missing %s file (%s)" % (k, f.name),
                    "annex_schema": None, "annex_version": None}
    try:
        model = annex_reader.load(str(files["dataset"]), [(str(files["run"]), str(files["annex"]))])
    except SystemExit as exc:
        return {"ok": False, "code": getattr(exc, "refusal_code", "MALFORMED"), "detail": getattr(exc, "detail", str(exc)),
                "annex_schema": None, "annex_version": None}
    except Exception as exc:  # noqa: BLE001 — any loader failure is a refusal, reported as such
        return {"ok": False, "code": "MALFORMED", "detail": "%s: %s" % (type(exc).__name__, exc),
                "annex_schema": None, "annex_version": None}
    ind = model["inds"][0]
    return {"ok": True, "code": None, "detail": None, "annex_schema": ind["annex_schema"],
            "annex_version": ind["annex_version"]}


def preflight(root, run_dir):
    """(ok, reason) form of `check`: reason = '[CODE] detail'."""
    c = check(root, run_dir)
    return (True, None) if c["ok"] else (False, "[%s] %s" % (c["code"], c["detail"]))


def _refusal(root, c, lang):
    msg = annex_reader.refusal_message(c["code"], lang)
    return _t("lt.no_open.annex", lang, code=c["code"], reason=msg)


def _open_block(root, run_dir, c, lang):
    rid = (json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8")) or {}).get("run_id")
    return {"label": _t("lt.open", lang), "description": _t("lt.open.desc", lang),
            "command": "python3 -m tools.pws_workspace local-test view --run-id %s" % shlex.quote(str(rid)),
            "scope": _t("lt.scope", lang), "final_state": _t("lt.final", lang), "annex_schema": c["annex_schema"],
            "annex_version": c["annex_version"], "version_note": _t("lt.version", lang, version=c["annex_version"])}


def chart_component(root):
    """True when the browser chart component (tools/vela_view) is installed: only then is the
    graphics annex worth writing. Packages built without it stay numeric."""
    from . import live
    return live.vela_state(root) != "absent"


def plan(root, slug, lang):
    p = _product(root, slug)
    src = Path(p["source"])
    viewer = chart_component(root)
    options = [{"value": "numeric", "label": _t("lt.numeric", lang), "description": _t("lt.numeric.desc", lang)}]
    if viewer:
        options.append({"value": "graphics", "label": _t("lt.graphics", lang),
                        "description": _t("lt.graphics.desc", lang)})
    options.append({"value": "back", "label": _t("lt.back", lang), "description": ""})
    notes = [_t("lt.not_tv", lang)] + ([] if viewer else [_t("lt.no_chart", lang)])
    from . import live                                                  # what THIS installation can do
    vela = live.vela_state(root)
    actions = {"numeric": True, "follow": True, "inspect": True, "chart": vela == "ready", "chart_state": vela}
    return {"ok": True, "language": lang, "script": {"slug": slug, "source": str(src), "source_sha256": _sha256(src),
                                                     "kind": p.get("script_kind")},
            "datasets": _datasets(root, lang),
            "dataset_question": _t("lt.dataset.question", lang),
            "graphics_screen": {"question": _t("lt.question", lang), "default": "numeric", "options": options},
            "chart_component": viewer, "actions": actions,
            "run_command": "python3 -m tools.pws_workspace local-test run --slug %s --dataset <path>%s"
                           % (shlex.quote(slug), " [--graphics]" if viewer else ""),
            "notes": notes}


def run(root, slug, dataset, graphics, lang, source=None, origin=None):
    """ONE runner invocation on a snapshot of the source and of the dataset, both copied into the
    run folder first: the run records exactly the revision it computed (`source`, default the
    registered source; a session work copy passes its own path and `origin`)."""
    p = _product(root, slug); src = Path(source) if source else Path(p["source"]); ds = Path(dataset)
    if not src.is_file():
        raise ValueError("source not found: %s" % src)
    if not ds.is_file():
        raise ValueError("dataset not found: %s" % ds)
    if graphics and not chart_component(root):
        raise ValueError(_t("lt.no_chart", lang))           # refused before any engine call
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = root / RUNTIME / slug / ("%s-%s" % (stamp, uuid.uuid4().hex[:8]))
    run_dir.mkdir(parents=True)
    shutil.copyfile(ds, run_dir / "dataset.json")                 # exact dataset snapshot of THIS run
    snap = run_dir / src.name
    shutil.copyfile(src, snap)                                     # exact source revision of THIS run
    pe = root / "tools" / "pine_exec"
    cmd = [shutil.which("node") or "node", str(pe / "runner.mjs"), "run", "--source", str(snap),
           "--dataset", str(run_dir / "dataset.json"), "--out", str(run_dir / "run.json")]
    if graphics:
        cmd += ["--graphics-out", str(run_dir / "graphics.json")]
    proc = subprocess.run(cmd, cwd=str(pe), capture_output=True, text=True, timeout=900)   # the ONE engine call
    rep = json.loads((run_dir / "run.json").read_text(encoding="utf-8")) if (run_dir / "run.json").is_file() else {}
    ga = rep.get("graphics_annex") or {}
    result = {"ok": rep.get("execution_status") == "PINETS_EXECUTION_PASS", "language": lang, "slug": slug,
              "run_dir": str(run_dir), "run_id": rep.get("run_id"), "execution_status": rep.get("execution_status"),
              "error": rep.get("error"), "runner_exit_code": proc.returncode, "runner_stderr": proc.stderr.strip()[:500],
              "engine_invocations": 1, "graphics_requested": bool(graphics),
              "graphics_annex": {k: ga.get(k) for k in ("schema", "status", "sha256", "file_state", "error")} if ga else None,
              "source_sha256": rep.get("source_sha256"), "dataset_sha256": rep.get("dataset_sha256"),
              "dataset_origin": str(ds), "source_origin": str(src), "source_snapshot": snap.name,
              "origin": origin or "registered", "pinets_version": rep.get("pinets_version"),
              "executor_fingerprint": rep.get("executor_fingerprint"),
              "normalized_payload_sha256": rep.get("normalized_payload_sha256"),
              "notes": [_t("lt.not_tv", lang)], "open": None, "open_refused": None}
    if not result["ok"]:
        result["open_refused"] = _t("lt.no_open.fail", lang)
    elif not graphics:
        result["open_refused"] = _t("lt.no_open.numeric", lang)
    else:
        c = check(root, run_dir)
        from . import live
        if not c["ok"]:
            result["open_refused"] = _refusal(root, c, lang)
            result["refusal_code"], result["refusal_detail"] = c["code"], c["detail"]
        elif live.vela_state(root) != "ready":
            result["open_refused"] = live.vela_absence(root, lang)["message"]
        else:
            result["open"] = _open_block(root, run_dir, c, lang)
    (run_dir / "local-test.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def find_run(root, run_id):
    """Run folder of an earlier test, found by its run_id (whatever was executed since)."""
    base = Path(root) / RUNTIME
    for rj in sorted(base.glob("*/*/run.json")):
        try:
            if json.loads(rj.read_text(encoding="utf-8")).get("run_id") == run_id:
                return rj.parent
        except (OSError, ValueError):
            continue
    return None



def reopen(root, run_dir, lang):
    run_dir = Path(run_dir)
    c = check(root, run_dir)
    ok = c["ok"]
    rep = {}
    try:
        rep = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    out = {"ok": ok, "language": lang, "run_dir": str(run_dir), "run_id": rep.get("run_id"),
           "execution_status": rep.get("execution_status"), "engine_invocations": 0}
    from . import live
    if ok and live.vela_state(root) == "ready":
        out["open"] = _open_block(root, run_dir, c, lang)
    elif ok:
        out["open_refused"] = live.vela_absence(root, lang)["message"]
    else:
        out["open_refused"] = _refusal(root, c, lang)
        out["refusal_code"], out["refusal_detail"] = c["code"], c["detail"]
    return out
