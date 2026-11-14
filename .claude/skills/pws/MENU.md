# Rendu de référence du menu PWS

Support de la skill `pws`. La structure et les textes sont **générés** par `python3 -m tools.pws_workspace menu --json` (`tools/pws_workspace/menu.py`, catalogue `i18n.py`) ; ce document décrit le rendu attendu, il n'est pas une seconde source de la structure : un écart entre ce document et la sortie du tooling est un défaut à signaler, jamais à combler à la main. Libellés ci-dessous en français ; la langue configurée (`en`/`fr`) s'applique.

## Règles de rendu

- Au plus quatre options par écran ; `Suite…` ouvre l'écran suivant ; **`Retour` figure sur chaque écran sous le premier niveau** (écran continué : deux entrées + Suite… + Retour ; dernier écran : jusqu'à trois entrées + Retour). `Retour` et `Annuler` n'écrivent rien et ne lancent rien.
- Chaque option : un intitulé simple et une courte description de l'utilité ou de l'effet (une conséquence n'est précisée que si elle aide à choisir). Aucun nom de skill, de commande, d'argument, d'empreinte ni de référence au standard dans les textes visibles.
- Un réglage affiche d'abord sa valeur actuelle, puis les autres choix et « Conserver « … » (Retour) » (aucune écriture quand la valeur ne change pas).
- Bannière du menu (champ `banner` de `menu --json`, constante `MENU` de `tools/pws_workspace/banner.py`) : ASCII Art **fixe** représentant « PWS » (FIGlet Standard, 23 colonnes, 5 lignes, un seul bloc ; décision du titulaire du 2026-11-08, remplaçant pour `/pws` seulement l'ancien repli en texte brut ; texte « PWS » depuis sa décision du 2026-11-14, à la place de « Pine-WS »). Elle est transmise **dans le texte de la question du menu principal** : `banner.question` = les cinq lignes exactes, une ligne vide, la question localisée (« Que souhaitez-vous faire ? » / « What would you like to do? »), passé tel quel à AskUserQuestion (`header` = `title`), à l'ouverture et à chaque retour au menu principal seulement. Jamais en texte libre avant l'appel (le texte intermédiaire est réécrit par la couche de présentation de Claude Code, constat du 2026-11-08), jamais devant un sous-menu, une autre question, un résultat, une sortie JSON ni un hook ; aucune adaptation à la largeur, aucun redimensionnement (largeur fixe : aucune tenue dans toute fenêtre n'est promise ; le rendu des espaces de tête par le dialogue n'est établi que par l'observation du titulaire). Usage distinct : la sous-commande `python3 -m tools.pws_workspace banner` (terminal) conserve ses variantes adaptatives PINE-WORKSPACE — large 81, compacte 64 ou texte brut 14 colonnes selon la largeur mesurée à chaque affichage, marge de deux colonnes, rien sous 14 colonnes connues (`--json` : forme structurée). Le nom officiel du workspace reste inchangé dans la documentation, les chemins, les commandes et les métadonnées : « PWS » n'est que le texte de la bannière du menu, identique dans les deux langues.

## Premier niveau (≤ 4 entrées, selon l'état réel ; pas de Retour)

```text
PWS
├── Travailler sur un script          (si ≥ 1 produit REGISTERED) — action d'abord, script ensuite
├── Nouveau / importer
├── Qualité / publication             (si ≥ 1 produit)
└── Maintenance / configuration
```

## Travailler sur un script → action → script

```text
Écran 1 : Développer / corriger · Documentation / tutoriel · Suite… · Retour
Écran 2 : Recherche · Revue · Audit approfondi · Retour
```
Puis le script : un seul REGISTERED → « Script : <slug> (<type>, <profil>) » affiché, options « Continuer avec ce script » · Retour ; plusieurs → « Choisir le script » (`script_screens` : quatre par écran, « Autres… », Retour). Routes : `pine-develop`, `pine-docs`, `pine-research`, `pine-review`, `pine-audit` (revue et audit sur demande explicite seulement ; documentation et tutoriel accessibles sans publication).

## Nouveau / importer

```text
├── Nouveau script          → type (Indicateur / Stratégie / Bibliothèque) → profil → récapitulatif → Démarrer / Modifier / Annuler → pine-new
├── Importer un script      → pine-onboard (les .pine UNREGISTERED et les produits non prêts sont proposés directement)
└── Retour
```

Écran profil (indicator / strategy) :
```text
├── FREE — source public, CC BY-NC-SA 4.0
├── FREE à source fermé — propriétaire, usage gratuit accordé
├── PRIVATE — propriétaire, usage personnel ou partage limité
└── COMMERCIAL — propriétaire, EULA configurable
```
Library : profil dérivé (FREE à source public, règle TradingView) — confirmation à deux options (Continuer / Retour). Le scanner rejette toute autre combinaison si elle est injectée autrement.

## Qualité / publication

```text
Écran 1 : Test local (PineTS) · Validation TradingView · Suite… · Retour
Écran 2 : Licence et conditions d'utilisation · Préparer une publication · Export GitHub · Retour
```
Chaque entrée demande ensuite le script (même règle que ci-dessus). Test local PineTS et validation TradingView restent deux couches distinctes (l'un ne vaut jamais l'autre). « Licence et conditions d'utilisation » (`pine-license`) : consulter, compléter, prévisualiser, puis enregistrer et générer sur choix explicite ; indépendant de la publication (aucun contrôle de release, aucune revue, ni PineTS ni TradingView). « Préparer une publication » ne publie rien ; les informations de licence ou de publication manquantes sont signalées et bloquent seulement la finalisation concernée. « Export GitHub » : consulter, préparer et prévisualiser sont toujours possibles ; l'envoi reste soumis à une autorisation explicite sur un plan précis.

## Maintenance / configuration

```text
Écran 1 : Diagnostic du workspace · État détaillé · Suite… · Retour
Écran 2 : Configuration · Outils et mises à jour · Archives et nettoyage · Retour
```

Outils et mises à jour (sous-menu généré, 2026-11-08) :
```text
Écran 1 : PineTS · Mettre à jour Pine-Workspace · Retour
```
« PineTS » → `pine-tools` ; « Mettre à jour Pine-Workspace » → `pws-update` : deux gestions distinctes dans le même sous-menu.

Configuration (six réglages, trois écrans, Retour sur chacun) :
```text
Écran 1 : Langue · Identité du titulaire · Suite… · Retour
Écran 2 : Profil par défaut · Mode TradingView · Suite… · Retour
Écran 3 : Destinations GitHub · Entretien au lancement · Retour
```

- Langue : valeur actuelle nommée (« Français » / « English », jamais le seul code) ; autre langue + « Conserver « Français » (Retour) ». Route : `config set language <code>`.
- Identité du titulaire : nom et alias actuels ; modification saisie conversationnellement (`config set identity.copyright_holder "…"`, `identity.header_aliases …`).
- Profil par défaut : FREE / PRIVATE / COMMERCIAL (`config set identity.default_profile <profil>`).
- Mode TradingView : mode courant (configuration) ; l'autre mode + Conserver (Retour) ; mutation seulement sur choix explicite du titulaire via `python3 -m tools.pws_workspace tv-mode <mode>` ; `manual` reste le défaut, `chrome-experimental` reste explicitement optionnel.
- Destinations GitHub : liste actuelle (« aucune » le cas échéant) ; ajout ou retrait sur décision du titulaire (`github destination-add` / `destination-remove`), jamais automatiquement.
- Entretien au lancement : Activé / Désactivé (`config set maintenance.startup_cleanup true|false`).

## Écrans propres aux skills routées (mêmes règles de rendu)

- Licence et conditions d'utilisation → `pine-license` : écran d'état d'abord (profil et axes, titulaire des droits distinct de l'identité juridique du fournisseur, documents du profil et leur état, informations manquantes ou à confirmer, statut brouillon / complet), puis « Consulter le détail » · « Compléter les informations » · Suite… · Retour / « Prévisualiser un document » · « Enregistrer et générer » · Retour ; le dialogue de complément avance par groupes cohérents, affiche un récapitulatif et une confirmation groupée avant toute écriture ; Retour et Annuler abandonnent les changements non enregistrés.
- Outils et mises à jour → PineTS → `pine-tools` : écran d'état d'abord (état local, disponibilité d'une mise à jour seulement d'après une recherche datée, points de retour utilisables : manifeste vérifié sur le contenu sauvegardé), puis « Vérifier l'installation de PineTS » · « Rechercher une mise à jour » · Suite… · Retour / « Installer une version » · « Préparer une recalibration » · « Revenir à une version sauvegardée » (si un point utilisable existe) · Retour.
- Outils et mises à jour → Mettre à jour Pine-Workspace → `pws-update` : écran d'état d'abord (version installée et type d'installation — distribution ou amont de développement —, dernière recherche datée ou « non recherchée », migrations en attente, sauvegardes), puis « Rechercher une nouvelle version » · « Consulter les changements et limites » · Suite… · Retour / « Préparer depuis la release officielle » · « Préparer depuis un paquet local » · « Retour arrière » · Retour ; toute préparation se termine par un récapitulatif (versions, origine et provenance, changements, conflits, migrations possibles, sauvegardes, relance de Claude Code, non-atomicité) et une seule question « Appliquer / Annuler » ; rien n'est recherché au démarrage, rien n'est appliqué sans cette confirmation ; sur l'amont de développement, consultation seulement.
- Export GitHub → `pine-github` : « Consulter la connexion et les destinations » · « Préparer un export » · Suite… · Retour / « Comparer avec le dépôt » · « Envoyer vers GitHub » · « Gérer les destinations » · Retour.
- Archives et nettoyage → `pine-maintenance` : « Voir le plan d'entretien » · « Exécuter l'entretien » · Suite… · Retour / « Importer des archives » · « Consulter l'index des archives » · Retour ; l'import se déroule en étapes distinctes (plan, copie vérifiée, indexation) et la suppression du dossier source n'est jamais comprise dans le choix d'importer.
