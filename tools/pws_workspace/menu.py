# SPDX-License-Identifier: Apache-2.0
"""Deterministic /pws menu tree — one workflow logic, localized labels.

The skill `pws` RENDERS this tree with AskUserQuestion (one screen at a
time); it carries no structure of its own. Every screen holds at most four
options (AskUserQuestion limit) — longer lists are paginated with "More…"
and EVERY screen below the first level carries "Back" (a continued screen
holds two entries + More… + Back; the last screen up to three + Back).
Applicability is derived from the real workspace state (session-status):
an inapplicable entry is listed with its reason and must not be offered.

Navigation order ratified on 2026-11-06: Work on a script → choose the
ACTION → choose the SCRIPT. With exactly one REGISTERED script the choice
is direct but its identity stays explicit (label "Script: <slug> (kind,
profile)" + "Continue with this script"); several scripts → the paginated
`script_screens` ("Others…" / Back). Incomplete / unregistered products keep
their dedicated routes (onboarding), never a silent selection.

Visible texts (revised after the holder's walkthrough): every offered node
carries a short `description` in the configured language; internal names
(skills, commands, hashes) never appear in labels or descriptions. The
Configuration submenu lists SETTING nodes (`kind: setting`) with the current
value (`current`, `current_label`), the canonical `choices` when the value
is an enumeration, a `keep_label` ("Keep … (Back)": no write when the value
does not change) and `free_text` when the value is typed conversationally.
"""
from . import i18n, profiles

MAX_OPTIONS = 4
DEFAULT_PROFILES = ("FREE", "PRIVATE", "COMMERCIAL")   # config.PROFILES_FOR_DEFAULT
TV_MODES = ("manual", "chrome-experimental")


def _script_label(p, lang):
    kind = i18n.t("menu.kind.%s" % p.get("script_kind"), lang) if p.get("script_kind") else "?"
    variant = p.get("profile_variant") or p.get("profile") or "?"
    return "%s (%s, %s)" % (p["slug"], kind, variant)


def _node(node_id, label, kind="action", route=None, applicable=True, reason=None,
          needs_script=False, children=None, **extra):
    n = {"id": node_id, "label": label, "kind": kind, "route": route,
         "applicable": applicable, "reason": reason, "needs_script": needs_script}
    if children is not None:
        n["children"] = children
    n.update(extra)
    return n


def _action(node_id, lang, route, **extra):
    """Action node with its localized label and short description."""
    return _node(node_id, i18n.t("menu.%s" % node_id, lang), route=route,
                 description=i18n.t("menu.%s.desc" % node_id, lang), **extra)


def _setting(node_id, lang, route, current, current_label, choices=None, free_text=False, **extra):
    """Configuration setting: current value shown first, canonical choices,
    and a "keep (Back)" option that writes nothing."""
    n = _node(node_id, i18n.t("menu.%s" % node_id, lang), kind="setting", route=route,
              description=i18n.t("menu.%s.desc" % node_id, lang),
              current=current, current_label=current_label,
              keep_label=i18n.t("menu.config.keep", lang, value=current_label),
              free_text=free_text, **extra)
    if extra.get("invalid"):
        n["keep_label"] = None          # an invalid value is never offered as "keep" (audit B-05)
    if choices is not None:
        n["choices"] = [{"value": v, "label": lbl, "selected": v == current} for v, lbl in choices]
    return n


HEADER_MAX = 12                       # limit of the dialog tool's header chip
SCREEN_HEADERS = ("kind", "profile", "script", "setting", "confirm")


def _add_headers(nodes, lang):
    """Give every submenu node its localized short header (menu.header.<id>)."""
    for node in nodes:
        if node.get("kind") == "submenu":
            node["header"] = i18n.t("menu.header.%s" % node["id"], lang)
        for screen in node.get("children") or []:
            _add_headers(screen, lang)


def paginate(options, lang, with_back=True, more_label=None):
    """Split a list of option nodes into screens of ≤ MAX_OPTIONS, adding
    More…/Back navigation nodes; Back is present on EVERY screen when
    with_back is true. Returns [screen] where screen = [node]."""
    back = _node("back", i18n.t("back", lang), kind="back")
    more = _node("more", more_label or i18n.t("more", lang), kind="more")
    nav = 1 if with_back else 0
    if len(options) + nav <= MAX_OPTIONS:
        return [options + ([back] if with_back else [])]
    screens = []
    per = MAX_OPTIONS - 1 - nav  # room for More… (+ Back) on a continued screen
    i = 0
    while i < len(options):
        remaining = len(options) - i
        if remaining + nav <= MAX_OPTIONS:
            screens.append(options[i:] + ([back] if with_back else []))
            break
        chunk = options[i:i + per]
        i += per
        screens.append(chunk + [more] + ([back] if with_back else []))
    return screens


def _config_children(status, lang):
    cfg = status.get("config") or {}
    holder = cfg.get("copyright_holder")
    aliases = [a for a in (cfg.get("header_aliases") or []) if isinstance(a, str)]
    unset = i18n.t("menu.config.unset", lang)
    identity_label = (holder + (" (%s)" % ", ".join(aliases) if aliases else "")) if holder else unset
    default_profile = cfg.get("default_profile") if cfg.get("default_profile") in DEFAULT_PROFILES else "FREE"
    tv = status.get("tv_mode") if status.get("tv_mode") in TV_MODES else None
    tv_invalid = tv is None and bool(status.get("tv_mode_error"))
    if tv is None and not tv_invalid:
        tv = "manual"
    dests = [d for d in (cfg.get("github_destinations") or []) if isinstance(d, dict) and d.get("name")]
    dest_names = [d["name"] for d in dests]
    cleanup = bool(cfg.get("startup_cleanup", True))
    on_off = {True: i18n.t("menu.cleanup.on", lang), False: i18n.t("menu.cleanup.off", lang)}
    return [
        _setting("config.language", lang, "command:config set language", lang,
                 i18n.t("menu.language.%s" % lang, lang),
                 choices=[(code, i18n.t("menu.language.%s" % code, lang)) for code in i18n.LANGUAGES]),
        _setting("config.identity", lang, "command:config set identity.copyright_holder", holder,
                 identity_label, free_text=True, aliases=aliases),
        _setting("config.profile", lang, "command:config set identity.default_profile", default_profile,
                 i18n.t("menu.profile.%s" % default_profile, lang),
                 choices=[(p, i18n.t("menu.profile.%s" % p, lang)) for p in DEFAULT_PROFILES]),
        _setting("config.tvmode", lang, "command:tv-mode", tv,
                 (i18n.t("menu.tvmode.invalid", lang, value=str(status.get("tv_mode_error") or "?")[:60])
                  if tv_invalid else i18n.t("menu.tvmode.%s" % tv, lang)),
                 choices=[(m, i18n.t("menu.tvmode.%s" % m, lang)) for m in TV_MODES],
                 explicit_choice_required=True, invalid=tv_invalid),
        _setting("config.github", lang, "command:github destinations", dest_names,
                 ", ".join(dest_names) or i18n.t("menu.config.none", lang), free_text=True,
                 destinations=dests),
        _setting("config.cleanup", lang, "command:config set maintenance.startup_cleanup", cleanup,
                 on_off[cleanup], choices=[(True, on_off[True]), (False, on_off[False])]),
    ]


def build_menu(status):
    """Build the tree from a session-status dict. Pure function (no I/O)."""
    lang = status.get("language") or i18n.DEFAULT_LANGUAGE
    products = status.get("products") or []
    registered = [p for p in products if p.get("product_structure_status") == "REGISTERED"]
    has_products = bool(products)
    scripts = [{"slug": p["slug"], "label": _script_label(p, lang),
                "script_kind": p.get("script_kind"), "profile": p.get("profile"),
                "profile_variant": p.get("profile_variant"),
                "status": p.get("product_structure_status")} for p in registered]
    not_ready = [{"slug": p["slug"], "status": p.get("product_structure_status"),
                  "route": "pine-onboard"} for p in products
                 if p.get("product_structure_status") != "REGISTERED"]
    single = scripts[0] if len(scripts) == 1 else None
    no_reg = i18n.t("menu.na.no_registered", lang)
    no_prod = i18n.t("menu.na.no_product", lang)
    need = {"applicable": bool(registered), "reason": None if registered else no_reg, "needs_script": True}

    work_children = [
        _action("work.develop", lang, "pine-develop", **need),
        _action("work.docs", lang, "pine-docs", **need),
        _action("work.research", lang, "pine-research", **need),
        _action("work.review", lang, "pine-review", **need),
        _action("work.audit", lang, "pine-audit", **need),
    ]
    new_children = [
        _action("new.script", lang, "pine-new", profile_screen=True),
        _action("new.import", lang, "pine-onboard",
                unregistered=list(status.get("unregistered_pine") or []), not_ready=not_ready),
    ]
    quality_children = [
        _action("quality.local", lang, "pine-local-test", **need),
        _action("quality.tv", lang, "tv-validate", **need),
        _action("quality.license", lang, "pine-license", **need),
        _action("quality.release", lang, "pine-release", **need),
        _action("quality.github", lang, "pine-github", **need),
    ]
    # Tools and updates (2026-11-08): PineTS management and the update of
    # Pine Workspace itself are two distinct entries of one generated submenu
    tools_children = [
        _action("tools.pinets", lang, "pine-tools"),
        _action("tools.update", lang, "pws-update"),
    ]
    if status.get("vela_state") in ("ready", "no-deps"):     # only where the browser chart is installed
        tools_children.insert(1, _action("tools.vela", lang, "vela-tools"))
    maintenance_children = [
        _action("maintenance.doctor", lang, "project-doctor"),
        _action("maintenance.status", lang, "command:session-status"),
        _node("maintenance.config", i18n.t("menu.maintenance.config", lang), kind="submenu",
              description=i18n.t("menu.maintenance.config.desc", lang),
              children=paginate(_config_children(status, lang), lang)),
        _node("maintenance.tools", i18n.t("menu.maintenance.tools", lang), kind="submenu",
              description=i18n.t("menu.maintenance.tools.desc", lang),
              children=paginate(tools_children, lang)),
        _action("maintenance.archives", lang, "pine-maintenance"),
    ]
    top = [
        _node("work", i18n.t("menu.work", lang), kind="submenu",
              applicable=bool(registered), reason=None if registered else no_reg,
              description=i18n.t("menu.work.desc", lang),
              children=paginate([c for c in work_children if c["applicable"]], lang)),
        _node("new", i18n.t("menu.new", lang), kind="submenu",
              description=i18n.t("menu.new.desc", lang),
              children=paginate(new_children, lang)),
        _node("quality", i18n.t("menu.quality", lang), kind="submenu",
              applicable=bool(registered), reason=None if registered else (no_reg if has_products else no_prod),
              description=i18n.t("menu.quality.desc", lang),
              children=paginate([c for c in quality_children if c["applicable"]], lang)),
        _node("maintenance", i18n.t("menu.maintenance", lang), kind="submenu",
              description=i18n.t("menu.maintenance.desc", lang),
              children=paginate(maintenance_children, lang)),
    ]
    script_nodes = [_node("script.%s" % s["slug"], s["label"], kind="script", slug=s["slug"])
                    for s in scripts]
    profile_options = [
        {"value": p, "label": i18n.t("menu.profile.%s" % p, lang), "description": i18n.t("menu.profile.%s.desc" % p, lang)}
        for p in ("FREE", "FREE_CLOSED", "PRIVATE", "COMMERCIAL")]
    # audit B-01 (2026-11-13): the screens are paginated here like every other screen (≤ 4 options, Back)
    profile_nodes = [_node("profile.%s" % o["value"], o["label"], kind="profile", value=o["value"],
                           description=o["description"]) for o in profile_options]
    # audit B-06 (2026-11-13): every submenu and question screen carries its
    # short dialog header (≤ HEADER_MAX characters), never improvised
    _add_headers(top, lang)
    return {
        "language": lang,
        "title": i18n.t("menu.title", lang),
        "headers": {k: i18n.t("menu.header.%s" % k, lang) for k in SCREEN_HEADERS},
        "top": [t for t in top if t["applicable"]],
        "inapplicable": [{"id": t["id"], "reason": t["reason"]} for t in top if not t["applicable"]],
        "scripts": scripts,
        "single_script": single,
        "single_script_label": (i18n.t("menu.script.single", lang, label=single["label"])
                                if single else None),
        "continue_label": i18n.t("menu.script.continue", lang),
        "choose_script_label": i18n.t("menu.script.choose", lang),
        "others_label": i18n.t("menu.script.others", lang),
        "script_screens": (paginate(script_nodes, lang, more_label=i18n.t("menu.script.others", lang))
                           if script_nodes else []),
        "not_ready": not_ready,
        "kinds": [{"value": k, "label": i18n.t("menu.kind.%s" % k, lang)}
                  for k in ("indicator", "strategy", "library")],
        "profiles": profile_options,
        "profile_screens": paginate(profile_nodes, lang),
        "library_rule": i18n.t("menu.na.library_profile", lang),
        "profile_defaults": {k: {"license": profiles.default_license(k),
                                 "publication": profiles.default_publication(k)}
                             for k in profiles.PROFILES},
        "free_closed_defaults": {"license": profiles.default_license("FREE", closed_source=True),
                                 "publication": profiles.default_publication("FREE", closed_source=True)},
        "publication_axes": {"state": list(profiles.PUBLICATION_STATES) + [None],
                             "privacy": list(profiles.PUBLICATION_PRIVACIES) + [None],
                             "mode": list(profiles.PUBLICATION_MODES) + [None]},
        "labels": {"back": i18n.t("back", lang), "more": i18n.t("more", lang),
                   "start": i18n.t("start", lang), "modify": i18n.t("modify", lang),
                   "cancel": i18n.t("cancel", lang)},
    }
