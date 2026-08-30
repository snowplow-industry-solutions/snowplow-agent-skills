# Worked example — recovering a string-typed field back to BIGINT

A complete, realistic run of the flow end to end, so you can see how the phases connect and what the
intermediate outputs look like. **This is an illustration, not a template to copy** — the table
names, schema, and field types are specific to this case. For the reusable statements with
placeholders, use `templates/athena.md`; for the reasoning, `reference/`.

## The scenario

- **Failed table:** `atomic_failed.events`
- **Good table:** `atomic.events`
- **Failing schema:** `iglu:com.acme/user_entity/jsonschema/1-0-0`
- **app_id:** `web`
- **When:** failures started ~2026-03-02, so we bound to `2026-03-01`–`2026-03-10`.
- **The bug:** the tracker sent `user_id` as a **string** (`"1042"`) and `account_age_days` as a
  string (`"365"`), but the schema (and the good-table column) type them as `BIGINT`. `user_name` was
  always a valid string. So two of three fields need a string→BIGINT coercion.

The good-table `DESCRIBE` (Phase 4) shows the recovery column and its Hive type:

```
contexts_com_acme_user_entity_1   array<struct<_schema_version:string,user_id:bigint,user_name:string,account_age_days:bigint>>
```

Converted to Athena types, the target the reconstruction must match is
`array(row(_schema_version varchar, user_id bigint, user_name varchar, account_age_days bigint))`.

## Phase 2 — identify

Summary query returns (abridged):

| failing_schema | app_id | failure_type | failed_events | first_seen | last_seen |
|---|---|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | web | SchemaViolation | 3,418 | 2026-03-02 08:14 | 2026-03-09 23:51 |

We pick that schema. The row-level drill-in shows `errors` complaining that `user_id` is a string
where integer is expected — our hypothesis. Duplicate pre-check returns **0** (never recovered). It's
a custom schema, so we also ask the user for the Iglu JSON to sanity-check field names/types.

## Phase 3 — inspect the payload

Payload-inspection query (`UNNEST` + `json_extract_scalar(failure_ctx.data, '$.<field>')`) returns
real values:

| failing_schema | user_id | user_name | account_age_days |
|---|---|---|---|
| iglu:com.acme/user_entity/jsonschema/1-0-0 | 1042 | ada.lovelace | 365 |
| iglu:com.acme/user_entity/jsonschema/1-0-0 | 1043 | alan.turing | 410 |

`json_extract_scalar` returns everything as text, so the `LIMIT 10` sample orients us but doesn't tell
us the underlying JSON encoding on its own — we profile before choosing.

## Phase 3.5 — profile & confirm coercibility

The field profiling query (one block per field, target types from the DESCRIBE) returns across all
3,418 rows:

| field | absent | uncoercible (→ target) |
|---|---|---|
| user_id | 0 | 0 → BIGINT |
| account_age_days | 0 | 0 → BIGINT |
| user_name | 0 | 0 → VARCHAR |

Every field is present in every row and 0 uncoercible → the whole population shares one recovery.
`CAST(json_extract_scalar(...) AS BIGINT)` will coerce the string-encoded integers, and
`CAST(... AS VARCHAR)` carries `user_name` through.

## Phase 4 — recovery expression + test SELECT

Built to match the good-table struct exactly (order: `_schema_version`, `user_id`, `user_name`,
`account_age_days`) as `CAST(ARRAY[ROW(...)] AS ARRAY(ROW(...)))`:

```sql
CAST(
    ARRAY[
        ROW(
            '1-0-0',                                                          -- corrected _schema_version
            CAST(json_extract_scalar(failure_data, '$.user_id') AS BIGINT),
            CAST(json_extract_scalar(failure_data, '$.user_name') AS VARCHAR),
            CAST(json_extract_scalar(failure_data, '$.account_age_days') AS BIGINT)
        )
    ]
AS ARRAY(ROW(_schema_version VARCHAR, user_id BIGINT, user_name VARCHAR, account_age_days BIGINT)))
```

The test SELECT wraps this in the `prep` + `unnested` CTEs and adds `typeof(...)`. Output spot-check:

| event_id | recovered | recovered_type |
|---|---|---|
| 5f3c…a1 | [{_schema_version=1-0-0, user_id=1042, user_name=ada.lovelace, account_age_days=365}] | array(row(_schema_version varchar, user_id bigint, user_name varchar, account_age_days bigint)) |

## Phase 5 — validate (gate)

- `recovered_type` = `array(row(_schema_version varchar, user_id bigint, user_name varchar, account_age_days bigint))`, matches the good-table column type field-for-field ✅ (decisive)
- Row count 3,418 = identification count ✅
- No unexpected nulls ✅
- `user_id` is now `1042` (integer), not `"1042"` ✅

Gate passes.

## Phase 6 — write path

Chose **staging** (recommended). Created it as an exact mirror (asked the user for an S3 location):

```sql
CREATE TABLE atomic.events_recovery_staging
WITH (
    table_type = 'ICEBERG',
    location = 's3://acme-recovery/events_recovery_staging/',
    is_external = false
)
AS SELECT * FROM atomic.events WHERE 1 = 0;
```

## Phase 7 — generate the INSERT

Wrote `config.json` (with `TARGET_DATABASE`/`TARGET_TABLE` = the staging table), `good_describe.txt`,
`failed_describe.txt`, and `recovery_expression.sql` (the validated expression, no trailing `AS`), then
ran `python3 scripts/generate_insert_athena.py`. It printed the full INSERT — failure column excluded,
`load_tstamp` = `current_timestamp`, `contexts_com_acme_user_entity_1` carrying the
`CAST(ARRAY[ROW(...)] ...)`, atomic columns passed through, good-only custom columns `CAST(NULL AS
...)` — and a sanity summary to stderr (`good columns: N | failed columns: M | custom pass-through: P
| custom nulled: Q`). Reviewed it; column count matched the good table.

## Phase 8 — run, validate, promote

Ran the INSERT into staging → 3,418 rows. Spot-checked `contexts_com_acme_user_entity_1[1]` in
staging: correct. Promoted:

```sql
INSERT INTO atomic.events
SELECT * FROM atomic.events_recovery_staging;
```

Re-validated the good table (row count + spot-check), then dropped the staging table.

## What this example demonstrates

- The good-table `DESCRIBE` — not the payload — dictates field names, types, and order; the
  reconstruction is `CAST(ARRAY[ROW(...)] AS ARRAY(ROW(...)))`, never the DDL `ARRAY<STRUCT<...>>`.
- Profiling first (not the `LIMIT 10` sample) is what let us confirm the population shared one
  recovery before suggesting an expression — no `TRY_CAST` in the expression itself, no silent NULLs.
- Had profiling shown `uncoercible > 0` on any field, the flow would stop and partition instead of
  assuming.
- Fields that were already valid (`user_name`) still get carried through the reconstruction.
- `typeof()` matching the good-table type is the decisive gate: if it matches, the INSERT type-checks.
- Staging + duplicate pre-check keep the write safe and idempotent.
