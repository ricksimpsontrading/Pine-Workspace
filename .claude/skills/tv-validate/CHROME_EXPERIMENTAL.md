# Mode `chrome-experimental` — protocole et savoir opérationnel

Statut : expérimental et optionnel (spec §31). Ce mode tente d'exécuter la même matrice que `manual` via l'intégration navigateur native de Claude Code. Il n'a PAS été activé pendant le bootstrap (décision du titulaire) ; aucun run n'a été promu dans ce protocole et aucun savoir opérationnel n'a été qualifié depuis, et la section « Savoir opérationnel qualifié » ci-dessous est donc VIDE — c'est l'état honnête attendu, rien ne doit y être inventé.

## 1. Préflight (avant chaque run)

Vérifier réellement, sans supposer :
- version Claude Code et disponibilité de l'intégration Chrome (`claude --chrome`, extension compatible, plan Anthropic direct connecté via /login) ;
- navigateur Chromium compatible en cours d'exécution ;
- outils navigateur réellement présents dans la session ;
- session TradingView déjà authentifiée, ou le titulaire disponible pour compléter le login (l'intégration s'arrête sur login/CAPTCHA) ;
- restrictions de plateforme actuelles (non supporté sous WSL à la date de la spec — revérifier la doc actuelle).

Le transport interne `claude-in-chrome` MCP fourni par Claude Code est un détail d'implémentation de la primitive native : PWS ne l'installe pas, ne crée aucun `.mcp.json`, et cette exception n'autorise aucun MCP tiers (spec §58).

## 2. Pre-write gate (avant TOUTE mutation du Pine Editor)

Établir avec une confiance suffisante :
1. la fenêtre Chrome attendue ;
2. l'onglet TradingView cible et son domaine ;
3. l'identité de l'éditeur ouvert ;
4. l'identité du script ou buffer actif ;
5. la présence éventuelle de modifications étrangères non sauvegardées ;
6. la correspondance entre ce buffer et le produit/source local attendu.

Une identité ambiguë → **NO WRITE** → fallback manual / action humaine. Après toute écriture, réobserver le buffer et le contexte : un clic réussi ne prouve ni que le bon script a été modifié ni que le contenu attendu est présent.

## 3. Frontière de preuve (spec §31.5)

Capacité à cliquer ≠ capacité à prouver. Si une étape ne peut pas être établie de manière suffisamment fiable comme réussie, elle n'est PAS `passed`. Le seuil de preuve ne baisse jamais, quel que soit le savoir accumulé.

## 4. Fallback (spec §31.6)

Déclencher le fallback manuel notamment sur : login requis, CAPTCHA, extension non connectée, Pine Editor inaccessible, UI différente, résultat ambigu, action navigateur échouée, contrôle visuel incertain, élément non automatisable, étape demandant un jugement humain, risque d'action de publication. Enregistrer dans le run : `requested_mode = chrome-experimental`, `effective_mode = manual`, `fallback_reason`. Le mode persistant reste inchangé — seul le titulaire le change.

## 5. Screenshots

Sauvegarder une capture uniquement lorsqu'elle constitue une preuve utile, sous `validation/evidence/<run_id>/`, hashée dans le rapport.

## 6. Publication exclue

Ce mode s'arrête AVANT toute publication publique, changement de visibilité, modification `invite-only` ou action commerciale (spec §31.8, §2.8).

## 7. Apprentissage opérationnel contrôlé (spec §31.9)

But : capitaliser les connaissances opérationnelles réellement utiles (workflows TradingView observés, landmarks UI fiables, signes de succès/échec, causes reproductibles de fallback) sans mémoire opaque ni nouvelle autorité. Ce n'est PAS de l'apprentissage statistique.

### 7.1 Préférence de repères

```text
état sémantique observable > rôle/label accessible > relation structurelle stable
> relation DOM stable > sélecteur fragile > coordonnée pixel absolue
```

Sélecteurs fragiles et coordonnées absolues : dernier recours, marqués comme tels.

### 7.2 Promotion d'un apprentissage

Une observation ponctuelle ne devient pas automatiquement durable. Avant de l'ajouter à la section 8, vérifier à une profondeur proportionnée qu'elle : (1) provient d'un run ou d'une vérification réelle ; (2) est réutilisable au-delà du cas ponctuel ; (3) est suffisamment établie (répétition, corroboration, documentation actuelle ou reproduction claire) ; (4) ne transforme pas un accident d'UI en invariant ; (5) ne généralise pas un résultat propre à un script ; (6) améliore réellement navigation, observation, détection d'ambiguïté ou qualité de preuve. L'auto-memory peut servir de sas temporaire pour une observation candidate ; elle ne remplace jamais cette promotion volontaire.

### 7.3 Frontière connaissance / preuve

```text
workflow connu        ≠ étape courante réussie
landmark connu        ≠ preuve automatique
absence historique d'ambiguïté ≠ absence actuelle d'ambiguïté
```

Chaque run réobserve l'état réellement présent.

### 7.4 Obsolescence et révision

Un apprentissage contradictoire, absent, ambigu ou manifestement obsolète : ne pas forcer l'ancien workflow ; le considérer non fiable pour le run courant ; explorer prudemment ou fallback manual ; puis corriger, marquer fragile ou retirer l'entrée quand une nouvelle observation suffisamment établie le justifie. Un changement de version (TradingView, Chrome, Claude Code) justifie la réévaluation sans être à lui seul une preuve d'obsolescence.

### 7.5 Contenu interdit ici

Mots de passe, cookies, tokens, credentials ; décisions produit du titulaire (elles ont leurs artefacts) ; résultats d'une validation spécifique présentés comme règles générales ; contenu propriétaire d'un script ; preuves de run sans fonction durable distincte ; coordonnées/sélecteurs fragiles présentés comme invariants fiables.

## 8. Savoir opérationnel qualifié

_Aucune entrée. Aucun run `chrome-experimental` réel n'a encore été exécuté. Chaque future entrée suit le format :_

```text
### <titre court>
Type : workflow | landmark | signe de succès/échec | failure mode | limite
Observé : <dates/runs réels>  —  Corroboration : <répétition/doc/reproduction>
Fiabilité : établi | fragile
Détail : <description actionnable, repère le plus robuste disponible>
```
