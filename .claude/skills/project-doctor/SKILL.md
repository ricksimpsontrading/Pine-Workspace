---
name: project-doctor
description: Diagnostic de santé du workspace — checks déterministes (structure, manifests, validation, standard, PineTS, Git, collisions de skills) et revue sémantique optionnelle. Utiliser pour vérifier l'état du workspace ou diagnostiquer une incohérence.
---

# Diagnostic du workspace

Langue : répondre dans la langue configurée (`language` de `session-status --json`). Le diagnostic recherche les problèmes sans jamais réparer automatiquement.

## Couche déterministe

```bash
python3 -m tools.pws_workspace doctor
```

Sortie : `OK / INFO / WARNING / BLOCKING` — chaque BLOCKING est actionnable. Couvre notamment : frontière physique (repo parent englobant, symlinks sortants), autorités et fraîcheur INDEX/TRACEABILITY, configuration PWS (`pws.config.json` : présence, validité, version du workspace, identité configurée), mode TV valide (configuration ; clé legacy signalée), axes produits (§44), profils et cohérence des axes de licence (schéma 2 ; manifeste v1 signalé pour migration), orphelins `.pine`, intégrité et staleness des validations, Git local (absence de Git ou de dépôt = mode dégradé signalé WARNING, jamais une exception ; remotes, worktrees ignorés), hooks configurés, exclusion MCP projet, collisions de skills critiques (les skills personnelles masquent les skills projet ; collisions enterprise non vérifiables d'ici), pin PineTS exact + lockfile + provenance + `license_basis` + identité de l'artefact installé (SHA enregistré dans `PROVENANCE.json` ; un artefact différent est BLOCKING, comme dans `pinets verify` : même fait, même gravité), restes d'un retour arrière PineTS interrompu (`pinets-rollback-leftovers`, WARNING, jamais supprimés automatiquement), cohérence calibration/triplet, absence d'`effective_gating` persisté.

Rappels d'interprétation :
- calibration `STALE`/`MISSING` → interdit seulement l'usage effectivement gating des capabilities concernées ; ne classe JAMAIS un source Pine `BROKEN` et ne remplace jamais la validation TradingView ;
- `node_modules` absent → limitation déclarée (`npm ci --ignore-scripts` dans `tools/pine_exec`), jamais un défaut d'un source Pine ;
- validation effective `stale` → le script ne peut pas être présenté comme validé/prêt tant que le SHA courant n'a pas été revalidé.

## Couche sémantique (à la demande, après une évolution d'architecture)

Vérifier manuellement : duplications d'instructions entre CLAUDE.md/rules/skills/agents, responsabilités devenues concurrentes, fichiers sans utilité, incohérences entre `docs/architecture/FILE_CONTRACTS.md` et l'implémentation réelle. Cette couche est une revue, pas un outil : la mener avec les questions de la spec §71.
