---
name: pine-tools
description: Outils intégrés et mises à jour — état de PineTS (local), disponibilité d'une mise à jour (recherche explicite datée), vérification de l'installation, installation d'une version choisie, préparation d'une recalibration, retour à une version sauvegardée utilisable. Aucune mise à jour silencieuse.
---

# Outils et mises à jour (PineTS)

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Cette skill ne gère que PineTS ; la mise à jour de Pine-Workspace lui-même relève de `pws-update` (« Mettre à jour Pine-Workspace », même sous-menu). Seul PineTS est un outil intégré géré. `pinets-cli`, Vela, edge-stats et LuxAlgo MCP ne sont ni installés ni activés : leur place éventuelle est seulement documentée (`tooling-status` → `other_tools`).

## 1. Écran d'état (toujours d'abord, lecture seule)

`python3 -m tools.pws_workspace tooling-status`, puis annoncer **trois informations distinctes**, jamais confondues :

1. **État local** — version installée (`pinets.installed`, avec pin et lockfile), intégrité d'après `artifact_check`, calculé à chaque appel sur cette machine (`match` : artefact installé égal à l'empreinte enregistrée dans `PROVENANCE.json` ; `differs` : le moteur sur disque n'est pas celui installé et calibré, intégrité en échec ; `missing`, `not-recorded`, `not-installed` : le dire avec `artifact_check_note`), calibration (`calibration.current` sur `calibration.capabilities`, `gating`, `freshness`). `provenance_verified_at` n'est que la date écrite dans `PROVENANCE.json` par qui l'a enregistré (livrée telle quelle avec une distribution, mise à jour par aucune commande) : ne jamais la présenter comme une vérification faite sur cette machine. `provenance_pinned` différent de `pinned` : la provenance ne décrit pas le moteur épinglé (signalé par `pinets verify`). `freshness` n'est jamais CURRENT pour un moteur absent ou un artefact différent de l'empreinte enregistrée ; le runner, lui, dérive la fraîcheur de chaque exécution du triplet sans comparer l'artefact (`freshness_basis`). CURRENT qualifie la fraîcheur d'une calibration ; GATING est un statut distinct, jamais déduit de CURRENT : une calibration actuelle ne rend aucune capacité bloquante.
2. **Disponibilité d'une mise à jour** — uniquement d'après `update_check`. `checked_at` nul : dire « non recherchée : on ignore si une version plus récente existe » ; ne jamais dire « à jour », « dernière version » ni « rien à mettre à jour » sans recherche. `checked_at` renseigné : donner `latest`, `result` et `update_available` **avec la date** de la recherche, en précisant que le résultat est réutilisé et réévalué contre le pin courant (`pinned_now`) ; si `pinned_at_check` diffère (installation ou retour arrière depuis la recherche), le dire ; proposer une nouvelle recherche si elle est ancienne. `update_available` n'est vrai que pour une version stable strictement plus récente que le pin : `ahead` (pin plus récent que `latest`) n'est jamais une mise à jour ; `prerelease` (`latest` désigne une préversion) n'est jamais proposée par défaut, l'installer reste un choix explicite ; `unknown` ou `not-comparable` : on ignore. Une recherche en échec (`ok` faux) n'enregistre rien et ne permet jamais de conclure « à jour ».
3. **Points de retour** — `rollback_points` : n'offrir que ceux dont `usable` est vrai (`rollback_points_usable`). Utilisable signifie vérifié : manifeste présent au format courant, complet, chaque empreinte contrôlée sur le contenu sauvegardé (fichiers du moteur et arbre `node_modules` entier, chemins confinés). Un point non utilisable est mentionné avec sa `reason` : disposition manuelle ou ancien format (noms de fichiers sans empreintes) → procédure documentée, jamais cette commande, jamais converti en recalculant les empreintes d'une ancienne sauvegarde ; contenu altéré → ne pas restaurer. Aucun point utilisable → le dire clairement, sans option de retour arrière. Jamais de version fixée en dur : les versions viennent de cette sortie. `rollback_tree_refused` renseigné : l'arborescence des points est un lien symbolique ou sort du workspace — aucun point n'y est listé, écrit ni restauré ; le signaler. `rollback_leftovers` non vide : un retour arrière a été interrompu ou est resté incomplet — le signaler avec `rollback_leftovers_note` (point `before-rollback-*` du même horodatage) ; ne jamais supprimer ces dossiers soi-même.

## 2. Écrans d'actions (textes visibles rendus dans la langue configurée — libellés de référence ci-dessous en français)

```text
Écran 1 : Vérifier l'installation de PineTS · Rechercher une mise à jour · Suite… · Retour
Écran 2 : Installer une version · Préparer une recalibration · Revenir à une version sauvegardée (seulement si un point utilisable existe) · Retour
```

| Libellé | Effet annoncé | Commande | Nature |
|---|---|---|---|
| Vérifier l'installation de PineTS | contrôle pin, lockfile, intégrité du registre, empreinte de l'artefact, fingerprint | `pinets verify` (`--record` : enregistre une première fois l'empreinte de l'artefact dans `PROVENANCE.json`) | lecture seule sauf `--record` ; identité = pin + lockfile + intégrité + artefact + fingerprint, jamais le seul numéro de version |
| Rechercher une mise à jour | interroge le registre npm ; n'installe rien ; enregistre le résultat daté | `pinets check-update` | réseau explicite ; écrit `.claude/runtime/tooling/last-update-check.json` |
| Installer une version | installe la version choisie après avoir sauvegardé un point de retour ; les calibrations actuelles deviennent STALE | `pinets install <version> --yes` | modifie le moteur : point de retour d'abord, `npm install --save-exact --ignore-scripts` puis `npm ci --ignore-scripts`, contrôle du moteur obtenu (pin, lockfile, `node_modules/pinets`, artefact) avant de mettre à jour `PROVENANCE.json` et de passer les calibrations STALE ; sinon échec annoncé avec l'état (`state`) et le point de retour à utiliser (`rollback_point`), rien d'autre de modifié |
| Préparer une recalibration | affiche le plan guidé ; n'exécute rien | `pinets recalibrate-plan` | lecture seule ; la recalibration elle-même est un acte manuel et revu (spec §24.4) ; CURRENT n'est jamais GATING par lui-même |
| Revenir à une version sauvegardée | restaure un point de retour utilisable en deux temps : validation complète du point (manifeste, chemins, chaque empreinte, destinations) et sauvegarde vérifiée du moteur actuel, copie préparée à côté et vérifiée, puis mise en place par renommages et vérification finale du moteur actif (artefact compris) | `pinets rollback <version> --yes` | modifie le moteur ; une seule anomalie refuse tout sans rien changer (`stage: refused`) ; une erreur ou une interruption (Ctrl-C, `interrupted`) pendant les renommages est signalée `incomplete` avec les éléments de récupération conservés (point, point pré-retour, arbres préparé et remplacé), jamais un faux succès ; sans version : le point enregistré par la dernière installation (`previous_pin.rollback_point`), sinon le plus récent point utilisable sauvegardé par une installation pour le pin précédent |

Décrire chaque action comme consultation (vérifier, rechercher, préparer) ou modification du moteur (installer, revenir) ; ne jamais présenter une lecture comme une modification, ni l'inverse.

## 3. Règles

- Jamais de mise à jour au démarrage ; chaque acte est explicite et demandé par le titulaire ; une sélection de menu ne vaut pas autorisation d'installer ni de restaurer.
- Une mise à jour du moteur invalide les calibrations dépendantes (STALE persisté) ; la recalibration est un acte distinct.
- TradingView reste l'autorité de validation ; PineTS est un laboratoire local ; aucun indicateur n'est modifié pour satisfaire une divergence du moteur (spec §24.4.8).
- `pinets install` et `pinets rollback` sauvegardent d'abord le moteur courant dans un point vérifié (format 2 : empreinte de chaque fichier, liens symboliques enregistrés) ; sans point vérifiable, l'installation est refusée avant tout changement. Un ancien point de même version n'est jamais écrasé ni converti : il est conservé tel quel et un nouveau point horodaté est créé à côté ; `PROVENANCE.json` enregistre le nom du point réellement sauvegardé (`previous_pin.rollback_point`).
- Commande de réparation du moteur, partout : `npm ci --ignore-scripts` dans `tools/pine_exec` (jamais `npm ci` seul).
- Après install ou rollback : `pinets verify` puis `python3 -m unittest discover -s tools/tests -t .`.
