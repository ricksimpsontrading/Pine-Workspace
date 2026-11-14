# Pine Workspace

Workspace Claude Code autonome pour développer, maintenir, documenter, valider et préparer la publication de scripts Pine Script V6. Aucun autre projet n'est requis : ce dossier est sa propre racine, lancé depuis lui-même. L'identité du titulaire des scripts, la langue de travail et les préférences vivent dans `pws.config.json` (configuration personnelle).

*English: Pine Workspace is a self-contained Claude Code workspace for Pine Script V6 development. Installation: `INSTALL.md`. Licences of the workspace's own components: Apache-2.0 for the core, AGPL-3.0-only for the PineTS thin adapter (`NOTICE`, `docs/licensing/`); your scripts remain yours.*

## Démarrer

```bash
cd "<dossier du workspace>"
python3 -m tools.pws_workspace init --language fr --copyright-holder "Votre nom"   # première configuration (une fois)
claude                     # session normale ; l'état PWS s'affiche au démarrage
/pws                       # menu guidé (action d'abord, script ensuite)
```

Nouvelle installation depuis une distribution : `INSTALL.md`. Mise à jour d'une installation existante : `/pws → Maintenance / configuration → Outils et mises à jour → Mettre à jour Pine-Workspace` (recherche explicite sur le dépôt officiel ou paquet local, plan, confirmation, puis `upgrade` et `migrate`), détails dans `docs/architecture/MIGRATION.md` ; jamais de réinstallation par-dessus.

## Les gestes principaux

- **Ajouter un script existant** : créer `scripts/<slug>/` et y déposer le `.pine`. Il est détecté UNREGISTERED et onboardé par la skill `pine-onboard` — analyse réelle du code, contexte spécifique, jamais de template.
- **Nouveau script** : décrire l'objectif à Claude (ou `/pws → Nouveau script`). Le workflow `pine-new` conçoit le produit avant tout code (recherche, benchmark, différenciation, architecture) et choisit un profil de licence : FREE (CC BY-NC-SA 4.0), FREE à source fermé, PRIVATE, COMMERCIAL (`docs/licensing/PROFILES.md`). Le profil ne change pas le niveau d'exigence.
- **Modifier** : `pine-develop` (lecture ciblée, contrôle du diff, vérifications proportionnées). **Audit approfondi** : `pine-audit` (explicite, périmètre annoncé). **Documentation / tutoriel** : `pine-docs` à tout moment. **Publication** : `pine-release` (ne publie jamais) puis, si souhaité, `pine-github` (plan, aperçu, publication sur autorisation).

## Vérifier l'état du workspace

```bash
python3 -m tools.pws_workspace doctor          # diagnostic complet, lecture seule (ne répare jamais)
python3 -m tools.pws_workspace session-status  # état compact
python3 -m tools.pws_workspace tooling-status  # outils intégrés (PineTS) : versions, identité, calibration
```

## Mode de validation TradingView

`manual` (défaut) : Claude prépare la matrice de tests, le titulaire observe dans TradingView. `chrome-experimental` : automatisation partielle via le navigateur, explicitement optionnelle, avec fallback manuel. Changement (réservé au titulaire) : `/tv-mode manual` ou `/tv-mode chrome-experimental`, ou `/pws → Maintenance / configuration → Configuration`.

## Outils, archives, Git

- **PineTS** (laboratoire local, jamais une validation TradingView) : installé par le titulaire (`npm ci --ignore-scripts` dans `tools/pine_exec`), géré par `pine-tools` (`pinets check-update`, `install <version> --yes`, `verify`, `rollback`) ; aucune mise à jour silencieuse ; une mise à jour rend les calibrations STALE.
- **Archives et nettoyage** : `pine-maintenance` — entretien déterministe des temporaires recréables au lancement, import vérifié d'archives externes dans `docs/maintenance/archives/` avec index des déplacements. Ces archives locales ne remplacent pas une sauvegarde indépendante du disque.
- **Git** : local-first ; commits uniquement sur décision explicite du titulaire ; `git push` et l'export GitHub soumis à autorisation explicite. Sans Git installé, PWS fonctionne en mode dégradé documenté (pas d'historique local).

## Aller plus loin

- Procédures détaillées : `docs/architecture/OPERATIONS.md`
- Architecture et justifications : `docs/architecture/ARCHITECTURE.md`
- Standard Pine canonique : `standards/PINE_SCRIPT_V6_STANDARD.md` (index : `standards/INDEX.md`)
- Licences : `NOTICE` et `docs/licensing/LICENSING.md` (Apache-2.0 du cœur PWS, AGPL-3.0-only de l'adaptateur PineTS, composants tiers), `docs/licensing/` (profils, modèles, notices tierces)
