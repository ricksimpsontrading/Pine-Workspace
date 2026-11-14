---
name: pine-new
description: Créer un nouveau produit Pine de zéro — objectif, benchmark, différenciation, conception produit et architecture AVANT tout code ; profil de licence et manifeste schéma 3. Utiliser quand le titulaire demande un nouveau script (jamais pour onboarder un .pine existant).
---

# Nouveau produit Pine

Langue : répondre dans la langue configurée ; code et textes du produit en anglais.

Un nouveau produit ne commence jamais par un `.pine` vide : conception avant code (spec §23, master §39).

## Workflow

1. Comprendre l'objectif fonctionnel ; clarifier UNIQUEMENT les décisions produit indéterminables.
2. Définir l'audience.
3. `script_kind` : indicator / strategy / library.
4. Profil de licence et axes (master §5, `docs/licensing/PROFILES.md`) : FREE (CC BY-NC-SA 4.0, source public), FREE à source fermé (propriétaire, `free-use`), PRIVATE, COMMERCIAL (EULA configurable, brouillon tant que les champs ne sont pas renseignés — jamais bloquant pour le développement). `library` → FREE à source public dérivé automatiquement, jamais autre chose tant que la règle TradingView l'impose. Le profil ne change pas le niveau d'exigence : l'ambition dépend du produit.
5. Vérifier la documentation Pine V6 actuelle pertinente (via `pine-research` / `pws-pine-researcher`).
6. Benchmark : meilleurs scripts publics open-source du domaine, Editors' Picks prioritaires (master §8) ; forces, limites, compromis des références ; définir comment la solution les SURPASSE par une implémentation originale (master §8.4–8.5 : ni copie, ni traduction ligne à ligne, ni renommage ; jamais de réutilisation de code sans la procédure de provenance et l'accord du titulaire ; références tracées dans la recherche, pas en crédits automatiques).
7. Concevoir le produit puis l'architecture : décisions utilisateur réellement nécessaires, settings, états et flux, MTF/realtime/repaint si applicable, visualisation et alertes seulement si utiles, risques.
8. Obtenir la confirmation du titulaire pour les décisions produit non délégables.
9. Créer `scripts/<slug>/` — slug stable, ASCII, kebab-case, descriptif, indépendant de la version.
10. Créer le contexte spécifique : `SCRIPT.json` (schéma 3 : `profile` ; `license` {id, grant, source_visibility, access, copyright_holder null → identité configurée, created_year = année courante **proposée explicitement à la création** et confirmée par le titulaire (jamais déduite ailleurs), terms_ref null, terms_url null} ; `publication` {state `unpublished`, privacy, mode} selon les défauts du profil, chaque dimension ajustable ou laissée nulle si inconnue), `PRODUCT.md`, `ARCHITECTURE.md` (cartographie initiale, maintenue ensuite), `CLAUDE.md` local, `validation/current.json` `unverified`, et le premier research run si une vraie recherche a été faite.
11. Version initiale : décision du titulaire ou politique explicitement ratifiée — ne JAMAIS inventer une convention de version initiale.
12. Créer le `.pine` avec le header rendu pour le profil (`python3 -m tools.pws_workspace license render --slug <slug> --kind header-free|header-proprietary`) et développer section par section ; commentaires techniques seulement (master §24.5).
13. Relire selon la couverture du master §9.2 et contrôler le diff ; auto-revue sur les quatre axes ; revue indépendante (`pine-review`) seulement à la demande du titulaire (la proposer avant la première validation si le risque le justifie, ne jamais l'engager) ; corriger.
14. `python3 -m tools.pws_workspace guard "scripts/<slug>"` (checks déterministes).
15. `pine-local-test` selon applicabilité, capabilities réellement utilisées, calibration courante et proportionnalité ; qualifier tout résultat avant d'en déduire une correction (spec §24.4.8).
16. `tv-validate` : validation TradingView réelle.
17. Synchroniser le contexte final (seulement ce qui est devenu faux).
