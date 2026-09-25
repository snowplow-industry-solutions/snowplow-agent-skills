# Recovery SQL templates — Databricks

Fill in every `<placeholder>`. These are the exact statements to hand the user at each phase; the
reasoning behind them lives in `reference/` and the failure modes in `troubleshooting.md`. The SQL here
is identical to the canonical recovery flow — do not paraphrase it.

All identifiers are Unity Catalog three-part names — `catalog.schema.table`. (Two-part
`schema.table` works if a default catalog is set, but prefer three-part so nothing is ambiguous.)

---

## Time window (applies to every query below)

Bounding `load_tstamp` scans far less data (and prunes files on the typically `load_tstamp`-clustered
tables). Ask the user in Phase 1 **when the failures occurred** and prefer a **bounded range**:

```sql
load_tstamp >= TIMESTAMP('2026-03-01') AND load_tstamp < TIMESTAMP('2026-03-10')
```

If the timeframe is unknown, fall back to a **lookback** (`DATE_SUB` takes an integer number of days):

```sql
DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
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
from the counts. `LATERAL VIEW explode` expands every element, so each failing schema is surfaced
wherever it sits in the array:

```sql
SELECT
    f.schema         AS failing_schema,
    app_id,
    f.failure_type   AS failure_type,
    COUNT(*)         AS failed_events,
    MIN(f.timestamp) AS first_seen,
    MAX(f.timestamp) AS last_seen
FROM <failed_catalog>.<failed_schema>.<failed_table>
     LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)  -- or a bounded range (see Time window)
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
    f.failure_type       AS failure_type,
    GET_JSON_OBJECT(f.errors[0], '$.source') AS source,  -- errors is ARRAY<STRING> → JSON-extract; contexts vs unstruct, a mix = separate runs (see reference/failure-context.md)
    f.errors             AS errors,
    f.data               AS data
FROM <failed_catalog>.<failed_schema>.<failed_table>
     LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)  -- or a bounded range
  AND f.schema = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

---

## Payload inspection query (Phase 3)

Expands the failure context with `LATERAL VIEW explode` so the user sees the real value behind each
field. Read `data` scalars with `GET_JSON_OBJECT` (they render as strings — the real target types
come from the recovery column's `full_data_type`).

```sql
SELECT
    f.schema                              AS failing_schema,
    GET_JSON_OBJECT(f.data, '$.field1')   AS field1,
    GET_JSON_OBJECT(f.data, '$.field2')   AS field2
FROM <failed_catalog>.<failed_schema>.<failed_table>
     LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
  AND f.schema = '<failing_schema_uri>'
  AND app_id = '<app_id>'
LIMIT 10;
```

Read the results for **how each value is encoded**, and note that a wrong path or un-castable value
can yield NULL rather than an error (see `reference/failure-context.md`). Expect failures to be
**compound** — a single schema's failed events can combine a renamed/missing field *and* a wrong
type. The real target types come from the recovery column's `full_data_type`.

---

## Finding the recovery column name and its type (Phase 4)

Snowplow materialises a custom entity into a column named
`contexts_<vendor>_<schema_name>_<major_version>`, with dots in the vendor replaced by underscores —
so `iglu:com.example/user_entity/jsonschema/2-0-1` *should* map to
`contexts_com_example_user_entity_2`. But casing and edge cases vary, and this is the
`<recovery_column>` placeholder used everywhere downstream, so **never confirm it from memory — have
the user run this and read the real name and `full_data_type` back**:

```sql
SELECT column_name, full_data_type
FROM <good_catalog>.information_schema.columns
WHERE table_schema = '<good_schema>' AND table_name = '<good_table>'
  AND lower(column_name) LIKE '%<schema_name_with_underscores>%'
ORDER BY column_name;
```

e.g. `LIKE '%user_entity%'`. The returned `column_name` is the exact `<recovery_column>`, and its
`full_data_type` (e.g. `ARRAY<STRUCT<_schema_version: STRING, user_id: BIGINT, user_name: STRING>>`)
is the struct contract the recovery expression must match. If several rows come back (multiple major
versions), pick the one whose trailing `_<major>` matches the schema version being recovered.

## Inspect a validated event (ground the target shape in the schema)

The repaired entity's shape and field types are defined by the Iglu schema and materialised in the
recovery column's type — not chosen. Cross-check by pulling a recent **validated** event of the same
entity from the **good** table. `<recovery_column>` is the entity column found above.

**contexts source** — the column is an `ARRAY<STRUCT<...>>`, so index element 0 and filter on `size`:

```sql
SELECT
    event_id,
    <recovery_column>[0] AS validated_entity
FROM <good_catalog>.<good_schema>.<good_table>
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)  -- recent sample; widen if 0 rows
  AND size(<recovery_column>) > 0
LIMIT 10;
```

**unstruct source** — the `unstruct_event_*` column is a **single `STRUCT<...>`, not an array**. Do
**not** use `[0]` or `size()` (both error on a struct). Read it directly and filter on `IS NOT NULL`:

```sql
SELECT
    event_id,
    <recovery_column> AS validated_entity
FROM <good_catalog>.<good_schema>.<good_table>
WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)  -- recent sample; widen if 0 rows
  AND <recovery_column> IS NOT NULL
LIMIT 10;
```

**Run this every time — don't assume the shape.** The recovery column's `full_data_type` is the
authoritative contract (field names, types, order, and whether `_schema_version` is a field); this query
confirms you read it correctly against a real row. Whether an unstruct column carries `_schema_version`
is settled by looking, not by defaulting.

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

Before writing any recovery expression, profile **every field you'll recover** across **all** failed
rows. This is also how you pre-empt Databricks' silent-NULL trap (a wrong path or un-castable value
becomes NULL, not an error) — confirm coercibility up front instead of discovering NULLs after the
write. The query can't error (`get_json_object`, `try_cast`, `count_if`). Add one block per field,
using that field's **target type** (from the recovery column's `full_data_type`) in the `try_cast`:

```sql
WITH prep AS (
    SELECT f.data AS d
    FROM <failed_catalog>.<failed_schema>.<failed_table>
         LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
    WHERE <load_tstamp window>
      AND f.schema = '<failing_schema_uri>'
      AND app_id = '<app_id>'
)
SELECT
    COUNT(*)                                                                          AS total_rows,
    -- one block per recovered field (swap <field> and its <TARGET_TYPE>):
    count_if(get_json_object(d, '$.<field>') IS NULL)                                 AS <field>_absent,
    count_if(get_json_object(d, '$.<field>') IS NOT NULL
             AND try_cast(get_json_object(d, '$.<field>') AS <TARGET_TYPE>) IS NULL)  AS <field>_uncoercible
FROM prep;
```

Decide, per field: any `_uncoercible > 0` → **stop, list the offending rows, and partition/scope**. Any
`_absent > 0` → required→partition, optional→NULL. Otherwise build the expression —
`CAST(GET_JSON_OBJECT(...) AS <type>)` will produce a value for every row (no silent NULLs) because
profiling confirmed coercibility. (Full decision table: `reference/databricks.md`.)

## Recovery expression pattern (Phase 4) — build & confirm with the user

The shape depends on the failure **source** (from the drill-in). Field names, types, and order must
match the recovery column's `full_data_type` exactly — read that type, don't assume. Extract each field
from the JSON `data` string with `GET_JSON_OBJECT`, then `CAST` to the target type. Read the payload
from **`f.data`** — the exploded failure element matching the schema being recovered (the `prep` CTE in
the test SELECT, null-count check, and generator below explodes the array and keeps the matching element
as `f`), not `[0]`, so an event whose target failure isn't first is still read from the right element.

**contexts source** — reconstruct as an **array of one struct**. Here `_schema_version` is the first
field (the `contexts_*` `full_data_type` lists it):

```sql
ARRAY(NAMED_STRUCT(
    '_schema_version', '1-0-0',  -- corrected version
    'user_id',   CAST(GET_JSON_OBJECT(f.data, '$.user_id')   AS BIGINT),
    'user_name', CAST(GET_JSON_OBJECT(f.data, '$.user_name') AS STRING)
))
```

**unstruct source** — reconstruct as a **single `NAMED_STRUCT`, no outer `ARRAY(...)`** (the
`unstruct_event_*` column is a bare `STRUCT`). Critically, the `unstruct_event_*` `full_data_type`
typically has **no `_schema_version` field** — so **omit it** unless the type actually lists it. Match
the type as-is:

```sql
NAMED_STRUCT(
    'nubmers',       CAST(GET_JSON_OBJECT(f.data, '$.nubmers')       AS BIGINT),
    'true_or_false', CAST(GET_JSON_OBJECT(f.data, '$.true_or_false') AS BOOLEAN),
    'words',         CAST(GET_JSON_OBJECT(f.data, '$.words')         AS STRING)
)
```

(Whichever source: the failed row's `data` still lives in the matched failure element, so extraction is
the same `GET_JSON_OBJECT(f.data, ...)` — only the target column and the wrapper differ.)

`STRUCT(CAST(...) AS user_id, ...)` (positional fields with `AS name`) is an equivalent form, but
`NAMED_STRUCT` makes the field names explicit and is preferred. Do **not** append `AS <column_name>`
here — the generator adds it. When embedding this into the in-warehouse generator query (Phase 7
fallback), it is placed inside a **single-quoted** string literal, so **backslash-escape every single
quote** inside the expression (`'1-0-0'` → `\'1-0-0\'`, `'$.user_id'` → `\'$.user_id\'`). Spark has no
`''` escape — a doubled quote coalesces and the quote disappears.

## Test SELECT (Phase 4 — run and validate before the INSERT)

Emit this so the user can prove the reconstructed column is correct before any INSERT is generated.

```sql
WITH prep AS (
    SELECT *
    FROM <failed_catalog>.<failed_schema>.<failed_table>
         LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
      AND app_id = '<app_id>'
      AND f.schema = '<failing_schema_uri>'
)
SELECT
    event_id,
    <recovery expression> AS recovered
FROM prep
LIMIT 20;
```

**A clean run does not prove correctness in Databricks** (see "Silent NULLs" in
`reference/failure-context.md`). Inspect the `recovered` values directly, and run the optional
per-field null-count check below to catch a wrong path or an un-castable value.

## Optional per-field null-count check (catches silent NULLs)

Because bad paths/casts can yield NULL rather than an error, count how many recovered rows are NULL
in each reconstructed field. **Expect 0** for every required field.

```sql
WITH prep AS (
    SELECT f.data AS d
    FROM <failed_catalog>.<failed_schema>.<failed_table>
         LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
      AND app_id = '<app_id>'
      AND f.schema = '<failing_schema_uri>'
)
SELECT
    COUNT(*)                                                                            AS total_rows,
    SUM(CASE WHEN CAST(GET_JSON_OBJECT(d, '$.user_id')   AS BIGINT) IS NULL THEN 1 ELSE 0 END) AS null_user_id,
    SUM(CASE WHEN CAST(GET_JSON_OBJECT(d, '$.user_name') AS STRING) IS NULL THEN 1 ELSE 0 END) AS null_user_name
FROM prep;
```

A non-zero count on a required field means a wrong JSON path or a genuinely bad value — fix before
proceeding. (A nullable/optional field may legitimately be NULL; judge against the schema.)

---

## Generate the INSERT with the local script (Phase 7 — PRIMARY)

The good table has ~130 columns and the INSERT is positional, so the column list and order come from
metadata. `scripts/generate_insert_databricks.py` assembles the whole statement **locally** in Python and writes it
to a `.sql` file — the SQL never passes through a string-literal layer, so there are no single quotes to
escape and nothing can silently coalesce away (see the fallback caveat below for why that matters).

### Step 1 — column-metadata queries (the user runs both, pastes each result)

These return plain `column_name, full_data_type` in ordinal order — no quotes to strip, so the copy is
lossless. Run **once against the good table, once against the failed table**. Any of Databricks' copy
formats works — **plain text, CSV, or markdown**: the script auto-detects the delimiter (tab, comma
with quoted types, or `|` table) and skips the header/separator row, so you don't have to pick one. If
a paste can't be parsed it errors with `no columns parsed` rather than dropping rows silently.

```sql
-- GOOD table columns
SELECT column_name, full_data_type
FROM <good_catalog>.information_schema.columns
WHERE table_schema = '<good_schema>' AND table_name = '<good_table>'
ORDER BY ordinal_position;
```

```sql
-- FAILED table columns
SELECT column_name, full_data_type
FROM <failed_catalog>.information_schema.columns
WHERE table_schema = '<failed_schema>' AND table_name = '<failed_table>'
ORDER BY ordinal_position;
```

### Step 2 — run the script

Save the two pastes (`good_columns.txt`, `failed_columns.txt`), the validated Phase-4 recovery
expression (`recovery_expression.sql`, **single quotes stay single** — it is *not* embedded in a
string literal here, so do **not** escape them), and a `config.json`:

```json
{
  "GOOD_CATALOG": "<good_catalog>", "GOOD_SCHEMA": "<good_schema>", "GOOD_TABLE": "<good_table>",
  "FAILED_CATALOG": "<failed_catalog>", "FAILED_SCHEMA": "<failed_schema>", "FAILED_TABLE": "<failed_table>",
  "RECOVERY_COLUMN": "<recovery_column>",
  "FAILING_SCHEMA_URI": "<failing_schema_uri>",
  "APP_ID": "<app_id>",
  "DAYS_LOOKBACK": <days>,
  "FAILURE_SOURCE": "<contexts|unstruct>",
  "TARGET_CATALOG": "<target_catalog>", "TARGET_SCHEMA": "<target_schema>", "TARGET_TABLE": "<target_table>"
}
```

`RECOVERY_COLUMN` is the `contexts_*` column for a **contexts** run or the `unstruct_event_*` column for
an **unstruct** run — the same column whose `full_data_type` you matched in Phase 4. `FAILURE_SOURCE`
(`contexts` or `unstruct`) scopes `prep` to that source, so a schema that failed both ways recovers one
source per run into its own column; omit it only when the drill-in showed a single source. `TARGET_*` is
optional (defaults to `GOOD_*`); set it to the **staging** table for the staging path. For a bounded
window instead of a lookback, drop `DAYS_LOOKBACK` and set `"LOAD_TSTAMP_START": "<start>"` (and
optionally `"LOAD_TSTAMP_END": "<end>"`). Then:

```bash
python3 scripts/generate_insert_databricks.py \
    --config config.json \
    --good-columns good_columns.txt \
    --failed-columns failed_columns.txt \
    --recovery-expr recovery_expression.sql \
    --out recovery.sql
```

It prints a sanity summary to stderr (good/failed column counts, pass-through, nulled) and writes the
runnable INSERT to `recovery.sql`. If it warns the recovery column wasn't found, `RECOVERY_COLUMN`
doesn't match the good table — fix it and re-run. Review `recovery.sql` with the user (recovery column
carries the expression, failure column nulled, `load_tstamp` refreshed, positional order matches the
good table), then have them run it.

The script classifies each good-table column identically to the in-warehouse generator below: recovery
column → the expression; `load_tstamp` → `CURRENT_TIMESTAMP()`; failure column → `CAST(NULL AS <type>)`;
present in failed table → pass-through; good-only → `CAST(NULL AS <type>)`. (Rationale:
`reference/databricks.md`.)

---

## In-warehouse INSERT-generator query (Phase 7 — FALLBACK, no local Python)

> **Use this only when the user can't run the local script.** It joins the good and failed tables'
> `INFORMATION_SCHEMA.COLUMNS`, classifies each column, and emits the **full INSERT as a single text
> cell** for the user to copy and run. **The catch:** the whole INSERT is built as one Spark string
> literal, so every single quote in the payload must be **backslash-escaped** (`\'`). Spark has no `''`
> escape — a doubled quote coalesces into nothing, so `app_id = ''test-app''` emits as `app_id = test-app`
> and won't parse, with no error to warn you. Get one escape wrong and the statement silently loses a
> quote. The local script above sidesteps this entirely, so prefer it whenever Python is available.

Fill in every `<placeholder>`. The recovery expression is embedded inside a **single-quoted** string
literal, so **every single quote inside it must be backslash-escaped** (`\'`) — this escaping is *only*
for this in-warehouse form; the script path takes the expression with its single quotes unchanged.
`array_sort` orders the
emitted expressions by `ordinal_position` (its first struct field) so the INSERT is positional and
lines up with the good table — `collect_list` alone does not guarantee order. (How each column is
classified: see `reference/databricks.md`.)

```sql
WITH good_cols AS (
    SELECT ordinal_position, column_name, full_data_type
    FROM <good_catalog>.information_schema.columns
    WHERE table_schema = '<good_schema>' AND table_name = '<good_table>'
),
failed_cols AS (
    SELECT column_name
    FROM <failed_catalog>.information_schema.columns
    WHERE table_schema = '<failed_schema>' AND table_name = '<failed_table>'
),
mapping AS (
    SELECT
        g.ordinal_position,
        CASE
            WHEN lower(g.column_name) = 'contexts_com_snowplowanalytics_snowplow_failure_1'
                THEN concat('CAST(NULL AS ', g.full_data_type, ') AS ', g.column_name)
            WHEN lower(g.column_name) = 'load_tstamp'
                THEN 'CURRENT_TIMESTAMP() AS load_tstamp'
            WHEN lower(g.column_name) = lower('<recovery_column>')
                THEN '<recovery_expression> AS <recovery_column>'
            WHEN f.column_name IS NOT NULL
                THEN g.column_name
            ELSE concat('CAST(NULL AS ', g.full_data_type, ') AS ', g.column_name)
        END AS select_expression
    FROM good_cols g
    LEFT JOIN failed_cols f ON lower(g.column_name) = lower(f.column_name)
),
select_clause AS (
    SELECT array_join(
        transform(
            array_sort(collect_list(named_struct('pos', ordinal_position, 'expr', select_expression))),
            x -> x.expr
        ),
        ',\n    '
    ) AS columns_sql
    FROM mapping
)
SELECT concat(
    'INSERT INTO <target_catalog>.<target_schema>.<target_table>\n',
    'WITH prep AS (\n',
    '  SELECT *\n',
    '  FROM <failed_catalog>.<failed_schema>.<failed_table>\n',
    '       LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f\n',
    '  WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)\n',
    '    AND app_id = \'<app_id>\'\n',
    '    AND f.schema = \'<failing_schema_uri>\'\n',
    -- mixed-source schema only: scope prep to the source being recovered, exactly as the
    -- primary script's FAILURE_SOURCE does. Omit if the drill-in showed a single source.
    '    AND GET_JSON_OBJECT(f.errors[0], \'$.source\') = \'<source>\'\n',
    ')\n',
    'SELECT\n    ',
    columns_sql,
    '\nFROM prep;'
) AS generated_sql
FROM select_clause;
```

Notes:
- `<target_*>` is the **staging** table (staging path) or the **good** table (direct path). Column
  classification always comes from the **good** table, so a staging table created with `SELECT * … LIMIT 0`
  lines up positionally.
- `prep` **explodes** the failure array and keeps the element whose `schema` matches the one being
  recovered, aliased `f`. This recovers events where the target schema isn't the first failure element
  (reading `[0]` would skip them); the recovery expression reads its payload from `f.data`. For a
  **single-source** schema the explode yields one row per recovered event. A schema that failed **both**
  ways carries two entries for the same URI on one event (one `contexts`, one `unstruct`), which would
  fan out to two rows and insert that `event_id` twice — keep the `<source>` predicate above for those,
  and recover one source per run into its own column.
- The generated INSERT is **positional** (no explicit column list): the SELECT expressions are
  emitted in good-table `ordinal_position` order, so they land in the right columns. This is why the
  recovery struct's field order should match the target type.
- `<recovery_expression>` is the validated Phase-4 expression with **every single quote backslash-escaped**
  (`\'`), inserted verbatim inside the single-quoted CASE branch; `<recovery_column>` is the entity column name.
- Before the user runs the generated INSERT, review it: recovery column carries the expression,
  failure column nulled, `load_tstamp` refreshed, and the column count matches the good table. If the
  recovery column wasn't matched (its expression is missing), check `<recovery_column>` against the
  good table's actual column name and regenerate.
- **If `CAST(NULL AS <full_data_type>)` for the failure column is rejected** (its full nested type is
  unusual), fall back to a simplified null of a compatible shape — e.g.
  `CAST(NULL AS ARRAY<STRUCT<schema:STRING, data:STRING>>)` — or give the INSERT an explicit column
  list that omits the failure column entirely. Diagnostics: `troubleshooting.md`.

---

## Staging-table patterns (Phase 6 / Phase 8 — staging write path)

### 1. Create an empty staging table that mirrors the good table

CTAS with `LIMIT 0` copies the exact column set, types, and order with zero rows:

```sql
CREATE TABLE <staging_catalog>.<staging_schema>.<staging_table> AS
SELECT * FROM <good_catalog>.<good_schema>.<good_table> LIMIT 0;
```

(`CREATE TABLE <staging> LIKE <good>` is an equivalent alternative on Databricks.)

### 2. Recovery INSERT into staging

Same generated INSERT, but with `<target_*>` set to the staging table (column classification still
comes from the good table).

### 3. Validate the staging table

```sql
SELECT COUNT(*) AS rows_in_staging FROM <staging_catalog>.<staging_schema>.<staging_table>;

-- contexts source (ARRAY column):  SELECT event_id, <recovery_column>[0] ...
-- unstruct source (STRUCT column): SELECT event_id, <recovery_column>    ...  (no [0])
SELECT event_id, <recovery_column>
FROM <staging_catalog>.<staging_schema>.<staging_table>
LIMIT 10;
```

### 4. Promote staging → good table

Column order matches (staging was created with `SELECT * … LIMIT 0`), so `SELECT *` is safe:

```sql
INSERT INTO <good_catalog>.<good_schema>.<good_table>
SELECT * FROM <staging_catalog>.<staging_schema>.<staging_table>;
```

### 5. (Optional) drop the staging table afterwards

```sql
DROP TABLE <staging_catalog>.<staging_schema>.<staging_table>;
```

### Direct-path time travel (compare before/after)

Delta time travel compares the good table before/after the INSERT (or use `VERSION AS OF <n>`):

```sql
SELECT COUNT(*) FROM <good_table> TIMESTAMP AS OF '2024-01-15T12:00:00'
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
FROM <good_catalog>.<good_schema>.<good_table> g
WHERE DATE(g.load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
  AND g.event_id IN (
    SELECT event_id
    FROM <failed_catalog>.<failed_schema>.<failed_table>
         LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f
    WHERE DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), <days>)
      AND app_id = '<app_id>'
      AND f.schema = '<failing_schema_uri>'
  );
```

Any rows returned are the overlapping `event_id`s — decide with the user (stop, narrow scope, or
proceed knowingly).
