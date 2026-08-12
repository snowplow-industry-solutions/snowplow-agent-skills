---
name: implement-custom-events
description: "End-to-end workflow for custom Snowplow event tracking — discover what to track, draft a tracking spec, design schemas and event specs via design-tracking-plan, create them in Console, instrument the code, and validate in Micro. Use when a customer wants custom event tracking added to an application from start to finish. Triggers: add custom events, implement tracking end to end, instrument a feature end to end, instrument and validate events."
---

# Implement Custom Events

End-to-end workflow that takes a tracking goal (or a feature/codebase to explore) all the way to validated events flowing into Snowplow. Composes the discovery, design, instrumentation, and validation skills into a single guided path.

## When To Use This Skill

Use this skill when:

- The user wants to add custom event tracking to an application from end to end.
- The user has a feature or PRD they want instrumented but hasn't decided what to track yet.
- The user wants the full path from "we should track X" to "events validated in Micro".

Don't use this skill when:

- The tracker isn't installed at all and the user only wants to set up the base SDK (use `install-snowplow-tracking` directly).
- The user only wants to design schemas without touching code (use `design-tracking-plan` directly).
- The user only wants to troubleshoot existing tracking (use the validate/debug skills directly).

## Prerequisites

- Application codebase is accessible for scanning and modification.
- Console access for the design and Console-write steps: either the Snowplow MCP (from the official `snowplow` plugin) or `snowplow-cli` with the git-backed workflow. If neither is available, stop after the spec-drafting step and tell the user what to install.
- User has authority to create schemas and event specs in the target organization.

## Instructions

### 1. Discover what to track

Branch on what the user has provided:

- **No specific tracking ask**: Explore the codebase to identify candidate events. Look for user actions (clicks, submits, navigations), state transitions, and lifecycle events. Group by feature area. Propose 3–8 high-value events to start; defer the long tail.
- **Specific feature provided**: Scope discovery to that feature only — read the relevant files, identify the user actions and outcomes in that flow, and list the entities involved.
- **PRD / written spec provided**: Extract events, entities, and KPIs from the document. Note any open questions to ask the user before designing.

If `.snowplow/agent-context.md` exists (created by `setup-snowplow-context`), read it first for vendor, platforms, and collaboration mode. If the file is missing, offer once to run `setup-snowplow-context` before continuing — it removes these questions for every later skill.

### 2. Draft a human-readable tracking spec

Produce a short Markdown spec for the user to review before any design work:

- **Goal**: one sentence on what these events answer.
- **Events**: name + trigger + why it matters.
- **Entities**: name + which events they attach to + key fields.
- **Open questions**: anything ambiguous from discovery.

Keep this conversational — it's a shared artifact, not a schema yet. Ask the user to confirm or amend before moving on.

### 3. Hand the spec to `design-tracking-plan`

> Invokes another skill.

Pass the approved spec to the `design-tracking-plan` skill. That skill owns the schema and event-specification design (entity-first modelling, naming conventions, property instructions, Iglu reuse) and runs its own user-confirmation step before creating anything in Console.

### 4. Verify the proposed design

When `design-tracking-plan` returns its proposal (its Phase 5), review it against the spec from step 2:

- Every event in the spec is represented.
- Entities match the spec; nothing extraneous added.
- Naming, cardinality, and reuse decisions look right.
- Property instructions exist where multiple specs share a schema.

Flag any gaps to the user before approving the design.

### 5. Create schemas in dev via the Snowplow MCP

> Executed inside `design-tracking-plan` Phase 7.

Confirm the design and let `design-tracking-plan` run. New schema versions for both event and entity schemas are created in the dev environment via the Snowplow MCP. Capture the resulting Iglu URIs for use during instrumentation.

### 6. Create tracking plans / event specs in Console

> Executed inside `design-tracking-plan` Phase 7.

Event specifications are created with the event schema and all entities in a single MCP call, attached to the target tracking plan.

### 7. Verify tracker initialisation

Inline check — scan the codebase for an existing Snowplow tracker initialisation:

- **Web/JavaScript**: imports from a `@snowplow/*-tracker` package and a `newTracker(...)` call.
- **iOS**: `Snowplow.createTracker(...)` in AppDelegate or main App.
- **Android**: `Snowplow.createTracker(...)` in the Application class.

If no initialisation is found, invoke the `install-snowplow-tracking` skill before continuing. If it exists, capture the tracker namespace and collector endpoint so new events use the same tracker.

### 8. Pick an instrumentation approach

> May invoke `fetch-snowplow-docs`.

Determine whether Snowtype (Snowplow's typed-code-generation tool) supports the codebase's primary language. Call `fetch-snowplow-docs` to confirm current Snowtype language support — don't rely on prior knowledge.

- **Supported language**: install and configure Snowtype, then generate typed event constructors from the schemas created in step 5. Use the generated code during instrumentation.
- **Unsupported language**: instrument custom self-describing events directly using the tracker SDK's `trackSelfDescribingEvent` (or platform equivalent), passing the Iglu URIs from step 5.

When generating `snowtype.config.json`, the following keys must always be present, even when they have no values — emit empty strings or empty arrays rather than omitting the key:

```json
{
  "organizationId": "",
  "tracker": "",
  "language": "",
  "outpath": "",
  "eventSpecificationIds": [],
  "dataProductIds": [],
  "dataStructures": [],
  "igluCentralSchemas": [],
  "repositories": []
}
```

Populate the values from this run (e.g. `tracker: "@snowplow/browser-tracker"`, `language: "typescript"`, `outpath: "./src/snowtype"`, and the event-spec IDs created in step 6) and leave the rest as empty arrays/strings. Do not drop empty keys — downstream tooling expects every key present.

### 9. Specify the implementation plan to the user

Before writing code, summarise:

- Files that will be modified.
- Events being added at each call site (with the triggering action).
- Entities attached to each event and where their data is sourced.
- Whether Snowtype is being used or events are being hand-instrumented.

Wait for explicit user approval before editing code.

### 10. Implement

Write the instrumentation:

- Use Snowtype-generated constructors where applicable.
- Otherwise build self-describing event payloads against the Iglu URIs from step 5.
- Attach entities to the event call (not as separate `trackSelfDescribingEvent` calls).
- Reuse the tracker namespace captured in step 7.

Keep edits minimal and co-located with the triggering UI/logic.

### 11. Test and validate in Micro

> Invokes `setup-micro` and `validate-snowplow-implementation`.

Invoke `setup-micro` if Micro isn't already running. Then invoke `validate-snowplow-implementation` to:

- Confirm each new event reaches the `/good` endpoint.
- Inspect that entities are attached as designed.
- Diagnose anything that lands in `/bad`.

Report results back to the user with the events confirmed and any follow-ups.

## Skills Composed by This Workflow

- `design-tracking-plan` — steps 3–6 (design + Console creation via the Snowplow MCP).
- `install-snowplow-tracking` — step 7, only if the tracker isn't installed.
- `fetch-snowplow-docs` — step 8, to confirm Snowtype support and fetch current SDK APIs.
- `setup-micro` — step 11, if Micro isn't running.
- `validate-snowplow-implementation` — step 11, to confirm events are good.

## Common Failure Modes

- **Schema URIs in code don't match Console**: re-check the Iglu URIs from step 5 output. Vendor/name/version must be exact.
- **Events reach Micro but appear in `/bad`**: usually a property type mismatch or missing required field. Let `validate-snowplow-implementation` parse the error.
- **Snowtype-generated types are stale**: re-run Snowtype after every schema change; don't hand-edit generated files.
- **Tracker namespace mismatch**: new events going through a different tracker than existing OOTB events. Standardise on the namespace captured in step 7.

## Limits

Targets the typical custom-event-implementation path. Does not cover:

- Server-side tracking on platforms outside web/iOS/Android (use `design-tracking-plan` plus the relevant SDK directly).
- Streaming/enrichment configuration.
- dbt modelling — use the unified-setup skill once events are flowing.
- Promoting schemas from dev to prod environments.
