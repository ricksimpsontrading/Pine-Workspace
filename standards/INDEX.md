# INDEX — PINE SCRIPT V6 STANDARD

Statut : dérivé, non normatif (spec §12). Généré automatiquement depuis les headings réels du master.
Ne jamais éditer à la main : régénérer avec `python3 -m tools.pws_workspace standard-index`.

Master : `standards/PINE_SCRIPT_V6_STANDARD.md`
SHA-256 : 855f0d68909dde4ce34a081b01bde5449776b579252d88f0102b7a0882d14de5
Généré le : 2026-11-13

Règle de fraîcheur : si le SHA du master diffère de celui ci-dessus, cet index est STALE
et ne doit plus être utilisé comme représentation fiable (`standard-status` le vérifie).

| Niveau | Section | Lignes | Mots-clés de routage | Consommateurs principaux |
|---|---|---|---|---|
| 1 | PINE WORKSPACE | 1–1 | pine, workspace |  |
| 1 | MASTER PINE SCRIPT V6 DEVELOPMENT STANDARD | 2–11 | master, pine, script, development, standard |  |
| 2 | 0. MISSION | 12–41 | mission | tous les workflows |
| 2 | 1. STATUTS NORMATIFS ET APPLICABILITÉ | 42–47 | statuts, normatifs, applicabilité | pine-develop, pine-review |
| 3 | 1.1 OBLIGATOIRE | 48–53 | obligatoire |  |
| 3 | 1.2 OBLIGATOIRE SI APPLICABLE | 54–72 | obligatoire, applicable |  |
| 3 | 1.3 PAR DÉFAUT | 73–80 | défaut |  |
| 3 | 1.4 OPTIONNEL | 81–86 | optionnel |  |
| 3 | 1.5 RELEASE UNIQUEMENT | 87–92 | release, uniquement |  |
| 3 | 1.6 Principe de proportionnalité | 93–100 | principe, proportionnalité |  |
| 2 | 2. CLASSES DE TÂCHES | 101–104 | classes, tâches | pine-develop, pine-audit |
| 3 | 2.1 CORRECTION LOCALE | 105–127 | correction, locale |  |
| 3 | 2.2 CHANGEMENT FONCTIONNEL | 128–146 | changement, fonctionnel |  |
| 3 | 2.3 CHANGEMENT STRUCTUREL | 147–167 | changement, structurel |  |
| 3 | 2.4 NOUVEAU SCRIPT | 168–183 | nouveau, script |  |
| 3 | 2.5 RELEASE | 184–198 | release |  |
| 2 | 3. AUTORITÉ TECHNIQUE ET RÉSOLUTION DES CONFLITS | 199–200 | autorité, technique, résolution, conflits | pine-research |
| 3 | 3.1 Objectif fonctionnel — OBLIGATOIRE | 201–215 | objectif, fonctionnel, obligatoire |  |
| 3 | 3.2 Documentation officielle TradingView — OBLIGATOIRE | 216–238 | documentation, officielle, tradingview, obligatoire |  |
| 3 | 3.3 Conflit entre une Convention Personnelle et TradingView — OBLIGATOIRE | 239–256 | conflit, entre, convention, personnelle, tradingview, obligatoire |  |
| 2 | 4. LANGUES ET COMMUNICATION | 257–258 | langues, communication | CLAUDE.md, config (langue), toutes les skills |
| 3 | 4.1 Communication avec le titulaire — OBLIGATOIRE | 259–273 | communication, titulaire, obligatoire |  |
| 3 | 4.2 Code et livrables — OBLIGATOIRE | 274–300 | code, livrables, obligatoire |  |
| 2 | 5. PROFILS DE LICENCE ET MODÈLE DE DISTRIBUTION | 301–341 | profils, licence, modèle, distribution | pine-new, pine-onboard, scan, profiles, licensing |
| 3 | 5.1 Corpus TradingView commun — OBLIGATOIRE POUR UN BENCHMARK | 342–357 | corpus, tradingview, commun, obligatoire, benchmark |  |
| 3 | 5.2 Profil FREE (source public) | 358–374 | profil, free, source, public |  |
| 3 | 5.3 Source fermé (PRIVATE, COMMERCIAL, FREE à source fermé) | 375–408 | source, fermé, private, commercial, free, source, fermé |  |
| 2 | 6. HEADER, VERSION PRODUIT ET LICENCE DU CODE SOURCE | 409–426 | header, version, produit, licence, code, source | guard, licensing, pine-new, pine-release |
| 3 | 6.1 Licence CC BY-NC-SA 4.0 (profil FREE à source public) | 427–452 | licence, by-nc-sa, profil, free, source, public |  |
| 3 | 6.2 Licence propriétaire (PRIVATE, COMMERCIAL, FREE à source fermé) | 453–476 | licence, propriétaire, private, commercial, free, source, fermé |  |
| 3 | 6.3 shorttitle — INTERDIT | 477–486 | shorttitle, interdit |  |
| 3 | 6.4 title — OBLIGATOIRE | 487–495 | title, obligatoire |  |
| 3 | 6.5 URL dans le source — OBLIGATOIRE | 496–501 | source, obligatoire |  |
| 2 | 7. RECHERCHE PINE AVANT CODE | 502–523 | recherche, pine, avant, code | pine-research |
| 2 | 8. BENCHMARK TRADINGVIEW | 524–537 | benchmark, tradingview | pine-research |
| 3 | 8.1 Corpus | 538–550 | corpus |  |
| 3 | 8.2 Même benchmark pour gratuit et payant | 551–558 | même, benchmark, gratuit, payant |  |
| 3 | 8.3 Axes de benchmark | 559–578 | axes, benchmark |  |
| 3 | 8.4 Benchmark comme plancher à dépasser | 579–608 | benchmark, comme, plancher, dépasser |  |
| 3 | 8.5 Frontière benchmark / réutilisation de code — OBLIGATOIRE | 609–642 | frontière, benchmark, réutilisation, code, obligatoire |  |
| 2 | 9. CARTOGRAPHIE OBLIGATOIRE | 643–644 | cartographie, obligatoire | pine-develop, pine-audit, pine-onboard, pws-pine-cartographer |
| 3 | 9.1 Script existant — trois niveaux de vérification | 645–660 | script, existant, trois, niveaux, vérification |  |
| 3 | 9.2 Relecture après modification | 661–674 | relecture, après, modification |  |
| 3 | 9.3 Nouveau script | 675–680 | nouveau, script |  |
| 2 | 10. INVENTAIRE D’IMPACT | 681–692 | inventaire, impact | pine-develop |
| 2 | 11. MÉTHODOLOGIE DE MODIFICATION | 693–719 | méthodologie, modification | pine-develop |
| 2 | 12. COMPATIBILITÉ PINE SCRIPT V6 | 720–740 | compatibilité, pine, script | pine-develop, guard |
| 2 | 13. INVARIANTS PINE SCRIPT V6 | 741–746 | invariants, pine, script | pine-develop, pine-review |
| 3 | 13.1 Version Pine | 747–750 | 13.1, version, pine |  |
| 3 | 13.2 Constantes | 751–756 | 13.2, constantes |  |
| 3 | 13.3 Booléens | 757–770 | 13.3, booléens |  |
| 3 | 13.4 Ternaires et calculs stateful | 771–789 | 13.4, ternaires, calculs, stateful |  |
| 3 | 13.5 Lazy evaluation de `and` et `or` | 790–797 | 13.5, lazy, evaluation, and, or |  |
| 3 | 13.6 Division entière | 798–803 | 13.6, division, entière |  |
| 3 | 13.7 UDT | 804–809 | 13.7 |  |
| 3 | 13.8 `request.security` | 810–815 | 13.8, request.security |  |
| 3 | 13.9 `dynamic_requests` en Pine V6 | 816–829 | 13.9, dynamic_requests, pine |  |
| 3 | 13.10 Primitives visuelles | 830–837 | 13.10, primitives, visuelles |  |
| 2 | 14. PATTERNS À RISQUE SILENCIEUX | 838–839 | patterns, risque, silencieux | pine-review |
| 3 | 14.1 `=` versus `:=` | 840–845 | 14.1, versus |  |
| 3 | 14.2 Scope de classification | 846–851 | 14.2, scope, classification |  |
| 3 | 14.3 Cascade de priorité | 852–857 | 14.3, cascade, priorité |  |
| 3 | 14.4 Champs UDT | 858–861 | 14.4, champs |  |
| 3 | 14.5 Fonctions stateful dans un scope conditionnel | 862–865 | 14.5, fonctions, stateful, scope, conditionnel |  |
| 3 | 14.6 État persistant dans une request | 866–873 | 14.6, état, persistant, request |  |
| 2 | 15. UTILISATION DES FEATURES MODERNES V6 | 874–887 | utilisation, features, modernes | pine-develop |
| 2 | 16. ARCHITECTURE DU CODE | 888–889 | architecture, code | pine-develop, pine-review |
| 3 | 16.1 Sections numérotées — OBLIGATOIRE LORSQU’UNE SECTION SIGNIFICATIVE EXISTE | 890–909 | 16.1, sections, numérotées, obligatoire, lorsqu, section, significative, existe |  |
| 3 | 16.2 Ordre des dépendances — PAR DÉFAUT | 910–917 | 16.2, ordre, dépendances, défaut |  |
| 3 | 16.3 Groupes d’inputs | 918–923 | 16.3, groupes, inputs |  |
| 3 | 16.4 Line wrapping — CONVENTION PERSONNELLE | 924–933 | 16.4, line, wrapping, convention, personnelle |  |
| 2 | 17. NAMING | 934–935 | naming | pine-review |
| 3 | 17.1 Forme syntaxique des identifiants — STYLE GUIDE TRADINGVIEW | 936–943 | 17.1, forme, syntaxique, identifiants, style, guide, tradingview |  |
| 3 | 17.2 Sémantique actuelle — CONVENTION PERSONNELLE OBLIGATOIRE | 944–953 | 17.2, sémantique, actuelle, convention, personnelle, obligatoire |  |
| 3 | 17.3 Suffixes descriptifs | 954–959 | 17.3, suffixes, descriptifs |  |
| 3 | 17.4 Legacy | 960–967 | 17.4, legacy |  |
| 2 | 18. DESIGN PRODUIT | 968–969 | design, produit | pine-new |
| 3 | 18.1 Produit opinionated — PAR DÉFAUT | 970–975 | 18.1, produit, opinionated, défaut |  |
| 3 | 18.2 Fonctionnalité perceptible — OBLIGATOIRE | 976–981 | 18.2, fonctionnalité, perceptible, obligatoire |  |
| 3 | 18.3 Adaptation automatique — PAR DÉFAUT | 982–989 | 18.3, adaptation, automatique, défaut |  |
| 2 | 19. UX DES SETTINGS | 990–991 | settings | pine-new, pine-review |
| 3 | 19.1 Hiérarchie — OBLIGATOIRE | 992–997 | 19.1, hiérarchie, obligatoire |  |
| 3 | 19.2 Préfixes d’arborescence — OPTIONNEL | 998–1003 | 19.2, préfixes, arborescence, optionnel |  |
| 3 | 19.3 Cascade `active=` — OBLIGATOIRE SI APPLICABLE | 1004–1021 | 19.3, cascade, active, obligatoire, applicable |  |
| 2 | 20. TOOLTIPS DES SETTINGS | 1022–1027 | tooltips, settings | pine-develop, pine-review |
| 3 | 20.1 Documentation — OBLIGATOIRE | 1028–1037 | 20.1, documentation, obligatoire |  |
| 3 | 20.2 Input numérique | 1038–1045 | 20.2, input, numérique |  |
| 3 | 20.3 Toggle | 1046–1049 | 20.3, toggle |  |
| 3 | 20.4 Source | 1050–1053 | 20.4, source |  |
| 3 | 20.5 Choice / enum | 1054–1057 | 20.5, choice, enum |  |
| 3 | 20.6 Timeframe | 1058–1061 | 20.6, timeframe |  |
| 3 | 20.7 Session | 1062–1065 | 20.7, session |  |
| 3 | 20.8 Color | 1066–1069 | 20.8, color |  |
| 3 | 20.9 Symbol | 1070–1073 | 20.9, symbol |  |
| 3 | 20.10 Time / Price | 1074–1081 | 20.10, time, price |  |
| 2 | 21. VALIDATION DES SETTINGS | 1082–1095 | validation, settings | pine-develop |
| 2 | 22. TERMINOLOGIE USER-FACING | 1096–1105 | terminologie, user-facing | pine-review, pine-release |
| 3 | 22.1 Acronymes | 1106–1115 | 22.1, acronymes |  |
| 3 | 22.2 Texte utile et actionnable | 1116–1123 | 22.2, texte, utile, actionnable |  |
| 3 | 22.3 Versions et licences | 1124–1133 | 22.3, versions, licences |  |
| 2 | 23. TOOLTIPS DES ÉLÉMENTS VISUELS | 1134–1139 | tooltips, éléments, visuels | pine-develop, pine-review |
| 3 | 23.1 Différence fondamentale | 1140–1147 | 23.1, différence, fondamentale |  |
| 3 | 23.2 Labels | 1148–1155 | 23.2, labels |  |
| 3 | 23.3 Tables et dashboards | 1156–1167 | 23.3, tables, dashboards |  |
| 3 | 23.4 Niveau d’obligation | 1168–1177 | 23.4, niveau, obligation |  |
| 2 | 24. COMMENTAIRES ET DOCUMENTATION INTERNE | 1178–1179 | commentaires, documentation, interne | pine-develop, pine-review, guard (no-worklog-comments) |
| 3 | 24.1 Annotations | 1180–1183 | 24.1, annotations |  |
| 3 | 24.2 Commenter le pourquoi | 1184–1189 | 24.2, commenter, pourquoi |  |
| 3 | 24.3 Aucun mur de commentaires — OBLIGATOIRE | 1190–1199 | 24.3, aucun, commentaires, obligatoire |  |
| 3 | 24.4 Commentaires synchronisés — OBLIGATOIRE | 1200–1205 | 24.4, commentaires, synchronisés, obligatoire |  |
| 3 | 24.5 Ce qui ne vit pas dans le source — OBLIGATOIRE | 1206–1218 | 24.5, source, obligatoire |  |
| 2 | 25. ROBUSTESSE NUMÉRIQUE ET EDGE CASES | 1219–1220 | robustesse, numérique, edge, cases | pine-develop, pine-review |
| 3 | 25.1 Division — OBLIGATOIRE SI APPLICABLE | 1221–1238 | 25.1, division, obligatoire, applicable |  |
| 3 | 25.2 Scores | 1239–1248 | 25.2, scores |  |
| 3 | 25.3 Historique | 1249–1252 | 25.3, historique |  |
| 3 | 25.4 Drawing coordinates | 1253–1258 | 25.4, drawing, coordinates |  |
| 3 | 25.5 Format des prix et valeurs — OBLIGATOIRE SI APPLICABLE | 1259–1272 | 25.5, format, prix, valeurs, obligatoire, applicable |  |
| 3 | 25.6 Debugging | 1273–1280 | 25.6, debugging |  |
| 2 | 26. ÉVÉNEMENTS, ÉTATS ET `ta.valuewhen()` | 1281–1304 | événements, états, ta.valuewhen | pine-develop, pine-review |
| 2 | 27. MTF, HISTORIQUE, REALTIME ET REPAINT | 1305–1306 | historique, realtime, repaint | pine-develop, tv-validate |
| 3 | 27.1 Principe général | 1307–1312 | 27.1, principe, général |  |
| 3 | 27.2 Anti-repaint — OBLIGATOIRE | 1313–1320 | 27.2, anti-repaint, obligatoire |  |
| 3 | 27.3 `lookahead` et future leak — OBLIGATOIRE SI APPLICABLE | 1321–1339 | 27.3, lookahead, future, leak, obligatoire, applicable |  |
| 3 | 27.4 Détection d’une nouvelle barre HTF | 1340–1345 | 27.4, détection, nouvelle, barre |  |
| 3 | 27.5 `varip` | 1346–1351 | 27.5, varip |  |
| 3 | 27.6 Scaling MTF | 1352–1359 | 27.6, scaling |  |
| 2 | 28. PERFORMANCE ET RESSOURCES | 1360–1365 | performance, ressources | pine-develop, pine-research |
| 3 | 28.1 Limites TradingView | 1366–1371 | 28.1, limites, tradingview |  |
| 3 | 28.2 Drawing objects | 1372–1379 | 28.2, drawing, objects |  |
| 3 | 28.3 `barstate.islast` | 1380–1387 | 28.3, barstate.islast |  |
| 3 | 28.4 Complexité | 1388–1395 | 28.4, complexité |  |
| 3 | 28.5 `max_bars_back` | 1396–1403 | 28.5, max_bars_back |  |
| 2 | 29. ÉLÉMENTS VISUELS — APPLICABILITÉ | 1404–1415 | éléments, visuels, applicabilité | pine-new, pine-review |
| 2 | 30. PALETTE ET IDENTITÉ VISUELLE | 1416–1417 | palette, identité, visuelle | pine-new, pine-review |
| 3 | 30.1 Dark + light — OBLIGATOIRE SI ÉLÉMENTS VISUELS | 1418–1423 | 30.1, dark, light, obligatoire, éléments, visuels |  |
| 3 | 30.2 Couleurs professionnelles — PAR DÉFAUT | 1424–1454 | 30.2, couleurs, professionnelles, défaut |  |
| 3 | 30.3 Hiérarchie visuelle — OBLIGATOIRE SI APPLICABLE | 1455–1462 | 30.3, hiérarchie, visuelle, obligatoire, applicable |  |
| 3 | 30.4 Transparence — PAR DÉFAUT | 1463–1470 | 30.4, transparence, défaut |  |
| 3 | 30.5 Couleurs configurables | 1471–1482 | 30.5, couleurs, configurables |  |
| 3 | 30.6 Cohérence inter-script | 1483–1490 | 30.6, cohérence, inter-script |  |
| 2 | 31. SEMANTIC VERSIONING | 1491–1502 | semantic, versioning | pine-release, guard |
| 3 | 31.1 Principe fondamental | 1503–1508 | 31.1, principe, fondamental |  |
| 3 | 31.2 MAJOR | 1509–1512 | 31.2, major |  |
| 3 | 31.3 MINOR | 1513–1516 | 31.3, minor |  |
| 3 | 31.4 PATCH | 1517–1520 | 31.4, patch |  |
| 3 | 31.5 Bugfix pouvant changer les sorties | 1521–1530 | 31.5, bugfix, pouvant, changer, sorties |  |
| 3 | 31.6 Bêta | 1531–1536 | 31.6, bêta |  |
| 3 | 31.7 Payant et breaking change | 1537–1542 | 31.7, payant, breaking, change |  |
| 2 | 32. CHANGELOG | 1543–1559 | changelog | pine-release, pine-github |
| 3 | 32.1 Règles communes | 1560–1577 | 32.1, règles, communes |  |
| 3 | 32.2 Source fermé (COMMERCIAL, PRIVATE, FREE à source fermé) | 1578–1587 | 32.2, source, fermé, commercial, private, free, source, fermé |  |
| 3 | 32.3 Profil FREE à source public | 1588–1595 | 32.3, profil, free, source, public |  |
| 2 | 33. TUTORIEL UTILISATEUR | 1596–1601 | tutoriel, utilisateur | pine-docs, pine-release |
| 3 | 33.1 Règles communes | 1602–1611 | 33.1, règles, communes |  |
| 3 | 33.2 Convention « premium » (par défaut pour COMMERCIAL et PRIVATE) | 1612–1640 | 33.2, convention, premium, défaut, commercial, private |  |
| 3 | 33.3 Convention « documentaire » (par défaut pour FREE) | 1641–1667 | 33.3, convention, documentaire, défaut, free |  |
| 3 | 33.4 Revue du tutoriel | 1668–1673 | 33.4, revue, tutoriel |  |
| 2 | 34. PUBLICATION TRADINGVIEW | 1674–1683 | publication, tradingview | pine-release, tv-validate |
| 3 | 34.1 Règles communes | 1684–1693 | 34.1, règles, communes |  |
| 3 | 34.2 Profil FREE à source public | 1694–1706 | 34.2, profil, free, source, public |  |
| 3 | 34.3 Source fermé (COMMERCIAL, PRIVATE publié, FREE à source fermé) | 1707–1720 | 34.3, source, fermé, commercial, private, publié, free, source, fermé |  |
| 3 | 34.4 Mode de publication payant — OBLIGATOIRE | 1721–1748 | 34.4, mode, publication, payant, obligatoire |  |
| 3 | 34.5 Chart de publication — OBLIGATOIRE | 1749–1764 | 34.5, chart, publication, obligatoire |  |
| 3 | 34.6 Benchmark de publication | 1765–1772 | 34.6, benchmark, publication |  |
| 2 | 35. TESTS PRÉ-RELEASE | 1773–1780 | tests, pré-release | pine-release, tv-validate |
| 3 | 35.1 Symboles | 1781–1786 | 35.1, symboles |  |
| 3 | 35.2 Timeframes | 1787–1790 | 35.2, timeframes |  |
| 3 | 35.3 Modes | 1791–1796 | 35.3, modes |  |
| 3 | 35.4 Affichage | 1797–1800 | 35.4, affichage |  |
| 3 | 35.5 Performance | 1801–1804 | 35.5, performance |  |
| 3 | 35.6 Repaint | 1805–1810 | 35.6, repaint |  |
| 3 | 35.7 Alertes | 1811–1814 | 35.7, alertes |  |
| 3 | 35.8 Settings extrêmes | 1815–1818 | 35.8, settings, extrêmes |  |
| 3 | 35.9 Instruments atypiques | 1819–1822 | 35.9, instruments, atypiques |  |
| 3 | 35.10 Release avec bug connu | 1823–1830 | 35.10, release, connu |  |
| 2 | 36. REVUE POST-CODE — QUATRE AXES | 1831–1834 | revue, post-code, quatre, axes | pine-review, pine-audit |
| 3 | AXE 1 — INTÉGRITÉ CONTEXTUELLE | 1835–1842 | intégrité, contextuelle |  |
| 3 | AXE 2 — ARTEFACTS DÉPENDANTS | 1843–1848 | artefacts, dépendants |  |
| 3 | AXE 3 — CONVENTIONS APPLICABLES | 1849–1856 | conventions, applicables |  |
| 3 | AXE 4 — REGARD FRAIS | 1857–1872 | regard, frais |  |
| 2 | 37. ANTI-PATTERNS | 1873–1874 | anti-patterns | pine-review, guard |
| 3 | 37.1 Inventer un fait | 1875–1880 | 37.1, inventer, fait |  |
| 3 | 37.2 Recherche fictive | 1881–1884 | 37.2, recherche, fictive |  |
| 3 | 37.3 Scope creep | 1885–1892 | 37.3, scope, creep |  |
| 3 | 37.4 Réécriture inutile | 1893–1896 | 37.4, réécriture, inutile |  |
| 3 | 37.5 Franglais | 1897–1900 | 37.5, franglais |  |
| 3 | 37.6 Internals user-facing | 1901–1904 | 37.6, internals, user-facing |  |
| 3 | 37.7 Anciennes conventions contradictoires | 1905–1910 | 37.7, anciennes, conventions, contradictoires |  |
| 3 | 37.8 Couleurs built-in primaires par défaut | 1911–1914 | 37.8, couleurs, built-in, primaires, défaut |  |
| 3 | 37.9 Hallucination d’API | 1915–1918 | 37.9, hallucination |  |
| 3 | 37.10 Héritage d’un autre script | 1919–1922 | 37.10, héritage, autre, script |  |
| 3 | 37.11 Modulo HTF | 1923–1926 | 37.11, modulo |  |
| 3 | 37.12 `var` pour constante | 1927–1930 | 37.12, var, constante |  |
| 3 | 37.13 Side effects dans `and` / `or` | 1931–1934 | 37.13, side, effects, and, or |  |
| 3 | 37.14 Copie depuis le benchmark | 1935–1942 | 37.14, copie, depuis, benchmark |  |
| 3 | 37.15 `shorttitle` | 1943–1948 | 37.15, shorttitle |  |
| 3 | 37.16 Version produit hors header | 1949–1952 | 37.16, version, produit, hors, header |  |
| 3 | 37.17 Future leak | 1953–1956 | 37.17, future, leak |  |
| 3 | 37.18 Publication payante non autorisée | 1957–1960 | 37.18, publication, payante, autorisée |  |
| 3 | 37.19 Journal de travail dans le source | 1961–1966 | 37.19, journal, travail, source |  |
| 2 | 38. WORKFLOW — SCRIPT EXISTANT | 1967–1997 | workflow, script, existant | pine-develop |
| 2 | 39. WORKFLOW — NOUVEAU SCRIPT | 1998–2032 | workflow, nouveau, script | pine-new |
| 2 | 40. VALIDATION TRADINGVIEW | 2033–2050 | validation, tradingview | tv-validate |
| 2 | 41. LIVRABLES DE RELEASE | 2051–2064 | livrables, release | pine-release, pine-github |
| 2 | 42. STANDARD DE FIN | 2065–2132 | standard | pine-develop, pine-release |

