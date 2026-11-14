---
paths:
  - "scripts/**/SCRIPT.json"
  - "scripts/**/PRODUCT.md"
  - "scripts/**/ARCHITECTURE.md"
  - "scripts/**/DECISIONS.md"
  - "scripts/**/CLAUDE.md"
---

# Contexte produit d'un script

> Ne jamais transformer une observation ou une inférence en décision du titulaire.

- Distinguer systématiquement : observé dans le source / confirmé par le titulaire / inféré / à confirmer.
- `SCRIPT.json` est la source machine canonique de `script_kind`, du `profile` (FREE / PRIVATE / COMMERCIAL), des axes de licence (`license` : id, grant, source_visibility, access, copyright_holder, created_year, terms_ref, terms_url ; `origin` et `status` pour la licence existante conservée d'un script importé — jamais une licence attribuée automatiquement) et des dimensions de publication TradingView (`publication` : state, privacy, mode — nulles si inconnues, jamais déduites) — schéma 3, champs inconnus rejetés, `id` == slug ; `library` toujours FREE à source public. Un manifeste schéma 1 ou 2 est lu (axes dérivés, signalés) et migré par `migrate --apply`, jamais réinterprété en silence. Les autres fichiers peuvent expliquer, jamais redéfinir.
- Aucune version produit dans ces fichiers (master §6/§31 ; spec §56).
- `PRODUCT.md` décrit le produit réel — pas de rubrique vide, pas de template. `ARCHITECTURE.md` est une cartographie dérivée du code : la mettre à jour seulement quand elle devient fausse.
- `DECISIONS.md` : append-only, `SUPERSEDED` plutôt que réécriture ; uniquement de vraies décisions durables (jamais un résumé de session).
- `CLAUDE.md` local : routeur de 30–80 lignes (identité, invariants, zones à risque, non-goals, pointeurs) — jamais un journal de lots ; l'historique vit dans l'artefact de suivi désigné et dans `DECISIONS.md` (spec §48).
