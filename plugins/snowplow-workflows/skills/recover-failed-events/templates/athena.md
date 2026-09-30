# Recovery SQL templates — Athena Iceberg

Fill in every `<placeholder>`. These are the exact statements to hand the user at each phase; the
reasoning behind them lives in `reference/` and the failure modes in `troubleshooting.md`. The SQL here
is identical to the canonical recovery flow — do not paraphrase it.

The bundled `scripts/generate_insert_athena.py` implements the column-classification and type-conversion
rules for the full INSERT (Phase 7) — prefer running it. Use the statements here directly for the
identification/inspection/test queries, and as the fallback when code execution is unavailable.

---

## Time window (applies to every query below)

The failed/good tables are partitioned by `load_tstamp_day`, so bounding `load_tstamp` prunes
partitions and scans far less data. Ask the user in Phase 1 **when the failures occurred** and
prefer a **bounded range**:

```sql
load_tstamp >= TIMESTAMP '2026-03-01 00:00:00' AND load_tstamp < TIMESTAMP '2026-03-10 00:00:00'
```

If the timeframe is unknown, fall back to a **lookback** (shown in the templates below):

```sql
load_tstamp > current_timestamp - interval '<days>' day
```

Use the **same** window in every query (identification, inspection, test, INSERT, duplicate
pre-check) so the identified, validated, and recovered sets match. The bundled generator accepts
either form (`LOAD_TSTAMP_START`/`LOAD_TSTAMP_END`, or `DAYS_LOOKBACK`).

---

## Identification query — summary (Phase 2, default)

Lead with this: one row per schema × app_id × failure type × source, with volumes and time span. Best for
surveying what's failing without dumping every row, especially over a wide window.

**Flatten the failure array — one event can fail on several entities at once**, so the
`contexts_com_snowplowanalytics_snowplow_failure_1` array holds one element per failed entity. Reading
only `[1]` would hide every schema that isn't an event's *first* failure and silently drop those events
from the counts. `CROSS JOIN UNNEST` expands every element, so each failing schema is surfaced wherever
it sits in the array:

```sql
SELECT
    failure_ctx.schema         AS failing_schema,
    app_id,
    failure_ctx.failure_type   AS failure_type,
    json_extract_scalar(failure_ctx.errors[1], '$.source') AS source,
    COUNT(*)                   AS failed_events,
    MIN(failure_ctx.timestamp) AS first_seen,
    MAX(failure_ctx.timestamp) AS last_seen
FROM <failed_database>.<failed_table>
CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
WHERE load_tstamp > current_timestamp - interval '<days>' day   -- or a bounded range (see Time window)
GROUP BY
    failure_ctx.schema,
    app_id,
    failure_ctx.failure_type,
    json_extract_scalar(failure_ctx.errors[1], '$.source')
ORDER BY failed_events DESC
```

Each row is one failing (schema, app_id, failure_type, source) — an event that failed on two schemas
appears under both, counted once in each, which is correct. `source` is the fourth key because a
schema that failed **both** as a context entity and as the self-describing event needs one run per
source: splitting it here makes each row's count the exact target for the Phase 5 row-count gate.
**Recover one schema per run; re-run this identification after each** to see what remains.

## Identification query — row-level drill-in (after a schema is chosen)

Once the user picks a failing schema, inspect *why* it's failing for that schema + app_id. Scoped,
so it returns a handful of rows, not a flood.

Flatten and match the chosen schema on `failure_ctx.schema`, so events where it isn't the first failure
element are included:

```sql
SELECT
    failure_ctx.failure_type       AS failure_type,
    json_extract_scalar(failure_ctx.errors[1], '$.source') AS source,  -- errors is array(varchar) JSON strings → JSON-extract; contexts vs unstruct, a mix = separate runs (see reference/failure-context.md)
    failure_ctx.errors             AS errors,
    failure_ctx.data               AS data
FROM <failed_database>.<failed_table>
CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
WHERE load_tstamp > current_timestamp - interval '<days>' day   -- or a bounded range (see Time window)
  AND failure_ctx.schema = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10
```

---

## Payload inspection query (Phase 3)

Expands the failure context with `UNNEST` so the user sees the real value behind each field, read
with `json_extract_scalar` (Athena does not support deep nested dot notation on the array — you must
`UNNEST` first). Read the results for **how each value is encoded**, not just its content, and note
the exact field names.

```sql
SELECT
    failure_ctx.schema                                 AS failing_schema,
    json_extract_scalar(failure_ctx.data, '$.field1')  AS field1,
    json_extract_scalar(failure_ctx.data, '$.field2')  AS field2
FROM <failed_database>.<failed_table>
CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
WHERE load_tstamp > current_timestamp - interval '<days>' day
  AND failure_ctx.schema = '<failing_schema_uri>'
LIMIT 10
```

---

## Inspect a validated event (ground the target shape against a real row)

`DESCRIBE` on the good table gives the authoritative struct contract — field names, types, order, and
whether `_schema_version` is a field. **Run this query too, every time**, to confirm you read that
contract correctly against a real validated row of the same entity. `<recovery_column>` is the entity
column from the good-table `DESCRIBE`.

**contexts source** — the column is `ARRAY(ROW(...))`. Trino arrays are **1-based**, so index element
`[1]`, and size it with `cardinality`:

```sql
SELECT
    event_id,
    <recovery_column>[1] AS validated_entity
FROM <good_database>.<good_table>
WHERE load_tstamp > current_timestamp - interval '<days>' day  -- recent sample; widen if 0 rows
  AND cardinality(<recovery_column>) > 0
LIMIT 10
```

**unstruct source** — the `unstruct_event_*` column is a single `ROW`, not an array. Do **not** use
`[1]` or `cardinality` (both error on a row). Read it directly and filter on `IS NOT NULL`. For the
Phase 7 generator, set `FAILURE_SOURCE = "unstruct"` and point `RECOVERY_COLUMN` at this
`unstruct_event_*` column:

```sql
SELECT
    event_id,
    <recovery_column> AS validated_entity
FROM <good_database>.<good_table>
WHERE load_tstamp > current_timestamp - interval '<days>' day  -- recent sample; widen if 0 rows
  AND <recovery_column> IS NOT NULL
LIMIT 10
```

The `load_tstamp` bound above is only there to keep the scan cheap — unlike the failed-side windows it
is **not** a correctness filter, so if the query returns nothing, **widen or drop it** before drawing
any conclusion: a validated example may simply predate the window. Do not infer types from the failed
payload alone (those values are exactly what failed validation).

**If the good table genuinely has no validated events for this entity — the column is missing from
`DESCRIBE`, or every row is NULL — stop and do not recover.** Recovering would make you, not the loader,
establish that column's shape; if it differs from what the loader later creates, the loader can fail on
its next write. Tell the user to send one valid event of this schema through the pipeline, let the
loader create and populate the column, then re-run the recovery. See `reference/failure-context.md`.

---

## Field profiling & coercibility confirmation (Phase 3.5 — gate before building the expression)

Before writing any recovery expression, profile **every field you'll recover** across **all** failed
rows, to confirm the whole population is recoverable by one expression. This query can't error
(`json_extract_scalar`, `TRY_CAST`, `count_if`). `<failure_data>` is the payload JSON string,
`failure_ctx.data` from the flattened matching element. Add one block per field, using that
field's **target type** (from the good-table `DESCRIBE`) in the `TRY_CAST`:

```sql
WITH prep AS (
    SELECT failure_ctx.data AS d
    FROM <failed_database>.<failed_table>
    CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
    WHERE <load_tstamp window>
      AND failure_ctx.schema = '<failing_schema_uri>'
      AND app_id = '<app_id>'
)
SELECT
    COUNT(*)                                                                              AS total_rows,
    -- one block per recovered field (swap <field> and its <TARGET_TYPE>):
    count_if(json_extract_scalar(d, '$.<field>') IS NULL)                                 AS <field>_absent,
    count_if(json_extract_scalar(d, '$.<field>') IS NOT NULL
             AND TRY_CAST(json_extract_scalar(d, '$.<field>') AS <TARGET_TYPE>) IS NULL)  AS <field>_uncoercible
FROM prep;
```

Decide, per field: any `_uncoercible > 0` → **stop, list the offending rows, and partition/scope**. Any
`_absent > 0` → required→partition, optional→NULL. Otherwise build the expression —
`CAST(json_extract_scalar(...) AS <type>)` runs clean because profiling confirmed every value coerces.
(Full decision table: `reference/athena.md`.)

---

## Recovery expression pattern (Phase 4) — build & confirm with the user

The shape depends on the failure **source** (from the drill-in), mapping each
`json_extract_scalar(failure_data, '$.field')` to its target field/type in the **same order** as the
good-table struct.

**contexts source** — `CAST(ARRAY[ROW(...)] AS ARRAY(ROW(...)))`. `_schema_version` is the first field
(the `contexts_*` struct in DESCRIBE lists it):

```sql
CAST(
    ARRAY[
        ROW(
            '1-0-0',                                                         -- corrected _schema_version
            CAST(json_extract_scalar(failure_data, '$.field1') AS VARCHAR),
            CAST(json_extract_scalar(failure_data, '$.field2') AS BIGINT)
        )
    ]
AS ARRAY(ROW(_schema_version VARCHAR, field1 VARCHAR, field2 BIGINT)))
```

**unstruct source** — a **single `CAST(ROW(...) AS ROW(...))`, no outer `ARRAY[...]`/`ARRAY(...)`** (the
`unstruct_event_*` column is a single `ROW`). Its DESCRIBE struct typically has **no `_schema_version`**
field (only `contexts_*` does) — omit it unless DESCRIBE lists it:

```sql
CAST(
    ROW(
        CAST(json_extract_scalar(failure_data, '$.field1') AS VARCHAR),
        CAST(json_extract_scalar(failure_data, '$.field2') AS BIGINT)
    )
AS ROW(field1 VARCHAR, field2 BIGINT))
```

Entity columns must be constructed with `CAST(... AS ARRAY(ROW(...)))` (contexts) or `CAST(... AS
ROW(...))` (unstruct). The `ARRAY<STRUCT<...>>` / `STRUCT<...>` form in DESCRIBE output is DDL-only and
invalid in a query. Do **not** append `AS <column_name>` here — the generator adds it.

---

## Test SELECT + type validation (Phase 4 — run and validate before the INSERT)

Emit this so the user can prove the reconstructed column is correct before any INSERT is generated.
It wraps the recovery expression in the CTEs and adds `typeof(...)` so the exact Athena type can be
compared against the good-table column definition.

```sql
WITH prep AS (
    SELECT *
    FROM <failed_database>.<failed_table>
    WHERE load_tstamp > current_timestamp - interval '<days>' day
      AND app_id = '<app_id>'
      -- keep events that failed on this schema at ANY array position (not just [1]); the UNNEST below
      -- then picks the matching element. any_match prunes the scan without dropping index-1+ events.
      AND any_match(contexts_com_snowplowanalytics_snowplow_failure_1, x -> x.schema = '<failing_schema_uri>')
),
unnested AS (
    SELECT prep.*, failure_ctx.data AS failure_data
    FROM prep
    CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
    WHERE failure_ctx.schema = '<failing_schema_uri>'
    -- mixed-source schema only: AND json_extract_scalar(failure_ctx.errors[1], '$.source') = '<source>'
)
SELECT
    event_id,
    <recovery expression>                AS recovered,
    typeof(<recovery expression>)        AS recovered_type
FROM unnested
LIMIT 20
```

`typeof()` returns the type as a string, e.g.
`array(row(_schema_version varchar, numbers bigint, true_or_false boolean, words varchar))` for a
contexts run, or `row(numbers bigint, true_or_false boolean, words varchar)` (no outer `array(...)`,
no `_schema_version`) for an unstruct run. Compare it field-for-field against the good-table column type
(validation checklist: `reference/athena.md`).

---

## Run the generator script (Phase 7 — the primary path)

`scripts/generate_insert_athena.py` implements the column classification, Hive→Athena type conversion
and reserved-word quoting deterministically, so the wide column list is not hand-assembled. Prefer it
whenever Python is available; it is standard-library only.

### Step 1 — collect both DESCRIBE outputs

```sql
DESCRIBE <good_database>.<good_table>;
DESCRIBE <failed_database>.<failed_table>;
```

Both are needed: membership in the failed table *is* the atomic-vs-custom classification.

### Step 2 — write the four input files

`good_describe.txt` and `failed_describe.txt` are the raw pastes. `recovery_expression.sql` is the
validated Phase-4 expression **without** a trailing `AS <column>` — single quotes stay single, it is
not embedded in a string literal here. And `config.json`:

```json
{
  "GOOD_DATABASE": "<good_database>", "GOOD_TABLE": "<good_table>",
  "FAILED_DATABASE": "<failed_database>", "FAILED_TABLE": "<failed_table>",
  "RECOVERY_COLUMN": "<recovery_column>",
  "FAILED_SCHEMA": "<failing_schema_uri>",
  "APP_ID": "<app_id>",
  "DAYS_LOOKBACK": <days>,
  "FAILURE_SOURCE": "<contexts|unstruct>",
  "TARGET_DATABASE": "<target_database>", "TARGET_TABLE": "<target_table>"
}
```

`RECOVERY_COLUMN` is the `contexts_*` column for a **contexts** run or the `unstruct_event_*` column
for an **unstruct** run — the same column whose `DESCRIBE` type you matched in Phase 4.
**`FAILURE_SOURCE`** (`contexts` or `unstruct`) scopes `prep` to that source, so a schema that failed
both ways recovers one source per run into its own column; omit it only when the drill-in showed a
single source. Leaving it out on a mixed-source schema double-inserts the `event_id`. `TARGET_*` is
optional (defaults to `GOOD_*`); set it to the **staging** table for the staging path. For a bounded
window instead of a lookback, drop `DAYS_LOOKBACK` and set `"LOAD_TSTAMP_START": "<start>"` (and
optionally `"LOAD_TSTAMP_END": "<end>"`) — it prunes partitions.

### Step 3 — run it

```bash
python3 scripts/generate_insert_athena.py \
    --config config.json \
    --good-describe good_describe.txt \
    --failed-describe failed_describe.txt \
    --recovery-expr recovery_expression.sql \
    --out recovery.sql
```

It prints a sanity summary (good/failed column counts, pass-through, nulled) to stderr and writes the
runnable INSERT to `recovery.sql`; drop `--out` to print it instead. If it warns the recovery column
wasn't found, `RECOVERY_COLUMN` doesn't match the good table — fix it and re-run. Review `recovery.sql`
with the user (recovery column carries the expression, failure column excluded, `load_tstamp` refreshed,
positional order matches the good table), then have them run it.

**In Claude Desktop** the user must enable *Code execution and file creation* (Settings → Capabilities)
for the script to run; it's off by default. In Claude Code it's already available. If code execution
isn't available at all, hand-assemble from the template below.

---

## Full INSERT template (Phase 7 — the generator emits this)

Prefer the bundled `scripts/generate_insert_athena.py`, which builds the wide column list deterministically
from both DESCRIBE outputs. This is the shape it produces (and the fallback to build inline when code
execution is unavailable). Escape single quotes in `app_id` and the schema URI as `''`. Place any
`--` comment on a **leading** line of a SELECT expression, never trailing (a trailing comment eats
the comma that joins expressions).

```sql
INSERT INTO <good_database>.<good_table> (
    <comma-separated column list, failure column excluded>
)
WITH prep AS (
    SELECT *
    FROM <failed_database>.<failed_table>
    WHERE load_tstamp > current_timestamp - interval '<days>' day
      AND app_id = '<app_id>'
      AND any_match(contexts_com_snowplowanalytics_snowplow_failure_1,
                    x -> x.schema = '<failing_schema_uri>')
),
unnested AS (
    SELECT
        prep.*,
        failure_ctx.data AS failure_data
    FROM prep
    CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)
    WHERE failure_ctx.schema = '<failing_schema_uri>'
    -- mixed-source schema only: AND json_extract_scalar(failure_ctx.errors[1], '$.source') = '<source>'
)
SELECT
    <comma-separated SELECT expressions in the same column order>
FROM unnested;
```

- `<good_database>.<good_table>` is the **staging** table (staging path) or the **good** table
  (direct path); columns are always classified from the **good-table** DESCRIBE. Set
  `TARGET_DATABASE`/`TARGET_TABLE` on the generator for the staging path.
- The recovery column carries the validated Phase-4 expression; the failure column is excluded
  entirely; `load_tstamp` is refreshed to `current_timestamp`.
- The `unnested` CTE filters `failure_ctx.schema` (and the source, for a mixed-source schema) so an
  event with a **multi-entry failure array** yields one row for the recovered entity, not one per
  failed entity. Without it the `UNNEST` fans the event into N rows — the same `event_id` inserted
  several times, each built from a different entry's payload.
- How each column is classified (pass-through vs null-cast, Hive→Athena type conversion,
  reserved-word quoting): `reference/athena.md`.

---

## Staging-table patterns (Phase 6 / Phase 8 — staging write path)

The staging table mirrors the good table's schema exactly, so the recovery INSERT (retargeted to
staging) and the final promote both line up positionally.

### 1. Create an empty staging table that mirrors the good table

```sql
CREATE TABLE <staging_database>.<staging_table>
WITH (
    table_type = 'ICEBERG',
    location = 's3://<your-bucket>/<path>/<staging_table>/',
    is_external = false
)
AS SELECT * FROM <good_database>.<good_table> WHERE 1 = 0;
```

`WHERE 1 = 0` clones the schema and column order with zero rows. Ask the user for the S3 location.

### 2. Recovery INSERT into staging

Same generated INSERT (above), but targeting the staging table — run the generator with
`TARGET_DATABASE`/`TARGET_TABLE` set to the staging table (column classification still comes from
the good-table DESCRIBE).

### 3. Validate the staging table

```sql
SELECT COUNT(*) AS rows_in_staging FROM <staging_database>.<staging_table>;

-- contexts source (ARRAY column):  SELECT event_id, <recovery_column>[1] ...   (1-based)
-- unstruct source (ROW column):    SELECT event_id, <recovery_column>    ...   (no [1])
SELECT event_id, <recovery_column>
FROM <staging_database>.<staging_table>
LIMIT 10;
```

### 4. Promote staging → good table

Column order matches (staging was cloned from good), so `SELECT *` is safe:

```sql
INSERT INTO <good_database>.<good_table>
SELECT * FROM <staging_database>.<staging_table>;
```

### 5. (Optional) drop the staging table afterwards

```sql
DROP TABLE <staging_database>.<staging_table>;
```

### Direct-path time travel (compare before/after)

Iceberg time travel compares the good table before/after a direct-path INSERT. Use Athena **engine v3**
syntax — `FOR TIMESTAMP AS OF` (the older `FOR SYSTEM_TIME AS OF` is engine v2, which Iceberg tables
reject):

```sql
SELECT COUNT(*) FROM <good_db>.<good_table> FOR TIMESTAMP AS OF TIMESTAMP '2024-01-15 12:00:00'
```

---

## Duplicate pre-check (Phase 2 / Phase 8 — run before the INSERT)

Confirms the events haven't already been recovered. The events being recovered only exist because
they failed validation, so any of their `event_id`s already present in the good table means a prior
recovery — running again would duplicate them. This one query **is** the whole check: it lists any
already-recovered `event_id`s, so an empty result is the all-clear and any rows are exactly the ones to
investigate. **Expect no rows.** (No separate `COUNT(*)` pass — it would scan the same data twice.)

The good-table side carries the **same `load_tstamp` window** as the failed side: a recovered row's
`load_tstamp` is stamped at recovery time (after the failures landed), so the window that bounds the
failed events safely bounds the good-table scan too, instead of scanning its full history.

```sql
SELECT g.event_id AS already_in_good
FROM <good_database>.<good_table> g
WHERE g.load_tstamp > current_timestamp - interval '<days>' day
  AND g.event_id IN (
    SELECT event_id
    FROM <failed_database>.<failed_table>
    WHERE load_tstamp > current_timestamp - interval '<days>' day
      AND app_id = '<app_id>'
      AND any_match(contexts_com_snowplowanalytics_snowplow_failure_1,
                    x -> x.schema = '<failing_schema_uri>')
  );
```

Any rows returned are the overlapping `event_id`s — decide with the user (stop, narrow scope, or
proceed knowingly).
