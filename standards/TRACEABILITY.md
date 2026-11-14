# TRACEABILITY — Standard maître → opérationnalisation workspace

Statut : dérivé architectural, non normatif (spec §13). Régénération : analyse sémantique humaine/Claude, jamais un simple parser.
Master : standards/PINE_SCRIPT_V6_STANDARD.md — SHA-256 855f0d68909dde4ce34a081b01bde5449776b579252d88f0102b7a0882d14de5
Généré le : 2026-09-04. Revu le : 2026-09-27 (relectures proportionnées) ; 2026-11-06 (édition neutre, profils de licence §5–§6, niveaux de vérification §9.1/§36/§38, commentaires §24.5, tutoriel §33, livrables §41, URL §6.5) ; 2026-11-06, intervention de vérification (dimensions de publication séparées §5, référence légale déclarée §6.5, aucun déclenchement automatique par classe de tâche §2.3/§9.1/§11/§36/§38) ; 2026-11-13 (amendement autorisé du §9.2 « Relecture après modification » : relecture ciblée selon le niveau et la classe, couverture globale consolidée en préparation de publication seulement ; correspondances de la ligne §9 inchangées). 2026-11-13, licences des scripts importés (décision du titulaire : §5 licence existante conservée, §6 en-tête d'origine et lignes de copyright des auteurs d'origine ; lignes §5 et §6 complétées ; précision du même jour : une licence CC importée exige un source public). Si le SHA du master change, ce fichier est STALE jusqu'à revue.

Dépendances réelles de ce document : le master (SHA ci-dessus, seule dépendance de fraîcheur mécanique) ; la spec de bootstrap pour les références « spec §… » (amendement du 2026-11-06) ; les skills, rules, agents et modules du tooling cités (vérifiés à la date de revue). Un changement de ces derniers n'est pas détecté mécaniquement : il appelle une revue de ce fichier, pas une déclaration de péremption automatique.

Format par section : contexte/rule → skill(s) → agent éventuel → check déterministe éventuel → exécution comportementale locale éventuelle → validation empirique éventuelle.
« — » = pas de mécanisme dédié nécessaire (la section vit par consultation directe du master via INDEX).

| § Master | Titre | Rule / contexte | Skill(s) | Agent | Check déterministe | Comportemental local | Empirique TV |
|---|---|---|---|---|---|---|---|
| 0 | Mission (titulaire) | CLAUDE.md (rappel autorités) | tous les workflows pine-* | — | — | — | — |
| 1 | Statuts normatifs / applicabilité | CLAUDE.md ; toutes les skills rappellent N/A ≠ à inventer | pine-develop, pine-review | pws-pine-reviewer | — | — | — |
| 2 | Classes de tâches (toutes au niveau 1 sauf audit demandé / publication) | — | pine-develop (classification en étape 2), pine-audit (sur demande) | — | — | profondeur pine-local-test proportionnée (seulement si prévue) | matrice tv-validate proportionnée |
| 3 | Autorité technique / conflits | CLAUDE.md (rôles des sources) | pine-research (vérif doc officielle) | pws-pine-researcher | — | — | — |
| 4 | Langues (langue configurée avec le titulaire, EN code) | CLAUDE.md ; `pws.config.json` (`language`) | toutes (directive de langue) ; menu localisé (`menu.py`, `i18n.py`) | tous (retour dans la langue de la mission) | `config` : langue validée | — | — |
| 5 | Profils de licence, axes, licence existante des scripts importés et dimensions de publication (état / confidentialité / mode) | script-context.md | pine-new (profil), pine-onboard (licence existante proposée puis confirmée), pine-license (`confirm --license-id`), pine-docs, pine-release | — | scan + `profiles.py` : schéma 3 (extension `origin`/`status`), cohérence des axes (§45.4), licence importée (liste fermée, « à analyser »), v1/v2 dérivés et signalés ; `license status`, `license detect` | — | — |
| 6 | Header, version produit, licence, URL (6.5) | pine-source.md | pine-new, pine-develop, pine-release ; `license render` (modèles) | — | guard : header selon licence et identité configurée (`header-structure`, `header-copyright` ; licence importée : notice d'origine présente et cohérente), `// Version:` dans la région d'en-tête, `//@version=6`, shorttitle, title ASCII, URL de licence en commentaire seulement + référence légale déclarée `terms_url` par correspondance exacte (`no-promo-urls`, `cc-url-placement`) | — | — |
| 7 | Recherche Pine avant code | research.md | pine-research, pine-develop (étape 5) | pws-pine-researcher | — | — | — |
| 8 | Benchmark, création originale (8.5) | research.md | pine-research (corpus, frontière, originalité) | pws-pine-researcher | — | — | — |
| 9 | Cartographie et trois niveaux de vérification (9.1), relecture (9.2) | pine-source.md (rappel) | pine-develop (lecture ciblée étendue selon la classe, étape 3), pine-audit (niveau 2, sur demande), pine-release (niveau 3), pine-onboard (cartographie initiale, étapes 3-5), pine-review (couverture rendue) | pws-pine-cartographer (audit demandé / onboarding), pws-pine-reviewer | — | — | — |
| 10 | Inventaire d'impact | — | pine-develop (étape 4) | — | — | comparaisons de régression ciblées | — |
| 11 | Méthodologie de modification | pine-source.md (rappel workflow) | pine-develop (diff + relecture §9.2 ; revue selon niveau) | — | — | — | — |
| 12 | Compatibilité Pine V6 | pine-source.md | pine-develop, pine-research (migration) | pws-pine-researcher | guard : //@version=6 | — | tests migration si applicable |
| 13 | Invariants Pine V6 | pine-source.md (routage) | pine-develop, pine-review | pws-pine-reviewer | — (sémantique) | observations ciblées possibles | validation réelle |
| 14 | Patterns à risque silencieux | — | pine-review (checklist) | pws-pine-reviewer | — | régressions comparables | — |
| 15 | Features modernes V6 | — | pine-develop, pine-research | pws-pine-researcher | — | — | — |
| 16 | Architecture du code | pine-source.md (rappel) | pine-develop, pine-review | pws-pine-reviewer | — | — | — |
| 17 | Naming | — | pine-review | pws-pine-reviewer | — | — | — |
| 18 | Design produit | script-context.md | pine-new (conception produit) | — | — | — | — |
| 19 | UX des settings | — | pine-new, pine-develop, pine-review | pws-pine-reviewer | — | — | test settings réels |
| 20 | Tooltips settings | documentation.md (routage) | pine-develop, pine-review | pws-pine-reviewer | — | — | rendu réel |
| 21 | Validation des settings | — | pine-develop | — | — | runtime.error observable localement selon capabilities | test settings extrêmes |
| 22 | Terminologie user-facing | documentation.md | pine-review, pine-docs, pine-release | pws-pine-reviewer, pws-release-reviewer | guard : aucune URL dans les textes utilisateur | — | — |
| 23 | Tooltips éléments visuels | documentation.md (routage) | pine-develop, pine-review | pws-pine-reviewer | — | — | rendu réel |
| 24 | Commentaires, ce qui ne vit pas dans le source (24.5) | pine-source.md | pine-develop, pine-review | pws-pine-reviewer (scan 37.19) | guard : `no-worklog-comments` (WARNING) | — | — |
| 25 | Robustesse numérique / edge cases | — | pine-develop, pine-review | pws-pine-reviewer | — | edge cases observables sur datasets contrôlés | — |
| 26 | Événements vs états, ta.valuewhen | — | pine-develop, pine-review | pws-pine-reviewer | — | observation event vs state possible | — |
| 27 | MTF / historique / realtime / repaint | pine-source.md (rappel 3 couches) | pine-develop, tv-validate | pws-pine-reviewer | — | selon capabilities (jamais preuve universelle de non-repaint) | historical/realtime/Replay réels |
| 28 | Performance / ressources | — | pine-develop, pine-research (limites actuelles) | pws-pine-researcher | — | — | Profiler / chargement réels |
| 29 | Éléments visuels — applicabilité | — | pine-new, pine-review | pws-pine-reviewer | — | — | — |
| 30 | Palette / identité visuelle | documentation.md (routage) | pine-new, pine-review | pws-pine-reviewer | — | — | dark + light réels |
| 31 | SemVer | release.md | pine-release (impact réel) | pws-release-reviewer | guard : Version X.Y.Z dans le header ; version absente hors source (§56 spec) | — | — |
| 32 | Changelog (complet avec le produit, exporté via GitHub) | release.md | pine-release, pine-github | pws-release-reviewer | — | — | — |
| 33 | Tutoriel (préparable à tout moment, même modèle de qualité) | documentation.md, release.md | pine-docs, pine-release (revue 33.4) | pws-release-reviewer | — | — | — |
| 34 | Publication TradingView | release.md | pine-release (règles actuelles revérifiées), tv-validate | pws-release-reviewer | — | — | chart + publication réels (jamais automatisés) |
| 35 | Tests pré-release | release.md | pine-release, tv-validate | — | — | tests comportementaux applicables | matrice pré-release réelle |
| 36 | Revue post-code 4 axes (selon niveau) | — | pine-develop (auto-revue en travail courant, toutes classes), pine-review (indépendante : audit demandé, publication, demande du titulaire — jamais déclenchée par la classe de la tâche) | pws-pine-reviewer | — | — | — |
| 37 | Anti-patterns (37.19 : journal de travail) | pine-source.md (rappel) | pine-review (scan) | pws-pine-reviewer | guard : 37.15 shorttitle, 37.16 version hors header, 37.19 commentaires de journal | — | — |
| 38 | Workflow script existant (niveaux) | — | pine-develop (orchestration), pine-audit | selon niveau | guard + scan | pine-local-test seulement si prévu | tv-validate |
| 39 | Workflow nouveau script | — | pine-new (orchestration ; profil) | tous | guard + scan | pine-local-test selon applicabilité | tv-validate |
| 40 | Validation TradingView | validation.md | tv-validate | — | validation-status (stale, intégrité ; auteur nul admis pour not-run/n-a) | jamais un substitut (§29.5 spec) | OUI — autorité finale |
| 41 | Livrables de release (sans site ; destination GitHub configurée) | release.md | pine-release, pine-github | pws-release-reviewer | `github export-plan` : liste de contenus autorisés | — | — |
| 42 | Standard de fin | CLAUDE.md (rappel) | pine-develop, pine-release | — | — | — | validation réelle requise |

## Contrôles inverses (mécanismes → master)

- guard (tools/pws_workspace/guard.py) applique uniquement : master §6 (headers selon licence et identité configurée, version dans la région d'en-tête, title, shorttitle, URL §6.5), §12 (//@version=6), §24.5/§37.19 (avertissement), §37.15, §37.16 + contrats machine spec (§45). Tout le reste du master est sémantique → workflows + reviewer.
- profiles.py / scan applique master §5 et spec §45.4 (profils, axes, cohérences, library open-source) ; licensing.py rend les modèles de master §6 et des conditions (`docs/licensing/templates/`).
- pine-local-test n'applique aucune règle du master : il observe le comportement (spec §24.4). Le master reste l'autorité de conception.
- Aucune section du master n'est recopiée dans rules/skills/agents ; routage uniquement (spec §2.1, §54).

## Sections sans mécanisme dédié (choix assumé)

§10, §14, §15, §17, §21, §25-26, §28-29 : portées par les workflows pine-develop / pine-review / pine-audit et le reviewer à contexte frais ; un check mécanique fiable n'existe pas pour ces exigences (spec §37.3, §38.3).
