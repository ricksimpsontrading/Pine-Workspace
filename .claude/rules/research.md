---
paths:
  - "scripts/**/research/**"
---

# Recherche par script

Chaque run de recherche persisté contient : date, question, sources réellement consultées, faits, conclusions, distinction observation/inférence, statut de fraîcheur.

- Jamais de recherche fictive : ne consigner que ce qui a réellement été consulté (master §37.2).
- `CURRENT.md` = synthèse de routage vers les runs, avec statut CURRENT, STALE ou NON REVÉRIFIÉ (spec §50.4) ; il ne remplace pas les runs. Un run reconstitué ne reçoit jamais CURRENT sans revérification datée.
- Pas de TTL universel : la fraîcheur dépend du sujet et du risque de changement. Toute règle TradingView de publication est revérifiée immédiatement avant une vraie release (master §34).
- Benchmark ≠ réutilisation de code : frontière du master §8.5 strictement appliquée (implémentation originale ; références tracées ici, jamais en crédits automatiques dans le script).
