---
name: recover-failed-events
description: "Recover schema-validation failed events back into the good atomic events table in the warehouse, by generating validation-gated recovery SQL through an interactive 8-phase flow. Supports Athena/Iceberg, BigQuery, Databricks, and Snowflake — routes on the warehouse. Handles ValidationError and ResolutionError, context-entity and self-describing (unstruct) failures. Triggers: recover failed events in the warehouse, reprocess failed events with SQL, reinsert schema-validation failures, recover failed events into the atomic events table, warehouse failed event recovery, recover Athena Iceberg failed events, recover BigQuery failed events, recover Databricks failed events, recover Snowflake failed events."
---

# Recover failed events in the warehouse

Snowplow writes schema-validation failures to a **failed events table**. Each failure carries the
original payload plus a `contexts_com_snowplowanalytics_snowplow_failure_1` column describing why it
failed. This skill reconstructs the repaired entity and inserts the events back into the **good atomic
events table** — building the SQL with you, one validated step at a time, never blind.

The reconstruction is warehouse-specific (type systems, JSON extraction, array handling all differ),
but the *decision flow* is the same everywhere. This SKILL.md carries that shared flow. The
per-warehouse specifics — the dialect tokens, the strict-typing rules, the runnable SQL — live in a
**dialect pack** you load once you know the warehouse.

## Three rules that shape everything

1. **One step at a time.** When a query needs a value another query establishes (a column name, a
   type), run that first and substitute the real value yourself. Never emit a guessed or placeholder
   value with a "swap this in" note. Never batch a query with the one whose output it depends on. Never
   ask the user to hand-edit the SQL.
2. **The target shape is defined by the data, never guessed.** Ground every reconstruction in the
   recovery column's real type (see the pack's *grounding source* — a `DESCRIBE`, an `INFORMATION_SCHEMA`
   type, or a validated good-table row) plus Phase 3.5 profiling. Do not infer the shape from the Iglu
   schema alone.
3. **Human-in-the-loop at every gate.** The user picks the schema, confirms the fix hypothesis, and
   approves the test SELECT before any write. You generate and explain; they decide.

**One run recovers one schema, one source.** A schema that failed both as a context entity and as the
self-describing event is two separate runs into two different columns.

## Where the knowledge lives

- **`reference/failure-context.md`** — shared, warehouse-independent: the failure-context data model,
  the `source` / contexts-vs-unstruct distinction, the per-warehouse navigation table, column
  classification, and the profiling/validation gates.
- **`reference/<warehouse>.md`** — the dialect pack: the token table, the strict-typing / classification
  rules, and the reconstruction forms specific to that warehouse. Load it in Phase 1.
- **`templates/<warehouse>.md`** — every runnable query for the 8-phase flow, in that dialect.
- **`examples/<warehouse>.md`** — one worked recovery end-to-end for that warehouse.
- **`troubleshooting.md`** — shared failure modes plus a per-warehouse section.
- **`scripts/generate_insert_athena.py`** / **`scripts/generate_insert_databricks.py`** — the local
  INSERT generators (Athena and Databricks only; BigQuery and Snowflake build the INSERT in-warehouse).
- Customer-facing overview: the Snowplow help-centre article on warehouse recovery with Claude.

## Phase 1 — Pick the warehouse, then gather tables

First, read `.snowplow/agent-context.md` if the project has one (written by `setup-snowplow-context`).
Its `warehouse` key routes the run:

| `warehouse` | What to do |
|---|---|
| `athena` / `bigquery` / `databricks` / `snowflake` | Load that dialect pack and continue. |
| `redshift` | Warehouse SQL recovery **isn't supported on Redshift**. Say so and stop — the failed-events table shape, the entity columns and the reconstruction primitives all differ, and there is no tested pack. Don't improvise one from a sibling dialect. |
| `none-yet` / `unknown` / missing | Offer to run `setup-snowplow-context` once, then ask which warehouse holds their events. |
| anything else | Flag the mismatch and stop rather than guessing a pack. |

If the file is absent, ask the user which warehouse holds their events, and offer once to run
`setup-snowplow-context` so this and every later skill stops asking.

**Load `reference/<warehouse>.md` now.** Everything below refers to the pack's *token table* for the
dialect. Rows are referred to **by their exact names** — *Failure-array expand*, *Read a `data`
scalar*, *Cast*, *contexts reconstruction* / *unstruct reconstruction*, *Profiling probe
(non-erroring)*, *Validation signal*, *Grounding source*, *Staging create*, *Time travel*,
*Good-entity array index* / *array size*, *Recorded schema URI*, *Recovery-expr embedding*,
*INSERT-build mechanism* — and to `templates/<warehouse>.md` for the SQL.

Then ask for both tables and the failure window in the opening message, so no placeholders linger:

> "What are your failed and good events tables (fully qualified — see the pack for this warehouse's
> naming), and roughly when did the failures happen (a date or range — helps me scan less)? If you're
> not sure, I'll use a lookback window. And do you want help finding recent failed events, or do you
> already know the failing schema and app_id you want to recover?"

Help identifying → Phase 2. Already know the target → collect the failing schema Iglu URI, app_id, and
target entity column → Phase 3. Carry one **time window** through every query from here so the
identified, validated, and recovered sets match.

**Prerequisite (Athena and Databricks only):** these two build the INSERT with a local script
(`scripts/generate_insert_athena.py` / `scripts/generate_insert_databricks.py`), which needs Python
3.6+ and, in Claude Desktop, the "Code execution and file creation" setting enabled. The pack notes the
in-warehouse fallback if neither is available (Databricks has one; Athena's script can be hand-assembled
from the template).

## Phase 2 — Identify the failures

Lead with the **summary identification query** (`templates/<warehouse>.md`): one row per schema × app_id
× failure type, with volumes. Read off which schemas fail, at what rate, which `failure_type`, which
app_ids. Have the user pick **one** schema.

**One event can fail on several entities at once**, so the failure column is an array with one
element per failed entity. The identification query **flattens** it (the pack's *Failure-array
expand*) so a schema is surfaced wherever it sits in the array — reading only the first element
would hide, and silently drop from the counts, every schema that isn't an event's first failure.
Recover **one schema per run** and re-run identification after each to see what remains. The whole
recovery path matches the target schema on the flattened element, so an event whose target failure
isn't first is still recovered.

Then run the **row-level drill-in** to form a fix hypothesis — including whether this is a
`ResolutionError` (Iglu couldn't resolve the schema) rather than a `ValidationError` (data didn't
conform). Read the `source` sub-field (contexts vs unstruct) from *inside* the `errors` element, using
the pack's navigation — never the failure top level.

Offer the **duplicate pre-check** (`templates/<warehouse>.md`). It lists any `event_id`s already in the
good table — expect **none**. If any come back, decide with the user (stop, narrow scope, or proceed
knowingly). If they skip it, note it and move on.

Then, if the failing schema is a **custom schema** (your own vendor, not a Snowplow / Iglu Central one),
get its Iglu JSON — **fetch before asking**. Try in order: the Console MCP if the official `snowplow`
plugin is installed (`.snowplow/agent-context.md`'s `mcp-available` records this); else `snowplow-cli
data-structures` with Console credentials; else a plain HTTP fetch of a public registry or a registry
URL the user gives. Only ask the user to paste it when the schema lives in a private authed registry you
can't reach. It's authoritative context — field names, types, `required`, enums — that catches a
renamed field and tells a genuinely-bad value from a wrong target type. It helps most in the
ResolutionError flow, where listing the registry finds the correct schema URI. Extra confidence, not a
substitute for the grounding in rule 2.

## Phase 3 — Inspect the payload

Run the **payload inspection query** to see how each field's value is actually encoded (a number sent
as a JSON string, a missing field, an extra one), not just its content. Use the pack's *Failure-array
expand* and *Read a `data` scalar*. This is where you confirm the fix hypothesis against real values and
spot compound failures (a renamed field *and* a wrong type together).

If the failure is **`additionalProperties`** — the payload carries a field the schema doesn't define —
stop and ask the user what should happen to that field before you profile anything. Their answer
decides which fields Phase 3.5 profiles. See *Recovering an `additionalProperties` failure* below.

## Phase 3.5 — Profile and confirm coercibility

Before building anything, run the **profiling gate**: a query that *cannot error* (it uses the pack's
*Profiling probe (non-erroring)*) reporting, per field across all rows, whether values are absent,
and whether they coerce to the target type. Decide per field, in order:

- any value **un-coercible** → **stop and partition** — the failed population isn't homogeneous, so one
  recovery expression won't fit all rows;
- any value **absent** → required field partitions the set; optional field can be NULL;
- else the field is uniform and coercible → **build it**.

This confirms one recovery expression covers the whole set before you write it. The pack notes the
warehouses where a per-field extractor choice (strict vs coercing cast) applies.

## Phase 4 — Build the recovery expression and prove it

Get the recovery column's real type from the pack's **grounding source** (run the finding-column query,
or paste a `DESCRIBE` — never confirm the column name from memory).

Then **run the pack's *inspect a validated event* query** and read the shape off a real good-table row.
Every time, on every warehouse: it is the only grounding Snowflake has, and elsewhere it is what catches
a misread column type. Whether an unstruct column carries `_schema_version` is settled by looking at a
good row, never by assuming and offering to check later.

**If that query returns no rows, stop.** Widen the lookback first — a validated example may predate the
window. If the good table genuinely holds no validated events for this entity, do not recover: see *No
validated events in the good table* in `reference/failure-context.md`. Tell the user to land one valid
event so the loader creates and populates the column, then re-run.

Then build the reconstruction with the pack's **contexts reconstruction** / **unstruct reconstruction**:

- **context entity** → an array of one struct, `_schema_version` first, matching the column's type
  field-for-field (name, type, order — strict warehouses insert positionally);
- **self-describing (unstruct)** → a single struct, no array wrapper, and `_schema_version` present only
  if the column type or the good row shows it (usually absent — confirm, don't assume).

Emit the **test SELECT** and read the pack's **validation signal** (a `typeof`/`TYPEOF` match, a clean
run, or a null-count check — warehouses differ on what proves correctness). Prove the reconstructed
column is right *before* any INSERT. If it's wrong, fix the expression and re-run — don't proceed.

## Phase 5 — Validate the gate

Confirm, on the test SELECT output: the reconstructed column's type/shape matches the target
field-for-field; the row count equals the failed-event count for this schema + app_id; there are no
unexpected NULLs (the pack flags the warehouse where a NULL is a silent bad-cast, not an error); and the
repaired values are actually corrected. Only pass the gate when all four hold.

## Phase 6 — Choose the write path

Ask the user, verbatim:

> "Two ways to write these back. **Staging (recommended):** I build a staging table mirroring the good
> table, insert the recovered rows there, you check them, then we promote with a single `INSERT … SELECT
> *`. **Direct:** we insert straight into the good events table. Staging is safer — it's a dry run you
> can inspect and drop. Which do you want?"

The pack carries the staging-create and time-travel syntax for this warehouse.

## Phase 7 — Generate the INSERT

Use the pack's **INSERT-build mechanism**:

- **Athena / Databricks** — the local script (`scripts/generate_insert_athena.py` /
  `scripts/generate_insert_databricks.py`). Give it the config, the good and failed table type listings,
  and the recovery expression; it emits a positional `INSERT`. The template's *Run the generator
  script* section lists every config key, input file and the invocation; the script header repeats them.
- **BigQuery / Snowflake** — the in-warehouse generator query, which builds the INSERT from
  `INFORMATION_SCHEMA`. Fill its placeholders with the real values you've established.

Either way, review the generated INSERT with the user: the recovery column carries the expression,
`load_tstamp` is refreshed, the failure column is excluded/nulled, and every sibling entity passes
through. Column classification is by membership in the failed table — no hardcoded atomic-column list.

## Phase 8 — Run, validate, promote

Run the INSERT. Re-run the validation checks against the landed rows (row count matches, values
correct, siblings preserved). On the staging path, promote with `INSERT INTO <good> SELECT * FROM
<staging>` and drop the staging table. Use the pack's *Time travel* syntax if you need a consistent
read across the write.

## Recovering a ResolutionError

A `ResolutionError` means Iglu couldn't resolve the schema — not that the data is bad. It's recoverable
in-warehouse when (a) the schema now resolves (transient registry, corrected URI, or a now-published
schema) and (b) a target column exists in the good table. Filter failed rows on the URI **as recorded
in the failure context** (the original, possibly-wrong one — the pack's **Recorded schema URI**), but
derive the target column and `_schema_version` from the **corrected** URI. Bail out only if the schema
can't be made to resolve or no target column can exist. Enrichment and adapter failures stay out of
scope.

## Recovering an `additionalProperties` failure

The event carried a field the schema doesn't define, so the target column has no home for that value.
Something has to happen to it, and by rule 3 that call is the user's. Dropping it silently loses data;
guessing a destination for it is worse. **Ask before building the expression.**

Show the stray field and its real values from the payload inspection, then put the options in words:

> "These events failed because they carry a `<field>` the schema doesn't define — example values
> `<v1>`, `<v2>`. The recovered event can't keep it as-is. How would you like it handled?
> **1. Drop it** — I recover every other field and discard `<field>`. That value won't be in the
> recovered events, though the failed-events table still holds the originals.
> **2. Map it onto a field the schema does define** — if `<field>` is a rename or misspelling of an
> existing field, I read the value from `<field>` and write it under that field's name. Tell me which.
> **3. Neither** — if the value genuinely belongs in the schema, the schema needs a new field first.
> Evolve it, let the loader create the column, then recover."

Handling the answer:

- **Drop** → reconstruct only the fields the target type lists. State in the run summary which field was
  dropped and how many events it affected. Never let a discard pass unmentioned.
- **Map** → read from the payload key, emit under the **target** field name; the two don't have to
  match, since the payload key is a JSON path and the target is a struct field/object key. Confirm the
  chosen target actually appears in the recovery column's type and in the validated good row (Phase 4)
  before building.
- **Neither** → stop. A field the schema doesn't define has no column to recover into, and this skill
  can't evolve the schema.

If one event tripped on several stray fields, ask per field — a drop and a map can both apply to the
same event.

## Recovering an unstruct (self-describing event) failure

The self-describing event lands in a single `unstruct_event_*` column, not a `contexts_*` array. Four
differences from the contexts path:

1. the target is a **single struct**, not an array of structs;
2. reconstruct with the pack's *unstruct reconstruction* (no array wrapper);
3. it usually has **no `_schema_version`** field — but confirm that against the column type and a
   validated good row rather than assuming it; match what you observe;
4. drop the pack's **Good-entity array index** and **Good-entity array size** from the inspection and
   validation queries — read the column directly and filter `IS NOT NULL`.

A failed unstruct event that also carried a valid context entity keeps that entity in its own column;
the pass-through preserves it. Do not null sibling entity columns.

## When this skill is *not* the right answer

- The good table has **no validated events for this entity** — the recovery column is missing, or every
  row is NULL. Recovering would make you, not the loader, define the column's shape, which can break the
  loader's next write to that table. Land one valid event first, then recover.
- The profiling gate shows values that **can't coerce** to the target type — the data is genuinely bad,
  not mis-typed. Fix the source or the schema instead.
- The failure is an **enrichment or adapter** failure, not schema validation. That's a different
  pipeline stage.
- The events never had a valid form to recover *to* (a schema that was never published and never will
  be, with no target column). Register the schema first.
- You're **debugging why events fail** rather than recovering known-good ones — use `debug-failed-events`.
