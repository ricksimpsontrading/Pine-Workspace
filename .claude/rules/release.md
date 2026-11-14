---
paths:
  - "scripts/**/release/**"
---

# Artefacts de release

- Toute release passe par la skill `pine-release` ; publication implicite interdite — l'état final est `READY FOR HUMAN PUBLICATION`, jamais `PUBLISHED` sans action explicite du titulaire. L'export GitHub (`pine-github`) suit la même règle : plan et aperçu d'abord, publication seulement sur autorisation explicite.
- Relire les règles TradingView actuelles immédiatement avant la release (publication, Vendor Requirements, libraries open-source, `Author's instructions` pour invite-only) — jamais une règle mémorisée seule (master §34).
- SemVer selon l'impact réel utilisateur (master §31) ; changelog au format master §32 ; description selon master §34 ; tutoriel selon master §33 ; textes de licence (`release/EULA.md`, notice, autorisation) rendus depuis les modèles et complétés par le parcours `pine-license` — une EULA en brouillon bloque la readiness d'une publication commerciale ; une licence existante importée « à analyser » bloque la readiness et l'export (jamais le travail courant) ; rien d'autre de ce parcours ne bloque.
- La gate finale reste la validation TradingView du SHA final du source (spec §27.3). Un statut PineTS non gating n'empêche pas d'y aller ; une régression locale `UNEXPECTED` réellement gating doit être qualifiée et résolue avant.
