---
name: pws-update
description: Mise à jour guidée de Pine-Workspace lui-même — version installée, recherche explicite d'une nouvelle version stable sur le dépôt officiel, changements et limites annoncés, préparation depuis la release officielle ou depuis un paquet local, plan avant application, application après confirmation groupée (upgrade puis migrate), retour arrière documenté. Rien au démarrage, rien d'automatique ; distinct de la gestion de PineTS (pine-tools).
---

# Mettre à jour Pine-Workspace

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Parcours ratifié le 2026-11-08 : `/pws → Maintenance / configuration → Outils et mises à jour → Mettre à jour Pine-Workspace`. Toute la logique est celle de `tools/pws_workspace/update.py`, qui orchestre les autorités existantes `upgrade` (code) et `migrate` (données) : aucune seconde mécanique de copie, de sauvegarde ni de restauration. Aucune recherche réseau au démarrage, aucune mise à jour automatique, aucun jeton ni authentification GitHub pour consulter une release publique.

## 1. Écran d'état (toujours d'abord, lecture seule)

```bash
python3 -m tools.pws_workspace update status
```

Annoncer, à partir de cette sortie et sans rien improviser :

1. **Version installée** (`installed_version`) et **type d'installation** (`installation.kind`) : `distribution` (manifeste de cœur : `manifest_version`, `built_at`, `source_commit`) ou `development` (amont de développement, `installation.reason` : consultation des releases possible ; un téléchargement ou une préparation de paquet reste possible car il s'écrit hors de l'installation, mais tout plan est refusé sur l'amont, donc aucune application ; ne pas proposer « Appliquer » ; la distribution se construit avec `build-distribution` / `build-release`, voir OPERATIONS.md).
2. **Dernière recherche** (`last_check`) : `checked_at` nul → « non recherchée : on ignore si une version plus récente existe » ; sinon la date, le `result` (`update-available`, `up-to-date`, `no-release`, `error`, `ahead` = version installée plus récente que la dernière publiée), la version `latest`, et la `source` (`github` = consultation réelle ; `simulated` = réponse déterministe de test, jamais présentée comme une consultation réelle). Un `error` ou un `no-release` ne devient jamais « à jour ». Un résultat ancien reste un résultat daté : proposer une nouvelle recherche.
3. **Migrations en attente** avec le code actuel (`pending_migrations`) et **sauvegardes** existantes (`backups`).

## 2. Écrans d'actions (textes visibles, Retour partout)

```text
Écran 1 : Rechercher une nouvelle version · Consulter les changements et limites · Suite… · Retour
Écran 2 : Préparer depuis la release officielle · Préparer depuis un paquet local · Retour arrière · Retour
```

| Libellé | Commandes | Nature |
|---|---|---|
| Rechercher une nouvelle version | `update check` (réseau explicite ; `--include-prereleases` seulement sur demande du titulaire) | lecture seule ; résultat daté enregistré ; versions comparées numériquement par le tooling |
| Consulter les changements et limites | `last_check.latest.notes` (notes de la release trouvée) ou `changes` d'un plan préparé | lecture seule |
| Préparer depuis la release officielle | `update fetch` (après une recherche ayant trouvé une release), puis `update plan --package-dir <package_dir>` | téléchargement dans un dossier temporaire hors de l'installation ; provenance des actifs (dépôt et tag officiels) et empreinte SHA-256 vérifiées ; rien n'est écrit dans l'installation hormis le fichier de plan (`.claude/runtime/pws-update/plans/`) |
| Préparer depuis un paquet local | chemin demandé conversationnellement ; `update prepare --package <zip ou dossier> [--sha256 <empreinte attendue>]`, puis `update plan --package-dir <package_dir>` | hors ligne ; **intégrité seulement**, origine non vérifiée en ligne |
| Appliquer (après le récapitulatif, §3) | `update apply --plan-file <plan> --yes` | écrit : `upgrade` puis migrations par le nouveau code |
| Retour arrière | `update rollback-info`, puis seulement sur choix explicite : `migrate --rollback <stamp>` (données) puis `upgrade --rollback <stamp>` (code) | l'information est en lecture seule ; les restaurations sont les commandes existantes, chacune confirmée |

## 3. Récapitulatif avant application (obligatoire)

À partir de la sortie de `update plan`, présenter dans cet ordre : version actuelle → version cible (`direction` ; un `downgrade` est refusé) ; origine du paquet (`origin`, `provenance` — pour une release : « intégrité vérifiée par l'empreinte, authenticité non prouvée » ; pour un paquet local : « intégrité vérifiée hors ligne, origine non vérifiée ») ; changements principaux (`changes`) ; fichiers en conflit (`upgrade.conflicts` : le parcours s'arrête là, jamais d'écrasement, jamais `--overwrite-local`) ; fichiers conservés localement (`upgrade.kept_local`, nouvelle version écrite en `.pws-new`) et retirés (`upgrade.retired`) ; migrations qui peuvent s'appliquer (`migrations_may_apply` ; `null` = paquet sans déclaration : toute étape arrêtera le parcours) ; sauvegardes et ordre du retour arrière (`backups`, `rollback`) ; nécessité de relancer Claude Code (`restart_required`) ; non-atomicité de l'ensemble (`notes.atomicity`). Puis **une seule question** : « Appliquer / Annuler ». `Annuler` et `Retour` n'écrivent rien. Si `applicable` est faux, expliquer `refusals` et ne pas proposer Appliquer. L'accord porte sur ce plan précis (empreinte `plan_hash`) : tout changement ultérieur fait refuser l'application.

## 4. Après application

Lire le `status` du rapport et le dire tel quel ; seul `applied` (`ok: true`, code de sortie 0) est une réussite. Toujours présenter ensuite `done` — code installé et vérifié (`code_installed`, `code_verified`), migrations appliquées, restantes, bloquées, diagnostic (`ok` / `blocking` / `unavailable` / `not-run`) —, les sauvegardes de `recovery` et la prochaine action utile `next_action`. Dès que `done.code_installed` est vrai, ne jamais dire que rien n'a changé.

- `applied` : code installé et vérifié, migrations prévues appliquées, diagnostic `ok` (des avertissements seuls ne bloquent pas, par contrat du doctor).
- `refused-before-mutation` : rien n'a changé (plan modifié, conflits, amont, confirmation absente).
- `stopped-blocked-migrations` : code installé ; une migration de données est **bloquée** (`stages.migrate.blocked`, avec son motif) : aucune migration appliquée, pas même les autres ; proposer de résoudre la cause puis `migrate --plan` / `migrate --apply` explicites, ou `upgrade --rollback <stamp>`. Cas de m001 (conflit entre le mode de `pws.config.json` et une valeur héritée, deux valeurs et leur origine présentées) : seul le titulaire choisit, par `/tv-mode <mode>` ou le menu Configuration ; ne jamais choisir à sa place.
- `stopped-unplanned-migrations` : code installé ; une migration sort du plan approuvé (`stages.migrate.unplanned`) : aucune migration appliquée ; mêmes propositions. Ne jamais étendre l'accord initial.
- `diagnostic-blocking` : code installé et vérifié, migrations appliquées, mais le doctor signale des constats BLOCKING (`stages.doctor.blocking`) : la mise à jour est en place mais n'est pas déclarée réussie ; proposer `doctor` et la résolution des constats ; le retour arrière reste disponible.
- `diagnostic-unavailable` : le doctor n'a pas pu être exécuté, a rendu un résultat inexploitable ou non conforme à son contrat (liste vide, entrée sans identifiant `check` exploitable, sévérité hors de OK / INFO / WARNING / BLOCKING, champ absent ou d'un type incorrect — l'entrée et le champ en cause sont nommés dans `stages.doctor.error`) ou un code de sortie incohérent avec son résultat : ne jamais présenter cela comme un diagnostic réussi ; proposer d'exécuter `doctor` soi-même.
- `incomplete` : code installé, mais une migration a échoué, une réponse de `migrate` était inexploitable (détail dans `stages.migrate.errors`), une migration reste due après l'application, des fichiers ne correspondent pas au manifeste, ou une erreur interne est survenue après l'installation du code ; donner `done`, `recovery` et `next_action` tels quels.
- Fichiers conservés localement (`done.kept_local`, par exemple après `pinets install`) : la mise à jour peut être `applied` ; dire que la version locale a été gardée et que la nouvelle est posée à côté (`<chemin>.pws-new`) pour examen.
- Mise à niveau interrompue par un arrêt brutal (`interrupted` dans le plan ou l'état) : proposer `upgrade --rollback <stamp>` ou une nouvelle application du même paquet, au choix explicite du titulaire.
- `failed-restored` (état antérieur restauré et vérifié), `failed-restore-*` (restauration refusée ou incomplète : éléments de récupération dans `recovery`) ; aucune nouvelle tentative automatique.

Le code de sortie de `update apply` vaut 0 seulement pour `applied`. Toujours terminer par l'invitation à quitter et relancer Claude Code (`notes.restart`) dès que le code est installé. Ne jamais qualifier l'ensemble « mise à niveau puis migrations » d'atomique ; aucun retour arrière automatique de l'ensemble n'existe.

## 5. Règles

- Rien n'est recherché au démarrage, rien n'est téléchargé ni appliqué sans un choix explicite ; une sélection de menu ne vaut jamais autorisation d'appliquer.
- Les préversions ne sont jamais proposées par défaut ; les versions ne sont jamais comparées comme des chaînes ; « à jour » ne se déduit jamais d'une erreur ni d'une absence de release.
- L'empreinte SHA-256 publiée assure l'intégrité du téléchargement, pas son authenticité : ne jamais annoncer de signature.
- Une réinstallation par-dessus n'est jamais la procédure de mise à jour (`install.py` la refuse).
- Les scripts, l'identité, la langue, les réglages, les validations et les preuves ne sont jamais touchés par `upgrade` ; les migrations de données sont explicites, sauvegardées et traçables (`MIGRATION.md`).
