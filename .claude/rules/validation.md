---
paths:
  - "scripts/**/validation/**"
---

# Validation TradingView d'un script

`validation/` est exclusivement réservé aux observations, runs et preuves TradingView (spec §51.1).

INTERDIT :
- persister `passed` sans run réel dont tous les contrôles obligatoires applicables ont réussi sur le SHA exact du source (spec §51.5) ;
- une preuve non liée au SHA-256 du source réellement testé ;
- confondre un résultat local (guard ou PineTS) avec une observation TradingView ;
- modifier manuellement un état de façon trompeuse ;
- écrire ici un artefact PineTS (ils vont sous `tests/behavioral/` ou l'espace runtime éphémère).

Statuts persistés : `unverified`, `in-progress`, `passed`, `failed`, `partial` — seule taxonomie machine. `stale` est dérivé (SHA courant ≠ SHA du run courant), jamais persisté. Toute promotion de run suit le protocole atomique de la spec §51.4 (rapport immuable d'abord, refus des runs plus anciens et des conflits concurrents) via `tools/pws_workspace`.
