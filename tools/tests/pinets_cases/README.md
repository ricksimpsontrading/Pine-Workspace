# Cas génériques d'essai de capacités PineTS

Matériel indépendant de tout produit. Aucun cas n'est un cas de calibration. Aucun résultat ne confère de statut `GATING` ni de statut TradingView.

## Deux choses distinctes

| | Rôle | Doit réussir ? |
|---|---|---|
| Tests du tooling : `tools/tests/test_pinets_cases.py` | Vérifient ce matériel : manifeste, attendus reproductibles, comparateur, observations à jour | Oui |
| Essais de capacités : `run_campaign.py` | Exécutent un moteur sur les cas et consignent le résultat | Non : concordance, divergence et échec sont trois résultats |

Un échec du moteur ne conduit jamais à modifier un source ni un attendu. Aucun test n'exige qu'une syntaxe échoue : une correction amont doit pouvoir être constatée lors d'une migration.

## Attendus

Chaque série de `expected/*.expected.json` indique sa provenance. Statut `established` : valeur fixée par une référence indépendante du moteur. Statut `exploration` : l'attente n'a pas pu être établie avec les moyens autorisés ; la valeur candidate est conservée, la preuve manquante est nommée, et le résultat du moteur est seulement décrit.

Les attendus des moyennes mobiles sont un contrat mathématique local, pas une correspondance TradingView.

## Commandes, depuis la racine du workspace

```bash
python3 -m tools.tests.pinets_cases.build_cases --check
```

```bash
python3 -m tools.tests.pinets_cases.run_campaign --out-dir .claude/runtime/pine-local-test/<dossier-neuf> --campaign-id <identifiant> --observed-on AAAA-MM-JJ
```

```bash
python3 -m tools.tests.pinets_cases.compare_campaigns <releve-a.json> <releve-b.json>
```

Options du lanceur : `--cases ID,ID` limite le périmètre ; `--executor DOSSIER` observe un autre exécuteur ; `--observations FICHIER` écrit un relevé durable.

## Garanties du lanceur

- Le dossier de sortie doit être neuf ou vide : aucun rapport antérieur ne peut servir de résultat.
- Les fichiers utilisés sont comparés au manifeste, et chaque rapport doit nommer les mêmes empreintes.
- Identité du moteur, schémas, statuts et intégrité des deux exécutions sont contrôlés avant toute conclusion.
- `EXECUTION_FAIL` est un échec rapporté par le moteur dans un rapport valide. `HARNESS_FAILURE` est un échec du lanceur ou un rapport absent ou invalide. `INVALID_PAYLOAD` est une restitution qui rompt son contrat, par exemple un booléen ou une valeur non finie à la place d'un nombre.
- Une campagne qui contient une tentative inexploitable est `UNUSABLE` : code de sortie 1, aucun relevé durable écrit.
- Codes de sortie : 0 campagne complète, 1 campagne inexploitable, 2 refus ou erreur d'usage.

## Relevés

Un relevé décrit une campagne identifiée sur son propre périmètre : moteur, fingerprint, cas et empreintes. Il n'est pas tenu de couvrir les cas ajoutés ou modifiés ensuite. Un relevé existant n'est jamais écrasé : toute nouvelle campagne s'écrit dans un nouveau fichier. Le comparateur canonique du thin adapter n'est pas utilisé entre deux versions.
