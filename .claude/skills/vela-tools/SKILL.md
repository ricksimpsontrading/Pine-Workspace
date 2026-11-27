---
name: vela-tools
description: Mise à jour guidée de Vela, le graphique du navigateur des tests locaux (tools/vela_view) — état, recherche, changements et licences, plan vérifié, une confirmation « Appliquer », installation hors ligne depuis les archives vérifiées, contrôles, retour à une version sauvegardée. Seulement dans une installation équipée du composant vela-view. Ne touche jamais PineTS ni ses calibrations.
---

# Vela — mise à jour guidée (EXPÉRIMENTAL)

Langue : répondre dans la langue configurée. Les synthèses viennent de l'outillage (`summary.text`), à afficher telles quelles.

Vela est un visualiseur : il affiche les séries déjà calculées par l'adaptateur PWS. Le mettre à jour ne change ni le moteur PineTS, ni son empreinte, ni les calibrations, ni les résultats ; aucune recalibration ne suit (contrôlé par l'application).

## Parcours (même forme que le guide PineTS)

| Étape | Commande | Nature |
|---|---|---|
| 1. État | `python3 -m tools.pws_workspace vela guide --stage state` | lecture seule : versions installées, pin, lockfile, empreinte du fichier chargé par la page, provenance enregistrée, points de retour vérifiés, dernière recherche datée |
| 2. Recherche | `vela guide --stage search` | réseau explicite (registre npm) ; dernière version stable seulement ; une erreur ne vaut jamais « à jour » ; « déjà à jour » est dit tel quel |
| 3. Préparation et plan | `vela guide [<version exacte>] --stage prepare` (`--accept-license PKG@VERSION=LICENCE` seulement sur décision explicite du titulaire) | téléchargements seulement, hors du workspace : archives npm (intégrité égale au registre et au lockfile), lockfile candidat, installation candidate jetable (scripts désactivés) ; plan : journal des changements de l'archive elle-même, dépendances, licences, contrôle des API nécessaires, analyse du paquet navigateur ; seule l'écriture du plan |
| 3 bis. Sonde | `vela guide --stage probe --plan-file <plan>` | obligatoire si le plan indique `probe_required` (déclarations ambiguës) : la version candidate réellement exécutée dans le navigateur |
| 4. Application | `vela guide --stage apply --plan-file <plan> --yes`, seulement après « Appliquer » | revérification, point de retour vérifié, `npm ci --offline --ignore-scripts` depuis les archives du plan, identité obtenue contre le plan, bascule, provenance, deux derniers points conservés |
| 5. Bilan | synthèse de l'étape 4 | version installée, empreinte du fichier npm installé, point de retour, « aucune recalibration » vérifié ; rien sur le navigateur tant qu'aucun onglet n'a été lu (voir « Deux empreintes ») |
| Retour | `vela rollback [--point <nom>] --yes` | point vérifié entièrement avant toute écriture ; l'état courant est sauvegardé d'abord ; hors ligne |

Règles :

- **Une seule confirmation** : AskUserQuestion avec `summary.confirm` (Appliquer / Annuler), y compris pour un changement de version mineure. « Annuler » : aucune commande. Tout changement de version, de décision de licence ou de l'état installé impose une nouvelle préparation.
- **Licence** : un changement de licence (ou une nouvelle dépendance sous une licence absente de l'arbre actuel) donne `decision_required` ; s'arrêter et présenter les éléments ; ne préparer à nouveau avec `--accept-license` que sur une décision explicite du titulaire portant sur ces éléments.
- **API** : une API nécessaire absente bloque l'application (`blocked`) ; une déclaration ambiguë exige la sonde réussie.
- **Première installation** : sans `PROVENANCE.json`, la préparation établit la provenance depuis le lockfile livré et le fichier extrait de l'archive npm vérifiée ; si la version est déjà la dernière, le plan se limite à enregistrer cette provenance (même confirmation).
- **Points de retour** : `.claude/runtime/vela-rollback/` ; les deux derniers points vérifiés sont conservés ; `vela points` les liste.

## Deux empreintes, jamais confondues

| Empreinte | Ce qu'elle mesure | Où la lire | Exemple de contrôle (essai du 2026-11-23, Vela 0.10.14) |
|---|---|---|---|
| **Fichier npm installé** | SHA-256 de `node_modules/@luxalgo/vela/dist/vela.global.min.js`, tel que publié dans l'archive npm vérifiée | plan (`target.bundle_sha256`), bilan de l'application, `vela guide --stage state`, `PROVENANCE.json` (`bundle.sha256`) | `40dced78…` |
| **Code préparé par PWS** | SHA-256 de la source de la fonction `window.__PWS_VELA` qui emballe ce fichier ; la page la recalcule dans le navigateur avant d'exécuter Vela | dans la page générée à l'ouverture d'un résultat : `index.html` (`integrity.vela_fn_sha256`), début du `?v=` de l'adresse du script ; dans le titre de l'onglet après lecture dans Safari | `b8e159733b2a…` |

- Elles diffèrent toujours par construction. Un même fichier npm donne toujours le même code préparé, mais aucune des deux ne se déduit de l'autre sans calcul : ne jamais annoncer l'une à la place de l'autre.
- Les valeurs ci-dessus sont des exemples. Elles changent avec chaque version : les valeurs à citer sont toujours lues dans les sorties de l'outillage ou dans la page générée, jamais recopiées d'ici.
- L'empreinte du code préparé n'existe qu'une fois la page générée (`local-test open`). Avant, le bilan ne la cite pas.

## Vérification dans le navigateur

Après une application ou un retour : rouvrir un résultat existant (`local-test open --run-id <run_id>`), seulement si le titulaire le demande. Aucun calcul PineTS n'est lancé.

La page n'exécute le JavaScript de Vela et son propre script qu'après avoir vérifié leur contenu. L'empreinte attendue est celle du **code préparé par PWS**, rapportée à la provenance du fichier npm. Un contenu différent n'est jamais exécuté (« INTEGRITY FAIL »), quels que soient le nom du fichier ou l'adresse.

Le titre de l'onglet a la forme `… vela <version> <12 premiers caractères du code préparé> verified | net <n> …` (par exemple `vela 0.10.14 b8e159733b2a verified | net 0`). Il ne contient jamais l'empreinte du fichier npm.

**Observé ou attendu.** Un titre n'est annoncé comme « observé » que si la session l'a effectivement lu dans Safari, par exemple avec `osascript -e 'tell application "Safari" to get name of current tab of front window'` après l'ouverture. On cite alors le texte lu tel quel.
- Sans lecture, on parle du titre « attendu ». Il se forme de la version installée et de l'empreinte du code préparé lue dans la page générée, et on précise que rien n'a été observé dans le navigateur.
- Sans page générée, on dit seulement que la vérification dans le navigateur n'a pas été faite.
- Un titre attendu n'est jamais présenté comme une vérification.
