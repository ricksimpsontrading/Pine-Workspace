"""Build the datasets, the expected documents and the manifest of the cases.

Deterministic: running it twice yields byte-identical files. Expected values
come from independent references only — tools/tests/ref_indicators.py for
the mathematical contracts, direct computation from the dataset file, or a
value derived by hand from the documented semantics of the language. The
engine is never an oracle. Datasets are written through the canonical
serializer of tools/pine_exec/datasets.mjs (imported, not modified).

Usage (from the repository root):
    python3 -m tools.tests.pinets_cases.build_cases          # write
    python3 -m tools.tests.pinets_cases.build_cases --check  # verify only
"""
import json
import subprocess
import sys
from pathlib import Path

from tools.tests import ref_indicators as ref
from tools.tests.pinets_cases import cases_lib as lib

T0 = 1577836800000
HOUR = 3600000
LCG60 = "tools/pine_exec/calibration/datasets/lcg-42-60.json"
CASES_REL = "tools/tests/pinets_cases"

DOC_ROOT = "https://www.tradingview.com/pine-script-docs/"


def _bars_constant(n):
    return [{"t": T0 + i * HOUR, "o": 10000, "h": 10000, "l": 10000,
             "c": 10000, "v": 1000} for i in range(n)]


def _bars_monotone(n):
    out = []
    for i in range(n):
        c = 10000 + 100 * (i + 1)
        o = c - 100
        out.append({"t": T0 + i * HOUR, "o": o, "h": c + 10, "l": o - 10,
                    "c": c, "v": 1000 + i})
    return out


def _bars_gapped(n):
    """LCG prices (seed 7) on a timeline with holes: after every fifth bar
    the next bar opens two hours later instead of one."""
    bars = ref.generate_bars(7, n, 10000, 150, T0, HOUR)
    t = T0
    for i, b in enumerate(bars):
        b["t"] = t
        t += 2 * HOUR if i % 5 == 4 else HOUR
    return bars


PLATEAU_CLOSES = [100, 101, 102, 102, 101, 100, 99, 99, 100, 103, 103, 103, 101,
                  100, 98, 98, 99, 101, 101, 100, 104, 102, 102, 104, 103, 101,
                  100, 100, 102, 105]


def _bars_plateau(n):
    """Hand-written closes with equal neighbours, to meet ties."""
    assert n == len(PLATEAU_CLOSES)
    out, prev = [], 100
    for i, close in enumerate(PLATEAU_CLOSES):
        o, c = prev * 100, close * 100
        out.append({"t": T0 + i * HOUR, "o": o, "h": max(o, c) + 50,
                    "l": min(o, c) - 50, "c": c, "v": 1000 + i})
        prev = close
    return out


DATASETS = {
    "plateau-30.json": ("pws-cases-plateau-v1",
                        {"bars": 30, "closes": "hand-written, with equal neighbours"},
                        _bars_plateau),
    "constant-30.json": ("pws-cases-constant-v1",
                         {"bars": 30, "price_cents": 10000}, _bars_constant),
    "monotone-30.json": ("pws-cases-monotone-v1",
                         {"bars": 30, "first_close_cents": 10100, "step_cents": 100},
                         _bars_monotone),
    "gapped-30.json": ("pws-cases-gapped-v1",
                       {"bars": 30, "seed": 7, "base_cents": 10000, "vol_cents": 150,
                        "hole": "one missing hour after every fifth bar"},
                       _bars_gapped),
}


def dataset_text(generator, params, bars):
    descriptor = {"type": "synthetic", "generator": generator, "params": params,
                  "symbol": "SYNTH", "timeframe_ms": HOUR, "timezone": "UTC",
                  "price_scale": 100}
    script = ("import { canonicalDatasetText } from './datasets.mjs';"
              "let s='';process.stdin.on('data',d=>s+=d);"
              "process.stdin.on('end',()=>{const j=JSON.parse(s);"
              "process.stdout.write(canonicalDatasetText(j.descriptor,j.bars));});")
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=str(lib.PINE_EXEC),
        input=json.dumps({"descriptor": descriptor, "bars": bars}).encode("utf-8"),
        capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return proc.stdout.decode("utf-8")


def _points(times, values):
    return [{"t": t, "v": lib.round12(v)} for t, v in zip(times, values)]


def _constant(times, value):
    return _points(times, [value] * len(times))


def _established(values, provenance):
    return {"status": lib.ESTABLISHED, "provenance": provenance, "values": values}


CONSULTED = "2026-09-28"
CAVEAT = (" Citation obtenue par un outil d'extraction, a reconfirmer par "
          "lecture directe.")
DOC_LOOPS = ("documentation officielle, User Manual v6, page language/loops, "
             "consultee le %s : la derniere iteration a lieu lorsque le "
             "compteur atteint la borne `to`, donc borne incluse." % CONSULTED
             + CAVEAT)
DOC_LAZY = ("documentation officielle, guide de migration vers v6, section "
            "Lazy evaluation of conditions, consultee le %s : `and` et `or` "
            "sont evalues paresseusement." % CONSULTED + CAVEAT)
DOC_DEFAULT = ("documentation officielle, User Manual v6, page "
               "language/objects, consultee le %s : un champ prend sa valeur "
               "par defaut declaree lorsqu'aucune valeur n'est fournie a la "
               "creation." % CONSULTED + CAVEAT)
DOC_HISTORY = ("documentation officielle, User Manual v6, pages "
               "language/execution-model et language/operators, consultees "
               "le %s : une reference historique vers une barre inexistante "
               "renvoie `na`." % CONSULTED + CAVEAT)
DOC_PLOT_BOOL = ("documentation officielle, User Manual v6, page "
                 "visuals/plots, consultee le %s : `plot()` exige une serie "
                 "int/float, un bool est converti par `cond ? 1 : 0`."
                 % CONSULTED + CAVEAT)
NO_REFERENCE = ("Reference Manual v6 illisible par l'outil le %s (deux "
                "tentatives)" % CONSULTED)
TV_FIXTURE = "observation TradingView de cette fixture"
REF_MANUAL = ("Reference Manual officiel v6, lu le 2026-09-28 dans les "
              "fichiers servis par la page "
              "https://www.tradingview.com/pine-script-reference/v6/ "
              "(donnees : bundles/42609.089e9e22f7101e985227.js, SHA-256 "
              "635cab3f...8b12b ; textes anglais : bundles/en.66605 et "
              "en.41280). Detail : docs/maintenance/2026-09-28-etude-outils/"
              "05-lecture-reference-manual.md")
REF_NZ = (REF_MANUAL + ". Entree `nz` : renvoie la valeur de `source` si elle "
          "n'est pas `na` ; si elle est `na`, renvoie zero, ou l'argument "
          "`replacement` lorsqu'il est fourni")
REF_NA = (REF_MANUAL + ". Entree `na()` : renvoie `true` si `x` est `na`, "
          "`false` sinon")
REF_NA_IGNORED = (REF_MANUAL + ". Entrees `ta.highest`, `ta.lowest`, "
                  "`ta.highestbars`, `ta.lowestbars`, `ta.sma` : les valeurs "
                  "`na` de la serie `source` sont ignorees")


def _exploration(values, basis, missing_proof):
    """A series whose expectation is NOT established: the candidate value is
    kept as a named variant, the engine result is only observed."""
    return {"status": lib.EXPLORATION, "provenance": basis,
            "missing_proof": missing_proof,
            "variants": {"candidate": values}}


def expected_p1(times, typed, function_variant):
    three = _constant(times, 3.0)
    if typed:
        series = {"TOTAL": _exploration(
            three,
            "valeur candidate : trois iterations, par application de la regle "
            "de la borne incluse (" + DOC_LOOPS + ") a un compteur annote",
            "la forme `for int i = ...` n'apparait ni dans le gabarit de "
            "syntaxe ni dans les exemples de la page lue ; elle n'y est ni "
            "autorisee ni interdite. Indice historique seulement : des sources "
            "contenant cette forme ont ete compiles par TradingView (runs "
            "enregistres du workspace), ce qui ne fixe pas la valeur de cette "
            "fixture. Preuve manquante : " + TV_FIXTURE)}
    else:
        series = {"TOTAL": _established(
            three, "valeur derivee a la main, trois iterations pour 0, 1 et 2 ; "
                   + DOC_LOOPS)}
    if function_variant:
        series["EMPTY"] = _exploration(
            _constant(times, 0.0),
            "valeur candidate : la boucle est gardee par `if n > 0`, aucun "
            "tour pour n = 0",
            "meme reserve que TOTAL sur le compteur annote. Preuve manquante : "
            + TV_FIXTURE)
    return series


def expected_p2(times, part):
    series = {
        "GUARDED": _established(
            _constant(times, 0.0),
            "valeur derivee a la main : l'operande gauche de `and` est faux, "
            "le droit n'est pas evalue ; " + DOC_LAZY),
        "EITHER": _established(
            _constant(times, 1.0),
            "valeur derivee a la main : l'operande gauche de `or` est vrai, "
            "le droit n'est pas evalue ; " + DOC_LAZY),
        "PICKED": _exploration(
            _constant(times, -1.0),
            "valeur candidate : la condition est fausse, la seconde branche "
            "est retenue. Le guide de migration vers v5 dit l'operateur `?:` "
            "evalue paresseusement ; le guide vers v6 le corrobore pour v5",
            "aucun enonce v6 explicite sur la non-evaluation de la branche non "
            "retenue, et le cas d'un `array.get()` sur tableau vide dans cette "
            "branche n'est pas documente. Preuve manquante : enonce officiel "
            "v6 ou " + TV_FIXTURE),
    }
    return {part: series[part]}


def expected_p3(times):
    unverified = ("non verifie par la recherche documentaire du %s. Preuve "
                  "manquante : enonce officiel ou " % CONSULTED + TV_FIXTURE)
    return {
        "A_IS_NA": _established(
            _constant(times, 1.0),
            "valeur derivee a la main : le champ `float price = na` non fourni "
            "prend sa valeur par defaut declaree, qui est `na` (" + DOC_DEFAULT
            + ") ; " + REF_NA + ". Attendu etabli le 2026-09-28 par la "
            "lecture du Reference Manual ; il etait auparavant en exploration"),
        "A_NZ": _established(
            _constant(times, -2.0),
            "valeur derivee a la main : le champ vaut `na` (" + DOC_DEFAULT
            + ") ; " + REF_NZ + ". Attendu etabli le 2026-09-28 par la "
            "lecture du Reference Manual ; il etait auparavant en exploration"),
        "A_TOUCHES": _established(
            _constant(times, 0.0),
            "valeur derivee a la main : champ `int touches = 0` non fourni ; "
            + DOC_DEFAULT),
        "B_DELTA": _exploration(
            _constant(times, 0.0),
            "valeur candidate : `b.price` recoit `close` par argument "
            "positionnel de `new()` sur chaque barre",
            "arguments positionnels de `new()` : " + unverified),
        "B_TOUCHES": _exploration(
            _constant(times, 2.0),
            "valeur candidate : deux appels de `bump()` sur un objet recree a "
            "chaque barre. `+=` sur un champ figure dans un exemple officiel "
            "(page language/objects), sans enonce de regle",
            "le passage par reference d'un objet en argument de methode n'est "
            "pas enonce dans les pages lues (seule l'assignation par "
            "reference l'est). Preuve manquante : enonce officiel ou "
            + TV_FIXTURE),
        "FIRST_PRICE": _exploration(
            _constant(times, 1.5),
            "valeur candidate : objet place dans un tableau `var` a la "
            "premiere barre, relu ensuite",
            "persistance d'un tableau `var` d'objets : " + unverified),
        "FIRST_TOUCHES": _exploration(
            _constant(times, 7.0),
            "valeur candidate : second champ du meme objet",
            "persistance d'un tableau `var` d'objets : " + unverified),
        "SIZE": _exploration(
            _constant(times, 1.0),
            "valeur candidate : un seul `array.push` sous `barstate.isfirst`",
            "persistance d'un tableau `var` et `barstate.isfirst` : "
            + unverified),
    }


def expected_p4(dataset_path):
    _, closes, _, _, times = ref.load_dataset(dataset_path)
    math = ("calcule par tools/tests/ref_indicators.py (implementation "
            "independante) a partir du fichier de donnees seul ; nature de "
            "l'attendu : contrat mathematique local, PAS une correspondance "
            "TradingView (" + NO_REFERENCE + " pour `ta.sma` et `ta.ema`)")
    series = {}
    for n in (1, 5, 20):
        series["SMA%d" % n] = _established(
            _points(times, ref.ref_sma(closes, n)),
            math + " ; contrat : moyenne arithmetique des %d dernieres "
                   "cloches, `na` tant que %d barres ne sont pas disponibles"
                   % (n, n))
        series["EMA%d" % n] = {
            "status": lib.ESTABLISHED,
            "provenance": math + " ; contrat : recurrence alpha = 2 / (length "
                                 "+ 1). La convention d'initialisation differe "
                                 "selon les implementations : les deux sont "
                                 "calculees et la concordance nomme celle qui "
                                 "est observee",
            "variants": {
                "first_value_seed": _points(times, ref.ref_ema_first_value_seed(closes, n)),
                "sma_seed": _points(times, ref.ref_ema_sma_seed(closes, n)),
            },
        }
    series["PREV1"] = _established(
        _points(times, ref.ref_prev(closes)),
        math + " ; contrat : `close[1]`, `na` sur la premiere barre ; "
        + DOC_HISTORY)
    prev3 = [None, None, None] + list(closes[:-3])
    series["PREV3"] = _established(
        _points(times, prev3),
        "calcul direct a partir du fichier de donnees ; contrat : `close[3]`, "
        "`na` sur les trois premieres barres ; " + DOC_HISTORY)
    return series


def expected_p7(dataset_path):
    data, closes, _, _, times = ref.load_dataset(dataset_path)
    scale = data["descriptor"].get("price_scale", 100)
    opens = [b["o"] / scale for b in data["bars"]]
    direct = "calcul direct a partir du fichier de donnees"
    even_close = [c if i % 2 == 0 else None for i, c in enumerate(closes)]
    return {
        "UP_FLAG": _established(
            _points(times, [1.0 if c > o else 0.0 for c, o in zip(closes, opens)]),
            direct + " : 1 lorsque la cloture depasse l'ouverture, sinon 0 ; "
            + DOC_PLOT_BOOL),
        "ALWAYS_NA": _established(
            _points(times, [None] * len(times)),
            "contrat du normaliseur pws-pinets-norm-v2 : `na` est restitue `null`"),
        "DUP": {
            "status": lib.EXPLORATION,
            "match": "title-and-suffixes",
            "provenance": direct + " pour les deux series de valeurs ; le NOM "
                                   "des cles n'a pas d'attendu independant",
            "missing_proof": "aucune reference independante ne fixe la facon "
                             "dont deux plots de meme titre doivent etre "
                             "nommes dans une restitution locale ; "
                             "TradingView les affiche tous les deux",
            "variants": {"close": _points(times, closes),
                         "even_bars_close": _points(times, even_close)},
        },
    }


NO_DOC = ("aucun enonce dans les pages officielles lues le %s ; %s"
          % (CONSULTED, NO_REFERENCE))


def _window(values, i, n):
    return values[i - n + 1:i + 1] if i >= n - 1 else None


def ref_extreme(values, n, pick):
    out = []
    for i in range(len(values)):
        w = _window(values, i, n)
        out.append(None if w is None else pick(w))
    return out


def ref_extreme_bars(values, n, pick, newest, sign):
    """Offset of the extreme inside the window: 0 on the current bar."""
    out = []
    for i in range(len(values)):
        w = _window(values, i, n)
        if w is None:
            out.append(None)
            continue
        target = pick(w)
        ages = [len(w) - 1 - j for j, v in enumerate(w) if v == target]
        age = min(ages) if newest else max(ages)
        out.append(float(sign * age) if age else 0.0)
    return out


def ref_pivot(values, left, right, high, equal_left, equal_right):
    """Value of the candidate `right` bars back when it is an extreme of its
    neighbourhood; ties admitted or not on each side."""
    out = []
    for i in range(len(values)):
        c = i - right
        if c - left < 0:
            out.append(None)
            continue
        v = values[c]
        def beats(other, equal_ok):
            if other == v:
                return equal_ok
            return other < v if high else other > v
        ok = all(beats(values[k], equal_left) for k in range(c - left, c)) and \
            all(beats(values[k], equal_right) for k in range(c + 1, c + right + 1))
        out.append(v if ok else None)
    return out


def expected_p5_extrema(dataset_path):
    _, closes, _, _, times = ref.load_dataset(dataset_path)
    math = ("calcul direct a partir du fichier de donnees ; nature de "
            "l'attendu : contrat mathematique local, PAS une correspondance "
            "TradingView")
    series = {
        "HIGHEST5": _established(
            _points(times, ref_extreme(closes, 5, max)),
            math + ". Les premieres barres sont `na` : enonce par un exemple "
                   "de la documentation officielle pour `ta.highest` (User "
                   "Manual v6, language/execution-model, consulte le %s)."
                   % CONSULTED + CAVEAT),
        "LOWEST5": _established(
            _points(times, ref_extreme(closes, 5, min)),
            math + ". Les premieres barres `na` ne sont documentees que pour "
                   "`ta.highest` ; leur extension a `ta.lowest` est une "
                   "symetrie retenue dans ce contrat local"),
    }
    for title, pick in (("HIGHESTBARS5", max), ("LOWESTBARS5", min)):
        series[title] = {
            "status": lib.EXPLORATION,
            "provenance": "valeurs candidates calculees a partir du fichier de "
                          "donnees. Seul le cas ou l'extreme est sur la barre "
                          "courante est documente (decalage nul, FAQ officielle "
                          "times-dates-and-sessions, consultee le %s)" % CONSULTED,
            "missing_proof": "signe du decalage et barre retenue en cas "
                             "d'egalite : " + NO_DOC + ". Preuve manquante : "
                             "entree du Reference Manual ou " + TV_FIXTURE,
            "variants": {
                "negative_newest_tie": _points(times, ref_extreme_bars(closes, 5, pick, True, -1)),
                "negative_oldest_tie": _points(times, ref_extreme_bars(closes, 5, pick, False, -1)),
                "positive_newest_tie": _points(times, ref_extreme_bars(closes, 5, pick, True, 1)),
                "positive_oldest_tie": _points(times, ref_extreme_bars(closes, 5, pick, False, 1)),
            },
        }
    return series


def expected_p5_pivots(dataset_path):
    _, closes, _, _, times = ref.load_dataset(dataset_path)
    series = {}
    for title, left, right, high in (("PIVOTHIGH_2_2", 2, 2, True),
                                     ("PIVOTLOW_2_2", 2, 2, False),
                                     ("PIVOTHIGH_3_1", 3, 1, True),
                                     ("PIVOTLOW_3_1", 3, 1, False)):
        series[title] = {
            "status": lib.EXPLORATION,
            "provenance": "valeurs candidates calculees a partir du fichier de "
                          "donnees. La documentation lue dit que la fonction "
                          "renvoie `na` hors des barres de pivot et confirme le "
                          "pivot apres un nombre de barres specifie (FAQ "
                          "officielle visuals et page repainting, consultees "
                          "le %s)" % CONSULTED,
            "missing_proof": "traitement des egalites a gauche et a droite, et "
                             "designation de `rightbars` comme delai de "
                             "confirmation : " + NO_DOC + ". Preuve manquante : "
                             "entree du Reference Manual ou " + TV_FIXTURE,
            "variants": {
                "strict_both_sides": _points(times, ref_pivot(closes, left, right, high, False, False)),
                "equal_admitted_left": _points(times, ref_pivot(closes, left, right, high, True, False)),
                "equal_admitted_right": _points(times, ref_pivot(closes, left, right, high, False, True)),
                "equal_admitted_both_sides": _points(times, ref_pivot(closes, left, right, high, True, True)),
            },
        }
    return series


def expected_p5_na_window(dataset_path):
    _, closes, _, _, times = ref.load_dataset(dataset_path)
    src = [None if i % 7 == 3 else c for i, c in enumerate(closes)]
    series = {"SRC": _established(
        _points(times, src),
        "calcul direct a partir du fichier de donnees : `na` lorsque "
        "`bar_index %% 7 == 3`, sinon la cloture ; `bar_index` vaut 0 sur la "
        "premiere barre (connaissance du langage, non reverifiee le %s)"
        % CONSULTED)}
    for title, pick in (("HIGHEST5", max), ("LOWEST5", min)):
        series[title] = {
            "status": lib.EXPLORATION,
            "provenance": "valeurs candidates calculees a partir du fichier de "
                          "donnees, selon trois conventions possibles",
            "missing_proof": NA_WINDOW_PROOF,
            "variants": {k: _points(times, v) for k, v in
                         _na_window_variants(src, pick).items()},
        }
    return series


def _na_window_variants(src, pick):
    ignored, poisoned, reset = [], [], []
    for i in range(len(src)):
        w = _window(src, i, 5)
        if w is None:
            ignored.append(None); poisoned.append(None); reset.append(None)
            continue
        real = [v for v in w if v is not None]
        ignored.append(pick(real) if real else None)
        poisoned.append(pick(w) if len(real) == len(w) else None)
        tail = []
        for v in reversed(w):
            if v is None:
                break
            tail.append(v)
        reset.append(pick(tail) if tail else None)
    last_n = []
    for i in range(len(src)):
        real = [v for v in src[:i + 1] if v is not None][-5:]
        last_n.append(pick(real) if len(real) == 5 and i >= 4 else None)
    return {"na_ignored": ignored, "na_in_window_gives_na": poisoned,
            "restart_after_na": reset, "last_n_non_na_values": last_n}


NA_WINDOW_PROOF = (
    "enonce officiel : " + REF_NA_IGNORED + ". Cet enonce ecarte la "
    "convention `na_in_window_gives_na`. Il ne dit pas si la fenetre reste "
    "celle des `length` dernieres barres (`na_ignored`) ou s'etend aux "
    "`length` dernieres valeurs non `na` (`last_n_non_na_values`), lecture "
    "que l'entree `ta.ema` enonce pour elle-meme. La convention "
    "`restart_after_na` n'est decrite par aucune entree lue. Preuve "
    "manquante pour choisir entre les deux lectures : " + TV_FIXTURE)


def synthetic_series(n):
    """The periodic series of p5_ties_synthetic.pine: independent of any
    market data, so the same fixture can be observed on any chart."""
    s = [float(PLATEAU_CLOSES[i % 30]) for i in range(n)]
    s_na = [None if (i % 30) % 7 == 3 else v for i, v in enumerate(s)]
    return s, s_na


def synthetic_candidates(n):
    """{title: {variant: values}} for the synthetic fixture."""
    s, s_na = synthetic_series(n)
    out = {}
    for title, pick in (("HIGHESTBARS5", max), ("LOWESTBARS5", min)):
        out[title] = {
            "negative_newest_tie": ref_extreme_bars(s, 5, pick, True, -1),
            "negative_oldest_tie": ref_extreme_bars(s, 5, pick, False, -1),
            "positive_newest_tie": ref_extreme_bars(s, 5, pick, True, 1),
            "positive_oldest_tie": ref_extreme_bars(s, 5, pick, False, 1)}
    for title, left, right, high in (("PIVOTHIGH_2_2", 2, 2, True),
                                     ("PIVOTLOW_2_2", 2, 2, False),
                                     ("PIVOTHIGH_3_1", 3, 1, True)):
        out[title] = {
            "strict_both_sides": ref_pivot(s, left, right, high, False, False),
            "equal_admitted_left": ref_pivot(s, left, right, high, True, False),
            "equal_admitted_right": ref_pivot(s, left, right, high, False, True),
            "equal_admitted_both_sides": ref_pivot(s, left, right, high, True, True)}
    out["HIGHEST5_NA"] = _na_window_variants(s_na, max)
    out["LOWEST5_NA"] = _na_window_variants(s_na, min)
    return out


def expected_p5_synthetic(dataset_path):
    _, _, _, _, times = ref.load_dataset(dataset_path)
    n = len(times)
    s, _ = synthetic_series(n)
    built = ("calcul direct a partir du motif ecrit dans le source ; "
             "independant de toute donnee de marche ; `bar_index` vaut 0 sur "
             "la premiere barre (connaissance du langage, non reverifiee le "
             "%s)" % CONSULTED)
    series = {
        "PHASE": _established(_points(times, [float(i % 30) for i in range(n)]), built),
        "S": _established(_points(times, s), built),
    }
    proofs = {
        "HIGHESTBARS5": "signe du decalage et barre retenue en cas d'egalite",
        "LOWESTBARS5": "signe du decalage et barre retenue en cas d'egalite",
        "PIVOTHIGH_2_2": "traitement des egalites et delai de confirmation",
        "PIVOTLOW_2_2": "traitement des egalites et delai de confirmation",
        "PIVOTHIGH_3_1": "traitement des egalites et delai de confirmation",
        "HIGHEST5_NA": "comportement avec une valeur `na` dans la fenetre",
        "LOWEST5_NA": "comportement avec une valeur `na` dans la fenetre",
    }
    for title, variants in sorted(synthetic_candidates(n).items()):
        series[title] = {
            "status": lib.EXPLORATION,
            "provenance": "valeurs candidates calculees a partir du motif "
                          "ecrit dans le source, selon les conventions nommees",
            "missing_proof": NA_WINDOW_PROOF if title.endswith("_NA") else (
                proofs[title] + " : les entrees du Reference Manual lues le "
                "2026-09-28 (`ta.highestbars`, `ta.lowestbars`, "
                "`ta.pivothigh`, `ta.pivotlow`) ne le precisent pas. Preuve "
                "manquante : " + TV_FIXTURE),
            "variants": {k: _points(times, v) for k, v in variants.items()},
        }
    return series


DOC_INPUT = ("documentation officielle, User Manual v6, page concepts/inputs, "
             "consultee le %s : `defval` est la valeur par defaut affectee a "
             "la variable d'input." % CONSULTED + CAVEAT)


def expected_p6(dataset_path, overridden):
    _, closes, _, _, times = ref.load_dataset(dataset_path)
    math = ("calcule par tools/tests/ref_indicators.py ou directement a partir "
            "du fichier de donnees ; contrat mathematique local")
    defaults = {"SMA_LEN": _points(times, ref.ref_sma(closes, 5)),
                "SCALED": _points(times, [c * 2.0 for c in closes])}
    series = {"SRC": _established(
        _points(times, closes),
        "calcul direct a partir du fichier de donnees : `input.source(close)` "
        "sans substitution ; " + DOC_INPUT)}
    if not overridden:
        for name, values in defaults.items():
            series[name] = _established(values, math + " avec les valeurs par "
                                        "defaut declarees (5 et 2.0) ; " + DOC_INPUT)
        return series
    replaced = {"SMA_LEN": _points(times, ref.ref_sma(closes, 3)),
                "SCALED": _points(times, [c * 0.5 for c in closes])}
    for name in defaults:
        series[name] = {
            "status": lib.EXPLORATION,
            "provenance": math + ". Les substitutions (Length = 3, Multiplier "
                          "= 0.5) sont passees par la configuration de "
                          "l'executeur, designees par le titre de l'input",
            "missing_proof": "la designation d'un input par son titre est une "
                             "interface de l'executeur et du moteur, pas une "
                             "regle du langage : aucune reference independante "
                             "ne la fixe. Le resultat dit seulement si la "
                             "substitution a ete appliquee",
            "variants": {"overrides_applied": replaced[name],
                         "defaults_kept": defaults[name]},
        }
    return series


P7_EXPLORATIONS = [
    {"topic": "alertes (`alert()`, `alertcondition()`) sur barres historiques",
     "missing_proof": "aucun attendu independant : sur TradingView une alerte "
                      "ne se declenche qu'en temps reel ; ce que doit contenir "
                      "la restitution d'une execution historique locale n'est "
                      "fixe par aucune reference autorisee"},
    {"topic": "objet graphique (`label.new`) et canaux internes",
     "missing_proof": "le normaliseur exclut les objets du contrat ; seule la "
                      "presence de cles internes est observee"},
    {"topic": "determinisme",
     "missing_proof": "aucune : deux executions du meme cas doivent donner "
                      "la meme empreinte de restitution ; verifie par la campagne"},
]

CASES = [
    ("P1-typed-counter", "P1", "p1_typed_counter.pine", LCG60,
     lambda ds, t: expected_p1(t, True, False), []),
    ("P1-untyped-counter", "P1", "p1_untyped_counter.pine", LCG60,
     lambda ds, t: expected_p1(t, False, False), []),
    ("P1-typed-counter-in-function", "P1", "p1_typed_counter_in_function.pine", LCG60,
     lambda ds, t: expected_p1(t, True, True), []),
    ("P2-lazy-and", "P2", "p2_lazy_and.pine", LCG60,
     lambda ds, t: expected_p2(t, "GUARDED"), []),
    ("P2-lazy-or", "P2", "p2_lazy_or.pine", LCG60,
     lambda ds, t: expected_p2(t, "EITHER"), []),
    ("P2-lazy-ternary", "P2", "p2_lazy_ternary.pine", LCG60,
     lambda ds, t: expected_p2(t, "PICKED"), []),
    ("P3-udt-collections", "P3", "p3_udt_collections.pine", LCG60,
     lambda ds, t: expected_p3(t), []),
    ("P4-core-lcg60", "P4", "p4_core_lengths.pine", LCG60,
     lambda ds, t: expected_p4(ds), []),
    ("P4-core-constant", "P4", "p4_core_lengths.pine",
     CASES_REL + "/datasets/constant-30.json", lambda ds, t: expected_p4(ds), []),
    ("P4-core-monotone", "P4", "p4_core_lengths.pine",
     CASES_REL + "/datasets/monotone-30.json", lambda ds, t: expected_p4(ds), []),
    ("P4-core-gapped", "P4", "p4_core_lengths.pine",
     CASES_REL + "/datasets/gapped-30.json", lambda ds, t: expected_p4(ds), []),
    ("P7-outputs", "P7", "p7_outputs.pine", LCG60,
     lambda ds, t: expected_p7(ds), P7_EXPLORATIONS),
    ("P5-extrema-gapped", "P5", "p5_extrema.pine",
     CASES_REL + "/datasets/gapped-30.json", lambda ds, t: expected_p5_extrema(ds), []),
    ("P5-extrema-plateau", "P5", "p5_extrema.pine",
     CASES_REL + "/datasets/plateau-30.json", lambda ds, t: expected_p5_extrema(ds), []),
    ("P5-pivots-gapped", "P5", "p5_pivots.pine",
     CASES_REL + "/datasets/gapped-30.json", lambda ds, t: expected_p5_pivots(ds), []),
    ("P5-pivots-plateau", "P5", "p5_pivots.pine",
     CASES_REL + "/datasets/plateau-30.json", lambda ds, t: expected_p5_pivots(ds), []),
    ("P5-na-window", "P5", "p5_na_window.pine",
     CASES_REL + "/datasets/gapped-30.json", lambda ds, t: expected_p5_na_window(ds), []),
    ("P5-ties-synthetic", "P5", "p5_ties_synthetic.pine", LCG60,
     lambda ds, t: expected_p5_synthetic(ds), []),
    ("P6-inputs-defaults", "P6", "p6_inputs.pine", LCG60,
     lambda ds, t: expected_p6(ds, False), []),
    ("P6-inputs-overridden", "P6", "p6_inputs.pine", LCG60,
     lambda ds, t: expected_p6(ds, True), []),
]

CONFIGS = {"P6-inputs-overridden": CASES_REL + "/configs/p6_overrides.json"}

ROLES = {
    "P1-typed-counter": "compteur de boucle type : construction a observer",
    "P1-untyped-counter": "temoin diagnostique du cas type, sans annotation",
    "P1-typed-counter-in-function": "compteur type dans une fonction, boucle gardee",
}


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build():
    """Returns {relative_path: text} of every generated file."""
    files = {}
    for name, (generator, params, maker) in sorted(DATASETS.items()):
        files["%s/datasets/%s" % (CASES_REL, name)] = dataset_text(
            generator, params, maker(params["bars"]))
    return files


def build_expected_and_manifest(dataset_texts):
    files = {}
    import hashlib
    entries = []
    for case_id, family, source, dataset, maker, explorations in CASES:
        ds_path = lib.resolve(dataset)
        _, _, _, _, times = ref.load_dataset(ds_path)
        doc = {"schema": lib.EXPECTED_SCHEMA, "case": case_id,
               "dataset": dataset, "series": maker(ds_path, times),
               "explorations": explorations}
        rel = "%s/expected/%s.expected.json" % (CASES_REL, case_id)
        files[rel] = dump(doc)
        src_rel = "%s/sources/%s" % (CASES_REL, source)
        if case_id in CONFIGS:
            extra = {"config": CONFIGS[case_id],
                     "config_sha256": lib.sha256_file(lib.resolve(CONFIGS[case_id]))}
        else:
            extra = {}
        entries.append({
            **extra,
            "id": case_id, "family": family,
            "role": ROLES.get(case_id, "essai de capacite generique"),
            "source": src_rel, "source_sha256": lib.sha256_file(lib.resolve(src_rel)),
            "dataset": dataset, "dataset_sha256": lib.sha256_file(ds_path),
            "expected": rel,
            "expected_sha256": hashlib.sha256(files[rel].encode("utf-8")).hexdigest(),
        })
    manifest = {
        "schema": lib.MANIFEST_SCHEMA,
        "purpose": "cas generiques d'essai de capacites PineTS, independants "
                   "de tout produit ; aucun n'est un cas de calibration et "
                   "aucun ne confere de statut gating",
        "independence": "aucun attendu n'est produit par le moteur observe",
        "cases": entries,
    }
    files["%s/cases.json" % CASES_REL] = dump(manifest)
    return files


def main(argv):
    check = "--check" in argv
    stale = []
    datasets = build()
    for rel, text in sorted(datasets.items()):
        path = lib.resolve(rel)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for rel, text in sorted(build_expected_and_manifest(datasets).items()):
        path = lib.resolve(rel)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if check:
        print(json.dumps({"stale": stale}, ensure_ascii=False))
        return 1 if stale else 0
    print(json.dumps({"written": len(datasets) + len(CASES) + 1}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
