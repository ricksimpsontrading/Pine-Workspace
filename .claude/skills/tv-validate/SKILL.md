---
name: tv-validate
description: Validation TradingView réelle d'un script Pine — matrice de tests dérivée du changement réel, preuve liée au SHA-256 du source, modes manual et chrome-experimental. Seule couche qui peut produire un statut TradingView.
---

# Validation TradingView

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

TradingView est la validation empirique finale (master §40, spec §2.6). Aucun résultat local — guard ou PineTS — ne satisfait jamais une étape TradingView.

## 1. Mode

Lire le mode persistant via le contrôleur (configuration `pws.config.json` ; jamais la variable d'environnement) :

```bash
python3 -m tools.pws_workspace tv-mode
```

- `manual` → suivre `MANUAL.md`.
- `chrome-experimental` → suivre `CHROME_EXPERIMENTAL.md` ; toute ambiguïté, login, CAPTCHA, UI inattendue, action non vérifiable ou risque de publication → fallback du run vers manual (le mode persistant reste inchangé ; enregistrer `requested_mode`, `effective_mode`, `fallback_reason`).

## 2. Identité du source AVANT tout run (spec §29.3)

```bash
python3 -m tools.pws_workspace source-fingerprint "scripts/<slug>/<source>.pine"
```

SHA-256, commit Git (ou null), working tree clean/dirty. La preuve centrale est le hash du source. Toute modification du `.pine` après un run rend l'état effectif `stale` : le run reste historique, le nouveau source doit être revalidé.

## 3. Matrice

Dérivée du standard maître (master §35 via INDEX), du type de script, du contexte produit et du changement réel. Jamais un checklist fixe : un test sans objet est N/A, pas une case à cocher. Deux portées distinctes (spec §30.5) : la compilation minimale (résultat de compilation seul, jamais `passed`) et la campagne fonctionnelle (contrôles comportementaux, regroupable sur le source stabilisé selon l'organisation décidée par le titulaire pour le produit). Candidats selon applicabilité : compilation Pine Editor, runtime, historical, realtime, Replay, MTF, changement symbole/timeframe, settings extrêmes, dark/light, objets visuels, alertes, rapport de stratégie, performance/Profiler.

## 4. Frontière PineTS (spec §29.5)

Les résultats `pine-local-test` peuvent aider à préparer la matrice, cibler un scénario, expliquer une anomalie, identifier un risque. Ils ne peuvent PAS satisfaire une étape TradingView, créer une preuve TradingView, modifier le statut TradingView, ni transformer `stale`/`unverified`/`in-progress` en `passed`. Une gate locale légitime bloque AVANT ce workflow ; elle ne crée aucun statut TradingView.

## 5. Enregistrement (spec §51)

- Rapport de run immuable, `schema_version: 2` (verdicts contrôlés par contrôle, identifiants uniques, groupes éventuels — détail dans `MANUAL.md`) : `run_id` collision-resistant, timestamps RFC 3339 UTC, statut ∈ in-progress/passed/failed/partial, source + SHA-256, commit, clean/dirty, requested/effective mode, fallback_reason, matrice appliquée, résultats, anomalies, preuves (chemin sous `evidence/<run_id>/` + type + SHA-256), conclusion.
- Promotion de `validation/current.json` via le protocole atomique du tooling (refus des runs plus anciens, des conflits concurrents et des égalités d'horloge).
- `passed` uniquement si TOUS les contrôles obligatoires applicables ont réellement réussi sur ce hash. Ne conserver que les preuves utiles — un compte rendu précis du titulaire est une observation réelle ; une capture n'est pas une obligation artificielle.
- Publication : hors périmètre de cette skill, toujours (spec §2.8).
