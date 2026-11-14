# MIGRATION — version du cœur, mise à niveau, migrations de données, retour arrière

Document opérationnel (français ; commandes et contrats stables, en anglais). Contrat normatif : spec §55 (idempotence), §19A, §45 (amendements des 2026-11-06).

Trois opérations distinctes, toujours dans cet ordre :

1. **Livraison d'une nouvelle version du cœur** (fichiers : outils, skills, rules, autorités, modèles, installateur, documentation) → `upgrade`.
2. **Application des migrations de données** (configuration, manifestes) → `migrate`.
3. **Retour arrière** → `migrate --rollback` (données) puis `upgrade --rollback` (code).

## Parcours guidé `update` (2026-11-08)

`/pws → Maintenance / configuration → Outils et mises à jour → Mettre à jour Pine-Workspace` (skill `pws-update`, module `tools/pws_workspace/update.py`) enchaîne ces trois opérations sans les remplacer : `update status` (version installée, type d'installation, dernière recherche datée ou « non recherchée », sauvegardes) ; `update check` (recherche explicite des releases stables du dépôt officiel `ricksimpsontrading/Pine-Workspace`, résultat daté, jamais « à jour » sur une erreur ou une absence de release, préversions exclues par défaut, versions comparées numériquement) ; `update fetch` (téléchargement de la release trouvée dans un dossier temporaire hors de l'installation : provenance des actifs — dépôt et tag officiels —, `RELEASE.json` lu d'abord, empreinte SHA-256 de l'archive comparée à la valeur publiée, extraction vérifiée avant toute écriture, manifeste de cœur contrôlé fichier par fichier) ou `update prepare --package <zip ou dossier>` (paquet local hors ligne : intégrité seulement, origine non vérifiée en ligne) ; `update plan --package-dir …` (récapitulatif en lecture seule, lié à une empreinte : versions, origine, changements, conflits, migrations possibles, sauvegardes, relance de Claude Code) ; `update apply --plan-file … --yes` (refus si le plan a changé, si l'installation est l'amont ou s'il reste un conflit ; puis `upgrade`, puis `migrate --plan` exécuté par le **nouveau** code : une étape bloquée arrête la phase de données avant toute migration ; les migrations ne sont appliquées que si elles figurent toutes dans le plan approuvé, sinon le parcours s'arrête après le code et les présente ; puis vérification des fichiers et de la version, et `doctor --json` interprété selon son contrat réel — contenu validé entrée par entrée avant tout verdict (liste non vide de constats portant chacun un identifiant `check` exploitable, une sévérité parmi OK / INFO / WARNING / BLOCKING et un `detail` textuel ; une seule entrée non conforme rend tout le diagnostic inexploitable, sans suppression ni valeur par défaut), code de sortie 1 si et seulement si un constat BLOCKING, des avertissements seuls ne bloquent pas, une exécution impossible, une réponse inexploitable ou non conforme, une liste vide ou un code incohérent avec le résultat ne valent jamais diagnostic réussi) ; `update rollback-info` (ordre et commandes de retour arrière, sauvegardes existantes, limites — ne restaure rien). Les statuts d'issue sont explicites et seul `applied` est une réussite (code de sortie 0) : `refused-before-mutation`, `failed-restored` / `failed-restore-*`, `incomplete`, `stopped-blocked-migrations`, `stopped-unplanned-migrations`, `diagnostic-blocking`, `diagnostic-unavailable`, `applied` ; chaque rapport indique ce qui a été accompli (`done` : code installé et vérifié, migrations appliquées / restantes / bloquées, diagnostic), les sauvegardes (`recovery`) et la prochaine action utile (`next_action`), et ne prétend jamais que rien n'a changé une fois le code installé. L'ensemble « code puis données » n'est **pas** atomique et n'est jamais présenté ainsi ; aucun retour arrière automatique de l'ensemble n'existe. L'amont de développement (aucun manifeste de cœur) peut consulter les releases mais aucune distribution publique ne s'y applique.

**Corrections du 2026-11-13 (mission de correction de l'audit, `docs/maintenance/2026-11-13-corrections-audit/`)** :

- **Fichiers conservés localement** (`keep-local`, par exemple après `pinets install`, `pinets verify --record` ou une recalibration) : la vérification finale les contrôle à part — fichier local inchangé depuis le plan ET nouvelle version intacte à côté (`<chemin>.pws-new`, empreinte du paquet) ; une mise à jour qui ne diffère que par ces fichiers aboutit à `applied`, avec `done.kept_local` et l'invitation à examiner les `.pws-new` ; un nouveau plan du même paquet n'est plus applicable une fois la nouvelle version posée.
- **Étapes récurrentes** : l'approbation porte sur toutes les étapes déclarées par le paquet ; le journal ne retire plus une étape fondée sur l'état réel (m004 revient à chaque version) ; `migrate --plan` du nouveau code décide seul de ce qui est dû. Plusieurs mises à jour successives aboutissent.
- **Réponses validées strictement** : `migrate --plan` (code de sortie, objet, `config_error`, chaque étape : `id`, `blocked` booléen, `detail`, `waits_for`) et `migrate --apply` (`applied`, `errors`, code de sortie cohérent) ; toute réponse inexploitable rend `incomplete`, jamais une réussite ; après l'application, `migrate --plan` est relancé : une étape encore due rend `incomplete`. Toute exception après l'installation du code produit quand même un compte rendu (`done`, `recovery`, `next_action`).
- **Interruptions** : chaque fichier est écrit dans un temporaire puis renommé ; la sauvegarde est complète et marquée `applying` avant la première écriture ; Ctrl-C est intercepté et l'état antérieur restauré puis vérifié. Un arrêt brutal (SIGKILL, coupure d'alimentation) ne peut pas être intercepté : la sauvegarde reste `applying`, `upgrade --plan` et `update plan` la signalent (`interrupted`), et la reprise est explicite — `upgrade --rollback <stamp>` (accepté pour cet état, restauration validée avant toute écriture) ou une nouvelle application du même paquet.
- **Ordre des retours arrière** : chaque sauvegarde porte sa date de création précise ; une sauvegarde plus ancienne est refusée tant qu'une plus récente est encore appliquée (du plus récent au plus ancien) ; une sauvegarde restaurée est marquée `rolled-back`. Le journal des migrations (`pws.config.json`) fait toujours partie de la sauvegarde de migration : un retour arrière retire aussi ses entrées.
- **Rien n'est perdu par un retour arrière** : avant d'écrire, la version actuelle de chaque fichier que la restauration remplace par un contenu différent ou supprime est copiée et vérifiée dans `<sauvegarde>.replaced-<date>/` à côté de la sauvegarde (`PRESERVED.json` les liste ; le rapport donne ce dossier dans `preserved`) ; si cette copie échoue, rien n'est écrit. Une sauvegarde de code qui ne relève pas les migrations présentes à son application fait refuser son retour arrière tant que des migrations sont enregistrées (sauf `--force`). Les liens symboliques ne sont jamais suivis : manifeste de sauvegarde, fichier de verrou, `settings.local.json`.
- **Mode TradingView hérité** (règle F-14 décidée par le titulaire le 2026-11-13) : une écriture de configuration sans rapport ne matérialise jamais le mode par défaut. m001 : sans valeur exploitable dans `pws.config.json`, la valeur héritée valide est reprise ; si les deux valeurs concordent, la migration se fait sans question ; si elles divergent et qu'aucune provenance ne distingue un choix explicite d'une valeur par défaut, le réglage en vigueur est conservé et seule la résolution du conflit est bloquée (m001 bloquée, m003 en attente : la valeur héritée n'est jamais retirée avant) jusqu'au choix du titulaire par `tv-mode <mode>` (ou `config set tv_validation_mode`), qui enregistre sa provenance (`tv_validation_mode_choice`). Le plan présente les deux valeurs et leur origine ; le consulter n'écrit rien ; une fois le choix enregistré et la migration faite, la question ne revient plus.

## Version du workspace

Convention ratifiée le 2026-11-08 : MAJEURE.MINEURE.CORRECTIF (majeure = rupture de compatibilité, mineure = évolution compatible, correctif = correction compatible) ; la première version publique est 2.1.0 ; une version publiée n'est jamais remplacée en silence, une livraison corrigée reçoit un nouveau numéro. Le numéro vit dans `tools/pws_workspace/version.py` seulement ; `VERSION`, `workspace_version` du manifeste de cœur, le tag `v<version>`, le nom du paquet et `RELEASE.json` en dérivent, et l'entrée de tête de `CHANGELOG.md` doit porter le même numéro (contrôlé par `build-release` et par le doctor, contrôle `version-sources`).

`python3 -m tools.pws_workspace version` affiche la version du cœur (`WORKSPACE_VERSION`, `tools/pws_workspace/version.py`), le schéma de configuration et le schéma des manifestes. Chaque installation enregistre la version à laquelle elle a été migrée dans `pws.config.json` (`workspace_version`) et la liste des étapes appliquées (`migrations`). Une installation issue d'une distribution porte aussi son **manifeste de cœur** (`PWS_DISTRIBUTION.json` à la racine : version et empreinte de chaque fichier livré) ; l'installation d'origine, à partir de laquelle la distribution est construite, n'en a pas : elle est l'amont et ne se met pas à niveau par `upgrade`.

## 1. Livraison d'une nouvelle version du cœur (`upgrade`)

Procédure manuelle, sans réseau : télécharger le nouveau paquet (le dossier produit par `build-distribution`, contenant `PWS_DISTRIBUTION.json`), puis depuis l'installation :

```bash
python3 -m tools.pws_workspace upgrade --from "/chemin/du/nouveau paquet" --plan
python3 -m tools.pws_workspace upgrade --from "/chemin/du/nouveau paquet" --apply [--overwrite-local]
```

Le plan (lecture seule) compare chaque fichier du paquet à l'installation et au manifeste de cœur installé :

| Action | Condition | Effet de `--apply` |
|---|---|---|
| `unchanged` | identique | rien |
| `update` | fichier installé = version précédente livrée, nouvelle version différente | remplacé (sauvegardé) |
| `add` | absent de l'installation | ajouté |
| `keep-local` | fichier de cœur **localement mutable** modifié sur place (`tools/pine_exec/PROVENANCE.json`, `calibration/capabilities.json`, `package.json`, `package-lock.json`, `.claude/settings.json`) | conservé ; la nouvelle version est écrite à côté en `<nom>.pws-new` pour revue |
| `conflict` | fichier de cœur modifié localement | **refusé** tant que `--overwrite-local` n'est pas passé ; alors remplacé après sauvegarde |
| `remove` | fichier du cœur retiré par la nouvelle version, non modifié localement | supprimé (sauvegardé) |
| `conflict-rm` | fichier retiré par la nouvelle version mais modifié localement | conservé sauf `--overwrite-local` |

Jamais touchés : `scripts/`, `docs/maintenance/`, `pws.config.json`, `.claude/settings.local.json`, `.claude/runtime/`, `node_modules`, et tout fichier absent des deux manifestes. Tout fichier touché est d'abord copié dans `.claude/runtime/upgrade-backup/<horodatage>/` (avec `MANIFEST.json`) ; une erreur pendant l'application restaure automatiquement cette sauvegarde et le signale. Le manifeste de cœur installé est remplacé par celui du paquet. `install.py` refuse toujours d'écraser une installation existante et renvoie vers cette procédure.

## 2. Migrations de données (`migrate`)

```bash
python3 -m tools.pws_workspace migrate --plan      # lecture seule : étapes applicables, fichiers touchés
python3 -m tools.pws_workspace migrate --apply     # sauvegarde + application dans l'ordre
python3 -m tools.pws_workspace doctor
```

Une migration ne se déduit jamais d'un numéro de version seul : chaque étape vérifie l'état réel et ne s'applique que si nécessaire ; elle est idempotente, sauvegarde avant d'écrire et ne touche jamais `DECISIONS.md`, `validation/`, les runs de recherche, un `PRODUCT.md`, les approbations Claude Code ni aucune clé de `settings.local.json` autre que l'ancienne clé de mode TradingView qu'elle déplace.

| Étape | Condition réelle | Effet |
|---|---|---|
| `m001-tv-mode-to-config` | `.claude/settings.local.json` (fichier réel, jamais un lien) porte encore `env.PWS_TV_VALIDATION_MODE` | sans mode exploitable dans `pws.config.json` : copie la valeur héritée ; valeurs concordantes ou choix explicite du titulaire (`tv_validation_mode_choice`) : conserve la configuration ; divergence sans provenance : **bloquée** jusqu'au choix du titulaire (`tv-mode <mode>`), rien n'est modifié |
| `m003-remove-legacy-tv-key` | clé legacy présente ; attend que m001 soit appliquée (jamais tant que m001 est bloquée) | retire la clé legacy (conservée dans la sauvegarde de migration), préserve toutes les autres clés |
| `m004-record-workspace-version` | `workspace_version` absent ou différent | enregistre la version courante |
| `m005-manifests-v3` | au moins un `scripts/<slug>/SCRIPT.json` en schéma 1 ou 2 | réécrit en schéma 3 : axes de licence conservés (année de création connue préservée, jamais inventée) ; publication séparée en `state` / `privacy` / `mode` ; seul ce qui était **enregistré** est conservé : `tradingview-open|protected|invite-only` → mode correspondant, confidentialité **nulle** (jamais déduite) ; `tradingview-private` → confidentialité privée, mode nul ; `unpublished` → état non publié ; schéma 1 → publication entièrement nulle (les défauts de profil sont des propositions pour un nouveau projet, pas des faits d'un projet migré). Tout nul figure dans les ambiguïtés rapportées. Remplace `m002-manifests-v2` du 2026-11-06. |
| `m006-publication-derivations` | manifeste schéma 3 dont `migration` montre qu'une confidentialité (ou, pour une chaîne v1 → v2 → v3, un mode) a été **déduite** par la version du 2026-11-06 | remet ces valeurs à `null`, trace chaque rectification dans `migration.rectifications` (champ, ancienne valeur, motif, date) ; ne touche jamais une valeur confirmée par le titulaire (`license confirm` → `migration.holder_confirmed`) ; idempotente. |

Une étape bloquée est signalée et ignorée ; une erreur arrête la séquence, la sauvegarde reste disponible.

## 3. Retour arrière

```bash
python3 -m tools.pws_workspace migrate --list-backups
python3 -m tools.pws_workspace migrate --rollback <horodatage>     # données, octet pour octet (restaure aussi pws.config.json ; versions remplacées copiées d'abord dans <sauvegarde>.replaced-<date>/)
python3 -m tools.pws_workspace upgrade --list-backups
python3 -m tools.pws_workspace upgrade --rollback <horodatage>     # code : fichiers restaurés, ajouts retirés, manifeste de cœur précédent rétabli
```

`upgrade --rollback` **refuse** tant que des migrations de données enregistrées après la mise à niveau sont encore appliquées (il indique lesquelles) : revenir d'abord sur les données, puis sur le code, pour que les deux restent cohérents (`--force` outrepasse, à vos risques). L'ordre est établi par comparaison avec la liste des migrations enregistrées au moment de la mise à niveau (`migrations_at_apply` dans le manifeste de sauvegarde), jamais par l'horloge : deux opérations dans la même seconde restent ordonnées. Les sauvegardes sont conservées dans l'espace éphémère : les protéger comme le reste du runtime si une reconstruction doit rester possible.

### Garanties des sauvegardes et des opérations mutantes (corrigées le 2026-11-06 après vérification indépendante)

- **Confinement physique** : chaque chemin lu ou écrit par `upgrade` (paquet, installation, sauvegardes, copies `.pws-new`, manifestes) est résolu physiquement avec les primitives partagées du cœur ; un dossier ou un fichier en lien symbolique sur la chaîne, un chemin qui sort de sa racine, un emplacement de sauvegarde symlinké ou une entrée de manifeste invalide **refusent le plan entier avant toute mutation** et sont listés (jamais ignorés en silence).
- **Sauvegardes uniques** : dossier créé exclusivement avec un nom unique (horodatage + suffixe aléatoire), jamais réutilisé, même dans la même seconde ; copies vérifiées par empreinte avant la première mutation ; manifeste écrit avant la mutation puis marqué `applied`.
- **Sérialisation** : `upgrade --apply|--rollback` et `migrate --apply|--rollback` prennent le même verrou (`.claude/runtime/pws-mutation.lock`) ; une opération concurrente est refusée avec un message explicite, jamais entrelacée.
- **Restauration validée avant toute écriture, puis vérifiée** (corrigé le 2026-11-06 après la seconde vérification indépendante ; module partagé `tools/pws_workspace/restore.py`, utilisé par `upgrade --rollback`, par la restauration automatique après un échec de `upgrade --apply` et par `migrate --rollback`) : sous le verrou partagé, l'ensemble de la restauration est d'abord validé — manifeste, chemins et confinement physique (côté installation et côté sauvegarde), destinations, présence et empreinte de chaque copie nécessaire ; **une seule entrée invalide refuse toute la restauration** (`stage: refused`, `ok: false`, « nothing changed ») : aucun fichier installé n'est remplacé, créé ni supprimé. Ensuite seulement, les fichiers sont copiés et chaque copie est vérifiée à nouveau ; le succès (`stage: verified`) n'est déclaré que si l'état restauré correspond au manifeste ; une erreur survenue pendant l'exécution malgré une validation réussie est signalée comme restauration incomplète (`stage: incomplete`, écarts listés) et la sauvegarde est conservée pour un nouvel essai. `migrate --apply` ne restaure jamais automatiquement : il s'arrête à la première étape en échec et conserve la sauvegarde pour un `migrate --rollback` explicite.
- **Confirmations** : `python3 -m tools.pws_workspace license confirm --slug <slug> [--state …] [--privacy …] [--mode …] [--created-year …]` enregistre des faits confirmés par le titulaire ; ils sont listés dans `migration.holder_confirmed` et aucune rectification ne les remet en cause.

## Nouvelle installation vs installation existante

- Nouvelle installation : `install.py` (voir `INSTALL.md`) → `init` écrit `pws.config.json` (anglais présélectionné, identité à renseigner, mode TradingView `manual`) ; le manifeste de cœur est copié.
- Installation existante : jamais de réinstallation par-dessus ; `upgrade --plan/--apply` puis `migrate --plan/--apply`. L'installation d'origine (amont) se met à jour par son propre dépôt ; `init --language fr --copyright-holder "…" --alias "…"` puis `migrate --apply` y ont préservé la langue, l'identité, les produits, les preuves et les réglages le 2026-11-06.

## Essais réalisés (2026-11-06, tests `tools/tests/test_upgrade.py` et `test_migration.py`)

Troisième série, après la seconde vérification indépendante (ordre des restaurations), pour `upgrade` et `migrate`, avec comparaison du contenu et de la présence / absence de chaque fichier avant et après chaque refus : copie de sauvegarde altérée placée en dernière position derrière des entrées valides dont des suppressions (refus avant toute mutation, fichier ajouté toujours présent, fichier retiré toujours absent) ; copie nécessaire manquante ; entrée sortant du périmètre ajoutée après les entrées valides ; destination installée remplacée par un lien symbolique vers l'extérieur (refus, fichier extérieur intact) ; restauration valide (`verified`, listes `restored` / `removed` exactes) ; restauration automatique après un échec d'application avec sauvegarde devenue inutilisable (refus signalé honnêtement, installation laissée telle qu'au moment de l'échec, sauvegarde conservée, retour arrière explicite ultérieur refusé pour la même raison sans écriture).

Seconde série, après vérification indépendante : dossier `.claude/skills` en lien symbolique vers l'extérieur (plan refusé, fichier extérieur intact, aucune sauvegarde créée) ; fichier de cœur en lien symbolique vers l'extérieur (refusé, intact) ; fichier de paquet symlinké (refusé) ; emplacement de sauvegarde symlinké (refusé avant toute mutation, arbre inchangé) ; entrée de manifeste invalide (plan entier refusé) ; deux applications avec la même horloge (deux sauvegardes distinctes, double retour arrière rétablissant l'état initial) ; collision explicite de nom (aucune réutilisation) ; opération concurrente (refusée pour `upgrade` et `migrate`) ; copie de sauvegarde altérée (retour arrière déclaré non vérifié) ; échec en cours d'application (état antérieur restauré et vérifié) ; ordre code/données dans la même seconde (refus puis réussite après retour des données) ; installation sans manifeste sur une fixture dédiée.

Paquet v2.1.0 construit depuis le cœur, installé par `install.py` dans un dossier temporaire dont le chemin contient des espaces, avec des données utilisateur représentatives (produit FREE, configuration `fr` + identité, note sous `docs/maintenance`, approbations Claude Code, une rule modifiée localement, `PROVENANCE.json` annoté). Second paquet simulant une version 9.9.9 (skill modifiée, document ajouté, deux rules retirées). Résultats : plan correct (update / add / remove / keep-local / conflict-rm) ; refus sans `--overwrite-local` ; application avec conservation de toutes les données utilisateur, `.pws-new` pour le fichier mutable, manifeste et `VERSION` mis à jour ; refus du retour arrière du code tant qu'une migration de données postérieure est enregistrée ; retour arrière complet après celui des données ; échec simulé en cours d'application → état antérieur restauré à l'identique.

## Limites connues

- Les fichiers d'instruction (skills, rules, agents, master, spec) sont rédigés en français ; l'assistant répond dans la langue configurée. Une édition anglaise est un suivi documenté, pas une fonctionnalité livrée.
- Windows : différé. Linux : non vérifié.
- Les rapports historiques de `docs/maintenance` conservent leurs chemins d'origine ; l'index des déplacements (`docs/maintenance/archives/INDEX.md`) permet de les résoudre.
- `upgrade` ne gère pas une installation antérieure aux manifestes de cœur (aucune n'existe en dehors de l'amont).
