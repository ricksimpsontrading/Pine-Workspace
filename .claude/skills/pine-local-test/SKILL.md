---
name: pine-local-test
description: Exécution comportementale locale du source Pine exact via le thin adapter PineTS — observations reproductibles capability-gated. N'est jamais une validation TradingView. Utiliser dans pine-develop/pine-new/pine-release selon applicabilité.
---

# Test comportemental local (PineTS)

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Contrat normatif complet : spec §24.4 (`docs/architecture/BOOTSTRAP_SPEC.md`). Résumé opérationnel :

## Ce que cette skill EST / N'EST PAS

Elle produit des observations reproductibles et, lorsqu'un contrat local le permet, des conclusions localement gating. Elle n'est JAMAIS : une validation TradingView, une autorité sur la sémantique officielle Pine, une preuve universelle de non-repaint, une preuve de parité Strategy Tester/TradingView, une instruction automatique de modification du code. `PINETS_EXECUTION_PASS ≠ TV_VALIDATED`.

## Parcours unique du test local (EXPÉRIMENTAL, copie isolée)

Deux entrées, un seul parcours : `/pine-local-test` et `/pws → Qualité / publication → Test local (PineTS) → choix du script` (route `pine-local-test`, `needs_script`). Tous les textes visibles viennent de l'outillage, dans la langue configurée ; les afficher tels quels. Ne proposer que les actions que `plan.actions` déclare disponibles dans CETTE installation.

1. **Script** : venant du menu, il est déjà choisi. Venant de `/pine-local-test`, utiliser les écrans de choix du script de `menu --json` (`single_script_label` / `continue_label`, ou `script_screens`).
2. **Plan, en lecture seule** : `python3 -m tools.pws_workspace local-test plan --slug <slug>`. Écran « jeu de données » : `dataset_question`, options `datasets[].label` (détails techniques dans `datasets[].details`), plus Retour. `Retour` n'écrit rien.
3. **Dès le choix des données, sans autre question** : `python3 -m tools.pws_workspace local-test work --slug <slug> --dataset <path>`.
   - Crée (ou reprend) la copie de travail sous `.claude/runtime/pine-local-test/work/<slug>/` (le source enregistré n'est jamais modifié), calcule une fois (un seul appel au moteur), puis démarre le suivi automatiquement (processus détaché, une seule instance). Aucune option « Suivre les modifications ».
   - Restituer `latest.state`, `latest.run_id`, `watch.started` et `session.work_source` (le fichier à modifier). `PINETS_EXECUTION_PASS` n'est jamais une validation TradingView.
4. **Actions proposées ensuite**, seulement si disponibles (`plan.actions`) :
   - `chart` vrai : « Ouvrir le graphique » → `local-test view --work [--bar N]` : Vela dans le navigateur habituel (page locale, hors ligne, sans serveur ; aucun appel au moteur ; elle s'actualise dans le même onglet à chaque nouveau résultat). C'est le seul visualiseur.
   - toujours : lire le résultat (`local-test status --wait 120`, `local-test inspect --work --bar N [--wait S] [--compare-run-id <run_id>]`) et arrêter le suivi (`local-test stop`).
   - `chart` vrai, sur demande (« Vérifie dans Vela le RSI à la barre 495 de ce test ») : `local-test observe --run-id <run_id> | --work --bar 495 --series RSI` (voir 5 ter).
   - `chart` faux : ne pas proposer « Ouvrir le graphique ». Une demande explicite (`local-test view` ou `open`) est refusée avec sa raison (code 7, `VELA_ABSENT` ou `VELA_NO_DEPS`, voir `chart_state`) ; rien n'est recalculé, le rapport numérique reste valable.
5. **Modification** (par le titulaire ou par Claude Code dans `work_source`) : les sauvegardes rapprochées sont regroupées ; seule la dernière révision enregistrée est calculée, une fois (suivi automatique de la séance : décision expérimentale du titulaire du 2026-11-23, `docs/architecture/OPERATIONS.md` ; hors séance, `pine-develop` garde sa règle d'inventaire d'impact).
   - **Avant d'examiner le résultat** d'une modification faite dans le cadre de `pine-develop` : `local-test expect --change <facettes> --unchanged <facettes> --note "<inventaire en une ligne>"` (facettes : values, signals, objects, styles) ; l'attente est liée à la révision enregistrée.
   - **Lire** : `status --wait S` puis `inspect --work --bar N` (attente bornée à 600 s). Quatre éléments distincts : `requested` (révision du fichier enregistré), `computing` (révision en calcul), `result` (dernier calcul terminé, réussi ou en échec, avec `relation` : `requested-revision` ou `earlier-revision`) et `last_good` (dernier résultat réussi, daté). Une valeur ou une erreur n'est présentée comme actuelle que si `fresh` est vrai ; sinon `inspect --work` ne donne aucune valeur actuelle, nomme les révisions et l'état réel (`wait.outcome` : `superseded` si une autre sauvegarde est survenue, `timeout`) et donne `last_good_values` étiquetées par leur run et leur date. Ne jamais présenter `last_good_values` comme le résultat de la révision demandée.
   - **Qualification** (`qualification`, calculée sur des résultats déjà obtenus, sans appel au moteur) : run de comparaison nommé (`compared_with`), `compare_runs` (compareRuns du runner ; INCONCLUSIVE expliqué dans `uncertain`), `comparability` (contrôle des deux rapports, sans programme : si `change` vaut `not-comparable`, rien n'est comparé entre les deux runs — ni facette ni divergence — et `comparability.explanation` nomme les runs et la raison), facettes modifiées (`values`, `signals`, `objects`, `styles`, plusieurs possibles ; `presentation-only` seulement pour des différences de style identifiées), `source` (`comment-only` garde chaînes, directives `//@` et indentation significatives), capacités avec `effective_gating`. `expectation_facts` met l'attente déclarée en regard des faits.
   - **Interprétation par Claude Code** : EXPECTED / UNEXPECTED / UNRESOLVED selon la demande et l'inventaire (spec §24.4.9) ; UNRESOLVED dès que `uncertain` n'est pas vide ou que les preuves ne tranchent pas. Une différence n'est ni une régression confirmée, ni une référence acceptée (`ACCEPTED_BEHAVIORAL_BASELINE` : décision explicite seulement), ni une validation TradingView ; aucune conclusion bloquante si une capacité utilisée n'est pas GATING + CURRENT ; aucune correction du Pine pour satisfaire PineTS.
   - `not_captured` dit ce qui n'est pas lisible.
5 ter. **Observation dans Vela, sur demande** : `local-test observe (--run-id <id> | --work) --bar N --series KEY [--timeout S]`. Une page d'observation figée sur le run déplace le curseur de Vela par des événements simulés et écrit dans le titre la valeur de l'**événement de curseur de Vela** (`CrosshairEvent.values`), le panneau et le texte du panneau de données ; PWS relit le titre (AppleScript, réglages inchangés). Réponse corrélée à la demande (`request`), au run, à la série, au panneau et à l'horodatage de la barre ; sinon « not observed » avec la raison (titre ancien, incomplet, cible différente, curseur hors du panneau, Vela non vérifié, délai). Restituer `vela_event_value`, `report_value`, `frame_value`, `equal_to_report` et leurs `sources`. C'est la valeur tenue par Vela, pas le rendu en pixels. Aucun calcul ; avec `--work`, refus si le résultat n'est pas celui de la révision enregistrée.
6. **Échec du calcul** : la page affiche l'erreur et le dernier graphique réussi, identifié comme tel ; `inspect --work` donne l'erreur seulement si elle appartient à la révision demandée, et `last_good` (run, révision, date) reste consultable.
7. **Historique** : « Ouvrir le graphique » d'un test passé → `local-test open --run-id <run_id> [--bar N]` (identique à `view --run-id`) : Vela dans le navigateur, page figée sur ce test (jamais de suivi) ; codes 4 refus de l'annexe, 7 Vela absent ; ouvrir, rouvrir, zoomer ou déplacer le curseur ne fait que consulter. Une annexe absente, altérée ou étrangère donne un refus explicite (code stable) sans recalcul ; le résultat numérique reste valable.
8. **Calcul ponctuel sans suivi**, seulement sur demande explicite : `local-test run --slug <slug> --dataset <path> [--graphics]` (« Préparer le graphique » n'est jamais présélectionné ; code 5 : calcul PASS mais graphique indisponible).

Aucun connecteur Vela n'est installé : `@luxalgo/vela-pinets` exécuterait PineTS une seconde fois dans le navigateur. Vela affiche les séries déjà calculées par l'adaptateur PWS (moteur de relecture `pws`, `tools/vela_view/page/pws-view.js`). La page ne fait que relire le rapport, l'annexe et la copie des données d'une exécution, après les contrôles du lecteur (`tools/pws_workspace/annex_reader.py`, contrat `READER_CONTRACT.md`), et affiche « Objets à l'état final ». Il n'existe plus de visualiseur de terminal (iTerm2, Terminal.app) ni de commande manuelle de secours.

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
