# Worked example — recovering a string-typed field back to BIGINT

A complete, realistic run of the flow end to end, so you can see how the phases connect and what the
intermediate outputs look like. **This is an illustration, not a template to copy** — the table
names, schema, and field types are specific to this case. For the reusable statements with
placeholders, use `templates/databricks.md`; for the reasoning, `reference/`.

## The scenario

- **Failed table:** `acme_prod.atomic_failed.events`
- **Good table:** `acme_prod.atomic.events`
- **Failing schema:** `iglu:com.acme/user_entity/jsonschema/1-0-0`
- **app_id:** `web`
- **When:** failures started ~2026-03-02, so we bound to `2026-03-01`–`2026-03-10`.
- **The bug:** the tracker sent `user_id` as a **string** (`"1042"`) and `account_age_days` as a
  string (`"365"`), but the schema (and the good-table column) type them as `BIGINT`. `user_name` was
  always a valid string. So two of three fields need a string→BIGINT coercion.

The good-table entity column and its type (from the Phase 4 lookup) turn out to be:

```
column_name    = contexts_com_acme_user_entity_1
full_data_type = ARRAY<STRUCT<_schema_version: STRING, user_id: BIGINT, user_name: STRING, account_age_days: BIGINT>>
```

That `full_data_type` is the contract the reconstruction must match field-for-field.

## Phase 2 — identify

Summary query returns (abridged):

| failing_schema | app_id | failure_type | failed_events | first_seen | last_seen |
|---|---|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | web | SchemaViolation | 3,418 | 2026-03-02 08:14 | 2026-03-09 23:51 |

We pick that schema. The row-level drill-in shows `errors` complaining that `user_id` is a string
where integer is expected — our hypothesis. Duplicate pre-check returns **0** (never recovered).

## Phase 3 — inspect the payload

Payload-inspection query (`LATERAL VIEW explode` + `GET_JSON_OBJECT(f.data, '$.<field>')`) returns
real values:

| failing_schema | user_id | user_name | account_age_days |
|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | 1042 | ada.lovelace | 365 |
| iglu:com.acme/user_entity/jsonschema/1-0-0 | 1043 | alan.turing | 410 |

`GET_JSON_OBJECT` renders every scalar as a string, so this sample only orients us — a clean render
here does **not** prove the values will cast, because Databricks NULLs silently. We profile before
choosing anything.

## Phase 3.5 — profile & confirm coercibility

The field profiling query (one block per field, target types from `full_data_type`) returns across
all 3,418 rows:

| field | absent | uncoercible (→ target) |
|---|---|---|
| user_id | 0 | 0 → BIGINT |
| account_age_days | 0 | 0 → BIGINT |
| user_name | 0 | 0 → STRING |

Every field is present in every row and 0 uncoercible → the whole population shares one recovery, and
`CAST(GET_JSON_OBJECT(...) AS <type>)` will produce a value for every row with no silent NULLs. If any
field had shown `_uncoercible > 0`, we would have stopped and partitioned instead of assuming.

## Phase 4 — recovery expression + test SELECT

Built to match `full_data_type` exactly (order: `_schema_version`, `user_id`, `user_name`,
`account_age_days`), extracting each field from the JSON `data` string and casting to its target type:

```sql
ARRAY(NAMED_STRUCT(
    '_schema_version', '1-0-0',
    'user_id',          CAST(GET_JSON_OBJECT(f.data, '$.user_id')          AS BIGINT),
    'user_name',        CAST(GET_JSON_OBJECT(f.data, '$.user_name')        AS STRING),
    'account_age_days', CAST(GET_JSON_OBJECT(f.data, '$.account_age_days') AS BIGINT)
))
```

The test SELECT wraps this over the failed rows (its `prep` CTE `LATERAL VIEW explode`s the failure
array and keeps the element matching the schema, as `f`, so an event whose target failure isn't first
is still recovered). Because a clean run is **not** proof in Databricks,
we inspect the values and run the per-field null-count check (all required fields return 0). Output
spot-check:

| event_id | recovered |
|---|---|
| 5f3c…a1 | [{_schema_version:"1-0-0", user_id:1042, user_name:"ada.lovelace", account_age_days:365}] |
| 7b90…c4 | [{_schema_version:"1-0-0", user_id:1043, user_name:"alan.turing", account_age_days:410}] |

## Phase 5 — validate (gate)

- No unexpected NULLs ✅ (per-field null-count check returned 0 for every required field; profiling
  had already confirmed coercibility)
- `user_id` is now `1042` (integer), not `"1042"`; pass-through fields intact ✅
- Struct shape = `_schema_version, user_id BIGINT, user_name STRING, account_age_days BIGINT`, matches
  `full_data_type`, `_schema_version` first ✅
- Row count 3,418 = identification count ✅

Gate passes.

## Phase 6 — write path

Chose **staging** (recommended). Created it as an exact mirror:

```sql
CREATE TABLE acme_prod.atomic.events_recovery_staging AS
SELECT * FROM acme_prod.atomic.events LIMIT 0;
```

## Phase 7 — generate the INSERT (local script)

Had the user run the two column-metadata queries (good and failed
`information_schema.columns`, `ORDER BY ordinal_position`) and pasted each result — plain
`column_name, full_data_type`, so nothing was lost in the copy. Saved those as `good_columns.txt` /
`failed_columns.txt`, the validated expression as `recovery_expression.sql` (single quotes left
single — no escaping), and a `config.json` with `TARGET_* = acme_prod.atomic.events_recovery_staging`,
`RECOVERY_COLUMN = contexts_com_acme_user_entity_1`, and the same window/app_id/schema. Then:

```bash
python3 scripts/generate_insert_databricks.py --config config.json \
    --good-columns good_columns.txt --failed-columns failed_columns.txt \
    --recovery-expr recovery_expression.sql --out recovery.sql
```

The stderr summary confirmed the column counts (and that the recovery column was matched). `recovery.sql`
was a positional `INSERT ... WITH prep AS (...) SELECT ...` where the failure column is
`CAST(NULL AS ...)`, `load_tstamp` is `CURRENT_TIMESTAMP()`, `contexts_com_acme_user_entity_1` carries
the `ARRAY(NAMED_STRUCT(...))`, atomic columns pass through, and good-only columns are `CAST(NULL AS ...)`.
Reviewed it, column count matched the good table. (The in-warehouse generator was avoided because it
builds the INSERT as a Spark string literal that needs every quote backslash-escaped — see
`troubleshooting.md`.)

## Phase 8 — run, validate, promote

Ran the INSERT into staging → 3,418 rows. Spot-checked `contexts_com_acme_user_entity_1[0]` in
staging: correct. Promoted:

```sql
INSERT INTO acme_prod.atomic.events
SELECT * FROM acme_prod.atomic.events_recovery_staging;
```

Re-validated the good table (row count + spot-check, optionally comparing before/after with
`TIMESTAMP AS OF`), then dropped the staging table.

## What this example demonstrates

- The `full_data_type` — not the payload — dictates field names, types, and order.
- Profiling first (not the `LIMIT 10` sample) is what let us proceed confidently: it confirmed every
  value coerces, pre-empting Databricks' silent-NULL trap. A clean test run alone would not have
  proven anything.
- Had profiling shown `uncoercible > 0` on any field, the population would *not* have shared one
  recovery — the flow would stop and partition instead of assuming.
- Fields that were already valid (`user_name`) still get carried through the reconstruction; you
  don't only rebuild the broken ones.
- Staging + duplicate pre-check keep the write safe and idempotent.
