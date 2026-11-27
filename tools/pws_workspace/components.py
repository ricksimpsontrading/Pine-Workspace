# SPDX-License-Identifier: Apache-2.0
"""Preparation of the local test components of a standard installation (isolated study copy):
PineTS (the only computation engine, tools/pine_exec), the 500-candle demonstration dataset and
Vela (the browser chart that displays PWS results, tools/vela_view).

`components prepare` is run by the installer and can be run again at any time to resume:
- nothing global is installed: only `npm ci --ignore-scripts` from the shipped lockfiles, inside
  tools/pine_exec and tools/vela_view (Node.js and npm must already be on the machine);
- a component already ready is left as it is; scripts, configuration, runs and the work copy of a
  session are never touched;
- PineTS is verified with the existing checks (pin, lockfile, registry integrity, installed artefact,
  executor fingerprint); Vela's provenance is established from the verified npm archive of the
  pinned version (guided path, provenance only — never a version change);
- a Vela failure leaves the numeric test usable when PineTS is ready;
- no follow-up is started and no browser is opened.
"""
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

STATE = Path(".claude") / "runtime" / "components.json"
DEMO = Path(".claude") / "runtime" / "pine-local-test" / "datasets" / "lcg-7-500.json"
DEMO_SHA256 = "65bb3837349c878e427ddde6da3a6ba89c836878dcb19c8de1db1c8833f16b9b"
DEMO_ARGS = ["gen", "--seed", "7", "--bars", "500", "--base-cents", "10000", "--vol-cents", "150"]
RESUME = "python3 -m tools.pws_workspace components prepare"

TEXT = {
    "node_missing": {"en": "Node.js and npm are needed for local tests and charts (not found: %s). Install Node.js "
                           "(it brings npm), then resume with: %s",
                     "fr": "Node.js et npm sont nécessaires aux tests locaux et aux graphiques (introuvables : %s). "
                           "Installez Node.js (npm est fourni avec), puis reprenez avec : %s"},
    "ready": {"en": "ready", "fr": "prêt"},
    "failed": {"en": "not ready", "fr": "pas prêt"},
    "skipped": {"en": "not prepared", "fr": "non préparé"},
    "head": {"en": "Local test components", "fr": "Composants des tests locaux"},
    "pinets": {"en": "PineTS %s (computation engine)", "fr": "PineTS %s (moteur de calcul)"},
    "demo": {"en": "demonstration data (500 simulated candles)", "fr": "données de démonstration (500 bougies simulées)"},
    "vela": {"en": "Vela %s (browser chart)", "fr": "Vela %s (graphique dans le navigateur)"},
    "numeric_ok": {"en": "The numeric local test is usable; the chart is not available until Vela is ready.",
                   "fr": "Le test local numérique est utilisable ; le graphique ne l'est pas tant que Vela n'est pas prêt."},
    "resume": {"en": "To resume (keeps your scripts and settings): %s", "fr": "Pour reprendre (vos scripts et réglages sont conservés) : %s"},
    "all_ready": {"en": "Everything is ready: test a script, then open its chart.",
                  "fr": "Tout est prêt : testez un script, puis ouvrez son graphique."},
}


def _t(key, lang, *a):
    s = TEXT[key].get(lang) or TEXT[key]["en"]
    return s % a if a else s


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _run(cmd, cwd, timeout=900):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "")[-2000:], (p.stderr or "")[-2000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", "%s: %s" % (type(exc).__name__, exc)


def _npm_ci(root, rel, runner):
    cmd = [shutil.which("npm") or "npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    return (runner or _run)(cmd, Path(root) / rel)


def lock_mismatches(root, rel):
    """Packages whose installed version differs from the lockfile (or that are missing), in `rel`."""
    base = Path(root) / rel
    try:
        pkgs = (json.loads((base / "package-lock.json").read_text(encoding="utf-8")).get("packages") or {})
    except (OSError, ValueError):
        return [{"package": "(lockfile)", "locked": None, "installed": None, "why": "package-lock.json unreadable"}]
    out = []
    for key, meta in sorted(pkgs.items()):
        if not key.startswith("node_modules/") or meta.get("dev") or meta.get("optional"):
            continue
        try:
            installed = json.loads((base / key / "package.json").read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            installed = None
        if installed != meta.get("version"):
            out.append({"package": key[len("node_modules/"):], "locked": meta.get("version"), "installed": installed})
    return out


def _pinets_ready(root):
    from . import tooling
    findings = tooling.verify(root)
    bad = [f for f in findings if f["status"] not in ("OK", "INFO")]
    fp = next((f["detail"] for f in findings if f["check"] == "fingerprint"), None)
    return not bad and any(f["check"] == "installed" and f["status"] == "OK" for f in findings), findings, fp


def prepare_pinets(root, runner=None):
    root = Path(root)
    pin = (json.loads((root / "tools/pine_exec/package.json").read_text()).get("dependencies") or {}).get("pinets")
    out = {"component": "pinets", "version": pin, "actions": [], "ok": False}
    ok, findings, fp = _pinets_ready(root)
    mism = lock_mismatches(root, "tools/pine_exec")
    if not ok or mism:
        if mism:
            out["actions"].append({"lock_mismatches": mism})
        rc, so, se = _npm_ci(root, "tools/pine_exec", runner)
        out["actions"].append({"npm_ci": rc, "stderr": se.strip()[-600:]})
        if rc != 0:
            out["problem"] = "npm ci failed in tools/pine_exec (exit %s): %s" % (rc, (se or so).strip()[-300:])
            return out
        ok, findings, fp = _pinets_ready(root)
        mism = lock_mismatches(root, "tools/pine_exec")
        if mism:
            out["problem"] = "after repair, installed versions still differ from the lockfile: %s" % ", ".join(
                "%s %s (locked %s)" % (m["package"], m["installed"], m["locked"]) for m in mism)
            return out
    out.update(ok=ok, executor_fingerprint=fp,
               verify=[{k: f[k] for k in ("check", "status")} for f in findings])
    if not ok:
        out["problem"] = "PineTS installed but its verification failed: %s" % ", ".join(
            "%s %s" % (f["check"], f["status"]) for f in findings if f["status"] not in ("OK", "INFO"))
    return out


def prepare_demo(root, runner=None):
    root = Path(root); f = root / DEMO
    out = {"component": "demo-dataset", "path": str(DEMO), "ok": False, "actions": []}
    if f.is_file() and _sha(f) == DEMO_SHA256:
        out["ok"] = True; return out
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    rc, so, se = (runner or _run)([shutil.which("node") or "node", "datasets.mjs"] + DEMO_ARGS + ["--out", str(tmp)],
                                  root / "tools" / "pine_exec", 120)
    out["actions"].append({"generate": rc})
    if rc != 0 or not tmp.is_file():
        out["problem"] = "demonstration data not generated (exit %s): %s" % (rc, (se or so).strip()[-300:]); return out
    if _sha(tmp) != DEMO_SHA256:
        tmp.unlink(); out["problem"] = "demonstration data differ from the reference (SHA-256)"; return out
    tmp.replace(f); out["ok"] = True
    return out


def prepare_vela(root, lang="en", runner=None, guide=None):
    from . import live, vela_guide
    root = Path(root); g = guide or vela_guide
    out = {"component": "vela", "ok": False, "actions": []}
    if not (root / "tools/vela_view/package.json").is_file():
        out["problem"] = "the Vela component is not part of this package"; return out
    pin = (json.loads((root / "tools/vela_view/package.json").read_text()).get("dependencies") or {}).get(g.PKG)
    out["version"] = pin
    ident = g.identity(root)
    mism = lock_mismatches(root, "tools/vela_view")
    if mism or ident.get("connector_installed") or live.vela_state(root) != "ready":
        if mism:
            out["actions"].append({"lock_mismatches": mism})
        rc, so, se = _npm_ci(root, "tools/vela_view", runner)
        out["actions"].append({"npm_ci": rc, "stderr": se.strip()[-600:]})
        if rc != 0:
            out["problem"] = "npm ci failed in tools/vela_view (exit %s)%s: %s" % (
                rc, "; installed versions differ from the lockfile: " + ", ".join(
                    "%s %s (locked %s)" % (m["package"], m["installed"], m["locked"]) for m in mism) if mism else "",
                (se or so).strip()[-300:])
            return out
        ident = g.identity(root)
        mism = lock_mismatches(root, "tools/vela_view")
        if mism:
            out["problem"] = "after repair, installed versions still differ from the lockfile: %s" % ", ".join(
                "%s %s (locked %s)" % (m["package"], m["installed"], m["locked"]) for m in mism)
            return out
    if ident.get("installed") != pin:
        out["problem"] = "Vela installed %s, pinned %s" % (ident.get("installed"), pin); return out
    prov = ident.get("provenance") or {}
    verified = ((prov.get("bundle") or {}).get("sha256") == ident.get("bundle_sha256")
                and prov.get("pinned_version") == pin)
    if not verified:
        # provenance from the verified npm archive of the PINNED version: a record-provenance plan only
        plan = g.prepare(root, target=pin, lang=lang)
        out["actions"].append({"provenance_plan": plan.get("plan_file"), "problems": plan.get("problems")})
        p, _ = (None, None)
        try:
            p = json.loads(Path(plan["plan_file"]).read_text()) if plan.get("plan_file") else None
        except (OSError, ValueError):
            p = None
        if not p or p.get("kind") != "record-provenance":
            out["problem"] = "Vela provenance not established: %s" % "; ".join(plan.get("problems") or
                                                                             ["the plan is not a provenance record (%s)" % (p or {}).get("kind")])
            return out
        r = g.apply(root, plan["plan_file"], yes=True, lang=lang)
        out["actions"].append({"provenance": r.get("status")})
        if r.get("status") != "provenance-recorded":
            out["problem"] = "Vela provenance not recorded: %s" % "; ".join(r.get("problems") or [str(r.get("status"))]); return out
        ident = g.identity(root); prov = ident.get("provenance") or {}
    out.update(ok=live.vela_state(root) == "ready", installed=ident.get("installed"), vela_ui=ident.get("installed_ui"),
               bundle_sha256=ident.get("bundle_sha256"),
               provenance_verified=(prov.get("bundle") or {}).get("sha256") == ident.get("bundle_sha256"))
    if not out["provenance_verified"]:
        out["ok"] = False; out["problem"] = "Vela's file differs from its recorded provenance"
    return out


def prepare(root, lang="en", runner=None, guide=None):
    """Prepare (or resume preparing) PineTS, the demonstration data and Vela. Idempotent."""
    root = Path(root)
    missing = [b for b in ("node", "npm") if not shutil.which(b)]
    rep = {"started_at": _now(), "node": shutil.which("node"), "npm": shutil.which("npm"), "components": []}
    if missing:
        rep.update(ok=False, problem=_t("node_missing", lang, ", ".join(missing), RESUME),
                   components=[{"component": c, "ok": False, "problem": "Node.js/npm missing"} for c in ("pinets", "demo-dataset", "vela")])
    else:
        p = prepare_pinets(root, runner); rep["components"].append(p)
        d = prepare_demo(root, runner) if p["ok"] else {"component": "demo-dataset", "ok": False, "problem": "needs PineTS"}
        rep["components"].append(d)
        try:
            v = prepare_vela(root, lang, runner, guide)
        except Exception as exc:  # noqa: BLE001 — a chart failure never hides the numeric test
            v = {"component": "vela", "ok": False, "problem": "%s: %s" % (type(exc).__name__, exc)}
        rep["components"].append(v)
        rep["ok"] = all(c["ok"] for c in rep["components"])
    rep["finished_at"] = _now()
    rep["numeric_test_usable"] = any(c["component"] == "pinets" and c["ok"] for c in rep["components"])
    rep["chart_usable"] = any(c["component"] == "vela" and c["ok"] for c in rep["components"])
    rep["resume"] = None if rep["ok"] else RESUME
    rep["summary"] = summary(rep, lang)
    st = root / STATE; st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rep


def summary(rep, lang):
    lines = [_t("head", lang) + " :" if lang == "fr" else _t("head", lang) + ":"]
    if rep.get("problem"):
        lines.append("- " + rep["problem"])
        return "\n".join(lines)
    for c in rep["components"]:
        name = {"pinets": _t("pinets", lang, c.get("version") or "?"), "demo-dataset": _t("demo", lang),
                "vela": _t("vela", lang, c.get("version") or "?")}[c["component"]]
        lines.append("- %s : %s%s" % (name, _t("ready" if c["ok"] else "failed", lang),
                                      "" if c["ok"] else " — " + (c.get("problem") or "")))
    if rep["ok"]:
        lines.append(_t("all_ready", lang))
    else:
        if rep["numeric_test_usable"] and not rep["chart_usable"]:
            lines.append(_t("numeric_ok", lang))
        lines.append(_t("resume", lang, RESUME))
    return "\n".join(lines)


def status(root):
    st = Path(root) / STATE
    try:
        return json.loads(st.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
