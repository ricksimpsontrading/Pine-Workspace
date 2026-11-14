---
name: tv-mode
description: Changer le mode persistant de validation TradingView (manual ou chrome-experimental). Réservé au titulaire — Claude ne peut pas invoquer cette skill.
disable-model-invocation: true
---

# /tv-mode — changement du mode TradingView persistant

Usage : `/tv-mode manual` ou `/tv-mode chrome-experimental`.

Exécuter le contrôleur déterministe partagé (unique propriétaire de la mutation) :

```bash
python3 -m tools.pws_workspace tv-mode <mode>
```

- Modifie UNIQUEMENT la clé `tv_validation_mode` de `pws.config.json` (configuration personnelle PWS) et la provenance de ce choix explicite (`tv_validation_mode_choice` : par le titulaire, date), qui permet de résoudre une seule fois un conflit avec une valeur héritée (migration m001), préserve toutes les autres clés, écrit atomiquement sous verrou et refuse toute modification concurrente. Les réglages de Claude Code (`.claude/settings*.json`) ne sont jamais touchés.
- Sans argument, `python3 -m tools.pws_workspace tv-mode` affiche le mode courant et sa source (`config`, `legacy`, `default`) — la variable d'environnement n'est jamais un chemin de lecture. `manual` est le défaut ; `chrome-experimental` reste explicitement optionnel.
- Claude ne change JAMAIS le mode persistant de sa propre initiative (spec §28.4). Le fallback d'un run `chrome-experimental` vers `manual` ne modifie pas le mode enregistré.
- La route `/pws → Maintenance / configuration → Configuration → Mode TradingView` transmet le choix explicite du titulaire au même contrôleur sans passer par cette skill.
