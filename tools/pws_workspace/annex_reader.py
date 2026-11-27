# SPDX-License-Identifier: Apache-2.0
"""Reader of the graphics annex of a local test — reader contract v1 (READER_CONTRACT.md next to
this module). Stdlib only, no display: it checks that a run report, its graphics annex and the
exact dataset belong together (annex SHA-256 recorded in the report, the seven identity fields,
the normalized payload recomputed, the dataset SHA-256, the annex values against the payload)
and returns the chart model. Every refusal carries a stable code; the files are only read.

Used by the browser chart (Vela, tools/vela_view) and by the local test path. It does not depend
on any terminal viewer. (Extracted from the former tools/visual/render.py reader; the terminal
viewers are no longer offered nor shipped.)
"""
import decimal
import hashlib
import json
import re

GRAPHICS_SCHEMA = "pws-pinets-graphics-v0.2-exp"          # the schema the runner writes today
LEGACY_SCHEMAS = ("pws-pinets-graphics-v0-exp", "pws-pinets-graphics-v0.1-exp")
READER_CONTRACT = "pws-graphics-reader-v1"
DRAWING_FAMILIES = ("boxes", "labels", "linefills", "lines", "polylines", "tables")

# Stable refusal codes of the reader contract v1, with their localized message. A refusal
# concerns the preview only: the run report is never modified and its result stays valid.
REFUSAL_TEXT = {
    "MISSING": {"fr": "fichier absent", "en": "file missing"},
    "MALFORMED": {"fr": "fichier illisible ou mal formé", "en": "unreadable or malformed file"},
    "REPORT_INVALID": {"fr": "rapport inutilisable pour un aperçu", "en": "report not usable for a preview"},
    "UNKNOWN_SCHEMA": {"fr": "version d'annexe inconnue de ce lecteur", "en": "annex version unknown to this reader"},
    "LEGACY": {"fr": "ancienne version d'annexe, insuffisamment liée à son rapport",
               "en": "old annex version, insufficiently bound to its report"},
    "SCHEMA_MISMATCH": {"fr": "le rapport et l'annexe déclarent des versions différentes",
                        "en": "the report and the annex declare different versions"},
    "ALTERED": {"fr": "annexe altérée ou remplacée", "en": "annex altered or replaced"},
    "OTHER_RUN": {"fr": "annexe issue d'une autre exécution", "en": "annex from another execution"},
    "OTHER_DATASET": {"fr": "jeu de données différent de celui du calcul", "en": "dataset differs from the computed one"},
}
REFUSAL_CODES = tuple(REFUSAL_TEXT)


def refusal_message(code, lang):
    e = REFUSAL_TEXT.get(code) or REFUSAL_TEXT["MALFORMED"]
    return e.get(lang) or e["en"]


def short_version(schema):
    """'pws-pinets-graphics-v0.2-exp' -> 'v0.2-exp' (shown as the annex's version of origin)."""
    return schema.rsplit("-graphics-", 1)[-1] if isinstance(schema, str) else "?"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTITY_FIELDS = ("run_id", "source_sha256", "dataset_sha256", "pinets_version", "executor_fingerprint",
                   "normalization_schema", "normalized_payload_sha256")


class Refused(SystemExit):
    """Artifacts refused before any display: a stable `refusal_code` (REFUSAL_CODES) and an
    English technical `detail`. (Not `code`: SystemExit already uses that name.)"""

    def __init__(self, detail, refusal_code="MALFORMED"):
        super().__init__(detail)
        self.detail, self.refusal_code = detail, refusal_code

    def __str__(self):
        return "[%s] %s" % (self.refusal_code, self.detail)


def _js_number(x):
    """Number text exactly as JavaScript's JSON.stringify writes it (ECMAScript Number::toString)."""
    if isinstance(x, bool): return "true" if x else "false"
    if isinstance(x, int) and abs(x) < 10 ** 21: return str(x)
    x = float(x)
    if x != x or x in (float("inf"), float("-inf")): return "null"
    if x == 0: return "0"
    sign, digits, exp = decimal.Decimal(repr(x)).normalize().as_tuple()
    ds = "".join(map(str, digits)); k = len(ds); n = exp + k
    if k <= n <= 21: out = ds + "0" * (n - k)
    elif 0 < n <= 21: out = ds[:n] + "." + ds[n:]
    elif -6 < n <= 0: out = "0." + "0" * (-n) + ds
    else:
        e = n - 1; out = ds[0] + ("." + ds[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return ("-" if sign else "") + out


def _js_key_order(keys):
    """Order JSON.stringify emits for an object whose keys were inserted sorted: array-index keys
    (canonical integers < 2**32 - 1) first in numeric order, then the others in sort order."""
    idx = sorted((k for k in keys if k.isdigit() and str(int(k)) == k and int(k) < 2 ** 32 - 1), key=int)
    rest = sorted((k for k in keys if k not in set(idx)), key=lambda k: k.encode("utf-16-be"))
    return idx + rest


def canonical_payload_text(o):
    """Python port of normalize.mjs canonicalPayloadText: JSON.stringify(sortKeys(payload))."""
    if o is None: return "null"
    if isinstance(o, bool) or isinstance(o, (int, float)): return _js_number(o)
    if isinstance(o, str): return json.dumps(o, ensure_ascii=False)
    if isinstance(o, list): return "[" + ",".join(canonical_payload_text(v) for v in o) + "]"
    if isinstance(o, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical_payload_text(o[k]) for k in _js_key_order(list(o))) + "}"
    raise Refused("unsupported value in normalized payload: %r" % type(o))


def js_round12(v):
    """Python port of normalize.mjs roundValue: Number(v.toPrecision(12)); non-numbers -> None."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)): return None
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")): return None
    if v == 0: return 0
    d = decimal.Decimal(v)                                   # exact binary value
    q = decimal.Decimal(1).scaleb(d.adjusted() - 11)          # 12 significant digits
    r = float(d.quantize(q, rounding=decimal.ROUND_HALF_UP))  # ties away from zero, as toPrecision
    return 0 if r == 0 else r


def payload_sha256(payload):
    return hashlib.sha256(canonical_payload_text(payload).encode("utf-8")).hexdigest()


def _need(cond, msg, code="MALFORMED"):
    if not cond: raise Refused(msg, code)


def _check_identity_types(d, where):
    for k in IDENTITY_FIELDS:
        v = d.get(k)
        if k in ("source_sha256", "dataset_sha256", "executor_fingerprint", "normalized_payload_sha256"):
            _need(isinstance(v, str) and HEX64.match(v), "%s: %s missing or not a lowercase SHA-256" % (where, k))
        else:
            _need(isinstance(v, str) and v != "", "%s: %s missing or not a non-empty string" % (where, k))


def _check_annex_shape(g, where):
    _need(isinstance(g.get("declaration"), dict), where + ": declaration must be an object")
    _need(isinstance(g.get("series"), list), where + ": series must be a list")
    for s in g["series"]:
        _need(isinstance(s, dict) and isinstance(s.get("key"), str) and isinstance(s.get("kind"), str)
              and isinstance(s.get("options"), dict) and isinstance(s.get("points"), list),
              where + ": malformed series entry")
        for p in s["points"]:
            _need(isinstance(p, dict) and isinstance(p.get("t"), int) and not isinstance(p.get("t"), bool), where + ": point time must be an integer (%s)" % s["key"])
            v = p.get("v")
            _need(v is None or isinstance(v, (bool, int, float)), where + ": point value must be a number, boolean or null (%s)" % s["key"])
    _need(isinstance(g.get("drawings"), dict) and all(isinstance(v, list) for v in g["drawings"].values()), where + ": drawings must map families to lists")
    _need(set(g["drawings"]) <= set(DRAWING_FAMILIES), where + ": unknown drawing family %s" % sorted(set(g["drawings"]) - set(DRAWING_FAMILIES)))
    _need(g.get("drawings_scope") == "final-state", where + ": drawings_scope must be 'final-state'")
    _need(isinstance(g.get("limits"), list) and all(isinstance(x, str) for x in g["limits"]), where + ": limits must be a list of texts")


# One shape check per annex version this reader knows; an annex is read under ITS version.
READERS = {GRAPHICS_SCHEMA: _check_annex_shape}


def load(dataset_path, pairs):
    """pairs: [(run_report_path, graphics_annex_path)], all on the same dataset.

    Binding contract (annex schema GRAPHICS_SCHEMA), all checked before any display:
    - run report: schema, PASS status, typed identity fields, payload hash recomputed with the
      canonical form of normalize.mjs, graphics_annex = {schema, sha256} without error;
    - annex file: SHA-256 of its bytes equals the report's graphics_annex.sha256, schema equal;
    - the seven identity fields equal between report and annex; dataset SHA-256 equals the file;
    - annex shape and types; series times equal the dataset times.
    Older artifacts (annex schema without the report-side SHA-256) are refused, never completed.
    Every refusal carries a stable code (REFUSAL_CODES); the files are only read."""
    try:
        with open(dataset_path, "rb") as fh: raw = fh.read()
    except OSError as e:
        raise Refused("dataset unreadable: %s" % e, "MISSING" if isinstance(e, FileNotFoundError) else "MALFORMED")
    try:
        ds = json.loads(raw); sc = ds["descriptor"]["price_scale"]
        bars = [{"t": b["t"], "o": b["o"] / sc, "h": b["h"] / sc, "l": b["l"] / sc, "c": b["c"] / sc} for b in ds["bars"]]
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        raise Refused("malformed dataset %s: %s" % (dataset_path, e))
    dsha = hashlib.sha256(raw).hexdigest()
    times = [b["t"] for b in bars]
    inds = []
    for rp, gp in pairs:
        try:
            with open(rp, encoding="utf-8") as fh: r = json.load(fh)
            with open(gp, "rb") as fh: graw = fh.read()
            g = json.loads(graw)
        except FileNotFoundError as e:
            raise Refused("missing artifact: %s" % e, "MISSING")
        except (OSError, ValueError) as e:
            raise Refused("unreadable artifact: %s" % e)
        _need(isinstance(r, dict) and isinstance(g, dict), "artifacts must be JSON objects")
        _need(r.get("schema") == "pws-pinets-run-v1", "not a PWS runner report (schema): %s" % rp, "REPORT_INVALID")
        _need(r.get("execution_status") == "PINETS_EXECUTION_PASS", "run is not PINETS_EXECUTION_PASS: %s" % rp,
              "REPORT_INVALID")
        gs = g.get("schema")
        if gs in LEGACY_SCHEMAS:
            raise Refused("legacy annex %s (%s): insufficiently bound (no SHA-256 of the annex in its run "
                          "report); re-run to produce %s — never completed artificially" % (gp, gs, GRAPHICS_SCHEMA),
                          "LEGACY")
        _need(gs in READERS, "unknown graphics annex schema %r in %s (known: %s)" % (gs, gp, ", ".join(READERS)),
              "UNKNOWN_SCHEMA")
        _check_identity_types(r, "run report " + rp); _check_identity_types(g, "annex " + gp)
        ga = r.get("graphics_annex")
        _need(isinstance(ga, dict) and isinstance(ga.get("sha256"), str) and HEX64.match(ga["sha256"])
              and not ga.get("error"),
              "run report %s does not record a valid graphics annex (sha256, no error)" % rp, "REPORT_INVALID")
        _need(ga.get("schema") == gs, "run report %s records annex schema %r, the annex declares %r"
              % (rp, ga.get("schema"), gs), "SCHEMA_MISMATCH")
        if hashlib.sha256(graw).hexdigest() != ga["sha256"]:
            other = g.get("run_id")
            if isinstance(other, str) and other != r.get("run_id"):
                raise Refused("annex %s comes from another execution (annex run_id %s, report run_id %s)"
                              % (gp, other, r.get("run_id")), "OTHER_RUN")
            raise Refused("annex %s is not the file recorded by run %s (SHA-256 differs: altered or replaced)" % (gp, rp),
                          "ALTERED")
        for k in IDENTITY_FIELDS:
            _need(g[k] == r[k], "annex %s does not belong to run %s (%s differs)" % (gp, rp, k), "OTHER_RUN")
        _need(isinstance(r.get("normalized"), dict), "run report %s has no normalized payload" % rp, "REPORT_INVALID")
        _need(payload_sha256(r["normalized"]) == r["normalized_payload_sha256"],
              "run report %s: normalized payload does not match normalized_payload_sha256" % rp, "REPORT_INVALID")
        _need(r["dataset_sha256"] == dsha, "run %s was computed on another dataset" % rp, "OTHER_DATASET")
        READERS[gs](g, "annex " + gp)
        # the annex series must carry the SAME computed values as the hashed payload
        plots = r["normalized"].get("plots")
        _need(isinstance(plots, dict), "run report %s: normalized.plots missing" % rp)
        _need(set(plots) == {s["key"] for s in g["series"]},
              "annex %s and payload of run %s list different series" % (gp, rp))
        for s in g["series"]:
            pv = plots[s["key"]]
            _need(isinstance(pv, list) and len(pv) == len(s["points"]) and all(
                  isinstance(b, dict) and b.get("t") == a["t"] and b.get("v") == js_round12(a["v"]) for a, b in zip(s["points"], pv)),
                  "annex %s: values of series %r differ from the hashed payload of run %s" % (gp, s["key"], rp))
        for s in g["series"]:
            _need([p["t"] for p in s["points"]] == times, "timestamps of %s differ from the dataset" % s["key"],
                  "OTHER_DATASET")
        inds.append({"title": g["declaration"].get("title", rp), "overlay": bool(g["declaration"].get("overlay")),
                     "series": {s["key"]: s for s in g["series"]}, "drawings": g["drawings"],
                     "annex_schema": gs, "annex_version": short_version(gs),
                     # the reader contract v1 guarantees only the family and the count of the drawings
                     "drawing_counts": {f: len(g["drawings"].get(f, [])) for f in DRAWING_FAMILIES},
                     "run_id": r["run_id"], "source_sha256": r["source_sha256"],
                     "executor_fingerprint": r["executor_fingerprint"]})
    return {"bars": bars, "times": times, "inds": inds, "dataset_sha256": dsha}
