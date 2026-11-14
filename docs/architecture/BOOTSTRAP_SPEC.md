# PINE WORKSPACE
# CLAUDE CODE PINE WORKSPACE — FINAL BOOTSTRAP SPECIFICATION

Document de construction du workspace Claude Code dédié au développement Pine Script V6.

Date de référence de la spécification : 2026-09-04  
Périmètre : environnement local Claude Code + Git local + développement Pine Script + exécution comportementale locale PineTS + validation TradingView  
Mode de validation TradingView initial : `manual`  
Amendement PineTS ratifié : 2026-08-23  
Amendement apprentissage opérationnel contrôlé `chrome-experimental` ratifié : 2026-08-24  
Amendement menu contextuel PWS ratifié : 2026-08-24  
Amendement autorité locale PineTS, granularité des capabilities et datasets reproductibles ratifié : 2026-08-27  
Amendement correctif global pré-bootstrap ratifié : 2026-08-28  
Amendement d’indépendance du projet ratifié : 2026-09-04  
Amendement §19.3 / §61.8 (portée des garanties de `settings.local.json` face à un écrivain externe non coordonné) ratifié : 2026-09-06  
Amendement de maintenance (attribution des findings du hook Stop, rapports de run version 2, confirmations par groupe, compilation minimale, relectures proportionnées, provenances, artefact de suivi, recherches reconstituées, tests du tooling) ratifié : 2026-09-27  
Complément de maintenance (alignement des relectures en §35.3 et des statuts en §50.4, enregistrement d’import, enregistrement et promotion d’une compilation minimale, correspondance §24.2) ratifié : 2026-09-27  
Amendement d’évolution consolidée (configuration personnelle `pws.config.json` §19A, profils de licence et manifeste schéma 2 §45, niveaux de vérification §24.2/§26, langue configurée, menu déterministe, outils PineTS, parcours d’export GitHub §43.5, archives et entretien, distribution publique et migrations §55, édition neutre : le « titulaire » remplace l’identité nominative) ratifié : 2026-11-06  
Amendement d’alignement des niveaux de vérification (§24.2 étapes 15-16, §26.1, §35.3, §41.1, flux §68 et §69 ; master §9.2 ; constats D-02 à D-04 de l’audit du 2026-11-12/13) autorisé par le titulaire : 2026-11-13  
Amendement de licence de l’adaptateur PineTS (§24.4.13 : adaptateur sous AGPL-3.0-only, cœur sous Apache-2.0 ; constat G-09) décidé par le titulaire : 2026-11-13  
Amendement du mode TradingView hérité (§19A : provenance d’un choix explicite ; conflit sans provenance bloqué jusqu’au choix du titulaire ; constat F-14) décidé par le titulaire : 2026-11-13  
Amendement des licences des scripts importés (§45.2, §45.4, §45.4bis : extension compatible du schéma 3, constat C-19) et du contrôle de visibilité réelle avant l’envoi d’un source fermé (parcours d’export GitHub, constat I-06) décidés par le titulaire : 2026-11-13  
Amendement des documents juridiques d’origine des scripts importés (§45.2, §45.4, §45.4bis, parcours d’export GitHub : `license.documents`, extension compatible du schéma 3, export à l’identique) et du contrôle d’identité de la destination pour tout envoi (parcours d’export GitHub) demandés par le titulaire : 2026-11-14

---

## 0. OBJET DE CE DOCUMENT

Ce document est la spécification de bootstrap du workspace Claude Code utilisé pour développer, maintenir, documenter, valider et préparer les publications des scripts Pine Script du titulaire du workspace (identité et langue configurées dans `pws.config.json`).

Il ne remplace pas le standard maître Pine Script.

Le standard maître Pine Script reste l’autorité canonique sur les conventions de développement des scripts.

Cette spécification gouverne autre chose :

- comment Claude Code doit organiser le workspace ;
- quelles primitives Claude Code doivent être utilisées ;
- comment le contexte doit être chargé ;
- comment un script existant doit être onboardé ;
- comment un nouveau script doit être conçu ;
- comment les informations persistantes doivent être stockées ;
- quels contrôles peuvent être déterministes ;
- comment une couche locale d’exécution comportementale PineTS doit être séparée des contrôles déterministes et de TradingView ;
- comment la validation TradingView réelle doit être reliée au code testé ;
- comment préserver l’autonomie sans créer un système inutilement complexe.

Le bootstrap doit être exécuté avec une règle centrale :

> Concevoir avant d’écrire.

La présence d’un fichier dans l’architecture cible définit une responsabilité à satisfaire, pas un texte générique à recopier.

Aucun fichier opérationnel ne doit être créé simplement pour compléter visuellement une arborescence.

Chaque fichier créé doit avoir une fonction démontrable.

---

## 1. RÉSULTAT ATTENDU

À la fin du bootstrap, le workspace doit permettre deux workflows produit principaux, accessibles directement ou par une façade guidée PWS.

### 1.1 Script Pine existant

Le titulaire crée par exemple :

```text
scripts/zigzag-orderblock/
└── ZigZag OrderBlock Retracement.pine
```

Au démarrage suivant, Claude Code détecte automatiquement que le `.pine` n’est pas onboardé.

Claude Code déclenche le workflow approprié, analyse réellement le script, puis crée seulement le contexte spécifique nécessaire à CE script.

Le contenu de ce contexte doit être dérivé :

- du code réel ;
- du standard maître ;
- des décisions le titulaire déjà connues ;
- de la documentation officielle actuelle lorsque nécessaire.

Il ne doit pas être produit à partir d’un template générique rempli mécaniquement.

### 1.2 Nouveau script

Le titulaire décrit l’objectif du nouveau produit.

Claude Code doit utiliser un workflow distinct de l’onboarding.

Il doit :

1. comprendre l’objectif ;
2. clarifier seulement les décisions produit impossibles à déterminer ;
3. déterminer le modèle de distribution ;
4. effectuer la recherche Pine actuelle ;
5. effectuer le benchmark TradingView requis ;
6. définir comment la solution le titulaire peut dépasser les meilleures références pertinentes sans les copier ;
7. concevoir le produit ;
8. concevoir son architecture ;
9. créer son contexte spécifique ;
10. seulement ensuite commencer le code Pine ;
11. développer ;
12. revoir ;
13. exécuter les checks locaux déterministes ;
14. exécuter les tests comportementaux PineTS applicables selon leur niveau de preuve ;
15. valider réellement dans TradingView.

Un nouveau produit ne doit donc pas commencer normalement par un fichier `.pine` vide créé manuellement.

### 1.3 Menu contextuel PWS

Le workspace doit également fournir une entrée guidée, à l'intérieur d'une session Claude Code interactive, sous la forme d'un menu contextuel PWS.

Ce menu :

- utilise en priorité la primitive native `AskUserQuestion` lorsque la surface Claude Code courante la fournit ;
- se navigue avec l'interface clavier native de Claude Code ;
- ouvre des sous-menus lorsque plusieurs décisions structurées sont nécessaires ;
- adapte ses choix à l'état réel du workspace ;
- route vers les mêmes skills et contrats que les commandes directes ; pour une action user-only que Claude ne peut pas invoquer, transmet le choix explicite au contrôleur déterministe partagé prévu par le contrat ;
- ne duplique aucune logique Pine, produit, validation ou release ;
- ne devient jamais une seconde source de vérité.

Exemple conceptuel :

```text
PWS
  ↓
Nouveau script
  ↓
Indicator / Strategy / Library
  ↓
Gratuit / open-source  |  Payant / closed-source
  ↓
Library → Gratuit / open-source dérivé automatiquement
  ↓
confirmation
  ↓
pine-new
```

Le menu reste réouvrable explicitement pendant la session.

---

## 2. PRINCIPES NON NÉGOCIABLES

### 2.1 Une seule constitution Pine

Le standard maître existe en une seule copie canonique :

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Ne pas recopier son contenu dans :

- `CLAUDE.md` ;
- les rules ;
- les skills ;
- les agents ;
- les fichiers de contexte des scripts ;
- les outils déterministes.

Les autres éléments du workspace doivent appliquer, router, résumer localement ou contrôler des sous-ensembles de ce standard sans devenir des autorités concurrentes.

### 2.2 Pas de gigantesque `CLAUDE.md`

Le `CLAUDE.md` racine doit rester concis.

La documentation Claude Code actuelle recommande de viser moins de 200 lignes par `CLAUDE.md`.

Les procédures multi-étapes vont dans des skills.

Les instructions dépendant de chemins vont dans `.claude/rules/`.

Les gros travaux de lecture/recherche/revue peuvent être isolés dans des subagents.

### 2.3 Pas d’import `@` du standard maître

Ne pas importer le master standard depuis `CLAUDE.md` avec `@`.

Un import est chargé dans le contexte ; il n’économise pas le coût contextuel.

Le standard maître est consulté à la demande à travers son index et les workflows.

### 2.4 Aucun fichier générique décoratif

Interdictions :

- faux scripts d’exemple ;
- `.gitkeep` ajouté uniquement pour matérialiser un dossier ;
- `TODO.md` vide ;
- `CHANGELOG_TEMPLATE.md` sans release réelle ;
- dossier `release/` vide ;
- dossier `docs/` vide ;
- dossier `research/` vide ;
- squelette `PRODUCT.md` identique pour tous les scripts ;
- `ARCHITECTURE.md` rempli de rubriques sans contenu réel ;
- placeholders destinés à être « remplis plus tard » sans besoin immédiat.

### 2.5 Git local-first

Le workspace utilise Git local.

Le bootstrap :

- initialise Git local si nécessaire ;
- ne crée aucun remote ;
- ne configure pas GitHub ni GitHub Actions ;
- ne dépend pas du CLI `gh` ;
- ne pousse rien vers un service distant.

GitHub n’est jamais une dépendance par défaut. Depuis la décision ratifiée du 2026-11-06, un **parcours d’export explicite** existe (§43.5) : destinations configurées dans `pws.config.json`, liste de contenus autorisés par profil de licence, plan et aperçu des fichiers inclus/exclus, publication ou mise à jour seulement après autorisation explicite du titulaire ; `gh` sert en lecture (`auth status`, `repo view`) et jamais pour un acte destructif ; aucun jeton n’est stocké par le workspace. Ce parcours n’introduit ni remote dans le workspace, ni CI distante, ni push implicite.

### 2.6 TradingView reste la vérité empirique finale pour TradingView

Aucune vérification locale ne constitue une validation TradingView.

Le workspace distingue strictement trois couches :

```text
STATIC / DETERMINISTIC CHECKS
≠
LOCAL BEHAVIORAL EXECUTION
≠
TRADINGVIEW VALIDATION
```

`STATIC / DETERMINISTIC CHECKS` vérifie uniquement ce qui peut être établi localement de manière mécanique et fiable.

`LOCAL BEHAVIORAL EXECUTION` exécute le source Pine hors de TradingView afin d’observer son comportement sur des données contrôlées et reproductibles. Cette couche peut notamment détecter des erreurs d’exécution, divergences comportementales, régressions, anomalies de stabilité ou edge cases selon les capabilities réellement qualifiées par son moteur.

PineTS est le backend initial retenu pour cette couche.

PineTS est un laboratoire local d’exécution comportementale. Il n’est ni une autorité normative sur la syntaxe ou la sémantique officielle Pine Script, ni une implémentation officielle TradingView, ni une preuve générale de compatibilité TradingView.

Dans un contrat local strictement borné, PineTS peut toutefois produire une conclusion comportementale localement gating lorsque toutes les capabilities matériellement nécessaires sont `GATING`, que leur calibration est `CURRENT`, et que le source, le dataset, la configuration et l’environnement d’exécution sont exactement identifiés.

`TRADINGVIEW VALIDATION` reste la validation empirique finale de tout comportement propre à la plateforme TradingView et de toute étape `tv-validate`.

Aucun résultat PineTS, quelle que soit sa qualité, ne peut :

- devenir une validation TradingView ;
- satisfaire à lui seul une étape `tv-validate` ;
- transformer un état persisté `unverified` ou `in-progress` en validation réussie ;
- prouver une parité TradingView qui n’a pas été observée réellement dans TradingView.

Inversement, une conclusion PineTS localement gating n’est pas annulée du seul fait qu’elle n’est pas une validation TradingView : elle peut bloquer le cycle local tant que le contrat comportemental local concerné n’est pas résolu, requalifié ou explicitement rendu non gating selon les règles de cette spécification.

Claude Code ne doit jamais déclarer un script validé dans TradingView lorsqu’aucune validation réelle n’a été exécutée sur le source exact concerné.

### 2.7 Deux modes TradingView

Le workspace doit supporter :

```text
manual
chrome-experimental
```

`manual` est le mode initial et stable.

`chrome-experimental` automatise autant que possible le même protocole de validation dans TradingView via les capacités navigateur de Claude Code.

En cas d’ambiguïté, d’échec, de login, de CAPTCHA, de changement d’interface, d’action non vérifiable ou de résultat visuel incertain :

```text
chrome-experimental
        ↓
fallback du run
        ↓
manual
```

Le fallback d’un run ne modifie pas automatiquement le mode enregistré.

Seul le titulaire change le mode persistant.

### 2.8 Publication jamais implicite

La validation automatisée du Pine Editor ne donne pas à Claude l’autorisation de publier.

Le bootstrap initial ne doit créer aucune automatisation qui :

- clique automatiquement sur une publication publique ;
- publie une nouvelle version ;
- modifie un accès `invite-only` ;
- modifie une relation commerciale ;
- change une visibilité ;
- effectue une action difficilement réversible.

La publication reste sous contrôle explicite du titulaire.

### 2.9 Mémoire automatique non normative

Si l’auto-memory Claude Code est active, elle peut retenir :

- apprentissages de debug ;
- particularités pratiques du repo ;
- commandes utiles ;
- observations non normatives.

Elle ne devient jamais l’unique source de :

- décision produit ;
- contrat de signal ;
- modèle de distribution ;
- règle de release ;
- Convention Personnelle ;
- décision de licence ;
- invariant métier durable.

Toute information durable de cette nature doit être promue dans un fichier versionné approprié.

Les apprentissages opérationnels liés à `chrome-experimental` suivent en plus le contrat de §31.9. L’auto-memory peut retenir temporairement une observation candidate, mais toute connaissance opérationnelle destinée à être réutilisée durablement doit être explicitement qualifiée puis promue dans `.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md`.

Une observation non promue reste non normative et ne doit pas être supposée vraie lors d’un run futur.

Le bootstrap ne doit pas forcer l’activation ou la désactivation de l’auto-memory de l’utilisateur.

### 2.10 PINE WORKSPACE PROJECT-INDEPENDENCE INVARIANT

Pine Workspace est un environnement de développement Pine Script V6 autonome.

Son bootstrap, son fonctionnement, sa validation, ses outils, sa documentation et son organisation ne doivent dépendre de l’existence, du nom, du chemin ou de l’état d’un autre projet externe.

Pine Workspace peut coexister avec d’autres projets dans un même répertoire parent, mais cette coexistence ne constitue ni une dépendance ni une autorisation de scanner, modifier ou suivre des symlinks vers ces autres projets.

---

## 3. SOURCES D’AUTORITÉ

Ne pas réduire ces sources à une hiérarchie simpliste qui détruirait leur rôle propre.

Leurs responsabilités sont complémentaires :

- l'objectif produit explicite et les décisions ratifiées définissent le résultat recherché ;
- la documentation officielle actuelle est l'autorité technique pour Claude Code, Pine Script et TradingView dans leurs périmètres respectifs ;
- cette spécification ratifiée est le contrat de construction du workspace ;
- le standard maître définit la méthode, la qualité, les conventions, l'UX, la documentation et l'identité produit Pine ;
- le contexte spécifique du script définit l'applicabilité locale et les invariants du produit concerné.

Une source ne doit pas être utilisée pour usurper la responsabilité d'une autre. Tout conflit réel ou apparent doit être signalé explicitement au titulaire avec les passages concernés ; il ne doit jamais être résolu silencieusement par un ordre de priorité inventé.

### 3.1 Objectif du titulaire

Définit CE QUE le produit doit accomplir.

### 3.2 Documentation officielle TradingView / Pine Script actuelle

Autorité technique pour :

- syntaxe ;
- APIs ;
- sémantique ;
- limitations ;
- runtime ;
- historical/realtime ;
- requests ;
- MTF ;
- publication ;
- règles techniques actuelles.

### 3.3 Standard maître le titulaire Pine Script

Définit les conventions de développement, qualité, UX, architecture, documentation et produit.

### 3.4 Contexte spécifique du script

Décrit la réalité et les invariants propres au produit concerné.

### 3.5 Décisions explicites du titulaire

Gouvernent les décisions produit ratifiées qui ne sont pas déductibles du code ou de la documentation technique.

En cas de conflit Pine/TradingView, appliquer la méthode de résolution définie dans le standard maître. Pour un conflit de construction du workspace ou de primitive Claude Code, confronter la spécification à la documentation officielle actuelle, signaler l'écart et demander une décision lorsqu'il ne peut pas être résolu sans modifier le contrat ratifié.

---

## 4. CATÉGORIES DE FICHIERS

Le bootstrap doit attribuer explicitement une catégorie à chaque artefact durable.

### 4.1 Normatif Pine

Exemple :

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Ne peut pas être régénéré depuis un résumé.

### 4.2 Normatif architecture workspace

Cette spécification de bootstrap constitue le contrat de construction du workspace.

L'instance canonique est conservée sous :

```text
docs/architecture/BOOTSTRAP_SPEC.md
```

Elle n’est pas chargée automatiquement dans chaque session.

### 4.3 Dérivé

Exemples :

- `standards/INDEX.md` ;
- `standards/TRACEABILITY.md` ;
- synthèses de recherche ;
- états de validation ;
- cartographies produites à partir du code.

Un artefact dérivé doit pouvoir être déclaré périmé.

### 4.4 Opérationnel

Exemples :

- `CLAUDE.md` ;
- rules ;
- skills ;
- agents ;
- settings ;
- outils déterministes.

Un artefact opérationnel matérialise une procédure ou un mécanisme.

Il ne doit pas devenir une deuxième constitution.

### 4.5 Preuve

Exemples :

- rapport de validation TradingView ;
- capture d’écran utile ;
- journal de test ;
- hash du source réellement testé.

Une preuve décrit une observation réelle.

Elle n’est pas une opinion.

### 4.6 Éphémère

Exemples :

- état de session d’un hook ;
- cache local ;
- fichiers temporaires.

Ces éléments sont gitignored et ne deviennent jamais une autorité durable.

---

## 5. ÉTAT INITIAL MINIMAL

Le bootstrap doit accepter un projet presque vide.

Entrées nécessaires :

1. cette spécification ;
2. le fichier maître le titulaire Pine Script ;
3. Claude Code installé ;
4. Git disponible ou installable localement ;
5. un runtime local approprié pour les petits outils déterministes.

Le bootstrap doit identifier sans ambiguïté le fichier maître.

S’il trouve plusieurs candidats plausibles, il demande au titulaire lequel est canonique.

Il ne choisit pas silencieusement.

Le fichier maître est ensuite déplacé explicitement, sans duplication normative, à :

```text
standards/PINE_SCRIPT_V6_STANDARD.md
```

Calculer son SHA-256 avant et après déplacement et vérifier l’identité du contenu.

La présente spécification est de même déplacée explicitement vers :

```text
docs/architecture/BOOTSTRAP_SPEC.md
```

Calculer son SHA-256 avant et après déplacement et vérifier l'identité du contenu.

Consigner dans `BOOTSTRAP_REPORT.md` les deux mappings `ancien chemin → chemin canonique`, les hashes avant/après et toute raison empêchant exceptionnellement un déplacement. Une copie d'entrée conservée pour une nécessité démontrée doit être explicitement marquée non normative ; aucune double autorité silencieuse n'est admise.

---

## 6. DISCOVERY AVANT TOUTE ÉCRITURE

Avant de créer l’arborescence finale, Claude Code doit effectuer une vraie phase de discovery.

### 6.1 Environnement

Détecter notamment :

- OS ;
- shell ;
- présence éventuelle de WSL ;
- version Claude Code ;
- chemin du projet ;
- version Git ;
- état Git ;
- branche courante ;
- remotes existants ;
- runtime Python 3 ou alternative locale ;
- runtime Node.js et gestionnaire de paquets disponibles pour la couche PineTS ;
- présence éventuelle d’une installation, configuration ou version PineTS préexistante dans le workspace ;
- capacités navigateur Claude Code réellement disponibles ;
- configuration locale Claude déjà existante ;
- fichiers `.claude/` déjà présents.

Avant toute écriture, établir aussi la frontière physique du workspace :

1. résoudre le chemin physique du workspace sans perdre la prise en charge des espaces ;
2. déterminer la racine Git effective, notamment par `git rev-parse --show-toplevel` lorsqu'applicable ;
3. rechercher si un repository parent englobe le dossier `pine workspace` ;
4. si une racine Git englobante existe au-dessus du workspace attendu, arrêter avant mutation et demander une décision au titulaire ;
5. refuser tout scan récursif, toute mutation ou tout suivi de symlink depuis le workspace vers le contenu d’un autre projet ou vers un emplacement extérieur à sa racine physique ;
6. manipuler les chemins par des objets de chemin ou des arguments structurés, jamais par concaténation shell fragile.

La discovery et les tests doivent couvrir une racine de workspace et un nom de source contenant des espaces.

L’absence de Node.js ou de PineTS ne doit jamais être interprétée comme un défaut du source Pine.

Si la couche PineTS ne peut pas être initialisée proprement, le workspace reste fonctionnel et les validations TradingView restent disponibles selon leur workflow normal.

Avant toute installation initiale ou mise à niveau de PineTS, vérifier la version, la documentation, la licence et les limitations actuelles du projet upstream. Le choix de version doit partir du registry npm actuel et de l'artefact exact réellement installable, puis être confirmé par les métadonnées du paquet, le tarball installé et le lockfile ; ne pas déduire la version depuis `main`, un README, un badge ou la page Releases seuls.

### 6.2 Documentation Claude Code actuelle

Vérifier dans la documentation officielle actuelle les primitives réellement disponibles avant de générer leur configuration.

Au minimum :

- `CLAUDE.md` ;
- `.claude/rules/` ;
- project skills ;
- custom subagents ;
- hooks ;
- project/local settings ;
- permission rules ;
- worktrees ;
- `.worktreeinclude` ;
- Chrome integration ;
- diagnostics de configuration.

Vérifier également la résolution effective des noms de skills critiques et la précédence actuelle entre skills personnelles, projet et autres sources afin de détecter toute collision qui détournerait `/pws`, `/tv-mode` ou une autre commande critique.

Ne pas se fier uniquement à cette spécification si Claude Code a évolué.

### 6.3 Documentation TradingView actuelle

Vérifier au minimum que la documentation Pine V6 actuelle est accessible.

La construction du workspace ne doit pas figer des limites numériques Pine qui peuvent évoluer.

### 6.4 Analyse complète du standard maître

Lire intégralement le standard maître avant de concevoir :

- rules ;
- skills ;
- agents ;
- checks ;
- workflows.

Construire une matrice interne :

```text
exigence
→ permanence
→ contexte d’application
→ primitive Claude Code adaptée
→ type de contrôle
→ artefact responsable
```

Exemples conceptuels :

```text
Recherche Pine actuelle
→ par tâche
→ développement Pine
→ skill + researcher
→ sémantique

Interdiction shorttitle
→ règle mécanique
→ source Pine
→ local guard
→ déterministe

Exécution comportementale locale
→ selon applicabilité
→ source Pine modifié
→ pine-local-test + thin adapter PineTS
→ comportemental local capability-gated

Validation TradingView
→ fin de cycle
→ source Pine modifié
→ tv-validate
→ empirique
```

---

## 7. DESIGN GATE AVANT CRÉATION DES FICHIERS

Avant d’écrire l’architecture finale, Claude Code doit justifier chaque artefact envisagé.

Pour chaque fichier ou dossier :

1. Quelle responsabilité possède-t-il ?
2. Quelle source d’autorité alimente son contenu ?
3. Qui le lit ?
4. Quand est-il chargé ?
5. Qui le modifie ?
6. Est-il normatif, dérivé, opérationnel, preuve ou éphémère ?
7. Son contenu existe-t-il déjà ailleurs ?
8. Une primitive Claude Code native est-elle meilleure ?
9. Peut-il être créé seulement au moment où il devient nécessaire ?
10. Comment détecter qu’il est périmé ?
11. Quel défaut concret apparaît s’il n’existe pas ?

Si les réponses ne justifient pas l’artefact, ne pas le créer.

---

## 8. CRITIQUE INDÉPENDANTE AVANT IMPLÉMENTATION

Avant la création définitive, exécuter une revue indépendante de l’architecture proposée.

Cette revue doit rechercher :

- duplication du standard maître ;
- règles contradictoires ;
- règles toujours chargées alors qu’elles pourraient être conditionnelles ;
- skills trop longues ;
- agents inutiles ;
- hooks qui tentent de juger de la sémantique ;
- fichiers génériques ;
- états dupliqués ;
- registres centraux qui pourraient dériver ;
- dépendances externes inutiles ;
- sur-automatisation ;
- fonctions Claude Code inventées ou obsolètes ;
- responsabilités sans propriétaire ;
- conventions du standard non opérationnalisées.

Corriger l’architecture avant écriture.

---

## 9. ARCHITECTURE CIBLE

L’architecture ci-dessous est le résultat attendu à maturité.

Les dossiers marqués « à la demande » ne doivent pas être créés tant qu’ils ne servent pas.

```text
<workspace-root>/
│
├── CLAUDE.md
├── README.md
├── .gitignore
├── .worktreeinclude
│
├── .claude/
│   ├── settings.json
│   ├── settings.local.json              # local, gitignored
│   │
│   ├── rules/
│   │   ├── pine-source.md
│   │   ├── script-context.md
│   │   ├── research.md
│   │   ├── validation.md
│   │   ├── pinets-behavioral.md
│   │   ├── documentation.md
│   │   └── release.md
│   │
│   ├── skills/
│   │   ├── pws/
│   │   │   └── SKILL.md
│   │   ├── pine-onboard/
│   │   │   └── SKILL.md
│   │   ├── pine-new/
│   │   │   └── SKILL.md
│   │   ├── pine-develop/
│   │   │   └── SKILL.md
│   │   ├── pine-research/
│   │   │   └── SKILL.md
│   │   ├── pine-review/
│   │   │   └── SKILL.md
│   │   ├── pine-local-test/
│   │   │   └── SKILL.md
│   │   ├── pine-release/
│   │   │   └── SKILL.md
│   │   ├── tv-validate/
│   │   │   ├── SKILL.md
│   │   │   ├── MANUAL.md
│   │   │   └── CHROME_EXPERIMENTAL.md
│   │   ├── tv-mode/
│   │   │   └── SKILL.md
│   │   └── project-doctor/
│   │       └── SKILL.md
│   │
│   └── agents/
│       ├── pws-pine-cartographer.md
│       ├── pws-pine-researcher.md
│       ├── pws-pine-reviewer.md
│       └── pws-release-reviewer.md
│
├── standards/
│   ├── PINE_SCRIPT_V6_STANDARD.md
│   ├── INDEX.md
│   └── TRACEABILITY.md
│
├── scripts/
│   └── <script-slug>/                   # seulement pour un vrai produit
│       ├── CLAUDE.md
│       ├── SCRIPT.json
│       ├── <actual-source>.pine
│       ├── PRODUCT.md
│       ├── ARCHITECTURE.md
│       ├── DECISIONS.md                 # à la demande
│       ├── research/                    # à la demande
│       │   ├── CURRENT.md
│       │   └── runs/
│       ├── tests/                       # à la demande
│       │   └── behavioral/              # à la demande
│       │       ├── config.json          # seulement si un contrat de test existe
│       │       ├── fixtures/            # seulement si spécifiques au produit
│       │       └── baselines/           # seulement pour des baselines acceptées
│       ├── validation/
│       │   ├── current.json
│       │   ├── runs/                    # à la première validation
│       │   └── evidence/                # uniquement si preuve fichier utile
│       ├── docs/                        # à la demande
│       └── release/                     # à la demande
│
├── docs/
│   └── architecture/
│       ├── BOOTSTRAP_SPEC.md
│       ├── ARCHITECTURE.md
│       ├── FILE_CONTRACTS.md
│       ├── OPERATIONS.md
│       └── BOOTSTRAP_REPORT.md
│
└── tools/
    ├── pws_workspace/
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── core.py
    │   ├── scan.py
    │   ├── standard.py
    │   ├── guard.py
    │   ├── validation.py
    │   └── tv_mode.py
    ├── pine_exec/
    │   ├── package.json
    │   ├── package-lock.json
    │   ├── runner.mjs
    │   ├── normalize.mjs
    │   └── calibration/
    └── tests/
        ├── test_scan.py
        ├── test_standard.py
        ├── test_guard.py
        ├── test_validation.py
        ├── test_tv_mode.py
        └── test_pine_exec.py             # ou factorisation équivalente justifiée
```

Le découpage interne exact du package Python peut être légèrement ajusté si l’analyse réelle démontre une meilleure factorisation.

Il ne doit toutefois pas devenir un framework volumineux.

`tools/pine_exec/` est un thin adapter Node minimal autour de PineTS.

Il ne doit pas devenir :

- une plateforme locale ;
- un serveur ;
- un service réseau ;
- un MCP ;
- une base de données ;
- un dashboard ;
- un framework de backtesting généraliste ;
- un clone fonctionnel de TradingView ou de LuxAlgo Quant.

Le découpage interne du thin adapter peut être légèrement ajusté si l’implémentation réelle le justifie, mais sa responsabilité reste limitée à :

```text
source Pine
+
dataset
+
configuration
+
capability state
        ↓
PineTS
        ↓
sortie normalisée
```

Les résultats d’exécution temporaires ne doivent pas être stockés durablement dans l’arbre produit par défaut.

`tests/behavioral/` contient uniquement les contrats, fixtures spécifiques et baselines ayant une utilité durable.

`validation/` reste exclusivement réservé à la validation TradingView et à ses preuves.

### 9.1 Conventions communes aux rules

Toutes les rules du socle initial doivent posséder un scope `paths` réel.

Une rule sans `paths` serait chargée à chaque session et doit donc être rejetée sauf justification exceptionnelle démontrée.

### 9.2 Conventions communes aux skills

Pour chaque skill :

- écrire une `description` courte, spécifique et suffisamment distincte pour éviter les déclenchements ambigus ;
- utiliser uniquement les outils réellement nécessaires ;
- garder `SKILL.md` concis ; la documentation Claude Code actuelle recommande moins de 500 lignes ;
- déplacer les références détaillées dans des fichiers de support uniquement lorsqu’elles apportent une vraie valeur ;
- ne pas créer un fichier de support qui ne serait qu’une copie d’une partie du standard maître ;
- réserver `disable-model-invocation: true` aux actions que le titulaire doit déclencher lui-même.

Les descriptions des skills font partie du contexte de découverte. Elles doivent donc être informatives sans devenir de mini-prompts.

### 9.3 Conventions communes aux subagents

Chaque agent doit avoir :

- une mission qui ne recouvre pas celle d’un autre agent ;
- le minimum d’outils requis ;
- une politique explicite d’écriture ;
- une politique explicite de mémoire ;
- un format de retour utile au parent.

Les quatre agents du socle initial sont spécialisés dans lecture, recherche ou revue. Ils ne doivent pas modifier le source Pine.

---

## 10. `CLAUDE.md` RACINE — CONTRAT

### 10.1 Rôle

Routeur permanent du workspace.

### 10.2 Taille

Viser nettement moins de 200 lignes.

### 10.3 Contenu nécessaire

Il doit contenir uniquement ce que Claude doit connaître dans presque toutes les sessions :

- identité du workspace ;
- mission générale ;
- invariant d’indépendance envers tout autre projet externe et confinement à la racine physique du workspace ;
- rôles des sources d’autorité ;
- chemin canonique du standard maître ;
- carte très courte du repo ;
- règles universelles de langue ;
- interdiction d’inventer des faits ;
- interdiction de modifier la constitution sans demande explicite ;
- politique Git local-first ;
- politique mémoire non normative ;
- règle de détection/onboarding des `.pine` non enregistrés ;
- routage vers le menu contextuel PWS et les principales skills ;
- séparation stricte entre checks déterministes, exécution comportementale locale PineTS et validation TradingView ;
- rappel que PineTS est capability-gated, peut produire une gate locale sur un contrat strictement borné, et ne remplace jamais l’autorité officielle Pine Script ni la validation empirique TradingView ;
- interdiction de déclarer un succès TradingView fictif ;
- interdiction de publication implicite.

### 10.4 Ce qui n’y appartient pas

Ne pas recopier :

- conventions Pine détaillées ;
- règles de tooltip ;
- palettes ;
- SemVer complet ;
- procédures de release ;
- workflow complet de recherche ;
- checklist MTF ;
- guide TradingView ;
- contenu du standard maître.

### 10.5 Import

Ne pas importer le standard maître avec `@`.

Référencer son chemin en code inline.

---

## 11. `README.md` — CONTRAT

### 11.1 Public

Humain.

### 11.2 Fonction

Présenter rapidement :

- but du workspace ;
- autonomie du workspace et absence de projet sibling requis ;
- emplacement des scripts ;
- comment ajouter un script existant ;
- comment demander un nouveau script ;
- comment lancer Claude Code ;
- comment changer le mode TradingView ;
- comment lancer `project-doctor` ;
- principe Git local.

### 11.3 Non-duplication

Les procédures détaillées vont dans `docs/architecture/OPERATIONS.md`.

Le README ne devient pas un second manuel.

---

## 12. `standards/INDEX.md` — CONTRAT

### 12.1 Statut

Dérivé, non normatif.

### 12.2 Source

`PINE_SCRIPT_V6_STANDARD.md`.

### 12.3 Contenu

Inclure :

- SHA-256 du standard source ;
- date de génération ;
- sections ;
- titres exacts ;
- lignes courantes ou plages utiles ;
- mots-clés de routage ;
- principaux consommateurs opérationnels.

### 12.4 Règle de fraîcheur

Si :

```text
SHA(master) != SHA enregistré dans INDEX
```

l’index est `STALE`.

Il ne doit plus être utilisé comme représentation fiable tant qu’il n’est pas régénéré.

### 12.5 Génération

Générer automatiquement à partir des headings réels du standard.

Ne pas inventer des sections.

---

## 13. `standards/TRACEABILITY.md` — CONTRAT

### 13.1 Statut

Dérivé architectural, non normatif.

### 13.2 But

Montrer où chaque partie du standard maître est opérationnalisée.

Exemple de structure :

```text
Section du standard
→ contexte/rule
→ skill
→ agent éventuel
→ check déterministe éventuel
→ exécution comportementale locale éventuelle
→ validation empirique éventuelle
```

### 13.3 Utilité

Empêcher :

- omission d’une convention ;
- duplication inutile ;
- création de règles concurrentes ;
- oubli d’un mécanisme lors d’une future évolution du standard.

### 13.4 Fraîcheur

Stocker le SHA-256 du standard maître.

Toute modification du master rend la traceability `STALE` jusqu’à revue.

La régénération demande une analyse sémantique.

Ne pas prétendre qu’un simple parser peut recréer correctement cette cartographie.

---

## 14. `ARCHITECTURE.md` DU WORKSPACE — CONTRAT

Expliquer les décisions et surtout leurs raisons.

Inclure notamment :

- pourquoi le master est unique ;
- pourquoi le workspace ne dépend de l’existence, du nom, du chemin ou de l’état d’aucun autre projet ;
- pourquoi il n’est pas importé dans `CLAUDE.md` ;
- pourquoi les rules sont path-scoped ;
- pourquoi les procédures vont dans des skills ;
- pourquoi les gros travaux utilisent des subagents frais ;
- pourquoi les agents de revue n’ont pas de mémoire persistante ;
- pourquoi les checks locaux restent mécaniques ;
- pourquoi l’exécution comportementale locale est séparée des checks déterministes ;
- pourquoi PineTS peut être une autorité d’exécution locale capability-gated sur un contrat borné sans concurrencer la documentation officielle Pine Script ni TradingView comme autorité sur le comportement propre à la plateforme ;
- pourquoi TradingView est une couche empirique séparée ;
- pourquoi Git est local-first ;
- pourquoi aucune registry centrale des scripts n’existe ;
- pourquoi les contextes script sont co-localisés ;
- pourquoi les dossiers de release/docs/research sont à la demande ;
- pourquoi GitHub, MCP, Agent Teams, dynamic workflows et CI distante ne sont pas des dépendances initiales.

Ne pas reformuler tout le standard Pine.

---

## 15. `FILE_CONTRACTS.md` — CONTRAT

Pour chaque artefact durable du workspace, documenter :

- responsabilité ;
- catégorie ;
- source d’autorité ;
- lecteur ;
- writer ;
- déclencheur de création ;
- déclencheur de mise à jour ;
- statut de fraîcheur éventuel ;
- contenu interdit ;
- doublons qu’il doit éviter ;
- test d’utilité.

Ce fichier sert de garde contre les artefacts décoratifs.

---

## 16. `OPERATIONS.md` — CONTRAT

Document humain concis pour les opérations récurrentes.

Doit décrire :

- que Pine Workspace fonctionne de façon autonome, sans projet sibling requis, et doit être lancé depuis sa propre racine physique ;
- ouvrir ou réouvrir le menu contextuel PWS ;
- ajouter un `.pine` existant ;
- créer un nouveau produit avec Claude Code ;
- lancer le doctor ;
- comprendre les axes `source_registration_status`, `product_structure_status` et `validation_effective_status`, notamment `UNREGISTERED`, `INCOMPLETE`, `BROKEN` et `stale` ;
- changer le mode TradingView ;
- lancer une validation manuelle ;
- lancer une validation expérimentale Chrome ;
- lancer `pine-local-test` lorsqu’un test comportemental local est applicable ;
- interpréter `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL`, `PINETS_INCONCLUSIVE` et les changements de régression sans les confondre avec une validation TradingView ;
- effectuer une mise à niveau contrôlée de PineTS avec recalibration obligatoire ;
- utiliser un worktree quand un chantier le justifie ;
- comportement Git local ;
- stratégie de sauvegarde locale optionnelle.

Ne pas recopier les règles de développement Pine.

---

## 17. `.gitignore` — CONTRAT

Doit ignorer au minimum les éléments réellement locaux ou éphémères produits par ce workspace.

Exemples applicables :

```text
.claude/settings.local.json
CLAUDE.local.md
.claude/runtime/
tools/pine_exec/node_modules/
.claude/worktrees/
.claude/runtime/pine-local-test/
__pycache__/
*.pyc
```

Ajouter les artefacts OS/editor réellement présents seulement si nécessaire.

Ne pas copier une énorme `.gitignore` générique depuis Internet.

Ne jamais ignorer :

- `.pine` ;
- contextes script versionnés ;
- standard maître ;
- rules ;
- skills ;
- agents ;
- rapports de validation destinés à persister ;
- `tools/pine_exec/package.json` ;
- `tools/pine_exec/package-lock.json` ;
- `tools/pine_exec/calibration/` ;
- `scripts/**/tests/behavioral/config.json`, fixtures et baselines lorsqu’ils existent et ont une utilité durable.

---

## 18. `.worktreeinclude` — CONTRAT

But : préserver dans les worktrees les fichiers locaux gitignored dont le workflow dépend.

Inclure au minimum, lorsqu’ils existent :

```text
.claude/settings.local.json
CLAUDE.local.md
```

Ne pas recopier des secrets non nécessaires.

`.worktreeinclude` ne constitue jamais un mécanisme de backup.

---

## 19. `.claude/settings.local.json` — CONTRAT

### 19.1 Statut

Local, gitignored. Depuis l’amendement du 2026-11-06, ce fichier appartient à Claude Code seul (approvals et réglages locaux de l’outil) : le workspace n’y écrit plus. La configuration propre à PWS vit dans `pws.config.json` (§19A).

### 19.2 Valeur initiale

Aucune valeur PWS n’y est initialisée. Historique : jusqu’au 2026-11-06, le mode TradingView y était persisté sous `env.PWS_TV_VALIDATION_MODE` ; cette clé est lue par compatibilité tant qu’elle existe (jamais à travers un lien symbolique), puis réglée par la migration (`migrate --apply`, étapes m001/m003, règle §19A du 2026-11-13 : copiée si `pws.config.json` n’a pas de mode exploitable, conservée dans la configuration si les valeurs concordent ou si le titulaire a choisi explicitement, conflit bloqué jusqu’à son choix sinon) et retirée seulement ensuite, sans toucher aucune autre clé.

### 19.3 Évolution

Ce fichier reçoit les approvals locaux que Claude Code y conserve. Le workspace ne les écrase jamais ; la seule écriture PWS admise est le retrait, une fois, de la clé legacy ci-dessus par la migration, sous verrou, avec préservation de toutes les autres clés et refus de conflit.

### 19A. `pws.config.json` — CONTRAT (ratifié le 2026-11-06)

Fichier personnel à la racine du workspace, gitignored, copié dans les worktrees via `.worktreeinclude`, jamais inclus dans une distribution. Schéma 1 : `schema_version`, `workspace_version` (version du cœur enregistrée par `init`/`migrate`), `language` (`en` par défaut en nouvelle installation, `fr` conservé par l’installation migrée), `identity` (`copyright_holder`, `header_aliases`, `default_profile`), `tv_validation_mode` (`manual` par défaut, `chrome-experimental` explicitement optionnel ; `tv_validation_mode_choice` facultatif = provenance d'un choix explicite du titulaire par `tv-mode` ou `config set`, qui seule résout un conflit avec une valeur héritée — migration m001, règle décidée par le titulaire le 2026-11-13), `github.destinations`, `maintenance.startup_cleanup`, `migrations`. Lecture tolérante : fichier absent → valeurs par défaut (jamais une erreur) ; fichier invalide → défauts plus diagnostic actionnable (doctor BLOCKING). Écritures : `init`, `config set`, `tv-mode <mode>`, `github destination-*`, `migrate`, toutes par le même contrôleur de configuration (`tools/pws_workspace/config.py`).

La source persistée du mode TradingView est `pws.config.json`, pas une variable héritée par le processus. Toute mutation doit :

1. lire le fichier courant ;
2. valider qu'il n'a pas changé entre lecture et écriture ;
3. effectuer un read-modify-write qui préserve toutes les autres clés, notamment les approvals ;
4. écrire un fichier temporaire dans le même filesystem puis effectuer un remplacement atomique ;
5. relire et valider le JSON résultant ;
6. signaler un conflit au lieu d'écraser silencieusement toute modification concurrente détectée entre la lecture initiale et la relecture précédant le remplacement atomique.

La portée de ces garanties :

- entre écrivains du workspace (le contrôleur de configuration et tout outil PWS), la sérialisation est garantie par un verrou exclusif partagé (`pws.config.json.lock`) couvrant l'intégralité de la transaction lecture-vérification-écriture ;
- `pws.config.json` n'a pas d'écrivain externe connu (Claude Code n'y écrit pas) : la fenêtre résiduelle documentée le 2026-09-06 pour `settings.local.json` ne s'applique plus au mode TradingView ; elle reste vraie pour `settings.local.json` lui-même, que le workspace n'écrit plus hors de la migration legacy ;
- si une version future de Claude Code expose un mécanisme de coordination pour ses fichiers, le contrôleur doit être réévalué pour l'utiliser.

Après écriture, relire via le contrôleur (`tv-mode` sans argument) que la valeur persistée est celle attendue. Une variable de processus n'est jamais un chemin de lecture.

---

## 20. `.claude/settings.json` — CONTRAT

### 20.1 Worktrees

Configurer :

```json
{
  "worktree": {
    "baseRef": "head"
  }
}
```

si cette syntaxe est toujours valide dans la version installée.

Le but est de faire partir les worktrees du `HEAD` local, sans dépendre d’un remote.

### 20.2 Permissions

Configurer une politique locale prudente.

Principes :

- lecture Git courante : autorisable ;
- `git diff`, `git status`, `git log`, `git show` : usage normal ;
- `git commit` : confirmation utilisateur ;
- création/modification/suppression d’un remote : confirmation utilisateur ;
- `git push` : confirmation utilisateur (jamais d’autorisation générale ; `--force` refusé) ;
- `gh` : lecture seule autorisée (`auth status`, `repo view`) ; `auth login`, `repo create` : confirmation ; `repo delete`, `api`, `secret`, `auth token` : refus ;
- sous-commandes PWS en lecture seule : autorisables ; sous-commandes mutantes à effet externe ou irréversible (`github publish`, `github fetch`, `pinets install`, `pinets rollback`, `pinets check-update`, `migrate --apply`, `migrate --rollback`, `maintenance archives-remove-source`) : confirmation ;
- commandes Git destructrices : confirmation ou refus selon gravité ;
- contournement de permissions : ne pas l’activer depuis le projet.

Vérifier la syntaxe actuelle `allow` / `ask` / `deny`.

Ne jamais ajouter une permission large uniquement pour éviter des prompts.

### 20.3 Hooks

Configurer uniquement les hooks justifiés dans cette spécification.

### 20.4 Sandbox

Ne pas activer ou désactiver arbitrairement un sandbox système sans vérifier :

- OS ;
- support ;
- impact ;
- configuration existante du titulaire.

Le bootstrap peut recommander une configuration, mais ne doit pas modifier une politique système hors projet sans nécessité et consentement.

---

## 21. RULES PATH-SCOPED

Les rules doivent rester courtes.

Elles ne doivent pas contenir la totalité du master.

### 21.1 `pine-source.md`

Scope :

```yaml
paths:
  - "scripts/**/*.pine"
```

Mission :

- reconnaître un source Pine le titulaire ;
- vérifier que le produit est onboardé avant modification substantielle ;
- pointer vers le contexte local du script ;
- pointer vers le standard maître sans l’importer ;
- rappeler le workflow `pine-develop` ;
- rappeler que checks déterministes, exécution comportementale PineTS et validation TradingView sont trois couches distinctes ;
- router vers `pine-local-test` lorsque le workflow ou le risque de modification justifie une exécution locale ;
- interdire toute modification du source Pine dont la seule justification serait de satisfaire une incompatibilité, limitation ou divergence PineTS.

Ne pas recopier toutes les conventions Pine.

### 21.2 `script-context.md`

Scope sur :

- `SCRIPT.json` ;
- `PRODUCT.md` ;
- `ARCHITECTURE.md` ;
- `DECISIONS.md` lorsqu’il existe ;
- `CLAUDE.md` dans les dossiers produits.

Règle principale :

> Ne jamais transformer une observation ou une inférence en décision le titulaire.

Distinguer :

- observé ;
- confirmé ;
- inféré ;
- à confirmer.

Les provenances suivantes restent distinctes et ne se substituent jamais l’une à l’autre : observation dans le source ; fait de documentation officielle daté ; observation de benchmark datée ; inférence ; confirmation par le titulaire d’une observation ; ratification par le titulaire d’une décision produit. Une preuve absente signifie non démontré, jamais non effectué.

### 21.3 `research.md`

Scope :

```text
scripts/**/research/**
```

Exiger :

- date ;
- question ;
- sources ;
- faits ;
- conclusions ;
- distinction observation/inférence ;
- statut de fraîcheur.

### 21.4 `validation.md`

Scope :

```text
scripts/**/validation/**
```

Interdire :

- `validated` sans run réel ;
- preuve non liée au hash du source ;
- confusion entre test local et TradingView ;
- modification manuelle trompeuse de l’état.

### 21.5 `documentation.md`

Scope sur les docs user-facing des scripts.

Doit router vers les sections applicables du standard.

Ne pas dupliquer le style complet des tutoriels.

### 21.6 `release.md`

Scope sur les artefacts de release.

Doit imposer :

- relecture des règles TradingView actuelles ;
- application de `pine-release` ;
- interdiction de publication automatique implicite.

### 21.7 `pinets-behavioral.md`

Scopes :

```yaml
paths:
  - "tools/pine_exec/calibration/**"
  - "scripts/**/tests/behavioral/**"
```

Cette rule reste concise et protège uniquement les invariants capables de modifier une gate locale :

- aucune promotion `GATING` sans calibration indépendante suffisante ;
- application des causes de staleness de §24.4.5 ;
- baseline durable uniquement après acceptation conforme à §24.4.10 ;
- aucune écriture de preuve PineTS sous `validation/` ;
- aucune modification du source Pine dont la seule justification serait de satisfaire PineTS.

Elle route vers le contrat `pine-local-test` au lieu de recopier toute la doctrine PineTS.

---

## 22. SKILL `pine-onboard`

### 22.1 Déclencheur

Claude peut l’invoquer automatiquement lorsqu’un `.pine` sous `scripts/**` est détecté comme non onboardé ou partiellement onboardé.

### 22.2 Principe

Onboarding = compréhension et contextualisation.

Onboarding ≠ refactoring.

### 22.3 Étapes

1. Identifier le product root.
2. Identifier le ou les `.pine`.
3. Si plusieurs sources rendent la racine ambiguë, demander au titulaire.
4. Lire intégralement le source principal.
5. Lire les parties applicables du master via l’index.
6. Cartographier le script.
7. Identifier :
   - type Pine ;
   - déclaration principale ;
   - modules ;
   - inputs ;
   - dépendances ;
   - types/enums/UDTs ;
   - état ;
   - arrays/maps/matrices ;
   - requests ;
   - MTF ;
   - signaux ;
   - objets ;
   - tables ;
   - alertes ;
   - performance sensible ;
   - risques historical/realtime/repaint.
8. Déterminer le profil de licence et ses axes (§45) si le header réel du code ou une décision fiable le permet ; noter les mentions légales existantes sans les retirer.
9. Si `script_kind = library`, dériver FREE à source public selon §45.4 et signaler toute valeur existante incompatible.
10. Si le profil, l’accès ou le mode de publication reste ambigu pour un indicator ou une strategy, demander au titulaire ; ne jamais deviner.
11. Définir ce qui est observé, confirmé et à confirmer.
12. Créer `SCRIPT.json`.
13. Créer `PRODUCT.md`.
14. Créer `ARCHITECTURE.md`.
15. Créer le `CLAUDE.md` local.
16. Créer `validation/current.json` à l’état non validé.
17. Créer `DECISIONS.md` seulement si au moins une vraie décision durable existe.
18. Créer `research/` seulement si une recherche réelle a été effectuée et mérite d’être conservée.
19. Exécuter les checks structurels.
20. Revoir les nouveaux fichiers pour supprimer le contenu générique.
21. Marquer l’onboarding complet uniquement si le contexte minimal est cohérent.

### 22.4 Interdictions

Pendant l’onboarding seul :

- ne pas modifier le `.pine` pour « corriger » ce qui est découvert ;
- ne pas inventer une intention produit ;
- ne pas inventer un modèle de distribution ;
- ne pas enregistrer une inférence comme décision ;
- ne pas créer de dossier release/docs sans besoin ;
- ne pas déclarer le script validé.

### 22.5 Résultat

Le produit obtient `product_structure_status = REGISTERED` seulement après validation structurelle de son contexte.

---

## 23. SKILL `pine-new`

### 23.1 Déclencheur

Utiliser lorsqu’il n’existe pas encore de source Pine et que le titulaire demande la création d’un nouveau produit.

### 23.2 Workflow obligatoire

1. Comprendre l’objectif fonctionnel.
2. Définir l’audience.
3. Déterminer `script_kind` parmi `indicator`, `strategy` et `library`.
4. Déterminer le profil de licence et ses axes selon §45 (FREE, FREE à source fermé, PRIVATE, COMMERCIAL). Pour `library`, dériver automatiquement FREE à source public et ne jamais proposer ni accepter un accès payant ou un source fermé tant que la règle TradingView actuelle impose la publication open-source des libraries.
5. Vérifier que l’objectif est suffisamment complet, abouti et différencié pour le produit visé — l’ambition dépend du produit, pas du profil (master §5).
6. Vérifier la documentation Pine V6 actuelle pertinente.
7. Rechercher les meilleurs scripts publics open-source du domaine.
8. Donner priorité aux Editors’ Picks pertinents.
9. Analyser les meilleures références accessibles.
10. Identifier leurs forces, limites, compromis et faiblesses.
11. Définir comment une solution le titulaire originale peut les surpasser.
12. Définir le produit avant le code.
13. Définir les décisions utilisateur réellement nécessaires.
14. Concevoir l’architecture.
15. Concevoir les settings.
16. Concevoir les états et flux de données.
17. Concevoir MTF/realtime/repaint si applicable.
18. Concevoir visualisation et alertes seulement si utiles.
19. Définir les risques.
20. Obtenir confirmation du titulaire pour les décisions produit non délégables.
21. Créer le dossier stable `scripts/<slug>/`.
22. Créer le contexte produit spécifique.
23. Créer le premier research run.
24. Déterminer la version produit initiale selon une décision le titulaire ou une politique explicitement ratifiée.
25. Ne jamais inventer une convention universelle de version initiale si elle n’existe pas.
26. Créer le `.pine` avec son header approprié.
27. Développer section par section.
28. Revoir.
29. Exécuter les checks locaux déterministes.
30. Exécuter `pine-local-test` selon applicabilité, capabilities effectivement utilisées, calibration courante et proportionnalité.
31. Qualifier tout résultat comportemental avant d’en déduire une correction.
32. Valider réellement dans TradingView.
33. Synchroniser le contexte final.

### 23.3 Slug

Le dossier produit utilise un slug :

- stable ;
- ASCII ;
- en kebab-case ;
- descriptif ;
- non dépendant de la version produit.

Ne pas renommer automatiquement un slug existant sans raison structurelle.

---

## 24. SKILL `pine-develop`

Orchestrateur principal des modifications.

### 24.1 Entrée

Une demande le titulaire portant sur un script onboardé.

### 24.2 Séquence

1. Lire le contexte local requis.
2. Comprendre précisément la demande.
3. Classer la tâche selon le standard maître ; le niveau de vérification (master §9.1) est le travail courant (cette skill) sauf audit approfondi demandé par le titulaire (`pine-audit`, périmètre annoncé) ou préparation de publication (`pine-release`).
4. Lire la cartographie du produit (`ARCHITECTURE.md`) puis les blocs concernés et leurs dépendances pertinentes, étendues selon la classe de la tâche ; lecture intégrale seulement dans un audit explicitement demandé (amendement du 2026-11-06 : aucune lecture intégrale, aucun agent, aucune cascade de revues déclenchés automatiquement par une modification, quelle que soit sa classe — un changement structurel compris).
5. Utiliser `pws-pine-cartographer` seulement dans un audit demandé ou un onboarding, lorsque la taille/complexité justifie l’isolation du volume.
6. Établir l’inventaire d’impact.
7. Vérifier la documentation Pine actuelle pertinente.
8. Effectuer la vérification de pertinence du benchmark.
9. Exécuter `pine-research` si nécessaire.
10. Définir la modification minimale cohérente.
11. Planifier.
12. Implémenter.
13. Relire selon la couverture du master §9.2.
14. Synchroniser les artefacts dépendants.
15. Revue indépendante (`pine-review`) seulement dans un audit approfondi demandé, en préparation de publication ou à la demande du titulaire ; jamais déclenchée par la classe de la tâche (amendement du 2026-11-13).
16. Corriger les constats retenus.
17. Exécuter les checks locaux déterministes.
18. Exécuter `pine-local-test` selon applicabilité, capabilities effectivement utilisées, calibration courante, inventaire d’impact et profondeur proportionnée à la modification.
19. Qualifier les résultats PineTS. Si une correction du source est réellement justifiée par l’objectif, le standard, la documentation Pine ou le contrat comportemental attendu, corriger puis réexécuter les étapes locales applicables.
20. Préparer/exécuter `tv-validate` selon applicabilité : compilation minimale intermédiaire lorsque l’inventaire d’impact le justifie (§30.5), campagne fonctionnelle sur le source stabilisé.
21. Revalider après toute correction qui change le source.
22. Mettre à jour uniquement les fichiers contextuels devenus réellement obsolètes.

Correspondance avec le master §38 : spec 1 (contexte local) → propre au workspace ; 2 → §38.1 ; 3 → §38.2 ; 4 → §38.4 ; 5 → §38.5 ; 6 → §38.6 ; 7 → §38.7 ; 8 → §38.8 ; 9 → §38.9 et §38.10 ; 10 → §38.11 à §38.13 ; 11 (planifier) → propre au workspace ; 12 → §38.14 ; 13 → §38.15 ; 14 → §38.18 ; 15 → §38.16 et §38.17 ; 16 (corriger après la revue) → propre au workspace ; 17 (checks déterministes), 18 et 19 (PineTS) → propres au workspace ; 20 → §38.19 et §38.20 ; 21 → §38.21 et §38.22 ; 22 → spec §53. Le master §38.23 (livrables) relève de `pine-release`. Le master §38.3 (modèle de distribution) est lu via `SCRIPT.json` à l’étape 1.

### 24.3 Pas de scope creep

Les améliorations non demandées sont proposées au titulaire avant implémentation lorsqu’elles constituent une décision produit.


### 24.4 Skill `pine-local-test` — contrat

Cette sous-section constitue le contrat normatif de la skill :

```text
.claude/skills/pine-local-test/SKILL.md
```

#### 24.4.1 Mission

`pine-local-test` fournit une exécution comportementale locale du source Pine exact au moyen de PineTS.

Sa mission est de produire des observations reproductibles et, lorsqu’un contrat local le permet, des conclusions comportementales localement gating avant `tv-validate`.

Elle ne constitue jamais :

- une validation TradingView ;
- une autorité sur la syntaxe ou la sémantique officielle Pine Script ;
- une preuve universelle de non-repaint ;
- une preuve générale de parité avec le Strategy Tester ou avec TradingView ;
- une preuve de performance TradingView ;
- une instruction automatique de modification du code.

Une conclusion PineTS peut être localement bloquante uniquement lorsqu’elle est précisément bornée au source, au dataset, à la configuration, à l’environnement et aux `capabilities_used` du run, et lorsque toutes les capabilities matériellement nécessaires à cette conclusion sont effectivement gating.

Cette autorité locale porte sur le contrat comportemental local testé. Elle ne crée aucun statut TradingView, ne remplace aucune observation TradingView requise et ne permet jamais d’extrapoler une compatibilité générale de PineTS avec TradingView.

#### 24.4.2 Backend

L’intégration durable utilise un thin adapter Node local autour d’une dépendance directe à PineTS.

La version PineTS doit être pinée exactement.

Interdire les ranges flottants tels que :

```text
^X.Y.Z
~X.Y.Z
latest
*
```

Le lockfile doit être versionné.

Aucun auto-upgrade de PineTS n’est autorisé.

Une mise à niveau PineTS constitue une opération explicite de maintenance. Elle invalide la fraîcheur des calibrations liées à l’ancienne identité d’environnement et exige une recalibration avant qu’une capability concernée puisse de nouveau produire une conclusion effectivement gating.

`pinets-cli` peut être utilisé ponctuellement pour un proof of concept ou un diagnostic, mais n’est pas le backend durable canonique du workspace sauf décision ultérieure explicite du titulaire.

#### 24.4.3 Executor fingerprint

Chaque environnement d’exécution comportementale possède un `executor_fingerprint` représentant l’ensemble des artefacts locaux susceptibles d’influencer le résultat normalisé.

Le fingerprint doit couvrir au minimum, lorsqu’ils existent ou influencent le comportement :

- `runner.mjs` ;
- `normalize.mjs` ;
- `package.json` ;
- `package-lock.json` ;
- la configuration comportementale du runner qui ne relève pas de la configuration propre au run ;
- tout module auxiliaire local chargé par l’exécuteur et susceptible de modifier l’exécution ou la normalisation ;
- version Node.js exacte ;
- plateforme et architecture ;
- options Node.js pertinentes ;
- variables d'environnement pertinentes et non secrètes ;
- timezone et locale, soit contrôlées explicitement, soit enregistrées lorsqu'elles peuvent influencer l'exécution ou la normalisation.

Le calcul exact doit être déterministe et reproductible. Une implémentation acceptable consiste à produire un manifeste canonique `chemin relatif → SHA-256` des éléments concernés, à y intégrer les faits d'environnement et paramètres d’exécuteur pertinents sous forme canonique, puis à calculer le SHA-256 de ce manifeste.

Ne pas fingerprint-er aveuglément tout l'environnement. Inclure uniquement les faits susceptibles d'influencer l'exécution ou la normalisation, sans jamais enregistrer une valeur secrète. Ces faits restent absorbés par `executor_fingerprint` : ils ne créent pas une quatrième dimension concurrente au triplet ratifié.

`executor_fingerprint` ne remplace pas `source_sha256`, `dataset_sha256` ni la `configuration` propre au run. Ces identités restent séparées.

#### 24.4.4 Capability gate, granularité et fraîcheur de calibration

Le workspace ne suppose jamais que toute fonctionnalité annoncée par PineTS est suffisamment compatible pour devenir gating.

Le statut est attribué à des capabilities suffisamment fines pour représenter le comportement réellement testé. Ne pas classer une famille entière telle que `MTF`, `request.*`, `strategy.*`, historical/realtime, inputs ou objets comme `GATING`, `EXPERIMENTAL` ou `UNSUPPORTED` lorsque ses sous-capabilities peuvent avoir des profils de compatibilité différents.

Aucune famille de fonctionnalités Pine n’est durablement condamnée à rester `EXPERIMENTAL` ou `UNSUPPORTED`, ni promue `GATING`, par sa seule catégorie. Les statuts doivent pouvoir évoluer capability par capability lorsque la calibration et les preuves réelles le justifient.

Une capability nouvellement rencontrée sans qualification suffisante peut être enregistrée provisoirement comme `EXPERIMENTAL` avec `calibration_status = MISSING`. Ce statut provisoire signifie uniquement « aucune autorité gating établie » ; il ne constitue pas une preuve que la capability est incorrecte. `UNSUPPORTED` exige une raison démontrable, par exemple une absence fonctionnelle, une divergence reproductible ou une incapacité actuelle à exécuter le contrat avec une fidélité suffisante.

Deux dimensions indépendantes sont conservées pour chaque capability :

```text
capability_status
calibration_status
```

`capability_status` accepte uniquement :

```text
GATING
EXPERIMENTAL
UNSUPPORTED
```

`calibration_status` accepte au minimum :

```text
CURRENT
STALE
MISSING
```

`capability_status = GATING` signifie que cette capability est autorisée à produire des conclusions gating lorsqu’une calibration indépendante courante existe pour l’environnement exact.

Un changement d’environnement ne transforme pas automatiquement `GATING` en `EXPERIMENTAL` ou `UNSUPPORTED`.

La capacité à bloquer effectivement est dérivée :

```text
effective_gating =
    capability_status == GATING
    AND calibration_status == CURRENT
```

Pour `EXPERIMENTAL` ou `UNSUPPORTED`, `effective_gating` est toujours faux.

L’identité de l’environnement calibré est déterminée par le triplet exact :

```text
pinets_version
+
executor_fingerprint
+
normalization_schema
```

Toute modification de l’un de ces trois éléments rend `calibration_status = STALE` pour les calibrations qui reposaient sur l’identité précédente.

L'identité d'environnement n'est pas la seule cause d'obsolescence. La fraîcheur de chaque capability dépend également de l'identité et de l'intégrité de ses cas, inputs, résultats attendus, références indépendantes et preuves éventuelles selon §24.4.5.

Lors d’une recalibration, `capability_status` peut être révisé si les preuves de compatibilité le justifient ; il n’est jamais réécrit automatiquement uniquement parce que l’environnement a changé.

Une capability `GATING` ne peut redevenir effectivement gating qu’après recalibration réussie contre l’identité d’environnement courante.

#### 24.4.5 Calibration

Le dossier :

```text
tools/pine_exec/calibration/
```

doit contenir un état de calibration durable permettant d’identifier au minimum :

- version PineTS exacte ;
- `executor_fingerprint` ;
- identité du schéma de normalisation ;
- date de calibration ;
- capabilities examinées ;
- `capability_status` de chaque capability ;
- `calibration_status` de chaque capability ;
- cas utilisés ;
- hashes ou identités canoniques des cas et inputs ;
- hashes ou identités canoniques des résultats attendus ;
- provenance de la référence indépendante ;
- hash et référence durable de la référence indépendante ;
- référence et hash de toute preuve TradingView utilisée pour soutenir le claim ;
- divergences connues ;
- limitations connues.

Une capability `GATING` exige une calibration indépendante avec :

- la version PineTS exacte installée ;
- l’`executor_fingerprint` exact ;
- le schéma de normalisation exact ;
- des cas représentatifs ;
- une référence attendue indépendante de PineTS.

Une référence de calibration peut provenir notamment :

- d’une observation TradingView correctement établie ;
- d’un calcul indépendant dont le résultat est déterminable sans utiliser PineTS comme oracle.

La référence doit correspondre au type de claim que la capability est autorisée à produire. Une capability destinée uniquement à établir un contrat mathématique ou comportemental local peut être calibrée contre une référence indépendante appropriée. Une capability utilisée pour soutenir un claim de correspondance avec un comportement propre à TradingView doit être calibrée contre une observation TradingView suffisamment probante pour ce claim précis.

Une sortie PineTS antérieure ne suffit jamais, à elle seule, à calibrer PineTS.

Une calibration `STALE` ou `MISSING` ne change pas le `capability_status`, mais interdit toute utilisation effectivement gating de cette capability.

Une calibration devient `STALE`, capability par capability, lorsque notamment :

- un cas ou un input de calibration change ;
- un résultat attendu change ;
- une référence indépendante ou une preuve requise disparaît, change ou ne passe plus sa vérification d'intégrité ;
- une nouvelle divergence reproductible contredit le contrat antérieurement calibré ;
- une évolution pertinente de la documentation officielle rend le contrat de calibration invalide.

L'âge seul d'une calibration n'est pas une preuve de staleness. Ne pas appliquer de TTL arbitraire.

La calibration ne doit pas devenir un second standard Pine Script.

Elle décrit uniquement ce que cette version précise de PineTS, avec cet exécuteur et ce schéma de normalisation, est autorisée à prouver localement.

#### 24.4.6 Identité et capabilities d’un run

Tout résultat comportemental utilisé pour une comparaison ou une conclusion doit être lié au minimum à :

```text
source_sha256
dataset_sha256
dataset_descriptor
pinets_version
executor_fingerprint
normalization_schema
configuration
capabilities_used
run_id
timestamp
```

`dataset_descriptor` décrit la provenance et les sémantiques nécessaires à l’interprétation du dataset sans remplacer son hash. Il distingue au minimum un dataset synthétique d’un snapshot importé et enregistre, selon applicabilité :

- type de dataset ;
- générateur et paramètres lorsque synthétique ;
- source ou provenance lorsque importé ;
- symbole, timeframe et plage temporelle ;
- timezone, session ou autres sémantiques temporelles pertinentes ;
- date ou référence d’acquisition/export lorsque utile ;
- information de licence ou de droit d’usage nécessaire lorsque la source est externe.

`timestamp` utilise RFC 3339 en UTC. `run_id` est collision-resistant et ne dépend pas d'une date locale seule.

`capabilities_used` doit enregistrer les capabilities PineTS effectivement sollicitées par le comportement ou la conclusion concernée, ainsi que leur état au moment du run.

Une représentation valide est par exemple :

```json
{
  "capabilities_used": {
    "series-history": {
      "capability_status": "GATING",
      "calibration_status": "CURRENT"
    },
    "ta-ema": {
      "capability_status": "GATING",
      "calibration_status": "CURRENT"
    },
    "request-security-udf": {
      "capability_status": "EXPERIMENTAL",
      "calibration_status": "CURRENT"
    }
  }
}
```

`effective_gating` est dérivé des deux statuts et ne doit pas être persisté comme une troisième source de vérité lorsqu’il peut être recalculé sans ambiguïté.

Un run peut s’exécuter avec succès tout en utilisant une ou plusieurs capabilities non effectivement gating.

Dans ce cas, `PINETS_EXECUTION_PASS` reste valide, mais aucune conclusion comportementale qui dépend matériellement d’une capability non effectivement gating ne peut être utilisée comme gate.

Lorsqu’une conclusion peut être isolée à un sous-ensemble de capabilities toutes effectivement gating, seule cette conclusion précisément bornée peut être gating.

Si les `capabilities_used` ne peuvent pas être déterminées avec une confiance suffisante pour la conclusion concernée, cette conclusion est `PINETS_INCONCLUSIVE` ou autrement non gating ; l’incertitude de détection ne doit jamais être transformée en preuve.

Lorsque le dataset est généré synthétiquement, sa définition doit être déterministe et permettre de reproduire exactement le même OHLCV.

Un snapshot OHLCV importé depuis une source indépendante peut également être utilisé lorsqu’il est conservé ou reconstructible de manière suffisamment fiable, que son `dataset_sha256` est stable, que sa provenance est enregistrée et que ses conditions d’usage permettent l’utilisation prévue.

Le bootstrap ne doit pas intégrer par défaut un fournisseur de données réseau ni créer une nouvelle plateforme de market data. Il doit seulement permettre au thin adapter de consommer des datasets locaux contrôlés selon un contrat documenté.

La couche PineTS ne doit pas automatiser l’extraction de données, contenus ou états TradingView dans le seul but d’alimenter le runtime local, sauf décision ultérieure explicitement ratifiée après analyse des conditions actuelles applicables à cet usage précis.

#### 24.4.7 Statuts : exécution et observations comportementales

Les statuts d’exécution et les observations comportementales sont deux axes distincts.

Le statut d’exécution décrit uniquement la capacité du runtime PineTS à exécuter le source dans l’environnement concerné :

```text
PINETS_EXECUTION_PASS
PINETS_EXECUTION_FAIL
```

Les observations comportementales décrivent ce qui a été observé après ou pendant une exécution exploitable :

```text
PINETS_REGRESSION_UNCHANGED
PINETS_REGRESSION_CHANGED

PINETS_STABILITY_NO_ANOMALY
PINETS_STABILITY_ANOMALY
```

Les statuts de qualification de preuve comprennent :

```text
PINETS_EXPERIMENTAL
PINETS_UNSUPPORTED
PINETS_INCONCLUSIVE
```

Les axes ne doivent jamais être fusionnés.

La combinaison suivante est parfaitement valide :

```text
PINETS_EXECUTION_PASS
+
PINETS_REGRESSION_CHANGED
```

Elle signifie que le runtime a exécuté le source et qu’un changement comportemental a été observé. Elle ne signifie pas un échec d’exécution.

`PINETS_EXECUTION_PASS` signifie uniquement que le source s’est exécuté avec succès dans l’environnement PineTS concerné.

Il ne signifie jamais `TV_VALIDATED`.

`PINETS_EXECUTION_FAIL` ne peut devenir un échec bloquant du workflow local que si :

1. les capabilities matériellement nécessaires à l’interprétation de cet échec sont effectivement gating ;
2. leur calibration est `CURRENT` ;
3. l’échec est attribuable au comportement du source ou à un contrat de test explicite ;
4. aucune divergence PineTS connue ne rend l’interprétation incertaine.

Sinon, utiliser un statut non gating approprié.

`PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` et `PINETS_INCONCLUSIVE` ne sont jamais assimilés à un échec du script.

Ils signifient que la couche locale ne peut pas fournir une preuve suffisante sur ce point.

Le workflow peut alors poursuivre vers TradingView.

#### 24.4.8 Frontière de correction

Claude Code ne modifie jamais le source Pine uniquement pour faire accepter le code par PineTS.

Avant toute correction déclenchée par un résultat PineTS, poser la question :

> Le code serait-il incorrect ou contraire à l’objectif, au standard, à la documentation Pine actuelle ou au contrat comportemental attendu si PineTS n’existait pas ?

Si la réponse est non ou indéterminable, ne pas modifier le Pine uniquement pour satisfaire PineTS.

Qualifier le résultat comme limitation, divergence, expérimental, unsupported ou inconclusif selon le cas.

#### 24.4.9 Régressions

Une différence comportementale n’est pas automatiquement un bug.

`PINETS_REGRESSION_CHANGED` signifie uniquement qu’une différence a été observée entre deux exécutions comparables.

Toute différence doit être confrontée :

- à l’objectif demandé par le titulaire ;
- à l’inventaire d’impact ;
- aux comportements annoncés comme devant rester inchangés ;
- aux comportements explicitement destinés à changer.

Classer la différence comme :

```text
EXPECTED
UNEXPECTED
UNRESOLVED
```

`EXPECTED` n’est pas un échec.

`UNRESOLVED` ne doit pas produire une correction spéculative.

`UNEXPECTED` peut bloquer le cycle local uniquement lorsque la conclusion concernée dépend exclusivement de capabilities effectivement gating et repose sur un contrat de régression valide.

#### 24.4.10 Accepted behavioral baseline

Une baseline durable porte le statut :

```text
ACCEPTED_BEHAVIORAL_BASELINE
```

Une première exécution PineTS n’est jamais automatiquement une baseline acceptée.

Toute `ACCEPTED_BEHAVIORAL_BASELINE` doit être liée au minimum à :

```text
source_sha256
dataset_sha256
dataset_descriptor
normalized_payload_sha256
pinets_version
executor_fingerprint
normalization_schema
configuration
capabilities_used
acceptance_basis
accepted_at
acceptance_evidence_ref
acceptance_rationale
```

La baseline doit idéalement provenir d’un source dont le même SHA a déjà passé la validation TradingView pertinente.

À défaut, elle ne peut être promue comme `ACCEPTED_BEHAVIORAL_BASELINE` que par une décision explicite du titulaire avec une justification enregistrée.

`acceptance_basis` doit permettre de distinguer notamment :

```text
TRADINGVIEW_VALIDATED_SOURCE
RICK_EXPLICIT_ACCEPTANCE
```

`normalized_payload_sha256` est requis lorsque le payload normalisé est séparé de son descripteur. Pour `TRADINGVIEW_VALIDATED_SOURCE`, `acceptance_evidence_ref` doit référencer la preuve durable du même SHA lorsqu'elle fonde l'acceptation. Pour `RICK_EXPLICIT_ACCEPTANCE`, `acceptance_rationale` doit expliquer la décision ; les champs non applicables peuvent être `null`, mais leur présence et leur sémantique restent normatives.

Une baseline acceptée signifie :

> ce comportement est accepté comme référence de non-régression pour ce contexte précis.

Elle ne signifie pas :

> PineTS a prouvé que cette sortie est universellement correcte.

Une baseline reste un artefact historique valide lorsque l’environnement évolue, mais elle ne peut plus soutenir directement une comparaison gating si son `pinets_version`, son `executor_fingerprint`, son `normalization_schema`, son dataset ou sa configuration ne correspondent pas au contexte de comparaison.

Dans ce cas, le source de référence doit être réexécuté dans l’environnement courant, ou la baseline doit être régénérée puis acceptée selon le contrat ci-dessus.

Aucune baseline n’est migrée automatiquement.

#### 24.4.11 Persistance

Les artefacts durables spécifiques à un produit résident exclusivement sous :

```text
scripts/<slug>/tests/behavioral/
```

Ils ne doivent jamais être écrits sous :

```text
scripts/<slug>/validation/
```

Les sorties temporaires d’exécution appartiennent à un espace runtime gitignored.

Ne pas conserver automatiquement chaque run.

Ne promouvoir une sortie en artefact durable que si elle possède une utilité réelle pour la régression, la reproduction d’un bug, la calibration ou la compréhension du produit.

#### 24.4.12 Proportionnalité et matrices explicites

`pine-local-test` n’impose pas une matrice lourde pour chaque correction.

La profondeur dépend :

- de la nature de la modification ;
- des modules affectés ;
- des risques identifiés ;
- des baselines existantes ;
- des capabilities disponibles ;
- du coût raisonnable du test.

Une petite correction peut justifier un simple smoke run.

Une refactorisation censée être sémantiquement neutre peut justifier une comparaison de régression approfondie.

Une modification MTF, historique, realtime ou strategy peut demander des tests plus ciblés, mais uniquement dans les limites des capabilities effectivement gating ou comme observation explicitement expérimentale/non gating.

Lorsqu’un besoin réel le justifie, un workflow explicite peut exécuter une matrice bornée comprenant notamment plusieurs datasets, symboles, timeframes, configurations ou valeurs d’inputs. Un parameter sweep local est donc autorisé comme technique d’exploration, de diagnostic ou de régression lorsque le runtime et les capabilities concernées le permettent.

Chaque exécution élémentaire de la matrice conserve sa propre identité de run. La matrice elle-même doit posséder un manifeste déterministe décrivant les combinaisons exécutées, afin qu’un résultat agrégé puisse être retracé jusqu’aux runs qui le composent.

Un classement de configurations, un optimum apparent ou une meilleure métrique observée localement ne constitue jamais à lui seul une preuve de qualité de signal, de robustesse hors échantillon, de performance TradingView ou de supériorité produit. Toute décision de modifier les paramètres du produit reste une décision produit explicite ou une conséquence justifiée d’un objectif déjà ratifié.

Le bootstrap ne construit pas un optimiseur générique, une plateforme de backtesting ou un moteur de market data. Les matrices sont une capacité bornée de `pine-local-test`, déclenchée uniquement par un workflow explicite. Aucun hook du socle ne lance automatiquement une matrice de datasets, paramètres ou stability probes.

#### 24.4.13 Licence, données, conditions d’usage et distribution

PineTS reste une dépendance tierce indépendante du source Pine le titulaire.

Avant l’installation initiale et toute mise à niveau :

- vérifier la licence upstream actuelle de PineTS ;
- conserver les notices et fichiers de licence requis ;
- ne pas supposer que les conditions de licence resteront identiques dans le temps.

Enregistrer la base de licence réellement utilisée, sans la résumer artificiellement comme « dual licence » :

```text
license_basis = AGPL-3.0-only
```

ou, uniquement si le titulaire détient réellement une licence commerciale séparée applicable :

```text
license_basis = separate-commercial-license
license_evidence = <référence locale appropriée et non secrète>
```

L'existence d'une offre de licence commerciale upstream ne prouve pas qu'une telle licence est détenue. Le rapport de provenance doit enregistrer la version exacte, l'intégrité de l'artefact installé, ses métadonnées de licence et le lockfile. Ce contrat de provenance ne remplace pas une analyse juridique.

Les droits et conditions applicables doivent être évalués selon la ressource réellement utilisée :

1. licence et conditions PineTS pour le runtime et son intégration ;
2. licence, contrat ou conditions de la source de données pour tout dataset externe ;
3. conditions TradingView pour toute interaction, automatisation, extraction, contenu ou donnée provenant effectivement des services TradingView.

Ne pas étendre par réflexe une restriction propre à un service externe à toute exécution locale indépendante ; inversement, ne pas supposer qu’une exécution locale rend libre un contenu ou une donnée provenant d’un service soumis à ses propres conditions.

L’intégration ratifiée ici vise un usage local/interne du workspace. Aucun fournisseur de données externe n’est imposé ni configuré par défaut par le bootstrap.

Si le thin adapter, PineTS ou une application dérivée doit être distribué à des tiers, intégré à un produit distribué ou exposé comme service réseau, arrêter l’opération et effectuer une nouvelle analyse de licence et des conditions d’usage applicables avant de poursuivre.

Décision du titulaire du 2026-11-13, après l’analyse requise ci-dessus pour la distribution publique : le thin adapter (`tools/pine_exec/runner.mjs`, `normalize.mjs`, `datasets.mjs`, `fingerprint.mjs` et les métadonnées de son paquet) est distribué sous **AGPL-3.0-only** (texte officiel dans `tools/pine_exec/LICENSE`, identifiant SPDX et notice dans chaque fichier) ; le reste du cœur reste sous Apache-2.0 ; PineTS n’est jamais livré. Architecture constatée : l’adaptateur charge PineTS dans son propre processus Node ; le cœur Apache-2.0 ne charge jamais PineTS : son outillage Python lance les programmes de l’adaptateur comme processus séparés et échange des fichiers et du JSON, et ses tests contiennent de courts programmes JavaScript qui importent des modules de l’adaptateur (jamais PineTS directement). Cette décision fixe la licence du code de Pine Workspace ; elle ne tranche pas juridiquement la frontière entre les composants. Toute autre forme (PineTS ou un dérivé embarqué, PineTS modifié, intégration du moteur à un produit distribué, service réseau) reste soumise à l’arrêt et à une nouvelle analyse.

---

## 25. SKILL `pine-research`

### 25.1 Mission

Produire de la recherche actuelle, traçable et utile au script.

### 25.2 Sources prioritaires

Pour les faits Pine :

- documentation officielle TradingView/Pine Script ;
- release notes officielles ;
- règles officielles de publication lorsque concernées.

Pour le benchmark :

- scripts publics open-source pertinents ;
- Editors’ Picks pertinents ;
- autres références open-source de haute qualité.

### 25.3 Réutilisation

Le benchmark n’autorise pas la réutilisation de code.

Appliquer strictement la frontière benchmark/réutilisation du standard maître.

### 25.4 Persistance

Ne pas écrire un run de recherche pour une recherche insignifiante.

Lorsqu’un résultat mérite d’être réutilisé :

```text
scripts/<slug>/research/runs/<timestamp>-<topic>.md
```

Puis mettre à jour :

```text
research/CURRENT.md
```

avec une synthèse de routage.

Lorsqu’un agent chercheur est invoqué, le parent persiste son rapport en run de recherche dès réception, avec la date de consultation et la provenance. Un run écrit après coup porte la date de recherche initiale, la date de reconstitution et la provenance, sans heure inventée ; sa fraîcheur reste celle de sa date initiale tant qu’aucune revérification datée n’est faite. Une recherche non effectuée n’est jamais datée.

### 25.5 Fraîcheur

Pas de TTL universel arbitraire.

La fraîcheur dépend :

- du sujet ;
- de sa volatilité ;
- de la date ;
- du risque de changement ;
- de la phase release.

Toute règle TradingView de publication doit être revérifiée immédiatement avant une vraie release, quelle que soit l’ancienneté d’un run précédent.

---

## 26. SKILL `pine-review`

### 26.1 Mission

Implémenter les quatre axes de revue du standard maître.

Déclenchement : audit approfondi demandé (`pine-audit`), préparation de publication (`pine-release`) ou demande explicite du titulaire ; jamais enchaînée automatiquement par une création ou une modification, quelle que soit la classe de la tâche ; une seule revue par unité de travail, sans cascade de contre-revues (master §9.1, §36 ; amendement du 2026-11-13).

### 26.2 Exécution

Déléguer le regard indépendant au subagent `pws-pine-reviewer`.

Le reviewer :

- ne modifie pas le code ;
- ne possède pas de mémoire persistante ;
- reçoit la demande, le source, le contexte nécessaire et le diff utile ;
- reçoit la couverture attendue (ciblée, élargie, globale) et rend la couverture réellement lue ;
- ne reçoit pas inutilement toute la conversation du développeur.

### 26.3 Sortie

Retour structuré :

- problème ;
- impact ;
- emplacement ;
- justification ;
- règle ou objectif concerné ;
- niveau de confiance.

Le parent décide des corrections et les implémente.

---

## 27. SKILL `pine-release`

### 27.1 Mission

Préparer une release, pas publier implicitement.

### 27.2 Étapes

Selon applicabilité :

- déterminer l’impact SemVer ;
- vérifier la version dans le header source ;
- préparer changelog ;
- préparer release notes ;
- préparer tutoriel si requis ;
- préparer description initiale si nouvelle publication ;
- vérifier documentation dépendante ;
- constater l'état des licences et conditions d'utilisation (`license status` ; les informations se complètent par le parcours `pine-license`, indépendant de cette skill) : une information manquante est signalée et bloque seulement la finalisation concernée, jamais complétée par invention ;
- revalider règles TradingView actuelles ;
- exécuter les tests comportementaux PineTS applicables lorsque des capabilities effectivement gating ou des `ACCEPTED_BEHAVIORAL_BASELINE` pertinentes existent ;
- qualifier et résoudre toute régression locale `UNEXPECTED` réellement gating avant la validation TradingView finale ;
- exécuter `pws-release-reviewer` ;
- vérifier validation TradingView du hash final ;
- préparer les artefacts de publication ;
- pour toute publication `invite-only`, préparer et vérifier le contenu `Author's instructions` requis par les règles TradingView actuelles.

### 27.3 Gate

Une release ne peut pas être déclarée prête si le source final n’a pas passé la validation TradingView requise.

Un statut `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` ou `PINETS_INCONCLUSIVE` n’empêche pas à lui seul une release de poursuivre vers TradingView.

La gate finale de release reste la validation TradingView du source final.

### 27.4 Publication

La skill ne finalise pas automatiquement une publication publique.

---

## 28. SKILL `tv-mode`

### 28.1 Invocation

Cette skill est réservée au titulaire.

Utiliser le frontmatter actuel permettant d’empêcher l’invocation automatique, par exemple :

```yaml
disable-model-invocation: true
```

si ce champ existe toujours.

### 28.2 Commandes

Supporter :

```text
/tv-mode manual
/tv-mode chrome-experimental
```

### 28.3 Effet

La skill appelle le contrôleur déterministe partagé :

```text
python -m tools.pws_workspace tv-mode <mode>
```

ou sa forme finale équivalente validée par le bootstrap. Ce contrôleur est l'unique propriétaire de la mutation et modifie uniquement :

```text
tv_validation_mode
```

dans `pws.config.json` (§19A). Les réglages de Claude Code ne sont jamais touchés.

Préserver toutes les autres clés existantes.

Appliquer le contrat atomique de §19A (sérialisation garantie entre écrivains du workspace par le verrou de la configuration ; refus des modifications concurrentes détectées).

### 28.4 Interdiction

Claude ne change jamais le mode persistant de sa propre initiative.

`disable-model-invocation: true` interdit à Claude d'appeler la skill `/tv-mode`. Lorsque le titulaire choisit explicitement `Changer le mode TV` dans `/pws`, la façade ne tente donc pas `Skill(tv-mode)` : elle transmet ce choix utilisateur au même contrôleur déterministe partagé. Cette route explicite ne donne aucune autorisation de changement spontané hors de ce choix.

---

## 29. SKILL `tv-validate`

### 29.1 Source du mode

Lire le mode via le contrôleur (`python3 -m tools.pws_workspace tv-mode`, configuration `pws.config.json` ; source `config`, `legacy` ou `default`) — jamais la variable de processus :

```text
tv_validation_mode
```

### 29.2 Matrice

La matrice de validation est dérivée :

- du standard maître ;
- du type de script ;
- du contexte produit ;
- du changement réel.

Elle n’est jamais un checklist fixe imposant des tests N/A.

### 29.3 Identité du source

Avant tout run :

1. calculer SHA-256 du `.pine` ;
2. capturer le commit Git courant s’il existe ;
3. capturer l’état dirty/clean ;
4. générer un `run_id`.

La preuve centrale est le hash du source.

### 29.4 Après modification

Toute modification du `.pine` après un run invalide la capacité de ce run à prouver le nouveau source.

Le dernier run reste historique.

L’état effectif devient `STALE`.

### 29.5 Frontière PineTS

`tv-validate` ne consomme jamais un résultat PineTS comme substitut à une observation TradingView.

Une conclusion PineTS effectivement gating peut bloquer le cycle local avant `tv-validate` lorsqu’elle démontre la violation d’un contrat comportemental local valide. Ce blocage local doit être résolu, expliqué ou requalifié avant de poursuivre comme si le test était passé ; il ne crée toutefois aucun statut TradingView.

Les résultats de `pine-local-test` peuvent :

- aider à préparer la matrice de validation ;
- cibler un scénario à reproduire ;
- expliquer une anomalie ;
- identifier un risque à vérifier.

Ils ne peuvent pas :

- satisfaire une étape TradingView ;
- créer une preuve TradingView ;
- modifier directement le statut TradingView ;
- transformer une validation effective `stale` ou persistée `unverified` / `in-progress` en `passed`.

Lorsqu’une validation TradingView est requise par le workflow, elle reste obligatoire sur le source exact concerné, indépendamment du résultat PineTS.

---

## 30. MODE TRADINGVIEW `manual`

### 30.1 Statut

Mode par défaut.

### 30.2 Fonctionnement

Claude :

1. termine les contrôles locaux ;
2. construit une matrice de tests spécifique ;
3. donne au titulaire des étapes précises ;
4. attend les observations réelles ;
5. enregistre les résultats ;
6. ne persiste `passed` que lorsque tous les contrôles obligatoires applicables ont réellement réussi.

### 30.3 Tests possibles selon applicabilité

- compilation Pine Editor ;
- runtime ;
- historical ;
- realtime ;
- Replay ;
- MTF ;
- changement symbole ;
- changement timeframe ;
- settings extrêmes ;
- dark theme ;
- light theme ;
- labels/tables/boxes/lines/fills ;
- alertes ;
- stratégie/report si script de stratégie ;
- performance/Profiler lorsque pertinent.

Ne pas exécuter mécaniquement un test sans objet.

### 30.4 Evidence

Conserver uniquement les preuves utiles.

Un compte rendu précis du titulaire peut constituer une observation réelle.

Une capture est utile lorsqu’elle prouve un état visuel ou une erreur, mais ne doit pas devenir une obligation artificielle pour chaque test.

Un compte rendu du titulaire peut couvrir un groupe de contrôles lorsque la liste exacte des contrôles du groupe lui a été présentée avant sa confirmation. Le run conserve cette liste, le texte présenté et la confirmation reçue. La confirmation ne s’étend à aucun contrôle non listé et n’autorise aucune mesure ou valeur non rapportée.

### 30.5 Compilation minimale et campagne fonctionnelle

La compilation minimale est l’observation, dans le Pine Editor, du résultat de compilation du source exact identifié par son SHA-256 : erreurs et avertissements, rapportés séparément. Elle ne porte sur aucun comportement. La campagne fonctionnelle est l’exécution des contrôles comportementaux applicables de la matrice ; elle peut être regroupée sur le source stabilisé d’une série de modifications.

Une compilation minimale intermédiaire est demandée lorsque l’inventaire d’impact identifie une transformation transversale présentant un risque de typage, de profondeur d’historique ou de taille compilée. Elle est consignée avec le risque qui la justifie. Elle n’est demandée ni après chaque micro-edit, ni après une correction locale sans ce risque. Aucune marge de taille compilée n’est déduite sans mesure rapportée.

Une compilation minimale réussie ne vaut pas validation : le run qui la consigne liste les contrôles comportementaux applicables comme `not-run` et ne peut pas être `passed`. L’absence d’erreur ne prouve pas l’absence d’avertissement.

Le run consigne séparément les erreurs et les avertissements. Pour chacun, il indique explicitement si une observation a été rapportée ; une absence d’observation est consignée comme telle, jamais déduite. Les résultats des contrôles comportementaux ne sont pas inventés.

L’enregistrement et la promotion sont distincts. Un rapport valide est toujours conservé comme run immuable. Sans run courant reconnu, sa promotion initiale suit le protocole normal. Sur le même SHA que le run courant reconnu, une compilation minimale qui n’est pas `failed` ne remplace pas ce run ; une compilation minimale `failed` peut le remplacer, avec le signalement explicite d’une contradiction si ce run était `passed`. Sur un autre SHA, la promotion suit le protocole normal et la fraîcheur reste calculée contre le source déclaré. Aucune de ces règles ne contourne les protections de §51.4. Un échec non promu pour conflit reste conservé et clairement signalé.

Le regroupement de la campagne fonctionnelle et la fréquence des sollicitations relèvent de l’organisation décidée par le titulaire pour chaque produit et sont consignés dans ses décisions. Une telle décision ne s’étend pas aux autres produits.

---

## 31. MODE TRADINGVIEW `chrome-experimental`

### 31.1 Statut

Expérimental et optionnel.

### 31.2 Préflight

Avant le run, vérifier les capacités réellement disponibles :

- version Claude Code ;
- Chrome/Chromium compatible ;
- extension compatible ;
- authentification Claude compatible ;
- outils navigateur présents ;
- connexion TradingView déjà établie ou possibilité pour le titulaire de la compléter ;
- restrictions de plateforme actuelles.

À la date de cette spécification, la documentation Claude Code indique notamment que l’intégration Chrome partage la session authentifiée du navigateur, s’arrête sur login/CAPTCHA et n’est pas supportée sous WSL.

Toujours revérifier la documentation actuelle.

### 31.3 Activation

Ne pas activer Chrome globalement si ce n’est pas nécessaire.

L’intégration navigateur augmente le contexte lorsque ses outils sont chargés.

Utiliser `--chrome` seulement pour les sessions/runs qui en ont besoin, sauf décision contraire du titulaire.

### 31.4 Exécution

Le mode expérimental tente d’exécuter la même matrice que le mode manuel.

Avant toute mutation du Pine Editor, appliquer un pre-write gate. Il doit établir avec une confiance suffisante :

1. la fenêtre Chrome attendue ;
2. l'onglet TradingView cible et son domaine ;
3. l'identité de l'éditeur ouvert ;
4. l'identité du script ou buffer actif ;
5. la présence éventuelle de modifications étrangères non sauvegardées ;
6. la correspondance entre ce buffer et le produit/source local attendu.

Si une identité reste ambiguë :

```text
NO WRITE
→ fallback manual / action humaine
```

Après toute écriture, réobserver le buffer et le contexte cible. Un clic ou une commande réussie ne prouve ni que le bon script a été modifié ni que le contenu attendu est présent.

Il peut, lorsque techniquement fiable :

- ouvrir TradingView ;
- ouvrir Pine Editor ;
- saisir/mettre à jour le source ;
- sauvegarder ;
- compiler ;
- ajouter au chart ;
- changer symbole/timeframe ;
- manipuler des settings ;
- observer runtime ;
- inspecter console/DOM si utile ;
- prendre des screenshots utiles.

### 31.5 Frontière

Ne pas confondre capacité à cliquer et capacité à prouver.

Si Claude ne peut pas établir de manière suffisamment fiable qu’une étape a réussi, cette étape n’est pas `passed`.

### 31.6 Fallback

Déclencher le fallback manuel si notamment :

- login requis ;
- CAPTCHA ;
- extension non connectée ;
- Pine Editor inaccessible ;
- UI différente ;
- résultat ambigu ;
- action navigateur échouée ;
- contrôle visuel incertain ;
- élément nécessaire impossible à automatiser ;
- étape demandant jugement humain ;
- risque d’action de publication.

Le run enregistre :

```text
requested_mode = chrome-experimental
effective_mode = manual
fallback_reason = ...
```

Le mode persistant reste inchangé.

### 31.7 Screenshots

Sauvegarder une capture sur disque uniquement lorsqu’elle constitue une preuve utile.

Les screenshots de validation appartiennent au dossier `validation/evidence/` du run concerné.

### 31.8 Publication exclue

`chrome-experimental` s’arrête avant toute publication publique ou modification commerciale.

### 31.9 Apprentissage opérationnel contrôlé

`chrome-experimental` doit pouvoir capitaliser progressivement les connaissances opérationnelles réellement utiles à la validation TradingView, sans introduire de modèle d’apprentissage autonome, de mémoire opaque, de nouvelle autorité ni de nouvelle couche d’architecture.

L’objectif est de réduire les explorations répétitives, d’améliorer la fiabilité des interactions et de mieux reconnaître les états ambigus ou obsolètes, tout en conservant la même exigence de preuve pour chaque run réel.

#### 31.9.1 Connaissances admissibles

Peuvent notamment devenir des apprentissages opérationnels :

- workflows TradingView réellement observés et réutilisables ;
- landmarks UI sémantiques fiables ;
- moyens robustes d’établir que Pine Editor est réellement ouvert et utilisable ;
- états visuels attendus après une action connue ;
- signes fiables de succès ou d’échec ;
- dialogs, transitions et états intermédiaires connus ;
- ambiguïtés déjà rencontrées ;
- causes reproductibles de fallback manuel ;
- différences observées après une évolution de l’UI ;
- méthodes de preuve qui améliorent la qualité d’un run sans abaisser son seuil de validation.

Ne pas confondre apprentissage opérationnel et apprentissage statistique ou machine learning.

#### 31.9.2 Préférence pour les repères robustes

Lorsqu’un workflow peut être décrit de plusieurs manières, préférer par ordre général :

```text
état sémantique observable
> rôle / label accessible
> relation structurelle stable dans l’UI
> relation DOM stable
> sélecteur fragile
> coordonnée pixel absolue
```

Les sélecteurs fragiles et coordonnées absolues ne doivent être conservés que comme dernier recours clairement identifié comme tel.

#### 31.9.3 Promotion d’un apprentissage

Une observation ponctuelle ne devient pas automatiquement une connaissance durable.

Avant promotion, vérifier à une profondeur proportionnée que l’observation :

1. provient d’un run réel ou d’une vérification réelle de TradingView ;
2. est réutilisable au-delà du cas ponctuel qui l’a révélée ;
3. est suffisamment établie par répétition, corroboration, documentation actuelle ou reproduction claire du comportement ;
4. ne transforme pas un détail accidentel de l’UI en invariant ;
5. ne transforme pas un résultat propre à un script en règle générale de TradingView ;
6. améliore réellement navigation, observation, détection d’ambiguïté ou qualité de preuve.

Ne pas imposer un nombre fixe de répétitions lorsqu’une observation peut être établie autrement de manière suffisamment fiable.

#### 31.9.4 Persistance

Le guide versionné :

```text
.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md
```

est le lieu durable pour les connaissances opérationnelles explicitement promues de ce mode.

Il doit distinguer clairement :

- les instructions stables du mode ;
- les workflows ou landmarks réellement qualifiés ;
- les limites et failure modes connus ;
- les éléments fragiles ou susceptibles de devenir stale.

L’auto-memory Claude Code peut servir de sas temporaire pour des observations candidates, mais ne remplace jamais cette promotion volontaire lorsqu’une connaissance doit être réutilisée durablement.

Les preuves propres à un run restent dans le système de validation prévu ; elles ne doivent pas être copiées dans `CHROME_EXPERIMENTAL.md` comme vérités générales.

#### 31.9.5 Frontière connaissance / preuve

Une connaissance apprise décrit comment mieux observer ou naviguer. Elle ne prouve jamais que l’état courant correspond encore à ce qui a été appris.

En particulier :

```text
workflow connu
≠ étape courante réussie

landmark connu
≠ preuve automatique

absence historique d’ambiguïté
≠ absence actuelle d’ambiguïté
```

Chaque run doit réobserver l’état réellement présent.

L’apprentissage ne doit jamais abaisser le seuil de preuve de §31.5, ni convertir une supposition fondée sur l’historique en `passed`.

#### 31.9.6 Détection d’obsolescence et révision

Le mode doit être capable de reconnaître qu’un workflow ou landmark appris ne correspond plus à l’UI actuelle.

Lorsqu’un apprentissage devient contradictoire, absent, ambigu ou manifestement obsolète :

1. ne pas forcer l’ancien workflow ;
2. considérer la connaissance concernée comme non fiable pour le run courant ;
3. explorer prudemment l’état actuel ou déclencher le fallback manuel selon §31.6 ;
4. corriger, qualifier comme fragile ou retirer la connaissance durable devenue fausse lorsqu’une nouvelle observation suffisamment établie le justifie.

Une évolution de TradingView, Chrome, Claude Code ou de l’intégration navigateur peut justifier cette réévaluation sans qu’un changement de version soit à lui seul assimilé automatiquement à une preuve d’obsolescence.

#### 31.9.7 Contenu interdit

Ne jamais promouvoir dans le savoir opérationnel durable :

- mot de passe ;
- cookie ;
- token ;
- credential ou secret d’authentification ;
- décision produit le titulaire qui appartient à un autre artefact ;
- résultat d’une validation spécifique présenté comme règle générale ;
- contenu propriétaire d’un script conservé uniquement pour apprendre l’UI ;
- screenshot ou autre preuve de run lorsqu’il n’a pas de fonction durable distincte ;
- coordonnées ou sélecteurs fragiles présentés comme invariants fiables.

#### 31.9.8 Pas de nouvelle couche

Cet apprentissage reste une capacité interne du mode `chrome-experimental` et de la skill `tv-validate`.

Il ne justifie pas la création d’une base de données, registry, nouveau dossier de mémoire, nouveau serveur, MCP, agent, skill, dashboard ou autre plateforme parallèle.

Le bootstrap initial doit construire le mécanisme et les règles de promotion dans `CHROME_EXPERIMENTAL.md`, mais ne doit inventer aucun landmark, workflow ou failure mode présenté comme observé s’il n’a pas réellement été vérifié.

---

## 32. SKILL `project-doctor`

### 32.1 Deux couches

Le doctor possède :

1. une couche déterministe ;
2. une couche sémantique optionnelle pour la cohérence de configuration.

### 32.2 Contrôles déterministes

Au minimum :

- standard maître présent ;
- hash index courant ;
- hash traceability courant ;
- JSON valides ;
- manifests valides ;
- source manifest présent ;
- produit root cohérent ;
- conformité normative de `SCRIPT.json`, y compris `schema_version` (2 ; 1 lu et signalé pour migration), champs inconnus, `id == slug`, unicité case-insensitive, cohérence des axes de licence (§45.4) et confinement du chemin source ;
- configuration personnelle (`pws.config.json`) : présence (absence = INFO, défauts), validité, version du workspace, identité configurée ; clé legacy du mode TradingView signalée ;
- identité de l’exécuteur PineTS installé : pin, lockfile, intégrité registry, SHA de l’artefact installé enregistré dans `PROVENANCE.json`, fingerprint ;
- Git absent ou dossier non initialisé : mode dégradé signalé (WARNING), jamais une exception ;
- `.pine` orphelins ;
- contextes partiels ;
- source manquante ;
- source supplémentaire ambigu ;
- local settings lisibles ;
- TV mode valide ;
- validation effective stale ;
- intégrité de `validation/current.json`, de son run référencé et des hashes des preuves ;
- références de baseline, descripteurs de dataset et hashes comportementaux durables ;
- hooks exécutables ;
- tests de tooling ;
- Git disponible ;
- remotes présents ;
- worktree config ;
- `.claude/worktrees/` effectivement ignoré par Git ;
- absence de chemin ou symlink sortant du workspace physique ;
- absence de configuration ou contrat exigeant l’existence, le nom, le chemin ou l’état d’un autre projet externe ;
- dossiers/fichiers placeholder connus ;
- présence et lisibilité du thin adapter PineTS lorsqu’il est configuré ;
- dépendance PineTS pinée sur une version exacte ;
- cohérence `package.json` / lockfile ;
- absence de range flottant pour PineTS ;
- cohérence entre `pinets_version`, `executor_fingerprint`, `normalization_schema` et l’état de calibration ;
- cohérence des identités de cas, inputs, attendus, références et preuves qui soutiennent la fraîcheur des calibrations ;
- absence de capability utilisée comme effectivement gating lorsque sa calibration n’est pas `CURRENT` ;
- absence d’intégration PineTS sous forme de serveur, MCP, base de données ou service persistant non ratifié ;
- résolution effective des skills critiques vers les skills projet attendues, avec diagnostic explicite de toute collision ;
- provenance de la version PineTS installée et `license_basis` réellement enregistré.

`project-doctor` ne lance pas automatiquement les matrices comportementales lourdes.

Il vérifie l’intégrité et la fraîcheur de la couche PineTS.

Une calibration `STALE` ou `MISSING` interdit uniquement d’utiliser les capabilities concernées comme effectivement gating.

Elle ne classe pas automatiquement le source Pine comme `BROKEN` et ne remplace pas la validation TradingView.

### 32.3 Contrôle sémantique

Lorsqu’une évolution d’architecture a eu lieu, vérifier :

- duplications d’instructions ;
- responsabilités devenues concurrentes ;
- fichiers sans utilité ;
- incohérences entre contracts et implémentation.

### 32.4 Sortie

Statuts concis avec sévérité :

```text
OK
INFO
WARNING
BLOCKING
```

Un `BLOCKING` doit être actionnable.

---

## 33. SUBAGENT `pws-pine-cartographer`

### 33.1 Outils

Read-only.

### 33.2 Mémoire

Aucune mémoire persistante.

### 33.3 Rôle

Lire un gros script sans saturer le contexte principal.

Produire :

- carte structurelle ;
- dépendances ;
- état ;
- requests ;
- MTF ;
- rendering ;
- alertes ;
- hotspots ;
- risques ;
- consumers importants.

### 33.4 Interdiction

Ne pas modifier le code.

Ne pas inventer une intention produit.

---

## 34. SUBAGENT `pws-pine-researcher`

### 34.1 Outils

Lecture locale + web/recherche selon capacités disponibles.

Pas d’écriture projet directe sauf nécessité explicitement décidée par l’architecture finale.

Le mode privilégié est de retourner le résultat au parent, qui persiste ce qui mérite de l’être.

### 34.2 Mémoire

Aucune mémoire persistante.

### 34.3 Rôle

Vérifier :

- documentation officielle ;
- comportement Pine actuel ;
- benchmark pertinent ;
- règles TradingView lorsque concernées.

### 34.4 Sortie

Séparer :

- faits officiels ;
- observation benchmark ;
- inférence ;
- recommandation.

---

## 35. SUBAGENT `pws-pine-reviewer`

### 35.1 Contexte

Subagent non-fork lorsque la version actuelle de Claude Code permet ainsi un contexte frais adapté.

### 35.2 Mémoire

Aucune.

### 35.3 Rôle

Être réellement un regard frais.

Le reviewer n’est invoqué que dans les cas du §26.1. Il relit selon la couverture indiquée dans la mission (ciblée, élargie ou globale, master §9.2) et le contexte produit réellement nécessaire ; sans indication, le source complet.

Le diff peut servir de point d’attention ; il ne définit pas la couverture.

### 35.4 Outils

Read-only.

### 35.5 Interdiction

Ne pas appliquer directement ses propres corrections.

Le parent conserve la responsabilité d’implémentation.

---

## 36. SUBAGENT `pws-release-reviewer`

### 36.1 Outils

Lecture + web.

### 36.2 Mémoire

Aucune.

### 36.3 Rôle

Juste avant release :

- vérifier règles TradingView actuelles ;
- vérifier exigences spécifiques au type de script ;
- vérifier cohérence des artefacts ;
- rechercher divergences entre source final, docs et publication ;
- signaler tout point non vérifié.

---

## 37. OUTIL DÉTERMINISTE LOCAL

Créer un petit package local, sans ambition de reproduire TradingView.

Commande conceptuelle :

```text
python -m tools.pws_workspace <subcommand>
```

Le bootstrap doit adapter le launcher au runtime réel détecté.

Ne pas ajouter de dépendance externe lorsqu’une bibliothèque standard suffit.

### 37.1 Sous-commandes minimales

Prévoir des fonctions équivalentes à :

```text
version
session-status
menu
scan
doctor
standard-index
standard-status
guard
source-fingerprint
validation-status
tv-mode
import-register
hook-session-start
hook-stop
init | config show | config set            (pws.config.json — §19A)
migrate --plan | --apply | --rollback      (§55)
tooling-status | pinets <action>           (PineTS : status, verify, check-update, install, rollback, recalibrate-plan)
github <action>                            (status, destinations, destination-add/remove, export-plan, fetch, export-diff, publish — §43.5)
maintenance <action>                       (cleanup, archives-plan/import/verify/remove-source)
license <action>                           (status, render, write, fields-skeleton, templates)
build-distribution --target <dir>          (distribution publique — cœur commun, liste blanche)
```

Le nom exact peut être ajusté pour cohérence. `menu` fournit l’arborescence déterministe et localisée du menu PWS (entrées applicables, ≤ 4 options par écran, parcours action → script) : la skill `pws` la rend sans la redéfinir.

### 37.2 Responsabilités du package

Seulement des faits mécaniques :

- filesystem ;
- Git local ;
- JSON ;
- hash ;
- structure ;
- header simple ;
- chaînes interdites mécaniquement ;
- état de validation ;
- état du standard.

`session-status` doit pouvoir fournir une représentation structurée exploitable par la skill `pws` afin que le menu dérive ses choix de faits mécaniques déjà calculés au lieu de réimplémenter le scan du workspace.

### 37.3 Ce qu’il ne juge pas

Interdit de prétendre déterminer :

- qualité du signal ;
- pertinence d’un tooltip ;
- repaint réel ;
- correctness métier ;
- bonne UX ;
- originalité ;
- qualité du benchmark ;
- architecture Pine optimale ;
- conformité visuelle TradingView.

---

## 38. GUARD PINE LOCAL

### 38.1 Scope

Uniquement les contrôles déterministes réellement fiables.

### 38.2 Contrôles candidats

Selon ce que le bootstrap peut implémenter proprement :

- source existant ;
- `//@version=6` selon le standard ;
- absence de `shorttitle` ;
- absence de `short_title` ;
- structure de header correspondant au modèle de distribution ;
- version produit dans le header source ;
- absence de version produit explicitement répétée dans les fichiers user-facing contrôlables ;
- title vérifiable comme ASCII lorsqu’extractible sûrement ;
- cohérence source/manifest ;
- JSON contextuels valides ;
- URLs manifestement interdites dans le header/source si une règle mécanique fiable existe.

### 38.3 Principe de prudence

Un check déterministe qui produit trop de faux positifs doit être réduit ou supprimé.

Ne pas transformer une heuristique fragile en gate bloquant.

---

## 39. TESTS DU TOOLING

Le package local doit posséder de vrais tests.

Préférer `unittest` de la bibliothèque standard si cela évite une dépendance.

Les tests doivent couvrir notamment :

- détection d’un script enregistré ;
- détection d’un `.pine` orphelin ;
- manifest incomplet ;
- manifest avec champ inconnu ;
- collision de slug/ID ne différant que par la casse ;
- source absolu, traversal `..` et symlink sortant du product root ;
- matrice type/distribution, notamment rejet de `library + paid-closed-source` ;
- source manquante ;
- plusieurs sources ambiguës ;
- détection `shorttitle` ;
- distinction entre `shorttitle` réel et occurrence dans un commentaire, une string ou une documentation ;
- URL Creative Commons légitime et URL promotionnelle interdite ;
- title multilignes extractible et syntaxe de title non extractible sans faux verdict bloquant ;
- header gratuit ;
- header payant ;
- hash source ;
- validation stale ;
- run de validation absent/invalide et preuve dont le hash diverge ;
- update atomique où un run plus ancien ne remplace pas un run plus récent ;
- mode TV valide/invalide ;
- standard index stale ;
- comportement hook Stop ;
- sortie structurée de `session-status` suffisante pour alimenter le menu PWS sans logique sémantique ;
- read-modify-write de `settings.local.json` préservant des approvals, selon la portée de §19.3 : sérialisation entre écrivains du workspace et refus des modifications externes détectables ;
- workspace et source dont les chemins contiennent des espaces ;
- détection d'un repository parent englobant et d'un symlink sortant ;
- fonctionnement avec un sibling arbitrairement nommé, présent ou absent, sans dépendance, scan ni mutation de son contenu ;
- tests durables du thin adapter et des contrats PineTS de §61.10 ;
- attribution des findings du hook Stop : déplacement sans modification, anomalie préexistante, anomalie introduite, provenance indéterminée, décalage de lignes, occurrences multiples ; cohérence des verdicts d’un rapport de version 2 : priorité de `failed`, couverture, identifiants uniques, refus de promotion d’un rapport de version antérieure ; confirmations par groupe ; compilation minimale jamais `passed`, erreurs et avertissements consignés séparément, enregistrement sans promotion sur le même SHA, remplacement par un échec avec contradiction signalée, protections de §51.4 jamais contournées ; enregistrement d’import : import déclaré puis onboardé sans modification, modification après import, refus de réenregistrement après modification, égalité d’empreinte sans dispense, rattachement ambigu.

Principe des guards textuels :

```text
incertitude du parseur
≠ preuve de violation
```

Un cas non extractible doit produire un diagnostic honnête ou une vérification complémentaire, pas un faux `BLOCKING`.

Ne pas créer cinq fichiers de tests contenant chacun un test trivial uniquement pour satisfaire l’arborescence.

La factorisation réelle prime.

---

## 40. HOOK `SessionStart`

### 40.1 Mission

Donner à Claude un petit état dynamique au démarrage et fournir les faits mécaniques nécessaires au menu contextuel PWS.

### 40.2 Actions

Le hook doit :

1. scanner `scripts/**`;
2. déterminer les statuts de registration ;
3. détecter les `.pine` orphelins ;
4. vérifier l’état du standard index ;
5. vérifier le mode TV ;
6. vérifier l’état Git ;
7. identifier les validations stale ;
8. créer un snapshot de session éphémère des sources enregistrées ;
9. injecter un résumé court dans le contexte ;
10. rendre disponible un état structuré suffisamment petit pour que la skill `pws` puisse construire son menu sans rescanner sémantiquement le projet.

### 40.3 Exemple de sortie

```text
PWS
Git: local / branch main / dirty
TV validation mode: manual
Registered scripts: 12
Unregistered scripts: 1
Incomplete products: 0
Stale TradingView validations: 2
Master index: current

UNREGISTERED
scripts/new-indicator/New Indicator.pine

Required action before substantive edits: pine-onboard
```

### 40.4 Onboarding automatique

Le hook ne prétend pas invoquer une skill lui-même.

Il rend le statut visible.

La description de `pine-onboard` et les instructions racine doivent permettre à Claude de l’invoquer automatiquement lorsqu’un script orphelin doit être traité.

### 40.5 Menu contextuel PWS

Créer la skill projet :

```text
.claude/skills/pws/SKILL.md
```

Sa commande utilisateur est :

```text
/pws
```

Elle constitue la façade guidée du workspace. Elle ne remplace aucune skill métier.

#### 40.5.1 Primitive d’interaction

Utiliser en priorité `AskUserQuestion`, primitive native Claude Code destinée aux choix multiples, tant qu’elle est disponible et adaptée sur la surface interactive courante.

Les limites exactes de `AskUserQuestion` peuvent évoluer. Les revérifier pendant la discovery et tester la primitive réellement installée. Concevoir dans tous les cas le menu comme une arborescence courte de sous-menus plutôt qu’une liste plate surchargée.

Ne pas créer au bootstrap :

- TUI Python concurrent ;
- application Electron ;
- serveur local ;
- dashboard web ;
- base de données de navigation ;
- MCP dédié au menu ;
- plugin custom uniquement pour afficher ce menu.

Si `AskUserQuestion` devient indisponible ou insuffisant dans une surface future, utiliser d’abord un fallback conversationnel simple puis réévaluer toute nouvelle couche selon §59.

#### 40.5.2 Modèle de démarrage

Le menu vit DANS la session Claude Code.

Architecture ratifiée :

```text
Claude Code interactif
        ↓
SessionStart
        ↓
état PWS compact
        ↓
skill pws
        ↓
AskUserQuestion
        ↓
choix utilisateur
        ↓
skill métier correspondante
```

Un hook `SessionStart` ne doit pas tenter de piloter directement un TTY interactif ou de simuler des touches clavier. Il fournit le contexte ; l’interaction appartient à la skill `pws` dans la conversation.

Pour une nouvelle session CLI où le titulaire souhaite arriver immédiatement sur le menu, documenter la forme native actuelle :

```text
claude "Ouvre le menu PWS."
```

Claude Code démarre alors en mode interactif avec cette demande comme premier prompt.

Le démarrage classique `claude` reste valide ; `/pws` ouvre alors le menu à tout moment.

Un resume, un compact ou un clear ne doit pas forcer la réouverture du menu et interrompre le travail en cours. Le titulaire peut toujours utiliser `/pws` explicitement.

#### 40.5.3 Menu contextuel

Le menu doit dériver ses choix de l’état réel du workspace.

Exemples de faits utiles, en conservant les axes distincts de §44 :

- aucun produit enregistré ;
- un ou plusieurs produits `REGISTERED` ;
- présence de `.pine` `UNREGISTERED` ;
- produit `INCOMPLETE` ou `BROKEN` ;
- validation TradingView `STALE` ;
- mode TV courant ;
- état Git pertinent.

Ne pas afficher artificiellement une action sans objet. Par exemple, ne pas proposer une release d’un produit inexistant.

Le premier niveau doit rester court. Une organisation de référence est :

```text
PWS
├── Travailler sur un script
├── Nouveau / importer
├── Qualité / validation
└── Maintenance / autre
```

Chaque branche ouvre uniquement les sous-options réellement applicables.

Exemple :

```text
Nouveau / importer
├── Nouveau script
├── Importer un script
└── Retour
```

Pour la branche « Qualité / publication » (libellé ratifié) :

```text
Qualité / publication
├── Test local (PineTS)
├── Validation TradingView
├── Licence et conditions d'utilisation     (consulter, compléter, prévisualiser, enregistrer et générer sur choix explicite ; indépendant de « Préparer une publication »)
├── Préparer une publication
├── Export GitHub
└── Retour
```

Puis, pour un nouveau script :

```text
Type
├── Indicator
├── Strategy
├── Library
└── Retour

Distribution
├── Gratuit / open-source
├── Payant / closed-source
└── Retour
```

Pour `Library`, ne pas ouvrir ce sous-menu avec une option payante. Dériver et afficher :

```text
Distribution
└── Gratuit / open-source (obligatoire pour les libraries TradingView)
```

La contrainte doit être revérifiée avant publication, mais le menu, `pine-new` et le schéma machine appliquent la règle officielle actuelle tant qu'elle demeure en vigueur.

Les libellés sont user-facing ; les valeurs transmises au workflow restent les valeurs canoniques du workspace, par exemple :

```text
script_kind = indicator
distribution = paid-closed-source
```

#### 40.5.4 Navigation et effets

Le menu doit respecter les invariants suivants :

- `Retour` ne produit aucun effet de bord ;
- annuler le menu ne modifie aucun fichier ;
- une sélection ne vaut pas autorisation implicite de publication ;
- un choix de workflow route vers la skill existante correspondante ;
- une décision durable prise dans le menu n’est persistée que dans l’artefact canonique prévu par le workflow ;
- aucune logique métier n’est dupliquée dans `pws/SKILL.md` ;
- le menu ne contourne ni les confirmations le titulaire déjà exigées, ni les gates, ni la validation TradingView ;
- si une information libre est nécessaire, sortir du menu et demander cette information conversationnellement au lieu de transformer le menu en formulaire généraliste.

Pour une création de produit, afficher avant toute création un récapitulatif court des choix structurés et demander confirmation :

```text
Type: Indicator
Distribution: Payant / closed-source

Démarrer / Modifier / Annuler
```

#### 40.5.5 Routage de référence

Le menu route notamment vers :

```text
Continuer / développer       → pine-develop
Nouveau script              → pine-new
Importer un script          → pine-onboard
Recherche                   → pine-research
Revue                       → pine-review
Test local                  → pine-local-test
Validation TradingView      → tv-validate
Licence et conditions d'utilisation → pine-license (indépendant de pine-release)
Préparer une release        → pine-release
Changer le mode TV          → choix utilisateur explicite → contrôleur déterministe partagé `pws_workspace tv-mode`
Maintenance                 → project-doctor ou état déterministe approprié
```

`Changer le mode TV` ne route pas vers `Skill(tv-mode)`, puisque `/tv-mode` reste user-only avec `disable-model-invocation: true`. La façade et la skill directe partagent le même contrôleur ; aucune logique de mutation n'est dupliquée dans le menu.

Les commandes directes restent disponibles. Le menu est une façade UX, pas une obligation pour Claude ni une couche d’autorité.

#### 40.5.6 Fraîcheur

Lorsqu’un `/pws` est invoqué longtemps après `SessionStart` ou après des changements significatifs, rafraîchir les faits mécaniques nécessaires via le tooling déterministe, de préférence `session-status`, avant de construire le menu.

Ne pas utiliser une ancienne observation de session comme vérité courante si elle peut avoir changé.

### 40.6 Snapshot

Le snapshot de session est éphémère et associé au `session_id`.

Il sert au Stop hook à distinguer :

- fichiers déjà présents au premier démarrage de la session ;
- sources réellement changés pendant cette session.

Créer la baseline une seule fois pour un `session_id`.

Si `SessionStart` se déclenche de nouveau à cause d’un resume, d’un compact, d’un clear ou d’un autre mécanisme qui conserve le même travail logique, ne pas écraser silencieusement une baseline déjà existante.

Les sessions de subagents doivent utiliser un état séparé ou ignorer cette baseline lorsqu’elles sont read-only ; elles ne doivent jamais réinitialiser l’état de la session principale.

Ne pas versionner ce snapshot.

---

## 41. HOOK `Stop`

### 41.1 Mission

Empêcher une clôture avec une violation mécanique réparable introduite pendant la session.

Garde-fou mécanique du travail courant (master §9.1, niveau 1) : il ne déclenche ni lecture intégrale, ni agent, ni revue (amendement du 2026-11-13).

### 41.2 Source des changements

Comparer avec le snapshot SessionStart et l’état Git pour identifier les `.pine` réellement modifiés depuis le démarrage. Le snapshot conserve, par fichier, le chemin, le SHA-256, les findings bloquants du guard évalués au démarrage et les checks non évaluables à ce moment. Chaque fichier présent au Stop est rattaché à la baseline par chemin, sinon par SHA-256 (déplacé, inchangé), sinon par un renommage détecté par Git lorsque la correspondance entre le fichier de la baseline et le fichier courant est non ambiguë (déplacé et modifié) ; à défaut, sa provenance est indéterminée. Un renommage détecté par Git est une correspondance technique ; il ne prouve pas à lui seul l’historique réel du fichier. Le nom du fichier ou l’appartenance au même produit ne suffisent pas ; toute correspondance ambiguë reste indéterminée. L’absence de correspondance ne prouve pas qu’un fichier est nouveau. L’attribution se fait finding par finding, un finding étant identifié par son check et par l’objet de l’anomalie (élément manquant, valeur ou URL en cause), indépendamment de sa position dans le fichier ; les occurrences multiples d’un même objet sont comptées. Un finding est introduit si le fichier est nouveau ou si le check était évaluable au démarrage sans ce finding ; préexistant si le même finding existait au démarrage, même si le fichier a changé ailleurs ; rendu visible par le contexte si le check n’était pas évaluable au démarrage ; indéterminé si la provenance du fichier ne peut pas être établie. Le guard est toujours ré-exécuté avec le contexte courant ; une empreinte connue ne dispense d’aucun check.

Un source importé pendant la session peut faire l’objet d’un enregistrement d’import (§52.5). Le fichier rattaché à cet enregistrement est comparé à l’état du guard relevé à l’import, selon les mêmes règles : un finding déjà présent à l’import est préexistant à l’import, un finding apparu ensuite est introduit, un check non évaluable à l’import est rendu visible par le contexte. Un enregistrement se rattache à un seul fichier ; une simple égalité d’empreinte ne dispense aucun autre fichier des contrôles, et tout rattachement ambigu reste indéterminé. Un fichier absent de la baseline et sans enregistrement d’import reste nouveau.

### 41.3 Comportement

Pour les `.pine` changés durant la session :

- vérifier qu’ils appartiennent à un produit onboardé ;
- exécuter le guard mécanique ;
- signaler validation TradingView stale ;
- bloquer seulement sur les violations mécaniques réellement bloquantes introduites pendant la session ; signaler sans bloquer les violations préexistantes, rendues visibles par le contexte ou d’attribution indéterminée, avec leur catégorie.

### 41.4 Validation TradingView stale

Une validation stale n’empêche pas automatiquement chaque réponse Claude.

Elle empêche de présenter le script comme finalement validé/prêt si la tâche exige cette validation.

Le Stop hook peut ajouter un contexte informatif sans boucle inutile.

### 41.5 Boucles

Respecter `stop_hook_active` ou l’équivalent actuel.

Ne pas créer une condition impossible à satisfaire.

Claude Code limite actuellement les continuations successives d’un Stop hook.

Le hook doit être :

- rapide ;
- déterministe ;
- actionnable ;
- peu bruyant.

---

## 42. PAS DE HOOK SÉMANTIQUE PAR DÉFAUT

Ne pas créer initialement :

- prompt hook jugeant la qualité du Pine à chaque edit ;
- agent hook de revue après chaque ligne ;
- hook réseau ;
- hook de publication ;
- hook de benchmark automatique à chaque changement ;
- hook lançant PineTS ;
- hook exécutant des régressions comportementales ;
- hook exécutant une matrice de datasets, de paramètres ou de stability probes.

Les checks sémantiques appartiennent aux workflows/agents.

PineTS n’est exécuté ni par `SessionStart`, ni par `PostToolUse`, ni par le `Stop` hook du socle.

L’exécution comportementale appartient exclusivement aux workflows explicites tels que `pine-new`, `pine-develop`, `pine-release` ou `pine-local-test`.

Les hooks restent des garde-fous mécaniques ou de contexte.

---

## 43. GIT LOCAL

### 43.1 Initialisation

Avant `git init` ou toute mutation, appliquer la frontière physique de §6.1. Si `pine workspace` est déjà englobé par un repository parent, ne pas initialiser un repository imbriqué ni accepter silencieusement la racine parent : arrêter et demander une décision au titulaire.

Si le workspace n’est pas un repo Git :

- initialiser localement ;
- utiliser le défaut Git de la machine lorsqu’il est sain ;
- sinon utiliser une branche de travail conventionnelle telle que `main` ;
- ne pas créer de remote.

Si un remote existe déjà dans un workspace préexistant :

- le signaler ;
- ne pas le supprimer silencieusement ;
- ne pas l’utiliser pour pousser sans décision explicite du titulaire.

### 43.2 Commit

Ne pas créer automatiquement un commit sans approbation explicite du titulaire.

Le bootstrap peut préparer les changements et proposer le premier commit.

### 43.3 Worktrees

Utiliser les worktrees pour :

- changement structurel risqué ;
- expérimentation ;
- travail parallèle ;
- futur agent modificateur ;
- isolation utile.

Ne pas imposer un worktree pour une typo.

Les worktrees Git ne sont utilisables qu'après l'existence d'un commit de base exploitable. Avant le premier commit autorisé, documenter cette limitation au lieu de prétendre que l'isolation worktree est opérationnelle.

### 43.4 Subagents actuels

Les quatre subagents de base sont read-only.

Ils n’ont donc pas besoin de worktree.

Tout futur subagent autorisé à modifier du code doit être évalué pour `isolation: worktree`.

### 43.5 Backup

Git local sur le même disque n’est pas un backup matériel.

`OPERATIONS.md` peut recommander, sans l’imposer :

- un second repo bare local ;
- un disque externe ;
- un NAS ;
- autre stockage privé décidé par le titulaire.

Ne pas introduire GitHub par défaut. Les archives locales regroupées sous `docs/maintenance/archives/` ne tiennent pas lieu de backup indépendant du disque.

**Parcours d’export GitHub (ratifié le 2026-11-06)** : destinations déclarées dans `pws.config.json` (`name`, `repo`, `visibility`, `path_prefix`, `branch`) ; `github export-plan` construit, pour un produit REGISTERED, l’ensemble exporté à partir d’une liste de contenus autorisés (source seulement si `source_visibility = public` ou destination `private` ; documents de release, tutoriel, conditions référencées) et liste les exclusions motivées (manifeste, contexte interne, décisions, recherche, preuves de validation, suivi) ; jamais le workspace, `pws.config.json`, `.claude/`, `docs/maintenance/`, des archives ni des secrets. `github fetch` (clone local, acte réseau explicite) puis `github export-diff` montrent ajouté/modifié/inchangé ; `github publish --yes` copie, committe et pousse dans le clone après autorisation explicite du titulaire pour ce plan précis (`git push` reste soumis à confirmation). Tout envoi, contenu public compris, exige avant toute écriture dans le clone que l’URL de la destination et le clone (une seule URL de fetch et de push, `pushurl` et réécritures appliqués) désignent le dépôt de github.com configuré pour la destination, sous des formes d’URL strictes ; le remote est relu juste avant le push et, s’il a changé après le commit local, rien n’est poussé et l’état laissé sur disque est décrit (demande du titulaire du 2026-11-14 : identité du dépôt autorisé, distincte de la confidentialité ; un contenu public peut aller vers un dépôt privé choisi explicitement). Ce qui part est exactement le plan : une entrée d’URL vide ou un réglage qui fait se connecter Git ailleurs que l’URL affichée ou sans la vérifier (programme SSH ou de connexion remplacé, assistant distant, adresse imposée, vérification TLS désactivée, dans la configuration ou l’environnement) est refusé ; une cible qui ne diffère que par la casse d’une entrée du dépôt ou qui exige un dossier là où il a un fichier est refusée ; un fichier dont Git modifierait les octets au commit est refusé avant toute écriture ; aucun hook ne s’exécute dans le clone de publication ; le commit local est vérifié avant le push. Un envoi qui contient un source fermé exige en outre, immédiatement avant le push, que GitHub rapporte comme `PRIVATE` le dépôt configuré lui-même (`gh repo view`, authentification courante) ; à défaut, refus (décision du titulaire du 2026-11-13, constat I-06). La visibilité peut changer entre ce contrôle et l’envoi : aucune garantie atomique. Un script importé est exporté avec ses documents juridiques d’origine déclarés (`license.documents`, §45.2), à l’identique (nom, octets, encodage, langue), jamais remplacés par un modèle PWS ; un fichier de nom juridique n’est jamais inclus pour son seul nom ni écarté en silence : tant qu’un document n’est pas déclaré, est absent, modifié depuis le plan ou refusé par un contrôle (lien, fichier spécial, contenu non contrôlable, syntaxe de modèle PWS, code d’un source fermé vers une destination publique), l’export entier attend, avec la résolution. Un dossier privé dans un dépôt public n’est jamais supposé possible ; un dépôt existant est une destination à configurer, jamais à restructurer ; retrait de fichiers, réécriture d’historique et changement de visibilité restent des actes du titulaire hors workflow.

---

## 44. MODÈLE DE REGISTRATION DES SCRIPTS

Ne pas maintenir de registry centrale séparée.

La vérité est distribuée par produit :

```text
scripts/<slug>/SCRIPT.json
```

Le workspace reconstruit la liste des produits en scannant ces manifests.

Cela évite :

```text
central registry ≠ dossiers réels
```

### 44.1 Axes d'état déterministes

Ne pas réduire plusieurs constats indépendants à un statut unique. Le scanner expose au minimum :

```text
product_structure_status:
  REGISTERED
  INCOMPLETE
  BROKEN
  AMBIGUOUS

source_registration_status:
  REGISTERED
  UNREGISTERED

validation_status persisted:
  unverified
  in-progress
  passed
  failed
  partial

validation_integrity_status:
  OK
  BROKEN

validation_effective_status derived:
  valeur persistée applicable
  stale
  null si l'intégrité est BROKEN
```

Un product root peut donc être `BROKEN` tout en contenant un `.pine` `UNREGISTERED`, sans qu'un constat écrase l'autre.

Dans l'axe `product_structure_status`, appliquer l'ordre déterministe suivant uniquement pour produire la valeur synthétique :

```text
AMBIGUOUS
> BROKEN
> INCOMPLETE
> REGISTERED
```

`AMBIGUOUS` signifie que l'identité sûre du produit ou de sa source ne peut pas être établie ; `BROKEN` qu'un contrat présent est invalide ou incohérent ; `INCOMPLETE` qu'un élément requis manque sans ambiguïté ni contrat cassé ; `REGISTERED` que les critères mécaniques sont satisfaits. Le scanner conserve parallèlement une liste structurée de tous les findings applicables afin que la valeur synthétique ne masque pas les causes secondaires.

### 44.2 `product_structure_status = REGISTERED`

Un produit est structurellement onboardé si :

- root produit valide ;
- `SCRIPT.json` valide ;
- source déclarée présente dans ce root ;
- `PRODUCT.md` présent, lisible, non vide et sans placeholder explicitement connu ;
- `ARCHITECTURE.md` présent, lisible, non vide et sans placeholder explicitement connu ;
- `CLAUDE.md` local présent, lisible, non vide et sans placeholder explicitement connu ;
- `validation/current.json` présent ;
- modèle de distribution résolu ;
- aucune ambiguïté de source principale.

Le scanner ne prétend pas juger mécaniquement que ces documents sont sémantiquement « substantiels » ou de bonne qualité. Cette revue appartient à l'onboarding, au reviewer ou à un contrôle sémantique explicite du doctor.

### 44.3 `source_registration_status`

`REGISTERED` signifie que le `.pine` est la source canonique d'un `SCRIPT.json` v1 valide dont le chemin se résout dans le même product root.

`UNREGISTERED` signifie qu'un `.pine` existe sous `scripts/**` mais n'appartient à aucun manifest valide.

Un même `.pine` ne peut pas être revendiqué par plusieurs manifests. Toute revendication multiple est signalée comme ambiguïté structurelle sans choix silencieux.

### 44.4 `product_structure_status = INCOMPLETE`

Des éléments d’onboarding existent mais le contexte minimal est incomplet.

### 44.5 `product_structure_status = BROKEN`

Le manifest pointe vers une source absente ou une structure incohérente.

### 44.6 `product_structure_status = AMBIGUOUS`

Plusieurs `.pine` ou plusieurs contextes empêchent de déterminer de manière sûre le produit/source principal.

### 44.7 `.pine` directement sous `/scripts`

Le signaler comme structurellement non onboardé.

Ne pas le déplacer silencieusement si le slug cible n’est pas évident.

---

## 45. `SCRIPT.json` — CONTRAT

### 45.1 But

Routage machine minimal.

### 45.2 Schéma 3 normatif (ratifié le 2026-11-06, dimensions de publication séparées)

```json
{
  "schema_version": 3,
  "id": "zigzag-orderblock-retracement",
  "source": "ZigZag OrderBlock Retracement.pine",
  "script_kind": "indicator",
  "profile": "COMMERCIAL",
  "license": {
    "id": "PROPRIETARY",
    "grant": "eula",
    "source_visibility": "closed",
    "access": "paid",
    "copyright_holder": null,
    "created_year": 2024,
    "terms_ref": "release/EULA.md",
    "terms_url": null
  },
  "publication": { "state": "published", "privacy": "public", "mode": "invite-only" },
  "migration": { "from_schema": 2, "from_publication": "tradingview-invite-only", "on": "2026-11-06", "note": "…" }
}
```

Pour `schema_version = 3`, les sept champs `schema_version`, `id`, `source`, `script_kind`, `profile`, `license`, `publication` sont obligatoires, `migration` est facultatif, et tout autre champ est rejeté. `license` porte quatre axes obligatoires (`id`, `grant`, `source_visibility`, `access`) et quatre champs facultatifs (`copyright_holder` : null → identité configurée ; `created_year` : année de création, conservée lors des mises à jour ; `terms_ref` : chemin relatif, confiné au product root, vers les conditions rendues ; `terms_url` : URL https de la référence légale déclarée du produit, seule URL non standard admise par le guard, par correspondance exacte). `publication` porte exactement trois dimensions indépendantes, chacune nullable (null = inconnu, signalé, jamais déduit) : `state` ∈ `unpublished`, `published` ; `privacy` ∈ `public`, `private` (confidentialité de la publication TradingView) ; `mode` ∈ `open`, `protected`, `invite-only` (mode du script : source visible, source masqué, accès par invitation). Aucune de ces valeurs n’est dérivée d’une autre ; les cohérences de §45.4 les contrôlent entre elles. Toute extension passe par une évolution explicite du schéma.

Schémas antérieurs, lus par compatibilité et migrés explicitement (`migrate --apply`, étape m005) : schéma 1 (`distribution` ∈ `free-open-source`, `paid-closed-source` → profil et axes dérivés des défauts, état de publication inconnu) ; schéma 2 (`license.publication` en une seule chaîne qui confondait confidentialité et mode → `tradingview-open|protected|invite-only` = mode correspondant et confidentialité INCONNUE (jamais déduite), `tradingview-private` = confidentialité privée et mode INCONNU, `unpublished` = état non publié ; l’état reste inconnu sauf pour `unpublished`) ; schéma 1 → publication entièrement inconnue (les défauts de profil sont des propositions pour un nouveau projet, jamais des faits d’un projet migré). Les deux formes sont signalées (`MANIFEST_LEGACY_SCHEMA`) ; la migration conserve les seules informations enregistrées, laisse les inconnues nulles et les rapporte comme ambiguïtés ; une migration antérieure ayant déduit une valeur est rectifiée de façon tracée (`migration.rectifications`) sans toucher une valeur confirmée par le titulaire (`migration.holder_confirmed`, `license confirm`). Une année de création inconnue n’est jamais remplacée par l’année courante.

`id` est exactement égal au slug du product root. Les IDs/slugs sont uniques dans le workspace avec une comparaison case-insensitive afin d'éviter les collisions sur les filesystems macOS généralement insensibles à la casse.

`source` est un chemin relatif au product root vers un fichier `.pine`. Sa résolution physique finale doit rester dans ce root. Sont rejetés :

- chemin absolu ;
- traversal `..` sortant ;
- symlink ou chaîne de symlinks sortant du product root ;
- référence à une source située dans un autre product root, un autre projet ou tout emplacement extérieur au product root ;
- chemin ambigu ou source principale non unique.

Aucun outil ne lit un source dont le chemin résolu sort du product root (scanner, guard, `validation-status`, hooks) ; un manifeste invalide ne provoque jamais une lecture hors périmètre.

`SCRIPT.json` est la source machine canonique de `script_kind`, du profil et des axes de licence. `PRODUCT.md` et `CLAUDE.md` peuvent les expliquer, mais ne les redéfinissent pas comme autorités concurrentes.

**Licence existante d’un script importé** (évolution explicite décidée par le titulaire le 2026-11-13, constat C-19 ; extension compatible : `schema_version` reste 3, tout manifeste antérieur reste valide et inchangé, aucune migration). `license` admet deux champs facultatifs supplémentaires : `origin` ∈ `profile` (défaut quand il est absent ou nul : licence d’un profil) | `imported` (licence existante d’un script importé, conservée) ; `status` ∈ `confirmed` | `to-analyse`, obligatoire quand `origin = imported` et interdit sinon. Avec `origin = imported` : `status = confirmed` ⇒ `id` ∈ liste fermée d’identifiants SPDX exacts confirmés par le titulaire (`CC-BY-NC-SA-4.0`, `MPL-2.0`, `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `GPL-2.0-only`, `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later`, `LGPL-2.1-only`, `LGPL-2.1-or-later`, `LGPL-3.0-only`, `LGPL-3.0-or-later`, `AGPL-3.0-only`, `AGPL-3.0-or-later`) ; `status = to-analyse` ⇒ `id = null` ; `grant = license` (droits définis par la licence elle-même ; `cc` pour `CC-BY-NC-SA-4.0`). `grant = license` est réservé à `origin = imported` ; `PROPRIETARY` n’est jamais une licence importée. Les identifiants SPDX dépréciés (`GPL-2.0`, `GPL-3.0`, `LGPL-2.1`, `LGPL-3.0`, `AGPL-3.0` et leurs formes « + ») ne sont jamais enregistrés ; « only » et « or later » ne sont jamais assimilés. Un manifeste de schéma 2 ne porte jamais ces champs. La vue validée n’expose `origin` et `status` que lorsqu’ils sont enregistrés. Documents juridiques d’origine (demande du titulaire du 2026-11-14, même extension compatible) : `license.documents`, facultatif et réservé à `origin = imported`, liste les fichiers qui accompagnent la licence existante (texte de licence, `NOTICE`, attributions), déclarés par le titulaire — chemins relatifs à la racine du produit ou directement sous `release/` portant un nom juridique (`LICENSE`, `LICENCE`, `COPYING`, `COPYRIGHT`, `NOTICE`, `PATENTS`, `AUTHORS`, `CREDITS`, `ATTRIBUTION`, `CONTRIBUTORS`, `THIRD_PARTY_NOTICES` et leurs variantes), ou textes `LICENSES/<licence>.txt` (disposition REUSE) ; jamais un fichier caché, un source Pine, un JSON, un verrou, un fichier interne de Pine Workspace ni un nom portant un caractère invisible ; un fichier de nom juridique situé ailleurs dans le produit (dossiers internes exceptés), un dossier de nom juridique ou un `release/` / `LICENSES/` qui est un lien fait attendre l’export jusqu’à ce que le titulaire le déplace ; `[]` = aucun document séparé ; absent ou nul = non déclaré. L’identifiant SPDX enregistré ne dit pas à lui seul quels documents une redistribution exige.

```json
"license": { "id": "MPL-2.0", "grant": "license", "source_visibility": "public", "access": "free",
             "origin": "imported", "status": "confirmed",
             "copyright_holder": null, "created_year": null, "terms_ref": null, "terms_url": null }
```

### 45.3 Valeurs `script_kind`

Supporter selon Pine actuel :

```text
indicator
strategy
library
```

### 45.4 Profils, axes de licence et dimensions de publication

Profils (configurations de départ, jamais des niveaux de qualité ni des modes imposés — master §5) :

| Profil | `license.id` / `grant` | `source_visibility` | `access` | `publication` par défaut (state / privacy / mode) |
| --- | --- | --- | --- | --- |
| `FREE` | `CC-BY-NC-SA-4.0` / `cc` | `public` | `free` | `unpublished` / `public` / `open` |
| `FREE` à source fermé (même profil, axes ajustés) | `PROPRIETARY` / `free-use` | `closed` | `free` | `unpublished` / `public` / `protected` |
| `PRIVATE` | `PROPRIETARY` / `none` | `closed` | `restricted` | `unpublished` / null / null |
| `COMMERCIAL` | `PROPRIETARY` / `eula` | `closed` | `paid` | `unpublished` / `public` / `invite-only` |

`PRIVATE` est un profil d’usage : il ne désigne ni une publication privée TradingView (`publication.privacy`) ni un dépôt GitHub privé. Règles TradingView consultées le 2026-11-06 (Pine Script User Manual, « Publishing scripts ») : confidentialité et mode sont deux réglages distincts de la publication ; seul un script public `invite-only` peut être payant ; la vente d’accès à un script privé est interdite, comme la facturation d’un script `open` ou `protected`.

**Licence existante d’un script importé.** Les profils sont les configurations proposées aux nouveaux projets ; ils ne forcent jamais la licence d’un script importé. Quatre notions restent distinctes : profil d’usage, licence (`license.id` exact), visibilité du source, publication (état, confidentialité, mode). Une licence importée conserve son texte, ses notices et ses attributions ; aucune licence n’est attribuée automatiquement ; une détection d’en-tête est une proposition à confirmer par le titulaire, jamais une preuve juridique. Proposition : « either version N of the License, or (at your option) any later version » → `-or-later` ; « version N » seule → `-only` ; toute autre formulation → à analyser (notamment plusieurs versions ou un choix entre versions — « version 2 or 3 », « v2 or v3 », expression SPDX `GPL-2.0-only OR GPL-3.0-only` — jamais un identifiant `-only` ou `-or-later` unique ; un identifiant SPDX déprécié, sur une ligne SPDX comme dans le texte de la notice) ; `MIT` désigne le texte Expat (notice X11 ou seule mention « MIT License » → à analyser).

Licence importée — BROKEN : `grant = license` sans `origin = imported` ; `origin = imported` sans `status`, avec un grant autre que `license` (`cc` pour CC-BY-NC-SA-4.0), avec `status = confirmed` et un identifiant hors liste fermée ou déprécié, ou avec `status = to-analyse` et un identifiant renseigné ; `documents` sans `origin = imported`, qui n’est pas une liste de chemins, ou dont une entrée sort des noms et emplacements admis ou est déclarée deux fois. Avertissements (jamais bloquants pour le développement) : `LICENSE_DOCUMENT_UNAVAILABLE` (document déclaré absent, lien symbolique ou fichier non ordinaire : l’export attend) ; `LICENSE_TO_ANALYSE` (licence importée à analyser : la préparation de publication et l’export ne la tiennent pas pour réglée tant que le titulaire n’a pas enregistré l’identifiant exact) ; `IMPORTED_LICENSE_CONFLICT` (licence copyleft — MPL, GPL, LGPL, AGPL — avec source fermé, mode `protected` ou `invite-only`, ou accès payant ; CC BY-NC-SA avec mode `protected` ou `invite-only`, ou accès payant (clause NonCommercial) — une CC BY-NC-SA importée avec source fermé reste BROKEN par la règle mécanique CC ⇒ source public ; licence permissive dont la notice doit accompagner l’œuvre : points à analyser, jamais un blocage automatique ni une conclusion juridique) ; `IMPORTED_LICENSE_TERMS` (`terms_ref` déclaré : aucun document PWS ne s’applique). Pour une licence importée, `PROFILE_AXES_DIVERGENCE` ne compare que l’accès ; `ACCESS_PAID_WITHOUT_EULA` et `TERMS_URL_WITHOUT_TERMS` ne s’appliquent pas. Guard : la notice existante doit rester présente et cohérente avec `license.id` (lue dans l’en-tête et dans le bloc de commentaires initial qui suit `//@version`, jusqu’à la première ligne de code ; jamais déplacée) (absente, ou établissant une autre licence de la même famille → bloquant ; l’enregistrement se corrige avec le titulaire, jamais la notice ; une notice qui n’établit pas exactement l’identifiant enregistré — plusieurs versions ou choix entre versions, identifiant déprécié, formulation ambiguë → avertissement, jamais un blocage ni une acceptation silencieuse) ; ni en-tête CC, ni `All Rights Reserved`, ni ligne © du titulaire configuré exigés (les auteurs d’origine restent cités ; absence de toute ligne de copyright → avertissement) ; licence à analyser → modèle d’en-tête non vérifiable ; la règle ciblée des URL de licence reste celle de la décision D.

Cohérences mécaniques (BROKEN) : `CC-BY-NC-SA-4.0` ⇒ `grant = cc` et `source_visibility = public` ; `grant = cc` ⇒ licence CC ; `publication.mode = open` ⇒ `source_visibility = public` ; `library` ⇒ `source_visibility = public`, `mode` ∈ `open`, null et `access ≠ paid` (règle library open-source telle qu’enregistrée par le master à sa date de vérification, revérifiée avant publication ; une évolution officielle exige un amendement du contrat plutôt qu'un contournement local silencieux) ; `terms_url` doit être une URL https. Avertissements (jamais bloquants pour le développement, signalés avant une publication) : `access = paid` sans `grant = eula` ; `access = paid` avec `privacy ≠ public` ou `mode ≠ invite-only` ; `grant = eula` sans `terms_ref` (EULA en brouillon) ; `terms_url` sans `terms_ref` ; `state = published` avec `privacy` ou `mode` inconnu ; `state` inconnu (manifeste migré, à confirmer). Le scanner, `pine-new`, `pine-onboard`, le menu PWS, `project-doctor`, `license status`, le parcours `pine-license` et les self-tests appliquent les mêmes règles.

### 45.4bis Parcours guidé « Licence et conditions d'utilisation » (ratifié le 2026-11-07)

Entrée `Qualité / publication → Licence et conditions d'utilisation → choix du script` (skill `pine-license`), indépendante de `pine-release` : elle ne déclenche aucun contrôle de release, aucune revue, ni PineTS ni TradingView. Fonctions : consulter le profil, la licence, les références légales et les informations déjà enregistrées ; identifier ce qui manque ou reste à confirmer ; compléter ou modifier par un dialogue guidé en groupes cohérents (identification du produit, fournisseur et contact, bénéficiaire ou compte autorisé, modèle commercial et durée, renouvellement et résiliation, support, remboursements, droit applicable, autres conditions — seuls les champs réellement prévus par les modèles du profil) ; prévisualiser les documents ; enregistrer les informations et générer les documents sur choix explicite. Documents servis sans imposer une EULA à tous : FREE à source public → en-tête CC ; FREE à source fermé → autorisation gratuite d'utilisation ; PRIVATE → notice propriétaire et autorisation particulière facultative ; COMMERCIAL → EULA configurable. Données et commandes réutilisées : manifeste (`license confirm`, y compris `--terms-ref` / `--terms-url`), `release/eula-fields.json` (`license set-fields`, valeurs existantes conservées, suppression explicite), modèles (`license preview` / `license write`) — aucune seconde logique ni second stockage. Règles : rien d'inventé (année, identité juridique, juridiction, conditions commerciales, URL) ; titulaire des droits distinct de l'identité juridique du fournisseur ; profil de licence, visibilité du source et dimensions de publication jamais confondus ; informations inconnues laissées vides et reprises plus tard ; statut brouillon tant que des informations indispensables manquent ; récapitulatif puis confirmation groupée avant enregistrement ; consultation et prévisualisation sans écriture ; Retour ou Annuler abandonne les changements non enregistrés ; un document techniquement complet n'est jamais présenté comme un contrat juridiquement validé. Interface dans la langue configurée, documents en anglais.

Licence existante d’un script importé : aucun document de conditions PWS (ni en-tête de modèle, ni EULA, notice ou autorisation : `license write` et `license confirm --terms-ref` refusent) ; `overview` et `status` l’affichent « licence existante conservée » (`kept`) ou « à analyser » (`to-analyse`) avec la proposition lue dans l’en-tête ; `license confirm --license-id` enregistre l’identifiant exact confirmé par le titulaire (liste fermée ; déprécié, ambigu, hors liste ou licence de profil refusés), `--clear license_id` le remet à « à analyser » ; `license detect --source` donne la proposition d’un source non encore onboardé (lecture seule) ; elle lit l’en-tête (`header_lines`) et le bloc de commentaires initial qui suit `//@version` (`after_version_lines`), et liste les fichiers de nom juridique du dossier du produit (`legal_document_candidates`, proposition jamais enregistrée). `license confirm --license-document <chemin>` (répétable ; la déclaration liste tous les documents et remplace la précédente) enregistre `license.documents` après vérification de chaque fichier (nom et emplacement admis, fichier ordinaire du produit sans lien, texte UTF-8 ou mono-octet contrôlable, aucun nom exporté partagé) ; `--no-license-documents` enregistre qu’aucun document séparé n’accompagne le script ; `--clear license_documents` revient à « non déclaré » ; refusés pour une licence de profil. `overview` et `status` montrent les documents déclarés, les fichiers de nom juridique trouvés, ceux qui ne sont pas déclarés et ce qui fait attendre l’export ; les documents ne sont jamais réécrits, traduits ni remplacés par un modèle.

### 45.5 Interdictions

Ne jamais stocker ici :

- numéro de version produit ;
- détails algorithmiques ;
- secrets ;
- benchmark ;
- historique de décisions ;
- duplication de PRODUCT.md ;
- hash de validation courant.

---

## 46. `PRODUCT.md` — CONTRAT

### 46.1 But

Décrire le produit réellement construit.

### 46.2 Construction

Doit être écrit après analyse du vrai script ou conception du nouveau produit.

### 46.3 Contenu utile selon applicabilité

- problème trader résolu ;
- audience ;
- promesse fonctionnelle ;
- comportement principal ;
- workflow utilisateur ;
- éléments de différenciation ;
- philosophie de configuration ;
- frontières ;
- non-goals ;
- modèle de distribution ;
- aspects propriétaires à ne pas exposer pour un produit payant.

### 46.4 Provenance

Distinguer clairement :

```text
Confirmed by le titulaire
Observed in source
Pending confirmation
```

Utiliser uniquement les catégories réellement utiles.

### 46.5 Interdiction

Ne pas remplir des rubriques vides.

Ne pas présenter une inférence comme décision.

---

## 47. `ARCHITECTURE.md` DU SCRIPT — CONTRAT

### 47.1 Statut

Cartographie vivante dérivée du code.

### 47.2 Contenu selon applicabilité

- sections logiques ;
- types/enums/UDTs ;
- helpers centraux ;
- flux de calcul ;
- input dependency tree ;
- état persistant ;
- collections ;
- requests ;
- MTF flow ;
- signal pipeline ;
- rendering pipeline ;
- object lifecycle ;
- tables ;
- alert dependencies ;
- hotspots performance ;
- zones repaint-sensitive ;
- consumers des fonctions importantes ;
- invariants propres au script.

### 47.3 Noms plutôt que lignes

Préférer les noms de symboles, sections et relations.

Les numéros de lignes peuvent être ajoutés comme aide dérivée, mais ne doivent pas constituer l’identité d’un composant.

### 47.4 Mise à jour

Mettre à jour uniquement lorsqu’une modification rend la cartographie fausse.

Ne pas réécrire ce fichier mécaniquement après chaque micro-edit.

---

## 48. `CLAUDE.md` LOCAL DU SCRIPT — CONTRAT

### 48.1 Chargement

Conçu pour être chargé à la demande quand Claude travaille dans le product root.

### 48.2 Taille

Viser environ 30 à 80 lignes.

### 48.3 Contenu

Seulement l’information que Claude doit avoir en contexte lorsqu’il touche CE produit :

- identité ;
- source principal ;
- objectif court ;
- distribution ;
- invariants produit critiques ;
- zones à risque ;
- fichiers contextuels à consulter ;
- non-goals importants ;
- règles propres au produit non couvertes par le master.

### 48.4 Non-duplication

Ne pas résumer intégralement :

- PRODUCT.md ;
- ARCHITECTURE.md ;
- master standard.

Le fichier local est un routeur et un rappel des invariants critiques.

---

## 49. `DECISIONS.md` — CRÉATION À LA DEMANDE

### 49.1 Déclencheur

Créer seulement lorsqu’une première décision durable doit être persistée.

### 49.2 Entrées valides

Exemples :

- décision produit du titulaire ;
- décision architecturale durable ;
- comportement volontaire dont la conservation future importe ;
- dérogation explicite.

### 49.3 Entrées invalides

Ne pas enregistrer :

- micro-refactor ;
- renommage banal ;
- résumé de session ;
- simple observation du source ;
- découverte temporaire ;
- hypothèse non ratifiée.

### 49.4 Structure

Chaque décision contient au minimum :

```text
ID
Date
Status
Decision
Rationale
Scope
Supersedes (si applicable)
Evidence/context
```

### 49.5 Historique

Préférer append-only et `SUPERSEDED` plutôt qu’une réécriture silencieuse du passé.

---

## 50. RESEARCH PAR SCRIPT

### 50.1 Création

`research/` apparaît seulement lorsqu’une recherche réellement utile est persistée.

### 50.2 Run

Nom recommandé :

```text
runs/YYYY-MM-DDTHHMMSS-<topic>.md
```

### 50.3 Contenu

- question ;
- contexte ;
- date ;
- sources consultées ;
- faits ;
- benchmark ;
- limites ;
- conclusion ;
- implications ;
- sujets à revérifier.

### 50.4 `CURRENT.md`

Synthèse de navigation.

Il ne remplace pas les runs.

Inclure :

- sujets actuellement pertinents ;
- date de dernière vérification ;
- run source ;
- statut `CURRENT`, `STALE` ou `NON REVÉRIFIÉ`.

Statuts admis dans `CURRENT.md` : `CURRENT` (revérification datée), `STALE` (changement connu ou revérification due), `NON REVÉRIFIÉ` (recherche reconstituée ou ancienne, sans revérification depuis sa date initiale). Un run reconstitué ne reçoit jamais `CURRENT` sans revérification.

---

## 51. VALIDATION PAR SCRIPT

### 51.1 Dossier minimal

Après onboarding :

```text
validation/
└── current.json
```

Créer `runs/` et `evidence/` seulement lorsqu’ils servent. Dès qu'un run réel durable existe, utiliser la convention :

```text
validation/current.json
validation/runs/<run_id>.json
validation/evidence/<run_id>/<evidence-file>
```

`validation/` est exclusivement réservé aux observations, runs et preuves TradingView. Les artefacts PineTS appartiennent à `tests/behavioral/` ou à l’espace runtime éphémère approprié et ne doivent jamais être mélangés ici.

### 51.2 `current.json`

Représente le dernier état de validation connu, pas une vérité éternelle.

Exemple initial normatif :

```json
{
  "schema_version": 1,
  "status": "unverified",
  "last_run": null
}
```

`last_run` est soit `null`, soit un objet de référence déterministe contenant au minimum :

```json
{
  "run_id": "<collision-resistant-id>",
  "report": "runs/<run_id>.json",
  "source_sha256": "<sha256>",
  "completed_at": "<RFC-3339 UTC>"
}
```

`current.json` désigne le run courant reconnu ; il ne contient pas une copie concurrente de tout le rapport.

### 51.3 États de run

Supporter au minimum :

```text
unverified
in-progress
passed
failed
partial
```

Une seule taxonomie est persistée : les cinq valeurs ci-dessus. Les tokens historiques ou d'affichage tels que `PENDING`, `TV_VALIDATION_PENDING`, `PASSED` ou `TV_VALIDATED` ne sont pas des valeurs machine supplémentaires ; ils doivent être supprimés ou mappés explicitement vers cette taxonomie.

Mapping normatif lorsqu'un ancien label ou un affichage humain doit être interprété :

| Label historique / affichage | Valeur machine |
| --- | --- |
| `PENDING`, `TV_VALIDATION_PENDING` | `unverified` ou `in-progress` selon l'existence d'un run commencé |
| `PASSED`, claim humain `TV_VALIDATED` | `passed`, uniquement si §51.5 est satisfait |
| `STALE` | dérivé `stale`, jamais persisté |

Le statut effectif devient `stale` lorsque le SHA-256 du source courant diffère du `source_sha256` du run courant reconnu. La comparaison porte sur le source déclaré par `SCRIPT.json`. Un run enregistré sur un autre SHA reste historique et ne valide pas le source courant.

`stale` est dérivé et n'est pas persisté comme sixième statut, afin de ne pas muter un fichier à chaque edit.

Si `current.json` référence un rapport absent, invalide ou dont l'identité ne correspond pas, définir `validation_integrity_status = BROKEN`, ne jamais considérer la validation comme `passed` et ne pas inventer une nouvelle valeur persistée. `validation_effective_status` reste alors nul/indisponible et un diagnostic actionnable explique la validation cassée/incomplète.

### 51.4 Run report

Chaque run réel conserve au minimum :

- `run_id` collision-resistant ;
- timestamps RFC 3339 UTC ;
- statut persistable parmi `in-progress`, `passed`, `failed` ou `partial` ;
- source ;
- SHA-256 ;
- commit Git ou null ;
- working tree clean/dirty ;
- requested mode ;
- effective mode ;
- fallback reason ;
- matrice appliquée ;
- résultats ; pour un rapport de version 2, chaque contrôle de la matrice porte un identifiant unique et chaque contrôle applicable un verdict parmi `passed`, `failed`, `not-run` ou `indeterminate`, avec l’observation, l’auteur et l’horodatage ; `n-a` est réservé aux contrôles explicitement non applicables. Amendement du 2026-11-06 : pour un verdict `not-run` ou `n-a`, aucune observation n’a eu lieu, donc l’auteur (`observed_by`) peut être nul — l’observation consigne alors pourquoi le contrôle n’a pas été exécuté, et l’horodatage reste requis ; on n’invente jamais un observateur, une observation ni une compilation pour satisfaire le schéma. Un rapport existant qui violait le contrat n’est jamais réécrit : un rectificatif est un nouveau fichier à côté de l’original, qui cite son empreinte et décrit chaque correction ;
- anomalies ;
- preuves, chacune avec chemin relatif sous `evidence/<run_id>/`, type et SHA-256 ;
- conclusion.

Le rapport référence les preuves ; une capture n'est pas obligatoire lorsqu'elle n'apporte aucune preuve utile.

Le rapport de run est écrit de manière immuable avant la mise à jour de `current.json`. Le contrôleur :

1. mémorise l'identité ou le hash du `current.json` lu au démarrage du run ;
2. écrit et vérifie le rapport complet ;
3. relit `current.json` avant promotion ;
4. refuse la promotion si le pointeur a changé de manière concurrente ou si l'ordre des runs ne peut pas être établi ;
5. empêche un run dont `completed_at` est antérieur au run courant reconnu de le remplacer ;
6. effectue le remplacement final de `current.json` atomiquement.

Une égalité ou anomalie d'horloge produit un conflit actionnable plutôt qu'un choix silencieux.

Un run de compilation minimale suit en outre les règles d'enregistrement et de promotion de §30.5, appliquées après ces protections.

### 51.5 `passed`

`passed` signifie :

> Tous les contrôles TradingView obligatoires applicables à ce run ont réellement réussi sur le source identifié par ce hash.

Les verdicts sont examinés avant la couverture. Un contrôle applicable `failed` impose le statut `failed`, même si d’autres contrôles n’ont pas de résultat ; il n’est jamais ramené à `in-progress` ni à `partial`. En l’absence de `failed`, un contrôle applicable `not-run`, `indeterminate` ou sans résultat interdit `passed` ; un contrôle sans résultat, ou l’absence de tout `passed`, n’admet que `in-progress`. `partial` exige au moins un `passed` et au moins un `not-run` ou `indeterminate`, tous les contrôles applicables ayant un résultat. Un contrôle sans résultat est « non renseigné » : rien n’est affirmé sur son exécution. Aucun run sans contrôle applicable ne peut être `passed`. Les rapports enregistrés sous une version antérieure du schéma restent lisibles et recevables sur leur SHA sans réécriture ; un nouveau rapport utilise la version courante. Cette compatibilité de lecture n’établit pas la date de création d’un fichier.

---

## 52. DÉTECTION AUTOMATIQUE DES `.pine` ORPHELINS — RATIFIÉE

Cette fonction est obligatoire.

### 52.1 À chaque session

`SessionStart` scanne `scripts/**`.

### 52.2 Doctor

`project-doctor` effectue la même détection indépendamment.

### 52.3 Comportement Claude

Lorsqu’un `.pine` est `UNREGISTERED` :

- le signaler ;
- utiliser automatiquement `pine-onboard` avant toute modification fonctionnelle substantielle ;
- demander au titulaire seulement ce qui ne peut pas être déterminé proprement.

### 52.4 Silence interdit

Un `.pine` orphelin ne doit jamais être ignoré silencieusement.

### 52.5 Onboarding non destructif

Le processus d’onboarding n’altère pas le source existant.

Toute correction du code constitue une tâche distincte.

Lorsqu’un source est importé pendant la session, l’onboarding enregistre l’import avant toute modification : chemin, SHA-256 et état du guard à cet instant, conservés dans l’état de session. Le déplacement du fichier inchangé déplace l’enregistrement. Un enregistrement n’est jamais renouvelé : une fois le contenu modifié, l’import ne peut plus être enregistré de nouveau. L’enregistrement est déclaratif ; il distingue un import d’une création et ne prouve pas l’origine du fichier.

---

## 53. MISE À JOUR DU CONTEXTE APRÈS UNE MODIFICATION

Ne pas régénérer tout le contexte par réflexe.

Après un changement :

- `PRODUCT.md` seulement si le produit a changé ;
- `ARCHITECTURE.md` si la cartographie est devenue fausse ;
- `DECISIONS.md` si une vraie décision durable a été prise ;
- `research/` si une recherche durable a été faite ;
- `validation` via un vrai run ;
- docs/release seulement si concernés.

Le contexte doit rester utile, pas devenir un journal de chaque edit.

Chaque produit désigne dans son `CLAUDE.md` local un artefact de suivi ; celui-ci consigne, par modification cohérente, la classe de tâche, la couverture de relecture lue, la conclusion de benchmark et la provenance des rapports d’agents utilisés. Sa forme est libre ; il ne remplace ni `DECISIONS.md` ni `validation/`.

---

## 54. REDONDANCE — GATE OBLIGATOIRE

Après bootstrap, puis après toute restructuration du workspace, effectuer une passe de non-redondance.

### 54.1 Question pour chaque règle répétée

La répétition possède-t-elle une fonction distincte ?

Exemple acceptable :

```text
master
→ convention normative

rule
→ routage contextuel concis

guard
→ enforcement mécanique
```

Exemple inutile :

```text
master
→ 20 lignes

CLAUDE.md
→ mêmes 20 lignes

skill
→ mêmes 20 lignes

agent
→ mêmes 20 lignes
```

### 54.2 Référencer plutôt que recopier

Les workflows doivent renvoyer au standard ou à la traceability lorsque le détail n’a pas besoin d’être répété.

### 54.3 Workflows

Une certaine répétition d’étapes dans un workflow est acceptable si elle rend la séquence exécutable.

La duplication de doctrine ne l’est pas.

---

## 55. IDÉMPOTENCE DU BOOTSTRAP

La spécification doit pouvoir être réexécutée sans détruire un workspace mature.

### 55.1 Avant toute réexécution

Détecter :

- fichiers existants ;
- modifications locales ;
- version du standard ;
- architecture actuelle ;
- contextes script ;
- hooks ;
- skills ;
- agents ;
- settings locaux.

### 55.2 Interdictions

Ne pas :

- écraser `DECISIONS.md` ;
- réinitialiser `validation/` ;
- supprimer les research runs ;
- remplacer un `PRODUCT.md` par un generic ;
- réécrire les skills sans diff/revue ;
- écraser `settings.local.json` ;
- supprimer les approvals locaux.

### 55.3 Migration

Si l’architecture doit évoluer, produire d’abord :

- diff attendu ;
- risques ;
- plan de migration ;
- compatibilité ;
- fichiers affectés.

Une migration importante nécessite validation du titulaire.

---

## 56. ABSENCE DE VERSION PRODUIT HORS SOURCE

Le workspace respecte la Convention Personnelle :

> La version produit apparaît uniquement dans le header du code source, sauf dérogation explicite.

Par conséquent, ne pas inclure la version produit dans :

- `SCRIPT.json` ;
- `PRODUCT.md` ;
- `ARCHITECTURE.md` ;
- `CLAUDE.md` local ;
- research ;
- validation state ;
- tutoriel ;
- changelog ;
- release notes ;
- description ;
- fichiers d’architecture workspace.

Le hash du source et le commit Git suffisent pour identifier techniquement une validation.

---

## 57. NOUVEAUX DOSSIERS À LA DEMANDE

### 57.1 `docs/`

Créer lorsqu’un livrable documentaire réel existe.

### 57.2 `release/`

Créer lorsqu’une vraie release nécessite des artefacts de préparation.

### 57.3 `research/`

Créer lorsqu’une recherche mérite persistance.

### 57.4 `validation/evidence/`

Créer lorsqu’un fichier de preuve existe.

`scripts/<slug>/tests/behavioral/` est également créé uniquement lorsqu’un vrai contrat de test comportemental, une fixture spécifique ou une baseline acceptée existe pour ce produit. Ne pas créer ce dossier pendant l’onboarding seul ou pour matérialiser l’arborescence.

### 57.5 Dynamic workflows

Ne pas créer `.claude/workflows/` au bootstrap initial.

L’ajouter seulement lorsqu’un besoin multi-script récurrent est démontré.

Exemple futur légitime :

> Une évolution Pine V6 est publiée ; analyser tous les scripts le titulaire et identifier lesquels sont affectés.

---

## 58. CAPACITÉS VOLONTAIREMENT EXCLUES DU SOCLE INITIAL

Ne pas installer par défaut :

- GitHub comme dépendance du workspace (remote, CI) — le parcours d’export explicite de §43.5 n’en est pas une ;
- GitHub Actions ;
- tout MCP configuré par le projet ou serveur MCP custom ;
- Agent Teams ;
- dynamic workflows prédéfinis ;
- CI distante ;
- base SQLite ;
- registry centrale ;
- serveur local ;
- dashboard web ;
- plugin custom Claude ;
- automatisation de publication TradingView ;
- agent d’édition parallèle ;
- mémoire persistante des reviewers ;
- gros moteur de règles sémantiques ;
- copie locale de la documentation TradingView entière.

Toute nouvelle couche doit répondre à un besoin réel démontré.

L’introduction du thin adapter PineTS ne constitue une exception à aucune de ces exclusions.

En particulier, elle n’autorise pas la création d’un serveur local, MCP, base de données, dashboard, CI comportementale distante ou plateforme parallèle autour de PineTS.

L'intégration native Claude in Chrome peut exposer aujourd'hui un transport interne nommé `claude-in-chrome` MCP. Ce transport fourni par Claude Code lui-même est autorisé uniquement comme détail d'implémentation de la primitive native utilisée par `chrome-experimental` :

- PWS ne l'installe pas comme dépendance projet ;
- PWS ne crée pas de `.mcp.json` pour lui ;
- cette exception n'autorise ni `tradingview-mcp`, ni un MCP tiers, ni un bridge CDP externe ;
- tout MCP projet, serveur custom, MCP PineTS ou MCP dédié au menu reste exclu sans ratification explicite.

---

## 59. CRITÈRE POUR AJOUTER UNE NOUVELLE COUCHE

Avant d’ajouter un outil, agent, skill, hook ou stockage :

1. Quel manque concret corrige-t-il ?
2. Une primitive native actuelle couvre-t-elle déjà le besoin ?
3. Le problème est-il réel ou hypothétique ?
4. Quel est le coût contextuel ?
5. Quel est le coût de maintenance ?
6. Crée-t-il une deuxième source de vérité ?
7. Peut-il devenir stale ?
8. Quel incident empêche-t-il ?
9. Peut-il être ajouté plus tard sans dette importante ?

Si le besoin n’est pas démontré, ne pas ajouter la couche.

### 59.1 Application ratifiée — PineTS

La couche `LOCAL BEHAVIORAL EXECUTION` répond au gate de cette section parce qu’elle couvre un manque concret non couvert par les primitives existantes :

```text
checks déterministes
→ aucune exécution réelle du Pine
→ validation TradingView
```

Le manque couvert est l’absence d’un runtime local permettant d’observer programmatiquement le comportement du source avant TradingView et, lorsque les preuves le permettent, de faire respecter un contrat comportemental local reproductible.

La frontière d’autorité est la suivante :

- la documentation officielle Pine Script reste l’autorité sur la syntaxe, les APIs et la sémantique officielle du langage ;
- TradingView reste l’autorité empirique sur le comportement propre à sa plateforme et sur toute étape `tv-validate` ;
- PineTS peut être une autorité d’exécution locale pour une conclusion strictement bornée lorsque toutes les capabilities nécessaires sont effectivement gating et que le source, le dataset, la configuration et l’environnement exacts sont identifiés ;
- une conclusion locale PineTS, même bloquante, ne devient jamais `TV_VALIDATED` et ne prouve jamais une parité générale avec TradingView.

Cette couche est admise uniquement sous les contraintes suivantes :

- son utilisation est capability-gated ;
- les capabilities sont qualifiées avec une granularité suffisante, sans condamner ou promouvoir une famille entière par principe ;
- `capability_status` et `calibration_status` restent deux dimensions distinctes ;
- toute capability effectivement gating possède une calibration indépendante `CURRENT` pour le triplet exact `pinets_version + executor_fingerprint + normalization_schema` ;
- les capabilities effectivement utilisées par chaque run sont enregistrées ;
- les datasets sont reproductibles, hashés et accompagnés d’une provenance suffisante ;
- les snapshots indépendants sont admis lorsque leurs conditions d’usage le permettent ;
- les matrices locales et parameter sweeps restent bornés, explicites et traçables, sans optimiseur générique ni déclenchement automatique par hook ;
- les licences et conditions d’usage de PineTS, des sources de données et de TradingView sont évaluées selon la ressource réellement utilisée ;
- la version PineTS est exactement pinée ;
- aucun auto-upgrade ;
- aucune correction du Pine uniquement destinée à satisfaire PineTS ;
- aucun hook de base ne lance PineTS ;
- aucune architecture serveur, MCP, base de données ou dashboard n’est créée ;
- les artefacts comportementaux restent séparés des preuves TradingView ;
- l’intégration reste un thin adapter et une skill, pas une seconde plateforme.

Si ces contraintes cessent d’être vraies, l’intégration doit être réévaluée selon le gate principal de §59.

### 59.2 Application ratifiée — menu contextuel PWS

La skill `pws` répond au gate de cette section parce qu’elle couvre un besoin UX explicite : permettre au titulaire de choisir un workflow et ses décisions structurées courtes dans une session Claude Code sans mémoriser les commandes directes ni transformer la conversation en suite de prompts répétitifs.

Le besoin est couvert par une primitive native actuelle, `AskUserQuestion`. L’architecture retenue exploite donc cette primitive au lieu de créer une application, un TUI externe ou une nouvelle plateforme.

Cette skill est admise uniquement sous les contraintes suivantes :

- une seule skill de façade `pws` ;
- aucune logique métier dupliquée ;
- routage vers les skills existantes ;
- état dérivé du tooling déterministe déjà présent ;
- aucune base de données ou registry supplémentaire ;
- aucun hook interactif fragile ;
- aucun serveur, MCP, plugin custom ou dashboard ;
- aucune persistance propre au menu hors décisions déjà prévues par les artefacts canoniques ;
- possibilité de contourner totalement le menu par les commandes directes ou la conversation ;
- fallback conversationnel si la primitive native n’est pas disponible.

Son coût contextuel doit rester faible : description courte toujours visible, corps de skill chargé seulement lorsqu’il est invoqué selon le mécanisme courant des skills Claude Code.

Si le menu commence à acquérir sa propre logique, son propre stockage ou un runtime d’interface distinct, il doit être réévalué selon le gate principal de §59.

---

## 60. BOOTSTRAP — PHASE D’IMPLÉMENTATION

Après discovery, extraction, design gate et critique indépendante :

### 60.1 Construire d’abord les autorités

- `standards/PINE_SCRIPT_V6_STANDARD.md`
- déplacement de cette bootstrap spec dans `docs/architecture/BOOTSTRAP_SPEC.md`

Appliquer le contrat de cycle de vie et de hashes de §5 ; ne pas conserver deux autorités normatives ambiguës.

### 60.2 Construire l’index et la traceability

- parser les headings réels ;
- générer INDEX ;
- créer TRACEABILITY après analyse complète.

### 60.3 Construire l’architecture opérationnelle

- `CLAUDE.md`
- rules
- skills, y compris la skill `pws` servant de menu contextuel natif
- agents
- settings
- Git files
- tooling
- tests
- skill `pine-local-test`
- thin adapter `tools/pine_exec`
- dépendance PineTS exactement pinée + lockfile
- calibration initiale des capabilities, sans obligation de promouvoir une capability `GATING`
- protocole d’apprentissage opérationnel contrôlé de `chrome-experimental` dans `tv-validate/CHROME_EXPERIMENTAL.md`, sans apprentissage fictif
- architecture docs

Ne pas créer `scripts/<slug>/tests/behavioral/` pendant le bootstrap s’il n’existe encore aucun vrai produit nécessitant un contrat comportemental.

Les dossiers comportementaux par produit restent à la demande.

### 60.4 Ne pas créer de faux produits

Le dossier `scripts/` peut exister vide localement.

Ne pas créer de `.gitkeep`.

Ne pas créer de script exemple.

### 60.5 Mode TV

Créer les settings locaux avec `manual`.

---

## 61. SELF-VALIDATION DU BOOTSTRAP

Avant de déclarer le workspace construit :

### 61.1 Syntaxe

Vérifier :

- JSON parse ;
- YAML frontmatter ;
- Markdown structure ;
- Python compile ;
- imports locaux.
- UTF-8 valide, fins de ligne LF et newline terminal pour les documents canoniques ;
- headings principaux continus et code fences équilibrés ;
- tous les blocs JSON parsables.

### 61.2 Tooling

Exécuter tous les tests.

### 61.3 Standard

Vérifier :

- SHA ;
- INDEX ;
- TRACEABILITY ;
- aucune modification involontaire du master.

### 61.4 Claude Code

Vérifier avec les commandes actuelles appropriées :

- settings chargés ;
- `CLAUDE.md` chargé ;
- rules détectées ;
- skills détectées ;
- agents détectés ;
- hooks détectés ;
- `/pws`, `/tv-mode` et les autres skills critiques résolus vers les skills projet attendues sans collision silencieuse ;
- transport Chrome natif distingué de tout MCP projet et absence de `.mcp.json` créé pour ce transport.

Utiliser notamment les diagnostics officiels disponibles comme `/context`, `/status`, `/doctor` ou leurs équivalents actuels.

### 61.5 Hooks

Tester les scripts de hook directement avec des inputs JSON de fixture.

Puis effectuer un vrai redémarrage de session si nécessaire pour confirmer `SessionStart`.

Tester le Stop hook sur une fixture contrôlée.

### 61.6 Orphan detection

Créer temporairement dans un espace de test un faux arbre minimal comportant un `.pine` orphelin.

Vérifier qu’il est détecté.

Ne pas laisser ce faux script dans `/scripts`.

### 61.7 Validation stale

Tester :

1. un run lié à hash A ;
2. source modifié vers hash B ;
3. `validation-status` doit produire `STALE`.

Tester également :

- `current.json` pointant vers un rapport absent ou invalide ne produit jamais `passed` ;
- chaque preuve référencée est vérifiée par son SHA-256 ;
- un run plus ancien ne peut pas remplacer atomiquement le run courant plus récent.

### 61.8 TV mode

Tester :

```text
manual
→ chrome-experimental
→ manual
```

sans perdre les autres clés du local settings.

Tester une modification concurrente simulée détectable (survenant avant la relecture pré-écriture) et vérifier que le contrôleur refuse l'écrasement ; documenter la fenêtre non détectable de §19.3 comme limitation déclarée. Confirmer que la route explicite `/pws → Changer le mode TV` appelle le contrôleur partagé sans invoquer `Skill(tv-mode)`, tandis que `/tv-mode` reste user-only.

Vérifier également que `.claude/skills/tv-validate/CHROME_EXPERIMENTAL.md` :

- décrit le protocole d’apprentissage opérationnel contrôlé de §31.9 ;
- distingue connaissance opérationnelle, observation courante et preuve de validation ;
- prévoit la détection d’obsolescence et la révision prudente ;
- n’invente aucun landmark, workflow ou failure mode présenté comme réellement observé pendant le bootstrap s’il ne l’a pas été.

### 61.9 Menu contextuel PWS

Vérifier dans une vraie session interactive compatible :

1. que `.claude/skills/pws/SKILL.md` est détectée et invocable par `/pws` ;
2. que la skill utilise `AskUserQuestion` lorsque cette primitive native est disponible ;
3. que chaque question respecte les limites courantes de la primitive et que les arborescences ne surchargent pas un écran unique ;
4. que le menu se comporte correctement dans au moins quatre états : workspace sans produit, produits enregistrés, présence d’un `.pine` `UNREGISTERED`, état mixte avec validation `STALE` ;
5. que `Retour` et `Annuler` ne produisent aucun effet de bord ;
6. que `Nouveau script → Indicator → COMMERCIAL` transmet les valeurs canoniques attendues (profil et axes) à `pine-new` sans créer de produit avant la confirmation finale ;
7. que `Nouveau script → Library` dérive FREE à source public, ne propose aucun autre profil et que le scanner rejette toute autre combinaison si elle est injectée autrement ;
7a. que le parcours « Travailler sur un script » propose l’action avant le script, affiche l’identité explicite du script unique, et que le premier niveau ne présente jamais un produit comme seul périmètre ;
8. qu’un `.pine` `UNREGISTERED` route vers `pine-onboard` ;
9. que les actions de développement, documentation/tutoriel, recherche, revue, audit, test local, validation TradingView, licence et conditions d'utilisation, publication, export GitHub, diagnostic, outils et archives routent vers les skills existantes au lieu de dupliquer leur logique, que la structure vient de `menu --json` (libellés dans la langue configurée) et que le changement de mode suit le contrôleur partagé ;
10. que le menu peut être réouvert avec `/pws` pendant une session ;
11. qu’un resume, un compact ou un clear n’impose pas la réouverture du menu ;
12. que `SessionStart` ne tente pas de manipuler un TTY ou de simuler des touches ;
13. qu’un fallback conversationnel simple existe si `AskUserQuestion` n’est pas disponible sur la surface courante.

La self-validation doit également confirmer la forme CLI actuelle de démarrage interactif avec prompt initial si elle est documentée dans `OPERATIONS.md`.

### 61.10 PineTS

Si la couche PineTS a été construite, vérifier :

1. que PineTS est piné sur une version exacte ;
2. qu’aucun range flottant n’est utilisé ;
3. que le lockfile correspond à la dépendance déclarée ;
4. que la version et l'artefact installés proviennent du registry npm et que leurs métadonnées, intégrité, licence et lockfile sont enregistrés sans déduction depuis `main` seul ;
5. que `license_basis` décrit la base réellement utilisée et ne prétend jamais à une licence commerciale sans preuve locale applicable ;
6. que l’`executor_fingerprint` couvre les artefacts d’exécution et de normalisation réellement influents, `package.json`, la version Node exacte et les faits d'environnement pertinents sans secrets ;
7. que le runner peut exécuter un cas minimal déterministe ;
8. que la sortie normalisée est reproductible ;
9. que le manifest de calibration correspond au triplet courant `pinets_version + executor_fingerprint + normalization_schema` ;
10. qu'une modification simulée de cas, input, attendu, référence ou preuve rend stale uniquement les calibrations concernées et qu'aucun TTL arbitraire n'est appliqué ;
11. qu’une capability non encore qualifiée n’est ni promue `GATING` ni déclarée `UNSUPPORTED` sans preuve, et peut rester provisoirement `EXPERIMENTAL` avec `calibration_status = MISSING` ;
12. que deux sous-capabilities d’une même famille peuvent recevoir des statuts différents lorsque les calibrations le justifient, sans classification globale forcée de la famille ;
13. qu’un changement simulé de `pinets_version`, d’`executor_fingerprint` ou de `normalization_schema` rend correctement `calibration_status = STALE` sans réécrire automatiquement `capability_status` ;
14. que `effective_gating` est faux pour toute capability dont `capability_status != GATING` ou `calibration_status != CURRENT` ;
15. que les `capabilities_used` d’un run empêchent une conclusion gating lorsque celle-ci dépend matériellement d’une capability non effectivement gating ;
16. appliquer le test conditionnel suivant :
    - si au moins une capability a légitimement obtenu `GATING + CURRENT`, vérifier qu'une violation volontaire d'un contrat reposant uniquement sur des capabilities effectivement gating bloque le cycle local sans produire ni modifier aucun statut TradingView ;
    - sinon, vérifier le chemin non-gating et confirmer qu'aucune capability n'est promue artificiellement pour satisfaire la self-validation ;
17. que l'absence totale de capability `GATING` est acceptée comme résultat valide du bootstrap et déclarée explicitement ;
18. que `PINETS_EXECUTION_PASS` et `PINETS_REGRESSION_CHANGED` peuvent coexister sans être assimilés à un échec d’exécution ;
19. que `PINETS_UNSUPPORTED`, `PINETS_EXPERIMENTAL` et `PINETS_INCONCLUSIVE` ne sont pas transformés en échec du source ;
20. qu’un dataset synthétique déterministe possède un `dataset_descriptor` reproductible et un `dataset_sha256` stable ;
21. qu’un fixture de snapshot OHLCV importé peut être consommé avec provenance explicite et hash stable sans nécessiter de fournisseur réseau ;
22. qu’une baseline durable possède son dataset descriptor, ses hashes et sa preuve ou justification d'acceptation vérifiables ;
23. qu’une petite matrice explicite de configurations produit un manifeste déterministe et conserve l’identité de chaque run élémentaire ;
24. qu’aucun hook du socle ne lance PineTS ni une matrice de datasets, paramètres ou stability probes ;
25. qu’aucune exécution PineTS n’écrit sous `validation/` ;
26. que les tests PineTS automatisables sont persistés durablement sous `tools/tests/` ou une factorisation équivalente justifiée et sont exécutés par le framework de test déjà retenu ;
27. que la documentation opérationnelle distingue les conditions de PineTS, celles d’une éventuelle source de données externe et celles de TradingView selon l’usage réel.

Le bootstrap ne doit jamais être obligé de produire une capability `GATING`. Si une ou plusieurs capabilities sont classées `GATING`, chacune de celles utilisées comme gate doit posséder une calibration indépendante `CURRENT` conforme au contrat. L'absence de gate locale initiale est un résultat honnête et valide lorsque les preuves ne suffisent pas.

### 61.11 Frontières physiques et contrats machine

Vérifier explicitement :

- workspace dont le chemin contient des espaces ;
- détection et arrêt sur repository parent englobant ;
- fonctionnement identique en l’absence de tout projet sibling et absence de scan ou mutation d’un sibling arbitrairement nommé ;
- refus des traversals et symlinks sortants ;
- unicité case-insensitive des IDs/slugs ;
- schéma `SCRIPT.json` v1 et matrice type/distribution ;
- séparation des axes `product_structure_status`, `source_registration_status` et validation ;
- `.claude/worktrees/` ignoré ;
- pre-write gate Chrome avec un cas ambigu qui produit `NO WRITE` ;
- aucune entrée ou artefact temporaire de test laissé sous `scripts/`.

---

## 62. BOOTSTRAP REPORT

Créer :

```text
docs/architecture/BOOTSTRAP_REPORT.md
```

### 62.1 Contenu

Inclure :

- date ;
- OS ;
- version Claude Code ;
- version Git ;
- runtime local retenu ;
- état Node.js ;
- version PineTS exactement retenue ;
- provenance registry/tarball, intégrité et métadonnées du paquet PineTS installé ;
- `license_basis` réellement utilisé et éventuelle référence non secrète applicable ;
- `executor_fingerprint` courant ;
- identité du schéma de normalisation ;
- état de calibration PineTS ;
- déclaration explicite lorsque zéro capability est `GATING`, sans présenter ce résultat comme un échec du bootstrap ;
- capabilities initialement `GATING`, `EXPERIMENTAL` ou `UNSUPPORTED`, granularité retenue et fraîcheur de leur calibration ;
- types de datasets locaux supportés, contrat de provenance et éventuelle source externe réellement configurée ;
- support ou limites des matrices locales explicites ;
- licence PineTS actuelle vérifiée et périmètre d’usage retenu ;
- conditions d’usage applicables à toute source de données externe réellement configurée et à toute interaction TradingView concernée ;
- hash master ;
- hash de la bootstrap spec ;
- mappings des deux fichiers d'entrée vers leurs chemins canoniques avec hashes avant/après ;
- documentation officielle vérifiée ;
- primitives Claude Code disponibles ;
- capacités non disponibles ;
- état Chrome ;
- état Git ;
- remotes ;
- architecture créée ;
- justification spécifique de chaque fichier ;
- fichiers volontairement non créés ;
- permissions ;
- hooks ;
- résultats des tests ;
- résultat doctor ;
- résultat orphan detection ;
- mode TradingView ;
- état et self-validation du menu contextuel PWS ;
- limitations ;
- points nécessitant encore le titulaire.

### 62.2 Qualité

Le rapport doit permettre de vérifier que Claude a réellement conçu l’environnement.

Il ne doit pas simplement lister :

```text
Created CLAUDE.md
Created skills
Created agents
```

Chaque choix significatif doit avoir une justification.

---

## 63. COMMIT INITIAL

À la fin du bootstrap :

- afficher au minimum `git status --short` ;
- afficher le diff des fichiers déjà suivis lorsqu'il existe ;
- inventorier les fichiers non suivis sans les stage uniquement pour fabriquer un diff ;
- afficher les totaux utiles ;
- afficher les remotes ;
- indiquer explicitement si le repository est unborn ou identifier le commit courant ;
- afficher un résumé du diff et des fichiers créés ;
- proposer un commit initial ;
- ne pas le créer sans approbation explicite du titulaire.

Aucun push.

---

## 64. CRITÈRES DE TERMINAISON DU BOOTSTRAP

Le bootstrap n’est terminé que si toutes les affirmations suivantes sont vraies.

### 64.1 Autorités

- le master est canonique et intact ;
- la bootstrap spec est conservée ;
- INDEX correspond au master ;
- TRACEABILITY correspond au master.

### 64.2 Contexte

- root `CLAUDE.md` est concis ;
- aucune copie du master n’y est importée ;
- aucune configuration ou procédure ne requiert l’existence, le nom, le chemin ou l’état d’un autre projet externe ;
- rules sont path-scoped ;
- skills ne sont pas gonflées de contenu de référence inutile ;
- agents ont des responsabilités distinctes.

### 64.3 Tooling

- tooling fonctionne ;
- tests passent ;
- doctor fonctionne ;
- orphan detection fonctionne ;
- stale validation fonctionne ;
- menu contextuel PWS détecté, routé et self-validé ;
- thin adapter PineTS fonctionnel ou limitation explicitement déclarée ;
- version PineTS non flottante ;
- `executor_fingerprint` déterministe ;
- calibration cohérente avec `pinets_version`, `executor_fingerprint` et `normalization_schema` courants ;
- aucune capability utilisée comme effectivement gating sans `capability_status = GATING` et `calibration_status = CURRENT` ;
- zéro capability `GATING` est accepté lorsque les preuves initiales ne suffisent pas ;
- aucune famille large de capabilities promue ou condamnée par principe lorsque des sous-capabilities doivent être distinguées ;
- datasets locaux hashés et provenance reproductible ;
- matrices explicites bornées et traçables lorsqu’elles sont supportées, sans optimiseur générique ni hook automatique ;
- lorsqu'une gate PineTS locale existe légitimement, elle peut bloquer localement sans jamais écrire ni satisfaire un statut TradingView ;
- séparation physique et sémantique entre `tests/behavioral/` et `validation/`.

### 64.4 Git

- repo local opérationnel ;
- aucun remote créé par le bootstrap ;
- `worktree.baseRef` local adapté ;
- `.claude/worktrees/` ignoré et limitation pré-premier-commit documentée ;
- aucun push possible implicitement selon la politique retenue.

### 64.5 TradingView

- mode initial `manual` ;
- switch user-only opérationnel ;
- Chrome experimental clairement séparé ;
- fallback documenté ;
- publication hors scope.

### 64.6 Redondance

- aucun artefact décoratif ;
- aucun placeholder produit ;
- aucune registry centrale ;
- aucune duplication massive du standard ;
- responsabilités non concurrentes.

### 64.7 Honnêteté

- aucune validation TradingView inventée ;
- aucun résultat PineTS présenté comme validation TradingView ;
- aucune capacité Claude Code inventée ;
- aucune décision le titulaire inventée ;
- aucune recherche prétendument effectuée sans source réelle.

---

## 65. CRITÈRES D’ONBOARDING COMPLET D’UN SCRIPT EXISTANT

Un script existant est prêt à être développé dans le workspace lorsque :

- le source a été entièrement lu ;
- le product root est stable ;
- `SCRIPT.json` est valide ;
- le profil de licence et ses axes sont résolus (schéma 2) ;
- `PRODUCT.md` est spécifique ;
- `ARCHITECTURE.md` est spécifique ;
- le `CLAUDE.md` local est spécifique et concis ;
- validation state existe ;
- les questions réellement indéterminables ont été posées au titulaire ;
- aucune décision n’a été inventée ;
- aucun fichier générique n’a été créé ;
- le source n’a pas été modifié pendant l’onboarding ;
- doctor classe le produit `REGISTERED`.

---

## 66. CRITÈRES DE CRÉATION CORRECTE D’UN NOUVEAU SCRIPT

Un nouveau produit a correctement traversé `pine-new` lorsque :

- l’objectif est clair ;
- l’audience est claire ;
- le `script_kind` est clair ;
- le profil de licence et ses axes sont clairs ;
- les cohérences de §45.4 sont respectées, notamment `library → FREE à source public` ;
- la recherche Pine actuelle a été faite ;
- le benchmark open-source / Editors’ Picks pertinent a été fait ;
- la différenciation est définie ;
- la cible de dépassement qualitatif est définie ;
- les décisions produit nécessaires ont été prises ;
- l’architecture est conçue avant le code ;
- le contexte spécifique existe ;
- le source a été créé selon le master ;
- le code n’est pas une adaptation déguisée d’une référence ;
- les checks locaux passent ;
- les tests comportementaux PineTS applicables ont été exécutés lorsque la couche possède des capabilities suffisantes ;
- les `capabilities_used` et leur fraîcheur de calibration bornent correctement toute conclusion gating ;
- tout résultat PineTS réellement gating a été qualifié et peut bloquer le cycle local uniquement dans les limites exactes de son contrat ;
- tout statut PineTS non gating ou limitation applicable est déclaré honnêtement plutôt que transformé en échec artificiel ;
- aucun claim local PineTS n’est élargi en claim de parité TradingView sans preuve TradingView correspondante ;
- la revue indépendante est faite ;
- la validation TradingView est faite avant déclaration finale.

---

## 67. EXEMPLE DE FLUX — SCRIPT EXISTANT AJOUTÉ PAR RICK

```text
le titulaire
│
├── crée scripts/zigzag-orderblock/
│
└── dépose ZigZag OrderBlock Retracement.pine
        │
        ▼
nouvelle session Claude Code
        │
        ▼
SessionStart
        │
        ├── scan scripts/**
        └── UNREGISTERED détecté
                │
                ▼
pine-onboard
                │
                ├── lecture intégrale
                ├── cartographie
                ├── analyse master applicable
                ├── résolution distribution
                ├── PRODUCT.md spécifique
                ├── ARCHITECTURE.md spécifique
                ├── CLAUDE.md local spécifique
                ├── SCRIPT.json
                └── validation = unverified
                        │
                        ▼
project-doctor
                        │
                        ▼
REGISTERED
```

---

## 68. EXEMPLE DE FLUX — NOUVEAU PRODUIT

```text
nouvelle session menu-first ou `/pws`
        │
        ▼
menu contextuel PWS
        │
        ├── Nouveau / importer
        ├── Nouveau script
        ├── type
        ├── distribution
        └── confirmation
        │
        ▼
Le titulaire décrit / précise l’objectif
        │
        ▼
pine-new
        │
        ├── objectif / audience / distribution
        ├── recherche Pine actuelle
        ├── benchmark open-source
        ├── Editors’ Picks
        ├── forces/faiblesses des références
        ├── différenciation le titulaire
        ├── conception produit
        ├── architecture
        ├── décisions le titulaire nécessaires
        │
        ▼
création du product root
        │
        ├── contexte spécifique
        ├── research run
        └── source Pine
                │
                ▼
pine-develop (relecture §9.2, auto-revue, contrôle du diff ;
        │      revue indépendante seulement sur demande du titulaire)
        ▼
local guard
        │
        ▼
pine-local-test
        │
        ├── execution status séparé des observations
        ├── gating seulement si capabilities_used effectivement gating
        ├── unsupported / experimental / inconclusive → non bloquant
        └── unexpected gating change → analyse / correction / re-run
        │
        ▼
tv-validate
      /     \
 manual   chrome-experimental
            │
            └── fallback manual si nécessaire
        │
        ▼
validation liée au SHA exact
```

---

## 69. EXEMPLE DE FLUX — MODIFICATION D’UN SCRIPT

```text
Le titulaire donne l’objectif
        │
        ▼
contexte produit chargé
        │
        ▼
pine-develop
        │
        ├── classification et niveau (travail courant)
        ├── lecture ciblée à partir de la cartographie
        ├── impact
        ├── recherche actuelle
        ├── benchmark si pertinent
        ├── plan
        ├── édition
        ├── relecture (§9.2) et contrôle du diff
        └── synchro artefacts
        │
        ▼
guard
        │
        ▼
pine-local-test selon applicabilité
        │
        ▼
qualification des résultats
        │
        ▼
tv-validate si requis
        │
        ▼
hash final prouvé
```

---

## 70. EXEMPLE DE FLUX — RELEASE

```text
source final
    │
    ▼
pine-release
    │
    ├── SemVer impact
    ├── artefacts applicables
    ├── règles TradingView actuelles
    ├── release reviewer
    └── checks pré-release
            │
            ├── tests comportementaux locaux applicables
            │       └── régressions gating qualifiées
            │
            ▼
validation TradingView du hash final
            │
            ▼
READY FOR HUMAN PUBLICATION
```

Le dernier état n’est pas :

```text
PUBLISHED
```

tant que le titulaire n’a pas effectivement finalisé ou explicitement autorisé la publication.

---

## 71. RÈGLES DE QUALITÉ POUR LE CONTENU GÉNÉRÉ PAR LE BOOTSTRAP

Chaque fichier créé doit être relu avec ces questions :

1. Ce contenu pourrait-il être copié tel quel dans n’importe quel repo ?
   - Si oui, il est probablement trop générique.
2. Quelle partie du standard maître ou de l’environnement réel justifie ce contenu ?
3. Ce fichier contient-il quelque chose déjà présent ailleurs ?
4. Claude a-t-il écrit une rubrique uniquement parce qu’un modèle de document en comportait une ?
5. Le contenu est-il actionnable ?
6. Un futur Claude peut-il savoir quand le fichier est stale ?
7. Un futur Claude peut-il savoir qui a autorité sur ce contenu ?
8. Une inférence est-elle présentée comme un fait ?
9. Une capacité de Claude Code est-elle supposée sans vérification ?
10. Une règle pourrait-elle être path-scoped au lieu d’être always-on ?

---

## 72. AUCUN CLAIM DE « SOPHISTICATION » SANS UTILITÉ

La sophistication recherchée est celle de la séparation correcte des responsabilités.

Elle ne se mesure pas au nombre de fichiers.

Architecture préférée :

```text
petit noyau toujours chargé
+
contexte conditionnel
+
procédures à la demande
+
agents frais spécialisés
+
checks mécaniques
+
preuves réelles
```

Architecture rejetée :

```text
énorme CLAUDE.md
+
50 fichiers de règles redondants
+
10 agents qui se recouvrent
+
base de données
+
orchestrateur custom
+
hooks sémantiques partout
```

---

## 73. SOURCES OFFICIELLES À REVÉRIFIER PENDANT LE BOOTSTRAP

Ces URLs servent de points de départ.

Toujours vérifier leur contenu actuel.

### Claude Code

```text
https://code.claude.com/docs/en/memory
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/hooks
https://code.claude.com/docs/en/tools-reference
https://code.claude.com/docs/en/settings
https://code.claude.com/docs/en/worktrees
https://code.claude.com/docs/en/chrome
https://code.claude.com/docs/en/workflows
```

### TradingView / Pine Script

```text
https://www.tradingview.com/pine-script-docs/
https://www.tradingview.com/pine-script-docs/writing/style-guide/
https://www.tradingview.com/pine-script-docs/writing/publishing/
https://www.tradingview.com/pine-script-docs/writing/limitations/
https://www.tradingview.com/pine-script-docs/concepts/libraries/
https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/
https://www.tradingview.com/support/solutions/43000549951-vendor-requirements/
```

### PineTS upstream

```text
https://github.com/LuxAlgo/PineTS
https://www.npmjs.com/package/pinets
```

Vérifier avant installation ou mise à niveau la version actuelle, la documentation, la licence, les limitations et les changements de compatibilité.

---

## 74. CONSIGNE DE DÉPART À CLAUDE CODE

Lorsque le titulaire fournit cette spécification avec le standard maître, commencer ainsi :

> Lis intégralement cette spécification et le standard maître avant toute création de structure.  
> Vérifie d’abord la documentation Claude Code et TradingView actuelle pour les primitives dont le bootstrap dépend.  
> Vérifie également l’upstream PineTS actuel avant installation : registry npm, artefact exact installable, version, intégrité, licence réellement applicable, limitations et compatibilité pertinente.  
> Inspecte l’environnement réel.  
> Traite le dossier courant comme la racine autonome de Pine Workspace ; ne suppose l’existence d’aucun projet sibling et ne scanne ni ne modifie le contenu d’éventuels projets siblings.  
> Construis la matrice exigences → contexte → primitive → contrôle.  
> Propose mentalement l’architecture, critique-la dans un contexte indépendant, puis seulement écris les fichiers.  
> Chaque fichier doit avoir une responsabilité spécifique et un contenu fondé sur le standard ou l’environnement réel.  
> N’utilise aucun template générique pour simuler de la complétude.  
> N’ajoute aucune couche dont l’utilité n’est pas démontrée.  
> Après construction, exécute tous les self-tests, le doctor, les contrôles de fraîcheur, la détection des `.pine` orphelins et une passe de non-redondance.  
> Ne crée aucun remote, aucun push, aucune publication TradingView et aucun commit sans autorisation explicite du titulaire.  
> Termine par `BOOTSTRAP_REPORT.md` et un résumé précis de ce qui est prêt, expérimental, volontairement absent ou encore à confirmer.

---

# FIN DE LA SPÉCIFICATION

Le workspace final doit rendre le bon comportement naturel pour Claude Code sans charger toute la constitution dans chaque contexte et sans créer une seconde plateforme autour de Claude Code.

La couche PineTS respecte ce principe uniquement tant qu’elle reste un laboratoire local minimal, capability-gated, exactement piné et calibré indépendamment. Elle peut faire respecter un contrat comportemental local précisément borné, mais reste sans autorité normative sur Pine Script et sans autorité sur le comportement propre à TradingView ou sur le statut `TV_VALIDATED`.

L’objectif est :

```text
RICK OBJECTIVE
+
CURRENT TRADINGVIEW TECHNICAL TRUTH
+
ONE CANONICAL PINE STANDARD
+
SCRIPT-SPECIFIC CONTEXT
+
ON-DEMAND PROCEDURES
+
FRESH SPECIALIZED REVIEW
+
DETERMINISTIC LOCAL GUARDS
+
CAPABILITY-GATED LOCAL BEHAVIORAL EXECUTION
+
LOCAL GIT
+
REAL TRADINGVIEW VALIDATION
=
A SMARTER, MORE AUTONOMOUS, TRACEABLE PINE DEVELOPMENT WORKSPACE
```

Le système doit rester capable de grandir avec le nombre de scripts sans dégrader :

- la précision ;
- le contexte ;
- la maintenabilité ;
- la traçabilité ;
- l’originalité ;
- la qualité des validations ;
- la capacité du titulaire à garder le contrôle des décisions produit.
