# SPDX-License-Identifier: Apache-2.0
"""Guided update of the PineTS engine (2.2.0) — one continuous path over the
EXISTING lifecycle of `tooling` (status, check-update, install with its
verified rollback point, verify, rollback) and the guided recalibration
(`recalibration`). No second installer, no second backup or restoration.

Stages, each explicit, none at session start:

  state     engine installed, integrity verified now, calibrations CURRENT /
            STALE, capabilities actually verified, documented divergences,
            last dated search.
  search    `pinets check-update` (npm registry); an error is never "up to
            date"; a pre-release is never proposed by default.
  prepare   for one exact version: registry metadata, download of the npm
            archive into a temporary folder OUTSIDE the workspace (`npm pack`,
            scripts disabled), its integrity compared with the registry
            value, its content read WITHOUT extraction (package.json, LICENSE,
            the artifact used by the adapter and its hash), prerequisites
            (Node / npm, declared engines), the entry used by the runner, the
            licence compared with the recorded one (a different licence
            identifier stops the plan: the holder decides, spec 24.4.13), the
            changes published on the repository declared by the package
            (absent notes are said absent, nothing inferred), and the
            recalibration cases. The plan is written with a hash; the summary
            is the confirmation request.
  apply     re-checks the engine on disk against the plan (nothing written
            otherwise), then `tooling.install` (verified rollback point first;
            refusal before any change if it cannot be saved), then the
            identity of the engine obtained against the archive verified in
            the plan (registry integrity, artifact hash, licence text) and
            `tooling.verify`, then the recalibration when the plan includes
            it. The account distinguishes: engine installed, integrity
            verified, calibrations CURRENT / STALE, capabilities re-exercised,
            divergences; a successful npm run is never a proof of
            compatibility. No automatic rollback: the verified point is named
            with its command.

A recalibration-only plan (same engine, e.g. after a rollback) follows the
same plan / confirmation / account.
"""
import base64
import hashlib
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path

from . import config, core, i18n, recalibration, tooling, update
from .update_guide import confirm_block, notes_lines, summary
from .version import compare as _compare, is_prerelease as _is_prerelease

PLANS_REL = core.RUNTIME_REL / "pinets-guide" / "plans"
PACKAGE_PREFIX = "package/"
ENTRY = "./dist/pinets.min.es.js"           # the module imported by the runner (node import condition)
REGISTRY_TARBALL = "https://registry.npmjs.org/pinets/-/pinets-%s.tgz"
GITHUB_REPO_RE = re.compile(r"^(?:git\+)?https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
MAX_TARBALL = 64 * 1024 * 1024


def _lang(root, lang=None):
    return i18n.normalize_language(lang or config.language(root))


def _pe(root):
    return Path(root) / tooling.PINE_EXEC_REL


def _calibration_sha(root):
    p = _pe(root) / "calibration" / "capabilities.json"
    return core.sha256_file(p) if p.is_file() else None


def _current(root):
    ident = tooling.engine_identity(root)
    return {"pinned": ident["pinned_version"], "locked": ident["locked_version"],
            "locked_integrity": ident["locked_integrity"], "installed": ident["installed_version"],
            "artifact_sha256": ident["installed_artifact"]["sha256"], "calibration_sha256": _calibration_sha(root)}


def _recorded_license(root):
    prov = tooling.engine_identity(root)["provenance"] or {}
    lic = prov.get("license") if isinstance(prov.get("license"), dict) else {}
    lic_file = _pe(root) / "PINETS_LICENSE"
    return {"spdx": lic.get("installed_metadata_license") or lic.get("license_basis"),
            "text_sha256": core.sha256_file(lic_file) if lic_file.is_file() else None}


# ---- stage 1: state ------------------------------------------------------------

def state(root, lang=None):
    root = Path(root)
    lang = _lang(root, lang)
    st = tooling.status(root)
    p, cal = st["pinets"], st["calibration"]
    ident = tooling.engine_identity(root)
    caps = ident["capabilities"]
    lines = [i18n.t("ptg.installed.yes", lang, v=p["installed"]) if p["installed"] else i18n.t("ptg.installed.no", lang)]
    art = p["artifact_check"]
    lines.append(i18n.t("ptg.integrity.match", lang) if art == "match" else
                 i18n.t("ptg.integrity.differs", lang) if art == "differs" else
                 i18n.t("ptg.integrity.other", lang, state=art))
    word = str(cal["freshness"]).split(" ")[0]          # CURRENT / STALE / unknown; details stay in `result`
    lines.append(i18n.t("ptg.calib.freshness", lang, current=cal["current"], total=cal["capabilities"],
                        freshness=word if word in ("CURRENT", "STALE") else i18n.t("guide.unknown", lang)))
    if word != "CURRENT":
        lines.append(i18n.t("ptg.calib.not_effective", lang))
    lines.append(i18n.t("ptg.calib.gating", lang, n=cal["gating"]))
    calib, _ = core.read_json(_pe(root) / "calibration" / "capabilities.json")
    div = sorted(k for k, v in ((calib or {}).get("capabilities") or {}).items()
                 if isinstance(v, dict) and v.get("known_divergences")) if isinstance(calib, dict) else []
    if div:
        lines.append(i18n.t("ptg.calib.divergences", lang, caps=", ".join(div)))
    uc = st["update_check"]
    lines.append(i18n.t("ptg.search.none", lang) if not uc.get("checked_at") else
                 i18n.t("ptg.search.dated", lang, at=uc["checked_at"], note_result=_result_text(lang, uc)))
    nxt = []
    if uc.get("result") == "update-available":
        nxt.append(i18n.t("ptg.next.prepare", lang, latest=uc["latest"]))
    stale = [k for k, v in caps.items() if v.get("calibration_status") != "CURRENT"]
    if p["installed"] and art in ("match", "not-recorded") and (stale or not str(cal["freshness"]).startswith("CURRENT")):
        nxt.append(i18n.t("ptg.next.recalibrate", lang))
    return {"stage": "state", "component": "pinets", "result": st,
            "summary": summary(lang, i18n.t("ptg.headline.status", lang, installed=p["installed"] or "—",
                                            pinned=p["pinned"] or "—"),
                               state=lines, limits=[i18n.t("ptg.tv", lang)], next=nxt)}


def _result_text(lang, rec):
    res = rec.get("result") or "not-searched"
    key = "ptg.result." + res if i18n.has_key("ptg.result." + res) else "ptg.result.error"
    return i18n.t(key, lang, latest=rec.get("latest"), pinned=rec.get("pinned_now") or rec.get("pinned"),
                  error=rec.get("error") or res)


# ---- stage 2: search -----------------------------------------------------------

def search(root, lang=None, runner=None):
    root = Path(root)
    lang = _lang(root, lang)
    rec = tooling.check_update(root, runner=runner)
    result = [_result_text(lang, rec), i18n.t("pwsg.search.nothing_changed", lang)]
    nxt = []
    if rec.get("result") == "update-available":
        nxt.append(i18n.t("ptg.next.prepare", lang, latest=rec["latest"]))
    elif rec.get("result") == "error":
        nxt.append(i18n.t("pwsg.next.retry", lang))
    return {"stage": "search", "component": "pinets", "result": rec,
            "summary": summary(lang, i18n.t("ptg.search.headline", lang), result=result, next=nxt)}


# ---- stage 3: prepare ------------------------------------------------------------

def _sri_sha512(path):
    h = hashlib.sha512()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha512-" + base64.b64encode(h.digest()).decode("ascii")


def read_tarball(path):
    """Read an npm archive WITHOUT extracting it: every member must be a
    regular file or folder under `package/`, with no absolute path, `..`,
    link or device. Returns (files {relative name: bytes} for the members
    needed, artifact sha256, problems)."""
    wanted = {"package.json", "LICENSE", ENTRY[2:]}
    files, problems, artifact_sha = {}, [], None
    try:
        with tarfile.open(str(path), "r:gz") as tf:
            total = 0
            for m in tf.getmembers():
                name = m.name
                if name.startswith("/") or "\\" in name or ".." in name.split("/") or not name.startswith(PACKAGE_PREFIX):
                    problems.append("unsafe archive entry: %r" % name[:80])
                    continue
                if not (m.isreg() or m.isdir()):
                    problems.append("link or special file refused: %r" % name[:80])
                    continue
                total += m.size
                if total > MAX_TARBALL:
                    problems.append("archive exceeds the size cap")
                    break
                rel = name[len(PACKAGE_PREFIX):]
                if m.isreg() and rel in wanted:
                    data = tf.extractfile(m).read()
                    files[rel] = data
                    if rel == ENTRY[2:]:
                        artifact_sha = hashlib.sha256(data).hexdigest()
    except (tarfile.TarError, OSError, EOFError) as exc:
        return {}, None, ["archive unreadable: %s" % exc]
    for rel in sorted(wanted - set(files)):
        problems.append("the archive has no %s" % rel)
    return files, artifact_sha, problems


def _license_diff(recorded_path, new_bytes, limit=6000):
    """Unified diff between the recorded examined licence copy and the new text
    (shown to the holder; nothing is written)."""
    import difflib
    old = recorded_path.read_text(encoding="utf-8", errors="replace") if recorded_path.is_file() else ""
    new = new_bytes.decode("utf-8", errors="replace")
    diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        "recorded PINETS_LICENSE", "LICENSE of the new version"))
    return diff[:limit] + ("\n… (truncated)" if len(diff) > limit else "")


def _github_repo(meta):
    repo = meta.get("repository")
    url = repo.get("url") if isinstance(repo, dict) else repo
    m = GITHUB_REPO_RE.match(url or "") if isinstance(url, str) else None
    return "%s/%s" % (m.group(1), m.group(2)) if m else None


def published_changes(repo, current, target, http=None):
    """Release notes published on the repository declared by the package for
    the stable tags after `current` up to `target` — information only, each
    with its state (available / absent / unusable); an error is reported."""
    if not repo:
        return {"ok": False, "repository": None, "error": "the package declares no GitHub repository", "releases": []}
    fetch = http or update._http_get_json
    code, data, err = fetch("https://api.github.com/repos/%s/releases?per_page=50" % repo)
    if err or not isinstance(data, list):
        return {"ok": False, "repository": repo, "error": err or "unexpected response", "releases": []}
    out = []
    for rel in data:
        if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
            continue
        tag = rel.get("tag_name")
        ver = tag[1:] if isinstance(tag, str) and tag.startswith("v") else tag
        c1, c2 = _compare(ver, current), _compare(ver, target)
        if c1 is None or c2 is None or c1 <= 0 or c2 > 0:
            continue
        body = rel.get("body") if isinstance(rel.get("body"), str) else None
        out.append({"tag": tag, "version": ver, "published_at": rel.get("published_at"), "notes": (body or "")[:20000],
                    "url": rel.get("html_url")})
    out.sort(key=lambda r: [int(x) for x in re.findall(r"\d+", r["version"])[:3]])
    return {"ok": True, "repository": repo, "releases": out,
            "target_listed": any(r["version"] == target for r in out)}


def _engines_check(engines, node_version):
    """Simple, honest reading of `engines.node`: only `>=X[.Y[.Z]]` is
    evaluated; anything else is reported as not checked automatically."""
    want = engines.get("node") if isinstance(engines, dict) else None
    if not want:
        return {"declared": None, "satisfied": None, "note": "no Node requirement declared"}
    m = re.match(r"^\s*>=\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*$", str(want))
    have = re.findall(r"\d+", node_version or "")
    if not m or len(have) < 3:
        return {"declared": want, "satisfied": None, "note": "requirement not evaluated automatically"}
    need = [int(x or 0) for x in m.groups()]
    return {"declared": want, "satisfied": [int(x) for x in have[:3]] >= need, "note": None}


def _plan_hash(plan):
    return core.sha256_bytes(core.canonical_json({k: v for k, v in plan.items()
                                                  if k not in ("plan_hash", "plan_file", "summary")}).encode("utf-8"))


def _write_plan(root, plan, plan_file=None):
    if plan_file:
        path = Path(plan_file)
        if os.path.lexists(str(path)):
            return None, "plan file %s already exists: choose a new file name (nothing was overwritten)" % path
    else:
        if not core.runtime_tree_is_real(root, PLANS_REL.parts):
            return None, "plan folder %s is a symlink or escapes the installation" % PLANS_REL
        (Path(root) / PLANS_REL).mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=tooling._now().replace(":", "") + "-", suffix=".json",
                                    dir=str(Path(root) / PLANS_REL))
        os.close(fd)
        path = Path(name)
    core.atomic_write_json(path, plan)
    return str(path), None


def prepare(root, target=None, lang=None, recalibrate=True, runner=None, http=None, dest=None, plan_file=None,
            recalibrate_only=False, accept_license_text=None):
    """Prepare and verify one exact version (or a recalibration of the current
    engine) and write the hash-bound plan. Installs nothing.

    `accept_license_text`: the SHA-256 of a changed LICENSE text that the
    holder has examined and explicitly decided to accept for THIS version —
    passed only on such an explicit decision, never from a general
    confirmation; it must equal the text found in the archive, and the decision
    is recorded in the plan (version, identifier, text hash). A different
    licence identifier is never accepted this way."""
    root = Path(root)
    lang = _lang(root, lang)
    run = runner or tooling._run
    cur = _current(root)
    out = {"stage": "prepare", "component": "pinets", "applicable": False, "plan_file": None, "plan_hash": None,
           "decision_required": None, "problems": [], "plan": None}

    def refuse(why, decision=False):
        out["problems"].append(why)
        if decision:
            out["decision_required"] = why
        key = "ptg.plan.decision" if decision else "ptg.plan.refused"
        out["summary"] = summary(lang, i18n.t(key, lang, why=why))
        return out

    contract = recalibration.contract(root)
    cases = sorted(contract["cases"])
    recal = {"included": bool(recalibrate or recalibrate_only), "cases": cases,
             "contract_ok": contract["ok"], "problems": contract["problems"], "uncovered": contract["uncovered"]}
    if recal["included"]:
        bind = recalibration.binding(root)
        if not bind["ok"]:
            return refuse("the recalibration contract or its artifacts are not valid (%s): the recalibration cannot "
                          "be planned — fix them, or plan the installation without recalibration"
                          % "; ".join(bind["problems"][:3] or ["no comparable case"]))
        recal["binding"] = bind
    if recalibrate_only:
        if not cur["installed"] or cur["installed"] != cur["pinned"]:
            return refuse("the engine is not installed as pinned: recalibration impossible (repair it first)")
        if not cases:
            return refuse("no comparable calibration case: %s" % "; ".join(contract["problems"][:3]))
        findings = tooling.verify(root)
        blocking = [f["check"] for f in findings if f["status"] == "BLOCKING"]
        if blocking:
            return refuse("integrity checks BLOCKING (%s): recalibrating this engine is refused" % ", ".join(blocking))
        plan = {"format": 1, "kind": "recalibrate", "created_at": tooling._now(), "current": cur, "target": None,
                "recalibration": recal}
        plan["plan_hash"] = _plan_hash(plan)
        path, err = _write_plan(root, plan, plan_file)
        if err:
            return refuse(err)
        out.update(plan=plan, plan_file=path, plan_hash=plan["plan_hash"], applicable=True)
        out["summary"] = summary(
            lang, i18n.t("ptg.plan.headline.recal", lang, cur=cur["pinned"]),
            change=[i18n.t("ptg.plan.change.recal", lang, cases=", ".join(cases))],
            kept=[i18n.t("ptg.plan.kept", lang)],
            checks=[i18n.t("ptg.check.rebind", lang), i18n.t("ptg.check.recal", lang)],
            limits=[i18n.t("ptg.limit.cases", lang), i18n.t("ptg.tv", lang), i18n.t("guide.permissions", lang)],
            confirm=confirm_block(lang))
        return out

    if target is None:
        uc = tooling.read_update_check(root)
        if uc.get("result") != "update-available" or not uc.get("latest"):
            return refuse("no dated search found a newer stable version — search first, or name an exact version")
        target = uc["latest"]
    if not isinstance(target, str) or not tooling.EXACT_VERSION_RE.match(target):
        return refuse("the target must be an exact version (e.g. 0.13.1)")
    cmp = _compare(target, cur["pinned"]) if cur["pinned"] else None
    if cmp is None:
        return refuse("the current pin is not an exact version: compare impossible")
    if cmp == 0:
        return refuse("the target equals the current pin: nothing to install")
    if cmp < 0:
        return refuse("the target %s is older than the pin %s: returning to a previous engine uses its verified "
                      "rollback point (pinets rollback), not an installation" % (target, cur["pinned"]))
    rc, txt, err = run(["npm", "view", "pinets@%s" % target, "version", "license", "engines", "dist", "repository",
                        "--json"], timeout=60)
    try:
        meta = json.loads(txt) if rc == 0 else None
    except ValueError:
        meta = None
    if not isinstance(meta, dict) or meta.get("version") != target:
        return refuse("registry metadata of pinets@%s unavailable or inconsistent (%s)"
                      % (target, (err or txt or "no output").strip()[:200]))
    dist = meta.get("dist") if isinstance(meta.get("dist"), dict) else {}
    integrity = dist.get("integrity")
    if not (isinstance(integrity, str) and integrity.startswith("sha512-")) or dist.get("tarball") != REGISTRY_TARBALL % target:
        return refuse("the registry gives no sha512 integrity or an unexpected archive URL for pinets@%s" % target)
    ddir = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="pinets-guide-"))
    if core.is_within(root, ddir):
        return refuse("the download folder must be outside the workspace")
    ddir.mkdir(parents=True, exist_ok=True)
    rc, txt, err = run(["npm", "pack", "pinets@%s" % target, "--pack-destination", str(ddir), "--json",
                        "--ignore-scripts"], timeout=300)
    tgz = ddir / ("pinets-%s.tgz" % target)
    if rc != 0 or not tgz.is_file() or tgz.is_symlink():
        return refuse("download of pinets@%s failed (%s)" % (target, (err or txt or "no output").strip()[:200]))
    got_integrity = _sri_sha512(tgz)
    if got_integrity != integrity:
        return refuse("the downloaded archive integrity differs from the registry value — refused")
    files, artifact_sha, problems = read_tarball(tgz)
    if problems:
        return refuse("archive refused: %s" % "; ".join(problems[:4]))
    try:
        pkg = json.loads(files["package.json"].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return refuse("the archive's package.json is unreadable")
    if pkg.get("name") != "pinets" or pkg.get("version") != target:
        return refuse("the archive's package.json says %r %r, expected pinets %s"
                      % (pkg.get("name"), pkg.get("version"), target))
    exports = pkg.get("exports") if isinstance(pkg.get("exports"), dict) else {}
    node_import = (((exports.get(".") or {}).get("node") or {}).get("import")) if isinstance(exports.get("."), dict) else None
    entry_ok = node_import == ENTRY or (not exports and pkg.get("module") == ENTRY[2:])
    if not entry_ok:
        return refuse("the package no longer exposes %s to Node (found %r): the adapter cannot load it as is — "
                      "an adapter change would be a separate decision" % (ENTRY, node_import))
    recorded = _recorded_license(root)
    spdx = pkg.get("license") if isinstance(pkg.get("license"), str) else None
    lic_sha = hashlib.sha256(files["LICENSE"]).hexdigest()
    if not spdx or not recorded["spdx"] or spdx != recorded["spdx"]:
        return refuse("licence of pinets@%s is %r, the recorded assessment covers %r: the licence analysis must be "
                      "redone by you before any installation (spec 24.4.13)" % (target, spdx, recorded["spdx"]),
                      decision=True)
    license_review = {"spdx": spdx, "recorded_spdx": recorded["spdx"], "text_sha256": lic_sha,
                      "recorded_text_sha256": recorded["text_sha256"], "text_identical": lic_sha == recorded["text_sha256"],
                      "decision": None,
                      "note": "documentary reading of the package metadata and LICENSE text — not a legal guarantee"}
    if not license_review["text_identical"]:
        out["license_text_diff"] = _license_diff(_pe(root) / "PINETS_LICENSE", files["LICENSE"])
        out["license_text_sha256"] = lic_sha
        if accept_license_text is None:
            why = ("the LICENSE text of pinets@%s (sha256 %s) differs from the recorded examined copy (%s): examine the "
                   "difference and decide explicitly before any plan; the recorded copy is not changed"
                   % (target, lic_sha, recorded["text_sha256"] or "no recorded copy"))
            return refuse(why, decision=True)
        if str(accept_license_text).strip().lower() != lic_sha:
            return refuse("the licence decision given names the text %s, the archive of pinets@%s carries %s: the "
                          "decision does not cover this text" % (accept_license_text, target, lic_sha), decision=True)
        license_review["decision"] = {"version": target, "spdx": spdx, "text_sha256": lic_sha,
                                      "recorded_text_sha256": recorded["text_sha256"], "decided_at": tooling._now(),
                                      "basis": "explicit decision of the holder after examining the difference, "
                                               "passed to `pinets guide --stage prepare --accept-license-text`"}
    st = tooling.status(root)
    prereq = {"node": st["node"], "npm": st["npm"],
              "engines": _engines_check(pkg.get("engines"), st["node"]),
              "dependencies": pkg.get("dependencies") if isinstance(pkg.get("dependencies"), dict) else {}}
    if prereq["engines"]["satisfied"] is False:
        return refuse("Node %s does not satisfy the requirement %s declared by pinets@%s"
                      % (st["node"], prereq["engines"]["declared"], target))
    changes = published_changes(_github_repo(meta), cur["pinned"], target, http=http)
    plan = {"format": 1, "kind": "install", "created_at": tooling._now(), "current": cur,
            "target": {"version": target, "prerelease": _is_prerelease(target), "registry_integrity": integrity,
                       "tarball": dist.get("tarball"), "archive": str(tgz), "artifact_path": tooling.ARTIFACT_REL,
                       "artifact_sha256": artifact_sha, "entry": ENTRY},
            "license": license_review, "prerequisites": prereq, "changes": changes, "recalibration": recal}
    plan["plan_hash"] = _plan_hash(plan)
    path, err = _write_plan(root, plan, plan_file)
    if err:
        return refuse(err)
    out.update(plan=plan, plan_file=path, plan_hash=plan["plan_hash"], applicable=True)
    out["summary"] = install_summary(lang, plan)
    return out


def install_summary(lang, plan):
    cur, tgt = plan["current"], plan["target"]
    change = [i18n.t("ptg.plan.component", lang),
              i18n.t("ptg.plan.origin", lang, v=tgt["version"], integrity=tgt["registry_integrity"][:23] + "…"),
              i18n.t("ptg.plan.change.pin", lang, cur=cur["pinned"], target=tgt["version"]),
              i18n.t("ptg.plan.change.provenance", lang), i18n.t("ptg.plan.change.stale", lang)]
    rec = plan["recalibration"]
    if rec["included"] and rec["cases"]:
        change.append(i18n.t("ptg.plan.change.recal", lang, cases=", ".join(rec["cases"])))
    pr = plan["prerequisites"]
    eng = pr["engines"]
    change.append(i18n.t("ptg.plan.prereq.node", lang, node=pr["node"], npm=pr["npm"],
                         engines=eng["declared"] or i18n.t("guide.none", lang)))
    change.append(i18n.t("ptg.plan.adapter", lang, entry=tgt["entry"]))
    lic = plan["license"]
    change.append(i18n.t("ptg.plan.license.same" if lic["text_identical"] else "ptg.plan.license.text", lang,
                         spdx=lic["spdx"]))
    if lic.get("decision"):
        change.append(i18n.t("ptg.plan.license.decided", lang, sha=lic["decision"]["text_sha256"][:16] + "…",
                             v=lic["decision"]["version"]))
    notes = []
    ch = plan["changes"]
    if not ch.get("ok"):
        notes.append(i18n.t("ptg.plan.changes.unavailable", lang, why=ch.get("error")))
    else:
        notes.append(i18n.t("ptg.plan.changes.header", lang, repo=ch["repository"]))
        for rel in ch["releases"]:
            state, lines = notes_lines(lang, rel.get("notes"))
            notes.append(i18n.t("ptg.plan.changes.version", lang, tag=rel["tag"], state=lines[0]))
        if not ch["releases"]:
            notes.append(i18n.t("ptg.plan.changes.unavailable", lang, why="no stable release listed in this range"))
    checks = [i18n.t("ptg.check.rebind", lang), i18n.t("ptg.check.point", lang), i18n.t("ptg.check.identity", lang),
              i18n.t("ptg.check.verify", lang)]
    if rec["included"]:
        checks.append(i18n.t("ptg.check.recal", lang))
    limits = [i18n.t("ptg.limit.version", lang), i18n.t("ptg.limit.cases", lang), i18n.t("ptg.limit.license", lang),
              i18n.t("guide.no_auto_rollback", lang), i18n.t("ptg.tv", lang), i18n.t("guide.permissions", lang)]
    return summary(lang, i18n.t("ptg.plan.headline", lang, cur=cur["pinned"], target=tgt["version"]),
                   change=change, kept=[i18n.t("ptg.plan.kept", lang)], checks=checks, limits=limits, notes=notes,
                   confirm=confirm_block(lang))


# ---- stage 4: apply --------------------------------------------------------------

def apply(root, plan_file, yes=False, lang=None, npm_runner=None, node_runner=None):
    root = Path(root)
    lang = _lang(root, lang)
    report = {"stage": "apply", "component": "pinets", "ok": False, "status": "refused-before-mutation",
              "plan_file": str(plan_file), "kind": None, "install": None, "identity": None, "verify": None,
              "recalibration": None, "error": None, "rollback_point": None}

    def refused(why):
        report["error"] = why
        report["summary"] = report_summary(lang, report)
        return report

    plan, err = core.read_json(plan_file)
    if err or not isinstance(plan, dict) or plan.get("plan_hash") != _plan_hash(plan if isinstance(plan, dict) else {}):
        return refused("plan file unreadable, or modified since it was written (hash mismatch)")
    report["kind"] = plan.get("kind")
    report["plan"] = {"current": plan.get("current"), "target": plan.get("target"),
                      "license_text_identical": (plan.get("license") or {}).get("text_identical")}
    if not yes:
        return refused("explicit confirmation required after reviewing the plan")
    lic = plan.get("license") or {}
    if plan.get("kind") == "install" and not lic.get("text_identical") and not (
            isinstance(lic.get("decision"), dict) and lic["decision"].get("text_sha256") == lic.get("text_sha256")
            and lic["decision"].get("version") == (plan.get("target") or {}).get("version")):
        return refused("the plan carries a changed licence text without the recorded decision covering it")
    problem = _plan_still_valid(root, plan)
    if problem:
        return refused(problem)
    if plan.get("kind") == "recalibrate":
        return _recalibrate_stage(root, plan, report, lang, node_runner, installed=False)
    tgt = plan.get("target") or {}
    ins = tooling.install(root, tgt["version"], yes=True, npm_runner=npm_runner,
                          precheck=lambda: _plan_still_valid(root, plan))   # same checks, under the shared lock
    report["install"] = ins
    report["rollback_point"] = ins.get("rollback_point")
    if not ins.get("ok"):
        if not ins.get("rollback_point"):          # stopped before the first npm command: nothing changed
            return refused(ins.get("error") or "installation refused")
        report["status"] = "install-failed"
        report["error"] = ins.get("error")
        report["state_after"] = _current(root)
        report["summary"] = report_summary(lang, report)
        return report
    now = tooling.engine_identity(root)
    identity = {"registry_integrity": now["locked_integrity"] == tgt["registry_integrity"],
                "artifact_sha256": now["installed_artifact"]["sha256"] == tgt["artifact_sha256"],
                "license_text": None}
    lic = _pe(root) / "node_modules" / "pinets" / "LICENSE"
    identity["license_text"] = lic.is_file() and core.sha256_file(lic) == (plan.get("license") or {}).get("text_sha256")
    report["identity"] = identity
    findings = tooling.verify(root)
    blocking = [f["check"] for f in findings if f["status"] == "BLOCKING"]
    report["verify"] = {"blocking": blocking, "findings": findings}
    if blocking or not all(identity.values()):
        report["status"] = "verification-failed"
        report["error"] = ("engine obtained does not match the plan (%s) or integrity checks BLOCKING (%s)"
                           % (", ".join(k for k, v in identity.items() if not v) or "identity ok",
                              ", ".join(blocking) or "none"))
        report["summary"] = report_summary(lang, report)
        return report
    if not (plan.get("recalibration") or {}).get("included"):
        report["status"], report["ok"] = "installed-verified", True
        report["summary"] = report_summary(lang, report)
        return report
    report["verified_engine"] = _engine_key(root)
    return _recalibrate_stage(root, plan, report, lang, node_runner, installed=True)


def _engine_key(root):
    ident = tooling.engine_identity(root)
    return {"pinned": ident["pinned_version"], "locked_integrity": ident["locked_integrity"],
            "installed": ident["installed_version"], "artifact_sha256": ident["installed_artifact"]["sha256"]}


def _plan_still_valid(root, plan):
    """Why the approved plan no longer holds (None when it does): the engine and
    its calibration as recorded in the plan, the verified archive (install), and
    — when the recalibration is planned — the comparison contract and every
    artifact it names. Called before, and again under the shared lock just
    before, the first change."""
    if _current(root) != plan.get("current"):
        return "the engine or its calibration changed since the plan was prepared — prepare it again"
    if plan.get("kind") == "install":
        tgt = plan.get("target") or {}
        archive = Path(tgt.get("archive") or "")
        if not archive.is_file() or _sri_sha512(archive) != tgt.get("registry_integrity"):
            return "the archive verified in the plan is missing or changed — prepare it again"
    rec = plan.get("recalibration") or {}
    if rec.get("included"):
        bound = rec.get("binding")
        if not isinstance(bound, dict):
            return "the plan includes a recalibration but carries no binding of its contract — prepare it again"
        now = recalibration.binding(root)
        if not now["ok"] or any(now.get(k) != bound.get(k) for k in ("contract_sha256", "cases", "artifacts")):
            return ("the recalibration contract (%s) or one of its sources, datasets or references changed, "
                    "disappeared or became invalid since the plan was prepared — prepare it again"
                    % bound.get("contract_path"))
    return None


def _recalibrate_stage(root, plan, report, lang, node_runner, installed):
    bound = (plan.get("recalibration") or {}).get("binding")
    try:
        with tooling._lock(root):
            # re-checked UNDER the lock: the engine recalibrated is the one verified (or planned)
            if installed:
                problem = None if _engine_key(root) == report.get("verified_engine") else \
                    "the engine changed between its verification and the recalibration"
            else:
                problem = _plan_still_valid(root, plan)
            if problem:
                if not installed:
                    report["error"] = problem
                    report["summary"] = report_summary(lang, report)
                    return report
                rec = {"status": "incomplete", "problems": [problem + ": recalibration not run"],
                       "cases": {}, "current": [], "stale": [], "calibration_written": False}
            else:
                rec = recalibration.run(root, node_runner=node_runner, expected_binding=bound)
    except TimeoutError:
        if not installed:
            return _refused_lock(report, lang)
        rec = {"status": "incomplete", "problems": ["another PWS mutation holds the lock: recalibration not run"],
               "cases": {}, "current": [], "stale": [], "calibration_written": False}
    except Exception as exc:  # noqa: BLE001 — an account is always returned once something may have changed
        rec = {"status": "incomplete", "problems": ["internal error during the recalibration: %s: %s"
                                                    % (type(exc).__name__, str(exc)[:300])],
               "cases": {}, "current": [], "stale": [], "calibration_written": False}
    report["recalibration"] = rec
    prefix = "" if installed else "recal-only-"
    if rec.get("status") == "recalibrated" and rec.get("calibration_written") and rec.get("calibration_verified"):
        report["status"], report["ok"] = ("completed" if installed else "recalibrated"), True
    elif rec["status"] == "divergent":
        report["status"] = "recalibration-divergent" if installed else prefix + "divergent"
    else:
        report["status"] = "recalibration-incomplete" if installed else prefix + "incomplete"
    report["summary"] = report_summary(lang, report)
    return report


def _refused_lock(report, lang):
    report["error"] = "another PWS mutation holds the lock — nothing changed"
    report["summary"] = report_summary(lang, report)
    return report


def report_summary(lang, r):
    status = r.get("status")
    plan = r.get("plan") or {}
    cur = (plan.get("current") or {}).get("pinned") or "?"
    tgt = (plan.get("target") or {}).get("version") or "?"
    recal_only = r.get("kind") == "recalibrate"
    skey = "ptg.status." + status if i18n.has_key("ptg.status." + str(status)) else "ptg.status.incomplete"
    headline = (i18n.t("ptg.report.headline.recal", lang, cur=cur, status=i18n.t(skey, lang)) if recal_only
                else i18n.t("ptg.report.headline", lang, cur=cur, target=tgt, status=i18n.t(skey, lang)))
    changed, checks, result, recovery, nxt = [], [], [], [], []
    if status == "refused-before-mutation":
        result.append(i18n.t("pwsg.done.reason", lang, why=r.get("error") or "?"))
        nxt.append(i18n.t("pwsg.next.replan", lang))
        return summary(lang, headline, result=result, next=nxt)
    ins = r.get("install") or {}
    state = ins.get("state") or r.get("state_after") or {}
    if not recal_only:
        changed.append(i18n.t("ptg.done.engine", lang, pinned=state.get("pinned"), installed=state.get("installed"),
                              artifact=(state.get("installed_artifact_sha256") or state.get("artifact_sha256") or "—")[:16]))
    if r.get("rollback_point"):
        checks.append(i18n.t("ptg.done.point", lang, point=r["rollback_point"]))
        recovery.append(i18n.t("ptg.recovery.point", lang, point=r["rollback_point"]))
    if r.get("identity") is not None:
        bad = [k for k, v in r["identity"].items() if not v]
        checks.append(i18n.t("ptg.done.identity", lang, verdict=i18n.t("guide.yes", lang) if not bad
                             else "≠ " + ", ".join(bad)))
    if r.get("verify") is not None:
        blk = r["verify"]["blocking"]
        checks.append(i18n.t("ptg.done.verify", lang, verdict=("BLOCKING: " + ", ".join(blk)) if blk else "OK"))
    rec = r.get("recalibration")
    if rec is not None:
        none = i18n.t("guide.none", lang)
        changed.append(i18n.t("ptg.done.calib", lang, current=", ".join(rec.get("current") or []) or none,
                              stale=", ".join(rec.get("stale") or []) or none))
        for case, cr in (rec.get("cases") or {}).items():
            if cr.get("verdict") == "divergent":
                bad = [n for n, s in (cr.get("series") or {}).items() if not s.get("ok")]
                result.append(i18n.t("ptg.done.divergent", lang, case=case,
                                     series=", ".join(bad) or (cr.get("problem") or "?")))
            elif cr.get("verdict") == "incomplete":
                result.append(i18n.t("ptg.done.incomplete_case", lang, case=case, why=cr.get("problem") or "?"))
        for p in rec.get("problems") or []:
            result.append(i18n.t("pwsg.done.reason", lang, why=p))
        if rec.get("results_dir"):
            checks.append(i18n.t("ptg.done.results", lang, path=rec["results_dir"]))
        if rec.get("calibration_backup"):
            recovery.append(i18n.t("ptg.recovery.calib", lang, path=rec["calibration_backup"]))
        changed.append(i18n.t("ptg.done.gating", lang))
        if rec.get("status") == "divergent":
            nxt.append(i18n.t("ptg.next.decide", lang))
    elif status == "installed-verified":
        changed.append(i18n.t("ptg.plan.change.stale", lang))
        nxt.append(i18n.t("ptg.next.recal_later", lang))
    if not recal_only and r.get("identity") is not None and plan.get("license_text_identical") is False:
        result.append(i18n.t("ptg.done.license_text", lang))
    if r.get("error") and status not in ("completed", "installed-verified", "recalibrated"):
        result.append(i18n.t("pwsg.done.reason", lang, why=r["error"]))
    if status in ("completed", "installed-verified", "recalibrated", "recalibration-divergent",
                  "recalibration-incomplete", "recal-only-divergent", "recal-only-incomplete"):
        nxt.append(i18n.t("ptg.next.tests", lang))
    return summary(lang, headline, changed=changed, checks_done=checks, result=result, recovery=recovery, next=nxt)
