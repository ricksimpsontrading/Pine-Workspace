# SPDX-License-Identifier: Apache-2.0
"""TradingView mode controller — sole owner of the persisted mode mutation.

The persisted truth is `pws.config.json` (key `tv_validation_mode`), the PWS
personal configuration — separated from Claude Code's own settings since
the 2026-11-06 evolution. Reads and writes both go through this module.

Legacy location (read-compatible, for migration only): the key
`env.PWS_TV_VALIDATION_MODE` of `.claude/settings.local.json`. It is
consulted only when the configuration file carries no mode; `migrate`
copies it into the configuration and removes it. The process environment
variable is never a read path.

Default: `manual`. A missing configuration is NOT an error — the default
applies and the source is reported as `default`. An INVALID persisted value
is an error (the doctor reports it BLOCKING).

Mutation contract (spec sections 19.3 / 28.3, updated): the whole
read-modify-write runs under the PWS writers' lock of the configuration file
(`pws.config.json.lock`), every other key is preserved, temp file + atomic
replace, re-read and validation, and a modification detected between the
initial read and the pre-write re-read is refused as a conflict. Only the
user triggers a persistent change (/tv-mode user-only skill, or the explicit
"TradingView mode" choice in /pws) — both routes call this controller; the
fallback of a chrome-experimental run to manual never changes the persisted
mode.
"""
from pathlib import Path

from . import config, core

DEFAULT_MODE = "manual"


def _legacy_mode(root):
    """(mode, detail) from the legacy settings.local.json key, or (None, None)
    when absent. An invalid legacy value is reported, never silently used."""
    path = Path(root) / core.LOCAL_SETTINGS_REL
    if path.is_symlink():
        # review RS-07 (2026-11-13), same rule as the migrations (F-12): content
        # outside the workspace is never read; the owner sets the mode explicitly
        return None, ("legacy settings.local.json is a symbolic link — not read; set the mode "
                      "with `tv-mode <mode>`")
    data, err = core.read_json(path)
    if err or not isinstance(data, dict):
        return None, None
    env = data.get("env")
    if not isinstance(env, dict) or core.TV_MODE_ENV_KEY not in env:
        return None, None
    mode = env.get(core.TV_MODE_ENV_KEY)
    if mode not in core.MODES:
        return None, ("legacy settings.local.json env.%s is %r (invalid)"
                      % (core.TV_MODE_ENV_KEY, mode))
    return mode, None


def read_mode_detail(root):
    """{mode, source: config|legacy|default, error}."""
    cfg = config.read_config(root)
    if cfg["error"]:
        return {"mode": None, "source": "config", "error": cfg["error"]}
    raw = cfg["raw"] or {}
    if "tv_validation_mode" in raw:
        mode = raw.get("tv_validation_mode")
        if mode not in core.MODES:
            return {"mode": None, "source": "config",
                    "error": "persisted mode %r invalid (expected one of %s)"
                             % (mode, list(core.MODES))}
        return {"mode": mode, "source": "config", "error": None}
    legacy, lerr = _legacy_mode(root)
    if lerr:
        return {"mode": None, "source": "legacy", "error": lerr}
    if legacy:
        return {"mode": legacy, "source": "legacy", "error": None}
    return {"mode": DEFAULT_MODE, "source": "default", "error": None}


def read_mode(root):
    """Current persisted mode. Returns (mode, detail) — detail is None when
    the mode is valid (configured, legacy or default)."""
    d = read_mode_detail(root)
    return d["mode"], d["error"]


def set_mode(root, mode):
    """Atomically set the persisted mode in pws.config.json, preserving all
    other keys. Creates the configuration file (defaults) when absent."""
    if mode not in core.MODES:
        return {"ok": False, "error": "invalid mode %r; allowed: %s" % (mode, ", ".join(core.MODES))}

    def mutate(data):
        data["tv_validation_mode"] = mode
        data[config.MODE_CHOICE_KEY] = config.mode_choice_record("tv-mode")
        return None

    result = config.update_config(root, mutate)
    if not result["ok"]:
        return {"ok": False, "error": result["error"]}
    persisted = (result.get("data") or {}).get("tv_validation_mode")
    if persisted != mode:
        return {"ok": False, "error": "post-write check: persisted mode is %r" % persisted}
    return {"ok": True, "mode": mode,
            "note": "persisted in pws.config.json; always read the mode via this controller"}
