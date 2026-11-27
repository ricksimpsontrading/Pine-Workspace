# SPDX-License-Identifier: Apache-2.0
"""User-facing message catalogue (fr / en).

One workflow logic, translated resources: menus, the SessionStart summary,
the doctor table headings and the human outputs of the maintenance
subcommands are localized. Identifiers, JSON keys, finding codes and
check names are stable technical contracts and are never translated.

Menu texts (revised 2026-11-06 after the holder's walkthrough): a plain
label plus a short description of the purpose or effect; internal names
(skills, commands, arguments, hashes, standard sections) stay out of the
visible texts and belong to the instructions and detailed results.
"""

LANGUAGES = ("en", "fr")
DEFAULT_LANGUAGE = "en"

_CATALOGUE = {
    # ---- generic -----------------------------------------------------------
    "back": {"en": "Back", "fr": "Retour"},
    "more": {"en": "More…", "fr": "Suite…"},
    "cancel": {"en": "Cancel", "fr": "Annuler"},
    "start": {"en": "Start", "fr": "Démarrer"},
    "modify": {"en": "Modify", "fr": "Modifier"},
    "yes": {"en": "Yes", "fr": "Oui"},
    "no": {"en": "No", "fr": "Non"},
    # ---- menu: first level -------------------------------------------------
    "menu.title": {"en": "PWS menu", "fr": "Menu PWS"},
    "menu.question": {"en": "What would you like to do?", "fr": "Que souhaitez-vous faire ?"},
    "menu.work": {"en": "Work on a script", "fr": "Travailler sur un script"},
    "menu.work.desc": {"en": "Choose the action first, then the script.",
                       "fr": "Choisir l'action d'abord, puis le script."},
    "menu.new": {"en": "New / import", "fr": "Nouveau / importer"},
    "menu.new.desc": {"en": "Create a new script or bring an existing one into the workspace.",
                      "fr": "Créer un nouveau script ou intégrer un script existant."},
    "menu.quality": {"en": "Quality / publication", "fr": "Qualité / publication"},
    "menu.quality.desc": {"en": "Local tests, TradingView validation, licence and terms, publication preparation, GitHub export.",
                          "fr": "Tests locaux, validation TradingView, licence et conditions, préparation d'une publication, export GitHub."},
    "menu.maintenance": {"en": "Maintenance / configuration", "fr": "Maintenance / configuration"},
    "menu.maintenance.desc": {"en": "Diagnostic, detailed state, configuration, tools, archives.",
                              "fr": "Diagnostic, état détaillé, configuration, outils, archives."},
    # ---- menu: work on a script -------------------------------------------
    "menu.work.develop": {"en": "Develop / fix", "fr": "Développer / corriger"},
    "menu.work.develop.desc": {"en": "Modify or fix an existing script.",
                               "fr": "Modifier ou corriger un script existant."},
    "menu.work.docs": {"en": "Documentation / tutorial", "fr": "Documentation / tutoriel"},
    "menu.work.docs.desc": {"en": "Prepare or update the user documentation and tutorial, at any time.",
                            "fr": "Préparer ou mettre à jour la documentation et le tutoriel, à tout moment."},
    "menu.work.research": {"en": "Research", "fr": "Recherche"},
    "menu.work.research.desc": {"en": "Check current Pine and TradingView documentation and compare with existing work.",
                                "fr": "Vérifier la documentation Pine et TradingView actuelle et comparer avec l'existant."},
    "menu.work.review": {"en": "Review", "fr": "Revue"},
    "menu.work.review.desc": {"en": "Independent re-reading of the script, on request only. Changes nothing.",
                              "fr": "Relecture indépendante du script, sur demande seulement. Ne modifie rien."},
    "menu.work.audit": {"en": "Deep audit", "fr": "Audit approfondi"},
    "menu.work.audit.desc": {"en": "Complete examination of the script; its scope is announced before it runs. On request only.",
                             "fr": "Examen complet du script ; le périmètre est annoncé avant exécution. Sur demande seulement."},
    # ---- menu: new / import ------------------------------------------------
    "menu.new.script": {"en": "New script", "fr": "Nouveau script"},
    "menu.new.script.desc": {"en": "Create a script from scratch: type, profile, summary, then start. Nothing is created before Start.",
                             "fr": "Créer un script de zéro : type, profil, récapitulatif, puis démarrage. Rien n'est créé avant Démarrer."},
    "menu.new.import": {"en": "Import a script", "fr": "Importer un script"},
    "menu.new.import.desc": {"en": "Bring an existing Pine script into the workspace.",
                             "fr": "Intégrer un script Pine existant dans le workspace."},
    # ---- menu: quality / publication --------------------------------------
    "menu.quality.local": {"en": "Local test (PineTS)", "fr": "Test local (PineTS)"},
    "menu.quality.local.desc": {"en": "Observe the script's behaviour locally. Not a TradingView validation.",
                                "fr": "Observer le comportement du script en local. Ne vaut pas une validation TradingView."},
    "menu.quality.tv": {"en": "TradingView validation", "fr": "Validation TradingView"},
    "menu.quality.tv.desc": {"en": "Check the script on TradingView and record the evidence.",
                             "fr": "Vérifier le script sur TradingView et enregistrer la preuve."},
    "menu.quality.license": {"en": "Licence and terms of use", "fr": "Licence et conditions d'utilisation"},
    "menu.quality.license.desc": {"en": "View, complete and preview the licence and terms of a script. Independent of publication; nothing is saved without your confirmation.",
                                  "fr": "Consulter, compléter et prévisualiser la licence et les conditions d'un script. Indépendant de la publication ; rien n'est enregistré sans votre confirmation."},
    "menu.quality.release": {"en": "Prepare a publication", "fr": "Préparer une publication"},
    "menu.quality.release.desc": {"en": "Prepare the documents and checks of a publication. Publishes nothing.",
                                  "fr": "Préparer les documents et les vérifications d'une publication. Ne publie rien."},
    "menu.quality.github": {"en": "GitHub export", "fr": "Export GitHub"},
    "menu.quality.github.desc": {"en": "Check the connection and destinations, prepare and preview an export. Sending stays subject to your authorization.",
                                 "fr": "Consulter la connexion et les destinations, préparer et prévisualiser un export. L'envoi reste soumis à votre autorisation."},
    # ---- menu: maintenance / configuration --------------------------------
    "menu.maintenance.doctor": {"en": "Workspace diagnostic", "fr": "Diagnostic du workspace"},
    "menu.maintenance.doctor.desc": {"en": "Check the workspace health. Read-only: nothing is repaired automatically.",
                                     "fr": "Vérifier l'état du workspace. Lecture seule : rien n'est réparé automatiquement."},
    "menu.maintenance.status": {"en": "Detailed state", "fr": "État détaillé"},
    "menu.maintenance.status.desc": {"en": "Show the detailed state: language, TradingView mode, products, pending migrations.",
                                     "fr": "Afficher l'état détaillé : langue, mode TradingView, produits, migrations en attente."},
    "menu.maintenance.config": {"en": "Configuration", "fr": "Configuration"},
    "menu.maintenance.config.desc": {"en": "Language, copyright holder, default profile, TradingView mode, GitHub destinations, startup cleanup.",
                                     "fr": "Langue, identité du titulaire, profil par défaut, mode TradingView, destinations GitHub, entretien au lancement."},
    "menu.maintenance.tools": {"en": "Tools and updates", "fr": "Outils et mises à jour"},
    "menu.maintenance.tools.desc": {"en": "PineTS on one side, the update of Pine-Workspace itself on the other.",
                                    "fr": "PineTS d'un côté, la mise à jour de Pine-Workspace lui-même de l'autre."},
    "menu.tools.pinets": {"en": "PineTS", "fr": "PineTS"},
    "menu.tools.pinets.desc": {"en": "Guided update of PineTS: state, search, plan, one confirmation, install, checks and recalibration; return to a saved version.",
                               "fr": "Mise à jour guidée de PineTS : état, recherche, plan, une confirmation, installation, vérifications et recalibration ; retour à une version sauvegardée."},
    "menu.tools.vela": {"en": "Vela (browser chart)", "fr": "Vela (graphique du navigateur)"},
    "menu.tools.vela.desc": {"en": "Guided update of Vela: state, search, changes and licences, verified plan, one confirmation, offline install, checks; return to a saved version.",
                             "fr": "Mise à jour guidée de Vela : état, recherche, changements et licences, plan vérifié, une confirmation, installation hors ligne, vérifications ; retour à une version sauvegardée."},
    "menu.tools.update": {"en": "Update Pine-Workspace", "fr": "Mettre à jour Pine-Workspace"},
    "menu.tools.update.desc": {"en": "Guided update: state, search, changes, verified plan, one confirmation, application and summary. Nothing is applied without your confirmation.",
                               "fr": "Mise à jour guidée : état, recherche, changements, plan vérifié, une confirmation, application et bilan. Rien n'est appliqué sans votre confirmation."},
    "menu.maintenance.archives": {"en": "Archives and cleanup", "fr": "Archives et nettoyage"},
    "menu.maintenance.archives.desc": {"en": "Cleanup of recreatable temporary files and import of archives.",
                                       "fr": "Entretien des fichiers temporaires recréables et import d'archives."},
    # ---- menu: configuration settings -------------------------------------
    "menu.config.language": {"en": "Language", "fr": "Langue"},
    "menu.config.language.desc": {"en": "Language of the conversation and of the menus.",
                                  "fr": "Langue des échanges et des menus."},
    "menu.config.identity": {"en": "Copyright holder", "fr": "Identité du titulaire"},
    "menu.config.identity.desc": {"en": "Name of the copyright holder and the aliases accepted in headers.",
                                  "fr": "Nom du titulaire et alias acceptés dans les en-têtes."},
    "menu.config.profile": {"en": "Default profile", "fr": "Profil par défaut"},
    "menu.config.profile.desc": {"en": "Profile proposed first for a new script.",
                                 "fr": "Profil proposé en premier pour un nouveau script."},
    "menu.config.tvmode": {"en": "TradingView mode", "fr": "Mode TradingView"},
    "menu.config.tvmode.desc": {"en": "How TradingView validation is run: manually, or with the experimental Chrome mode.",
                                "fr": "Façon de valider sur TradingView : manuellement, ou avec le mode Chrome expérimental."},
    "menu.config.github": {"en": "GitHub destinations", "fr": "Destinations GitHub"},
    "menu.config.github.desc": {"en": "Repositories configured for exports. No automatic connection or publication.",
                                "fr": "Dépôts configurés pour les exports. Aucune connexion ni publication automatique."},
    "menu.config.cleanup": {"en": "Startup cleanup", "fr": "Entretien au lancement"},
    "menu.config.cleanup.desc": {"en": "Removal of recreatable temporary files when a session starts.",
                                 "fr": "Suppression des fichiers temporaires recréables au lancement d'une session."},
    "menu.config.keep": {"en": "Keep “{value}” (Back)", "fr": "Conserver « {value} » (Retour)"},
    "menu.config.unset": {"en": "not set", "fr": "non renseigné"},
    "menu.config.none": {"en": "none", "fr": "aucune"},
    "menu.language.en": {"en": "English", "fr": "English"},
    "menu.language.fr": {"en": "Français", "fr": "Français"},
    "menu.tvmode.manual": {"en": "Manual (default)", "fr": "Manuel (par défaut)"},
    "menu.tvmode.chrome-experimental": {"en": "Chrome experimental (optional)", "fr": "Chrome expérimental (optionnel)"},
    "menu.cleanup.on": {"en": "Enabled", "fr": "Activé"},
    "menu.cleanup.off": {"en": "Disabled", "fr": "Désactivé"},
    # ---- menu: scripts, kinds, profiles ------------------------------------
    "menu.script.single": {"en": "Script: {label}", "fr": "Script : {label}"},
    "menu.script.continue": {"en": "Continue with this script", "fr": "Continuer avec ce script"},
    "menu.script.choose": {"en": "Choose the script", "fr": "Choisir le script"},
    "menu.script.others": {"en": "Others…", "fr": "Autres…"},
    "menu.kind.indicator": {"en": "Indicator", "fr": "Indicateur"},
    "menu.kind.strategy": {"en": "Strategy", "fr": "Stratégie"},
    "menu.kind.library": {"en": "Library", "fr": "Bibliothèque"},
    "menu.profile.FREE": {"en": "FREE — public source, CC BY-NC-SA 4.0",
                          "fr": "FREE — source public, CC BY-NC-SA 4.0"},
    "menu.profile.FREE_CLOSED": {"en": "FREE with closed source — proprietary, free use granted",
                                 "fr": "FREE à source fermé — propriétaire, usage gratuit accordé"},
    "menu.profile.PRIVATE": {"en": "PRIVATE — proprietary, personal or limited sharing",
                             "fr": "PRIVATE — propriétaire, usage personnel ou partage limité"},
    "menu.profile.COMMERCIAL": {"en": "COMMERCIAL — proprietary, configurable EULA",
                                "fr": "COMMERCIAL — propriétaire, EULA configurable"},
    "menu.na.no_registered": {"en": "no ready script yet (create or import one first)",
                              "fr": "aucun script prêt pour l'instant (en créer ou en importer un d'abord)"},
    "menu.profile.FREE.desc": {"en": "Free script, source visible, Creative Commons non-commercial licence.",
                               "fr": "Script gratuit, source visible, licence Creative Commons non commerciale."},
    "menu.profile.FREE_CLOSED.desc": {"en": "Free script, source hidden, free use granted by you.",
                                      "fr": "Script gratuit, source masqué, usage gratuit accordé par vous."},
    "menu.profile.PRIVATE.desc": {"en": "Script for your own use or a limited circle, source hidden.",
                                  "fr": "Script pour votre usage ou un cercle restreint, source masqué."},
    "menu.profile.COMMERCIAL.desc": {"en": "Paid script, source hidden, terms set by an EULA.",
                                     "fr": "Script payant, source masqué, conditions fixées par un contrat (EULA)."},
    "menu.tvmode.invalid": {"en": "invalid value ({value}) — choose a mode", "fr": "valeur invalide ({value}) — choisir un mode"},
    "menu.na.no_product": {"en": "no product", "fr": "aucun produit"},
    "menu.na.library_profile": {"en": "a library is always FREE with public source (TradingView rule)",
                                "fr": "une bibliothèque est toujours FREE à source public (règle TradingView)"},
    # ---- guided path: licence and terms of use -----------------------------
    "license.group.product": {"en": "Product identification", "fr": "Identification du produit"},
    "license.group.provider": {"en": "Provider identity and contact", "fr": "Identité du fournisseur et contact"},
    "license.group.beneficiary": {"en": "Beneficiary or authorized account", "fr": "Bénéficiaire ou compte autorisé"},
    "license.group.commercial": {"en": "Commercial model and term", "fr": "Modèle commercial et durée"},
    "license.group.renewal": {"en": "Renewal and termination", "fr": "Renouvellement et résiliation"},
    "license.group.support": {"en": "Support", "fr": "Support"},
    "license.group.refunds": {"en": "Refunds", "fr": "Remboursements"},
    "license.group.law": {"en": "Governing law", "fr": "Droit applicable"},
    "license.group.additional": {"en": "Additional terms", "fr": "Autres conditions"},
    "license.field.PRODUCT_NAME": {"en": "Product name as written in the document",
                                   "fr": "Nom du produit tel qu'écrit dans le document"},
    "license.field.PROVIDER_LEGAL_NAME": {"en": "Legal name of the provider (may differ from the copyright holder)",
                                          "fr": "Identité juridique du fournisseur (peut différer du titulaire des droits)"},
    "license.field.PROVIDER_CONTACT": {"en": "Provider contact", "fr": "Contact du fournisseur"},
    "license.field.AUTHORIZED_ACCOUNT_RULE": {"en": "Rule for the authorized account or beneficiary",
                                              "fr": "Règle du compte ou du bénéficiaire autorisé"},
    "license.field.LICENSE_MODEL": {"en": "Licence model (subscription, fixed term…)",
                                    "fr": "Modèle de licence (abonnement, durée fixe…)"},
    "license.field.TERM_OR_PERIOD": {"en": "Term or period", "fr": "Durée ou période"},
    "license.field.ACCESS_CHANNEL": {"en": "Access channel", "fr": "Canal d'accès"},
    "license.field.PRICE_OR_PLAN_REFERENCE": {"en": "Price or plan reference (optional)",
                                              "fr": "Référence de prix ou d'offre (facultatif)"},
    "license.field.RENEWAL_TERMS": {"en": "Renewal terms", "fr": "Conditions de renouvellement"},
    "license.field.EXPIRY_AND_TERMINATION": {"en": "Expiry and termination", "fr": "Expiration et résiliation"},
    "license.field.SUPPORT_TERMS": {"en": "Support terms", "fr": "Conditions de support"},
    "license.field.REFUND_POLICY_REFERENCE": {"en": "Refund policy reference (optional)",
                                              "fr": "Référence de la politique de remboursement (facultatif)"},
    "license.field.GOVERNING_LAW_REFERENCE": {"en": "Governing law reference", "fr": "Référence du droit applicable"},
    "license.field.ADDITIONAL_TERMS": {"en": "Additional terms (optional)", "fr": "Conditions supplémentaires (facultatif)"},
    "license.doc.header-free": {"en": "Source header (CC BY-NC-SA 4.0)", "fr": "En-tête du source (CC BY-NC-SA 4.0)"},
    "license.doc.header-proprietary": {"en": "Source header (proprietary)", "fr": "En-tête du source (propriétaire)"},
    "license.doc.notice": {"en": "Proprietary notice", "fr": "Notice propriétaire"},
    "license.doc.grant": {"en": "Free-use grant", "fr": "Autorisation gratuite d'utilisation"},
    "license.doc.eula": {"en": "End-user licence agreement (EULA)", "fr": "Contrat de licence utilisateur (EULA)"},
    "license.role.header": {"en": "reference header for the source", "fr": "en-tête de référence du source"},
    "license.role.terms": {"en": "terms made available with the script", "fr": "conditions mises à disposition avec le script"},
    "license.role.permission": {"en": "optional particular permission", "fr": "autorisation particulière facultative"},
    "license.confirm.holder": {"en": "Copyright holder (configuration)", "fr": "Titulaire des droits (configuration)"},
    "license.confirm.created_year": {"en": "Creation year of the script", "fr": "Année de création du script"},
    "license.confirm.publication_state": {"en": "Publication state on TradingView (published or not)",
                                          "fr": "État de publication sur TradingView (publié ou non)"},
    "license.confirm.publication_privacy": {"en": "Privacy of the TradingView publication (public or private)",
                                            "fr": "Confidentialité de la publication TradingView (publique ou privée)"},
    "license.confirm.publication_mode": {"en": "TradingView script mode (open, protected, invite-only)",
                                         "fr": "Mode du script TradingView (ouvert, protégé, sur invitation)"},
    "license.confirm.terms_ref": {"en": "Terms document attached to the product",
                                  "fr": "Document de conditions rattaché au produit"},
    # ---- session summary ---------------------------------------------------
    # The configured language, stated explicitly at session start (never left
    # to be inferred from the language of this summary or of any file).
    "summary.language": {"en": "Configured language: en — menus, explanations, questions, confirmations and reports in English",
                         "fr": "Langue configurée : fr — menus, explications, questions, confirmations et comptes rendus en français"},
    "summary.git.local": {"en": "Git: local / branch {branch} / {state}{unborn}",
                          "fr": "Git : local / branche {branch} / {state}{unborn}"},
    "summary.git.none": {"en": "Git: not a repository (degraded mode: no local history)",
                         "fr": "Git : pas de dépôt (mode dégradé : aucun historique local)"},
    "summary.git.unavailable": {"en": "Git: not installed (degraded mode: no local history)",
                                "fr": "Git : non installé (mode dégradé : aucun historique local)"},
    "summary.dirty": {"en": "dirty", "fr": "modifié"},
    "summary.clean": {"en": "clean", "fr": "propre"},
    "summary.unborn": {"en": " / no commit yet", "fr": " / aucun commit"},
    "summary.remotes": {"en": " / remotes: {remotes}", "fr": " / remotes : {remotes}"},
    "summary.tvmode": {"en": "TradingView validation mode: {mode}{source}",
                       "fr": "Mode de validation TradingView : {mode}{source}"},
    "summary.tvmode.invalid": {"en": "TradingView validation mode: INVALID ({error})",
                               "fr": "Mode de validation TradingView : INVALIDE ({error})"},
    "summary.tvmode.default": {"en": " (default, not configured)", "fr": " (défaut, non configuré)"},
    "summary.tvmode.legacy": {"en": " (legacy settings.local.json — run migrate)",
                              "fr": " (ancien settings.local.json — lancer migrate)"},
    "summary.products": {"en": "Products: {registered} registered / {incomplete} incomplete / {broken} broken / {ambiguous} ambiguous",
                         "fr": "Produits : {registered} enregistré(s) / {incomplete} incomplet(s) / {broken} cassé(s) / {ambiguous} ambigu(s)"},
    "summary.unregistered": {"en": "Unregistered .pine: {n}", "fr": ".pine non enregistrés : {n}"},
    "summary.stale": {"en": "Stale TradingView validations: {n}",
                      "fr": "Validations TradingView périmées : {n}"},
    "summary.standard": {"en": "Master index: {index} / traceability: {traceability}",
                         "fr": "Index du master : {index} / traçabilité : {traceability}"},
    "summary.config.missing": {"en": "Configuration: pws.config.json missing — defaults apply (run: python3 -m tools.pws_workspace init)",
                               "fr": "Configuration : pws.config.json absent — valeurs par défaut (lancer : python3 -m tools.pws_workspace init)"},
    "summary.config.migrate": {"en": "Migration pending: {n} step(s) — python3 -m tools.pws_workspace migrate --plan",
                               "fr": "Migration en attente : {n} étape(s) — python3 -m tools.pws_workspace migrate --plan"},
    "summary.list.unregistered": {"en": "UNREGISTERED (required before substantive edits: pine-onboard)",
                                  "fr": "NON ENREGISTRÉS (requis avant toute édition substantielle : pine-onboard)"},
    "summary.list.stale": {"en": "STALE VALIDATIONS", "fr": "VALIDATIONS PÉRIMÉES"},
    "summary.list.broken": {"en": "BROKEN VALIDATION STATE", "fr": "ÉTAT DE VALIDATION CASSÉ"},
    "summary.list.stop": {"en": "STOP HOOK — reported without blocking at the previous close",
                          "fr": "HOOK STOP — signalé sans blocage à la clôture précédente"},
    "summary.list.cleanup": {"en": "STARTUP CLEANUP", "fr": "ENTRETIEN AU LANCEMENT"},
    # short dialog headers (≤ 12 characters, menu.HEADER_MAX)
    "menu.header.work": {"en": "Script", "fr": "Script"},
    "menu.header.new": {"en": "New", "fr": "Nouveau"},
    "menu.header.quality": {"en": "Quality", "fr": "Qualité"},
    "menu.header.maintenance": {"en": "Maintenance", "fr": "Maintenance"},
    "menu.header.maintenance.config": {"en": "Settings", "fr": "Réglages"},
    "menu.header.maintenance.tools": {"en": "Tools", "fr": "Outils"},
    "menu.header.kind": {"en": "Type", "fr": "Type"},
    "menu.header.profile": {"en": "Profile", "fr": "Profil"},
    "menu.header.script": {"en": "Script", "fr": "Script"},
    "menu.header.setting": {"en": "Setting", "fr": "Réglage"},
    "menu.header.confirm": {"en": "Confirm", "fr": "Confirmer"},
    "summary.list.hookerrors": {"en": "HOOK — internal error: the check did not run (trace: .claude/runtime/session/hook-errors.json)",
                                "fr": "HOOK — erreur interne : le contrôle n'a pas été effectué (trace : .claude/runtime/session/hook-errors.json)"},
    "summary.more": {"en": "  (+{n} more — python3 -m tools.pws_workspace session-status)",
                     "fr": "  (+{n} de plus — python3 -m tools.pws_workspace session-status)"},
    # ---- doctor ------------------------------------------------------------
    "doctor.header": {"en": "Workspace diagnostic (read-only: nothing is repaired automatically)",
                      "fr": "Diagnostic du workspace (lecture seule : rien n'est réparé automatiquement)"},
    "doctor.result": {"en": "Diagnostic result: {worst}", "fr": "Résultat du diagnostic : {worst}"},
    "doctor.legend": {"en": "BLOCKING = actionable defect; WARNING = attention; INFO = declared limitation; OK = verified",
                      "fr": "BLOCKING = défaut actionnable ; WARNING = point d'attention ; INFO = limitation déclarée ; OK = vérifié"},
    # ---- Stop hook (2026-11-14: rendered in the language in force when shown) ----
    "stop.reason.introduced": {"en": "Repairable mechanical violations introduced during the session (PWS guard):",
                               "fr": "Violations mécaniques réparables introduites pendant la session (guard PWS) :"},
    "stop.reason.legal": {"en": "Never remove or modify a licence notice, an attribution or a third-party legal "
                                "reference to satisfy the guard: if a finding concerns such a mention, present it to "
                                "the holder and wait for their decision.",
                          "fr": "Ne jamais retirer ni modifier une notice de licence, une attribution ou une référence "
                                "légale tierce pour satisfaire le guard : si un constat porte sur une telle mention, le "
                                "présenter au titulaire et attendre sa décision."},
    "stop.reason.info": {"en": "Reported without blocking (not introduced during the session):",
                         "fr": "Signalé sans blocage (non introduit pendant la session) :"},
    "stop.item.unregistered_modified": {"en": "{rel}: modified during the session but UNREGISTERED — run pine-onboard",
                                        "fr": "{rel}: modifié pendant la session mais UNREGISTERED — exécuter pine-onboard"},
    "stop.item.unregistered": {"en": "{rel}: UNREGISTERED — run pine-onboard — {category}",
                               "fr": "{rel}: UNREGISTERED — exécuter pine-onboard — {category}"},
    "stop.item.indeterminate_clean": {"en": "{rel}: provenance not established — no blocking finding",
                                      "fr": "{rel}: provenance non établie — aucun finding bloquant"},
    "stop.item.introduced": {"en": "{rel}: [{check}] {text}", "fr": "{rel}: [{check}] {text}"},
    "stop.item.new_file": {"en": "{rel}: [{check}] {text} (new file)", "fr": "{rel}: [{check}] {text} (nouveau fichier)"},
    "stop.item.note": {"en": "{rel}: [{check}] {text} — {label}", "fr": "{rel}: [{check}] {text} — {label}"},
    "stop.category.moved-unchanged": {"en": "moved without modification, already unregistered",
                                      "fr": "déplacé sans modification, déjà non enregistré"},
    "stop.category.imported-unchanged": {"en": "declared import, content unchanged, onboarding to complete",
                                         "fr": "import déclaré, contenu inchangé, onboarding à terminer"},
    "stop.category.indeterminate": {"en": "indeterminate attribution (provenance of the file not established)",
                                    "fr": "attribution indéterminée (provenance du fichier non établie)"},
    "stop.label.indeterminate": {"en": "indeterminate attribution (provenance of the file not established: check its provenance)",
                                 "fr": "attribution indéterminée (provenance du fichier non établie : vérifier sa provenance)"},
    "stop.label.visible": {"en": "made visible by the context (check not evaluable {moment})",
                           "fr": "rendu visible par le contexte (check non évaluable {moment})"},
    "stop.label.visible.changed": {"en": "; content modified during the session: an introduction is not excluded",
                                   "fr": " ; contenu modifié pendant la session : une introduction n'est pas exclue"},
    "stop.label.preexisting": {"en": "pre-existing", "fr": "préexistant"},
    "stop.label.preexisting_at": {"en": "pre-existing {moment}", "fr": "préexistant {moment}"},
    "stop.label.resumed": {"en": "present at the resumption (session lineage not established: an earlier introduction is not excluded)",
                           "fr": "présent à la reprise (lignée de session non établie : une introduction antérieure n'est pas exclue)"},
    "stop.moment.start": {"en": "at session start", "fr": "au démarrage"},
    "stop.moment.import": {"en": "at import", "fr": "à l'import"},
    "stop.recorded": {"en": "[as recorded] ", "fr": "[tel qu'enregistré] "},
    # ---- maintenance -------------------------------------------------------
    "cleanup.removed": {"en": "removed {n} recreatable temporary item(s) ({bytes} bytes)",
                        "fr": "{n} élément(s) temporaire(s) recréable(s) supprimé(s) ({bytes} octets)"},
    "cleanup.anomaly": {"en": "cleanup anomaly: {detail}", "fr": "anomalie d'entretien : {detail}"},
    "cleanup.skipped_lock": {"en": "cleanup skipped: another maintenance run holds the lock",
                             "fr": "entretien ignoré : une autre exécution détient le verrou"},
}


# guided update paths (2.2.0): texts kept in their own module, one catalogue
from .guide_text import CATALOGUE as _GUIDE_CATALOGUE  # noqa: E402

_CATALOGUE.update(_GUIDE_CATALOGUE)


def normalize_language(value):
    """Return a supported language code; unknown or missing → default."""
    if isinstance(value, str):
        v = value.strip().lower()[:2]
        if v in LANGUAGES:
            return v
    return DEFAULT_LANGUAGE


def t(key, lang=DEFAULT_LANGUAGE, **kwargs):
    """Translate `key` into `lang` (fallback: English, then the key itself)."""
    entry = _CATALOGUE.get(key)
    if entry is None:
        return key
    text = entry.get(normalize_language(lang)) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def has_key(key):
    return key in _CATALOGUE
