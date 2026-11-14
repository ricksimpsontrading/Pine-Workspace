# TRACEABILITY — Master standard → workspace operationalization

Status: derived, architectural, non-normative (spec §13). Regeneration: human/Claude semantic analysis, never a simple parser.
Master: standards/PINE_SCRIPT_V6_STANDARD.md — SHA-256 2a4e0dc62fe4fc749b94982af88c2b8c33cb4a9ffd2400ee206d5007ac9e2987
Generated on: 2026-09-04. Reviewed on: 2026-09-27 (proportionate re-readings); 2026-11-06 (neutral edition, licence profiles §5–§6, verification levels §9.1/§36/§38, comments §24.5, tutorial §33, deliverables §41, URLs §6.5); 2026-11-06, verification intervention (separate publication dimensions §5, declared legal reference §6.5, no automatic triggering by task class §2.3/§9.1/§11/§36/§38); 2026-11-13 (authorized amendment of §9.2 "Re-reading after modification": targeted re-reading according to the level and the class, consolidated global coverage in publication preparation only; correspondences of the §9 row unchanged). 2026-11-13, licences of imported scripts (holder's decision: §5 existing licence kept, §6 original header and copyright lines of the original authors; §5 and §6 rows completed; clarification of the same day: an imported CC licence requires a public source). 2026-11-14: English translation of the master and of this file (faithful: statuses, section numbers and correspondences unchanged); master §4.1 amended with the language rule ratified by the holder; §4 row completed (session-start summary); "re-reading" (§9.2) kept distinct from "review" (§36) after the cross-check; record of ratified amendments in the master header completed with 2026-11-13 (correspondences unchanged). If the SHA of the master changes, this file is STALE until review.

Real dependencies of this document: the master (SHA above, the only mechanical freshness dependency); the bootstrap spec for the "spec §…" references (amendment of 2026-11-06); the skills, rules, agents and tooling modules cited (checked at the review date). A change in the latter is not detected mechanically: it calls for a review of this file, not an automatic declaration of staleness.

Format per section: context/rule → skill(s) → agent, if any → deterministic check, if any → local behavioural execution, if any → empirical validation, if any.
"—" = no dedicated mechanism necessary (the section lives through direct consultation of the master via INDEX).

| § Master | Title | Rule / context | Skill(s) | Agent | Deterministic check | Local behavioural | TV empirical |
|---|---|---|---|---|---|---|---|
| 0 | Mission (holder) | CLAUDE.md (authorities reminder) | all pine-* workflows | — | — | — | — |
| 1 | Normative statuses / applicability | CLAUDE.md; all skills recall N/A ≠ to invent | pine-develop, pine-review | pws-pine-reviewer | — | — | — |
| 2 | Task classes (all at level 1 except requested audit / publication) | — | pine-develop (classification in step 2), pine-audit (on request) | — | — | proportionate pine-local-test depth (only if planned) | proportionate tv-validate matrix |
| 3 | Technical authority / conflicts | CLAUDE.md (roles of the sources) | pine-research (official doc check) | pws-pine-researcher | — | — | — |
| 4 | Languages (configured language with the holder, reference documentation and code in EN) | CLAUDE.md; `pws.config.json` (`language`); session-start summary (explicit language line, `session.py`) | all (language directive); localized menu (`menu.py`, `i18n.py`) | all (report in the language of the mission) | `config`: language validated | — | — |
| 5 | Licence profiles, axes, existing licence of imported scripts and publication dimensions (state / privacy / mode) | script-context.md | pine-new (profile), pine-onboard (existing licence proposed then confirmed), pine-license (`confirm --license-id`), pine-docs, pine-release | — | scan + `profiles.py`: schema 3 (`origin`/`status` extension), consistency of the axes (§45.4), imported licence (closed list, "to analyse"), v1/v2 derived and flagged; `license status`, `license detect` | — | — |
| 6 | Header, product version, licence, URLs (6.5) | pine-source.md | pine-new, pine-develop, pine-release; `license render` (templates) | — | guard: header according to the licence and the configured identity (`header-structure`, `header-copyright`; imported licence: original notice present and consistent), `// Version:` in the header region, `//@version=6`, shorttitle, ASCII title, licence URL in a comment only + declared legal reference `terms_url` by exact match (`no-promo-urls`, `cc-url-placement`) | — | — |
| 7 | Pine research before code | research.md | pine-research, pine-develop (step 5) | pws-pine-researcher | — | — | — |
| 8 | Benchmark, original creation (8.5) | research.md | pine-research (corpus, boundary, originality) | pws-pine-researcher | — | — | — |
| 9 | Mapping and three verification levels (9.1), re-reading (9.2) | pine-source.md (reminder) | pine-develop (targeted reading extended according to the class, step 3), pine-audit (level 2, on request), pine-release (level 3), pine-onboard (initial mapping, steps 3-5), pine-review (coverage reported) | pws-pine-cartographer (requested audit / onboarding), pws-pine-reviewer | — | — | — |
| 10 | Impact inventory | — | pine-develop (step 4) | — | — | targeted regression comparisons | — |
| 11 | Modification methodology | pine-source.md (workflow reminder) | pine-develop (diff + §9.2 re-reading; review according to level) | — | — | — | — |
| 12 | Pine V6 compatibility | pine-source.md | pine-develop, pine-research (migration) | pws-pine-researcher | guard: //@version=6 | — | migration tests if applicable |
| 13 | Pine V6 invariants | pine-source.md (routing) | pine-develop, pine-review | pws-pine-reviewer | — (semantic) | targeted observations possible | real validation |
| 14 | Silent-risk patterns | — | pine-review (checklist) | pws-pine-reviewer | — | comparable regressions | — |
| 15 | Modern V6 features | — | pine-develop, pine-research | pws-pine-researcher | — | — | — |
| 16 | Code architecture | pine-source.md (reminder) | pine-develop, pine-review | pws-pine-reviewer | — | — | — |
| 17 | Naming | — | pine-review | pws-pine-reviewer | — | — | — |
| 18 | Product design | script-context.md | pine-new (product design) | — | — | — | — |
| 19 | Settings UX | — | pine-new, pine-develop, pine-review | pws-pine-reviewer | — | — | real settings test |
| 20 | Settings tooltips | documentation.md (routing) | pine-develop, pine-review | pws-pine-reviewer | — | — | real rendering |
| 21 | Settings validation | — | pine-develop | — | — | runtime.error observable locally according to capabilities | extreme settings test |
| 22 | User-facing terminology | documentation.md | pine-review, pine-docs, pine-release | pws-pine-reviewer, pws-release-reviewer | guard: no URL in user texts | — | — |
| 23 | Visual element tooltips | documentation.md (routing) | pine-develop, pine-review | pws-pine-reviewer | — | — | real rendering |
| 24 | Comments, what does not live in the source (24.5) | pine-source.md | pine-develop, pine-review | pws-pine-reviewer (scan 37.19) | guard: `no-worklog-comments` (WARNING) | — | — |
| 25 | Numerical robustness / edge cases | — | pine-develop, pine-review | pws-pine-reviewer | — | edge cases observable on controlled datasets | — |
| 26 | Events vs states, ta.valuewhen | — | pine-develop, pine-review | pws-pine-reviewer | — | event vs state observation possible | — |
| 27 | MTF / history / realtime / repaint | pine-source.md (3-layer reminder) | pine-develop, tv-validate | pws-pine-reviewer | — | according to capabilities (never universal evidence of non-repaint) | real historical/realtime/Replay |
| 28 | Performance / resources | — | pine-develop, pine-research (current limits) | pws-pine-researcher | — | — | real Profiler / loading |
| 29 | Visual elements — applicability | — | pine-new, pine-review | pws-pine-reviewer | — | — | — |
| 30 | Palette / visual identity | documentation.md (routing) | pine-new, pine-review | pws-pine-reviewer | — | — | real dark + light |
| 31 | SemVer | release.md | pine-release (real impact) | pws-release-reviewer | guard: Version X.Y.Z in the header; version absent outside the source (spec §56) | — | — |
| 32 | Changelog (complete with the product, exported via GitHub) | release.md | pine-release, pine-github | pws-release-reviewer | — | — | — |
| 33 | Tutorial (can be prepared at any time, same quality model) | documentation.md, release.md | pine-docs, pine-release (review 33.4) | pws-release-reviewer | — | — | — |
| 34 | TradingView publication | release.md | pine-release (current rules re-checked), tv-validate | pws-release-reviewer | — | — | real chart + publication (never automated) |
| 35 | Pre-release tests | release.md | pine-release, tv-validate | — | — | applicable behavioural tests | real pre-release matrix |
| 36 | Post-code review, 4 axes (according to level) | — | pine-develop (self-review in routine work, all classes), pine-review (independent: requested audit, publication, holder's request — never triggered by the class of the task) | pws-pine-reviewer | — | — | — |
| 37 | Anti-patterns (37.19: work log) | pine-source.md (reminder) | pine-review (scan) | pws-pine-reviewer | guard: 37.15 shorttitle, 37.16 version outside the header, 37.19 work-log comments | — | — |
| 38 | Existing script workflow (levels) | — | pine-develop (orchestration), pine-audit | according to level | guard + scan | pine-local-test only if planned | tv-validate |
| 39 | New script workflow | — | pine-new (orchestration; profile) | all | guard + scan | pine-local-test according to applicability | tv-validate |
| 40 | TradingView validation | validation.md | tv-validate | — | validation-status (stale, integrity; null author admitted for not-run/n-a) | never a substitute (spec §29.5) | YES — final authority |
| 41 | Release deliverables (no website; configured GitHub destination) | release.md | pine-release, pine-github | pws-release-reviewer | `github export-plan`: list of allowed contents | — | — |
| 42 | Completion standard | CLAUDE.md (reminder) | pine-develop, pine-release | — | — | — | real validation required |

## Reverse checks (mechanisms → master)

- guard (tools/pws_workspace/guard.py) applies only: master §6 (headers according to the licence and the configured identity, version in the header region, title, shorttitle, URLs §6.5), §12 (//@version=6), §24.5/§37.19 (warning), §37.15, §37.16 + machine contracts of the spec (§45). Everything else in the master is semantic → workflows + reviewer.
- profiles.py / scan applies master §5 and spec §45.4 (profiles, axes, consistency rules, open-source library); licensing.py renders the templates of master §6 and of the terms (`docs/licensing/templates/`).
- pine-local-test applies no rule of the master: it observes behaviour (spec §24.4). The master remains the design authority.
- No section of the master is copied into rules/skills/agents; routing only (spec §2.1, §54).

## Sections without a dedicated mechanism (deliberate choice)

§10, §14, §15, §17, §21, §25-26, §28-29: carried by the pine-develop / pine-review / pine-audit workflows and the fresh-context reviewer; no reliable mechanical check exists for these requirements (spec §37.3, §38.3).
