# SPDX-License-Identifier: Apache-2.0
"""Guided update of Vela, the browser chart of local tests (tools/vela_view) — EXPERIMENTAL.

Same stages as the PineTS guide (pinets_guide.py), reusing its common steps (safe reading of an
npm archive, SRI integrity, plan hash, shared summary format, mutation lock, rollback-tree walk):

  state    read-only: installed versions, pin, lockfile, Vela browser bundle hash now, recorded
           provenance (PROVENANCE.json), verified rollback points, last dated search.
  search   explicit network: latest STABLE version on the npm registry (never a prerelease by
           default); dated record kept in .claude/runtime/tooling/last-vela-check.json.
  prepare  downloads only: the npm archives of the current and target versions (integrity equal to
           the registry and to the lockfile), a candidate lockfile and a disposable candidate
           installation in a folder OUTSIDE the workspace (scripts disabled). The plan presents the
           CHANGELOG of the archive itself, dependency and licence changes, the API check of what
           the page needs (a missing API blocks; an ambiguous declaration requires the probe) and
           the bundle scan. Only the plan file is written.
  probe    optional / required when ambiguous: the candidate bundle actually run in the browser.
  apply    after "Apply" only: re-check, verified rollback point, `npm ci --offline
           --ignore-scripts` from the archives of the plan into a staging tree, identity of what was
           obtained against the plan, switch, PROVENANCE, prune to the two latest verified points.
  rollback restore a verified point (validated entirely before any write), offline.

Vela is a display component: it never touches tools/pine_exec, the executor fingerprint, the
calibrations or the results — no recalibration follows a Vela update (checked by apply).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config, core, i18n, pinets_guide, tooling, update_guide

VV = Path("tools/vela_view")
PKG = "@luxalgo/vela"
BUNDLE_IN_PKG = "dist/vela.global.min.js"
BUNDLE_REL = "node_modules/@luxalgo/vela/" + BUNDLE_IN_PKG
PROVENANCE = "PROVENANCE.json"
TOP_FILES = ("package.json", "package-lock.json")
ROLLBACK_REL = core.RUNTIME_REL / "vela-rollback"
PLANS_REL = core.RUNTIME_REL / "vela-guide" / "plans"
CHECK_REL = core.RUNTIME_REL / "tooling" / "last-vela-check.json"
POINT_MANIFEST = "VELA_ROLLBACK.json"
POINT_FORMAT = 1
KEEP_POINTS = 2
NODE_MODULES = "node_modules"
STABLE_RE = re.compile(r"^\d+\.\d+\.\d+$")

# What the PWS page needs from Vela (tools/vela_view/page/pws-view.js): (label, declaration,
# exact member text, member name). A missing declaration or member blocks; a member present with
# another signature is ambiguous (the probe decides).
REQUIRED_API = (
    ("Vela class", "class Vela", "registerEngine(language: string, engine: ScriptingEngine)", "registerEngine"),
    ("addIndicator", "class Vela", "addIndicator(source: string, options?: AddIndicatorOptions): IndicatorHandle", "addIndicator"),
    ("setMarket", "class Vela", "setMarket(next: MarketSwitch)", "setMarket"),
    ("inspect", "class Vela", "inspect(): SceneInspection", "inspect"),
    ("renderer", "class Vela", "get renderer(): RendererControl", "renderer"),
    ("screenshot", "class RendererControl", "screenshot(): string | null", "screenshot"),
    ("onCrosshairMove", "class RendererControl", "onCrosshairMove(cb: (e: CrosshairEvent) => void)", "onCrosshairMove"),
    ("updateCode", "interface IndicatorHandle", "updateCode(", "updateCode"),
    ("handle events", "interface IndicatorHandle", "on<K extends keyof IndicatorEventMap>", "on"),
    ("engine prepare", "interface ScriptingEngine", "prepare(source: string, instanceId: string): Promise<PreparedScript>", "prepare"),
    ("engine execute", "interface ScriptingEngine", "execute(req: ExecutionRequest, handlers: ExecutionHandlers): ExecutionSession", "execute"),
    ("onModel", "interface ExecutionHandlers", "onModel(model: IndicatorModel): void", "onModel"),
    ("model series", "interface IndicatorModel", "series: SeriesSpec[]", "series"),
    ("model price lines", "interface IndicatorModel", "priceLines: PriceLine[]", "priceLines"),
    ("market data option", "interface MarketConfig", "data?: OHLCV[]", "data"),
)
BUNDLE_SCAN = (("dynamic import()", r"\bimport\(\s*['\"`]"), ("new Worker", r"new Worker\("),
               ("importScripts", r"importScripts\("), ("font files", r"\.(?:woff2?|ttf|otf)\b"))

_T = {
    "head.state": {"fr": "Vela — visualiseur du navigateur", "en": "Vela — browser chart"},
    "head.search": {"fr": "Recherche d'une nouvelle version de Vela (registre npm)",
                    "en": "Search for a new version of Vela (npm registry)"},
    "head.plan": {"fr": "Plan : Vela {cur} → {tgt}", "en": "Plan: Vela {cur} → {tgt}"},
    "head.record": {"fr": "Plan : enregistrer la provenance de Vela {cur} (aucun changement de version)",
                    "en": "Plan: record the provenance of Vela {cur} (no version change)"},
    "head.uptodate": {"fr": "Vela {cur} est déjà la dernière version stable publiée : aucune mise à jour.",
                      "en": "Vela {cur} is already the latest published stable version: no update."},
    "head.apply": {"fr": "Vela {cur} → {tgt} : {status}", "en": "Vela {cur} → {tgt}: {status}"},
    "head.rollback": {"fr": "Retour de Vela à {tgt} : {status}", "en": "Vela restored to {tgt}: {status}"},
    "nothing": {"fr": "Rien n'a été modifié.", "en": "Nothing was changed."},
    "no_recal": {"fr": "Aucune recalibration : Vela n'affecte ni le moteur PineTS, ni son empreinte, ni les calibrations.",
                 "en": "No recalibration: Vela affects neither the PineTS engine, nor its fingerprint, nor the calibrations."},
    "license_decision": {"fr": "Changement de licence : décision explicite requise ({items}). Relancer la préparation avec --accept-license pour chaque élément accepté.",
                         "en": "Licence change: explicit decision required ({items}). Prepare again with --accept-license for each accepted item."},
    "api_blocked": {"fr": "API nécessaire absente de la version candidate : {items}. Application impossible.",
                    "en": "Required API missing from the candidate: {items}. Cannot apply."},
    "api_ambiguous": {"fr": "Déclarations ambiguës : {items}. La sonde dans le navigateur doit réussir avant l'application.",
                      "en": "Ambiguous declarations: {items}. The browser probe must pass before applying."},
    "offline": {"fr": "Après « Appliquer », l'installation se fait hors ligne, depuis les archives vérifiées de ce plan, scripts désactivés.",
                "en": "After \"Apply\", installation runs offline from the verified archives of this plan, scripts disabled."},
}


def _t(key, lang, **kw):
    e = _T[key]; s = e.get(lang) or e["en"]
    return s.format(**kw) if kw else s


def _lang(root, lang=None):
    return i18n.normalize_language(lang or config.language(root))


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vv(root):
    return Path(root) / VV


def _npm_env(cache):
    env = dict(os.environ, npm_config_cache=str(cache), npm_config_update_notifier="false",
               npm_config_fund="false", npm_config_audit="false")
    return env


def _run(cmd, cwd=None, env=None, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def _version_key(v):
    return [int(x) for x in v.split(".")] if isinstance(v, str) and STABLE_RE.match(v) else None


# ----------------------------------------------------------------------------- local state
def _pkg_version(base, name):
    data, err = core.read_json(Path(base) / NODE_MODULES / name / "package.json")
    return data if isinstance(data, dict) and not err else {}


def _lock_entries(lock):
    pk = (lock or {}).get("packages") or {}
    out = {}
    for k, v in pk.items():
        if k.startswith("node_modules/") and isinstance(v, dict):
            out[k[len("node_modules/"):]] = {"version": v.get("version"), "integrity": v.get("integrity"),
                                             "resolved": v.get("resolved"), "license": v.get("license")}
    return out


def identity(root, base=None):
    """What is installed in `base` (default tools/vela_view): pin, lockfile entries, installed
    packages, bundle hash now, recorded provenance."""
    base = Path(base) if base else _vv(root)
    pkg, _ = core.read_json(base / "package.json")
    lock, _ = core.read_json(base / "package-lock.json")
    prov, perr = core.read_json(base / PROVENANCE)
    bundle = base / BUNDLE_REL
    deps = (pkg or {}).get("dependencies") or {}
    entries = _lock_entries(lock)
    return {"present": (base / "page" / "pws-view.js").is_file() or (base / "package.json").is_file(),
            "pinned": deps.get(PKG), "dependencies": deps,
            "lock_version": (entries.get(PKG) or {}).get("version"), "lock_integrity": (entries.get(PKG) or {}).get("integrity"),
            "lock_entries": entries, "lock_sha256": core.sha256_file(base / "package-lock.json") if (base / "package-lock.json").is_file() else None,
            "package_sha256": core.sha256_file(base / "package.json") if (base / "package.json").is_file() else None,
            "installed": _pkg_version(base, PKG).get("version"),
            "installed_ui": _pkg_version(base, "@luxalgo/vela-ui").get("version"),
            "connector_installed": (base / NODE_MODULES / "@luxalgo" / "vela-pinets").is_dir(),
            "bundle_sha256": core.sha256_file(bundle) if bundle.is_file() else None,
            "provenance": prov if isinstance(prov, dict) and not perr else None}


def _engine_guard(root):
    """Executor fingerprint and calibration file: a Vela operation must leave both unchanged."""
    cap = Path(root) / "tools" / "pine_exec" / "calibration" / "capabilities.json"
    try:
        fp = tooling._current_fingerprint(root)
    except Exception:  # noqa: BLE001 — reported as unknown, never guessed
        fp = None
    return {"executor_fingerprint": fp, "capabilities_sha256": core.sha256_file(cap) if cap.is_file() else None}


def state(root, lang=None):
    root = Path(root); lang = _lang(root, lang); ident = identity(root)
    prov = ident["provenance"] or {}
    points = list_points(root)
    chk, _ = core.read_json(Path(root) / CHECK_REL)
    lines = []
    if not ident["present"]:
        lines.append({"fr": "Vela n'est pas installé dans cet espace (composant vela-view absent).",
                      "en": "Vela is not installed in this workspace (vela-view component absent)."}[lang])
    else:
        lines.append(("Vela installé : %s (pin %s, vela-ui %s)" if lang == "fr" else "Vela installed: %s (pin %s, vela-ui %s)")
                     % (ident["installed"], ident["pinned"], ident["installed_ui"]))
        if prov.get("bundle", {}).get("sha256"):
            ok = prov["bundle"]["sha256"] == ident["bundle_sha256"] and prov.get("pinned_version") == ident["installed"]
            lines.append(({True: "Provenance vérifiée maintenant : le fichier chargé par la page correspond à l'archive npm enregistrée.",
                           False: "Provenance : le fichier chargé par la page NE correspond PAS à l'archive enregistrée."}[ok]) if lang == "fr"
                         else ({True: "Provenance verified now: the file the page loads matches the recorded npm archive.",
                                False: "Provenance: the file the page loads does NOT match the recorded archive."}[ok]))
        else:
            lines.append("Provenance non enregistrée : la préparation l'établira depuis le lockfile et l'archive npm vérifiée."
                         if lang == "fr" else "Provenance not recorded: preparation establishes it from the lockfile and the verified npm archive.")
        if ident["connector_installed"]:
            lines.append("Le connecteur @luxalgo/vela-pinets est encore installé." if lang == "fr"
                         else "The @luxalgo/vela-pinets connector is still installed.")
        lines.append(("Points de retour vérifiés : %s" if lang == "fr" else "Verified rollback points: %s")
                     % (", ".join(p["name"] for p in points if p["usable"]) or "-"))
        lines.append((("Dernière recherche : %s, dernière stable %s" if lang == "fr" else "Last search: %s, latest stable %s")
                      % (chk.get("checked_at"), chk.get("latest"))) if isinstance(chk, dict) and chk.get("checked_at")
                     else ("Aucune recherche effectuée : on ignore si une version plus récente existe." if lang == "fr"
                           else "No search done: whether a newer version exists is unknown."))
    return {"stage": "state", "component": "vela", "identity": ident, "rollback_points": points, "last_check": chk,
            "summary": update_guide.summary(lang, _t("head.state", lang), state=lines)}


# ----------------------------------------------------------------------------- search
def _npm_view(spec, fields, cache, runner=None):
    rc, out, err = (runner or _run)(["npm", "view", spec] + list(fields) + ["--json"], env=_npm_env(cache), timeout=120)
    if rc != 0:
        return None, (err or out).strip()[:300] or "npm view failed"
    try:
        return json.loads(out), None
    except ValueError:
        return None, "unreadable npm view output"


def search(root, lang=None, runner=None):
    root = Path(root); lang = _lang(root, lang); ident = identity(root)
    with tempfile.TemporaryDirectory(prefix="pws-vela-search-") as tmp:
        data, err = _npm_view(PKG, ["dist-tags", "versions", "time"], Path(tmp) / "cache", runner)
    rec = {"checked_at": _now(), "package": PKG, "pinned": ident["pinned"], "ok": data is not None, "error": err}
    if data:
        latest = (data.get("dist-tags") or {}).get("latest")
        stable = [v for v in (data.get("versions") or []) if STABLE_RE.match(v)]
        rec.update(latest=latest, latest_is_stable=bool(latest and STABLE_RE.match(latest)),
                   latest_published_at=(data.get("time") or {}).get(latest), stable_versions=stable[-10:])
        cur, lat = _version_key(ident["pinned"]), _version_key(latest)
        rec["result"] = ("update-available" if cur and lat and lat > cur else "up-to-date" if cur == lat
                         else "ahead" if cur and lat and lat < cur else "unknown")
        dest = Path(root) / CHECK_REL
        if core.runtime_tree_is_real(root, CHECK_REL.parent.parts):
            dest.parent.mkdir(parents=True, exist_ok=True); core.atomic_write_json(dest, rec)
    else:
        rec["result"] = "error"
    res = {"update-available": ("Version %s disponible sur npm (pin %s)." if lang == "fr" else "Version %s available on npm (pin %s).")
           % (rec.get("latest"), ident["pinned"]),
           "up-to-date": _t("head.uptodate", lang, cur=ident["pinned"]),
           "error": ("Recherche en échec : %s (on ne conclut pas « à jour »)." if lang == "fr"
                     else "Search failed: %s (never read as \"up to date\").") % err}.get(rec["result"], rec["result"])
    return {"stage": "search", "component": "vela", "result": rec,
            "summary": update_guide.summary(lang, _t("head.search", lang), result=[res, _t("nothing", lang)])}


# ----------------------------------------------------------------------------- archives and checks
def _fetch_archive(name, version, dest, cache, runner=None):
    """Download one npm archive (`npm pack`, scripts disabled) and check its integrity against the
    registry. Returns ({path, integrity, registry_integrity, license}, problems)."""
    meta, err = _npm_view("%s@%s" % (name, version), ["dist.integrity", "license"], cache, runner)
    if err:
        return None, ["registry: %s" % err]
    reg = meta.get("dist.integrity") if isinstance(meta, dict) else None
    dest.mkdir(parents=True, exist_ok=True)
    rc, out, err2 = (runner or _run)(["npm", "pack", "%s@%s" % (name, version), "--ignore-scripts", "--json",
                                      "--pack-destination", str(dest)], env=_npm_env(cache), timeout=300)
    if rc != 0:
        return None, ["npm pack failed: %s" % (err2 or out).strip()[:300]]
    try:
        fname = json.loads(out)[0]["filename"]
    except (ValueError, LookupError, TypeError):
        return None, ["npm pack: unreadable output"]
    path = dest / fname.replace("@", "").replace("/", "-")
    if not path.is_file():
        cands = sorted(dest.glob("*.tgz"), key=lambda p: p.stat().st_mtime)
        path = cands[-1] if cands else path
    sri = pinets_guide._sri_sha512(path) if path.is_file() else None
    problems = [] if sri and sri == reg else ["archive integrity %s differs from the registry (%s)" % (sri, reg)]
    return {"path": str(path), "integrity": sri, "registry_integrity": reg,
            "license": meta.get("license") if isinstance(meta, dict) else None}, problems


def _read_vela_archive(path):
    files, sha, problems = pinets_guide.read_tarball(path, wanted={"package.json", "LICENSE"},
                                                     entry="./" + BUNDLE_IN_PKG, optional=("CHANGELOG.md",))
    return files, sha, problems


def changelog_sections(text, current, target):
    """Sections `## [x.y.z]` / `## x.y.z` of the archive's own CHANGELOG with current < x <= target."""
    if not isinstance(text, str):
        return []
    cur, tgt = _version_key(current), _version_key(target)
    out, head, buf = [], None, []

    def flush():
        if head:
            k = _version_key(head)
            if k and cur and tgt and ((cur < k <= tgt) or (tgt < k <= cur)):
                out.append({"version": head, "text": "\n".join(buf).strip()[:8000]})
    for line in text.splitlines():
        m = re.match(r"^##\s+\[?v?(\d+\.\d+\.\d+)\]?", line)
        if m:
            flush(); head, buf = m.group(1), []
        elif head:
            buf.append(line)
    flush()
    return out


def _block(text, decl):
    m = re.search(r"(?:declare\s+)?%s\b[^{]*\{" % re.escape(decl), text)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0); i += 1
    return text[m.end():i]


def api_check(dist_dir):
    """Static check of what the page needs, in the candidate's type declarations."""
    texts = []
    for f in sorted(Path(dist_dir).glob("*.d.ts")):
        try:
            texts.append(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    text = "\n".join(texts)
    out = []
    for label, decl, exact, name in REQUIRED_API:
        blocks = []
        for m in re.finditer(r"(?:declare\s+)?%s\b" % re.escape(decl), text):
            b = _block(text[m.start():], decl)
            if b:
                blocks.append(b)
        if not blocks:
            status = "missing"
        elif any(exact in b for b in blocks):
            status = "ok"
        elif any(re.search(r"\b%s\b\s*[(<:?]" % re.escape(name), b) for b in blocks):
            status = "ambiguous"
        else:
            status = "missing"
        out.append({"api": label, "declaration": decl, "expected": exact, "status": status})
    return out


def bundle_scan(data):
    s = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    hits = {name: len(re.findall(rx, s)) for name, rx in BUNDLE_SCAN}
    urls = sorted(set(re.findall(r"https?://[A-Za-z0-9.-]+", s)))
    return {"starts_with_var_vela": s.lstrip().startswith("var Vela="), "loaders": hits, "network_hosts": urls}


def _tree_licenses(base, entries):
    out = {}
    for name, e in entries.items():
        lic = _pkg_version(base, name).get("license") or e.get("license")
        out[name] = {"version": e.get("version"), "license": lic if isinstance(lic, str) else json.dumps(lic)}
    return out


# ----------------------------------------------------------------------------- prepare
def prepare(root, target=None, lang=None, accept_license=(), dest=None, plan_file=None, runner=None):
    lang = _lang(Path(root), lang)
    out = _prepare(root, target, lang, accept_license, dest, plan_file, runner)
    if "summary" not in out:
        out["summary"] = update_guide.summary(lang, _t("head.state", lang), result=out["problems"] or [_t("nothing", lang)])
    return out


def _prepare(root, target, lang, accept_license, dest, plan_file, runner):
    root = Path(root); ident = identity(root)
    out = {"stage": "prepare", "component": "vela", "applicable": False, "plan_file": None, "plan_hash": None,
           "decision_required": None, "problems": []}
    if not ident["present"] or not ident["installed"]:
        out["problems"].append("Vela is not installed here (tools/vela_view)")
        out["summary"] = update_guide.summary(lang, _t("head.state", lang), result=out["problems"])
        return out
    work = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="pws-vela-plan-"))
    if core.is_within(root, work):
        out["problems"].append("the download folder must be outside the workspace")
        return out
    cache, arch = work / "cache", work / "archives"
    cur = ident["installed"]
    # 1. provenance of the CURRENT version: lockfile + verified archive + bundle extracted from it
    a_cur, probs = _fetch_archive(PKG, cur, arch, cache, runner)
    baseline = None
    if a_cur:
        files, bsha, p2 = _read_vela_archive(a_cur["path"])
        probs += p2
        if ident["lock_integrity"] != a_cur["integrity"]:
            probs.append("lockfile integrity of %s@%s differs from the verified archive" % (PKG, cur))
        if bsha and bsha != ident["bundle_sha256"]:
            probs.append("installed bundle differs from the bundle of the verified archive (altered installation)")
        baseline = {"package": PKG, "pinned_version": cur, "registry_integrity": a_cur["registry_integrity"],
                    "bundle": {"path": BUNDLE_REL, "sha256": bsha,
                               "source": "extracted from the npm archive whose integrity equals the lockfile and the registry"},
                    "license": json.loads(files.get("package.json", b"{}")).get("license") if files else None,
                    "dependencies": {k: v["version"] for k, v in ident["lock_entries"].items()},
                    "verified_at": _now()}
    if probs:
        out["problems"] += probs
        out["summary"] = update_guide.summary(lang, _t("head.state", lang), result=probs)
        return out
    # 2. target
    if target is None:
        meta, err = _npm_view(PKG, ["dist-tags"], cache, runner)
        tags = (meta.get("dist-tags", meta) if isinstance(meta, dict) else {}) or {}
        target = tags.get("latest") if isinstance(tags, dict) else None
        if not target:
            out["problems"].append("search failed: %s" % err)
            return out
    if not STABLE_RE.match(str(target)):
        out["problems"].append("target must be an exact stable version")
        return out
    plan = {"format": 1, "component": "vela", "created_at": _now(), "work_dir": str(work), "cache": str(cache),
            "current": {"version": cur, "package_sha256": ident["package_sha256"], "lock_sha256": ident["lock_sha256"],
                        "bundle_sha256": ident["bundle_sha256"]},
            "baseline_provenance": baseline, "engine_guard": _engine_guard(root)}
    if target == cur:
        if ident["provenance"] and (ident["provenance"].get("bundle") or {}).get("sha256") == baseline["bundle"]["sha256"]:
            out.update(applicable=False, up_to_date=True)
            out["summary"] = update_guide.summary(lang, _t("head.uptodate", lang, cur=cur), result=[_t("nothing", lang)])
            return out
        plan.update(kind="record-provenance", target={"version": cur})
        headline = _t("head.record", lang, cur=cur)
        change = [("Provenance : %s@%s, intégrité %s…, fichier chargé %s…" if lang == "fr" else
                   "Provenance: %s@%s, integrity %s…, loaded file %s…") % (PKG, cur, baseline["registry_integrity"][:20],
                                                                          baseline["bundle"]["sha256"][:16])]
    else:
        # 3. candidate lockfile and disposable candidate installation (scripts disabled)
        cand = work / "candidate"; cand.mkdir(parents=True, exist_ok=True)
        pkg, _ = core.read_json(_vv(root) / "package.json")
        pkg = dict(pkg or {}); pkg["dependencies"] = dict(pkg.get("dependencies") or {}); pkg["dependencies"][PKG] = target
        core.atomic_write_json(cand / "package.json", pkg)
        for cmd in (["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
                    ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]):
            rc, o, e = (runner or _run)(cmd, cwd=cand, env=_npm_env(cache), timeout=600)
            if rc != 0:
                out["problems"].append("%s failed: %s" % (" ".join(cmd[:2]), (e or o).strip()[:300]))
                return out
        a_tgt, probs = _fetch_archive(PKG, target, arch, cache, runner)
        if not a_tgt:
            out["problems"] += probs; return out
        files, tsha, p2 = _read_vela_archive(a_tgt["path"])
        probs += p2
        cident = identity(root, cand)
        if cident["lock_integrity"] != a_tgt["integrity"]:
            probs.append("candidate lockfile integrity differs from the verified archive")
        if cident["bundle_sha256"] != tsha:
            probs.append("candidate installation bundle differs from the bundle of the verified archive")
        if probs:
            out["problems"] += probs; return out
        cur_lic = _tree_licenses(_vv(root), ident["lock_entries"])
        new_lic = _tree_licenses(cand, cident["lock_entries"])
        deps = {"added": {k: v for k, v in new_lic.items() if k not in cur_lic},
                "removed": {k: v for k, v in cur_lic.items() if k not in new_lic},
                "changed": {k: {"from": cur_lic[k]["version"], "to": v["version"]} for k, v in new_lic.items()
                            if k in cur_lic and cur_lic[k]["version"] != v["version"]}}
        known = {v["license"] for v in cur_lic.values()}
        lic_changes = []
        for k, v in new_lic.items():
            if k in cur_lic and cur_lic[k]["license"] != v["license"]:
                lic_changes.append({"package": k, "version": v["version"], "from": cur_lic[k]["license"], "to": v["license"]})
            elif k not in cur_lic and v["license"] not in known:
                lic_changes.append({"package": k, "version": v["version"], "from": None, "to": v["license"]})
        accepted = set(accept_license or ())
        pending = [c for c in lic_changes if "%s@%s=%s" % (c["package"], c["version"], c["to"]) not in accepted]
        api = api_check(cand / NODE_MODULES / "@luxalgo" / "vela" / "dist")
        scan = bundle_scan(files.get(BUNDLE_IN_PKG, b"") or (cand / BUNDLE_REL).read_bytes())
        missing = [a["api"] for a in api if a["status"] == "missing"]
        ambiguous = [a["api"] for a in api if a["status"] == "ambiguous"]
        if not scan["starts_with_var_vela"]:
            ambiguous.append("global `var Vela=` form of the browser bundle")
        plan.update(kind="update", target={"version": target, "registry_integrity": a_tgt["registry_integrity"],
                                           "bundle_sha256": tsha, "license": json.loads(files["package.json"]).get("license")},
                    candidate={"dir": str(cand), "package_sha256": core.sha256_file(cand / "package.json"),
                               "lock_sha256": core.sha256_file(cand / "package-lock.json"),
                               "lock_entries": cident["lock_entries"]},
                    changelog=changelog_sections((files.get("CHANGELOG.md") or b"").decode("utf-8", "replace"), cur, target),
                    dependencies=deps, license_changes=lic_changes, license_accepted=sorted(accepted),
                    api=api, bundle_scan=scan, probe_required=bool(ambiguous), blocked=bool(missing))
        headline = _t("head.plan", lang, cur=cur, tgt=target)
        change = ["Composant : visualiseur Vela du navigateur (tools/vela_view) — package.json, lockfile, node_modules, PROVENANCE."
                  if lang == "fr" else "Component: browser chart Vela (tools/vela_view) — package.json, lockfile, node_modules, PROVENANCE.",
                  ("Archive %s@%s : intégrité égale au registre (%s…) ; fichier chargé par la page %s…" if lang == "fr"
                   else "Archive %s@%s: integrity equal to the registry (%s…); file loaded by the page %s…")
                  % (PKG, target, a_tgt["registry_integrity"][:20], tsha[:16]),
                  ("Dépendances : %d ajoutée(s), %d retirée(s), %d changée(s) — %s" if lang == "fr"
                   else "Dependencies: %d added, %d removed, %d changed — %s")
                  % (len(deps["added"]), len(deps["removed"]), len(deps["changed"]),
                     ", ".join("%s %s→%s" % (k, v["from"], v["to"]) for k, v in deps["changed"].items()) or "-"),
                  ("Licences : %s" if lang == "fr" else "Licences: %s")
                  % ("; ".join("%s@%s %s→%s" % (c["package"], c["version"], c["from"], c["to"]) for c in lic_changes)
                     or ("aucun changement" if lang == "fr" else "no change"))]
        for sec in plan["changelog"]:
            change.append("CHANGELOG %s : %s" % (sec["version"], sec["text"][:600].replace("\n", " ")))
        if missing:
            out["problems"].append(_t("api_blocked", lang, items=", ".join(missing)))
        if pending:
            out["decision_required"] = {"kind": "license", "items": ["%s@%s=%s" % (c["package"], c["version"], c["to"])
                                                                     for c in pending]}
    checks = [_t("offline", lang), ("Point de retour vérifié fichier par fichier avant tout changement ; les deux derniers points vérifiés sont conservés."
                                    if lang == "fr" else "Rollback point verified file by file before any change; the two latest verified points are kept."),
              _t("no_recal", lang)]
    if plan.get("probe_required"):
        checks.append(_t("api_ambiguous", lang, items=", ".join(a["api"] for a in plan["api"] if a["status"] == "ambiguous") or "bundle"))
    plan["plan_hash"] = pinets_guide._plan_hash(plan)
    if not core.runtime_tree_is_real(root, PLANS_REL.parts):
        out["problems"].append("plan folder is a symlink or escapes the workspace"); return out
    (root / PLANS_REL).mkdir(parents=True, exist_ok=True)
    pf = Path(plan_file) if plan_file else root / PLANS_REL / ("%s-%s.json" % (_now().replace(":", ""), plan.get("kind")))
    if os.path.lexists(str(pf)):
        out["problems"].append("plan file exists: %s" % pf); return out
    core.atomic_write_json(pf, plan)
    blocked = plan.get("blocked") or bool(out["decision_required"])
    out.update(applicable=not blocked, plan_file=str(pf), plan_hash=plan["plan_hash"], plan=plan)
    lim = [{"fr": "Une version ou une installation npm réussie ne prouve pas la compatibilité : contrôle d'API, sonde éventuelle et essai dans Safari la vérifient.",
            "en": "A version number or a successful npm install never proves compatibility: the API check, the probe if any and the Safari check do."}[lang]]
    out["summary"] = update_guide.summary(lang, headline, change=change, checks=checks, limits=lim,
                                          result=out["problems"] + ([_t("license_decision", lang, items=", ".join(out["decision_required"]["items"]))]
                                                                    if out["decision_required"] else []),
                                          confirm=update_guide.confirm_block(lang) if not blocked else None)
    return out


# ----------------------------------------------------------------------------- probe
PROBE_JS = r"""
(function(){var R=[],t=function(m){document.title='PWS-VELA-PROBE '+m;};
try{var V=window.Vela; if(!V||!V.Vela){t('fail no-global');return;}
var n=60,b=[],t0=1577836800000;for(var i=0;i<n;i++){var c=100+Math.sin(i/5)*3;b.push({time:t0+i*3600000,open:c,high:c+1,low:c-1,close:c+0.3});}
var ch=new V.Vela('#c',{symbol:'P',timeframe:'60',data:b,live:false,theme:'dark',volume:false});
var eng={language:'pws',capabilities:{streaming:false,visibleRange:false,inputs:false},
prepare:function(s,id){return Promise.resolve({language:'pws',inputs:[],meta:{title:'probe',overlay:false},reactsToViewport:false,token:id});},
execute:function(req,h){setTimeout(function(){h.onModel({id:req.prepared.token,title:'probe',overlay:false,paneHint:'new',
series:[{id:'p:s',title:'S',paneId:'unrouted',kind:'line',style:{color:'#9C27B0',width:1,lineStyle:'solid'},points:b.map(function(x){return{time:x.time,value:x.close%7}})}],
fills:[],backgrounds:[],priceLines:[{id:'p:l',paneId:'unrouted',price:3,color:'#F23645',lineStyle:'dashed',width:1,title:'L'}],inputs:[],inputValues:{}});if(h.onDone)h.onDone();},0);
return{stop:function(){},update:function(){},setVisibleRange:function(){},notifyBars:function(){}};}};
ch.registerEngine('pws',eng);var hd=ch.addIndicator('probe',{language:'pws',id:'probe'});
setTimeout(function(){try{var T=ch.inspect().totals;R.push('series='+T.series,'levels='+T.priceLines);
R.push('updateCode='+(typeof hd.updateCode),'crosshair='+(typeof ch.renderer.onCrosshairMove),'setMarket='+(typeof ch.setMarket));
var u=ch.renderer.screenshot();R.push('png='+(typeof u==='string'&&u.indexOf('data:image/png')===0));
var ok=T.series>=1&&T.priceLines>=1&&typeof hd.updateCode==='function'&&typeof ch.renderer.onCrosshairMove==='function'&&typeof u==='string';
t((ok?'ok ':'fail ')+R.join(' '));}catch(e){t('fail '+e.message);}},2500);}catch(e){t('fail '+e.message);}})();
"""


def probe(root, plan_file, lang=None, opener=None, reader=None, wait=30):
    """Run the CANDIDATE bundle in the default browser (macOS): a page with a tiny chart, the replay
    engine shape of PWS, a price line and a screenshot; the tab title carries the verdict."""
    plan, err = core.read_json(plan_file)
    if err or plan.get("kind") != "update":
        return {"ok": False, "error": "no update plan to probe"}
    cand = Path(plan["candidate"]["dir"])
    page = cand / "probe.html"
    page.write_text('<!doctype html><meta charset="utf-8"><title>PWS-VELA-PROBE loading</title>'
                    '<div id="c" style="width:800px;height:420px"></div><script src="%s"></script><script>%s</script>'
                    % ((cand / BUNDLE_REL).as_uri(), PROBE_JS), encoding="utf-8")
    (opener or subprocess.run)(["open", str(page)], capture_output=True, text=True, timeout=30)
    import time
    title, t0 = "", time.time()
    while time.time() - t0 < wait:
        if reader:
            title = reader()
        else:
            rc, o, e = _run(["osascript", "-e", 'tell application "Safari" to get name of current tab of front window'], timeout=10)
            title = o.strip()
        if title.startswith("PWS-VELA-PROBE ok") or title.startswith("PWS-VELA-PROBE fail"):
            break
        time.sleep(0.5)
    res = {"ok": title.startswith("PWS-VELA-PROBE ok"), "title": title, "plan_hash": plan["plan_hash"],
           "bundle_sha256": plan["target"]["bundle_sha256"], "at": _now()}
    core.atomic_write_json(Path(plan["work_dir"]) / "probe.json", res)
    return res


# ----------------------------------------------------------------------------- rollback points
def _rb_ok(root):
    return core.runtime_tree_is_real(root, ROLLBACK_REL.parts)


def _save_point(root, label):
    """Copy package.json, lockfile, PROVENANCE (if any) and node_modules of tools/vela_view into a
    new point with a per-file hash manifest, then validate it. No verified point → no change."""
    if not _rb_ok(root):
        return {"ok": False, "error": "rollback tree is a symlink or escapes the workspace"}
    vv, rdir = _vv(root), Path(root) / ROLLBACK_REL
    import uuid
    dest = rdir / ("%s-%s-%s" % (label, _now().replace(":", "").replace("-", ""), uuid.uuid4().hex[:6]))
    dest.mkdir(parents=True)
    entries, problems = [], []
    try:
        for rel in TOP_FILES + (PROVENANCE,):
            src = vv / rel
            if src.is_file() and not src.is_symlink():
                shutil.copy2(str(src), str(dest / rel)); entries.append({"path": rel, "sha256": core.sha256_file(src)})
        for rel, kind, info in tooling._walk_tree(vv / NODE_MODULES):
            full = NODE_MODULES + "/" + rel
            if kind == "file":
                (dest / full).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(vv / full), str(dest / full)); entries.append({"path": full, "sha256": info})
            elif kind == "symlink" and tooling._symlink_target_ok(full, info):
                entries.append({"path": full, "symlink": info})
            else:
                problems.append("%s: not saved (%s)" % (full, kind))
        ident = identity(root)
        core.atomic_write_json(dest / POINT_MANIFEST, {"format": POINT_FORMAT, "component": "vela", "saved_at": _now(),
                                                       "version": ident["installed"], "bundle_sha256": ident["bundle_sha256"],
                                                       "entries": entries})
        chk = check_point(root, dest)
        problems += chk["problems"]
    except (OSError, KeyboardInterrupt) as exc:
        shutil.rmtree(str(dest), ignore_errors=True)
        return {"ok": False, "error": "rollback point not saved: %s" % exc}
    if problems:
        shutil.rmtree(str(dest), ignore_errors=True)
        return {"ok": False, "error": "rollback point not verified: %s" % "; ".join(problems[:3])}
    return {"ok": True, "name": dest.name, "path": str(dest), "entries": len(entries)}


def check_point(root, pdir):
    pdir = Path(pdir)
    man, err = core.read_json(pdir / POINT_MANIFEST)
    if err or not isinstance(man, dict) or man.get("format") != POINT_FORMAT:
        return {"usable": False, "problems": ["manifest missing or in another format"], "manifest": None}
    problems, listed = [], set()
    for e in man.get("entries") or []:
        rel = e.get("path", "")
        if rel.startswith("/") or ".." in rel.split("/"):
            problems.append("unsafe path %r" % rel); continue
        listed.add(rel)
        if "sha256" in e:
            f = pdir / rel
            if not f.is_file() or f.is_symlink() or core.sha256_file(f) != e["sha256"]:
                problems.append("%s: missing or altered" % rel)
        elif not tooling._symlink_target_ok(rel, e.get("symlink")):
            problems.append("%s: symlink target leaves node_modules" % rel)
    if (pdir / NODE_MODULES).is_dir():
        for rel, kind, _ in tooling._walk_tree(pdir / NODE_MODULES):
            if kind == "file" and (NODE_MODULES + "/" + rel) not in listed:
                problems.append("%s/%s: not listed" % (NODE_MODULES, rel)); break
    bundle = next((e for e in man["entries"] if e.get("path") == BUNDLE_REL), None)
    if not bundle or bundle.get("sha256") != man.get("bundle_sha256"):
        problems.append("bundle entry missing or different from the recorded bundle hash")
    return {"usable": not problems, "problems": problems, "manifest": man}


def list_points(root):
    rdir = Path(root) / ROLLBACK_REL
    if not _rb_ok(root) or not rdir.is_dir():
        return []
    out = []
    for d in sorted(rdir.iterdir()):
        if d.is_dir() and not d.is_symlink():
            c = check_point(root, d)
            m = c["manifest"] or {}
            out.append({"name": d.name, "version": m.get("version"), "saved_at": m.get("saved_at"),
                        "bundle_sha256": m.get("bundle_sha256"), "usable": c["usable"], "problems": c["problems"][:3]})
    out.sort(key=lambda p: p["saved_at"] or "")
    return out


def _prune(root, keep_names=()):
    """Keep the KEEP_POINTS latest verified points (plus any in `keep_names`); unverifiable points
    are never deleted here (reported)."""
    usable = [p for p in list_points(root) if p["usable"]]
    drop = [p for p in usable[:-KEEP_POINTS] if p["name"] not in keep_names] if len(usable) > KEEP_POINTS else []
    for p in drop:
        shutil.rmtree(str(Path(root) / ROLLBACK_REL / p["name"]), ignore_errors=True)
    return [p["name"] for p in drop]


def _switch(root, stage_nm, top_files, provenance, expect_bundle):
    """Replace tools/vela_view/node_modules by `stage_nm` and write the top files; verify the bundle."""
    vv = _vv(root); stamp = _now().replace(":", "")
    old = vv / ("node_modules.replaced-" + stamp)
    os.rename(str(vv / NODE_MODULES), str(old))
    try:
        os.rename(str(stage_nm), str(vv / NODE_MODULES))
    except OSError:
        os.rename(str(old), str(vv / NODE_MODULES)); raise
    for rel, data in top_files.items():
        tmp = vv / (rel + ".tmp-" + stamp); tmp.write_bytes(data); os.replace(str(tmp), str(vv / rel))
    if provenance is not None:
        core.atomic_write_json(vv / PROVENANCE, provenance)
    got = core.sha256_file(vv / BUNDLE_REL) if (vv / BUNDLE_REL).is_file() else None
    if got != expect_bundle:
        return False, str(old), got
    shutil.rmtree(str(old), ignore_errors=True)
    return True, None, got


# ----------------------------------------------------------------------------- apply / rollback
def apply(root, plan_file, yes=False, lang=None, npm_runner=None):
    root = Path(root); lang = _lang(root, lang)
    rep = {"stage": "apply", "component": "vela", "ok": False, "status": "refused-before-mutation", "problems": []}
    plan, err = core.read_json(plan_file)
    if err or not isinstance(plan, dict) or plan.get("component") != "vela":
        rep["problems"].append("plan unreadable"); return rep
    if pinets_guide._plan_hash(plan) != plan.get("plan_hash"):
        rep["problems"].append("plan modified after its preparation")
    if not yes:
        rep["problems"].append("explicit confirmation required (--yes after \"Apply\")")
    ident = identity(root)
    for k in ("package_sha256", "lock_sha256", "bundle_sha256"):
        if ident[k] != plan["current"][k]:
            rep["problems"].append("installed Vela changed since the plan (%s)" % k)
    if plan.get("blocked"):
        rep["problems"].append("plan blocked by a missing API")
    lic = [c for c in plan.get("license_changes") or []
           if "%s@%s=%s" % (c["package"], c["version"], c["to"]) not in set(plan.get("license_accepted") or [])]
    if lic:
        rep["problems"].append("licence change without explicit decision")
    if plan.get("probe_required"):
        pr, _ = core.read_json(Path(plan["work_dir"]) / "probe.json")
        if not (isinstance(pr, dict) and pr.get("ok") and pr.get("plan_hash") == plan["plan_hash"]):
            rep["problems"].append("browser probe of the candidate required and not passed")
    guard0 = _engine_guard(root)
    if guard0 != plan["engine_guard"]:
        rep["problems"].append("PineTS engine changed since the plan")
    if rep["problems"]:
        return _apply_summary(rep, plan, lang)
    with tooling._lock(root):
        point = _save_point(root, ident["installed"] or "unknown")
        if not point["ok"]:
            rep["problems"].append(point["error"]); return _apply_summary(rep, plan, lang)
        rep["rollback_point"] = point["name"]
        vv = _vv(root)
        if plan["kind"] == "record-provenance":
            prov = dict(plan["baseline_provenance"], previous=None, recorded_at=_now())
            core.atomic_write_json(vv / PROVENANCE, prov)
            rep.update(ok=True, status="provenance-recorded")
        else:
            stage = vv / (".vela-stage-" + _now().replace(":", ""))
            stage.mkdir()
            cand = Path(plan["candidate"]["dir"])
            for rel in TOP_FILES:
                shutil.copy2(str(cand / rel), str(stage / rel))
            if core.sha256_file(stage / "package-lock.json") != plan["candidate"]["lock_sha256"] or \
                    core.sha256_file(stage / "package.json") != plan["candidate"]["package_sha256"]:
                shutil.rmtree(str(stage), ignore_errors=True)
                rep["problems"].append("candidate files differ from the plan"); return _apply_summary(rep, plan, lang)
            rc, o, e = (npm_runner or _run)(["npm", "ci", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"],
                                            cwd=stage, env=_npm_env(plan["cache"]), timeout=600)
            sident = identity(root, stage)
            bad = rc != 0 or sident["installed"] != plan["target"]["version"] or sident["bundle_sha256"] != plan["target"]["bundle_sha256"] \
                or {k: v["integrity"] for k, v in sident["lock_entries"].items()} != \
                {k: v["integrity"] for k, v in plan["candidate"]["lock_entries"].items()}
            if bad:
                shutil.rmtree(str(stage), ignore_errors=True)
                rep.update(status="install-failed")
                rep["problems"].append("offline installation differs from the plan: %s" % ((e or o).strip()[:200] if rc else "identity"))
                return _apply_summary(rep, plan, lang)
            prov = {"package": PKG, "pinned_version": plan["target"]["version"], "registry_integrity": plan["target"]["registry_integrity"],
                    "bundle": {"path": BUNDLE_REL, "sha256": plan["target"]["bundle_sha256"],
                               "source": "extracted from the npm archive whose integrity equals the lockfile and the registry"},
                    "license": plan["target"]["license"],
                    "dependencies": {k: v["version"] for k, v in plan["candidate"]["lock_entries"].items()},
                    "verified_at": _now(), "previous": {"version": plan["current"]["version"], "rollback_point": point["name"],
                                                         "provenance": plan.get("baseline_provenance")}}
            tops = {rel: (stage / rel).read_bytes() for rel in TOP_FILES}
            ok, kept, got = _switch(root, stage / NODE_MODULES, tops, prov, plan["target"]["bundle_sha256"])
            shutil.rmtree(str(stage), ignore_errors=True)
            if not ok:
                rep.update(status="verification-failed", kept=kept)
                rep["problems"].append("active bundle %s differs from the plan" % got); return _apply_summary(rep, plan, lang)
            rep.update(ok=True, status="completed")
        rep["pruned"] = _prune(root, keep_names=(point["name"],))
    rep["engine_guard_unchanged"] = _engine_guard(root) == guard0
    rep["identity"] = identity(root)
    return _apply_summary(rep, plan, lang)


def _apply_summary(rep, plan, lang):
    cur = plan.get("current", {}).get("version") if isinstance(plan, dict) else "?"
    tgt = (plan.get("target") or {}).get("version") if isinstance(plan, dict) else "?"
    changed, checks = [], []
    if rep.get("ok"):
        ident = rep["identity"]
        changed.append(("Vela installé : %s ; fichier chargé par la page %s…" if lang == "fr" else
                        "Vela installed: %s; file loaded by the page %s…") % (ident["installed"], (ident["bundle_sha256"] or "")[:16]))
        checks.append(("Point de retour vérifié : %s" if lang == "fr" else "Verified rollback point: %s") % rep.get("rollback_point"))
        checks.append(_t("no_recal", lang) + (" ✓" if rep.get("engine_guard_unchanged") else " ✗"))
        if rep.get("pruned"):
            checks.append(("Anciens points retirés (deux conservés) : %s" if lang == "fr" else
                           "Older points removed (two kept): %s") % ", ".join(rep["pruned"]))
    rec = ["python3 -m tools.pws_workspace vela rollback --yes"] if rep.get("rollback_point") else []
    rep["summary"] = update_guide.summary(lang, _t("head.apply", lang, cur=cur, tgt=tgt, status=rep["status"]),
                                          changed=changed, checks_done=checks, result=rep["problems"], recovery=rec)
    return rep


def rollback(root, point=None, yes=False, lang=None):
    """Restore a verified point (default: the latest whose version differs from the installed one),
    after saving the current state as a point; offline; validated entirely before any write."""
    root = Path(root); lang = _lang(root, lang)
    rep = {"stage": "rollback", "component": "vela", "ok": False, "status": "refused", "problems": []}
    points = list_points(root); ident = identity(root)
    if point:
        chosen = next((p for p in points if p["name"] == point), None)
    else:
        cands = [p for p in points if p["usable"] and p["version"] != ident["installed"]]
        chosen = cands[-1] if cands else None
    if not chosen or not chosen["usable"]:
        rep["problems"].append("no verified rollback point to restore" + (": %s" % "; ".join(chosen["problems"]) if chosen else ""))
    if not yes:
        rep["problems"].append("explicit confirmation required (--yes)")
    if rep["problems"]:
        rep["summary"] = update_guide.summary(lang, _t("head.rollback", lang, tgt=chosen["version"] if chosen else "?",
                                                      status=rep["status"]), result=rep["problems"])
        return rep
    guard0 = _engine_guard(root)
    pdir = Path(root) / ROLLBACK_REL / chosen["name"]
    with tooling._lock(root):
        chk = check_point(root, pdir)
        if not chk["usable"]:
            rep["problems"] += chk["problems"]; return rep
        pre = _save_point(root, ident["installed"] or "unknown")
        if not pre["ok"]:
            rep["problems"].append(pre["error"]); return rep
        vv = _vv(root); stage = vv / (".vela-restore-" + _now().replace(":", ""))
        (stage / NODE_MODULES).mkdir(parents=True)
        for e in chk["manifest"]["entries"]:
            if e["path"].startswith(NODE_MODULES + "/"):
                dst = stage / e["path"]; dst.parent.mkdir(parents=True, exist_ok=True)
                if "sha256" in e:
                    shutil.copy2(str(pdir / e["path"]), str(dst))
                    if core.sha256_file(dst) != e["sha256"]:
                        shutil.rmtree(str(stage), ignore_errors=True)
                        rep["problems"].append("%s: copy differs" % e["path"]); return rep
                else:
                    os.symlink(e["symlink"], str(dst))
        tops = {rel: (pdir / rel).read_bytes() for rel in TOP_FILES if (pdir / rel).is_file()}
        prov, _ = core.read_json(pdir / PROVENANCE)
        if not isinstance(prov, dict):
            prov = None
            (vv / PROVENANCE).unlink(missing_ok=True)
        ok, kept, got = _switch(root, stage / NODE_MODULES, tops, prov, chk["manifest"]["bundle_sha256"])
        shutil.rmtree(str(stage), ignore_errors=True)
        if not ok:
            rep.update(status="incomplete", kept=kept); rep["problems"].append("restored bundle %s differs" % got); return rep
        rep.update(ok=True, status="restored", restored=chosen["name"], pre_rollback_point=pre["name"])
        rep["pruned"] = _prune(root, keep_names=(pre["name"], chosen["name"]))
    rep["engine_guard_unchanged"] = _engine_guard(root) == guard0
    rep["identity"] = identity(root)
    rep["summary"] = update_guide.summary(lang, _t("head.rollback", lang, tgt=chosen["version"], status=rep["status"]),
                                          changed=[("Vela installé : %s ; fichier chargé %s…" if lang == "fr" else "Vela installed: %s; loaded file %s…")
                                                   % (rep["identity"]["installed"], rep["identity"]["bundle_sha256"][:16])],
                                          checks_done=[("Point restauré : %s ; état précédent sauvegardé : %s" if lang == "fr" else
                                                        "Point restored: %s; previous state saved: %s") % (chosen["name"], pre["name"]),
                                                       _t("no_recal", lang) + (" ✓" if rep["engine_guard_unchanged"] else " ✗")])
    return rep
