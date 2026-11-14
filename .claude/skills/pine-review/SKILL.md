---
name: pine-review
description: Revue structurée d'un script Pine selon les quatre axes du standard, par un reviewer indépendant à contexte frais. Utiliser sur demande explicite du titulaire, dans un audit approfondi demandé ou en préparation de publication — jamais déclenchée automatiquement par une modification, quelle que soit sa classe.
---

# Revue quatre axes

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Implémente master §36 en déléguant le regard indépendant à l'agent `pws-pine-reviewer`. Quand : audit approfondi demandé (`pine-audit`), préparation de publication (`pine-release`), ou demande du titulaire (menu « Revue »). En travail courant, quelle que soit la classe de la tâche (changement structurel compris), l'auto-revue du développeur et le contrôle du diff suffisent (master §9.1, §36) ; cette skill n'est jamais enchaînée automatiquement.

## Exécution

Une seule revue par unité de travail, pas de cascade de contre-revues. Fournir au reviewer : la demande initiale, le chemin du source, le contexte produit nécessaire, et le diff utile comme point d'attention. La mission indique la couverture attendue (ciblée, élargie, globale — master §9.2) ; le reviewer rend en tête la couverture réellement lue. Ne pas transmettre toute la conversation.

Transmettre au reviewer, par référence et sans recopie : la section des invariants du `CLAUDE.md` local, les identifiants des décisions de `DECISIONS.md` concernées, les points `Pending confirmation` de `PRODUCT.md` touchés et l'inventaire d'impact. Le développeur travaille à partir des mêmes références. Aucune liste parallèle n'est créée.

Le reviewer applique les quatre axes du master §36 et le scan anti-patterns du master §37 — le détail est porté par sa définition (`.claude/agents/pws-pine-reviewer.md`), pas dupliqué ici.

## Sortie et responsabilité

Retour structuré : problème / impact / emplacement / justification / règle ou objectif concerné / niveau de confiance. Le reviewer ne modifie JAMAIS le code ; le parent décide et implémente les corrections, puis relit selon la couverture du master §9.2.
