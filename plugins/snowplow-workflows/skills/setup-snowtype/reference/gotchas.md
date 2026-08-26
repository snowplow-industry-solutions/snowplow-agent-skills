# Snowtype Gotchas

The failure modes the Snowtype docs undercover. Every entry names its source so it can be re-verified when Snowtype releases. Mechanics (commands, flags, config options) are deliberately absent — fetch them live via `fetch-snowplow-docs` from the pages listed at the bottom.

Verified 2026-08-25 against `@snowplow/snowtype@0.17.3` and the docs pages dated 2026-08-25; re-checked 2026-08-26 in a live run against the JavaScript tag tracker (the config-keys, lock-file and `export` entries below were corrected from that run).

## Config keys

**All five source arrays must be present, even when empty.** The config validator only insists on `tracker`, `language`, and `outpath`, so a file missing `dataProductIds`, `dataStructures`, `igluCentralSchemas`, or `repositories` passes validation ("Valid configuration found") and then `update`/`generate` crash with `Cannot read properties of undefined (reading 'map')` — the runtime maps over each array unguarded. Always write `eventSpecificationIds`, `dataProductIds`, `dataStructures`, `igluCentralSchemas`, and `repositories`, filling the ones you use and leaving the rest `[]`. `organizationId` is needed whenever any Console source is populated. *Source: observed 2026-08-26 on 0.17.3 (crash in the data-product and data-structure resolvers when the key is absent); configuration-reference page.*

**`organizationId`, never `orgId`.** Several docs example blocks (generate-tracking-code, keep-code-up-to-date, example pages) show `"orgId"`. The CLI does not recognise that key — it appears nowhere in the package — so a config copied from those examples cannot reach Console and fails with a credentials/organization error. *Source: package strings (29 × `organizationId`, 0 × `orgId`); docs examples.*

**`namespace` is Swift-only.** Setting it for any tracker other than `snowplow-ios-tracker` errors at generation. *Source: configuration-reference.*

**Terminology drift.** Console and the docs now say "tracking plan"; the config key is still `dataProductIds` and the CLI flags are `--dataProductIds` / `--dataProducts`. The ID is the last path segment after `/data-products/` in the Console URL. *Source: snowtype-config, command-reference.*

## Lock file and drafts

**The first `generate` creates the lock file; `update` needs it to exist.** On a project with no `.snowtype-lock.json`, `update --yes` fails with `Lock file is invalid or corrupted. Please recover it or delete it, and run 'snowtype generate' so a new one will be created` (ENOENT underneath). So the order is: first ever run → `generate` (it writes the lock with every configured spec pinned); every later change → `update` then `generate`. *Source: error string in package; observed 2026-08-26 on 0.17.3.*

**After that, new event specs are silently skipped until the lock file knows them.** `generate` reads `.snowtype-lock.json`, not Console. Adding IDs to the config of a project that already has a lock and running `generate` yields `⚠ Warning: Skipping N event specification(s) not found in lock file. Run 'update --yes' to add new entries.` and produces no code for them. Run `update --yes` (or accept the interactive `update`) before `generate` whenever specs were added. *Source: keep-code-up-to-date; warning string present in package.*

**Draft event specs are invisible to `update`.** By default `update` checks published versions only. Specs just created — by `design-tracking-plan`, the Console MCP, or by hand — are drafts until published, so `update` reports nothing and the agent concludes Snowtype "cannot see" them. Add `--latestDraft`. *Source: keep-code-up-to-date; flag present in package.*

**Commit `.snowtype-lock.json` and the config.** Without the lock file each teammate generates from whatever version is current, and generated output diverges. *Source: keep-code-up-to-date; configuration-reference.*

**`purge` is destructive.** It strips lock entries no longer referenced by the config. Commit the lock file first. *Source: keep-code-up-to-date.*

## Dev vs prod

**`disallowDevSchemas` must be off during local development.** Schemas created by `design-tracking-plan` / `implement-custom-events` land in the DEV environment first. With `disallowDevSchemas` on (config or `--disallowDevSchemas`), generation fails with "only deployed on DEV environment". Leave it off locally; turn it on in the CI/production generate step so dev-only schemas cannot ship. *Source: command-reference; configuration-reference; string present in package.*

**`update --yes` overwrites the config file.** It is the right call in CI and whenever specs were added to a project that already has a lock file, but locally it discards any uncommitted config edits. Commit before running it. *Source: command-reference (`-y` description); keep-code-up-to-date.*

## Multi-tracker

**One config serves one tracker.** `tracker` and `language` are single values. A project with both client and server tracking (Next.js, Remix, SvelteKit with the browser tracker plus `@snowplow/node-tracker`) needs one config per tracker — e.g. `snowtype.config.json` and `snowtype.config.server.json` — each with its own `outpath`, run via `-c <path>`. Wrap them in npm scripts (see `templates/package-scripts.md`). Every `generate`/`update` then runs per config, so the lock-file gotcha above applies to each. Verify at run time whether auto-discovery finds a non-default filename; `-c` always works. *Source: configuration-reference (single `tracker`/`language`); command-reference (`-c, --config` on generate/update/patch/purge).*

## Local repositories

**`repositories` paths: CLI root or `data-structures/`, never `data-products/`.** Snowtype reads local data structures only. Pointing at a `data-products/` directory does nothing, silently. Paths are relative to the **config file**, whereas `outpath` is relative to the **current working directory** when the command runs. *Source: snowtype-config ("This won't do anything" example; "Provide the path relative to the location of your configuration file"); configuration-reference (`outpath`).*

**Local repositories cannot supply tracking plans.** No `trackXSpec` functions and no `event_specification` entity from a local-only setup — those need Console sources. *Source: snowtype-config "Snowtype limitation" callout.*

## JavaScript tag tracker

**The `@snowplow/javascript-tracker` output contains one `export` statement.** Everything else in the generated file is plain functions meant to be loaded with a classic `<script>` tag and called as globals, but 0.17.3 emits `export function createEventSpecification(...)`. A classic script throws `SyntaxError: Unexpected token 'export'` on that line and **defines none of the functions** — every `trackXSpec` call then fails with "is not defined". Check the output for `^export ` after generating. Workaround: `templates/snowtype-postgenerate.js` strips the leading `export`; wire it into the `snowtype:generate` npm script so it runs on every regeneration — never hand-edit the file. Loading the file as `type="module"` is not a fix: the functions would no longer be globals. *Source: observed 2026-08-26 in 0.17.3 output; not documented on generate-tracking-code.*

## Client-side validation

**`--validations` is browser-tracker-only** (`@snowplow/browser-tracker`, JavaScript or TypeScript) and requires `ajv@8`, `ajv-formats@2`, `ajv-draft-04@1` installed by the project. It adds bundle weight — keep it to development and test builds. *Source: client-side-validation.*

## Environment

**Node: the package declares `engines.node >=24.15.0`; the docs say 18+.** On an older Node, npm prints `EBADENGINE` but installs, and the CLI has been seen to run on 22.x. Treat anything below 24.15 as unsupported: recommend Node 24 and mention the warning so it is not mistaken for a failure. *Source: package.json `engines`; install-snowtype page; verified on Node 22.14.*

**Two credentials, not one.** Console access needs both `SNOWPLOW_CONSOLE_API_KEY` and `SNOWPLOW_CONSOLE_API_KEY_ID` (or `--apiKey` and `--apiKeyId`). Missing either gives "Required API key credentials not detected". Keep them in the environment or a git-ignored `.env`, not in the config file or command history. *Source: install-snowtype; error string observed.*

**Snowtype does not install the tracker.** Generated code imports (or, for the JavaScript tag tracker, calls `window.snowplow`) a tracker it assumes is already present. Check the tracker exists first; hand off to `install-snowplow-tracking` if not. *Source: generate-tracking-code.*

**Hand edits to generated output are lost on the next `generate`.** Wrap or extend generated functions from your own modules; never edit the output file. *Source: generate-tracking-code.*

## Docs pages (fetch live via `fetch-snowplow-docs`)

All under `https://docs.snowplow.io/docs/event-studio/implement-tracking/`:

- `install-snowtype/` — install, authenticate, `init`
- `snowtype-config/` — adding sources (specs, tracking plans, data structures, Iglu Central, local repos)
- `configuration-reference/` — every config key; supported tracker/language table
- `command-reference/` — every command and flag
- `generate-tracking-code/` (+ `example-data-structures/`, `example-event-specs/`) — output shape per tracker; how to call generated code
- `keep-code-up-to-date/` — lock file, `update`, `purge`, CI pattern
- `client-side-validation/` — runtime validation for the browser tracker
