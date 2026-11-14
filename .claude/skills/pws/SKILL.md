---
name: pws
description: Menu contextuel guidé du Pine Workspace. Rend l'arborescence déterministe fournie par le tooling (menu --json, libellés et descriptions localisés) avec AskUserQuestion et route vers les skills métier. Utiliser quand le titulaire tape /pws ou demande le menu PWS.
---

# Menu contextuel PWS

Façade UX pure : aucune logique métier, aucune persistance propre, aucune autorité. Ni la structure ni les textes visibles ne sont écrits ici : ils sont calculés par le tooling à partir de l'état réel et de la langue configurée. Les commandes directes restent toujours disponibles.

## 1. État frais, arborescence fournie

```bash
python3 -m tools.pws_workspace menu --json
```

La sortie contient : `language`, `title`, `banner` (bannière fixe « Pine-WS » du menu : `question` = texte complet de la question du menu principal, `text`, `width`, `fixed`, voir §2), `top` (entrées applicables du premier niveau, chacune avec ses écrans `children` déjà paginés : au plus quatre options et `Retour` sur chaque écran), `inapplicable` (entrées masquées et leur raison), `scripts` (produits REGISTERED, libellé « slug (type, profil) »), `single_script` / `single_script_label` / `continue_label`, `script_screens` (écrans de choix du script : quatre par écran, « Autres… », Retour), `not_ready` (produits incomplets → onboarding), `kinds`, `profiles`, `profile_defaults`, `free_closed_defaults`, `library_rule`, `labels`. Ne jamais réutiliser une sortie ancienne si le workspace a pu changer (spec §40.5.6). Le mode TradingView affiché vient de cette sortie (configuration), jamais de la variable d'environnement.

## 2. Rendu avec AskUserQuestion

- Menu principal (ouverture de `/pws` et chaque retour au menu principal) : un seul appel AskUserQuestion dont le texte de question est **`banner.question`, transmis tel quel** (les cinq lignes de la bannière fixe « Pine-WS », une ligne vide, la question dans la langue configurée ; espaces et sauts de ligne préservés exactement, rien d'ajouté, rien de modifié), `header` = `title`, options = `top` dans l'ordre avec `label` et `description`. **Ne jamais émettre la bannière en texte libre avant l'appel** : le texte émis entre un résultat d'outil et un appel d'outil est traité par Claude Code comme une narration de progression et peut être réécrit par sa couche de présentation (constat du titulaire du 2026-11-08 : bannière remplacée par un « summary » en anglais) ; cette règle remplace la précédente, les deux mécanismes ne se cumulent pas. La bannière est fixe (police FIGlet Standard, 41 colonnes, 5 lignes ; décision du titulaire du 2026-11-08) : aucune adaptation à la largeur, aucun redimensionnement, aucune tenue dans toute fenêtre promise ; le rendu des espaces de tête par le dialogue n'est établi que par l'observation du titulaire. Jamais de bannière dans un sous-menu, une autre question, un résultat ni une sortie structurée. Les variantes adaptatives PINE-WORKSPACE relèvent uniquement de la sous-commande `banner` dans un terminal, jamais de `/pws`. Ne jamais reconstruire, agrandir ni improviser la bannière : seule la sortie du tooling la fournit.
- En-tête (`header`, 12 caractères au plus) : celui du nœud `submenu` ouvert, ou, pour les écrans de question, `headers` (`kind`, `profile`, `script`, `setting`, `confirm`) ; jamais un en-tête improvisé ni tronqué à la main.
- Un écran = les options d'un `children[i]`, dans l'ordre, avec `label` et `description` **tels quels** (déjà dans la langue configurée) ; répondre au titulaire dans cette même langue. `more` ouvre l'écran suivant ; `back` revient à l'écran précédent sans aucune écriture ni lancement d'action. `back` figure sur chaque écran sous le premier niveau : ne jamais l'omettre, ne jamais compter sur `/pws`, Échap ou la saisie libre pour le remplacer. Le menu principal n'en a pas.
- Les textes visibles restent ceux du tooling : ne jamais y ajouter de noms de skills, de commandes, d'arguments, d'empreintes, de fingerprints ni de références au standard. Ces détails vont dans les instructions, l'aide et les résultats détaillés affichés après une action. Si un nœud attendu n'a pas d'enfants ou si une entrée prévue manque, le signaler comme défaut du tooling ; ne jamais reconstruire un écran d'après `MENU.md` ni improviser des choix.
- Parcours « Travailler sur un script » et actions de « Qualité / publication » (test local, validation TradingView, licence et conditions d'utilisation, préparation d'une publication, export GitHub) : **l'action d'abord**, puis le script (`needs_script`). Un seul script enregistré : afficher `single_script_label`, proposer `continue_label` et Retour (sélection directe mais explicite). Plusieurs : question `choose_script_label` avec les `script_screens`. Le premier niveau ne présente jamais le nom d'un produit comme s'il était le seul périmètre possible.
- Produits `not_ready` : proposer l'onboarding (`pine-onboard`), jamais une sélection silencieuse.
- « Nouveau script » : écran type (`kinds`) → écrans profil (`profile_screens`, déjà paginés par le tooling avec `Suite…` et Retour : FREE, FREE à source fermé, PRIVATE, COMMERCIAL, chacun avec sa description ; `profiles` reste la liste des valeurs ; pour une library, seul FREE à source public — `library_rule`) → récapitulatif court (type, profil, axes par défaut) → `Démarrer / Modifier / Annuler`. Rien n'est créé avant `Démarrer`.
- Réglages de « Configuration » (`kind: setting`) : annoncer la valeur actuelle (`current_label`) ; options = les autres `choices` (transmettre la `value` canonique) + `keep_label` (« Conserver … (Retour) » : aucune écriture quand la valeur ne change pas) ; une valeur persistante invalide (`invalid: true`, `keep_label` nul) est annoncée comme telle et seuls les `choices` et Retour sont proposés. Un réglage `free_text` (identité du titulaire, destinations GitHub) se saisit hors menu, conversationnellement, puis passe par la sous-commande de `route` ; aucune destination GitHub n'est jamais renseignée automatiquement. `config.tvmode` : changement seulement sur choix explicite du titulaire entre `manual` et `chrome-experimental`, via `python3 -m tools.pws_workspace tv-mode <mode>` (jamais la skill `/tv-mode`, réservée au titulaire).
- Routes `command:` : exécuter la sous-commande indiquée, puis résumer son résultat.

## 3. Invariants

- `Retour` et l'annulation ne produisent AUCUN effet de bord.
- Une sélection ne vaut jamais autorisation de publication (TradingView ou GitHub), de suppression, de mise à jour ni de restauration ; ces actes relèvent de leur skill et d'une autorisation explicite portant sur un résultat concret.
- Un choix route vers la skill existante (`pine-new`, `pine-onboard`, `pine-develop`, `pine-docs`, `pine-research`, `pine-review`, `pine-audit`, `pine-local-test`, `tv-validate`, `pine-license`, `pine-release`, `pine-github`, `project-doctor`, `pine-tools`, `pws-update`, `pine-maintenance`) — jamais de duplication de leur logique ; les écrans propres à ces skills suivent les mêmes règles (quatre options, Retour partout, textes courts).
- Valeurs transmises = valeurs canoniques (`script_kind` ∈ indicator|strategy|library ; `profile` ∈ FREE|PRIVATE|COMMERCIAL avec, pour FREE à source fermé, les axes `free_closed_defaults` ; `value` des `choices`), pas les libellés.
- Information libre nécessaire (objectif produit, nom du titulaire, dépôt…) → sortir du menu et la demander conversationnellement.

## 4. Fallback

Si AskUserQuestion est indisponible : mêmes écrans en liste numérotée conversationnelle, mêmes invariants. Documentation du rendu : `MENU.md`.
