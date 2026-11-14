---
name: pine-docs
description: Documentation et tutoriel utilisateur d'un script Pine onboardé — préparation ou mise à jour à tout moment, sans déclencher une préparation complète de publication. Même modèle de qualité pour FREE, PRIVATE et COMMERCIAL ; textes en anglais (master §33, §34, §22).
---

# Documentation / tutoriel

Langue : échanges dans la langue configurée (`language` de `session-status --json`) ; le tutoriel et tous les textes du produit restent en anglais (master §4.2).

## Ce que cette skill fait

Préparer ou mettre à jour, pour un produit REGISTERED : le tutoriel utilisateur (master §33), la description TradingView (§34) et les textes utilisateur dérivés (release notes hors release, FAQ interne au produit). Elle n'exige ni SemVer, ni changelog, ni validation TradingView : c'est `pine-release` qui finalise ces artefacts à la publication (master §33 : préparable à tout moment, finalisé et revu à la release).

## Étapes

1. Lire `SCRIPT.json` (profil, axes de licence), `PRODUCT.md`, `ARCHITECTURE.md`, le `CLAUDE.md` local ; lire les sections du source nécessaires aux textes (settings, visuels, alertes) — pas de lecture intégrale par défaut.
2. Appliquer un **même modèle de qualité** quel que soit le profil ; seules diffèrent les informations liées au produit, à sa distribution et à ses conditions d'accès (licence, mode de publication, accès, support). Direction visuelle par défaut : master §33.2 (COMMERCIAL, PRIVATE) ou §33.3 (FREE) — directions, pas niveaux.
3. Rédiger en anglais, terminologie user-facing du master §22 ; aucune version produit, aucune URL de licence, aucun site, aucune promesse de performance.
4. Mentions de licence dans la documentation : obtenir le texte rendu par `python3 -m tools.pws_workspace license render --slug <slug> --kind notice|grant|eula` ; une EULA en brouillon (champs manquants) est signalée, jamais complétée par invention.
5. Déposer sous `scripts/<slug>/docs/` (tutoriel) ou `scripts/<slug>/release/` (textes de publication) — dossiers à la demande.
6. Revue du tutoriel selon master §33.4 par le développeur (auto-revue) ; la revue indépendante relève de `pine-release`.
7. Consigner dans l'artefact de suivi du produit ce qui a été produit et à partir de quel SHA du source.
