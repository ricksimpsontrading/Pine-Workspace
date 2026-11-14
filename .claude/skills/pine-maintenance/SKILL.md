---
name: pine-maintenance
description: Archives et nettoyage — entretien déterministe des temporaires recréables (liste blanche), import vérifié d'un dossier d'archives externe dans docs/maintenance/archives avec index des déplacements, quarantaine réversible. La suppression d'un dossier source importé est une étape distincte, soumise à une autorisation explicite. Ne supprime jamais une preuve, une décision, un point de retour ni un fichier référencé.
---

# Archives et nettoyage

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

## Écrans (textes visibles, Retour partout)

```text
Écran 1 : Voir le plan d'entretien · Exécuter l'entretien · Suite… · Retour
Écran 2 : Importer des archives · Consulter l'index des archives · Retour
```

| Libellé | Effet | Commande | Nature |
|---|---|---|---|
| Voir le plan d'entretien | liste ce qui serait supprimé ; ne supprime rien | `python3 -m tools.pws_workspace maintenance cleanup` | lecture seule |
| Exécuter l'entretien | supprime uniquement les temporaires recréables de la liste blanche, journalisé | `maintenance cleanup --execute` | suppression limitée, seulement sur ce choix |
| Importer des archives | procédure en étapes distinctes (ci-dessous) ; le chemin du dossier externe est demandé conversationnellement | voir ci-dessous | lecture, puis copie vérifiée, puis index |
| Consulter l'index des archives | lecture de `docs/maintenance/archives/INDEX.md` (déplacements, doublons référencés) | — | lecture seule |

## Entretien (liste blanche)

- Au lancement de session, le hook exécute `maintenance.startup_cleanup` : uniquement les fichiers `*.pyc` rangés directement dans un `__pycache__/` sous `tools/` (le dossier lui-même seulement s'il ne contient rien d'autre), les fichiers `.DS_Store`, et les instantanés de session au format écrit par le hook (`<identifiant>.json` contenant `files`) inutilisés depuis 7 jours. L'ancienneté d'un instantané se mesure sur sa date de dernière modification (sa dernière utilisation), jamais sur sa création ; l'instantané désigné par `latest.json` et celui de la session courante ne sont jamais supprimés, et aucun ne l'est tant que `latest.json` est illisible. Rapide, verrouillé contre un nettoyage concurrent, journalisé (`.claude/runtime/maintenance/cleanup-log.jsonl`), silencieux sans action. Désactivable : `config set maintenance.startup_cleanup false` (réglage « Entretien au lancement » du menu Configuration).
- Protections dans le code : suppression fichier par fichier, octets annoncés exacts ; un fichier utilisateur, un sous-dossier ou un lien rangé dans ces dossiers n'est jamais touché ; un élément cité par son chemin relatif dans un fichier texte suivi par Git est conservé (si ce contrôle est impossible, rien n'est supprimé et une anomalie est signalée) ; un dossier illisible devient une anomalie, jamais un échec du hook.
- Jamais nettoyés automatiquement (hors fichiers `.DS_Store`, artefacts macOS que l'import d'archives ne copie jamais) : contenu des archives et de `docs/maintenance`, sources `.pine`, points de retour (`pinets-rollback`), `pinets-eval`, sorties `pine-local-test`, sauvegardes de migration, exports GitHub, fichiers `*.lock`, tout fichier référencé par un document suivi. Une date ancienne ne qualifie jamais un fichier d'inutile.

## Import d'archives externes — quatre étapes distinctes

```bash
# 1. Plan (lecture seule) : inventaire du dossier externe, références des doublons exacts
python3 -m tools.pws_workspace maintenance archives-plan --source "<dossier externe>" --plan-file <plan.json>
# 2. Copie et vérification des empreintes (écrit sous docs/maintenance/archives/)
python3 -m tools.pws_workspace maintenance archives-import --plan-file <plan.json>
python3 -m tools.pws_workspace maintenance archives-verify --plan-file <plan.json>      # complétude
# 3. Indexation : docs/maintenance/archives/INDEX.md + MANIFEST.json (écrits par l'import, cumulatifs)
# 4. Suppression éventuelle du dossier source — étape séparée, voir ci-dessous
python3 -m tools.pws_workspace maintenance archives-remove-source --plan-file <plan.json> --yes
```

- Le choix « Importer des archives » couvre les étapes 1 à 3 seulement. **Il n'autorise jamais la suppression du dossier source.**
- Chemin de la source : chemin absolu du dossier réel. Relations refusées par le code au plan, à l'import et à la suppression (comparaison par identité physique, donc aussi pour une autre écriture du même dossier) : source égale au workspace, contenue dans le workspace ou le contenant ; source contenue dans une autre installation PWS ou la contenant ; source donnée par un lien symbolique ; cible hors de `docs/maintenance/archives` (un sous-dossier est accepté avec `--target docs/maintenance/archives/<nom>`).
- Le plan est lié au dossier source (identité physique) et à son inventaire (empreinte SHA-256). Un plan d'un format antérieur, modifié, sans entrée ou portant une anomalie bloquante (source manquante, fichier qui écraserait `MANIFEST.json`/`INDEX.md`, destination existante au contenu différent) est refusé. Un fichier de plan neuf par import, hors du dossier source ; ne jamais réutiliser le plan d'un import précédent.
- Liens symboliques, fichiers spéciaux (tube nommé…) et fichiers illisibles : signalés au plan sans le bloquer, jamais suivis ni copiés ; ils bloquent la suppression de la source.
- `MANIFEST.json` et `INDEX.md` (racine de `docs/maintenance/archives`) sont cumulatifs : chaque import y reste listé et résoluble ; relancer le même import met à jour son enregistrement sans le dupliquer ; un index étranger, illisible ou privé de son manifeste n'est jamais écrasé.
- Une copie n'apparaît sous sa destination qu'une fois son empreinte vérifiée : un fichier modifié depuis le plan ou une copie interrompue n'installe rien ; relancer l'import reprend la copie.
- La suppression (étape 4) exige une autorisation explicite du titulaire **nommant le dossier concerné**, donnée après la vérification complète de la copie. Au moment de la suppression, la commande refait l'inventaire complet du contenu ACTUEL de la source et la refuse si un fichier est nouveau, modifié, non copié ou non vérifiable, ou si le dossier a été recréé ou remplacé depuis le plan (détail dans `changes`) ; elle la refuse aussi sans `--yes` et tant que la vérification n'est pas complète. Elle ne supprime ensuite que les fichiers qu'elle vient de vérifier (et les `.DS_Store`), un par un, puis les dossiers vidés — jamais une suppression récursive ; ce qui apparaît pendant l'opération est conservé. `--yes` ne remplace aucune de ces vérifications. Une autorisation déjà donnée pour cette même opération et ce même dossier n'est pas redemandée.
- Doublons exacts (même SHA-256) : une seule copie conservée, les références permettent de retrouver le contenu.
- Fichiers potentiellement inutiles : quarantaine réversible (dossier `quarantine/` sous les archives, inventorié), jamais de suppression définitive sur appréciation incertaine.
- Les anciens rapports gardent leurs chemins d'origine : utiliser l'index des déplacements, ne pas les réécrire.
- Ces archives locales ne remplacent pas une sauvegarde indépendante du disque (repo bare, disque externe, NAS — OPERATIONS.md).
