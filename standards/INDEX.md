# INDEX — PINE SCRIPT V6 STANDARD

Status: derived, non-normative (spec §12). Generated automatically from the real headings of the master.
Never edit by hand: regenerate with `python3 -m tools.pws_workspace standard-index`.

Master: `standards/PINE_SCRIPT_V6_STANDARD.md`
SHA-256: 2a4e0dc62fe4fc749b94982af88c2b8c33cb4a9ffd2400ee206d5007ac9e2987
Generated on: 2026-11-14

Freshness rule: if the SHA of the master differs from the one above, this index is STALE
and must no longer be used as a reliable representation (`standard-status` checks it).

| Level | Section | Lines | Routing keywords | Main consumers |
|---|---|---|---|---|
| 1 | PINE WORKSPACE | 1–1 | pine, workspace |  |
| 1 | MASTER PINE SCRIPT V6 DEVELOPMENT STANDARD | 2–11 | master, pine, script, development, standard |  |
| 2 | 0. MISSION | 12–41 | mission | all workflows |
| 2 | 1. NORMATIVE STATUSES AND APPLICABILITY | 42–47 | normative, statuses, applicability | pine-develop, pine-review |
| 3 | 1.1 MANDATORY | 48–53 | mandatory |  |
| 3 | 1.2 MANDATORY IF APPLICABLE | 54–72 | mandatory, applicable |  |
| 3 | 1.3 DEFAULT | 73–80 | default |  |
| 3 | 1.4 OPTIONAL | 81–86 | optional |  |
| 3 | 1.5 RELEASE ONLY | 87–92 | release |  |
| 3 | 1.6 Proportionality principle | 93–100 | proportionality, principle |  |
| 2 | 2. TASK CLASSES | 101–104 | task, classes | pine-develop, pine-audit |
| 3 | 2.1 LOCAL FIX | 105–127 | local |  |
| 3 | 2.2 FUNCTIONAL CHANGE | 128–146 | functional, change |  |
| 3 | 2.3 STRUCTURAL CHANGE | 147–167 | structural, change |  |
| 3 | 2.4 NEW SCRIPT | 168–183 | script |  |
| 3 | 2.5 RELEASE | 184–198 | release |  |
| 2 | 3. TECHNICAL AUTHORITY AND CONFLICT RESOLUTION | 199–200 | technical, authority, conflict, resolution | pine-research |
| 3 | 3.1 Functional objective — MANDATORY | 201–215 | functional, objective, mandatory |  |
| 3 | 3.2 Official TradingView documentation — MANDATORY | 216–238 | official, tradingview, documentation, mandatory |  |
| 3 | 3.3 Conflict between a Personal Convention and TradingView — MANDATORY | 239–256 | conflict, between, personal, convention, tradingview, mandatory |  |
| 2 | 4. LANGUAGES AND COMMUNICATION | 257–258 | languages, communication | CLAUDE.md, config (language), all skills |
| 3 | 4.1 Communication with the holder — MANDATORY | 259–279 | communication, holder, mandatory |  |
| 3 | 4.2 Code and deliverables — MANDATORY | 280–306 | code, deliverables, mandatory |  |
| 2 | 5. LICENCE PROFILES AND DISTRIBUTION MODEL | 307–347 | licence, profiles, distribution, model | pine-new, pine-onboard, scan, profiles, licensing |
| 3 | 5.1 Common TradingView corpus — MANDATORY FOR A BENCHMARK | 348–363 | common, tradingview, corpus, mandatory, benchmark |  |
| 3 | 5.2 FREE profile (public source) | 364–380 | free, profile, public, source |  |
| 3 | 5.3 Closed source (PRIVATE, COMMERCIAL, FREE with closed source) | 381–414 | closed, source, private, commercial, free, closed, source |  |
| 2 | 6. HEADER, PRODUCT VERSION AND SOURCE CODE LICENCE | 415–432 | header, product, version, source, code, licence | guard, licensing, pine-new, pine-release |
| 3 | 6.1 CC BY-NC-SA 4.0 licence (FREE profile with public source) | 433–458 | by-nc-sa, licence, free, profile, public, source |  |
| 3 | 6.2 Proprietary licence (PRIVATE, COMMERCIAL, FREE with closed source) | 459–482 | proprietary, licence, private, commercial, free, closed, source |  |
| 3 | 6.3 shorttitle — FORBIDDEN | 483–492 | shorttitle, forbidden |  |
| 3 | 6.4 title — MANDATORY | 493–501 | title, mandatory |  |
| 3 | 6.5 URLs in the source — MANDATORY | 502–507 | urls, source, mandatory |  |
| 2 | 7. PINE RESEARCH BEFORE CODE | 508–529 | pine, research, code | pine-research |
| 2 | 8. TRADINGVIEW BENCHMARK | 530–543 | tradingview, benchmark | pine-research |
| 3 | 8.1 Corpus | 544–556 | corpus |  |
| 3 | 8.2 Same benchmark for free and paid | 557–564 | same, benchmark, free, paid |  |
| 3 | 8.3 Benchmark axes | 565–584 | benchmark, axes |  |
| 3 | 8.4 Benchmark as a floor to exceed | 585–614 | benchmark, floor, exceed |  |
| 3 | 8.5 Benchmark / code reuse boundary — MANDATORY | 615–648 | benchmark, code, reuse, boundary, mandatory |  |
| 2 | 9. MANDATORY MAPPING | 649–650 | mandatory, mapping | pine-develop, pine-audit, pine-onboard, pws-pine-cartographer |
| 3 | 9.1 Existing script — three verification levels | 651–666 | existing, script, three, verification, levels |  |
| 3 | 9.2 Re-reading after modification | 667–680 | re-reading, modification |  |
| 3 | 9.3 New script | 681–686 | script |  |
| 2 | 10. IMPACT INVENTORY | 687–698 | impact, inventory | pine-develop |
| 2 | 11. MODIFICATION METHODOLOGY | 699–725 | modification, methodology | pine-develop |
| 2 | 12. PINE SCRIPT V6 COMPATIBILITY | 726–746 | pine, script, compatibility | pine-develop, guard |
| 2 | 13. PINE SCRIPT V6 INVARIANTS | 747–752 | pine, script, invariants | pine-develop, pine-review |
| 3 | 13.1 Pine version | 753–756 | 13.1, pine, version |  |
| 3 | 13.2 Constants | 757–762 | 13.2, constants |  |
| 3 | 13.3 Booleans | 763–776 | 13.3, booleans |  |
| 3 | 13.4 Ternaries and stateful calculations | 777–795 | 13.4, ternaries, stateful, calculations |  |
| 3 | 13.5 Lazy evaluation of `and` and `or` | 796–803 | 13.5, lazy, evaluation, and, or |  |
| 3 | 13.6 Integer division | 804–809 | 13.6, integer, division |  |
| 3 | 13.7 UDT | 810–815 | 13.7 |  |
| 3 | 13.8 `request.security` | 816–821 | 13.8, request.security |  |
| 3 | 13.9 `dynamic_requests` in Pine V6 | 822–835 | 13.9, dynamic_requests, pine |  |
| 3 | 13.10 Visual primitives | 836–843 | 13.10, visual, primitives |  |
| 2 | 14. SILENT-RISK PATTERNS | 844–845 | silent-risk, patterns | pine-review |
| 3 | 14.1 `=` versus `:=` | 846–851 | 14.1, versus |  |
| 3 | 14.2 Classification scope | 852–857 | 14.2, classification, scope |  |
| 3 | 14.3 Priority cascade | 858–863 | 14.3, priority, cascade |  |
| 3 | 14.4 UDT fields | 864–867 | 14.4, fields |  |
| 3 | 14.5 Stateful functions in a conditional scope | 868–871 | 14.5, stateful, functions, conditional, scope |  |
| 3 | 14.6 Persistent state in a request | 872–879 | 14.6, persistent, state, request |  |
| 2 | 15. USE OF MODERN V6 FEATURES | 880–893 | modern, features | pine-develop |
| 2 | 16. CODE ARCHITECTURE | 894–895 | code, architecture | pine-develop, pine-review |
| 3 | 16.1 Numbered sections — MANDATORY WHEN A SIGNIFICANT SECTION EXISTS | 896–915 | 16.1, numbered, sections, mandatory, significant, section, exists |  |
| 3 | 16.2 Dependency order — DEFAULT | 916–923 | 16.2, dependency, order, default |  |
| 3 | 16.3 Input groups | 924–929 | 16.3, input, groups |  |
| 3 | 16.4 Line wrapping — PERSONAL CONVENTION | 930–939 | 16.4, line, wrapping, personal, convention |  |
| 2 | 17. NAMING | 940–941 | naming | pine-review |
| 3 | 17.1 Syntactic form of identifiers — TRADINGVIEW STYLE GUIDE | 942–949 | 17.1, syntactic, form, identifiers, tradingview, style, guide |  |
| 3 | 17.2 Current semantics — MANDATORY PERSONAL CONVENTION | 950–959 | 17.2, current, semantics, mandatory, personal, convention |  |
| 3 | 17.3 Descriptive suffixes | 960–965 | 17.3, descriptive, suffixes |  |
| 3 | 17.4 Legacy | 966–973 | 17.4, legacy |  |
| 2 | 18. PRODUCT DESIGN | 974–975 | product, design | pine-new |
| 3 | 18.1 Opinionated product — DEFAULT | 976–981 | 18.1, opinionated, product, default |  |
| 3 | 18.2 Perceptible feature — MANDATORY | 982–987 | 18.2, perceptible, feature, mandatory |  |
| 3 | 18.3 Automatic adaptation — DEFAULT | 988–995 | 18.3, automatic, adaptation, default |  |
| 2 | 19. SETTINGS UX | 996–997 | settings | pine-new, pine-review |
| 3 | 19.1 Hierarchy — MANDATORY | 998–1003 | 19.1, hierarchy, mandatory |  |
| 3 | 19.2 Tree prefixes — OPTIONAL | 1004–1009 | 19.2, tree, prefixes, optional |  |
| 3 | 19.3 `active=` cascade — MANDATORY IF APPLICABLE | 1010–1027 | 19.3, active, cascade, mandatory, applicable |  |
| 2 | 20. SETTINGS TOOLTIPS | 1028–1033 | settings, tooltips | pine-develop, pine-review |
| 3 | 20.1 Documentation — MANDATORY | 1034–1043 | 20.1, documentation, mandatory |  |
| 3 | 20.2 Numeric input | 1044–1051 | 20.2, numeric, input |  |
| 3 | 20.3 Toggle | 1052–1055 | 20.3, toggle |  |
| 3 | 20.4 Source | 1056–1059 | 20.4, source |  |
| 3 | 20.5 Choice / enum | 1060–1063 | 20.5, choice, enum |  |
| 3 | 20.6 Timeframe | 1064–1067 | 20.6, timeframe |  |
| 3 | 20.7 Session | 1068–1071 | 20.7, session |  |
| 3 | 20.8 Color | 1072–1075 | 20.8, color |  |
| 3 | 20.9 Symbol | 1076–1079 | 20.9, symbol |  |
| 3 | 20.10 Time / Price | 1080–1087 | 20.10, time, price |  |
| 2 | 21. SETTINGS VALIDATION | 1088–1101 | settings, validation | pine-develop |
| 2 | 22. USER-FACING TERMINOLOGY | 1102–1111 | user-facing, terminology | pine-review, pine-release |
| 3 | 22.1 Acronyms | 1112–1121 | 22.1, acronyms |  |
| 3 | 22.2 Useful and actionable text | 1122–1129 | 22.2, useful, actionable, text |  |
| 3 | 22.3 Versions and licences | 1130–1139 | 22.3, versions, licences |  |
| 2 | 23. VISUAL ELEMENT TOOLTIPS | 1140–1145 | visual, element, tooltips | pine-develop, pine-review |
| 3 | 23.1 Fundamental difference | 1146–1153 | 23.1, fundamental, difference |  |
| 3 | 23.2 Labels | 1154–1161 | 23.2, labels |  |
| 3 | 23.3 Tables and dashboards | 1162–1173 | 23.3, tables, dashboards |  |
| 3 | 23.4 Level of obligation | 1174–1183 | 23.4, level, obligation |  |
| 2 | 24. COMMENTS AND INTERNAL DOCUMENTATION | 1184–1185 | comments, internal, documentation | pine-develop, pine-review, guard (no-worklog-comments) |
| 3 | 24.1 Annotations | 1186–1189 | 24.1, annotations |  |
| 3 | 24.2 Comment on the why | 1190–1195 | 24.2, comment |  |
| 3 | 24.3 No wall of comments — MANDATORY | 1196–1205 | 24.3, wall, comments, mandatory |  |
| 3 | 24.4 Synchronized comments — MANDATORY | 1206–1211 | 24.4, synchronized, comments, mandatory |  |
| 3 | 24.5 What does not live in the source — MANDATORY | 1212–1224 | 24.5, does, live, source, mandatory |  |
| 2 | 25. NUMERICAL ROBUSTNESS AND EDGE CASES | 1225–1226 | numerical, robustness, edge, cases | pine-develop, pine-review |
| 3 | 25.1 Division — MANDATORY IF APPLICABLE | 1227–1244 | 25.1, division, mandatory, applicable |  |
| 3 | 25.2 Scores | 1245–1254 | 25.2, scores |  |
| 3 | 25.3 History | 1255–1258 | 25.3, history |  |
| 3 | 25.4 Drawing coordinates | 1259–1264 | 25.4, drawing, coordinates |  |
| 3 | 25.5 Format of prices and values — MANDATORY IF APPLICABLE | 1265–1278 | 25.5, format, prices, values, mandatory, applicable |  |
| 3 | 25.6 Debugging | 1279–1286 | 25.6, debugging |  |
| 2 | 26. EVENTS, STATES AND `ta.valuewhen()` | 1287–1310 | events, states, ta.valuewhen | pine-develop, pine-review |
| 2 | 27. MTF, HISTORY, REALTIME AND REPAINT | 1311–1312 | history, realtime, repaint | pine-develop, tv-validate |
| 3 | 27.1 General principle | 1313–1318 | 27.1, general, principle |  |
| 3 | 27.2 Anti-repaint — MANDATORY | 1319–1326 | 27.2, anti-repaint, mandatory |  |
| 3 | 27.3 `lookahead` and future leak — MANDATORY IF APPLICABLE | 1327–1345 | 27.3, lookahead, future, leak, mandatory, applicable |  |
| 3 | 27.4 Detecting a new HTF bar | 1346–1351 | 27.4, detecting |  |
| 3 | 27.5 `varip` | 1352–1357 | 27.5, varip |  |
| 3 | 27.6 MTF scaling | 1358–1365 | 27.6, scaling |  |
| 2 | 28. PERFORMANCE AND RESOURCES | 1366–1371 | performance, resources | pine-develop, pine-research |
| 3 | 28.1 TradingView limits | 1372–1377 | 28.1, tradingview, limits |  |
| 3 | 28.2 Drawing objects | 1378–1385 | 28.2, drawing, objects |  |
| 3 | 28.3 `barstate.islast` | 1386–1393 | 28.3, barstate.islast |  |
| 3 | 28.4 Complexity | 1394–1401 | 28.4, complexity |  |
| 3 | 28.5 `max_bars_back` | 1402–1409 | 28.5, max_bars_back |  |
| 2 | 29. VISUAL ELEMENTS — APPLICABILITY | 1410–1421 | visual, elements, applicability | pine-new, pine-review |
| 2 | 30. PALETTE AND VISUAL IDENTITY | 1422–1423 | palette, visual, identity | pine-new, pine-review |
| 3 | 30.1 Dark + light — MANDATORY IF VISUAL ELEMENTS EXIST | 1424–1429 | 30.1, dark, light, mandatory, visual, elements, exist |  |
| 3 | 30.2 Professional colours — DEFAULT | 1430–1460 | 30.2, professional, colours, default |  |
| 3 | 30.3 Visual hierarchy — MANDATORY IF APPLICABLE | 1461–1468 | 30.3, visual, hierarchy, mandatory, applicable |  |
| 3 | 30.4 Transparency — DEFAULT | 1469–1476 | 30.4, transparency, default |  |
| 3 | 30.5 Configurable colours | 1477–1488 | 30.5, configurable, colours |  |
| 3 | 30.6 Cross-script consistency | 1489–1496 | 30.6, cross-script, consistency |  |
| 2 | 31. SEMANTIC VERSIONING | 1497–1508 | semantic, versioning | pine-release, guard |
| 3 | 31.1 Fundamental principle | 1509–1514 | 31.1, fundamental, principle |  |
| 3 | 31.2 MAJOR | 1515–1518 | 31.2, major |  |
| 3 | 31.3 MINOR | 1519–1522 | 31.3, minor |  |
| 3 | 31.4 PATCH | 1523–1526 | 31.4, patch |  |
| 3 | 31.5 Bugfix that can change the outputs | 1527–1536 | 31.5, bugfix, change, outputs |  |
| 3 | 31.6 Beta | 1537–1542 | 31.6, beta |  |
| 3 | 31.7 Paid script and breaking change | 1543–1548 | 31.7, paid, script, breaking, change |  |
| 2 | 32. CHANGELOG | 1549–1565 | changelog | pine-release, pine-github |
| 3 | 32.1 Common rules | 1566–1583 | 32.1, common, rules |  |
| 3 | 32.2 Closed source (COMMERCIAL, PRIVATE, FREE with closed source) | 1584–1593 | 32.2, closed, source, commercial, private, free, closed, source |  |
| 3 | 32.3 FREE profile with public source | 1594–1601 | 32.3, free, profile, public, source |  |
| 2 | 33. USER TUTORIAL | 1602–1607 | user, tutorial | pine-docs, pine-release |
| 3 | 33.1 Common rules | 1608–1617 | 33.1, common, rules |  |
| 3 | 33.2 "Premium" convention (default for COMMERCIAL and PRIVATE) | 1618–1646 | 33.2, premium, convention, default, commercial, private |  |
| 3 | 33.3 "Documentary" convention (default for FREE) | 1647–1673 | 33.3, documentary, convention, default, free |  |
| 3 | 33.4 Tutorial review | 1674–1679 | 33.4, tutorial, review |  |
| 2 | 34. TRADINGVIEW PUBLICATION | 1680–1689 | tradingview, publication | pine-release, tv-validate |
| 3 | 34.1 Common rules | 1690–1699 | 34.1, common, rules |  |
| 3 | 34.2 FREE profile with public source | 1700–1712 | 34.2, free, profile, public, source |  |
| 3 | 34.3 Closed source (COMMERCIAL, published PRIVATE, FREE with closed source) | 1713–1726 | 34.3, closed, source, commercial, published, private, free, closed, source |  |
| 3 | 34.4 Paid publication mode — MANDATORY | 1727–1754 | 34.4, paid, publication, mode, mandatory |  |
| 3 | 34.5 Publication chart — MANDATORY | 1755–1770 | 34.5, publication, chart, mandatory |  |
| 3 | 34.6 Publication benchmark | 1771–1778 | 34.6, publication, benchmark |  |
| 2 | 35. PRE-RELEASE TESTS | 1779–1786 | pre-release, tests | pine-release, tv-validate |
| 3 | 35.1 Symbols | 1787–1792 | 35.1, symbols |  |
| 3 | 35.2 Timeframes | 1793–1796 | 35.2, timeframes |  |
| 3 | 35.3 Modes | 1797–1802 | 35.3, modes |  |
| 3 | 35.4 Display | 1803–1806 | 35.4, display |  |
| 3 | 35.5 Performance | 1807–1810 | 35.5, performance |  |
| 3 | 35.6 Repaint | 1811–1816 | 35.6, repaint |  |
| 3 | 35.7 Alerts | 1817–1820 | 35.7, alerts |  |
| 3 | 35.8 Extreme settings | 1821–1824 | 35.8, extreme, settings |  |
| 3 | 35.9 Atypical instruments | 1825–1828 | 35.9, atypical, instruments |  |
| 3 | 35.10 Release with a known bug | 1829–1836 | 35.10, release, known |  |
| 2 | 36. POST-CODE REVIEW — FOUR AXES | 1837–1840 | post-code, review, four, axes | pine-review, pine-audit |
| 3 | AXIS 1 — CONTEXTUAL INTEGRITY | 1841–1848 | axis, contextual, integrity |  |
| 3 | AXIS 2 — DEPENDENT ARTEFACTS | 1849–1854 | axis, dependent, artefacts |  |
| 3 | AXIS 3 — APPLICABLE CONVENTIONS | 1855–1862 | axis, applicable, conventions |  |
| 3 | AXIS 4 — FRESH EYES | 1863–1878 | axis, fresh, eyes |  |
| 2 | 37. ANTI-PATTERNS | 1879–1880 | anti-patterns | pine-review, guard |
| 3 | 37.1 Inventing a fact | 1881–1886 | 37.1, inventing, fact |  |
| 3 | 37.2 Fictitious research | 1887–1890 | 37.2, fictitious, research |  |
| 3 | 37.3 Scope creep | 1891–1898 | 37.3, scope, creep |  |
| 3 | 37.4 Unnecessary rewrite | 1899–1902 | 37.4, unnecessary, rewrite |  |
| 3 | 37.5 Franglais | 1903–1906 | 37.5, franglais |  |
| 3 | 37.6 User-facing internals | 1907–1910 | 37.6, user-facing, internals |  |
| 3 | 37.7 Contradictory old conventions | 1911–1916 | 37.7, contradictory, conventions |  |
| 3 | 37.8 Primary built-in colours by default | 1917–1920 | 37.8, primary, built-in, colours, default |  |
| 3 | 37.9 API hallucination | 1921–1924 | 37.9, hallucination |  |
| 3 | 37.10 Inheritance from another script | 1925–1928 | 37.10, inheritance, another, script |  |
| 3 | 37.11 HTF modulo | 1929–1932 | 37.11, modulo |  |
| 3 | 37.12 `var` for a constant | 1933–1936 | 37.12, var, constant |  |
| 3 | 37.13 Side effects in `and` / `or` | 1937–1940 | 37.13, side, effects, and, or |  |
| 3 | 37.14 Copying from the benchmark | 1941–1948 | 37.14, copying, benchmark |  |
| 3 | 37.15 `shorttitle` | 1949–1954 | 37.15, shorttitle |  |
| 3 | 37.16 Product version outside the header | 1955–1958 | 37.16, product, version, outside, header |  |
| 3 | 37.17 Future leak | 1959–1962 | 37.17, future, leak |  |
| 3 | 37.18 Unauthorized paid publication | 1963–1966 | 37.18, unauthorized, paid, publication |  |
| 3 | 37.19 Work log in the source | 1967–1972 | 37.19, work, source |  |
| 2 | 38. WORKFLOW — EXISTING SCRIPT | 1973–2003 | workflow, existing, script | pine-develop |
| 2 | 39. WORKFLOW — NEW SCRIPT | 2004–2038 | workflow, script | pine-new |
| 2 | 40. TRADINGVIEW VALIDATION | 2039–2056 | tradingview, validation | tv-validate |
| 2 | 41. RELEASE DELIVERABLES | 2057–2070 | release, deliverables | pine-release, pine-github |
| 2 | 42. COMPLETION STANDARD | 2071–2138 | completion, standard | pine-develop, pine-release |

