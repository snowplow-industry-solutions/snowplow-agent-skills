# Roadmap

Source: the field skills map (`docs/snowplow-skills-map.pdf`). Waves are indicative order, not commitments. Boxes marked *product* are served by the official `snowplow` plugin, not this repo.

| Skills-map box | Persona | Disposition | Skill | Wave |
|---|---|---|---|---|
| Setup working preferences | All | shipped | `setup-snowplow-context` | 1 |
| snowplow-cli / Authenticate with Console | All | shared reference, not a skill | `design-tracking-plan` references | 1 |
| Product Spec > Data Spec | PM/Analyst | shipped | `create-data-spec` (entry A) | 1 |
| Data Spec > Snowplow Semantics | PM/Analyst | shipped | `create-data-spec` (entry B) | 1 |
| Design Tracking Plans / Event Specs | PM/Analyst | shipped | `design-tracking-plan` | 1 |
| Create Git-backed Structures | PM/Analyst | shipped | `design-tracking-plan` (git-backed path) | 1 |
| Make changes directly to Snowplow-managed schemas | PM/Analyst | folded in | `design-tracking-plan` decision framework | 1 |
| Publishing (decoupled from design) | PM/Analyst | shipped | `design-tracking-plan` git-backed workflow | 1 |
| Discover tracking opportunities / product event surfaces | PM/Analyst | planned | discovery step of `implement-custom-events` today; dedicated skill later | 2 |
| Create tracking plans from uncategorised Data Structures | PM/Analyst | planned | — | 3 |
| Frontend / Mobile / Tracker init / OOTB | Developer | shipped | `install-snowplow-tracking` | 1 |
| Backend serverside | Developer | planned | extend `install-snowplow-tracking` | 2 |
| Plugin-specific instrumentation (media, ecom) | Developer | planned | — | 2 |
| Anonymous tracking implementation | Developer | planned | shared with governance anonymous-tracking skill | 3 |
| Writing a custom plugin | Developer | planned | — | 3 |
| Setup Snowtype | Developer | shipped | `setup-snowtype` (also delegated from `implement-custom-events` step 8) | 2 |
| Check OOTB events against HTML markup | Developer | planned | — | 3 |
| Testing locally / Spin up Micro | Developer | shipped | `setup-micro`, `validate-snowplow-implementation` | 1 |
| Debugging failed events | Developer | shipped | `debug-failed-events` (local-first; production side is *product* `troubleshooting`) | 1 |
| Workflow: auto-implement events + monitor in Micro | Developer | shipped | `implement-custom-events` | 1 |
| Writing once-off queries | Analyst | planned | — | 2 |
| Debugging data quality issues | Analyst | planned | — | 2 |
| Event recovery (+ keyhole backfills) | Analyst | planned | — | 3 |
| New dbt project for Snowplow models | Analytics Eng | planned | — | 2 |
| Unified model setup | Analytics Eng | planned | — | 2 |
| Attribution model setup | Analytics Eng | planned | — | 2 |
| Autogenerate custom model | Analytics Eng | planned | — | 2 |
| Create semantic definitions from schema | Analytics Eng | planned | — | 2 |
| Audit / scoring of existing schemas | Governance | planned | — | 3 |
| Audits (spec-to-reality, anon tracking, missing events) | Governance | planned | — | 3 |
| Console configuration questions | Governance | *product* (`console-operations`) | — | — |
| Configure enrichments | Governance | *product* (`console-operations`); custom JS enrichment authoring stays here | 3 |
| Writing custom JS enrichment | Governance | planned | — | 3 |
| Anonymous tracking | Governance | planned | — | 3 |
| Schema discoverability tool | Governance | planned | — | 3 |
| Quick onboarding wizard | Migration | planned | — | 3 |
| GA4 > Snowplow | Migration | planned | — | 2 |
| Write a new Event Forwarding destination | Future | deferred | — | future |
| Signals | Future | *product* (`signals`) | — | — |
