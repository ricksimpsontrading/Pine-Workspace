# PINE WORKSPACE

Workspace Claude Code dédié au développement, à la maintenance, à la documentation, à la validation et à la préparation des publications des scripts Pine Script V6 du titulaire. L'identité du titulaire, sa langue de travail et ses préférences vivent dans `pws.config.json` (configuration personnelle, jamais dans ce fichier ni dans les autorités).

## Indépendance et frontière physique

- Ce dossier est la racine autonome de Pine Workspace. Aucun autre projet externe n'est requis : ne jamais dépendre de l'existence, du nom, du chemin ou de l'état d'un projet sibling ; ne jamais scanner, modifier ou suivre un symlink vers un contenu extérieur à cette racine physique.
- Le chemin du workspace peut contenir des espaces : manipuler les chemins avec des outils structurés, jamais par concaténation shell fragile.

## Sources d'autorité (rôles complémentaires, jamais concurrents)

- Objectif produit explicite et décisions ratifiées du titulaire → résultat recherché.
- Documentation officielle actuelle (Claude Code, Pine Script, TradingView) → autorité technique dans son périmètre.
- `docs/architecture/BOOTSTRAP_SPEC.md` → contrat de construction du workspace.
- `standards/PINE_SCRIPT_V6_STANDARD.md` → unique standard maître Pine (méthode, qualité, conventions, UX, documentation, profils de licence). Ne jamais le recopier ni l'importer avec `@` ; le consulter à la demande via `standards/INDEX.md`.
- Contexte spécifique du script (`scripts/<slug>/`) → applicabilité locale et invariants du produit.

Tout conflit réel ou apparent entre sources est signalé au titulaire avec les passages concernés ; jamais résolu silencieusement.

## Carte du repo

- `standards/` — standard maître + INDEX (dérivé) + TRACEABILITY (dérivé).
- `scripts/<slug>/` — un produit réel par dossier : `SCRIPT.json` (schéma 3 : profil d'usage, axes de licence dont la licence existante conservée d'un script importé, dimensions de publication), source `.pine`, `PRODUCT.md`, `ARCHITECTURE.md` (cartographie de référence), `CLAUDE.md` local, `validation/`.
- `docs/architecture/` — spec, architecture, contrats de fichiers, opérations, migration, rapport de bootstrap.
- `docs/licensing/` — profils FREE / PRIVATE / COMMERCIAL, modèles de textes (anglais) et explications, licences du cœur PWS (Apache-2.0) et de l'adaptateur PineTS (AGPL-3.0-only, `LICENSING.md`), notices tierces.
- `docs/maintenance/` — rapports, dossiers de maintenance et archives locales (index des déplacements).
- `tools/pws_workspace/` — outil déterministe local : `python3 -m tools.pws_workspace <sous-commande>` (`menu`, `session-status`, `doctor`, `guard`, `config`, `migrate`, `upgrade`, `update`, `pinets`, `github`, `maintenance`, `license`, `build-distribution`, `build-release`…).
- `tools/pine_exec/` — thin adapter PineTS (exécution comportementale locale, capability-gated ; moteur installé par le titulaire, jamais mis à jour en silence).
- `.claude/` — rules path-scoped, skills, agents, settings (permissions Claude Code uniquement).
- `pws.config.json` — configuration personnelle PWS (identité, langue, mode TradingView, destinations GitHub, entretien) ; `install.py`, `INSTALL.md` — installation d'une distribution.

## Règles universelles

- Langue : tous les échanges avec le titulaire dans la langue configurée (`language` de `pws.config.json`, lisible via `session-status --json`) ; code, identifiants et livrables produit en anglais (master §4). Zéro franglais dans les livrables. Commandes et contrats techniques stables.
- Ne jamais inventer un fait : API Pine, règle TradingView, capacité Claude Code, décision du titulaire, recherche non effectuée, identité légale ou condition commerciale.
- Ne jamais modifier `standards/PINE_SCRIPT_V6_STANDARD.md` ni `docs/architecture/BOOTSTRAP_SPEC.md` sans demande explicite du titulaire.
- Git local-first : aucun remote implicite, aucun push implicite ; commit uniquement avec l'accord explicite du titulaire. GitHub n'intervient que par le parcours `pine-github` (destination configurée, plan et aperçu, publication sur autorisation explicite) ; `git push` reste soumis à confirmation.
- Mémoire auto non normative : toute décision produit, contrat de signal, règle de release ou invariant durable est promu dans un fichier versionné approprié, jamais retenu seulement en mémoire.
- Aucune publication TradingView implicite, jamais.

## Trois niveaux de vérification (master §9.1) — proportionnalité

1. **Travail courant** (`pine-develop`) : lecture ciblée à partir de la cartographie, dépendances immédiates, contrôle du diff, guard, vérifications utiles au changement. Jamais de lecture intégrale, d'agent ou de cascade de revues déclenchés automatiquement par une modification, quelle que soit sa classe (changement structurel compris) ; PineTS seulement si l'inventaire d'impact le prévoit.
2. **Audit approfondi** (`pine-audit`) : explicite, périmètre annoncé avant exécution.
3. **Préparation de publication** (`pine-release`) : exigences finales de livraison.

## Trois couches de vérification — ne jamais les confondre

1. Checks déterministes locaux (`guard`, `doctor`) : faits mécaniques uniquement ; le diagnostic ne répare jamais automatiquement.
2. Exécution comportementale locale PineTS (`pine-local-test`) : observation reproductible, capability-gated ; peut bloquer localement sur un contrat strictement borné (capabilities toutes GATING + calibration CURRENT) ; n'est ni une autorité sur la sémantique officielle Pine, ni une validation TradingView. `PINETS_EXECUTION_PASS ≠ TV_VALIDATED` ; CURRENT ne signifie jamais GATING.
3. Validation TradingView (`tv-validate`) : seule validation empirique finale. Ne jamais déclarer un script validé TradingView sans run réel sur le SHA exact du source.

Ne jamais modifier un source Pine dans le seul but de satisfaire PineTS.

## Scripts et onboarding

- Tout `.pine` sous `scripts/**` non rattaché à un `SCRIPT.json` valide est UNREGISTERED : le signaler et exécuter la skill `pine-onboard` avant toute modification substantielle. Jamais d'ignorance silencieuse.
- Nouveau produit → skill `pine-new` (jamais un `.pine` vide créé à la main). Modification → `pine-develop`. Documentation / tutoriel → `pine-docs`. Recherche → `pine-research`. Revue → `pine-review`. Audit → `pine-audit`. Test local → `pine-local-test`. Licence et conditions d'utilisation → `pine-license` (indépendant de la publication). Publication → `pine-release`. Validation → `tv-validate`. Export GitHub → `pine-github`. Diagnostic → `project-doctor`. Outils et mises à jour → `pine-tools` (PineTS) et `pws-update` (mise à jour de Pine-Workspace lui-même : recherche explicite, plan, confirmation, `upgrade` puis `migrate`). Archives et nettoyage → `pine-maintenance`.
- Commentaires d'un source : fonctionnement, choix techniques non évidents, contraintes utiles, mentions légales légitimes — jamais d'historique de lots, de référence à une conversation, d'instruction à l'assistant ni de récit de revue (master §24.5).

## Menu PWS

`/pws` ouvre le menu contextuel guidé (façade AskUserQuestion) : la structure vient de `python3 -m tools.pws_workspace menu --json` (état réel, libellés localisés, action puis script). Il route vers les skills ci-dessus sans dupliquer leur logique. La bannière fixe « Pine-WS » du menu (champ `banner` de cette sortie : ASCII Art FIGlet Standard de 41 colonnes, sans adaptation à la largeur) est transmise telle quelle dans le texte de la question du menu principal (`banner.question`), à l'ouverture et au retour au menu principal seulement — jamais en texte libre avant l'appel, jamais devant un sous-menu, une autre question, un résultat, une sortie JSON ni un hook ; Claude ne la reconstruit jamais. Les variantes adaptatives PINE-WORKSPACE relèvent de la seule sous-commande `banner` (terminal). Le mode TradingView persistant (`manual` par défaut / `chrome-experimental` explicitement optionnel) n'est changé que par le titulaire : `/tv-mode <mode>` (user-only) ou choix explicite dans `/pws → Maintenance / configuration → Configuration` ; les deux passent par `python3 -m tools.pws_workspace tv-mode <mode>`. Claude ne change jamais ce mode de sa propre initiative.
