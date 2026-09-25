---
name: query-snowplow-data
description: "Teach and apply Snowplow-specific SQL query patterns against the atomic events table — unnesting and joining self-describing event and entity columns, event deduplication, bot filtering, timestamp selection, identity and session pitfalls, and page-ping engagement — for Snowflake, BigQuery, Databricks, and Redshift, including Iceberg and Delta tables loaded by the Lake Loader. Reads the warehouse from the project's Snowplow context file and emits dialect-correct SQL, or runs it when a warehouse tool is available. Triggers: query snowplow data, snowplow SQL patterns, unnest entities, query atomic events, deduplicate snowplow events, filter bot events, snowplow warehouse query, once-off query."
---

# Query Snowplow Data

Write and review SQL against Snowplow's atomic events table — reaching correctly into its
self-describing event and entity columns, and avoiding the recurring pitfalls (duplicates, bots,
the wrong timestamp, over/undercounted users and sessions, page-ping inflation) that make an
otherwise-correct-looking query return the wrong answer.

## When to use this skill

Use this skill when writing or reviewing a SQL query against Snowplow atomic data.

Don't use this skill when:

- Events are failing validation before they ever land in the warehouse — use `debug-failed-events`.
- Failed events already sit in a warehouse failed-events table and need recovering into the good
  events table — use the `recover-failed-events` skill.
- The job is designing schemas or entities rather than querying data already collected — use
  `design-tracking-plan`.
- The job is building or configuring dbt models — out of scope for this skill, planned for a later
  wave.

## Step 1 — load context

Read `.snowplow/agent-context.md`. If the file is missing, offer once to run
`setup-snowplow-context` before continuing. Take `warehouse` from it, and treat `mcp-available` as
a hint only. Confirm the warehouse with the user rather than re-establishing it from scratch, and
never modify the file — `setup-snowplow-context` is its only writer.

## Step 2 — route on warehouse

| `warehouse` value | Where to go |
|---|---|
| `snowflake` | `reference/dialect-snowflake.md` |
| `bigquery` | `reference/dialect-bigquery.md` |
| `databricks` | `reference/dialect-databricks.md` |
| `redshift` | `reference/dialect-redshift.md` |
| `athena` | Athena is typically the failed-events diagnosis engine, not the analyst warehouse — check whether the user actually means failed events (→ `debug-failed-events` or `recover-failed-events`). For a genuine good-event query via Athena, fetch current docs at runtime. |
| `none-yet` / `unknown` / missing | Offer to run `setup-snowplow-context` once; otherwise ask which warehouse. |

## Step 3 — table format (Snowflake and Databricks only)

Determine whether the table is a native table or a Lake Loader table (Iceberg on Snowflake, Delta
on Databricks) before writing any entity access. If the Snowplow Console MCP is available in this
session, look up the pipeline's loader/destination through it — live tool presence is the truth,
`mcp-available` is only a hint. Otherwise ask the user once. If the table is Iceberg, the dialect
sheet's Iceberg section governs entity access. Catalog specifics (Hive Metastore, Polaris, AWS
Glue, Databricks Unity) are combinatorial — always a runtime docs lookup via `fetch-snowplow-docs`,
never assumed.

## Step 4 — route by task

| Task | Where to go |
|---|---|
| Unnesting or joining entity/event columns | The dialect sheet from Step 2 |
| Duplicate rows or double-counting | `reference/deduplication.md` |
| Excluding bot traffic | `reference/bot-filtering.md` |
| Which timestamp to filter or order by | `reference/timestamps.md` |
| Counting users or sessions | `reference/identity-and-sessions.md` |
| Engagement or time-on-page | `reference/page-pings-and-engagement.md` |
| A field whose history spans schema major versions (`_1` and `_2` columns or tables) | `reference/schema-versions.md` |

## Step 5 — execute or hand off

If a warehouse query tool is live in the session, offer to run the SQL and iterate on the results.
Otherwise emit the SQL for the user to run themselves. Never substitute a raw HTTP call for a
missing warehouse tool.

## Prefer derived tables

If dbt-derived tables (users, sessions, page-views models) already exist in the warehouse, prefer
those for questions they answer — this skill is for querying atomic data directly, and dbt model
guidance is out of scope.

## Limits and alternatives

This skill teaches query patterns against atomic data, not data modeling — recurring dbt-style
models belong to a dbt project, not here. Behavioural bot thresholds (see
`reference/bot-filtering.md`) are exploratory and agreed with the user per site, never encoded as
fixed rules. Loader and catalog mechanics change over time and by deployment, so those specifics
always come from a live `fetch-snowplow-docs` lookup rather than this skill's own knowledge.
