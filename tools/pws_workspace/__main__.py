# SPDX-License-Identifier: Apache-2.0
"""CLI dispatcher: python3 -m tools.pws_workspace <subcommand> [options].

Output is JSON for every subcommand except doctor's human table and the
`banner` text (--json for their machine form; the /pws menu reads `menu
--json`, which carries the FIXED "PWS" banner of the menu as a data
field, and `session-status --json`; the adaptive PINE-WORKSPACE variants
belong to the `banner` subcommand only). No JSON output, hook output or
tool-facing data is ever prefixed with a banner. Mutating subcommands
(each the sole owner of its target):
tv-mode <mode> and config/init (pws.config.json), migrate --apply,
standard-index, import-register (ephemeral), pinets install/rollback/verify
--record, github destination-*/export-plan/fetch/publish, maintenance
cleanup --execute / archives-*, license write / set-fields / confirm, build-distribution.
"""
import argparse
import json
import sys
from pathlib import Path

from . import (banner, config, core, doctor, guard, i18n, licensing, maintenance,
               menu, migration, scan, session, standard, tooling, tv_mode,
               update, validation, version)


def _p(obj, as_json=True):
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def _confine(root, candidate):
    """Resolve a CLI path argument inside root; None when it escapes."""
    p = Path(candidate)
    if not p.is_absolute():
        p = root / p
    return p if core.is_within(root, p) else None


def _main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m tools.pws_workspace")
    parser.add_argument("--root", default=None, help="workspace root override (tests only)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="workspace version and schema levels")
    sub.add_parser("session-status", help="structured mechanical state (menu/diagnostics)") \
        .add_argument("--json", action="store_true")
    sub.add_parser("menu", help="deterministic /pws menu tree (localized; `banner` field: "
                                "the fixed PWS banner of the menu, as data)") \
        .add_argument("--json", action="store_true")
    sub.add_parser("banner", help="adaptive PINE-WORKSPACE banner fitted to the terminal attached "
                                  "to stdout (plain text; --json: structured form) — distinct "
                                  "from the fixed banner of the /pws menu") \
        .add_argument("--json", action="store_true")
    sub.add_parser("scan", help="scan scripts/** products and orphans") \
        .add_argument("--json", action="store_true")
    sub.add_parser("doctor", help="deterministic health checks (read-only)") \
        .add_argument("--json", action="store_true")
    sub.add_parser("standard-index", help="regenerate standards/INDEX.md from real headings")
    sub.add_parser("standard-status", help="freshness of INDEX and TRACEABILITY") \
        .add_argument("--json", action="store_true")
    g = sub.add_parser("guard", help="mechanical checks on a product root or source")
    g.add_argument("target", help="product dir (containing SCRIPT.json) or .pine file")
    g.add_argument("--json", action="store_true")
    f = sub.add_parser("source-fingerprint", help="SHA-256 + git identity of a source")
    f.add_argument("source")
    f.add_argument("--json", action="store_true")
    v = sub.add_parser("validation-status", help="derived validation view of a product")
    v.add_argument("product", help="product dir under scripts/")
    v.add_argument("--json", action="store_true")
    t = sub.add_parser("tv-mode", help="read (no arg) or set the persisted TV mode")
    t.add_argument("mode", nargs="?", choices=list(core.MODES))
    im = sub.add_parser("import-register",
                        help="declare a .pine imported during the session, "
                             "before any modification (pine-onboard)")
    im.add_argument("source", help=".pine file under scripts/")
    im.add_argument("--json", action="store_true")
    sub.add_parser("hook-session-start", help="SessionStart hook entry (stdin JSON)")
    sub.add_parser("hook-stop", help="Stop hook entry (stdin JSON)")

    ini = sub.add_parser("init", help="first PWS configuration (pws.config.json)")
    ini.add_argument("--language", default="en", help="en (default) or fr")
    ini.add_argument("--copyright-holder", default=None)
    ini.add_argument("--alias", action="append", default=[],
                     help="additional © mark accepted in existing headers (repeatable)")
    ini.add_argument("--default-profile", default="FREE", choices=("FREE", "PRIVATE", "COMMERCIAL"))
    ini.add_argument("--force", action="store_true", help="reset an existing configuration")

    c = sub.add_parser("config", help="show or set the PWS configuration")
    c_sub = c.add_subparsers(dest="config_cmd", required=True)
    c_sub.add_parser("show")
    cs = c_sub.add_parser("set")
    cs.add_argument("key", help="language | tv_validation_mode | identity.copyright_holder | "
                               "identity.header_aliases | identity.default_profile | "
                               "maintenance.startup_cleanup")
    cs.add_argument("value", nargs="+")

    m = sub.add_parser("migrate", help="plan / apply / rollback workspace migrations")
    mg = m.add_mutually_exclusive_group(required=True)
    mg.add_argument("--plan", action="store_true")
    mg.add_argument("--apply", action="store_true")
    mg.add_argument("--rollback", metavar="STAMP")
    mg.add_argument("--list-backups", action="store_true")

    sub.add_parser("tooling-status", help="read-only view of the integrated tools (PineTS)")
    pn = sub.add_parser("pinets", help="PineTS lifecycle")
    pn.add_argument("action", choices=("status", "verify", "check-update", "install",
                                       "rollback", "recalibrate-plan"))
    pn.add_argument("version", nargs="?", help="exact version for install/rollback")
    pn.add_argument("--yes", action="store_true")
    pn.add_argument("--record", action="store_true", help="verify: record the artifact hash")

    gh = sub.add_parser("github", help="GitHub export workflow")
    gh.add_argument("action", choices=("status", "destinations", "destination-add",
                                       "destination-remove", "export-plan", "fetch",
                                       "export-diff", "publish"))
    gh.add_argument("--name")
    gh.add_argument("--repo", help="owner/name")
    gh.add_argument("--visibility", choices=("public", "private"))
    gh.add_argument("--path-prefix", default="")
    gh.add_argument("--branch", default="main")
    gh.add_argument("--url", help="explicit clone URL (tests / local bare repo)")
    gh.add_argument("--slug")
    gh.add_argument("--destination")
    gh.add_argument("--message")
    gh.add_argument("--yes", action="store_true")

    mt = sub.add_parser("maintenance", help="cleanup and archive import")
    mt.add_argument("action", choices=("cleanup", "archives-plan", "archives-import",
                                       "archives-verify", "archives-remove-source"))
    mt.add_argument("--execute", action="store_true", help="cleanup: actually remove")
    mt.add_argument("--yes", action="store_true",
                    help="archives-remove-source: the holder explicitly authorizes deleting the verified source folder")
    mt.add_argument("--source", help="archives: external folder")
    mt.add_argument("--target", default="docs/maintenance/archives")
    mt.add_argument("--plan-file", help="archives: plan JSON (written by archives-plan)")

    lc = sub.add_parser("license", help="licence templates, rendering, status, confirmations, guided path")
    lc.add_argument("action", choices=("status", "overview", "render", "preview", "write", "set-fields",
                                       "fields-skeleton", "templates", "confirm", "detect"))
    lc.add_argument("--slug")
    lc.add_argument("--kind", choices=tuple(licensing.KINDS))
    lc.add_argument("--dest", default=None, help="write: path inside the product root")
    lc.add_argument("--state", choices=("unpublished", "published"), help="confirm: publication state")
    lc.add_argument("--privacy", choices=("public", "private"), help="confirm: publication privacy")
    lc.add_argument("--mode", choices=("open", "protected", "invite-only"), help="confirm: script mode")
    lc.add_argument("--created-year", type=int, default=None, help="confirm: creation year")
    lc.add_argument("--terms-ref", default=None, help="confirm: attached terms document (path inside the product)")
    lc.add_argument("--terms-url", default=None, help="confirm: declared https URL of the terms")
    lc.add_argument("--license-id", default=None,
                    help="confirm: exact SPDX identifier of the existing licence of an IMPORTED script, confirmed "
                         "by the holder (closed list; deprecated or ambiguous identifiers are refused)")
    lc.add_argument("--license-document", action="append", default=[], metavar="PATH",
                    help="confirm: an original legal document of an IMPORTED script (LICENSE, COPYING, NOTICE…, at "
                         "the product root, directly under release/ or LICENSES/), declared by the holder; repeatable "
                         "— the declaration lists every document and replaces the previous one")
    lc.add_argument("--no-license-documents", action="store_true",
                    help="confirm: the holder records that no separate legal document accompanies the imported script")
    lc.add_argument("--source", default=None,
                    help="detect: a .pine file under scripts/ — licence PROPOSAL read in its header (read-only)")
    lc.add_argument("--field", action="append", default=[], metavar="NAME=value",
                    help="set-fields: a value supplied by the holder (repeatable)")
    lc.add_argument("--clear", action="append", default=[], metavar="NAME",
                    help="set-fields: remove a recorded value; confirm: return a manifest value to unknown "
                         "(state, privacy, mode, created_year, terms_ref, terms_url, license_id, license_documents) "
                         "(repeatable)")
    lc.add_argument("--dry-run", action="store_true", help="set-fields: show the changes, write nothing")

    bd = sub.add_parser("build-distribution", help="build the public distribution tree")
    bd.add_argument("--target", required=True)
    bd.add_argument("--force", action="store_true", help="replace a previous PWS distribution build")

    up = sub.add_parser("upgrade", help="upgrade an installed core from a distribution package")
    up.add_argument("--from", dest="package", help="distribution package folder")
    ug = up.add_mutually_exclusive_group(required=True)
    ug.add_argument("--plan", action="store_true")
    ug.add_argument("--apply", action="store_true")
    ug.add_argument("--rollback", metavar="STAMP")
    ug.add_argument("--list-backups", action="store_true")
    up.add_argument("--overwrite-local", action="store_true",
                    help="apply: replace locally modified core files (they are backed up)")
    up.add_argument("--force", action="store_true",
                    help="rollback: ignore data migrations recorded after the upgrade")

    ud = sub.add_parser("update", help="guided update of an INSTALLED core from the official releases or a "
                                       "local package (orchestrates `upgrade` then `migrate`; nothing automatic)")
    ud.add_argument("action", choices=("status", "check", "fetch", "prepare", "plan", "apply", "rollback-info"))
    ud.add_argument("--tag", help="fetch: tag of the release found by the last search")
    ud.add_argument("--package", help="prepare: local archive (.zip) or extracted package folder")
    ud.add_argument("--sha256", help="prepare: expected SHA-256 of the local archive")
    ud.add_argument("--package-dir", help="plan: verified package folder (from fetch/prepare)")
    ud.add_argument("--dest", help="fetch/prepare: folder for the download or extraction (default: temporary, outside the installation)")
    ud.add_argument("--plan-file", help="plan: where to write the plan; apply: the approved plan")
    ud.add_argument("--include-prereleases", action="store_true", help="check: also consider pre-releases")
    ud.add_argument("--yes", action="store_true", help="apply: the holder confirmed the reviewed plan")

    br = sub.add_parser("build-release", help="maintainer: build the publication artefacts of the current "
                                              "version (distribution, archive, SHA-256, RELEASE.json, notes)")
    br.add_argument("--target", required=True)
    br.add_argument("--force", action="store_true", help="replace an UNPUBLISHED build of the same version")

    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else core.workspace_root()
    as_json = getattr(args, "json", False)
    lang = config.language(root)

    if args.cmd == "version":
        _p({"workspace_version": version.WORKSPACE_VERSION,
            "config_schema": version.CONFIG_SCHEMA_VERSION,
            "manifest_schema": version.MANIFEST_SCHEMA_VERSION})
    elif args.cmd == "session-status":
        _p(session.session_status(root), as_json)
    elif args.cmd == "menu":
        tree = menu.build_menu(session.session_status(root))
        # the FIXED "PWS" banner of /pws, as a data field: the same text whether
        # this output is captured (Claude Code) or not — never width-adapted;
        # `banner.question` is the ready-to-send text of the main-menu question
        tree["banner"] = banner.menu_banner(tree["language"])
        _p(tree, as_json)
    elif args.cmd == "banner":
        info = banner.current()      # adaptive variants, measured on this terminal (not /pws)
        if as_json:
            _p(info)
        elif info["text"]:
            print(info["text"])      # omitted (nothing printed) below the name's own width
    elif args.cmd == "scan":
        _p(scan.scan_workspace(root), as_json)
    elif args.cmd == "doctor":
        results = doctor.run_doctor(root)
        if as_json:
            _p(results, True)
        else:
            worst = "OK"
            order = ["OK", "INFO", "WARNING", "BLOCKING"]
            print(i18n.t("doctor.header", lang))
            for r in results:
                print("[%-8s] %-32s %s" % (r["severity"], r["check"], r["detail"]))
                if order.index(r["severity"]) > order.index(worst):
                    worst = r["severity"]
            print("\n" + i18n.t("doctor.result", lang, worst=worst))
            print(i18n.t("doctor.legend", lang))
        if any(r["severity"] == "BLOCKING" for r in results):
            return 1
    elif args.cmd == "standard-index":
        _p(standard.generate_index(root), False)
    elif args.cmd == "standard-status":
        _p(standard.standard_status(root), as_json)
    elif args.cmd == "guard":
        target = _confine(root, args.target)
        if target is None:
            _p({"error": "target escapes the workspace — refused"})
            return 1
        identity = config.identity(root)
        if target.is_dir():
            findings = guard.guard_product(target, identity)
        else:
            findings = guard.check_source(target, None, None, identity)
        _p(findings, as_json)
        if any(x["status"] == "BLOCKING" for x in findings):
            return 1
    elif args.cmd == "source-fingerprint":
        src = _confine(root, args.source)
        if src is None:
            _p({"error": "source escapes the workspace — refused"})
            return 1
        _p(validation.source_fingerprint(root, src), as_json)
    elif args.cmd == "validation-status":
        pdir = _confine(root, args.product)
        if pdir is None:
            _p({"error": "product escapes the workspace — refused"})
            return 1
        if pdir.is_symlink():
            _p({"persisted": None, "integrity": "BROKEN", "effective": None,
                "detail": "product root is a symlink — identity not "
                          "establishable, nothing read (spec 6.1.5)",
                "findings": []}, True)
            return 1
        manifest, _ = core.read_json(pdir / "SCRIPT.json")
        source = None
        if isinstance(manifest, dict) and isinstance(manifest.get("source"), str) \
                and not Path(manifest["source"]).is_absolute():
            candidate = pdir / manifest["source"]
            source = candidate if core.is_within(pdir, candidate) else None
        _p(validation.validation_status(pdir, source), as_json)
    elif args.cmd == "tv-mode":
        if args.mode is None:
            detail = tv_mode.read_mode_detail(root)
            _p(detail, True)
            if detail["mode"] is None:
                return 1
        else:
            result = tv_mode.set_mode(root, args.mode)
            _p(result, True)
            if not result.get("ok"):
                return 1
    elif args.cmd == "import-register":
        result = session.register_import(root, args.source)
        _p(result, True)
        if result.get("refused"):
            return 1
    elif args.cmd == "hook-session-start":
        try:
            data = json.load(sys.stdin)
        except ValueError:
            data = {}
        text, _ = session.hook_session_start(root, data)
        print(text)
    elif args.cmd == "hook-stop":
        try:
            data = json.load(sys.stdin)
        except ValueError:
            data = {}
        code, out = session.hook_stop(root, data)
        if out:
            print(out)
        return code
    elif args.cmd == "init":
        r = config.init_config(root, args.language, args.copyright_holder, args.alias,
                               args.default_profile, force=args.force)
        _p(r)
        return 0 if r["ok"] else 1
    elif args.cmd == "config":
        if args.config_cmd == "show":
            cfg = config.read_config(root)
            _p({"present": cfg["present"], "error": cfg["error"], "problems": cfg["problems"],
                "data": config.redacted(cfg["data"]), "path": cfg["path"]})
        else:
            raw = args.value
            if args.key == "identity.header_aliases":
                # audit A-11: `none` (alone) clears the list; anything else is taken literally
                value = [] if len(raw) == 1 and raw[0].strip().lower() in ("none", "null", "[]") else raw
            elif args.key == "maintenance.startup_cleanup":
                word = raw[0].strip().lower()
                truthy, falsy = ("1", "true", "yes", "on", "oui", "vrai"), ("0", "false", "no", "off", "non", "faux")
                if word not in truthy + falsy:     # audit A-11: never a silent false
                    _p({"ok": False, "error": "maintenance.startup_cleanup expects true or false, got %r" % raw[0]})
                    return 1
                value = word in truthy
            else:
                value = " ".join(raw)
                if args.key == "identity.copyright_holder" and value.lower() in ("null", "none", ""):
                    value = None
            r = config.set_value(root, args.key, value)
            if isinstance(r.get("data"), dict):
                r = dict(r, data=config.redacted(r["data"]))
            _p(r)
            return 0 if r["ok"] else 1
    elif args.cmd == "migrate":
        if args.plan:
            r = migration.plan(root)
            _p(r)
            return 1 if r.get("config_error") else 0    # an unreadable configuration is never an empty plan
        elif args.apply:
            r = migration.apply(root)
            _p(r)
            return 0 if not r["errors"] else 1
        elif args.list_backups:
            _p({"backups": migration.list_backups(root)})
        else:
            r = migration.rollback(root, args.rollback)
            _p(r)
            return 0 if r["ok"] else 1
    elif args.cmd == "tooling-status":
        _p(tooling.status(root))
    elif args.cmd == "pinets":
        if args.action == "status":
            _p(tooling.status(root))
        elif args.action == "verify":
            findings = tooling.verify(root, record=args.record)
            _p(findings)
            return 1 if any(f["status"] == "BLOCKING" for f in findings) else 0
        elif args.action == "check-update":
            r = tooling.check_update(root)
            _p(r)
            return 0 if r["ok"] else 1
        elif args.action == "install":
            if not args.version:
                _p({"ok": False, "error": "an exact version is required"})
                return 1
            r = tooling.install(root, args.version, yes=args.yes)
            _p(r)
            return 0 if r["ok"] else 1
        elif args.action == "rollback":
            r = tooling.rollback(root, args.version, yes=args.yes)
            _p(r)
            return 0 if r["ok"] else 1
        else:
            _p(tooling.recalibrate_plan(root))
    elif args.cmd == "github":
        from . import github
        a = args.action
        if a == "status":
            _p(github.status(root))
        elif a == "destinations":
            _p({"destinations": github.destinations(root)})
        elif a == "destination-add":
            if not (args.name and args.repo and args.visibility):
                _p({"ok": False, "error": "--name, --repo and --visibility are required"})
                return 1
            r = github.destination_add(root, args.name, args.repo, args.visibility,
                                       args.path_prefix, args.branch, args.url)
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "destination-remove":
            r = github.destination_remove(root, args.name or "")
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "export-plan":
            if not (args.slug and args.destination):
                _p({"ok": False, "error": "--slug and --destination are required"})
                return 1
            r = github.export_plan(root, args.slug, args.destination)
            _p(r)
            return 0 if r.get("ok") else 1
        elif a == "fetch":
            r = github.fetch(root, args.destination or "")
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "export-diff":
            r = github.export_diff(root, args.slug or "", args.destination or "")
            _p(r)
            return 0 if r.get("ok") else 1
        else:
            r = github.publish(root, args.slug or "", args.destination or "", args.message, yes=args.yes)
            _p(r)
            return 0 if r.get("ok") else 1
    elif args.cmd == "maintenance":
        a = args.action
        if a == "cleanup":
            _p(maintenance.cleanup(root, execute=args.execute))
        elif a == "archives-plan":
            if not args.source:
                _p({"ok": False, "error": "--source is required"})
                return 1
            plan = maintenance.plan_import(root, args.source, args.target)
            ok = plan.get("ok") is True and "error" not in plan
            if not ok:
                # a refused plan is never written: an approved plan file is kept
                _p({"ok": False, "error": plan.get("error") or "plan refused",
                    "plan_file_written": False, "plan": plan})
                return 1
            if args.plan_file:
                try:
                    core.atomic_write_json(Path(args.plan_file), plan)
                except OSError as exc:
                    _p({"ok": False, "error": "plan file not written: %s" % exc,
                        "plan_file_written": False})
                    return 1
                _p({"ok": True, "plan_file": args.plan_file, "plan_file_written": True,
                    "counts": plan.get("counts"), "anomalies": plan.get("anomalies"),
                    "total_bytes": plan.get("total_bytes"), "copy_bytes": plan.get("copy_bytes")})
            else:
                _p(plan)
        else:
            plan, err = core.read_json(args.plan_file or "")
            if err or not isinstance(plan, dict):
                _p({"ok": False, "error": "--plan-file required (archives-plan output): %s" % (err or "invalid")})
                return 1
            if a == "archives-import":
                r = maintenance.execute_import(root, plan)
            elif a == "archives-verify":
                complete, problems = maintenance.verify_import(root, plan)
                r = {"ok": complete, "problems": problems}
            else:
                r = maintenance.remove_source(root, plan, yes=args.yes)
            _p(r)
            return 0 if r.get("ok") else 1
    elif args.cmd == "license":
        a = args.action
        if a == "templates":
            _p({"templates": licensing.KINDS, "folder": str(licensing.TEMPLATES_REL)})
        elif a == "fields-skeleton":
            print(licensing.eula_fields_skeleton(), end="")
        elif a == "detect":
            r = licensing.detect_source_licence(root, args.source or "")
            _p(r)
            return 0 if r["ok"] else 1
        elif not args.slug:
            _p({"ok": False, "error": "--slug is required"})
            return 1
        elif a == "status":
            r = licensing.status(root, args.slug)
            _p(r)
            return 0 if r.get("ok", True) else 1
        elif a == "overview":
            r = licensing.overview(root, args.slug, lang)
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "confirm":
            if args.license_document and args.no_license_documents:
                _p({"ok": False, "error": "--license-document and --no-license-documents exclude each other"})
                return 1
            documents = (list(args.license_document) if args.license_document
                         else [] if args.no_license_documents else None)
            r = licensing.confirm_publication(root, args.slug, state=args.state, privacy=args.privacy,
                                              mode=args.mode, created_year=args.created_year,
                                              terms_ref=args.terms_ref, terms_url=args.terms_url,
                                              clear=tuple(args.clear), license_id=args.license_id,
                                              license_documents=documents)
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "set-fields":
            updates = {}
            for item in args.field:
                if "=" not in item:
                    _p({"ok": False, "error": "--field expects NAME=value (got %r)" % item})
                    return 1
                name, value = item.split("=", 1)
                updates[name.strip()] = value
            r = licensing.set_fields(root, args.slug, updates, clear=args.clear, dry_run=args.dry_run)
            _p(r)
            return 0 if r["ok"] else 1
        elif a in ("render", "preview"):
            if not args.kind:
                _p({"ok": False, "error": "--kind is required"})
                return 1
            r = licensing.render(root, args.slug, args.kind)
            _p(r)
            return 0 if r["ok"] else 1
        else:
            if not args.kind:
                _p({"ok": False, "error": "--kind is required"})
                return 1
            dest = args.dest or licensing.default_dest(args.kind)
            r = licensing.write_rendered(root, args.slug, args.kind, dest)
            _p(r)
            return 0 if r["ok"] else 1
    elif args.cmd == "build-distribution":
        from . import distribution
        r = distribution.build(root, Path(args.target), force=args.force)
        _p(r)
        return 0 if r["ok"] else 1
    elif args.cmd == "upgrade":
        from . import upgrade
        if args.list_backups:
            _p({"backups": upgrade.list_backups(root)})
        elif args.rollback:
            r = upgrade.rollback(root, args.rollback, force=args.force)
            _p(r)
            return 0 if r["ok"] else 1
        elif not args.package:
            _p({"ok": False, "error": "--from <package folder> is required"})
            return 1
        elif args.plan:
            r = upgrade.plan(root, Path(args.package))
            _p(r)
            return 0 if r["ok"] else 1
        else:
            r = upgrade.apply(root, Path(args.package), overwrite_local=args.overwrite_local)
            _p(r)
            return 0 if r["ok"] else 1
    elif args.cmd == "update":
        a = args.action
        if a == "status":
            _p(update.status(root))
        elif a == "rollback-info":
            _p(update.rollback_info(root))
        elif a == "check":
            r = update.check(root, include_prereleases=args.include_prereleases)
            _p(r)
            return 0 if r["result"] != "error" else 1
        elif a == "fetch":
            r = update.fetch_release(root, tag=args.tag, dest=args.dest)
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "prepare":
            if not args.package:
                _p({"ok": False, "error": "--package <archive or folder> is required"})
                return 1
            r = update.prepare_local(root, args.package, expected_sha256=args.sha256, dest=args.dest)
            _p(r)
            return 0 if r["ok"] else 1
        elif a == "plan":
            if not args.package_dir:
                _p({"ok": False, "error": "--package-dir <verified package folder> is required"})
                return 1
            r = update.plan(root, args.package_dir, plan_file=args.plan_file)
            _p(r)
            return 0 if r["applicable"] else 1
        else:
            if not args.plan_file:
                _p({"ok": False, "error": "--plan-file <approved plan> is required"})
                return 1
            r = update.apply(root, args.plan_file, yes=args.yes)
            _p(r)
            return 0 if r["ok"] else 1
    elif args.cmd == "build-release":
        from . import release
        r = release.build_release(root, Path(args.target), force=args.force)
        _p(r)
        return 0 if r["ok"] else 1
    return 0


def main(argv=None):
    """Entry point with a common safety net (2026-11-13): an unexpected error
    becomes a JSON report `{"ok": false, "error": …}` with exit code 1 — never
    a bare Python trace for a subcommand whose contract is JSON. A hook never
    breaks the session: it prints one explanatory line and exits 0."""
    try:
        return _main(argv)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — the last line of defence; root causes are fixed where found
        words = list(sys.argv[1:] if argv is None else argv)
        command = next((w for w in words if not w.startswith("-")), None)
        detail = "%s: %s" % (type(exc).__name__, str(exc)[:400])
        if command and command.startswith("hook-"):
            print("PWS — internal error in %s (%s); run `python3 -m tools.pws_workspace doctor`" % (command, detail))
            return 0
        print(json.dumps({"ok": False, "error": "internal error (%s)" % detail, "command": command},
                         indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
