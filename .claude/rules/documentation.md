---
paths:
  - "scripts/**/docs/**"
  - "scripts/**/*TUTORIAL*"
  - "scripts/**/*Tutorial*"
  - "scripts/**/*tutorial*"
---

# Documentation user-facing d'un script

- Anglais uniquement ; zéro franglais ; terminologie user-facing du master §22 (jamais `bool`, `enum`, `alertcondition`, `:=`… exposés à l'utilisateur).
- Tooltips : deux catégories strictement distinctes — settings = expliquer un choix (master §20) ; éléments visuels = informer sur un état observé (master §23).
- Tutoriel : conventions du master §33 — même modèle de qualité pour FREE, PRIVATE et COMMERCIAL ; palette et structure par défaut selon le positionnement (§33.2, §33.3) ; préparable à tout moment via `pine-docs`, finalisé à la release.
- Aucune version produit, aucune URL de licence, aucun site ni lien promotionnel dans les textes utilisateur (master §22.3) ; les textes de licence sont rendus depuis `docs/licensing/templates/` (`license render`), jamais inventés.
- Router vers les sections applicables via `standards/INDEX.md` ; ne pas dupliquer le style complet ici.
- Exception : l'artefact de suivi interne désigné par le `CLAUDE.md` local d'un produit (spec §53), même placé sous `docs/` et rédigé en français, n'est pas user-facing.
