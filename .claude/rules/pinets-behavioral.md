---
paths:
  - "tools/pine_exec/calibration/**"
  - "scripts/**/tests/behavioral/**"
---

# Invariants de la couche comportementale PineTS

Ces fichiers peuvent modifier une gate locale. Contrat complet : skill `pine-local-test` (spec §24.4). Invariants protégés ici :

- Aucune promotion `GATING` sans calibration indépendante suffisante contre le triplet exact `pinets_version + executor_fingerprint + normalization_schema` (référence jamais issue de PineTS seul).
- Causes de staleness de la spec §24.4.5 : changement de cas, input, attendu, référence ou preuve ; divergence reproductible nouvelle ; évolution documentaire pertinente. Jamais de TTL arbitraire.
- Baseline durable uniquement via le contrat `ACCEPTED_BEHAVIORAL_BASELINE` (spec §24.4.10) : jamais automatique, toujours avec `acceptance_basis` et justification.
- `effective_gating` n'est jamais persisté : il est dérivé à la lecture.
- Aucune preuve PineTS sous `validation/`.
- Aucune modification d'un source Pine dont la seule justification serait de satisfaire PineTS.
