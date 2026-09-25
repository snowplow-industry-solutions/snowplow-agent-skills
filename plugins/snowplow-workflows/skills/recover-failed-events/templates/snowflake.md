# Recovery SQL templates — Snowflake

Fill in every `<placeholder>`. These are the exact statements to hand the user at each phase; the
reasoning behind them lives in `reference/` and the failure modes in `troubleshooting.md`. The SQL here
is identical to the canonical recovery flow — do not paraphrase it. Unlike the Athena and Databricks
paths, Snowflake uses **no local script**: the INSERT-generator query reads both tables'
`INFORMATION_SCHEMA.COLUMNS` and builds the wide INSERT itself.

---

## Time window (applies to every query below)

Bounding `load_tstamp` scans far less data. Ask the user in Phase 1 **when the failures occurred**
and prefer a **bounded range**:

```sql
load_tstamp >= '2026-03-01'::TIMESTAMP AND load_tstamp < '2026-03-10'::TIMESTAMP
```

If the timeframe is unknown, fall back to a **lookback**:

```sql
load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'
```

Use the **same** window in every query (identification, inspection, test, INSERT, duplicate
pre-check) so the identified, validated, and recovered sets match.

---

## Identification query — summary (Phase 2, default)

Lead with this: one row per schema × app_id × failure type with volumes and time span. Best for
surveying what's failing without dumping every row, especially over a wide window.

**Flatten the failure array — one event can fail on several entities at once**, so the
`contexts_com_snowplowanalytics_snowplow_failure_1` array holds one element per failed entity. Reading
only `[0]` would hide every schema that isn't an event's *first* failure and silently drop those events
from the counts. `LATERAL FLATTEN` expands every element, so each failing schema is surfaced wherever
it sits in the array:

```sql
SELECT
    f.value:schema::STRING       AS failing_schema,
    app_id,
    f.value:failure_type::STRING AS failure_type,
    COUNT(*)                     AS failed_events,
    MIN(f.value:timestamp::TIMESTAMP) AS first_seen,
    MAX(f.value:timestamp::TIMESTAMP) AS last_seen
FROM <failed_database>.<failed_schema>.<failed_table>,
     LATERAL FLATTEN(input => contexts_com_snowplowanalytics_snowplow_failure_1) f
WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'   -- or a bounded range (see Time window)
GROUP BY
    f.value:schema::STRING,
    app_id,
    f.value:failure_type::STRING
ORDER BY failed_events DESC;
```

Each row is one failing (schema, app_id, failure_type) — an event that failed on two schemas appears
under both, counted once in each, which is correct. **Recover one schema per run; re-run this
identification after each** to see what remains.

## Identification query — row-level drill-in (after a schema is chosen)

Once the user picks a failing schema, inspect *why* it's failing for that schema + app_id. Scoped,
so it returns a handful of rows, not a flood.

Flatten and match the chosen schema on `f.value:schema`, so events where it isn't the first failure
element are included:

```sql
SELECT
    f.value:failure_type::STRING     AS failure_type,
    f.value:errors[0]:source::STRING AS source,
    f.value:errors                   AS errors,
    f.value:data                     AS data
FROM <failed_database>.<failed_schema>.<failed_table>,
     LATERAL FLATTEN(input => contexts_com_snowplowanalytics_snowplow_failure_1) f
WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'   -- or a bounded range (see Time window)
  AND f.value:schema::STRING = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

The **`source`** column (`f.value:errors[0]:source` — nested under `errors`, **never** the top-level
`f.value:source`, which is NULL) tells you whether each row failed as a `contexts` entity or an
`unstruct` event. A mix means the recovery must be **split into separate runs into different columns** —
scope to one `source` and handle the other separately (see `reference/failure-context.md`). Carry the
same `errors[0]:source` predicate through the profiling, test, INSERT, and duplicate-check queries when
you scope by source.

---

## Payload inspection query (Phase 3)

Expands the failure context with `LATERAL FLATTEN` so the user sees the real value behind each field.

```sql
SELECT
    f.value:schema::STRING                AS failing_schema,
    f.value:data:field1::STRING           AS field1,
    f.value:data:field2::STRING           AS field2
FROM <failed_database>.<failed_schema>.<failed_table>,
     LATERAL FLATTEN(input => contexts_com_snowplowanalytics_snowplow_failure_1) f
WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'
  AND f.value:schema::STRING = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

Read the results for **how each value is encoded**, not just its content: a number shown in quotes
(`"5"`) is a *string-encoded* int, which the profiling step (Phase 3.5) will flag. This `LIMIT 10`
sample just orients you — the profiling query quantifies it across all rows. Expect failures to be
**compound** — a single schema's failed events can combine a renamed/missing field *and* a wrong
type. The real target types come from the recovery column / a validated event, not the payload.

---

## Finding the recovery column name (query, don't guess) (Phase 4)

Snowplow materialises a custom entity into a column named
`contexts_<vendor>_<schema_name>_<major_version>`, with dots in the vendor replaced by underscores —
so `iglu:com.example/user_entity/jsonschema/2-0-1` *should* map to
`contexts_com_example_user_entity_2`. But casing and edge cases vary, and this is the
`<recovery_column>` placeholder used everywhere downstream, so **never confirm it from memory — have
the user run this and read the real name back**:

```sql
SELECT column_name, data_type
FROM <good_database>.INFORMATION_SCHEMA.COLUMNS
WHERE LOWER(table_schema) = LOWER('<good_schema>')
  AND LOWER(table_name)   = LOWER('<good_table>')
  AND LOWER(column_name) LIKE '%<schema_name_with_underscores>%'
ORDER BY column_name;
```

e.g. `LIKE '%user_entity%'`. The returned `column_name` is the exact `<recovery_column>`. If several
rows come back (multiple major versions), pick the one whose trailing `_<major>` matches the schema
version being recovered.

## Inspect a validated event (ground the target types in the schema)

The repaired entity's shape and field types are defined by the Iglu schema, not chosen. The quickest
way to see them is to pull a recent **validated** event of the same entity from the **good** table
and read its keys and value types. Use this before building the recovery expression whenever the
intended types aren't already obvious. `<recovery_column>` is the entity column found above.

**contexts source** — the column is a VARIANT **array** of objects, so index element 0:

```sql
SELECT
    event_id,
    <recovery_column>[0]                              AS validated_entity,
    TYPEOF(<recovery_column>[0]:field1)               AS field1_type,
    TYPEOF(<recovery_column>[0]:field2)               AS field2_type
FROM <good_database>.<good_schema>.<good_table>
WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'  -- recent sample; widen if 0 rows
  AND <recovery_column> IS NOT NULL
  AND ARRAY_SIZE(<recovery_column>) > 0
LIMIT 10;
```

**unstruct source** — the `unstruct_event_*` column is a **single VARIANT object, not an array**. Drop
the `[0]` and `ARRAY_SIZE`; read the object directly:

```sql
SELECT
    event_id,
    <recovery_column>                                 AS validated_entity,
    TYPEOF(<recovery_column>:field1)                  AS field1_type,
    TYPEOF(<recovery_column>:field2)                  AS field2_type
FROM <good_database>.<good_schema>.<good_table>
WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'  -- recent sample; widen if 0 rows
  AND <recovery_column> IS NOT NULL
LIMIT 10;
```

**Run this every time — it is the only grounding Snowflake has.** The entity column is VARIANT, so there
is no DDL type to read: the `TYPEOF()` of each field on a known-good row *is* the target type your
`::TYPE` casts must produce, and a good row is the only thing that tells you whether an unstruct value
carries `_schema_version`. Never assume that shape and offer to verify it afterwards.

The `load_tstamp` bound above is only there to keep the scan cheap — unlike the failed-side windows it
is **not** a correctness filter, so if the query returns nothing, **widen or drop it** before drawing
any conclusion: a validated example may simply predate the window. Do not infer types from the failed
payload alone (the values are exactly what failed validation).

**If the good table genuinely has no validated events for this entity — the column is missing, or
every row is NULL — stop and do not recover.** On Snowflake you would have no grounding at all, and the INSERT
would make you, not the loader, establish the column; if it differs from what the loader later creates, the loader can fail on its next write.
Tell the user to send one valid event of this schema through the pipeline, let the loader create and
populate the column, then re-run the recovery. See `reference/failure-context.md`.

## Field profiling & coercibility confirmation (Phase 3.5 — gate before building the expression)

Before writing any recovery expression, profile **every field you'll recover** across **all** failed
rows, to confirm the whole population is recoverable by one expression. This query can't error
(`TYPEOF`, `TRY_CAST`, `COUNT_IF` tolerate any input). Add one block per field, using that field's
**target type** (from the recovery column / a validated event) in the `TRY_CAST`:

```sql
WITH prep AS (
    SELECT f.value:data AS d
    FROM <failed_database>.<failed_schema>.<failed_table>,
         LATERAL FLATTEN(input => contexts_com_snowplowanalytics_snowplow_failure_1) f
    WHERE <load_tstamp window>
      AND f.value:schema::STRING = '<failing_schema_uri>'
      AND app_id = '<app_id>'
)
SELECT
    COUNT(*)                                                                     AS total_rows,
    -- one block per recovered field (swap <field> and its <TARGET_TYPE>):
    LISTAGG(DISTINCT TYPEOF(d:<field>), ',')                                     AS <field>_variant_types,
    COUNT_IF(d:<field> IS NULL)                                                  AS <field>_absent,
    COUNT_IF(d:<field> IS NOT NULL
             AND TRY_CAST(d:<field>::STRING AS <TARGET_TYPE>) IS NULL)           AS <field>_uncoercible
FROM prep;
```

Decide, per field: any `_uncoercible > 0` → the rows don't share one recovery; **stop, list the
offending rows, and partition/scope**. Any `_absent > 0` → required→partition, optional→NULL.
Otherwise build the expression — the `::TYPE` casts will run clean because profiling confirmed every
value coerces. (`TRY_CAST(...::STRING AS <TYPE>)` mirrors the recovery cast without erroring.) Full
decision table: `reference/snowflake.md`.

## Recovery expression pattern (Phase 4) — build & confirm with the user

The shape depends on the failure **source** (from the drill-in). Cast each field with `::TYPE`. Read
the payload from **`failure_entry:data`** — the flattened failure element matching the schema being
recovered (the `prep` CTE in the test SELECT and generator below aliases it as `failure_entry`), not
`[0]`, so an event whose target failure isn't first is still read from the right element.

**contexts source** — reconstruct as a VARIANT **array of one object**. `_schema_version` is the first
key (the loader writes it into contexts objects):

```sql
ARRAY_CONSTRUCT(
    OBJECT_CONSTRUCT(
        '_schema_version', '1-0-0',                                                    -- corrected version
        'field1', failure_entry:data:field1::STRING,
        'field2', failure_entry:data:field2::INTEGER
    )
)
```

**unstruct source** — reconstruct as a **single `OBJECT_CONSTRUCT(...)`, no outer `ARRAY_CONSTRUCT`**
(the `unstruct_event_*` column is a single VARIANT object). Match a validated unstruct event's keys:
on the Databricks and BigQuery loaders the self-describing event object carries **no `_schema_version`**
(only contexts objects do), so omit it unless a validated event shows it:

```sql
OBJECT_CONSTRUCT(
    'field1', failure_entry:data:field1::STRING,
    'field2', failure_entry:data:field2::INTEGER
)
```

There is no strict struct-type matching in Snowflake (columns are VARIANT), so no field-order or
reserved-word concerns — the keys are plain string literals. Do **not** append `AS <column_name>` here
— the generator adds it. When embedding this into the generator query's string literal (Phase 7),
**double every single quote** (`'` → `''`).

## Test SELECT + type validation (Phase 4 — run and validate before the INSERT)

Emit this so the user can prove the reconstructed column is correct before any INSERT is generated.

**Build the reconstructed column in a CTE, then call `TYPEOF()` on its VARIANT fields** — do **not**
wrap `TYPEOF()` around a `::TYPE` cast. `TYPEOF()` only accepts a VARIANT, but `::TYPE` returns a
native scalar, so `TYPEOF(...:data:<field>::STRING)` fails with `Invalid argument types for function
'TYPEOF'`. Compute `recovered` first, then read its fields back with `TYPEOF(recovered[0]:<field>)`
(VARIANT navigation into the array you just built):

```sql
WITH prep AS (
    SELECT src.*, f.value AS failure_entry
    FROM <failed_database>.<failed_schema>.<failed_table> src,
         LATERAL FLATTEN(input => src.contexts_com_snowplowanalytics_snowplow_failure_1) f
    WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'
      AND app_id = '<app_id>'
      AND f.value:schema::STRING = '<failing_schema_uri>'
      -- add for a mixed-source schema: AND f.value:errors[0]:source::STRING = '<source>'
),
recovered_rows AS (
    SELECT
        event_id,
        <recovery expression> AS recovered
    FROM prep
)
SELECT
    event_id,
    recovered,
    -- contexts source (recovered is an ARRAY): TYPEOF(recovered[0]:field1)
    -- unstruct source (recovered is an OBJECT): TYPEOF(recovered:field1)  -- no [0]
    TYPEOF(recovered[0]:field1)        AS field1_type,
    TYPEOF(recovered[0]:field2)        AS field2_type
FROM recovered_rows
LIMIT 20;
```

`TYPEOF()` returns a VARIANT value's type as a string, e.g. `INTEGER`, `VARCHAR`, `BOOLEAN`. Because
Snowflake raises an error on a failed `::TYPE` cast, a test SELECT that runs at all already proves
the casts hold. For an **unstruct** run the reconstructed value is a single OBJECT, so read its fields
with `recovered:field` (no `[0]`). (Validation checklist: see
`reference/snowflake.md`.)

---

## INSERT-generator query (Phase 7 — Snowflake builds the INSERT itself)

This is the centrepiece of the Snowflake path — it builds the INSERT in-warehouse (as BigQuery does),
where the Athena and Databricks paths use a local Python script instead. It joins the good and failed
tables' `INFORMATION_SCHEMA.COLUMNS`, classifies each good-table column, and emits the **full INSERT
statement as a single text cell**. The user runs it, copies the returned statement, and runs that.

Fill in every `<placeholder>`. Note the doubled single quotes inside the generated string literals.
(How each column is classified: see `reference/snowflake.md`.)

```sql
WITH good_cols AS (
    SELECT ordinal_position, column_name, data_type
    FROM <good_database>.INFORMATION_SCHEMA.COLUMNS
    WHERE LOWER(table_schema) = LOWER('<good_schema>')
      AND LOWER(table_name)   = LOWER('<good_table>')
),
failed_cols AS (
    SELECT column_name
    FROM <failed_database>.INFORMATION_SCHEMA.COLUMNS
    WHERE LOWER(table_schema) = LOWER('<failed_schema>')
      AND LOWER(table_name)   = LOWER('<failed_table>')
),
mapping AS (
    SELECT
        g.ordinal_position,
        CASE
            WHEN LOWER(g.column_name) = 'contexts_com_snowplowanalytics_snowplow_failure_1'
                THEN 'CAST(NULL AS ' || g.data_type || ') AS ' || g.column_name
            WHEN LOWER(g.column_name) = 'load_tstamp'
                THEN 'CURRENT_TIMESTAMP() AS load_tstamp'
            WHEN LOWER(g.column_name) = LOWER('<recovery_column>')
                THEN '<recovery_expression_with_doubled_quotes> AS ' || g.column_name
            WHEN f.column_name IS NOT NULL
                THEN g.column_name
            ELSE 'CAST(NULL AS ' || g.data_type || ') AS ' || g.column_name
        END AS select_expression
    FROM good_cols g
    LEFT JOIN failed_cols f ON LOWER(g.column_name) = LOWER(f.column_name)
),
select_clause AS (
    SELECT LISTAGG(select_expression, ',\n    ')
             WITHIN GROUP (ORDER BY ordinal_position) AS columns_sql
    FROM mapping
)
SELECT
    'INSERT INTO <target_database>.<target_schema>.<target_table>\n'
    || 'WITH prep AS (\n'
    || '    SELECT src.*, f.value AS failure_entry\n'
    || '    FROM <failed_database>.<failed_schema>.<failed_table> src,\n'
    || '         LATERAL FLATTEN(input => src.contexts_com_snowplowanalytics_snowplow_failure_1) f\n'
    || '    WHERE load_tstamp::DATE > CURRENT_DATE - INTERVAL ''<days> DAY''\n'
    || '      AND app_id = ''<app_id>''\n'
    || '      AND f.value:schema::STRING = ''<failing_schema_uri>''\n'
    || '      AND f.value:errors[0]:source::STRING = ''<source>''\n'
    || ')\n'
    || 'SELECT\n    '
    || columns_sql
    || '\nFROM prep;' AS insert_statement
FROM select_clause;
```

Notes:
- `<target_*>` is the **staging** table (staging path) or the **good** table (direct path). Column
  classification always comes from the **good** table, so a staging table created `LIKE` the good
  table lines up positionally.
- The generated INSERT is **positional** (no explicit column list): the SELECT expressions are
  emitted in good-table `ordinal_position` order, so they land in the right columns.
- The `<recovery_expression_with_doubled_quotes>` is the Phase-4 recovery expression with every `'`
  replaced by `''`, because it lives inside a SQL string literal here. `<recovery_column>` is the
  `contexts_*` column for a contexts run or the `unstruct_event_*` column for an unstruct run (whose
  expression is the single `OBJECT_CONSTRUCT(...)`, no `ARRAY_CONSTRUCT`).
- `prep` **flattens** the failure array and keeps the element whose `schema` matches the one being
  recovered, aliased `failure_entry`. This recovers events where the target schema isn't the first
  failure element (reading `[0]` would skip them). The target schema appears once per event, so the
  flatten yields one row per recovered event — no fan-out.
- `<source>` scopes `prep` to one failure source — `contexts` or `unstruct`. A schema that failed both
  ways is two separate runs, one per source, each into its own column. Drop this predicate only when the
  drill-in showed a single source.
- Sibling entity columns (other `contexts_*`) **pass through** by name, so a valid entity the event
  also carried is preserved in the recovered row — not nulled.
- Before the user runs the generated INSERT, review it: recovery column carries the expression,
  failure column nulled, `load_tstamp` refreshed, and the column count matches the good table. If
  the recovery column wasn't matched (its expression is missing), check `<recovery_column>` against
  the good table's actual column name and regenerate.

---

## Staging-table patterns (Phase 6 / Phase 8 — staging write path)

### 1. Create an empty staging table that mirrors the good table

`LIKE` copies the exact column set, types, and order with zero rows:

```sql
CREATE TABLE <staging_database>.<staging_schema>.<staging_table>
    LIKE <good_database>.<good_schema>.<good_table>;
```

### 2. Recovery INSERT into staging

Same generated INSERT (above), but with `<target_*>` set to the staging table (column classification
still comes from the good table).

### 3. Validate the staging table

```sql
SELECT COUNT(*) AS rows_in_staging FROM <staging_database>.<staging_schema>.<staging_table>;

-- contexts source (ARRAY column):  SELECT event_id, <recovery_column>[0] ...
-- unstruct source (OBJECT column): SELECT event_id, <recovery_column>    ...  (no [0])
SELECT event_id, <recovery_column>
FROM <staging_database>.<staging_schema>.<staging_table>
LIMIT 10;
```

### 4. Promote staging → good table

Column order matches (staging was created `LIKE` good), so `SELECT *` is safe:

```sql
INSERT INTO <good_database>.<good_schema>.<good_table>
SELECT * FROM <staging_database>.<staging_schema>.<staging_table>;
```

### 5. (Optional) drop the staging table afterwards

```sql
DROP TABLE <staging_database>.<staging_schema>.<staging_table>;
```

### Direct-path time travel (compare before/after)

```sql
SELECT COUNT(*) FROM <good_table> AT (TIMESTAMP => '2024-01-15 12:00:00'::TIMESTAMP)
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
FROM <good_database>.<good_schema>.<good_table> g
WHERE g.load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'
  AND g.event_id IN (
    SELECT src.event_id
    FROM <failed_database>.<failed_schema>.<failed_table> src,
         LATERAL FLATTEN(input => src.contexts_com_snowplowanalytics_snowplow_failure_1) f
    WHERE src.load_tstamp::DATE > CURRENT_DATE - INTERVAL '<days> DAY'
      AND src.app_id = '<app_id>'
      AND f.value:schema::STRING = '<failing_schema_uri>'
  );
```

Any rows returned are the overlapping `event_id`s — decide with the user (stop, narrow scope, or
proceed knowingly).
