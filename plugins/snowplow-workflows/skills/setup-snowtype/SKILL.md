---
name: setup-snowtype
description: "Set up Snowtype, Snowplow's typed tracking-code generator, in a project and keep the generated code current — detect trackers, configure sources from Console or local schemas, generate, and handle the lock file, drafts, and dev-versus-prod schema rules. Standalone, or delegated from implement-custom-events step 8. CLI mechanics come from the live docs; this skill carries the pitfalls. Triggers: snowtype, set up snowtype, generate tracking code, typed tracking code, snowtype update, snowtype lock file, stale generated tracking code."
---

# Setup Snowtype

Snowtype turns event specifications and data structures into tracker-ready functions (`trackXSpec`, `createX`) so tracking calls are typed and carry the `event_specification` entity automatically. This skill gets it installed, configured and generating, then keeps the output current. It adds what the docs undercover; every command, flag and config option comes from the docs at run time.

## When To Use This Skill

Use this skill when:

- Event specs or data structures exist (Console or a local snowplow-cli repository) and the project should track them through generated, typed code.
- `implement-custom-events` reaches its Snowtype step and delegates here.
- Generated tracking code is stale, event specs "aren't being picked up", or a `generate` run skipped specs.
- A project needs Snowtype in CI (regenerate on schema change, block dev-only schemas).

Don't use this skill when:

- No schemas or event specs exist yet — go to `design-tracking-plan` (or `create-data-spec` first).
- The tracker itself is not installed — `install-snowplow-tracking` first; Snowtype does not install trackers.
- The tracker or language is not in Snowtype's supported table (check live, step 2) — hand-instrument with `trackSelfDescribingEvent` against the Iglu URIs instead.

## Prerequisites

- A Console API key **and** its key ID for any Console source (event specs, tracking plans, Console data structures). Local-repository-only setups need neither.
- Node available in the project; the package declares `>=24.15.0` (see `reference/gotchas.md#environment`).
- The Snowplow tracker the code will target is already installed or loaded.

## Instructions

Read `reference/gotchas.md` before the first Snowtype command in a session.

### 0. Choose the mode

- **Delegated** — invoked by `implement-custom-events` (the caller says "delegated mode"). Ask nothing. Do steps 1–6, report the generated function names and output path, and return. The caller owns instrumentation.
- **Standalone** — ask one question: *"Set up and generate only, or also switch the tracking code over to the generated functions?"*
  - **Set up only** → steps 1–7; done when `generate` is clean and config + lock file are committed.
  - **Set up and implement** → steps 1–8.

### 1. Load context and detect trackers

Read `.snowplow/agent-context.md` if present (written by `setup-snowplow-context`; read-only here — use values as written, never rewrite the file):

- `console-org` → `organizationId`
- `schema-workflow: git-backed` + `iglu-repositories` → candidate `repositories` paths
- `tracked-platforms` → tracker candidates

If the file is missing, offer `setup-snowplow-context` once; if declined, ask inline for the org ID.

Scan the codebase for tracker signals: `@snowplow/browser-tracker`, `@snowplow/javascript-tracker` (npm or a `sp.js` CDN snippet), `@snowplow/node-tracker`, `@snowplow/react-native-tracker` in `package.json`; `SnowplowTracker` in `Podfile`/SPM; `snowplow-android-tracker` in Gradle; Go/Java/Flutter tracker dependencies.

- **None** → invoke `install-snowplow-tracking`, then resume here.
- **One** → one config.
- **Client and server both** (e.g. browser + Node in a Next.js app) → one config **per tracker** with separate `outpath`s, run via `-c`. Say so before writing anything — see `reference/gotchas.md#multi-tracker`.

### 2. Confirm support against the live docs

> Invokes `fetch-snowplow-docs`.

Fetch the configuration-reference page and read the supported tracker/language table. Match the detected tracker to a `tracker` value and a `language`. The CDN `sp.js` tag tracker is `@snowplow/javascript-tracker` / `javascript` — its output calls `window.snowplow()` and is loaded with a script tag, not imported.

Unsupported → stop and return "hand-instrument with `trackSelfDescribingEvent`" (in delegated mode the caller does this in its own instrumentation step).

### 3. Install, authenticate, initialise

> Invokes `fetch-snowplow-docs` for install-snowtype.

Follow the install page. This skill adds only:

- Check `node --version` against the package's `engines` (`npm view @snowplow/snowtype engines`). Below it, say the install will warn `EBADENGINE` and recommend Node 24 — `reference/gotchas.md#environment`.
- Both `SNOWPLOW_CONSOLE_API_KEY` and `SNOWPLOW_CONSOLE_API_KEY_ID`, in the environment or a git-ignored `.env`. Never write them into the config or echo them into the transcript.
- The org key is `organizationId`. Docs example blocks that show `orgId` are wrong — `reference/gotchas.md#config-keys`.
- Prefer `templates/snowtype.config.json` over `init`'s prompts when running non-interactively. Keep **all five** source arrays in the file (`eventSpecificationIds`, `dataProductIds`, `dataStructures`, `igluCentralSchemas`, `repositories`), empty where unused — the validator lets you omit them but the runtime crashes with `reading 'map'` if you do — `reference/gotchas.md#config-keys`.

### 4. Add sources

Sources, in order of preference:

1. **Tracking plan ID(s)** (`dataProductIds`) — generates every spec in the plan; ID is the last URL segment after `/data-products/`.
2. **Event spec IDs** (`eventSpecificationIds`) — delegated mode: the caller passes the IDs it just created; standalone: from Console URLs or the Console MCP's list tools if present.
3. **Data structure URIs** (`dataStructures`) / **Iglu Central URIs** (`igluCentralSchemas`) — when there are no specs.
4. **Local `repositories`** — git-backed projects; CLI root or `data-structures/` only, path relative to the config file — `reference/gotchas.md#local-repositories`. Local sources give data structures only, never `trackXSpec`.

Set `disallowDevSchemas: false` locally (schemas from `design-tracking-plan` are in DEV) — `reference/gotchas.md#dev-vs-prod`.

### 5. Generate, and keep the lock file in step

> Invokes `fetch-snowplow-docs` for keep-code-up-to-date if the commands are unfamiliar.

1. **No `.snowtype-lock.json` yet** (first run): run `generate` — it creates the lock with every configured spec pinned. `update` fails with "Lock file is invalid or corrupted" until the lock exists. **Lock file exists and specs were added**: run `update --yes` **before** `generate`, otherwise `generate` skips the new specs with a warning and emits nothing for them. Specs created minutes ago are drafts: add `--latestDraft` or `update` finds nothing — `reference/gotchas.md#lock-file-and-drafts`.
2. Confirm the output file exists at `outpath` and contains the expected `trackXSpec` / `createX` names. Read the generated file's header comments for `@deprecated` (outdated data structure) or "Hidden data structure" warnings and surface them. For `@snowplow/javascript-tracker`, grep the output for `^export ` — see `reference/gotchas.md#javascript-tag-tracker`.
3. Add the scripts from `templates/package-scripts.md`.
4. Commit `snowtype.config.*` and `.snowtype-lock.json`.

Delegated mode ends here: report `outpath`, the generated function names, and any warnings, then return.

### 6. Verify the tracker can reach the generated code

- Import-based trackers: the output is a module at `outpath`; import from it.
- JavaScript tag tracker (`sp.js`): the output is a plain script defining global functions that call `window.snowplow()`; load it with a `<script>` tag **after** the tracker snippet and **before** the app code that calls it, on every page that calls it. 0.17.3 leaves one `export` in that file, which makes a classic script define nothing — strip it in a post-generate step (`templates/package-scripts.md`) and confirm the file parses as a classic script before wiring the tag.

### 7. Lifecycle (set up only — explain; set up and implement — also apply)

Cover, from the keep-code-up-to-date page: `update` with `--maximumBump` for data structures; `update --latestDraft` while specs are unpublished; `purge` (commit first); the CI pattern `update --yes` → `generate --disallowDevSchemas`, failing the build on diff. Never hand-edit the output — wrap it.

### 8. Implement (standalone "set up and implement" only)

Replace hand-built self-describing payloads with the generated functions: `trackXSpec` for events that have a spec (it attaches the `event_specification` entity and validates cardinality in typed languages), `createX` for entities passed in `context`. Keep the existing tracker namespace. Then invoke `setup-micro` if Micro is not running and `validate-snowplow-implementation`; every migrated event must land in `/good` with its `event_specification` entity attached.

## Reference Documentation

- `reference/gotchas.md` — the sourced Snowtype pitfalls, grouped by config keys, lock file and drafts, dev vs prod, multi-tracker, local repositories, JavaScript tag tracker, client-side validation, environment. Read before the first command; ends with the list of docs pages to fetch live.

## Templates

- `templates/snowtype.config.json` — config with the three required keys plus all five source arrays (keep them all; fill the ones you use). Fill `organizationId`, `tracker`, `language`; drop `organizationId` for local-only.
- `templates/package-scripts.md` — npm scripts for one config and for two (`-c`), the JavaScript-tag post-generate step, and the CI variant.
- `templates/snowtype-postgenerate.js` — the post-generate script for `@snowplow/javascript-tracker` output; copy to the project root and chain after `generate`.

## Common Failure Modes

- **`update` or `generate` dies with `Cannot read properties of undefined (reading 'map')` right after "Valid configuration found"**: a source array is missing from the config; add all five, empty where unused — `reference/gotchas.md#config-keys`.
- **`update` says "Lock file is invalid or corrupted" on a fresh project**: no lock file yet; run `generate` first, it creates one — `reference/gotchas.md#lock-file-and-drafts`.
- **`generate` prints "Skipping N event specification(s) not found in lock file"**: run `update --yes` (add `--latestDraft` for unpublished specs), then `generate` again — `reference/gotchas.md#lock-file-and-drafts`.
- **Browser console shows `Unexpected token 'export'` and `trackXSpec is not defined` with the JavaScript tag tracker**: the generated file has an `export` line; strip it post-generate — `reference/gotchas.md#javascript-tag-tracker`.
- **`update` reports no updates although specs were just created**: they are drafts; `update --latestDraft`.
- **"only deployed on DEV environment" during generate**: `disallowDevSchemas` is on while schemas are still in DEV; turn it off locally, keep it for CI — `reference/gotchas.md#dev-vs-prod`.
- **"Required API key credentials not detected"**: one of the two env vars is missing; both key and key ID are needed.
- **Config copied from a docs example can't reach Console**: the example used `orgId`; the key is `organizationId`.
- **Local `repositories` path yields nothing**: it points at `data-products/` or is relative to the wrong place — `reference/gotchas.md#local-repositories`.
- **`npm install` warns `EBADENGINE`**: Node below the package's `engines`; it may still run, but recommend Node 24.

## Limits and Alternatives

- Two-config (client + server) projects are handled by instruction; no worked example ships yet.
- Google Tag Manager output (`google-tag-manager` / `javascript-gtm`) and custom Snowtype templates are out of scope.
- If the team does not want generated code in the repository, hand-instrumented `trackSelfDescribingEvent` calls remain valid — `implement-custom-events` covers that path.
