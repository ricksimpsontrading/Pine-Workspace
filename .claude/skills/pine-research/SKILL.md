---
name: pine-research
description: Recherche Pine/TradingView actuelle et traçable — documentation officielle, benchmark open-source et Editors' Picks. Utiliser avant une décision technique incertaine, un nouveau produit ou une release.
---

# Recherche Pine actuelle

Langue : répondre dans la langue configurée (`language` de `session-status --json`).

Produire de la recherche actuelle, traçable et utile au script (spec §25). Déléguer les lectures volumineuses à l'agent `pws-pine-researcher` (contexte frais, retour structuré : faits officiels / observation benchmark / inférence / recommandation).

## Sources prioritaires

- Faits Pine : documentation officielle TradingView/Pine Script, release notes officielles, règles officielles de publication lorsque concernées. Ne JAMAIS inventer une API ni prétendre avoir consulté une source non consultée (master §37.1–37.2).
- Benchmark : scripts publics open-source pertinents, Editors' Picks prioritaires, autres références open-source de haute qualité. Jamais de code closed-source/invite-only comme corpus d'analyse (master §5.1).

## Frontière

Le benchmark n'autorise aucune réutilisation de code : frontière master §8.5 (implémentation originale ; provenance, licence, règles TradingView, accord explicite du titulaire). Les références étudiées sont tracées dans le run de recherche, jamais en crédits automatiques dans le script.

## Persistance

- Recherche insignifiante → ne rien écrire.
- Résultat réutilisable → `scripts/<slug>/research/runs/YYYY-MM-DDTHHMMSS-<topic>.md` (contenu : question, contexte, date, sources, faits, benchmark, limites, conclusion, implications, à revérifier) puis mise à jour de `research/CURRENT.md` (synthèse de routage + statut CURRENT/STALE/NON REVÉRIFIÉ).
- Lorsqu'un agent chercheur est invoqué, le parent persiste son rapport en run de recherche dès réception, avec la date de consultation et la provenance. Un run écrit après coup porte la date de recherche initiale, la date de reconstitution et la provenance, sans heure inventée ; sa fraîcheur reste celle de sa date initiale tant qu'aucune revérification datée n'est faite. Une recherche non effectuée n'est jamais datée (spec §25.4). Le run conserve le rapport final et la table des sources, pas le journal complet.
- Statuts de `CURRENT.md` (spec §50.4) : `CURRENT` (revérification datée), `STALE`, `NON REVÉRIFIÉ` ; un run reconstitué ne reçoit jamais `CURRENT` sans revérification.
- Benchmark : qualifier chaque cas par « effectué et tracé », « non tracé » ou « N/A motivé et tracé » ; une preuve absente signifie non démontré, jamais non effectué (spec §21.2).
- Fraîcheur : pas de TTL arbitraire ; les règles de publication TradingView sont TOUJOURS revérifiées juste avant une vraie release.
