# Git-Backed Schema Workflow (snowplow-cli)

Read this when the user keeps data structures and tracking plans in a git repository, or wants schema changes gated by code review and CI.

In this mode the repository is the source of truth for *design*, and Console is a deployment target. Design happens in files and pull requests; publishing is a separate, decoupled act performed by CI. That decoupling is the whole point: a schema can be designed, reviewed, and merged without anyone touching Console, and it reaches an environment only when a pipeline says so.

Commands below are the current `snowplow-cli` syntax. Every command has a short alias — `ds` for `data-structures`, `dp` for `data-products` — used interchangeably in Snowplow's own docs. Run `snowplow-cli <command> --help` before relying on a flag you have not used here.

## Terminology

Tracking plans are still called **data products** in the CLI and API. `snowplow-cli dp ...` operates on tracking plans, event specifications, and source applications.

## Prerequisites

Install:

```bash
brew install snowplow/taps/snowplow-cli
# or download the binary from https://github.com/snowplow/snowplow-cli/releases/latest
snowplow-cli --help
```

Authenticate with a Console API key. Three variables are needed:

```
SNOWPLOW_CONSOLE_ORG_ID
SNOWPLOW_CONSOLE_API_KEY_ID
SNOWPLOW_CONSOLE_API_KEY
```

Supply them as environment variables, in a `.env` file (`--env-file`), or in `$HOME/.config/snowplow/snowplow.yml` under `console.org-id`, `console.api-key-id`, `console.api-key`. `snowplow-cli setup` writes that config interactively (`--read-only` for a read-only key, `--dotenv` to write a `.env` instead).

In CI, store all three as repository/organisation secrets and inject them as environment variables on the job. Never commit them, and never write them into a schema file or a `.snowplow/` context file.

## Repository layout

`snowplow-cli` generates and expects this layout:

```
data-structures/
  com.acme/
    login.yaml
    product_action.yaml
  com.acme.mobile/
    screen_view.yaml
data-products/
  ecommerce-checkout.yaml
  source-apps/
    web-storefront.yaml
```

Data structures are one file per schema, foldered by vendor. Tracking plans live at the top of `data-products/`, with source applications in `data-products/source-apps/`. Event specifications are embedded inside their tracking plan file, not stored separately — the same rule as the MCP path, where an event spec is created with its event schema and all entities in one call.

A data structure file wraps the JSON Schema in CLI metadata:

```yaml
apiVersion: v1
resourceType: data-structure
meta:
  hidden: false
  schemaType: event
  customData: {}
data:
  $schema: http://iglucentral.com/schemas/com.snowplowanalytics.self-desc/schema/jsonschema/1-0-0#
  self:
    vendor: com.example
    name: login
    format: jsonschema
    version: 1-0-0
  type: object
  properties:
    result:
      enum: [success, failure]
  additionalProperties: false
```

`meta.schemaType` is `event` or `entity`. The `data` block is the ordinary self-describing JSON Schema — everything in the main skill about naming, entity-first modelling, and SchemaVer applies unchanged here.

## Step 1: Pull existing Console state into the repository

Before designing anything, get the current state into files so the diff is meaningful:

```bash
snowplow-cli ds download                 # → ./data-structures
snowplow-cli dp download                 # → ./data-products
```

Both accept an explicit target directory as a positional argument. `ds download` skips draft data structures that have never been deployed to dev — add `--include-drafts` when you need them, and `--match` to restrict to specific vendors or names. Use `-f json` (`--output-format`) if the team prefers JSON files over YAML.

Commit this download as its own commit, before any design work. It is the baseline every later diff is read against.

## Step 2: Design in files

Scaffold a new data structure rather than hand-rolling the wrapper:

```bash
snowplow-cli ds generate product_action --vendor com.acme --event
snowplow-cli ds generate product --vendor com.acme --entity
```

For tracking plans and source applications:

```bash
snowplow-cli dp generate --data-product ecommerce-checkout
snowplow-cli dp generate --source-app web-storefront
snowplow-cli dp add-event-spec data-products/ecommerce-checkout.yaml -e "Add To Cart"
```

Edit the generated files. Property instructions for an event spec live inside the tracking plan file alongside the spec they constrain — the subtype rules in `reference/property_instructions.md` apply identically.

## Step 3: Validate locally before opening the PR

```bash
snowplow-cli ds validate                         # defaults to ./data-structures
snowplow-cli ds validate data-structures/com.acme/product_action.yaml
snowplow-cli dp validate                         # defaults to ./data-products
```

`ds validate` checks file format, JSON Schema conformance, and warehouse-loading hazards (column-name collisions, types that will not load cleanly). `dp validate` validates tracking plans against Console; `--full` widens the check.

Validation needs Console credentials — it is a server-side check, not a purely local one. A developer without a key cannot validate locally; that is a normal reason to lean on the CI check instead.

Fix every warning before publishing. A missing `description` is a warning, not an error, and it is the one most often shipped by accident.

## Step 4: Publish dev → prod

```bash
snowplow-cli ds publish dev                      # defaults to ./data-structures
snowplow-cli ds publish prod
snowplow-cli ds publish dev --dry-run            # print planned changes only
```

Two properties of this pair drive the whole promotion model:

- `publish dev` validates before uploading. `publish prod` does **not** validate — it requires every referenced data structure to already exist in dev. Dev is therefore a mandatory gate, not an optional staging step.
- Publishing is decoupled from design. Merging a schema change does not deploy it; running `publish` does. A team can review and merge on one cadence and promote to prod on another.

For tracking plans, `sync` pushes local changes to Console and `release` additionally releases draft event specifications:

```bash
snowplow-cli dp sync                             # validate + push local changes
snowplow-cli dp release                          # sync, then release draft event specs
snowplow-cli dp sync --dry-run
```

`dp publish` still works as an alias for `sync` but is deprecated — use `sync` or `release`.

Add `--managed-from $GITHUB_REPOSITORY` (`-m`) on publishing commands so Console records which repository owns each resource. This is what stops someone editing a git-managed schema in the Console UI without realising it will be overwritten.

## Step 5: CI

Validate on pull request, publish on merge. `--gh-annotate` turns validation output into GitHub workflow annotations on the diff.

```yaml
on:
  pull_request:
    branches: [develop, main]

jobs:
  validate:
    runs-on: ubuntu-latest
    env:
      SNOWPLOW_CONSOLE_ORG_ID: ${{ secrets.SNOWPLOW_CONSOLE_ORG_ID }}
      SNOWPLOW_CONSOLE_API_KEY_ID: ${{ secrets.SNOWPLOW_CONSOLE_API_KEY_ID }}
      SNOWPLOW_CONSOLE_API_KEY: ${{ secrets.SNOWPLOW_CONSOLE_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: snowplow/setup-snowplow-cli@v1
      - run: snowplow-cli ds validate --gh-annotate
```

```yaml
on:
  push:
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    env:
      SNOWPLOW_CONSOLE_ORG_ID: ${{ secrets.SNOWPLOW_CONSOLE_ORG_ID }}
      SNOWPLOW_CONSOLE_API_KEY_ID: ${{ secrets.SNOWPLOW_CONSOLE_API_KEY_ID }}
      SNOWPLOW_CONSOLE_API_KEY: ${{ secrets.SNOWPLOW_CONSOLE_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: snowplow/setup-snowplow-cli@v1
      - run: snowplow-cli ds publish prod --managed-from $GITHUB_REPOSITORY
```

Snowplow's own tutorial publishes straight to prod on merge to `main`. Recommend the three-stage shape instead when the team wants a real gate:

1. **Pull request** — `ds validate --gh-annotate` and `dp validate`. Blocks the merge.
2. **Merge to main** — `ds publish dev --managed-from $GITHUB_REPOSITORY`, then `dp sync`. Every merged change lands in dev automatically.
3. **Tag or release, behind an environment approval** — `ds publish prod --managed-from $GITHUB_REPOSITORY`, then `dp release`. A human approves promotion.

Stage 3 is where "decoupled from design" becomes visible: the schema was designed and merged days earlier, and the release job only promotes what dev already proved.

## Vendored Snowplow-managed schemas

Never edit a Snowplow-managed schema in place. Copy it into your own vendor namespace, publish the copy from your repo, and track it as your own data structure. Editing the original couples your repo to a schema Snowplow will version on its own schedule, and the next upstream change silently conflicts.

## Failure modes

- **`publish prod` fails on a schema that validates fine.** The structure is not in dev yet. Run `publish dev` first — prod publishing resolves references against dev, it does not validate.
- **Validation fails in CI but passed locally.** The local run used a different Console org, or stale credentials. Check `SNOWPLOW_CONSOLE_ORG_ID` matches on both sides.
- **A schema edited in Console reappears with old content after CI runs.** Two sources of truth for one data structure. Pick one — for a git-managed schema, port the Console edit back into the repo and re-publish, and set `--managed-from` so Console flags it next time.
- **`ds download` misses a schema the user can see in Console.** It is a draft never deployed to dev. Re-run with `--include-drafts`.
