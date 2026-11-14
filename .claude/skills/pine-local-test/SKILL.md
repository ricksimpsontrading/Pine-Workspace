---
name: pine-local-test
description: Exécution comportementale locale du source Pine exact via le thin adapter PineTS — observations reproductibles capability-gated. N'est jamais une validation TradingView. Utiliser dans pine-develop/pine-new/pine-release selon applicabilité.
---

# Test comportemental local (PineTS)

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Contrat normatif complet : spec §24.4 (`docs/architecture/BOOTSTRAP_SPEC.md`). Résumé opérationnel :

## Ce que cette skill EST / N'EST PAS

Elle produit des observations reproductibles et, lorsqu'un contrat local le permet, des conclusions localement gating. Elle n'est JAMAIS : une validation TradingView, une autorité sur la sémantique officielle Pine, une preuve universelle de non-repaint, une preuve de parité Strategy Tester/TradingView, une instruction automatique de modification du code. `PINETS_EXECUTION_PASS ≠ TV_VALIDATED`.

## Exécution

```bash
cd tools/pine_exec
node runner.mjs run --source <src.pine> --dataset <dataset.json> [--config cfg.json] --out <run.json>
node runner.mjs matrix --manifest <matrix.json> --out-dir <dir>       # matrice bornée explicite
node runner.mjs compare --a <run1.json> --b <run2.json>               # qualification de régression
```

Le runner applique lui-même l'environnement contrôlé (TZ=UTC, LANG=C, LC_ALL=C). `compare` exige des runs comparables (même dataset, configuration, version PineTS, fingerprint, schéma de normalisation, deux PASS) — sinon `PINETS_INCONCLUSIVE` ; il rend `PINETS_REGRESSION_UNCHANGED/CHANGED` avec les plots divergents. La fraîcheur de calibration de chaque run est DÉRIVÉE du triplet courant et de l'intégrité des artefacts de calibration : un environnement différent (autre machine, autre Node, adapter modifié) dégrade `CURRENT → STALE` pour ce run sans toucher `capability_status`.

- Datasets : locaux uniquement (synthétiques `datasets.mjs gen` ou snapshots importés avec provenance). Aucun fournisseur réseau.
- Sorties temporaires → `.claude/runtime/pine-local-test/` (gitignored). JAMAIS sous `validation/`.
- Artefacts durables (contrats, fixtures, baselines) → `scripts/<slug>/tests/behavioral/`, créés seulement quand ils ont une utilité durable.
- `node_modules` absent (worktree/checkout frais) → `npm ci --ignore-scripts` dans `tools/pine_exec` ; jamais un défaut du source Pine.

## Règles de gate (résumé)

- `effective_gating = capability_status == GATING ET calibration_status == CURRENT` — dérivé, jamais persisté. État courant : `tools/pine_exec/calibration/capabilities.json` (bootstrap : ZÉRO capability GATING — toute conclusion est non gating, à qualifier honnêtement).
- Closed-world : une conclusion ne peut être gating que si `unclassified_tokens` est vide ET toutes les `capabilities_used` matériellement nécessaires sont effectivement gating. Sinon → `PINETS_INCONCLUSIVE`/non gating.
- Axes jamais fusionnés : exécution (`PINETS_EXECUTION_PASS/FAIL`) ≠ observations (`PINETS_REGRESSION_UNCHANGED/CHANGED`, `PINETS_STABILITY_*`) ≠ qualification (`PINETS_EXPERIMENTAL/UNSUPPORTED/INCONCLUSIVE`). `PASS + REGRESSION_CHANGED` est une combinaison valide.
- Régression : classer `EXPECTED` / `UNEXPECTED` / `UNRESOLVED` contre l'objectif et l'inventaire d'impact (spec §24.4.9). `UNRESOLVED` → pas de correction spéculative.
- Frontière de correction (spec §24.4.8) : « Le code serait-il incorrect si PineTS n'existait pas ? » Non ou indéterminable → ne pas toucher au Pine ; qualifier le résultat.
- Baselines : contrat `ACCEPTED_BEHAVIORAL_BASELINE` (spec §24.4.10) — jamais automatique.
- Profondeur proportionnée (spec §24.4.12) : exécution seulement si l'inventaire d'impact ou le périmètre d'un audit la prévoit — smoke run pour une petite correction concernée, comparaison de régression pour un refactor neutre ; matrice bornée uniquement via workflow explicite, jamais par hook, jamais par défaut après une petite modification.
- Upgrade PineTS = maintenance explicite via `pine-tools` (`pinets check-update`, `pinets install <version> --yes`, `pinets rollback`) : jamais d'auto-upgrade ; les calibrations dépendantes passent STALE ; recalibration obligatoire et distincte (spec §24.4.2).
- Réévaluation après un `PINETS_EXECUTION_FAIL` : relancer une exécution locale lorsque l'une des conditions suivantes est vraie : la construction ayant provoqué le dernier échec a changé ou disparu ; la version pinée de PineTS, l'adapter (`executor_fingerprint`), le schéma de normalisation, la configuration d'exécution ou le dataset de référence ont changé ; une capability concernée par la modification est devenue gating ou sa calibration a changé ; la modification touche MTF, historique ou temps réel et une baseline comparable existe ; le titulaire le demande. Sinon, citer le run de référence et la construction bloquante dans l'artefact de suivi.
