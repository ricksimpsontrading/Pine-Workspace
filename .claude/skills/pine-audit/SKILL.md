---
name: pine-audit
description: Audit approfondi d'un script Pine onboardé, déclenché explicitement, avec périmètre annoncé avant exécution — lecture globale, cartographie par agent, revue indépendante élargie, comparaison PineTS si prévue. Niveau 2 du master §9.1 ; jamais lancé automatiquement après une modification.
---

# Audit approfondi (niveau 2)

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

L'audit est le seul cadre où la lecture intégrale du produit, la cartographie par agent et une revue indépendante élargie sont légitimes hors préparation de publication (master §9.1). Il ne se déclenche que sur demande explicite du titulaire ; aucune classe de tâche, structurelle comprise, ne le déclenche à elle seule. L'assistant peut le proposer lorsqu'il juge le risque élevé, jamais l'engager.

## 1. Périmètre annoncé AVANT exécution

Présenter et faire confirmer, en une question :

- le ou les scripts concernés ;
- les sections ou symboles couverts (ou « global ») ;
- les axes retenus : intégrité contextuelle, artefacts dépendants, conventions applicables, regard frais (master §36), anti-patterns (§37), commentaires de journal de travail (§24.5), licence et en-tête (§6) ;
- l'exécution locale PineTS : incluse (smoke run ou comparaison de régression contre un run de référence identifié) ou exclue ; jamais implicite ;
- la validation TradingView : hors périmètre de l'audit (elle relève de `tv-validate`).

Pas de confirmation → pas d'audit.

## 2. Exécution

1. `python3 -m tools.pws_workspace guard "scripts/<slug>"` (faits mécaniques).
2. Cartographie : lecture intégrale du source dans le périmètre annoncé ; `pws-pine-cartographer` si le volume le justifie (un seul agent, un seul passage).
3. Revue indépendante : `pws-pine-reviewer` à contexte frais avec la couverture annoncée (une seule revue ; pas de cascade de contre-revues).
4. PineTS seulement si inclus au périmètre (`pine-local-test`) ; qualifier les résultats (spec §24.4.7–24.4.9), jamais de correction du source pour satisfaire le moteur.
5. Synthèse : constats classés problème / impact / emplacement / règle / confiance, distinction observé / inféré, liste de ce qui n'a pas pu être vérifié.

## 3. Sortie

- Rapport dans la conversation, consigné dans l'artefact de suivi du produit (classe de tâche, couverture réellement lue, provenance des rapports d'agents).
- Mise à jour d'`ARCHITECTURE.md` seulement si la cartographie est devenue fausse.
- Aucune correction n'est appliquée par l'audit lui-même : chaque correction est une tâche de travail courant (`pine-develop`) décidée par le titulaire.
- Une unité de travail auditée n'est pas réauditée sans raison nouvelle.
