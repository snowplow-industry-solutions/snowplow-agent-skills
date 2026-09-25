# Recovery SQL templates — BigQuery

Fill in every `<placeholder>`. These are the exact statements to hand the user at each phase; the
reasoning behind them lives in `reference/` and the failure modes in `troubleshooting.md`. The SQL here
is identical to the canonical recovery flow — do not paraphrase it.

---

## Time window (applies to every query below)

Bounding `load_tstamp` scans far less data (and prunes partitions on the typically
`load_tstamp`-partitioned tables). Ask the user in Phase 1 **when the failures occurred** and prefer
a **bounded range**:

```sql
load_tstamp >= TIMESTAMP('2026-03-01') AND load_tstamp < TIMESTAMP('2026-03-10')
```

If the timeframe is unknown, fall back to a **lookback**:

```sql
DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
```

Use the **same** window in every query (identification, inspection, test, INSERT, duplicate
pre-check) so the identified, validated, and recovered sets match.

---

## Identification query — summary (Phase 2, default)

Lead with this: one row per schema × app_id × failure type with volumes and time span. Best for
surveying what's failing without dumping every row, especially over a wide window.

**Flatten the failure array — one event can fail on several entities at once**, so the
`contexts_com_snowplowanalytics_snowplow_failure_1` array holds one element per failed entity. Reading
only `[SAFE_OFFSET(0)]` would hide every schema that isn't an event's *first* failure and silently drop
those events from the counts. `UNNEST` expands every element, so each failing schema is surfaced
wherever it sits in the array:

```sql
SELECT
    f.schema       AS failing_schema,
    app_id,
    f.failure_type AS failure_type,
    COUNT(*)       AS failed_events,
    MIN(f.timestamp) AS first_seen,
    MAX(f.timestamp) AS last_seen
FROM `<failed_project>.<failed_dataset>.<failed_table>`,
     UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)  -- or a bounded range (see Time window)
GROUP BY 1, 2, 3
ORDER BY failed_events DESC;
```

Each row is one failing (schema, app_id, failure_type) — an event that failed on two schemas appears
under both, counted once in each, which is correct. **Recover one schema per run; re-run this
identification after each** to see what remains.

## Identification query — row-level drill-in (after a schema is chosen)

Once the user picks a failing schema, inspect *why* it's failing for that schema + app_id. Scoped,
so it returns a handful of rows, not a flood.

Flatten and match the chosen schema on `f.schema`, so events where it isn't the first failure element
are included:

```sql
SELECT
    f.failure_type              AS failure_type,
    JSON_VALUE(f.errors[SAFE_OFFSET(0)].source) AS source,  -- contexts vs unstruct; a mix = separate runs (see reference/failure-context.md)
    f.errors                    AS errors,
    f.data                      AS data
FROM `<failed_project>.<failed_dataset>.<failed_table>`,
     UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)  -- or a bounded range
  AND f.schema = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

---

## Payload inspection query (Phase 3)

Expands the failure context with `UNNEST` so the user sees the real value behind each field. Render
each scalar with `JSON_VALUE` (never the strict `STRING()` accessor — it errors on a non-string JSON
value such as a number or boolean).

```sql
SELECT
    f.schema                        AS failing_schema,
    JSON_VALUE(f.data.field1)       AS field1,
    JSON_VALUE(f.data.field2)       AS field2
FROM `<failed_project>.<failed_dataset>.<failed_table>`,
     UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
  AND f.schema = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

Read the results for **how each value is encoded**, not just its content: a number shown in quotes
(`"5"`) is a *string-encoded* int, which the profiling step (Phase 3.5) will flag so the field is
recovered with `CAST(JSON_VALUE(...) AS INT64)` rather than the strict `INT64`. This `LIMIT 10` sample
just orients you — the profiling query quantifies it across all rows. Expect failures to be
**compound** — a single schema's failed events can combine a renamed/missing field *and* a wrong type.
The real target types come from the recovery column's `data_type`.

---

## Finding the recovery column name and its type (Phase 4)

Snowplow materialises a custom entity into a column named
`contexts_<vendor>_<schema_name>_<major_version>`, with dots in the vendor replaced by underscores —
so `iglu:com.example/user_entity/jsonschema/2-0-1` *should* map to
`contexts_com_example_user_entity_2`. But casing and edge cases vary, and this is the
`<recovery_column>` placeholder used everywhere downstream, so **never confirm it from memory — have
the user run this and read the real name and `data_type` back**:

```sql
SELECT column_name, data_type
FROM `<good_project>.<good_dataset>`.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = '<good_table>'
  AND LOWER(column_name) LIKE '%<schema_name_with_underscores>%'
ORDER BY column_name;
```

e.g. `LIKE '%user_entity%'`. The returned `column_name` is the exact `<recovery_column>`, and its
`data_type` (e.g. `ARRAY<STRUCT<_schema_version STRING, user_id INT64, user_name STRING>>`) is the
struct contract the recovery expression must match. If several rows come back (multiple major
versions), pick the one whose trailing `_<major>` matches the schema version being recovered.

## Inspect a validated event (ground the target shape in the schema)

The repaired entity's shape and field types are defined by the Iglu schema and materialised in the
recovery column's type — not chosen. Cross-check by pulling a recent **validated** event of the same
entity from the **good** table. `<recovery_column>` is the entity column found above.

**contexts source** — the column is `ARRAY<STRUCT<...>>`, so index element 0 and filter on `ARRAY_LENGTH`:

```sql
SELECT
    event_id,
    <recovery_column>[SAFE_OFFSET(0)] AS validated_entity
FROM `<good_project>.<good_dataset>.<good_table>`
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)  -- recent sample; widen if 0 rows
  AND ARRAY_LENGTH(<recovery_column>) > 0
LIMIT 10;
```

**unstruct source** — the `unstruct_event_*` column is a **single `STRUCT`, not an array**. Do **not**
use `[0]` / `[OFFSET(0)]` or `ARRAY_LENGTH` (they error on a non-array). Read it directly and filter on
`IS NOT NULL`:

```sql
SELECT
    event_id,
    <recovery_column> AS validated_entity
FROM `<good_project>.<good_dataset>.<good_table>`
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)  -- recent sample; widen if 0 rows
  AND <recovery_column> IS NOT NULL
LIMIT 10;
```

**Run this every time — don't assume the shape.** The recovery column's `data_type` is the authoritative
contract (field names, types, order, and whether `_schema_version` is a field); this query confirms you
read it correctly against a real row. Whether an unstruct column carries `_schema_version` is settled by
looking, not by defaulting.

The `load_tstamp` bound above is only there to keep the scan cheap — unlike the failed-side windows it
is **not** a correctness filter, so if the query returns nothing, **widen or drop it** before drawing
any conclusion: a validated example may simply predate the window. Do not infer types from the failed
payload alone (those values are exactly what failed validation).

**If the good table genuinely has no validated events for this entity — the column is missing, or
every row is NULL — stop and do not recover.** Recovering would make you, not the loader, establish that
column's shape; if it differs from what the loader later creates, the loader can fail on its next write.
Tell the user to send one valid event of this schema through the pipeline, let the loader create and
populate the column, then re-run the recovery. See `reference/failure-context.md`.

## Field profiling & coercibility confirmation (Phase 3.5 — gate before building the expression)

Before writing any recovery expression, profile **every field you'll recover** across **all** the
failed rows, so you pick the right extractor per field and confirm the whole population is recoverable
by one expression. This query can never error (`JSON_TYPE`, `JSON_VALUE`, `SAFE_CAST`, `COUNTIF`
tolerate any input), so it's always safe to suggest. Add one block per field, using that field's
**target type** (from the recovery column's `data_type`) in the `SAFE_CAST`:

```sql
WITH prep AS (
    SELECT f.data AS d
    FROM `<failed_project>.<failed_dataset>.<failed_table>`,
         UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS f
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
      AND app_id = '<app_id>'
      AND f.schema = '<failing_schema_uri>'
)
SELECT
    COUNT(*)                                                                            AS total_rows,
    -- one block per recovered field (swap <field> and its <TARGET_TYPE>, e.g. INT64):
    STRING_AGG(DISTINCT JSON_TYPE(d.<field>))                                           AS <field>_json_types,
    COUNTIF(JSON_TYPE(d.<field>) IS NULL)                                               AS <field>_absent,
    COUNTIF(JSON_TYPE(d.<field>) = 'null')                                              AS <field>_json_null,
    COUNTIF(JSON_TYPE(d.<field>) NOT IN ('null')
            AND SAFE_CAST(JSON_VALUE(d.<field>) AS <TARGET_TYPE>) IS NULL)              AS <field>_uncoercible
FROM prep;
```

Read the result and decide **per field** (full decision table: `reference/bigquery.md`),
in order:

1. **Any `_uncoercible > 0`** → the failed rows do **not** share one recovery; some values can't become
   the target type. Do **not** suggest a recovery expression yet — list the offending rows and
   partition or narrow scope with the user first.
2. **Any `_absent > 0` or `_json_null > 0`** → some rows carry no value for the field: it's either
   missing (`_absent` — `JSON_TYPE` returns SQL `NULL`) or present but explicitly JSON `null`
   (`_json_null` — `JSON_TYPE` returns the string `'null'`). Both extract to SQL `NULL`. The `_json_null`
   counter exists because an explicit JSON `null` slips past *both* the `_absent` and `_uncoercible`
   checks otherwise, and `CAST(JSON_VALUE(...))` would then write a silent NULL into the good table — the
   exact silent-incomplete-recovery the no-`LAX` rule guards against. If the schema **requires** the
   field, partition those rows off; if it's **optional**, NULL is an acceptable recovered value. Either
   way, decide it with the user — don't let it pass unseen.
3. Otherwise, per field: `_json_types` is exactly the **native** type (`number` for INT64/FLOAT64,
   `string` for STRING, `boolean` for BOOL) → use the **strict** accessor; a **wrong/mixed** encoding
   (e.g. `string`, or `number,string`) with `_uncoercible = 0` → use **`CAST(JSON_VALUE(...) AS <TYPE>)`**.

Only once every field lands on `strict` or `CAST` with `_uncoercible = 0` do you build the expression —
which guarantees the test SELECT below runs clean.

## Recovery expression pattern (Phase 4) — build & confirm with the user

The shape depends on the failure **source** (from the drill-in). Field names, types, and order must
match the recovery column's `data_type` exactly — read that type, don't assume. Extract **each field
with the extractor the profiling step selected for it** — strict where the value is already the native
JSON type, `CAST(JSON_VALUE(...) AS <TYPE>)` where it's string-encoded or mixed. Read the payload from
**`failure_entry.data`** — the `UNNEST`ed failure element matching the schema being recovered (the
`prep` CTE in the test SELECT and generator below exposes it as `failure_entry`), not `[SAFE_OFFSET(0)]`,
so an event whose target failure isn't first is still read from the right element.

**contexts source** — reconstruct as an **array of one struct**. `_schema_version` is the first field
(the `contexts_*` `data_type` lists it):

```sql
[STRUCT(
    '1-0-0'                                                    AS _schema_version,  -- corrected version
    CAST(JSON_VALUE(failure_entry.data.user_id) AS INT64)      AS user_id,     -- profiled as string/mixed → coerce
    STRING(failure_entry.data.user_name)                       AS user_name    -- profiled as native string → strict
)]
```

**unstruct source** — reconstruct as a **single `STRUCT(...)`, no array brackets** (the
`unstruct_event_*` column is a bare `STRUCT`). Its `data_type` typically has **no `_schema_version`**
field — omit it unless the type lists it. Same per-field extractors:

```sql
STRUCT(
    CAST(JSON_VALUE(failure_entry.data.user_id) AS INT64) AS user_id,
    STRING(failure_entry.data.user_name)                  AS user_name
)
```

Both the strict accessors and `CAST(JSON_VALUE(...))` **error** on a value they can't convert — but
profiling has already confirmed every value coerces, so the expression is guaranteed to run clean.
**Do not use the lenient `LAX_` accessors:** they swallow an un-coercible value into NULL silently,
which would write an incomplete recovery into the good table without erroring.

`ARRAY(SELECT AS STRUCT ...)` is an equivalent contexts form, but the array literal `[STRUCT(...)]` is
simplest for a single element. Do **not** append `AS <column_name>` here — the generator adds it.
When embedding this into the generator query (Phase 7), **wrap the whole expression in a triple-quoted
string (`'''…'''`)**, not a plain `"…"`: a long single-line `"…"` literal breaks with
`Unclosed string literal` the moment the paste wraps it across lines, whereas a triple-quoted string
tolerates newlines. Its single quotes (`'1-0-0'`) still need no escaping inside `'''…'''`; just keep the
expression itself free of `'''` (it uses dot navigation and unquoted casts, so it will be).

## Test SELECT (Phase 4 — run and validate before the INSERT)

Emit this so the user can prove the reconstructed column is correct before any INSERT is generated.

```sql
WITH prep AS (
    SELECT src.*, failure_entry
    FROM `<failed_project>.<failed_dataset>.<failed_table>` src,
         UNNEST(src.contexts_com_snowplowanalytics_snowplow_failure_1) AS failure_entry
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
      AND app_id = '<app_id>'
      AND failure_entry.schema = '<failing_schema_uri>'
)
SELECT
    event_id,
    <recovery expression> AS recovered
FROM prep
LIMIT 20;
```

Because profiling (Phase 3.5) already confirmed every value coerces, and both the strict accessors and
`CAST(JSON_VALUE(...))` **error** on a bad value, a test SELECT that runs clean genuinely proves the
casts hold — no separate null-count step is needed. BigQuery has no `TYPEOF`; validate the struct
**shape** by comparing the reconstructed fields against the recovery column's `data_type`, and eyeball
the values. (Validation checklist: see `reference/bigquery.md`.)

---

## INSERT-generator query (Phase 7 — BigQuery builds the INSERT itself)

This joins the good and failed tables' `INFORMATION_SCHEMA.COLUMNS`, classifies each good-table
column, and emits the **full INSERT statement as a single text cell**. The user runs it, copies the
returned statement, and runs that.

The recovery expression is embedded as a **triple-quoted** string literal (`'''…'''`, so its single
quotes need no escaping and a wrapped paste can't break it). The outer `FORMAT(""" ... """)` template is
triple-double-quoted, so the single quotes around `<app_id>` / `<failing_schema_uri>` inside it are
literal. (How each column is classified: see
`reference/bigquery.md`.)

```sql
WITH good_cols AS (
    SELECT ordinal_position, column_name, data_type
    FROM `<good_project>.<good_dataset>`.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '<good_table>'
),
failed_cols AS (
    SELECT column_name
    FROM `<failed_project>.<failed_dataset>`.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '<failed_table>'
),
mapping AS (
    SELECT
        g.ordinal_position,
        CASE
            WHEN LOWER(g.column_name) = 'contexts_com_snowplowanalytics_snowplow_failure_1'
                THEN FORMAT('CAST(NULL AS %s) AS %s', g.data_type, g.column_name)
            WHEN LOWER(g.column_name) = 'load_tstamp'
                THEN 'CURRENT_TIMESTAMP() AS load_tstamp'
            WHEN LOWER(g.column_name) = LOWER('<recovery_column>')
                THEN '''<recovery_expression> AS <recovery_column>'''
            WHEN f.column_name IS NOT NULL
                THEN g.column_name
            ELSE FORMAT('CAST(NULL AS %s) AS %s', g.data_type, g.column_name)
        END AS select_expression
    FROM good_cols g
    LEFT JOIN failed_cols f ON LOWER(g.column_name) = LOWER(f.column_name)
),
select_clause AS (
    SELECT STRING_AGG(select_expression, ',\n    ' ORDER BY ordinal_position) AS columns_sql
    FROM mapping
)
SELECT FORMAT("""INSERT INTO `<target_project>.<target_dataset>.<target_table>`
WITH prep AS (
  SELECT src.*, failure_entry
  FROM `<failed_project>.<failed_dataset>.<failed_table>` src,
       UNNEST(src.contexts_com_snowplowanalytics_snowplow_failure_1) AS failure_entry
  WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
    AND app_id = '<app_id>'
    AND failure_entry.schema = '<failing_schema_uri>'
    AND JSON_VALUE(failure_entry.errors[SAFE_OFFSET(0)].source) = '<source>'
)
SELECT
    %s
FROM prep;""", columns_sql) AS generated_sql
FROM select_clause;
```

Notes:
- `<target_*>` is the **staging** table (staging path) or the **good** table (direct path). Column
  classification always comes from the **good** table, so a staging table created `LIKE` the good
  table lines up positionally.
- The generated INSERT is **positional** (no explicit column list): the SELECT expressions are
  emitted in good-table `ordinal_position` order, so they land in the right columns. This is exactly
  why the recovery struct's field order must match the target type.
- `<recovery_expression>` is the validated Phase-4 expression, inserted verbatim inside the double
  quotes; `<recovery_column>` is the entity column — the `contexts_*` column for a contexts run or the
  `unstruct_event_*` column for an unstruct run.
- `prep` **flattens** the failure array (`UNNEST`) and keeps the element whose `schema` matches the one
  being recovered, exposed as `failure_entry`. This recovers events where the target schema isn't the
  first failure element (reading `[SAFE_OFFSET(0)]` would skip them). The target schema appears once per
  event, so the flatten yields one row per recovered event — no fan-out.
- `<source>` scopes `prep` to one failure source — `contexts` or `unstruct`. A schema that failed both
  ways is two separate runs, one per source, each into its own column. If the drill-in showed a single
  source you can drop this predicate, but keeping it is harmless.
- Sibling entity columns (other `contexts_*`) **pass through** by name, so a valid entity the event also
  carried is preserved in the recovered row — not nulled.
- Before the user runs the generated INSERT, review it: recovery column carries the expression,
  failure column nulled, `load_tstamp` refreshed, and the column count matches the good table.
- If the failure-column null cast is rejected, or the recovery column wasn't matched, see
  `troubleshooting.md`.

---

## Staging-table patterns (Phase 6 / Phase 8 — staging write path)

### 1. Create an empty staging table that mirrors the good table

`LIKE` copies the exact column set, types, and order with zero rows:

```sql
CREATE TABLE `<staging_project>.<staging_dataset>.<staging_table>`
LIKE `<good_project>.<good_dataset>.<good_table>`;
```

### 2. Recovery INSERT into staging

Same generated INSERT (above), but with `<target_*>` set to the staging table (column classification
still comes from the good table).

### 3. Validate the staging table

```sql
SELECT COUNT(*) AS rows_in_staging FROM `<staging_project>.<staging_dataset>.<staging_table>`;

-- contexts source (ARRAY column):  SELECT event_id, <recovery_column>[SAFE_OFFSET(0)] ...
-- unstruct source (STRUCT column): SELECT event_id, <recovery_column>    ...  (no [0])
SELECT event_id, <recovery_column>
FROM `<staging_project>.<staging_dataset>.<staging_table>`
LIMIT 10;
```

### 4. Promote staging → good table

Column order matches (staging was created `LIKE` good), so `SELECT *` is safe:

```sql
INSERT INTO `<good_project>.<good_dataset>.<good_table>`
SELECT * FROM `<staging_project>.<staging_dataset>.<staging_table>`;
```

### 5. (Optional) drop the staging table afterwards

```sql
DROP TABLE `<staging_project>.<staging_dataset>.<staging_table>`;
```

### Direct-path time travel (compare before/after)

```sql
SELECT COUNT(*) FROM `<good_table>` FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR);
```

---

## Duplicate pre-check (Phase 2 / Phase 8 — run before the INSERT)

Confirms the events haven't already been recovered. The events being recovered only exist because
they failed validation, so any of their `event_id`s already present in the good table means a prior
recovery — running again would duplicate them. This one query **is** the whole check: it lists any
already-recovered `event_id`s, so an empty result is the all-clear and any rows are exactly the ones to
investigate. **Expect no rows.** (No separate `COUNT(*)` pass — it would bill the identical scan twice.)

The good-table side carries the **same `load_tstamp` window** as the failed side. A recovered row's
`load_tstamp` is stamped at recovery time, which is after the failures landed, so the window that bounds
the failed events safely bounds the good-table scan too. Without it, the scan reads the full history of
the good table on BigQuery (bytes billed ignore `LIMIT`).

```sql
SELECT g.event_id AS already_in_good
FROM `<good_project>.<good_dataset>.<good_table>` g
WHERE DATE(g.load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
  AND g.event_id IN (
    SELECT event_id
    FROM `<failed_project>.<failed_dataset>.<failed_table>`,
         UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS f
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), INTERVAL <days> DAY)
      AND app_id = '<app_id>'
      AND f.schema = '<failing_schema_uri>'
  );
```

Any rows returned are the overlapping `event_id`s — decide with the user (stop, narrow scope, or
proceed knowingly).
