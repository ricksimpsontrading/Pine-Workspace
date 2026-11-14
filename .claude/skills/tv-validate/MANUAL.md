# Mode `manual` — protocole

Mode par défaut et stable (spec §30). Claude prépare et enregistre ; le titulaire observe dans TradingView.

## Déroulé

1. Terminer les contrôles locaux (`guard`, et `pine-local-test` si applicable, résultats qualifiés).
2. Capturer l'identité du source (`source-fingerprint`) et créer le run `in-progress`.
3. Construire la matrice spécifique au changement (voir SKILL.md §3) — chaque test avec : objectif, étapes précises dans TradingView, résultat attendu, ce qui constituerait un échec.
4. Donner au titulaire les étapes une par une ou en bloc court ; attendre ses observations RÉELLES. Ne jamais supposer un résultat. Confirmation par groupe (spec §30.4) : présenter au titulaire la liste EXACTE des contrôles du groupe AVANT de demander sa confirmation ; consigner dans `groups`, pour chaque groupe : `id`, `controls` (liste exacte des identifiants présentés), `presented_text` (texte présenté), `confirmation_text` (réponse reçue), `observed_by` et `at` (RFC 3339 UTC). Un contrôle absent de la liste présentée n'est pas couvert ; aucune mesure, valeur ou configuration non rapportée n'est déduite.
5. Enregistrer chaque observation telle que rapportée (succès, échec, anomalie, capture éventuelle si elle prouve quelque chose d'utile). Rapport de version 2 : chaque contrôle de la matrice a un `id` unique ; chaque résultat porte `verdict`, `observation`, `observed_by`, `at` et, s'il vient d'une confirmation par groupe, `group` avec l'observation « confirmé par groupe, sans détail individuel ». Verdicts d'un contrôle applicable : `passed`, `failed`, `not-run`, `indeterminate` ; `n-a` est réservé aux contrôles déclarés non applicables.
6. Statut final (spec §51.5, vérifié par le tooling, verdicts avant couverture) :
   - `failed` — au moins un contrôle applicable a échoué, même si d'autres ne sont pas renseignés (corriger via `pine-develop`, puis NOUVEAU run sur le nouveau SHA) ;
   - `passed` — tous les contrôles applicables ont le verdict `passed` ;
   - `partial` — aucun échec, au moins un `passed`, au moins un `not-run` ou `indeterminate`, tous les contrôles applicables renseignés ;
   - `in-progress` — un contrôle applicable n'est pas renseigné, ou aucun n'a encore réussi.
7. Promouvoir le run via le protocole atomique, preuves hashées. Un rapport de version 1 n'est plus promu ; les rapports déjà enregistrés restent lisibles et recevables sur leur SHA, jamais réécrits.

## Compilation minimale (spec §30.5)

Demandée seulement lorsque l'inventaire d'impact l'a conclue requise. Demander au titulaire de compiler le source exact (SHA relevé avant) dans le Pine Editor et de rapporter SÉPARÉMENT les erreurs et les avertissements. Rapport : `scope: "compilation"` ; dans la matrice, exactement un contrôle applicable avec `kind: "compilation"` et les contrôles comportementaux applicables, listés `not-run` sans inventer leurs résultats ; objet `compilation` avec `errors` et `warnings` séparés, chacun `{ "reported": true|false, "items": [textes rapportés] }`. `reported: false` consigne une absence d'observation : ne jamais la transformer en « aucun avertissement ». `reported: true` avec une liste vide consigne une absence observée. Un tel run n'est jamais `passed`.

Enregistrement et promotion sont distincts. Le rapport valide est toujours conservé. Sur le même SHA que le run courant reconnu, une compilation non `failed` est enregistrée sans promotion et le run courant est conservé. Une compilation `failed` le remplace ; si le run courant était `passed`, le résultat signale une contradiction à présenter au titulaire. Lire `promoted`, `recorded`, `conflict` et `notes` dans le résultat de la promotion et les rapporter tels quels.

## Interdits

- Déclarer `passed` sans observation réelle du titulaire sur le SHA exact.
- Exécuter mécaniquement un test sans objet.
- Considérer une compilation locale ou un run PineTS comme une observation TradingView.
