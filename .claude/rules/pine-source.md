---
paths:
  - "scripts/**/*.pine"
---

# Source Pine du titulaire

Ce fichier est un source Pine Script V6 du titulaire du workspace (identité : `pws.config.json`).

- Avant toute modification substantielle : vérifier que le produit est onboardé (`SCRIPT.json` valide dans le product root). Sinon → skill `pine-onboard` d'abord. Jamais d'édition substantielle d'un `.pine` UNREGISTERED.
- Contexte local du produit : `CLAUDE.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `SCRIPT.json` du même dossier.
- Conventions : `standards/PINE_SCRIPT_V6_STANDARD.md` (naviguer via `standards/INDEX.md`). Ne pas recopier le standard ici.
- Toute modification passe par le workflow `pine-develop` : lecture ciblée à partir de la cartographie (`ARCHITECTURE.md`), inventaire d'impact, modification minimale cohérente, contrôle du diff, relecture selon la couverture du master §9.2 ; lecture globale et revue indépendante seulement dans un audit approfondi demandé par le titulaire (`pine-audit`) ou en préparation de publication — jamais déclenchées par la classe de la tâche (master §9.1, §36).
- Commentaires : fonctionnement, choix techniques non évidents, contraintes utiles et mentions légales légitimes seulement ; aucun historique de lots, référence de conversation, instruction à l'assistant ni récit de revue (master §24.5).
- Trois couches distinctes, jamais fusionnées : checks déterministes (`guard`) ≠ exécution comportementale locale PineTS (`pine-local-test`) ≠ validation TradingView (`tv-validate`).
- Router vers `pine-local-test` seulement quand l'inventaire d'impact ou le périmètre d'un audit prévoit une exécution locale.
- INTERDIT : modifier ce source dans le seul but de satisfaire une incompatibilité, limitation ou divergence PineTS (spec §24.4.8).
