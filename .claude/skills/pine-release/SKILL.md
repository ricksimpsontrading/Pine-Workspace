---
name: pine-release
description: Préparer une publication d'un script Pine (niveau 3) — SemVer, changelog, notes, tutoriel finalisé, textes de licence, vérification des règles TradingView actuelles, couverture globale consolidée et revue de release. Ne publie jamais. Utiliser quand le titulaire demande de préparer une livraison ou publication.
---

# Préparation de publication (niveau 3)

Langue : répondre dans la langue configurée ; livrables du produit en anglais.

Préparer, jamais publier implicitement (spec §27, master §31–§35, §41). Exigences finales de livraison, distinctes d'un simple candidat à tester (master §9.1).

## Étapes selon applicabilité

1. Déterminer l'impact SemVer d'après l'impact RÉEL utilisateur (master §31 — un bugfix qui change les signaux historiques n'est pas automatiquement PATCH).
2. Vérifier/mettre à jour la version dans le header du source (seul emplacement autorisé — master §6, spec §56) ; header conforme au profil (`python3 -m tools.pws_workspace license render --slug <slug> --kind header-free|header-proprietary` comme référence).
3. Licence et publication : `python3 -m tools.pws_workspace license status --slug <slug>` — une licence existante importée « à analyser » (`license_release_blockers` non vide) bloque la déclaration de readiness et l'export comme conditions définitives — jamais le travail courant ; les avertissements `IMPORTED_LICENSE_CONFLICT` sont présentés au titulaire comme points à analyser, jamais tranchés ; aucune licence importée ne reçoit de document de conditions PWS et son en-tête d'origine reste tel quel ; une EULA en brouillon (champs indispensables manquants), un `terms_ref` absent pour un accès payant ou des informations de publication non confirmées (état, confidentialité, mode, année) sont **signalés** au titulaire avec la liste précise de ce qui manque, et **bloquent seulement la finalisation concernée** (déclaration de readiness, export des documents en brouillon) ; ils n'empêchent ni de préparer les autres documents, ni d'identifier les informations nécessaires. Jamais complété par invention : les informations se complètent par le parcours `pine-license` (menu « Licence et conditions d'utilisation »), indépendant de cette préparation.
4. Préparer changelog (format master §32), release notes, tutoriel finalisé (master §33 — préparé à tout moment via `pine-docs`, revu ici selon §33.4), description initiale si nouvelle publication (master §34). Même modèle de qualité pour FREE, PRIVATE et COMMERCIAL.
5. Vérifier la documentation dépendante (master §36 axe 2).
6. REVÉRIFIER les règles TradingView actuelles : publication, Vendor Requirements, modes payants (`invite-only` public), libraries open-source, chart de publication (master §34) — via `pine-research`, jamais de mémoire seule.
7. Publication `invite-only` : préparer et vérifier le contenu `Author's instructions` requis (anglais en premier).
8. Couverture globale consolidée du source stabilisé, une seule fois (master §9.2), par le développeur ou par le reviewer indépendant — la preuve dit lequel.
9. Exécuter les tests comportementaux PineTS applicables lorsque des capabilities effectivement gating ou des `ACCEPTED_BEHAVIORAL_BASELINE` pertinentes existent ; qualifier et résoudre toute régression locale `UNEXPECTED` réellement gating avant la validation finale.
10. Tests pré-release TradingView applicables (master §35) via `tv-validate`.
11. Revue indépendante par l'agent `pws-release-reviewer` (une fois).
12. Vérifier que la validation TradingView couvre le SHA-256 FINAL du source (`python3 -m tools.pws_workspace validation-status "scripts/<slug>"` — effectif `passed`, pas `stale`).
13. Export GitHub éventuel : `pine-github` (plan, aperçu, puis publication seulement sur autorisation explicite).

## Gate

Release prête uniquement si le source final a passé la validation TradingView requise. Un statut `PINETS_UNSUPPORTED/EXPERIMENTAL/INCONCLUSIVE` n'empêche pas d'y aller ; il ne la remplace jamais. État final : `READY FOR HUMAN PUBLICATION` — la publication reste un acte du titulaire.
