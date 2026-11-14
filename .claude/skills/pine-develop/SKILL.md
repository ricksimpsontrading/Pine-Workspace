---
name: pine-develop
description: Orchestrateur de toute modification d'un script Pine onboardé — classification, lecture ciblée à partir de la cartographie, impact, implémentation minimale, contrôle du diff, checks mécaniques, tests locaux et validation TradingView proportionnés. Utiliser pour corriger, améliorer ou restructurer un script existant.
---

# Modification d'un script onboardé

Langue : répondre dans la langue configurée (`language` de `session-status --json`) ; code et textes du produit en anglais.

## Séquence (spec §24.2, master §38 — niveaux de vérification du master §9.1)

1. Lire le contexte local requis (`CLAUDE.md` local, `PRODUCT.md`, `ARCHITECTURE.md`, `SCRIPT.json` : profil et axes de licence).
2. Comprendre précisément la demande ; classer la tâche (master §2 : correction locale / changement fonctionnel / structurel / release). Le niveau est le **travail courant** (cette skill) pour toute classe, y compris un changement structurel ; l'**audit approfondi** (`pine-audit`) n'a lieu que si le titulaire le demande (le proposer si le risque le justifie, ne jamais l'engager) ; la **préparation de publication** relève de `pine-release`.
3. Lire la cartographie (`ARCHITECTURE.md`) puis les blocs concernés et leurs dépendances pertinentes (producteurs, consommateurs, textes, visuels, alertes), étendues selon la classe : plus larges pour un changement structurel, jamais intégrales par défaut. Agent `pws-pine-cartographer` et lecture intégrale : seulement dans un audit demandé. Cartographie jugée fausse ou insuffisante : le signaler et proposer un audit.
4. Inventaire d'impact (master §10) : ce qui change, ce qui doit rester inchangé, consommateurs, textes/visuels/alertes dépendants. L'inventaire conclut explicitement sur la compilation minimale intermédiaire (spec §30.5) : « requise », avec le risque nommé (typage, profondeur d'historique, taille compilée), ou « non requise ».
5. Vérifier la documentation Pine actuelle pertinente ; vérification de pertinence du benchmark (master §8 — conclure `N/A` explicitement si rien d'utile) ; `pine-research` si nécessaire. Toute implémentation reste originale (master §8.5).
6. Définir la modification minimale cohérente ; planifier ; implémenter par unités cohérentes (master §11 — pas de scope creep : toute amélioration non demandée qui constitue une décision produit est proposée au titulaire d'abord). Aucun journal de travail dans les commentaires du source (master §24.5).
7. Relire selon la couverture du master §9.2 et contrôler le diff ; auto-revue sur les quatre axes du master §36 limitée au périmètre modifié ; synchroniser les artefacts dépendants (axe 2). Pour chaque affirmation significative modifiée ou déclarée vérifiée (tooltip, commentaire, conclusion de conformité), garder une référence courte au symbole ou au contrat qui la justifie et sa limite.
8. Revue indépendante (`pine-review` → `pws-pine-reviewer`) seulement dans un audit demandé, en préparation de publication ou à la demande du titulaire — jamais déclenchée par la classe de la tâche ; une fois, sans cascade.
9. `python3 -m tools.pws_workspace guard "scripts/<slug>"`.
10. `pine-local-test` seulement si l'inventaire d'impact l'a prévu (construction touchée couverte par une capability, risque réel) : smoke run pour une petite correction, comparaison de régression pour un refactor neutre ; jamais par défaut après une petite modification.
11. Qualifier les résultats PineTS (spec §24.4.7–24.4.9). Correction du source uniquement si elle serait justifiée même sans PineTS (spec §24.4.8) ; puis réexécuter les étapes locales applicables.
12. `tv-validate` selon applicabilité : compilation minimale intermédiaire si l'inventaire l'a conclue requise, campagne fonctionnelle sur le source stabilisé (spec §30.5) ; revalider après toute correction qui change le source. Le regroupement de la campagne suit l'organisation décidée par le titulaire pour ce produit (`DECISIONS.md`), jamais celle d'un autre produit.
13. Mettre à jour uniquement les fichiers contextuels devenus réellement obsolètes (spec §53) ; consigner les quatre mentions de suivi (classe de tâche et niveau, couverture lue, conclusion de benchmark, provenance des rapports d'agents s'il y en a eu) dans l'artefact désigné par le `CLAUDE.md` local du produit. Une unité de travail terminée n'est pas réauditée sans raison nouvelle.
